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
    _claim_is_eligible_for_ats_contract,
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


class TestAtsTermContractEligibilityAnchor(unittest.TestCase):
    """CR-112-ats-term-contract-eligibility-defect: the fallback (tag-matched,
    no evidence_map anchor) path must not manufacture an ATS-term requirement
    from a term whose only real JD occurrence is outside the required/
    preferred/responsibilities text (e.g. benefits boilerplate or marketing
    copy) -- that produced an impossible citation demand in a real submission
    (Camunda: "Support" -> ACC-185-CUSTOMER-DISCOVERY, whose card has no
    allowed_claims; "Visible" -> ACC-134-VISIBLE, a banned VOC codename whose
    only JD occurrence was "visible impact" in recruiting copy).
    """

    def test_fallback_term_without_requirement_anchor_is_dropped(self):
        import jd_term_extractor as j

        with mock.patch.object(
            j, "_load_true_vocabulary", return_value={"support": "Support"}
        ):
            contract = build_packet_ats_term_contract(
                jd_text="Perks that support you no matter where you are based.",
                evidence_map=[],
                claims={"ACC-185-X": {"tags": ["Support Signals"]}},
                excerpt_claim_ids={"ACC-185-X"},
                requirement_text="Own the roadmap and ship on time.",
            )
        self.assertEqual(contract, [])

    def test_fallback_term_with_requirement_anchor_is_kept(self):
        import jd_term_extractor as j

        with mock.patch.object(
            j, "_load_true_vocabulary", return_value={"support": "Support"}
        ):
            contract = build_packet_ats_term_contract(
                jd_text="Provide support for enterprise customers day to day.",
                evidence_map=[],
                claims={"ACC-185-X": {"tags": ["Support Signals"]}},
                excerpt_claim_ids={"ACC-185-X"},
                requirement_text="Provide support for enterprise customers day to day.",
            )
        self.assertEqual(len(contract), 1)
        self.assertEqual(contract[0]["term"], "Support")
        self.assertEqual(contract[0]["claim_ids"], ["ACC-185-X"])

    def test_requirement_text_none_preserves_legacy_behavior(self):
        """No requirement_text passed (older/other caller) -> unchanged from
        pre-fix behavior; a term with no real anchor still enters via tag
        match alone. Confirms the anchor check is opt-in, not a silent
        behavior change for any caller that hasn't been updated."""
        import jd_term_extractor as j

        with mock.patch.object(
            j, "_load_true_vocabulary", return_value={"support": "Support"}
        ):
            contract = build_packet_ats_term_contract(
                jd_text="Perks that support you no matter where you are based.",
                evidence_map=[],
                claims={"ACC-185-X": {"tags": ["Support Signals"]}},
                excerpt_claim_ids={"ACC-185-X"},
            )
        self.assertEqual(len(contract), 1)
        self.assertEqual(contract[0]["term"], "Support")

    def test_disabled_claim_dropped_from_fallback_path(self):
        import jd_term_extractor as j

        with mock.patch.object(
            j, "_load_true_vocabulary", return_value={"support": "Support"}
        ):
            contract = build_packet_ats_term_contract(
                jd_text="Provide support for enterprise customers.",
                evidence_map=[],
                claims={"ACC-185-X": {"tags": ["Support Signals"]}},
                excerpt_claim_ids={"ACC-185-X"},
                disabled={"ACC-185-X"},
                requirement_text="Provide support for enterprise customers.",
            )
        self.assertEqual(contract, [])

    def test_disabled_claim_dropped_from_main_loop(self):
        contract = build_packet_ats_term_contract(
            jd_text="Own the roadmap for our platform.",
            evidence_map=[
                {
                    "jd_item": "Own the roadmap for our platform.",
                    "claim_ids": ["ACC-179-ROADMAP"],
                }
            ],
            disabled={"ACC-179-ROADMAP"},
        )
        self.assertEqual(contract, [])

    def test_main_loop_anchored_term_unaffected_by_requirement_text(self):
        """A term already anchored via evidence_map (main loop) must survive
        regardless of requirement_text -- the anchor check only applies to
        the tag-matched fallback path, per the design doc."""
        contract = build_packet_ats_term_contract(
            jd_text="Own the roadmap for our platform.",
            evidence_map=[
                {
                    "jd_item": "Own the roadmap for our platform.",
                    "claim_ids": ["ACC-179-ROADMAP"],
                }
            ],
            requirement_text="",  # deliberately empty/unrelated
        )
        self.assertEqual(len(contract), 1)
        self.assertEqual(contract[0]["claim_ids"], ["ACC-179-ROADMAP"])

    def test_camunda_sanitized_repro(self):
        """Sanitized synthetic fixture reproducing the exact original failure
        shape without real JD or candidate text (test 18 of the design doc's
        list): a term present only in non-requirement JD text, tag-matched to
        a claim with no usable evidence."""
        import jd_term_extractor as j

        jd_text = (
            "We invest in your wellbeing, growth, and perks that support you "
            "no matter where you are based.\n"
            "Own the roadmap for foundational platform capabilities."
        )
        requirement_text = "Own the roadmap for foundational platform capabilities."
        with mock.patch.object(
            j,
            "_load_true_vocabulary",
            return_value={"support": "Support", "roadmap": "Roadmap"},
        ):
            contract = build_packet_ats_term_contract(
                jd_text=jd_text,
                evidence_map=[],
                claims={
                    "SIM-UNUSABLE": {"tags": ["Support Signals"]},
                    "SIM-USABLE": {"tags": ["Roadmap"]},
                },
                excerpt_claim_ids={"SIM-UNUSABLE", "SIM-USABLE"},
                requirement_text=requirement_text,
            )
        terms = sorted(e["term"] for e in contract)
        self.assertEqual(terms, ["Roadmap"])


class TestAtsTermContractClaimEligibility(unittest.TestCase):
    """CR-112 design doc's "Eligibility filter" section (design_v1_pending_review,
    2026-09-13) was never implemented -- confirmed via grep, zero references to
    eligible_claim_ids/NOT_ACTIONABLE anywhere in scripts/. This is the real,
    still-open half of FIXQUEUE bug #8 (2026-09-21): the requirement_text anchor
    only checks WHERE a term occurs in the JD, never WHETHER the claim it would
    cite is actually usable, so a genuinely-anchored term could still cite a
    "flagged but unusable" claim (empty allowed_claims, non-empty
    prohibited_claims -- the same shape ACC-185-CUSTOMER-DISCOVERY had before
    it was disabled for FIXQUEUE bug #5)."""

    def test_helper_flags_flagged_but_unusable_claim(self):
        self.assertFalse(_claim_is_eligible_for_ats_contract(
            "X", {"X": {"allowed_claims": [], "prohibited_claims": ["no"]}}
        ))

    def test_helper_allows_claim_with_real_allowed_claims(self):
        self.assertTrue(_claim_is_eligible_for_ats_contract(
            "X", {"X": {"allowed_claims": ["real thing"], "prohibited_claims": ["no"]}}
        ))

    def test_helper_allows_unconstrained_empty_empty_card(self):
        """No allowed_claims, no prohibited_claims -- unconstrained, per the
        design doc's own rule, stays eligible."""
        self.assertTrue(_claim_is_eligible_for_ats_contract("X", {"X": {}}))
        self.assertTrue(_claim_is_eligible_for_ats_contract("X", {}))

    def test_fallback_loop_drops_ineligible_claim_even_when_anchored(self):
        """Design doc test 1/4 shape: term genuinely anchored via
        requirement_text, but the only candidate claim is flagged-unusable."""
        import jd_term_extractor as j

        with mock.patch.object(
            j, "_load_true_vocabulary",
            return_value={"customer discovery": "Customer Discovery"},
        ):
            contract = build_packet_ats_term_contract(
                jd_text="Run customer discovery interviews with enterprise accounts weekly.",
                evidence_map=[],
                claims={
                    "ACC-BOUNDARY-X": {
                        "tags": ["Customer Discovery"],
                        "allowed_claims": [],
                        "prohibited_claims": ["that direct discovery conversations occurred"],
                    },
                },
                excerpt_claim_ids={"ACC-BOUNDARY-X"},
                requirement_text="Run customer discovery interviews with enterprise accounts weekly.",
            )
        self.assertEqual(contract, [])

    def test_fallback_loop_keeps_eligible_sibling_when_one_claim_ineligible(self):
        """Design doc test 5 shape: an ineligible and an eligible claim both
        tag-match the same term -- only the eligible one should survive."""
        import jd_term_extractor as j

        with mock.patch.object(
            j, "_load_true_vocabulary",
            return_value={"customer discovery": "Customer Discovery"},
        ):
            contract = build_packet_ats_term_contract(
                jd_text="Run customer discovery interviews with enterprise accounts weekly.",
                evidence_map=[],
                claims={
                    "ACC-BOUNDARY-X": {
                        "tags": ["Customer Discovery"],
                        "allowed_claims": [],
                        "prohibited_claims": ["that direct discovery conversations occurred"],
                    },
                    "ACC-REAL-Y": {
                        "tags": ["Customer Discovery"],
                        "allowed_claims": ["ran structured feedback sessions"],
                        "prohibited_claims": ["a formal discovery program"],
                    },
                },
                excerpt_claim_ids={"ACC-BOUNDARY-X", "ACC-REAL-Y"},
                requirement_text="Run customer discovery interviews with enterprise accounts weekly.",
            )
        self.assertEqual(len(contract), 1)
        self.assertEqual(contract[0]["claim_ids"], ["ACC-REAL-Y"])

    def test_main_loop_drops_ineligible_claim(self):
        """Design doc test 1 shape, but via the evidence_map-anchored main
        loop rather than the tag-matched fallback loop."""
        contract = build_packet_ats_term_contract(
            jd_text="Run agile ceremonies with the team.",
            evidence_map=[{
                "jd_item": "Run agile ceremonies with the team.",
                "claim_ids": ["ACC-BOUNDARY-Y"],
            }],
            claims={"ACC-BOUNDARY-Y": {"allowed_claims": [], "prohibited_claims": ["no"]}},
        )
        self.assertEqual(contract, [])

    def test_main_loop_keeps_eligible_sibling_when_one_claim_ineligible(self):
        contract = build_packet_ats_term_contract(
            jd_text="Run agile ceremonies with the team.",
            evidence_map=[{
                "jd_item": "Run agile ceremonies with the team.",
                "claim_ids": ["ACC-BOUNDARY-Y", "ACC-REAL-Z"],
            }],
            claims={
                "ACC-BOUNDARY-Y": {"allowed_claims": [], "prohibited_claims": ["no"]},
                "ACC-REAL-Z": {"allowed_claims": ["ran agile ceremonies"], "prohibited_claims": []},
            },
        )
        self.assertTrue(contract, "real vocabulary should still match at least one term")
        for entry in contract:
            self.assertEqual(entry["claim_ids"], ["ACC-REAL-Z"])
