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


class TestCoverWordPadding(unittest.TestCase):
    def test_platform_letter_reaches_word_min(self):
        catalog = load_catalog()
        plan = build_cover_plan(ALLSTATE_JD, "Allstate", catalog)
        md = render_cover_letter(plan, catalog, ALLSTATE_JD)
        wc, in_band = word_count_report(md)
        self.assertGreaterEqual(wc, WORD_MIN, f"expected >={WORD_MIN}, got {wc}")
        self.assertTrue(in_band, f"word count {wc} outside band")

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
