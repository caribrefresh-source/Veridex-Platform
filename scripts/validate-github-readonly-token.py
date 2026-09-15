#!/usr/bin/env python3
"""Reject classic PATs and prove a fine-grained token cannot write Git refs."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True, help="owner/name")
    args = parser.parse_args()
    token = os.environ.get("ARGOCD_REPO_PAT", "")
    if not token:
        print("ERROR: ARGOCD_REPO_PAT is not set", file=sys.stderr)
        return 2
    request = urllib.request.Request(
        f"https://api.github.com/repos/{args.repository}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "veridex-argocd-credential-validator",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
            classic_scopes = {
                item.strip()
                for item in response.headers.get("X-OAuth-Scopes", "").split(",")
                if item.strip()
            }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: GitHub authorization check failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    if payload.get("full_name", "").lower() != args.repository.lower():
        print("ERROR: token did not resolve the required repository", file=sys.stderr)
        return 1
    if classic_scopes:
        print("ERROR: classic PAT scopes are not accepted; use a fine-grained read-only credential", file=sys.stderr)
        return 1
    # The response's `permissions` object describes the authenticated user's
    # repository role, not the permissions granted to a fine-grained token.
    # Prove denial at the write endpoint instead. The all-zero object ID can
    # never create a ref: a write-capable credential reaches payload validation
    # (422), while a Contents:read credential is rejected at authorization
    # (403). Thus this probe cannot change repository state either way.
    probe = urllib.request.Request(
        f"https://api.github.com/repos/{args.repository}/git/refs",
        data=json.dumps(
            {
                "ref": f"refs/heads/veridex-permission-probe-{secrets.token_hex(8)}",
                "sha": "0" * 40,
            }
        ).encode(),
        method="POST",
        headers=request.headers,
    )
    try:
        urllib.request.urlopen(probe, timeout=20)
    except urllib.error.HTTPError as exc:
        if exc.code != 403:
            print(
                f"ERROR: Git reference write reached payload handling (HTTP {exc.code}); "
                "token is not proven read-only",
                file=sys.stderr,
            )
            return 1
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"ERROR: GitHub write-denial probe failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    else:
        print("ERROR: Git reference write unexpectedly succeeded", file=sys.stderr)
        return 1
    print(f"PASS: credential can read {args.repository} and cannot write Git refs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
