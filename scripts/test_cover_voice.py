"""Tests for CR-043/044 deterministic cover voice."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cover_phrasing import (
    BANNED_ROBOT_PHRASES,
    WORD_MAX,
    WORD_MIN,
    apply_voice_polish,
    audit_need_fragment,
    jd_presence_clause,
    render_forward_close,
    render_structured_close,
    strip_opener_hook_from_body,
    value_lead_from_story,
)
from cover_narrative_templates import render_proof_paragraph, render_value_first_opening
from claim_catalog import ClaimCatalog, ClaimRecord
from cover_letter_plan import CoverProofSlot


RETENTION_STORY = (
    "After a shelved corporate migration left the flagship platform in retention mode, "
    "churn reports and customer-facing teams became my prioritization input, not optional context. "
    "I used VOC, CX escalations, and renewal risk to decide what engineering shipped next "
    "alongside stability work. Retention held near 7% annually through progressive resource "
    "constraints and sustained incident response because customers could see the platform "
    "was being stewarded, not abandoned."
)


class TestCoverPhrasing(unittest.TestCase):
    def test_word_band_constants(self):
        self.assertEqual(WORD_MIN, 300)
        self.assertEqual(WORD_MAX, 400)

    def test_strips_robot_bridge(self):
        raw = (
            "After a shelved migration I kept customers successful. "
            "That experience is directly relevant to Acme's focus on platform scale."
        )
        out = apply_voice_polish(raw)
        for phrase in BANNED_ROBOT_PHRASES:
            self.assertNotIn(phrase, out)

    def test_audit_fragment_non_empty(self):
        need = (
            "5+ years of product management experience, with at least 2 years "
            "owning analytics, data, BI, or ML/AI products"
        )
        frag = audit_need_fragment(need)
        self.assertGreaterEqual(len(frag), 20)
        self.assertNotIn("with at.", frag)
        self.assertIn("5+ years", frag)

    def test_tenure_not_recited_in_opener(self):
        need = (
            "5+ years of product management experience, with at least 2 years "
            "owning analytics, data, BI, or ML/AI products"
        )
        self.assertEqual(jd_presence_clause(need), "")

    def test_value_lead_is_first_sentence_only(self):
        lead = value_lead_from_story(RETENTION_STORY)
        self.assertIn("shelved", lead.lower())
        self.assertNotIn("7%", lead)

    def test_value_first_opening_no_credential_stack(self):
        opener = render_value_first_opening(
            "CVS Health",
            "Product Manager",
            RETENTION_STORY,
            "analytics products adopted not demoed",
        )
        self.assertIn("drew me to the", opener)
        self.assertNotIn("I bring 5+ years", opener)
        self.assertNotIn("your posting emphasizes", opener.lower())
        self.assertNotIn("track record in platform", opener.lower())

    def test_forward_close_names_business_problem(self):
        jd = (
            "What You'll Do\n"
            "Ship analytics products that get adopted, not just demoed for sales teams."
        )
        c = render_forward_close("CVS Health", jd)
        self.assertIn("welcome a conversation", c.lower())
        self.assertIn("adopt", c.lower())
        self.assertNotIn("priorities in your posting", c.lower())


class TestStructuredClose(unittest.TestCase):
    def test_no_circular_outcome_with_generic_fallback(self):
        """When no JD-specific outcomes are found, close must not say 'the product outcomes
        that drive measurable product outcomes'."""
        jd = (
            "Product Manager\n"
            "What You'll Do\n"
            "- Own roadmap prioritization and stakeholder alignment.\n"
            "- Improve roadmap clarity and cross-functional delivery.\n"
        )
        close = render_structured_close("HiBob", jd)
        self.assertNotIn(
            "product outcomes that drive measurable product outcomes",
            close.lower(),
            "Circular 'product outcomes that drive measurable product outcomes' in close",
        )
        self.assertIn("hibob", close.lower())

    def test_no_circular_outcome_when_target_equals_outcome(self):
        """When a target and an outcome are the same phrase, the close must not repeat it
        (e.g., 'improve product adoption … drive product adoption')."""
        jd = (
            "Product Manager\n"
            "What You'll Do\n"
            "- Drive product adoption across the platform.\n"
            "- Improve product adoption metrics and KPIs.\n"
        )
        close = render_structured_close("OXIO", jd)
        # "product adoption" may appear once (as the target), but not in both target and outcome
        self.assertNotIn(
            "product outcomes that drive product adoption",
            close.lower(),
            "Target-equals-outcome circularity in close",
        )
        self.assertIn("oxio", close.lower())

    def test_specific_jd_outcomes_still_rendered(self):
        """When the JD has specific outcome signals (funnel conversion, funded volume),
        the 'the product outcomes that drive …' pattern should still appear."""
        jd = (
            "Product Manager — Lending Marketplace\n"
            "What You'll Do\n"
            "- Own lender integration quality and funnel conversion.\n"
            "- Drive funded volume growth through borrower-lender matching.\n"
        )
        close = render_structured_close("Splash Financial", jd, archetype_id="marketplace_fintech")
        self.assertIn("funnel conversion", close.lower())
        self.assertIn("funded volume", close.lower())
        self.assertIn("the product outcomes that drive", close.lower())

    def test_dedupes_overlapping_jd_targets_in_close(self):
        """Analytics product adoption + product adoption should not both appear."""
        jd = (
            "CVS Health\n"
            "Product Manager\n"
            "What You'll Do\n"
            "- Own analytics product delivery and product adoption across teams.\n"
            "- Improve analytics product adoption metrics and KPIs.\n"
        )
        close = render_structured_close("CVS Health", jd)
        self.assertNotIn(
            "strengthen product adoption",
            close.lower(),
            "Redundant overlapping targets in close",
        )
        self.assertIn("analytics product adoption", close.lower())


class TestCoverPhrasePolish(unittest.TestCase):
    def test_documentation_phrase_not_ungrammatical(self):
        raw = (
            "The B2B PR attribution tool had no surviving documentation and was "
            "becoming unstable during the migration."
        )
        out = apply_voice_polish(raw)
        self.assertNotIn("had no documentation remained", out.lower())
        self.assertIn("had no documentation left", out.lower())


class TestOpenerHookDedup(unittest.TestCase):
    def test_strip_hook_after_em_dash_normalization(self):
        story = (
            "Customers told us the contact data was wrong—that was a failure. "
            "I eliminated the 40% drop-off."
        )
        hook = value_lead_from_story(story)
        body = apply_voice_polish(story)
        stripped = strip_opener_hook_from_body(body, hook)
        self.assertNotIn("Customers told us", stripped.split(".")[0])
        self.assertIn("40%", stripped)


class TestProofParagraphNoBridge(unittest.TestCase):
    def test_cover_story_only(self):
        cat = ClaimCatalog()
        cat.claims["ACC-101-RETENTION"] = ClaimRecord(
            claim_id="ACC-101-RETENTION",
            title="retention",
            body="Maintained 7% churn.",
            employer="cision",
            cover_story=(
                "After a shelved corporate migration I used VOC to prioritize engineering. "
                "Retention held near 7% annually."
            ),
        )
        slot = CoverProofSlot(
            claim_id="ACC-101-RETENTION",
            lens="retention",
            jd_need="analytics product delivery",
            employer="cision",
            project_id="ACC-101",
        )
        para = render_proof_paragraph(slot, cat, "CVS Health")
        self.assertIn("7%", para)
        self.assertNotIn("That experience is directly relevant", para)


if __name__ == "__main__":
    unittest.main()
