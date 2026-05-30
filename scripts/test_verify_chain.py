#!/usr/bin/env python3
"""
Tier A verification_chain unit tests (CR-ARCH-001 / VERIFY-01).

No full verify_document_bundle — inline fixtures only; STRICT_* env off.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Pin strict modes off for deterministic CI
os.environ.pop("STRICT_METRICS", None)
os.environ.pop("STRICT_ANTI_CLAIMS", None)

from verification_chain import (
    strip_all_metadata_tokens,
    check_jd_inflation_in_output,
    check_anti_claims,
)

passed = 0
failed = 0


def assert_test(name: str, condition: bool, error_msg: str = "") -> None:
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name}: {error_msg}")
        failed += 1


def main() -> None:
    print("VERIFY-01: verification_chain Tier A tests")

    text = "Shipped feature [ACC-101] and metric [MET-05]."
    stripped = strip_all_metadata_tokens(text)
    assert_test(
        "VERIFY-01a: strip_all_metadata_tokens",
        "ACC-101" not in stripped and "MET-05" not in stripped,
        stripped,
    )

    jd = "We need someone who led a team of 50 engineers."
    resume = "Led platform work for internal tools."
    assert_test(
        "VERIFY-01b: check_jd_inflation no leak when JD has mgmt phrase",
        check_jd_inflation_in_output(resume, jd) is None,
        "unexpected inflation hit",
    )

    jd_mgmt = "Managed a team of 12 direct reports."
    resume_echo = "Managed a team of 12 direct reports on the platform."
    assert_test(
        "VERIFY-01c: check_jd_inflation detects echo",
        check_jd_inflation_in_output(resume_echo, jd_mgmt) is not None,
        "expected inflation detection",
    )

    hints = ["cryptocurrency expertise across the org"]
    bad = "Built cryptocurrency expertise across the org."
    assert_test(
        "VERIFY-01d: check_anti_claims",
        check_anti_claims(bad, hints) is not None,
        "expected anti-claim hit",
    )

    print(f"\nVERIFY-01 complete: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
