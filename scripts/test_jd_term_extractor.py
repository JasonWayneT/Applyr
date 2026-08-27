"""Tests for jd_term_extractor.py's stemmed resume matching.

Added 2026-08-18 -- no prior test coverage existed for this script. The same-day
fix (matching word-form variants like "Supported" for "Support" instead of exact-
literal-only) had nothing regression-testing it beyond a manual check against one
real submission folder.
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

from jd_term_extractor import (  # noqa: E402
    _stem,
    _term_present_stemmed,
    build_packet_ats_term_contract,
    find_jd_term_gaps,
)


def test_stem_reduces_known_word_form_pairs_to_same_root():
    assert _stem("support") == _stem("supported")
    assert _stem("reliability") == _stem("reliable")


def test_stem_does_not_corrupt_short_important_terms():
    for term in ("sql", "ai", "api", "ux"):
        assert _stem(term) == term


def test_term_present_stemmed_matches_inflected_form():
    assert _term_present_stemmed("support", "i supported the team through the migration")
    assert _term_present_stemmed("reliability", "the platform stayed reliable under load")


def test_term_present_stemmed_multiword_term_stays_exact_literal():
    """Multi-word phrases deliberately keep the original exact-literal match --
    stemming a phrase's word order/components is a different, riskier problem
    this fix doesn't attempt."""
    assert not _term_present_stemmed("product lifecycle", "I owned the lifecycle of several products")
    assert _term_present_stemmed("product lifecycle", "I owned the product lifecycle end to end")


def test_find_jd_term_gaps_no_longer_flags_inflected_resume_term(monkeypatch, tmp_path):
    """Regression: the real false positive found 2026-08-18 -- a JD requiring
    "Support" (catalog term) must not be flagged missing when the resume says
    "Supported" instead of the bare literal word."""
    import jd_term_extractor as j

    monkeypatch.setattr(j, "_load_true_vocabulary", lambda: {"support": "Support"})
    result = find_jd_term_gaps(
        jd_text="This role requires strong customer support experience.",
        resume_text="* Supported enterprise accounts through a major platform migration.",
    )
    assert result["missing_from_resume"] == []


def test_find_jd_term_gaps_still_flags_genuinely_absent_term(monkeypatch):
    import jd_term_extractor as j

    monkeypatch.setattr(j, "_load_true_vocabulary", lambda: {"support": "Support"})
    result = find_jd_term_gaps(
        jd_text="This role requires strong customer support experience.",
        resume_text="* Shipped a roadmap feature on time.",
    )
    assert result["missing_from_resume"] == ["Support"]


class TestPacketAtsTermContract(unittest.TestCase):
    def test_requires_only_mapped_jd_terms(self):
        import jd_term_extractor as j

        with mock.patch.object(
            j,
            "_load_true_vocabulary",
            return_value={
                "support": "Support",
                "engagement": "Engagement",
                "analytics": "Analytics",
            },
        ):
            contract = build_packet_ats_term_contract(
                "Support and engagement matter. Analytics is also valuable.",
                [
                    {
                        "jd_item": "Support ongoing member engagement.",
                        "claim_ids": ["ACC-112-PIPELINE"],
                    },
                    {
                        "jd_item": "Analytics is valuable.",
                        "claim_ids": [],
                    },
                ],
            )
        self.assertEqual(
            contract,
            [
                {
                    "term": "Engagement",
                    "claim_ids": ["ACC-112-PIPELINE"],
                    "jd_items": ["Support ongoing member engagement."],
                },
                {
                    "term": "Support",
                    "claim_ids": ["ACC-112-PIPELINE"],
                    "jd_items": ["Support ongoing member engagement."],
                },
            ],
        )

    def test_packet_excerpt_tag_covers_stage0_omission(self):
        import jd_term_extractor as j

        with mock.patch.object(
            j,
            "_load_true_vocabulary",
            return_value={"cross-functional planning": "Cross-Functional Planning"},
        ):
            contract = build_packet_ats_term_contract(
                "Lead cross-functional planning cycles.",
                evidence_map=[],
                claims={
                    "ACC-178-SCOPING": {
                        "tags": ["Product Scoping", "Cross-Functional Planning"]
                    }
                },
                excerpt_claim_ids={"ACC-178-SCOPING"},
            )
        self.assertEqual(contract[0]["term"], "Cross-Functional Planning")
        self.assertEqual(contract[0]["claim_ids"], ["ACC-178-SCOPING"])
