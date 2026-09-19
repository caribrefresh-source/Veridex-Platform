#!/usr/bin/env python3
"""Fail-closed validation for the Gate 32 namespace contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

MAP_PATH = Path("docs/architecture/namespace-map.yaml")
ACTIVE = "kubernetes/cluster/namespaces/active/"
WORKLOAD_PATH = Path("docs/architecture/workload-namespace-map.yaml")
PLANNED = "kubernetes/cluster/namespaces/planned/"
REPO_URL = "https://github.com/caribrefresh-source/Veridex-Platform.git"
SERVER = "https://kubernetes.default.svc"
WORKLOAD_KINDS = {"CronJob", "DaemonSet", "Deployment", "Job", "StatefulSet"}
REQUIRED_MAP_FIELDS = {"name", "lifecycle", "wave", "role", "owner", "recoveryClass"}
REQUIRED_LABELS = {
    "veridex.io/wave", "veridex.io/role", "veridex.io/lifecycle",
    "veridex.io/recovery-class", "veridex.io/data-classification",
}
REQUIRED_ANNOTATIONS = {
    "veridex.io/owner", "veridex.io/purpose", "argocd.argoproj.io/sync-options",
}


def documents(path: Path):
    try:
        parsed = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot parse {path.as_posix()}: {exc}") from exc
    return [doc for doc in parsed if isinstance(doc, dict)]


def load_map(root: Path):
    docs = documents(root / MAP_PATH)
    if len(docs) != 1 or docs[0].get("kind") != "NamespaceMap":
        raise ValueError(f"{MAP_PATH.as_posix()} must contain one NamespaceMap")
    spec = docs[0].get("spec") or {}
    mapped = {}
    for entry in spec.get("namespaces") or []:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not name or name in mapped:
            raise ValueError(f"namespace map has missing or duplicate name: {name!r}")
        missing = REQUIRED_MAP_FIELDS - set(entry)
        if missing:
            raise ValueError(f"namespace map entry {name!r} misses {sorted(missing)}")
        if entry["lifecycle"] not in {"active", "planned", "bootstrap", "builtin"}:
            raise ValueError(f"namespace map entry {name!r} has invalid lifecycle")
        for key in REQUIRED_MAP_FIELDS:
            if entry.get(key) in (None, ""):
                raise ValueError(f"namespace map entry {name!r} has empty {key}")
        mapped[name] = entry
    workload_docs = documents(root / WORKLOAD_PATH)
    if len(workload_docs) != 1 or workload_docs[0].get("kind") != "WorkloadNamespaceMap":
        raise ValueError(f"{WORKLOAD_PATH.as_posix()} must contain one WorkloadNamespaceMap")
    workload_spec = workload_docs[0].get("spec") or {}
    workloads = {}
    for item in workload_spec.get("workloads") or []:
        name = item.get("name") if isinstance(item, dict) else None
        namespace = item.get("namespace") if isinstance(item, dict) else None
        if not name or not namespace:
            raise ValueError("each workload requires non-empty name and namespace")
        if name in workloads:
            raise ValueError(f"workload {name!r} is mapped more than once")
        if namespace not in mapped:
            raise ValueError(f"workload {name!r} targets unknown namespace {namespace!r}")
        workloads[name] = namespace
    if not workloads:
        raise ValueError("namespace map workload inventory is empty")
    deployed = {}
    for item in workload_spec.get("deployedResources") or []:
        if not isinstance(item, dict):
            raise ValueError("each deployed resource must be an object")
        missing = {"workload", "kind", "name", "namespace", "path"} - set(item)
        if missing:
            raise ValueError(f"deployed resource misses {sorted(missing)}")
        workload = item["workload"]
        kind = item["kind"]
        name = item["name"]
        namespace = item["namespace"]
        path = item["path"]
        if kind not in WORKLOAD_KINDS:
            raise ValueError(f"deployed resource {kind}/{name} has unsupported kind")
        if workload not in workloads:
            raise ValueError(f"deployed resource {kind}/{name} references unknown workload {workload!r}")
        if namespace != workloads[workload]:
            raise ValueError(
                f"deployed resource {kind}/{name} namespace {namespace!r} disagrees "
                f"with workload {workload!r} namespace {workloads[workload]!r}"
            )
        if not isinstance(path, str) or not path.startswith("kubernetes/") or not path.endswith((".yaml", ".yml")):
            raise ValueError(f"deployed resource {kind}/{name} has invalid manifest path")
        key = (kind, namespace, name)
        if key in deployed:
            raise ValueError(f"deployed resource {kind}/{namespace}/{name} is mapped more than once")
        deployed[key] = {"workload": workload, "path": path}
    if not deployed:
        raise ValueError("deployed resource inventory is empty")
    return (
        mapped,
        workloads,
        deployed,
        set(spec.get("forbiddenNames") or []),
        tuple(spec.get("forbiddenPrefixes") or []),
    )


def validate(root: Path):
    errors = []
    try:
        mapped, _, deployed, forbidden, prefixes = load_map(root)
    except ValueError as exc:
        return [str(exc)]

    for name in mapped:
        if name in forbidden or any(name.startswith(prefix) for prefix in prefixes):
            errors.append(f"{name!r}: forbidden namespace name appears in map")

    declarations = {}
    applications = []
    projects = {}
    discovered_workloads = {}
    for base_name in ("kubernetes", "gitops"):
        base = root / base_name
        for path in sorted(base.rglob("*.y*ml")):
            rel = path.relative_to(root).as_posix()
            try:
                docs = documents(path)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            for doc in docs:
                kind = doc.get("kind")
                meta = doc.get("metadata") or {}
                if kind == "Namespace":
                    name = meta.get("name")
                    if not isinstance(name, str) or not name:
                        errors.append(f"{rel}: Namespace has missing/non-string name")
                    else:
                        declarations.setdefault(name, []).append((rel, meta))
                elif kind == "Application":
                    applications.append((rel, doc))
                elif kind == "AppProject":
                    name = meta.get("name")
                    if name in projects:
                        errors.append(f"{name!r}: AppProject declared more than once")
                    projects[name] = (rel, doc)
                if base_name == "kubernetes" and kind in WORKLOAD_KINDS:
                    name = meta.get("name")
                    namespace = meta.get("namespace")
                    if not isinstance(name, str) or not name:
                        errors.append(f"{rel}: {kind} has missing/non-string name")
                        continue
                    if not isinstance(namespace, str) or not namespace:
                        errors.append(f"{rel}: {kind}/{name} must declare metadata.namespace")
                        continue
                    key = (kind, namespace, name)
                    if key in discovered_workloads:
                        errors.append(f"{kind}/{namespace}/{name}: workload controller declared more than once")
                    discovered_workloads[key] = rel
                    registered = deployed.get(key)
                    if not registered:
                        errors.append(f"{rel}: unregistered deployed workload {kind}/{namespace}/{name}")
                    elif registered["path"] != rel:
                        errors.append(
                            f"{kind}/{namespace}/{name}: manifest path {rel!r} disagrees "
                            f"with registry path {registered['path']!r}"
                        )

    for key, registered in sorted(deployed.items()):
        if key not in discovered_workloads:
            kind, namespace, name = key
            errors.append(
                f"registered deployed workload {kind}/{namespace}/{name} "
                f"not found at {registered['path']}"
            )

    for name, items in sorted(declarations.items()):
        if len(items) != 1:
            errors.append(f"{name!r}: declared {len(items)} times")
            continue
        rel, meta = items[0]
        if name == "argocd":
            continue
        if name not in mapped:
            errors.append(f"{name!r}: declaration is absent from namespace map")
            continue
        entry = mapped[name]
        lifecycle = entry["lifecycle"]
        expected_prefix = ACTIVE if lifecycle == "active" else PLANNED if lifecycle == "planned" else None
        if expected_prefix and not rel.startswith(expected_prefix):
            errors.append(f"{name!r}: lifecycle {lifecycle!r} requires path {expected_prefix}")
        labels = meta.get("labels") or {}
        annotations = meta.get("annotations") or {}
        for key in sorted(REQUIRED_LABELS):
            if labels.get(key) in (None, ""):
                errors.append(f"{name!r}: missing or empty label {key}")
        for key in sorted(REQUIRED_ANNOTATIONS):
            if annotations.get(key) in (None, ""):
                errors.append(f"{name!r}: missing or empty annotation {key}")
        comparisons = {
            "veridex.io/lifecycle": lifecycle,
            "veridex.io/wave": str(entry["wave"]),
            "veridex.io/role": entry["role"],
            "veridex.io/recovery-class": entry["recoveryClass"],
        }
        for key, expected in comparisons.items():
            if str(labels.get(key)) != str(expected):
                errors.append(f"{name!r}: manifest {key} disagrees with map")
        if annotations.get("veridex.io/owner") != entry["owner"]:
            errors.append(f"{name!r}: manifest owner disagrees with map")
        sync_options = str(annotations.get("argocd.argoproj.io/sync-options", ""))
        if "Prune=false" not in sync_options or "Delete=false" not in sync_options:
            errors.append(f"{name!r}: Namespace lacks prune/delete protection")

    for name, entry in mapped.items():
        if entry["lifecycle"] in {"active", "planned"} and name not in declarations:
            errors.append(f"{name!r}: mapped namespace has no manifest")

    for rel, app in applications:
        spec = app.get("spec") or {}
        if spec.get("project") != "veridex":
            errors.append(f"{rel}: Application must use project veridex")
        source = spec.get("source") or {}
        if source.get("repoURL") != REPO_URL:
            errors.append(f"{rel}: Application source repoURL is not approved")
        if source.get("targetRevision") != "main":
            errors.append(f"{rel}: Application targetRevision must be main")
        destination = spec.get("destination") or {}
        if destination.get("server") != SERVER:
            errors.append(f"{rel}: Application destination server is not in-cluster")
        dest = destination.get("namespace")
        if dest == "*" or dest not in mapped:
            errors.append(f"{rel}: destination namespace {dest!r} is not approved")
        elif mapped[dest]["lifecycle"] == "planned":
            errors.append(f"{rel}: Application targets planned namespace {dest!r}")

    project = projects.get("veridex")
    if not project:
        errors.append("veridex AppProject is missing")
    else:
        spec = project[1].get("spec") or {}
        if spec.get("sourceRepos") != [REPO_URL]:
            errors.append("veridex AppProject sourceRepos differs from approved repository")
        destinations = spec.get("destinations") or []
        pairs = [(item.get("server"), item.get("namespace")) for item in destinations]
        expected = {(SERVER, name) for name in mapped}
        if set(pairs) != expected or len(pairs) != len(set(pairs)):
            errors.append("veridex AppProject destinations differ from exact map/server pairs")

    default = projects.get("default")
    if not default:
        errors.append("default AppProject deny manifest is missing")
    else:
        spec = default[1].get("spec") or {}
        if spec.get("sourceRepos") != ["https://invalid.invalid/disabled.git"]:
            errors.append("default AppProject source is not the disabled sentinel")
        destinations = spec.get("destinations") or []
        expected = [(SERVER, "__disabled_default_project__")]
        actual = [(item.get("server"), item.get("namespace")) for item in destinations]
        if actual != expected:
            errors.append("default AppProject destination is not the disabled sentinel")
        if spec.get("clusterResourceWhitelist") != []:
            errors.append("default AppProject cluster resource whitelist must be empty")
        if spec.get("namespaceResourceWhitelist") != []:
            errors.append("default AppProject namespace resource whitelist must be empty")

    namespace_app = next(
        (app for _, app in applications if (app.get("metadata") or {}).get("name") == "cluster-namespaces"),
        None,
    )
    if not namespace_app:
        errors.append("cluster-namespaces Application is missing")
    else:
        spec = namespace_app.get("spec") or {}
        if (spec.get("source") or {}).get("path") != ACTIVE.rstrip("/"):
            errors.append("cluster-namespaces must source only the active directory")
        automated = (spec.get("syncPolicy") or {}).get("automated") or {}
        if automated.get("prune") is True:
            errors.append("cluster-namespaces automated prune must be disabled")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    errors = validate(Path(args.root).resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"{len(errors)} namespace contract violation(s).")
        return 1
    print("Namespace contract is consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
