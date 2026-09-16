#!/usr/bin/env python3
"""CR-112 Story 3.6 — closed-world recovery after extra-packet detection."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from closed_world_recovery import (
    LEAKED_DIR,
    plan_recovery,
    recover_stage1_extras_guarded,
)
from packet_closed_world import extra_packet_findings

_PEARL = {
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

_LOOT = {
    "ACC-108-OPS": {
        "employer": "cision",
        "project_id": "ACC-108",
        "tags": ["operations"],
        "attribution": "OWNED",
    },
    "ACC-108-SUPPORT": {
        "employer": "cision",
        "project_id": "ACC-108",
        "tags": ["support", "zendesk"],
        "attribution": "OWNED",
    },
}

_REPLACE = {
    "ACC-101-PM": {
        "employer": "cision",
        "project_id": "ACC-101",
        "tags": ["platform"],
        "attribution": "OWNED",
    },
    "ACC-103-INFRA": {
        "employer": "cision",
        "project_id": "ACC-103",
        "tags": ["platform"],
        "attribution": "OWNED",
    },
    "ACC-102-K8S": {
        "employer": "cision",
        "project_id": "ACC-102",
        "tags": ["ingestion", "operations"],
        "attribution": "OWNED",
    },
}


def _write_folder(folder: Path, *, packet: dict, provenance: dict, trace: dict | None = None,
                  resume: str = "", cover: str = "", state: str | None = None) -> None:
    (folder / "authoring_packet.json").write_text(
        json.dumps(packet, indent=2), encoding="utf-8"
    )
    (folder / "claim_provenance.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8"
    )
    if trace is not None:
        (folder / "evidence_selection_trace.json").write_text(
            json.dumps(trace, indent=2), encoding="utf-8"
        )
    (folder / "Resume.md").write_text(resume or "* Owned the platform.\n", encoding="utf-8")
    (folder / "CoverLetter.md").write_text(cover or "I did the work.\n", encoding="utf-8")
    if state is not None:
        (folder / "workflow_state.json").write_text(state, encoding="utf-8")
        receipts = folder / "stage_receipts"
        receipts.mkdir()
        (receipts / "stage0.json").write_text('{"status": "COMPLETE"}\n', encoding="utf-8")


def _pearl_packet() -> dict:
    return {
        "excerpts": {"ACC-101-PM": "Owned the platform stabilization work."},
        "evidence_map": [
            {
                "jd_item": "Own cost and savings on the platform",
                "claim_ids": ["ACC-102-OPS", "ACC-101-PM"],
                "omitted_reasons": [{"claim_id": "ACC-101-SAVINGS", "reason": "top2_cutoff"}],
            }
        ],
        "soft_gaps": [],
    }


def _pearl_trace() -> dict:
    return {
        "items": [
            {
                "jd_item": "Own cost and savings on the platform",
                "bucket": "required",
                "picked": ["ACC-102-OPS", "ACC-101-PM"],
                "candidates": [
                    {"claim_id": "ACC-102-OPS", "score": 7322, "reason": "picked"},
                    {"claim_id": "ACC-101-PM", "score": 4165, "reason": "picked"},
                    {"claim_id": "ACC-101-SAVINGS", "score": 4164, "reason": "top2_cutoff"},
                ],
            }
        ]
    }


class TestDetectorStillDoesNotRecover(unittest.TestCase):
    def test_findings_have_no_action_or_widen(self) -> None:
        findings = extra_packet_findings(
            _pearl_packet(),
            {
                "resume_claims": [{"bullet": "Cut spend", "claim_ids": ["ACC-101-SAVINGS"]}],
                "cover_letter_claims": [],
            },
        )
        self.assertEqual(findings[0]["claim_id"], "ACC-101-SAVINGS")
        self.assertNotIn("action", findings[0])
        self.assertNotIn("WIDEN_PACKET", findings[0].values())


class TestRemoveExtra(unittest.TestCase):
    def test_pearl_savings_remove_extra_never_widen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _write_folder(
                folder,
                packet=_pearl_packet(),
                provenance={
                    "resume_claims": [
                        {"bullet": "Owned the platform.", "claim_ids": ["ACC-101-PM"]},
                        {"bullet": "Cut $2M ingest spend.", "claim_ids": ["ACC-101-SAVINGS"]},
                    ],
                    "cover_letter_claims": [],
                },
                trace=_pearl_trace(),
                resume="* Owned the platform.\n* Cut $2M ingest spend.\n",
                state='{"status": "IN_PROGRESS"}\n',
            )
            result = recover_stage1_extras_guarded(folder, claims=_PEARL, apply=True)
            self.assertEqual(result["report"]["items"][0]["action"], "REMOVE_EXTRA")
            self.assertNotEqual(result["report"]["items"][0]["action"], "WIDEN_PACKET")
            packet = json.loads((folder / "authoring_packet.json").read_text(encoding="utf-8"))
            self.assertEqual(packet["evidence_map"][0]["claim_ids"], ["ACC-102-OPS", "ACC-101-PM"])
            resume = (folder / "Resume.md").read_text(encoding="utf-8")
            self.assertNotIn("Cut $2M ingest spend", resume)
            self.assertIn("Owned the platform", resume)
            provenance = json.loads((folder / "claim_provenance.json").read_text(encoding="utf-8"))
            cited = [cid for row in provenance["resume_claims"] for cid in row["claim_ids"]]
            self.assertNotIn("ACC-101-SAVINGS", cited)
            self.assertEqual(
                extra_packet_findings(packet, provenance),
                [],
            )
            self.assertEqual(
                (folder / "workflow_state.json").read_text(encoding="utf-8"),
                '{"status": "IN_PROGRESS"}\n',
            )
            self.assertEqual(
                (folder / "stage_receipts" / "stage0.json").read_text(encoding="utf-8"),
                '{"status": "COMPLETE"}\n',
            )

    def test_supplyhouse_two_acc101_slots_remove_savings_never_widen(self) -> None:
        claims = {
            **_PEARL,
            "ACC-101-SCOPE": {
                "employer": "cision",
                "project_id": "ACC-101",
                "tags": ["scope"],
                "attribution": "OWNED",
            },
        }
        packet = {
            "excerpts": {
                "ACC-101-PM": "Owned the platform.",
                "ACC-101-SCOPE": "Owned scope.",
            },
            "evidence_map": [
                {
                    "jd_item": "Own cloud infrastructure and savings",
                    "claim_ids": ["ACC-101-PM", "ACC-101-SCOPE"],
                    "omitted_reasons": [{"claim_id": "ACC-101-SAVINGS", "reason": "top2_cutoff"}],
                }
            ],
            "soft_gaps": [],
        }
        trace = {
            "items": [
                {
                    "jd_item": "Own cloud infrastructure and savings",
                    "bucket": "required",
                    "picked": ["ACC-101-PM", "ACC-101-SCOPE"],
                    "candidates": [
                        {"claim_id": "ACC-101-PM", "score": 90, "reason": "picked"},
                        {"claim_id": "ACC-101-SCOPE", "score": 80, "reason": "picked"},
                        {"claim_id": "ACC-101-SAVINGS", "score": 200, "reason": "top2_cutoff"},
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _write_folder(
                folder,
                packet=packet,
                provenance={
                    "resume_claims": [{"bullet": "Cut $2M ingest spend.", "claim_ids": ["ACC-101-SAVINGS"]}],
                    "cover_letter_claims": [],
                },
                trace=trace,
            )
            plan = plan_recovery(folder, claims=claims)
            self.assertEqual(plan["items"][0]["action"], "REMOVE_EXTRA")
            self.assertNotEqual(plan["items"][0]["action"], "WIDEN_PACKET")
            self.assertNotEqual(plan["items"][0]["action"], "HUMAN_COMPARE")

    def test_loot_labs_support_remove_never_widen(self) -> None:
        packet = {
            "excerpts": {"ACC-108-OPS": "Owned operations."},
            "evidence_map": [{"jd_item": "Own zendesk support operations", "claim_ids": ["ACC-108-OPS"]}],
            "soft_gaps": [],
        }
        trace = {
            "items": [
                {
                    "jd_item": "Own zendesk support operations",
                    "bucket": "required",
                    "picked": ["ACC-108-OPS"],
                    "candidates": [
                        {"claim_id": "ACC-108-OPS", "score": 80, "reason": "picked"},
                        {"claim_id": "ACC-108-SUPPORT", "score": 200, "reason": "top2_cutoff"},
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _write_folder(
                folder,
                packet=packet,
                provenance={
                    "resume_claims": [{"bullet": "Ran zendesk support.", "claim_ids": ["ACC-108-SUPPORT"]}],
                    "cover_letter_claims": [],
                },
                trace=trace,
                resume="* Ran zendesk support.\n",
            )
            plan = plan_recovery(folder, claims=_LOOT)
            self.assertEqual(plan["items"][0]["action"], "REMOVE_EXTRA")
            self.assertNotEqual(plan["items"][0]["action"], "WIDEN_PACKET")
            self.assertNotEqual(plan["items"][0]["action"], "HUMAN_COMPARE")

    def test_extra_not_in_trace_cannot_widen(self) -> None:
        packet = {
            "excerpts": {"ACC-101-PM": "Owned platform."},
            "evidence_map": [{"jd_item": "Own platform", "claim_ids": ["ACC-101-PM"]}],
            "soft_gaps": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _write_folder(
                folder,
                packet=packet,
                provenance={
                    "resume_claims": [{"bullet": "Did security work.", "claim_ids": ["ACC-103-SEC"]}],
                    "cover_letter_claims": [],
                },
                trace={"items": [{"jd_item": "Own platform", "picked": ["ACC-101-PM"], "candidates": []}]},
            )
            plan = plan_recovery(folder, claims={**_PEARL, "ACC-103-SEC": {"project_id": "ACC-103", "attribution": "OWNED"}})
            self.assertEqual(plan["items"][0]["action"], "REMOVE_EXTRA")
            self.assertEqual(plan["items"][0]["reason"], "not_in_trace_omitted")


class TestRewriteAndPause(unittest.TestCase):
    def test_disabled_extra_rewrite_packet_unchanged(self) -> None:
        claims = dict(_PEARL)
        claims["ACC-101-SAVINGS"] = {**claims["ACC-101-SAVINGS"], "disabled": True}
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            packet = _pearl_packet()
            _write_folder(
                folder,
                packet=packet,
                provenance={
                    "resume_claims": [{"bullet": "Cut spend.", "claim_ids": ["ACC-101-SAVINGS"]}],
                    "cover_letter_claims": [],
                },
                trace=_pearl_trace(),
                resume="* Cut spend.\n",
            )
            result = recover_stage1_extras_guarded(folder, claims=claims, apply=True)
            self.assertEqual(result["report"]["items"][0]["action"], "REWRITE_UNSUPPORTED")
            after = json.loads((folder / "authoring_packet.json").read_text(encoding="utf-8"))
            self.assertEqual(after["evidence_map"][0]["claim_ids"], packet["evidence_map"][0]["claim_ids"])

    def test_ambiguous_pauses_with_both_candidates(self) -> None:
        claims = {
            "ACC-101-PM": {
                "employer": "cision",
                "project_id": "ACC-101",
                "tags": ["platform"],
                "attribution": "OWNED",
            },
            "ACC-103-INFRA": {
                "employer": "cision",
                "project_id": "ACC-103",
                "tags": ["platform"],
                "attribution": "OWNED",
            },
            "ACC-102-OPS": {
                "employer": "cision",
                "project_id": "ACC-102",
                "tags": ["operations"],
                "attribution": "OWNED",
            },
        }
        packet = {
            "excerpts": {"ACC-101-PM": "x", "ACC-103-INFRA": "y"},
            "evidence_map": [
                {
                    "jd_item": "Own operations and platform work",
                    "claim_ids": ["ACC-101-PM", "ACC-103-INFRA"],
                    "omitted_reasons": [{"claim_id": "ACC-102-OPS", "reason": "top2_cutoff"}],
                }
            ],
            "soft_gaps": [],
        }
        trace = {
            "items": [
                {
                    "jd_item": "Own operations and platform work",
                    "bucket": "required",
                    "picked": ["ACC-101-PM", "ACC-103-INFRA"],
                    "candidates": [
                        {"claim_id": "ACC-101-PM", "score": 100, "reason": "picked"},
                        {"claim_id": "ACC-103-INFRA", "score": 80, "reason": "picked"},
                        {"claim_id": "ACC-102-OPS", "score": 85, "reason": "top2_cutoff"},
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _write_folder(
                folder,
                packet=packet,
                provenance={
                    "resume_claims": [{"bullet": "Ran operations.", "claim_ids": ["ACC-102-OPS"]}],
                    "cover_letter_claims": [],
                },
                trace=trace,
                resume="* Ran operations.\n",
            )
            result = recover_stage1_extras_guarded(folder, claims=claims, apply=True)
            self.assertEqual(result["status"], "PAUSE_REVIEW")
            self.assertFalse(result["applied"])
            item = result["report"]["items"][0]
            self.assertEqual(item["action"], "QUALITATIVE_REVIEW")
            self.assertEqual(item["candidate_id"], "ACC-102-OPS")
            self.assertEqual(item["anchor_id"], "ACC-103-INFRA")
            self.assertTrue(item.get("axes"))
            resume = (folder / "Resume.md").read_text(encoding="utf-8")
            self.assertIn("Ran operations", resume)

    def test_unreadable_packet_human_compare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "authoring_packet.json").write_text("{not-json", encoding="utf-8")
            (folder / "claim_provenance.json").write_text("{}", encoding="utf-8")
            plan = plan_recovery(folder, claims=_PEARL)
            self.assertEqual(plan["items"][0]["action"], "HUMAN_COMPARE")

    def test_constraint_conflict_is_human_compare(self) -> None:
        packet = _pearl_packet()
        packet["claim_constraints"] = {
            "ACC-101-PM": {"prohibited_claims": ["ACC-101-SAVINGS"]}
        }
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _write_folder(
                folder,
                packet=packet,
                provenance={
                    "resume_claims": [{"bullet": "Cut spend.", "claim_ids": ["ACC-101-SAVINGS"]}],
                    "cover_letter_claims": [],
                },
                trace=_pearl_trace(),
            )
            plan = plan_recovery(folder, claims=_PEARL)
            self.assertEqual(plan["items"][0]["action"], "HUMAN_COMPARE")
            self.assertEqual(plan["items"][0]["reason"], "we_constraint_conflict")


class TestWidenPacket(unittest.TestCase):
    def test_same_item_replace_invalidates_leaked_draft(self) -> None:
        jd = "Own ingestion operations on the platform"
        packet = {
            "excerpts": {"ACC-101-PM": "Owned platform work.", "ACC-103-INFRA": "Owned infra."},
            "evidence_map": [
                {
                    "jd_item": jd,
                    "claim_ids": ["ACC-101-PM", "ACC-103-INFRA"],
                    "omitted_reasons": [{"claim_id": "ACC-102-K8S", "reason": "top2_cutoff"}],
                }
            ],
            "soft_gaps": [],
        }
        leaked_bullet = "Leaked ingestion sentence that must not be stamped."
        trace = {
            "items": [
                {
                    "jd_item": jd,
                    "bucket": "required",
                    "picked": ["ACC-101-PM", "ACC-103-INFRA"],
                    "candidates": [
                        {"claim_id": "ACC-101-PM", "score": 100, "reason": "picked"},
                        {"claim_id": "ACC-103-INFRA", "score": 80, "reason": "picked"},
                        {"claim_id": "ACC-102-K8S", "score": 200, "reason": "top2_cutoff"},
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _write_folder(
                folder,
                packet=packet,
                provenance={
                    "resume_claims": [{"bullet": leaked_bullet, "claim_ids": ["ACC-102-K8S"]}],
                    "cover_letter_claims": [],
                },
                trace=trace,
                resume=f"* {leaked_bullet}\n",
                state='{"status": "IN_PROGRESS"}\n',
            )
            result = recover_stage1_extras_guarded(folder, claims=_REPLACE, apply=True)
            self.assertEqual(result["status"], "WAITING_FOR_LLM")
            self.assertEqual(result["report"]["items"][0]["action"], "WIDEN_PACKET")
            after = json.loads((folder / "authoring_packet.json").read_text(encoding="utf-8"))
            self.assertEqual(after["evidence_map"][0]["claim_ids"], ["ACC-101-PM", "ACC-102-K8S"])
            self.assertEqual(
                {row["claim_id"]: row["reason"] for row in after["evidence_map"][0]["omitted_reasons"]},
                {"ACC-103-INFRA": "displaced_by_dominance"},
            )
            self.assertFalse((folder / "Resume.md").exists())
            self.assertFalse((folder / "claim_provenance.json").exists())
            leaked = folder / LEAKED_DIR / "Resume.md"
            self.assertTrue(leaked.exists())
            self.assertIn(leaked_bullet, leaked.read_text(encoding="utf-8"))
            excerpt = after["excerpts"]["ACC-102-K8S"]
            self.assertNotIn(leaked_bullet, excerpt)
            self.assertEqual(
                (folder / "workflow_state.json").read_text(encoding="utf-8"),
                '{"status": "IN_PROGRESS"}\n',
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
