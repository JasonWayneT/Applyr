"""Everbridge / connected-devices cover tests."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from claim_catalog import load_catalog
from cover_claim_picker import is_connected_devices_jd
from cover_letter_audit import audit_cover_letter
from cover_letter_renderer import render_cover_letter
from cover_plan_builder import build_cover_plan
from cover_letter_structure import detect_archetype


def _load_everbridge_jd() -> str:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data", "submissions", "everbridge", "Original_JD.txt")
    with open(path, encoding="utf-8") as f:
        jd = f.read()
    if jd.startswith("URL:"):
        jd = "\n".join(jd.splitlines()[1:])
    return jd


class TestEverbridgeCover(unittest.TestCase):
    def setUp(self):
        self.jd = _load_everbridge_jd()
        self.catalog = load_catalog()
        self.plan = build_cover_plan(self.jd, "Everbridge", self.catalog)

    def test_connected_devices_archetype(self):
        self.assertTrue(is_connected_devices_jd(self.jd))
        self.assertEqual(
            detect_archetype(self.jd, self.plan.ranked_needs), "connected_devices"
        )

    def test_letter_reflects_jd_and_passes_audit(self):
        md = render_cover_letter(self.plan, self.catalog, self.jd)
        body = md.lower()
        self.assertIn("connected device", body)
        self.assertIn("vendor integration", body)
        self.assertNotIn("build resilience in an increasingly complex", body)
        corpus = "\n".join(
            (rec.cover_story or rec.body)
            for rec in self.catalog.claims.values()
        )
        audit = audit_cover_letter(md, self.plan, self.jd, corpus)
        self.assertNotIn(
            "JD need not reflected in letter body",
            audit.issues,
            audit.issues,
        )
        wc = len(re.findall(r"\b\w+\b", md.split("Dear Hiring Manager,")[-1]))
        self.assertGreaterEqual(wc, 300)


if __name__ == "__main__":
    unittest.main()
