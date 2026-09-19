#!/usr/bin/env python3
"""CR-118 false-skip regressions from the sitting-2 marks. Implements FR-337–FR-339."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("APPLYR_STAGE0_SECTION_MODE", "deterministic")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jd_content_validation import check_network_page
from stage0_prefs_gate import (
    _check_blocked_company,
    _check_people_management,
    run_prefs_gate,
)

_PREFS = {
    "blocked_companies": ["RemoteHunter", "Unity"],
    "experience_range": {"max": 7},
}

SMARTLIGHT = (
    "This is not a people-management role and carries no direct reports."
)
ESO = (
    "Provide direct support and coaching to all levels of management as they "
    "help their direct reports."
)


class TestCompanyExactMatch(unittest.TestCase):
    def test_remote_does_not_match_remotehunter(self) -> None:
        rejects = _check_blocked_company("Remote", _PREFS)
        self.assertEqual(rejects, [])

    def test_blank_company_does_not_match(self) -> None:
        rejects = _check_blocked_company("", _PREFS)
        self.assertEqual(rejects, [])
        rejects = _check_blocked_company("   ", _PREFS)
        self.assertEqual(rejects, [])

    def test_exact_unity_still_blocks(self) -> None:
        rejects = _check_blocked_company("Unity", _PREFS)
        self.assertEqual(rejects[0]["code"], "blocked_company")


class TestPeopleManagementNegation(unittest.TestCase):
    def test_smartlight_not_a_people_management_role(self) -> None:
        self.assertEqual(_check_people_management(SMARTLIGHT), [])

    def test_eso_coaching_other_managers_reports(self) -> None:
        self.assertEqual(_check_people_management(ESO), [])

    def test_eso_mentoring_junior_talent_does_not_skip(self) -> None:
        jd = (
            ESO
            + " Mentoring junior talent and coaching to all levels of management "
            "as they help their direct reports."
        )
        self.assertEqual(_check_people_management(jd), [])

    def test_role_with_direct_reports_still_skips(self) -> None:
        jd = "You will have 3 direct reports and manage a team of engineers."
        codes = {row["code"] for row in _check_people_management(jd)}
        self.assertIn("exclusion_zone_people_management", codes)


class TestNetworkPageIsFlag(unittest.TestCase):
    def test_network_page_does_not_skip_prefs(self) -> None:
        jd = "Apply once and get matched with employers. Join our talent network."
        with patch(
            "industry_semantic.classify_industry_safe",
            return_value={"blocked_industry": "", "confidence": "high", "reasoning": "test"},
        ):
            result = run_prefs_gate("Acme", jd, _PREFS)
        codes = {row["code"] for row in result["rejects"]}
        self.assertNotIn("network_page", codes)
        flag_codes = {row["code"] for row in result["flags"]}
        self.assertIn("network_page", flag_codes)
        self.assertTrue(check_network_page(jd))


class TestPreferredLeadInHeader(unittest.TestCase):
    def test_also_great_to_have_is_preferred_header(self) -> None:
        from build_stage0_fit_gate import _extract_sections, classify_jd_header

        bucket, is_label = classify_jd_header("Also great to have:")
        self.assertEqual(bucket, "preferred")
        self.assertTrue(is_label)
        jd = (
            "Requirements\n"
            "- 5+ years of product management experience\n"
            "Also great to have:\n"
            "- CSPO certification is a plus\n"
        )
        buckets = _extract_sections(jd)
        self.assertTrue(any("CSPO" in item for item in buckets["preferred"]))
        self.assertFalse(any("CSPO" in item for item in buckets["required"]))

    def test_is_required_overrides_preferred_header(self) -> None:
        from build_stage0_fit_gate import _extract_sections

        jd = (
            "Preferred Qualifications\n"
            "- Financial services, banking, or payments industry experience is required\n"
        )
        buckets = _extract_sections(jd)
        self.assertTrue(
            any("Financial services" in item for item in buckets["required"])
        )
        self.assertFalse(
            any("Financial services" in item for item in buckets["preferred"])
        )


if __name__ == "__main__":
    unittest.main()
