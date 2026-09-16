#!/usr/bin/env python3
"""CR-112 Story 3.5 — pre-authoring comparative replace (FR-313 / FR-314)."""
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
from build_authoring_packet import assemble_packet, build_evidence_map
from evidence_dominance import (
    apply_class1_dominance,
    compare_pair,
    jd_priority_margin,
)

_DIGEST = "# Authoring Rule Digest — Test\nUse only packet claim_ids.\n"
_DIGEST_VERSION = "testver1234567a"

_PEARL_CLAIMS = {
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
        "tags": ["savings", "$2,000,000"],
        "metrics": ["$2,000,000"],
        "attribution": "CONTRIBUTED",
    },
}

_REPLACE_CLAIMS = {
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


def _compare(**overrides: object) -> dict:
    claims = overrides.pop("claims")
    packet_picked = list(overrides.pop("packet_picked_ids"))
    kwargs = {
        "cid_a": "ACC-102-K8S",
        "score_a": 200,
        "cid_b": "ACC-103-INFRA",
        "score_b": 80,
        "claims": claims,
        "jd_item": "Own ingestion operations on the platform",
        "jd_text": "Own ingestion operations on the platform",
        "packet_picked_ids": packet_picked,
        "employer_counts": {"cision": 2},
        "project_counts": {"ACC-101": 1, "ACC-103": 1},
        "max_slots_per_project": 4,
        "omitted_reason": "top2_cutoff",
        "class_kind": 1,
    }
    kwargs.update(overrides)
    return compare_pair(**kwargs)


class TestComparatorAxes(unittest.TestCase):
    def test_clear_replace_when_omitted_dominates(self) -> None:
        result = _compare(claims=_REPLACE_CLAIMS, packet_picked_ids=["ACC-101-PM", "ACC-103-INFRA"])
        self.assertEqual(result["decision"], "REPLACE")
        self.assertEqual(result["axes"]["jd_priority"], "A_better")
        self.assertNotEqual(result["axes"]["distinctiveness"], "B_better")

    def test_near_tie_does_not_replace(self) -> None:
        claims = {
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
        }
        result = compare_pair(
            cid_a="ACC-102-OPS",
            score_a=4164,
            cid_b="ACC-101-PM",
            score_b=4165,
            claims=claims,
            jd_item="Own cost and savings on the platform",
            jd_text="Own cost and savings on the platform",
            packet_picked_ids=["ACC-101-PM"],
            employer_counts={"cision": 1},
            project_counts={"ACC-101": 1},
            max_slots_per_project=4,
            omitted_reason="top2_cutoff",
        )
        self.assertEqual(jd_priority_margin(4165), 417)
        self.assertEqual(result["axes"]["jd_priority"], "tie")
        self.assertNotEqual(result["decision"], "REPLACE")

    def test_larger_metric_does_not_replace(self) -> None:
        claims = {
            "ACC-101-PM": {
                "employer": "cision",
                "project_id": "ACC-101",
                "tags": ["platform"],
                "attribution": "OWNED",
            },
            "ACC-109-SAVINGS": {
                "employer": "cision",
                "project_id": "ACC-109",
                "tags": ["platform"],
                "metrics": ["$2,000,000"],
                "attribution": "OWNED",
            },
        }
        result = compare_pair(
            cid_a="ACC-109-SAVINGS",
            score_a=70,
            cid_b="ACC-101-PM",
            score_b=90,
            claims=claims,
            jd_item="Own cost and savings on the platform",
            packet_picked_ids=["ACC-101-PM"],
            employer_counts={"cision": 1},
            project_counts={"ACC-101": 1},
            max_slots_per_project=4,
            omitted_reason="top2_cutoff",
        )
        self.assertNotEqual(result["decision"], "REPLACE")
        self.assertEqual(result["axes"]["evidence_strength"], "tie")

    def test_unsafe_attribution_does_not_replace(self) -> None:
        claims = {
            "ACC-101-PM": {
                "employer": "cision",
                "project_id": "ACC-101",
                "tags": ["platform"],
                "attribution": "OWNED",
            },
            "ACC-102-K8S": {
                "employer": "cision",
                "project_id": "ACC-102",
                "tags": ["ingestion"],
                "attribution": "CONTRIBUTED",
            },
        }
        result = _compare(
            claims=claims,
            packet_picked_ids=["ACC-101-PM"],
            cid_b="ACC-101-PM",
            score_b=100,
            project_counts={"ACC-101": 1},
            employer_counts={"cision": 1},
        )
        self.assertEqual(result["axes"]["attribution_safety"], "veto_A")
        self.assertEqual(result["decision"], "KEEP")

    def test_sibling_lens_does_not_replace(self) -> None:
        claims = {
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
        result = compare_pair(
            cid_a="ACC-108-SUPPORT",
            score_a=200,
            cid_b="ACC-108-OPS",
            score_b=80,
            claims=claims,
            jd_item="Own zendesk support operations",
            jd_text="Own zendesk support operations",
            packet_picked_ids=["ACC-108-OPS"],
            employer_counts={"cision": 1},
            project_counts={"ACC-108": 1},
            max_slots_per_project=4,
            omitted_reason="top2_cutoff",
        )
        self.assertEqual(result["axes"]["distinctiveness"], "B_better")
        self.assertNotEqual(result["decision"], "REPLACE")

    def test_redundant_evidence_does_not_replace(self) -> None:
        claims = {
            "ACC-101-PM": {
                "employer": "cision",
                "project_id": "ACC-101",
                "tags": ["platform", "ingestion"],
                "attribution": "OWNED",
            },
            "ACC-102-K8S": {
                "employer": "cision",
                "project_id": "ACC-102",
                "tags": ["ingestion"],
                "attribution": "OWNED",
            },
        }
        result = compare_pair(
            cid_a="ACC-102-K8S",
            score_a=200,
            cid_b="ACC-101-PM",
            score_b=80,
            claims=claims,
            jd_item="Own ingestion operations on the platform",
            packet_picked_ids=["ACC-101-PM"],
            employer_counts={"cision": 1},
            project_counts={"ACC-101": 1},
            max_slots_per_project=4,
            omitted_reason="top2_cutoff",
        )
        self.assertEqual(result["axes"]["distinctiveness"], "B_better")
        self.assertNotEqual(result["decision"], "REPLACE")

    def test_capacity_violation_does_not_replace(self) -> None:
        claims = {
            "ACC-201-STERK": {
                "employer": "sterkly",
                "project_id": "ACC-201",
                "tags": ["security"],
                "attribution": "OWNED",
            },
            "ACC-102-K8S": {
                "employer": "cision",
                "project_id": "ACC-102",
                "tags": ["ingestion"],
                "attribution": "OWNED",
            },
        }
        result = compare_pair(
            cid_a="ACC-102-K8S",
            score_a=200,
            cid_b="ACC-201-STERK",
            score_b=80,
            claims=claims,
            jd_item="Own ingestion operations",
            packet_picked_ids=["ACC-201-STERK"],
            employer_counts={"cision": 6, "sterkly": 1},
            project_counts={"ACC-201": 1},
            max_slots_per_project=4,
            omitted_reason="top2_cutoff",
        )
        self.assertEqual(result["axes"]["document_capacity"], "veto_A")
        self.assertEqual(result["decision"], "KEEP")

    def test_contributed_cannot_beat_missing_attribution(self) -> None:
        claims = {
            "ACC-101-PM": {
                "employer": "cision",
                "project_id": "ACC-101",
                "tags": ["platform"],
            },
            "ACC-102-K8S": {
                "employer": "cision",
                "project_id": "ACC-102",
                "tags": ["ingestion"],
                "attribution": "CONTRIBUTED",
            },
        }
        result = compare_pair(
            cid_a="ACC-102-K8S",
            score_a=200,
            cid_b="ACC-101-PM",
            score_b=80,
            claims=claims,
            jd_item="Own ingestion operations",
            packet_picked_ids=["ACC-101-PM"],
            employer_counts={"cision": 1},
            project_counts={"ACC-101": 1},
            max_slots_per_project=4,
            omitted_reason="top2_cutoff",
        )
        self.assertEqual(result["axes"]["attribution_safety"], "tie")
        self.assertEqual(result["decision"], "AMBIGUOUS")

    def test_disabled_is_ineligible(self) -> None:
        claims = dict(_REPLACE_CLAIMS)
        claims["ACC-102-K8S"] = {
            **claims["ACC-102-K8S"],
            "disabled": True,
        }
        result = _compare(claims=claims, packet_picked_ids=["ACC-101-PM", "ACC-103-INFRA"])
        self.assertEqual(result["decision"], "INELIGIBLE")

    def test_influenced_and_observed_case_fold(self) -> None:
        """AC-410: INFLUENCED / OBSERVED rank after case-fold, not ATTR_RANK-only."""
        claims = {
            "ACC-101-PM": {
                "employer": "cision",
                "project_id": "ACC-101",
                "tags": ["platform"],
                "attribution": "owned",
            },
            "ACC-102-K8S": {
                "employer": "cision",
                "project_id": "ACC-102",
                "tags": ["ingestion"],
                "attribution": "Influenced",
            },
        }
        influenced = compare_pair(
            cid_a="ACC-102-K8S",
            score_a=200,
            cid_b="ACC-101-PM",
            score_b=80,
            claims=claims,
            jd_item="Own ingestion operations",
            packet_picked_ids=["ACC-101-PM"],
            employer_counts={"cision": 1},
            project_counts={"ACC-101": 1},
            max_slots_per_project=4,
            omitted_reason="top2_cutoff",
        )
        self.assertEqual(influenced["axes"]["attribution_safety"], "veto_A")
        self.assertEqual(influenced["decision"], "KEEP")

        claims["ACC-102-K8S"]["attribution"] = "OBSERVED"
        claims["ACC-101-PM"]["attribution"] = "contributed"
        observed = compare_pair(
            cid_a="ACC-102-K8S",
            score_a=200,
            cid_b="ACC-101-PM",
            score_b=80,
            claims=claims,
            jd_item="Own ingestion operations",
            packet_picked_ids=["ACC-101-PM"],
            employer_counts={"cision": 1},
            project_counts={"ACC-101": 1},
            max_slots_per_project=4,
            omitted_reason="top2_cutoff",
        )
        self.assertEqual(observed["axes"]["attribution_safety"], "veto_A")
        self.assertEqual(observed["decision"], "KEEP")

    def test_deterministic_identical_inputs(self) -> None:
        first = _compare(claims=_REPLACE_CLAIMS, packet_picked_ids=["ACC-101-PM", "ACC-103-INFRA"])
        second = _compare(claims=_REPLACE_CLAIMS, packet_picked_ids=["ACC-101-PM", "ACC-103-INFRA"])
        self.assertEqual(first, second)

    def test_module_does_not_call_llm(self) -> None:
        src = Path(__file__).with_name("evidence_dominance.py").read_text(encoding="utf-8")
        self.assertNotIn("from utils import call_llm", src)
        self.assertNotIn("utils.call_llm", src)


class TestPearlAndSupplyHouseKeep(unittest.TestCase):
    def test_pearl_savings_never_replace_in_map(self) -> None:
        ranked = [
            ("ACC-102-OPS", 7322),
            ("ACC-101-PM", 4165),
            ("ACC-101-SAVINGS", 4164),
        ]
        trace: list = []
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=ranked,
        ):
            em = build_evidence_map(
                _stage0("Own cost and savings on the platform"),
                "cost savings platform",
                _PEARL_CLAIMS,
                set(),
                jd_profile=None,
                trace_out=trace,
            )
        row = em[0]
        self.assertEqual(row["claim_ids"], ["ACC-102-OPS", "ACC-101-PM"])
        self.assertEqual(_omitted(row).get("ACC-101-SAVINGS"), "top2_cutoff")
        self.assertNotIn("displaced_by_dominance", _omitted(row).values())
        self.assertNotEqual(trace[0].get("decision"), "REPLACE")

    def test_supplyhouse_two_acc101_slots_still_keep_savings(self) -> None:
        claims = {
            **_PEARL_CLAIMS,
            "ACC-101-SCOPE": {
                "employer": "cision",
                "project_id": "ACC-101",
                "tags": ["scope"],
                "attribution": "OWNED",
            },
        }
        ranked = [
            ("ACC-101-PM", 90),
            ("ACC-101-SCOPE", 80),
            ("ACC-101-SAVINGS", 200),
        ]
        trace: list = []
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=ranked,
        ):
            em = build_evidence_map(
                _stage0("Own cloud infrastructure and savings"),
                "cloud infrastructure savings",
                claims,
                set(),
                jd_profile=None,
                trace_out=trace,
            )
        self.assertEqual(em[0]["claim_ids"], ["ACC-101-PM", "ACC-101-SCOPE"])
        self.assertNotEqual(trace[0].get("decision"), "REPLACE")


class TestClass1Wiring(unittest.TestCase):
    def test_replace_swaps_before_prompt_and_records_trace(self) -> None:
        ranked = [
            ("ACC-101-PM", 100),
            ("ACC-103-INFRA", 80),
            ("ACC-102-K8S", 200),
        ]
        trace: list = []
        jd = "Own ingestion operations on the platform"
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=ranked,
        ):
            em = build_evidence_map(
                _stage0(jd),
                jd,
                _REPLACE_CLAIMS,
                set(),
                jd_profile=None,
                trace_out=trace,
            )
        row = em[0]
        self.assertEqual(row["claim_ids"], ["ACC-101-PM", "ACC-102-K8S"])
        self.assertNotIn("ACC-103-INFRA", row["claim_ids"])
        self.assertEqual(_omitted(row).get("ACC-103-INFRA"), "displaced_by_dominance")
        self.assertNotIn("ACC-102-K8S", _omitted(row))
        self.assertEqual(trace[0]["decision"], "REPLACE")
        self.assertEqual(trace[0]["candidate_id"], "ACC-102-K8S")
        self.assertEqual(trace[0]["anchor_id"], "ACC-103-INFRA")
        self.assertIn("jd_priority", trace[0]["axes"])
        self.assertNotIn("selection_review", trace[0])

        stage0 = _stage0(jd)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            packet = assemble_packet(
                stage0=stage0,
                evidence_map=em,
                excerpts={"ACC-101-PM": "Owned platform work.", "ACC-102-K8S": "Owned ingestion."},
                disabled=set(),
                hook_fact=None,
                company="PearlLike",
                role_title="Product Manager",
                slug="replace_like",
                url=None,
                claim_constraints={
                    "ACC-101-PM": {"attribution": "OWNED"},
                    "ACC-102-K8S": {"attribution": "OWNED"},
                },
                jd_text=jd,
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
            digest = folder / "authoring_rule_digest.md"
            version = folder / "authoring_rule_digest.version"
            digest.write_text(_DIGEST, encoding="utf-8")
            version.write_text(_DIGEST_VERSION, encoding="utf-8")
            prompt_md, _meta = build_authoring_prompt(
                folder,
                force=True,
                digest_path=digest,
                digest_version_path=version,
            )
            self.assertIn("displaced_by_dominance", json.dumps(packet))
            self.assertNotIn('"score": 200', prompt_md)
            self.assertNotIn('"score":200', prompt_md)
            self.assertNotIn("A_better", prompt_md)
            self.assertNotIn("jd_priority", prompt_md)

    def test_ambiguous_keeps_top2_and_flags_review(self) -> None:
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
        ranked = [
            ("ACC-101-PM", 100),
            ("ACC-103-INFRA", 80),
            ("ACC-102-OPS", 85),
        ]
        trace: list = []
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=ranked,
        ):
            em = build_evidence_map(
                _stage0("Own operations and platform work"),
                "operations platform",
                claims,
                set(),
                jd_profile=None,
                trace_out=trace,
            )
        self.assertEqual(em[0]["claim_ids"], ["ACC-101-PM", "ACC-103-INFRA"])
        self.assertEqual(_omitted(em[0]).get("ACC-102-OPS"), "top2_cutoff")
        self.assertEqual(trace[0]["decision"], "AMBIGUOUS")
        self.assertTrue(trace[0].get("selection_review"))

    def test_apply_pass_is_deterministic(self) -> None:
        evidence_map = [
            {
                "jd_item": "Own ingestion operations on the platform",
                "bucket": "required",
                "claim_ids": ["ACC-101-PM", "ACC-103-INFRA"],
                "omitted_reasons": [{"claim_id": "ACC-102-K8S", "reason": "top2_cutoff"}],
            }
        ]
        traces = [
            {
                "jd_item": "Own ingestion operations on the platform",
                "bucket": "required",
                "picked": ["ACC-101-PM", "ACC-103-INFRA"],
                "candidates": [
                    {"claim_id": "ACC-101-PM", "score": 100, "reason": "picked"},
                    {"claim_id": "ACC-103-INFRA", "score": 80, "reason": "picked"},
                    {"claim_id": "ACC-102-K8S", "score": 200, "reason": "top2_cutoff"},
                ],
            }
        ]
        copy_map = json.loads(json.dumps(evidence_map))
        copy_trace = json.loads(json.dumps(traces))
        apply_class1_dominance(
            evidence_map, traces, _REPLACE_CLAIMS, jd_text="k8s", max_slots_per_project=4
        )
        apply_class1_dominance(
            copy_map, copy_trace, _REPLACE_CLAIMS, jd_text="k8s", max_slots_per_project=4
        )
        self.assertEqual(evidence_map, copy_map)
        self.assertEqual(traces, copy_trace)

    def test_disabled_high_score_does_not_shadow_replace(self) -> None:
        claims = dict(_REPLACE_CLAIMS)
        claims["ACC-109-DISABLED"] = {
            "employer": "cision",
            "project_id": "ACC-109",
            "tags": ["ingestion"],
            "attribution": "OWNED",
            "disabled": True,
        }
        evidence_map = [
            {
                "jd_item": "Own ingestion operations on the platform",
                "bucket": "required",
                "claim_ids": ["ACC-101-PM", "ACC-103-INFRA"],
                "omitted_reasons": [
                    {"claim_id": "ACC-109-DISABLED", "reason": "top2_cutoff"},
                    {"claim_id": "ACC-102-K8S", "reason": "top2_cutoff"},
                ],
            }
        ]
        traces = [
            {
                "jd_item": "Own ingestion operations on the platform",
                "bucket": "required",
                "picked": ["ACC-101-PM", "ACC-103-INFRA"],
                "candidates": [
                    {"claim_id": "ACC-101-PM", "score": 100, "reason": "picked"},
                    {"claim_id": "ACC-103-INFRA", "score": 80, "reason": "picked"},
                    {"claim_id": "ACC-109-DISABLED", "score": 300, "reason": "top2_cutoff"},
                    {"claim_id": "ACC-102-K8S", "score": 200, "reason": "top2_cutoff"},
                ],
            }
        ]
        apply_class1_dominance(
            evidence_map, traces, claims, jd_text="ingestion", max_slots_per_project=4
        )
        self.assertEqual(evidence_map[0]["claim_ids"], ["ACC-101-PM", "ACC-102-K8S"])
        self.assertEqual(traces[0]["decision"], "REPLACE")
        self.assertEqual(traces[0]["candidate_id"], "ACC-102-K8S")


if __name__ == "__main__":
    unittest.main(verbosity=2)
