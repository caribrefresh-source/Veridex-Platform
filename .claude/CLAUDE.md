# Repository Operating Contract

**Version:** 1.1 (revised 2026-08-24) — supersedes prior undated version.
**Scope:** Governs AI-assisted analysis, changes, and validation in this repository.

## 0. Precedence (single source of truth)

Highest to lowest authority. Do not restate this ordering elsewhere in this file — reference this section instead.

1. Safety / security / legal
2. Explicit user requirements
3. Descendant `CLAUDE.md` files — **except** they MUST NOT weaken repo-wide security, GitOps, or recovery rules defined here
4. This file (repo-wide contract)
5. Repo policies / ADRs
6. Official vendor/upstream documentation
7. General engineering practice

**On conflict:** STOP and report — do not silently pick a side. This applies both to conflicting *instructions* (e.g., a descendant file contradicts this one) and conflicting *evidence* (e.g., repo state contradicts documented design). Say which kind of conflict it is when you report it.

## 1. Evidence Standard

Every factual claim in analysis or output must carry one label:

- `VERIFIED` — observed directly in this repo or live system via code (source files, rendered manifests, `kubectl`/API output, test runs). State as fact, and say where you looked. Reading a doc or ADR does not qualify — see `DOCUMENTED` below.
- `DOCUMENTED` — found in official docs/ADRs, not independently confirmed against this repo. Cite the source. This is a lower tier than `VERIFIED` precisely because it has not been checked against code: treat it as a claim to verify, not a substitute for verification.
- `ASSUMED` — plausible, not confirmed. Label explicitly and verify via code before acting on it — checking documentation is not sufficient to clear an `ASSUMED` label to `VERIFIED`.
- `UNKNOWN` — absent or contradictory evidence. Do not rely on it. Stop only if it blocks a safety- or correctness-critical decision.

The only way a claim earns `VERIFIED` status is direct inspection of code, rendered config, or a live system. Documentation can inform where to look, but citing documentation alone never upgrades a claim past `DOCUMENTED`.

Never present `ASSUMED` or `UNKNOWN` information as fact. This applies to every value in this document too, including Section 2 below — treat those as claims to verify against current repo/cluster state, not as pre-verified facts, unless you have independently confirmed them.

## 2. Critical Platform Constraints

State as of last verification (verify before relying on any of these — see Section 1):

- **netcup Cloud vLAN**: no DHCP. Every address is assigned by us from `10.2.0.0/16`, and interfaces use a /16 mask (not /24, or the kube-vip VIP falls outside the node subnet). Addresses are defined ONLY in the address register (`ansible/inventory/production/group_vars/all.yml`) and `ansible/inventory/production/hosts.yml`. Never hardcode an IP anywhere else — reference the inventory variables.
- **Host / vLAN MTU**: 1500, measured 2026-09-12 (`ping -M do`: 1472-byte payload passes, 1473 fails; no jumbo frames). Set by `roles/common` (`vlan_mtu`). Re-measure before changing.
- **Cilium**: VXLAN tunnel; WireGuard provides encryption only, not tunneling.
- **Cilium MTU**: `cilium_mtu: 0` (auto-detect), chosen deliberately after testing — setting 1350 only lowered usable payload. Accepted gap: pods advertise 1500 but only ~1354 bytes cross nodes over VXLAN + WireGuard. TCP is unaffected (MSS clamping); large single-datagram UDP can be dropped silently. The Helm key is `MTU` (uppercase): `--set mtu=` is accepted and silently discarded. Measurements and reasoning: `ansible/inventory/production/group_vars/all.yml`.
- **Cilium API**: `k8sServiceHost` and `k8sServicePort: 6443` are required settings.
- **Cilium stability**: no routine DaemonSet restarts (see Section 9 — this is the one authoritative statement of that rule; do not duplicate it).
- **Recovery**: order is Control plane → GitOps → Stateful (native mechanism) → Remaining. Full procedure: `docs/data-plane/backup-dr-runbook.md` — NOT YET WRITTEN for the netcup cluster. Until it exists and a dated drill is recorded, recovery is unproven.
- **RPO/RTO targets**: ≤ 1h / ≤ 30m. These are targets to measure against, not confirmed current performance — do not report them as met without a recent, dated recovery-test result.

If repo evidence conflicts with any item above, STOP and report per Section 0.

## 3. Tool Triggers

- `/graphify` → load `.claude/skills/graphify/SKILL.md` first and follow it exactly.

This list is illustrative, not exhaustive — other slash commands or skills may exist under `.claude/skills/`. Check there before assuming a request has no matching tool.

## 4. Core Engineering Principles

- **IIR (Immutable, Idempotent, Reproducible)**: permanent changes must be declarative, version-controlled, reproducible, and reversible. *(If this repo uses "IIR" to mean something else, correct this definition — it was previously used undefined.)*
- **GitOps**: Git is the source of truth. The live cluster is evidence to check Git against, not an alternate source of truth. Changes to reconciled resources go through ArgoCD, not direct cluster mutation.
- **Emergency mutations**: allowed only for an authorized emergency. "Authorized" means: approved by [named role/on-call process — fill in for this repo], recorded with reason, scope, blast-radius, and an explicit expiry, and reconciled back to zero drift by that expiry. An emergency mutation with no named authorizer and no expiry is not authorized — treat it as unauthorized drift.
- **Migrations**: immutable once released. Never rewrite released migration history — write a new migration to correct a released one.

## 5. Layered Ownership

Change the most upstream (most declarative, least specific) layer that legitimately owns the concern — don't patch a downstream layer to work around an upstream gap.

- **Terraform**: cloud infra, networks, machines.
- **Ansible**: host/OS config, K3s bootstrap, node lifecycle.
- **ArgoCD**: application lifecycle, GitOps reconciliation.
- **K8s manifests/Helm**: desired workload state.
- **App code**: domain behavior, APIs, schemas.

Example: a networking MTU problem belongs in Ansible/Terraform, not a workaround in a Helm value or app-level retry loop.

## 6. Approved Stack

Platform focus: document intelligence, workflow automation, AI services.

- **Compute**: K3s HA, ArgoCD
- **Network**: Cilium
- **Relational**: CloudNativePG / PostgreSQL
- **Object**: MinIO
- **Cache**: Redis
- **Events**: NATS JetStream
- **Workflows**: Temporal
- **Secrets**: SOPS + age

## 7. Data Plane Constraints

- **CloudNativePG**: transactional relational data only. Never objects or workflow state.
- **Temporal**: durable workflow state only. Never a general-purpose app database.
- **NATS JetStream**: event transport, streams, replay. Consumers MUST be idempotent — never assume exactly-once delivery.
- **MinIO**: objects and backups only. Never a relational store.
- **Redis**: caches and transient state only. Never the sole durable record of anything.

## 8. Security & Multi-Tenancy

- Least privilege by default.
- Never grant `cluster-admin` outside a recorded, expiring emergency mutation (Section 4) — there is no standing legitimate use.
- Enforce tenant isolation (RLS) with tests that run against production-equivalent schema and policies, not a relaxed test-only configuration.
- Security tests MUST include adversarial cases (attempt the bypass, confirm it's blocked). Never weaken auth, TLS, or RLS to make a test pass — fix the code or fix the test's expectations, not the guardrail.

## 9. Reliability & Disaster Recovery

- Every stateful component needs: backups, a written restore procedure, and a recovery test that has actually been exercised (not just designed).
- **Full-cluster recovery**: follow `docs/data-plane/backup-dr-runbook.md` (not yet written — see Section 2):
  1. Validate control plane.
  2. Restore GitOps/operators/CRDs.
  3. Each data set gets exactly one authoritative restore mechanism.
  4. CNPG PITR must bootstrap from a base backup plus WAL.
- **Never restore overlapping CNPG PVC data via both Velero and CNPG PITR** — pick one mechanism per data set (see point 3) and do not run both against the same PVC.
- **No routine Cilium DaemonSet restarts.** Any restart requires a root-cause analysis and explicit authorization first (this is the same rule as Section 2 — stated once, here, as the canonical version).

## 10. Observability & Status Claims

Status claims require evidence at each stage before advancing to the next:

`merged` → `reconciled` (ArgoCD shows Synced/Healthy) → `workload healthy` (pods ready, probes passing) → `behavior verified` (the actual feature/fix works, not just "pod is up") → `recovery verified` (a real or drilled recovery test passed, dated).

Don't claim a later stage without evidence for every stage before it.

## 11. Change Workflow

- **Before**: read the relevant code/ADRs. Identify the owning layer (Section 5) and dependencies. State what's known vs. unknown (Section 1 labels).
- **During**: make the smallest coherent change that satisfies the explicit user requirement — nothing more.
  - Implement exactly what was asked. Do not add unrequested features, refactors, abstractions, config knobs, or "while I'm in here" cleanups, even if they seem like good practice.
  - If you spot an adjacent problem or improvement that's out of scope, surface it under Residual Risks (see Completion, below) or ask — don't act on it unprompted.
  - If the requirement's scope is ambiguous, ask the one blocking question (Section 14) rather than guessing broad and building extra to cover every interpretation.
  - Update code, tests, and docs together. Pin versions explicitly.
- **Validation**: static → unit → integration → adversarial → recovery, in that order. Test the actual invariant the change is supposed to preserve, not a proxy for it.
- **Completion**: do not claim "complete" unless tests pass, a rollback path is viable and stated, and residual risks are disclosed. "Complete" is a claim under Section 1 — it needs evidence like any other.

## 12. High-Risk Operations

**Triggers**: Cilium/networking changes, etcd, CNPG/Temporal/MinIO/Redis persistence, PV migrations, CRDs/operators, cluster-scoped deletions, stateful failovers, auth/secrets.

**Required before proceeding**: current state, blast radius, failure modes, rollback plan, validation plan, and explicit authorization from the user.

Note: Section 14's "max one blocking question" is about keeping a single request focused — it does not mean skipping any of the five required items above. If multiple facts are genuinely unknown, gather what you can yourself first (read the repo, check the cluster) and reduce the ask to the smallest decision that actually needs a human.

## 13. Kubernetes Governance

- Every namespace needs: a named owner, a stated purpose, and exactly one ArgoCD path managing it.
- Prefer namespace-scoped resources. Cluster-scoped resources need explicit written justification in the PR/commit.

## 14. Response Contract

For any proposed change, structure the response as:

1. Current State
2. Proposed Change
3. Benefits
4. Risks
5. Owning Layer (Section 5)
6. Rollback
7. Implementation
8. Validation (Section 11)
9. Residual Risks

Rules: lead with the outcome. State uncertainty using the Section 1 labels. Ask at most one blocking question per turn (see Section 12 note above for how this interacts with high-risk operations). Use code blocks only for code/manifests, not prose. Never fabricate values — if a value is unknown, say so per Section 1 rather than filling it in. State the scope boundary explicitly in the Proposed Change section — what's included, and what's deliberately excluded.

## 15. Prohibited

Never:

- Treat live drift as intended design.
- Guess at APIs, Helm values, schemas, or versions — verify or label as `ASSUMED`/`UNKNOWN`.
- Call a mocked or unit-level test "production validation."
- Rewrite released migration history.
- Bypass a security control to make progress.
- Use Redis or MinIO as a system of record.
- Restart Cilium DaemonSets routinely, or without RCA and authorization (Section 9).
- Restore overlapping CNPG PVC data via both Velero and CNPG PITR (Section 9).
- Recommend `kubectl edit`/`patch`/`apply` or `helm install`/`upgrade` run by hand as a *permanent* solution — these are fine as emergency mutations (Section 4) but the permanent fix goes through Git.
- Expand a change beyond the explicit user requirement (drive-by refactors, speculative abstractions, unrequested features, extra "nice to have" code) without asking first.

## 16. Glossary

- **IIR** — Immutable, Idempotent, Reproducible (see Section 4). *(Confirm this matches local usage.)*
- **RPO/RTO** — Recovery Point Objective / Recovery Time Objective: how much data loss and how much downtime is tolerable in a recovery.
- **RLS** — Row-Level Security (PostgreSQL access control at the row level).
- **PITR** — Point-In-Time Recovery.
- **CRD** — Custom Resource Definition (Kubernetes API extension).
- **ADR** — Architecture Decision Record.

## Governing Principle

Inspect first. Change the owning source (Section 5). Validate the real invariant (Section 11). Preserve recoverability (Section 9). Report only what the evidence proves (Section 1).