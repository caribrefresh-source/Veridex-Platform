---
description: Read-only progress dashboard across all Document Intelligence Platform build phases, derived fresh from the build plan every run. No writes, no cluster access. Usage /phase-status.
---

# Build Status — Read-Only Report

Produce a read-only progress dashboard across **all** Document Intelligence Platform build phases. **No writes, no cluster access, no implementation.** Pure inspection of existing artifacts.

**Self-updating by design.** The phase list, ordering, and sequencing rules below are never hardcoded in this command — they are re-derived from per-phase files under `eng-design/sequential build/` (the authoritative split edition, superseding the monolithic `eng-design/Sequential Build Plan.md`). The build plan has already been restructured more than once (phases split into sub-phases, a phase inserted mid-sequence, phases renumbered) and will likely be restructured again; this command must reflect whatever it currently says, not whatever it said when this command was last edited.

## Inputs
- `eng-design/sequential build/` — the single source of truth for phase definitions, ordering, prerequisites, and sequencing rules (per-phase split files, superseding the monolithic `eng-design/Sequential Build Plan.md`). Start at `eng-design/sequential build/00 - Overview & Reference.md`. Read every phase file fresh, every run.
- `docs/build/phases/BUILD-STATUS.md` — append-only status log (may not exist yet).
- `docs/build/phases/phase-*-brief.md` and `phase-*-exit-gate.md` (may not exist yet).

## Steps

### 1. Derive the canonical phase list — fresh every run, never hardcoded

Scan the build plan for every **live, buildable** phase section. A phase section is a heading of one of two forms:
- `## Phase <id> — <name>` (the common case), or
- `# Phase <id> Build Plan — <name>` (the self-contained-document pattern: some phases are large enough to carry their own internal `## 1 ... ## N` numbering directly as their own gate, rather than nesting under the Sequential Build Plan's own heading level. As of this writing Phase 2 and Phase 2.5 use this pattern — but check whether that's still true; a future phase could adopt or drop it).

**Exclude** any heading explicitly marked as historical or superseded — e.g. containing "SUPERSEDED-IN-PLACE", or a "Gate Wrapper" heading whose own text says a fuller version now exists elsewhere. This document's convention is to mark deprecated sections in place rather than delete them, so they will say so explicitly; when in doubt, read the section's own text rather than guessing from its title.

**Exclude** any phase-numbered heading that is itself an umbrella/status-note pointing at sub-phases rather than a buildable unit — recognizable because its own text says it has been split into ordered sub-phases (e.g. "executed as five ordered sub-phases below"). Include the sub-phases instead of the umbrella; don't double-count both, and don't treat the umbrella itself as gate-able.

For each live phase found, record: its **id** exactly as written (e.g. `0`, `1`, `2`, `2.5`, `3a`, `3a.5`, `6`, `8a`), its **name**, its **Exit Gate criterion count**, and — critically — its stated **Prerequisite** (read the phase's own "Prerequisite" / "Hard Prerequisites" text verbatim). Do not assume prerequisite = "the previous number" — that assumption is exactly what breaks when the plan is restructured.

### 2. Per-phase state
For each phase determine:
- **Brief present?** — does `docs/build/phases/phase-<id>-brief.md` exist? (For phases using the self-contained-document pattern, a separate brief file may legitimately not exist — note this rather than treating it as a gap.)
- **Gate verdict** — parse the verdict line from `phase-<id>-exit-gate.md` (PASS | PARTIAL | BLOCKED | — if no record).
- **Date** — latest gate verdict date.
- **Blockers** — from the exit-gate record, if any.
- **Latest status line** — most recent matching line in `BUILD-STATUS.md`, if any.

### 3. Determine readiness and active phase(s) — dependency-based, not numeric-order-based

Do not assume phases unlock in numeric order — several already don't (Phase 2.5 sits between 2 and 3; 3a.5 was inserted after 3a; 3c and 3d both depend only on 3a and may proceed in parallel; 8a and 8b are explicitly independent). Build a dependency view from each phase's own stated Prerequisite (Step 1):

- A phase is **ready** if every phase it names as a prerequisite has a recorded PASS, or if it states no prerequisite.
- **More than one phase can be ready/active at once.** Report all of them, not just the lowest-numbered — the build plan states explicitly, in each relevant phase's own text, when phases may proceed in parallel.
- At least one phase in this plan is **data-gated** rather than purely dependency-gated — it does not start on a calendar or on prerequisite-PASS alone, but on a stated corpus/decision threshold in its own text (e.g. "does not start... regardless of when that occurs" until N reviewer decisions exist). Find this by reading each phase's own gating language fresh each run; do not hardcode which phase this is or what its threshold is, since both have changed before under renumbering.

Report:
- Every phase with a PASS verdict.
- Every phase that is ready to build next (dependencies satisfied, no PASS yet) — list all of them if more than one.
- Every phase that is blocked, naming the specific unmet prerequisite.
- The data-gated phase's current status against its own stated threshold, if the plan currently defines one.

### 4. Sequencing-sanity check — apply the rules' own current text, never restate them

Re-read the **"The Three Hard Sequencing Rules"** section in full, fresh, every run. For each rule, use whatever phase names/numbers **that section's own current text** names — do not hardcode phase numbers for these rules anywhere in this command. Two of the three rules already reference phase numbers that have changed once under renumbering (the RAG-layer phase and the HITL-gates phases both moved); they can move again. Check each rule's current phase references against Step 2's per-phase state and report any violation using the rule's own wording.

## Output contract (your final message)

1. Status table:

   | Phase | Name | Brief | Gate | Date | Prerequisite | Blockers |
   |-------|------|:-----:|------|------|---------------|----------|

   (Prerequisite column: the phase this one depends on per its own stated text, or "—" if none.)

2. **Ready / active phase(s):** every phase currently ready to build (dependencies satisfied, not yet PASS) — list all if more than one. If every defined phase has PASS, report "all passed → Deferred" and list the Deferred set.
3. **Data-gated phase status:** if the plan currently defines one, its name and current status against its own stated threshold.
4. **Sequencing violations:** list, using the rules' own current phase references, or "none".
5. **Gaps:** phases with no brief yet; phases with a brief but no gate run; phases with PARTIAL/BLOCKED gates.
6. **Recommended next action:** e.g. `/phase-brief <id>` to draft the spec, or `/build-phase <id>` to run the loop — one per ready phase.

**Do NOT** modify, create, or delete any file. If `docs/build/phases/` does not exist, report "no build artifacts yet — start with `/phase-brief 0`". If the phase list this run derives differs from an earlier run's, that is expected and correct — the build plan is the source of truth, not this command's memory of a prior run.
