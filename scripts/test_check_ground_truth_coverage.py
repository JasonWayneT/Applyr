"""Tests for check_ground_truth_coverage.py's claim_provenance.json cross-reference.

Added 2026-08-18 -- no prior test coverage existed for this script despite it being
part of the Stage 1/Stage 2 gate chain. The same-day fix (checking claim_provenance.json
before falling back to fuzzy metric/tag text matching) had nothing regression-testing it
beyond a manual check against one real submission folder.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import check_ground_truth_coverage as gtc  # noqa: E402


def _write(folder: str, name: str, content) -> None:
    path = os.path.join(folder, name)
    if isinstance(content, (dict, list)):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(content, f)
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)


def test_load_provenance_claim_ids_missing_file_returns_none(tmp_path):
    assert gtc._load_provenance_claim_ids(str(tmp_path)) is None


def test_load_provenance_claim_ids_unions_resume_and_cover(tmp_path):
    _write(str(tmp_path), "claim_provenance.json", {
        "company": "Acme",
        "resume_claims": [{"bullet": "x", "claim_ids": ["ACC-101-SCOPE", "MET-01"]}],
        "cover_letter_claims": [{"proof_point": "y", "claim_ids": ["ACC-102-LEAD"]}],
    })
    ids = gtc._load_provenance_claim_ids(str(tmp_path))
    assert ids == {"ACC-101-SCOPE", "MET-01", "ACC-102-LEAD"}


def test_provenance_cited_claim_not_flagged_even_when_paraphrased(tmp_path, monkeypatch):
    """The exact false positive found 2026-08-18: a claim genuinely used in
    fresh prose that dropped the literal metric figure and tag words must
    not be flagged once it's confirmed via claim_provenance.json."""
    folder = str(tmp_path)
    _write(folder, "Original_JD.txt", "We need a Product Manager with strong compliance experience.")
    _write(folder, "Resume.md", "* Led a licensing review that kept the platform on the right side of vendor rules.")
    _write(folder, "CoverLetter.md", "Dear Hiring Manager,\n\nI focus on doing things right.\n\nBest,\nJason")
    _write(folder, "claim_provenance.json", {
        "company": "Acme",
        "resume_claims": [{"bullet": "Led a licensing review", "claim_ids": ["ACC-112-COMPLIANCE"]}],
        "cover_letter_claims": [],
    })

    fake_claims = {
        "ACC-112-COMPLIANCE": {
            "project_id": "ACC-112",
            "tags": {"compliance", "licensing"},
            "metrics": set(),  # metric-less -> would need 2+ literal tag hits without provenance
        }
    }
    monkeypatch.setattr(gtc, "_load_claims", lambda: fake_claims)

    result = gtc.check_folder(folder)
    assert result["jd_relevant_claims_possibly_unused"] == []
    assert result["clean"] is True


def test_claim_absent_from_provenance_still_flagged_when_unused(tmp_path, monkeypatch):
    """A claim genuinely never used (absent from provenance, and its tags
    don't appear twice in the drafted text) must still be flagged -- the
    provenance cross-reference should only clear real citations, not
    silence the check entirely."""
    folder = str(tmp_path)
    _write(folder, "Original_JD.txt", "We need a Product Manager with strong compliance experience.")
    _write(folder, "Resume.md", "* Shipped a roadmap feature on time.")
    _write(folder, "CoverLetter.md", "Dear Hiring Manager,\n\nI ship things.\n\nBest,\nJason")
    _write(folder, "claim_provenance.json", {
        "company": "Acme",
        "resume_claims": [{"bullet": "Shipped a roadmap feature", "claim_ids": ["ACC-999-OTHER"]}],
        "cover_letter_claims": [],
    })

    fake_claims = {
        "ACC-112-COMPLIANCE": {
            "project_id": "ACC-112",
            "tags": {"compliance", "licensing"},
            "metrics": set(),
        }
    }
    monkeypatch.setattr(gtc, "_load_claims", lambda: fake_claims)

    result = gtc.check_folder(folder)
    flagged_ids = [f["claim_id"] for f in result["jd_relevant_claims_possibly_unused"]]
    assert "ACC-112-COMPLIANCE" in flagged_ids
    assert result["clean"] is False


def test_no_provenance_file_falls_back_to_metric_heuristic(tmp_path, monkeypatch):
    """Pre-CR-075 submissions have no claim_provenance.json at all --
    behavior must fall back to the original literal metric/tag matching,
    unchanged."""
    folder = str(tmp_path)
    _write(folder, "Original_JD.txt", "We need a Product Manager with strong leadership experience.")
    _write(folder, "Resume.md", "* Resolved a 40% data failure rate across the platform.")
    _write(folder, "CoverLetter.md", "Dear Hiring Manager,\n\nI fix things.\n\nBest,\nJason")
    # No claim_provenance.json written.

    fake_claims = {
        "ACC-102-LEAD": {
            "project_id": "ACC-102",
            "tags": {"leadership"},
            "metrics": {"40%"},
        }
    }
    monkeypatch.setattr(gtc, "_load_claims", lambda: fake_claims)

    result = gtc.check_folder(folder)
    assert result["packet_scoping"].startswith("unavailable") or "claim_ids offered" in result["packet_scoping"]
    assert result["jd_relevant_claims_possibly_unused"] == []
