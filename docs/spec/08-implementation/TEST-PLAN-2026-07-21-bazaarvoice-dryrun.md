# Test Plan — Full Pipeline Dry Run (Bazaarvoice, archive practice)

**Purpose**: exercise the entire `generate-submission` Stage 0-3 process, plus everything hardened in
the 2026-07-21 review session, against a real archived JD — as a completely fresh session would, with
no memory of today's conversation. This is a process test, not a real application: output stays
`.md`-only in `data/authored_drafts/bazaarvoice_test/` per the skill's archive-practice scope, never
in `data/submissions/`.

**JD under test**: `data/archive/submissions/bazaarvoice/Original_JD.txt` (Senior Product Manager,
Content Moderation, Bazaarvoice). Chosen deliberately because it stresses three things at once:
- Heavy ML/AI language ("leverage advanced ML/AI," "Partner with Data Science to evolve models,"
  "AI-generated explanations") — a real test of whether the process holds the line on workExperience.md
  §1.3's "NOT an AI/ML Product Lead" exclusion zone instead of drifting into implied ML ownership.
- A genuine domain-anchor gap: content moderation / trust & safety / fraud detection has no direct
  anchor in workExperience.md or master_claims.json tags. Tests whether Stage 0 step 2 actually flags
  it and whether Stage 1 step 3 finds an honest transferable-skill bridge (compliance/privacy workflows,
  security backlog triage) rather than overclaiming or silently dropping it.
- An explicit, literal "B2B SaaS" mention in its own requirements section — a clean control case:
  the resume summary SHOULD use B2B SaaS framing here, and `LW-013` should NOT fire. If it does fire,
  that is a bug in the check, not a real finding.

## Part A — Authoring run (Stage 0 through Stage 3, archive-practice scope)

Run the full `generate-submission` skill against this one JD as if it were a real batch of one company:

1. Stage 0: DB check (this is archive practice, so the DB-status check does not apply — confirm you
   correctly recognize that per the skill's own scope note, rather than querying `jobagent.sqlite`),
   bucket split (culture/responsibilities/requirements, required vs. preferred), anchor-check every
   required item including the compound-line splitting rule, stage/size signal, thin-JD flag, Tier
   classification. Persist `stage0_fit_gate.json` in the output folder.
2. Stage 1: author Resume.md and CoverLetter.md from ground truth only (`workExperience.md`,
   `master_claims.json` tags, `data/aiProjects.md` if genuinely relevant — this JD does not ask for
   hands-on AI tooling, so do not force an AI paragraph in just because it exists as an option).
   Explicitly resolve the content-moderation/trust-and-safety gap flagged in Stage 0 with a named
   transferable-skill bridge, not a confession.
   Run `lint_folder` before considering Stage 1 done, per the skill's own step 9.
3. Stage 3 (archive scope): leave the output in `data/authored_drafts/bazaarvoice_test/` as `.md` only
   — no PDF compile, no `draft_manifest.json`, no cheat sheet, per the skill's stated archive-practice
   exemption.

**Report, in addition to the documents themselves:**
- Every judgment call you made and why (which ACCs you selected and rejected, and specifically whether
  you considered and rejected using ACC-107 compliance/privacy or ACC-103 security-backlog-triage as
  the trust-and-safety bridge, or found something else).
- Any point where the SKILL.md or CLAUDE.md instructions were ambiguous, contradictory, or required you
  to guess.
- Confirm explicitly: did you avoid claiming ML model ownership, training, or engineering anywhere?
  Quote the exact sentence that engages the ML/AI-heavy JD language, if any.
- Confirm explicitly: does the resume summary use "B2B SaaS" framing, and did you check that against
  the JD's own literal text before writing it?
- Run every check in "Required Verification Before You're Done" (CLAUDE.md) that applies to a
  `.md`-only archive draft (lint, `check_resume`, `check_and_repair_cover_letter`, unapproved-metrics
  sweep) and paste the raw output.

## Part B — Independent Stage 2 review (separate session, no authoring context)

This must run as a genuinely separate agent invocation with no visibility into Part A's reasoning —
only given: `Original_JD.txt`, the authored `Resume.md`/`CoverLetter.md`, and `stage0_fit_gate.json`.
Perform the six-point Stage 2 review exactly as SKILL.md defines it (rubric score, mechanical checks,
attribution fidelity, required-item fidelity — including whether the ML/AI and trust-and-safety gaps
were engaged honestly — repeated-device check, restatement/three-sentence test). Report findings in
the six-point scope only; anything outside it gets named as a side observation, not acted on.

## Part C — Process-cohesion audit (separate, no context, whole-repo scope)

Independent of Parts A/B. Answer: for every mechanical check that exists in `submission_linter.py`,
`quality_checker.py`, and `approved_metrics.py`, is it actually reachable from the documented
`Required Verification` commands in `CLAUDE.md`/`AGENTS.md` and `SKILL.md`'s Stage 2 code sample — or
does it exist but never get called (the `check_and_repair_cover_letter`/dead-`find_unapproved_metrics`-
import failure class from earlier this project)? Also check `CLAUDE.md` and `AGENTS.md` are still
byte-identical, and whether `tone_guard.py` (referenced by name in CLAUDE.md's R-011 note) is actually
invoked anywhere in the live `generate-submission` path or only in the retired `draft_compiler.py`
pipeline.
