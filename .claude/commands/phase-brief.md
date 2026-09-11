---
description: Generate or refresh the executable phase brief (objectives, scope, deliverables, performance specs, tasks, exit gates) for one phase. Spec-only — no cluster changes, no implementation. Usage /phase-brief <id>  (e.g. /phase-brief 0, /phase-brief 6a).
---

# Phase Brief Generator — Phase $1

Generate or refresh the **executable brief** for Phase $1 only. This command is **spec-only**: it reads the authoritative sources and writes one artifact. It does **not** implement, deploy, touch the live cluster, or run the Exit Gate. Use `/build-phase $1` when you want the full implementation + verification loop. This command is idempotent — re-run it any time the build plan changes to refresh the brief.

## Authoritative inputs (read these first)
- **Phase definition (SSOT):** `eng-design/sequential build/Phase $1` — the per-phase split file (authoritative split edition, superseding the monolithic `eng-design/Sequential Build Plan.md`). For overview, prerequisites, and shared definitions, first read `eng-design/sequential build/00 - Overview & Reference.md` which carries `Gate Window Definitions`, `Storage Decision`, `WORM Verification`, `CI/CD Foundation`, `The Three Hard Sequencing Rules`, and `Recommendations Appendix`.
- **Process registry:** `eng-design/Document Intelligence Platform v4.3.txt` Part 4 — resolve every "Processes Activated" ID to its "What It Must Do" spec.
- **Repo rules:** `CLAUDE.md`.

## Steps

### 1. EXTRACT (verbatim)
From the Phase $1 section, copy verbatim: **Objective**, **Scope**, **Processes Activated**, **Deliverables**, **Exit Gate** (every line — this is the contract; do not paraphrase or weaken), **Rollback**. Resolve each Process ID against v4.3.

### 2. WRITE the brief
Create/regenerate `docs/build/phases/phase-$1-brief.md` containing:
- **Objective** (verbatim)
- **Scope** (verbatim)
- **Processes Activated** (ID + one-line "must do", from v4.3)
- **Deliverables** (verbatim list)
- **Performance Specifications** — convert EACH Exit Gate criterion into an executable assertion, exact shape:

  ```
  - id: EG-<n>
    criterion: <verbatim Exit Gate line>
    owning_layer: Terraform | Ansible | ArgoCD | Kubernetes-manifest | CI/CD | Operational
    how_to_measure: <concrete method>
    command_or_test: <exact command / test name / runbook step>
    pass_condition: <boolean the evidence must satisfy>
    evidence_artifact: <path where proof is stored>
    window: <if "sustained"/"zero gaps"/"stable" → resolve via Gate Window Definitions (7 days / no missing sequence numbers over 48h / 30 days); else N/A>
  ```
- **Task Breakdown** — ordered tasks; each: `id`, `title`, `owning_layer`, `feeds_deliverable`, `feeds_assertion`, `verify_check`.
- **Risks & Rollback** (verbatim) + a mitigation per risk; flag any item the build plan itself reclassifies (e.g., Phase 4 cache ratio → ongoing SLO; GPU processes 52/72 → no-op stubs).

### 3. CONSISTENCY CHECK (report; do not silently skip)
Verify and report each gap:
- Every **Deliverable** maps to ≥1 task.
- Every **Exit Gate criterion** maps to ≥1 assertion (EG-n).
- Every **task** maps to ≥1 assertion or deliverable.
- Any criterion whose `window` cannot be observed at build time is explicitly flagged with its reclassification (per the build plan).

## Output contract (your final message)
1. Path of the brief written.
2. Counts: `<n>` assertions, `<n>` tasks, `<n>` deliverables.
3. Any consistency gaps found.
4. Explicit statement that no implementation / cluster change / commit occurred.

**Do NOT** implement tasks, run the Exit Gate, access the cluster, or commit anything.
