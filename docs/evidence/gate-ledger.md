# Gate ledger — Veridex cluster production end-state plan, Revision 3

Maintained by `.claude/skills/veridex-gate/SKILL.md`. **The three tables are
append only.** Never edit or renumber a row; a reopened gate is recorded in the
reopen log and gets a new row when it closes again, and a changed ordering
decision is a new row that names the row it supersedes.

Plan: `docs/Engineering Documents/Initial Stages Plan.txt`

## Position

Last deliverable **D28**, last exit-gate check **EG24** (Gate 4, closed
2026-09-14). The next closed gate starts at **D29** and **EG25**.

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

## Reopen log

| Date (UTC) | Gate | Trigger | Evidence | Cascaded to |
|---|---|---|---|---|

## Ordering decisions

| # | Date (UTC) | Conflict | Decision | Decided by |
|---|---|---|---|---|
| O1 | 2026-09-13 | Plan: "Execute each gate in order and stop on the first unmet dependency." Gate 13: the MINIO_KMS_SECRET_KEY incident "(Gate 22) is closed before this gate can pass", with scheduling "enforced per Gate 23" and "capacity thresholds per Gate 24", and a stop condition of "capacity below safety threshold". Gate 22: "must complete before … Gate 13 or Gate 24 can pass." In strict numeric order Gate 13 closes before Gate 22, so neither can close. | Gate 13 may be **built** (MinIO deployed, not approved for production) once Gates 0–12 are closed. Gates 22, 23 and 24 then close, in that order, before Gate 13 **closes**. Their dependencies are Gates 0–12 plus Gate 13's deployment — not Gates 14–21. Gate 14 is not built until Gate 13 closes. | Repository owner, 2026-09-13 session, adopting the resolution proposed there |

## Open ordering conflicts

Found by reading every cross-reference in the plan (commit `4ebc8de`). Each is a
forward reference a lower gate depends on, so strict numeric order deadlocks.
Not yet decided — each needs an Ordering decisions row before the lower gate
can close. Remove an entry here only when its decision row is appended.

- **Gate 8 → Gates 18–21.** Gate 8: "Exact bucket architecture, credential
  mechanism and Object Lock activation are specified in Gates 18–21." Gate 21
  also covers producers that do not exist until Gates 9, 12, 13 and 14, so it
  cannot simply move ahead of Gate 8 whole. Reached next, after Gate 7.
- **Gate 9 → Gates 17 and 18.** Gate 9's stop condition includes "unproven
  Wasabi behavior for the pinned k3s version" (Gate 17's k3s etcd row) and it
  uses `veridex-etcd-backup` from Gate 18.
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
