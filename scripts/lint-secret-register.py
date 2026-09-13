#!/usr/bin/env python3
"""Check that every secret this repository consumes has a registered destination.

Why this exists
---------------
Gate 0 of the cluster plan requires a secret-name scan without revealing values
and stops on an unresolved secret destination. A secret that code reads but
nobody has written down the home of works on one operator's machine until the
day it is needed elsewhere.

What counts as a consumed secret
--------------------------------
  env                Ansible env lookups (lookup, query or q; short or fully
                     qualified; any number of literal names; across lines),
                     printenv or dollar references inside an Ansible pipe
                     lookup, and Python environ / getenv reads. Every name
                     counts in ansible/, scripts/, .github/, kubernetes/,
                     gitops/ and the Makefile. In other tracked code, and for
                     shell and Makefile variable references anywhere, only
                     secret-like names count (token, secret, password, key,
                     credential, PAT).
  github-actions     secrets.<name> and secrets['<name>'] inside workflow
                     expressions (GITHUB_TOKEN is built in)
  kubernetes-secret  any YAML, JSON or template file declaring kind Secret, and
                     any kustomize secretGenerator
  file               Ansible private key file settings (inventory variables,
                     ansible.cfg, the private-key command-line option), community.sops
                     lookups and ~/.config/veridex/<file> paths

Documentation (docs/, Markdown and text files) is not a consumer.

Each must appear in docs/security/secret-register.yml saying where its value is
held. The check runs both ways: consumed-but-unregistered fails, and a
registered name nothing consumes fails as stale.

It also fails when
------------------
  - a destination is empty or a placeholder, or held_in / provider names
    Hetzner or the old cluster
  - status is deferred without deferred_until_gate
  - an env lookup, a Python env read or an Actions secrets reference uses a
    name that is not a literal, or a workflow passes every secret at once
  - a literal value is assigned to a sensitive registered name, or to an
    Ansible variable fed from a sensitive env lookup -- in YAML and JSON parsed
    structurally, elsewhere line by line
  - a Kubernetes Secret, a kustomize secretGenerator or a kubectl command
    creates a secret from a literal value
  - any tracked file contains private key material (PEM or PGP private key
    blocks, age secret keys)

It never reads environment values and prints names, files and line numbers
only. This file's pattern definitions sit between the BEGIN and END secret-scan
patterns comments; only those lines are exempt from its own scan.

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
PATTERNS_BEGIN = "# BEGIN secret-scan patterns"
PATTERNS_END = "# END secret-scan patterns"

STRICT_ROOTS = ("ansible/", "scripts/", ".github/", "kubernetes/", "gitops/")
STRICT_FILES = ("Makefile",)
DOC_SUFFIXES = (".md", ".markdown", ".rst", ".txt")
STRUCTURED_SUFFIXES = (".yml", ".yaml", ".json")
SHELL_SUFFIXES = (".sh", ".bash", ".zsh", ".env", ".envrc")
MAKEFILE_NAMES = ("Makefile", "makefile", "GNUmakefile")

KINDS = {"env", "github-actions", "kubernetes-secret", "file"}
STATUSES = {"active", "deferred"}
REQUIRED_FIELDS = ("name", "kind", "sensitive", "purpose", "held_in", "provider", "status")

# BEGIN secret-scan patterns
NAME = r"([A-Za-z_][A-Za-z0-9_]*)"
QUOTE = r"\\?['\"]"
LITERAL_NAME = QUOTE + r"[A-Za-z_][A-Za-z0-9_]*" + QUOTE
ENV_PLUGIN = r"\b(?:lookup|query|q)\(\s*" + QUOTE + r"(?:ansible\.builtin\.)?env" + QUOTE

ANSIBLE_ENV_CALL = re.compile(ENV_PLUGIN + r"((?:\s*,\s*" + LITERAL_NAME + r")+)(?=\s*[,)])")
ANSIBLE_ENV_DYNAMIC = re.compile(ENV_PLUGIN + r"\s*,(?!\s*" + LITERAL_NAME + r"\s*[,)])")
QUOTED_NAME = re.compile(QUOTE + NAME + QUOTE)
ANSIBLE_PIPE_CALL = re.compile(
    r"\b(?:lookup|query|q)\(\s*" + QUOTE + r"(?:ansible\.builtin\.)?pipe" + QUOTE
    + r"\s*,\s*" + QUOTE + r"([^'\"\\]*)"
)
SHELL_ENV_READ = re.compile(r"\bprintenv\s+" + NAME + r"|\$\{?" + NAME + r"\}?")
SOPS_LOOKUP = re.compile(
    r"\b(?:lookup|query|q)\(\s*" + QUOTE + r"community\.sops\.sops" + QUOTE
    + r"\s*,\s*" + QUOTE + r"([^'\"\\]+)"
)
PYTHON_ENV_READ = re.compile(
    r"\b(?:environ(?:\.(?:get|pop|setdefault))?\s*[\[(]|getenv\()\s*['\"]" + NAME + r"['\"]"
)
PYTHON_ENV_DYNAMIC = re.compile(
    r"\b(?:environ(?:\.(?:get|pop|setdefault))?\s*[\[(]|getenv\()\s*(?=[A-Za-z_])"
)
SHELL_VAR_READ = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?|\$\(([A-Za-z_][A-Za-z0-9_]*)\)")
SECRET_LIKE = re.compile(
    r"TOKEN|SECRET|PASSW|PASSPHRASE|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY|CREDENTIAL|(?:^|_)PAT(?:_|$)",
    re.IGNORECASE,
)

ACTIONS_EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)
ACTIONS_SECRET_REF = re.compile(
    r"\bsecrets\s*(?:\.\s*" + NAME + r"|\[\s*['\"]" + NAME + r"['\"]\s*\])"
)
ACTIONS_SECRET_DYNAMIC = re.compile(r"\bsecrets\s*\[\s*(?!['\"])")
ACTIONS_ALL_SECRETS = re.compile(r"\btoJSON\s*\(\s*secrets\s*\)")
ACTIONS_INHERIT = re.compile(r"^\s*secrets\s*:\s*['\"]?inherit['\"]?\s*(?:#.*)?$", re.MULTILINE)
ACTIONS_BUILTIN = {"GITHUB_TOKEN"}

K8S_SECRET_LINE = re.compile(
    r"^\s*['\"]?kind['\"]?\s*:\s*['\"]?Secret['\"]?\s*,?\s*(?:#.*)?$", re.MULTILINE
)
KUBECTL_LITERAL_SECRET = re.compile(r"\bkubectl\s+create\s+secret\b[^\n]*--from-literal")
STRINGDATA_NON_SECRET_KEYS = {"type", "url", "project", "name", "insecure", "enableLfs", "proxy", "noProxy"}

FILE_PATTERNS = (
    re.compile(r"\bansible(?:_ssh)?_private_key_file\s*[:=]\s*['\"]?([^'\"\s#,}]+)"),
    re.compile(r"^\s*private_key_file\s*=\s*([^\s#;]+)", re.MULTILINE),
    re.compile(r"--private-key(?:=|\s+)['\"]?([^'\"\s]+)"),
    re.compile(r"(~/\.config/veridex/[A-Za-z0-9._-]+)"),
)
PYTHON_HOME_PATH = re.compile(
    r"Path\.home\(\)\s*/\s*['\"]\.config['\"]\s*/\s*['\"]veridex['\"]\s*/\s*['\"]([A-Za-z0-9._-]+)['\"]"
)

KEY_MATERIAL = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----|\bAGE-SECRET-KEY-1[0-9A-Z]{58}\b"
)
LITERAL_ASSIGNMENT = r"(?<![A-Za-z0-9_]){name}[\"']?\s*[:=]\s*[\"']?([^\s\"']{{8,}})"
TEMPLATE_MARKERS = ("{{", "{%", "lookup(", "query(", "${{", "$(", "${")

PLACEHOLDER = re.compile(r"^(?:tbd|tba|todo|unknown|unresolved|n/?a|none|null|pending|\?*)$", re.IGNORECASE)
FORBIDDEN_DESTINATION = re.compile(
    r"hetzner|hcloud|your-objectstorage|your-server\.de|k3s-ha|old cluster|entrepeai", re.IGNORECASE  # provider-drift-ok: rejects old-cluster secret destinations
)
# END secret-scan patterns


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


def pattern_block_lines(text: str) -> set[int]:
    lines = text.splitlines()
    begins = [i for i, line in enumerate(lines) if line.strip() == PATTERNS_BEGIN]
    ends = [i for i, line in enumerate(lines) if line.strip() == PATTERNS_END]
    if len(begins) != 1 or len(ends) != 1 or ends[0] <= begins[0]:
        return set()
    return set(range(begins[0] + 1, ends[0] + 2))


def blank_lines(text: str, exempt: set[int]) -> str:
    return "\n".join("" if index + 1 in exempt else line for index, line in enumerate(text.split("\n")))


def is_documentation(rel: str) -> bool:
    return rel.startswith("docs/") or rel.lower().endswith(DOC_SUFFIXES)


def is_literal(value: str | None) -> bool:
    if not value or not value.strip():
        return False
    stripped = value.strip()
    if stripped.startswith("<") and stripped.endswith(">"):
        return False  # documented placeholder
    return not any(marker in value for marker in TEMPLATE_MARKERS)


def compose_documents(text: str):
    try:
        return [node for node in yaml.compose_all(text, Loader=yaml.SafeLoader) if node is not None]
    except yaml.YAMLError:
        return None


def iter_mappings(root_node):
    stack = [root_node]
    while stack:
        node = stack.pop()
        if isinstance(node, yaml.MappingNode):
            yield node
            stack.extend(value for _, value in node.value)
        elif isinstance(node, yaml.SequenceNode):
            stack.extend(node.value)


def scalar(node) -> str | None:
    if isinstance(node, yaml.ScalarNode) and isinstance(node.value, str):
        return node.value
    return None


def mapping_get(mapping: yaml.MappingNode, key: str):
    for key_node, value_node in mapping.value:
        if scalar(key_node) == key:
            return value_node
    return None


def discover(rel: str, text: str, strict: bool, found, problems: list[str], documents) -> None:
    def at(offset: int) -> str:
        return f"{rel}:{text.count(chr(10), 0, offset) + 1}"

    def counts(name: str) -> bool:
        return strict or bool(SECRET_LIKE.search(name))

    lower = rel.lower()
    is_shell = lower.endswith(SHELL_SUFFIXES) or PurePosixPath(rel).name in MAKEFILE_NAMES

    for call in ANSIBLE_ENV_CALL.finditer(text):
        for name in QUOTED_NAME.findall(call.group(1)):
            if counts(name):
                found[("env", name)].append(at(call.start()))
    for call in ANSIBLE_ENV_DYNAMIC.finditer(text):
        problems.append(f"{at(call.start())}: env lookup with a non-literal name -- its destination cannot be checked")
    for call in ANSIBLE_PIPE_CALL.finditer(text):
        for printenv_name, dollar_name in SHELL_ENV_READ.findall(call.group(1)):
            name = printenv_name or dollar_name
            if counts(name):
                found[("env", name)].append(at(call.start()))
    for call in SOPS_LOOKUP.finditer(text):
        found[("file", call.group(1))].append(at(call.start()))
    for read in PYTHON_ENV_READ.finditer(text):
        if counts(read.group(1)):
            found[("env", read.group(1))].append(at(read.start()))
    if strict:
        for read in PYTHON_ENV_DYNAMIC.finditer(text):
            problems.append(f"{at(read.start())}: environment read with a non-literal name -- its destination cannot be checked")
    if is_shell:
        for read in SHELL_VAR_READ.finditer(text):
            name = read.group(1) or read.group(2)
            if SECRET_LIKE.search(name):
                found[("env", name)].append(at(read.start()))

    for expression in ACTIONS_EXPRESSION.finditer(text):
        body = expression.group(1)
        for dotted, indexed in ACTIONS_SECRET_REF.findall(body):
            name = dotted or indexed
            if name not in ACTIONS_BUILTIN:
                found[("github-actions", name)].append(at(expression.start()))
        if ACTIONS_SECRET_DYNAMIC.search(body):
            problems.append(f"{at(expression.start())}: Actions secrets reference with a non-literal name -- its destination cannot be checked")
        if ACTIONS_ALL_SECRETS.search(body):
            problems.append(f"{at(expression.start())}: an Actions expression serializes every repository secret -- reference secrets by name")
    if lower.endswith((".yml", ".yaml")):
        for match in ACTIONS_INHERIT.finditer(text):
            problems.append(f"{at(match.start())}: inheriting secrets passes every secret to the called workflow -- pass secrets by name")

    secret_line = K8S_SECRET_LINE.search(text)
    if secret_line:
        found[("kubernetes-secret", rel)].append(at(secret_line.start()))
    for match in KUBECTL_LITERAL_SECRET.finditer(text):
        problems.append(f"{at(match.start())}: kubectl creates a secret from a literal flag, putting its value on the command line (value not shown)")

    for document in documents or []:
        for mapping in iter_mappings(document):
            if scalar(mapping_get(mapping, "kind")) == "Secret":
                found[("kubernetes-secret", rel)].append(f"{rel}:{mapping.start_mark.line + 1}")
                for field in ("data", "stringData"):
                    block = mapping_get(mapping, field)
                    if not isinstance(block, yaml.MappingNode):
                        continue
                    for key_node, value_node in block.value:
                        key = scalar(key_node)
                        if field == "stringData" and key in STRINGDATA_NON_SECRET_KEYS:
                            continue
                        if is_literal(scalar(value_node)):
                            problems.append(
                                f"{rel}:{value_node.start_mark.line + 1}: Secret {field}.{key} holds a literal "
                                "value -- commit it encrypted or templated (value not shown)"
                            )
            generators = mapping_get(mapping, "secretGenerator")
            if isinstance(generators, yaml.SequenceNode):
                found[("kubernetes-secret", rel)].append(f"{rel}:{generators.start_mark.line + 1}")
                for generator in generators.value:
                    if not isinstance(generator, yaml.MappingNode):
                        continue
                    literals = mapping_get(generator, "literals")
                    if isinstance(literals, yaml.SequenceNode) and literals.value:
                        problems.append(
                            f"{rel}:{generator.start_mark.line + 1}: kustomize secretGenerator with literals "
                            "commits a secret value (value not shown)"
                        )

    for pattern in FILE_PATTERNS:
        for match in pattern.finditer(text):
            found[("file", match.group(1))].append(at(match.start()))
    for match in PYTHON_HOME_PATH.finditer(text):
        found[("file", f"~/.config/veridex/{match.group(1)}")].append(at(match.start()))


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
            value = entry[field]
            compact = re.sub(r"[^A-Za-z0-9/?]+", "", value) if isinstance(value, str) else ""
            if not isinstance(value, str) or PLACEHOLDER.match(compact):
                errors.append(f"{label}: {field} is empty or a placeholder -- unresolved secret destination")
        for field in ("held_in", "provider"):
            if isinstance(entry[field], str) and FORBIDDEN_DESTINATION.search(entry[field]):
                errors.append(f"{label}: {field} names Hetzner or the old cluster -- not an allowed secret destination")
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
    problems: list[str] = []

    if not files:
        print(f"ERROR: no tracked files found under {root}")
        return 1
    if REGISTER.as_posix() not in files:
        problems.append(f"{REGISTER}: not tracked -- the register must be committed")
    register = load_register(root / REGISTER, problems) if (root / REGISTER).is_file() else {}

    texts: dict[str, tuple[str, set[int]]] = {}
    documents: dict[str, list] = {}
    consumed: dict[tuple[str, str], list[str]] = defaultdict(list)

    for rel in files:
        path = root / rel
        raw = read_text(path)
        if raw is None:
            continue
        exempt = pattern_block_lines(raw) if path.resolve() == SELF else set()
        text = blank_lines(raw, exempt) if exempt else raw
        texts[rel] = (raw, exempt)
        if rel.lower().endswith(STRUCTURED_SUFFIXES):
            parsed = compose_documents(text)
            if parsed is not None:
                documents[rel] = parsed
        if rel == REGISTER.as_posix() or is_documentation(rel):
            continue
        strict = rel.startswith(STRICT_ROOTS) or rel in STRICT_FILES
        discover(rel, text, strict, consumed, problems, documents.get(rel))

    for key in sorted(consumed):
        if key not in register:
            kind, name = key
            problems.append(
                f"{kind} {name}: consumed at {consumed[key][0]} but not in {REGISTER} -- unresolved secret destination"
            )
    for key in sorted(register):
        if key not in consumed:
            kind, name = key
            problems.append(f"{REGISTER}: {kind} {name} is registered but nothing consumes it -- remove the stale entry")

    # Names whose literal assignment would commit a secret: sensitive registered
    # env / Actions names, and every Ansible variable fed from a sensitive env lookup.
    non_sensitive = {name for (kind, name), entry in register.items() if kind == "env" and entry.get("sensitive") is False}
    protected = {
        name for (kind, name), entry in register.items()
        if kind in ("env", "github-actions") and entry.get("sensitive") is not False
    }
    for rel, parsed in documents.items():
        if not rel.startswith(STRICT_ROOTS):
            continue
        for document in parsed:
            for mapping in iter_mappings(document):
                for key_node, value_node in mapping.value:
                    key, value = scalar(key_node), scalar(value_node)
                    if not key or not value:
                        continue
                    for call in ANSIBLE_ENV_CALL.finditer(value):
                        if any(name not in non_sensitive for name in QUOTED_NAME.findall(call.group(1))):
                            protected.add(key)

    for rel, parsed in documents.items():
        if rel == REGISTER.as_posix():
            continue
        for document in parsed:
            for mapping in iter_mappings(document):
                for key_node, value_node in mapping.value:
                    key = scalar(key_node)
                    if key in protected and is_literal(scalar(value_node)):
                        problems.append(
                            f"{rel}:{value_node.start_mark.line + 1}: {key} is assigned a literal value (value not shown)"
                        )

    literal_patterns = [
        (name, re.compile(LITERAL_ASSIGNMENT.format(name=re.escape(name))))
        for name in sorted(protected)
    ]
    for rel, (raw, exempt) in texts.items():
        structured = rel in documents
        for lineno, line in enumerate(raw.splitlines(), 1):
            if lineno in exempt:
                continue
            if KEY_MATERIAL.search(line):
                problems.append(f"{rel}:{lineno}: private key material in a tracked file (content not shown)")
            if structured or rel == REGISTER.as_posix():
                continue
            for name, pattern in literal_patterns:
                for match in pattern.finditer(line):
                    if is_literal(match.group(1)) and not match.group(1).startswith(("$", "{", "<")):
                        problems.append(f"{rel}:{lineno}: {name} appears to be assigned a literal value (value not shown)")

    for problem in problems:
        print(f"ERROR: {problem}")
    by_kind: dict[str, int] = defaultdict(int)
    for kind, _ in consumed:
        by_kind[kind] += 1
    print()
    print(
        f"secret register: {len(register)} entries; consumed: "
        + ", ".join(f"{by_kind[k]} {k}" for k in sorted(KINDS))
        + f"; scanned {len(texts)} tracked text files"
    )
    if problems:
        print(f"errors: {len(problems)}")
        return 1
    print("Every consumed secret has a registered destination.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
