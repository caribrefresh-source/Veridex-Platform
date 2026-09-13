#!/usr/bin/env python3
"""Attach a Cloud vLAN vNIC to netcup servers. IDEMPOTENT.

This is the one write operation in the netcup provisioning path, kept separate
from `netcup-discover.py` so that script's read-only guarantee stays intact.

Idempotence (repo contract section 4, IIR): before creating anything it reads
the server's existing interfaces and skips any server already attached to the
target vLAN. Re-running is safe and reports "already attached" rather than
creating a duplicate vNIC.

Safety
------
Defaults to DRY RUN. Nothing is written without an explicit --apply.

Usage
-----
    # show what would happen (default)
    python3 scripts/netcup-attach-vlan.py --vlan 1006740 --servers 938801

    # actually do it
    python3 scripts/netcup-attach-vlan.py --vlan 1006740 --servers 938801 --apply

    # all five
    python3 scripts/netcup-attach-vlan.py --vlan 1006740 \
        --servers 938801,938802,938803,939122,939123 --apply

Requires Python 3.8+, standard library only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DISCOVER = HERE / "netcup-discover.py"

# Reuse the discovery script's OAuth + GET plumbing rather than duplicating the
# device-code flow. The filename has a hyphen, so it cannot be imported normally.
_spec = importlib.util.spec_from_file_location("netcup_discover", DISCOVER)
if _spec is None or _spec.loader is None:  # pragma: no cover
    raise SystemExit(f"cannot load {DISCOVER}")
nd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nd)


def api_post_json(path: str, payload: dict, token: str) -> tuple[int, object]:
    """POST a JSON body. Separate from nd._request, which form-encodes."""
    if not path.startswith("/"):
        raise nd.DiscoveryError(f"path must start with '/' (got {path!r})")
    body = json.dumps(payload).encode()
    req = urllib.request.Request(f"{nd.API}{path}", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=nd.HTTP_TIMEOUT) as resp:
            text = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        text, status = exc.read().decode("utf-8", "replace"), exc.code
    except urllib.error.URLError as exc:
        raise nd.DiscoveryError(f"network failure calling POST {path}: {exc.reason}") from exc
    try:
        return status, json.loads(text) if text.strip() else None
    except json.JSONDecodeError:
        return status, text


def attached_vlan_ids(server_id: int, token: str) -> set[int]:
    """vLAN ids this server already has a vNIC on.

    /interfaces returns `Interface`, which carries no vlan fields, so the vlan
    view comes from /servers/{id} -> serverLiveInfo.interfaces (ServerInterface).
    """
    full = nd.api_get(f"/servers/{server_id}", token) or {}
    live = full.get("serverLiveInfo") or {}
    return {
        i.get("vlanId")
        for i in (live.get("interfaces") or [])
        if i.get("vlanInterface") and i.get("vlanId") is not None
    }


def poll_task(uuid: str, token: str, attempts: int = 24, interval: int = 5) -> str:
    for _ in range(attempts):
        task = nd.api_get(f"/tasks/{uuid}", token) or {}
        status = str(task.get("status") or task.get("state") or "")
        if status.upper() in ("SUCCESS", "SUCCEEDED", "DONE", "FINISHED", "COMPLETED"):
            return status
        if status.upper() in ("FAILED", "ERROR", "CANCELLED"):
            raise nd.DiscoveryError(f"task {uuid} ended as {status}: {json.dumps(task)[:300]}")
        time.sleep(interval)
    return "still-running"


def main() -> int:
    ap = argparse.ArgumentParser(description="Attach a Cloud vLAN vNIC to netcup servers.")
    ap.add_argument("--vlan", type=int, required=True, help="target vlanId")
    ap.add_argument("--servers", required=True,
                    help="comma-separated SCP server ids")
    ap.add_argument("--driver", default="VIRTIO",
                    choices=["VIRTIO", "E1000", "E1000E", "RTL8139", "VMXNET3"],
                    help="NIC driver (default VIRTIO -- paravirtualised, matches existing NICs)")
    ap.add_argument("--apply", action="store_true",
                    help="actually write. Without this, dry run only.")
    ap.add_argument("--token-cache", default=str(nd.DEFAULT_TOKEN_CACHE))
    args = ap.parse_args()

    server_ids = [int(s) for s in args.servers.split(",") if s.strip()]
    token = nd.authenticate(Path(args.token_cache))

    # Confirm the vLAN exists and report the tier we are wiring into.
    vlan = nd.api_get(f"/vlans/{args.vlan}", token)
    if not vlan:
        raise nd.DiscoveryError(f"vlanId {args.vlan} not found")
    bw = vlan.get("bandwidthClass") or {}
    site = vlan.get("site") or {}
    print(f"vLAN {args.vlan}: {bw.get('name') or '?'} "
          f"({bw.get('speedInMBit')} Mbit/s), site id={site.get('id')} {site.get('city')}")
    print(f"mode: {'APPLY' if args.apply else 'DRY RUN (no writes)'}")
    print()

    created = skipped = 0
    for sid in server_ids:
        full = nd.api_get(f"/servers/{sid}", token) or {}
        name = full.get("name", "?")
        site_id = (full.get("site") or {}).get("id")
        if site_id != site.get("id"):
            print(f"  [{sid}] {name}: SKIP -- server site id={site_id} "
                  f"!= vLAN site id={site.get('id')}; a vLAN spans one location only")
            skipped += 1
            continue

        if args.vlan in attached_vlan_ids(sid, token):
            print(f"  [{sid}] {name}: already attached to vLAN {args.vlan} -- no action")
            skipped += 1
            continue

        if not args.apply:
            print(f"  [{sid}] {name}: WOULD attach vNIC "
                  f"(vlanId={args.vlan}, driver={args.driver})")
            continue

        status, body = api_post_json(
            f"/servers/{sid}/interfaces",
            {"vlanId": args.vlan, "networkDriver": args.driver},
            token,
        )
        if status not in (200, 201, 202, 204):
            raise nd.DiscoveryError(
                f"[{sid}] attach failed -> HTTP {status}: {json.dumps(body)[:400]}")
        print(f"  [{sid}] {name}: attached (HTTP {status})")
        created += 1

        # The write may be asynchronous; follow the task when one is returned.
        uuid = None
        if isinstance(body, dict):
            uuid = body.get("uuid") or body.get("taskUuid") or body.get("id")
        if uuid and isinstance(uuid, str) and "-" in uuid:
            print(f"        task {uuid}: {poll_task(uuid, token)}")

    print()
    print(f"attached: {created}   skipped: {skipped}")
    if args.apply and created:
        print("Re-run scripts/netcup-discover.py to read the vLAN interface MTU.")
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
