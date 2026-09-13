#!/usr/bin/env python3
"""Set netcup SCP nicknames to reflect each server's k3s role. IDEMPOTENT.

Why nickname and not hostname
-----------------------------
`nickname` is the SCP display label: cosmetic, reversible, and with no DNS
side effects. `hostname` currently holds netcup's rDNS-backed FQDN (e.g.
v2202609417155518911.megasrv.de); changing it touches reverse DNS. The
hostname the cluster actually uses is set at OS-install time via the
`hostname` field of ServerImageSetup, and Ansible's base role re-asserts it
from `inventory_hostname`, so it does not need to be patched here.

Role assignment (decided from measured capacity, see conversation 2026-09-12)
---------------------------------------------------------------------------
  server-1..3  : the 3x RS 1000 G12 (4 vCPU / 8 GiB / 256 GiB)
                 Homogeneous, symmetric etcd quorum. Matches the Hetzner
                 control-plane nodes exactly, which run 4/8 at 63-68% RAM.
  agent-1..2   : the 2x RS 2000 G12 (8 vCPU / 16 GiB / 512 GiB)
                 The heavy data plane: Longhorn replicas, CNPG primaries,
                 MinIO shards. The 512 GiB disks belong where replicas live.

Naming mirrors the Hetzner convention (k3s-ha-server-N / k3s-ha-agent-N) so
the inventory grouping by hostname prefix ports unchanged.

Safety
------
Defaults to DRY RUN. Nothing is written without an explicit --apply.

Usage
-----
    python3 scripts/netcup-set-nicknames.py
    python3 scripts/netcup-set-nicknames.py --apply
    python3 scripts/netcup-set-nicknames.py --prefix veridex --apply
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("netcup_discover", HERE / "netcup-discover.py")
if _spec is None or _spec.loader is None:  # pragma: no cover
    raise SystemExit("cannot load netcup-discover.py")
nd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nd)

# SCP server id -> (role, index). Explicit rather than inferred from machine
# type, so the role decision is recorded in Git rather than re-derived.
USER_ID = 253927  # SCP userId (NOT the CCP customer number)

ROLE_MAP: dict[int, tuple[str, int]] = {
    938801: ("server", 1),   # RS 1000 G12
    938802: ("server", 2),   # RS 1000 G12
    938803: ("server", 3),   # RS 1000 G12
    939122: ("agent", 1),    # RS 2000 G12
    939123: ("agent", 2),    # RS 2000 G12
}


def patch_nickname(server_id: int, nickname: str, token: str) -> tuple[int, object]:
    """PATCH the nickname. Content type is application/merge-patch+json."""
    body = json.dumps({"nickname": nickname}).encode()
    req = urllib.request.Request(
        f"{nd.API}/servers/{server_id}", data=body, method="PATCH")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/merge-patch+json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=nd.HTTP_TIMEOUT) as resp:
            text, status = resp.read().decode("utf-8", "replace"), resp.status
    except urllib.error.HTTPError as exc:
        text, status = exc.read().decode("utf-8", "replace"), exc.code
    except urllib.error.URLError as exc:
        raise nd.DiscoveryError(
            f"network failure calling PATCH /servers/{server_id}: {exc.reason}") from exc
    try:
        return status, json.loads(text) if text.strip() else None
    except json.JSONDecodeError:
        return status, text


def patch_vlan_name(vlan_id: int, name: str, token: str) -> tuple[int, object]:
    """PUT the vLAN name. VLanSave carries only `name` -- bandwidth class is a
    product tier and is not settable through the API."""
    body = json.dumps({"name": name}).encode()
    req = urllib.request.Request(
        f"{nd.API}/users/{USER_ID}/vlans/{vlan_id}", data=body, method="PUT")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=nd.HTTP_TIMEOUT) as resp:
            text, status = resp.read().decode("utf-8", "replace"), resp.status
    except urllib.error.HTTPError as exc:
        text, status = exc.read().decode("utf-8", "replace"), exc.code
    except urllib.error.URLError as exc:
        raise nd.DiscoveryError(
            f"network failure calling PUT vlans/{vlan_id}: {exc.reason}") from exc
    try:
        return status, json.loads(text) if text.strip() else None
    except json.JSONDecodeError:
        return status, text


def main() -> int:
    ap = argparse.ArgumentParser(description="Set netcup nicknames to k3s roles.")
    ap.add_argument("--prefix", default="veridex",
                    help="cluster name prefix (default: veridex)")
    ap.add_argument("--vlan", type=int, default=1006740,
                    help="vLAN to name (default: 1006740)")
    ap.add_argument("--vlan-name", default="veridex-netcup-prod-k3s",
                    help="name to give the vLAN")
    ap.add_argument("--apply", action="store_true",
                    help="actually write. Without this, dry run only.")
    ap.add_argument("--token-cache", default=str(nd.DEFAULT_TOKEN_CACHE))
    args = ap.parse_args()

    token = nd.authenticate(Path(args.token_cache))
    servers = nd.api_get("/servers", token) or []
    by_id = {s["id"]: s for s in servers}

    print(f"mode: {'APPLY' if args.apply else 'DRY RUN (no writes)'}")
    print()

    changed = skipped = 0
    for sid, (role, index) in sorted(ROLE_MAP.items(), key=lambda kv: (kv[1][0], kv[1][1])):
        server = by_id.get(sid)
        if server is None:
            print(f"  [{sid}] NOT FOUND in this account -- skipped")
            skipped += 1
            continue

        desired = f"{args.prefix}-{role}-{index}"
        current = server.get("nickname") or ""
        if current == desired:
            print(f"  [{sid}] already named {desired} -- no action")
            skipped += 1
            continue

        if not args.apply:
            print(f"  [{sid}] {server.get('name')}: WOULD set nickname "
                  f"{current or '(none)'!r} -> {desired!r}")
            continue

        status, body = patch_nickname(sid, desired, token)
        if status not in (200, 202, 204):
            raise nd.DiscoveryError(
                f"[{sid}] nickname patch failed -> HTTP {status}: {json.dumps(body)[:300]}")
        print(f"  [{sid}] {server.get('name')}: nickname -> {desired}  (HTTP {status})")
        changed += 1

    # vLAN name
    vlan = nd.api_get(f"/vlans/{args.vlan}", token) or {}
    current_vlan_name = vlan.get("name") or ""
    if current_vlan_name == args.vlan_name:
        print(f"  [vlan {args.vlan}] already named {args.vlan_name} -- no action")
        skipped += 1
    elif not args.apply:
        print(f"  [vlan {args.vlan}] WOULD set name "
              f"{current_vlan_name or '(none)'!r} -> {args.vlan_name!r}")
    else:
        status, body = patch_vlan_name(args.vlan, args.vlan_name, token)
        if status not in (200, 202, 204):
            raise nd.DiscoveryError(
                f"[vlan {args.vlan}] name patch failed -> HTTP {status}: "
                f"{json.dumps(body)[:300]}")
        print(f"  [vlan {args.vlan}] name -> {args.vlan_name}  (HTTP {status})")
        changed += 1

    # Gate 0.4: the kube-vip VIP must not be assigned to any interface.
    vip = "10.2.0.100"
    conflicts = []
    for sid in by_id:
        for iface in nd.api_get(f"/servers/{sid}/interfaces", token) or []:
            for addr in iface.get("ipv4Addresses") or []:
                ip = addr.get("ip") if isinstance(addr, dict) else str(addr)
                if ip == vip:
                    conflicts.append((sid, iface.get("mac")))
    print()
    if conflicts:
        print(f"  !! VIP {vip} IS ASSIGNED: {conflicts} -- kube-vip cannot use it")
    else:
        print(f"  VIP {vip} is unassigned on all interfaces -- free for kube-vip")

    print()
    print(f"changed: {changed}   skipped: {skipped}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except nd.DiscoveryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        sys.exit(130)
