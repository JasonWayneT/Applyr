#!/usr/bin/env python3
"""CR-112 Story 3.3 — advisory swap report (FR-304 / AC-401)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from report_evidence_swaps import build_swap_report, label_candidate, main as swap_main

_REPO = Path(__file__).resolve().parents[1]


def _dummy_drafts(folder: Path) -> dict[str, bytes]:
    payloads = {
        "Resume.md": b"# Resume\n* Did platform work.\n",
        "CoverLetter.md": b"Dear Hiring Manager,\nHello.\n",
        "authoring_packet.json": b'{"schema_version":"1.0","slug":"fixture"}\n',
    }
    for name, body in payloads.items():
        (folder / name).write_bytes(body)
    return payloads


class TestSwapReportLabels(unittest.TestCase):
    def test_top2_cutoff_is_swap_candidate(self) -> None:
        """AC-33-1."""
        self.assertEqual(
            label_candidate(
                {"claim_id": "ACC-101-SAVINGS", "reason": "top2_cutoff"},
                ["ACC-101-PM"],
            ),
            "SWAP_CANDIDATE",
        )

    def test_project_slot_cap_is_intentional_tradeoff(self) -> None:
        """AC-33-2."""
        self.assertEqual(
            label_candidate(
                {"claim_id": "ACC-102-OPS", "reason": "project_slot_cap"},
                [],
            ),
            "INTENTIONAL_TRADEOFF",
        )

    def test_score_zero_is_insufficient_proof(self) -> None:
        """AC-33-3."""
        self.assertEqual(
            label_candidate(
                {"claim_id": "ACC-103-ROADMAP", "reason": "score_zero"},
                [],
            ),
            "INSUFFICIENT_PROOF",
        )

    def test_picked_claim_is_not_labeled(self) -> None:
        """AC-33-6."""
        self.assertIsNone(
            label_candidate(
                {"claim_id": "ACC-101-PM", "reason": "top2_cutoff"},
                ["ACC-101-PM"],
            )
        )

    def test_unknown_reason_is_skipped(self) -> None:
        """AC-33-10."""
        report = build_swap_report(
            {
                "slug": "fixture",
                "packet_version": "v1",
                "items": [
                    {
                        "jd_item": "Own the platform",
                        "bucket": "required",
                        "picked": ["ACC-101-PM"],
                        "candidates": [
                            {"claim_id": "ACC-101-PM", "reason": "picked", "score": 90},
                            {
                                "claim_id": "ACC-199-MYSTERY",
                                "reason": "not_a_real_reason",
                                "score": 10,
                            },
                        ],
                    }
                ],
            }
        )
        self.assertEqual(report["rows"], [])

    def test_disabled_reason_is_skipped(self) -> None:
        """AC-33-10: dirty-main mapped disabled; Story 3.2 does not emit it."""
        self.assertIsNone(
            label_candidate({"claim_id": "ACC-114-COST", "reason": "disabled"}, [])
        )


class TestSwapReportItems(unittest.TestCase):
    def test_empty_item_without_filter_is_packet_missing(self) -> None:
        """AC-33-4."""
        report = build_swap_report(
            {
                "slug": "fixture",
                "packet_version": "v1",
                "items": [
                    {
                        "jd_item": "SQL warehouse",
                        "bucket": "required",
                        "picked": [],
                        "candidates": [],
                        "filter": None,
                    }
                ],
            }
        )
        row = report["rows"][0]
        self.assertEqual(row["label"], "PACKET_MISSING")
        self.assertIsNone(row["claim_id"])
        self.assertIsNone(row["reason"])
        self.assertEqual(report["packet_version"], "v1")

    def test_boilerplate_filter_is_tradeoff_not_missing(self) -> None:
        """AC-33-5: exact Story 3.2 TRACE shape."""
        report = build_swap_report(
            {
                "slug": "fixture",
                "packet_version": "v1",
                "items": [
                    {
                        "jd_item": "Excellent communication skills",
                        "bucket": "preferred",
                        "picked": [],
                        "candidates": [],
                        "filter": "boilerplate_filtered",
                    }
                ],
            }
        )
        row = report["rows"][0]
        self.assertEqual(row["label"], "INTENTIONAL_TRADEOFF")
        self.assertEqual(row["reason"], "boilerplate_filtered")
        self.assertNotEqual(row["label"], "PACKET_MISSING")
        self.assertIsNone(row["claim_id"])
        self.assertIsNone(row["rank"])
        self.assertIsNone(row["score"])

    def test_savings_rank_is_full_candidate_index(self) -> None:
        report = build_swap_report(
            {
                "slug": "pearl_like",
                "packet_version": "digestv1",
                "items": [
                    {
                        "jd_item": "Own cost and savings on the platform",
                        "bucket": "required",
                        "picked": ["ACC-101-PM", "ACC-102-OPS"],
                        "candidates": [
                            {
                                "claim_id": "ACC-101-PM",
                                "reason": "picked",
                                "score": 90,
                                "attribution": "OWNED",
                            },
                            {
                                "claim_id": "ACC-102-OPS",
                                "reason": "picked",
                                "score": 80,
                                "attribution": "OWNED",
                            },
                            {
                                "claim_id": "ACC-101-SAVINGS",
                                "reason": "top2_cutoff",
                                "score": 70,
                                "attribution": "CONTRIBUTED",
                            },
                        ],
                    }
                ],
            }
        )
        row = report["rows"][0]
        self.assertEqual(row["claim_id"], "ACC-101-SAVINGS")
        self.assertEqual(row["label"], "SWAP_CANDIDATE")
        self.assertEqual(row["rank"], 3)
        self.assertEqual(row["score"], 70)
        self.assertEqual(row["attribution"], "CONTRIBUTED")
        self.assertEqual(report["packet_version"], "digestv1")


class TestSwapReportCliIsolation(unittest.TestCase):
    def test_cli_does_not_rewrite_drafts(self) -> None:
        """AC-33-7."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            before = _dummy_drafts(folder)
            (folder / "evidence_selection_trace.json").write_text(
                json.dumps(
                    {
                        "slug": "fixture",
                        "packet_version": "v1",
                        "items": [
                            {
                                "jd_item": "Own cost and savings",
                                "picked": ["ACC-101-PM"],
                                "candidates": [
                                    {"claim_id": "ACC-101-PM", "reason": "picked"},
                                    {
                                        "claim_id": "ACC-101-SAVINGS",
                                        "reason": "top2_cutoff",
                                        "score": 70,
                                    },
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            rc = swap_main([str(folder)])
            self.assertEqual(rc, 0)
            self.assertTrue((folder / "evidence_swap_report.json").is_file())
            for name, body in before.items():
                self.assertEqual((folder / name).read_bytes(), body)

    def test_missing_trace_exits_without_report(self) -> None:
        """AC-33-8 missing."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            before = _dummy_drafts(folder)
            rc = swap_main([str(folder)])
            self.assertEqual(rc, 1)
            self.assertFalse((folder / "evidence_swap_report.json").exists())
            for name, body in before.items():
                self.assertEqual((folder / name).read_bytes(), body)

    def test_unreadable_trace_exits_without_report(self) -> None:
        """AC-33-8 unreadable JSON."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            before = _dummy_drafts(folder)
            (folder / "evidence_selection_trace.json").write_text(
                "{not-json", encoding="utf-8"
            )
            rc = swap_main([str(folder)])
            self.assertEqual(rc, 1)
            self.assertFalse((folder / "evidence_swap_report.json").exists())
            for name, body in before.items():
                self.assertEqual((folder / name).read_bytes(), body)


class TestNotWiredIntoPipeline(unittest.TestCase):
    def test_stage_scripts_do_not_reference_swap_report(self) -> None:
        """AC-33-9."""
        needles = ("evidence_swap_report", "report_evidence_swaps")
        paths = [
            _REPO / "scripts" / "author_from_packet.py",
            _REPO / "scripts" / "run_submission.py",
            _REPO / "scripts" / "finalize_submission_job.py",
        ]
        for path in paths:
            self.assertTrue(path.is_file(), path)
            text = path.read_text(encoding="utf-8")
            for needle in needles:
                self.assertNotIn(
                    needle,
                    text,
                    f"{path.name} must not reference {needle}",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
