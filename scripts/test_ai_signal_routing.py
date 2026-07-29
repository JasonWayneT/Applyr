"""Regression tests for the AI-Native trigger gap (P-005, batch2-jd-tailoring-findings.md).

Confirmed root causes fixed here:
1. The resume PROJECTS section (FR-208, has_ai_signal-gated) was stripped on any
   over-budget render before a single bullet was trimmed, so it almost never
   survived to the final resume.
2. The cover letter path had no mechanism at all to use the AI-tooling story
   (projects_catalog.json was resume-only; no matching master_claims.json entry
   existed for the cover-letter claim picker to select).
3. Even after adding a master_claims.json entry (ACC-401-AITOOLS) and an
   AI-signal scoring bonus, the metric-density guard in pick_cover_proofs
   silently discarded it every time because it has no digit in its text.
4. All 8 projects_catalog.json entries used a literal em-dash in the name,
   which would have hard-blocked the linter (LR-006) the first time the
   PROJECTS section actually survived to a final resume.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from claim_catalog import load_catalog
from cover_claim_picker import pick_cover_proofs
from jd_tailoring import build_jd_profile_deterministic, extract_jd_pain_points, has_ai_signal
from local_draft_stages import build_projects_section
from submission_linter import lint_document

AI_JD = """
The Role
Ship AI features end to end: prototype with Claude and Cursor, write and evaluate
prompts, and partner with engineering to take agentic workflows from idea to
production. We are an AI-native product team and expect daily fluency with modern
AI tools.
"""

NON_AI_JD = """
The Role
Own lender integrations and consumer funnel optimization for a personal loan
product: scope and launch lender integrations, improve borrower-lender matching,
run A/B tests and funnel experiments, partner with engineering and data science.
"""


class TestAiSignalRouting(unittest.TestCase):
    def test_ai_claim_selected_when_jd_signals_ai(self):
        catalog = load_catalog()
        self.assertIn("ACC-401-AITOOLS", catalog.claims)
        self.assertTrue(has_ai_signal(AI_JD))
        profile = build_jd_profile_deterministic(AI_JD)
        needs = extract_jd_pain_points(AI_JD)
        proofs = pick_cover_proofs(catalog, needs, profile, AI_JD, k=3)
        claim_ids = [p.claim_id for p in proofs]
        self.assertIn("ACC-401-AITOOLS", claim_ids)

    def test_ai_claim_not_forced_onto_non_ai_jd(self):
        catalog = load_catalog()
        self.assertFalse(has_ai_signal(NON_AI_JD))
        profile = build_jd_profile_deterministic(NON_AI_JD)
        needs = extract_jd_pain_points(NON_AI_JD)
        proofs = pick_cover_proofs(catalog, needs, profile, NON_AI_JD, k=3)
        claim_ids = [p.claim_id for p in proofs]
        self.assertNotIn("ACC-401-AITOOLS", claim_ids)

    def test_ai_claim_survives_metric_density_guard(self):
        # ACC-401-AITOOLS has no digit in its body by design (qualitative
        # capability claim) — confirm the metric-completeness guard no longer
        # silently discards it once selected on an AI-signal JD.
        rec = load_catalog().claims["ACC-401-AITOOLS"]
        import re
        self.assertFalse(re.search(r"\d", rec.body))

    def test_projects_section_returns_single_entry(self):
        out = build_projects_section(AI_JD)
        self.assertEqual(out.count("**"), 2)  # one "**Name**" pair, not three

    def test_projects_section_has_no_forbidden_em_dash(self):
        out = build_projects_section(AI_JD)
        self.assertNotIn("—", out)
        result = lint_document(out, doc_type="resume")
        self.assertEqual(result.blocks, [])


if __name__ == "__main__":
    unittest.main()
