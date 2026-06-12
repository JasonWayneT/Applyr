"""Tests for experience-backed summary themes (FR-224)."""
import unittest

from experience_theme_guard import (
    build_transferable_bridge,
    filter_experience_backed_themes,
    is_theme_experience_backed,
    summary_focus_phrase,
)
from jd_tailoring import JdProfile
from local_draft_stages import build_summary_deterministic


CISION_PIPELINE_CORPUS = (
    "Owned integration between upstream data providers and the platform ingestion layer, "
    "coordinating schema changes across teams to resolve a 40% data failure rate. "
    "Maintained a 7% annual churn rate across 3,500 enterprise accounts on a $40M ARR platform."
)


class TestExperienceThemeGuard(unittest.TestCase):
    def test_analytics_theme_not_backed_by_pipeline_work(self):
        self.assertFalse(
            is_theme_experience_backed(
                "analytics product delivery and adoption",
                CISION_PIPELINE_CORPUS,
            )
        )

    def test_data_and_platform_themes_backed(self):
        self.assertTrue(
            is_theme_experience_backed(
                "data integrity and ingestion",
                CISION_PIPELINE_CORPUS,
            )
        )
        self.assertTrue(
            is_theme_experience_backed(
                "platform reliability and scale",
                CISION_PIPELINE_CORPUS,
            )
        )

    def test_summary_omits_jd_only_analytics(self):
        profile = JdProfile(
            priority_themes=[
                "platform reliability and scale",
                "data integrity and ingestion",
                "analytics product delivery and adoption",
            ]
        )
        bullets = {
            "cision": [CISION_PIPELINE_CORPUS],
        }
        summary = build_summary_deterministic(bullets, "analytics data BI products", profile)
        self.assertNotIn("analytics product delivery", summary.lower())
        self.assertIn("data integrity", summary.lower())

    def test_transferable_bridge_names_jd_emphasis(self):
        themes = [
            "data integrity and ingestion",
            "analytics product delivery and adoption",
        ]
        backed = filter_experience_backed_themes(themes, CISION_PIPELINE_CORPUS)
        bridge = build_transferable_bridge(backed, themes, CISION_PIPELINE_CORPUS)
        self.assertIn("analytics", bridge.lower())
        self.assertIn("data integrity", bridge.lower())

    def test_summary_focus_phrase_excludes_api_without_corpus_signal(self):
        themes = ["API integration and cross-system workflows", "data integrity and ingestion"]
        phrase = summary_focus_phrase(themes, CISION_PIPELINE_CORPUS)
        self.assertIsNotNone(phrase)
        self.assertNotIn("api", phrase.lower())


if __name__ == "__main__":
    unittest.main()
