# GATE 3 — Host prerequisites and firewall

| | |
|---|---|
| **Verdict** | **PASS** |
| **Closed (UTC)** | 2026-09-14T04:47:46Z |
| **Plan** | `docs/Engineering Documents/Initial Stages Plan.txt` @ `4ebc8def34df78a0bc6b29e42656986ef987f4c9`, sha256 `42eaac5e61d177430ce8e331767d2137b3f9b2bd197e13945b84f7c5e8cd79c7` (blob in Git) |
| **Tested repo commit** | `a194cf64777d30ffaa4cc71a6122a27d03e29fc1` (branch `feat/gate-03-host-prereqs`) |
| **Target identity** | hosts `veridex-server-1` (152.53.177.26), `veridex-server-2` (152.53.140.210), `veridex-server-3` (152.53.142.131), `veridex-agent-1` (159.195.197.136), `veridex-agent-2` (159.195.197.40); SSH host-key fingerprints match `ansible/files/known_hosts` |
| **High-risk** | Yes — kernel module and sysctl changes on all five production nodes (CLAUDE.md §12 trigger: Cilium/networking-adjacent host configuration) |
| **Verifier independence** | Tier 1 — one independent adversarial review (separate context, given only the diff and the Gate 3 plan text). Found 6 issues (0 critical/high blocking the stop condition); the two real, cheap ones were fixed and reverified live. No Tier 2 review obtained; proceeding at Tier 1 continues the pattern accepted at Gates 0-1. |

## 1. Objective

> Kernel, sysctl, modules, packages and firewall satisfy k3s, Cilium and Longhorn. open‑iscsi is installed and iscsid is active. nfs‑common is installed where RWX is supported. Public access is restricted to approved ingress and rate‑limited SSH.

## 2. Scope

**In scope**
- `open-iscsi`/`iscsid`, `nfs-common`, required kernel modules and sysctls: verified live, gaps found and fixed (`roles/host-prereqs`, new).
- Firewall: already built and verified in Gates 0-1 (`roles/firewall`, unmodified). Fresh, dated evidence captured for this gate's own closure (external port scan, private-port test) rather than reused from an earlier gate.

**Out of scope**
- Longhorn's own literal `longhornctl check preflight` tool: Longhorn is not deployed yet (a later gate), so there is no such tool to run against these nodes. Its documented host prerequisites are verified directly instead (§5, §8).
- `cilium-cli`'s preflight subcommand: Cilium is already installed and running from prior work, not being freshly installed, so a pre-install preflight tool does not apply here either.
- Reverting `firewall_public_tcp_ports`/adding Traefik NodePorts → later gate, when an ingress controller exists.
- A deliberate reboot test to prove the new modules/sysctls actually survive a real boot, not just persistence-file presence → flagged as a residual limitation (§8), not attempted here (a canary reboot is a distinct, higher-risk action needing its own authorization).

## 3. Processes activated

| Process | Owner (Workflow ownership table) | Detection if it silently stops |
|---|---|---|
| `roles/host-prereqs` keeps `iscsid` enabled/active, `nfs-common` installed, and the required kernel modules/sysctls persisted on every converge | Ansible | The role's own asserts (module loaded, sysctl value, `iscsid` active, `nfs-common` installed) fail the play if any drifts. |
| Public access restricted to rate-limited SSH only (`roles/firewall`, pre-existing) | Ansible | `roles/firewall`'s own read-back assert (already verified at Gates 0-1) fails the play if the ruleset ever admits more. |

## 4. Deliverables

| ID | Artifact | Commit |
|---|---|---|
| D22 | `ansible/roles/host-prereqs/` — packages, `iscsid`, kernel modules, sysctls, all read back and asserted | `a194cf6` |
| D23 | `ansible/playbooks/prepare-hosts.yml` — `host-prereqs` wired in after `common` | `a194cf6` |
| D24 | `docs/evidence/gates/gate-03/closure.md` — this record | (evidence commit follows) |

No new firewall deliverable: `roles/firewall` (a Gate 0-1 artifact) is verified, not re-delivered, by this gate.

## 5. Technical detail

**Decision rationale**
- *Template + `sysctl -p`, not `ansible.builtin.sysctl`*: that module lives in the `ansible.posix` collection, which this repo does not otherwise depend on (same reasoning already applied to `roles/ssh-access` at Gate 1, which uses `copy` instead of `ansible.posix.authorized_key`).
- *This role does not manage `net.ipv4.conf.*.rp_filter`*: Cilium's own installer already writes `/etc/sysctl.d/99-zzz-override_cilium.conf` for that. Verified live that neither that file nor netcup's own `/etc/sysctl.d/99-nc-kernel.conf` sets any of the three keys this role does own — checked directly (found during independent review), not assumed.
- *`nfs-common` installed on all five nodes, not a subset*: the plan says "where RWX is supported"; nothing in this repo scopes which nodes are RWX-eligible, `nfs-common` is an inert client package with no running daemon until something mounts NFS, and the existing repo comment already ties it to the Wasabi backup target as well as Longhorn RWX — so universal installation is the reading that doesn't require inventing a distinction the plan doesn't draw.
- *Self-healing sysctl apply*: found during independent review — the apply task originally only ran when the rendered file changed, so it could never correct a live value that drifted back without the file itself changing. Fixed to always run (a safe no-op when values already match).

**Resource tables** — Ansible roles added: `host-prereqs`. `prepare-hosts.yml` role order: `common, host-prereqs, chrony, ssh-access, ssh-hardening, firewall`.

## 6. Exit gate

| ID | Acceptance item (plan) | Method | Evidence | Result |
|---|---|---|---|---|
| EG14 | Longhorn preflight | `systemctl is-active/is-enabled iscsid`, `dpkg-query nfs-common`, `lsmod iscsi_tcp`, `uname -r` on all five nodes | `c1-longhorn-preflight.txt` | **PASS** — `iscsid` active+enabled, `nfs-common` installed, `iscsi_tcp` loaded, kernel `6.8.0-139-generic` on all five |
| EG15 | Cilium preflight | `lsmod` for `overlay`/`br_netfilter`/`vxlan`, `sysctl` for `ip_forward`/`bridge-nf-call-{ip,ip6}tables` on all five nodes | `c2-cilium-preflight.txt` | **PASS** — all modules loaded, all sysctls `= 1` on all five |
| EG16 | systemd checks | `systemctl is-active`/`is-enabled` for `iscsid`, `nftables`, `chrony` on all five nodes | `c3-systemd-checks.txt` | **PASS** — all three active and enabled on all five |
| EG17 | External port scan | `Test-NetConnection` against public IPs, ports 22/6443/10250/2379/2380, all five nodes | `c4-external-port-scan.txt` | **PASS** — only 22 open; 6443/10250/2379/2380 closed on all five |
| EG18 | Private-port tests | `/dev/tcp` probe of `10.2.1.10:6443` and `:10250` from a different server and a different agent, over the private vLAN | `c5-private-port-tests.txt` | **PASS** — both ports reachable from both probing nodes |
| EG19 | `changed=0` rerun | `ansible-playbook playbooks/prepare-hosts.yml` (fleet-wide) after the hardening-loop fixes | `c6-iir-rerun.txt` | **PASS** — `changed=0`, `failed=0` on all five nodes |

**Stop condition (verbatim):** "Failed preflight, exposed 6443/10250, disabled firewall, broad public source rule, or host restart on rerun."

**Triggered: no.**
- *Failed preflight:* EG14/EG15 — every checked prerequisite present and correct on all five nodes.
- *Exposed 6443/10250:* EG17 — both closed externally on all five.
- *Disabled firewall:* EG16 — `nftables` active and enabled on all five (unchanged from Gate 0-1's verification).
- *Broad public source rule:* unchanged from Gate 0-1 — `firewall_public_tcp_ports`/`firewall_public_udp_ports` remain empty; only rate-limited SSH is admitted publicly.
- *Host restart on rerun:* EG19 — `changed=0` on the second run; no task in `roles/host-prereqs` notifies a restart of `iscsid` or any other service on a no-op converge, and none fired.

## 7. Rollback

### 7.1 Reversal procedure

Ansible-managed, declarative changes only. In reverse dependency order: revert `roles/host-prereqs` and rerun `prepare-hosts.yml` — this disables and stops `iscsid` (per the `systemd` module's normal revert-of-absence behavior once the task is removed, i.e., a further explicit task would be needed to actively stop it; simply removing the role leaves `iscsid` running but no longer managed, which is not itself unsafe), leaves `nfs-common` installed (removing a package on revert is not attempted by this role and would need an explicit uninstall task if ever required), and removes the `/etc/modules-load.d/veridex-host-prereqs.conf` and `/etc/sysctl.d/60-veridex-host-prereqs.conf` files on the next converge that includes a cleanup task (not included here, since removing already-correct persistence was not requested). No step is irreversible; nothing outside these two files and package/service state was touched.

### 7.2 Adversarial hardening loop

One iteration (cap 11).

| Iteration | Source | Findings | Fix commits |
|---|---|---|---|
| 1 | Independent review (Tier 1, separate context, given the diff and Gate 3 plan text) | 6 findings: (medium) sysctl-apply task could not self-heal live drift, only fail the assert; (medium) cross-file sysctl conflict with netcup's/Cilium's own sysctl.d files was asserted in a comment but not actually checked; (medium, disclosed) the boot-persistence guarantee this role exists for is unproven by an actual reboot; (low) fragile substring match for "module already loaded"; (low, pre-existing) unpinned package versions, matching the existing `roles/chrony` convention; (info) `nfs-common` installed on all five rather than a RWX-scoped subset, judged acceptable (§5) | `a194cf6` (fixed: self-healing sysctl apply, line-anchored module check, cross-file conflict checked live and recorded as VERIFIED; not fixed: reboot-persistence proof (disclosed, §8), package pinning (pre-existing repo-wide gap, out of this gate's scope)) |

**Attacks attempted:** the review's brief explicitly asked it to look for silent-success paths, host/service restarts on rerun, worse-than-before states from sysctl conflicts, non-idempotence not visible on a single rerun, and over/under-scoped `nfs-common` installation. None of the "silent success" or "restart on rerun" attack angles found a working exploit — the two real findings were about a recovery gap (self-healing) and an unverified cross-file assumption, both fixed; the third (reboot-persistence) is a genuine, disclosed limit on what this evidence proves, not a defect in the code as written.

**Tracked exceptions** (disclosed, not fixed by this gate):

| ID | Weakness | Where it would be addressed |
|---|---|---|
| E4 | Kernel-module and sysctl persistence across an actual reboot is unproven (only inspected live, running state) | A deliberate, authorized canary reboot of one node, drained first |
| E5 | `open-iscsi`/`nfs-common` use `state: present` (unpinned), matching the pre-existing `roles/chrony` pattern | Repo-wide package-pinning pass, if ever undertaken |

### 7.3 IIR attestation

- **Immutable:** every fix is committed on `feat/gate-03-host-prereqs` (`a194cf6`).
- **Idempotent:** a fleet-wide rerun after the hardening-loop fixes reports `changed=0`, `failed=0` on all five nodes — `c6-iir-rerun.txt`. No service was restarted (`iscsid` uses `state: started`, not `restarted`; no task in this role notifies a restart).
- **Repeatable:** the same role, applied to any node in this state, converges identically — proven by the canary-then-fleet rollout pattern (single node first, then the remaining four, all reaching the same `ok`/`changed` shape). Reproducibility from a bare/reinstalled node, and survival of an actual reboot, are not proven here (E4).

## 8. Known limitations

- The central guarantee this gate exists for — that the required kernel modules and sysctls survive a reboot — is verified by inspecting the persistence files' presence and content, not by an actual reboot (E4). This is disclosed rather than implicitly claimed.
- `open-iscsi`/`nfs-common` package versions are unpinned (E5), a pre-existing repo-wide pattern, not a regression introduced here.
- "Longhorn preflight" and "Cilium preflight" are satisfied by directly verifying the documented host prerequisites each tool would check, not by running the literal upstream tools — Longhorn isn't deployed yet, and Cilium isn't being freshly installed.
- Same limitations already disclosed in Gates 1-2's closure records continue to apply unchanged (break-glass key co-location, host-key TOFU, no bare-node reproducibility proof).
