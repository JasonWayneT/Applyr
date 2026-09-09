---
status: implemented
created: 2026-09-07
related: CR-098, CR-107, CR-094, CR-076-084
source: docs/instruction-authority-audit-2026-09-07.md
---

# CR-111 — Instruction-Authority Hygiene

## Problem

The 2026-09-07 instruction-authority audit
(`docs/instruction-authority-audit-2026-09-07.md`) found that Applyr's agent instruction
system has nine files claiming some form of canonical authority, with specific, live
contradictions between them:

- `.claude/agents/engineering-manager.md` orders `CLAUDE.md` and `AGENTS.md` to be "edited
  byte-identically if either changed" — the exact twin-drift failure banned 2026-08-14,
  sitting inside the pipeline's final quality gate.
- Cover-letter word band is stated three ways: 250–400 (root `AGENTS.md`), 300–400
  (`docs/ACTIVE_WORKFLOW.md`, CR-043 era), 220–450 (`submission_linter.py` LW-001).
- Registry `AC-076` mandates stripping `## Core Competencies`; root `AGENTS.md` and the
  same registry's `FR-195` mandate injecting it. AC-076 was never marked superseded.
- Root `AGENTS.md`'s File Map says `candidate_preferences.json` holds "min fit score 72"
  (floors moved to `fit_rubric_calibration.json` under CR-093) and claims "there is no
  automated page-count gate in this pipeline yet" (false since
  `verify_submission.py::_pdf_page_count`).
- Four skills exist as byte-identical twins across `.claude/skills/` and `.codex/skills/`
  with no declared canonical; frontmatter has already started diverging.
  `.codex/skills/submission-no-ai-slop/SKILL.md` is a full clone of the `.agents` canonical
  whose own text names a different file as canonical.
- `docs/AGENTS.md` claims parallel root authority ("All AI agents must follow this file"),
  never defers to root `AGENTS.md`, and links `SDD_PROCESS.md` via a stale absolute
  `file:///` path into the pre-rename `JobAgent` folder.
- Registry status rot: CR-079/080/081 rows still say `WAITING_FOR_HUMAN` (renamed by
  CR-107); CR-076–084 rows still `in_progress` though landed; duplicate IDs (AC-095 ×2,
  AC-119 ×3, NFR-004 ×2) violate the repo's own ID-uniqueness rule.
- `.claude/agents/tech-lead.md` hardcodes a stale active-CR list;
  `.claude/agents/product-manager.md` references `superpowers` skills that exist only as an
  unwired copy under `scratch/superpowers/`.

The same audit confirmed the safety precondition for this cleanup: the anti-hallucination
core (forbidden titles, people management, revenue ownership, unverified tools, codenames,
em-dashes, gap confessions, workforce-reduction framing, 1-page rule) is already enforced
mechanically as HARD_BLOCKs in `submission_linter.py` / `quality_checker.py` /
`verify_submission.py`. The prose contradictions are therefore repairable without touching
any actual submission protection.

## Decision

Fix the authority skeleton before any content diet. Three moves, no rule rewrites:

1. **Contradiction fixes.** Resolve or explicitly annotate every item in the audit's
   "Contradictions And Drift" list. No substantive rule is reworded, relocated, or deleted
   — only false claims, stale facts, and direct cross-file conflicts.
2. **Skill canonicalization.** Each skill gets exactly one declared canonical copy; every
   other harness directory holds a thin pointer stub of the form already proven by
   `.claude/skills/submission-no-ai-slop/SKILL.md`. Canonical homes: `.agents/skills/`
   stays canonical for `submission-no-ai-slop` (CR-098, already declared); `.codex/skills/`
   becomes canonical for `generate-submission`, `conversion-ready-pass`, and
   `networking-outreach` (the only tree carrying the full skill inventory);
   `.claude/skills/` copies become stubs.
3. **Instruction drift guard.** A new `scripts/check_instruction_drift.py` mechanically
   fails when a pointer stub regrows, a declared canonical target goes missing, a `file:///`
   absolute link appears in an instruction file, or a banned phrase from this audit's
   findings reappears — so this class of rot is caught by a check instead of the next audit.

The larger restructuring the audit recommends (shrinking root `AGENTS.md` to a thin
always-on layer, moving incident narratives to postmortems, slimming
`generate-submission/SKILL.md`) is deliberately **not** this CR. It is only safe once the
authority skeleton is unambiguous and the drift guard exists.

## Requirements

| ID | Title | Description |
|----|-------|-------------|
| `FR-290` | No live instruction contradicts canonical-file rules | Agent and instruction files carry no instruction that conflicts with root `AGENTS.md`'s canonical-file, import-stub, or status-authority rules. |
| `FR-291` | One authoritative value per shared fact | Cover-letter band, fit-threshold location, page-count gate, Core Competencies status, and the CR-107 state name each appear with exactly one current value across instruction files and the registry. |
| `FR-292` | One canonical copy per skill | Each skill declares a single canonical path; every other harness copy is a pointer stub that still loads in its harness. |
| `FR-293` | Drift guard | `scripts/check_instruction_drift.py` fails on regrown stubs, missing canonical targets, `file:///` links, and banned instruction phrases. |
| `FR-294` | `docs/AGENTS.md` subordinated | Its header names root `AGENTS.md` as the canonical always-on instruction set and links `SDD_PROCESS.md` repo-relatively. |
| `NFR-013` | Zero behavior change | CR-111 changes no submission behavior, linter rule, threshold, or pipeline code. Doc/agent-file edits only, plus the new drift-guard script and its tests. |

## Acceptance criteria

- [x] `AC-379`: No file under `.claude/agents/` instructs byte-identical edits of
      `AGENTS.md`/`CLAUDE.md`; the import-stub rule is the only stated policy.
- [x] `AC-380`: `tech-lead.md` and `product-manager.md` contain no hardcoded active-CR
      enumeration and no reference to skills that are not installed.
- [x] `AC-381`: Registry has no duplicate requirement IDs and no `WAITING_FOR_HUMAN`
      presented as a current state.
- [x] `AC-382`: All 12 items in the audit's "Contradictions And Drift" section are resolved
      or annotated in place as deferred with a reason.
- [x] `AC-383`: Exactly one cover-letter word band is the stated authoring target; the
      linter's wider WARN band is reconciled in a code comment.
- [x] `AC-384`: Root `AGENTS.md`'s File Map contains no claim contradicted by
      `verify_submission.py` or `docs/ACTIVE_WORKFLOW.md`.
- [x] `AC-385`: `AC-076` is marked superseded by `FR-195`.
- [x] `AC-386`: Exactly one canonical declaration exists per skill; every stub is ≤ 20
      lines and names its canonical target.
- [x] `AC-387`: A Claude Code session and a Codex session each load `generate-submission`,
      `conversion-ready-pass`, `networking-outreach`, and `submission-no-ai-slop` through
      their stubs. Claude Code PASS is recorded in harness-bridge session 009 R52;
      Codex PASS is recorded in R53.
- [x] `AC-388`: No skill body content exists in more than one file (diffing any stub
      against its canonical shows pointer text only).
- [x] `AC-389`: The drift guard exits nonzero on a fixture containing a regrown stub, a
      banned phrase, or a `file:///` link.
- [x] `AC-390`: The drift guard runs in the same verification path as
      `check_context_pack_freshness.py` and passes clean on `main`.
- [x] `AC-391`: `docs/AGENTS.md`'s header defers to root `AGENTS.md`; the `SDD_PROCESS.md`
      link is repo-relative.
- [ ] Full verification: `verify_submission.py` passes on one real submission folder;
      `npm test` shows no regression. `npm test` passes 47/47, but no real submission
      folder exists in this checkout, so the `verify_submission.py` portion remains
      environmentally blocked. (Guard for NFR-013.)

## Decisions confirmed for implementation

1. **Cover-letter band.** The authoring target is 250–400 words (root `AGENTS.md`).
   `docs/ACTIVE_WORKFLOW.md`'s 300–400 statement is stale as an authoring target.
   LW-001's 220–450 range remains the linter's wider WARN tolerance. The renderer's
   300–400 constants are documented as deferred because changing them would change
   submission behavior.
2. **Canonical home for the three twin skills.** `.codex/skills/` is canonical for
   `generate-submission`, `conversion-ready-pass`, and `networking-outreach` in CR-111.
   `.agents/skills/submission-no-ai-slop/` remains canonical for `submission-no-ai-slop`.
   Whether `.agents/skills/` should become the universal canonical home is deferred to
   the follow-on architecture CR.

## Not in scope

Explicitly deferred to a later CR (the audit's "CR+1"):

- Shrinking or restructuring root `AGENTS.md` (the "Layer-0" thin always-on form).
- Moving dated incident narratives out of root `AGENTS.md` or skill files into
  `docs/postmortems/` or owning CR docs.
- Slimming `generate-submission/SKILL.md`'s incident history.
- New linter rules (codename-coverage gap: CPRE/Visible/PIC/Datagroups/C3;
  `Original_JD.txt` URL-first-line check; domain-qualifier subtitle check).
- Rewriting or re-homing `docs/AGENTS.md`'s engineering-standards content (this CR only
  fixes its header, precedence line, and stale link).
- Registry rewrite or restructure beyond the specific stale rows listed above.
- Any change to `data/submissions/`, drafting behavior, thresholds, gates, or pipeline
  code paths.
- Retroactively editing historical CR docs or session handoffs (per CR-107 precedent:
  point-in-time records stay as written).
