#!/usr/bin/env python3
"""Tests for scripts/stage0_prefs_gate.py, focused on _check_required_language.

Found 2026-09-19 on binance (Data Product Manager, Derivatives): the JD stated
"Bilingual English/Mandarin required to coordinate with overseas partners."
Stage 0's LLM evidence classifier downgraded this to gap_class SOFT, reasoning
that Jason's experience coordinating with distributed teams IN ENGLISH
demonstrated "the underlying cross-geographic coordination capability" --
a different skill that does not address actual language fluency. Jason
confirmed directly: no Mandarin, "a little Spanish and English." A factual,
binary question (does the candidate speak this language) should not be left
to an LLM's soft/hard judgment call, same reasoning as the existing
deterministic travel/years/title gates.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stage0_prefs_gate import _check_required_language, run_prefs_gate


class TestRequiredLanguageGate(unittest.TestCase):
    def test_bilingual_mandarin_required_hard_rejects(self) -> None:
        jd = (
            "Bilingual English/Mandarin required to coordinate with "
            "overseas partners and stakeholders."
        )
        rejects, flags = _check_required_language(jd)
        self.assertEqual(len(rejects), 1)
        self.assertEqual(rejects[0]["code"], "required_language_unmet")
        self.assertIn("Mandarin", rejects[0]["reason"])
        self.assertEqual(flags, [])

    def test_real_binance_jd_text_hard_rejects(self) -> None:
        # The exact live JD line that produced the miss.
        jd = (
            "Requirements\n\n2+ years in product management...\n"
            "Bilingual English/Mandarin required to coordinate with overseas "
            "partners and stakeholders."
        )
        rejects, _ = _check_required_language(jd)
        self.assertTrue(any(r["code"] == "required_language_unmet" for r in rejects))

    def test_fluent_in_french_required_hard_rejects(self) -> None:
        jd = "Fluent in French is required for this role."
        rejects, flags = _check_required_language(jd)
        self.assertEqual(len(rejects), 1)
        self.assertIn("French", rejects[0]["reason"])

    def test_native_japanese_speaker_required_hard_rejects(self) -> None:
        jd = "Native Japanese speaker required to support our Tokyo office."
        rejects, _ = _check_required_language(jd)
        self.assertEqual(len(rejects), 1)
        self.assertIn("Japanese", rejects[0]["reason"])

    def test_spanish_required_is_a_soft_flag_not_a_reject(self) -> None:
        # Jason has some Spanish -- a genuine partial case, not a clean hard
        # reject like a language he has zero of. Needs a human check.
        jd = "Spanish fluency is required to support LATAM accounts."
        rejects, flags = _check_required_language(jd)
        self.assertEqual(rejects, [])
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["code"], "required_language_partial")

    def test_english_required_is_not_flagged(self) -> None:
        jd = "Fluent in English is required to communicate with US stakeholders."
        rejects, flags = _check_required_language(jd)
        self.assertEqual(rejects, [])
        self.assertEqual(flags, [])

    def test_preferred_language_is_not_flagged(self) -> None:
        # "Preferred"/"a plus" framing is a legitimate soft gap the existing
        # evidence cascade can reason about -- this gate only fires on
        # required/must/fluent framing, not preference language.
        jd = "Mandarin language skills are a plus but not required."
        rejects, flags = _check_required_language(jd)
        self.assertEqual(rejects, [])
        self.assertEqual(flags, [])

    def test_domain_fluency_is_not_flagged(self) -> None:
        # Real false positive found live on indigo's queued JD: an earlier
        # version of this gate matched any word after "fluent in", not just a
        # language name.
        jd = (
            "At the one-inch level, you'll become deeply fluent in legal and "
            "medical workflows, dogfood the product, work directly with "
            "customers, and uncover the friction others miss."
        )
        rejects, flags = _check_required_language(jd)
        self.assertEqual(rejects, [])
        self.assertEqual(flags, [])

    def test_no_jd_text_returns_empty(self) -> None:
        self.assertEqual(_check_required_language(""), ([], []))
        self.assertEqual(_check_required_language(None), ([], []))

    def test_duplicate_mentions_do_not_duplicate_findings(self) -> None:
        jd = (
            "Fluent in Mandarin is required. Later in the posting: "
            "Bilingual English/Mandarin required for client calls."
        )
        rejects, _ = _check_required_language(jd)
        self.assertEqual(len(rejects), 1)

    def test_run_prefs_gate_surfaces_required_language_reject(self) -> None:
        jd = (
            "We build derivatives products.\n"
            "Bilingual English/Mandarin required to coordinate with overseas "
            "partners and stakeholders."
        )
        result = run_prefs_gate("Binance", jd, prefs={})
        self.assertFalse(result["passed"])
        self.assertTrue(
            any(r["code"] == "required_language_unmet" for r in result["rejects"])
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
