# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""
CR-069 Round 1 Step 4 — loop-by-loop score_claim_for_jd trace (Decision item 4 -> AC 4).

Standalone diagnostic script. Re-implements the exact bookkeeping of
score_claim_for_jd's 4 scoring loops (scripts/jd_tailoring.py:316-345) --
importing the same THEME_KEYWORDS table and _rarity_weight function used in
production, not reimplementing their internals -- so it can report which loop(s)
fired, which token(s) each contributed, each token's tier / rarity-weight / DCG
rank-discount, and the final score. A sanity-check assertion confirms the traced
total equals the real production score_claim_for_jd(...) call for the same inputs,
for every pair traced.

No production edits: jd_tailoring.py's score_claim_for_jd is called directly
(unmodified) for the sanity check; the loop trace below is a read-only parallel
reproduction for observability only.
"""
from __future__ import annotations

import math
import os
import re

from claim_catalog import load_catalog
from jd_tailoring import (
    THEME_KEYWORDS,
    _rarity_weight,
    build_jd_profile_deterministic,
    score_all_claims,
    score_claim_for_jd,
)
from utils import PROJECT_ROOT

ARCHIVE_SUBMISSIONS_DIR = os.path.join(PROJECT_ROOT, "data", "archive", "submissions")


def traced_score(claim_text: str, profile, jd_text: str):
    """Read-only parallel reproduction of score_claim_for_jd's loop bookkeeping
    (jd_tailoring.py:316-345), instrumented to report per-token detail instead of
    just the final int."""
    text_l = claim_text.lower()
    jd_l = jd_text.lower()

    matched: dict = {}          # tok -> tier
    contributions: dict = {}    # tok -> which loop(s) fired for it (for reporting only)

    def _bump(tok: str, tier: int, loop: str) -> None:
        contributions.setdefault(tok, []).append((loop, tier))
        if matched.get(tok, 0) < tier:
            matched[tok] = tier

    for w in profile.keywords:                              # loop 1, tier 1
        if w in text_l and w in jd_l:
            _bump(w, 1, "loop1_keywords")
    for req in profile.requirements:                         # loop 2, tier 2
        for token in re.findall(r"[a-z]{5,}", req.lower()):
            if token in text_l:
                _bump(token, 2, "loop2_requirements")
    for theme in profile.priority_themes:                    # loop 3, tier 1
        for token in re.findall(r"[a-z]{5,}", theme.lower()):
            if token in text_l:
                _bump(token, 1, "loop3_priority_themes")
    for kw, _phrase in THEME_KEYWORDS:                        # loop 4, tier 3
        if kw in jd_l and kw in text_l:
            _bump(kw, 3, "loop4_theme_keywords_full_table")

    per_token = []
    for tok, tier in matched.items():
        rw = _rarity_weight(tok)
        per_token.append({
            "token": tok,
            "winning_tier": tier,
            "loops_that_matched_it": contributions[tok],
            "rarity_weight": rw,
            "tier_x_rarity": tier * rw,
        })
    # DCG rank discount: sort contributions descending, discount by log2(rank+1)
    per_token.sort(key=lambda d: d["tier_x_rarity"], reverse=True)
    total = 0.0
    for rank, d in enumerate(per_token, start=1):
        discount = math.log2(rank + 1)
        discounted = d["tier_x_rarity"] / discount
        d["dcg_rank"] = rank
        d["dcg_discount_divisor"] = discount
        d["discounted_contribution"] = discounted
        total += discounted

    final_score = int(round(total))
    return final_score, per_token


def top5_cutoff(profile, catalog, jd_text: str) -> int:
    scored = score_all_claims(profile, catalog, jd_text)
    if len(scored) >= 5:
        return scored[4][1]
    return scored[-1][1] if scored else 0


def run_pair(label: str, claim_id: str, slug: str, catalog):
    jd_path = os.path.join(ARCHIVE_SUBMISSIONS_DIR, slug, "Original_JD.txt")
    with open(jd_path, encoding="utf-8") as f:
        jd_text = f.read()

    profile = build_jd_profile_deterministic(jd_text)
    claim_text = catalog.claims[claim_id].body

    traced_final, per_token = traced_score(claim_text, profile, jd_text)
    prod_final = score_claim_for_jd(claim_text, profile, jd_text)
    cutoff = top5_cutoff(profile, catalog, jd_text)

    print(f"\n### {label}: claim={claim_id}  jd={slug}")
    print(f"  priority_themes used: {profile.priority_themes}")
    print(f"  requirements used ({len(profile.requirements)}): {profile.requirements}")
    print(f"  keywords used ({len(profile.keywords)}): {profile.keywords}")
    if not per_token:
        print("  NO TOKENS MATCHED by any of the 4 loops.")
    for d in sorted(per_token, key=lambda x: x["dcg_rank"]):
        print(
            f"  token={d['token']!r:22} winning_tier={d['winning_tier']} "
            f"(matched by {d['loops_that_matched_it']})  rarity_weight={d['rarity_weight']:.4f}  "
            f"tier*rarity={d['tier_x_rarity']:.4f}  dcg_rank={d['dcg_rank']} "
            f"discount_divisor={d['dcg_discount_divisor']:.4f}  "
            f"discounted_contribution={d['discounted_contribution']:.4f}"
        )
    print(f"  TRACED FINAL SCORE: {traced_final}   PRODUCTION score_claim_for_jd(): {prod_final}")
    assert traced_final == prod_final, f"MISMATCH for {label}: traced {traced_final} != production {prod_final}"
    print(f"  [Sanity check OK: traced == production]")
    print(f"  JD's actual top-5 cutoff score (5th place in score_all_claims ranking): {cutoff}")
    print(f"  Claim's score vs cutoff: {'>= cutoff (would be top-5 if unique)' if prod_final >= cutoff else 'BELOW cutoff by ' + str(cutoff - prod_final)}")
    return {
        "label": label, "claim_id": claim_id, "slug": slug,
        "traced_final": traced_final, "prod_final": prod_final,
        "cutoff": cutoff, "per_token": per_token,
    }


def main():
    catalog = load_catalog()
    results = []

    print("=" * 100)
    print("ACC-401-AITOOLS loop-by-loop trace (6 should-surface JDs)")
    print("=" * 100)
    for slug in ["ontra", "remote", "covideo", "datagrail", "mytime", "pointclickcare"]:
        results.append(run_pair(f"ACC-401-AITOOLS / {slug}", "ACC-401-AITOOLS", slug, catalog))

    print("\n" + "=" * 100)
    print("ACC-204 loop-by-loop trace (2 should-surface JDs, BOTH variants ACC-204-QA and ACC-204-GLOBAL)")
    print("=" * 100)
    for slug in ["buyers_edge_platform", "par_technology"]:
        for claim_id in ["ACC-204-QA", "ACC-204-GLOBAL"]:
            results.append(run_pair(f"{claim_id} / {slug}", claim_id, slug, catalog))

    print("\n" + "=" * 100)
    print("Summary: all 8 should-surface pairs (ACC-204 pairs shown as best-of-2-variants)")
    print("=" * 100)
    seen_acc204_jd = set()
    for r in results:
        if r["claim_id"] in ("ACC-204-QA", "ACC-204-GLOBAL"):
            if r["slug"] in seen_acc204_jd:
                continue
        gap = r["prod_final"] - r["cutoff"]
        print(f"  {r['label']:45} score={r['prod_final']:4}  cutoff={r['cutoff']:4}  gap={gap:+4}")


if __name__ == "__main__":
    main()
