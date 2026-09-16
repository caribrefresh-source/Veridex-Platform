# Gate ledger — Veridex cluster production end-state plan, Revision 3

Maintained by `.claude/skills/veridex-gate/SKILL.md`. **The three tables are
append only.** Never edit or renumber a row; a reopened gate is recorded in the
reopen log and gets a new row when it closes again, and a changed ordering
decision is a new row that names the row it supersedes.

Plan: `docs/Engineering Documents/Initial Stages Plan.txt`

## Position

Last deliverable **D62**, last exit-gate check **EG67** (Gate 11, closed
2026-09-16). The next closed gate starts at **D63** and **EG68**.

**Gate 11 tracked exception.** Gate 11 closed **PASS** with one disclosed,
user-accepted exception rather than a fully clean hardening pass:
`kubernetes/cluster/policies/argocd-health-probes.yaml` admits ports
8080/8082/8084 by L4 port alone (not path-restricted), which over-grants
the full ArgoCD UI/API/gRPC surface on those ports, not just the /healthz
probe, to any source matching host/remote-node/health, the pod CIDR, or
(compensating for a separate, still-unfixed Cilium identity-
misclassification bug) the `world` entity. An L7 fix was implemented and
rolled out live, immediately caused a real production regression
(argocd-server/repo-server/application-controller probe failures with
climbing restart counts), and was reverted within minutes — see
`docs/evidence/gates/gate-11/closure.md` Sec.7.2 for the full finding,
attack, and revert record. Accepted as a tracked exception by the
repository owner, 2026-09-15, rather than holding closure for a safer L7
approach. Any gate that later touches Argo CD's network exposure should
revisit this.

**Gate 10 stop-condition deviation.** Gate 10 closed **PASS** despite its own
stop condition ("writable repo key") being triggered: the deployed
`ARGOCD_REPO_PAT` was found live to carry near-full account-admin GitHub
scope, not read-only. This is an explicit, disclosed operator override of
the plan's own stop-condition rule, not a finding that the condition didn't
apply — see `docs/evidence/gates/gate-10/closure.md`'s deviation note and
`pat-scope-finding.txt` for the full account. Treat `ARGOCD_REPO_PAT`'s scope
as an open risk in any later gate that touches repository credentials.

**Gate 9 implementation note.** The plan's End state for Gate 9 names "k3s's
native S3-compatible snapshot target" as the off-cluster upload mechanism.
That mechanism was tried, live, against the exact pinned k3s version and
found incompatible with Gate 8's Object-Lock-enabled bucket (it never sends
the `Content-MD5`/`x-amz-checksum-` header B2's Object Lock requires — full
finding in `docs/evidence/gates/gate-09/native-uploader-incompatibility.txt`).
With the repository owner's explicit authorization, a sidecar uploader
(`roles/etcd-s3-backup`, built on the already-proven-working `b2` CLI)
replaces it. Gate 9's substantive acceptance evidence is met in full; the
specific tool is not the one the plan's prose names.

**Resolved 2026-09-15:** the plan document has now been amended to describe
the implemented sidecar rather than the native uploader — Gate 9's End
state, the "Highest-priority unresolved issue" section, the k3s/etcd row of
the Recovery objectives table, and the immediate implementation backlog
(which now says explicitly: "The etcd producer is the pinned b2-CLI
sidecar; do not substitute the failed native k3s path in its evidence
row"). Gate 9's row below names the pre-amendment plan commit, which
remains valid: the amendment corrects prose to match what Gate 9 actually
proved and changes no decision it recorded. Gate 17 must assess the
sidecar path.

The plan blob advanced from `4ebc8de` to `64d80e6` at Gate 7's closure (the
Gates 32-35 amendment, Part D; hardening backlog renumbered to Part E). Gates
0-6's rows name the earlier blob and remain valid against the newer one: the
amendment adds gates and cross-references only and changes no decision recorded
for Gates 0-31. A differing plan commit between rows is therefore expected here
and is not the release/cluster mismatch `audit all` looks for.

Evidence recorded before Revision 3 lives in `docs/evidence/legacy/`. It is not
closure evidence; `docs/evidence/legacy/README.md` maps it to Revision 3 gates.

## Closed gates

| Gate | Title | D-range | EG-range | Closed (UTC date) | Plan commit | Tested repo commit | Target identity | Record |
|---|---|---|---|---|---|---|---|---|
| 0 | Repository and provider boundary | D1–D8 | EG1–EG4 | 2026-09-14 | `4ebc8de` | `82a1dd4` | repository `github.com/caribrefresh-source/Veridex-Platform` @ `82a1dd4` | `docs/evidence/gates/gate-00/closure.md` |
| 1 | Operating systems and access | D9–D20 | EG5–EG9 | 2026-09-14 | `4ebc8de` | `3573063` | hosts veridex-server-1/2/3, veridex-agent-1/2 @ `3573063` (SSH host-key fingerprints in `ansible/files/known_hosts`) | `docs/evidence/gates/gate-01/closure.md` |
| 2 | Private network | D21–D21 | EG10–EG13 | 2026-09-14 | `4ebc8de` | `5cb1beb` | hosts veridex-server-1/2/3, veridex-agent-1/2 @ `5cb1beb` (SSH host-key fingerprints in `ansible/files/known_hosts`) | `docs/evidence/gates/gate-02/closure.md` |
| 3 | Host prerequisites and firewall | D22–D24 | EG14–EG19 | 2026-09-14 | `4ebc8de` | `a194cf6` | hosts veridex-server-1/2/3, veridex-agent-1/2 @ `a194cf6` (SSH host-key fingerprints in `ansible/files/known_hosts`) | `docs/evidence/gates/gate-03/closure.md` |
| 4 | k3s control plane | D25–D28 | EG20–EG24 | 2026-09-14 | `4ebc8de` | `ccf4041` | kube-system namespace UID d7d8a462-c503-49ed-a1e0-899f372f9465; API https://10.2.0.100:6443 | `docs/evidence/gates/gate-04/closure.md` |
| 5 | kube‑vip failure behavior | D29–D29 | EG25–EG31 | 2026-09-14 | `4ebc8de` | `9f50972` | kube-system namespace UID d7d8a462-c503-49ed-a1e0-899f372f9465; API https://10.2.0.100:6443 | `docs/evidence/gates/gate-05/closure.md` |
| 6 | Cilium and cluster DNS | D30–D33 | EG32–EG37 | 2026-09-14 | `4ebc8de` | `8bf4f56` | kube-system namespace UID d7d8a462-c503-49ed-a1e0-899f372f9465; API https://10.2.0.100:6443 | `docs/evidence/gates/gate-06/closure.md` |
| 7 | Verification automation | D34–D37 | EG38–EG41 | 2026-09-14 | `64d80e6` | `64d80e6` | kube-system namespace UID d7d8a462-c503-49ed-a1e0-899f372f9465; API https://10.2.0.100:6443 | `docs/evidence/gates/gate-07/closure.md` |
| 8 | Backup foundation | D38–D40 | EG42–EG46 | 2026-09-15 | `bc27a0a` | `f287056` | Backblaze B2 account c1beac90ce56; bucket veridex-etcd-backup, bucketId 4c818bbe7abca920ac0e0516 | `docs/evidence/gates/gate-08/closure.md` |
| 9 | etcd recovery | D41–D47 | EG47–EG51 | 2026-09-15 | `bc27a0a` | `212122c` | kube-system namespace UID d7d8a462-c503-49ed-a1e0-899f372f9465; API https://10.2.0.100:6443; Backblaze B2 bucket veridex-etcd-backup, bucketId 4c818bbe7abca920ac0e0516 | `docs/evidence/gates/gate-09/closure.md` |
| 10 | Argo CD handover | D48–D53 | EG52–EG56 | 2026-09-15 | `bc27a0a` | `145df11` | kube-system namespace UID d7d8a462-c503-49ed-a1e0-899f372f9465; API https://127.0.0.1:6443 (local kubeconfig on veridex-server-1; same cluster, confirmed by UID match against Gates 4-9's VIP-addressed https://10.2.0.100:6443) | `docs/evidence/gates/gate-10/closure.md` (**PASS via explicit operator override of the plan's own stop-condition rule** — see Position note above) |
| 11 | Baseline observability | D54–D62 | EG57–EG67 | 2026-09-16 | `4f591e3e` | `dfc225d7af1bd4c5306b8569f8cc98c08442e5ba` | kube-system namespace UID d7d8a462-c503-49ed-a1e0-899f372f9465; API https://127.0.0.1:6443 (local kubeconfig on veridex-server-1; same cluster, confirmed by UID match against Gates 4-10's VIP-addressed https://10.2.0.100:6443) | `docs/evidence/gates/gate-11/closure.md` (**PASS with one disclosed, user-accepted tracked exception** — see Position note above) |

## Reopen log

| Date (UTC) | Gate | Trigger | Evidence | Cascaded to |
|---|---|---|---|---|

## Ordering decisions

| # | Date (UTC) | Conflict | Decision | Decided by |
|---|---|---|---|---|
| O1 | 2026-09-13 | Plan: "Execute each gate in order and stop on the first unmet dependency." Gate 13: the MINIO_KMS_SECRET_KEY incident "(Gate 22) is closed before this gate can pass", with scheduling "enforced per Gate 23" and "capacity thresholds per Gate 24", and a stop condition of "capacity below safety threshold". Gate 22: "must complete before … Gate 13 or Gate 24 can pass." In strict numeric order Gate 13 closes before Gate 22, so neither can close. | Gate 13 may be **built** (MinIO deployed, not approved for production) once Gates 0–12 are closed. Gates 22, 23 and 24 then close, in that order, before Gate 13 **closes**. Their dependencies are Gates 0–12 plus Gate 13's deployment — not Gates 14–21. Gate 14 is not built until Gate 13 closes. | Repository owner, 2026-09-13 session, adopting the resolution proposed there |
| O2 | 2026-09-15 | Gate 8: "Exact bucket architecture, credential mechanism and Object Lock activation are specified in Gates 18–21." Gate 21: "One key per producer/bucket pairing" for producers (CloudNativePG, MinIO, Longhorn, k3s etcd) that do not exist until Gates 9, 12, 13 and 14 close. Neither side can go first under strict numeric order: Gate 8 names Gates 18–21 as its own specification, and Gate 21 cannot fully close before producers built at Gates 9/12/13/14, which themselves follow Gate 8 in numeric order. | Gate 8 **builds and closes now** on its own self-contained acceptance evidence (one protected test bucket, Object Lock two-phase activation per Gate 19, one writer key + one restore key under the application-key model of Gates 20–21) — using Gates 18–21's text as design reference, not as a closure blocker. Gates 18–21 close later, incrementally, as their own fuller requirements become satisfiable: Gate 18 once all six buckets are formally defined, Gate 20 once full account isolation is audited, Gate 21 only once each producer exists (Gates 9/12/13/14) and gets its own scoped key. Mirrors O1's split exactly. | Repository owner, 2026-09-15 session, adopting the resolution proposed there |
| O3 | 2026-09-15 | Gate 9: "see Gate 17, veridex-etcd-backup in Gate 18." Gate 17's "k3s etcd" row requires proof of "Scheduled upload, listing, pruning and isolated restore" — substantively Gate 9's own acceptance evidence — but Gate 17 as a whole cannot close until all six producer rows (CloudNativePG, Velero, MinIO, Longhorn, k3s etcd, audit exporter) are each proven, at gates (12, 13, 14) that follow Gate 9 in numeric order. `veridex-etcd-backup` (Gate 18) already exists live, created at Gate 8. | Gate 9 **builds and closes now** on its own self-contained acceptance evidence (two observed scheduled snapshot cycles, local and remote retention verified, download, isolated restore, API query of restored objects) against the real `veridex-etcd-backup` bucket and `ETCD_S3_ACCESS_KEY`/`ETCD_S3_SECRET_KEY` Gate 8 already created — using Gate 17's "k3s etcd" row and Gate 18's bucket text as design reference, not a closure blocker. Gate 17 closes later, once every producer row is proven at its own gate; Gate 9 proving its own row now is a contribution toward that, not something blocked by it. Mirrors O1 and O2 exactly. | Repository owner, 2026-09-15 session, adopting the resolution proposed there |
| O4 | 2026-09-15 | Gate 10: "Gate 32 (namespace enumeration) runs here ... every namespace name used by the rollout waves below and by Gate 11 onward must be resolved and committed before any wave begins." Gate 11: "Wave 1 of the namespace rollout (dedicated test namespace) opens here, once Gate 32 has resolved its name ... Gate 34 (namespace RBAC) begins riding along at this same wave." Gate 32 is a higher-numbered, unbuilt gate; in strict numeric order Gate 11 closes before Gate 32, but Gate 11's own Wave 1 text is conditional on Gate 32. Same deadlock shape as O1-O3. | Gate 11 **builds and closes now** on its own self-contained End state/Acceptance evidence/Stop condition (node, etcd snapshot, disk, Cilium, DNS and Argo reconciliation alerts; metrics/events/logs coverage; Hubble flow visibility) — none of which name a namespace. Precedent: Traefik (Wave 7 "cluster services") was already deployed live into `kube-system` ahead of Gate 32's namespace map (PR #18), establishing that cluster-infrastructure deployment is not blocked on Gate 32 — only the namespace's *P0-P6 NetworkPolicy enforcement promotion* is (Wave 7, later). Gate 11's `monitoring` namespace is built the same way: a new, plain, unlabeled namespace now; Gate 32 may later confirm/rename it as the resolved Wave 7 name. Wave 1's dedicated test namespace and Gate 34's RBAC riding alongside it are deferred until Gate 32 closes and resolves that name. Mirrors O1-O3 exactly. | Repository owner, 2026-09-15 session, adopting the resolution proposed there |

## Open ordering conflicts

Found by reading every cross-reference in the plan (commit `4ebc8de`). Each is a
forward reference a lower gate depends on, so strict numeric order deadlocks.
Not yet decided — each needs an Ordering decisions row before the lower gate
can close. Remove an entry here only when its decision row is appended.

**This list has not been fully re-derived against plan commit `64d80e6`.** That
amendment (Gates 32-35) adds cross-references of the same shape. The one
directly blocking Gate 11 — Gate 32 must resolve namespace names before the
Wave 1 rollout at Gate 11, with Gate 34 riding along from Wave 1 — is now
decided, see **O4** above. Still not enumerated below or decided: Gate 35 must
be decided by Gate 15, and Gate 29's step 12 is Gate 35's exit check. None
involve Gates 0-7, so none blocked Gate 7's closure; this remaining
re-derivation is owed before Gate 15 closes.

- **Gate 12 → Gate 26.** Gate 12 defers "final tiering and node feasibility" to
  Gate 26, whose stop condition must be resolved "before longhorn-critical is
  used".
- **Gate 16 ↔ Gate 29.** Gate 16 is "superseded in detail by" Gate 29's drill,
  while every gate after 16 depends on it by numeric order.
- **Gates 13 and 24 → "the §6 conflict".** The plan says to resolve "the §6
  conflict below (SOPS + age vs. SealedSecrets and Longhorn)" before Gates 13 or
  24 close, but the plan contains no §6. The nearest match is `.claude/CLAUDE.md`
  §6 Approved Stack, which lists SOPS + age and does not list SealedSecrets,
  Longhorn or Velero. This is a stack decision, not only an ordering one.
