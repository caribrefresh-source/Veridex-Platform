#!/usr/bin/env python3
"""Install an OS image on netcup servers. DESTRUCTIVE -- wipes the disk.

netcup's own API summary for this endpoint reads:
    "Setup image for a server. Attention: All data will be lost during
     formatting on selected disk!"

There is no undo. This is the only script in this repo that destroys data, and
it is deliberately awkward to run: it requires an explicit server list, an
explicit --apply, AND an explicit --yes-destroy-disks. No defaults, no "all".

What it does
------------
  * resolves the image flavour PER SERVER from netcup's live catalogue
    (policy: newest point release of the target series matching that server's
    firmware) rather than trusting a stored id, which goes stale silently
  * reads the target hostname from the Ansible inventory, so the inventory
    stays the single source of truth for which server is which
  * injects the account SSH key and DISABLES password authentication, closing
    out the delivery passwords in the same operation
  * polls the async task to completion

After it runs
-------------
The server's SSH host keys change (it is a fresh OS). Clear the old entry:
    ssh-keygen -R <public-ip>
The vLAN vNIC is a hypervisor device and survives the reinstall, but the guest
must reconfigure the interface -- expect mtu to read 0 again until it does.

Usage
-----
    python3 scripts/netcup-install-os.py --servers 938801
    python3 scripts/netcup-install-os.py --servers 938801 --apply --yes-destroy-disks
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
REPO = HERE.parent
INVENTORY = REPO / "ansible" / "inventory" / "production" / "hosts.yml"

_spec = importlib.util.spec_from_file_location("netcup_discover", HERE / "netcup-discover.py")
if _spec is None or _spec.loader is None:  # pragma: no cover
    raise SystemExit("cannot load netcup-discover.py")
nd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nd)


def inventory_hostnames() -> dict[int, str]:
    """netcup server id -> inventory hostname, read from the Ansible inventory.

    The inventory owns this mapping; duplicating it here would let the two
    drift and an install could then name a node after the wrong role.
    """
    try:
        import yaml
    except ImportError:  # pragma: no cover
        raise nd.DiscoveryError("PyYAML required: pip install pyyaml")
    data = yaml.safe_load(INVENTORY.read_text(encoding="utf-8"))
    out: dict[int, str] = {}
    for group in (data.get("all", {}).get("children") or {}).values():
        for name, vars_ in (group.get("hosts") or {}).items():
            sid = (vars_ or {}).get("netcup_server_id")
            if sid is not None:
                out[int(sid)] = name
    return out


def post_image(server_id: int, payload: dict, token: str,
               _retried: bool = False) -> tuple[int, object]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{nd.API}/servers/{server_id}/image", data=body, method="POST")
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
            f"network failure calling POST image on {server_id}: {exc.reason}") from exc
    if status == 401 and not _retried:
        # Access token aged out between servers in a fleet run.
        return post_image(server_id, payload, nd.refresh_access_token(), _retried=True)
    try:
        return status, json.loads(text) if text.strip() else None
    except json.JSONDecodeError:
        return status, text


def poll_task(uuid: str, token: str, attempts: int = 120, interval: int = 10) -> str:
    """An OS install takes minutes, not seconds -- poll patiently."""
    last = ""
    for _ in range(attempts):
        task = nd.api_get(f"/tasks/{uuid}", token) or {}
        status = str(task.get("status") or task.get("state") or "")
        if status != last:
            print(f"        task {uuid}: {status or '(no status)'}")
            last = status
        if status.upper() in ("SUCCESS", "SUCCEEDED", "DONE", "FINISHED", "COMPLETED"):
            return status
        if status.upper() in ("FAILED", "ERROR", "CANCELLED"):
            raise nd.DiscoveryError(f"task {uuid} ended as {status}: {json.dumps(task)[:400]}")
        time.sleep(interval)
    return "still-running"


def main() -> int:
    ap = argparse.ArgumentParser(description="Install an OS image on netcup servers.")
    ap.add_argument("--servers", required=True,
                    help="comma-separated SCP server ids. No default, no 'all'.")
    ap.add_argument("--series", default="24.04", help="Ubuntu series (default 24.04)")
    ap.add_argument("--variant", default="plain",
                    choices=["plain", "cloudimg", "openclaw"])
    ap.add_argument("--ssh-key-id", type=int, default=51926,
                    help="SCP ssh key id to inject (default: veridex-netcup-prod)")
    ap.add_argument("--apply", action="store_true", help="actually install")
    ap.add_argument("--yes-destroy-disks", action="store_true",
                    help="required alongside --apply; acknowledges data loss")
    ap.add_argument("--token-cache", default=str(nd.DEFAULT_TOKEN_CACHE))
    args = ap.parse_args()

    if args.apply and not args.yes_destroy_disks:
        raise nd.DiscoveryError(
            "--apply also requires --yes-destroy-disks.\n"
            "This formats the disk and every byte on it is lost.")

    server_ids = [int(s) for s in args.servers.split(",") if s.strip()]
    token = nd.authenticate(Path(args.token_cache))
    hostnames = inventory_hostnames()

    keys = nd.api_get(f"/users/253927/ssh-keys", token) or []
    if not any(k.get("id") == args.ssh_key_id for k in keys):
        raise nd.DiscoveryError(
            f"ssh key id {args.ssh_key_id} is not registered on this account. "
            "Installing without it would leave the server with no key access.")

    print(f"mode: {'APPLY -- DISKS WILL BE FORMATTED' if args.apply else 'DRY RUN (no writes)'}")
    print(f"ssh key: id={args.ssh_key_id}  password auth: DISABLED")
    print()

    plans = []
    for sid in server_ids:
        full = nd.api_get(f"/servers/{sid}", token) or {}
        if not full:
            raise nd.DiscoveryError(f"server {sid} not found on this account")
        live = full.get("serverLiveInfo") or {}
        uefi = bool(live.get("uefi"))
        flavours = nd.api_get(f"/servers/{sid}/imageflavours", token) or []
        best = nd.select_image_flavour(flavours, uefi, args.series, args.variant)
        if not best:
            raise nd.DiscoveryError(
                f"server {sid}: no bootable {args.series} {args.variant} image "
                f"for {'UEFI' if uefi else 'BIOS'} firmware")
        hostname = hostnames.get(sid)
        if not hostname:
            raise nd.DiscoveryError(
                f"server {sid} has no netcup_server_id entry in {INVENTORY.name}; "
                "add it before installing so the node is named correctly")
        disks = live.get("disks") or []
        plans.append((sid, full, best, hostname, disks))

        print(f"  [{sid}] {full.get('nickname') or full.get('name')}")
        print(f"        hostname     -> {hostname}")
        print(f"        image        -> id={best['id']}  {best['image']}")
        print(f"        firmware     :  {'UEFI' if uefi else 'BIOS'}")
        for d in disks:
            cap = d.get("capacityInMiB")
            print(f"        WILL ERASE   :  {d.get('dev')} "
                  f"{cap/1024:.0f} GiB" if isinstance(cap, (int, float))
                  else f"        WILL ERASE   :  {d.get('dev')}")

    if not args.apply:
        print()
        print("Dry run only. Re-run with --apply --yes-destroy-disks to install.")
        return 0

    print()
    for sid, full, best, hostname, _ in plans:
        payload = {
            "imageFlavourId": best["id"],
            "hostname": hostname,
            "sshKeyIds": [args.ssh_key_id],
            "sshPasswordAuthentication": False,
            "rootPartitionFullDiskSize": True,
        }
        status, body = post_image(sid, payload, token)
        if status not in (200, 201, 202, 204):
            raise nd.DiscoveryError(
                f"[{sid}] install failed -> HTTP {status}: {json.dumps(body)[:400]}")
        print(f"  [{sid}] install accepted (HTTP {status}) -> {hostname}")
        uuid = body.get("uuid") or body.get("taskUuid") or body.get("id") \
            if isinstance(body, dict) else None
        if isinstance(uuid, str) and "-" in uuid:
            print(f"        {poll_task(uuid, token)}")
        else:
            print("        no task uuid returned; poll /tasks or re-run discovery")

    print()
    print("Next:")
    print("  ssh-keygen -R <public-ip>      # host keys changed, clear the old entry")
    print("  python3 scripts/netcup-discover.py")
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
