import os
import tempfile

from fit_judgment_io import write_equivalence_judgment
from structured_fit import evaluate_structured_fit

JD_TEXT = "Senior Product Manager, B2B SaaS platform. Requirements: 5+ years PM experience, roadmap ownership, cross-functional delivery."
WORK_EXP = "Jason Taylor: 6 years B2B SaaS PM at Cision, owned $40M ARR legacy platform, cross-functional delivery with Engineering, DBA, DevOps."


def test_claude_native_mode_reads_pre_written_judgment_file(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        monkeypatch.setenv("FIT_JUDGMENT_MODE", "claude_native")
        monkeypatch.setenv("FIT_JUDGMENT_FOLDER", folder)
        write_equivalence_judgment(folder, {
            "must_haves": [{"text": "5+ years PM experience", "judgment": "yes", "justification": "6 years at Cision"}],
            "criteria": {
                "title_seniority_fit": {"judgment": "yes", "justification": "Senior PM matches"},
                "pm_craft_overlap": {"judgment": "yes", "justification": "roadmap + cross-functional"},
                "team_structure_fit": {"judgment": "yes", "justification": "structured team"},
                "execution_depth": {"judgment": "yes", "justification": "shipped $40M platform ownership"},
                "transition_potential": {"judgment": "yes", "justification": "same B2B SaaS domain"},
            },
        })
        result = evaluate_structured_fit(JD_TEXT, WORK_EXP, {}, min_fit_score=72)
        assert result is not None
        assert result["Decision"] == "YES"
        assert result["Score"] >= 72


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
            "must_haves": [{"text": "5+ years PM experience", "judgment": "yes", "justification": "6 years at Cision"}],
            "criteria": {
                "title_seniority_fit": {"judgment": "yes", "justification": "Senior PM matches"},
                "pm_craft_overlap": {"judgment": "yes", "justification": "roadmap + cross-functional"},
                "team_structure_fit": {"judgment": "yes", "justification": "structured team"},
                "execution_depth": {"judgment": "yes", "justification": "shipped $40M platform ownership"},
                # "transition_potential" intentionally omitted — criteria dict is incomplete
            },
        })
        result = evaluate_structured_fit(JD_TEXT, WORK_EXP, {}, min_fit_score=72)
        assert result is not None  # incomplete criteria -> read_equivalence_judgment returns None -> heuristic fallback
