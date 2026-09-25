#!/usr/bin/env python3
"""Tests for sandboxed Stage 2 Agy rubric scoring (CR-121 / FR-356).

No live Agy. No utils.call_llm.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_stage2_rubric as rubric  # noqa: E402


def _fill(max_values: dict[str, int], total: int) -> dict[str, int]:
    remaining = total
    breakdown: dict[str, int] = {}
    for key, maximum in max_values.items():
        value = min(remaining, maximum)
        breakdown[key] = value
        remaining -= value
    return breakdown


def _payload(resume_total: int = 63, cover_total: int = 74) -> dict:
    resume = _fill(
        {"R1": 10, "R2": 15, "R3": 15, "R4": 20, "R5": 15, "R6": 10, "R7": 10, "R8": 5},
        resume_total,
    )
    cover = _fill({"C1": 25, "C2": 25, "C3": 20, "C4": 20, "C5": 10}, cover_total)
    return {
        "resume": {"total": resume_total, "breakdown": resume, "citations": {}},
        "cover_letter": {"total": cover_total, "breakdown": cover, "citations": {}},
    }


def _fence(payload: dict) -> str:
    return "```json\n" + json.dumps(payload) + "\n```"


class TestParseAndBind(unittest.TestCase):
    def test_module_does_not_import_call_llm(self) -> None:
        source = Path(rubric.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
                imported.extend(alias.name for alias in node.names)
        blob = " ".join(imported)
        self.assertNotIn("call_llm", blob)
        self.assertNotIn("eval_submission", blob)
        self.assertNotIn("utils", blob)

    def test_parse_fenced_json(self) -> None:
        parsed = rubric.parse_score_payload(_fence(_payload()))
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["resume"]["total"], 63)
        self.assertEqual(parsed["cover_letter"]["total"], 74)
        self.assertEqual(set(parsed["resume"]["breakdown"]), set(f"R{i}" for i in range(1, 9)))

    def test_bind_scorecard_row_hashes_documents(self) -> None:
        parsed = rubric.parse_score_payload(_fence(_payload()))
        assert parsed is not None
        hashes = {"resume": "a" * 64, "cover_letter": "b" * 64}
        row = rubric.bind_scorecard_row(
            parsed,
            hashes=hashes,
            role="authoring_session",
            reviewer_run_id="test-1",
            scored_at="2026-09-21T00:00:00+00:00",
        )
        self.assertEqual(row["schema_version"], 1)
        self.assertEqual(row["document_sha256"], hashes)
        self.assertEqual(row["reviewer_role"], "authoring_session")
        self.assertTrue(row["rubric_sha256"])

    def test_disagree_low_binds(self) -> None:
        high_parsed = rubric.parse_score_payload(_fence(_payload(72, 70)))
        low_parsed = rubric.parse_score_payload(_fence(_payload(64, 70)))
        self.assertIsNotNone(high_parsed)
        self.assertIsNotNone(low_parsed)
        assert high_parsed is not None and low_parsed is not None
        high = rubric.bind_scorecard_row(
            high_parsed,
            hashes={"resume": "a", "cover_letter": "b"},
            role="authoring_session",
            reviewer_run_id="s",
            scored_at="2026-09-21T00:00:00+00:00",
        )
        low = rubric.bind_scorecard_row(
            low_parsed,
            hashes={"resume": "a", "cover_letter": "b"},
            role="independent_blind",
            reviewer_run_id="b",
            scored_at="2026-09-21T00:00:00+00:00",
        )
        binding = rubric.choose_binding_row(high, low)
        self.assertEqual(binding["resume"]["total"], 64)
        self.assertEqual(binding["reviewer_role"], "independent_blind")

    def test_boundary_band_needs_blind(self) -> None:
        band_parsed = rubric.parse_score_payload(_fence(_payload(71, 74)))
        far_parsed = rubric.parse_score_payload(_fence(_payload(63, 74)))
        self.assertIsNotNone(band_parsed)
        self.assertIsNotNone(far_parsed)
        assert band_parsed is not None and far_parsed is not None
        row = rubric.bind_scorecard_row(
            band_parsed,
            hashes={"resume": "a", "cover_letter": "b"},
            role="authoring_session",
            reviewer_run_id="s",
            scored_at="2026-09-21T00:00:00+00:00",
        )
        self.assertTrue(rubric.needs_independent_blind(row))
        far = rubric.bind_scorecard_row(
            far_parsed,
            hashes={"resume": "a", "cover_letter": "b"},
            role="authoring_session",
            reviewer_run_id="s",
            scored_at="2026-09-21T00:00:00+00:00",
        )
        self.assertFalse(rubric.needs_independent_blind(far))

    def test_fail_closed_if_inflated(self) -> None:
        self.assertFalse(
            rubric.fail_closed_if_inflated(parked_resume=63, agy_resume=70)
        )
        self.assertTrue(
            rubric.fail_closed_if_inflated(parked_resume=63, agy_resume=64)
        )
        self.assertTrue(
            rubric.fail_closed_if_inflated(parked_resume=72, agy_resume=75)
        )


class TestRunForFolder(unittest.TestCase):
    def test_missing_docs_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            result = rubric.run_for_folder(folder)
        self.assertEqual(result["outcome"], "rubric_failed")
        self.assertEqual(result["reason"], "missing_docs")

    def test_fixture_json_writes_scorecard_and_manifest(self) -> None:
        payload = _payload(63, 74)

        def spawn(cmd, cwd):
            self.assertIn("--sandbox", cmd)
            proc = mock.Mock()
            proc.stdin = mock.Mock()
            proc.stdin.write = mock.Mock()
            proc.stdout = mock.Mock()
            return proc

        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "Resume.md").write_text("# Name\nresume\n", encoding="utf-8")
            (folder / "CoverLetter.md").write_text("Dear Hiring Manager,\n", encoding="utf-8")
            (folder / "Original_JD.txt").write_text("Product Manager\n", encoding="utf-8")
            (folder / "draft_manifest.json").write_text(
                json.dumps(
                    {
                        "company": "Velosio",
                        "title": "Product Manager",
                        "verification_passed": False,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(
                rubric,
                "run_author_process",
                return_value={"outcome": "ok", "text": _fence(payload)},
            ):
                result = rubric.run_for_folder(folder, spawn=spawn)
            self.assertEqual(result["outcome"], "ok")
            self.assertTrue((folder / "reviews" / "rubric_scorecard.json").is_file())
            rows = json.loads(
                (folder / "reviews" / "rubric_scorecard.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["resume"]["total"], 63)
            manifest = json.loads((folder / "draft_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["rubric_score"]["resume"]["total"], 63)
            self.assertIs(manifest["verification_passed"], False)
            resume_hash = hashlib.sha256((folder / "Resume.md").read_bytes()).hexdigest()
            self.assertEqual(rows[0]["document_sha256"]["resume"], resume_hash)

    def test_boundary_band_runs_second_session_and_binds_low(self) -> None:
        session = _payload(72, 70)
        blind = _payload(64, 70)
        calls: list[str] = []

        def fake_process(prompt, **kwargs):
            calls.append(prompt)
            payload = session if len(calls) == 1 else blind
            return {"outcome": "ok", "text": _fence(payload)}

        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "Resume.md").write_text("resume body\n", encoding="utf-8")
            (folder / "CoverLetter.md").write_text("cover body\n", encoding="utf-8")
            (folder / "Original_JD.txt").write_text("JD\n", encoding="utf-8")
            (folder / "draft_manifest.json").write_text(
                json.dumps(
                    {
                        "company": "Acme",
                        "title": "Product Manager",
                        "verification_passed": False,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(rubric, "run_author_process", side_effect=fake_process):
                result = rubric.run_for_folder(folder)
            self.assertEqual(result["outcome"], "ok")
            self.assertEqual(len(calls), 2)
            self.assertIn("not seen a prior score", calls[1])
            self.assertEqual(result["binding_resume"], 64)
            rows = json.loads(
                (folder / "reviews" / "rubric_scorecard.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1]["reviewer_role"], "independent_blind")


class TestHookGate(unittest.TestCase):
    def test_hook_off_by_default(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "APPLYR_STAGE2_AGY_RUBRIC"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertFalse(rubric.stage2_agy_rubric_enabled())

    def test_hook_requires_explicit_flag(self) -> None:
        with mock.patch.dict(os.environ, {"APPLYR_STAGE2_AGY_RUBRIC": "1"}):
            self.assertTrue(rubric.stage2_agy_rubric_enabled())


if __name__ == "__main__":
    unittest.main()
