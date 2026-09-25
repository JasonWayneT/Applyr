"""Unit checks for the independent loop evaluator. Not a pipeline gate."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loop_eval import evaluate_pair  # noqa: E402

_RESUME = """# Name
contact

## PROFESSIONAL SUMMARY
A product manager who writes requirements with engineering.

## PROFESSIONAL EXPERIENCE
### Product Manager | Cision | September 2021 - January 2026
Remote
* Saved $8,500 per quarter by replacing a manual setup.
* Saved $8,500 annually by replacing a manual setup.

### Product Manager / Product Owner | Sterkly | February 2019 - August 2021
Remote
* Shipped a macOS security product.

### Account Manager / Product Owner | Zero To Sixty | June 2017 - January 2019
Remote
* Ran account work.
"""

_LETTER = """# Name
contact

Dear Hiring Manager,

The migration finished without service disruption.

Best regards,
Name
"""


class TestLoopEval(unittest.TestCase):
    def test_unit_drift_and_dropped_disruption_hedge_are_flagged(self) -> None:
        findings = evaluate_pair(_RESUME, _LETTER, None)
        rules = {row["rule"] for row in findings}
        self.assertIn("L1-metric-unit", rules)
        self.assertIn("L1-disruption-hedge", rules)
        annual = [row for row in findings if row["rule"] == "L1-metric-unit"]
        self.assertTrue(any("annually" in row["text"] for row in annual))
        self.assertFalse(any("per quarter" in row["text"] for row in annual))

    def test_empty_role_is_flagged(self) -> None:
        resume = _RESUME.replace(
            "* Shipped a macOS security product.\n",
            "",
        )
        findings = evaluate_pair(resume, _LETTER, None)
        self.assertTrue(any(row["rule"] == "L1-empty-role" for row in findings))


if __name__ == "__main__":
    unittest.main()
