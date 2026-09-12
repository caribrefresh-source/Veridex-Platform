#!/usr/bin/env python3
"""Fail the build when Hetzner-specific assumptions leak into netcup config.

Why this exists
---------------
This platform is being rebuilt on netcup using the Hetzner K3s-HA cluster as
the reference implementation. The reference is read constantly during the
migration, so provider-specific values get copied across by reflex: an hcloud
StorageClass, a 10.1.x address, a `nbg1` location. Each one works right up
until it silently doesn't, because netcup has no hcloud CSI, no 10.1.0.0/16,
and no Hetzner locations.

A grep run once during migration catches today's leaks. This runs on every
commit and catches tomorrow's.

What it does NOT flag
---------------------
Hetzner Object Storage endpoints (`your-objectstorage.com`). Backups
deliberately continue to land in the existing WORM buckets: S3 is reachable
over the internet, so the dependency is on an S3 endpoint rather than on being
hosted at Hetzner, and keeping compute and backups at different providers is
better isolation than co-locating them.

Comment lines are skipped. Explaining *why* netcup differs from Hetzner
requires naming Hetzner, and that prose must not fail the build.

Escape hatch
------------
Append `# provider-drift-ok: <reason>` to a line that must legitimately keep a
flagged value. The reason is mandatory -- an unexplained suppression is the
thing this linter exists to prevent.

Usage
-----
    python3 scripts/lint-provider-drift.py            # ERRORs fail, WARNs report
    python3 scripts/lint-provider-drift.py --strict   # WARNs fail too
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Directories that hold live configuration. docs/ and scripts/ are excluded:
# prose and tooling reference Hetzner legitimately and constantly.
SCAN_DIRS = ("ansible", "kubernetes", "gitops")
SCAN_SUFFIXES = (".yml", ".yaml", ".yaml.j2", ".yml.j2", ".j2", ".tf", ".sh", ".env")

SUPPRESS = re.compile(r"#\s*provider-drift-ok:\s*\S+")

# (severity, compiled pattern, human explanation)
RULES: list[tuple[str, re.Pattern, str]] = [
    ("ERROR", re.compile(r"\bcsi\.hetzner\.cloud\b"),
     "Hetzner CSI provisioner -- netcup has no CSI driver; storage is Longhorn"),
    ("ERROR", re.compile(r"\bhcloud-volumes\b"),
     "Hetzner StorageClass name -- does not exist on netcup"),
    ("ERROR", re.compile(r"\bhcloud_(token|network|ccm_version|csi_version)\b"),
     "Hetzner Cloud API variable -- no netcup equivalent"),
    ("ERROR", re.compile(r"load-balancer\.hetzner\.cloud"),
     "Hetzner CCM LoadBalancer annotation -- netcup has no managed LB"),
    ("ERROR", re.compile(r"cloud-provider=external"),
     "requires a CCM to clear node.cloudprovider.kubernetes.io/uninitialized; "
     "netcup has none, so nodes would never schedule"),
    ("ERROR", re.compile(r"\b10\.1\.\d{1,3}\.\d{1,3}\b"),
     "Hetzner private network (10.1.0.0/16) -- netcup uses 10.2.0.0/16"),
    ("ERROR", re.compile(r"\bk3s-ha-(server|agent)-\d"),
     "Hetzner node name -- netcup nodes are veridex-server-N / veridex-agent-N"),
    ("ERROR", re.compile(r"\bnbg1\b|\bfsn1\b(?!\.your-objectstorage)"),
     "Hetzner datacenter location -- netcup uses site id 1 (Nuremberg)"),
    ("ERROR", re.compile(r"plugin:\s*hcloud"),
     "Hetzner dynamic inventory plugin -- netcup has none; inventory is static"),

    # Context-dependent: only drift if the cluster keeps distinct pod/service
    # CIDRs. Pending that decision these report without failing.
    ("WARN", re.compile(r"\b10\.4[23]\.\d{1,3}\.\d{1,3}\b|10\.4[23]\.0\.0/16"),
     "Hetzner pod/service CIDR -- drift only if this cluster uses distinct ranges"),
]


def scan_file(path: Path) -> list[tuple[int, str, str, str]]:
    findings = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return findings
    for lineno, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue  # comment-only line: prose may name Hetzner freely
        if SUPPRESS.search(raw):
            continue
        for severity, pattern, why in RULES:
            m = pattern.search(raw)
            if m:
                findings.append((lineno, severity, m.group(0), why))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect Hetzner drift in netcup config.")
    ap.add_argument("--strict", action="store_true", help="treat WARN as failure")
    ap.add_argument("--root", default=".", help="repository root (default: cwd)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    errors = warns = scanned = 0

    for d in SCAN_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or not path.name.endswith(SCAN_SUFFIXES):
                continue
            scanned += 1
            for lineno, severity, matched, why in scan_file(path):
                rel = path.relative_to(root).as_posix()
                print(f"{severity}: {rel}:{lineno}: {matched!r}\n        {why}")
                if severity == "ERROR":
                    errors += 1
                else:
                    warns += 1

    print()
    print(f"scanned {scanned} files in {'/, '.join(SCAN_DIRS)}/")
    print(f"errors: {errors}   warnings: {warns}")

    if errors or (args.strict and warns):
        print()
        print("Provider drift detected. Either fix the value for netcup, or append")
        print("  # provider-drift-ok: <reason>")
        print("to the line if it is genuinely correct as written.")
        return 1
    print("No blocking provider drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
