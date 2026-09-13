#!/usr/bin/env python3
"""Fail the build when a Hetzner dependency, Hetzner-specific value or old-cluster
identity is in the repository.

Why this exists
---------------
This platform is being rebuilt on netcup using the old Hetzner cluster as the
reference implementation. The reference is read constantly during the
migration, so provider-specific values get copied across by reflex: an hcloud
StorageClass, an address from the old private network, an old datacenter
location. Each one works right up until it silently doesn't, because netcup has
none of them.

A grep run once during migration catches today's leaks. This runs on every
commit and catches tomorrow's.

Why every tracked file
----------------------
Revision 3 of the cluster plan (Gate 0) requires that no Hetzner endpoint,
variable, backend configuration, bucket, DNS, credential, documentation
instruction or workflow dependency remains anywhere -- not only in live
configuration -- and that historical references are explicitly labelled
historical, and it stops on ambiguous cluster identity. A command file telling
an operator to run against the old inventory is as much a dependency as a
manifest that uses it. So this scans every file Git tracks.

What it does NOT flag
---------------------
Prose that names Hetzner, outside .claude/. The rules match provider-specific
values and old-cluster identity, not the word, so explaining why netcup differs
never fails the build. Inside .claude/ -- agent and operator instructions --
the word itself is an error: an instruction there is a dependency.

Comment-only lines are skipped in code and configuration: lines starting with
a hash or a double slash, and a line that is entirely one HTML comment. In
Markdown a line starting with a hash is a heading, and it is scanned.

How text is read
----------------
The encoding comes from a byte-order mark (UTF-8, UTF-16, UTF-32), otherwise
UTF-8. A file containing NUL bytes without a byte-order mark is skipped only if
its extension is a known binary type; otherwise it is an ERROR, because other
tools may still read it as text. Backslash-newline continuations are joined.
Each line is NFKC-normalized, dash punctuation is folded to a hyphen, dot
look-alikes to a full stop, and invisible format characters are removed. YAML
files are also parsed and every scalar is scanned after YAML unescaping, so an
escape sequence cannot hide a value.

Labelling exceptions
--------------------
One line: provider-drift-ok, a colon, then a reason of at least three words, in
any comment syntax. Every suppression is printed with its reason and counted.

Historical records: a file named .provider-drift-historical, containing the
reason, marks its directory tree historical. Findings there are reported as
HISTORICAL and never fail the build. Markers are honoured only under docs/; a
marker anywhere else is an ERROR, because labelling live configuration
historical would silence this check.

This file's own rule table sits between the BEGIN and END provider-drift rules
comments; only those lines are exempt when the linter scans itself.

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

import yaml

SELF = Path(__file__).resolve()
RULES_BEGIN = "# BEGIN provider-drift rules"
RULES_END = "# END provider-drift rules"

HISTORICAL_MARKER = ".provider-drift-historical"
HISTORICAL_ROOT = "docs/"
SUPPRESS = re.compile(r"provider-drift-ok:(.*)")
COMMENT_CLOSERS = re.compile(r"(-->|\*/)\s*$")
MIN_REASON_WORDS = 3

MARKDOWN_SUFFIXES = (".md", ".markdown")
YAML_SUFFIXES = (".yml", ".yaml")
BINARY_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".icns", ".webp", ".bmp", ".pdf",
    ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".jar", ".war", ".whl",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp3", ".mp4", ".wav", ".webm",
    ".wasm", ".so", ".dll", ".dylib", ".exe", ".bin", ".pyc", ".class",
)
BYTE_ORDER_MARKS = (
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)

# Code points folded in addition to Unicode dash punctuation (category Pd):
# minus sign and hyphen bullet. Dot look-alikes: ideographic full stop,
# halfwidth ideographic full stop, small full stop, one dot leader, Syriac
# supralinear and sublinear full stops.
EXTRA_DASHES = frozenset({0x2212, 0x2043})
DOT_LOOKALIKES = frozenset({0x3002, 0xFF61, 0xFE52, 0x2024, 0x0701, 0x0702})


# BEGIN provider-drift rules
# (severity, pattern, explanation, path prefixes the rule is limited to or None)
# Ordered most specific first: a later rule's match that overlaps an earlier
# match on the same line is not reported again.
RULES: list[tuple[str, re.Pattern, str, tuple[str, ...] | None]] = [
    ("ERROR", re.compile(r"caribrefresh-source/k3s-ha\b", re.IGNORECASE),
     "K3s-HA repository -- the netcup platform's source of truth is "
     "caribrefresh-source/Veridex-Platform", None),
    ("ERROR", re.compile(r"\bk3s-ha-(?:server|agent)-\d+", re.IGNORECASE),
     "Hetzner node name -- netcup nodes are veridex-server-N / veridex-agent-N", None),
    ("ERROR", re.compile(r"(?:\*|\b[a-z0-9-]+)\.entrepeai\.com\b", re.IGNORECASE),
     "entrepeai.com hostname -- resolves through Hetzner DNS to the K3s-HA "
     "cluster; platform hostnames live under veridexeai.com", None),
    ("ERROR", re.compile(r"(?<![a-z0-9])k3s-ha\b", re.IGNORECASE),
     "names the Hetzner K3s-HA cluster, its kube context or its repository -- "
     "target the netcup cluster; label history", None),
    ("ERROR", re.compile(r"\bcsi\.hetzner\.cloud\b", re.IGNORECASE),
     "Hetzner CSI provisioner -- netcup has no CSI driver", None),
    ("ERROR", re.compile(r"load-balancer\.hetzner\.cloud", re.IGNORECASE),
     "Hetzner CCM LoadBalancer annotation -- netcup has no managed LB", None),
    ("ERROR", re.compile(r"your-objectstorage\.com", re.IGNORECASE),
     "Hetzner Object Storage endpoint -- backups go to Wasabi; no Hetzner "
     "bucket may be required by production or recovery", None),
    ("ERROR", re.compile(r"\b(?:[a-z0-9-]+\.)*(?:hetzner\.(?:com|de|cloud)|your-server\.de)\b", re.IGNORECASE),
     "Hetzner hostname (API, DNS, nameserver, console, robot, charts) -- no "
     "netcup dependency on it", None),
    ("ERROR", re.compile(r"\bhcloud-volumes\b"),
     "Hetzner StorageClass name -- does not exist on netcup", None),
    ("ERROR", re.compile(r"\bhcloud_[a-z][a-z0-9_]*"),
     "Hetzner Cloud variable or Terraform resource -- no netcup equivalent", None),
    ("ERROR", re.compile(r"\b(?:HCLOUD|HETZNER)_[A-Z0-9_]+|hetznercloud/hcloud"),
     "Hetzner credential, variable or Terraform provider -- no netcup equivalent", None),
    ("ERROR", re.compile(
        r"\bhcloud\s+(?:server|network|volume|load-balancer|context|firewall|image|ssh-key"
        r"|floating-ip|primary-ip|certificate|datacenter|location|placement-group)\b"),
     "Hetzner Cloud CLI command -- no netcup equivalent", None),
    ("ERROR", re.compile(r"\binventory/hcloud\b|plugin:\s*hcloud"),
     "Hetzner inventory -- netcup's inventory is ansible/inventory/production/hosts.yml", None),
    ("ERROR", re.compile(r"cloud-provider=external"),
     "requires a CCM to clear node.cloudprovider.kubernetes.io/uninitialized; "
     "netcup has none, so nodes would never schedule", None),
    ("ERROR", re.compile(r"\b10\.1\.\d{1,3}\.\d{1,3}\b"),
     "Hetzner private network (10.1.0.0/16) -- netcup uses 10.2.0.0/16", None),
    ("ERROR", re.compile(r"\b(?:nbg1|fsn1|hel1)\b|\blocation\s*[:=]\s*[\"']?(?:ash|hil|sin)\b", re.IGNORECASE),
     "Hetzner datacenter location -- netcup uses site id 1 (Nuremberg)", None),
    ("ERROR", re.compile(r"\bHetzner\b", re.IGNORECASE),
     "Hetzner named in agent or operator instructions -- nothing in .claude/ "
     "may reference Hetzner; move history to docs/ under a historical marker", (".claude/",)),

    # Context-dependent: only drift if the cluster keeps distinct pod/service
    # CIDRs. Pending that decision these report without failing.
    ("WARN", re.compile(r"\b10\.4[23]\.\d{1,3}\.\d{1,3}\b|10\.4[23]\.0\.0/16"),
     "Hetzner pod/service CIDR -- drift only if this cluster uses distinct ranges", None),
]
# END provider-drift rules


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


def read_text(path: Path, rel: str) -> tuple[str | None, str | None]:
    """Return (text, problem). A known binary file returns (None, None)."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        return None, f"cannot be read ({exc.__class__.__name__})"
    for bom, encoding in BYTE_ORDER_MARKS:
        if data.startswith(bom):
            try:
                return data.decode(encoding), None
            except UnicodeDecodeError:
                return None, "starts with a byte-order mark but does not decode"
    if b"\0" in data:
        if rel.lower().endswith(BINARY_SUFFIXES):
            return None, None
        return None, ("contains NUL bytes without a byte-order mark; other tools may "
                      "still read it as text, so it cannot be skipped")
    return data.decode("utf-8", errors="replace"), None


def normalize(line: str) -> str:
    """Fold look-alikes to ASCII and drop invisible format characters.

    NFKC folds fullwidth and compatibility forms. Every dash-punctuation
    character, the minus sign and the hyphen bullet become a hyphen; dot
    look-alikes become a full stop; category Cf characters (zero-width space
    and joiners, soft hyphen, bidi controls) are removed, so they cannot split
    a match while the text still reads as the flagged value.
    """
    out = []
    for ch in unicodedata.normalize("NFKC", line):
        category = unicodedata.category(ch)
        code = ord(ch)
        if category == "Cf":
            continue
        if category == "Pd" or code in EXTRA_DASHES:
            out.append("-")
        elif code in DOT_LOOKALIKES:
            out.append(".")
        else:
            out.append(ch)
    return "".join(out)


def logical_lines(text: str):
    """Yield (first physical line number, line) with backslash-newline joined."""
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        start = index
        line = lines[index]
        while line.endswith("\\") and index + 1 < len(lines):
            index += 1
            line = line[:-1] + lines[index]
        yield start + 1, line
        index += 1


def is_comment_only(stripped: str, rel: str) -> bool:
    if stripped.startswith("<!--") and stripped.endswith("-->") and "-->" not in stripped[4:-3]:
        return True
    if rel.lower().endswith(MARKDOWN_SUFFIXES):
        return False
    return stripped.startswith(("#", "//"))


def suppression(line: str) -> tuple[bool, str]:
    match = SUPPRESS.search(line)
    if not match:
        return False, ""
    return True, COMMENT_CLOSERS.sub("", match.group(1)).strip()


def reason_is_real(reason: str) -> bool:
    return len(re.findall(r"[A-Za-z0-9]+", reason)) >= MIN_REASON_WORDS


def match_rules(text: str, rel: str) -> list[tuple[str, str, str]]:
    normalized = normalize(text)
    taken: list[tuple[int, int]] = []
    hits = []
    for severity, pattern, why, scope in RULES:
        if scope and not rel.startswith(scope):
            continue
        for match in pattern.finditer(normalized):
            start, end = match.span()
            if any(start < taken_end and taken_start < end for taken_start, taken_end in taken):
                continue
            taken.append((start, end))
            hits.append((severity, match.group(0), why))
    return hits


def rule_table_lines(text: str) -> set[int]:
    """Line numbers of this file's rule table: the only part exempt from its own scan."""
    lines = text.splitlines()
    begins = [i for i, line in enumerate(lines) if line.strip() == RULES_BEGIN]
    ends = [i for i, line in enumerate(lines) if line.strip() == RULES_END]
    if len(begins) != 1 or len(ends) != 1 or ends[0] <= begins[0]:
        return set()
    return set(range(begins[0] + 1, ends[0] + 2))


def scan_text(text: str, rel: str, exempt: set[int]):
    findings: list[tuple[int, str, str, str]] = []
    suppressions: list[tuple[int, str, list[str]]] = []
    for lineno, raw in logical_lines(text):
        if lineno in exempt:
            continue
        stripped = raw.strip()
        if not stripped or is_comment_only(stripped, rel):
            continue
        hits = match_rules(raw, rel)
        if not hits:
            continue
        present, reason = suppression(raw)
        if present and reason_is_real(reason):
            suppressions.append((lineno, reason, [token for _, token, _ in hits]))
            continue
        if present:
            findings.append((lineno, "ERROR", "provider-drift-ok",
                             "suppression needs a reason of at least three words"))
        for severity, token, why in hits:
            findings.append((lineno, severity, token, why))
    return findings, suppressions


def scan_yaml_values(text: str, rel: str) -> list[tuple[int, str, str, str]]:
    """Scan every YAML scalar after unescaping; invalid YAML is left to yamllint."""
    try:
        documents = [node for node in yaml.compose_all(text, Loader=yaml.SafeLoader) if node is not None]
    except yaml.YAMLError:
        return []
    findings = []
    stack = list(documents)
    while stack:
        node = stack.pop()
        if isinstance(node, yaml.ScalarNode):
            if isinstance(node.value, str):
                for severity, token, why in match_rules(node.value, rel):
                    findings.append((node.start_mark.line + 1, severity, token, why))
        elif isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                stack.extend((key, value))
        elif isinstance(node, yaml.SequenceNode):
            stack.extend(node.value)
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect Hetzner drift anywhere in the repo.")
    ap.add_argument("--strict", action="store_true", help="treat WARN as failure")
    ap.add_argument("--root", default=".", help="repository root (default: cwd)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    files = tracked_files(root)
    errors = warns = historical = scanned = suppressed_total = 0

    historical_dirs: set[str] = set()
    for rel in files:
        if PurePosixPath(rel).name != HISTORICAL_MARKER:
            continue
        text, _ = read_text(root / rel, rel)
        if not rel.startswith(HISTORICAL_ROOT):
            print(f"ERROR: {rel}: historical marker outside {HISTORICAL_ROOT} -- "
                  "live configuration cannot be labelled historical")
            errors += 1
        elif not (text or "").strip():
            print(f"ERROR: {rel}: historical marker has no reason")
            errors += 1
        else:
            historical_dirs.add(str(PurePosixPath(rel).parent))

    def is_historical(rel: str) -> bool:
        return any(str(parent) in historical_dirs for parent in PurePosixPath(rel).parents)

    for rel in files:
        if PurePosixPath(rel).name == HISTORICAL_MARKER:
            continue
        path = root / rel
        text, problem = read_text(path, rel)
        if problem:
            print(f"ERROR: {rel}: {problem}")
            errors += 1
            continue
        if text is None:
            continue
        scanned += 1

        exempt = rule_table_lines(text) if path.resolve() == SELF else set()
        findings, suppressions = scan_text(text, rel, exempt)
        if rel.lower().endswith(YAML_SUFFIXES):
            suppressed_lines = {lineno for lineno, _, _ in suppressions}
            seen = {(lineno, severity, token.lower()) for lineno, severity, token, _ in findings}
            for lineno, severity, token, why in scan_yaml_values(text, rel):
                key = (lineno, severity, token.lower())
                if lineno in exempt or lineno in suppressed_lines or key in seen:
                    continue
                seen.add(key)
                findings.append((lineno, severity, token, why))

        label_historical = is_historical(rel)
        for lineno, severity, matched, why in sorted(findings):
            if label_historical:
                severity = "HISTORICAL"
            print(f"{severity}: {rel}:{lineno}: {matched!r}\n        {why}")
            if severity == "ERROR":
                errors += 1
            elif severity == "WARN":
                warns += 1
            else:
                historical += 1
        for lineno, reason, tokens in suppressions:
            print(f"SUPPRESSED: {rel}:{lineno}: {', '.join(map(repr, tokens))} -- {reason}")
            suppressed_total += 1

    # A scan of nothing proves nothing. This happens when --root is wrong or
    # sits inside a Git repository that tracks none of its files.
    if scanned == 0:
        print(f"ERROR: no tracked text files found under {root}")
        errors += 1

    print()
    print(f"scanned {scanned} tracked text files")
    print(f"errors: {errors}   warnings: {warns}   historical: {historical}   suppressed: {suppressed_total}")

    if errors or (args.strict and warns):
        print()
        print("Provider drift detected. Either fix the value for netcup, or add")
        print("  provider-drift-ok: <a reason of at least three words>")
        print("to the line if it is genuinely correct as written.")
        return 1
    print("No blocking provider drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
