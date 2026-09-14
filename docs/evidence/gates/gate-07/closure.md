# GATE 7 — Verification automation

| | |
|---|---|
| **Verdict** | **BLOCKED (PLAN_UNTRACKED)** — every individual check below is **PASS**; the ledger row cannot be appended this run (see Known Limitations) |
| **Closed (UTC)** | not closed |
| **Plan** | `docs/Engineering Documents/Initial Stages Plan.txt` — **uncommitted working copy**, sha256 `a32ea3fbfc2c69aeb06346ad7d251e9df14e54c5302259b739be5df871665a0c`. Last committed plan blob: `4ebc8def34df78a0bc6b29e42656986ef987f4c9` (unchanged since Gates 0-6; Gate 7's own text, lines 176-197, is identical in both). The working copy differs only in unrelated, pre-existing material (a Gates 32-35 amendment) found already modified at the start of this session, before any Gate 7 work. |
| **Tested repo commit** | `a4d5223e1856efe45ce7f59144ae73597624f4c1` (branch `feat/gate-07-verification-automation`) |
| **Target identity** | `kube-system` namespace UID `d7d8a462-c503-49ed-a1e0-899f372f9465`; API server `https://10.2.0.100:6443` (private VIP); hosts `veridex-server-1/2/3`, `veridex-agent-1/2` |
| **High-risk** | Yes — reads etcd data and secrets/audit-log configuration (CLAUDE.md §12 triggers: etcd, auth/secrets), though strictly read-only, no mutation |
| **Verifier independence** | Tier 1 — one independent adversarial review (separate context, given only the diff and the Gate 7 plan text). Found 4 issues; the one high and one low were real and fixed, one medium was a false positive on direct inspection, one low was accepted as a pre-existing upstream pattern outside this gate's scope. No Tier 2 review obtained; continuing the pattern accepted at Gates 0-6. |

## 1. OBJECTIVE

> verify‑cluster.yml implements gates 3 through 6 as read‑only assertions, identifies the cluster, fails closed, and has a deliberate negative test for each critical category.

## 2. SCOPE

**In scope**
- New role `ansible/roles/verify-cluster/` (defaults + tasks) re-asserting, read-only, the intended state Gates 3-6 already built: host prereqs/firewall (kernel modules, sysctls, systemd units, nftables ruleset), k3s control plane (node identity, etcd voter count, per-node cert SAN, secrets-encryption config, audit log freshness), kube-vip (lease holder, VIP health), Cilium/CoreDNS (cilium status, cilium-config settings, CoreDNS replica count/Service/node spread).
- `ansible/playbooks/verify-cluster.yml` rewritten from an empty `tasks: []` stub to invoke the role.
- New constant `verify_cluster_expected_kube_system_uid` (`group_vars/all.yml`), captured live at Gate 4's own closure, so the playbook can positively identify the cluster before doing anything else.
- Deliberate negative testing across a representative sample of critical categories spanning all four verified gates, confirming fail-closed behavior (non-zero exit) and a useful, specific diagnostic for each.

**Out of scope**
- Gate 4's live "create a marker Secret, grep for it, delete it" and "trigger a request, find the matching audit event" proofs are **not** repeated here — both mutate the cluster. Read-only proxies substitute (existing-data encryption-prefix check; audit-log freshness) → disclosed as weaker evidence, §8.
- Gate 5's hard power-off drill is **not** repeated — destructive, and the plan's Workflow ownership table assigns that action to a human-approved destructive runbook, not a routine verification playbook. A non-destructive lease/VIP-health consistency check substitutes.
- Gate 6's live disposable-pod cross-node ping and DNS-resolution test is **not** repeated — creating a pod is a mutation. CoreDNS scheduling/Service structural proxies substitute.
- Exhaustive negative testing of every one of the role's ~17 individual assertions — 9 representative categories across all four gates were tested instead (§8).
- Gates 32-35 (the in-progress plan amendment found uncommitted in this repository at the start of this session) — unrelated to Gate 7, not touched by this work.
- CI wiring to run this playbook automatically after a change to Gates 3-6's territory — not requested.

## 3. PROCESSES ACTIVATED

None on a continuous/enforced basis. `verify-cluster.yml` is an on-demand diagnostic tool (`make verify-cluster` or a direct `ansible-playbook` invocation) — it enforces nothing by itself and runs nothing on a schedule. Its value is realized when an operator (or a future CI gate) chooses to invoke it, e.g. before/after a change touching Gates 3-6's territory. No entry in the plan's Workflow ownership table currently assigns "run this automatically" to CI; wiring that in is future work, not claimed here.

## 4. DELIVERABLES

Gate-local ids only — cumulative D-numbers are assigned at ledger-append time (§10 of the skill), which this run cannot reach (see Verdict).

| ID | Artifact | Commit |
|---|---|---|
| G07-D1 | `ansible/roles/verify-cluster/defaults/main.yml`, `ansible/roles/verify-cluster/tasks/main.yml` — the read-only assertion role | `5220971`, `a4d5223` |
| G07-D2 | `ansible/playbooks/verify-cluster.yml` — rewritten to invoke the role (`hosts: all`, `gather_facts: true`, `any_errors_fatal: true`) | `5220971` |
| G07-D3 | `ansible/inventory/production/group_vars/all.yml` — `verify_cluster_expected_kube_system_uid` | `5220971` |
| G07-D4 | `docs/evidence/gates/gate-07/` — this record and its four evidence files | (evidence commit follows) |

## 5. TECHNICAL DETAIL

**Decision rationale**
- *`include_vars` over the five roles' own `defaults/main.yml` files, not a second copy of their values*: verify-cluster has no expected values of its own to drift from `host-prereqs`, `firewall`, `k3s-server`, `cilium` and `coredns`'s real intent. Checked directly (and independently re-checked in review) that none of those five files redefine a variable `group_vars/all.yml` also sets to a different, more specific value — `include_vars` is higher precedence than group_vars and would silently clobber such a case if one existed.
- *Cluster identity is the first task, tagged `always`*: found live during this gate's own hardening loop (independent review, HIGH) that tagging it only `gate7-identity` let an isolated `--tags gate4` run — the role's own documented way to re-verify one gate — skip identification entirely while still making live reads. Reproduced, then fixed and reverified (`docs/evidence/gates/gate-07/c2-cluster-identity.txt`, sub-test 2).
- *`(_g4_nodes.stdout | from_json)['items']`, subscript not dot notation*: `.items` on the parsed dict resolves to Python's own `dict.items` bound method before Jinja ever tries the JSON key of the same name — found live while building this gate (a real `TypeError`, not theoretical), fixed everywhere it appeared.
- *`KUBECONFIG` set explicitly for `cilium status`*: the `cilium` CLI otherwise defaults to `localhost:8080`, which nothing on these nodes serves — found live (`connection refused`), matching the same pattern `roles/cilium`'s own install/upgrade tasks already use.
- *Quotes stripped from the `cilium-config` grep pipeline*: the ConfigMap's YAML values are quoted strings (`enable-wireguard: "true"`), so the existing pattern in `roles/cilium/tasks/main.yml` (which only ever `debug`-prints this value, never asserts on it) needed `tr -d ' "'` added, not just `tr -d ' '`, before this role's assert could match it.
- *kube-vip lease read by exact name (`plndr-cp-lock`), not every lease in `kube-system`*: that namespace also holds per-apiserver identity leases and k3s's/cilium-operator's own leader-election locks; reading all of them at once produced a multi-holder false failure on the very first live run.
- *Numeric var overrides cast with `| int`*: found in this gate's own negative testing — a bare `-e key=value` extra-var is not auto-typed the way a JSON-form `-e '{"key": 0}'` is, so an integer comparison against an un-cast var threw a Python type error instead of the intended assertion message on two checks (audit freshness, CoreDNS replica count). Cast explicitly on both sides everywhere a plain numeric var is compared.
- *etcd voter count derived from `groups['k3s_servers'] | length`, not hardcoded `3`*: found in independent review (LOW) — `roles/k3s-server`'s own equivalent assert (Gate 4, already closed) does hardcode it, but this read-only re-assertion has no reason to inherit that fragility.

**Resource tables** — new role `verify-cluster` (2 files, ~40 read+assert task pairs across the four gates); one new `group_vars/all.yml` constant.

## 6. EXIT GATE

| ID | Acceptance item (plan) | Method | Evidence | Result |
|---|---|---|---|---|
| G07-EG1 | Healthy pass | Full `ansible-playbook verify-cluster.yml` run, all 5 hosts, no tags/limits | `c1-healthy-pass.txt` | **PASS** — exit 0; `ok=39/18/18/13/13`, `changed=0`, `failed=0` on every host |
| G07-EG2 | Identifies the cluster; fails closed against the wrong cluster | `-e verify_cluster_expected_kube_system_uid=<wrong>`, full run; same override with `--tags gate4` (isolated-tag regression check for the HIGH finding above) | `c2-cluster-identity.txt` | **PASS** — both sub-tests exit 2, failing at the identity assert with a specific diagnostic naming the observed vs. expected UID, before any other check runs |
| G07-EG3 | Break one disposable assertion at a time; confirm non-zero exit and a useful diagnostic, for each critical category | 9 targeted `-e` overrides / temporary reverted edits, one per category, across Gate 3 (modules, sysctls, firewall, systemd), Gate 4 (cert SAN, audit freshness), Gate 5 (kube-vip lease) and Gate 6 (Cilium config, CoreDNS replicas) | `c3-negative-tests.txt` | **PASS** — every sub-test exits 2 with a diagnostic naming the specific host, item and expected-vs-actual value; the two temporary edits (systemd unit list, lease name) were reverted immediately after and confirmed byte-identical (`revert.txt`, included in the same evidence file) |
| G07-EG4 | Healthy rerun | Full run immediately after the negative-test sequence and the file revert | `c4-healthy-rerun.txt` | **PASS** — exit 0; `changed=0`, `failed=0` on every host, identical shape to G07-EG1 |

**Stop condition (verbatim):** "Empty task list, ignored failure, mutation during verification, or success against the wrong cluster."

**Triggered: no.**
- *Empty task list:* the role has ~40 read+assert task pairs; the playbook no longer reads `tasks: []`.
- *Ignored failure:* no `ignore_errors` appears anywhere in the role (confirmed by direct search and by independent review); the one `failed_when: false` (systemd unit reads) is immediately followed by a compensating `assert` over the same registered results — confirmed by G07-EG3's systemd sub-test, which fails correctly.
- *Mutation during verification:* confirmed three ways — `changed=0` on every host on every run (G07-EG1, G07-EG4, and every sub-test of G07-EG2/EG3); a direct search of the role for any create/apply/delete/patch/template/copy/systemd-enable/apt task found none; independent review reached the same conclusion.
- *Success against the wrong cluster:* the opposite is proven — G07-EG2 shows a wrong cluster identity fails closed, including under the isolated `--tags gate4` invocation that was found, during this gate's own hardening loop, to have originally bypassed it.

## 7. ROLLBACK

### 7.1 Reversal procedure

Git revert of `5220971` and `a4d5223` restores `ansible/playbooks/verify-cluster.yml` to its prior empty-task stub and removes `ansible/roles/verify-cluster/` and the `verify_cluster_expected_kube_system_uid` constant. Nothing on the live cluster changes on revert — this gate never wrote to cluster or host state in the first place (that is its own stop condition), so there is no data-loss surface and nothing IRREVERSIBLE.

### 7.2 Adversarial hardening loop

One iteration (cap 11), combining organic bugs found while first getting the role to run live and one independent-review pass.

| Iteration | Source | Findings | Fix commits |
|---|---|---|---|
| 1 | (a) Live testing while first bringing the role up; (b) independent review (Tier 1, separate context, given the diff and Gate 7 plan text) | (a) 5 real bugs found running live: `host_prereq_*`/`firewall_*`/etc. vars undefined (roles' `defaults/main.yml` not in scope without `include_vars`); `(...).items` resolving to Python's dict method instead of the JSON key; `cilium status` failing with `connection refused` (missing `KUBECONFIG`); the `cilium-config` assert never matching (YAML values quoted, grep pipeline didn't strip quotes); the kube-vip lease read returning every lease in `kube-system`, not just `plndr-cp-lock`; a deprecated `ansible_date_time` top-level fact reference. (b) 4 findings: HIGH — cluster-identity check skippable via `--tags gateN`, reproducing the gate's own "wrong cluster" stop condition through documented use; MEDIUM — claimed missing `set -o pipefail` on the cilium-config read (false positive on direct inspection: already present); LOW — etcd voter count hardcoded instead of derived from inventory; LOW — pod-network firewall check validates only index `[0]` of `firewall_trusted_pod_networks` (mirrors `roles/firewall`'s own existing, already-closed Gate 6 assert exactly — accepted, not a regression, out of this gate's scope to redesign) | `5220971` (implementation plus every organic fix); `a4d5223` (the HIGH and one LOW finding from independent review; the MEDIUM was not acted on, being false; the other LOW was evaluated and accepted as a pre-existing upstream pattern) |

**Attacks attempted:** 11 deliberate negative tests (one full-cluster wrong-identity run, one isolated-tag wrong-identity regression check, and 9 per-category checks spanning Gates 3-6) via `-e` variable overrides and two temporary, immediately-reverted file edits (kube-vip lease name, systemd unit list — the two checks with no variable to override). Every one produced a non-zero exit and a diagnostic naming the specific host, item, and expected-vs-actual value. The isolated-tag regression check specifically re-attacked the HIGH finding after its fix, confirming the same bypass no longer succeeds.

**Tracked exceptions:** the one LOW finding not acted on (firewall index-`[0]` check) — a pre-existing pattern in `roles/firewall` (Gate 6, already closed), not a defect this gate introduced; redesigning it is out of Gate 7's scope, which verifies each role's own intended values rather than inventing stricter ones.

### 7.3 IIR attestation

- **Immutable:** every fix is committed on `feat/gate-07-verification-automation` (`5220971`, `a4d5223`).
- **Idempotent:** `changed=0` on every host, both immediately before and immediately after the full 11-test negative sequence (`c1-healthy-pass.txt`, `c4-healthy-rerun.txt`) — expected by construction, since every task in the role is a read (`changed_when: false`) and none can report `changed: true`.
- **Repeatable:** every expected value the role checks is derived from the same role defaults and `group_vars/all.yml` that `host-prereqs`, `firewall`, `k3s-server`, `cilium` and `coredns` themselves already use to converge a node — not a second, independently-typed copy. Reproducibility from an actual from-scratch node/cluster rebuild is not proven here (the same disclosed gap carried at every gate since Gate 1).

## 8. KNOWN LIMITATIONS

- **The plan is uncommitted in this working tree.** `docs/Engineering Documents/Initial Stages Plan.txt` was already modified (a Gates 32-35 amendment, unrelated to Gate 7) when this session started. This skill's own rule requires `close`/`reopen` to run against a committed, unmodified plan (`PLAN_UNTRACKED` otherwise) — a closure cannot cite a plan revision nobody else can retrieve. Gate 7's own text (lines 176-197) is byte-identical between the committed blob (`4ebc8de`) and the working copy, so nothing about Gate 7's requirements is in question — but this record's `plan_commit`/`plan_sha256` fields are necessarily taken from the working copy and marked as such, and **the ledger row cannot be appended until the plan is committed (or the amendment is reverted/stashed) and a `close` re-run confirms `git status --porcelain` is empty for that path.** This is the single blocker to a final PASS verdict; every technical check above already is one.
- Gate 4's encrypted-at-rest and audit-event checks are read-only proxies (existing-data encryption-prefix presence; audit-log freshness), not a fresh create-and-verify marker test — weaker than Gate 4's own closure evidence, and disclosed per-check in the role's own task comments.
- Gate 5's kube-vip check is a non-destructive consistency check (single lease holder, VIP reachable), not a replay of the hard power-off drill — that remains reserved for a human-approved destructive runbook.
- Gate 6's CoreDNS check is a structural/scheduling proxy (replica count, Service ClusterIP, node spread), not a live disposable-pod resolution test.
- Negative testing (G07-EG3) covered 9 of the role's ~17 individual assertions — a representative cross-gate sample, not every one individually. Every check shares the same `ansible.builtin.assert` failure mechanism, so this is disclosed as sufficient rather than claimed as exhaustive.
- Verifier independence is Tier 1 only, for a gate CLAUDE.md §12 classifies high-risk (etcd/secrets-adjacent reads) — no Tier 2/external grader obtained, continuing the pattern already accepted at Gates 0-6.
- This session's execution path (a WSL Ubuntu Python venv, `ansible-playbook` invoked against `/mnt/c/...`) could not get Ansible to load the repo's own `ansible/ansible.cfg` (flagged "world writable directory" — a WSL/drvfs permission-model artifact of the Windows-drive mount, not a repository defect). SSH host-key verification during this session's live commands therefore relied on the operator's own `~/.ssh/known_hosts` in WSL rather than the repo-pinned `UserKnownHostsFile` (`ansible/files/known_hosts`) the committed `ansible.cfg` specifies — confirmed to hold matching keys for the same five hosts (different on-disk format: hashed vs. plain), so nothing this session did was unverified, but the repo-pinned file itself was not the thing consulted. Flagged for the operator's awareness; this is Gate 1's territory (already closed) and out of scope to fix here.
- No CI wiring to run this playbook automatically was built (not requested).
