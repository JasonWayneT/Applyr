"""Tests for fleet bullet word-budget enforcement (CR-048)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bullet_fit import enforce_bullet_word_budget


class TestEnforceBulletWordBudget(unittest.TestCase):
    def test_long_catalog_line_is_fitted_or_metric_preserved(self):
        source = (
            "Owned the integration between upstream data providers and the platform "
            "ingestion layer, coordinating cross-team schema changes that resolved a "
            "40% data failure rate before records entered the core platform."
        )
        bullets = {"ACC-102-INT": source}
        valid_ids = {"ACC-102-INT": source}
        out = enforce_bullet_word_budget(bullets, valid_ids, max_words=28)
        self.assertIn("40%", out["ACC-102-INT"])
        # Prefer fit; keep long source only when fit would drop grounded metrics.
        self.assertTrue(
            len(out["ACC-102-INT"].split()) <= 28 or out["ACC-102-INT"] == source
        )

    def test_keeps_long_bullet_when_fit_would_drop_metrics(self):
        source = (
            "Owned the integration between upstream data providers and the platform "
            "ingestion layer, coordinating cross-team schema changes that resolved a "
            "40% data failure rate before records entered the core platform."
        )
        bullets = {"ACC-102-INT": source}
        valid_ids = {"ACC-102-INT": source}
        out = enforce_bullet_word_budget(bullets, valid_ids, max_words=12)
        self.assertIn("40%", out["ACC-102-INT"])


if __name__ == "__main__":
    unittest.main()
