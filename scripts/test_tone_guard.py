"""Tests for scripts/tone_guard.py."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tone_guard import sanitize_submission_tone, tone_violations  # noqa: E402


class TestToneGuard(unittest.TestCase):
    def test_workforce_attrition_still_blocked(self) -> None:
        text = "The team navigated a period of workforce attrition."
        self.assertEqual(tone_violations(text), ["attrition"])

    def test_bare_attrition_still_blocked(self) -> None:
        text = "Hiring slowed during a period of attrition."
        self.assertEqual(tone_violations(text), ["attrition"])

    def test_layoffs_still_blocked(self) -> None:
        self.assertTrue(tone_violations("The company went through layoffs."))

    def test_customer_attrition_is_not_blocked(self) -> None:
        """Found live on swoon, 2026-09-20: 'customer attrition' is standard
        churn vocabulary, unrelated to workforce reduction, but the bare
        \\battrition\\b pattern fired on it anyway."""
        text = "Stale contact information was a primary driver of customer attrition."
        self.assertEqual(tone_violations(text), [])

    def test_client_and_subscriber_attrition_not_blocked(self) -> None:
        self.assertEqual(tone_violations("A rise in client attrition followed."), [])
        self.assertEqual(tone_violations("Subscriber attrition rose that quarter."), [])

    def test_account_user_member_attrition_not_blocked(self) -> None:
        """Found live on isolved, 2026-09-21: 'account attrition' is exactly
        the same class of ordinary SaaS churn vocabulary as 'customer
        attrition' (fixed 2026-09-20), just a different noun the original
        allowlist didn't happen to include."""
        self.assertEqual(
            tone_violations("data accuracy issues were driving account attrition."), []
        )
        self.assertEqual(tone_violations("user attrition rose that quarter."), [])
        self.assertEqual(tone_violations("member attrition was the main driver."), [])

    def test_sanitize_leaves_customer_attrition_untouched(self) -> None:
        text = "Analysis revealed drivers of customer attrition."
        self.assertEqual(sanitize_submission_tone(text), text)

    def test_sanitize_rewrites_bare_attrition(self) -> None:
        text = "The org saw high attrition that year."
        self.assertIn("staffing constraints", sanitize_submission_tone(text))
        self.assertNotIn("attrition", sanitize_submission_tone(text))


if __name__ == "__main__":
    unittest.main()
