#!/usr/bin/env python3
"""Fail the build when a Hetzner dependency or Hetzner-specific value is in the repo.

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

Why every tracked file
----------------------
Revision 3 of the cluster plan (Gate 0) requires that no Hetzner endpoint,
variable, backend configuration, bucket, DNS, credential, documentation
instruction or workflow dependency remains anywhere -- not only in live
configuration -- and that historical references are explicitly labelled
historical. A command file telling an operator to ping a Hetzner VIP is as
much a dependency as a manifest that uses it. So this scans every file Git
tracks, and it flags Hetzner Object Storage endpoints: backups go to Wasabi.

What it does NOT flag
---------------------
Prose that names Hetzner. The rules match provider-specific values, not the
word, so explaining why netcup differs never fails the build. Comment-only
lines are skipped for the same reason.

Labelling exceptions
--------------------
One line: put `provider-drift-ok: <reason>` on the line, in whatever comment
syntax the file uses (`# ...`, `<!-- ... -->`, `// ...`). The reason is
mandatory -- an unexplained suppression is the thing this linter exists to
prevent.

Historical records: a file named `.provider-drift-historical` marks its
directory and everything beneath it as historical. Its content is the reason
and must not be empty. Findings there are reported as HISTORICAL and never
fail the build, so they stay visible without blocking.

Usage
-----
    python3 scripts/lint-provider-drift.py            # ERRORs fail, WARNs report
    python3 scripts/lint-provider-drift.py --strict   # WARNs fail too
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from pathlib import Path, PurePosixPath

# The linter necessarily contains every pattern it looks for.
SELF = Path(__file__).resolve()

HISTORICAL_MARKER = ".provider-drift-historical"
SUPPRESS = re.compile(r"provider-drift-ok:(.*)")
COMMENT_CLOSERS = re.compile(r"(-->|\*/)\s*$")


def suppressed(line: str) -> bool:
    """True only when the suppression carries a real reason.

    A comment terminator is not a reason: `<!-- provider-drift-ok: -->` would
    otherwise pass a bare `\\S+` check on the `-->` alone.
    """
    m = SUPPRESS.search(line)
    if not m:
        return False
    reason = COMMENT_CLOSERS.sub("", m.group(1)).strip()
    return re.search(r"[A-Za-z0-9]", reason) is not None
COMMENT_PREFIXES = ("#", "//", "<!--")

# Characters that look like a hyphen or dot but are not ASCII, so a rule for
# "K3s-HA" or "argocd.entrepeai.com" could be dodged by pasting a typographic
# variant. NFKC folds fullwidth forms (e.g. U+FF0E full stop); the table folds
# the dash family (U+2010-U+2015, U+2212, U+FE58, U+FE63, U+FF0D). Written as
# escapes so the characters are visible in review.
DASHES = dict.fromkeys(
    map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d"), "-"
)


def normalize(line: str) -> str:
    """Fold look-alikes to ASCII and drop invisible format characters.

    Unicode category Cf (zero-width space and joiners, soft hyphen, bidi
    controls) renders as nothing, so "K3s-" + U+200B + "HA" would otherwise
    split a match while reading as K3s-HA.
    """
    folded = unicodedata.normalize("NFKC", line).translate(DASHES)
    return "".join(ch for ch in folded if unicodedata.category(ch) != "Cf")

# (severity, compiled pattern, human explanation)
RULES: list[tuple[str, re.Pattern, str]] = [
    ("ERROR", re.compile(r"\bcsi\.hetzner\.cloud\b"),
     "Hetzner CSI provisioner -- netcup has no CSI driver"),
    ("ERROR", re.compile(r"\bhcloud-volumes\b"),
     "Hetzner StorageClass name -- does not exist on netcup"),
    ("ERROR", re.compile(r"\bhcloud_(token|network|ccm_version|csi_version)\b"),
     "Hetzner Cloud API variable -- no netcup equivalent"),
    ("ERROR", re.compile(r"\bHCLOUD_TOKEN\b|hetznercloud/hcloud"),
     "Hetzner Cloud credential or Terraform provider -- no netcup equivalent"),
    ("ERROR", re.compile(r"load-balancer\.hetzner\.cloud"),
     "Hetzner CCM LoadBalancer annotation -- netcup has no managed LB"),
    ("ERROR", re.compile(r"cloud-provider=external"),
     "requires a CCM to clear node.cloudprovider.kubernetes.io/uninitialized; "
     "netcup has none, so nodes would never schedule"),
    ("ERROR", re.compile(r"\b10\.1\.\d{1,3}\.\d{1,3}\b"),
     "Hetzner private network (10.1.0.0/16) -- netcup uses 10.2.0.0/16"),
    ("ERROR", re.compile(r"\bk3s-ha-(server|agent)-\d"),
     "Hetzner node name -- netcup nodes are veridex-server-N / veridex-agent-N"),
    ("ERROR", re.compile(r"\b(nbg1|fsn1|hel1)\b"),
     "Hetzner datacenter location -- netcup uses site id 1 (Nuremberg)"),
    ("ERROR", re.compile(r"plugin:\s*hcloud"),
     "Hetzner dynamic inventory plugin -- netcup has none; inventory is static"),
    ("ERROR", re.compile(r"your-objectstorage\.com"),
     "Hetzner Object Storage endpoint -- backups go to Wasabi; no Hetzner "
     "bucket may be required by production or recovery"),
    ("ERROR", re.compile(r"\b(api|dns|console)\.hetzner\.(cloud|com)\b"
                         r"|\brobot(-ws)?\.your-server\.de\b"),
     "Hetzner API, DNS or console endpoint -- no netcup dependency on it"),

    # Old cluster identity. Gate 0 stops on "ambiguous cluster identity": an
    # instruction that targets the K3s-HA cluster, one of its hostnames or its
    # repository runs against Hetzner while looking like platform tooling.
    # entrepeai.com is delegated to Hetzner DNS with a wildcard to the K3s-HA
    # cluster (verified 2026-09-13); platform hostnames live under
    # veridexeai.com. Label genuine history with .provider-drift-historical.
    ("ERROR", re.compile(r"\bK3s-HA\b"),
     "names the Hetzner K3s-HA cluster as a target -- instructions must target "
     "the netcup cluster; label historical references"),
    ("ERROR", re.compile(r"\b[a-z0-9-]+\.entrepeai\.com\b", re.IGNORECASE),
     "entrepeai.com hostname -- resolves through Hetzner DNS to the K3s-HA "
     "cluster; platform hostnames live under veridexeai.com"),
    ("ERROR", re.compile(r"caribrefresh-source/k3s-ha\b", re.IGNORECASE),
     "K3s-HA repository -- the netcup platform's source of truth is "
     "caribrefresh-source/Veridex-Platform"),

    # Context-dependent: only drift if the cluster keeps distinct pod/service
    # CIDRs. Pending that decision these report without failing.
    ("WARN", re.compile(r"\b10\.4[23]\.\d{1,3}\.\d{1,3}\b|10\.4[23]\.0\.0/16"),
     "Hetzner pod/service CIDR -- drift only if this cluster uses distinct ranges"),
]


def tracked_files(root: Path) -> list[str]:
    """Files Git tracks, so CI and a local checkout scan the same set."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return sorted(
            p.relative_to(root).as_posix()
            for p in root.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(root).parts
        )
    return sorted(f for f in out.decode("utf-8").split("\0") if f)


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None  # binary
    return data.decode("utf-8", errors="replace")


def scan_text(text: str) -> list[tuple[int, str, str, str]]:
    findings = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith(COMMENT_PREFIXES):
            continue  # comment-only line: prose may name Hetzner freely
        if suppressed(raw):
            continue
        line = normalize(raw)
        for severity, pattern, why in RULES:
            m = pattern.search(line)
            if m:
                findings.append((lineno, severity, m.group(0), why))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect Hetzner drift anywhere in the repo.")
    ap.add_argument("--strict", action="store_true", help="treat WARN as failure")
    ap.add_argument("--root", default=".", help="repository root (default: cwd)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    files = tracked_files(root)

    historical_dirs: set[str] = set()
    bad_markers: list[str] = []
    for rel in files:
        if PurePosixPath(rel).name != HISTORICAL_MARKER:
            continue
        reason = (read_text(root / rel) or "").strip()
        if reason:
            historical_dirs.add(str(PurePosixPath(rel).parent))
        else:
            bad_markers.append(rel)

    def is_historical(rel: str) -> bool:
        return any(str(p) in historical_dirs for p in PurePosixPath(rel).parents)

    errors = warns = historical = scanned = 0
    for rel in files:
        path = root / rel
        if PurePosixPath(rel).name == HISTORICAL_MARKER or path.resolve() == SELF:
            continue
        text = read_text(path)
        if text is None:
            continue
        scanned += 1
        label_historical = is_historical(rel)
        for lineno, severity, matched, why in scan_text(text):
            if label_historical:
                severity = "HISTORICAL"
            print(f"{severity}: {rel}:{lineno}: {matched!r}\n        {why}")
            if severity == "ERROR":
                errors += 1
            elif severity == "WARN":
                warns += 1
            else:
                historical += 1

    for rel in bad_markers:
        print(f"ERROR: {rel}: historical marker has no reason")
        errors += 1

    # A scan of nothing proves nothing. This happens when --root is wrong or
    # sits inside a Git repository that tracks none of its files.
    if scanned == 0:
        print(f"ERROR: no tracked text files found under {root}")
        errors += 1

    print()
    print(f"scanned {scanned} tracked text files")
    print(f"errors: {errors}   warnings: {warns}   historical: {historical}")

    if errors or (args.strict and warns):
        print()
        print("Provider drift detected. Either fix the value for netcup, or add")
        print("  provider-drift-ok: <reason>")
        print("to the line if it is genuinely correct as written.")
        return 1
    print("No blocking provider drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
