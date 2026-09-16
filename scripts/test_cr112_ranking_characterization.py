#!/usr/bin/env python3
"""CR-112 ranking characterization corpus (FR-321 / AC-419).

Converts the reviewed savings-vs-messaging cases into deterministic
fixtures against live `_score_claims_for_item` without changing the
formula. Camunda's current SAVINGS-over-messaging rank is a known
defect, not a desired assertion.

Pearl/SupplyHouse negative controls stay on the Story 3.5 REPLACE gate
as well as ranking characterization. Metric-bearing claims should still
win when the JD item is actually about cost or ARR/reliability.
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from typing import Any
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_authoring_packet import (  # noqa: E402
    _claim_text_for_scoring,
    _distinctive_overlap,
    _item_specificity_boost,
    _score_claims_for_item,
    build_evidence_map,
)
from evidence_dominance import compare_pair, jd_priority_margin  # noqa: E402
from jd_tailoring import (  # noqa: E402
    _rarity_weight,
    build_jd_profile_deterministic,
    score_claim_for_jd,
)

# Implements FR-321 / AC-419 (CR-112 ranking characterization corpus)
KNOWN_DEFECT_CAMUNDA_SAVINGS = "camunda_savings_vs_messaging"

CAMUNDA_DISTRIBUTED_ITEM = (
    "Strong understanding of distributed systems concepts, including "
    "scalability, fault tolerance, event-driven architecture, and "
    "performance optimization."
)

# Isolated full-JD blob: SaaS/platform language plus the technical item.
# Enough for `jd_score` overweight without loading gitignored packets.
CAMUNDA_LIKE_JD = """
Camunda is a process orchestration platform. We build technical SaaS
products, PaaS, and cloud-native workflow software.
Requirements:
- 5+ years of product management experience in distributed systems,
  technical SaaS products, PaaS, or cloud-native products.
- Strong understanding of distributed systems concepts, including
  scalability, fault tolerance, event-driven architecture, and
  performance optimization.
- Experience with Java, Kafka, and event-driven architecture.
We operate a customer-facing B2B SaaS platform at enterprise scale.
Reliability, infrastructure, and storage optimization matter.
"""

COST_REDUCTION_ITEM = (
    "Reduce infrastructure storage spend and vendor cost through "
    "platform optimization."
)
COST_REDUCTION_JD = (
    COST_REDUCTION_ITEM
    + " Enterprise SaaS platform reliability. Reduce infrastructure "
    "cost and storage spend."
)

ARR_RELIABILITY_ITEM = (
    "Own platform reliability for a large ARR SaaS product used by "
    "thousands of enterprise users."
)
ARR_RELIABILITY_JD = (
    ARR_RELIABILITY_ITEM
    + " B2B SaaS platform. Protect revenue. Reliability at scale for "
    "enterprise customers."
)

PEARL_ITEM = (
    "Own platform operations and customer workflows across the product."
)
PEARL_JD = (
    PEARL_ITEM
    + " Product manager for a healthcare workflow SaaS. Own operations, "
    "customer workflows, and platform delivery. Not a cost-reduction "
    "mandate."
)

SUPPLYHOUSE_ITEM = (
    "Own cloud infrastructure roadmap and platform reliability for "
    "suppliers."
)
SUPPLYHOUSE_JD = (
    SUPPLYHOUSE_ITEM
    + " B2B commerce platform. Cloud infrastructure, supplier catalogs, "
    "operations. Savings is not the hiring thesis."
)

MESSAGING_CLAIMS: dict[str, dict[str, Any]] = {
    "ACC-101-SAVINGS": {
        "employer": "cision",
        "project_id": "ACC-101",
        "lens": "savings",
        "tags": [
            "Cost Reduction",
            "Infrastructure",
            "Storage Optimization",
            "Legacy Systems",
        ],
        "metrics": ["2000000"],
        "attribution": "contributed",
    },
    "ACC-215-RABBITMQ": {
        "employer": "cision",
        "project_id": "ACC-215",
        "lens": "rabbitmq",
        "tags": [
            "RabbitMQ",
            "Message Queues",
            "Distributed Messaging",
            "News Monitoring",
        ],
        "metrics": [],
        "attribution": "OWNED",
    },
    "ACC-189-KAFKA": {
        "employer": "cision",
        "project_id": "ACC-189",
        "lens": "kafka",
        "tags": [
            "Kafka",
            "Product Architecture",
            "Data Pipeline",
            "ETL",
            "Architecture Planning",
        ],
        "metrics": [],
        "attribution": "OWNED",
    },
}

PEARL_CLAIMS: dict[str, dict[str, Any]] = {
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
        "tags": [
            "Cost Reduction",
            "Infrastructure",
            "Storage Optimization",
            "Legacy Systems",
        ],
        "metrics": ["$2,000,000"],
        "attribution": "CONTRIBUTED",
    },
}

SUPPLYHOUSE_CLAIMS: dict[str, dict[str, Any]] = {
    **PEARL_CLAIMS,
    "ACC-101-SCOPE": {
        "employer": "cision",
        "project_id": "ACC-101",
        "tags": ["scope"],
        "attribution": "OWNED",
    },
}

ARR_CLAIMS: dict[str, dict[str, Any]] = {
    "ACC-101-PM": {
        "employer": "cision",
        "project_id": "ACC-101",
        "lens": "pm",
        "tags": [
            "Platform Scale",
            "Revenue Protection",
            "Enterprise",
            "Reliability",
        ],
        "metrics": ["40000000 ARR", "3500 users"],
        "attribution": "OWNED",
    },
    "ACC-105-PROCESS": {
        "employer": "cision",
        "project_id": "ACC-105",
        "lens": "process",
        "tags": ["Prioritization", "Delivery", "Agile Planning"],
        "metrics": [],
        "attribution": "OWNED",
    },
}

DESIRED_CAMUNDA_SLOT1 = frozenset({"ACC-215-RABBITMQ", "ACC-189-KAFKA"})


def _explain_claim(
    item_text: str,
    cid: str,
    rec: dict[str, Any],
    jd_profile: Any,
    jd_text: str,
) -> dict[str, Any]:
    """Return overlap, jd_score, and expected total for one claim.

    Args: item_text, cid, rec, jd_profile, jd_text are ranking inputs.
    Returns: a dict recording why the current formula produced its total.
    """
    item_words = set(re.findall(r"[a-z]{4,}", item_text.lower()))
    scoring_text = _claim_text_for_scoring(cid, rec)
    tag_words = set(re.findall(r"[a-z]{4,}", scoring_text.lower()))
    overlap_words = _distinctive_overlap(item_words, tag_words)
    overlap = sum(_rarity_weight(w) for w in overlap_words)
    jd_score = (
        score_claim_for_jd(scoring_text, jd_profile, jd_text)
        if jd_profile is not None
        else overlap
    )
    capability_boost = _item_specificity_boost(item_text, scoring_text)
    if overlap == 0 and capability_boost == 0:
        expected_total = 0
    else:
        expected_total = capability_boost + int(round(overlap * 1000)) + jd_score
    return {
        "claim_id": cid,
        "overlap_words": overlap_words,
        "overlap": overlap,
        "capability_boost": capability_boost,
        "jd_score": jd_score,
        "expected_total": expected_total,
        "scoring_text": scoring_text,
    }


def _rank_with_why(
    item_text: str,
    claims: dict[str, dict[str, Any]],
    jd_text: str,
) -> tuple[list[tuple[str, int]], dict[str, dict[str, Any]]]:
    """Score claims and attach a per-claim explanation.

    Args: item_text is the JD item; claims are isolated records; jd_text is
    the full-JD blob used by `jd_score`. Returns ranked (cid, total) plus
    explanations keyed by claim id.
    """
    profile = build_jd_profile_deterministic(jd_text)
    ranked = _score_claims_for_item(
        item_text, claims, set(), jd_profile=profile, jd_text=jd_text
    )
    why = {
        cid: _explain_claim(item_text, cid, rec, profile, jd_text)
        for cid, rec in claims.items()
    }
    return ranked, why


def _stage0(item: str) -> dict[str, Any]:
    """Minimal Stage 0 row for REPLACE-gate characterization."""
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


def _omitted(row: dict[str, Any]) -> dict[str, str]:
    """Map omitted claim_id → reason from an evidence_map row."""
    return {item["claim_id"]: item["reason"] for item in row.get("omitted_reasons") or []}


class TestCamundaDistributedSystemsKnownDefect(unittest.TestCase):
    """Camunda technical item: current formula vs desired messaging rank."""

    def test_overlap_is_weak_systems_optimization_not_messaging(self) -> None:
        ranked, why = _rank_with_why(
            CAMUNDA_DISTRIBUTED_ITEM, MESSAGING_CLAIMS, CAMUNDA_LIKE_JD
        )
        for cid, total in ranked:
            self.assertEqual(why[cid]["expected_total"], total)
        self.assertEqual(
            why["ACC-101-SAVINGS"]["overlap_words"],
            {"systems", "optimization"},
        )
        self.assertEqual(
            why["ACC-215-RABBITMQ"]["overlap_words"],
            {"distributed"},
        )
        self.assertEqual(
            why["ACC-189-KAFKA"]["overlap_words"],
            {"architecture"},
        )
        self.assertEqual(why["ACC-101-SAVINGS"]["capability_boost"], 0)
        self.assertGreater(
            why["ACC-101-SAVINGS"]["jd_score"],
            why["ACC-215-RABBITMQ"]["jd_score"],
        )

    def test_technical_messaging_beats_broad_savings_overlap(self) -> None:
        ranked, why = _rank_with_why(
            CAMUNDA_DISTRIBUTED_ITEM, MESSAGING_CLAIMS, CAMUNDA_LIKE_JD
        )
        slot1 = ranked[0][0]
        self.assertIn(slot1, DESIRED_CAMUNDA_SLOT1)
        self.assertLess(
            dict(ranked)["ACC-101-SAVINGS"],
            max(dict(ranked)[cid] for cid in DESIRED_CAMUNDA_SLOT1),
        )
        self.assertEqual(
            why["ACC-101-SAVINGS"]["overlap_words"],
            {"systems", "optimization"},
        )

    def test_source_does_not_assert_savings_as_desired_rank(self) -> None:
        src = __file__
        with open(src, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("known_defect", text)
        self.assertIn(KNOWN_DEFECT_CAMUNDA_SAVINGS, text)
        desired_assert = "assertEqual(" + "slot1, " + '"ACC-101-SAVINGS")'
        self.assertEqual(text.count(desired_assert), 0)


class TestSemanticVsFullJdOverlap(unittest.TestCase):
    """Same claims, different item: item semantics vs full-JD vibe."""

    def test_cost_item_savings_should_rank_first(self) -> None:
        ranked, why = _rank_with_why(
            COST_REDUCTION_ITEM, MESSAGING_CLAIMS, COST_REDUCTION_JD
        )
        self.assertEqual(ranked[0][0], "ACC-101-SAVINGS")
        self.assertGreater(ranked[0][1], 0)
        self.assertEqual(why["ACC-215-RABBITMQ"]["expected_total"], 0)
        self.assertEqual(why["ACC-189-KAFKA"]["expected_total"], 0)
        cost_tokens = why["ACC-101-SAVINGS"]["overlap_words"]
        self.assertTrue(cost_tokens & {"cost", "storage", "infrastructure", "optimization"})

    def test_arr_reliability_metric_claim_beats_process_only(self) -> None:
        ranked, why = _rank_with_why(
            ARR_RELIABILITY_ITEM, ARR_CLAIMS, ARR_RELIABILITY_JD
        )
        self.assertEqual(ranked[0][0], "ACC-101-PM")
        self.assertGreater(why["ACC-101-PM"]["expected_total"], 0)
        self.assertEqual(why["ACC-105-PROCESS"]["expected_total"], 0)

    def test_corpus_flips_camunda_but_keeps_cost_control(self) -> None:
        technical, _ = _rank_with_why(
            CAMUNDA_DISTRIBUTED_ITEM, MESSAGING_CLAIMS, CAMUNDA_LIKE_JD
        )
        cost, _ = _rank_with_why(
            COST_REDUCTION_ITEM, MESSAGING_CLAIMS, COST_REDUCTION_JD
        )
        self.assertEqual(cost[0][0], "ACC-101-SAVINGS")
        self.assertIn(technical[0][0], DESIRED_CAMUNDA_SLOT1)


class TestPearlAndSupplyHouseControls(unittest.TestCase):
    """REPLACE gate plus ranking characterization for closed-world extras."""

    def test_pearl_ranking_does_not_nominate_savings(self) -> None:
        ranked, why = _rank_with_why(PEARL_ITEM, PEARL_CLAIMS, PEARL_JD)
        self.assertEqual(why["ACC-101-SAVINGS"]["expected_total"], 0)
        self.assertNotEqual(ranked[0][0], "ACC-101-SAVINGS")
        self.assertIn(ranked[0][0], {"ACC-102-OPS", "ACC-101-PM"})

    def test_pearl_replace_gate_keeps_savings_out(self) -> None:
        ranked_patch = [
            ("ACC-102-OPS", 7322),
            ("ACC-101-PM", 4165),
            ("ACC-101-SAVINGS", 4164),
        ]
        trace: list = []
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=ranked_patch,
        ):
            em = build_evidence_map(
                _stage0(PEARL_ITEM),
                PEARL_JD,
                PEARL_CLAIMS,
                set(),
                jd_profile=None,
                trace_out=trace,
            )
        row = em[0]
        self.assertEqual(row["claim_ids"], ["ACC-102-OPS", "ACC-101-PM"])
        self.assertEqual(_omitted(row).get("ACC-101-SAVINGS"), "top2_cutoff")
        self.assertNotEqual(trace[0].get("decision"), "REPLACE")

    def test_supplyhouse_ranking_may_prefer_savings_but_replace_must_keep(self) -> None:
        ranked, why = _rank_with_why(
            SUPPLYHOUSE_ITEM, SUPPLYHOUSE_CLAIMS, SUPPLYHOUSE_JD
        )
        # Current ranking can still prefer SAVINGS via Infrastructure overlap.
        # That is characterization, not a desired Top-2 pick.
        self.assertIn("ACC-101-SAVINGS", [cid for cid, _ in ranked])
        self.assertGreaterEqual(why["ACC-101-SAVINGS"]["expected_total"], 0)
        ranked_patch = [
            ("ACC-101-PM", 90),
            ("ACC-101-SCOPE", 80),
            ("ACC-101-SAVINGS", 200),
        ]
        trace: list = []
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=ranked_patch,
        ):
            em = build_evidence_map(
                _stage0(SUPPLYHOUSE_ITEM),
                SUPPLYHOUSE_JD,
                SUPPLYHOUSE_CLAIMS,
                set(),
                jd_profile=None,
                trace_out=trace,
            )
        self.assertEqual(em[0]["claim_ids"], ["ACC-101-PM", "ACC-101-SCOPE"])
        self.assertNotIn("ACC-101-SAVINGS", em[0]["claim_ids"])
        self.assertNotEqual(trace[0].get("decision"), "REPLACE")


class TestNearTieStableNoAutoReplace(unittest.TestCase):
    """Near-tie ranking stays stable; comparator must not auto-REPLACE."""

    def test_ranking_order_is_deterministic(self) -> None:
        item = "Own cost and savings on the platform"
        claims = {
            "ACC-101-PM": {
                "employer": "cision",
                "project_id": "ACC-101",
                "tags": ["platform", "cost", "savings"],
                "attribution": "OWNED",
            },
            "ACC-102-OPS": {
                "employer": "cision",
                "project_id": "ACC-102",
                "tags": ["operations", "cost", "savings"],
                "attribution": "OWNED",
            },
        }
        first, _ = _rank_with_why(item, claims, item)
        second, _ = _rank_with_why(item, claims, item)
        self.assertEqual(first, second)

    def test_near_tie_comparator_does_not_replace(self) -> None:
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


class TestFormulaContract(unittest.TestCase):
    """Guard: characterization must use the live ranker arithmetic."""

    def test_live_function_is_score_claims_for_item(self) -> None:
        ranked, why = _rank_with_why(
            CAMUNDA_DISTRIBUTED_ITEM, MESSAGING_CLAIMS, CAMUNDA_LIKE_JD
        )
        self.assertTrue(ranked)
        live_totals = dict(ranked)
        for cid, rec in why.items():
            self.assertEqual(live_totals[cid], rec["expected_total"])


if __name__ == "__main__":
    unittest.main()
