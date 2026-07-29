"""Unit tests for JD completeness helpers in batch_pipeline."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from batch_pipeline import (
    _effective_jd_body,
    get_min_jd_chars_evaluate,
    _jd_meets_evaluate_threshold,
)


class TestJdCompleteness(unittest.TestCase):
    def test_effective_jd_body_strips_headers(self):
        raw = "Title: PM\nURL: https://example.com\n\nFull job description body here."
        body = _effective_jd_body(raw)
        self.assertIn("Full job description", body)
        self.assertNotIn("Title:", body)

    def test_min_jd_default(self):
        self.assertEqual(get_min_jd_chars_evaluate({}), 800)

    def test_meets_threshold(self):
        jd = "Title: PM\n\n" + ("x" * 850)
        self.assertTrue(_jd_meets_evaluate_threshold(jd, {"min_jd_chars_evaluate": 800}))

    def test_below_threshold(self):
        jd = "Title: PM\n\nshort"
        self.assertFalse(_jd_meets_evaluate_threshold(jd, {"min_jd_chars_evaluate": 800}))


if __name__ == "__main__":
    unittest.main()
