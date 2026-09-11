#!/usr/bin/env python3
"""Offline tests for scripts/audit_packet_integrity.py (CR-112 Story 1.4)."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_packet_integrity import (  # noqa: E402
    EXIT_CLEAN,
    EXIT_FLAGGED,
    EXIT_INCOMPLETE,
    classify_findings,
    format_report,
    is_wiped_constraints_packet,
    main,
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


def _run_cli(root: Path) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(["--root", str(root)])
    return code, buf.getvalue()


class TestAuditPacketIntegrityCli(unittest.TestCase):
    """R10 P2: CLI must distinguish clean, flagged, and unable-to-inspect."""

    def test_corrupt_json_is_incomplete_not_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "broken"
            folder.mkdir()
            (folder / "authoring_packet.json").write_text("{not json", encoding="utf-8")
            code, out = _run_cli(root)
            self.assertEqual(code, EXIT_INCOMPLETE)
            self.assertIn("unable-to-inspect 1", out)
            self.assertIn("Incomplete inspection", out)
            self.assertNotIn("No wiped-constraint ready packets found.", out)

    def test_non_object_payload_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "array"
            folder.mkdir()
            (folder / "authoring_packet.json").write_text("[]", encoding="utf-8")
            code, out = _run_cli(root)
            self.assertEqual(code, EXIT_INCOMPLETE)
            self.assertIn("packet is not an object", out)
            self.assertNotIn("No wiped-constraint ready packets found.", out)

    def _healthy_payload(self) -> dict:
        return {
            "packet_status": "ready",
            "claim_constraints": {"ACC-101-PM": {"attribution": "OWNED"}},
            "evidence_map": [{"jd_item": "x", "claim_ids": ["ACC-101-PM"]}],
            "soft_gaps": [],
            "estimated_tokens": 4000,
        }

    def _assert_field_type_incomplete(self, payload: dict, field: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(root / f"bad_{field}", payload)
            _write_packet(root / "healthy", self._healthy_payload())
            findings = scan_packets(root)
            slugs = {row.get("slug"): row for row in findings}
            self.assertFalse(slugs[f"bad_{field}"].get("inspect_ok"), field)
            self.assertIn(field, slugs[f"bad_{field}"].get("error", ""), field)
            self.assertTrue(slugs["healthy"].get("inspect_ok"), field)
            self.assertFalse(slugs["healthy"]["flagged"], field)
            code, out = _run_cli(root)
            self.assertEqual(code, EXIT_INCOMPLETE, field)
            self.assertIn("unable-to-inspect 1", out)

    def test_invalid_claim_constraints_type_is_incomplete(self) -> None:
        self._assert_field_type_incomplete(
            {
                "packet_status": "ready",
                "claim_constraints": ["not", "an", "object"],
                "evidence_map": [],
                "soft_gaps": [],
            },
            "claim_constraints",
        )

    def test_invalid_evidence_map_type_is_incomplete(self) -> None:
        self._assert_field_type_incomplete(
            {
                "packet_status": "ready",
                "claim_constraints": {},
                "evidence_map": "also-not-a-list",
                "soft_gaps": [],
            },
            "evidence_map",
        )

    def test_invalid_soft_gaps_type_is_incomplete(self) -> None:
        self._assert_field_type_incomplete(
            {
                "packet_status": "ready",
                "claim_constraints": {},
                "evidence_map": [],
                "soft_gaps": {"not": "a-list"},
            },
            "soft_gaps",
        )

    def test_malformed_claim_constraints_alone_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(
                root / "bad_constraints",
                {
                    "packet_status": "ready",
                    "claim_constraints": ["not", "an", "object"],
                    "evidence_map": [],
                    "soft_gaps": [],
                },
            )
            findings = scan_packets(root)
            self.assertEqual(len(findings), 1)
            self.assertFalse(findings[0]["inspect_ok"])
            self.assertIn("claim_constraints", findings[0]["error"])
            code, out = _run_cli(root)
            self.assertEqual(code, EXIT_INCOMPLETE)
            self.assertIn("unable-to-inspect 1", out)

    def test_malformed_evidence_map_alone_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(
                root / "bad_evidence_map",
                {
                    "packet_status": "ready",
                    "claim_constraints": {"ACC-101-PM": {"attribution": "OWNED"}},
                    "evidence_map": "not-a-list",
                    "soft_gaps": [],
                },
            )
            findings = scan_packets(root)
            self.assertEqual(len(findings), 1)
            self.assertFalse(findings[0]["inspect_ok"])
            self.assertIn("evidence_map", findings[0]["error"])
            code, out = _run_cli(root)
            self.assertEqual(code, EXIT_INCOMPLETE)
            self.assertIn("unable-to-inspect 1", out)

    def test_malformed_soft_gaps_alone_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(
                root / "bad_soft_gaps",
                {
                    "packet_status": "ready",
                    "claim_constraints": {"ACC-101-PM": {"attribution": "OWNED"}},
                    "evidence_map": [],
                    "soft_gaps": {"not": "a-list"},
                },
            )
            findings = scan_packets(root)
            self.assertEqual(len(findings), 1)
            self.assertFalse(findings[0]["inspect_ok"])
            self.assertIn("soft_gaps", findings[0]["error"])
            code, out = _run_cli(root)
            self.assertEqual(code, EXIT_INCOMPLETE)
            self.assertIn("unable-to-inspect 1", out)

    def test_invalid_utf8_packet_is_incomplete_and_scan_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "bad_bytes"
            good = root / "healthy"
            bad.mkdir()
            (bad / "authoring_packet.json").write_bytes(b'{"packet_status": "ready", "x": "\xff"}')
            _write_packet(
                good,
                {
                    "packet_status": "ready",
                    "claim_constraints": {"ACC-101-PM": {"attribution": "OWNED"}},
                    "evidence_map": [{"jd_item": "x", "claim_ids": ["ACC-101-PM"]}],
                    "soft_gaps": [],
                },
            )
            findings = scan_packets(root)
            slugs = {row.get("slug"): row for row in findings}
            self.assertFalse(slugs["bad_bytes"].get("inspect_ok"))
            self.assertIn("unreadable packet", slugs["bad_bytes"]["error"])
            self.assertTrue(slugs["healthy"].get("inspect_ok"))
            self.assertFalse(slugs["healthy"]["flagged"])
            code, out = _run_cli(root)
            self.assertEqual(code, EXIT_INCOMPLETE)
            self.assertIn("unable-to-inspect 1", out)
            self.assertIn("Incomplete inspection", out)
            self.assertNotIn("No wiped-constraint ready packets found.", out)

    def test_unreadable_disposition_does_not_abort_or_unflag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "wiped"
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
            (folder / "packet_integrity_disposition.json").write_bytes(b'{"verdict": "\xff"}')
            findings = scan_packets(root)
            self.assertEqual(len(findings), 1)
            self.assertTrue(findings[0]["inspect_ok"])
            self.assertTrue(findings[0]["flagged"])
            self.assertEqual(
                findings[0]["disposition"],
                {"error": "unreadable disposition sidecar"},
            )
            code, out = _run_cli(root)
            self.assertEqual(code, EXIT_FLAGGED)
            self.assertIn("flagged 1", out)
            self.assertIn("unable-to-inspect 0", out)
            self.assertIn("sidecar_error=unreadable disposition sidecar", out)
            self.assertNotIn("sidecar_verdict=recorded", out)

    def test_unreadable_disposition_on_healthy_stays_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "healthy"
            _write_packet(
                folder,
                {
                    "packet_status": "ready",
                    "claim_constraints": {"ACC-101-PM": {"attribution": "OWNED"}},
                    "evidence_map": [{"jd_item": "x", "claim_ids": ["ACC-101-PM"]}],
                    "soft_gaps": [],
                },
            )
            (folder / "packet_integrity_disposition.json").write_bytes(b'{"verdict": "\xff"}')
            findings = scan_packets(root)
            self.assertTrue(findings[0]["inspect_ok"])
            self.assertFalse(findings[0]["flagged"])
            self.assertEqual(
                findings[0]["disposition"],
                {"error": "unreadable disposition sidecar"},
            )
            code, out = _run_cli(root)
            self.assertEqual(code, EXIT_CLEAN)
            self.assertIn("No wiped-constraint ready packets found.", out)

    def test_nonexistent_root_is_incomplete(self) -> None:
        missing = Path(tempfile.gettempdir()) / "applyr-missing-audit-root-does-not-exist"
        if missing.exists():
            self.fail("precondition: sentinel path must not exist")
        code, out = _run_cli(missing)
        self.assertEqual(code, EXIT_INCOMPLETE)
        self.assertIn("root is not a directory", out)
        self.assertIn("Incomplete inspection", out)
        self.assertNotIn("No wiped-constraint ready packets found.", out)

    def test_empty_existing_root_is_zero_inspected_not_safety(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            findings = scan_packets(root)
            self.assertEqual(findings, [])
            self.assertEqual(classify_findings(findings), EXIT_CLEAN)
            code, out = _run_cli(root)
            self.assertEqual(code, EXIT_CLEAN)
            self.assertIn("Inspected 0 packets. This is not evidence of safety.", out)
            self.assertNotIn("No wiped-constraint ready packets found.", out)

    def test_healthy_control_is_clean_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(
                root / "healthy",
                {
                    "packet_status": "ready",
                    "claim_constraints": {"ACC-101-PM": {"attribution": "OWNED"}},
                    "evidence_map": [{"jd_item": "x", "claim_ids": ["ACC-101-PM"]}],
                    "soft_gaps": [],
                    "estimated_tokens": 4000,
                },
            )
            code, out = _run_cli(root)
            self.assertEqual(code, EXIT_CLEAN)
            self.assertIn("Inspected 1 packet(s); flagged 0; unable-to-inspect 0.", out)
            self.assertIn("No wiped-constraint ready packets found.", out)

    def test_flagged_control_still_exits_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_packet(
                root / "wiped",
                {
                    "packet_status": "ready",
                    "claim_constraints": {},
                    "evidence_map": [{"jd_item": "x"}],
                    "soft_gaps": [],
                    "estimated_tokens": 7227,
                },
            )
            code, out = _run_cli(root)
            self.assertEqual(code, EXIT_FLAGGED)
            self.assertIn("flagged 1", out)
            self.assertIn("wiped", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
