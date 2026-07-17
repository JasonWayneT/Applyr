import os
import tempfile

from fit_judgment_io import write_equivalence_judgment
from structured_fit import (
    _heuristic_judgments,
    compute_fit_report,
    evaluate_structured_fit,
    extract_must_haves,
)

JD_TEXT = "Senior Product Manager, B2B SaaS platform. Requirements: 5+ years PM experience, roadmap ownership, cross-functional delivery."
WORK_EXP = "Jason Taylor: 6 years B2B SaaS PM at Cision, owned $40M ARR legacy platform, cross-functional delivery with Engineering, DBA, DevOps."

# Deliberately heuristic-unfriendly fixture: none of _keyword_craft_judgment's keywords
# (roadmap/cross-functional/stakeholder/agile/platform/saas/b2b) appear in the JD, and the
# work-exp blob shares only one token ("roles") with the extracted must-have, so
# _heuristic_judgments alone lands well under a 72 fit-score threshold (see the
# heuristic-only cross-check inside test_claude_native_mode_reads_pre_written_judgment_file
# for the exact math: fit_score=38, Decision=NO). This lets a written judgment file that
# asserts all "yes" produce a result the heuristic path could not plausibly produce on its
# own, so the tests below actually prove the claude_native branch was exercised.
WEAK_JD_TEXT = (
    "Product Manager role at a growing company.\n"
    "We ship features and coordinate with engineering teams.\n"
    "Requirements:\n"
    "- 5+ years experience in product roles\n"
)
WEAK_WORK_EXP = (
    "Jason Taylor has spent time in enterprise software roles working with "
    "engineering teams on delivery timelines."
)


def test_claude_native_mode_reads_pre_written_judgment_file(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        monkeypatch.setenv("FIT_JUDGMENT_MODE", "claude_native")
        monkeypatch.setenv("FIT_JUDGMENT_FOLDER", folder)
        fabricated_justification = (
            "Confirmed equivalence via named case study: led the Meridian onboarding "
            "relaunch end to end"
        )
        write_equivalence_judgment(folder, {
            "must_haves": [
                {
                    "text": "5+ years experience in product roles",
                    "judgment": "yes",
                    "justification": fabricated_justification,
                }
            ],
            "criteria": {
                "title_seniority_fit": {"judgment": "yes", "justification": "Senior PM matches"},
                "pm_craft_overlap": {"judgment": "yes", "justification": fabricated_justification},
                "team_structure_fit": {"judgment": "yes", "justification": "structured team"},
                "execution_depth": {"judgment": "yes", "justification": "shipped $40M platform ownership"},
                "transition_potential": {"judgment": "yes", "justification": "same B2B SaaS domain"},
            },
        })
        result = evaluate_structured_fit(WEAK_JD_TEXT, WEAK_WORK_EXP, {}, min_fit_score=72)
        assert result is not None
        assert result["Decision"] == "YES"
        assert result["Score"] >= 72

        # Prove the file was actually read rather than coincidentally matched: the
        # heuristic path only ever emits fixed canned justifications (e.g. "JD PM craft
        # keyword density"), never this fabricated text, so its presence in the output
        # can only come from the claude_native file-read path.
        justifications = [c["justification"] for c in result["FitReport"]["criteria_scores"]]
        assert fabricated_justification in justifications

        # Cross-check: simulate the claude_native branch being completely broken (falls
        # straight through to the heuristic) on this SAME fixture, and confirm it would
        # NOT produce the YES / >=72 result above. If this fixture ever stops
        # discriminating (e.g. someone tweaks the heuristic to be more generous), this
        # assertion fails loudly instead of the test silently losing its teeth.
        must_haves = extract_must_haves(WEAK_JD_TEXT)
        heuristic_only = compute_fit_report(
            WEAK_JD_TEXT,
            WEAK_WORK_EXP,
            _heuristic_judgments(WEAK_JD_TEXT, WEAK_WORK_EXP, must_haves),
            {},
            min_fit_score=72,
        )
        assert heuristic_only.decision != "YES" or heuristic_only.fit_score < 72


def test_claude_native_mode_falls_back_to_heuristic_when_file_missing(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        monkeypatch.setenv("FIT_JUDGMENT_MODE", "claude_native")
        monkeypatch.setenv("FIT_JUDGMENT_FOLDER", folder)
        result = evaluate_structured_fit(JD_TEXT, WORK_EXP, {}, min_fit_score=72)
        assert result is not None  # heuristic fallback still produces a result, never crashes


def test_claude_native_mode_falls_back_when_criteria_incomplete(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        monkeypatch.setenv("FIT_JUDGMENT_MODE", "claude_native")
        monkeypatch.setenv("FIT_JUDGMENT_FOLDER", folder)
        write_equivalence_judgment(folder, {
            "must_haves": [
                {
                    "text": "5+ years experience in product roles",
                    "judgment": "yes",
                    "justification": "6 years at Cision",
                }
            ],
            "criteria": {
                "title_seniority_fit": {"judgment": "yes", "justification": "Senior PM matches"},
                "pm_craft_overlap": {"judgment": "yes", "justification": "roadmap + cross-functional"},
                "team_structure_fit": {"judgment": "yes", "justification": "structured team"},
                "execution_depth": {"judgment": "yes", "justification": "shipped $40M platform ownership"},
                # "transition_potential" intentionally omitted — criteria dict is incomplete
            },
        })
        result = evaluate_structured_fit(WEAK_JD_TEXT, WEAK_WORK_EXP, {}, min_fit_score=72)
        assert result is not None

        # This pins down WHICH fallback behavior actually happened. If the incomplete
        # file were silently accepted (missing criterion defaulted to "partial" by
        # compute_fit_report's `crit_blob.get(name) or {}`), the other four "yes"
        # judgments alone would already clear min_fit_score=72 (fit_score ~96,
        # Decision=YES). Getting a low score / non-YES decision on this
        # heuristic-unfriendly fixture instead proves read_equivalence_judgment rejected
        # the incomplete file wholesale (per its REQUIRED_CRITERIA_KEYS.issubset(...)
        # contract in fit_judgment_io.py) and the heuristic path took over completely.
        assert result["Decision"] != "YES"
        assert result["Score"] < 72
