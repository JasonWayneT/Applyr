#!/usr/bin/env python3
"""Solo PM trap gate tests — FR-189 / CR-036."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from solo_pm_gate import check_solo_pm_gate

PREFS = {
    "preferences": {
        "avoid_solo_pm_trap": True,
        "structured_team_required": True,
    }
}


def _assert(name: str, cond: bool, detail: str = "") -> int:
    if cond:
        print(f"  [PASS] {name}")
        return 0
    print(f"  [FAIL] {name} {detail}")
    return 1


def main() -> int:
    print("VERIFY-SOLO-PM: solo trap gate (FR-189)")
    failed = 0

    reject_jds = [
        ("Founding PM", "You will be our first product manager and build the product function."),
        ("Only PM", "You will be the only product manager on the team reporting to the CEO."),
        ("First hire", "We are looking for our first PM hire to establish the product team."),
    ]
    for label, jd in reject_jds:
        ok, reason = check_solo_pm_gate(jd, PREFS)
        failed += _assert(f"reject {label}", not ok and reason.startswith("solo_pm_trap"), reason)

    pass_jds = [
        (
            "DailyPay squad",
            "Senior Product Manager for a squad within our product organization. "
            "Guide L1/L2 PMs through informal mentorship.",
        ),
        (
            "Structured org",
            "Product Manager reporting to Director of Product. Work with peer PMs on the product organization.",
        ),
        (
            "Cross-functional",
            "Own roadmap for your squad. Collaborate cross-functionally with engineering and design.",
        ),
    ]
    for label, jd in pass_jds:
        ok, reason = check_solo_pm_gate(jd, PREFS)
        failed += _assert(f"pass {label}", ok, reason)

    disabled = {"preferences": {"avoid_solo_pm_trap": False}}
    ok, _ = check_solo_pm_gate(reject_jds[0][1], disabled)
    failed += _assert("disabled preference skips gate", ok)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
