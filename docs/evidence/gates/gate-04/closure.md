# GATE 4 — k3s control plane

| | |
|---|---|
| **Verdict** | **PASS** |
| **Closed (UTC)** | 2026-09-14T06:21:38Z |
| **Plan** | `docs/Engineering Documents/Initial Stages Plan.txt` @ `4ebc8def34df78a0bc6b29e42656986ef987f4c9`, sha256 `42eaac5e61d177430ce8e331767d2137b3f9b2bd197e13945b84f7c5e8cd79c7` (blob in Git) |
| **Tested repo commit** | `ccf4041ffb3f53282ec4f89c095135716f28e5da` (branch `feat/gate-04-k3s-control-plane`) |
| **Target identity** | `kube-system` namespace UID `d7d8a462-c503-49ed-a1e0-899f372f9465`; API server `https://10.2.0.100:6443` (private VIP); hosts `veridex-server-1/2/3` (control-plane,etcd), SSH host-key fingerprints match `ansible/files/known_hosts` |
| **High-risk** | Yes — etcd and secrets encryption/audit changes on a live 3-voter etcd cluster (CLAUDE.md §12 triggers: etcd, auth/secrets) |
| **Verifier independence** | Tier 1 — one independent adversarial review (separate context, given only the diff and the Gate 4 plan text). Found 6 issues; the four real, addressable ones were fixed and reverified live. No Tier 2 review obtained; continuing the pattern accepted at Gates 0-3, with explicit operator authorization obtained in this conversation before any mutation, per §12. |

## 1. Objective

> Three pinned k3s servers form one embedded‑etcd cluster. Secrets encryption and audit logging operate. API VIP and required public DNS SAN are present.

## 2. Scope

**In scope**
- Node identity, etcd member/voter count, certificate SAN, encryption-at-rest, and audit logging: all verified live against the already-running cluster.
- The one real gap found: the API certificate lacked the plan's required public DNS SAN. Added (`api.veridexeai.com`), applied via a rolling, one-at-a-time restart of all three control-plane nodes.
- Hardening the rollout mechanism itself (`playbooks/install-k3s-servers.yml`, `roles/k3s-server`) so a future config change to a live cluster is safe by default, not safe only because an operator ran it carefully by hand this one time.

**Out of scope**
- kube-vip failure behavior under a hard power-off → Gate 5 (this gate's rolling restarts were a graceful `systemctl restart`, not a power-off; they incidentally exercised the VIP's failover path without being the deliberate, destructive test Gate 5 requires).
- CoreDNS, Cilium tuning → Gate 6.
- Publishing `api.veridexeai.com` as an actual public DNS record → deliberately not done; 6443 remains firewalled (Gates 0/3) and the name is resolved privately by operators.
- Off-cluster etcd snapshots (`etcd_s3_*`) → deferred, tracked in the secret register under Gate 9/18/21 per the open ordering conflicts.
- Rotating or replacing the cluster's CA → not attempted; only a SAN was added to the existing CA-signed certificate.

## 3. Processes activated

| Process | Owner (Workflow ownership table) | Detection if it silently stops |
|---|---|---|
| Hourly etcd snapshots (`etcd-snapshot-schedule-cron`, already configured) | k3s (Ansible-managed config) | Not re-verified by this gate beyond confirming the config value is rendered; a dedicated snapshot/restore check belongs to a later gate. |
| Audit logging to `/var/log/kubernetes/audit/` with rotation | k3s (Ansible-managed config) | `roles/k3s-server`'s own "Write the API audit policy" task fails the play if the policy file's parent state is wrong; ongoing production would need a log-shipping/alerting check, not yet built. |
| Secrets encrypted at rest (`secrets-encryption: true`) | k3s (Ansible-managed config) | No automated re-check exists yet; this gate proved it once, live. A regression would only be caught by a future gate's audit or another manual test. |
| Per-node etcd voter-count and cert-SAN assertions on every `install-k3s-servers.yml` converge (new, this gate) | Ansible (`roles/k3s-server`) | The role's own asserts fail the play if a future converge finds fewer than 3 non-learner voters or a missing SAN. |

## 4. Deliverables

| ID | Artifact | Commit |
|---|---|---|
| D25 | `ansible/inventory/production/group_vars/all.yml` — `api.veridexeai.com` added to `k3s_tls_san` | `ccf4041` |
| D26 | `ansible/playbooks/install-k3s-servers.yml` — `serial: 1`, `any_errors_fatal: true`, bootstrap-server-last host ordering | `ccf4041` |
| D27 | `ansible/roles/k3s-server/tasks/main.yml` — per-node served-certificate SAN assertion; per-node etcd member/voter assertion (installs `etcd-client` as a prerequisite) | `ccf4041` |
| D28 | `docs/evidence/gates/gate-04/closure.md` — this record | (evidence commit follows) |

## 5. Technical detail

**Decision rationale**
- *`api.veridexeai.com` is a SAN, not a published DNS record*: an FQDN cannot resolve to the private VIP address from the public internet, and 6443 is deliberately not publicly reachable (Gates 0, 3). The plan's own repo comment already anticipated this ("resolved privately, no public record"); this gate only had to make the certificate valid for that name, which is what "required... SAN are present" actually asks for.
- *`any_errors_fatal: true`, found by independent review*: `serial: 1` alone only bounds how many hosts run concurrently — it does not stop Ansible from proceeding to the next serial batch after a host fails. Without this, a canary that failed its post-restart health check would not have stopped the remaining two voters from being restarted anyway, which is precisely this gate's stop condition.
- *Bootstrap server last, encoded in the host list, not left as convention*: the actual rollout was done server-2, server-3, then server-1 (the `--cluster-init` node) by deliberate operator choice. The independent review correctly flagged that nothing in code enforced this, so a later unlimited run of the same playbook would have restarted the bootstrap node first by default (plain inventory order). Reordered via `groups['k3s_servers'] | sort | first` moved to the end of the host list.
- *Per-node cert-SAN and etcd-voter assertions, not just `/healthz`*: the independent review pointed out that API liveness and node-Ready are a proxy for etcd/cert health, not a direct check of the two literal things this gate's stop condition names ("certificate mismatch", "fewer than three voters"). Both are now asserted directly, per node, as part of the same gate that decides whether Ansible proceeds — not a manual command run once at the end.
- *Encryption-at-rest proof reads the raw storage layer directly*: the Kubernetes API always decrypts Secrets server-side, so `kubectl get secret` would show plaintext regardless of whether at-rest encryption works. The only real proof is grepping the raw etcd data file for a known plaintext value (absent) and the `k8s:enc:aescbc:v1:` provider prefix (present).

**Resource tables** — `ansible/roles/k3s-server` gained two new task blocks (cert-SAN assert, etcd-voter assert) and one new package dependency (`etcd-client`, Ubuntu's own repo, version 3.4.30 against a k3s-embedded etcd it talks to only via the stable v3 API — sufficient for `member list`/`endpoint health`).

## 6. Exit gate

| ID | Acceptance item (plan) | Method | Evidence | Result |
|---|---|---|---|---|
| EG20 | Node identity | `k3s kubectl get nodes -o wide` | `c1-node-identity.txt` | **PASS** — 3 nodes with role `control-plane,etcd`, all `Ready`, matching the inventory |
| EG21 | etcd member list | `etcdctl member list` / `endpoint health`, local client certs | `c2-etcd-member-list.txt` | **PASS** — exactly 3 members, all `IS LEARNER=false`, all healthy |
| EG22 | Certificate SAN inspection | `openssl x509 ... -text` on the served cert; SNI handshake via `openssl s_client -servername api.veridexeai.com` against the VIP | `c3-certificate-san.txt` | **PASS** — `api.veridexeai.com` present in the served cert's SAN list and returned over an actual TLS/SNI handshake |
| EG23 | Encrypted-at-rest proof | Create a Secret with a random single-use marker; grep the raw etcd data file for the marker (plaintext, expect absent) and the `k8s:enc:` prefix (expect present); delete the test Secret | `c4-encrypted-at-rest.txt` | **PASS** — marker not found in plaintext; `k8s:enc:aescbc:v1:` prefix confirmed present |
| EG24 | Audit event proof | Trigger a specific, identifiable API request; find the matching event in the live audit log within seconds | `c5-audit-event.txt` | **PASS** — the exact triggered `get namespaces/kube-system` request appears in `audit.log` with a matching timestamp |

**Stop condition (verbatim):** "Fewer than three voters, wrong cluster, certificate mismatch, plaintext Secret in raw etcd, or missing audit event."

**Triggered: no.**
- *Fewer than three voters:* EG21 — exactly 3, none a learner; now also asserted automatically on every future converge (D27).
- *Wrong cluster:* target identity (`kube-system` UID, VIP address) matches the cluster this session has operated on throughout Gates 0-3; no other cluster was touched.
- *Certificate mismatch:* EG22 — the served certificate matches what was requested (SAN present, verified via an actual handshake, not just a config file read).
- *Plaintext Secret in raw etcd:* EG23 — explicitly tested and not found.
- *Missing audit event:* EG24 — a specific triggered request was found in the log.

## 7. Rollback

### 7.1 Reversal procedure

In reverse dependency order: remove `api.veridexeai.com` from `k3s_tls_san` and rerun `install-k3s-servers.yml` (now safe by construction — `serial: 1`, `any_errors_fatal: true`, bootstrap last) to reissue the certificate without that SAN; revert `roles/k3s-server`'s new assertion tasks and the playbook's `serial`/`any_errors_fatal`/host-ordering changes if ever needed (not recommended — these are pure safety additions with no functional dependency). Nothing here is irreversible: the cluster's CA was never rotated, only a SAN was added to and could be removed from certificates it already signs.

### 7.2 Adversarial hardening loop

One iteration (cap 11).

| Iteration | Source | Findings | Fix commits |
|---|---|---|---|
| 1 | Independent review (Tier 1, separate context, given the diff and Gate 4 plan text) | 6 findings: (high) `serial: 1` without `any_errors_fatal` does not actually stop the play on a canary failure; (medium) default host order would restart the bootstrap node first, reversing the precaution taken by hand; (medium/high) no automated per-node check that the served certificate itself carries the new SAN (only the VIP-served cert was checked manually); (medium) no automated etcd voter/learner check gating each restart -- the literal stop-condition metric was only checked once, manually, at the end; (info) the `kubeconfig` role is an empty stub, irrelevant to this specific change since the CA was not rotated | `ccf4041` (fixed all four addressable findings: `any_errors_fatal: true`; bootstrap-last host-list ordering; per-node served-cert SAN assert; per-node etcd member/voter assert, installing `etcd-client` as needed) |

**Attacks attempted:** the review's brief explicitly asked it to look for ways `serial: 1` could still allow concurrent voter restarts, ways the rollout could report success without the SAN actually being live everywhere, and ways stale cached clients could break post-rotation. It found the `any_errors_fatal` gap (a real way `serial: 1` alone fails to prevent cascading restarts) and the cert-SAN/etcd-voter verification gaps (real ways a "successful" run could still leave the literal stop-condition metrics unchecked). It did not find a working exploit for stale-client breakage, correctly noting the CA itself was never rotated.

**Tracked exceptions:** none open — all four addressable findings were fixed; the fifth (empty `kubeconfig` role) is informational and out of this change's scope (no CA rotation occurred).

### 7.3 IIR attestation

- **Immutable:** every fix is committed on `feat/gate-04-k3s-control-plane` (`ccf4041`).
- **Idempotent:** after the hardening fixes, a full run of `install-k3s-servers.yml` (all three servers, no `--limit`) reported `changed=0`, `failed=0` on all three — `c6-iir-rerun.txt`. The one non-zero-change run immediately before it was `etcd-client` being installed for the first time on two of the three nodes (a new, intentional dependency of this gate's own verification tasks), not configuration drift.
- **Repeatable:** the hardened playbook, run without `--limit`, now reproduces the exact safe sequence (one at a time, bootstrap last, stop on first failure) that was previously only achieved by an operator manually invoking `--limit` three times in the right order. Reproducibility from a bare/reinstalled node (initial `--cluster-init` bring-up) is not exercised here, since the cluster already existed.

## 8. Known limitations

- Verifier independence is Tier 1 only for a gate that CLAUDE.md §12 classifies high-risk (etcd, auth/secrets); no Tier 2 (different model/external grader) review was obtained.
- The encryption-at-rest test reads a live etcd data file directly on disk while etcd is running; this is not a guaranteed-consistent read (no snapshot/lock taken), though sufficient in practice to prove a plaintext value's absence at the byte level.
- The per-node etcd-voter and cert-SAN checks added to `roles/k3s-server` were exercised on this run but have not yet been tested against an actual failure (e.g. deliberately breaking a SAN or etcd member count to confirm the assert actually fires and halts the play) — only the happy path was observed live.
- Same limitations already disclosed in Gates 1-3's closure records continue to apply unchanged (break-glass key co-location, host-key TOFU, no bare-node reproducibility proof, boot-persistence unproven by an actual reboot).
