# Prompt for Gemini / Cursor — Full Stage 1 re-author pass on existing submissions

Paste this directly into the session, after telling it which companies from the list at the bottom
are its share (Jason will fill that in).

---

You are re-authoring existing real submissions in `data/submissions/` through the current, fully
hardened process — not drafting new ones. This is the same task Claude Code just ran end-to-end on
`data/submissions/dataminr/` as a diagnostic pilot on 2026-08-04. Read that folder's current
`Resume.md`, `CoverLetter.md`, and `draft_manifest.json` (its `diagnostic_pilot_notes` field) first as
your worked example of what "actually doing this" looks like, before starting on your assigned
companies.

## Why this prompt is unusually explicit about not skipping steps

A prior cross-harness run on this exact repo substituted a templated, plausible-looking rubric score
instead of actually reading the document against `conversion_rubric.md` — 8 submissions in one batch
landed with byte-identical rubric sub-scores across 8 different companies. It was caught by
`scripts/verify_submission.py --audit`'s duplicate-score detector, not by anyone noticing the scores
looked fake. This is already documented as a known failure mode in
`.claude/skills/generate-submission/SKILL.md`'s "Cross-Harness Operating Rules" section, rule 4:
**"Say 'can't,' don't fake 'did.'"** If any step below genuinely cannot be completed — context limits,
a tool unavailable, ground truth insufficient — say so explicitly in your report. Do not substitute a
plausible-looking result. `--audit` will be run against every company you touch before this is
accepted as done, and it will catch a repeat of the exact same failure.

## What "actually doing this" means, per company

1. Read the company's current `Resume.md`, `CoverLetter.md`, `stage0_fit_gate.json`,
   `Original_JD.txt`, and `draft_manifest.json` in full before changing anything. Back up the current
   `Resume.md`/`CoverLetter.md` (e.g. `.before` suffix) so a real before/after exists — delete the
   backups only after reporting the comparison.
2. Reuse `stage0_fit_gate.json` — do not re-derive Stage 0.
3. Run the **full** Stage 1 process from `.claude/skills/generate-submission/SKILL.md`: read
   `workExperience.md` and `master_claims_tags_only.json` fresh, map every required/preferred/
   responsibilities item to its single strongest available evidence (not the first thing that clears
   the bar), write every sentence fresh (do not lightly edit the old wording), resolve every flag from
   **both** `scripts/check_ground_truth_coverage.py` **and** `scripts/jd_term_extractor.py` (the second
   one is new as of today — if a run predates this, it will not know to check it; you must run it
   explicitly). A flagged term either gets worked into a bullet naturally, in context, or you document
   why it genuinely doesn't belong — never force one into a bare list just to pass the check.
4. Run `lint_folder` before calling Stage 1 done (`LW-009-PAIR`, `LW-008-PAIR`, every document's
   `blocks` list empty) — fix what it finds and re-run until clean, don't hand-wave a warning.
5. Stage 2: score the rubric **by hand**, reading the actual document against
   `data/conversion_rubric.md`, one evidence citation per criterion. Compile PDFs
   (`scripts/compile_single.py`), run `scripts/verify_submission.py`, then
   `scripts/verify_submission.py --audit` — both must exit clean.
6. Run the no-ai-slop Detect pass (`.claude/skills/submission-no-ai-slop/SKILL.md`) on the two final
   documents. Surface findings; don't auto-edit past what's obviously needed.
7. Report, per company: what changed and why (tie every change to a real `ACC-`/`MET-` ID or a
   specific mechanical flag it resolved), old rubric score vs. new, old `jd_literal_term_gaps` vs. new,
   any flag you deliberately left unresolved and why, and confirmation `--audit` passed clean.

## Explicitly out of scope

- Don't touch `dataminr` — already done.
- Don't touch any company not on your assigned list below.
- Don't invent new claims. Every change must trace to `workExperience.md`/`master_claims.json` or a
  named mechanical check.

## Your assigned companies

*(Jason fills this in before sending — do not start without a specific list.)*
