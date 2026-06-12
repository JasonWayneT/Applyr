"""Universal cover block assembly tests (CR-047 extension)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from claim_catalog import load_catalog
from cover_letter_structure import build_cover_blocks, blocks_to_prose, detect_archetype
from cover_plan_builder import build_cover_plan
from cover_letter_renderer import render_cover_letter

CVS_JD = """
Product Manager — Analytics Platform
CVS Health is hiring a Product Manager to own analytics products for underwriting and sales teams.

What You'll Do
Ship analytics products that get adopted, not just demoed for sales teams.
Define roadmap prioritization with engineering and design.
Drive platform adoption and measurable product outcomes.

Requirements
5+ years of product management experience, with at least 2 years owning analytics products.
"""


class TestUniversalCoverStructure(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.plan = build_cover_plan(CVS_JD, "CVS Health", self.catalog)

    def test_analytics_uses_application_first(self):
        self.assertEqual(
            detect_archetype(CVS_JD, self.plan.ranked_needs), "analytics_adoption"
        )
        self.assertEqual(self.plan.opening_variant, "application_first")

    def test_universal_proof_bridge_and_close(self):
        blocks = build_cover_blocks(self.plan, self.catalog, CVS_JD)
        prose = blocks_to_prose(blocks).lower()
        self.assertIn("i am applying for", prose)
        self.assertIn("at cision", prose)
        self.assertIn("real adoption", prose)
        self.assertIn("welcome the opportunity", prose)

    def test_render_full_letter_application_first(self):
        md = render_cover_letter(self.plan, self.catalog, CVS_JD)
        self.assertIn("Dear Hiring Manager", md)
        self.assertIn("I am applying for", md)
        self.assertNotIn("is hiring a", md.lower())


if __name__ == "__main__":
    unittest.main()
