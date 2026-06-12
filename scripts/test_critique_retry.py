"""Tests for CR-042 critique retry and strict gate helpers."""
import os
import unittest

from critique_retry import (
    FIXABLE_CODES,
    apply_critique_fixes,
    extract_failing_codes,
    format_critique_failure,
    has_fixable,
)
from pipeline_env import conversion_retry_max, strict_conversion_critique


class TestCritiqueRetry(unittest.TestCase):
    def test_extract_failing_codes(self):
        issues = [
            "[CW-011] Incomplete summary",
            "[CW-001] advisory only",
            "[CW-014] Theme not backed",
        ]
        codes = extract_failing_codes(issues)
        self.assertEqual(codes, ["CW-011", "CW-014"])

    def test_has_fixable(self):
        self.assertTrue(has_fixable({"pass": False, "issues": ["[CW-013] bad proof"]}))
        self.assertFalse(has_fixable({"pass": True, "issues": []}))

    def test_apply_fixes_theme_skip(self):
        retry_state: dict = {"retry_opts": {}}
        fix = apply_critique_fixes(
            ["CW-014"],
            bullets={"ACC-101": "Led platform roadmap."},
            valid_ids={"ACC-101": "Led platform roadmap."},
            jd_text="analytics platform",
            fallback_bullet_fn=lambda *a, **k: "Fallback.",
            retry_state=retry_state,
            attempt=1,
        )
        self.assertTrue(fix["changed"])
        self.assertEqual(fix["retry_opts"].get("theme_skip"), 1)
        self.assertTrue(fix["rebuild_summary"])

    def test_format_failure_includes_hints(self):
        msg = format_critique_failure(
            {"pass": False, "issues": ["[CW-015] missing payoff"]},
            [{"attempt": 1, "action": "force_attribution_payoff", "codes": ["CW-015"]}],
        )
        self.assertIn("STRICT_CONVERSION_CRITIQUE", msg)
        self.assertIn("CW-015", msg)
        self.assertIn("adoption payoff", msg)

    def test_fixable_codes_set(self):
        self.assertIn("CW-011", FIXABLE_CODES)
        self.assertNotIn("CW-001", FIXABLE_CODES)


class TestPipelineEnvStrict(unittest.TestCase):
    def test_defaults_off(self):
        os.environ.pop("STRICT_CONVERSION_CRITIQUE", None)
        self.assertFalse(strict_conversion_critique())

    def test_strict_on(self):
        os.environ["STRICT_CONVERSION_CRITIQUE"] = "1"
        try:
            self.assertTrue(strict_conversion_critique())
        finally:
            os.environ.pop("STRICT_CONVERSION_CRITIQUE", None)

    def test_retry_max_default(self):
        os.environ.pop("CONVERSION_RETRY_MAX", None)
        self.assertEqual(conversion_retry_max(), 2)


if __name__ == "__main__":
    unittest.main()
