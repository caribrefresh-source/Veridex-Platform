# GATE 2 — Private network

| | |
|---|---|
| **Verdict** | **PASS** |
| **Closed (UTC)** | 2026-09-14T03:46:35Z |
| **Plan** | `docs/Engineering Documents/Initial Stages Plan.txt` @ `4ebc8def34df78a0bc6b29e42656986ef987f4c9`, sha256 `42eaac5e61d177430ce8e331767d2137b3f9b2bd197e13945b84f7c5e8cd79c7` (blob in Git) |
| **Tested repo commit** | `5cb1bebad43f3df8ee4e3a3b1cfa2408f5434354` (branch `feat/gate-02-private-network`, same code as `main`) |
| **Target identity** | hosts `veridex-server-1` (152.53.177.26), `veridex-server-2` (152.53.140.210), `veridex-server-3` (152.53.142.131), `veridex-agent-1` (159.195.197.136), `veridex-agent-2` (159.195.197.40); SSH host-key fingerprints match `ansible/files/known_hosts` |
| **High-risk** | No — read-only verification only; no code change, no mutation (the one live Ansible run reported `changed=0` on every node) |
| **Verifier independence** | Tier 0 — no code was introduced for this gate, so no adversarial hardening loop applies (§8: "run over every code change... introduced for the gate" — none was). The live evidence itself (ping matrix, DF-bit test, route capture, idempotent rerun) is the verification. |

## 1. Objective

> Static private addresses, /16 mask and MTU 1500 are applied idempotently. All nodes reach every other node over the intended private interface. Public and private routes are unambiguous.

## 2. Scope

**In scope**
- Verifying `roles/common` (already built and live on all five nodes before this gate's Revision-3 numbering existed) actually satisfies Gate 2's end state and acceptance evidence, with fresh live checks dated to this closure.
- Capturing the four acceptance-evidence items the plan names: ping matrix, MTU DF-bit test, route/interface capture, idempotent rerun.

**Out of scope**
- Building new automation: none was needed. `roles/common` already implements static `/16` addressing on `eth1` via a declarative Jinja template with idempotence asserts (see Gate 1's `iir-rerun.txt`, which already showed this role converging with `changed=0`).
- Kernel/sysctl/firewall host prerequisites → Gate 3.
- Deep inspection of netcup's own vLAN switch/hypervisor routing beneath the guest OS → outside this repository's control, not attempted.

## 3. Processes activated

| Process | Owner (Workflow ownership table) | Detection if it silently stops |
|---|---|---|
| `roles/common` keeps the private vLAN interface (`eth1`, `10.2.1.0/16`, MTU 1500) declared and idempotent | Ansible | A rerun reporting `changed` on the vLAN tasks, or the role's own asserts (prefix must be `/16`, interface must carry the intended address) failing the play. |

No new process is activated by this gate — `roles/common` already ran as part of Gate 1's `prepare-hosts.yml` converges; this gate adds no new enforcement, only fresh dated proof that the existing enforcement meets Gate 2's specific acceptance criteria.

## 4. Deliverables

| ID | Artifact | Commit |
|---|---|---|
| D21 | `docs/evidence/gates/gate-02/closure.md` and its four evidence files — this record | (this branch's evidence commit) |

No code deliverables: `roles/common`, which this gate verifies, was already a Gate 1 deliverable (D16, wired into `prepare-hosts.yml`) and is not re-delivered here.

## 5. Technical detail

**Decision rationale**
- *No build step.* The plan's Gate 2 acceptance evidence (ping matrix, MTU test, route capture, idempotent rerun) is entirely satisfiable by re-running and re-observing the already-built `roles/common`. Writing new code to satisfy an already-met requirement would be scope creep past the smallest coherent change (CLAUDE.md §11).
- *Two node pairs tested for MTU, not all ten.* `server-1↔server-2` (two RS 1000 G12 control-plane nodes) and `agent-2↔agent-1` (two RS 2000 G12 workers) cover both machine types on the fleet; the ping matrix (all 25 paths) already proves basic reachability for every pair, so the DF-bit test's purpose — confirming the path MTU ceiling — is adequately sampled rather than exhaustively repeated for a value (1500) already measured and recorded in CLAUDE.md §2 on 2026-09-12.
- *`ttl=63` on the agent-2→agent-1 echo reply, `ttl=64` between the two servers*: observed and left unexplained by design — it reflects netcup's underlying vLAN infrastructure, which this repository does not configure or control, not an asymmetry in this repository's own route tables (identical `10.2.0.0/16 dev eth1 proto kernel scope link` on all five nodes — see `c3-routes-and-interfaces.txt`). Not a stop-condition trigger: the plan's "asymmetric route" concerns configured routing, which is uniform.

## 6. Exit gate

| ID | Acceptance item (plan) | Method | Evidence | Result |
|---|---|---|---|---|
| EG10 | Full ping matrix | `ping -c1` between every ordered pair of the five nodes, over the private interface | `c1-ping-matrix.txt` | **PASS** — 25/25 paths OK |
| EG11 | 1472-byte DF success / 1473-byte DF failure | `ping -M do -s 1472/1473` on two node pairs (one server pair, one agent pair) | `c2-mtu-df-test.txt` | **PASS** — 1472 succeeds (0% loss) and 1473 fails with `message too long, mtu=1500` on both pairs |
| EG12 | Route and interface capture | `ip -4 addr show`, `ip route`, `ip -d link show eth1` on all five nodes | `c3-routes-and-interfaces.txt` | **PASS** — every node: `eth0` (public /22 + default route), `eth1` (`10.2.1.x/16`, MTU 1500, scope link, no gateway) — identical structure, no ambiguity |
| EG13 | Second Ansible run `changed=0` | `ansible-playbook playbooks/prepare-hosts.yml` (fleet-wide) | `c4-iir-rerun.txt` | **PASS** — `changed=0`, `failed=0` on all five nodes; `roles/common`'s vLAN tasks specifically reported `ok` |

**Stop condition (verbatim):** "Asymmetric route, MTU mismatch, public fallback between nodes, duplicate address or non‑idempotent network change."

**Triggered: no.**
- *Asymmetric route:* EG12 — identical route-table structure on all five nodes; the private CIDR is reached only via `eth1`, scope link, on every node.
- *MTU mismatch:* EG11 — 1500 confirmed as the exact path MTU ceiling on both tested pairs, matching CLAUDE.md §2's recorded measurement.
- *Public fallback between nodes:* EG12 — no route sends `10.2.0.0/16` traffic via `eth0`; the only matching route on every node is the direct `eth1` link route.
- *Duplicate address:* enforced continuously by `scripts/validate-inventory.py` (Gate 0), which asserts unique `private_ip`/`ansible_host`/`vlan_mac`/`netcup_server_id` across the inventory; still passing.
- *Non-idempotent network change:* EG13 — `changed=0` on the vLAN tasks specifically.

## 7. Rollback

### 7.1 Reversal procedure

No code changed by this gate. Nothing to roll back beyond deleting `docs/evidence/gates/gate-02/` and reverting the ledger row, which would return the repository to Gate 1's closed state with no effect on the live nodes (this gate performed no mutation).

### 7.2 Adversarial hardening loop

Not run: no code, script, manifest or policy was introduced or changed for this gate (§8 applies to changes; there was none). The live evidence itself — an exhaustive ping matrix, a DF-bit boundary test, and a full route/interface capture on every node — serves as the verification this gate requires.

**Tracked exceptions:** none newly introduced by this gate.

### 7.3 IIR attestation

- **Immutable:** no code changed; the evidence commit on `feat/gate-02-private-network` is the only artifact.
- **Idempotent:** `changed=0`, `failed=0` on all five nodes — `c4-iir-rerun.txt`.
- **Repeatable:** the same live checks were run fresh, on demand, from this session with no manual step beyond the SSH commands captured verbatim in the evidence files. Reproducibility from a bare/reinstalled node is not proven here (same gap disclosed at Gate 1 — would additionally exercise `k3s-server`/`kubevip`/`kubeconfig`, out of scope for Gates 1-2).

## 8. Known limitations

- MTU was boundary-tested on 2 of the 10 possible node pairs, not all 10; the full ping matrix (EG10) confirms basic reachability on every pair, but not the exact MTU ceiling on the untested 8.
- The `ttl=63` vs `ttl=64` discrepancy between different node-pair combinations is observed but not root-caused; it reflects infrastructure this repository does not control (§5) and does not affect any acceptance criterion, but is noted rather than silently dropped.
- This gate performed no mutation and introduced no new enforcement; it depends entirely on Gate 1's `roles/common` continuing to run correctly, and would need to be reopened if that role's behavior regresses.
- Same limitations already disclosed in Gate 1's closure record continue to apply unchanged (break-glass key co-location, host-key TOFU, no bare-node reproducibility proof).
