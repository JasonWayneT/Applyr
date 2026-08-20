#!/usr/bin/env python3
"""Offline tests for id-only Stage 0 extraction (clean, harvest, resolve)."""
from __future__ import annotations

import os
import sys
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stage0_extract import (  # noqa: E402
    clean_jd_text,
    harvest_extract_candidates,
    resolve_labeled_buckets,
)


class TestCleanJdText(unittest.TestCase):
    def test_unescapes_html_entities_and_strips_tags(self):
        raw = (
            "Role: &lt;p&gt;Technical Program Manager&lt;/p&gt;\n"
            "&lt;p&gt;5+ years of product management experience in B2B SaaS&lt;/p&gt;"
        )
        cleaned = clean_jd_text(raw)
        self.assertNotIn("&lt;", cleaned)
        self.assertNotIn("<p>", cleaned.lower())
        self.assertIn("5+ years of product management experience in B2B SaaS", cleaned)


class TestHarvestExtractCandidates(unittest.TestCase):
    def test_bullets_get_stable_ids_headers_dropped(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Strong analytical and communication skills

            Preferred
            - Experience with Salesforce or similar CRM platforms
            """
        )
        cands = harvest_extract_candidates(jd)
        texts = [c["text"] for c in cands]
        ids = [c["id"] for c in cands]
        self.assertEqual(ids, list(range(1, len(cands) + 1)))
        self.assertTrue(any("5+ years" in t for t in texts))
        self.assertTrue(any("Salesforce" in t for t in texts))
        self.assertFalse(any(t.lower() in {"requirements", "preferred"} for t in texts))

    def test_mature_header_labels_are_not_candidates(self):
        jd = textwrap.dedent(
            """
            Required Qualifications:
            - 5+ years of product management experience in B2B SaaS

            Minimum Qualifications
            - Strong written communication skills
            """
        )
        texts = [c["text"].lower() for c in harvest_extract_candidates(jd)]
        self.assertFalse(any("required qualifications" in t for t in texts))
        self.assertFalse(any("minimum qualifications" in t for t in texts))
        self.assertTrue(any("5+ years" in t for t in texts))

    def test_requirements_and_preferred_get_section_hints(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Strong analytical and communication skills

            Preferred
            - Experience with Salesforce or similar CRM platforms

            About us
            - We believe barriers were made to be broken
            """
        )
        cands = harvest_extract_candidates(jd)
        by_snip = {c["text"]: c.get("section") for c in cands}
        req = next(t for t in by_snip if "5+ years" in t)
        pref = next(t for t in by_snip if "Salesforce" in t)
        self.assertEqual(by_snip[req], "required")
        self.assertEqual(by_snip[pref], "preferred")
        culture_hits = [s for t, s in by_snip.items() if "barriers" in t]
        if culture_hits:
            self.assertIsNone(culture_hits[0])


    def test_url_line_is_not_a_candidate(self):
        jd = (
            "URL: https://example.com/jobs/12345-product-manager-infrastructure\n"
            "- 5+ years of product management experience in B2B SaaS\n"
        )
        cands = harvest_extract_candidates(jd)
        self.assertTrue(any("5+ years" in c["text"] for c in cands))
        self.assertFalse(any(c["text"].lower().startswith("url:") for c in cands))

    def test_html_entity_jd_still_harvests_requirement_lines(self):
        raw = (
            "&lt;p&gt;Requirements&lt;/p&gt;"
            "&lt;ul&gt;&lt;li&gt;5+ years of product management experience in B2B SaaS"
            "&lt;/li&gt;&lt;li&gt;Strong written communication skills&lt;/li&gt;&lt;/ul&gt;"
        )
        cands = harvest_extract_candidates(raw)
        blob = " | ".join(c["text"] for c in cands)
        self.assertIn("5+ years of product management experience in B2B SaaS", blob)
        self.assertIn("Strong written communication skills", blob)

    def test_long_paragraph_is_split_not_kept_as_one_candidate(self):
        para = (
            "As a Technical Program Manager in Infrastructure, you will drive programs "
            "that span multiple Stripe product areas and partner with engineering "
            "managers across several time zones while reporting to the Head of Infra "
            "and coordinating delivery across payments, billing, and risk workstreams "
            "for the next four planning cycles of the organization. "
            "You will also own quarterly planning and risk reporting for the org "
            "and present status to directors who sit outside the immediate team."
        )
        self.assertGreater(len(para), 400)
        cands = harvest_extract_candidates(para)
        self.assertGreater(len(cands), 1)
        self.assertTrue(all(len(c["text"]) <= 400 for c in cands))

    def test_prose_without_bullets_falls_back_to_sentences(self):
        jd = (
            "We are hiring a Product Manager to own the roadmap. "
            "You need 5+ years of product management experience in B2B SaaS. "
            "Apply with a resume that shows ownership of ambiguous problems."
        )
        cands = harvest_extract_candidates(jd)
        blob = " | ".join(c["text"] for c in cands)
        self.assertIn("5+ years of product management experience", blob)


class TestResolveLabeledBuckets(unittest.TestCase):
    def setUp(self):
        self.cands = [
            {"id": 1, "text": "5+ years of product management experience in B2B SaaS"},
            {"id": 2, "text": "Strong analytical and communication skills"},
            {"id": 3, "text": "Experience with Salesforce or similar CRM platforms"},
        ]

    def test_ids_map_to_original_text(self):
        data = {
            "required": [1, 2],
            "preferred": [3],
            "responsibilities": [],
            "culture": [],
        }
        out = resolve_labeled_buckets(self.cands, data)
        self.assertEqual(out["required"][0], self.cands[0]["text"])
        self.assertEqual(out["preferred"][0], self.cands[2]["text"])

    def test_unknown_ids_and_copied_strings_are_dropped(self):
        data = {
            "required": [1, 99, "10+ years of experience leading a team of engineers"],
            "preferred": ["3"],
            "responsibilities": [],
            "culture": [],
        }
        out = resolve_labeled_buckets(self.cands, data)
        self.assertEqual(out["required"], [self.cands[0]["text"]])
        self.assertEqual(out["preferred"], [self.cands[2]["text"]])
        joined = " ".join(out["required"])
        self.assertNotIn("leading a team", joined)

    def test_duplicate_id_keeps_highest_priority_bucket(self):
        data = {
            "required": [1],
            "preferred": [1],
            "responsibilities": [],
            "culture": [],
        }
        out = resolve_labeled_buckets(self.cands, data)
        self.assertEqual(out["required"], [self.cands[0]["text"]])
        self.assertEqual(out["preferred"], [])

    def test_omitted_ids_fill_from_required_preferred_hints(self):
        cands = [
            {"id": 1, "text": "5+ years of product management experience in B2B SaaS", "section": "required"},
            {"id": 2, "text": "Strong analytical and communication skills", "section": "required"},
            {"id": 3, "text": "Experience with Salesforce or similar CRM platforms", "section": "preferred"},
            {"id": 4, "text": "We believe barriers were made to be broken", "section": None},
        ]
        data = {
            "required": [1],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
        }
        out = resolve_labeled_buckets(cands, data)
        self.assertEqual(out["required"][0], cands[0]["text"])
        self.assertIn(cands[1]["text"], out["required"])
        self.assertEqual(out["preferred"], [cands[2]["text"]])
        self.assertNotIn(cands[3]["text"], out["required"])
        self.assertNotIn(cands[3]["text"], out["culture"])

    def test_model_label_wins_over_section_hint(self):
        cands = [
            {
                "id": 1,
                "text": "Technical degree in Computer Science, Engineering, or a related field.",
                "section": "preferred",
            },
            {
                "id": 2,
                "text": "4+ years of experience or equivalent expertise in technical program management",
                "section": "required",
            },
        ]
        data = {
            "required": [1],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
        }
        out = resolve_labeled_buckets(cands, data)
        self.assertIn(cands[0]["text"], out["required"])
        self.assertIn(cands[1]["text"], out["required"])
        self.assertEqual(out["preferred"], [])



if __name__ == "__main__":
    unittest.main()
