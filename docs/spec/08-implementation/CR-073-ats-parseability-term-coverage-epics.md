---
status: implemented
created: 2026-08-04
related: none (net-new verification checks, no schema/API changes)
contains: CR-073 (ATS Parseability Verification & JD-Specific Term-Coverage Gate)
---

# CR-073 — ATS Parseability & Term-Coverage Hardening: Epics & Stories

**Handoff doc, one change request.** Resumable plan for CR-073 — no open decisions left, the spec
([CR-073](../05-change-requests/CR-073-ats-parseability-term-coverage.md)) is final. A new session can pick
up at the first unchecked story with no other context needed beyond that spec doc and this file.

Epic 1 is independent of Epic 2 — either can go first. Epic 1 is empirical and cheap (resolves a real
unknown before deciding whether to touch rendering); do it first so Epic 2 isn't started under a false
assumption about what's already safe.

## Epic 1 — Table reading-order verification

Resolves whether the CORE COMPETENCIES `<table>` risk is real, with actual extracted text, not
assumption.

- [x] **Story 1.1 + 1.2 (combined, done 2026-08-04)**: Ran `pdftotext -layout` directly against a real
  compiled `data/submissions/accertify/Resume.pdf`. **Finding: no live risk.** Checked all 12 real
  submission folders' `Resume.md` — none use pipe-delimited CORE COMPETENCIES rows; the actual generator
  (`build_skills_section`, `local_draft_stages.py`, FR-195) outputs bold-label + comma-separated text, so
  no `<table>` element exists in current compiled output. Extraction came back clean, correct top-to-bottom
  order. The pipe-table regex in `compile_single.py` is dead code for a format nothing currently generates.
  CR-073 spec's Problem/Decision sections corrected to reflect this rather than left standing on a wrong
  premise.
- [ ] **Story 1.3**: Not needed — no scrambling found, no table markup exists in current output. Skipped.
- [x] **Story 1.4 (done 2026-08-04, Jason confirmed: add the guard anyway)**: Added `_check_reading_order()`
  to `scripts/verify_submission.py` — confirms `##` headings extract via `pdftotext -layout` in the same
  relative order as the source Markdown. Wired into `verify_one()`'s receipt as `reading_order`, WARN-only
  (excluded from `mechanically_verified`). Verified against a real submission
  (`data/submissions/accertify`): `checked: true`, all 4 headings found in order, `ok: true`.

## Epic 2 — JD-specific literal hard-skill/title coverage gate

Depends on nothing in Epic 1. Replaces the generic static-list keyword check with a real per-JD
extraction, per CR-073's Decision points 3-5.

- [x] **Story 2.1 + 2.2 (combined, done 2026-08-04)**: Built `scripts/jd_term_extractor.py`. Design
  differs from the original plan in one deliberate way: instead of freely extracting candidate terms from
  raw JD prose and then filtering by ground truth (noisy — company names, boilerplate, false acronyms),
  it inverts the direction — builds the "true vocabulary" set directly from `data/skills_catalog.json`'s
  flat tool list + `data/master_claims_tags_only.json`'s claim tags (excluding compound `:`/`/` labels),
  then checks which of *those* terms appear in the JD. Fabrication-safety (AC4) is structural, not a
  filter step: every candidate term originates from a ground-truth source, so nothing not genuinely true
  of Jason can ever be surfaced.
- [x] **Story 2.3 (done 2026-08-04)**: `find_jd_term_gaps()` diffs the JD-required subset against
  `Resume.md` + `CoverLetter.md` text (whole-phrase, case-insensitive, word-boundary-aware matching).
- [x] **Story 2.4 (done 2026-08-04)**: Tested against `accertify`, `dataminr`, `acuitymd`. First pass was
  noisy — claim tags mixed real hard-skill/domain nouns (SLA, Product Lifecycle, Vulnerability Management,
  Go-to-Market) with generic soft-skill adjectives (Collaboration, Leadership, Velocity, Cross-functional)
  that inflated false-positive gaps on every JD regardless of real overlap. Added a small, hand-curated
  `_GENERIC_SOFT_SKILL_TERMS` exclusion set (mirrors Jobscan's own hard-skill-vs-soft-skill split) and
  re-verified: accertify dropped from 6 noisy gaps to 2 real ones (Product Lifecycle, SLA); dataminr's 6
  gaps are all genuine (Gemini, Go-to-Market, Privacy, Product Adoption, Product Lifecycle, Vulnerability
  Management). AC3 met.
- [x] **Story 2.5 (done 2026-08-04)**: Wired into `verify_submission.py`'s receipt as
  `jd_literal_term_gaps`, alongside the existing generic `jd_keyword_coverage` field. WARN-level — not
  included in `mechanically_verified`. Ran end-to-end against `data/submissions/dataminr`: field is
  legible, `mechanically_verified` unaffected. AC5 met.

## Definition of Done for the whole CR

All boxes above checked, plus: re-read CR-073's Acceptance Criteria (1-5) and confirm each one directly
against real output (`verification_receipt.json` for an actual submission), not just against story
checkboxes. Update CR-073's status line to "Implemented" and add its row to
`docs/spec/05-change-requests/README.md` only after that direct check.

**Follow-up fix, same day (Jason-prompted):** asked whether the same keyword-coverage logic should apply
to the cover letter too. Answer was no — the ATS mechanisms this check targets (Jobscan match-rate, SAP
Boolean search) parse and score the resume, not the cover letter, and treating the letter as a
keyword-coverage target risks colliding with `LW-011`/`LW-012` (JD-paraphrase hook, assertion-of-fit
overclaim). But the question surfaced a real bug: `find_jd_term_gaps()` originally pooled resume + cover
letter into one coverage check, so a term mentioned only in the cover letter's prose was silently credited
as "covered" — masking a real resume-side gap in the one document that's actually ATS-parsed. Fixed:
output split into `missing_from_resume` (the primary, actionable signal) and `cover_letter_only_mentions`
(informational only, never counts as coverage). Verified against dataminr: "Claude" was previously masked
as covered (only in the cover letter); now correctly surfaces under `missing_from_resume` with
`cover_letter_only_mentions: ["Claude"]` alongside it. Re-ran all 14 real folders — still MECHANICALLY
CLEAN, zero regressions.

**Done — 2026-08-04.** Acceptance criteria re-checked directly against real receipts, not just story
checkboxes:

1. AC1 — `reading_order` field confirmed clean/in-order against `data/submissions/accertify`.
2. AC2 — no scrambling found, no rendering change made (correctly not needed).
3. AC3 — `jd_literal_term_gaps` spot-checked against 3 real JDs (accertify, dataminr, acuitymd); tuned
   once to remove generic soft-skill false positives.
4. AC4 — structural by construction: every surfaced term originates only from
   `skills_catalog.json`/`master_claims_tags_only.json`, never from free JD-text extraction.
5. AC5 — confirmed legible in `data/submissions/dataminr/verification_receipt.json`.

Ran `verify_submission.py` against all 14 real folders in `data/submissions/` — all report MECHANICALLY
CLEAN, no crashes, no regressions to `mechanically_verified` from either new field. CR-073 spec's status
line and the registry row in `docs/spec/05-change-requests/README.md` both updated to "Implemented."
