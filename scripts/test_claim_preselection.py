"""Tests for Epic 3 — claim pre-selection in jd_tailoring.py."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


def _make_jd_profile(keywords=None, themes=None, requirements=None):
    profile = MagicMock()
    profile.keywords = keywords or ["data", "platform", "reliability"]
    profile.priority_themes = themes or ["platform reliability", "data quality"]
    profile.requirements = requirements or []
    return profile


def _make_catalog(claims: dict):
    """Minimal ClaimCatalog-like object."""
    catalog = MagicMock()
    catalog.claims = claims
    catalog.raw_truth_lines = {cid: c.body for cid, c in claims.items()}
    return catalog


def _make_claim(claim_id, body, disabled=False, cover_story="", enabled_for_cover=True):
    rec = MagicMock()
    rec.claim_id = claim_id
    rec.body = body
    rec.disabled = disabled
    rec.cover_story = cover_story
    rec.enabled_for_cover = enabled_for_cover
    return rec


class TestScoreAllClaims:
    def test_disabled_claims_excluded(self):
        from jd_tailoring import score_all_claims
        jd = _make_jd_profile()
        active = _make_claim("ACC-102", "Fixed 40% contact data drop-off.")
        disabled = _make_claim("ACC-114", "CAD 800K platform", disabled=True)
        catalog = _make_catalog({"ACC-102": active, "ACC-114": disabled})

        results = score_all_claims(jd, catalog)
        ids = [r.claim_id for r, _ in results]
        assert "ACC-114" not in ids
        assert "ACC-102" in ids

    def test_returns_sorted_by_score_descending(self):
        from jd_tailoring import score_all_claims
        jd = _make_jd_profile(keywords=["data", "platform"])
        high = _make_claim("ACC-102", "Eliminated 40% data drop-off across the platform pipeline.")
        low = _make_claim("ACC-301", "Automated laptop fulfillment for Zero To Sixty.")
        catalog = _make_catalog({"ACC-102": high, "ACC-301": low})

        results = score_all_claims(jd, catalog, jd_text="platform data reliability")
        scores = [s for _, s in results]
        # Scores should be non-increasing
        assert scores == sorted(scores, reverse=True)

    def test_empty_claims_returns_empty(self):
        from jd_tailoring import score_all_claims
        jd = _make_jd_profile()
        catalog = _make_catalog({})
        results = score_all_claims(jd, catalog)
        assert results == []


class TestSelectClClaims:
    def test_returns_n_claims(self):
        from jd_tailoring import select_cl_claims
        jd = _make_jd_profile()
        c1 = _make_claim("ACC-102", "Eliminated 40% contact data drop-off.", cover_story="Short cover story.")
        c2 = _make_claim("ACC-103", "Resolved 90% of 300-item security backlog.", cover_story="Security story.")
        c3 = _make_claim("ACC-104", "Drove 700 voluntary account migrations.")
        catalog = _make_catalog({"ACC-102": c1, "ACC-103": c2, "ACC-104": c3})

        results = select_cl_claims(jd, catalog, resume_claim_ids=[], n=2)
        assert len(results) <= 2

    def test_disabled_claims_never_selected(self):
        from jd_tailoring import select_cl_claims
        jd = _make_jd_profile()
        active = _make_claim("ACC-102", "Platform data remediation — 40% drop-off resolved.")
        disabled = _make_claim("ACC-114", "800K Canadian", disabled=True)
        catalog = _make_catalog({"ACC-102": active, "ACC-114": disabled})

        results = select_cl_claims(jd, catalog, resume_claim_ids=[], n=2)
        ids = [r.claim_id for r in results]
        assert "ACC-114" not in ids

    def test_resume_prominent_claims_down_weighted(self):
        from jd_tailoring import select_cl_claims
        jd = _make_jd_profile(keywords=["data", "platform"])
        # ACC-102 is the best match but already used in resume lead bullets
        strong_resume = _make_claim("ACC-102", "Eliminated 40% data drop-off across the platform.")
        strong_cover = _make_claim("ACC-103", "Resolved 90% of security backlog while maintaining roadmap.")
        catalog = _make_catalog({"ACC-102": strong_resume, "ACC-103": strong_cover})

        # Pass ACC-102 as resume-prominent
        results = select_cl_claims(
            jd, catalog, resume_claim_ids=["ACC-102"], n=1
        )
        ids = [r.claim_id for r in results]
        # ACC-102 should not be selected (it's already leading the resume)
        assert "ACC-102" not in ids or len(ids) == 0 or ids[0] != "ACC-102" or len(ids) > 1

    def test_returns_list_type(self):
        from jd_tailoring import select_cl_claims
        jd = _make_jd_profile()
        c1 = _make_claim("ACC-102", "Contact data remediation.")
        catalog = _make_catalog({"ACC-102": c1})
        results = select_cl_claims(jd, catalog, resume_claim_ids=[], n=2)
        assert isinstance(results, list)
