#!/usr/bin/env python3
"""Tests for scripts/build_stage1_repair_prompt.py."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_stage1_repair_prompt as repair  # noqa: E402


def _seed(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "authoring_prompt.md").write_text(
        "SYSTEM digest\nUSER packet\nDo not invent education.\n",
        encoding="utf-8",
    )
    (folder / "Resume.md").write_text(
        "# Name\n\n## EDUCATION\nB.S. Fake College, 2018\n",
        encoding="utf-8",
    )
    (folder / "CoverLetter.md").write_text(
        "Dear Hiring Manager,\n\nBody.\n",
        encoding="utf-8",
    )
    (folder / "claim_provenance.json").write_text(
        json.dumps({"resume": [{"text": "x", "claim_ids": ["ACC-101"]}]}),
        encoding="utf-8",
    )


class TestStage1RepairPrompt(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name) / "rentana"
        _seed(self.folder)

    def test_prompt_contains_ranked_findings_and_drafts_not_work_experience(self) -> None:
        findings = "FAIL [stage1_quality]: education institution is not grounded"
        code, message = repair.build_for_folder(self.folder, findings_text=findings)
        self.assertEqual(code, 0)
        self.assertIn("WROTE", message)
        prompt = (self.folder / repair.REPAIR_PROMPT_NAME).read_text(encoding="utf-8")
        self.assertIn("1. " + findings, prompt)
        self.assertIn("B.S. Fake College, 2018", prompt)
        self.assertIn("## EDUCATION", prompt)
        self.assertNotIn("Dear Hiring Manager", prompt)
        self.assertIn("## Relevant digest", prompt)
        self.assertNotIn("## Original authoring prompt", prompt)
        self.assertIn("Fix ONLY the ranked findings listed below", prompt)
        self.assertIn(
            "Do not load workExperience.md, master_claims.json, AGENTS.md, or agent_context_pack.md.",
            prompt,
        )
        self.assertNotIn("data/workExperience.md", prompt)

    def test_same_findings_no_progress_keeps_blocking(self) -> None:
        findings = "FAIL [lint]: LR-014 semicolon"

    def test_same_findings_no_progress_keeps_blocking(self) -> None:
        findings = "FAIL [lint]: LR-014 semicolon"
        self.assertEqual(repair.build_for_folder(self.folder, findings_text=findings)[0], 0)
        code, message = repair.build_for_folder(self.folder, findings_text=findings)
        self.assertEqual(code, 2)
        self.assertIn("NO_PROGRESS", message)
        self.assertIn("LR-014", message)
        state = json.loads((self.folder / repair.REPAIR_STATE_NAME).read_text(encoding="utf-8"))
        self.assertEqual(state["attempts"], 1)
        self.assertEqual(state["last_outcome"], "no_progress_blocking")

    def test_same_warn_findings_forward_to_stage2(self) -> None:
        findings = "WARN [evidence_utilization]: unused high-priority claims forwarded: ACC-106"
        self.assertEqual(repair.build_for_folder(self.folder, findings_text=findings)[0], 0)
        code, message = repair.build_for_folder(self.folder, findings_text=findings)
        self.assertEqual(code, 0)
        self.assertIn("NO_PROGRESS", message)
        self.assertIn("forwarded", message)
        notes = json.loads((self.folder / repair.FORWARDED_NOTES).read_text(encoding="utf-8"))
        self.assertTrue(any("ACC-106" in row for row in notes["repair_forwarded"]))

    def test_new_findings_write_another_round(self) -> None:
        first = "FAIL [lint]: LR-014 semicolon"
        second = "FAIL [optimization_bar]: required evidence unused — Own roadmap (need one of: ACC-104)"
        self.assertEqual(repair.build_for_folder(self.folder, findings_text=first)[0], 0)
        code, message = repair.build_for_folder(self.folder, findings_text=second)
        self.assertEqual(code, 0)
        self.assertIn("repair round 2", message)
        state = json.loads((self.folder / repair.REPAIR_STATE_NAME).read_text(encoding="utf-8"))
        self.assertEqual(state["attempts"], 2)

    def test_uses_author_output_snapshot_when_present(self) -> None:
        snap = self.folder / repair.AUTHOR_OUTPUT_DIR
        snap.mkdir()
        (snap / "Resume.md").write_text("SNAPSHOT RESUME\n", encoding="utf-8")
        (snap / "CoverLetter.md").write_text("SNAPSHOT LETTER\n", encoding="utf-8")
        (snap / "claim_provenance.json").write_text("{\"ok\": true}\n", encoding="utf-8")
        findings = "FAIL [stage1_quality]: education institution is not grounded"
        repair.build_for_folder(self.folder, findings_text=findings)
        prompt = (self.folder / repair.REPAIR_PROMPT_NAME).read_text(encoding="utf-8")
        self.assertIn("SNAPSHOT RESUME", prompt)
        self.assertNotIn("B.S. Fake College, 2018", prompt)
        self.assertNotIn("## Original authoring prompt", prompt)

    def test_rentana_lr013_single_finding_prompt_under_10kb(self) -> None:
        source = Path(__file__).resolve().parents[1] / "data" / "submissions" / "rentana"
        resume = (source / "Resume.md").read_text(encoding="utf-8")
        letter = (source / "CoverLetter.md").read_text(encoding="utf-8")
        packet = json.loads((source / "authoring_packet.json").read_text(encoding="utf-8"))
        from generate_authoring_rule_digest import generate_digest
        from submission_linter import lint_document

        result = lint_document(resume, "resume", filename="Resume.md")
        lr013 = next(item for item in result.blocks if item.rule_id == "LR-013")
        findings = repair._format_lint_item("FAIL", "Resume.md", lr013, resume)
        drafts = {
            "Resume.md": resume,
            "CoverLetter.md": letter,
            "claim_provenance.json": "{}",
        }
        digest, _version = generate_digest()
        prompt = repair.build_repair_prompt(
            drafts,
            findings,
            digest_text=digest,
            packet=packet,
        )
        self.assertLess(len(prompt.encode("utf-8")), 10_000, len(prompt.encode("utf-8")))
        self.assertIn("[LR-013]", prompt)
        self.assertIn("line 8", prompt)
        self.assertIn("six years", prompt)
        self.assertIn("suggestion:", prompt.lower())
        self.assertIn("seven years", prompt.lower())
        self.assertIn("## Relevant digest", prompt)
        self.assertIn("Self-Check", prompt)
        self.assertNotIn("## Original authoring prompt", prompt)
        self.assertNotIn("## Current CoverLetter.md", prompt)
        self.assertNotIn("Implemented mobile Unique Visitors", prompt)

    def test_missing_files_fail(self) -> None:
        (self.folder / "claim_provenance.json").unlink()
        code, message = repair.build_for_folder(
            self.folder, findings_text="FAIL [x]"
        )
        self.assertEqual(code, 1)
        self.assertIn("claim_provenance.json", message)

    def test_six_years_auto_fixed_without_agy_prompt(self) -> None:
        (self.folder / "Resume.md").write_text(
            "Product Manager with six years of experience in B2B platforms.\n",
            encoding="utf-8",
        )
        with mock.patch.object(
            repair,
            "collect_findings",
            side_effect=[
                "FAIL [lint/Resume.md]: 1 hard block(s)\n  [LR-013] six years",
                "",
            ],
        ):
            code, message = repair.build_for_folder(self.folder)
        self.assertEqual(code, 0)
        self.assertIn("AUTO_FIXED", message)
        self.assertFalse((self.folder / repair.REPAIR_PROMPT_NAME).is_file())
        state = json.loads((self.folder / repair.REPAIR_STATE_NAME).read_text(encoding="utf-8"))
        self.assertEqual(state["last_outcome"], "auto_fixed")
        self.assertTrue(any(row.get("rule_id") == "LR-013" for row in state["auto_fixes"]))
        self.assertIn(
            "seven years of experience",
            (self.folder / "Resume.md").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
