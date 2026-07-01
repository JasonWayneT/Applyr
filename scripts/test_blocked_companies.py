#!/usr/bin/env python3
"""Blocked company gate — CR-054 Epic 3."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from batch_pipeline import passes_jd_keyword_gate

JD = "Title: Senior TPM\nGaming platform. B2B SaaS roadmap cross-functional agile."
JD_SAFE = "Title: Product Manager\nB2B SaaS platform roadmap cross-functional agile stakeholder."


def main() -> int:
    print("VERIFY-BLOCKED-COMPANIES (CR-054 Epic 3)")
    prefs = {
        "blocked_companies": ["Unity"],
        "blocked_role_titles": ["Director"],
        "experience_range": {"max": 7},
        "signal_keywords": ["saas", "platform", "roadmap"],
    }
    if passes_jd_keyword_gate(JD, prefs, company_name="Unity"):
        print("  [FAIL] Unity should be blocked")
        return 1
    print("  [PASS] Unity blocked at gate")
    if not passes_jd_keyword_gate(JD_SAFE, prefs, company_name="Acme Corp"):
        print("  [FAIL] unrelated company should pass title/years gates")
        return 1
    print("  [PASS] non-blocked company passes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
