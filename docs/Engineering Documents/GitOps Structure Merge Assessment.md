# GitOps structure merge assessment — K3s-HA proposal vs. Veridex-Platform actual

**Status:** Assessment only. Does not amend the Initial Stages Plan, the gate ledger, or any closed gate. Where this document and the plan disagree, the plan governs.

**Purpose:** `docs/operations/proposed-gitops-structure.md` in the K3s-HA repo is a rewrite proposal for that repo's own sprawling, 70-Application Hetzner `gitops/` tree. This Veridex-Platform repo's `gitops/` is a separate, much younger, gate-governed netcup-native tree (3 real Applications; `applications/` and `platform/` are still empty `.gitkeep` placeholders). They are not two drafts of the same thing — one is the legacy source, the other is the actual destination. This document reconciles them: which of the K3s-HA proposal's fixes still apply here, and what this repo already does better that should be documented so it doesn't regress.

## Concept mapping

| K3s-HA proposal | Veridex-Platform (this repo, actual) | Verdict |
| --- | --- | --- |
| `base/` | `infrastructure/` | Adopt this repo's name — no reason to diverge from the live convention. |
| `data-plane/` (one tier) | `platform/` (empty) + `applications/` (empty) | This repo already anticipates a two-tier split the K3s-HA proposal collapsed into one. The plan's own GitOps-boundary line (Initial Stages Plan, line 53) names four categories Argo CD owns: cluster services, data services, policies, applications. Map `infrastructure/` → cluster services, `platform/` → data services (CNPG, NATS, MinIO, Redis, Temporal), `applications/` → the DIP microservices, when each is built. |
| `provider-overlays/{hetzner,netcup}` | none | Not needed here. This repo is netcup-native from day one — nothing to isolate. Stays a K3s-HA-only concern for the coexistence/rollback window. |
| `observability/` (consolidated, fixing 4 scattered homes in K3s-HA) | `infrastructure/monitoring.yaml` (single file, Gate 11 in progress) | Already consistent — no scatter yet. But `monitoring.yaml`'s own comment lists VictoriaMetrics, vmagent, vmalert, Alertmanager, node-exporter, kube-state-metrics, and Loki all going into one Application — the exact shape that fragmented into four directories in K3s-HA. **Recommend promoting `infrastructure/monitoring.yaml` to `infrastructure/monitoring/` (a directory) before Gate 11 finishes**, not after. |
| `partials/_ignore-prune-false-diff.yaml` | Same bug class, independently discovered, fixed inline | See `docs/architecture/argocd-omitempty-gotchas.md` (new, this pass). |
| `projects/` (absent from the K3s-HA proposal — it still used `project: default`) | `projects/veridex.yaml` — dedicated AppProject, RBAC roles, scoped `sourceRepos`/`destinations` | This repo is ahead. The K3s-HA proposal never addressed that every Application there still uses `project: default` (no RBAC scoping, no repo/destination allowlist). Keep this repo's pattern as the standard; it is not something to weaken to match K3s-HA. |
| `policies/` (Rego + capability gates) | *(missing)* | Real gap — see below. |
| `templates/`, `vendor/<x>/VERSION`, `gitops/README.md` | none exist yet | Nothing to reconcile yet. Apply the rule from day one: no `.example` files next to live manifests, pin any vendored CRD dump with a `VERSION` file, and write `gitops/README.md` now while there are 3 Applications to document instead of 70. |

## Finding 1 — the same Argo CD bug, independently, in both repos

`infra-app.yaml` in K3s-HA documents a confirmed-live incident: a child Application declaring `syncPolicy.automated.prune: false` explicitly gets that value silently dropped by the API server (`omitempty` on the zero value), so the parent Application sees a diff it can never resolve and sits permanently `OutOfSync`.

`infrastructure/monitoring.yaml` and `infrastructure/traefik.yaml` in **this repo** independently hit the same bug class through a different field: `directory: {recurse: false}` — also a zero-value under `omitempty`, also silently dropped, also produced a permanently-`OutOfSync` root Application (confirmed live, fixed 2026-09-15 by removing the stanza — the fix that had been blocking the Gate 11 monitoring Application from applying at all).

Two different fields, same root cause, found independently three weeks apart. That is a real Argo CD footgun class, not a one-off: **never declare a field's zero-value explicitly when that field is `omitempty` in the CRD.** Written up as its own reference document rather than left as two separate inline comments — see `docs/architecture/argocd-omitempty-gotchas.md`.

## Finding 2 — this repo is missing a directory the plan itself calls for

The Initial Stages Plan's GitOps-boundary line names four things Argo CD owns: cluster services, data services, **policies**, and applications. This repo's `gitops/` has `applications/`, `bootstrap/`, `infrastructure/`, `platform/`, and `projects/` — no `policies/`. K3s-HA already has a working pattern for exactly this: `gitops/policies/` holding OPA/Rego admission policies plus a data-driven consumer-capability-gates contract file. **Action taken this pass:** created `gitops/policies/` here — see its own README for what carried over and what didn't (the two Rego files in K3s-HA turned out to be non-functional stubs and were not ported as-is; the capability-gates mechanism is real and valuable and was scaffolded, empty, for when the first consumer/provider service pair exists).

## Finding 3 — a K3s-HA inconsistency this comparison surfaced (informational only; K3s-HA is out of scope to fix from this repo)

This repo's `gitops/bootstrap/namespace.yaml` documents explicitly that the `argocd` namespace is created by Ansible before Argo CD exists, labels it `managed-by: ansible`, and `root-application.yaml` excludes `bootstrap/**` so Argo never claims to reconcile the object that creates it. K3s-HA's equivalent `bootstrap/namespace.yaml` has no such label and no such comment, and its `root-app.yaml`'s `directory.exclude` pattern does not exclude that file — meaning K3s-HA's root Application has likely been silently adopting reconciliation of its own control-plane namespace, a layering violation this repo's design avoids by construction. Noted here for the record; fixing it is a K3s-HA change, not a Veridex-Platform one, and is out of scope for this document.

## Actions taken this pass

1. Created `gitops/policies/` (README + scaffolded, empty `consumer-capability-gates.yaml`) — closes Finding 2.
2. Created `docs/architecture/argocd-omitempty-gotchas.md` — closes Finding 1.

## Actions still open (not done in this pass — flagging, not executing)

- Promote `infrastructure/monitoring.yaml` to `infrastructure/monitoring/` before Gate 11 finishes adding Alertmanager/node-exporter/kube-state-metrics.
- Write `gitops/README.md` describing the bootstrap → infrastructure → platform → applications split and the sync-wave convention, while there are still only 3 real Applications to document.
- When the first pair of interdependent services lands in `applications/` or `platform/`, populate `consumer-capability-gates.yaml` with real gates and wire in a checker script (K3s-HA's `scripts/check-consumer-capability-gates.py` is the reference implementation, not the copy source — its paths are K3s-HA-specific).
