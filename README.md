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

- Namespaces are declared **once**, in `kubernetes/cluster/namespaces/`. No other kustomization creates one.
- `kubernetes/environments/<env>/` aggregates; it never introduces resources.
- Cluster state is reconciled by Argo CD from `gitops/` — apply manifests by hand only while bootstrapping.

## Getting started

```sh
make help                      # list targets
make prepare-hosts ENV=staging
make install-cluster ENV=staging
make verify-cluster ENV=staging
make bootstrap-argocd ENV=staging
```
