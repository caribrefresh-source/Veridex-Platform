#!/usr/bin/env python3
"""Check that every secret this repository consumes has a registered destination.

Why this exists
---------------
Gate 0 of the cluster plan requires a "secret-name scan without revealing
values" and stops on an "unresolved secret destination". A secret that code
reads from the environment but nobody has written down the home of is exactly
that: it works on one operator's machine until the day it is needed elsewhere.

What counts as a consumed secret
--------------------------------
Found in ansible/, scripts/, .github/, kubernetes/, gitops/ and the Makefile:

  env                lookup('env', 'NAME') in Ansible; os.environ / os.getenv in Python
  github-actions     ${{ secrets.NAME }} in workflows (GITHUB_TOKEN is built in)
  kubernetes-secret  any YAML or template file containing `kind: Secret`
  file               ansible_ssh_private_key_file, and ~/.config/veridex/<file> paths

Each must appear in docs/security/secret-register.yml saying where its value is
held. The check runs both ways: consumed-but-unregistered fails, and a
registered name nothing consumes fails as stale.

It also fails when
------------------
  - held_in is empty or a placeholder (an unresolved destination)
  - held_in or provider names Hetzner
  - status is deferred without deferred_until_gate
  - a registered env or Actions name is assigned a literal value in any tracked file
  - any tracked file contains a private key block

It never reads environment values, and prints names, files and line numbers only.

Usage
-----
    python3 scripts/lint-secret-register.py [--root .]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath

import yaml

SELF = Path(__file__).resolve()
REGISTER = PurePosixPath("docs/security/secret-register.yml")
CONSUMER_ROOTS = ("ansible/", "scripts/", ".github/", "kubernetes/", "gitops/")
CONSUMER_FILES = ("Makefile",)

NAME = r"([A-Za-z_][A-Za-z0-9_]*)"
ENV_PATTERNS = (
    # lookup / query / q, short or fully qualified plugin name, with quotes
    # optionally backslash-escaped inside a double-quoted YAML string.
    re.compile(
        r"(?:lookup|query|q)\(\s*\?['\"](?:ansible\.builtin\.)?env\?['\"]\s*,\s*\?['\"]"
        + NAME + r"\?['\"]"
    ),
    # os.environ or a bare `environ` (from os import environ), indexed or via
    # .get / .pop / .setdefault; os.getenv or a bare getenv.
    re.compile(r"environ(?:\.(?:get|pop|setdefault))?\s*[\[(]\s*['\"]" + NAME + r"['\"]"),
    re.compile(r"getenv\(\s*['\"]" + NAME + r"['\"]"),
)
ACTIONS_PATTERN = re.compile(r"\$\{\{\s*secrets\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
ACTIONS_BUILTIN = {"GITHUB_TOKEN"}
K8S_SECRET_PATTERN = re.compile(r"^\s*kind:\s*['\"]?Secret['\"]?\s*(?:#.*)?$")
FILE_PATTERNS = (
    re.compile(r"ansible_ssh_private_key_file:\s*['\"]?([^'\"\s#]+)"),
    re.compile(r"(~/\.config/veridex/[A-Za-z0-9._-]+)"),
)
PYTHON_HOME_PATH = re.compile(
    r"Path\.home\(\)\s*/\s*['\"]\.config['\"]\s*/\s*['\"]veridex['\"]\s*/\s*['\"]([A-Za-z0-9._-]+)['\"]"
)
PRIVATE_KEY_BLOCK = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")

KINDS = {"env", "github-actions", "kubernetes-secret", "file"}
STATUSES = {"active", "deferred"}
REQUIRED_FIELDS = ("name", "kind", "sensitive", "purpose", "held_in", "provider", "status")
PLACEHOLDER = re.compile(r"^\s*(tbd|todo|unknown|unresolved|n/?a|none|\?+)?\s*$", re.IGNORECASE)
FORBIDDEN_DESTINATION = re.compile(r"hetzner|hcloud|your-objectstorage|your-server\.de", re.IGNORECASE)


def tracked_files(root: Path) -> list[str]:
    """Files Git tracks, so CI and a local checkout scan the same set."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True
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
        return None
    return data.decode("utf-8", errors="replace")


def is_consumer(rel: str) -> bool:
    return rel.startswith(CONSUMER_ROOTS) or rel in CONSUMER_FILES


def discover(rel: str, text: str, found: dict[tuple[str, str], list[str]]) -> None:
    yamlish = rel.endswith((".yml", ".yaml", ".j2"))
    for lineno, line in enumerate(text.splitlines(), 1):
        where = f"{rel}:{lineno}"
        for pattern in ENV_PATTERNS:
            for name in pattern.findall(line):
                found[("env", name)].append(where)
        for name in ACTIONS_PATTERN.findall(line):
            if name not in ACTIONS_BUILTIN:
                found[("github-actions", name)].append(where)
        if yamlish and K8S_SECRET_PATTERN.match(line):
            found[("kubernetes-secret", rel)].append(where)
        for pattern in FILE_PATTERNS:
            for name in pattern.findall(line):
                found[("file", name)].append(where)
        for name in PYTHON_HOME_PATH.findall(line):
            found[("file", f"~/.config/veridex/{name}")].append(where)


def load_register(path: Path, errors: list[str]) -> dict[tuple[str, str], dict]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f"{REGISTER}: cannot be read ({exc.__class__.__name__})")
        return {}
    entries = (data or {}).get("secrets") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        errors.append(f"{REGISTER}: must be a mapping with a `secrets:` list")
        return {}

    register: dict[tuple[str, str], dict] = {}
    for index, entry in enumerate(entries):
        label = f"{REGISTER}: secrets[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: must be a mapping")
            continue
        missing = [f for f in REQUIRED_FIELDS if f not in entry]
        if missing:
            errors.append(f"{label}: missing {', '.join(missing)}")
            continue
        name, kind = str(entry["name"]), str(entry["kind"])
        label = f"{REGISTER}: {kind} {name}"
        if kind not in KINDS:
            errors.append(f"{label}: kind must be one of {sorted(KINDS)}")
        if not isinstance(entry["sensitive"], bool):
            errors.append(f"{label}: sensitive must be true or false")
        if entry["status"] not in STATUSES:
            errors.append(f"{label}: status must be one of {sorted(STATUSES)}")
        for field in ("purpose", "held_in", "provider"):
            if not isinstance(entry[field], str) or PLACEHOLDER.match(entry[field]):
                errors.append(f"{label}: {field} is empty or a placeholder -- unresolved secret destination")
        for field in ("held_in", "provider"):
            if isinstance(entry[field], str) and FORBIDDEN_DESTINATION.search(entry[field]):
                errors.append(f"{label}: {field} names Hetzner -- no Hetzner secret destination is allowed")
        gate = entry.get("deferred_until_gate")
        if entry["status"] == "deferred":
            if not isinstance(gate, int) or isinstance(gate, bool) or not 1 <= gate <= 31:
                errors.append(f"{label}: deferred entries need deferred_until_gate between 1 and 31")
        elif gate is not None:
            errors.append(f"{label}: deferred_until_gate is only valid when status is deferred")
        if (kind, name) in register:
            errors.append(f"{label}: registered more than once")
        register[(kind, name)] = entry
    return register


def main() -> int:
    ap = argparse.ArgumentParser(description="Check the secret register against consumed secrets.")
    ap.add_argument("--root", default=".", help="repository root (default: cwd)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    files = tracked_files(root)
    errors: list[str] = []

    if not files:
        print(f"ERROR: no tracked files found under {root}")
        return 1
    if REGISTER.as_posix() not in files:
        errors.append(f"{REGISTER}: not tracked -- the register must be committed")
    register = load_register(root / REGISTER, errors) if (root / REGISTER).is_file() else {}

    consumed: dict[tuple[str, str], list[str]] = defaultdict(list)
    texts: dict[str, str] = {}
    for rel in files:
        path = root / rel
        if path.resolve() == SELF:
            continue
        text = read_text(path)
        if text is None:
            continue
        texts[rel] = text
        if is_consumer(rel):
            discover(rel, text, consumed)

    for key in sorted(consumed):
        if key not in register:
            kind, name = key
            errors.append(
                f"{kind} {name}: consumed at {consumed[key][0]} but not in {REGISTER} -- unresolved secret destination"
            )
    for key in sorted(register):
        if key not in consumed:
            kind, name = key
            errors.append(f"{REGISTER}: {kind} {name} is registered but nothing consumes it -- remove the stale entry")

    literal_names = sorted(name for kind, name in register if kind in ("env", "github-actions"))
    literal_patterns = [
        (name, re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"\s*[:=]\s*[\"']?[^\s\"'{}$<>()\[\],;]{8,}"))
        for name in literal_names
    ]
    for rel, text in texts.items():
        if rel == REGISTER.as_posix():
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if PRIVATE_KEY_BLOCK.search(line):
                errors.append(f"{rel}:{lineno}: private key block in a tracked file (content not shown)")
            if "lookup(" in line or "{{" in line:
                continue
            for name, pattern in literal_patterns:
                if pattern.search(line):
                    errors.append(f"{rel}:{lineno}: {name} appears to be assigned a literal value (value not shown)")

    for err in errors:
        print(f"ERROR: {err}")
    by_kind = defaultdict(int)
    for kind, _ in consumed:
        by_kind[kind] += 1
    print()
    print(
        f"secret register: {len(register)} entries; consumed: "
        + ", ".join(f"{by_kind[k]} {k}" for k in sorted(KINDS))
        + f"; scanned {len(texts)} tracked text files"
    )
    if errors:
        print(f"errors: {len(errors)}")
        return 1
    print("Every consumed secret has a registered destination.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
