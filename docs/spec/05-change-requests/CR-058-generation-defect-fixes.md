# CR-058: Resume/Cover-Letter Generation Defect Fixes

## Metadata
- **Epic**: Drafting Pipeline Reliability
- **Status**: Implemented (uncommitted as of 2026-07-07 — verify `git status` before assuming these are live)
- **Date**: 2026-07-07
- **Investigation**: [_bmad-output/implementation-artifacts/investigations/applyr-generation-defects-investigation.md](../../../_bmad-output/implementation-artifacts/investigations/applyr-generation-defects-investigation.md) (parent dir, shared BMAD install)

## Problem
A manual QC pass on 8 generated submissions found the same defects recurring across independently-generated folders — evidence they were generator bugs, not one-off drafting mistakes:
1. `ACC-105-PROCESS.cover_story` in `master_claims.json` had `"metrics": []` but its prose invented a "roughly half" headcount drop and "$2M" savings figure not backed by any MET code.
2. `summary_builder.py`'s resume-summary generator (the one that actually runs, per `draft_compiler.py:562-563`) hardcoded a security-backlog outcome line unconditionally — the *correctly*-gated logic in `local_draft_stages.py:858` only ran as a fallback that rarely triggered.
3. `cover_jd_needs.py`'s JD-need extraction copied raw JD lines with only shape-based filtering (length/word-count), so both bare qualification bullets ("Familiarity with...") and mid-word-truncated paragraph fragments ("...Get deep i.") leaked into cover letters verbatim.
4. Hardcoded opener-hook templates in `cover_letter_structure.py` contained literal em-dashes; the downstream cleanup (`cover_phrasing.py`, 3 sites) replaced `"—"` with `", "` without consuming the surrounding space, producing `"word , word"`.
5. `summary_builder.classify_jd_context` listed "retention" as a consumer-app signal, contradicting `data/conversion_rubric.md` R8 (which treats retention/churn as a B2B signal) — this misclassified B2B JDs that mention retention (e.g. a nonprofit donor-CRM platform) as "consumer," pulling in an ungrounded ~25,000-user scale metric.
6. The adaptive summary's scale-metric constant (`_SCALE_ENTERPRISE`/`_SCALE_CONSUMER`) was never checked against the run's actual selected bullets before use — when not grounded, `audit_text_against_bullet_corpus` correctly discarded the whole summary, silently degrading every resume to a generic fallback far more often than necessary.
7. `test_claim_preselection.py` showed disabled claims (e.g. `ACC-114`) aren't excluded by `score_all_claims`/`select_cl_claims` themselves — `claim_catalog.load_catalog()` already filters them at load time so production was never actually exposed, but there was no defense-in-depth for any future caller that builds a `ClaimCatalog` a different way.

## Decision
- `data/master_claims.json`: rewrote `ACC-105-PROCESS.cover_story` to drop the unverified figures, kept only qualitative language plus the one verified figure (7% retention, MET-04) already used elsewhere in the same story.
- `summary_builder.py`: split `_OUTCOME_2` into `_OUTCOME_2_SECURITY`/`_OUTCOME_2_DEFAULT`, gated by the existing `conversion_framing.has_security_jd_signal(jd_text)` (threaded `jd_text` through `build_jd_adaptive_summary`/`extract_summary_context`). Added `bullet_corpus`-aware grounding check (`_grounded()`) that swaps `_SCALE_ENTERPRISE`/`_SCALE_CONSUMER` for a number-free fallback phrase when the run's selected bullets don't contain the figure, instead of discarding the whole summary. Removed "retention" from `_CONSUMER_SIGNALS`.
- `cover_jd_needs.py`: added `_truncate_at_word_boundary()` and applied it everywhere paragraph/line text gets sliced (was hard byte-slicing, could cut mid-word). Added `_QUALIFICATION_BULLET_STARTS` check to `_clause_valid` (bare noun-phrase JD bullets — always invalid, safe in the shared gate). Defined `_JD_IMPERATIVE_VERB_STARTS` (extended with "advise" and ~15 other missing verbs) but deliberately did **not** add it to the shared `_clause_valid` — an earlier attempt to do so filtered out legitimate, complete JD sentences needed for proof-matching/scoring elsewhere. It's only wired into `cover_letter_structure._valid_opener_context_phrase`, the one call site that inserts raw text directly into rendered prose.
- `cover_letter_structure.py`: removed literal em-dashes from 4 hardcoded hook templates in `_need_based_hook`, replaced with proper punctuation.
- `cover_phrasing.py`: fixed 3 sites doing `.replace("—", ", ")` → `re.sub(r"\s*(?:—|--)\s*", ", ", text)` (consumes surrounding whitespace).
- `claim_catalog.py`: added `disabled: bool = False` field to `ClaimRecord`. `jd_tailoring.score_all_claims`: added a defense-in-depth skip for `rec.disabled`.

## Acceptance Criteria
- All existing unit tests pass (`test_summary_builder.py` 18/18, `test_claim_preselection.py` 7/7, `test_cover_voice.py`/`test_cover_word_padding.py` no regressions — 2 pre-existing failures in `test_cover_everbridge.py`/`test_cover_splash_golden.py` are `FileNotFoundError` on missing fixture JDs, unrelated to this change).
- Live end-to-end regeneration (`draft_compiler.run()`, `DRAFT_MODE=compose`) against Donorbox's JD (non-security control) no longer produces the stray-space punctuation artifact, the JD-leak fragment, or reflexive security framing; rubric self-score moved 80.5 → 86.5/100 across the fix rounds.
- Same regeneration against Avetta's JD (security/compliance-relevant control) moved 59.8 → 66.9/100 after the grounding fix, confirming the audit-rejection→generic-fallback loop was the dominant quality ceiling, not a hard defect.

## Out of Scope
- Whether Avetta's JD should trigger security framing at all — `has_security_jd_signal`'s regex is narrow (matches "vulnerability"/"cybersecurity"/"security backlog", not bare "compliance"/"risk") and Avetta's JD uses the latter. Deliberately not loosened this session: it's a shared regex used elsewhere (`local_draft_stages.py`, `defensive_summary_violations`) that wasn't fully audited, and one over-broadening mistake already happened this session (see Decision above, `_clause_valid`).
- The "exp" (bullet-content) half of the pipeline's internal rubric score, which capped both test runs below 90 — untouched, unexplored this session.
- Whether `DRAFT_MODE=compose` (the actual default, routes through `claim_composer.py`) or `legacy_llm` (the alternate path in `bullet_generation.py`, better-scoped for small local LLMs) is the one actually producing bullet content day-to-day — flagged as an open question for CR-059.
