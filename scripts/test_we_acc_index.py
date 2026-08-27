"""Tests for scripts/we_acc_index.py (CR-094)."""
from __future__ import annotations

import os
import sys
import textwrap
import unittest

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import we_acc_index as wai


_WE = textwrap.dedent("""
    * **[ACC-154] Not owned:** import into the next-gen platform.

    * **[ACC-173] Cold-Storage Tiering Discussion — Considered, Not Implemented**: talk only.

    * **[ACC-172] Docker — personal only, not professional**: personal use.

    * **[ACC-101] Platform Stabilization**: Mitigated indexing crashes with storage monitoring.

    * **[ACC-122] What Jason drove:** Proactive storage monitoring and alerting.

    * **[ACC-123] Attribution:** **OWNED** — Jason owned the monitoring work.

    * **[ACC-124] DO NOT CLAIM:** sole causation of a company-wide reliability program.

    * **[ACC-119] Tools Used**: Confluence, Pendo, Productboard.

    * **[ACC-102] Data Remediation**: Drove centralized platform data remediation.

    * **[ACC-125] Attribution:** **CONTRIBUTED** — partnered with engineering.

    * **[ACC-126] DO NOT CLAIM:** owning the ETL platform.

    * **[ACC-169] Hands-On AWS S3**: Used S3 for a legacy content ingestion path.
""").strip()


class ClassifyWeAccTests(unittest.TestCase):
    def test_classifies_story_attribution_dnc_and_tools(self):
        classes = wai.classify_we_acc_ids(_WE)
        self.assertEqual(classes["ACC-101"], wai.CLASS_STORY)
        self.assertEqual(classes["ACC-102"], wai.CLASS_STORY)
        self.assertEqual(classes["ACC-169"], wai.CLASS_STORY)
        self.assertEqual(classes["ACC-122"], wai.CLASS_SUBSTORY)
        self.assertEqual(classes["ACC-154"], wai.CLASS_NONCLAIMABLE)
        self.assertEqual(classes["ACC-173"], wai.CLASS_NONCLAIMABLE)
        self.assertEqual(classes["ACC-172"], wai.CLASS_NONCLAIMABLE)
        self.assertEqual(classes["ACC-123"], wai.CLASS_ATTRIBUTION)
        self.assertEqual(classes["ACC-125"], wai.CLASS_ATTRIBUTION)
        self.assertEqual(classes["ACC-124"], wai.CLASS_DO_NOT_CLAIM)
        self.assertEqual(classes["ACC-126"], wai.CLASS_DO_NOT_CLAIM)
        self.assertEqual(classes["ACC-119"], wai.CLASS_TOOLS)

    def test_indexable_ids_are_stories_only(self):
        self.assertEqual(
            wai.indexable_project_ids(_WE),
            {"ACC-101", "ACC-102", "ACC-169"},
        )


class HedgeExtractionTests(unittest.TestCase):
    def test_hedges_attach_to_preceding_story(self):
        h101 = wai.hedges_for_project(_WE, "ACC-101")
        self.assertEqual(h101["attribution"], "OWNED")
        self.assertTrue(
            any("sole causation" in p.lower() for p in h101["prohibited_claims"])
        )

        h102 = wai.hedges_for_project(_WE, "ACC-102")
        self.assertEqual(h102["attribution"], "CONTRIBUTED")
        self.assertTrue(
            any("etl" in p.lower() for p in h102["prohibited_claims"])
        )

    def test_unknown_project_returns_empty_hedges(self):
        empty = wai.hedges_for_project(_WE, "ACC-999")
        self.assertEqual(empty["attribution"], "")
        self.assertEqual(empty["prohibited_claims"], [])


if __name__ == "__main__":
    unittest.main()
