# scripts/archive/

Retired / one-shot scripts moved here on 2026-08-04 (legacy pipeline isolation audit).

These are **not** part of the live authoring path (generate-submission skill) and are
**not** called by confirmed live entry points. They are kept for historical reference —
nothing in this folder is deleted.

Live verification/authoring entry points remain in scripts/:
- erify_submission.py, compile_single.py, check_ground_truth_coverage.py
- submission_linter.py, quality_checker.py, pproved_metrics.py
- context-pack helpers, jd_term_extractor.py, etc.

**Important:** atch_pipeline.py / draft_compiler.py were NOT moved in this pass —
the Applyr server UI still shells out to atch_pipeline.py (see STOP list in the
audit report). Do not assume they are dead until that wire is intentionally cut.
