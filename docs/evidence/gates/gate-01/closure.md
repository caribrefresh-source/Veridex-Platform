# GATE 1 — Operating systems and access

| | |
|---|---|
| **Verdict** | **PASS** |
| **Closed (UTC)** | 2026-09-14T03:11:49Z |
| **Plan** | `docs/Engineering Documents/Initial Stages Plan.txt` @ `4ebc8def34df78a0bc6b29e42656986ef987f4c9`, sha256 `42eaac5e61d177430ce8e331767d2137b3f9b2bd197e13945b84f7c5e8cd79c7` (blob in Git) |
| **Tested repo commit** | `35730638452fac63972aa37bd38346d96e37e5e1` (branch `feat/gate-01-os-access`) |
| **Target identity** | hosts `veridex-server-1` (152.53.177.26), `veridex-server-2` (152.53.140.210), `veridex-server-3` (152.53.142.131), `veridex-agent-1` (159.195.197.136), `veridex-agent-2` (159.195.197.40); SSH host-key fingerprints match `ansible/files/known_hosts` |
| **High-risk** | Yes — SSH authentication/authorization changes on all five production nodes (CLAUDE.md §12 trigger: auth/secrets) |
| **Verifier independence** | Tier 1 — one independent adversarial review (separate context, given only the diff and the Gate 1 plan text). Found 8 issues (0 critical, 2 high, 4 medium, 2 low); the actionable ones were fixed and reverified live (§7.2). No Tier 2 (different model/external grader) review was obtained; accepted at Tier 1 by the repository owner's direction to proceed with this build. |

## 1. Objective

> All five nodes run the approved Ubuntu 24.04 point release. SSH is key‑only, root policy is explicit, host keys match recorded fingerprints, time synchronization is healthy, and administrative access is recoverable.

## 2. Scope

**In scope**
- Time synchronization: chrony installed, pinned NTP pools, verified synced (`roles/chrony`).
- Recorded host-key baseline for all five nodes, enforced by Ansible (`ansible/files/known_hosts`, `ansible.cfg`).
- Recoverable administrative access: a second (break-glass) SSH key, independent of the single key netcup's provisioning API installed, made part of a declarative, version-controlled key list (`roles/ssh-access`).
- Explicit, hardened root login policy restated independently of netcup's provisioning-time default (`roles/ssh-hardening`).
- A code-enforced check that each node runs the approved OS (`roles/common`).
- A tooling fix (`manual_only` + required review date) needed to honestly register the break-glass key as a secret no automation consumes.

**Out of scope**
- Cross-checking inventory public addresses against the netcup API → Gate 1 was already scoped to this repository's own records; a live netcup-API cross-check was not requested and is not part of this gate's acceptance evidence.
- Storing the break-glass private key somewhere independent of the primary key's storage (both currently live on the same operator workstation) → flagged as an open gap in `docs/security/emergency-access.md`, not fixed here.
- netcup's own rescue/KVM console as an alternative recovery path → not evaluated; the break-glass key was judged sufficient for this gate.
- Private network addressing, MTU, firewall rules → Gate 2, Gate 3 (this gate's `prepare-hosts.yml` changes ran alongside the pre-existing `common`/`firewall` roles without modifying their scope).
- k3s, kube-vip, Cilium, CoreDNS → Gates 4-6, already live on these nodes from prior work (see `docs/evidence/legacy/`) but not re-verified or owned by this gate.

## 3. Processes activated

| Process | Owner (Workflow ownership table) | Detection if it silently stops |
|---|---|---|
| `roles/chrony` keeps chrony installed, configured and synced on every converge | Ansible | `chronyc tracking`/`sources` (captured here); a future `prepare-hosts.yml` run reporting `changed` on the chrony tasks unexpectedly, or `chronyc waitsync` failing the play. |
| `roles/ssh-access` keeps `admin_ssh_public_keys` as the sole source of truth for root's `authorized_keys`, and refuses to run with fewer than two keys | Ansible | The role's own assert fails the play if the list is ever reduced to one key. |
| `roles/ssh-hardening` keeps `PermitRootLogin`/`PasswordAuthentication` explicit regardless of the OS-provisioning default | Ansible | The role's own `sshd -T` assert fails the play if the effective config drifts from the hardened values. |
| Host-key checking against `ansible/files/known_hosts` | Ansible (`ansible.cfg`, `ssh_args`) | Any Ansible/SSH connection fails closed (`StrictHostKeyChecking=yes`) if a node's host key ever changes without the baseline being deliberately re-captured. |
| `manual_only` secret-register entries require a human-confirmed `manual_only_reviewed` date | `scripts/lint-secret-register.py` (CI) | A missing or malformed date fails the secret-register CI job. |

## 4. Deliverables

| ID | Artifact | Commit |
|---|---|---|
| D9 | `ansible/roles/chrony/` — install, pinned NTP pools, `waitsync` verification | `b2df48c` |
| D10 | `ansible/roles/ssh-access/` — declarative `authorized_keys`, key-format validation | `b2df48c`, `3573063` |
| D11 | `ansible/roles/ssh-hardening/` — hardened root-login drop-in, `sshd -t` validation, fresh-connection reconnect check | `b2df48c`, `4f0575f`, `3573063` |
| D12 | `ansible/files/known_hosts` — recorded host-key baseline, all five nodes | `b2df48c` |
| D13 | `ansible/ansible.cfg` — `host_key_checking = True`, `ssh_args` pinned to the committed baseline | `b2df48c` |
| D14 | `ansible/inventory/production/group_vars/all.yml` — `admin_ssh_public_keys` (primary + break-glass) | `b2df48c` |
| D15 | `ansible/roles/common/tasks/main.yml` — approved-OS assert (Gate 1's "unsupported OS" stop condition) | `3573063` |
| D16 | `ansible/playbooks/prepare-hosts.yml` — roles wired (`common, chrony, ssh-access, ssh-hardening, firewall`), `serial: 1` | `b2df48c`, `3573063` |
| D17 | `docs/security/emergency-access.md` — break-glass key procedure and disclosed limitations | `b2df48c`, `3573063` |
| D18 | `docs/security/secret-register.yml` — break-glass key entry (`manual_only`, reviewed date) | `b2df48c`, `3573063` |
| D19 | `scripts/lint-secret-register.py` — `manual_only` + `manual_only_reviewed` escape hatch | `176d4cc`, `3573063` |
| D20 | `docs/evidence/gates/gate-01/closure.md` — this record | `3573063` (evidence commit follows) |

## 5. Technical detail

**Decision rationale**
- *`without-password` over `prohibit-password`*: both are accepted by `sshd_config`, but `sshd -T` always echoes the setting back as `without-password`. Written and verified using the same spelling so the config and its own verification agree — found live on `veridex-server-2` during the first apply (§7.2).
- *`serial: 1` on `prepare-hosts.yml`*: `roles/ssh-hardening` reloads `sshd` and forces a reconnect on every host it touches. Without `serial`, Ansible's default `forks=5` runs that sequence on all five hosts in the same batch, so a bad config change would not "fail on the first node" as the role's comments claim — found by independent review (§7.2).
- *`manual_only` escape hatch, not a code reference*: the break-glass private key must never be read by automation — that would defeat its purpose as an out-of-band fallback — so it cannot satisfy the secret-register lint's normal consumption-pattern check. A reviewed, dated, explicit opt-out is the smallest change that keeps the register honest without inventing a fake consumer.
- *Host-key baseline is disclosed TOFU*: `ssh-keyscan` was run from this operator session with no independent out-of-band source (e.g. netcup's provisioning email) to cross-check against. Recorded as a known limitation, not presented as independently verified.

**Resource tables** — Ansible roles added: `chrony`, `ssh-access`, `ssh-hardening`. Existing roles changed: `common` (OS assert added), `firewall` (unchanged, reordered after the new roles in `prepare-hosts.yml`).

## 6. Exit gate

| ID | Acceptance item (plan) | Method | Evidence | Result |
|---|---|---|---|---|
| EG5 | os-release | `cat /etc/os-release` on all five nodes | `c1-os-release.txt` | **PASS** — Ubuntu 24.04.5 LTS on all five, matching each other and the netcup-catalogue policy recorded in `group_vars/all.yml` |
| EG6 | sshd effective configuration | `sshd -T` (filtered) on all five nodes | `c2-sshd-effective-config.txt` | **PASS** — `permitrootlogin without-password`, `passwordauthentication no`, `kbdinteractiveauthentication no`, `permitemptypasswords no` on all five |
| EG7 | chrony status | `chronyc tracking; chronyc sources` on all five nodes | `c3-chrony-status.txt` | **PASS** — all five report `Leap status: Normal` with multiple reachable sources (`ntp.ubuntu.com` pool members and `time.cloudflare.com`) |
| EG8 | host-key fingerprint comparison | Fresh `ssh-keyscan -t ed25519` against all five public IPs, diffed against the committed `ansible/files/known_hosts` | `c4-host-key-fingerprints.txt` | **PASS** — exact match, zero diff |
| EG9 | access test from approved runner | SSH using only the break-glass private key (`~/.ssh/veridex_breakglass_ed25519`) to all five nodes | `c5-recoverable-access.txt` | **PASS** — authenticates as root on all five; primary key remains the routine-use key |

**Stop condition (verbatim):** "Password authentication, mismatched fingerprint, unsupported OS, clock drift, or unavailable emergency access."

**Triggered: no.**
- *Password authentication:* EG6 — `passwordauthentication no` and `kbdinteractiveauthentication no` on all five, `permitrootlogin` restricted to key-only (`without-password`).
- *Mismatched fingerprint:* EG8 — zero diff between the live keyscan and the recorded baseline.
- *Unsupported OS:* EG5 — Ubuntu 24.04.5 on all five; also now asserted on every converge (`roles/common`), not only checked once.
- *Clock drift:* EG7 — all five synced, `Leap status: Normal`.
- *Unavailable emergency access:* EG9 — the break-glass key is live-tested and authenticates as root on all five nodes today. The residual gap (both keys on one workstation) is disclosed in §8, not a trigger of this stop condition as the plan states it (a specific fallback key that does not work).

## 7. Rollback

### 7.1 Reversal procedure

Ansible-managed, declarative changes only; nothing outside Git and the five nodes' `/etc` was touched. In reverse dependency order: revert `roles/ssh-hardening` (restores `PermitRootLogin yes`, relying again on the global `PasswordAuthentication no` alone) and rerun `prepare-hosts.yml`; then revert `roles/ssh-access` (returns `authorized_keys` to whatever the next converge without it would leave — in practice, still both keys, since nothing deletes a file `ssh-access` no longer manages; a full removal would need an explicit cleanup task, not included here since it was not requested); then revert `roles/chrony` (chrony stays installed but unmanaged — no automatic uninstall, by design, since removing a working time sync service is not a safe default); then revert `ansible.cfg`'s `host_key_checking`/`ssh_args` and delete `ansible/files/known_hosts` to return to the pre-Gate-1 (unchecked) state. No step is irreversible. The break-glass private key, once generated, is not un-generated by any rollback — its public half would need to be removed from `admin_ssh_public_keys` and a converge run to actually revoke it from the nodes.

### 7.2 Adversarial hardening loop

Two iterations (cap 11).

| Iteration | Source | Findings | Fix commits |
|---|---|---|---|
| 1 | Live application (canary run, `veridex-server-2`) | `sshd -T` echoes `PermitRootLogin prohibit-password` back as `without-password` — the verification assert used the input spelling and failed even though the applied config was correct | `4f0575f` |
| 2 | Independent review (Tier 1, separate context, given the diff and Gate 1 plan text) | 8 findings: (high) break-glass key not independent of the primary key's storage; (high) no `serial` control, so a bad sshd change would hit all five nodes before failing; (medium) no code-enforced OS-version assert; (medium) break-glass key tested on only 2 of 5 nodes; (medium) `manual_only` has no decay/review mechanism; (medium, disclosed) host-key baseline is unverified TOFU; (low) `reset_connection`'s `when:` is silently ignored by Ansible; (low) key-write verification was near-tautological (proved the write matched the variable, not that the key is well-formed) | `3573063` (fixed: OS assert, `serial: 1`, key-format validation, `reset_connection` cleanup, `manual_only_reviewed` requirement, break-glass key tested on the remaining 3 nodes, limitation disclosed in `emergency-access.md`); not fixed: break-glass key still co-located with the primary key (tracked exception, §8); host-key TOFU (already disclosed, §8) |

**Attacks attempted:** the independent review's brief explicitly asked it to try to find ways the change could lock out SSH, fail to actually close the recoverability gap, silently no-op, leave a node worse off, or let `manual_only` hide a stale secret. Its findings are listed above; none of the "lock out SSH" or "silent no-op" attack angles produced a working exploit — the two high findings were about incomplete risk closure (break-glass key co-location) and a latent blast-radius gap (no `serial`), not an active break.

**Tracked exceptions** (disclosed, not fixed by this gate):

| ID | Weakness | Where it would be addressed |
|---|---|---|
| E1 | Break-glass private key lives on the same operator workstation as the primary key; losing the workstation loses both | Operational hardening: store the break-glass key in an offline vault, hardware token or sealed physical backup |
| E2 | Host-key baseline (`ansible/files/known_hosts`) was captured trust-on-first-use, with no independent out-of-band cross-check | Cross-check against netcup's console/provisioning record when available |
| E3 | `roles/ssh-access`'s rollback does not remove keys from a node once `ssh-access` stops managing it | Explicit cleanup task, if ever needed |

### 7.3 IIR attestation

- **Immutable:** every fix is committed on `feat/gate-01-os-access` (`176d4cc`..`3573063`).
- **Idempotent:** a fleet-wide rerun after all fixes reports `changed=0` on all five nodes, `failed=0` — `iir-rerun.txt`. No k3s, Cilium, CoreDNS, kube-vip or storage service was restarted (this gate's roles touch none of them; `firewall`, which runs after, also reported `ok` not `changed`).
- **Repeatable:** the same roles, run against any node in this state, converge identically — proven by running them a second time after the hardening-loop fixes and getting `changed=0` immediately, not after a separate stabilization pass. Reproducibility from a bare/reinstalled node is not proven here (out of Gate 1's scope; would additionally exercise `k3s-server`/`kubevip`/`kubeconfig`).

## 8. Known limitations

- The break-glass key and the primary operator key are both held on the same workstation (E1) — this gate closes "one key is lost or wrong," not "the workstation is lost."
- The host-key baseline is trust-on-first-use (E2); an attacker positioned during the original capture would not be caught by this gate's checks.
- Verifier independence is Tier 1 only; no Tier 2 (different model or external grader) review was obtained for a high-risk, auth-touching gate.
- This build ran through a Windows-native Ansible incompatibility (ansible-core requires `fcntl`, Unix-only) via a disposable Docker container as the control node; the container is not part of the repository and is not itself a reproducible artifact — only the playbooks and roles it ran are.
- `roles/ssh-access`'s full-file `authorized_keys` render is exclusive by construction (anything not in `admin_ssh_public_keys` is gone on the next converge) but this was not adversarially tested against a third, unmanaged key actually being present on a node at converge time.
- `entrepeai.com`, workstation kubeconfigs pointing at the old K3s-HA cluster, and the open ordering conflicts remain exactly as recorded in Gate 0's closure record — untouched by this gate.
