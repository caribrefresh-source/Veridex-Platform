# Proposed ideal `gitops/` structure — Veridex-Platform

**Status:** Proposal only. Does not amend the Initial Stages Plan, the gate ledger, or any closed gate. Where this document and the plan disagree, the plan governs.

**Purpose:** A target structure for this repo's `gitops/` tree, grounded in what's actually built today (3 real Applications plus the `policies/` scaffold from the prior pass), what the plan explicitly names as coming, and two hard-won lessons from the K3s-HA comparison (`GitOps Structure Merge Assessment.md`, `argocd-omitempty-gotchas.md`). Every entry below is labeled by how solid its basis is — this repo is 12 gates into a 35-gate plan, so most of this tree is still a placeholder, not a fact.

## Two decisions this structure must not violate

**Cilium and CoreDNS never appear under `gitops/`.** `docs/security/cilium-coredns-ownership.md` documents this as closing part of Gate 10's End State: both are bootstrap-path components owned by Ansible (Cilium) and k3s itself (CoreDNS), verified live against the actual cluster. `root-application.yaml`'s `directory.recurse: true` picks up *anything* placed under `gitops/` with no allow-list, so a future `gitops/infrastructure/cilium/` is explicitly called out in that document as a stop-condition violation, not a routine addition. This structure has no Cilium or CoreDNS directory anywhere, on purpose.

**No Velero, no cluster-wide backup Application.** The plan's backup design is per-producer, not a single backup layer: the etcd path is a pinned b2-CLI sidecar owned by Ansible (same bootstrap-path logic as Cilium — it's not GitOps-managed), CNPG uses its own Barman Cloud plugin, MinIO gets an object-level mirror, and the Backblaze B2 buckets themselves are "provisioned as a separate infrastructure-as-code stack outside the netcup cluster" (plan text) — explicitly stated to be un-triggerable by "the cluster's own GitOps root app" (Gate 31). Nothing in `gitops/` should ever declare a bucket, a bucket policy, or a whole-cluster backup Application. Each producer's backup config lives inline with that producer's own manifests under `platform/`.

## Full tree

```
gitops/
├── README.md                           # NEW — hierarchy map, sync-wave convention, the two decisions above
│
├── bootstrap/                           # REAL, unchanged
│   ├── namespace.yaml                   # the argocd namespace — Ansible's sole bootstrap exception, explicitly excluded from root's recursion
│   └── root-application.yaml            # app-of-apps root; excludes bootstrap/** by design
│
├── projects/                            # REAL, unchanged
│   └── veridex.yaml                     # the one AppProject; RBAC roles, scoped sourceRepos/destinations
│
├── infrastructure/                      # "cluster services" (plan line 53). Provider-neutral. Never Cilium/CoreDNS.
│   ├── namespaces.yaml                  # REAL — cluster-namespaces Application, sync-wave 0
│   ├── ingress/
│   │   └── traefik.yaml                 # REAL (moved from top-level infrastructure/traefik.yaml) — makes room for cert-manager alongside it
│   ├── cert-manager/                    # PLACEHOLDER — named in the plan's own workload list (line 606: "...Argo CD, monitoring, ingress, cert-manager..."); not yet built
│   │   └── (cert-manager-app.yaml, cluster-issuer, when Gate work reaches it)
│   └── monitoring/                      # REAL content, NEW as a directory — promoted from the single monitoring.yaml before Gate 11 finishes adding Alertmanager, node-exporter, kube-state-metrics, and the rest of what that file's own comment already lists
│       └── monitoring-app.yaml          # renamed from infrastructure/monitoring.yaml
│
├── platform/                            # "data services" (plan line 53). Empty today — every entry below is a PLACEHOLDER named by Gates 12-14, not yet built.
│   ├── longhorn/                        # storage tiering — Gate 26 (node-count feasibility for longhorn-critical is still an open condition, see the capacity-budget.md conflict)
│   ├── cnpg/                            # CloudNativePG operator + cluster + Barman Cloud backup config to B2 — Gates 12, 27
│   ├── nats/                            # JetStream — Gates 14, 33 (Wave 5/Wave 6 overlap must resolve first, per Gate 33)
│   ├── temporal/                        # workflow engine — Gates 14, 33 (same overlap dependency as NATS)
│   ├── redis/                           # ephemeral cache/locks/heartbeats only — no durable workflow or session state, per the plan's own constraint
│   └── minio/                           # exactly 4 server pods across 4 labelled failure domains, never described as "4 replicas" — Gates 13, 23, 24, with object-level mirror to B2
│
├── applications/                        # "applications" (plan line 53). Empty today — grouped by the plan's own namespace rollout waves, not K3s-HA's flat numeric-prefix scheme, once anything lands.
│   ├── wave-1-foundation/               # migration-runner, auth-service, governance-service — namespace resolved at Gate 32
│   ├── wave-2-intake/                   # file-manager, ingestion-service, preview-service
│   ├── wave-3-processing/               # ocr, nlp-preprocessing, embedding, cross-encoder
│   ├── wave-4-search-rag/               # search-gateway, rag-retriever/reranker/context-builder/orchestrator, litellm-gateway
│   └── wave-5-governance/               # hitl-service, processing-authorization(-reconciler/-mode-*), notification-service, client-sync-service
│
├── policies/                            # "policies" (plan line 53). REAL, created this pass.
│   ├── README.md                        # documents what carried over from K3s-HA and what didn't (the two Rego stubs were non-functional and were not ported)
│   └── consumer-capability-gates.yaml   # scaffold, gates: [] until the first interdependent service pair exists
│
├── secrets/                             # PLACEHOLDER — mechanism is an open plan decision, not assumed
│   └── README.md                        # NEW — states plainly that §6's "SOPS + age vs. SealedSecrets and Longhorn" conflict is unresolved (must close before Gates 13/24), and that docs/security/secret-register.yml is the interim source of truth for what secrets exist and where they're held today (operator-workstation env vars, not yet in-cluster for most entries)
│
├── vendor/                              # PLACEHOLDER — empty until any chart/CRD needs pinning
│   └── (each subdirectory gets a VERSION file recording the exact upstream release it was extracted from — K3s-HA's 157 KB unpinned Velero CRD dump is the example of what not to do)
│
└── templates/                           # PLACEHOLDER — empty until an example/reference manifest is needed
    └── (never mixed with live manifests — K3s-HA's grpc-ingressroute.yaml.example living next to real IngressRoutes is the example of what not to do)
```

## What's confirmed vs. what's a placeholder

Confirmed real today: `bootstrap/`, `projects/veridex.yaml`, `infrastructure/namespaces.yaml`, `infrastructure/ingress/traefik.yaml` (path changes only — content unchanged), `policies/` (created last pass). Everything under `platform/` and `applications/` is a placeholder directory name inferred from the plan's own workload list and namespace rollout order — not a commitment to that exact layout once Gates 12-14 and 32 actually close. `secrets/`, `vendor/`, and `templates/` are placeholders for patterns worth having ready, not directories this repo needs today.

## Migration notes

Only two real moves are proposed against what exists today — everything else is either already correct or doesn't exist yet to move:

1. `infrastructure/traefik.yaml` → `infrastructure/ingress/traefik.yaml` (update `root-application.yaml`'s recursive watch needs no change — it already recurses all of `gitops/` — but confirm no other manifest hardcodes the old path).
2. `infrastructure/monitoring.yaml` → `infrastructure/monitoring/monitoring-app.yaml` (same recursion note; do this before Gate 11 adds the rest of the observability stack, not after).

Everything else — `secrets/README.md`, `gitops/README.md`, and every `platform/`/`applications/` subdirectory — is additive scaffolding with no existing file to move, so there's no sync risk in creating it ahead of the services that will eventually populate it.
