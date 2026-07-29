#!/usr/bin/env python3
"""Location gate regression fixtures — CR-053 Epic 1 / Phase D prefs-driven geo."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from zero_shot_classifier import classify_onsite, resolve_location_verdict

# Example prefs — local areas are user-configured, not hardcoded in code.
TEST_PREFS = {
    "location_preference": "United States",
    "local_area_terms": ["san diego"],
    "timezone_flexibility_terms": [],
}

# Synthetic fixtures from calibration self-reject notes (jd_text empty in DB for many rows).
FIXTURES_REJECT = [
    (
        "case_iq_canada",
        "Title: Product Owner\nCompany: Case IQ\nLocation: In person, Ottawa, Canada\n"
        "About the role: On-site collaboration with the product team in Canada.",
        True,
    ),
    (
        "secureframe_hybrid_nyc",
        "Title: Product Manager\nLocation: Hybrid, New York City, NY\n"
        "This is a hybrid role based in our NYC office. 3 days per week in-office.",
        True,
    ),
    (
        "yeet_onsite_chicago",
        "Title: Product Manager\nLocation: Chicago, IL\nOn-site position in Chicago.",
        True,
    ),
    (
        "mandolin_onsite_sf",
        "Title: Product Manager\nOn-site role in San Francisco, CA.",
        True,
    ),
    (
        "agreeya_sacramento_hybrid",
        "Title: Product Manager\nHybrid role based in Sacramento, CA.",
        True,
    ),
]

FIXTURES_PASS = [
    (
        "true_remote_us",
        "Title: Product Manager\nFully remote position. Work from anywhere in the United States.",
        False,
    ),
    (
        "remote_or_dallas",
        "Title: Product Manager\nLocation: Dallas, TX or Remote within the US.",
        False,
    ),
    (
        "san_diego_local",
        "Title: Product Manager\nHybrid role in San Diego, CA.",
        False,
    ),
    (
        "pm_growth_remote",
        "Title: Product Manager, Growth\nRemote-first B2B SaaS company.",
        False,
    ),
    (
        "sai360_est_remote_default",
        "Title: Product Manager\nRemote role. Must be located in EST or CST timezone.",
        False,
    ),
]

FIXTURES_REJECT_OPT_IN_TZ = [
    (
        "sai360_est_remote_opt_in",
        "Title: Product Manager\nRemote role. Must be located in EST or CST timezone.",
        True,
    ),
]


def _assert(name: str, jd: str, expect_reject: bool, prefs: dict | None = None) -> int:
    prefs = prefs or TEST_PREFS
    verdict, _ = resolve_location_verdict(jd, prefs)
    reject, reason = classify_onsite(jd, prefs)
    ok = reject == expect_reject
    if ok:
        print(f"  [PASS] {name} verdict={verdict}")
        return 0
    print(f"  [FAIL] {name} reject={reject} verdict={verdict} reason={reason!r}")
    return 1


def main() -> int:
    print("VERIFY-LOCATION-GATE: calibration-derived fixtures (prefs-driven geo)")
    failed = 0
    for name, jd, expect_reject in FIXTURES_REJECT + FIXTURES_PASS:
        failed += _assert(name, jd, expect_reject)
    opt_in_prefs = {
        **TEST_PREFS,
        "preferences": {"reject_est_cst_remote": True},
    }
    for name, jd, expect_reject in FIXTURES_REJECT_OPT_IN_TZ:
        failed += _assert(name, jd, expect_reject, opt_in_prefs)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
