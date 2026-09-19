# Namespace map

`namespace-map.yaml` and `workload-namespace-map.yaml` are the machine-readable sources of truth. This document
records the decisions behind it. A namespace is promoted only by changing its
map lifecycle and moving its manifest from `planned/` to `active/` in the same
reviewed change. Planned manifests are deliberately outside the Argo CD
`cluster-namespaces` source.

Every coded `Deployment`, `StatefulSet`, `DaemonSet`, `Job`, and `CronJob` must
also have exactly one `deployedResources` entry in `workload-namespace-map.yaml`.
That entry binds its kind, Kubernetes name, manifest path, and namespace to one
architectural workload. CI fails closed for an unregistered controller, a stale
registration, a duplicate registration, a moved manifest, or a namespace that
differs from the workload's approved namespace. Adding a future component is
therefore one reviewed atomic change: add its architectural workload mapping,
its deployed-resource registration, and its manifest.

| Wave | Namespace | Contents | Recovery contract |
|---|---|---|---|
| 1 | `veridex-policy-test` | Permanent policy regression harness; no production data | Disposable contents; retain namespace |
| 2 | `veridex-edge` | Frontend, viewer/portal, public callback adapters | Redeploy |
| 3 | `veridex-auth` | Auth service, auth CNPG/Redis, audit verifier and auth migrations | Isolated restore contract |
| 4 | `veridex-apps` | Request-driven document, governance and search APIs | Redeploy |
| 5 | `veridex-workers` | Temporal/NATS clients and reconcilers; initially zero replicas | Redeploy |
| 5 | `veridex-ai` | OCR, NLP, embeddings, RAG, LiteLLM and Ollama | Redeploy; repull cache |
| 6 | `cnpg-system` | CloudNativePG operator | Reconcile |
| 6 | `longhorn-system` | Longhorn storage controllers | Reconcile |
| 6 | `veridex-database` | Main CNPG, pooler and PITR resources | PITR |
| 6 | `veridex-object` | Four-domain MinIO and B2 mirroring | Restore or remirror |
| 6 | `veridex-messaging` | NATS JetStream and Temporal Server | Durable restore |
| 6 | `veridex-derived` | Qdrant, Meilisearch, Memgraph and shared cache Redis | Rebuild/replay is authoritative; snapshots may accelerate |

Wave 7 retains component-specific handling for `argocd`, `kube-system`,
`cert-manager`, `monitoring`, and `veridex-access`. The existing public `site`
namespace remains Wave 8 and is not silently renamed to `veridex-edge`.

Names from the reference Hetzner cluster are not target names. New
`docintel`, `data-plane`, `dip-*`, `observability`, `ingress-nginx`, and
standalone `headlamp` namespaces are forbidden.

## Promotion invariant

No production pod starts until its namespace's deny policy and minimum DNS,
probe, monitoring, quota, ServiceAccount and RBAC controls have landed as one
bundle. Removing an active manifest is not a deletion mechanism: Namespace
objects are protected from Argo pruning and require a separately authorized,
guarded decommission procedure.
