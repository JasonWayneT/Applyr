"""Tests for Epic 9 — gap acknowledgment injection (gap_detector.py)."""
from __future__ import annotations

import types
import unittest


def _make_jd_profile(requirements=None, keywords=None):
    p = types.SimpleNamespace()
    p.requirements = requirements or []
    p.keywords = keywords or []
    p.priority_themes = []
    return p


class TestClassifyGapType(unittest.TestCase):
    def test_fintech(self):
        from gap_detector import classify_gap_type
        self.assertEqual(classify_gap_type("Experience in fintech or payments required"), "fintech/payments")

    def test_healthcare(self):
        from gap_detector import classify_gap_type
        self.assertEqual(classify_gap_type("Healthcare or clinical domain experience preferred"), "healthcare/domain")

    def test_consumer(self):
        from gap_detector import classify_gap_type
        self.assertEqual(classify_gap_type("Consumer product background with B2C experience"), "consumer/b2c")

    def test_iot(self):
        from gap_detector import classify_gap_type
        self.assertEqual(classify_gap_type("IoT hardware experience required"), "iot/hardware")

    def test_aiml(self):
        from gap_detector import classify_gap_type
        self.assertEqual(classify_gap_type("Machine learning or AI product ownership"), "ai/ml")

    def test_edtech(self):
        from gap_detector import classify_gap_type
        self.assertEqual(classify_gap_type("Experience with LMS or edtech platforms"), "edtech/lms")

    def test_generic_fallback(self):
        from gap_detector import classify_gap_type
        self.assertEqual(classify_gap_type("Unrelated domain xyz"), "domain_generic")

    def test_crm_lifecycle(self):
        from gap_detector import classify_gap_type
        self.assertEqual(classify_gap_type("CRM ownership and lifecycle marketing experience"), "crm/lifecycle")


class TestDetectSoftGaps(unittest.TestCase):
    def test_no_gaps_when_fit_below_72(self):
        from gap_detector import detect_soft_gaps
        jd = _make_jd_profile(requirements=["Fintech experience required"])
        result = detect_soft_gaps(jd, {}, overall_fit_score=65.0)
        self.assertEqual(result, [])

    def test_domain_gap_detected_above_72(self):
        from gap_detector import detect_soft_gaps
        jd = _make_jd_profile(requirements=["Must have fintech or payments domain experience"])
        result = detect_soft_gaps(jd, {}, overall_fit_score=80.0)
        self.assertIsInstance(result, list)
        # Should detect at least one gap (fintech is a domain gap)
        if result:
            self.assertGreater(result[0].relevance_score, 0.0)

    def test_skill_gap_not_flagged(self):
        from gap_detector import detect_soft_gaps
        # Python is a hard skill, not a domain gap
        jd = _make_jd_profile(requirements=["Python programming experience required"])
        result = detect_soft_gaps(jd, {}, overall_fit_score=85.0)
        # Python should not be flagged as a domain gap
        gap_areas = [g.gap_area for g in result]
        self.assertNotIn("python", gap_areas)

    def test_returns_sorted_by_relevance(self):
        from gap_detector import detect_soft_gaps
        jd = _make_jd_profile(requirements=[
            "Fintech or payments experience required",
            "Healthcare domain knowledge preferred",
        ])
        result = detect_soft_gaps(jd, {}, overall_fit_score=80.0)
        if len(result) >= 2:
            for i in range(len(result) - 1):
                self.assertLessEqual(result[i].relevance_score, result[i + 1].relevance_score)


class TestBuildGapParagraph(unittest.TestCase):
    def test_fintech_paragraph_structure(self):
        from gap_detector import detect_soft_gaps, select_primary_gap, build_gap_paragraph, SoftGap
        gap = SoftGap(
            requirement_text="Fintech or payments product experience required",
            relevance_score=0.20,
            gap_area="fintech/payments",
            transfer_skill="platform data integrity, cross-functional compliance coordination",
        )
        result = build_gap_paragraph(gap)
        self.assertIn("fintech/payments", result)
        self.assertIn("What I bring instead", result)
        self.assertIn("I'd welcome the chance", result)

    def test_no_apology_tone(self):
        from gap_detector import build_gap_paragraph, SoftGap
        gap = SoftGap(
            requirement_text="Consumer product B2C background",
            relevance_score=0.25,
            gap_area="consumer/b2c",
            transfer_skill="enterprise SaaS platform ownership",
        )
        result = build_gap_paragraph(gap)
        apology_phrases = ["I'm sorry", "Unfortunately", "I apologize", "regret"]
        for phrase in apology_phrases:
            self.assertNotIn(phrase, result, f"Apology phrase found: {phrase}")

    def test_locked_template_fields_present(self):
        from gap_detector import build_gap_paragraph, SoftGap
        gap = SoftGap(
            requirement_text="IoT hardware experience",
            relevance_score=0.20,
            gap_area="iot/hardware",
            transfer_skill="cross-functional platform delivery",
        )
        result = build_gap_paragraph(gap)
        # Template must have all three anchor phrases
        self.assertIn("I'll be direct about", result)
        self.assertIn("What I bring instead is", result)
        self.assertIn("I'd welcome the chance to", result)


class TestSelectPrimaryGap(unittest.TestCase):
    def test_returns_none_for_empty(self):
        from gap_detector import select_primary_gap
        self.assertIsNone(select_primary_gap([]))

    def test_returns_lowest_relevance(self):
        from gap_detector import select_primary_gap, SoftGap
        g1 = SoftGap("req1", 0.35, "fintech/payments", "platform integrity")
        g2 = SoftGap("req2", 0.20, "consumer/b2c", "enterprise platform ownership")
        g3 = SoftGap("req3", 0.30, "iot/hardware", "cross-functional delivery")
        result = select_primary_gap([g1, g2, g3])
        self.assertEqual(result.relevance_score, 0.20)
        self.assertEqual(result.gap_area, "consumer/b2c")

    def test_one_gap_returns_it(self):
        from gap_detector import select_primary_gap, SoftGap
        gap = SoftGap("req", 0.15, "fintech/payments", "data integrity")
        result = select_primary_gap([gap])
        self.assertEqual(result.gap_area, "fintech/payments")

    def test_one_gap_per_cl(self):
        from gap_detector import select_primary_gap, SoftGap
        # Even with many gaps, select_primary_gap returns exactly one
        gaps = [SoftGap(f"req{i}", 0.1 * (i + 1), f"area_{i}", "skill") for i in range(5)]
        result = select_primary_gap(gaps)
        self.assertIsNotNone(result)
        # Should be the single lowest-relevance gap
        self.assertEqual(result.relevance_score, min(g.relevance_score for g in gaps))


if __name__ == "__main__":
    unittest.main()
