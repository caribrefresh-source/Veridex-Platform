# Workload Migration Assessment — Veridex Platform (netcup)

**Document ID:** VP-WMA-001
**Status:** Assessment / proposal — not a plan amendment
**Date:** 2026-09-15
**Companion to:** `docs/Engineering Documents/Initial Stages Plan.txt` (Revision 3, 36 gates)
**Relationship to the plan:** This document does **not** amend, supersede, or renumber anything in the Initial Stages Plan or the gate ledger. It assesses the *workload migration* question the plan deliberately leaves to Gates 14–15 ("Data services", "Applications"): what actually has to move from the existing source reference cluster/Hetzner platform onto this cluster, what it costs, and in what order. Where this document and the plan disagree, **the plan governs**.

---

## 1. Evidence basis and method

Every claim below carries a `.claude/CLAUDE.md` §1 label. The method was deliberate, and its limits matter:

| Evidence tier | What was done | What that permits |
| --- | --- | --- |
| Repository inspection (this repo) | Direct reads of `ansible/`, `gitops/`, `kubernetes/`, `docs/evidence/`, plus re-running `scripts/lint-provider-drift.py` against current HEAD | `VERIFIED` for committed configuration; never for runtime behavior |
| Repository inspection (source reference cluster source platform) | Direct reads of `gitops/`, `k3s/manifests/`, `services/`, `eng-design/` | `VERIFIED` for committed configuration |
| Live cluster query (source reference cluster only) | `kubectl get applications.argoproj.io -n argocd` executed 2026-09-15 during this assessment | `VERIFIED` as of that timestamp only |
| Gate closure records | Read of `docs/evidence/gates/gate-00` … `gate-10` closure records and supporting files | `DOCUMENTED` — a dated evidence record, not independently re-executed here |

**Explicit limitation.** No live query was made against the **netcup cluster** during this assessment — no kubeconfig context for it was reachable from the authoring environment (`kubectl config get-contexts` returned only an unrelated `default` context). Therefore **nothing in this document claims `Verified live` status on the netcup cluster.** Every netcup runtime claim is either `DOCUMENTED` (from a gate closure record, which *does* contain captured live output from when it was taken) or `VERIFIED` only in the sense of committed repository configuration. Per the plan's own Status vocabulary, "Configured" and "Code only" are the correct tiers for most of what follows.

---

## 2. Current state — Veridex netcup cluster

### 2.1 Gate position

`DOCUMENTED` (`docs/evidence/gate-ledger.md`): **Gates 0–10 are closed.** Last deliverable D53, last exit-gate check EG56, Gate 10 closed 2026-09-15. Next closure starts at D54/EG57.

`VERIFIED` (repository inspection): the closure claims for Gates 0–5 are consistent with committed repository state on every statically checkable artifact. Specifically:

| Claim | Where verified |
| --- | --- |
| Private network `10.2.0.0/16`, /16 prefix | `ansible/inventory/production/group_vars/all.yml:77,87` |
| vLAN MTU 1500 | `ansible/roles/common/defaults/main.yml:12`, rendered at `ansible/roles/common/templates/60-private-vlan.yaml.j2:20` |
| k3s secrets encryption, audit logging, API VIP + DNS SAN | `ansible/roles/k3s-server/templates/config.yaml.j2:40-43,47,67-72`; `group_vars/all.yml:151-155` |
| Three-etcd-voter assertion, no learners | `ansible/roles/k3s-server/tasks/main.yml:243-264` |
| No live Hetzner dependency anywhere in the tracked tree | `scripts/lint-provider-drift.py` re-run at current HEAD; all hits are comparative/rationale comments |
| Cilium 1.20.1, kube-proxy replacement, `k8sServiceHost` = kube-vip VIP | `group_vars/all.yml:233,242-244` |
| Backblaze B2 sidecar uploader (b2 CLI 4.7.1), bucket `veridex-etcd-backup` | `ansible/roles/etcd-s3-backup/defaults/main.yml:17,29,38-39` |

`DOCUMENTED`, not re-verifiable from repository files: every live-node result — the ping/MTU matrix, the `sshd -T` and `chrony` captures, the etcd/cert/audit proofs, and Gate 5's operator-performed hard power-off drill (~7.45 s measured VIP outage). These are inherently live drills; the closure records label them honestly.

### 2.2 What exists beyond Gate 10

`VERIFIED` (repository inspection): **Gate 11 (Baseline observability) is scaffolded but not closed.** There is no `docs/evidence/gates/gate-11/` directory, no closure record, and no ledger row. What does exist:

- `gitops/infrastructure/monitoring.yaml` — an Argo CD Application (destination namespace `monitoring`), explicitly commented `# Gate 11 (baseline observability)`
- `kubernetes/infrastructure/monitoring/` — a complete manifest set: `vmsingle`, `vmagent`, `vmalert`, `alertmanager`, `node-exporter`, `kube-state-metrics`, `loki`, `fluent-bit`, plus `rbac.yaml` and `namespace.yaml`
- `ansible/roles/cilium/defaults/main.yml:18-23` — `cilium_hubble_relay_enabled: true`, commented for Gate 11 flow visibility
- `ansible/roles/etcd-s3-backup/templates/sync-script.sh.j2:21-46` — emits `etcd_snapshot_sync_last_success_timestamp_seconds` as a Prometheus textfile metric, pre-wired for Gate 11's vmalert

In the plan's own vocabulary this is **Configured / Code only**, not Verified live. The gate ledger's **O4 ordering decision** (2026-09-15) already records how Gate 11 may close independently of Gate 32.

`VERIFIED` (repository inspection): **Gates 12 and 13 have no work product at all.** No file matching `longhorn` or `minio` exists anywhere under `kubernetes/` or `gitops/`. Likewise Gate 32's artifacts — `namespace-map.md`, `wave5-wave6-resolution.md`, `tenant-isolation-model.md` — do not exist; they appear only as forward references inside the ledger's O4 entry.

**Therefore: no data platform exists on netcup yet.** No Longhorn, no MinIO, no CloudNativePG, no NATS, no Temporal, no Redis. Everything in §3 below has to be built before a single application workload can run.

### 2.3 Open risks carried forward from closed gates

These are disclosed in the ledger itself, not new findings. They are restated here because they are load-bearing for everything downstream:

1. `VERIFIED` — **`ARGOCD_REPO_PAT` is over-scoped and unremediated live.** `docs/evidence/gates/gate-10/pat-scope-finding.txt:26-27` shows the live `x-oauth-scopes` header carrying `admin:org`, `admin:enterprise`, `delete_repo`, `repo`, `workflow` — near-full account-admin, against Gate 10's own stop condition of "writable repo key". Gate 10 closed PASS by explicit, disclosed operator override. The current secret register correctly records the broad grant; repository automation now rejects classic or repository-writable credentials. Rotation and revocation still require an operator-supplied fine-grained credential and live converge.
2. `VERIFIED` — **B2 credentials are plaintext on disk.** `ansible/roles/etcd-s3-backup/templates/credentials.j2:11-12` renders `B2_APPLICATION_KEY_ID` / `B2_APPLICATION_KEY` as plain shell assignments, deployed 0600 root-only (`tasks/main.yml:63-70`). No SOPS anywhere in that path. This is consistent with the closure's own disclosure (SOPS encryption is Gate 21's requirement, not Gate 9's) — a scheduled gap, not a hidden one.
3. `DOCUMENTED` — **Gate 9 deviates from the plan's literal text.** k3s's native S3 snapshot target was tested live against the pinned version and found incompatible with B2 Object Lock (it never sends the `Content-MD5` / `x-amz-checksum-` header B2 requires); `docs/evidence/gates/gate-09/native-uploader-incompatibility.txt` carries the `journalctl` error. A `b2`-CLI sidecar replaces it, with authorization. **Gate 17's "k3s etcd" row must be assessed against the sidecar, not the plan's prose.**
4. `DOCUMENTED` — Gate 6 closed with **28 of 83 Cilium connectivity tests failing**, self-disclosed in its closure record. Any Gate 30 network-policy work inherits that baseline.

---

## 3. Current state — what has to migrate

### 3.1 Source platform inventory

`VERIFIED` (live query, source reference cluster cluster, 2026-09-15): the source platform runs **78 Argo CD `Application` resources**. That number is not a service count — it decomposes as:

| Source | Count |
| --- | ---: |
| `gitops/bootstrap/` (root + 3 app-of-apps) | 4 |
| `gitops/infra/*` via the `infra` app-of-apps | 20 |
| `gitops/apps/data-plane/*` via `dip-data-plane` | 43 |
| Generated by the `dip-scaling-appset` ApplicationSet | 3 |
| `k3s/manifests/observability/apps/*` via the `observability` app-of-apps | 8 |
| **Total** | **78** |

`VERIFIED`: two further `Application` manifests exist in the source repo but are **orphaned** — nothing references them, so Argo CD never adopts them: `ingress-nginx` and `kube-prometheus-stack` (the latter's own file header reads "LEGACY … Safe to delete"). Neither should be carried across.

Of the 78, the ones that are **Hetzner-specific and must not be migrated** are `hcloud-csi`, `hetzner-ccm`, and — conditionally — `cert-manager-webhook-hetzner` (keep only if Hetzner DNS remains authoritative for the zone; that is a `DECISION REQUIRED`, not a technical blocker). This is consistent with Gate 0's already-closed provider-boundary requirement.

### 3.2 Coded services

`VERIFIED` (repository inspection, source reference cluster `services/`): **24 source directories**, of which 22 map to a deployed workload:

`auth-service`, `client-sync-service`, `cross-encoder-service`, `data-consistency`, `dip-migration-runner`, `embedding-service`, `file-manager`, `governance-service`, `hitl-service`, `ingestion-service`, `nlp-preprocessing-service`, `notification-service`, `ocr-service`, `preview-service`, `processing-authorization-service`, `rag-context-builder`, `rag-orchestrator`, `rag-reranker`, `rag-retriever`, `search-gateway`, `search-service`, `temporal-workers`.

Two require disposition before migration:
- `rule-service` — **not missing.** See §4.1; it ships inside the governance Application.
- `marker-worker` — `UNKNOWN`. Source exists; no `Application` and no Deployment found in any Application's manifest path. Resolve before Gate 15, do not migrate blind.

---

## 4. Proposed new services — the governance control plane

**Scope boundary for this section:** this describes what the GPBRMS specification (`eng-design/sequential build/Enterprise Governance, Policy & Business Rules Architecture Specification.txt`, Revision 1.1, in the source reference cluster repo) commits to building, and what of it already exists. It is included because these services are **additional workloads the netcup cluster must be sized for** — they are not in the 22 above. Deciding *whether* to build GP-5 onward is out of scope here.

### 4.1 Already built (GP-0 … GP-4) — migrates with the platform

`VERIFIED` (repository inspection, source reference cluster): the single `governance-service` Argo CD Application (`gitops/apps/data-plane/31-governance-service.yaml`, source path `k3s/manifests/governance`) deploys **four Deployments**, one per GP phase directory:

| Deployment | Phase dir | GP phase |
| --- | --- | --- |
| `governance-service` | `gp0/` | GP-0 / GP-1 — artifact registry, ownership, lifecycle, audit |
| `metadata-service` | `gp2/` | GP-2 — glossary, taxonomy, schema registry |
| `policy-service` | `gp3/` | GP-3 — policy authoring, versioning, approval, publication |
| `rule-service` | `gp4/` | GP-4 — rule registration, translation, testing, deployment |

Each has its own `deployment.yaml`, `service.yaml`, and `network-policy.yaml`.

**This resolves the `rule-service` question.** It has no Argo CD `Application` of its own *by design* — counting Applications undercounts governance workloads by three.

**Discrepancy flagged** (`VERIFIED` against `DOCUMENTED`): the specification's own §17 audit-reconciliation note (dated 2026-09-03) states "the live surface is **governance-service** … and **rule-service**. There is **no separate policy-service, decision-service, or compliance-service**." That is **inconsistent with the committed manifests**, which contain a `policy-service` Deployment (`gp3/`) and a `metadata-service` Deployment (`gp2/`). The reconciliation note is either stale or means "no separate *Application*/schema" — either way it should not be relied on as-written. Per `.claude/CLAUDE.md` §0 this is a *conflicting-evidence* case: repo state contradicts documented design, and the repo state is the stronger evidence.

### 4.2 Specified but not built (GP-5 … GP-20) — net-new services

`DOCUMENTED` (GPBRMS spec §13). Four net-new deployable services, plus phases that extend existing ones:

| Service | Phase | Purpose | Request floor (spec) |
| --- | --- | --- | --- |
| `decision-service` | GP-5 | Rule evaluation against facts; decision trace, cache, explanation | 300m / 384Mi |
| `compliance-service` | GP-6 | Controls, evidence, regulatory mapping (SOC2/GDPR/HIPAA/ISO 27001) | 200m / 256Mi |
| `governance-portal` | GP-7 | Unified admin UI (frontend bundle) | 100m / 128Mi |
| `governance-worker` | GP-8 | Temporal workflows: policy/exception approval, scheduled control testing | 200m / 256Mi |

GP-9 … GP-19 add capability to the above rather than new deployments (advanced rule engine, decision analytics, exception and evidence management, digital signature, simulation, studios, KPIs, control testing, regulatory mapping). GP-20 is a 30-day stabilization window.

**Known dependency blocker** (`DOCUMENTED`, spec §A-3): GP-6's evidence-collection exit gate (EG-63) is **blocked on DIP Phase 7** (full audit-log shipping, Process 91), which the spec records as not started. `compliance-service` can deploy and define controls; it cannot close that gate.

**Capacity claim, and why it should not be trusted as-is** (`DOCUMENTED`, spec §19.2): GPBRMS totals **2400m CPU / 2816Mi memory at request floor** across 8 services. The spec's own verdict on its capacity fit is explicit: *"this is asserted, not measured, and should not be read as a Phase 0-style gate-pass."* It was sized against a **6× CPX32 (24 vCPU / 48 GB)** cluster. The netcup target is five nodes, only two of which are application workers (§5.1). That number must be re-derived against netcup's actual hardware before GP-3 onward is scheduled, not carried over.

---

## 5. Risks, ranked by evidence strength

### 5.1 Capacity — the plan already contradicts itself here, in writing

This is the highest-confidence risk in this document because **the plan states it against itself.**

`DOCUMENTED` (Initial Stages Plan, "Capacity condition"): *"With only two worker nodes, four independent MinIO node failure domains require two MinIO server pods to run on selected control-plane nodes. If control-plane nodes must remain storage-free, the five-node fleet cannot satisfy four node-level MinIO failure domains… The same two-worker constraint means the two large RS 2000 disks alone cannot provide three Longhorn node-level replicas — Gate 26 must resolve this before longhorn-critical is used."*

So, before any application workload is considered, the target topology already cannot simultaneously satisfy Gate 13 (four MinIO domains) and Gate 26 (three Longhorn replicas) without placing storage on control-plane nodes. Layered on top of that unresolved condition:

- 22 coded services (§3.2)
- 4 governance workloads already built (§4.1)
- up to 4 more governance services if GP-5…GP-8 proceed (§4.2), at a further 800m/1024Mi request floor
- the full data platform — CNPG, MinIO ×4, NATS, Redis, Temporal, Longhorn (Gates 12–14)
- the Gate 11 observability stack — vmsingle, vmagent, vmalert, alertmanager, loki, fluent-bit, node-exporter, kube-state-metrics

The source platform runs a comparable workload on **six** nodes and `[project_cnpg_cpu_throttling]` records CNPG as *already CPU-throttled in production there at 500m*. Compressing onto two worker nodes is not a detail to resolve at Gate 26.

**Recommendation:** continue the gate build while measuring continuously. Gate 11 must collect actual container CPU, memory working set/RSS, throttling, OOM, PVC usage and node storage before Gate 12 adds storage. At every later gate, record physical/allocatable, pledged requests/limits/PVCs, actual p50/p95/p99/max and failure-mode headroom. Final workload promotion—not continued construction—is blocked when measured headroom or recovery evidence fails its threshold.

### 5.2 Credential posture is behind the build front

`VERIFIED LIVE`, 2026-09-15: Argo CD now uses a fine-grained token restricted to `caribrefresh-source/Veridex-Platform`, with Contents: Read-only and Metadata: Read-only. Repository read succeeds, a non-mutating Git-reference write probe is denied, and the root Application remains Synced/Healthy. The superseded broad credential is retained outside the cluster by explicit operator direction and remains an accepted residual risk. The B2 keys are plaintext on disk (§2.3.2); Ansible output/diff suppression is now enforced, but removing persistent runtime plaintext remains a Gate 21 design and rotation task.

### 5.3 Backup proves one producer of six

`DOCUMENTED`: Gate 8/9 proved the **etcd** path to B2 end-to-end, including an isolated restore. Gate 17's matrix requires the same for **CloudNativePG, Velero, MinIO, Longhorn, and the audit exporter** — none of which exist yet. The plan's own "highest-priority unresolved issue" says the remaining risk is B2-specific behavior (multipart limits, throttling during a full restore, egress against the 3× free allowance), not protocol compatibility. Treat one proven producer as one, not as evidence the pattern generalizes.

### 5.4 Recovery is unproven, by the repo's own admission

`DOCUMENTED` (`.claude/CLAUDE.md` §2): `docs/data-plane/backup-dr-runbook.md` is **not yet written** for the netcup cluster. Until it exists and a dated drill is recorded, the ≤1h RPO / ≤30m RTO targets are targets only. The plan is already correct on this (Gate 29, "Recovery objectives and proof") — no RTO/RPO should be quoted externally until Gate 16/29 produce a measured figure.

---

## 6. Owning layer

Per `.claude/CLAUDE.md` §5, nothing in this assessment proposes a layer change:

| Concern | Owner |
| --- | --- |
| Node count / sizing decision (§5.1) | Provider provisioning + Ansible inventory |
| MTU, addressing, kube-vip, k3s, Cilium bootstrap | Ansible (already established, Gates 2–6) |
| Longhorn / MinIO / CNPG / NATS / Temporal lifecycle | Argo CD (Gates 12–14) |
| Governance services | Argo CD, as one Application per the existing source reference cluster pattern (§4.1) |
| B2 buckets, keys, Object Lock | Separate IaC stack, outside cluster GitOps (Gate 31 — mechanism still an open decision) |

---

## 7. Proposed sequencing

This does not renumber or reorder any gate. It states where the workload-migration work attaches to the existing sequence:

| Before | Do this | Because |
| --- | --- | --- |
| Gate 12 | Per-wave capacity budget against real RS 1000/RS 2000 specs; resolve Gate 26's node-feasibility question | §5.1 — the topology contradiction is already documented and blocks both Gate 13 and Gate 26 |
| Gate 12 | No remaining Argo credential action: description, validation and live rotation completed 2026-09-15 | §5.2 — the superseded broad credential is retained outside the cluster as an accepted operator risk |
| Gate 14 | Resolve `marker-worker` disposition | §3.2 — do not migrate an unidentified workload |
| Gate 14 | Re-derive the GPBRMS capacity figure against netcup | §4.2 — the 2400m figure is explicitly "asserted, not measured", and was sized for a different cluster |
| Gate 15 | Decide GP-5…GP-8 scope | §4.2 — four more services is a material capacity decision, not a default |
| Gate 17 | Assess the "k3s etcd" row against the b2-CLI sidecar, not the plan's prose | §2.3.3 — the implemented mechanism differs from the plan text by authorized deviation |

---

## 8. Rollback

This document changes no cluster state and no configuration. Rollback is deletion of this file. The corrections it *recommends* each have their own rollback path, stated in the gate that owns them.

---

## 9. Residual risks and open items

1. **No live netcup verification in this assessment.** Everything about the running cluster is `DOCUMENTED` from gate closure records. A live re-verification pass should precede Gate 12.
2. **Gate 6's 28 failing connectivity tests** are carried forward unresolved into any Gate 30 policy work.
3. **The §6 conflict remains open** — the plan requires resolving "SOPS + age vs. SealedSecrets and Longhorn" before Gates 13 or 24 close; `.claude/CLAUDE.md` §6 lists SOPS + age and lists neither SealedSecrets, Longhorn, nor Velero. This is a stack decision, not only an ordering one, and it is unresolved.
4. **`MINIO_KMS_SECRET_KEY` incident (Gate 22)** is carried as open in the plan and must close before MinIO reaches production.
5. **Gate 31's IaC mechanism is undecided.** The plan notes Backblaze publishes a Terraform provider but that this platform has not adopted Terraform — naming a provider does not settle what holds that state or where it is backed up.
6. **The GPBRMS spec's §17/§18 reconciliation notes are partly inaccurate** (§4.1). They should be corrected in the source reference cluster repo before being used as a migration input.
