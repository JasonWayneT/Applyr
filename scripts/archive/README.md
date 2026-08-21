# scripts/archive/

Retired / one-shot scripts moved here on 2026-08-04 (legacy pipeline isolation audit).

These are **not** part of the live authoring path (generate-submission skill) and are
**not** called by confirmed live entry points. They are kept for historical reference —
nothing in this folder is deleted.

Live verification/authoring entry points remain in scripts/:
- verify_submission.py, compile_single.py, check_ground_truth_coverage.py
- submission_linter.py, quality_checker.py, approved_metrics.py
- context-pack helpers, jd_term_extractor.py, etc.

**Important (2026-08-04):** batch_pipeline.py / draft_compiler.py were NOT moved in this
pass — the Applyr server UI still shelled out to batch_pipeline.py (see STOP list in the
audit report). Do not assume they were dead until that wire was intentionally cut.

**Update (2026-08-20, CR-093):** that wire has since been cut for fit-evaluation
specifically. batch_pipeline.py's evaluate_job_fit()/process_single()/process_batch()
and the whole `--mode single|batch` CLI entry point are deleted, along with the DB/JD
helper functions that had no live caller (confirmed by trace, not just grep). The file
is now ~100 lines: passes_jd_keyword_gate() and two small display/summary helpers, both
with live callers. The archived scripts in this folder that still import evaluate_job_fit /
get_min_fit_score / process_single from batch_pipeline (evaluate_csv_jobs.py,
calibration_harness.py, the draft_*.py scripts, etc.) will ImportError if run — they are
historical reference only, per this file's original framing above, not something to
revive without rewriting them against the current evidence-scale engine
(scripts/evidence_scale.py; see docs/spec/05-change-requests/CR-093-evidence-scale-fit-engine.md).
