#!/usr/bin/env python3
"""READ-ONLY inventory discovery against the netcup SCP REST API.

Purpose
-------
Answer the questions blocking the netcup k3s build with evidence rather than
assumption:

  * which servers exist, and their SCP server IDs
  * whether a Cloud vLAN is attached to each
  * the REAL vLAN MTU, read off the interface -- not inherited from Hetzner's
    host 1400 / cilium_mtu 1360, which derive from Hetzner's 1450 private
    network and do not transfer
  * the current IPv4 layout per interface
  * the imageFlavourId for Ubuntu 24.04, for parity with the Hetzner pin in
    terraform/environments/prod/main.tf (its Ubuntu image data source)

Safety
------
Performs GET requests ONLY. The sole non-GET calls are the OAuth2 token
exchanges against Keycloak, which are authentication, not mutation. This
script cannot create, reinstall, power-cycle, or delete anything; `api_get`
refuses any other method by construction.

Authentication
--------------
netcup issues no static API token, so this uses the OAuth2 device-code flow:

  first run (interactive) : prints a URL and code to approve in a browser
  later runs / CI         : reuses the cached offline refresh token

The offline refresh token does not expire while used at least once every 30
days. For CI, pass it via SCP_REFRESH_TOKEN and no browser is involved.

Usage
-----
    python3 scripts/netcup-discover.py
    python3 scripts/netcup-discover.py -o discovery.json
    SCP_REFRESH_TOKEN=... python3 scripts/netcup-discover.py
    NETCUP_USER_ID=12345 python3 scripts/netcup-discover.py

Requires Python 3.8+. Standard library only -- no curl, no jq, no pip installs.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SCP_BASE = "https://www.servercontrolpanel.de"
API = f"{SCP_BASE}/scp-core/api/v1"
OIDC = f"{SCP_BASE}/realms/scp/protocol/openid-connect"
CLIENT_ID = "scp"

# Spec version this script was written against. netcup support does not
# support their own API and may change endpoints without notice, so drift is
# surfaced as a warning to re-verify rather than passing silently.
PINNED_SPEC_VERSION = "2026.0909.114758"

DEFAULT_TOKEN_CACHE = Path.home() / ".config" / "veridex" / "netcup-refresh-token"
HTTP_TIMEOUT = 30
# Fallback only. The real deadline comes from the device authorization
# response's `expires_in`, so the poll window matches however long netcup
# actually honours the user_code rather than a guess that expires early.
DEVICE_EXPIRES_FALLBACK = 600

RULE_WIDTH = 78


class DiscoveryError(RuntimeError):
    """Fatal, user-actionable problem."""


# Keycloak access tokens here live ~5 minutes. Any operation that outlives
# that -- installing an OS across a fleet, for instance -- will hit HTTP 401
# partway through and abandon the remaining work. Holding the refresh token
# centrally lets every call transparently re-mint an access token instead.
_AUTH: dict[str, object] = {"cache": None, "token": None}


def current_token() -> str:
    tok = _AUTH.get("token")
    if not tok:
        raise DiscoveryError("not authenticated; call authenticate() first")
    return str(tok)


def refresh_access_token() -> str:
    """Re-mint an access token from the stored refresh token."""
    cache = _AUTH.get("cache")
    if not cache:
        raise DiscoveryError("no token cache recorded; cannot refresh")
    return authenticate(Path(str(cache)))


def log(msg: str = "") -> None:
    print(msg, file=sys.stderr)


def warn(msg: str) -> None:
    print(f"WARN: {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _request(
    url: str,
    *,
    method: str,
    data: dict[str, str] | None = None,
    token: str | None = None,
) -> tuple[int, str]:
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        raise DiscoveryError(f"network failure calling {url}: {exc.reason}") from exc


def post_form(url: str, data: dict[str, str]) -> tuple[int, Any]:
    status, text = _request(url, method="POST", data=data)
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, {"raw": text}


def api_get(path: str, token: str | None = None, _retried: bool = False) -> Any:
    """GET an API path. Any other verb is unreachable from here by design."""
    if not path.startswith("/"):
        raise DiscoveryError(f"api_get: path must start with '/' (got {path!r})")
    token = token or current_token()
    status, text = _request(f"{API}{path}", method="GET", token=token)
    if status == 401 and not _retried and _AUTH.get("cache"):
        # Access token aged out mid-operation; re-mint and retry once.
        return api_get(path, refresh_access_token(), _retried=True)
    if status == 200:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise DiscoveryError(f"GET {path} returned non-JSON: {text[:200]}") from exc
    if status in (401, 403):
        raise DiscoveryError(f"GET {path} -> HTTP {status}: token rejected or insufficient scope")
    if status == 404:
        warn(f"GET {path} -> HTTP 404 (not found)")
        return None
    if status == 429:
        raise DiscoveryError(f"GET {path} -> HTTP 429: rate limited, retry later")
    raise DiscoveryError(f"GET {path} -> HTTP {status}: {text[:300]}")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
def save_refresh_token(cache: Path, token: str) -> None:
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(token + "\n", encoding="utf-8")
    try:
        cache.chmod(0o600)
    except OSError:
        pass  # best effort; Windows filesystems may not honour this


def device_login(cache: Path) -> str:
    log("No cached credential. Starting netcup device-code login.")
    status, resp = post_form(
        f"{OIDC}/auth/device",
        {"client_id": CLIENT_ID, "scope": "offline_access openid"},
    )
    if status != 200 or "device_code" not in resp:
        raise DiscoveryError(f"device authorization request failed (HTTP {status}): {resp}")

    device_code = resp["device_code"]
    interval = int(resp.get("interval", 5))
    expires_in = int(resp.get("expires_in", DEVICE_EXPIRES_FALLBACK))
    deadline = time.monotonic() + expires_in

    log("")
    log(f"  Open:  {resp.get('verification_uri')}")
    log(f"  Code:  {resp.get('user_code')}")
    if resp.get("verification_uri_complete"):
        log(f"  Or go straight to: {resp['verification_uri_complete']}")
    log("")
    log(f"Waiting for approval (code valid for {expires_in // 60}m{expires_in % 60:02d}s)...")

    while time.monotonic() < deadline:
        time.sleep(interval)
        _, tok = post_form(
            f"{OIDC}/token",
            {
                "client_id": CLIENT_ID,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
            },
        )
        if tok.get("refresh_token"):
            save_refresh_token(cache, tok["refresh_token"])
            log(f"Approved. Offline refresh token cached at {cache}")
            return tok["refresh_token"]
        err = tok.get("error", "")
        if err == "slow_down":
            interval += 5
        elif err == "expired_token":
            break
        elif err not in ("authorization_pending", ""):
            raise DiscoveryError(f"device login failed: {err}")

    raise DiscoveryError(
        f"device login not approved within {expires_in}s, so the code expired.\n"
        "Re-run to get a fresh code and approve it in the browser."
    )


def authenticate(cache: Path) -> str:
    env_token = os.environ.get("SCP_REFRESH_TOKEN")
    if env_token:
        refresh = env_token.strip()
        log("Using SCP_REFRESH_TOKEN from environment.")
    elif cache.is_file():
        refresh = cache.read_text(encoding="utf-8").strip()
        log(f"Using cached refresh token ({cache}).")
    else:
        refresh = device_login(cache)

    status, tok = post_form(
        f"{OIDC}/token",
        {"client_id": CLIENT_ID, "grant_type": "refresh_token", "refresh_token": refresh},
    )
    if status != 200 or "access_token" not in tok:
        detail = tok.get("error_description") or tok.get("error") or tok
        raise DiscoveryError(
            f"token refresh rejected: {detail}\n"
            "An offline refresh token expires after 30 days of non-use.\n"
            f"Delete {cache} and re-run to perform a fresh device login."
        )

    # Keycloak rotates refresh tokens; persist the new one so the 30-day
    # window keeps sliding forward rather than silently lapsing.
    if tok.get("refresh_token") and not env_token:
        save_refresh_token(cache, tok["refresh_token"])

    _AUTH["cache"] = str(cache)
    _AUTH["token"] = tok["access_token"]
    return tok["access_token"]


def resolve_user_id(access_token: str) -> int:
    """The SCP userId is an internal integer and is NOT the CCP customer number.

    The API exposes no "current user" endpoint, so read it from the token
    claims and fall back to an explicit override.
    """
    override = os.environ.get("NETCUP_USER_ID")
    if override:
        return int(override)

    parts = access_token.split(".")
    claims: dict[str, Any] = {}
    if len(parts) >= 2:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        try:
            claims = json.loads(base64.urlsafe_b64decode(payload))
        except Exception:  # noqa: BLE001 - malformed token is handled below
            claims = {}

    # `id` is the SCP userId. Confirmed against a live token, where `id` and
    # `preferred_username` held different values -- the latter being the CCP
    # customer number. Never fall back to preferred_username / customerNumber:
    # the OpenAPI description states the CCP customer number is NOT the SCP
    # userId, so using it yields a 403 against another account rather than a
    # useful error.
    for key in ("id", "scpUserId", "scp_user_id", "userId", "user_id", "uid"):
        value = claims.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)

    hint = ", ".join(sorted(claims)) if claims else "(token claims unreadable)"
    raise DiscoveryError(
        "could not determine the SCP userId from the token claims.\n"
        f"claims present: {hint}\n"
        "The SCP userId is an internal integer, NOT your CCP customer number.\n"
        "Find it in the Server Control Panel and re-run:\n"
        "    NETCUP_USER_ID=<id> python3 scripts/netcup-discover.py"
    )


def check_spec_version() -> None:
    """The OpenAPI document is public and needs no auth."""
    try:
        status, text = _request(f"{API}/openapi", method="GET")
        version = json.loads(text)["info"]["version"] if status == 200 else None
    except Exception:  # noqa: BLE001 - advisory check only
        version = None

    if not version:
        warn("could not read the live OpenAPI version; continuing.")
    elif version != PINNED_SPEC_VERSION:
        warn(f"SCP API spec is {version}; this script targets {PINNED_SPEC_VERSION}.")
        warn("netcup does not support their own API and may change endpoints without notice.")
        warn("Re-verify schemas before building any write operation on this.")
    else:
        log(f"SCP API spec version {version} matches pin.")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def rule(char: str = "-") -> None:
    print(char * RULE_WIDTH)


# netcup image names look like:
#   "Ubuntu 24.04.4 BIOS amd64"
#   "Ubuntu cloudimg 24.04.4 UEFI amd64"
#   "Ubuntu openclaw 24.04.4 UEFI amd64"
UBUNTU_IMAGE = re.compile(
    r"Ubuntu\s+(?:(?P<variant>cloudimg|openclaw)\s+)?"
    r"(?P<series>\d+\.\d+)(?:\.(?P<point>\d+))?\s+"
    r"(?P<firmware>BIOS|UEFI)",
    re.IGNORECASE,
)


def parse_ubuntu_flavour(flavour: dict) -> dict | None:
    """Decompose a netcup image flavour into comparable parts, or None."""
    image = (flavour.get("image") or {}).get("name", "") or ""
    m = UBUNTU_IMAGE.search(image)
    if not m:
        return None
    return {
        "id": flavour.get("id"),
        "image": image,
        "series": m.group("series"),
        "point": int(m.group("point") or 0),
        "variant": (m.group("variant") or "plain").lower(),
        "uefi": m.group("firmware").upper() == "UEFI",
    }


def select_image_flavour(flavours: list, server_uefi: bool,
                         series: str = "24.04", variant: str = "plain") -> dict | None:
    """Newest point release of `series` that will actually boot this server.

    The point release is chosen from netcup's live catalogue rather than pinned:
    netcup carries its own selection of Ubuntu point releases and adds newer
    ones over time, so hardcoding e.g. 24.04.4 silently goes stale. Firmware
    must match the server -- a UEFI image will not boot a BIOS-configured
    machine, and netcup ships some variants for one firmware only.
    """
    candidates = [
        p for p in (parse_ubuntu_flavour(f) for f in flavours or [])
        if p and p["series"] == series and p["variant"] == variant
        and p["uefi"] == bool(server_uefi)
    ]
    return max(candidates, key=lambda p: p["point"]) if candidates else None


def report(servers: list, vlans: list, detail: dict[int, dict]) -> None:
    rule("=")
    print("netcup SCP discovery -- READ-ONLY")
    rule("=")

    print()
    print("CLOUD vLANs")
    rule()
    if not vlans:
        print("  NONE.")
        print("  No Cloud vLAN on this account. The Hetzner build standard binds")
        print("  node-ip, advertise-address, the VXLAN underlay and the kube-vip")
        print("  VIP to a private address, so a vLAN (or a WireGuard mesh in its")
        print("  place) is required before that design can be ported.")
    else:
        for vlan in vlans:
            # Site carries `city`, not `name` (see the Site schema).
            site = vlan.get("site") or {}
            bw = vlan.get("bandwidthClass") or {}
            speed = bw.get("speedInMBit")
            print(f"  vlanId={vlan.get('vlanId')}  name={vlan.get('name') or '(unnamed)'}"
                  f"  site=id={site.get('id')} {site.get('city') or '?'}")
            if speed:
                print(f"        bandwidth: {bw.get('name') or '?'} ({speed} Mbit/s)")
            else:
                print("        bandwidth: unknown")

    print()
    print("SERVERS")
    rule()
    vlan_mtus: set[int] = set()
    public_mtus: set[int] = set()
    unconfigured_vlan_ifaces: list[tuple] = []
    vlan_ifaces = 0
    sites: set[tuple] = set()

    for server in servers:
        sid = server.get("id")
        entry = detail.get(sid, {})
        full = entry.get("server") or {}
        live = full.get("serverLiveInfo") or {}
        site = full.get("site") or {}
        sites.add((site.get("id"), site.get("city")))

        flags = "  DISABLED" if server.get("disabled") else ""
        nickname = server.get("nickname") or ""
        label = f"{nickname}  ({server.get('name')})" if nickname else str(server.get("name"))
        print(f"  [{sid}] {label}{flags}")
        print(f"        hostname : {server.get('hostname') or '-'}")
        print(f"        site     : id={site.get('id')} {site.get('city') or '?'}"
              f"   template={(full.get('template') or {}).get('name') or '?'}"
              f"   state={live.get('state') or '?'}")
        print(f"        capacity : {live.get('cpuCount') or '?'} vCPU"
              f"  {live.get('currentServerMemoryInMiB') or '?'} MiB RAM"
              f"  arch={full.get('architecture') or '?'}")
        for disk in live.get("disks") or []:
            cap = disk.get("capacityInMiB")
            gib = f"{cap / 1024:.0f} GiB" if isinstance(cap, (int, float)) else "?"
            print(f"        disk     : {disk.get('dev')} {gib} driver={disk.get('driver')}")

        # mtu only exists on ServerInterface (serverLiveInfo), keyed by mac.
        mtu_by_mac = {i.get("mac"): i.get("mtu") for i in live.get("interfaces") or []}
        vlan_by_mac = {i.get("mac"): (i.get("vlanInterface"), i.get("vlanId"))
                       for i in live.get("interfaces") or []}

        for iface in entry.get("interfaces") or []:
            mac = iface.get("mac")
            mtu = mtu_by_mac.get(mac)
            is_vlan, vlan_id = vlan_by_mac.get(mac, (False, None))
            kind = f"vLAN {vlan_id}" if is_vlan else "public"
            # ipv4Addresses here are ServerIpv4 objects, not plain strings.
            addrs = []
            for a in iface.get("ipv4Addresses") or []:
                if isinstance(a, dict):
                    addrs.append(f"{a.get('cidr') or a.get('ip')}"
                                 f" gw={a.get('gateway') or '-'}")
                else:
                    addrs.append(str(a))
            print(f"        {kind:<9} {mac}  mtu={mtu}  driver={iface.get('driver')}"
                  f"  {iface.get('speedInMBits') or '?'} Mbit")
            for a in addrs or ["(no IPv4)"]:
                print(f"                    ipv4 {a}")
            if is_vlan:
                vlan_ifaces += 1
                # mtu 0 means the vNIC exists in the hypervisor but the guest
                # has not configured the link yet -- not a real measurement.
                if isinstance(mtu, int) and mtu > 0:
                    vlan_mtus.add(mtu)
                else:
                    unconfigured_vlan_ifaces.append((sid, mac))
            elif isinstance(mtu, int) and mtu > 0:
                public_mtus.add(mtu)
        print()

    print("SITE (Cloud vLAN spans one location only)")
    rule()
    for sid_, city in sorted(sites, key=lambda t: (t[0] is None, t)):
        print(f"  site id={sid_}  {city}")
    if len(sites) == 1:
        print("  -> All servers share a site. A Cloud vLAN between them is possible.")
    else:
        print("  !! Servers span multiple sites. A Cloud vLAN CANNOT join them;")
        print("     a private underlay would have to be WireGuard over public IPs.")

    print()
    print("MTU (measured, not assumed)")
    rule()
    for mtu in sorted(public_mtus):
        print(f"  public interface MTU = {mtu}")
    for mtu in sorted(vlan_mtus):
        print(f"  vLAN interface MTU   = {mtu}")
    if unconfigured_vlan_ifaces:
        print(f"  {len(unconfigured_vlan_ifaces)} vLAN vNIC(s) attached but NOT yet configured"
              " in the guest (mtu=0):")
        for sid, mac in unconfigured_vlan_ifaces:
            print(f"      server {sid}  {mac}")
        print("  netcup reports mtu=0 until the OS brings the link up, so the real")
        print("  private-network MTU cannot be read from the API alone -- it has to")
        print("  be measured on the node once the interface is configured:")
        print("      ip link show <iface>            # kernel's view")
        print("      ping -M do -s <n> <peer-vlan-ip>  # largest unfragmented payload")
    if not vlan_mtus and not unconfigured_vlan_ifaces:
        print("  No vLAN interface exists, so there is no private-network MTU yet.")
    if len(vlan_mtus) > 1:
        print("  !! vLAN interfaces disagree on MTU. Resolve before building.")
    elif len(vlan_mtus) == 1:
        print(f"  Derive the Cilium MTU from {next(iter(vlan_mtus))}, minus VXLAN (50 B)")
        print("  and WireGuard overhead. Do NOT copy Hetzner's host 1400 / cilium_mtu")
        print("  1360 -- those follow from Hetzner's 1450 private network.")

    print()
    print("UBUNTU IMAGE FLAVOURS (parity target: ubuntu-24.04)")
    rule()
    # The distinguishing detail is image.name; flavour name/alias are all
    # "minimal". Firmware must match the server: a UEFI image will not boot a
    # BIOS-configured server (and vice versa).
    # Flavours are machine-type dependent, so every server is resolved
    # individually rather than sampling one and assuming the rest match.
    selections: dict[int, dict | None] = {}
    for sid, entry in sorted(detail.items()):
        flavours = entry.get("imageflavours") or []
        server_uefi = bool(((entry.get("server") or {}).get("serverLiveInfo") or {}).get("uefi"))
        tmpl = ((entry.get("server") or {}).get("template") or {}).get("name", "?")
        best = select_image_flavour(flavours, server_uefi)
        selections[sid] = best
        fw = "UEFI" if server_uefi else "BIOS"
        if best:
            print(f"  [{sid}] {tmpl:<12} {fw}  -> imageFlavourId={best['id']}"
                  f"  ({best['image']})")
        else:
            print(f"  [{sid}] {tmpl:<12} {fw}  -> NO bootable plain Ubuntu 24.04 flavour")

    chosen = {s["id"] for s in selections.values() if s}
    points = {s["point"] for s in selections.values() if s}
    print()
    if not chosen:
        print("  No usable Ubuntu 24.04 image. Check machine-type storage-driver support.")
    elif len(chosen) > 1:
        print(f"  !! Servers resolve to DIFFERENT flavour ids {sorted(chosen)} --")
        print("     install each with its own id; do not reuse one across the fleet.")
    else:
        only = next(iter(selections.values()))
        print(f"  All servers resolve to imageFlavourId={only['id']} "
              f"(Ubuntu {only['series']}.{only['point']}).")
    if points:
        print(f"  Newest 24.04 point release netcup offers: .{max(points)}")
        print("  Selected from the live catalogue, not pinned -- netcup carries its")
        print("  own subset of Ubuntu point releases and adds newer ones over time,")
        print("  so re-run this before an install rather than trusting a stored id.")
        print("  (The point release only sets the starting image; apt brings a node")
        print("  to the current patch level on first boot regardless.)")

    print()
    rule("=")
    print("VERDICT")
    rule("=")
    print(f"  servers found   : {len(servers)}")
    print(f"  Cloud vLANs     : {len(vlans)}")
    print(f"  vLAN interfaces : {vlan_ifaces}")
    if len(servers) >= 3 and vlan_ifaces >= 3:
        print("  -> vLAN topology present on 3+ servers. Hetzner design ports directly.")
    elif vlans and vlan_ifaces == 0:
        print("  -> A vLAN exists but no server has a vNIC on it. Attach interfaces first.")
    elif not vlans:
        print("  -> No vLAN. Topology decision required before the build workflow.")
    else:
        print("  -> Partial vLAN coverage. All control-plane nodes need a vNIC.")
    rule("=")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only netcup SCP discovery for the k3s build.")
    parser.add_argument("-o", "--output", metavar="FILE",
                        help="also write the raw API responses as JSON")
    parser.add_argument("--token-cache", metavar="PATH", default=str(DEFAULT_TOKEN_CACHE),
                        help=f"refresh-token cache location (default: {DEFAULT_TOKEN_CACHE})")
    args = parser.parse_args()

    check_spec_version()
    token = authenticate(Path(args.token_cache))

    user_id = resolve_user_id(token)
    user = api_get(f"/users/{user_id}", token) or {}
    log(f"Authenticated as SCP userId={user_id} ({user.get('username', '?')})")
    log("")

    vlans = api_get(f"/users/{user_id}/vlans", token) or []
    servers = api_get("/servers", token) or []

    detail: dict[int, dict] = {}
    for server in servers:
        sid = server["id"]
        # Three calls per server, because the two interface views differ:
        #   /servers/{id}            -> Server: site, template, and
        #                               serverLiveInfo.interfaces (ServerInterface),
        #                               which is the ONLY place `mtu` is exposed
        #   /servers/{id}/interfaces -> Interface: no mtu, but full ServerIpv4
        #                               objects carrying cidr + gateway
        detail[sid] = {
            "id": sid,
            "server": api_get(f"/servers/{sid}", token) or {},
            "interfaces": api_get(f"/servers/{sid}/interfaces", token) or [],
            "imageflavours": api_get(f"/servers/{sid}/imageflavours", token) or [],
        }

    report(servers, vlans, detail)

    if args.output:
        payload = {"servers": servers, "vlans": vlans, "detail": list(detail.values())}
        Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nmachine-readable output written to {args.output}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except DiscoveryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        sys.exit(130)
