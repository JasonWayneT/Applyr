# Cursor Handoff: CR-114 Stage 0

Date: 2026-09-17. Owner for next implementation pass: Cursor, running directly in this Applyr checkout. This is a handoff, not a declaration that Stage 0 is finished.

## Mission

Make Stage 0 accurate through a meaningful batch without depending on Groq/Gemini free-tier capacity. Improve local NLP and evidence matching from **human-adjudicated** corrections so subscription-harness use falls over time. The harness is a bounded fallback for uncertain extraction and uncertain evidence judgment, not a training-label authority. Stage 1-3 changes are out of scope.

Read `AGENTS.md`, `docs/ACTIVE_WORKFLOW.md`, `docs/SDD_PROCESS.md`, `docs/spec/05-change-requests/CR-114-stage0-local-learning-and-bounded-fallback.md`, and **Section 18** of `docs/reports/stage0-architecture-research-report.md` first. Section 18 supersedes the report's older offline-only harness plan. Follow `applyr-team-pipeline` roles and record decisions in the local `pipeline-log.md`. Use the CR stories in order, one bounded change at a time. The older `SESSION-HANDOFF-2026-09-17-stage0-metis-division.md` is a historical routing record, not the current implementation plan.

## Starting State: Do Not Lose This Work

HEAD is `8e3064a` (`docs: make Stage 0 harness a bounded runtime fallback`). The checkout is intentionally dirty. Do not reset, stash, or discard it. At handoff, modified files are `.gitignore`, `CHANGELOG.md`, `README.md`, `docs/spec/02-requirements-registry.md`, `docs/spec/03-feature-specs/FEAT-002-evaluation.md`, `docs/spec/06-traceability/traceability-matrix.md`, `scripts/build_stage0_fit_gate.py`, `scripts/retrain_stage0.py`, `scripts/stage0_confirmations.py`, and `scripts/test_stage0_confirmations.py`. Untracked files are CR-114, this handoff, the historical Metis handoff, and `scripts/test_retrain_stage0.py`. Re-run `git status --short` before editing because Jason or another agent may have changed the tree since this snapshot.

Two uncommitted slices are already present:

1. Review Center false-positive fix: a model-flagged confirmation must be a JD-grounded named tool. Generic traits such as "critical thinking" do not create a skill card. Code: `stage0_confirmations.py`, `build_stage0_fit_gate.py`, `test_stage0_confirmations.py`. Inspect for false negatives on genuine tools before accepting.
2. CR-114 Story 1 safety boundary: extraction fallback no longer appends raw model answers to `training_data_feedback.csv`; retraining ignores that legacy file, accepts only `training_data_approved.csv` with reviewer provenance, splits by company before training, writes a candidate/report, and requires a candidate-hash-bound 30-JD replay report for explicit promotion. Code: `build_stage0_fit_gate.py`, `retrain_stage0.py`, `test_retrain_stage0.py`. Story 1 is **unchecked pending independent QA**. Audit its provenance and promotion validation; a self-authored JSON report is not, by itself, independent evidence.

No model was promoted. `data/stage0_classifier.pkl` is tracked and unchanged. Generated candidate artifacts were removed. Do not commit private `data/` rows, JDs, WE excerpts, SQLite files, credentials, or generated models. `.gitignore` now excludes candidate and rollback model artifacts. The ignored `pipeline-log.md` is a local work record, not a commit target.

## Evidence Already Collected

- Agy's narrow audit found unreviewed API labels were double-weighted before a random line split, contaminating training and leaking into evaluation. That direct write and old retraining path have been changed locally.
- New candidate trained from 3,627 base rows and zero approved corrections: 71.7% accuracy and 32.5% coverage at confidence 0.65 on 721 lines from 48 held-out companies. The live model scored 82.5% / 58.4% on the same slice, but its historic training lineage may overlap the slice. Do **not** treat this as an unbiased comparison or promote the candidate. Details are in CR-114.
- Focused tests after the import fix: `python -m unittest scripts.test_retrain_stage0 -q` passed 5; `python -m unittest scripts.test_retrain_stage0 scripts.test_cr112_stage0_extraction_review.TestExtractSectionsNlpDumpSites scripts.test_stage0_confirmations -q` passed 29. A larger earlier run completed 79 tests with one import error from the original test-file snapshot; that import was fixed, but the full suite has not been rerun. `git diff --check` passed. `npm test` and `npm run build` have **not** been run on these edits.
- Metis through claudexor could route Agy, but a broad Claude audit timed out at 600 seconds and Cursor preflight was unroutable on that bridge. Direct Cursor work does not require the Metis bridge. Do not burn Claude/Agy/Factory credits or silently substitute a paid API. If direct Cursor is working, keep all implementation in Cursor.

## Next Work, In Order

1. **Review and checkpoint the existing diff.** Run focused tests, then `npm test` and `npm run build`; inspect all staged changes and privacy implications. Fix issues. Only independent QA may check Story 1. If green, make a clearly named baseline commit of the reviewed Stage 0 safety work. Keep the Review Center fix in a separate commit if practical; otherwise state its inclusion in the commit message. Never stage everything blindly.
2. **Build and test the Stage 0-only subscription adapter (Story 2).** Discover the actual claudexor 3.12.1 CLI/schema result contract with a *small, capped* real-schema smoke using Cursor's intended subscription profile. Give extraction and evidence distinct prompts/schemas. Enforce profile, wall-clock and per-batch call ceilings, exact item binding, cache/version keys, privacy, and `subscription_minutes` separate from `api_cents`. Failed, invalid, or exhausted calls must lead to explicit resumable review. No Groq/Gemini spillover. Unit tests should mock process execution; live smoke is deliberately small.
3. **Connect uncertain extraction (Story 3).** Preserve confident NLP behavior and every uncertain line. Reuse the CR-112 unresolved/review path on adapter failure. Test partial mappings, malformed JSON, timeout, cache hit, cap exhausted, and no lost lines.
4. **Build the local evidence matcher in shadow (Story 4), then connect uncertain evidence to the bounded adapter (Story 5).** Use only reviewed aliases/cases. Matchers abstain on uncertainty and cannot issue a terminal HARD/Skip without the existing safety policy. Preserve Stage 0 checkpoint/resume. Compare to adjudicated gold before granting any new authority.
5. **Review Center and release evidence (Stories 6-7).** Expose decision basis, JD/evidence excerpt, uncertainty, and correction action without making generic traits into cards. Inventory all other Stage 0 hosted calls. Run 5-10 archived JD actual-schema smoke, then a timed, redacted, adjudicated 30-JD replay. Measure extraction/evidence errors, false skips, abstentions, review load, calls, time, and both cost units. Set numeric caps from evidence. Keep the production switch off until the gates pass.

If a representative adjudicated corpus or a verified subscription route is unavailable, continue only with code/tests that can be safely verified. Do not manufacture gold labels, mark the remaining stories complete, or claim the production cutover. Write the exact blocker and the smallest required human decision in the final handoff.

## Commit And Exit Contract

- Commit only reviewed, passing, scoped work. Prefer one commit per story; include requirement IDs and test evidence in commit messages or the final report. Never commit generated `*.pkl`, private `data/`, `.metis/`, `.claudexor/`, or `pipeline-log.md`.
- Update CR-114 checkboxes, requirements/traceability, `CHANGELOG.md`, and `README.md` for actual behavior only. Do not check a story just because its code exists. Security review is required for PII, subprocess, cache, filesystem, SQLite, or settings changes. QA reruns tests; final reviewer compares full diff to the CR.
- Before any production enablement, show the locked corpus provenance, replay command and results, budget/latency telemetry, zero unreviewed false skips, no silent line loss, rollback procedure, and the unchanged Stage 1-3 boundary. Otherwise leave the feature off and say "not released."
- End with: commit hashes; `git status --short` (ideally empty); stories done vs open; exact test/build commands and outcomes; any privacy/security findings; live model hash before/after; provider settings before/after; whether real harness calls occurred and their count; generated artifacts left on disk; and the next actionable blocker. If the tree cannot be clean, list every remaining file and why.

## Cursor Start Prompt

Continue CR-114 Stage 0 in this checkout. Read `docs/spec/08-implementation/CURSOR-HANDOFF-2026-09-17-CR-114.md` and its named source documents first. Preserve the dirty tree, independently verify the two existing uncommitted slices, make a clean checkpoint commit only if they pass, then implement CR-114 stories in order with bounded Cursor usage. Keep the subscription switch off until actual-schema smoke and an adjudicated 30-JD replay pass. Do not use Factory or substitute paid APIs. Finish with the Commit And Exit Contract from the handoff, including hashes, clean/dirty status, tests, open stories, and release verdict.
