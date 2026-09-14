# GATE 5 — kube‑vip failure behavior

| | |
|---|---|
| **Verdict** | **PASS** |
| **Closed (UTC)** | 2026-09-14T10:24:14Z |
| **Plan** | `docs/Engineering Documents/Initial Stages Plan.txt` @ `4ebc8def34df78a0bc6b29e42656986ef987f4c9`, sha256 `42eaac5e61d177430ce8e331767d2137b3f9b2bd197e13945b84f7c5e8cd79c7` (blob in Git) |
| **Tested repo commit** | `9f50972a8ce6cda6fc53bb2439ce8669d1a98282` (branch `feat/gate-05-kubevip-failure`; no code changed for this gate — see §5) |
| **Target identity** | `kube-system` namespace UID `d7d8a462-c503-49ed-a1e0-899f372f9465`; API server `https://10.2.0.100:6443` (private VIP); hosts `veridex-server-1/2/3` (control-plane,etcd) |
| **High-risk** | Yes — stateful failover of a live etcd voter (CLAUDE.md §12 trigger); an actual hard power-off, not a simulation |
| **Verifier independence** | Tier 4 — the destructive action itself (hard power-off, and later power-on) was performed directly by the repository owner via netcup's control panel, not by the agent, per the plan's Workflow ownership table ("hard-power failover drills" → human approved destructive runbook) and this repo's own `netcup-discover.py`, which deliberately cannot power-cycle anything. The agent prepared the drill, ran the sustained probe, and verified cluster state before, during and after. |

## 1. Objective

> The API remains reachable through the private VIP when the current VIP holder is hard powered off, and returns to full redundancy after recovery.

## 2. Scope

**In scope**
- A real hard power-off of the node currently holding the kube-vip lease (`veridex-server-3`), performed by the operator, observed and measured by this session.
- Sustained API-reachability probing through the VIP, bracketing the outage.
- Verification before, during, and after: VIP holder identity, node status, etcd member health.

**Out of scope**
- Any code change: this gate found and needed none — kube-vip and etcd already behaved correctly (built and configured at earlier gates). See §5 for why no deliverable beyond evidence exists.
- Cilium/CoreDNS behavior during the same outage → Gate 6.
- A hard power-off of more than one node at once, or of a non-VIP-holding node → not this gate's acceptance content, not attempted.
- Any change to kube-vip's failback behavior (it stayed on the new holder rather than returning to the original node) → not required by the plan ("returns to full redundancy", not "returns to the original holder"); no action needed.

## 3. Processes activated

| Process | Owner (Workflow ownership table) | Detection if it silently stops |
|---|---|---|
| kube-vip leader election and VIP failover (already built, Gate 4/legacy bring-up; this gate is its first live-drill proof under Revision 3) | Ansible (`roles/kubevip`, deployed) | A future drill, or an actual unplanned outage, showing sustained API loss beyond a short handover would indicate regression — recommend `reopen 5` if observed. |

No new process is activated by this gate — it proves an existing one works, with dated, live evidence, per Revision 3's requirement that Gate 5 not simply inherit the pre-Revision-3 kube-vip ARP evidence in `docs/evidence/legacy/gate-4-kubevip-arp-proof.md` (`DOCUMENTED`, not `VERIFIED`, and not a hard power-off).

## 4. Deliverables

| ID | Artifact | Commit |
|---|---|---|
| D29 | `docs/evidence/gates/gate-05/closure.md` and its seven evidence files — this record | (evidence commit follows) |

No code deliverables: kube-vip's failover behavior was verified, not built or changed, by this gate.

## 5. Technical detail

**Decision rationale**
- *No code change for this gate.* Every acceptance-evidence item (identify holder, sustained probe, hard power-off, record interruption, verify new holder, restore old node, verify etcd/node health) is a live observation of already-built behavior (`roles/kubevip`, `roles/k3s-server`'s etcd, both from earlier gates). Writing code to satisfy an already-working requirement would be scope creep past the smallest coherent change (CLAUDE.md §11) — matching the precedent set at Gate 2.
- *The agent did not perform the power-off itself.* Two independent reasons, both cited to the operator before the drill: `scripts/netcup-discover.py`'s own docstring states it "cannot create, reinstall, power-cycle, or delete anything"; and the plan's Workflow ownership table (line 563) assigns "hard-power failover drills" to a "Human approved destructive runbook", distinct from "Routine convergence". This session disclosed current state, blast radius and rollback, then the operator performed both the power-off and the later power-on directly.
- *Probe measures TCP reachability, not a full authenticated API call.* Sufficient for measuring the interruption window (the plan's acceptance item is "sustained API probe" and "record interruption", not a specific protocol depth), and avoids handling kubeconfig credentials in a throwaway shell loop on a worker node.
- *Interruption measured at ~7.45 seconds, no approved-loss threshold exists elsewhere in this plan to compare it against.* Reported as a measurement. The stop condition's "loss exceeds approved threshold" is not triggered because no threshold is defined anywhere in the plan for this gate to exceed — flagged rather than silently assumed passing by default.

**Resource tables** — none; no manifests, Terraform or IAM policy changed.

## 6. Exit gate

| ID | Acceptance item (plan) | Method | Evidence | Result |
|---|---|---|---|---|
| EG25 | Identify holder | kube-vip lease + ARP for the VIP, before the drill | `c1-identify-holder.txt` | **PASS** — `veridex-server-3`, lease and ARP agree |
| EG26 | Sustained API probe | TCP-connect probe of the VIP every ~0.3-0.7s from a worker node, 10-minute window bracketing the drill | `c2-sustained-probe.txt` | **PASS** — 1639 samples captured, continuous through baseline, outage and recovery |
| EG27 | Hard power-off | Operator-performed, via netcup's control panel; corroborated by ping/etcd-endpoint failure moments later | `c3-hard-power-off.txt` | **PASS** — `operator-captured`, corroborated live by this session |
| EG28 | Record interruption | Transition analysis of the probe log | `c4-interruption-window.txt` | **PASS** — 7.451 seconds, single contiguous outage, no flapping |
| EG29 | Verify new holder | kube-vip lease + ARP for the VIP, during the outage | `c5-verify-new-holder.txt` | **PASS** — `veridex-server-2`, lease and ARP agree; no second holder ever observed |
| EG30 | Restore old node | Operator-performed power-on; polled until `Ready` | `c6-restore-old-node.txt` | **PASS** — recovered by the first poll after operator confirmation |
| EG31 | Verify etcd and node health | `kubectl get nodes`, `etcdctl endpoint health`/`member list`, post-recovery | `c7-verify-etcd-and-node-health.txt` | **PASS** — all 5 nodes `Ready`; same 3 etcd member IDs, all healthy, none a learner |

**Stop condition (verbatim):** "Loss exceeds approved threshold, split‑brain VIP, manual repair, or etcd membership degradation."

**Triggered: no.**
- *Loss exceeds approved threshold:* no threshold is defined anywhere in this plan for Gate 5 to compare against (flagged, §5); the measured 7.45s is consistent with kube-vip's documented leader-election/ARP-update timing and is not, on its face, an outage a human would call excessive for a hard node failure.
- *Split-brain VIP:* EG29 — exactly one holder observed at every point; lease and live ARP agreed throughout.
- *Manual repair:* none was needed or performed — kubelet, k3s and kube-vip all rejoined on their own once the node powered back on.
- *etcd membership degradation:* EG31 — same 3 member IDs before and after, none a learner, no member removed or re-added.

## 7. Rollback

### 7.1 Reversal procedure

Nothing to roll back: no code changed, and the cluster's live state fully returned to its pre-drill baseline (same node set, same etcd membership, all `Ready`/healthy). The only irreversible fact is that the drill happened — recorded here, not undone.

### 7.2 Adversarial hardening loop

Not run: no code, script, manifest or policy was introduced or changed for this gate (§8 applies to changes; there was none), matching the precedent at Gate 2. The live drill itself — an actual hard power-off with continuous measurement, not a simulation — is the verification this gate requires, at Tier 4 independence (the destructive action was performed by the operator, not the agent).

**Tracked exceptions:** none newly introduced.

### 7.3 IIR attestation

- **Immutable:** no code changed; the evidence commit is the only artifact.
- **Idempotent:** not applicable in the Ansible-rerun sense — this gate is a live behavioral drill, not a converge. The cluster's own state (node list, etcd membership) was confirmed identical before and after.
- **Repeatable:** the same drill could be repeated (e.g. against a different node, or with a longer probe interval) using the same procedure; not repeated in this session, since one full pass already produced clean, unambiguous PASS evidence.

## 8. Known limitations

- No approved-loss threshold is defined anywhere in this plan for Gate 5's stop condition to compare the measured 7.45-second interruption against (§5, §6) — a future revision of the plan should state one explicitly.
- The probe measures TCP reachability only, not full authenticated API request/response latency; a real client using a kubeconfig could see a marginally different effective interruption window (e.g. due to client-side connection retry/backoff behavior), though the underlying VIP-level gap this measures is the dominant factor.
- Only one node (the then-current VIP holder) was hard-powered-off; this gate does not prove behavior for two simultaneous node failures (which would break etcd quorum by design — not a target state) or for a non-VIP-holding node's failure.
- Same limitations already disclosed in Gates 1-4's closure records continue to apply unchanged (break-glass key co-location, host-key TOFU, no bare-node reproducibility proof, boot-persistence unproven by an actual reboot, Tier 1 review ceiling on Gates 1-4's code changes).
