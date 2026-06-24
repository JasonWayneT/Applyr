"""Golden structural tests for Splash / marketplace_fintech covers (CR-047)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from claim_catalog import load_catalog
from cover_letter_structure import build_cover_blocks, blocks_to_prose, detect_archetype
from cover_plan_builder import build_cover_plan
from cover_letter_renderer import render_cover_letter

def _load_splash_jd() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data", "submissions", "splash_financial", "Original_JD.txt")
    with open(path, encoding="utf-8") as f:
        jd = f.read()
    if jd.startswith("URL:"):
        jd = "\n".join(jd.splitlines()[1:])
    return jd


class TestSplashGolden(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.jd = _load_splash_jd()
        self.plan = build_cover_plan(self.jd, "Splash Financial", self.catalog)

    def test_archetype_marketplace_fintech(self):
        self.assertEqual(detect_archetype(self.jd, self.plan.ranked_needs), "marketplace_fintech")
        self.assertEqual(self.plan.opening_variant, "need_first")

    def test_need_first_structure(self):
        blocks = build_cover_blocks(self.plan, self.catalog, self.jd)
        kinds = [b.kind for b in blocks]
        self.assertEqual(kinds[0], "opener")
        self.assertEqual(kinds[-1], "close")
        self.assertGreaterEqual(kinds.count("proof"), 2)

        prose = blocks_to_prose(blocks).lower()
        self.assertIn("splash financial", prose)
        self.assertIn("customer-facing product problems", prose)
        self.assertIn("at cision", prose)
        self.assertIn("product trust problem", prose)
        self.assertIn("lender integrations", prose)
        self.assertIn("40%", prose)
        self.assertIn("7%", prose)
        self.assertIn("the borrower offer experience", prose.lower())
        self.assertIn("funnel conversion, approval rates, and funded volume", prose)

    def test_render_full_letter(self):
        md = render_cover_letter(self.plan, self.catalog, self.jd)
        self.assertIn("Dear Hiring Manager", md)
        self.assertNotIn("Customers told us", md)
        self.assertIn("improve lender integrations", md.lower())


if __name__ == "__main__":
    unittest.main()
