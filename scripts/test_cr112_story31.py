#!/usr/bin/env python3
"""CR-112 Story 3.1 — closed-world extra-packet provenance completion-block tests."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from author_from_packet import _check_extra_packet_provenance
from packet_closed_world import (
    extra_packet_claim_ids,
    extra_packet_findings,
    scan_extra_packet_folders,
)


class TestExtraPacketBlock(unittest.TestCase):
    def test_prefix_match_does_not_clear_savings_vs_pm(self) -> None:
        """Implements FR-312 / AC-409. Prefix is still extra. Severity is BLOCK."""
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
        self.assertEqual(findings[0]["severity"], "BLOCK")
        self.assertEqual(findings[0]["recovery_state"], "UNRESOLVED")

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

    def test_detector_does_not_rank_or_recommend(self) -> None:
        packet = {
            "excerpts": {"ACC-101-PM": "x"},
            "evidence_map": [{"claim_ids": ["ACC-101-PM"]}],
            "soft_gaps": [],
        }
        provenance = {
            "resume_claims": [{"bullet": "x", "claim_ids": ["ACC-101-SAVINGS"]}],
            "cover_letter_claims": [],
        }
        findings = extra_packet_findings(packet, provenance)
        self.assertEqual(
            set(findings[0]),
            {"id", "claim_id", "severity", "recovery_state"},
        )
        self.assertNotIn("decision", findings[0])
        self.assertNotIn("rank", findings[0])
        self.assertNotIn("REPLACE", findings[0].values())

    def test_helper_fails_verify_and_does_not_rewrite(self) -> None:
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
            packet_path = folder / "authoring_packet.json"
            prov_path = folder / "claim_provenance.json"
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            prov_path.write_text(json.dumps(provenance), encoding="utf-8")
            before_p = packet_path.read_bytes()
            before_v = prov_path.read_bytes()
            ok, lines = _check_extra_packet_provenance(folder)
            self.assertFalse(ok)
            self.assertTrue(lines)
            self.assertTrue(all(line.startswith("FAIL [") for line in lines))
            self.assertFalse(any(line.startswith("WARN [") for line in lines))
            joined = "\n".join(lines)
            self.assertIn("ACC-101-SAVINGS", joined)
            self.assertIn("recovery_state=UNRESOLVED", joined)
            self.assertEqual(packet_path.read_bytes(), before_p)
            self.assertEqual(prov_path.read_bytes(), before_v)

    def test_exact_id_helper_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            packet = {
                "excerpts": {"ACC-101-SAVINGS": "x"},
                "evidence_map": [{"claim_ids": ["ACC-101-SAVINGS"]}],
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
            ok, lines = _check_extra_packet_provenance(folder)
            self.assertTrue(ok)
            self.assertTrue(any("PASS [extra_packet]" in line for line in lines))
            self.assertFalse(any("REPLACE" in line for line in lines))

    def test_sibling_lens_does_not_authorize(self) -> None:
        packet = {
            "excerpts": {"ACC-108-OPS": "ops"},
            "evidence_map": [{"claim_ids": ["ACC-108-OPS"]}],
            "soft_gaps": [],
        }
        provenance = {
            "resume_claims": [{"bullet": "triage", "claim_ids": ["ACC-108-SUPPORT"]}],
            "cover_letter_claims": [],
        }
        self.assertEqual(extra_packet_claim_ids(packet, provenance), ["ACC-108-SUPPORT"])

    def test_ordinal_and_substring_do_not_authorize(self) -> None:
        packet = {
            "excerpts": {"ACC-101-PM": "pm"},
            "evidence_map": [{"claim_ids": ["ACC-101-PM"]}],
            "soft_gaps": [],
        }
        provenance = {
            "resume_claims": [
                {"bullet": "a", "claim_ids": ["req-001"]},
                {"bullet": "b", "claim_ids": ["ACC-101"]},
            ],
            "cover_letter_claims": [],
        }
        self.assertEqual(extra_packet_claim_ids(packet, provenance), ["req-001", "ACC-101"])

    def test_catalog_presence_does_not_authorize(self) -> None:
        """Detector never consults workExperience.md or master_claims.json."""
        packet = {
            "excerpts": {"ACC-101-PM": "pm"},
            "evidence_map": [{"claim_ids": ["ACC-101-PM"]}],
            "soft_gaps": [],
        }
        provenance = {
            "resume_claims": [
                {"bullet": "savings", "claim_ids": ["ACC-101-SAVINGS"]},
            ],
            "cover_letter_claims": [],
        }
        findings = extra_packet_findings(packet, provenance)
        self.assertEqual(findings[0]["claim_id"], "ACC-101-SAVINGS")

    def test_pearl_and_supplyhouse_savings_fail_without_replace(self) -> None:
        packet = {
            "excerpts": {"ACC-101-PM": "pm", "ACC-101-SCOPE": "scope"},
            "evidence_map": [{"claim_ids": ["ACC-101-PM", "ACC-101-SCOPE"]}],
            "soft_gaps": [],
        }
        provenance = {
            "resume_claims": [
                {"bullet": "$2M", "claim_ids": ["ACC-101-SAVINGS"]},
            ],
            "cover_letter_claims": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "authoring_packet.json").write_text(
                json.dumps(packet), encoding="utf-8"
            )
            (folder / "claim_provenance.json").write_text(
                json.dumps(provenance), encoding="utf-8"
            )
            ok, lines = _check_extra_packet_provenance(folder)
        joined = "\n".join(lines)
        self.assertFalse(ok)
        self.assertIn("ACC-101-SAVINGS", joined)
        self.assertIn("recovery_state=UNRESOLVED", joined)
        self.assertNotIn("REPLACE", joined)
        self.assertNotIn("WIDEN", joined)

    def test_missing_provenance_cannot_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "authoring_packet.json").write_text(
                json.dumps(
                    {"excerpts": {"ACC-101-PM": "x"}, "evidence_map": [], "soft_gaps": []}
                ),
                encoding="utf-8",
            )
            ok, lines = _check_extra_packet_provenance(folder)
            self.assertFalse(ok)
            self.assertTrue(any("CLOSED_WORLD_UNREADABLE" in line for line in lines))

    def test_malformed_provenance_cannot_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "authoring_packet.json").write_text(
                json.dumps(
                    {"excerpts": {"ACC-101-PM": "x"}, "evidence_map": [], "soft_gaps": []}
                ),
                encoding="utf-8",
            )
            (folder / "claim_provenance.json").write_text("{not-json", encoding="utf-8")
            ok, lines = _check_extra_packet_provenance(folder)
            self.assertFalse(ok)
            self.assertTrue(any("CLOSED_WORLD_UNREADABLE" in line for line in lines))


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
