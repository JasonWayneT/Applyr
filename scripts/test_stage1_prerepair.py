"""Tests for scripts/stage1_prerepair.py."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import stage1_prerepair as prerepair  # noqa: E402

_WE = "### 1.0 Contact\nA PM with **7 years** of experience in platforms.\n"


class TestStage1Prerepair(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name)

    def test_six_years_fixed_without_agy(self) -> None:
        resume = "Product Manager with six years of experience in B2B platforms.\n"
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text("Dear Hiring Manager,\n\nHello.\n", encoding="utf-8")
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertTrue(result["changed"])
        self.assertTrue(any(row["rule_id"] == "LR-013" for row in result["applied"]))
        text = (self.folder / "Resume.md").read_text(encoding="utf-8")
        self.assertIn("seven years of experience", text)
        self.assertNotIn("six years", text)

    def test_clean_draft_stays_byte_identical(self) -> None:
        resume = "Product Manager with seven years of experience in B2B platforms.\n"
        letter = "Dear Hiring Manager,\n\nHello there.\n"
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text(letter, encoding="utf-8")
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertFalse(result["changed"])
        self.assertEqual((self.folder / "Resume.md").read_text(encoding="utf-8"), resume)
        self.assertEqual((self.folder / "CoverLetter.md").read_text(encoding="utf-8"), letter)

    def test_semicolon_splits_into_two_sentences(self) -> None:
        resume = "I aligned engineering and CX; we shipped the cutover.\n"
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text("Dear Hiring Manager,\n\nHello.\n", encoding="utf-8")
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertTrue(result["changed"])
        text = (self.folder / "Resume.md").read_text(encoding="utf-8")
        self.assertNotIn(";", text)
        self.assertIn("CX. We shipped", text)

    def test_colon_split_resyncs_claim_provenance(self) -> None:
        """Found live on obie, 2026-09-20: an LR-015 colon-split rewrote a
        resume bullet's text but left claim_provenance.json pointing at the
        old (pre-fix) wording, turning a fully-cited bullet into a false
        sentence_provenance FAIL on the very next verify pass."""
        bullet = (
            "Organized the platform roadmap under four strategic pillars: "
            "cost reduction, platform stabilization, churn stabilization."
        )
        resume = f"## PROFESSIONAL EXPERIENCE\n\n* {bullet}\n"
        (self.folder / "Resume.md").write_text(resume, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text("Dear Hiring Manager,\n\nHello.\n", encoding="utf-8")
        provenance = {
            "company": "Acme",
            "resume_claims": [{"bullet": bullet, "claim_ids": ["ACC-179-ROADMAP"]}],
            "cover_letter_claims": [],
        }
        (self.folder / "claim_provenance.json").write_text(
            json.dumps(provenance, indent=2), encoding="utf-8"
        )
        result = prerepair.apply_mechanical_fixes(self.folder, we_text=_WE)
        self.assertTrue(result["changed"])
        new_resume = (self.folder / "Resume.md").read_text(encoding="utf-8")
        self.assertNotIn(":", new_resume)
        updated = json.loads((self.folder / "claim_provenance.json").read_text(encoding="utf-8"))
        stored_bullet = updated["resume_claims"][0]["bullet"]
        # The provenance's stored bullet text must match the rewritten resume
        # bullet (stripped of its leading "* " marker), not the stale
        # pre-fix wording -- otherwise sentence_provenance's exact-string
        # comparison falsely reports the bullet as uncited.
        self.assertIn(stored_bullet.rstrip(".!? "), new_resume)
        self.assertNotEqual(stored_bullet, bullet)


if __name__ == "__main__":
    unittest.main()
