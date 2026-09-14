# GATE 0 — Repository and provider boundary

| | |
|---|---|
| **Verdict** | **PASS** |
| **Closed (UTC)** | 2026-09-14T00:57:35Z |
| **Plan** | `docs/Engineering Documents/Initial Stages Plan.txt` @ `4ebc8def34df78a0bc6b29e42656986ef987f4c9`, sha256 `42eaac5e61d177430ce8e331767d2137b3f9b2bd197e13945b84f7c5e8cd79c7` (blob in Git) |
| **Tested repo commit** | `82a1dd4bb406aadd6091e6ec756c41ac7426add4` (branch `feat/gate-00-provider-boundary`) |
| **Target identity** | repository `https://github.com/caribrefresh-source/Veridex-Platform.git` at commit `82a1dd4` (repository-only gate) |
| **High-risk** | No — repository tooling, CI and documentation only; no cluster, network, secret value or persistence change (CLAUDE.md §12) |
| **Verifier independence** | Tier 1 — three independent adversarial reviews, each by a separate-context agent given the diff and the gate text. No Tier 2 verifier. The last fix round (M1–M6, S1) was verified by the attack suites and CI only, without a further independent review, as decided by the repository owner on 2026-09-14. |

## 1. Objective

> Inventory identifies only the five netcup nodes. Automated scanning finds no active Hetzner endpoints, variables, backend configuration, buckets, DNS, credentials, documentation instructions, or workflow dependencies. Historical references are explicitly labelled historical.

## 2. Scope

**In scope**
- Automated scanning of every Git-tracked file for Hetzner values, Hetzner software dependencies and old-cluster identity (provider-drift lint).
- A secret register recording where every consumed secret is held, and a names-only scan that enforces it.
- Inventory schema and identity validation: exactly five netcup nodes, identity defined in one place.
- CI jobs running those checks on every push to `main`, every pull request and on dispatch.
- Retargeting imported agent/operator instructions away from the old cluster and Hetzner services.
- Historical labelling: `docs/evidence/legacy/` (pre-Revision-3 records, labelled in PR #3) and `docs/evidence/gates/` (captured closure evidence).

**Out of scope**
- `entrepeai.com` and its Hetzner-hosted DNS: the separate company site, declared outside the Veridex netcup platform by the repository owner (2026-09-13).
- Operator workstation kubeconfigs that point at the old cluster, and a netcup kubeconfig → Gate 4 prerequisite.
- The public API DNS name `api.veridexeai.com` in the API certificate → Gate 4.
- Cross-checking inventory public addresses against the netcup API → Gate 1.
- The Argo CD repository token → Gate 10. Off-cluster etcd snapshot keys → Gate 9, specified in Gates 18 and 21.
- The secret mechanism question ("§6 conflict") → open item in the ledger, before Gates 13/24.
- Refusing an empty `K3S_TOKEN` in the k3s roles → Gate 4.
- Pinning GitHub Actions by commit SHA, hash-pinned requirements, CODEOWNERS, branch protection → operational hardening backlog (plan Part D).

## 3. Processes activated

| Process | Owner (Workflow ownership table) | Detection if it silently stops |
|---|---|---|
| Provider-drift lint on every push to `main`, pull request and dispatch | CI | No branch protection is available on this GitHub plan (API returned HTTP 403, 2026-09-13), so the job is not a required check and could be removed from `ci.yml` unnoticed. Detection: `/veridex-gate audit 0` re-runs the check; any change to `.github/workflows/ci.yml` shows in review. |
| Secret register enforcement: a newly consumed secret fails CI until its destination is registered | CI (enforcement); Operators (register content) | Same as above: `/veridex-gate audit 0`. |
| Inventory schema and identity validation | CI | Same as above. |
| Historical labelling only in `docs/evidence/legacy/` and `docs/evidence/gates/` | CI | A marker anywhere else fails the provider-drift job. |

## 4. Deliverables

| ID | Artifact | Commit |
|---|---|---|
| D1 | `schemas/inventory.schema.json` — five-node inventory schema | `db0fb7a` |
| D2 | `scripts/validate-inventory.py` — schema, identity and stray-inventory validation | `82a1dd4` |
| D3 | `scripts/lint-secret-register.py` — names-only secret scan | `ef388e4` |
| D4 | `docs/security/secret-register.yml` — register of 10 consumed secrets and their destinations | `3587b28` |
| D5 | `scripts/lint-provider-drift.py` — provider and old-cluster identity lint over every tracked file | `edcaa73` |
| D6 | `scripts/requirements-lint.txt` — pinned lint dependencies, including transitive ones | `42767a2` |
| D7 | `.github/workflows/ci.yml` — inventory-schema and secret-register jobs, pinned lint install, 10-minute job timeouts | `9bca388` |
| D8 | Retargeted instructions: 22 files under `.claude/commands/`, 3 skills, 2 script docstrings, the API SAN comment in `ansible/inventory/production/group_vars/all.yml` | `cc886bb`, `560802d` |

## 5. Technical detail

**Decision rationale**
- *Every tracked file, not only configuration.* The plan's end state names documentation instructions and workflow dependencies; an agent command that runs against the old inventory is a dependency.
- *Deferred register entries are not unresolved destinations.* A consumer that is disabled or not yet run, with the gate that creates the secret named, satisfies "resolved". Applies to the Argo CD repository credential (Gate 10) and the etcd snapshot keys (Gate 9).
- *`entrepeai.com` is out of scope* by the repository owner's decision (company site); only its subdomains used as platform endpoints are flagged.
- *Platform DNS is `veridexeai.com` at Squarespace*; no Hetzner DNS is used by the platform.
- *No Terraform* (repository owner, 2026-09-13).
- *Encrypted values are not literals:* SOPS values in a document with a `sops` block and Ansible Vault values pass, so the plan's Gate 21 path (keys encrypted through SOPS in Git) can pass CI.
- *Closure evidence is labelled historical* because the lint output it records quotes the tokens it found.

**Resource tables** — CI jobs added or changed: `inventory-schema`, `secret-register`, `provider-drift` (installs pinned requirements); all six jobs carry `timeout-minutes: 10`.

## 6. Exit gate

| ID | Acceptance item (plan) | Method | Evidence | Result |
|---|---|---|---|---|
| EG1 | Provider drift lint | `python3 scripts/lint-provider-drift.py` and `--strict` on `82a1dd4` | `c1-provider-drift-lint.txt`, `c1-provider-drift-lint-strict.txt` | **PASS** — 288 files, 0 errors, 0 warnings, 3 historical (all in `docs/evidence/legacy/`), 1 reasoned suppression |
| EG2 | Secret‑name scan without revealing values | `python3 scripts/lint-secret-register.py` on `82a1dd4` | `c2-secret-name-scan.txt` | **PASS** — 10 register entries (7 env, 2 file, 1 kubernetes-secret); every consumed secret registered; output names only |
| EG3 | Inventory/schema validation | `python3 scripts/validate-inventory.py` on `82a1dd4` | `c3-inventory-schema-validation.txt` | **PASS** — 5 hosts (3 k3s_servers, 2 k3s_agents), bootstrap server `veridex-server-1`, `ansible.cfg` inventory pinned, no other hosts |
| EG4 | Pipeline dry run | CI workflow run `34794269417` (workflow_dispatch) on `82a1dd4` | `c4-pipeline-dry-run.txt` | **PASS** — all 6 jobs succeeded; deploys nothing |

**Stop condition (verbatim):** "Any active Hetzner dependency, unresolved secret destination, or ambiguous cluster identity."

**Triggered: no.**
- *Active Hetzner dependency:* EG1 finds none in tracked files. `entrepeai.com`'s Hetzner DNS is out of scope by owner decision (§2).
- *Unresolved secret destination:* EG2 — every consumed secret has a destination; five entries are deferred with a named gate (§5).
- *Ambiguous cluster identity:* EG3 — identity is defined only in the production `hosts.yml`, no other inventory or `ansible.cfg` exists; EG1's identity rules find no reference to the old cluster, its hostnames or its repository.

## 7. Rollback

### 7.1 Reversal procedure

Nothing in the cluster, DNS or any secret store was changed; rollback is Git only. In reverse dependency order: revert the CI job changes (D7), then the scripts, schema and register (D1–D6), then the instruction retargeting (D8), or do not merge `feat/gate-00-provider-boundary`. Nothing is destroyed; every version stays in Git history. Reverting D7 removes enforcement (§3) and should be followed by `reopen 0`. No step is irreversible.

### 7.2 Adversarial hardening loop

Five iterations (cap 11). Every fix is a commit on the gate branch.

| Iteration | Source | Findings | Fix commits |
|---|---|---|---|
| 1 | Own attack suites | Env lookups through `query`/`q`/FQCN; bare `environ` and `pop`/`setdefault`; `kind: Secret` with a comment; Unicode look-alike hyphens | `22784a2`, `c188e3b`, `17f9ab9`, `930f01a` |
| 2 | Own attack suites | Regression from iteration 1 (lost escaping made the env patterns match nothing); multi-name and multi-line env reads; pipe lookups; raw characters in the dash table; zero-width characters. The suites were changed to assert the reason, not only the exit code. | `56139ca`, `1982b1a`, `f084271`, `075b1b8`, `65b36a4`, `0e1363a` |
| 3 | Independent review 1 | 13 findings (2 high: live Hetzner instructions in `.claude/`; literal secrets under Ansible variable names) plus marker placement and transitive pins; a whitespace-backtracking regression caught before commit | `cc886bb`, `c9f79e4`, `29deef8`, `4b73fed`, `42767a2`, `3587b28` |
| 4 | Independent review 2 | 15 findings, none high; owner-approved subset N3, N4, N5, N7, N9, N10, N11 (ansible.cfg), N12, N13, N14, N15. Measured: the hostname rule took 34.8 s on one 60,000-character line before, 0.003 s after. | `0d8d1d9`, `c992cbd`, `9cd0af1`, `9bca388` |
| 5 | Independent review 3 | 6 confirmed medium (M1–M6), 1 suspected medium (S1), 7 low (L1–L7); owner decision: fix M1–M6 and S1 without another review | `edcaa73`, `ef388e4`, `82a1dd4` |

Final attack suites on the tested code: 259 cases across nine suites (drift 49 + 24 + 19, secret scan 72 + 27 + 14, inventory 38 + 9 + 7), each asserting the reason and, for secrets, that no value is printed — all pass.

**Tracked exceptions** (accepted by the repository owner; open, not fixed):

| ID | Weakness | Where it would be addressed |
|---|---|---|
| N1 | Hardcoded secrets under names that are neither registered nor fed from an env lookup (e.g. an arbitrary `redis_password:`) | A pinned dedicated secret scanner, later |
| N2 | Literal values hidden in Jinja string literals or `default(...)` fallbacks, Makefile `?=`/`:=`, shell `${X:-literal}`, Python env assignment | Same |
| N6 | Env reads in extensionless shell scripts, PowerShell `$env:`, `ansible_env` facts, `community.sops` filters and `load_vars`, `ANSIBLE_PRIVATE_KEY_FILE` | Same |
| N8 | Escape sequences in `.json`/`.j2` files, and invalid YAML skipped by the drift lint's value scan | Drift lint follow-up |
| N11 | Node identity set through role vars, play vars, `set_fact`/`add_host` or SSH connection arguments | Inventory validator follow-up |
| L1 | At most 20 base64 runs checked per line | Secret scan follow-up |
| L2 | A doubly base64-encoded kubeconfig is not recognised | Secret scan follow-up |
| L3 | Some agent instruction files (lowercase `claude.md`, Copilot and Cursor rule files, `.gemini/` commands) lack the provider-name rule | Drift lint follow-up |
| L4 | YAML alias bombs slow the inventory validator (fails closed; CI timeout applies) | Inventory validator follow-up |
| L5 | A list-valued `status` in the register raises a traceback (fails closed) | Secret scan follow-up |
| L6 | A SOPS dotenv line (`NAME=ENC[...]`) is reported as a literal (false positive) | Secret scan follow-up |
| L7 | A literal value inside a `.j2` Secret template is not parsed (overlaps N1) | Same as N1 |

### 7.3 IIR attestation

- **Immutable:** every fix is committed on `feat/gate-00-provider-boundary` (26 commits, `db0fb7a`..`82a1dd4`); lint dependencies are pinned including transitive ones. GitHub Actions are pinned by tag, not commit SHA (§2, out of scope).
- **Idempotent:** every check is read-only; a second run of all four lint commands produced identical output and exit codes — `iir-rerun.txt`.
- **Repeatable:** the same checks ran on a clean GitHub-hosted runner from the tested commit and reached the same results — `c4-pipeline-dry-run.txt`. No manual step is needed. The adversarial suites are not committed to the repository (§8).

## 8. Known limitations

- The checks are pattern-based. They prove the absence of the Hetzner dependencies and secret forms they recognise, not of every possible spelling; the tracked exceptions in §7.2 are known gaps.
- The final fix round (M1–M6, S1) had no independent review; it rests on the attack suites and CI.
- The CI jobs are not required status checks (no branch protection on this plan), so enforcement depends on reviewers noticing a failing or removed job.
- The pipeline evidence (EG4) is a `workflow_dispatch` run on the gate branch; the run on `main` after merge is not yet recorded.
- The 259 adversarial test cases live outside the repository and cannot be re-run by others from Git.
- A register destination is text: the scan proves every secret has a recorded destination, not that the destination physically holds the value.
- Outside the repository, and not proven here: the operator workstation's kubeconfigs point at the old cluster, and `entrepeai.com` DNS is hosted by Hetzner (company site, out of scope).
- An untracked `archieve-workflow/` folder exists in the operator's working copy; untracked files are not scanned, and it would be scanned if committed.
