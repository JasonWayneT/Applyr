#!/usr/bin/env python3
"""Tests for the five-JD first-draft quality cohort reporter."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import contracts
from run_quality_cohort import (
    EXIT_INCOMPLETE,
    EXIT_SIGNAL_FAILED,
    evaluate_cohort,
    main,
)
from workflow.receipts import build_receipt

_ROOT = _SCRIPT_DIR.parent


def _sha256(path: Path) -> str:
    """Return a fixture file SHA-256."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    """Write a fixture JSON value."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _breakdown(side: str, total: float) -> dict[str, float]:
    """Build a complete valid rubric breakdown with the requested total."""
    maxima = contracts.RUBRIC_BREAKDOWN_MAX[side]
    remaining = float(total)
    values: dict[str, float] = {}
    for key in contracts.RUBRIC_BREAKDOWN_KEYS[side]:
        value = min(float(maxima[key]), remaining)
        values[key] = value
        remaining -= value
    if remaining:
        raise AssertionError(f"fixture total {total} exceeds {side} maximum")
    return values


def _seed_case(
    root: Path,
    slug: str,
    *,
    resume_total: float = 74,
    cover_total: float = 69,
    decision: str = "PASS",
    observed_at: str = "2026-09-15T12:00:00Z",
    workflow_status: str = "PRACTICE_COMPLETE",
    include_draft: bool = True,
    jd_text: str | None = None,
) -> Path:
    """Create one synthetic cohort case and return its folder."""
    folder = root / slug
    folder.mkdir(parents=True)
    (folder / "Original_JD.txt").write_text(
        jd_text if jd_text is not None else f"{slug} Product Manager role\n",
        encoding="utf-8",
    )
    _write_json(
        folder / "stage0_fit_gate.json",
        {
            "company": slug,
            "decision": decision,
            "required": ["Own roadmap"],
            "preferred": [],
            "responsibilities": ["Ship features"],
            "flagged_gaps": [],
            "stage_signal": "existing product",
            "thin_jd": False,
        },
    )
    gate_path = folder / "stage0_fit_gate.json"
    jd_path = folder / "Original_JD.txt"
    stage0_status = "COMPLETE" if decision == "PASS" else "SKIPPED"
    receipt = build_receipt(
        stage="stage0",
        status=stage0_status,
        mode="practice",
        input_hashes={"Original_JD.txt": _sha256(jd_path)},
        output_hashes={"stage0_fit_gate.json": _sha256(gate_path)},
        result={"decision": decision},
        checks={"contracts.check_stage0_fit_gate": True},
    )
    _write_json(folder / "stage_receipts" / "stage0.json", receipt)
    _write_json(
        folder / "workflow_state.json",
        {
            "mode": "practice",
            "status": workflow_status,
            "stages": {
                "stage0": {
                    "status": stage0_status,
                    "receipt_id": receipt["receipt_id"],
                    "integrity": "CLEAN",
                }
            },
        },
    )
    if decision == "SKIP" or not include_draft:
        return folder

    snapshot = folder / "stage1_first_draft"
    snapshot.mkdir()
    (snapshot / "Resume.md").write_text(f"Resume for {slug}\n", encoding="utf-8")
    (snapshot / "CoverLetter.md").write_text(
        f"Cover letter for {slug}\n", encoding="utf-8"
    )
    hashes = {
        "resume": _sha256(snapshot / "Resume.md"),
        "cover_letter": _sha256(snapshot / "CoverLetter.md"),
    }
    _write_json(
        snapshot / "verify_history.json",
        [
            {
                "attempt": 1,
                "observed_at": observed_at,
                "passed": True,
                "resume_sha256": hashes["resume"],
                "cover_sha256": hashes["cover_letter"],
                "violations": [],
            }
        ],
    )
    _write_json(
        folder / "reviews" / "rubric_scorecard.json",
        [
            {
                "schema_version": 1,
                "rubric_sha256": _sha256(_ROOT / "data" / "conversion_rubric.md"),
                "scored_at": observed_at,
                "reviewer_role": "authoring_session",
                "reviewer_run_id": f"author-{slug}",
                "document_sha256": hashes,
                "resume": {
                    "total": resume_total,
                    "breakdown": _breakdown("resume", resume_total),
                },
                "cover_letter": {
                    "total": cover_total,
                    "breakdown": _breakdown("cover_letter", cover_total),
                },
            }
        ],
    )
    return folder


class QualityCohortTests(unittest.TestCase):
    """Exercise denominator integrity and untouched floor tracking."""

    def setUp(self) -> None:
        """Create an isolated fixture root for each test."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def _five(self) -> list[Path]:
        """Create five distinct passing first-draft cases."""
        return [
            _seed_case(
                self.root,
                f"jd_{index}",
                observed_at=f"2026-09-15T12:00:0{index}Z",
            )
            for index in range(1, 6)
        ]

    def test_exact_five_distinct_cases_complete_denominator(self) -> None:
        """Five valid cases fill the denominator and pass the floor signal."""
        report = evaluate_cohort(self._five())
        self.assertEqual(report["denominator_status"], "COMPLETE")
        self.assertEqual(report["eligible_count"], 5)
        self.assertEqual(
            report["first_draft_signal"]["pairs_clearing_both_floors"], 5
        )
        self.assertEqual(report["first_draft_signal"]["status"], "PASS")
        self.assertTrue(all(row["denominator_included"] for row in report["cases"]))

    def test_skip_is_preserved_but_replacement_keeps_denominator_at_five(self) -> None:
        """A Skip stays visible while five eligible replacements fill the denominator."""
        skipped = _seed_case(self.root, "skipped", decision="SKIP")
        report = evaluate_cohort([skipped, *self._five()])
        self.assertEqual(report["attempted_count"], 6)
        self.assertEqual(report["eligible_count"], 5)
        self.assertEqual(report["excluded_count"], 1)
        self.assertEqual(report["denominator_status"], "COMPLETE")
        self.assertEqual(report["cases"][0]["classification"], "EXCLUDED_SKIP")
        self.assertFalse(report["cases"][0]["denominator_included"])

    def test_block_is_preserved_outside_denominator(self) -> None:
        """A failed no-draft run is retained as an excluded Block."""
        blocked = _seed_case(
            self.root,
            "blocked",
            workflow_status="FAILED",
            include_draft=False,
        )
        report = evaluate_cohort([blocked, *self._five()])
        self.assertEqual(report["cases"][0]["classification"], "EXCLUDED_BLOCK")
        self.assertEqual(report["denominator_status"], "COMPLETE")

    def test_fewer_than_five_eligible_cases_is_incomplete(self) -> None:
        """Four eligible cases cannot silently shrink the denominator."""
        report = evaluate_cohort(self._five()[:4])
        self.assertEqual(report["denominator_status"], "INCOMPLETE")
        self.assertEqual(report["first_draft_signal"]["status"], "NOT_EVALUABLE")
        self.assertIn("exactly 5", report["errors"][0])

    def test_more_than_five_eligible_cases_requires_explicit_selection(self) -> None:
        """Six eligible cases cannot be silently truncated to five."""
        folders = self._five()
        folders.append(_seed_case(self.root, "jd_6"))
        report = evaluate_cohort(folders)
        self.assertEqual(report["denominator_status"], "INCOMPLETE")
        self.assertIn("select exactly 5", report["errors"][0])

    def test_duplicate_jd_content_invalidates_denominator(self) -> None:
        """Byte-identical JDs do not count as distinct denominator entries."""
        folders = self._five()
        duplicate = _seed_case(
            self.root,
            "jd_5_duplicate",
            jd_text=(folders[0] / "Original_JD.txt").read_text(encoding="utf-8"),
        )
        folders[-1] = duplicate
        report = evaluate_cohort(folders)
        self.assertEqual(report["denominator_status"], "INCOMPLETE")
        self.assertTrue(any("duplicate Original_JD" in error for error in report["errors"]))

    def test_stale_stage0_receipt_fails_closed(self) -> None:
        """A JD changed after its Stage 0 receipt cannot enter the denominator."""
        folders = self._five()
        (folders[0] / "Original_JD.txt").write_text(
            "mutated JD after stage0\n", encoding="utf-8"
        )
        report = evaluate_cohort(folders)
        self.assertEqual(report["eligible_count"], 4)
        self.assertEqual(report["denominator_status"], "INCOMPLETE")
        self.assertTrue(
            any("receipt hash is stale" in error for error in report["errors"])
        )

    def test_snapshot_hash_mismatch_fails_closed(self) -> None:
        """A mutated first-draft snapshot cannot enter the denominator."""
        folders = self._five()
        (folders[0] / "stage1_first_draft" / "Resume.md").write_text(
            "mutated snapshot\n", encoding="utf-8"
        )
        report = evaluate_cohort(folders)
        self.assertEqual(report["eligible_count"], 4)
        self.assertEqual(report["cases"][0]["classification"], "PENDING")
        self.assertTrue(
            any("does not match immutable" in error for error in report["cases"][0]["errors"])
        )

    def test_scorecard_hash_mismatch_fails_closed(self) -> None:
        """A score for different bytes cannot score the immutable first draft."""
        folders = self._five()
        score_path = folders[0] / "reviews" / "rubric_scorecard.json"
        rows = json.loads(score_path.read_text(encoding="utf-8"))
        rows[0]["document_sha256"]["resume"] = "0" * 64
        _write_json(score_path, rows)
        report = evaluate_cohort(folders)
        self.assertEqual(report["eligible_count"], 4)
        self.assertTrue(
            any(
                "exactly one authoring_session row" in error
                for error in report["cases"][0]["errors"]
            )
        )

    def test_four_of_five_floor_pairs_pass_signal(self) -> None:
        """One isolated below-floor pair retains the four-of-five PASS signal."""
        folders = self._five()
        weak = _seed_case(
            self.root,
            "weak",
            resume_total=64,
            cover_total=57,
            observed_at="2026-09-15T12:00:03Z",
        )
        folders[2] = weak
        report = evaluate_cohort(folders)
        self.assertEqual(report["first_draft_signal"]["pairs_clearing_both_floors"], 4)
        self.assertEqual(report["first_draft_signal"]["status"], "PASS")

    def test_corrected_score_does_not_replace_untouched_score(self) -> None:
        """A later high score cannot be presented as first-draft performance."""
        folders = self._five()
        score_path = folders[0] / "reviews" / "rubric_scorecard.json"
        rows = json.loads(score_path.read_text(encoding="utf-8"))
        rows[0]["resume"]["total"] = 64
        rows[0]["resume"]["breakdown"] = _breakdown("resume", 64)
        corrected = json.loads(json.dumps(rows[0]))
        corrected["reviewer_role"] = "correcting_implementer"
        corrected["reviewer_run_id"] = "correction-1"
        corrected["resume"]["total"] = 78
        corrected["resume"]["breakdown"] = _breakdown("resume", 78)
        rows.append(corrected)
        _write_json(score_path, rows)

        report = evaluate_cohort(folders)
        first = report["cases"][0]
        self.assertEqual(first["first_draft_scores"]["resume"], 64)
        self.assertFalse(first["first_draft_floor"]["resume_pass"])

    def test_two_consecutive_below_floor_resumes_fail_signal(self) -> None:
        """Adjacent eligible runs below the resume floor fail the sequence signal."""
        folders = self._five()
        folders[1] = _seed_case(
            self.root,
            "weak_2",
            resume_total=64,
            observed_at="2026-09-15T12:00:02Z",
        )
        folders[2] = _seed_case(
            self.root,
            "weak_3",
            resume_total=65,
            observed_at="2026-09-15T12:00:03Z",
        )
        report = evaluate_cohort(folders)
        signal = report["first_draft_signal"]
        self.assertEqual(signal["status"], "FAIL")
        self.assertFalse(signal["no_two_consecutive_resume_below_floor"])
        self.assertEqual(signal["consecutive_resume_below_floor"], [["weak_2", "weak_3"]])

    def test_cli_exit_codes_distinguish_signal_failure_and_incomplete(self) -> None:
        """CLI returns one for quality failure and two for an incomplete denominator."""
        folders = self._five()
        folders[0] = _seed_case(self.root, "weak_1", resume_total=64)
        folders[1] = _seed_case(self.root, "weak_2", resume_total=65)
        self.assertEqual(main([str(folder) for folder in folders]), EXIT_SIGNAL_FAILED)
        self.assertEqual(
            main([str(folder) for folder in folders[:4]]),
            EXIT_INCOMPLETE,
        )

    def test_cli_writes_optional_report_without_changing_cases(self) -> None:
        """The optional output contains the evaluated report."""
        folders = self._five()
        output = self.root / "reports" / "cohort.json"
        before = {
            path: path.read_bytes()
            for folder in folders
            for path in folder.rglob("*")
            if path.is_file()
        }
        self.assertEqual(
            main(["--out", str(output), *[str(folder) for folder in folders]]),
            0,
        )
        persisted = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(persisted["denominator_status"], "COMPLETE")
        after = {path: path.read_bytes() for path in before}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
