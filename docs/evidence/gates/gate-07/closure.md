# GATE 7 — Verification automation

| | |
|---|---|
| **Verdict** | **PASS** |
| **Closed (UTC)** | 2026-09-14T21:08:37Z |
| **Plan** | `docs/Engineering Documents/Initial Stages Plan.txt` @ `64d80e624252a71345d1c6bdc179297b085e73e9`, sha256 `a32ea3fbfc2c69aeb06346ad7d251e9df14e54c5302259b739be5df871665a0c` (blob in Git) |
| **Tested repo commit** | `64d80e624252a71345d1c6bdc179297b085e73e9` (branch `feat/gate-07-verification-automation`; role code unchanged since `a4d5223`) |
| **Target identity** | `kube-system` namespace UID `d7d8a462-c503-49ed-a1e0-899f372f9465`; API server `https://10.2.0.100:6443` (private VIP); hosts `veridex-server-1/2/3`, `veridex-agent-1/2` |
| **High-risk** | Yes — reads etcd data and secrets/audit-log configuration (CLAUDE.md §12 triggers: etcd, auth/secrets), though strictly read-only, with no mutation of any kind |
| **Verifier independence** | Tier 1 — one independent adversarial review (separate context, given only the diff and the Gate 7 plan text). Found 4 issues; the one high and one low were real and fixed, one medium was a false positive on direct inspection, one low was accepted as a pre-existing upstream pattern outside this gate's scope. No Tier 2 review obtained; continuing the pattern accepted at Gates 0-6. |

**Plan revision note.** Gates 0-6 closed against plan blob `4ebc8de`. This gate closes against `64d80e6`, which adds the Gates 32-35 amendment (Part D) and renumbers the hardening backlog to Part E. Gate 7's own text (End state, Acceptance evidence, Stop condition) is byte-identical between the two blobs, verified by direct comparison before closing, and the amendment changes no decision recorded for Gates 0-31 — so earlier rows in the ledger remain valid against it.

## 1. OBJECTIVE

> verify‑cluster.yml implements gates 3 through 6 as read‑only assertions, identifies the cluster, fails closed, and has a deliberate negative test for each critical category.

## 2. SCOPE

**In scope**
- New role `ansible/roles/verify-cluster/` (defaults + tasks) re-asserting, read-only, the intended state Gates 3-6 already built: host prereqs/firewall (kernel modules, sysctls, systemd units, nftables ruleset), k3s control plane (node identity and readiness, etcd voter count, per-node certificate SAN, secrets-encryption configuration, encryption-provider prefix in raw etcd, audit-log freshness), kube-vip (single lease holder, API reachable through the VIP), Cilium/CoreDNS (cilium status, cilium-config settings, CoreDNS replica count, Service ClusterIP, node spread).
- `ansible/playbooks/verify-cluster.yml` rewritten from an empty `tasks: []` stub to invoke the role across every inventory host, with `any_errors_fatal: true`.
- New constant `verify_cluster_expected_kube_system_uid` (`group_vars/all.yml`), captured live at Gate 4's closure, so the playbook positively identifies the cluster before doing anything else.
- Deliberate negative testing across a representative sample of critical categories spanning all four verified gates, confirming fail-closed behavior (non-zero exit) and a specific, useful diagnostic for each.

**Out of scope**
- Gate 4's live "create a marker Secret, grep for it, delete it" and "trigger a request, find the matching audit event" proofs are **not** repeated — both mutate the cluster, which is this gate's own stop condition. Read-only proxies substitute (encryption-provider prefix over existing data; audit-log freshness) → §8.
- Gate 5's hard power-off drill is **not** repeated — destructive, and the plan's Workflow ownership table assigns it to a human-approved destructive runbook, not a routine verification playbook. A non-destructive single-holder/VIP-health consistency check substitutes.
- Gate 6's live disposable-pod cross-node ping and DNS resolution test is **not** repeated — creating a pod is a mutation. CoreDNS scheduling and Service structural proxies substitute.
- Exhaustive negative testing of every one of the role's ~17 individual assertions — 9 representative categories across all four gates were tested instead (§8).
- Gates 32-35 (the plan amendment committed at `64d80e6` to make this closure citable) — unrelated to Gate 7; no work was done against them.
- CI wiring to run this playbook automatically after a change in Gates 3-6's territory — not requested.

## 3. PROCESSES ACTIVATED

No continuously-enforced process. `verify-cluster.yml` is an on-demand diagnostic (`make verify-cluster ENV=production`, or a direct `ansible-playbook` invocation) — it enforces nothing by itself and runs on no schedule.

| Process | Owner (Workflow ownership table) | Detection if it silently stops |
|---|---|---|
| Read-only verification of Gates 3-6's invariants, available on demand to any operator or future CI gate | Ansible ("read-only verification", explicitly named in the Ansible row) | Not applicable — nothing depends on this running, and it enforces nothing. Its own failure mode is the opposite one: silently passing when it should fail, which is what G07-EG2 and G07-EG3 exist to disprove, and what the `--tags` gap found in the hardening loop would have caused. |

## 4. DELIVERABLES

| ID | Artifact | Commit |
|---|---|---|
| D34 | `ansible/roles/verify-cluster/defaults/main.yml`, `ansible/roles/verify-cluster/tasks/main.yml` — the read-only assertion role | `5220971`, `a4d5223` |
| D35 | `ansible/playbooks/verify-cluster.yml` — rewritten to invoke the role (`hosts: all`, `gather_facts: true`, `any_errors_fatal: true`) | `5220971` |
| D36 | `ansible/inventory/production/group_vars/all.yml` — `verify_cluster_expected_kube_system_uid` | `5220971` |
| D37 | `docs/evidence/gates/gate-07/` — this record and its four evidence files | (evidence commit follows) |

## 5. TECHNICAL DETAIL

**Decision rationale**
- *`include_vars` over the five verified roles' own `defaults/main.yml`, not a second copy of their values*: verify-cluster holds no expected values of its own that could drift from what `host-prereqs`, `firewall`, `k3s-server`, `cilium` and `coredns` actually converge to. Verified directly (and independently re-checked in review) that none of those five files redefines a variable `group_vars/all.yml` also sets to a different, more specific value — `include_vars` outranks group_vars in Ansible's precedence and would silently clobber such a case if one existed.
- *Cluster identity runs first and is tagged `always`*: found during this gate's hardening loop (independent review, HIGH) that tagging it `gate7-identity` let an isolated `--tags gate4` run — the role's own documented way to re-verify one gate — skip identification while still making live reads and asserts. Reproduced live, fixed, and re-attacked to confirm (`c2-cluster-identity.txt`, sub-test 2).
- *`(_g4_nodes.stdout | from_json)['items']`, subscript not dot notation*: `.items` on the parsed dict resolves to Python's own `dict.items` bound method before Jinja tries the JSON key of the same name — a real `TypeError` hit while building, not a theoretical risk.
- *`KUBECONFIG` set explicitly for the `cilium` CLI*: it otherwise defaults to `localhost:8080`, which nothing on these nodes serves (`connection refused`, observed live). Matches the pattern `roles/cilium`'s own install/upgrade tasks already use.
- *Quotes stripped in the `cilium-config` pipeline*: the ConfigMap's values are quoted strings (`enable-wireguard: "true"`), so `tr -d ' "'` is required before an assert can match. The equivalent read in `roles/cilium` only ever `debug`-prints this value and never asserts on it, so the quoting never mattered there.
- *kube-vip lease read by exact name (`plndr-cp-lock`)*: `kube-system` also holds per-apiserver identity leases and k3s's and cilium-operator's own leader-election locks; reading every lease in the namespace produced a multi-holder false failure on the first live run.
- *Numeric variables cast with `| int` on both sides of every comparison*: found by this gate's own negative testing — a bare `-e key=value` extra-var is not auto-typed the way the JSON form `-e '{"key": 0}'` is, so an un-cast comparison threw a Python type error instead of the intended assertion message on two checks.
- *etcd voter count derived from `groups['k3s_servers'] | length`, not a literal `3`*: independent review (LOW). `roles/k3s-server`'s own equivalent assert does hardcode it, but a read-only re-assertion has no reason to inherit that fragility.

**Resource tables** — new role `verify-cluster` (2 files; ~40 read/assert task pairs across the four gates, tagged `gate3`/`gate4`/`gate5`/`gate6` for isolated re-verification, with prerequisites and identity tagged `always`); one new `group_vars/all.yml` constant. No manifests, no Terraform, no IAM policy.

## 6. EXIT GATE

| ID | Acceptance item (plan) | Method | Evidence | Result |
|---|---|---|---|---|
| EG38 | Healthy pass | Full `ansible-playbook verify-cluster.yml` run, all 5 hosts, no tags or limits | `c1-healthy-pass.txt` | **PASS** — exit 0; `ok=39/18/18/13/13`, `changed=0`, `failed=0` on every host |
| EG39 | Identifies the cluster; fails closed against the wrong cluster | `-e verify_cluster_expected_kube_system_uid=<wrong>` on a full run; the same override with `--tags gate4` (isolated-tag regression check for the HIGH hardening finding) | `c2-cluster-identity.txt` | **PASS** — both sub-tests exit 2, failing at the identity assert with a diagnostic naming observed vs. expected UID, before any other check runs |
| EG40 | Break one disposable assertion at a time; confirm non-zero exit and useful diagnostic, for each critical category | 9 targeted `-e` overrides / temporary reverted edits, one per category: Gate 3 (modules, sysctls, firewall, systemd), Gate 4 (certificate SAN, audit freshness), Gate 5 (kube-vip lease), Gate 6 (Cilium config, CoreDNS replicas) | `c3-negative-tests.txt` | **PASS** — every sub-test exits 2 with a diagnostic naming the specific host, item and expected-vs-actual value; the two temporary edits were reverted and confirmed identical (revert confirmation included in the same file; `git status` clean afterwards) |
| EG41 | Healthy rerun | Full run immediately after the negative-test sequence and the revert | `c4-healthy-rerun.txt` | **PASS** — exit 0; `changed=0`, `failed=0` on every host, identical shape to EG38 |

**Stop condition (verbatim):** "Empty task list, ignored failure, mutation during verification, or success against the wrong cluster."

**Triggered: no.**
- *Empty task list:* the role has ~40 read/assert task pairs covering all four gates; the playbook no longer reads `tasks: []`.
- *Ignored failure:* no `ignore_errors` appears anywhere in the role (confirmed by direct search and by independent review). The single `failed_when: false` (the `systemctl is-active` reads, which return non-zero for an inactive unit by design) is immediately followed by a compensating `assert` over the same registered results — proven by EG40's systemd sub-test, which fails correctly on an inactive unit.
- *Mutation during verification:* confirmed three ways — `changed=0` on every host on every run (EG38, EG41, and all 11 negative sub-tests); a direct search of the role for any create/apply/delete/patch/template/copy/systemd-enable/apt task returns nothing; independent review reached the same conclusion on the diff.
- *Success against the wrong cluster:* the opposite is proven — EG39 shows a wrong cluster identity fails closed, including under the isolated `--tags` invocation that originally bypassed it.

## 7. ROLLBACK

### 7.1 Reversal procedure

Git revert of `5220971` and `a4d5223` (in reverse order) restores `ansible/playbooks/verify-cluster.yml` to its prior empty-task stub and removes `ansible/roles/verify-cluster/` and the `verify_cluster_expected_kube_system_uid` constant. Nothing on the live cluster changes on revert, because this gate never wrote to cluster or host state in the first place — that is its own stop condition, and EG38/EG41 evidence it. No data-loss surface; no step is IRREVERSIBLE. Reverting only loses the ability to re-verify Gates 3-6 cheaply; it invalidates nothing those gates already proved.

The separate plan commit `64d80e6` (Gates 32-35 amendment) is not part of this gate's deliverables and is not covered by this rollback.

### 7.2 Adversarial hardening loop

One iteration (cap 11), combining bugs found while first getting the role to run live with one independent-review pass.

| Iteration | Source | Findings | Fix commits |
|---|---|---|---|
| 1 | (a) Live testing while bringing the role up; (b) independent review (Tier 1, separate context, given only the diff and the Gate 7 plan text) | **(a) 6 real bugs, all found by running it:** role-default variables (`host_prereq_*`, `firewall_*`, `k3s_*`, `cilium_*`, `coredns_*`) undefined, because a role's `defaults/` is not in scope unless that role runs — fixed with `include_vars`, which also removed the temptation to duplicate the values; `(... | from_json).items` resolving to Python's `dict.items` method instead of the JSON key; `cilium status` failing `connection refused` for want of `KUBECONFIG`; the `cilium-config` assert never matching because the ConfigMap's values are quoted; the kube-vip lease read returning every lease in `kube-system` rather than `plndr-cp-lock`; a deprecated top-level `ansible_date_time` reference. **(b) 4 findings:** HIGH — the cluster-identity check was skippable via `--tags gateN`, reproducing this gate's own "wrong cluster" stop condition through documented use; MEDIUM — claimed missing `set -o pipefail` on the cilium-config read (**false positive**: verified present on direct inspection, not acted on); LOW — etcd voter count hardcoded rather than derived from inventory; LOW — the pod-network firewall check validates only index `[0]` of `firewall_trusted_pod_networks` (**accepted**: mirrors `roles/firewall`'s own assert exactly, a Gate 6 artifact, not a regression this gate introduced and out of scope to redesign) | `5220971` (implementation and all six organic fixes); `a4d5223` (the HIGH and the actionable LOW) |

**Attacks attempted.** 11 deliberate negative tests — one full-cluster wrong-identity run, one isolated-tag wrong-identity regression check, and 9 per-category breaks spanning Gates 3-6 — applied via `-e` variable overrides and, for the two checks with no variable to override, temporary edits reverted immediately afterwards. Every one produced a non-zero exit and a diagnostic naming the specific host, item and expected-vs-actual value; none passed silently. The isolated-tag test specifically re-attacked the HIGH finding after its fix and confirmed the bypass no longer works. Two further attacks were attempted and found nothing: a direct search for any mutating module or `ignore_errors` in the role, and a variable-precedence audit checking whether any `include_vars`-loaded role default silently clobbers a more specific `group_vars/all.yml` value.

One negative test initially produced a false PASS and is worth recording: forcing the audit-freshness check to fail by setting its window to `0` did not fail, because the audit log's mtime can legitimately run a fraction of a second *ahead* of the epoch captured at fact-gathering time, making the elapsed interval negative and therefore still "under" the window. The test method was wrong, not the check — re-run with a `-3600` window, it failed correctly. The production default (300s) is unaffected either way, and a negative interval is the correct answer for a log being written right now.

**Tracked exceptions:** the one LOW finding not acted on (firewall index-`[0]` check), a pre-existing pattern in `roles/firewall` from Gate 6, already closed. Not a defect this gate introduced.

### 7.3 IIR attestation

- **Immutable:** every fix is committed on `feat/gate-07-verification-automation` (`5220971`, `a4d5223`); no uncommitted change remains in the working tree (`git status` clean after the reverted negative-test edits).
- **Idempotent:** `changed=0` on every host, both immediately before and immediately after the full 11-test negative sequence (`c1-healthy-pass.txt`, `c4-healthy-rerun.txt`), with no restart of k3s, Cilium, CoreDNS, kube-vip or any storage service. This is structural rather than incidental: every task in the role is a read carrying `changed_when: false`, so none can report `changed` at all.
- **Repeatable:** every expected value the role checks is read at runtime from the same role defaults and `group_vars/all.yml` that the verified roles themselves converge against — not a second, independently-maintained copy — so the role stays correct as those values change. Reproducibility from an actual from-scratch node or cluster rebuild is not proven here (the same gap disclosed at every gate since Gate 1).

## 8. KNOWN LIMITATIONS

- Gate 4's encrypted-at-rest and audit-event checks are read-only proxies here — the encryption-provider prefix over data that already exists, and audit-log freshness — not a fresh create-and-verify marker test or a triggered-and-matched audit event. Both are weaker than Gate 4's own closure evidence, deliberately: performing those would mutate the cluster and trip this gate's stop condition. In particular, the freshness check would not detect an audit pipeline that is still writing but has silently stopped recording a *particular class* of event.
- Gate 5's kube-vip check is a single-holder/VIP-reachability consistency check, not a replay of the hard power-off drill. It would not detect a failover path that is broken in a way only an actual node loss reveals.
- Gate 6's CoreDNS check is structural (replica count, Service ClusterIP, distinct-node spread), not a live resolution test. A CoreDNS that is scheduled correctly but answering wrongly would pass this check — Gate 6's own closure evidence covers that, this does not re-prove it.
- Negative testing (EG40) covered 9 of the role's ~17 individual assertions — at least one per critical category per gate, not every assertion individually. Disclosed as a representative sample rather than claimed as exhaustive; it is valid to the extent that every check shares one `assert` primitive and one fail-closed mechanism.
- The role's correctness depends on `verify_cluster_expected_kube_system_uid` being the right value. EG39 proves a wrong *supplied* identity is rejected; nothing here independently re-derives that the pinned UID is the intended cluster's — that value came from Gate 4's live closure and is carried in `group_vars/all.yml`. If the cluster is ever rebuilt from scratch, that constant must be updated or every run fails closed (the safe direction).
- Verifier independence is Tier 1 only, for a gate CLAUDE.md §12 classifies high-risk (etcd/secrets-adjacent reads) — no Tier 2 or external grader obtained, continuing the pattern accepted at Gates 0-6.
- This session's execution path (a WSL Ubuntu Python venv running `ansible-playbook` against `/mnt/c/...`) could not get Ansible to load the repository's own `ansible/ansible.cfg` — it is flagged "world writable directory", an artifact of the Windows-drive mount's permission model, not a repository defect. SSH host-key verification therefore relied on the operator's `~/.ssh/known_hosts` inside WSL rather than the repo-pinned `UserKnownHostsFile` (`ansible/files/known_hosts`) that the committed `ansible.cfg` specifies. Both hold keys for the same five hosts (different on-disk format: hashed vs. plain), so no connection this session made was unverified — but the repo-pinned file was not the thing consulted, and any operator running from this path inherits the same gap. Flagged for awareness; host-key policy is Gate 1's territory, already closed, and fixing it is out of this gate's scope.
- No CI wiring was built to run this playbook automatically after a change in Gates 3-6's territory (not requested). Until that exists, the role only runs when someone chooses to run it.
- The plan amendment committed at `64d80e6` introduces cross-references that create new ordering questions for Gates 11-15 and 29 (Gate 32 must resolve namespace names before the Wave 1 rollout at Gate 11; Gate 34 rides along from Wave 1; Gate 35 must be decided by Gate 15; Gate 29's step 12 is Gate 35's exit check). These are forward references from lower-numbered gates to higher-numbered ones — the same shape as the entries already listed under the ledger's *Open ordering conflicts* — and none of them involve Gate 7. They are **not** enumerated in the ledger yet; that enumeration is owed before Gate 11 closes, not before this one.
