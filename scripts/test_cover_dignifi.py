"""Dignifi / product_domain cover tests."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from claim_catalog import load_catalog
from cover_claim_picker import is_product_domain_jd
from cover_letter_audit import audit_cover_letter
from cover_letter_renderer import render_cover_letter
from cover_plan_builder import build_cover_plan
from cover_letter_structure import build_cover_blocks, blocks_to_prose, detect_archetype


def _load_dignifi_jd() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data", "submissions", "dignifi", "Original_JD.txt")
    with open(path, encoding="utf-8") as f:
        jd = f.read()
    if jd.startswith("URL:"):
        jd = "\n".join(jd.splitlines()[1:])
    return jd


class TestDignifiCover(unittest.TestCase):
    def setUp(self):
        self.jd = _load_dignifi_jd()
        self.catalog = load_catalog()
        self.plan = build_cover_plan(self.jd, "Dignifi", self.catalog)

    def test_product_domain_archetype(self):
        self.assertTrue(is_product_domain_jd(self.jd))
        self.assertEqual(
            detect_archetype(self.jd, self.plan.ranked_needs), "product_domain"
        )
        self.assertEqual(self.plan.opening_variant, "domain_first")

    def test_domain_first_structure(self):
        blocks = build_cover_blocks(self.plan, self.catalog, self.jd)
        prose = blocks_to_prose(blocks).lower()
        self.assertIn("fits the work i do best", prose)
        self.assertIn("owning complex product areas", prose)
        self.assertIn("b2b saas platform work", prose)
        self.assertIn("b2c product experience", prose)
        self.assertIn("engineering headcount", prose)
        self.assertIn("capacity model", prose)
        self.assertIn("when customers said", prose)
        self.assertIn("product trust problem", prose)
        self.assertIn("40%", prose)
        self.assertIn("applied the same discipline", prose)
        self.assertIn("technical failure was also a business problem", prose)
        self.assertIn("customer-visible product problems", prose)
        self.assertIn("feature trade-offs explicit", prose)
        self.assertNotIn("non-critical feature", prose)
        self.assertIn("limited capacity", prose)
        self.assertIn("financing experiences for dealers and customers where trust", prose)
        self.assertNotIn("dealer and customer-facing financing", prose)
        self.assertNotIn("customers told us", prose)
        self.assertNotIn("metrics and delivery patterns above", prose)
        self.assertNotIn("i am applying for", prose)

        opener = blocks[0].text.lower()
        trust_hook = "when customers said the contact data"
        self.assertNotIn(trust_hook, opener)
        body_after_opener = prose
        self.assertEqual(body_after_opener.count(trust_hook), 1)

    def test_letter_passes_audit(self):
        md = render_cover_letter(self.plan, self.catalog, self.jd)
        corpus = "\n".join(
            (rec.cover_story or rec.body)
            for rec in self.catalog.claims.values()
        )
        audit = audit_cover_letter(md, self.plan, self.jd, corpus)
        self.assertEqual(audit.grade, "Pass", audit.issues)
        wc = len(re.findall(r"\b\w+\b", md.split("Dear Hiring Manager,")[-1]))
        self.assertGreaterEqual(wc, 300)


if __name__ == "__main__":
    unittest.main()
