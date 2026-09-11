#!/usr/bin/env python3
"""CR-112 Story 3.2 — omitted_reasons + sibling ranking trace (FR-303 / AC-400)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from author_from_packet import build_authoring_prompt
from build_authoring_packet import (
    assemble_packet,
    build_evidence_map,
    build_packet,
)

_DIGEST = "# Authoring Rule Digest — Test\nUse only packet claim_ids.\n"
_DIGEST_VERSION = "testver1234567a"

_CLAIMS = {
    "ACC-101-PM": {
        "employer": "cision",
        "project_id": "ACC-101",
        "tags": ["platform"],
        "attribution": "OWNED",
    },
    "ACC-102-OPS": {
        "employer": "cision",
        "project_id": "ACC-102",
        "tags": ["operations"],
        "attribution": "OWNED",
    },
    "ACC-101-SAVINGS": {
        "employer": "cision",
        "project_id": "ACC-101",
        "tags": ["savings"],
        "attribution": "CONTRIBUTED",
    },
}

_WE_TEXT = (
    "*   **[ACC-101] Platform**: Owned the platform stabilization work.\n"
    "*   **[ACC-102] Operations**: Owned the operations coordination work.\n"
)

_PACKET_OMITTED = frozenset({"top2_cutoff", "project_slot_cap"})


def _stage0(item: str) -> dict:
    return {
        "company": "PearlLike",
        "role": "Product Manager",
        "tier": "Tier 1",
        "thin_jd": True,
        "required": [{"item": item, "gap": False}],
        "preferred": [],
        "responsibilities": [],
        "flagged_gaps": [],
    }


def _omitted(row: dict) -> dict[str, str]:
    return {item["claim_id"]: item["reason"] for item in row.get("omitted_reasons") or []}


def _write_digest(folder: Path) -> tuple[Path, Path]:
    digest = folder / "authoring_rule_digest.md"
    version = folder / "authoring_rule_digest.version"
    digest.write_text(_DIGEST, encoding="utf-8")
    version.write_text(_DIGEST_VERSION, encoding="utf-8")
    return digest, version


class TestPearlLikeOmittedReasons(unittest.TestCase):
    def test_savings_rank3_is_top2_cutoff_not_inserted(self) -> None:
        """Implements FR-303 / AC-400 / AC-32-1 / AC-32-8."""
        ranked = [
            ("ACC-101-PM", 90),
            ("ACC-102-OPS", 80),
            ("ACC-101-SAVINGS", 70),
        ]
        stage0 = _stage0("Own cost and savings on the platform")
        trace: list = []
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=ranked,
        ):
            em = build_evidence_map(
                stage0,
                "cost savings platform",
                _CLAIMS,
                set(),
                jd_profile=None,
                trace_out=trace,
            )
        row = em[0]
        self.assertEqual(row["claim_ids"], ["ACC-101-PM", "ACC-102-OPS"])
        self.assertNotIn("ACC-101-SAVINGS", row["claim_ids"])
        omitted = _omitted(row)
        self.assertEqual(omitted.get("ACC-101-SAVINGS"), "top2_cutoff")
        self.assertTrue(set(omitted.values()) <= _PACKET_OMITTED)
        savings = next(
            c for c in trace[0]["candidates"] if c["claim_id"] == "ACC-101-SAVINGS"
        )
        self.assertEqual(savings["reason"], "top2_cutoff")
        self.assertEqual(savings["score"], 70)

    def test_savings_rank1_is_picked_not_top2_cutoff(self) -> None:
        """AC-32-2 negative control."""
        ranked = [
            ("ACC-101-SAVINGS", 90),
            ("ACC-101-PM", 80),
            ("ACC-102-OPS", 70),
        ]
        trace: list = []
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=ranked,
        ):
            em = build_evidence_map(
                _stage0("Own cost and savings on the platform"),
                "cost savings platform",
                _CLAIMS,
                set(),
                jd_profile=None,
                trace_out=trace,
            )
        row = em[0]
        self.assertIn("ACC-101-SAVINGS", row["claim_ids"])
        self.assertNotEqual(_omitted(row).get("ACC-101-SAVINGS"), "top2_cutoff")
        savings = next(
            c for c in trace[0]["candidates"] if c["claim_id"] == "ACC-101-SAVINGS"
        )
        self.assertEqual(savings["reason"], "picked")


class TestSlotCapAndScoreZero(unittest.TestCase):
    def test_project_slot_cap_not_mislabeled_top2(self) -> None:
        """AC-32-3."""
        claims = {
            "ACC-101-A": {"project_id": "ACC-101", "attribution": "OWNED"},
            "ACC-101-B": {"project_id": "ACC-101", "attribution": "OWNED"},
            "ACC-101-C": {"project_id": "ACC-101", "attribution": "OWNED"},
            "ACC-101-D": {"project_id": "ACC-101", "attribution": "OWNED"},
            "ACC-101-E": {"project_id": "ACC-101", "attribution": "OWNED"},
            "ACC-102-X": {"project_id": "ACC-102", "attribution": "OWNED"},
        }
        ranked_by_item = {
            "Need one": [("ACC-101-A", 90), ("ACC-101-B", 80)],
            "Need two": [("ACC-101-C", 90), ("ACC-101-D", 80)],
            "Need three": [("ACC-101-E", 90), ("ACC-102-X", 80)],
        }

        def fake_score(item_text: str, *args: object, **kwargs: object):
            return ranked_by_item[item_text]

        stage0 = {
            "tier": "Tier 1",
            "thin_jd": True,
            "required": [
                {"item": "Need one", "gap": False},
                {"item": "Need two", "gap": False},
                {"item": "Need three", "gap": False},
            ],
            "preferred": [],
            "responsibilities": [],
            "flagged_gaps": [],
        }
        trace: list = []
        with patch(
            "build_authoring_packet._score_claims_for_item",
            side_effect=fake_score,
        ):
            em = build_evidence_map(
                stage0, "need", claims, set(), jd_profile=None, trace_out=trace
            )
        third = em[2]
        self.assertEqual(third["claim_ids"], ["ACC-102-X"])
        omitted = _omitted(third)
        self.assertEqual(omitted.get("ACC-101-E"), "project_slot_cap")
        self.assertNotEqual(omitted.get("ACC-101-E"), "top2_cutoff")
        e_cand = next(
            c for c in trace[2]["candidates"] if c["claim_id"] == "ACC-101-E"
        )
        self.assertEqual(e_cand["reason"], "project_slot_cap")

    def test_score_zero_stays_out_of_packet_omitted_reasons(self) -> None:
        """AC-32-9: catalog zeros belong in the sibling TRACE only."""
        ranked = [
            ("ACC-101-PM", 90),
            ("ACC-102-OPS", 80),
            ("ACC-101-SAVINGS", 0),
        ]
        trace: list = []
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=ranked,
        ):
            em = build_evidence_map(
                _stage0("Own cost and savings on the platform"),
                "cost savings platform",
                _CLAIMS,
                set(),
                jd_profile=None,
                trace_out=trace,
            )
        omitted = _omitted(em[0])
        self.assertNotIn("ACC-101-SAVINGS", omitted)
        savings = next(
            c for c in trace[0]["candidates"] if c["claim_id"] == "ACC-101-SAVINGS"
        )
        self.assertEqual(savings["reason"], "score_zero")
        self.assertEqual(savings["score"], 0)


class TestBoilerplateAndPromptIsolation(unittest.TestCase):
    def test_boilerplate_preferred_is_trace_filter_not_row(self) -> None:
        """AC-32-6."""
        stage0 = {
            "tier": "Tier 1",
            "thin_jd": True,
            "required": [{"item": "Agile sprint planning and roadmap experience", "gap": False}],
            "preferred": [{"item": "Excellent communication skills"}],
            "responsibilities": [],
            "flagged_gaps": [],
        }
        ranked = [("ACC-101-PM", 90), ("ACC-102-OPS", 80)]
        trace: list = []
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=ranked,
        ):
            em = build_evidence_map(
                stage0, "agile roadmap", _CLAIMS, set(), jd_profile=None, trace_out=trace
            )
        self.assertNotIn("Excellent communication skills", [r["jd_item"] for r in em])
        filtered = [row for row in trace if row.get("filter") == "boilerplate_filtered"]
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["jd_item"], "Excellent communication skills")
        self.assertEqual(filtered[0]["candidates"], [])

    def test_author_prompt_has_reason_code_not_scores_or_trace_filename(self) -> None:
        """AC-32-4."""
        ranked = [
            ("ACC-101-PM", 90),
            ("ACC-102-OPS", 80),
            ("ACC-101-SAVINGS", 70),
        ]
        stage0 = _stage0("Own cost and savings on the platform")
        trace: list = []
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=ranked,
        ):
            em = build_evidence_map(
                stage0,
                "cost savings platform",
                _CLAIMS,
                set(),
                jd_profile=None,
                trace_out=trace,
            )
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            packet = assemble_packet(
                stage0=stage0,
                evidence_map=em,
                excerpts={"ACC-101-PM": "Owned platform work."},
                disabled=set(),
                hook_fact=None,
                company="PearlLike",
                role_title="Product Manager",
                slug="pearl_like",
                url=None,
                claim_constraints={"ACC-101-PM": {"attribution": "OWNED"}},
                jd_text="Own cost and savings on the platform",
                ats_term_contract=[],
            )
            packet["packet_status"] = "ready"
            packet["incomplete_reasons"] = []
            packet["rule_digest_version"] = _DIGEST_VERSION
            packet["learned_examples"] = []
            packet["example_bank_version"] = ""
            (folder / "authoring_packet.json").write_text(
                json.dumps(packet, indent=2), encoding="utf-8"
            )
            digest_path, version_path = _write_digest(folder)
            prompt_md, _meta = build_authoring_prompt(
                folder,
                force=True,
                digest_path=digest_path,
                digest_version_path=version_path,
            )
            self.assertIn("top2_cutoff", json.dumps(packet))
            self.assertNotIn("evidence_selection_trace.json", prompt_md)
            self.assertNotIn('"score": 70', prompt_md)
            self.assertNotIn('"score":70', prompt_md)


class TestBuildPacketWritesSiblingTrace(unittest.TestCase):
    def test_build_packet_writes_evidence_selection_trace(self) -> None:
        """AC-32-5: production build_packet, not a hand-called helper."""
        ranked = [
            ("ACC-101-PM", 90),
            ("ACC-102-OPS", 80),
            ("ACC-101-SAVINGS", 70),
        ]
        stage0 = _stage0("Own cost and savings on the platform")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "stage0_fit_gate.json").write_text(
                json.dumps(stage0), encoding="utf-8"
            )
            (folder / "Original_JD.txt").write_text(
                "Own cost and savings on the platform\n", encoding="utf-8"
            )
            with patch(
                "build_authoring_packet._score_claims_for_item",
                return_value=ranked,
            ), patch(
                "build_authoring_packet.select_examples",
                return_value=[],
            ):
                build_packet(
                    folder,
                    no_hook=True,
                    claims_override=_CLAIMS,
                    disabled_override=set(),
                    we_text_override=_WE_TEXT,
                    ai_text_override="",
                    hook_fact_override=None,
                )
            trace_path = folder / "evidence_selection_trace.json"
            self.assertTrue(trace_path.exists(), "build_packet must write the sibling trace")
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["slug"], folder.name)
            blob = json.dumps(payload)
            self.assertIn("top2_cutoff", blob)
            self.assertIn('"score": 70', blob)


if __name__ == "__main__":
    unittest.main(verbosity=2)
