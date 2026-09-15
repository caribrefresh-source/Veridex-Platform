# GATE 9 — etcd recovery

| | |
|---|---|
| **Verdict** | **PASS** |
| **Closed (UTC)** | 2026-09-15T07:12:11Z |
| **Plan** | `docs/Engineering Documents/Initial Stages Plan.txt` @ `bc27a0a2b9e872679007342b5d255b888e000722`, sha256 `0c30445b0074edf3688ba57936e1c5149497b829e0f7d1b4328c5181bd222af8` (blob in Git) |
| **Tested repo commit** | `212122c45dbcd38a012902b943f90a498d5e5de8` (branch `feat/gate-09-etcd-recovery`; matches every evidence file's own `repo_commit:` field — the state live testing was run against, before this record and its evidence files were themselves committed) |
| **Target identity** | kube-system namespace UID `d7d8a462-c503-49ed-a1e0-899f372f9465`; API `https://10.2.0.100:6443`; host `veridex-server-1`; Backblaze B2 account `c1beac90ce56`, bucket `veridex-etcd-backup` (bucketId `4c818bbe7abca920ac0e0516`); isolated restore target was a disposable Docker container (`rancher/k3s:v1.36.4-k3s1`), not the production cluster |
| **High-risk** | Yes — etcd, auth/secrets (CLAUDE.md §12): a real production etcd snapshot and the production secrets-encryption key were used in an isolated restore drill |
| **Verifier independence** | Tier 1 — one independent adversarial review (separate context, given the diff and Gate 9 plan text). Found 6 issues (0 critical/high, 2 medium, 3 low, 1 info); both mediums and the actionable lows were fixed and reverified live; the remaining items are disclosed rather than fixed. No Tier 2 review obtained; continuing the pattern accepted at Gates 0-8. |

**Ordering note.** This gate closes under Ordering decision **O3** (`docs/evidence/gate-ledger.md`): Gate 9 builds and closes now on its own self-contained acceptance evidence, using Gate 17's "k3s etcd" row and Gate 18's bucket text as design reference rather than a closure blocker. Gate 17 (all six producer rows) closes later, incrementally, as each producer is built at its own gate.

**Mechanism note.** The plan's End state names "k3s's native S3-compatible snapshot target" as the off-cluster upload mechanism. That mechanism was tried, live, and found incompatible with Gate 8's Object-Lock-enabled bucket (full finding in §5 and `native-uploader-incompatibility.txt`). With the repository owner's explicit authorization, a sidecar uploader was built instead. Gate 9's substantive acceptance evidence — explicit hourly snapshots, explicit retention, a proven isolated restore — is met in full; the specific tool that uploads the bytes is not the one the plan's prose names.

## 1. OBJECTIVE

> Hourly local and off‑cluster snapshots are explicit, retention is explicit, and a snapshot restores successfully in isolation with protected server token and encryption material. The off‑cluster path uses k3s's native S3‑compatible snapshot target pointed at Backblaze B2 — proof is still required against the exact pinned k3s version, not assumed from protocol compatibility alone — see Gate 17, veridex-etcd-backup in Gate 18.

## 2. SCOPE

**In scope**
- Live proof that k3s's own local hourly snapshot mechanism (built at earlier gates) is working and correctly retaining exactly 48 snapshots.
- Diagnosis, live, of why k3s's native `--etcd-s3` uploader cannot write to `veridex-etcd-backup`: it does not send the `Content-MD5`/`x-amz-checksum-` header B2's Object Lock requires on every PUT. The firewall and B2 itself were independently ruled out before concluding it was k3s's own S3 client.
- A new Ansible role (`etcd-s3-backup`) that uploads local snapshots to B2 via the already-proven-working `b2` CLI, on a cron offset from k3s's own schedule, deployed and verified live on the bootstrap server.
- A B2 lifecycle rule on `veridex-etcd-backup` (remote retention), set once via the master key, confirmed not to disturb Gate 8's Object Lock or encryption settings.
- Two full autonomous scheduled cycles observed (the sync cron firing on its own, twice, each finding exactly one new local snapshot).
- A full isolated restore drill: download a real snapshot, restore it into a disposable Docker container running the exact pinned k3s version, using the production server token and a read-only copy of the production secrets-encryption key (deleted immediately after the drill), and query the restored API — namespaces, Secrets (decrypted cleanly), all five real node names, and configmaps.
- A code-enforced guard (an `assert` in `roles/k3s-server/tasks/main.yml`) preventing the proven-broken native uploader from ever being silently re-enabled by a future variable override.

**Out of scope**
- The other five B2 buckets and their own writer/restore identities → Gate 18, Gate 21, as each producer is built.
- Compliance-mode Object Lock, full account-isolation audit and change alerting → Gates 19, 20 (unchanged from Gate 8's own scope statement — this gate did not touch Object Lock mode).
- Amending the plan document's own prose to record the native-uploader → sidecar substitution → noted here and in the ledger's Position section instead, since the plan format doesn't have a per-gate "implementation note" field the way the ledger's Ordering decisions table does for sequencing conflicts.
- A from-scratch, fully-reproducible IaC restore of the isolated drill environment → the drill was performed with recorded, evidenced manual Docker commands (three corrective iterations, all disclosed), not a committed one-shot script. Gate 31's still-open IaC-mechanism decision is the natural place to formalize this if a repeatable drill script is wanted later.

## 3. PROCESSES ACTIVATED

| Process | Owner (Workflow ownership table) | Detection if it silently stops |
|---|---|---|
| Hourly local etcd snapshots, 48 retained | Ansible (`roles/k3s-server`, already active since Gate 4) — unchanged by this gate, re-verified | Local snapshot count deviating from 48, or the newest snapshot's timestamp falling behind an hour, would both be visible on the next `ls`/`k3s etcd-snapshot ls` — no automated alert exists yet (Gate 11's territory). |
| Hourly off-cluster upload to B2, offset 5 minutes past the local schedule | Ansible (`roles/etcd-s3-backup`, new this gate) | `/var/log/etcd-s3-backup/sync.log` on veridex-server-1: a missing "sync end, ok" line for an expected hour is the failure signal (the script's own `set -e` means a failure exits before printing it). No automated alert exists yet — same gap as above. |
| B2 lifecycle rule enforcing remote retention (hide 3 days after upload, delete 1 day after hidden) on `veridex-etcd-backup` | Backblaze B2 (provider-enforced, external to this repo) | None built yet — Gate 20's territory, same disclosed gap as Gate 8. |

## 4. DELIVERABLES

| ID | Artifact | Commit |
|---|---|---|
| D41 | `ansible/roles/etcd-s3-backup/` — defaults, tasks, two templates (credentials, sync script) | `c26880d`, `212122c` |
| D42 | `ansible/playbooks/etcd-s3-backup.yml` | `c26880d` |
| D43 | `ansible/roles/k3s-server/defaults/main.yml` (native-uploader finding, documented) and `tasks/main.yml` (code-enforced guard against it silently re-enabling) | `c26880d`, `212122c` |
| D44 | `ansible/inventory/production/group_vars/all.yml` — documents why `etcd_s3_endpoint`/`bucket` stay blank | `c26880d` |
| D45 | `Makefile` — `etcd-s3-backup` target, slotted into `bring-up` | `c26880d` |
| D46 | `docs/security/secret-register.yml` — `ETCD_S3_ACCESS_KEY`/`SECRET_KEY` correctly naming `roles/etcd-s3-backup` (not k3s) as the real consumer | `c26880d`, `212122c` |
| D47 | `docs/evidence/gates/gate-09/` — this record and its six evidence files | (this commit) |

## 5. TECHNICAL DETAIL

**Decision rationale**
- *The native-uploader incompatibility, in full*: `k3s etcd-snapshot save --etcd-s3 ...` against `veridex-etcd-backup` fails every time with `"Content-MD5 OR x-amz-checksum- HTTP header is required for Put Object requests with Object Lock parameters"` — confirmed via `journalctl` on the exact pinned k3s binary (v1.36.4+k3s1). No flag adds the missing header (checked `k3s server --help` and `k3s etcd-snapshot save --help` directly against the live binary). No `k3s-io/k3s` GitHub issue exists for this combination as of this check. The firewall was ruled out (`nft list ruleset`: OUTPUT policy accept) and B2/network reachability confirmed (`curl` to the endpoint succeeds with the expected unauthenticated-403). The `b2` CLI itself uploads to this same bucket without issue (Gate 8's own evidence) — the incompatibility is specific to k3s's minimal built-in S3 client, not B2, this bucket's Object Lock configuration in general, or the network path.
- *Sidecar over weakening Object Lock*: the alternative — disabling Object Lock on `veridex-etcd-backup` so the native uploader would work as the plan literally describes — was explicitly offered to and rejected by the repository owner, who chose to preserve Gate 8's immutability guarantee and build a sidecar instead. Recorded as a deliberate architectural choice, not a unilateral one (CLAUDE.md §15 prohibits weakening a security control to pass a check; this instead avoids the control ever being weakened).
- *Reusing Gate 8's writer key, not minting a new one*: the key is already scoped to exactly this bucket, exactly this producer, with exactly the right capabilities (`listBuckets,listFiles,writeFiles`, no `deleteFiles`) — matches Gate 21's "one key per producer/bucket pairing" even though the upload tool changed.
- *`b2 sync` with neither `--delete` nor `--keep-days`*: confirmed from this session's own live capture of `b2 sync --help` (pinned CLI 4.7.1) that both flags are optional and mutually exclusive, and that omitting both means the sync "optionally deletes or hides destination files that the source does not have" — i.e., without either flag, neither happens. Local retention pruning (k3s removing its own oldest local file) therefore never propagates as a remote deletion; B2-side retention is the lifecycle rule alone. This was flagged as unverified by independent review and is confirmed here from the pinned tool's own authoritative output, not re-guessed.
- *Sync offset 5 minutes past k3s's own schedule, not a tighter race*: k3s's own snapshot save completes in low single-digit seconds (observed live in the journal timestamps) — 5 minutes is generous headroom, not a narrow window.
- *Cluster-cidr/service-cidr and the `disable:` list matched to production exactly for the isolated restore*: the restored Node objects carry production's real PodCIDR annotations (`10.44.0.0/16`); k3s's stock defaults (`10.42.0.0/16`) caused `kube-controller-manager`'s node-ipam-controller to error and crash-loop the whole process on the first fully-configured attempt. Matching production's actual `k3s_cluster_cidr`/`k3s_service_cidr` and `disable:` list (`roles/k3s-server` group_vars/template) fixed it.
- *Encryption files placed AFTER `--cluster-reset`, not before*: `--cluster-reset` backs up and regenerates the entire `cred`/`tls` directory as part of its own documented procedure. A file placed there beforehand is swept into a timestamped backup and never read by the subsequent server start — found live (the first full attempt's `"identity transformer tried to read encrypted data"` errors on every Secret), fixed by placing production's `encryption-config.json` and `encryption-state.json` into the freshly-regenerated directory after the reset step, not before it.
- *`--secrets-encryption=true` explicitly passed*: k3s does not encrypt at rest without it, and its absence on the first attempt is why no encryption config existed to reconcile against at all. Once added, k3s auto-generates its own fresh (non-production) encryption files if none exist yet — these must still be overwritten with production's real ones, which was verified explicitly (diff of the auto-generated timestamp vs. production's, and the subsequent successful decryption of Secrets that predate this drill).

**Resource tables** — one new Ansible role (`etcd-s3-backup`: 2 template files, ~15 tasks); one new assert task in `k3s-server`; one B2 lifecycle rule (`etcd-snapshots/` prefix, 3-day hide, 1-day-after-hidden delete); one disposable Docker volume + container for the restore drill (both destroyed after use). No Kubernetes manifests, no Terraform, no IAM policy documents.

## 6. EXIT GATE

| ID | Acceptance item (plan) | Method | Evidence | Result |
|---|---|---|---|---|
| EG47 | Observe two scheduled cycles | Deliberate ~2h05m wait spanning two real hourly firings of both k3s's local cron and the new sync cron, with no manual trigger; independently reconfirmed via the `b2` CLI | `c1-two-scheduled-cycles.txt` | **PASS** — cron fired autonomously at 06:05:01Z and 07:05:01Z, each uploading exactly one newly-created local snapshot |
| EG48 | Verify local and remote retention | Local: exact snapshot count vs. configured `etcd-snapshot-retention`; Remote: `b2 bucket get`, confirming the lifecycle rule and that Gate 8's Object Lock/encryption settings are unchanged | `c2-local-and-remote-retention.txt` | **PASS** — local: exactly 48, matching config; remote: lifecycle rule present, bucket revision advanced 3→4 (partial update only) |
| EG49 | Download | `b2 file download` as the restricted restore key; sha1 comparison | `c3-download.txt` | **PASS** — checksum matches exactly |
| EG50 | Isolated restore | `k3s server --cluster-reset --cluster-reset-restore-path=...` against a real downloaded snapshot, in a disposable Docker container (pinned k3s version), using the production server token and a read-only, immediately-deleted copy of the production encryption key | `c4-isolated-restore.txt` | **PASS** — three corrective iterations disclosed in full; the final run restored cleanly and the container stayed running |
| EG51 | API query of restored objects | `kubectl get namespaces` / `secrets -A` / `nodes` / `configmaps -n kube-system` against the restored, isolated API | `c5-api-query-restored-objects.txt` | **PASS** — real production namespaces (with real historical ages), all Secrets listed with correct types (proving clean decryption, no values ever shown), all five real node names, real configmaps |

**Stop condition (verbatim):** "Only filename/checksum proof, missing token, untested restore, ambiguous RPO, or unproven Backblaze B2 behavior for the pinned k3s version."

**Triggered: no.**
- *Only filename/checksum proof:* EG50/EG51 go far beyond a checksum — a full API server came up from the restored data and served real queries, including decrypting Secrets.
- *Missing token:* the isolated restore used the real production `K3S_TOKEN`, matching the plan's own End-state language ("protected server token").
- *Untested restore:* EG50 is a live, executed restore, not a described procedure.
- *Ambiguous RPO:* RPO is explicit and observed: hourly local (EG47/48), and now hourly off-cluster within 5 minutes of the local snapshot (EG47), not "eventually" or "best effort."
- *Unproven Backblaze B2 behavior for the pinned k3s version:* the opposite of unproven — this gate is the proof, and what it proved is that the native path does NOT work for this exact pinned version against this bucket, which is exactly the kind of finding the plan's own "Highest-priority unresolved issue" and Gate 17's stop condition anticipated might occur. The stop condition's concern (silently trusting an unproven combination) is what this gate's whole native-uploader diagnosis exists to prevent — it was not quietly assumed to work, it was tested, found broken, and replaced with a proven-working alternative.

## 7. ROLLBACK

### 7.1 Reversal procedure

**Repo-side (reversible, IIR-safe):** `git revert` of `c26880d` and `212122c` (in reverse order) removes the `etcd-s3-backup` role, playbook, Makefile target, the k3s-server guard/comment, and the register/group_vars documentation. Rerunning `install-k3s-servers.yml` and `etcd-s3-backup.yml` afterward would restore the pre-Gate-9 state (native uploader still disabled by default, sidecar removed).

**Host-side:** removing the cron entry (`ansible.builtin.cron` with `state: absent`, not yet added since this gate is adding the schedule, not removing it) and deleting `/etc/etcd-s3-backup/`, `/usr/local/bin/etcd-s3-backup-sync.sh`, `/opt/etcd-s3-backup/venv` and `/var/log/etcd-s3-backup/` would fully remove the sidecar from `veridex-server-1`. Nothing else on the host is touched.

**B2-side (external, not version-controlled):** the lifecycle rule can be removed with a plain `bucket update --lifecycle-rule '[]'` (reversible — lifecycle rules, unlike Object Lock's fileLockEnabled flag, can be freely changed). The 52 uploaded snapshot objects remain under Gate 8's governance-mode retention until it lapses; none were deleted by this gate.

**The isolated restore drill itself:** fully torn down already (§6, `c4-isolated-restore.txt`) — the Docker container and volume were removed and the production encryption key copy was securely deleted (`shred -u`) immediately after the drill completed. Nothing from this drill persists anywhere outside this evidence record's prose.

No step in this gate is IRREVERSIBLE.

### 7.2 Adversarial hardening loop

One iteration (cap 11), covering both the sidecar role and the native-uploader diagnosis.

| Iteration | Source | Findings | Fix commits |
|---|---|---|---|
| 1 | (a) Live testing while diagnosing the native uploader and building the restore drill; (b) independent review (Tier 1, separate context, given the diff and Gate 9 plan text) | **(a) 4 real issues found by running it:** `k3s_data_dir` undefined in the new role (same class of bug as Gate 7 — a role's defaults are out of scope unless that role runs; fixed with `include_vars`); the isolated restore's pre-placed encryption config swept away by `--cluster-reset`'s own backup step; `--secrets-encryption=true` missing entirely from the first restore attempt; production's cluster-cidr/service-cidr not matched, crash-looping the restored controller-manager. **(b) 6 findings:** MEDIUM — the credential file `source`-d as unquoted shell; MEDIUM — the blank `etcd_s3_endpoint`/`bucket` guard was comment-only, not code-enforced; LOW — the sync script's log redirect ran after code that could fail silently; LOW — `docs/security/secret-register.yml` still described the old (native-uploader) consumer; LOW — unquoted path argument in the sync command; INFO — `b2 sync`'s non-destructive default behavior asserted without a cited source | `c26880d` (implementation and all four organic fixes); `212122c` (both mediums and the two actionable lows fixed; the `b2 sync` INFO item resolved by citing this session's own `--help` capture rather than re-verifying, since the source was already authoritative) |

**Attacks attempted:** the isolated restore drill was itself the most direct attack on the whole gate's premise — actually restoring a real snapshot into a real (if disposable) k3s instance and querying it, rather than trusting that the upload path alone was sufficient proof. Two of the three corrective iterations it took were failures the drill itself surfaced (encryption config swept away; cidr mismatch), not failures found by inspection — the drill was adversarial toward its own success. Separately, the code-enforced guard added in `212122c` was reverified by rerunning `install-k3s-servers.yml` fleet-wide and confirming `changed=0` on all three control-plane nodes — the guard passes without disturbing production, and a deliberate attempt to reason through "what if someone sets `etcd_s3_endpoint` in group_vars later" (the exact scenario the guard defends against) confirms the assert would catch it on the very next converge, before any broken upload could be attempted.

**Tracked exceptions:** none. Every independent-review finding was either fixed or resolved (the `b2 sync` INFO item) in this iteration.

### 7.3 IIR attestation

- **Immutable:** every fix is committed on `feat/gate-09-etcd-recovery` (`c26880d`, `212122c`); `git status` is clean except the pre-existing, unrelated `archieve-workflow/` directory.
- **Idempotent:** `install-k3s-servers.yml` re-run fleet-wide after adding the code-enforced guard reports `changed=0` on all three control-plane nodes, no restart — the guard is a pure read-time assertion, not a config change. `etcd-s3-backup.yml` re-run after the hardening fixes redeployed the corrected credential/script templates (`changed`, as expected for an actual content change) and its own immediate verification task passed again.
- **Repeatable:** the sidecar role is fully Ansible-managed and reruns cleanly from a fresh converge. The isolated restore drill is **not** yet a repeatable script — it was performed via recorded, evidenced manual Docker commands with three disclosed corrective iterations. A future drill (or Gate 29's full drill) would need to either redo that iteration or, better, have someone turn the corrected final command sequence in `c4-isolated-restore.txt` into a committed script — flagged as a real gap, not hidden (§8).

## 8. KNOWN LIMITATIONS

- **The plan's literal mechanism (k3s's native S3 uploader) is not what's running.** A sidecar is. This is disclosed at the top of this record and throughout, with the full live diagnosis in `native-uploader-incompatibility.txt` — not a silent substitution. If a future k3s release adds the missing header, reverting to the native uploader is the smaller change (`roles/k3s-server/defaults/main.yml` says exactly what to check).
- **The isolated restore drill is not yet a repeatable, version-controlled script.** Three manual corrective iterations were needed and are fully disclosed (§7.2, `c4-isolated-restore.txt`). Turning the corrected final sequence into a committed script is real future work, not done here.
- **No alerting exists** if the sync cron silently stops firing, if the B2 lifecycle rule is ever changed or removed, or if the 90-day key expiry (Gate 8, 2026-12-14) arrives unrotated — all Gate 20's territory, not built here.
- **Remote (B2) retention and local retention are different mechanisms with different windows** (an exact 48-count locally vs. a time-based lifecycle rule remotely) — disclosed in `c2-local-and-remote-retention.txt` as intentional, not a mismatch to be reconciled.
- **This gate's off-cluster upload runs from the bootstrap server only** (`veridex-server-1`). If that specific node is permanently lost before a failover/promotion mechanism exists, off-cluster upload stops until the sidecar is redeployed to a surviving control-plane node — a manual, undocumented recovery step today. Not a gap in the DATA (any control-plane node's own local snapshot is independently complete, and the already-uploaded history in B2 is unaffected), but a gap in the AUTOMATION's own resilience, worth flagging for whichever later gate formalizes node-loss runbooks.
- **The Content-MD5/Object-Lock incompatibility finding is scoped to the exact pinned versions tested** (k3s v1.36.4+k3s1, b2 CLI 4.7.1) and to this specific combination (k3s's *built-in* S3 client against a B2 bucket with Object Lock *enabled*). It says nothing about other S3-compatible backends, non-Object-Lock buckets, or other k3s versions.
- **Verifier independence is Tier 1 only**, for a gate CLAUDE.md §12 classifies high-risk (a real production etcd snapshot and encryption key used in the restore drill) — no Tier 2/external grader obtained, continuing the pattern accepted at Gates 0-8.
