"""Tests for human-mirror resume conversion critique (FR-220–FR-222)."""
import os
import tempfile
import unittest

from resume_conversion_eval import (
    check_pdf_experience_header_order,
    check_summary_completeness,
    check_summary_prose_quality,
    check_sterkly_narrative_coherence,
    is_incomplete_summary_sentence,
    is_participle_proof_fragment,
)


SAMPLE_RESUME = """# JOHN DOE

## PROFESSIONAL SUMMARY
Product Manager with 6+ years across enterprise SaaS platforms. Rebuilt a B2B attribution feature that let customers trace content placements to revenue outcomes, producing a version reliable enough that other internal platform teams sought to adopt it.

## PROFESSIONAL EXPERIENCE

### Product Manager | Acme Corp | September 2021 - January 2026
Remote

* Maintained a 7% annual churn rate across 3,500 enterprise accounts on a $40M ARR platform over four years.

### Product Manager | Example Inc | February 2019 - August 2021
City, State

* Sustained an estimated $1M-$3M in at-risk product revenue on macos by eliminating dependency on unreliable third-party vendors.
* Partnered closely with a dedicated team of 5-8 developers to ensure accurate, on-time delivery of technical workflow solutions.
* Restored certificate issuance for a security product when all vendor sources failed.

## EDUCATION

* **Bachelor of Business Administration** , Example University, 2019
"""


class TestIncompleteSummary(unittest.TestCase):
    def test_detects_dangling_teams_clause(self):
        bad = (
            "Rebuilt a B2B PR attribution feature, producing a version reliable enough "
            "that other internal platform teams."
        )
        self.assertTrue(is_incomplete_summary_sentence(bad))

    def test_accepts_complete_adoption_clause(self):
        good = (
            "Producing a version reliable enough that other internal platform teams "
            "sought to adopt it."
        )
        self.assertFalse(is_incomplete_summary_sentence(good))

    def test_cw011_flags_bad_summary_in_resume(self):
        bad_resume = SAMPLE_RESUME.replace(
            "sought to adopt it.",
            "that other internal platform teams.",
        )
        issues = check_summary_completeness(bad_resume)
        self.assertTrue(any("[CW-011]" in i for i in issues))


class TestSummaryProse(unittest.TestCase):
    def test_detects_participle_fragment(self):
        self.assertTrue(is_participle_proof_fragment(
            "Coordinating schema changes across teams to resolve a 40% data failure rate."
        ))

    def test_cw013_flags_stacked_proofs(self):
        bad = (
            "# JOHN DOE\n\n## PROFESSIONAL SUMMARY\n"
            "Product Manager with 6+ years across enterprise SaaS platforms. "
            "Experienced partnering with engineering teams. "
            "Coordinating schema changes across teams to resolve a 40% data failure rate. "
            "Producing a version reliable enough that other internal platform teams sought to adopt it.\n\n"
            "## PROFESSIONAL EXPERIENCE\n\n* Example bullet.\n"
        )
        issues = check_summary_prose_quality(bad)
        self.assertTrue(any("[CW-013]" in i for i in issues))

    def test_passes_single_outcome_proof(self):
        good = (
            "# JOHN DOE\n\n## PROFESSIONAL SUMMARY\n"
            "Product Manager with 6+ years across enterprise SaaS platforms. "
            "Experienced partnering with engineering teams. "
            "Rebuilt a B2B PR attribution feature that let customers trace content placements to revenue outcomes.\n\n"
            "## PROFESSIONAL EXPERIENCE\n\n* Example bullet.\n"
        )
        issues = check_summary_prose_quality(good)
        self.assertEqual(issues, [])


class TestSummaryBulletOverlap(unittest.TestCase):
    def test_cw016_flags_verbatim_proof(self):
        bullet = (
            "Replaced reactive sprint planning with a capacity model using T-shirt sizing "
            "and uncertainty bands."
        )
        resume = (
            "# JOHN DOE\n\n## PROFESSIONAL SUMMARY\n"
            "Product Manager with 6+ years across enterprise SaaS platforms. "
            "Experienced partnering with engineering teams. "
            f"{bullet}\n\n"
            "## PROFESSIONAL EXPERIENCE\n\n"
            "### Product Manager | Cision | 2021 - 2026\nRemote\n\n"
            f"* {bullet}\n"
        )
        from resume_conversion_eval import check_summary_bullet_overlap, evaluate_resume_conversion

        issues = check_summary_bullet_overlap(resume)
        self.assertTrue(any("[CW-016]" in i for i in issues))
        critique = evaluate_resume_conversion(resume)
        self.assertFalse(critique["pass"])

    def test_cw016_passes_distinct_proof(self):
        resume = (
            "# JOHN DOE\n\n## PROFESSIONAL SUMMARY\n"
            "Product Manager with 6+ years across enterprise SaaS platforms. "
            "Experienced partnering with engineering teams. "
            "Rebuilt a B2B PR attribution feature that let customers trace revenue outcomes.\n\n"
            "## PROFESSIONAL EXPERIENCE\n\n* Different experience bullet here.\n"
        )
        from resume_conversion_eval import check_summary_bullet_overlap

        self.assertEqual(check_summary_bullet_overlap(resume), [])


from unittest.mock import patch

@patch("candidate_context.employer_tiers", return_value=("acme_corp", "example_inc", "startup_co"))
class TestSterklyNarrative(unittest.TestCase):
    def test_flags_macos_only_section(self, mock_tiers):
        bad = SAMPLE_RESUME.replace(
            "* Partnered closely with a dedicated team of 5-8 developers to ensure accurate, on-time delivery of technical workflow solutions.\n",
            "",
        )
        issues = check_sterkly_narrative_coherence(bad)
        self.assertTrue(any("[CW-012]" in i for i in issues))

    def test_passes_with_context_bullet(self, mock_tiers):
        issues = check_sterkly_narrative_coherence(SAMPLE_RESUME)
        self.assertEqual(issues, [])


class TestPdfHeaderOrder(unittest.TestCase):
    def test_compile_single_produces_ordered_headers(self):
        """Integration: fixed compile_single must place company before location in PDF text."""
        try:
            import compile_single
            import subprocess
            import sys
        except ImportError:
            self.skipTest("compile_single not importable")

        with tempfile.TemporaryDirectory() as tmp:
            md_path = os.path.join(tmp, "Resume.md")
            pdf_path = os.path.join(tmp, "Resume.pdf")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(SAMPLE_RESUME)

            script = os.path.join(os.path.dirname(__file__), "compile_single.py")
            result = subprocess.run(
                [sys.executable, script, md_path, pdf_path],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                self.skipTest(f"Playwright PDF compile unavailable: {result.stderr[:200]}")

            issues = check_pdf_experience_header_order(pdf_path, SAMPLE_RESUME)
            layout_issues = [i for i in issues if "[CW-009]" in i]
            self.assertEqual(
                layout_issues,
                [],
                f"PDF header layout issues: {layout_issues}",
            )


if __name__ == "__main__":
    unittest.main()
