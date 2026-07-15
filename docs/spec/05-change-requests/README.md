# Change Requests Index

**Active runtime:** [docs/ACTIVE_WORKFLOW.md](../../ACTIVE_WORKFLOW.md)

## How to use

| Need | Read |
|------|------|
| Current scout/evaluate/draft behavior | `ACTIVE_WORKFLOW.md`, `FEAT-001`–`004`, `.agent/rules/pipeline_env.md` |
| Implement a new feature | New `CR-*` + registry + FEAT + traceability |
| Historical context | Closed CR below (audit only) |

## Active / recent CRs (maintainers)

| CR | Topic | Status |
|----|-------|--------|
| CR-ARCH-000–006 | Server/process refactor | Implemented |
| CR-027 | Industry blocklist gate | Implemented |
| CR-028 | Keywords / anchors | Implemented |
| CR-031 | Draft quality gates | Implemented |
| CR-026 | Sync evaluate visibility | Implemented |
| CR-035 | Fit scoring hardening | Implemented |
| CR-036 | Solo PM trap + years policy lock | Implemented |
| CR-037 | Required domain experience gate | Implemented |
| CR-038 | B2C role openness | Implemented |
| CR-039 | Transferable skills over domain gate | Implemented |
| CR-040 | Theme primary claims (resume/cover numeric alignment) | Implemented |
| CR-041 | ATS watchlist — no example.json at runtime | Implemented |
| CR-042 | Resume quality enforcement (strict gate + retry + fleet proof) | Implemented |
| CR-043 | Deterministic cover letter voice | Implemented |
| CR-044–052 | *(table not maintained for this range — see individual `CR-0XX-*.md` files in this directory)* | `[VERIFY]` |
| CR-053 | Fit rubric overhaul — evidence-tiered scoring, replaces holistic LLM score | **Partial** — Epics 1–3 + SDD closeout done; calibration/dedup open — [epics](../08-implementation/CR-053-fit-rubric-overhaul-epics.md), [spec](CR-053-fit-rubric-overhaul.md) |
| CR-054 | Pipeline integrity & failure transparency (silent-success-on-failed-draft bug) | **Partial** — Epic 1 done — [spec](CR-054-pipeline-integrity.md) |
| CR-055 | Collection gate accuracy (years-gate regex bug, title-blocklist false positives) | **Partial** — Epics 1–2 done — [spec](CR-055-collection-gate-accuracy.md) |
| CR-058 | Generation defect fixes — fabricated metrics, JD-text leakage, punctuation corruption, misclassification, grounding audit | Implemented (uncommitted) — [spec](CR-058-generation-defect-fixes.md) |
| CR-059 | Local LLM tuning loop — task-aware prompting/routing for the small local models the drafting pipeline actually calls | **Not started** — [handoff + round tracker](../08-implementation/CR-059-local-llm-tuning-loop.md) |
| CR-060 | Conversational manual-JD triage — chat-based fit review/re-score before drafting, replaces one-shot Cursor-paste workflow | **Not started** — roadmap item for eventual public/cloud release — [spec](CR-060-manual-jd-chat-triage.md) |
| CR-061 | AI-Native trigger gap fix — resume PROJECTS section pruning order, missing cover-letter mechanism, metric-guard exception, projects_catalog.json em-dash cleanup | Implemented — [spec](CR-061-ai-native-trigger-gap-fix.md) |
| CR-062 | Local-rewrite harness (Deterministic-Minimal-LLM) — sentence-naturalization local-LLM call at 3 sites (bullets, summary, cover letter), `DRAFT_MODE=local_rewrite`, phase 1 of the local-LLM builder redesign | Implemented (opt-in, not yet default) — [spec](CR-062-local-rewrite-harness.md) |
| CR-063 | JD theme-extraction & claim-selection test-and-iterate loop — measures `THEME_KEYWORDS`/`score_claim_for_jd` selection accuracy against a 16-JD human-verified eval set before Hybrid Anchor + Polish (CR-062 phase 2) gets built | **Diagnostic phase done** — both proposed fallbacks (embeddings, LLM-mode profiling) ruled out with real measured data; root cause pinned to `score_claim_for_jd`'s formula; fix handed off as CR-064 — [spec](CR-063-jd-theme-claim-selection-loop.md), [tracker](../08-implementation/CR-063-jd-theme-claim-selection-loop-tracker.md), [eval set](../../reports/jd-theme-claim-eval-set.md) |
| CR-064 | Claim-score formula rework — dedup + rarity weighting + DCG breadth dampener for `score_claim_for_jd` (CR-063's root-caused defect) | **Closed partial** — all 3 mechanisms implemented and verified individually, but `ACC-105-EXECUTION`'s cross-JD top-5 over-representation (the CR's target metric) did not move (10/14 before and after) — [spec](CR-064-claim-score-formula-rework.md), [tracker](../08-implementation/CR-064-claim-score-formula-rework-tracker.md) |
| CR-065 | JD-profile extraction diagnostic — direct test of whether `build_jd_profile_deterministic`'s `keywords`/`requirements`/`priority_themes` are too generic/non-discriminating to support correct downstream claim ranking, now that 3 CR-064 ranking-formula mechanisms have failed to move the metric | **Diagnostic phase done** — finding (a): `keywords`' alphabetical selection is the dominant, universal (13/13) driver; `requirements`' boilerplate-capture is a real secondary, JD-layout-dependent contributor (4/13); fix handed off as CR-066 — [spec](CR-065-jd-profile-extraction-diagnostic.md), [tracker](../08-implementation/CR-065-jd-profile-extraction-diagnostic-tracker.md) |
| CR-066 | JD-profile `keywords` fix — change `build_jd_profile_deterministic`'s `keywords` selection from alphabetical to frequency-sorted (CR-065's root-caused, cleanly-isolated defect); first production code change in this investigation arc | **Complete** — Security CLEAR, QA PASS, EM-approved. `ACC-105-EXECUTION` top-5 count dropped 9/12 -> 5/12 as expected, aggregate should-surface hit rate improved 10/34 -> 11/34, zero regressions, pytest 28F/195P/1S; two non-blocking follow-ups logged (weak `test_cutoff_is_twelve` fixture; inert 5th `.keywords` consumer in `summary_builder.py`) — [spec](CR-066-jd-profile-keywords-frequency-fix.md), [tracker](../08-implementation/CR-066-jd-profile-keywords-frequency-fix-tracker.md) |
| CR-067 | `requirements` boilerplate-capture diagnostic — re-investigated CR-065 Part D's `requirements` finding directly against real JD text, no subagent pipeline support available (session rate-limited) | **Diagnostic phase done, no fix shipped** — found 3 independent, compounding root causes (heading-phrase coverage gap, `_NEXT_SECTION_RE`'s Title-Case/no-separator blindness, 120-char line-length cap silently dropping long real bullets), not the 1-2 CR-065 guessed at; corrected a CR-065 mischaracterization of Covideo's failure mode; in-progress partial fix code reverted rather than shipped without independent review — [spec](CR-067-requirements-section-extraction-diagnostic.md) |

**Note:** CR-053/054/055 supersede the scoring policy set by CR-039 (transferable-skills-over-domain
gate) — domain fit is being reinstated as a bounded scored signal rather than ignored. If CR-039's
text and the CR-053 doc disagree, CR-053 wins until this table is updated to mark CR-039 superseded.

## Archive (implemented — do not treat as daily instructions)

CR-001 through CR-025, CR-021 (detail), CR-024, etc. remain for audit traceability. If code and an old CR disagree, **code + ACTIVE_WORKFLOW + registry** win.
