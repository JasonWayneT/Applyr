#!/usr/bin/env python3
"""
Gate-reject test for batch_pipeline.process_single (CR-ARCH-001 / VERIFY-02).

No LLM mock — JD fails zero-token gate before evaluate_job_fit.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    print("VERIFY-02: process_single gate-reject (no LLM)")

    # Title blocklist fails before any LLM call
    jd = "Title: Director of Product Management\nB2B SaaS platform roadmap execution."
    prefs = {
        "blocked_titles": ["Director"],
        "blocked_industries": [],
        "must_have_keywords": [],
        "experience_range": {"max": 10},
    }

    import batch_pipeline

    buf = io.StringIO()
    with patch.object(batch_pipeline, "load_candidate_preferences", return_value=prefs):
        with contextlib.redirect_stdout(buf):
            batch_pipeline.process_single("TestCo", "", jd, job_id=None)

    out = buf.getvalue()
    failed = 0

    if '"passed": false' not in out.replace(" ", "") and '"passed":false' not in out.replace(" ", ""):
        print("  [FAIL] VERIFY-02: expected passed:false in stdout")
        print(out[:500])
        failed = 1
    else:
        print("  [PASS] VERIFY-02: gate reject emitted passed:false")

    # Ensure we never reached fit running (no fit score JSON with Score > 0 path)
    if '"id": "fit"' in out and '"status": "running"' in out:
        print("  [FAIL] VERIFY-02: fit stage ran despite title block")
        failed = 1
    else:
        print("  [PASS] VERIFY-02: fit stage did not run")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
