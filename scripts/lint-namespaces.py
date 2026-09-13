#!/usr/bin/env python3
"""Enforce that every Namespace is declared exactly once, in the right place.

Why this exists
---------------
The repository rule is that namespaces are declared exactly once: Argo CD-
managed workload and platform namespaces under kubernetes/cluster/namespaces/,
and `argocd` only in gitops/bootstrap/namespace.yaml, because it must exist
before Argo CD can reconcile anything at all.

Both halves of that rule fail quietly. A second declaration of a namespace
renders fine and applies fine -- Kustomize does not object, and the last
writer wins, so two files can disagree about a namespace's labels or quotas
with nothing to show for it until someone reads both. A workload that targets
a namespace nobody declared also renders fine, and only fails at apply time,
against a live cluster, as a namespace-not-found on an object that looks
correct in Git.

This runs on every commit instead.

What counts as a reference
--------------------------
metadata.namespace on any object, the top-level `namespace:` directive in a
kustomization, and an Argo CD Application's spec.destination.namespace.

Scope
-----
kubernetes/ and gitops/. Ansible is deliberately not scanned: it operates at
the bootstrap layer, below Argo CD, and the only namespaces it touches are
kube-system (a Kubernetes built-in) and argocd (the documented exception).

Usage
-----
    python3 scripts/lint-namespaces.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("ERROR: PyYAML is required (pip install pyyaml)", file=sys.stderr)
    raise SystemExit(2)

SCAN_DIRS = ("kubernetes", "gitops")
SUFFIXES = (".yml", ".yaml")

# Created by Kubernetes itself. Declaring these would collide with the cluster.
BUILTINS = {"default", "kube-system", "kube-public", "kube-node-lease"}

# The single documented bootstrap exception, and the only file allowed to
# declare it.
BOOTSTRAP_NS = "argocd"
BOOTSTRAP_PATH = "gitops/bootstrap/namespace.yaml"

# Where every other namespace must be declared.
NAMESPACE_DIR = "kubernetes/cluster/namespaces"

OWNER_ANNOTATION = "veridex.io/owner"
PURPOSE_ANNOTATION = "veridex.io/purpose"


def load_docs(path: Path):
    """Yield YAML documents, skipping files that are not parseable manifests."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    try:
        for doc in yaml.safe_load_all(text):
            if isinstance(doc, dict):
                yield doc
    except yaml.YAMLError:
        # Malformed YAML is yamllint's job to report, not this linter's.
        return


def collect(root: Path):
    """Return (declarations, references) found across the scanned trees."""
    declarations: list[tuple[str, str, dict]] = []   # (name, relpath, metadata)
    references: dict[str, set[str]] = {}             # name -> {relpath, ...}

    def note_ref(name, rel):
        if isinstance(name, str) and name:
            references.setdefault(name, set()).add(rel)

    for d in SCAN_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in SUFFIXES:
                continue
            rel = path.relative_to(root).as_posix()
            is_kustomization = path.stem == "kustomization"

            for doc in load_docs(path):
                meta = doc.get("metadata") or {}

                if doc.get("kind") == "Namespace":
                    name = meta.get("name")
                    if isinstance(name, str) and name:
                        declarations.append((name, rel, meta))

                # metadata.namespace on any object
                note_ref(meta.get("namespace"), rel)

                # Argo CD Application destination
                if doc.get("kind") == "Application":
                    dest = (doc.get("spec") or {}).get("destination") or {}
                    note_ref(dest.get("namespace"), rel)

                # Kustomize top-level namespace directive
                if is_kustomization:
                    note_ref(doc.get("namespace"), rel)

    return declarations, references


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate Namespace declarations.")
    ap.add_argument("--root", default=".", help="repository root (default: cwd)")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    declarations, references = collect(root)
    errors: list[str] = []

    declared_names = {name for name, _, _ in declarations}

    # 1. A referenced namespace with no declaration.
    for name, where in sorted(references.items()):
        if name in BUILTINS or name in declared_names:
            continue
        locations = ", ".join(sorted(where))
        errors.append(
            f"namespace {name!r} is referenced but never declared\n"
            f"        referenced by: {locations}\n"
            f"        declare it in {NAMESPACE_DIR}/{name}.yaml"
        )

    # 2. Duplicate declarations.
    seen: dict[str, list[str]] = {}
    for name, rel, _ in declarations:
        seen.setdefault(name, []).append(rel)
    for name, paths in sorted(seen.items()):
        if len(paths) > 1:
            errors.append(
                f"namespace {name!r} is declared {len(paths)} times\n"
                f"        in: {', '.join(sorted(paths))}\n"
                f"        exactly one declaration is allowed"
            )

    for name, rel, meta in sorted(declarations):
        annotations = meta.get("annotations") or {}

        # 3. Missing owner or purpose.
        for key in (OWNER_ANNOTATION, PURPOSE_ANNOTATION):
            value = annotations.get(key)
            if not (isinstance(value, str) and value.strip()):
                errors.append(
                    f"namespace {name!r} in {rel} is missing a non-empty "
                    f"{key} annotation"
                )

        # 4. argocd declared outside bootstrap.
        if name == BOOTSTRAP_NS and rel != BOOTSTRAP_PATH:
            errors.append(
                f"namespace 'argocd' is declared in {rel}\n"
                f"        it is the bootstrap exception and belongs only in "
                f"{BOOTSTRAP_PATH}"
            )

        # 5. Any non-bootstrap namespace declared outside the namespaces dir.
        if name != BOOTSTRAP_NS and not rel.startswith(NAMESPACE_DIR + "/"):
            errors.append(
                f"namespace {name!r} is declared in {rel}\n"
                f"        every non-bootstrap namespace belongs in {NAMESPACE_DIR}/"
            )

        # A namespace must never be one Kubernetes creates itself.
        if name in BUILTINS:
            errors.append(
                f"namespace {name!r} in {rel} is a Kubernetes built-in and "
                f"must not be declared"
            )

    print(f"declarations found: {len(declarations)}")
    for name, rel, _ in sorted(declarations):
        print(f"  {name:<24} {rel}")
    print(f"referenced namespaces: {len(references)}")
    for name in sorted(references):
        tag = " (built-in)" if name in BUILTINS else ""
        print(f"  {name}{tag}")

    print()
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        print()
        print(f"{len(errors)} namespace rule violation(s).")
        return 1
    print("Namespace declarations are consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
