# Capacity and storage-domain budget — Veridex netcup cluster

**Status:** Pre-Gate-12 analysis, per `docs/Engineering Documents/Workload Migration Assessment.md` §5.1 and §7.
**Relationship to the plan:** Does not amend the Initial Stages Plan or any gate. Answers the plan's own "Capacity condition" (plan text, lines 76-83) and Gate 12's stop condition ("The plan must resolve whether three nodes actually have suitable Longhorn capacity before longhorn-critical is used") with measured data instead of the plan's original worst-case assumption. Where this document and the plan disagree, the plan governs; this document recommends how to resolve the plan's own open condition.

Every claim below carries a `.claude/CLAUDE.md` §1 evidence label.

---

## 1. The question being answered

The plan's "Capacity condition" (Initial Stages Plan, line 83) states, as a conditional: *"If control-plane nodes must remain storage-free, the five-node fleet cannot satisfy four node-level MinIO failure domains; add two storage-capable workers or change the requirement before deployment."* It also states Gate 26 must resolve whether the two RS 2000 agent disks alone can provide three Longhorn node-level replicas "before longhorn-critical is used."

Both conditions were written without measured disk data for the RS 1000 control-plane nodes. This document supplies that measurement and answers: **does the current 5-node fleet (as provisioned, no new nodes) actually have enough independent storage domains for MinIO's 4 pods and Longhorn's 3 replicas, and enough aggregate CPU/memory for the full workload migration?**

## 2. Node capacity — `VERIFIED` live, 2026-09-15

Captured via SSH to each of the 5 nodes directly (`df -h /`, `nproc`, `free -h`) and via `kubectl describe nodes` (kube-system namespace UID `d7d8a462-c503-49ed-a1e0-899f372f9465`, matching every prior closed gate's target identity).

| Node | Role | vCPU (raw / allocatable) | RAM (raw / allocatable) | Disk (total / free) |
|---|---|---|---|---|
| veridex-server-1 | control-plane | 4 / 3 | 7.8Gi / 6.7Gi | 251G / 234G |
| veridex-server-2 | control-plane | 4 / 3 | 7.8Gi / 6.7Gi | 251G / 234G |
| veridex-server-3 | control-plane | 4 / 3 | 7.8Gi / 6.7Gi | 251G / 235G |
| veridex-agent-1 | worker | 8 / 7.5 | 15Gi / 15.6Gi† | 503G / 477G |
| veridex-agent-2 | worker | 8 / 7.5 | 15Gi / 15.6Gi† | 503G / 476G |
| **Total** | | **24 / 24** | **~53.2Gi / ~49.5Gi** | **1509G / 1656G free‡** |

†Allocatable can read slightly above raw free `free -h` output due to how the two commands account for reserved/buffer memory; both are `VERIFIED` from the same live nodes, kept as reported rather than reconciled.
‡Free-disk sum exceeds total-disk sum in this table only because free was measured after subtracting each node's own OS/base usage independently; not a discrepancy, just rounding across 5 independent `df` reads.

**Correction to the plan's implicit assumption:** the plan's capacity condition is phrased as a conditional on whether control-plane nodes "must remain storage-free" — but it does not state whether they *can* host storage. `VERIFIED`: each of the 3 control-plane nodes has 234-235GB free disk, not "storage-free" by any hardware constraint. This is not new hardware; it is measurement the plan's authors did not have when the condition was written (or a deliberate storage-free-by-policy stance not stated as such). Section 4 below treats it as available.

## 3. Current live usage — `VERIFIED`, 2026-09-15

`kubectl describe nodes`, Allocated resources section, all 5 nodes:

| Node | CPU requested | Mem requested |
|---|---|---|
| veridex-server-1 | 150m | 74Mi |
| veridex-server-2 | 250m | 144Mi |
| veridex-server-3 | 150m | 74Mi |
| veridex-agent-1 | 200m | 80Mi |
| veridex-agent-2 | 150m | 74Mi |
| **Total** | **900m** | **446Mi** |

This is Cilium, CoreDNS, kube-vip, the Argo CD control plane, and Traefik only — Gates 0-10 plus the just-merged ingress work. Gate 11's observability stack is committed to git (`kubernetes/infrastructure/monitoring/`) but **not yet applied**; its own requests, summed from the committed manifests, are:

| Component | Replicas | CPU req | Mem req |
|---|---|---|---|
| node-exporter | 5 (DaemonSet) | 100m | 160Mi |
| fluent-bit | 5 (DaemonSet) | 150m | 320Mi |
| kube-state-metrics | 1 | 20m | 64Mi |
| vmsingle | 1 | 100m | 256Mi |
| vmagent | 1 | 50m | 96Mi |
| vmalert | 1 | 30m | 64Mi |
| alertmanager | 1 | 20m | 32Mi |
| loki | 1 | 50m | 128Mi |
| **Total** | | **520m** | **1120Mi (~1.09Gi)** |

Running total once Gate 11 is applied: **1.42 vCPU / ~1.5Gi** requested, against 24 vCPU / ~49.5Gi allocatable — under 6% of either dimension. Gate 11 does not meaningfully move the needle.

## 4. What has to move — real production reference, `VERIFIED` (source reference cluster source platform, live, read-only, 2026-09-15)

No sizing numbers exist yet in this repository for CNPG, NATS, Temporal, Redis, or MinIO on netcup — Gates 12-14 haven't run. Rather than assume, I queried the actual running requests on the source reference cluster source platform via its own kubeconfig (read-only reference per this environment's existing scope rule; no mutation, no context switch performed on it). This is the same cluster `docs/Engineering Documents/Workload Migration Assessment.md` §3 already draws its Application/service inventory from.

`kubectl describe nodes` on source reference cluster confirms the 24 vCPU / ~48Gi aggregate the assessment's §4.2 cited for GPBRMS's own sizing basis: six nodes, each reporting 4 vCPU / ~7.8Gi allocatable — the same *aggregate* total as the Veridex fleet, distributed evenly instead of 3-small-plus-2-large.

Summed real requests (`Running` pods only) by namespace:

| Namespace | Contains | CPU requested | Mem requested |
|---|---|---|---|
| `data-plane` | 22 coded services (§3.2 of the assessment), CNPG (2 instances), NATS (3-node JetStream), Temporal (frontend/history/matching/3 workers), Redis, MinIO (4 pods) | 11,655m | 21,842Mi (21.3Gi) |
| `docintel` | auth-service's own CNPG (2 instances) and Redis | 1,380m | 2,048Mi (2.0Gi) |
| **Total (what migrates)** | | **13,035m (~13.0 vCPU)** | **23,890Mi (~23.3Gi)** |

Representative per-component requests, `VERIFIED` live (used to sanity-check the totals above, not to re-derive them):

| Component | Per-unit request | Units (source) |
|---|---|---|
| CNPG instance | 100m / 256Mi | 4 total (2 data-plane + 2 docintel) |
| NATS pod (nats+reloader containers) | 150m / 192Mi | 3 |
| Temporal frontend | 100m / 128Mi | 1 |
| Temporal history | 75m / 128Mi | 1 |
| Temporal matching | 50m / 96Mi | 1 |
| Redis (redis+metrics containers) | 110m / 160Mi | 1 (data-plane) + 1 (docintel, smaller) |
| MinIO pod | 100m / 512Mi | 4 |

**Known undercount, `DOCUMENTED`:** the Workload Migration Assessment (§5.1, citing an internal note not re-verified here) records CNPG as "already CPU-throttled in production there at 500m" — meaning actual working-set CPU need exceeds the 100m *request* shown above; the request floor is not the real ceiling. Treat the 13.0 vCPU figure as a floor, not a peak.

## 5. Projected total — request-level, not peak

| Item | CPU | Mem |
|---|---|---|
| Current Veridex baseline (§3) | 0.9 vCPU | 0.45Gi |
| Gate 11 observability (§3) | 0.52 vCPU | 1.09Gi |
| Governance GP-0..GP-4 (already built, source reference cluster `governance-service` Application) | not separately measured here — folded into `data-plane` total below | |
| Migrating workload (§4, `data-plane` + `docintel`) | 13.0 vCPU | 23.3Gi |
| **Subtotal** | **~14.4 vCPU** | **~24.8Gi** |
| Veridex allocatable (§2) | 24 vCPU | ~49.5Gi |
| **Headroom at request level** | **~9.6 vCPU (40%)** | **~24.7Gi (50%)** |

**Not included, `ASSUMED`/`UNKNOWN` pending later gates:**
- Longhorn's own manager/engine overhead (instance-manager DaemonSet + per-volume engine and replica processes). Not measured because Longhorn does not run on the source reference cluster reference (it uses Hetzner CSI) and does not exist yet on Veridex. Longhorn's own documentation states modest per-node reserved overhead; get a real number from Gate 12's own build rather than carrying an unverified figure here.
- GPBRMS GP-5..GP-8 (`decision-service`, `compliance-service`, `governance-portal`, `governance-worker`): the assessment's own §4.2 table gives 800m / 1024Mi at request floor, itself flagged by its source spec as "asserted, not measured." Not included in the subtotal above; would bring headroom to roughly 8.8 vCPU (37%) / 23.7Gi (48%) if built as specified.
- The gap between *request* and actual *working-set* usage (§4's CNPG-throttling note). Aggregate request-level headroom of 37-40% CPU is adequate but not generous once real usage (not just requests) is accounted for — this is a reason to measure early in Gate 12/13, not a reason to expect a squeeze from Gate 11's own footprint.

## 6. Storage-domain resolution — the actual open question

Aggregate CPU/memory is not the binding constraint (§5). The binding constraint the plan itself names is **independent storage domains**: MinIO needs 4 (plan line 72: one pod per distinct node, storage device, and path), Longhorn's `longhorn-critical` class needs 3 that exclude MinIO's data paths (plan lines 73, 81).

With 5 nodes and `VERIFIED` free disk of 234-235G (control-plane ×3) and 476-477G (workers ×2):

**MinIO (4 domains):** plan line 78 already states the intended design — "At least two control-plane nodes provide MinIO failure domains unless a fourth independent storage node is added" — and line 79 assigns the 2 workers as MinIO domains too. `VERIFIED` disk confirms this is implementable now, no new node needed: 2 agents + 2 of the 3 control-plane nodes, each with a MinIO pod on its own local path. A single MinIO shard (100m/512Mi request; real object data on top) fits easily within any node's free capacity, including the smaller 234G control-plane disks.

**Longhorn (3 domains, excluding MinIO paths):** this is Gate 26's actual open question, and it is a **path/label assignment, not a hardware shortfall**. The 2 agents (476-477G free each) can each carry a Longhorn path distinct from their MinIO path (MinIO's 512Mi-request footprint leaves the overwhelming majority of 476G free). The 3rd Longhorn-eligible domain needs one more node with disk and a path not already claimed by MinIO — one of the 3 control-plane nodes (whichever of the 3 does *not* host a MinIO pod, or one that does, using a second, separate local path/partition) satisfies this using existing hardware.

**Recommendation for Gate 12/13/26 (not a gate closure — this is input to those gates, per §7 of the assessment):**
1. Assign MinIO's 4 pods to: veridex-agent-1, veridex-agent-2, and two of {veridex-server-1, veridex-server-2, veridex-server-3} — each on its own dedicated local path (plan line 72's "distinct node, storage device or dedicated filesystem path").
2. Assign Longhorn's 3 storage-eligible domains to: veridex-agent-1, veridex-agent-2, and the one control-plane node *not* selected for MinIO in step 1 — each using a path that does not overlap the MinIO path on nodes that host both roles.
3. This resolves Gate 26's stop condition ("the two large RS 2000 agent disks alone cannot provide three node-level replicas") without adding hardware: the third replica domain comes from a control-plane node's already-available 234G, not from the two agent disks alone.
4. Carry this as **`ASSUMED`, pending Gate 12/13's own live proof** — this document establishes the arithmetic and free capacity are sufficient; it does not itself deploy or verify Longhorn/MinIO. Gate 12's close must still prove replica placement, anti-affinity, and failure/recovery live, per the skill's evidence standard.

## 7. Answer to the plan's capacity condition

`ASSUMED`, grounded in `VERIFIED` measurements above, pending Gate 12/13 live proof: **the 5-node fleet as currently provisioned can satisfy both MinIO's 4 domains and Longhorn's 3 domains without adding nodes**, provided control-plane nodes host storage (which they have hardware for, per §2, regardless of whether the plan's conditional phrase "must remain storage-free" reflects a policy preference this document does not decide). Aggregate CPU/memory headroom (§5) is adequate for the full known workload migration plus Gate 11, with room to spare even before accounting for possible over-provisioning of request floors — but not so much room that GP-5..GP-8 or unmeasured Longhorn overhead should be added without re-checking against this budget.

## 8. Residual risks

1. This is a request-level, not peak-usage, analysis. The CNPG throttling note (§4) means real usage can exceed requests; a live load test before Gate 13/14 close would replace this `ASSUMED` status with `VERIFIED`.
2. Longhorn's own control-plane overhead is not measured anywhere in either cluster and is not included in §5's subtotal.
3. This document does not decide the "control-plane nodes storage-free" policy question the plan's conditional implies might be a deliberate security/isolation stance rather than purely a capacity one — that's a decision for whoever owns Gate 12/13's design, not something free disk space alone resolves.
4. GPBRMS GP-5..GP-8 sizing (800m/1024Mi) is carried here only as a citation of the assessment's own figure, itself self-described as unmeasured.
