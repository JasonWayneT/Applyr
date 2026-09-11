#!/usr/bin/env python3
"""Offline tests for scripts/audit_packet_integrity.py (CR-112 Story 1.4)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_packet_integrity import (  # noqa: E402
    format_report,
    is_wiped_constraints_packet,
    scan_packets,
)


def _write_packet(folder: Path, payload: dict) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "authoring_packet.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestAuditPacketIntegrity(unittest.TestCase):
    def test_flags_ready_empty_constraints_with_evidence(self) -> None:
        """Implements FR-298 / AC-395."""
        packet = {
            "packet_status": "ready",
            "claim_constraints": {},
            "evidence_map": [{"jd_item": "x", "claim_ids": ["ACC-105-AGILE"]}],
            "soft_gaps": [],
            "estimated_tokens": 7227,
        }
        self.assertTrue(is_wiped_constraints_packet(packet))

    def test_does_not_flag_ready_with_constraints(self) -> None:
        packet = {
            "packet_status": "ready",
            "claim_constraints": {"ACC-105-AGILE": {"attribution": "OWNED"}},
            "evidence_map": [{"jd_item": "x", "claim_ids": ["ACC-105-AGILE"]}],
            "soft_gaps": [],
        }
        self.assertFalse(is_wiped_constraints_packet(packet))

    def test_does_not_flag_incomplete_empty_constraints(self) -> None:
        packet = {
            "packet_status": "incomplete",
            "claim_constraints": {},
            "evidence_map": [{"jd_item": "x"}],
            "soft_gaps": [],
        }
        self.assertFalse(is_wiped_constraints_packet(packet))

    def test_does_not_flag_ready_empty_when_no_evidence(self) -> None:
        packet = {
            "packet_status": "ready",
            "claim_constraints": {},
            "evidence_map": [],
            "soft_gaps": [],
        }
        self.assertFalse(is_wiped_constraints_packet(packet))

    def test_flags_ready_empty_constraints_with_soft_gaps_only(self) -> None:
        packet = {
            "packet_status": "ready",
            "claim_constraints": None,
            "evidence_map": [],
            "soft_gaps": [{"item": "SQL", "class": "SOFT"}],
        }
        self.assertTrue(is_wiped_constraints_packet(packet))

    def test_scan_is_read_only_and_skips_missing_packets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flagged_dir = root / "supplyhouse"
            clean_dir = root / "arbiter"
            skip_dir = root / "no_packet"
            skip_dir.mkdir()
            flagged_path = _write_packet(
                flagged_dir,
                {
                    "packet_status": "ready",
                    "claim_constraints": {},
                    "evidence_map": [{"jd_item": "x", "claim_ids": ["ACC-101-PM"]}],
                    "soft_gaps": [],
                    "estimated_tokens": 7227,
                },
            )
            _write_packet(
                clean_dir,
                {
                    "packet_status": "ready",
                    "claim_constraints": {"ACC-101-PM": {"attribution": "OWNED"}},
                    "evidence_map": [{"jd_item": "x", "claim_ids": ["ACC-101-PM"]}],
                    "soft_gaps": [],
                    "estimated_tokens": 4000,
                },
            )
            before_mtime = flagged_path.stat().st_mtime
            before_bytes = flagged_path.read_bytes()
            findings = scan_packets(root)
            self.assertEqual(flagged_path.read_bytes(), before_bytes)
            self.assertEqual(flagged_path.stat().st_mtime, before_mtime)
            slugs = {row["slug"]: row for row in findings}
            self.assertIn("supplyhouse", slugs)
            self.assertTrue(slugs["supplyhouse"]["flagged"])
            self.assertEqual(slugs["supplyhouse"]["constraint_count"], 0)
            self.assertIn("arbiter", slugs)
            self.assertFalse(slugs["arbiter"]["flagged"])
            self.assertIsNone(slugs["supplyhouse"]["disposition"])
            self.assertNotIn("no_packet", slugs)

    def test_disposition_sidecar_does_not_unflag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "supplyhouse"
            _write_packet(
                folder,
                {
                    "packet_status": "ready",
                    "claim_constraints": {},
                    "evidence_map": [{"jd_item": "x"}],
                    "soft_gaps": [],
                    "estimated_tokens": 7227,
                },
            )
            (folder / "packet_integrity_disposition.json").write_text(
                json.dumps(
                    {
                        "verdict": "HUMAN_ACCEPTED_RISK",
                        "reason": "end product corrected separately",
                    }
                ),
                encoding="utf-8",
            )
            findings = scan_packets(root)
            self.assertTrue(findings[0]["flagged"])
            self.assertEqual(findings[0]["disposition"]["verdict"], "HUMAN_ACCEPTED_RISK")
            report = format_report(findings)
            self.assertIn("supplyhouse", report)
            self.assertIn("informational; not authorization", report)
            self.assertNotIn("drafts are accepted", report)


if __name__ == "__main__":
    unittest.main(verbosity=2)
