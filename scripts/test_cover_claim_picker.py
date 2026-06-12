"""Tests for cover proof selection (CR-024 / picker hardening)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from claim_catalog import load_catalog
from cover_claim_picker import dedupe_cover_proofs, is_marketplace_fintech_jd, pick_cover_proofs
from cover_jd_needs import extract_ranked_needs
from cover_letter_plan import CoverProofSlot
from jd_tailoring import build_jd_profile_deterministic, extract_jd_pain_points


SPLASH_JD_SNIPPET = """
The Role
Own lender integrations and consumer funnel optimization for Splash's personal loan product:
scope and launch lender integrations, improve borrower-lender matching and offer experience,
run A/B tests and funnel experiments, partner with engineering and data science.
WHAT YOU'LL DO AT SPLASH:
Run experiments and funnel optimizations, partnering with design on research and A/B testing
to improve conversion.
"""


class TestCoverClaimPicker(unittest.TestCase):
    def test_dedupe_cover_proofs(self):
        slot = CoverProofSlot("ACC-101-PM", "product", "need", "cision", "ACC-101")
        out = dedupe_cover_proofs([slot, slot])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].claim_id, "ACC-101-PM")

    def test_pick_cover_proofs_k3_has_unique_claim_ids(self):
        catalog = load_catalog()
        profile = build_jd_profile_deterministic(SPLASH_JD_SNIPPET)
        needs = extract_ranked_needs(SPLASH_JD_SNIPPET, profile)
        proofs = pick_cover_proofs(catalog, needs, profile, SPLASH_JD_SNIPPET, k=3)
        claim_ids = [p.claim_id for p in proofs]
        self.assertEqual(len(claim_ids), len(set(claim_ids)))
        self.assertGreaterEqual(len(proofs), 2)

    def test_fintech_jd_prefers_dropoff_story(self):
        catalog = load_catalog()
        profile = build_jd_profile_deterministic(SPLASH_JD_SNIPPET)
        needs = extract_ranked_needs(SPLASH_JD_SNIPPET, profile)
        proofs = pick_cover_proofs(catalog, needs, profile, SPLASH_JD_SNIPPET, k=3)
        claim_ids = {p.claim_id for p in proofs}
        self.assertIn("ACC-102-BUS", claim_ids)

    def test_underwriting_alone_is_not_marketplace_fintech(self):
        jd = "Own analytics products for underwriting and sales teams. Drive platform adoption."
        self.assertFalse(is_marketplace_fintech_jd("", jd))

    def test_industry_tag_footer_is_not_marketplace_fintech(self):
        jd = (
            "Ship analytics products that get adopted, not just demoed.\n"
            "Artificial Intelligence • Fintech • Software • Financial Services"
        )
        self.assertFalse(is_marketplace_fintech_jd("", jd))

    def test_pain_points_capture_fintech_signals(self):
        pains = extract_jd_pain_points(SPLASH_JD_SNIPPET)
        joined = " ".join(pains).lower()
        self.assertTrue(
            "borrower" in joined or "funnel" in joined or "lender" in joined,
            f"expected fintech pain point, got {pains}",
        )


if __name__ == "__main__":
    unittest.main()
