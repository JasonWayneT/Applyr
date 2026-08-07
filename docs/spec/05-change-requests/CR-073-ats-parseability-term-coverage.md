# CR-073: ATS Parseability Verification & JD-Specific Term-Coverage Gate

## Metadata
- **Status**: Implemented (2026-08-04)
- **Date**: 2026-08-04
- **Related requirements**: None formally registered — originated from a 2026-08-04 research brainstorm on ATS/AI screening failure modes (parsing, ranking, disqualification, timing), cross-checked against the actual pipeline before scoping
- **Tracker**: [epics](../08-implementation/CR-073-ats-parseability-term-coverage-epics.md)

## Problem
A research pass on ATS parsing/ranking failure modes (vendor docs for Greenhouse/Lever/SAP SuccessFactors/Eightfold, HBS/Accenture "Hidden Workers" study, Jobscan's published methodology) was checked against Applyr's actual generation pipeline rather than accepted at face value. Most proposed mitigations turned out to already be solved by the existing architecture (Playwright HTML→PDF produces a genuine text layer — no Canva-style vector-export risk; single font/column already enforced; a static keyword-coverage check already runs in `verify_submission.py`; Stage 0 of `generate-submission` already does eligibility gating more rigorously than proposed). Two gaps survived the cross-check as real and unaddressed:

1. ~~Unverified table-parseability risk.~~ **Checked 2026-08-04, not real for current output.** The concern was that `## CORE COMPETENCIES` renders as a genuine HTML `<table>`, inferred from a comment in `compile_single.py` referencing "CORE COMPETENCIES rows" in a pipe-table regex. Checked against all 12 real submissions in `data/submissions/`: none use pipe-delimited rows — the actual generator (`build_skills_section`, `local_draft_stages.py`, FR-195) outputs bold-label + comma-separated text, never a Markdown table. `pdftotext` against a real compiled `Resume.pdf` confirms clean, correctly-ordered extraction. That regex is dead code guarding a format nothing currently generates. No rendering change needed — see Decision below for the residual (optional) value.
2. **No per-JD literal hard-skill/title coverage check.** `verify_submission.py`'s existing `jd_keyword_coverage` check runs against a static, generic 14-word list in `candidate_preferences.json` (saas, b2b, platform, agile...) applied identically to every application — not an extraction of *that specific JD's* required hard skills, tools, and title phrasing. Jobscan's own published methodology weights exactly this (hard skills, job title, other keywords) as the primary driver of rule-based/Boolean ATS filters, which the current generic list doesn't test for.

## Decision
1. ~~Add a `pdftotext`-based extraction check...~~ **Resolved by direct check, no live risk found (see Problem above).** Residual decision: add a small, cheap `pdftotext`-based reading-order check to `verify_submission.py` anyway, as a standing regression guard in case the dead pipe-table code path is ever reactivated — near-zero marginal cost since `pdftotext` is already available and the check is a few lines. Jason's call whether it's worth the receipt-field noise for a risk that isn't currently live.
2. ~~If Story 1 finds real scrambling, replace the pipe-table rendering...~~ **Not needed — no scrambling found, no table markup exists in current output.**
3. Build a JD-specific term extractor: pulls candidate hard-skill/tool/title terms from `Original_JD.txt` (Title-Case multi-word phrases, acronyms, matches against `data/skills_catalog.json`'s known-tool list, the JD's own stated title line).
4. Cross-reference extracted terms against what's genuinely true for Jason (`skills_catalog.json` / `master_claims_tags_only.json` / `workExperience.md`) — only ever flag a term that is JD-required **and** real **and** missing from the draft. Never surface a term Jason can't actually claim.
5. Wire the result into `verify_submission.py`'s receipt as a new `jd_literal_term_gaps` field — WARN-level, informational, same posture as the existing generic keyword check. Does not replace rubric scoring or `check_ground_truth_coverage.py` (which flags unused *true claims*, not unmatched *JD literal terms* — a different failure mode).

## Acceptance criteria
| ID | Criterion |
|----|-----------|
| AC1 | `verify_submission.py` reports whether Resume.pdf's CORE COMPETENCIES content extracts in correct reading order, tested against a real compiled submission |
| AC2 | If scrambling is found, the table rendering is replaced and re-verified clean; if not found, no rendering change is made |
| AC3 | JD term extractor produces a real, reviewable term list against at least 2 existing `data/submissions/*/Original_JD.txt` files, with a false-positive rate low enough to be useful (spot-checked, not just run) |
| AC4 | Extracted terms are filtered to only those verifiably true of Jason before ever being surfaced — no fabrication risk introduced |
| AC5 | `jd_literal_term_gaps` appears in `verification_receipt.json` for a real submission and is legible enough to act on |

## Out of scope
- Outcome/rejection-speed logging (Stage 3 idea from the same research pass) — deferred pending Jason's call on whether current DB data supports it.
- Timing/queue-position tactics (Stage 4 of the research) — belongs to the scouting/ingestion pipeline (CR-072), not resume/cover-letter drafting.
- Native `.docx` generation pipeline — solves a vector-text-export risk this architecture's Playwright-based PDF path doesn't have.
- Making the new checks hard blocks — both ship as WARN-level until real-world false-positive rate is known.
