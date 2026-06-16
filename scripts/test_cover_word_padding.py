"""Word-count padding tests (CR-047 extension)."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from claim_catalog import load_catalog
from cover_letter_renderer import render_cover_letter, word_count_report
from cover_plan_builder import build_cover_plan
from cover_phrasing import WORD_MIN, WORD_MIN_NEED_FIRST

ALLSTATE_JD = """
Product Manager
Allstate is hiring a Product Manager to own roadmap prioritization and platform delivery.

What You'll Do
Define roadmap priorities with engineering and design across a complex legacy platform.
Partner with cross-functional teams to ship measurable product outcomes.
Maintain platform stability while delivering customer-facing improvements.

Requirements
5+ years of product management experience on B2B or enterprise platforms.
"""

# Minimal JD that produces empty ranked_needs — simulates the Optum failure case
_THIN_JD = """
Product Manager
We are looking for a Product Manager to help us improve health outcomes by connecting people.
"""


class TestCoverWordPadding(unittest.TestCase):
    def test_platform_letter_reaches_word_min(self):
        catalog = load_catalog()
        plan = build_cover_plan(ALLSTATE_JD, "Allstate", catalog)
        md = render_cover_letter(plan, catalog, ALLSTATE_JD)
        wc, in_band = word_count_report(md)
        self.assertGreaterEqual(wc, WORD_MIN, f"expected >={WORD_MIN}, got {wc}")
        self.assertTrue(in_band, f"word count {wc} outside band")

    def test_thin_jd_still_produces_proof_content(self):
        """Empty ranked_needs must not produce a near-empty cover letter (Optum regression)."""
        catalog = load_catalog()
        plan = build_cover_plan(_THIN_JD, "Acme", catalog)
        md = render_cover_letter(plan, catalog, _THIN_JD)
        wc, _ = word_count_report(md)
        self.assertGreaterEqual(wc, 80, f"cover letter critically short ({wc} words) — proof fallback failed")
        self.assertIn("cision", md.lower(), "expected at least one proof from claim catalog")

    def test_opener_does_not_contain_jd_role_description(self):
        """Goal phrases that are raw JD role-description sentences must not leak into the opener."""
        ROLE_DESC_JD = """
Product Manager
We are seeking a Product Manager role.

Responsibilities
The Digital Product Manager is responsible for defining, delivering, and managing product lifecycle.
Collaborate with stakeholders to drive cross-functional alignment.

Requirements
5+ years of PM experience.
"""
        catalog = load_catalog()
        plan = build_cover_plan(ROLE_DESC_JD, "TestCo", catalog)
        md = render_cover_letter(plan, catalog, ROLE_DESC_JD)
        opener_end = md.find("\n\n", md.find("Dear Hiring Manager"))
        opener = md[:opener_end].lower() if opener_end > 0 else md[:600].lower()
        self.assertNotIn(
            "is responsible for defining",
            opener,
            "JD role-description sentence leaked into opener",
        )

    def test_secondary_proof_keeps_first_sentence(self):
        """Secondary proof bodies must not start with a dangling pronoun after value_lead strip."""
        catalog = load_catalog()
        plan = build_cover_plan(ALLSTATE_JD, "Allstate", catalog)
        md = render_cover_letter(plan, catalog, ALLSTATE_JD)
        # ACC-106-RETENTION cover_story now uses "it" not "that"
        self.assertNotIn(
            "I treated that as a JTBD failure",
            md,
            "ACC-106-RETENTION used dangling 'that' — cover_story or value_lead strip regressed",
        )
        # If the ACC-101-PM legacy proof is rendered, the setup sentence must precede the mandate line
        if "My mandate was stability" in md:
            self.assertIn(
                "I was hired after leadership ended",
                md,
                "ACC-101-PM legacy proof is missing its setup sentence — value_lead incorrectly stripped for secondary proof",
            )
            self.assertLess(
                md.index("I was hired after leadership ended"),
                md.index("My mandate was stability"),
                "ACC-101-PM setup sentence must precede 'My mandate was stability'",
            )

    def test_analytics_language_absent_from_non_analytics_letter(self):
        """'not an analytics PM by title' must not appear in a non-analytics JD letter."""
        catalog = load_catalog()
        plan = build_cover_plan(ALLSTATE_JD, "Allstate", catalog)
        md = render_cover_letter(plan, catalog, ALLSTATE_JD)
        self.assertNotIn(
            "not an analytics PM by title",
            md.lower(),
            "analytics-specific language appeared in a non-analytics letter",
        )

    def test_jd_verb_fragment_not_appended_to_opener(self):
        """Verb-initial JD bullet fragments ('drive', 'solve', etc.) must not be appended to the opener."""
        VERB_FRAG_JD = """
Product Manager
Drive capabilities from concept through adoption.
Solve complex cross-functional delivery problems.
Scale the platform to serve enterprise customers.

Requirements
3+ years of PM experience.
"""
        catalog = load_catalog()
        plan = build_cover_plan(VERB_FRAG_JD, "VerbCo", catalog)
        md = render_cover_letter(plan, catalog, VERB_FRAG_JD)
        opener_end = md.find("\n\n", md.find("Dear Hiring Manager"))
        opener = md[:opener_end].lower() if opener_end > 0 else md[:600].lower()
        for bad_start in ("drive capabilities", "solve complex", "scale the platform"):
            self.assertNotIn(
                bad_start,
                opener,
                f"JD verb fragment '{bad_start}' leaked into opener paragraph",
            )

    def test_splash_need_first_reaches_lower_band(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        jd_path = os.path.join(root, "submissions", "splash_financial", "Original_JD.txt")
        if not os.path.exists(jd_path):
            self.skipTest("Splash JD not present")
        with open(jd_path, encoding="utf-8") as f:
            jd = f.read()
        if jd.startswith("URL:"):
            jd = "\n".join(jd.splitlines()[1:])
        catalog = load_catalog()
        plan = build_cover_plan(jd, "Splash Financial", catalog)
        md = render_cover_letter(plan, catalog, jd)
        body = md.split("Dear Hiring Manager,")[-1]
        wc = len(re.findall(r"\b\w+\b", body))
        self.assertGreaterEqual(wc, WORD_MIN_NEED_FIRST, f"expected >={WORD_MIN_NEED_FIRST}, got {wc}")


if __name__ == "__main__":
    unittest.main()
