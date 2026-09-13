# Veridex Platform

Build the K3s cluster: infrastructure, GitOps configuration, and application
source for the Veridex platform.

## Layout

| Path | Purpose |
| --- | --- |
| `ansible/` | Host preparation and k3s cluster installation (servers, agents, kubeconfig, Argo CD bootstrap). |
| `kubernetes/cluster/` | Namespaces — **the only place namespaces are declared** — plus quotas, LimitRanges, and the default-deny baseline. |
| `kubernetes/infrastructure/` | Cluster-level components: Cilium, ingress, cert-manager, storage, sealed-secrets, observability. |
| `kubernetes/platform/` | Shared services: databases, messaging, workflow, object storage. |
| `kubernetes/applications/` | Per-application manifests. |
| `kubernetes/environments/` | Aggregating kustomizations only — **no resources of their own**; each lists the app overlays present in that environment. |
| `gitops/` | Argo CD bootstrap, projects, and the Applications that reconcile everything under `kubernetes/`. |
| `apps/`, `services/`, `packages/` | Application, service, and shared-library source. |
| `schemas/` | Shared contracts and schema definitions. |
| `scripts/`, `tests/`, `docs/` | Tooling, test suites, documentation. |

## Conventions

- Namespaces are declared exactly once. All Argo CD-managed workload and platform
  namespaces are declared under `kubernetes/cluster/namespaces/`. The `argocd`
  namespace is the sole bootstrap exception and is declared only in
  `gitops/bootstrap/namespace.yaml`, because it must exist before Argo CD can
  reconcile cluster state. No other manifest or kustomization may create a
  Namespace.
- `kubernetes/environments/<env>/` aggregates; it never introduces resources.
- Cluster state is reconciled by Argo CD from `gitops/` — apply manifests by hand only while bootstrapping.

## Getting started

```sh
make help                        # list targets
make bring-up ENV=production     # the whole sequence, in order
```

Or step by step. The order matters: the servers run with
`flannel-backend=none`, so every node — agents included — stays `NotReady`
until Cilium lands. Running `bootstrap-argocd` before `install-cilium`
leaves Argo CD with nowhere to schedule.

```sh
make prepare-hosts ENV=production     # baseline + nftables, before k3s
make install-cluster ENV=production   # k3s servers, then agents
make install-cilium ENV=production    # CNI — nodes go Ready here
make verify-cluster ENV=production
make bootstrap-argocd ENV=production
```

`ENV` selects the inventory under `ansible/inventory/`. It defaults to
`staging`, which currently declares no hosts — pass `ENV=production` to
target the real fleet.
