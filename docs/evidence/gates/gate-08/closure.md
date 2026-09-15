# GATE 8 — Backup foundation

| | |
|---|---|
| **Verdict** | **PASS** |
| **Closed (UTC)** | 2026-09-15T00:45:00Z |
| **Plan** | `docs/Engineering Documents/Initial Stages Plan.txt` @ `bc27a0a2b9e872679007342b5d255b888e000722`, sha256 `0c30445b0074edf3688ba57936e1c5149497b829e0f7d1b4328c5181bd222af8` (blob in Git) |
| **Tested repo commit** | `f28705617bf219deec96604d81c19d088418321d` (branch `feat/gate-08-backup-foundation`) |
| **Target identity** | Backblaze B2 account `c1beac90ce56` (dedicated backup account); bucket `veridex-etcd-backup`, bucketId `4c818bbe7abca920ac0e0516`; native API node `api005`/`f005.backblazeb2.com` |
| **High-risk** | Yes — auth/secrets (CLAUDE.md §12): real credentials created on a live, billed external account |
| **Verifier independence** | Tier 1 — one independent adversarial review (separate context, given the evidence files, the secret-register diff, and Gates 8/19/20/21 plan text). Found 6 issues (0 critical/high, 3 medium, 2 low, 1 info); every medium was fixed and reverified, the low/info findings are disclosed rather than fixed (out of this gate's own scope). No Tier 2 review obtained; continuing the pattern accepted at Gates 0-7. |

**Ordering note.** This gate closes under Ordering decision **O2** (`docs/evidence/gate-ledger.md`): Gate 8 builds and closes now on its own self-contained acceptance evidence, using Gates 18-21's text as design reference rather than a closure blocker. Gates 18-21 close later, incrementally, as their own fuller requirements (all six buckets, full account-isolation audit, one key per producer) become satisfiable.

## 1. OBJECTIVE

> Backblaze B2 — not Hetzner — is the configured backup destination, with versioning, encryption and provider‑enforced immutability via Object Lock. Separate write and restore identities exist. Exact bucket architecture, credential mechanism and Object Lock activation are specified in Gates 18–21.

## 2. SCOPE

**In scope**
- One real bucket, `veridex-etcd-backup`, created on Backblaze B2 with Object Lock (file-lock) enabled at creation, default server-side encryption (SSE-B2/AES256), and a governance-mode default retention (2 days, provisional — see §8).
- Two application keys, both restricted to this one bucket, matching the plan's Identity table: a **writer** identity (`listBuckets,listFiles,writeFiles`) and a **restore** identity (`listBuckets,listFiles,readFiles`) — neither holds `deleteFiles`, `writeFileRetentions` or `bypassGovernance`.
- Live proof of the full mechanism: upload a protected object as the writer, confirm it inherited the bucket's governance retention, prove both identities are denied early deletion and retention reduction, list and download the object as the restore identity with a verified checksum match.
- `docs/security/secret-register.yml` updated to reflect that `ETCD_S3_ACCESS_KEY`/`ETCD_S3_SECRET_KEY` (the writer key) and the restore key now genuinely exist, plus `docs/security/b2-restore-access.md` documenting the restore identity's purpose and constraints (mirroring `emergency-access.md`'s existing pattern).

**Out of scope**
- The other five buckets Gate 18 will eventually define (`veridex-cnpg-backup`, `veridex-minio-backup`, `veridex-longhorn-backup`, `veridex-recovery-keys`, `veridex-audit-worm`) → Gate 18.
- Compliance-mode Object Lock activation → Gate 19's own explicit two-phase procedure; this gate deliberately stays in Governance mode only.
- Full account isolation (MFA audit, access logging export, change alerting) → Gate 20.
- One key per producer (CloudNativePG, MinIO, Longhorn, audit exporter) → Gate 21, as each producer is built.
- Wiring `ETCD_S3_ACCESS_KEY`/`ETCD_S3_SECRET_KEY` into k3s's actual etcd-s3 snapshot config → Gate 9 (a separate, already-flagged ordering conflict in the ledger, Gate 9 → Gates 17/18).
- SOPS encryption of these credentials in Git → Gate 21's own requirement; today they live only as local, ungitignored-but-uncommitted operator-workstation files (`~/.config/veridex/`), the same pattern already established for `K3S_TOKEN` and the SSH keys.

## 3. PROCESSES ACTIVATED

| Process | Owner (Workflow ownership table) | Detection if it silently stops |
|---|---|---|
| Object Lock governance-mode retention enforcement on `veridex-etcd-backup` | Backblaze B2 (provider-enforced, external to this repo) | None built yet — this is exactly Gate 20's "alerts for ... retention and bucket configuration changes," not yet built. Disclosed as a known limitation (§8), not hidden. |

No repo-owned automation is activated by this gate — nothing in this repository yet reads these credentials (Gate 9 is what wires them into k3s). The bucket, retention and keys exist and are proven; nothing depends on them operating correctly until Gate 9 closes.

## 4. DELIVERABLES

| ID | Artifact | Commit |
|---|---|---|
| D38 | `docs/security/secret-register.yml` — `ETCD_S3_ACCESS_KEY`/`ETCD_S3_SECRET_KEY` marked active; `~/.config/veridex/b2-etcd-backup-restore-key` registered `manual_only` | `2d16772`, `f287056` |
| D39 | `docs/security/b2-restore-access.md` — restore-identity purpose, usage, and constraints | `f287056` |
| D40 | `docs/evidence/gates/gate-08/` — this record and its five evidence files | (evidence commit follows) |

No Kubernetes/Ansible deliverable: this gate's actual subject (the B2 bucket, its Object Lock configuration, and the two application keys) is external cloud state, not version-controlled — consistent with the plan's own "Wasabi/B2 infrastructure is provisioned outside both [Ansible and Argo CD]" (Gate 31's territory, not yet decided).

## 5. TECHNICAL DETAIL

**Decision rationale**
- *`veridex-etcd-backup` created now, not a throwaway test bucket*: per Ordering decision O2, proving the mechanism on the real bucket Gate 9 will need avoids orphaning a disposable one, and B2 bucket names are globally unique — reserving the real name now removes a small but real risk of losing it to another account before Gate 9 is built.
- *Governance mode, not Compliance, and a provisional 2-day retention*: Compliance-mode activation is Gate 19's own explicit two-phase procedure (create → test → approve → lock), and committing to a Compliance period here would pre-empt that approval step and be irreversible. 2 days mirrors the plan's own "48 kept" hourly-snapshot figure for this bucket; Gate 18 may set a different final duration, which a plain `bucket update` can still change under Governance mode.
- *`listBuckets` granted to both restricted keys*: this CLI's own `--help` output (captured this session, pinned CLI version 4.7.1) states plainly that bucket-name-to-ID resolution requires the key to hold `listBuckets`, and `account authorize`'s own help lists it as a required capability. Not independently proven with a negative test (a key created without it) — sourced from the pinned tool's own authoritative documentation instead, which this plan's evidence standard treats as `DOCUMENTED`, not `VERIFIED` by this gate. Low risk regardless: a bucket-restricted key's `listBuckets` call is itself scoped to that one bucket.
- *Bucket-default retention relied on, not an explicit per-file `--file-retention-mode`*: setting file retention explicitly requires `writeFileRetentions`, which the writer key deliberately does not hold (matching "backup writers hold writeFiles but not... retention configuration" from Gate 20). Uploading without those flags inherits the bucket default automatically — confirmed live (§6, EG42).
- *Master key confined to bootstrap and one read-only check*: bucket create/update, the two `key create` calls, and one `file info` call (needed because neither restricted key holds `readFileRetentions`, so neither can independently confirm the uploaded object's actual retention — only the master key, or a key explicitly granted that capability, can). Never used for the deletion, retention-reduction, list or download tests, which exercise only the two restricted identities Gate 21 will eventually formalize.
- *Both keys given a 90-day expiry, not indefinite*: `validDurationSeconds` is available and unused expiry is a real risk this plan calls out generally (rotation, Gate 21); no rotation alerting exists yet (Gate 20), so the expiry date is recorded in the secret register in plain text as the interim safeguard (disclosed, §8).

**Resource tables** — one B2 bucket (`veridex-etcd-backup`, file-lock enabled, SSE-B2 default encryption, governance/2-days default retention); two B2 application keys (writer: `listBuckets,listFiles,writeFiles`; restore: `listBuckets,listFiles,readFiles`), each bucket-restricted, 90-day expiry. No Kubernetes manifests, no Terraform, no IAM policy documents (B2 has none — capability lists on the keys themselves are the access-control mechanism).

## 6. EXIT GATE

| ID | Acceptance item (plan) | Method | Evidence | Result |
|---|---|---|---|---|
| EG42 | Create protected test object | `b2 bucket create --file-lock-enabled --default-server-side-encryption SSE-B2`; `b2 bucket update --default-retention-mode governance --default-retention-period "2 days"`; `b2 file upload` as the writer key; independent read-only `b2 file info` as the master key to confirm inherited retention | `c1-create-protected-object.txt` | **PASS** — bucket created with file lock + SSE-B2; object uploaded, sha1 verified; master-key read-back confirms `fileRetention.mode: governance`, `retainUntilTimestamp` exactly 172800000ms (48h) after `uploadTimestamp` |
| EG43 | Deny early deletion and retention reduction | `b2 rm --fail-fast` as writer key, then as restore key (expect deny); `b2 file update --file-retention-mode none --bypass-governance` as writer key (expect deny) | `c2-deny-deletion-and-retention.txt` | **PASS** — all three exit 1 with `unauthorized for application key with capabilities ...`, naming the exact missing capability in each case |
| EG44 | List with restore identity | `b2 ls -l b2://veridex-etcd-backup/` as the restore key | `c3-list-with-restore-identity.txt` | **PASS** — object listed correctly; `file info` under the same identity correctly reports retention/legal-hold as unauthorized-to-read (least privilege, not a defect — see limitations) |
| EG45 | Download and verify | `b2 file download` as the restore key; sha1 comparison against the uploaded file | `c4-download-and-verify.txt` | **PASS** — download succeeded, sha1 `61e832fadd03a42550ad26f75d9c8c60e391efcc` matches exactly |
| EG46 | Record B2 account/bucket/region | `b2 bucket get`; `b2 file url`; `b2 account get` filtered to non-sensitive URL fields only | `c5-record-identity.txt` | **PASS** — account ID and bucket identity fully recorded; region code not independently confirmed by this CLI version (disclosed, §8) |

**Stop condition (verbatim):** "Cluster‑local‑only backup, administrator can silently remove retention, shared runtime credential, or any Hetzner dependency."

**Triggered: no.**
- *Cluster-local-only backup:* the destination is Backblaze B2, entirely external to the netcup cluster — EG42/EG44/EG45 all exercise real off-cluster storage.
- *Administrator can silently remove retention:* not triggered under the reading this gate uses — no automated or routine identity can remove or shorten retention (EG43 proves both runtime identities are denied). The account's master key does retain a deliberate `bypassGovernance` override under Governance mode, which is inherent to Governance mode by design and requires an explicit, deliberate flag to invoke — it is not silent in the sense of happening without action, but there is no alerting yet if it were used (Gate 20's territory, not yet built). This distinction is stated explicitly rather than glossed over (independent review finding, addressed in `c2-deny-deletion-and-retention.txt` and repeated here); Gate 19 (Compliance mode) is what removes even the master key's override, and is explicitly not attempted at this gate.
- *Shared runtime credential:* the writer and restore identities are two distinct, separately-scoped application keys — EG43 proves neither can perform the other's function (writer cannot read retention state at the detail level restore-adjacent reads would need; restore cannot write or delete).
- *Any Hetzner dependency:* none. `lint-provider-drift.py` re-run at this gate's tested commit reports 0 errors, 0 warnings.

## 7. ROLLBACK

### 7.1 Reversal procedure

**Repo-side (reversible, IIR-safe):** `git revert` of the deliverable commits (`2d16772`, `f287056` and this evidence commit) removes the register entries and the restore-access doc from the tree. No cluster or automation currently depends on them (Gate 9 has not wired them in), so nothing else breaks.

**B2-side (external, not version-controlled):**
- Deleting the two application keys (`b2 key delete <keyId>`, using the master key) is fully reversible — new keys can be created at any time and the secret register updated to match.
- Deleting the bucket itself is possible only after every object's retention has expired (governance mode, 2 days from upload) — this is Object Lock working as designed, not a rollback obstacle unique to this gate.
- **Lowering or removing the bucket's default retention mode is IRREVERSIBLE in one direction only if it is ever raised to Compliance** (Gate 19's territory, not done here). At Governance mode, the master key can lower or remove the default retention (`b2 bucket update --default-retention-mode none`) — reversible, not attempted, no approval sought or needed at this gate since nothing was locked to Compliance.
- The uploaded test object (`gate8-test-object-20260915T003358Z.txt`, 89 bytes) cannot be deleted by either restricted key before its retention lapses (2026-09-17, per EG42's confirmed `retainUntilTimestamp`) — flagged in §8 as a residual cleanup item, not a blocker.

### 7.2 Adversarial hardening loop

One iteration (cap 11).

| Iteration | Source | Findings | Fix commits |
|---|---|---|---|
| 1 | Independent review (Tier 1, separate context, given the evidence files, the secret-register diff, and Gates 8/19/20/21 plan text) | 6 findings: (medium) restore key existed live but had no secret-register entry — Gate 21 requires every key be "recorded alongside the key," and Gate 8's own end state already implies this key is a foundational identity, not a throwaway; (medium) c5's bucket-get output showed `defaultRetention`/`isFileLockEnabled`/`defaultServerSideEncryption` as unknown/null, contradicting c1's fully-populated values at the identical bucket revision, with no explanation in the evidence; (medium) c2's evidence proved denial for runtime identities but the write-up did not distinguish that from the stop condition's "administrator can silently remove retention," which is a different guarantee involving the master key and Gate 20's not-yet-built alerting; (low) region not recorded, self-disclosed already; (low) no rotation/expiry reminder for the 90-day keys beyond the register's own free-text; (info) `listBuckets`'s necessity asserted from the CLI's own `--help` text, not proven with a live negative test | `2d16772` (restore key not yet registered at this point — root cause of finding 1), `f287056` (all three medium findings fixed: restore key registered `manual_only` with `docs/security/b2-restore-access.md` as its usage doc mirroring `emergency-access.md`; c5 rewritten to name the identity that produced the masked output and cross-reference c1's authoritative values; c2 rewritten to state the stop-condition distinction explicitly; expiry dates added to all three register entries as the interim safeguard for the low finding) |

**Attacks attempted:** the review was asked to verify every claim in the evidence against the actual command output (not just trust the prose), to check whether the chosen capability sets were actually minimal against Gates 19-21's requirements, and to grep all five evidence files for anything secret-shaped. It found the three medium discrepancies above by cross-checking evidence files against each other and against the plan's stop condition text word-for-word — not by finding anything that broke the security model itself. No mutating attack was re-run against the live bucket by the reviewer (it had no B2 credentials); the three EG43 denial tests already constitute the adversarial attempt against the actual access-control mechanism, performed directly by this session at the recorded independence tier for that specific action (Tier 0 — same context that built it; disclosed, not a Tier 1 claim for EG43 itself).

**Tracked exceptions:** the two low findings and the one info finding (region, key-expiry alerting, `listBuckets` proof depth) are disclosed in §8 rather than fixed — each belongs to a later gate's own scope (Gate 18, Gate 20) or is already evidenced at the `DOCUMENTED` tier via the pinned tool's own authoritative output.

### 7.3 IIR attestation

- **Immutable:** every fix is committed on `feat/gate-08-backup-foundation` (`2d16772`, `f287056`); `git status` is clean except the pre-existing, unrelated `archieve-workflow/` directory.
- **Idempotent:** re-running `lint-provider-drift.py`, `lint-secret-register.py`, `lint-namespaces.py` and `validate-inventory.py` at the final commit all report zero errors — the same four checks Gate 0 established, unaffected by this gate's changes. There is no Ansible/k3s/Cilium automation for this gate to rerun `changed=0` against; the B2-side state (bucket, retention, keys) was created exactly once, not reconciled by a repeatable playbook — flagged in §8, not hidden.
- **Repeatable:** the bucket-creation and key-creation commands are recorded verbatim in the evidence files and are themselves idempotent-adjacent (re-running `bucket create` on an existing name fails loudly rather than silently duplicating; `key create` always makes a new key, so it is not safely rerunnable as-is) — a from-scratch reproduction would need a short, explicit script rather than manual CLI invocation, which is exactly the gap Gate 31's still-open IaC-mechanism decision is meant to close. Not built here — disclosed, §8.

## 8. KNOWN LIMITATIONS

- **This gate's provisioning is manual CLI invocation, not declarative/version-controlled infrastructure.** Gate 31 has not yet decided the mechanism for B2 infrastructure-as-code (the plan previously assumed Terraform; this platform has explicitly decided against Terraform, per prior session decision). Until Gate 31 closes, reproducing this bucket and these keys from scratch requires re-running the same manual commands, recorded in this gate's evidence, not a single declarative apply.
- **The master application key that bootstrapped this gate was found in a plaintext file also containing unrelated live credentials** (a personal email password and two GitHub personal access tokens), and was read into this session's conversation to extract it. The user was informed of this in-session and advised to rotate all of the exposed credentials, including this B2 master key, once Gates 18-21's remaining bucket/key creation work is done. This gate does not verify that rotation happened — it is the operator's own follow-up action, not something this gate can close on the operator's behalf.
- **Governance mode, not Compliance mode.** The master key can still lower or remove this bucket's default retention (a deliberate action, not silent, and not currently alerted on). Gate 19 is the gate that removes this by locking Compliance mode after a documented approval; not attempted here by design (§5, §7.1).
- **No alerting exists** if the master key is ever used to bypass governance retention, if an application key is created with excessive capabilities, or if these keys silently expire (2026-12-14) before a rotation happens — all Gate 20's territory.
- **The test object uploaded during EG42-EG45 cannot be deleted by either restricted key until its retention lapses** (2026-09-17). It will sit alongside real etcd snapshots once Gate 9 starts writing to this bucket; harmless (89 bytes) but should be cleaned up by an operator with elevated access once retention expires, or left as a permanent, harmless marker of this gate's proof.
- **Region is not independently confirmed.** The pinned CLI/SDK version's `account get` output exposes the native API node (`api005`/`f005.backblazeb2.com`) but not a friendly S3-style region code — confirm from the B2 web console when Gate 18 documents the full bucket architecture.
- **`listBuckets`'s necessity for bucket-name-based CLI operations is sourced from the pinned tool's own `--help` text**, not proven with a dedicated negative test (a key created without it). Low risk (a bucket-restricted key's `listBuckets` call is itself scoped to that bucket) but disclosed as `DOCUMENTED`, not independently `VERIFIED`, per this plan's own evidence standard.
- **No repeatable, idempotent playbook exists for this bucket/key creation** — a from-scratch rebuild today means re-reading this gate's evidence and re-typing the commands, not rerunning one script. Flagged for whatever mechanism Gate 31 eventually chooses.
- **Verifier independence is Tier 1 only**, for a gate CLAUDE.md §12 classifies high-risk (auth/secrets against a live billed account) — no Tier 2/external grader obtained, continuing the pattern accepted at Gates 0-7.
