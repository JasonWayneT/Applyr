"""Regression tests for CR-054 Epic 1 — audit convergence failure propagation."""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from audit_and_improve import AuditImproveResult, audit_and_improve_company
from drafting_engine import run_drafting_engine

SAMPLE_RESUME = """# Jason Taylor
email@example.com

## PROFESSIONAL SUMMARY
**Platform PM**
One sentence only.

## PROFESSIONAL EXPERIENCE
### Product Manager | Example Co | 2020 - Present
Remote
* Stabilized platform serving 3,500 accounts.

## EDUCATION
BS Example
"""

SAMPLE_CL = """Jason Taylor
email@example.com

Dear Hiring Manager,

Body paragraph one.

Regards,

Jason Taylor
"""

SAMPLE_JD = "Product Manager role. Remote US. B2B SaaS platform."


class TestAuditConvergence(unittest.TestCase):
    """Implements CR-054 / TEST-* audit failure transparency."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.folder = os.path.join(self.tmp, "test_co")
        os.makedirs(self.folder)
        self._write_assets("ORIGINAL_RESUME_MARKER", "ORIGINAL_CL_MARKER")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_assets(self, resume_body: str, cl_body: str) -> None:
        resume_path = os.path.join(self.folder, "Resume.md")
        cl_path = os.path.join(self.folder, "CoverLetter.md")
        jd_path = os.path.join(self.folder, "Original_JD.txt")
        with open(resume_path, "w", encoding="utf-8") as fh:
            fh.write(SAMPLE_RESUME.replace("One sentence only.", resume_body))
        with open(cl_path, "w", encoding="utf-8") as fh:
            fh.write(SAMPLE_CL.replace("Body paragraph one.", cl_body))
        with open(jd_path, "w", encoding="utf-8") as fh:
            fh.write(SAMPLE_JD)

    def test_audit_failure_returns_not_converged(self) -> None:
        """Forced non-convergence must return converged=False with issues."""
        context = {
            "company_stage": "Growth",
            "product_motion": "Enterprise B2B SaaS",
            "primary_partners": ["Engineering"],
        }

        def bad_summary(resume_md, ctx, jd_text, bullets, feedback=""):
            return resume_md, "bad summary"

        with patch("audit_and_improve.analyze_company_context", return_value=context):
            with patch("audit_and_improve.improve_resume_summary", side_effect=bad_summary):
                with patch("audit_and_improve.improve_cover_letter", side_effect=lambda cl, *a, **k: cl):
                    with patch("audit_and_improve.generate_pdf"):
                        result = audit_and_improve_company(self.folder)

        self.assertFalse(result.converged)
        self.assertEqual(result.attempts, 3)
        self.assertTrue(result.final_issues)

    def test_audit_failure_restores_pre_audit_files(self) -> None:
        """Non-converged audit must not leave enhanced content on disk."""
        context = {
            "company_stage": "Growth",
            "product_motion": "Enterprise B2B SaaS",
            "primary_partners": ["Engineering"],
        }

        def bad_summary(resume_md, ctx, jd_text, bullets, feedback=""):
            return resume_md.replace("ORIGINAL_RESUME_MARKER", "CORRUPTED_RESUME"), "bad"

        with patch("audit_and_improve.analyze_company_context", return_value=context):
            with patch("audit_and_improve.improve_resume_summary", side_effect=bad_summary):
                with patch("audit_and_improve.improve_cover_letter", side_effect=lambda cl, *a, **k: cl):
                    with patch("audit_and_improve.generate_pdf"):
                        audit_and_improve_company(self.folder)

        with open(os.path.join(self.folder, "Resume.md"), encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn("ORIGINAL_RESUME_MARKER", content)
        self.assertNotIn("CORRUPTED_RESUME", content)

    def test_run_drafting_engine_raises_on_audit_failure(self) -> None:
        """run_drafting_engine must not claim success when audit fails."""
        fake_eval = {"Score": 85, "Decision": "YES", "Summary": "Good fit"}
        fail_result = AuditImproveResult(
            converged=False,
            attempts=3,
            final_issues=["cover letter metric mismatch"],
        )

        with patch("drafting_engine.run_research"):
            with patch("draft_compiler.run"):
                with patch("audit_and_improve.audit_and_improve_company", return_value=fail_result):
                    with self.assertRaises(RuntimeError) as ctx:
                        run_drafting_engine(
                            "test_co",
                            SAMPLE_JD,
                            "work exp",
                            fake_eval,
                            display_name="Test Co",
                        )
        self.assertIn("Post-drafting quality audit failed", str(ctx.exception))

    def test_process_single_reports_passed_false_on_audit_failure(self) -> None:
        """batch_pipeline.process_single must emit passed:false when audit fails."""
        import batch_pipeline

        fake_eval = {"Score": 85, "Decision": "YES", "Summary": "Good fit", "Title": "Product Manager"}
        fail_result = AuditImproveResult(
            converged=False,
            attempts=3,
            final_issues=["summary sentence count"],
        )

        jd = (
            "Product Manager. Remote US only. B2B SaaS platform. "
            "Cross-functional roadmap ownership. 5+ years experience."
        )

        buf = io.StringIO()
        with patch.object(batch_pipeline, "passes_jd_keyword_gate", return_value=True):
            with patch.object(batch_pipeline, "classify_onsite", return_value=(False, "")):
                with patch.object(batch_pipeline, "evaluate_job_fit", return_value=fake_eval):
                    with patch.object(batch_pipeline, "load_file", return_value="work exp"):
                        with patch.object(batch_pipeline, "run_drafting_engine", side_effect=RuntimeError("audit failed")):
                            with patch.object(batch_pipeline, "generate_cheat_sheet"):
                                with patch.object(batch_pipeline, "_has_required_pdfs", return_value=True):
                                    with redirect_stderr(buf):
                                        with patch("sys.stdout", new=io.StringIO()) as out:
                                            batch_pipeline.process_single("test_co", "http://example.com", jd)

        lines = [ln.strip() for ln in out.getvalue().splitlines() if ln.strip()]
        payload_lines = [ln for ln in lines if ln.startswith("{")]
        final = json.loads(payload_lines[-1])
        self.assertFalse(final["passed"])
        self.assertEqual(final["score"], 85)


if __name__ == "__main__":
    unittest.main()
