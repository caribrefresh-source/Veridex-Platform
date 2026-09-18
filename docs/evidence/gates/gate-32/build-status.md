# Gate 32 namespace operationalization — build status

Status: **CODE COMPLETE / LIVE VERIFICATION PENDING**

Base: `origin/main` at `a8057299e0c3df8a7d4a1c82df022140d600d395`
Branch: `feat/namespace-operationalization`

No live cluster resource was changed while producing this build. The current
`veridex-operator` identity correctly denied server-side dry-run writes to
AppProjects, Applications, Namespaces and namespace-scoped resources.

## Deliverables

- **D105** — machine-readable and human-readable namespace maps plus active and
  planned Namespace manifests.
- **D106** — shared-namespace tenant isolation model.
- **D107** — Wave 5 client / Wave 6 backing-infrastructure decision, explicitly
  pending Gate 14 verification rather than falsely closing Gate 33.
- **D108** — active/planned GitOps separation, namespace deletion protection,
  exact AppProject destinations and disabled default AppProject.
- **D109** — permanent `veridex-policy-test` namespace baseline with restricted
  Pod Security, quota, LimitRange, tokenless ServiceAccount, default deny and
  CoreDNS-only egress.
- **D110** — fail-closed namespace contract validator, CI integration and seven
  adversarial fixture tests.

## Exit checks

- **EG109 PASS** — all ten workload namespaces map exactly once.
- **EG110 PASS** — active and planned manifests are path-separated; the Argo
  namespace Application sources only `active/`.
- **EG111 PASS** — automated namespace pruning is disabled and Namespace
  resources carry `Prune=false,Delete=false`.
- **EG112 PASS** — every repository Application uses `project: veridex` and
  targets a mapped, non-planned namespace.
- **EG113 PASS** — the `veridex` AppProject has no destination wildcard and its
  destinations equal the namespace map.
- **EG114 PASS** — static lint, provider-drift lint, secret-register lint,
  namespace lint, contract lint, YAML lint and seven adversarial tests pass.
- **EG115 PASS** — client-side Kubernetes construction accepts all changed
  AppProject, Application, Namespace, quota, LimitRange, ServiceAccount and
  NetworkPolicy resources.
- **EG116 PENDING** — server-side admission dry-run. The read-only operator was
  denied as designed; an authorized verification identity or Argo reconciliation
  of an approved commit must prove admission without bypassing GitOps.
- **EG117 PENDING** — live Argo Sync/Healthy and resource-level status.
- **EG118 PENDING** — live policy-test positive/negative flows and sanitized
  Hubble evidence. Test pod images must first be digest-pinned and proven under
  restricted Pod Security.

Gate 32 must not be recorded PASS in the append-only ledger until EG116–EG118
pass against the identified target cluster and reviewed commit.

## Closed-loop review

### Iteration 1

Found that adding manifests to the existing namespace directory would create
all namespaces immediately. Added the `active/` / `planned/` boundary and
changed the Argo source to `active/` only.

### Iteration 2

Adversarial review found that `prune: true` could delete a Namespace and all of
its contents. Disabled automated namespace pruning, protected each Namespace,
and replaced deletion rollback with a guarded decommission procedure. It also
found root recursion into future non-live YAML directories; those paths are now
excluded.

### Iteration 3

Static and negative tests found no remaining code-level contract violation.
The live server dry-run was blocked by least-privilege RBAC, leaving admission
and behavior checks honestly pending rather than escalating privileges.

## Rollback

Before merge: delete the branch/worktree. After merge but before workloads:
revert the commit through Git. Do not delete an active Namespace as rollback.
After any workload or data exists, only the guarded decommission runbook may
remove a namespace, with explicit authorization and an empty-resource proof.

