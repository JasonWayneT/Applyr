#!/usr/bin/env python3
"""Regression ratchet for _extract_sections() against the real archived JD
corpus (CR-092, 2026-08-15).

Why this exists: every fix to _extract_sections() so far (CR-086, CR-089,
CR-090, several 2026-08-10/11 batches, and this one) was made against a
single JD that happened to surface a miss, then verified only against that
one JD. A diagnostic sweep of the full data/archive/submissions/ corpus
(401 real JDs at the time) found the same two failure classes recurring at
scale -- 15.5% "starved required bucket" (a real qualifications section
exists but the parser captured 0-1 items from it) and 2.2% "boilerplate
leaked into a bucket" (EEO text, anti-scam paragraphs, ATS page chrome
landing in required/preferred) -- neither of which a single-JD fix could
ever catch regressing.

This does NOT hand-verify "correct" output for every JD in the corpus --
that would require reading and hand-labeling hundreds of real postings,
out of scope for one session. Instead it's a ratchet: record today's
post-fix counts as a ceiling, and fail loudly if a future change makes
either count go back up. Combined with the specific locked-in assertions
below (the 3 confirmed Greenhouse-footer cases), this turns "the same bug
recurs one company at a time" into "a regression here is caught immediately,
against the full known-bad set, not just whichever JD prompted the fix."

Reads directly from data/archive/submissions/ rather than duplicating JD
text into a fixtures/ copy -- that folder is real, private application data
(gitignored) and is already the durable, existing home for this corpus;
copying it would both proliferate PII and require manually re-syncing two
copies as the archive grows. Skips (does not fail) if that directory isn't
present, since it's private data that may not exist in every environment.
"""
from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_stage0_fit_gate import _extract_sections, _parse_url_and_jd, _strip_ats_chrome

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ARCHIVE = os.path.join(_REPO_ROOT, "data", "archive", "submissions")

# Ratchet ceiling: today's post-fix counts (2026-08-15, after the ATS-chrome
# pre-pass landed). A future change may bring these DOWN (great) but must
# never push them back UP without a deliberate, reviewed change to this file.
_MAX_STARVED = 65
_MAX_BOILERPLATE = 8

_REQUIREMENTS_SIGNAL_RE = re.compile(
    r"\b(required qualifications|qualifications|requirements|skills you.?ll need|"
    r"what you.?ll need|minimum qualifications|basic qualifications|must have|"
    r"years of experience|years.? experience)\b",
    re.I,
)

_BOILERPLATE_SIGNATURES = [
    (r"equal opportunity employer", "EEO boilerplate"),
    (r"without regard to race", "EEO boilerplate"),
    (r"reasonable accommodation", "ADA/accommodation boilerplate"),
    (r"will never solicit money|will never ask for (?:your )?(?:bank|credit card|social security)", "anti-scam warning"),
    (r"do not communicate with candidates via", "anti-scam warning"),
    (r"beware of (?:recruitment|recruiting|job) (?:scams|fraud)", "anti-scam warning"),
    (r"e-verify", "E-Verify boilerplate"),
    (r"background check", "background-check boilerplate"),
    (r"\xa9\s*\d{4}|all rights reserved", "copyright boilerplate"),
    (r"privacy (?:policy|notice)", "privacy-policy boilerplate"),
    (r"apply (?:now|today)!*$", "apply-now CTA"),
    (r"join (?:us|the team) (?:at|today)", "marketing CTA"),
]
_BOILERPLATE_RES = [(re.compile(p, re.I), label) for p, label in _BOILERPLATE_SIGNATURES]


def _classify_jd(text: str) -> dict:
    url, jd = _parse_url_and_jd(text)
    jd = _strip_ats_chrome(jd)
    buckets = _extract_sections(jd)
    required = buckets.get("required", [])

    starved = len(required) <= 1 and bool(_REQUIREMENTS_SIGNAL_RE.search(jd))

    boilerplate_hits = []
    for bucket_name in ("required", "preferred", "responsibilities"):
        for item in buckets.get(bucket_name, []):
            for pat, label in _BOILERPLATE_RES:
                if pat.search(item):
                    boilerplate_hits.append((bucket_name, label, item[:90]))
                    break

    return {"starved": starved, "boilerplate_hits": boilerplate_hits}


def _sweep_corpus() -> tuple[int, int, list[str], dict[str, list]]:
    """Returns (starved_count, boilerplate_count, boilerplate_slugs, details)."""
    starved_count = 0
    boilerplate_count = 0
    boilerplate_slugs: list[str] = []
    details: dict[str, list] = {}

    for name in sorted(os.listdir(_ARCHIVE)):
        folder = os.path.join(_ARCHIVE, name)
        jd_path = os.path.join(folder, "Original_JD.txt")
        if not os.path.isfile(jd_path):
            continue
        try:
            with open(jd_path, encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue
        if not text.strip():
            continue
        result = _classify_jd(text)
        if result["starved"]:
            starved_count += 1
        if result["boilerplate_hits"]:
            boilerplate_count += 1
            boilerplate_slugs.append(name)
            details[name] = result["boilerplate_hits"]

    return starved_count, boilerplate_count, boilerplate_slugs, details


@unittest.skipUnless(
    os.path.isdir(_ARCHIVE) and any(
        os.path.isfile(os.path.join(_ARCHIVE, n, "Original_JD.txt"))
        for n in os.listdir(_ARCHIVE)
    ) if os.path.isdir(_ARCHIVE) else False,
    "data/archive/submissions/ not present in this environment (private data) -- skipping corpus ratchet",
)
class TestExtractionCorpusRatchet(unittest.TestCase):
    """Not exhaustive ground truth -- a ratchet against real-world regression.
    See module docstring for why this shape was chosen over hand-labeling."""

    @classmethod
    def setUpClass(cls):
        cls.starved_count, cls.boilerplate_count, cls.boilerplate_slugs, cls.details = _sweep_corpus()

    def test_starved_required_bucket_does_not_regress(self):
        self.assertLessEqual(
            self.starved_count, _MAX_STARVED,
            f"starved-required-bucket count rose to {self.starved_count} "
            f"(ceiling {_MAX_STARVED}) -- a change made _extract_sections() "
            f"worse at finding real qualifications sections, not better."
        )

    def test_boilerplate_leak_does_not_regress(self):
        self.assertLessEqual(
            self.boilerplate_count, _MAX_BOILERPLATE,
            f"boilerplate-leaked-into-a-bucket count rose to {self.boilerplate_count} "
            f"(ceiling {_MAX_BOILERPLATE}) -- details: {self.details}"
        )

    def test_confirmed_greenhouse_footer_cases_stay_fixed(self):
        """The 3 real cases that motivated _strip_ats_chrome() (CR-092) --
        locked in specifically, not just covered by the aggregate ceiling
        above, so a regression here fails with a precise, named cause."""
        for slug in ("altimate", "factory", "yeet"):
            folder = os.path.join(_ARCHIVE, slug)
            if not os.path.isfile(os.path.join(folder, "Original_JD.txt")):
                continue  # archive contents can change; not fatal if renamed/removed
            self.assertNotIn(
                slug, self.boilerplate_slugs,
                f"{slug} regressed -- the Greenhouse page-chrome footer is leaking "
                f"into a bucket again, _strip_ats_chrome() may have broken."
            )


if __name__ == "__main__":
    unittest.main()
