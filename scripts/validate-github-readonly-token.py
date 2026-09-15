#!/usr/bin/env python3
"""Reject an Argo CD GitHub credential with repository write access."""

from __future__ import annotations

import argparse
import json
import os
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
    permissions = payload.get("permissions") or {}
    forbidden = [name for name in ("admin", "maintain", "push") if permissions.get(name)]
    if forbidden:
        print("ERROR: token has repository write/admin permission: " + ", ".join(forbidden), file=sys.stderr)
        return 1
    if not permissions.get("pull"):
        print("ERROR: token lacks repository read permission", file=sys.stderr)
        return 1
    print(f"PASS: credential can read {args.repository} and has no repository write/admin permission")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
