#!/usr/bin/env python3
"""CR-112 Story 3.4 — admin fingerprint/schedule skip (FR-305 / AC-402)."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_authoring_packet import build_evidence_map
from build_stage0_fit_gate import _is_administratively_satisfied

_ROADMAP = {
    "ACC-103-ROADMAP": {
        "employer": "cision",
        "project_id": "ACC-103",
        "tags": [
            "fingerprint",
            "roadmap",
            "background",
            "security",
            "weekends",
            "nights",
        ],
        "attribution": "OWNED",
    },
    "ACC-101-PM": {
        "employer": "cision",
        "project_id": "ACC-101",
        "tags": ["platform", "product management", "saas"],
        "attribution": "OWNED",
    },
}

_FINGERPRINT = "Must pass a Level II fingerprint background check"
_NIGHTS = "Nights and weekends availability required"
_ROADMAP_ITEM = "Own the product roadmap and prioritization"
_RELEASE = "Own the release schedule with engineering"
_PRODUCT_BG = "Own the background check product roadmap"
_YEARS = "5+ years product management on a B2B SaaS platform"
_BACHELORS = "Bachelor's degree in Computer Science or equivalent"


def _stage0(*items: str) -> dict:
    return {
        "tier": "Tier 1",
        "thin_jd": True,
        "required": [{"item": item, "gap": False} for item in items],
        "preferred": [],
        "responsibilities": [],
        "flagged_gaps": [],
    }


class TestAdminScreeningSkip(unittest.TestCase):
    def test_fingerprint_line_gets_no_roadmap_claim(self) -> None:
        """AC-34-1 / AC-34-6."""
        scored: list[str] = []

        def spy(item_text: str, *args: object, **kwargs: object):
            scored.append(item_text)
            return [("ACC-103-ROADMAP", 90)]

        with patch("build_authoring_packet._score_claims_for_item", side_effect=spy):
            em = build_evidence_map(
                _stage0(_FINGERPRINT, _ROADMAP_ITEM),
                _FINGERPRINT,
                _ROADMAP,
                set(),
                jd_profile=None,
            )
        fingerprint = next(r for r in em if r["jd_item"] == _FINGERPRINT)
        self.assertEqual(fingerprint["claim_ids"], [])
        self.assertNotIn("ACC-103-ROADMAP", fingerprint["claim_ids"])
        self.assertIn("Administratively satisfied", fingerprint["bridge"] or "")
        self.assertNotIn(_FINGERPRINT, scored)
        self.assertIn(_ROADMAP_ITEM, scored)

    def test_nights_and_weekends_gets_no_roadmap_claim(self) -> None:
        """AC-34-2."""
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=[("ACC-103-ROADMAP", 90)],
        ):
            em = build_evidence_map(
                _stage0(_NIGHTS),
                _NIGHTS,
                _ROADMAP,
                set(),
                jd_profile=None,
            )
        self.assertEqual(em[0]["claim_ids"], [])
        self.assertNotIn("ACC-103-ROADMAP", em[0]["claim_ids"])
        self.assertIn("Administratively satisfied", em[0]["bridge"] or "")

    def test_product_roadmap_item_can_receive_roadmap_claim(self) -> None:
        """AC-34-3 negative control."""
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=[("ACC-103-ROADMAP", 90)],
        ):
            em = build_evidence_map(
                _stage0(_ROADMAP_ITEM),
                _ROADMAP_ITEM,
                _ROADMAP,
                set(),
                jd_profile=None,
            )
        self.assertIn("ACC-103-ROADMAP", em[0]["claim_ids"])


class TestAdminMatcherNegatives(unittest.TestCase):
    def test_release_schedule_is_not_admin(self) -> None:
        """AC-34-4."""
        self.assertFalse(_is_administratively_satisfied(_RELEASE.lower()))
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=[("ACC-103-ROADMAP", 90)],
        ):
            em = build_evidence_map(
                _stage0(_RELEASE),
                _RELEASE,
                _ROADMAP,
                set(),
                jd_profile=None,
            )
        self.assertIn("ACC-103-ROADMAP", em[0]["claim_ids"])

    def test_years_line_still_may_receive_claims(self) -> None:
        """AC-34-5: years stay scorable; bachelor's stays admin."""
        self.assertTrue(_is_administratively_satisfied(_BACHELORS.lower()))
        self.assertTrue(_is_administratively_satisfied(_YEARS.lower()))
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=[("ACC-101-PM", 90)],
        ):
            em = build_evidence_map(
                _stage0(_YEARS, _BACHELORS),
                _YEARS,
                _ROADMAP,
                set(),
                jd_profile=None,
            )
        years = next(r for r in em if r["jd_item"] == _YEARS)
        bachelors = next(r for r in em if r["jd_item"] == _BACHELORS)
        self.assertIn("ACC-101-PM", years["claim_ids"])
        self.assertEqual(bachelors["claim_ids"], [])
        self.assertIn("Administratively satisfied", bachelors["bridge"] or "")

    def test_product_background_check_roadmap_is_not_admin(self) -> None:
        """AC-34-7."""
        self.assertFalse(_is_administratively_satisfied(_PRODUCT_BG.lower()))
        with patch(
            "build_authoring_packet._score_claims_for_item",
            return_value=[("ACC-103-ROADMAP", 90)],
        ):
            em = build_evidence_map(
                _stage0(_PRODUCT_BG),
                _PRODUCT_BG,
                _ROADMAP,
                set(),
                jd_profile=None,
            )
        self.assertIn("ACC-103-ROADMAP", em[0]["claim_ids"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
