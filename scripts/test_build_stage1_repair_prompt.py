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
        self.assertIn("## Current Resume.md", prompt)
        self.assertIn("## Current CoverLetter.md", prompt)
        self.assertIn("Dear Hiring Manager", prompt)
        self.assertIn("## Relevant digest", prompt)
        self.assertNotIn("## Original authoring prompt", prompt)
        self.assertIn("Return the full corrected Resume.md and CoverLetter.md", prompt)
        self.assertIn("omit claim_provenance.json to keep the current file", prompt)
        self.assertIn(
            "Do not load workExperience.md, master_claims.json, AGENTS.md, or agent_context_pack.md.",
            prompt,
        )
        self.assertNotIn("data/workExperience.md", prompt)

    def test_same_findings_no_progress_keeps_blocking(self) -> None:
        findings = "FAIL [lint]: LR-014 semicolon"
        self.assertEqual(repair.build_for_folder(self.folder, findings_text=findings)[0], 0)
        code, message = repair.build_for_folder(self.folder, findings_text=findings)
        self.assertEqual(code, 0)
        self.assertIn("already waiting", message)
        import run_stage1_repair as runner

        runner.apply_repair_result(
            self.folder,
            {
                "outcome": "repair_timeout",
                "reason": "event_count",
                "event_count": 6,
                "wall_seconds": 1.2,
                "text": "",
            },
        )
        code, message = repair.build_for_folder(self.folder, findings_text=findings)
        self.assertEqual(code, 2)
        self.assertIn("NO_PROGRESS", message)
        self.assertIn("LR-014", message)
        state = json.loads((self.folder / repair.REPAIR_STATE_NAME).read_text(encoding="utf-8"))
        self.assertEqual(state["attempts"], 1)
        self.assertEqual(state["last_outcome"], "no_progress_blocking")
        self.assertEqual(state["no_progress_streak"], 2)
        self.assertEqual(state["timeout_attempts"], 1)

    def test_wrote_prompt_does_not_requeue(self) -> None:
        with mock.patch.object(repair, "_maybe_requeue_repair") as requeue:
            code, message = repair.build_for_folder(
                self.folder, findings_text="FAIL [lint]: LR-014 semicolon"
            )
        self.assertEqual(code, 0)
        self.assertIn("WROTE", message)
        requeue.assert_not_called()
        self.assertFalse((self.folder / "Resume.md").read_text(encoding="utf-8") == "")

    def test_same_warn_findings_forward_to_stage2(self) -> None:
        findings = "WARN [evidence_utilization]: unused high-priority claims forwarded: ACC-106"
        self.assertEqual(repair.build_for_folder(self.folder, findings_text=findings)[0], 0)
        import run_stage1_repair as runner

        runner.apply_repair_result(
            self.folder,
            {
                "outcome": "repair_failed",
                "reason": "tool_or_permission",
                "event_count": 2,
                "wall_seconds": 0.4,
                "text": "",
            },
        )
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

    def test_rentana_lr013_single_finding_prompt_under_16kb(self) -> None:
        source = Path(__file__).resolve().parents[1] / "data" / "submissions" / "rentana"
        resume = (source / "Resume.md").read_text(encoding="utf-8")
        if "six years" not in resume.lower():
            resume = resume.replace("seven years", "six years", 1)
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
        self.assertLess(
            len(prompt.encode("utf-8")),
            repair.REPAIR_PROMPT_BYTE_TARGET,
            len(prompt.encode("utf-8")),
        )
        self.assertIn("[LR-013]", prompt)
        self.assertIn("line 8", prompt)
        self.assertIn("six years", prompt)
        self.assertIn("suggestion:", prompt.lower())
        self.assertIn("seven years", prompt.lower())
        self.assertIn("## Relevant digest", prompt)
        self.assertIn("Self-Check", prompt)
        self.assertIn("## Current Resume.md", prompt)
        self.assertIn("## Current CoverLetter.md", prompt)
        self.assertNotIn("## Original authoring prompt", prompt)
        self.assertNotIn("evidence_map", prompt)

    def test_uncited_sentence_finding_pulls_all_packet_excerpts(self) -> None:
        # An "uncited bullet/sentence" finding never names a claim ID in its own
        # text -- that's the whole problem -- so the old code (which only pulled
        # excerpts for claim IDs literally mentioned in the findings) handed the
        # repair nothing to cite from, and it kept regenerating an uncited
        # paraphrase across rounds instead of converging. Confirmed live on
        # 2026-09-19 on binance (ACC-220-CLOUDERAEXIT) and healthstream.
        findings = (
            'FAIL [sentence_provenance/resume]: uncited bullet '
            '"Drove the decision to exit Cloudera hosting, pivoting to AWS EKS and MSK."'
        )
        packet = {
            "excerpts": {
                "ACC-220-CLOUDERAEXIT": "Prioritized and drove the decision to exit Cloudera...",
                "ACC-101-SCOPE": "Some unrelated excerpt about scope.",
            }
        }
        drafts = {
            "Resume.md": "# Name\n\n## EDUCATION\nB.S. Fake College, 2018\n",
            "CoverLetter.md": "Dear Hiring Manager,\n\nBody.\n",
            "claim_provenance.json": "{}",
        }
        prompt = repair.build_repair_prompt(drafts, findings, packet=packet)
        self.assertIn("ACC-220-CLOUDERAEXIT excerpt:", prompt)
        self.assertIn("ACC-101-SCOPE excerpt:", prompt)
        self.assertIn("must be backed by one of the excerpts below", prompt)
        self.assertIn("do not invent a citation", prompt)
        self.assertIn("do not remove it", prompt)

    def test_non_uncited_finding_only_pulls_named_claim_excerpts(self) -> None:
        # A finding that already names a claim ID (e.g. an attribution or
        # prohibited-language violation on a specific claim) should not balloon
        # the prompt with every excerpt in the packet -- only uncited-sentence
        # findings need the full set.
        findings = "FAIL [attribution]: ACC-101-SCOPE overclaims ownership"
        packet = {
            "excerpts": {
                "ACC-220-CLOUDERAEXIT": "Prioritized and drove the decision to exit Cloudera...",
                "ACC-101-SCOPE": "Some unrelated excerpt about scope.",
            }
        }
        drafts = {
            "Resume.md": "# Name\n",
            "CoverLetter.md": "Dear Hiring Manager,\n\nBody.\n",
            "claim_provenance.json": "{}",
        }
        prompt = repair.build_repair_prompt(drafts, findings, packet=packet)
        self.assertIn("ACC-101-SCOPE excerpt:", prompt)
        self.assertNotIn("ACC-220-CLOUDERAEXIT excerpt:", prompt)

    def test_lw039_rentana_line_12_feeds_repair_prompt(self) -> None:
        source = Path(__file__).resolve().parents[1] / "data" / "submissions" / "rentana"
        jd = (source / "Original_JD.txt").read_text(encoding="utf-8")
        letter = (
            "# Jason Taylor\n"
            "San Diego, CA | candidate@example.com\n"
            "\n"
            "Dear Hiring Manager,\n"
            "\n"
            "Rentana's use of operating data to support decisions caught my attention.\n"
            "\n"
            "At Cision I owned the customer-facing platform for media monitoring.\n"
            "\n"
            "I also organized the roadmap around cost efficiency and platform stability.\n"
            "\n"
            "I have worked across two fully remote companies with engineering "
            "distributed across the U.S., Budapest, and India, and I would welcome "
            "the chance to bring that approach to Rentana's platform.\n"
            "\n"
            "Best regards,\n"
            "\n"
            "Jason Taylor\n"
        )
        from generate_authoring_rule_digest import generate_digest
        from submission_linter import check_unsolicited_geography

        warns = check_unsolicited_geography(letter, jd, "cover_letter")
        self.assertEqual(warns[0].line, 12)
        findings = repair._format_lint_item("WARN", "CoverLetter.md", warns[0], letter)
        drafts = {
            "Resume.md": "# Name\n",
            "CoverLetter.md": letter,
            "claim_provenance.json": "{}",
        }
        digest, _version = generate_digest()
        prompt = repair.build_repair_prompt(
            drafts,
            findings,
            digest_text=digest,
            packet={"company": "Rentana", "evidence_map": []},
        )
        self.assertIn("[LW-039]", prompt)
        self.assertIn("line 12", prompt)
        self.assertIn("Budapest", prompt)
        self.assertIn("Collaboration Framing", prompt)
        self.assertIn("who, what was aligned, what shipped", prompt.lower())
        self.assertIn("## Current CoverLetter.md", prompt)

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
