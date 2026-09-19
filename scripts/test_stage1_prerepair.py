"""Tests for scripts/stage1_prerepair.py."""
from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
