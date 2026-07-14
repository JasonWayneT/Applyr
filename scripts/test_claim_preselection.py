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


class TestScoreClaimForJdDedup:
    def teardown_method(self, _method):
        from jd_tailoring import _reset_rarity_cache
        _reset_rarity_cache()

    def test_cross_loop_double_count_collapses_to_max_tier(self):
        """CR-064 Round 2: a token matched by multiple loops must contribute once,
        at its highest tier — not once per loop/line it happens to match in.

        `platform` fires in 3 of the 4 loops here (keyword tier 1, requirement
        tier 2, THEME_KEYWORDS tier 3). The pre-Round-2 formula sums every hit
        independently: 1+2+3 = 6. The dedup formula takes the max tier per unique
        token once: 3.

        CR-064 Round 3 layered a rarity-weight multiplier on top of dedup (every
        matched token's tier is now scaled by catalog rarity, not just summed), so
        this test pins a synthetic rarity table where the token involved has
        weight 1.0 (df == n) to isolate the dedup mechanism specifically.

        CR-064 Round 5 layered a DCG rank-discount breadth dampener on top of that
        (see `TestScoreClaimForJdBreadthDampener` below), which discounts every
        matched token past the single strongest one by its descending rank. That
        dampener is a mathematical no-op for a claim with exactly ONE distinct
        matched token (rank-1 divisor is `log2(2) == 1`), which is why this test
        now uses a single token (`platform`) rather than the three distinct
        tokens (`platform`/`roadmap`/`reliability`) it used before Round 5 — with
        three distinct tokens, the dampener's rank-discount would apply and this
        test would silently start asserting against dampener arithmetic it was
        never designed to test, rather than dedup specifically. Dampener
        arithmetic itself is covered by `TestScoreClaimForJdBreadthDampener`.
        """
        from jd_tailoring import JdProfile, score_claim_for_jd, _set_rarity_table

        _set_rarity_table({"platform": 10}, 10)

        profile = JdProfile(
            keywords=["platform"],
            requirements=["Own the platform roadmap end to end"],
            priority_themes=[],
            source="deterministic",
        )
        jd_text = "We need someone to own the platform roadmap end to end."
        claim_text = "Built platform improvements across the platform."

        score = score_claim_for_jd(claim_text, profile, jd_text)
        assert score == 3, (
            f"expected deduped score 3 (single token 'platform' at max tier 3, "
            f"dampener no-op for a single-token claim), got {score} — cross-loop "
            "double counting was not collapsed"
        )


class TestScoreClaimForJdRarity:
    """CR-064 Round 3: layer a rarity-weight multiplier on top of the Round 2 dedup pass.

    Uses `_set_rarity_table`/`_reset_rarity_cache` to pin a synthetic, deterministic
    df table rather than depending on live `master_claims.json` contents (per the
    tracker's test-isolation decision), so this test doesn't drift as the catalog
    changes.
    """

    def teardown_method(self, _method):
        from jd_tailoring import _reset_rarity_cache
        _reset_rarity_cache()

    def test_rare_token_match_outweighs_common_token_match(self):
        """Two claims each match exactly one keyword-loop (tier 1) token against the
        same JD. `raretoken` appears in only 1 of 50 synthetic catalog claims (highly
        rare); `commontoken` appears in all 50 (maximally common, weight floors to
        1.0, i.e. behaves like the old unweighted sum). The rare-token claim must
        score strictly higher despite matching the same number of tokens at the same
        tier.
        """
        from jd_tailoring import JdProfile, score_claim_for_jd, _set_rarity_table, _reset_rarity_cache

        _reset_rarity_cache()
        _set_rarity_table({"raretoken": 1, "commontoken": 50}, 50)

        profile = JdProfile(
            keywords=["raretoken", "commontoken"],
            requirements=[],
            priority_themes=[],
            source="deterministic",
        )
        jd_text = "We need someone fluent in raretoken and commontoken practices."

        rare_claim_text = "Delivered raretoken improvements across the org."
        common_claim_text = "Delivered commontoken improvements across the org."

        rare_score = score_claim_for_jd(rare_claim_text, profile, jd_text)
        common_score = score_claim_for_jd(common_claim_text, profile, jd_text)

        # weight(raretoken) = 1 + ln(50/1) = 4.912; tier 1 -> round(4.912) = 5
        # weight(commontoken) = 1 + ln(50/50) = 1.0; tier 1 -> round(1.0) = 1
        assert rare_score == 5, f"expected rare-token score 5, got {rare_score}"
        assert common_score == 1, f"expected common-token score 1 (flat, unweighted), got {common_score}"
        assert rare_score > common_score


class TestScoreClaimForJdBreadthDampener:
    """CR-064 Round 5: layer a DCG rank-discount breadth dampener on top of the
    Round 2 (dedup) + Round 3 (rarity-weight) formula.

    Uses `_set_rarity_table`/`_reset_rarity_cache` to pin a synthetic,
    deterministic df table (per the tracker's test-isolation decision), so this
    test doesn't drift as the catalog changes.
    """

    def teardown_method(self, _method):
        from jd_tailoring import _reset_rarity_cache
        _reset_rarity_cache()

    def test_many_token_breadth_claim_taxed_while_single_token_claim_immune(self):
        """One claim wins on a SINGLE rare, high-weight token ("killerterm", df=1
        of N=1000 -> weight ~=7.908). A separate claim wins on NINE common,
        floor-weight (1.0) tokens, all tier 1, which pre-dampener sum to a total
        (9) in the same ballpark as the single-token claim's pre-dampener total
        (~8) -- this mirrors the Round 4 hand-check's Cresta (many moderately-rare
        tokens) vs. Remote (one rare token) shape, with synthetic pinned numbers
        instead of live catalog contents.

        Post-DCG-dampener (this round's change): the single-token claim is
        mathematically unaffected -- with only one matched token there is no
        rank 2+ to discount, so `total / log2(1+1) == total`. The many-token
        claim's contributions get sorted descending and divided by
        `log2(rank+1)`, which drops its total from 9 to ~4.25 (rounds to 4) --
        meaningfully lower despite matching far more tokens.
        """
        from jd_tailoring import JdProfile, score_claim_for_jd, _set_rarity_table, _reset_rarity_cache

        _reset_rarity_cache()
        breadth_tokens = [f"breadthterm{i}" for i in range(9)]
        rarity_df = {"killerterm": 1}
        for tok in breadth_tokens:
            rarity_df[tok] = 1000  # df == N -> weight floors to 1.0 (common)
        _set_rarity_table(rarity_df, 1000)

        # Single high-value token claim.
        single_profile = JdProfile(
            keywords=["killerterm"], requirements=[], priority_themes=[], source="deterministic",
        )
        single_jd_text = "We need deep expertise in killerterm specifically."
        single_claim_text = "Delivered killerterm improvements across the org."

        # Many common-token (breadth) claim.
        breadth_profile = JdProfile(
            keywords=breadth_tokens, requirements=[], priority_themes=[], source="deterministic",
        )
        breadth_jd_text = "We need someone fluent in " + ", ".join(breadth_tokens) + "."
        breadth_claim_text = "Delivered " + " and ".join(breadth_tokens) + " improvements."

        single_score = score_claim_for_jd(single_claim_text, single_profile, single_jd_text)
        breadth_score = score_claim_for_jd(breadth_claim_text, breadth_profile, breadth_jd_text)

        # weight(killerterm) = 1 + ln(1000/1) = 7.908; tier 1, 1 token, rank-1
        # divisor log2(2) = 1 -> dampener is a no-op for a single-token claim.
        assert single_score == 8, f"expected single-token score 8 (unaffected by dampener), got {single_score}"

        # Pre-dampener (Round 3 formula) the breadth claim would sum to
        # 9 * 1.0 = 9 (round(9.0) == 9) -- in the same ballpark as the
        # single-token claim's 8. Post-dampener, sorted descending and divided
        # by log2(rank+1) (rank 1..9), the total drops to ~4.25 -> 4.
        assert breadth_score == 4, (
            f"expected breadth claim's DCG-dampened score 4 (pre-dampener would "
            f"have been 9), got {breadth_score} -- breadth dampener did not tax "
            "the many-token claim as designed"
        )
        assert breadth_score < single_score


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
