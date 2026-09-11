#!/usr/bin/env python3
"""CR-112 Story 3.1 — closed-world extra-packet provenance WARN tests."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from author_from_packet import _warn_extra_packet_provenance
from packet_closed_world import extra_packet_findings, scan_extra_packet_folders


class TestExtraPacketWarn(unittest.TestCase):
    def test_prefix_match_does_not_clear_savings_vs_pm(self) -> None:
        """Implements FR-302 / AC-399."""
        packet = {
            "excerpts": {"ACC-101-PM": "Owned the platform stabilization work."},
            "evidence_map": [{"claim_ids": ["ACC-101-PM"]}],
            "soft_gaps": [],
        }
        provenance = {
            "resume_claims": [
                {"bullet": "Cut spend", "claim_ids": ["ACC-101-SAVINGS"]},
            ],
            "cover_letter_claims": [],
        }
        findings = extra_packet_findings(packet, provenance)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["claim_id"], "ACC-101-SAVINGS")
        self.assertEqual(findings[0]["id"], "truth.provenance.extra.ACC-101-SAVINGS")
        self.assertEqual(findings[0]["severity"], "WARN")

    def test_exact_packet_id_is_not_extra(self) -> None:
        packet = {
            "excerpts": {"ACC-101-SAVINGS": "Contributed to ingest savings."},
            "evidence_map": [],
            "soft_gaps": [],
        }
        provenance = {
            "resume_claims": [
                {"bullet": "Cut spend", "claim_ids": ["ACC-101-SAVINGS"]},
            ],
            "cover_letter_claims": [],
        }
        self.assertEqual(extra_packet_findings(packet, provenance), [])

    def test_warn_helper_does_not_emit_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            packet = {
                "excerpts": {"ACC-101-PM": "x"},
                "evidence_map": [{"claim_ids": ["ACC-101-PM"]}],
                "soft_gaps": [],
            }
            provenance = {
                "resume_claims": [{"bullet": "x", "claim_ids": ["ACC-101-SAVINGS"]}],
                "cover_letter_claims": [],
            }
            (folder / "authoring_packet.json").write_text(
                json.dumps(packet), encoding="utf-8"
            )
            (folder / "claim_provenance.json").write_text(
                json.dumps(provenance), encoding="utf-8"
            )
            lines = _warn_extra_packet_provenance(folder)
            self.assertTrue(lines)
            self.assertTrue(all(line.startswith("WARN [") for line in lines))
            self.assertFalse(any("FAIL" in line for line in lines))


class TestExtraPacketScanReadOnly(unittest.TestCase):
    def test_scan_does_not_rewrite_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "acme"
            folder.mkdir()
            packet = {
                "excerpts": {"ACC-101-PM": "x"},
                "evidence_map": [{"claim_ids": ["ACC-101-PM"]}],
                "soft_gaps": [],
            }
            provenance = {
                "resume_claims": [{"bullet": "x", "claim_ids": ["ACC-101-SAVINGS"]}],
                "cover_letter_claims": [],
            }
            packet_path = folder / "authoring_packet.json"
            prov_path = folder / "claim_provenance.json"
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            prov_path.write_text(json.dumps(provenance), encoding="utf-8")
            before_p = packet_path.read_bytes()
            before_v = prov_path.read_bytes()
            rows = scan_extra_packet_folders(root)
            self.assertEqual(rows[0]["extra_ids"], ["ACC-101-SAVINGS"])
            self.assertEqual(packet_path.read_bytes(), before_p)
            self.assertEqual(prov_path.read_bytes(), before_v)
            buf = io.StringIO()
            with redirect_stdout(buf):
                from packet_closed_world import main as scan_main

                scan_main(["--root", str(root)])
            self.assertIn("Did not rewrite", buf.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
