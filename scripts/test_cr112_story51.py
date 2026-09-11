"""Tests for the CR-112 Story 5.1 trailing-gerund reporter."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "report_resume_gerund_rate.py"
RUN_SUBMISSION_PATH = REPO_ROOT / "scripts" / "run_submission.py"
SUBMISSION_LINTER_PATH = REPO_ROOT / "scripts" / "submission_linter.py"


def load_reporter_module() -> ModuleType:
    """Load the Story 5.1 reporter module from disk."""
    spec = importlib.util.spec_from_file_location("report_resume_gerund_rate", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load reporter module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestCr112Story51(unittest.TestCase):
    """Exercise the advisory trailing-mechanism reporter against temp resumes."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_resume(self, slug: str, lines: list[str]) -> Path:
        folder = self.root / slug
        folder.mkdir(parents=True, exist_ok=True)
        resume_path = folder / "Resume.md"
        resume_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return resume_path

    def _scan(self, slug: str, lines: list[str]) -> dict[str, object]:
        self._write_resume(slug, lines)
        reporter = load_reporter_module()
        results = reporter.scan_root(self.root)
        self.assertEqual(len(results), 1)
        return results[0].to_dict()

    def test_ac_51_1_counts_by_clause(self) -> None:
        result = self._scan("story51", ["- Reduced outages by adding storage alerts."])
        self.assertEqual(result["trailing_mechanism_count"], 1)
        self.assertEqual(result["examples"], ["- Reduced outages by adding storage alerts."])

    def test_ac_51_2_counts_while_clause(self) -> None:
        result = self._scan("story51", ["- Partnered with legal while aligning the cutover."])
        self.assertEqual(result["trailing_mechanism_count"], 1)

    def test_ac_51_3_counts_comma_clause(self) -> None:
        result = self._scan("story51", ["- Shipped the ingest cutover, reducing repeat incidents."])
        self.assertEqual(result["trailing_mechanism_count"], 1)

    def test_ac_51_4_ignores_plain_bullet(self) -> None:
        result = self._scan("story51", ["- Owned the platform roadmap for eight scrum teams."])
        self.assertEqual(result["trailing_mechanism_count"], 0)
        self.assertEqual(result["examples"], [])

    def test_ac_51_5_ignores_end_gerund(self) -> None:
        result = self._scan("story51", ["- Partnered with engineering on sequencing."])
        self.assertEqual(result["trailing_mechanism_count"], 0)

    def test_ac_51_6_ignores_after_clause(self) -> None:
        result = self._scan("story51", ["- Shipped the ingest cutover after aligning legal."])
        self.assertEqual(result["trailing_mechanism_count"], 0)

    def test_ac_51_7_empty_bullet_list_returns_zeroes(self) -> None:
        result = self._scan("story51", ["# Resume", "## PROFESSIONAL EXPERIENCE"])
        self.assertEqual(result["bullet_count"], 0)
        self.assertEqual(result["trailing_mechanism_count"], 0)
        self.assertEqual(result["rate"], 0.0)
        self.assertEqual(result["examples"], [])

    def test_ac_51_8_cli_exits_zero_keeps_bytes_and_prints_footer(self) -> None:
        resume_path = self._write_resume("story51", ["- Reduced outages by adding storage alerts."])
        before_bytes = resume_path.read_bytes()
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--root", str(self.root)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        after_bytes = resume_path.read_bytes()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(before_bytes, after_bytes)
        self.assertIn("Advisory only. No linter rule. No rewrite.", result.stdout)

        json_result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--root", str(self.root), "--json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json_result.returncode, 0)
        payload = json.loads(json_result.stdout)
        self.assertEqual(payload[0]["slug"], "story51")
        self.assertIn("bullet_count", payload[0])
        self.assertIn("trailing_mechanism_count", payload[0])
        self.assertIn("rate", payload[0])
        self.assertIn("examples", payload[0])

    def test_ac_51_9_skips_folder_without_resume(self) -> None:
        (self.root / "missing_resume").mkdir(parents=True, exist_ok=True)
        reporter = load_reporter_module()
        self.assertEqual(reporter.scan_root(self.root), [])

    def test_default_root_is_repo_relative(self) -> None:
        reporter = load_reporter_module()
        expected_root = REPO_ROOT / "data" / "submissions"
        self.assertEqual(reporter.DEFAULT_ROOT, expected_root)
        self.assertEqual(reporter.build_parser().parse_args([]).root, str(expected_root))

    def test_ac_51_10_reporter_is_not_wired_into_linter_or_workflow(self) -> None:
        run_submission_text = RUN_SUBMISSION_PATH.read_text(encoding="utf-8")
        submission_linter_text = SUBMISSION_LINTER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("report_resume_gerund_rate", run_submission_text)
        self.assertNotIn("report_resume_gerund_rate", submission_linter_text)

    def test_ac_51_11_uses_temp_synthetic_roots_only(self) -> None:
        self._write_resume("story51", ["- Reduced outages by adding storage alerts."])
        reporter = load_reporter_module()
        results = reporter.scan_root(self.root)
        self.assertEqual([result.slug for result in results], ["story51"])
        self.assertFalse(str(self.root).lower().endswith("data\\submissions"))


if __name__ == "__main__":
    unittest.main()
