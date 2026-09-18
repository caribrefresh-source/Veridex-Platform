from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "namespace_contract", ROOT / "scripts" / "lint-namespace-contract.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class NamespaceContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in ("docs", "gitops", "kubernetes"):
            shutil.copytree(ROOT / name, self.root / name)

    def tearDown(self):
        self.temp.cleanup()

    def errors(self):
        return MODULE.validate(self.root)

    def mutate_one(self, relative, callback):
        path = self.root / relative
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        callback(documents[0])
        path.write_text(yaml.safe_dump_all(documents, sort_keys=False), encoding="utf-8")

    def test_repository_contract_passes(self):
        self.assertEqual([], self.errors())

    def test_rejects_project_default(self):
        self.mutate_one(
            "gitops/applications/site.yaml",
            lambda doc: doc["spec"].update(project="default"),
        )
        self.assertTrue(any("must use project veridex" in error for error in self.errors()))

    def test_rejects_application_targeting_planned_namespace(self):
        self.mutate_one(
            "gitops/applications/site.yaml",
            lambda doc: doc["spec"]["destination"].update(namespace="veridex-edge"),
        )
        self.assertTrue(any("targets planned namespace" in error for error in self.errors()))

    def test_rejects_missing_required_label(self):
        self.mutate_one(
            "kubernetes/cluster/namespaces/planned/veridex-edge.yaml",
            lambda doc: doc["metadata"]["labels"].pop("veridex.io/recovery-class"),
        )
        self.assertTrue(any("missing label veridex.io/recovery-class" in error for error in self.errors()))

    def test_rejects_namespace_source_outside_active(self):
        self.mutate_one(
            "gitops/infrastructure/namespaces.yaml",
            lambda doc: doc["spec"]["source"].update(path="kubernetes/cluster/namespaces"),
        )
        self.assertTrue(any("source only the active directory" in error for error in self.errors()))

    def test_rejects_malformed_yaml_fail_closed(self):
        path = self.root / "kubernetes/cluster/namespaces/planned/veridex-edge.yaml"
        path.write_text("apiVersion: v1\nmetadata: [\n", encoding="utf-8")
        self.assertTrue(any("cannot parse" in error for error in self.errors()))

    def test_rejects_wildcard_project_destination(self):
        self.mutate_one(
            "gitops/projects/veridex.yaml",
            lambda doc: doc["spec"].update(
                destinations=[{"server": "https://kubernetes.default.svc", "namespace": "*"}]
            ),
        )
        errors = self.errors()
        self.assertTrue(any("destinations differ" in error for error in errors))
        self.assertTrue(any("wildcard namespace" in error for error in errors))


    def test_rejects_external_application_server(self):
        self.mutate_one(
            "gitops/applications/site.yaml",
            lambda doc: doc["spec"]["destination"].update(server="https://evil.example"),
        )
        self.assertTrue(any("server is not in-cluster" in error for error in self.errors()))

    def test_rejects_application_source_drift(self):
        self.mutate_one(
            "gitops/applications/site.yaml",
            lambda doc: doc["spec"]["source"].update(repoURL="https://evil.example/repo.git"),
        )
        self.assertTrue(any("repoURL is not approved" in error for error in self.errors()))

    def test_rejects_map_manifest_owner_drift(self):
        self.mutate_one(
            "kubernetes/cluster/namespaces/planned/veridex-edge.yaml",
            lambda doc: doc["metadata"]["annotations"].update(
                {"veridex.io/owner": "wrong-owner"}
            ),
        )
        self.assertTrue(any("owner disagrees" in error for error in self.errors()))

    def test_rejects_duplicate_appproject(self):
        source = self.root / "gitops/projects/veridex.yaml"
        duplicate = self.root / "gitops/projects/veridex-duplicate.yaml"
        duplicate.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertTrue(any("AppProject declared more than once" in error for error in self.errors()))

    def test_rejects_default_project_resource_grant(self):
        self.mutate_one(
            "gitops/projects/default-deny.yaml",
            lambda doc: doc["spec"].update(
                clusterResourceWhitelist=[{"group": "*", "kind": "*"}]
            ),
        )
        self.assertTrue(any("cluster resource whitelist" in error for error in self.errors()))

    def test_rejects_duplicate_workload_mapping(self):
        self.mutate_one(
            "docs/architecture/workload-namespace-map.yaml",
            lambda doc: doc["spec"]["workloads"].append(
                {"name": "longhorn", "namespace": "longhorn-system"}
            ),
        )
        self.assertTrue(any("mapped more than once" in error for error in self.errors()))

    def test_rejects_external_appproject_server(self):
        self.mutate_one(
            "gitops/projects/veridex.yaml",
            lambda doc: doc["spec"]["destinations"][0].update(
                server="https://evil.example"
            ),
        )
        self.assertTrue(any("exact map/server pairs" in error for error in self.errors()))


if __name__ == "__main__":
    unittest.main()

