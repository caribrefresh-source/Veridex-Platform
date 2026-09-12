#!/usr/bin/env python3
"""List and register SSH public keys in the netcup SCP account. IDEMPOTENT.

netcup's SSH key store is account-level (`/users/{userId}/ssh-keys`), not
per-server: one key registered once can be applied to every server. The key is
applied at OS-install time via `sshKeyIds` in ServerImageSetup -- registering a
key does NOT push it to already-running servers. Those need ssh-copy-id, or a
reinstall.

Only the PUBLIC key is transmitted. The private key never leaves this machine.

Safety
------
Defaults to DRY RUN for --add. Listing is always safe.

Usage
-----
    python3 scripts/netcup-ssh-keys.py --list
    python3 scripts/netcup-ssh-keys.py --add ~/.ssh/veridex_netcup_ed25519.pub \
        --name veridex-netcup-prod
    python3 scripts/netcup-ssh-keys.py --add ... --name ... --apply
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

USER_ID = 253927  # SCP userId, NOT the CCP customer number


def post_key(name: str, key: str, token: str) -> tuple[int, object]:
    body = json.dumps({"name": name, "key": key}).encode()
    req = urllib.request.Request(
        f"{nd.API}/users/{USER_ID}/ssh-keys", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=nd.HTTP_TIMEOUT) as resp:
            text, status = resp.read().decode("utf-8", "replace"), resp.status
    except urllib.error.HTTPError as exc:
        text, status = exc.read().decode("utf-8", "replace"), exc.code
    except urllib.error.URLError as exc:
        raise nd.DiscoveryError(f"network failure registering key: {exc.reason}") from exc
    try:
        return status, json.loads(text) if text.strip() else None
    except json.JSONDecodeError:
        return status, text


def normalise(pubkey: str) -> str:
    """Compare on type+material only. The trailing comment is cosmetic and
    differs between copies of the same key."""
    parts = pubkey.strip().split()
    return " ".join(parts[:2]) if len(parts) >= 2 else pubkey.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="Manage netcup SCP SSH keys.")
    ap.add_argument("--list", action="store_true", help="list registered keys")
    ap.add_argument("--add", metavar="PUBKEY_PATH", help="public key file to register")
    ap.add_argument("--name", help="name to register the key under")
    ap.add_argument("--apply", action="store_true", help="actually write")
    ap.add_argument("--token-cache", default=str(nd.DEFAULT_TOKEN_CACHE))
    args = ap.parse_args()

    token = nd.authenticate(Path(args.token_cache))
    existing = nd.api_get(f"/users/{USER_ID}/ssh-keys", token) or []

    print(f"registered keys: {len(existing)}")
    for k in existing:
        print(f"  id={k.get('id')}  name={k.get('name')}  created={k.get('createdAt')}")
        print(f"      {normalise(str(k.get('key')))[:64]}...")

    if not args.add:
        return 0

    if not args.name:
        raise nd.DiscoveryError("--add requires --name")

    path = Path(args.add).expanduser()
    if not path.is_file():
        raise nd.DiscoveryError(f"public key not found: {path}")
    pubkey = path.read_text(encoding="utf-8").strip()
    if not pubkey.startswith(("ssh-", "ecdsa-")):
        raise nd.DiscoveryError(
            f"{path} does not look like a public key. Never pass a PRIVATE key here.")

    print()
    for k in existing:
        if normalise(str(k.get("key"))) == normalise(pubkey):
            print(f"  already registered as id={k.get('id')} "
                  f"name={k.get('name')} -- no action")
            return 0

    if not args.apply:
        print(f"  WOULD register {path.name} as {args.name!r}")
        print(f"      {normalise(pubkey)[:64]}...")
        return 0

    status, body = post_key(args.name, pubkey, token)
    if status not in (200, 201, 202, 204):
        raise nd.DiscoveryError(f"registration failed -> HTTP {status}: "
                                f"{json.dumps(body)[:300]}")
    new_id = body.get("id") if isinstance(body, dict) else None
    print(f"  registered {args.name!r}  (HTTP {status}, id={new_id})")
    print()
    print("  Use this id in ServerImageSetup.sshKeyIds at install time.")
    print("  Already-running servers are unaffected -- netcup applies SCP keys")
    print("  only during an image install.")
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
