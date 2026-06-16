"""Tests for deterministic summary builder hardening (CR-049 / FR-241)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from local_draft_stages import build_summary_deterministic, dedupe_metric_collision_bullets
from resume_conversion_eval import (
    evaluate_resume_conversion,
    is_incomplete_summary_sentence,
    _summary_sentences,
    _summary_text,
)


DIGNIFI_BULLETS = {
    "cision": [
        (
            "Owned integration between upstream data providers and the platform ingestion layer, "
            "coordinating schema changes across teams to resolve a 40% data failure rate at the source boundary."
        ),
        (
            "Identified and drove a critical cross-functional data remediation initiative, aligning "
            "engineering and database administration to permanently resolve a 40% data ingestion failure."
        ),
        (
            "Rebuilt a B2B PR attribution feature that let customers trace content placements to revenue "
            "outcomes, producing a version reliable enough that other internal platform teams sought to adopt it."
        ),
        (
            "Replaced reactive sprint planning with a rigorous capacity model using T-shirt sizing and "
            "uncertainty bands, managing resource allocations across stability, compliance, and roadmap items."
        ),
    ],
    "sterkly": [
        "Partnered closely with a dedicated team of 5-8 developers to ensure accurate, on-time delivery.",
    ],
    "zero_to_sixty": [
        "Managed a fulfillment program governing $288,000 in vendor contracts, generating $8,500 per quarter in savings.",
    ],
}


class TestSummaryBuilder(unittest.TestCase):
    def test_no_incomplete_attribution_proof(self):
        summary = build_summary_deterministic(
            DIGNIFI_BULLETS,
            "Product Manager role focused on data integrity and platform reliability.",
            profile=None,
        )
        for sent in _summary_sentences(summary):
            self.assertFalse(
                is_incomplete_summary_sentence(sent),
                f"Incomplete summary sentence: {sent}",
            )
        self.assertNotIn("platform teams.", summary.split("sought to adopt")[0])

    def test_at_most_one_proof_sentence(self):
        summary = build_summary_deterministic(
            DIGNIFI_BULLETS,
            "analytics product adoption and data integrity",
            profile=None,
        )
        sents = _summary_sentences(summary)
        self.assertLessEqual(len(sents), 3)
        proof_sents = sents[2:]
        self.assertLessEqual(len(proof_sents), 1)

    def test_summary_has_min_three_sentences_without_proof(self):
        bullets = {
            "cision": [
                "Replaced reactive sprint planning with a capacity model using T-shirt sizing.",
            ],
            "sterkly": ["Partnered with developers on delivery."],
            "zero_to_sixty": ["Managed vendor contracts with measurable savings."],
        }
        summary = build_summary_deterministic(
            bullets,
            "platform reliability and sprint planning",
            profile=None,
        )
        self.assertGreaterEqual(len(_summary_sentences(summary)), 3)

    def test_metric_dedupe_drops_second_40pct_story(self):
        bullets = {
            "ACC-102-A": DIGNIFI_BULLETS["cision"][0],
            "ACC-102-B": DIGNIFI_BULLETS["cision"][1],
            "ACC-113": DIGNIFI_BULLETS["cision"][2],
        }
        valid = dict(bullets)
        out = dedupe_metric_collision_bullets(bullets, valid, jd_text="data integrity 40%")
        self.assertEqual(len(out), 2)
        joined = " ".join(out.values()).lower()
        self.assertEqual(joined.count("40%"), 1)

    def test_summary_avoids_capacity_model_dup(self):
        bullets_by_company = {
            "cision": DIGNIFI_BULLETS["cision"],
            "sterkly": DIGNIFI_BULLETS["sterkly"],
            "zero_to_sixty": DIGNIFI_BULLETS["zero_to_sixty"],
        }
        summary = build_summary_deterministic(
            bullets_by_company,
            "cross-functional stakeholder alignment and capacity planning",
            profile=None,
        )
        cap = "Replaced reactive sprint planning with a capacity model"
        self.assertNotIn(cap, summary)


class TestDignifiRegression(unittest.TestCase):
    def test_sample_resume_md_passes_conversion(self):
        summary = build_summary_deterministic(
            DIGNIFI_BULLETS,
            "data integrity and cross-functional stakeholder alignment",
            profile=None,
        )
        resume = f"""# JOHN DOE

## PROFESSIONAL SUMMARY
{summary}

## PROFESSIONAL EXPERIENCE

### Product Manager | Cision | September 2021 - January 2026
Remote

* {DIGNIFI_BULLETS['cision'][2]}
* {DIGNIFI_BULLETS['cision'][3]}

## EDUCATION

* **Bachelor** , University, 2019
"""
        critique = evaluate_resume_conversion(resume)
        hard = [i for i in critique["issues"] if "[CW-011]" in i or "[CW-013]" in i]
        self.assertEqual(hard, [], critique["issues"])


if __name__ == "__main__":
    unittest.main()
