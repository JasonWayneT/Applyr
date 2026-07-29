"""
CR-069 Round 1 Step 5 — guard-mitigation confirmation (Decision item 5 -> AC 5).

Standalone diagnostic script. Drives the REAL, unmodified production functions
directly with real inputs -- no instrumentation of internals needed, since these
are just function calls:

  - cover_claim_picker.pick_cover_proofs (the real cover-letter proof path, called
    exactly as cover_plan_builder.build_plan calls it in production: profile via
    build_jd_profile_deterministic(jd_text), ranked_needs via
    cover_jd_needs.extract_ranked_needs(jd_text, profile), k=4)
  - jd_tailoring.score_all_claims (the resume-side selection ranking -- same
    ranking pick_cover_bullets' fallback path sorts by, no guard exists on
    either consumer)

Reports, with real output: which of the 6 ACC-401-AITOOLS JDs actually get
ACC-401-AITOOLS into a cover-letter proof slot, whether has_ai_signal + the
_protected_ai_slot guard conditions were true when it did, confirms ACC-204
never lands a cover-letter proof slot (no guard exists for it), and reports each
claim's resume-side rank (score_all_claims, unguarded) for the same 8 pairs.

No production edits.
"""
from __future__ import annotations

import os

from claim_catalog import load_catalog
from cover_claim_picker import pick_cover_proofs
from cover_jd_needs import extract_ranked_needs
from jd_tailoring import build_jd_profile_deterministic, has_ai_signal, score_all_claims
from utils import PROJECT_ROOT

ARCHIVE_SUBMISSIONS_DIR = os.path.join(PROJECT_ROOT, "data", "archive", "submissions")

AITOOLS_SLUGS = ["ontra", "remote", "covideo", "datagrail", "mytime", "pointclickcare"]
ACC204_SLUGS = ["buyers_edge_platform", "par_technology"]


def _has_metric(catalog, claim_id: str) -> bool:
    import re
    rec = catalog.claims.get(claim_id)
    return bool(rec and re.search(r"\d", rec.body))


def run_cover_path(slug: str, catalog):
    jd_path = os.path.join(ARCHIVE_SUBMISSIONS_DIR, slug, "Original_JD.txt")
    with open(jd_path, encoding="utf-8") as f:
        jd_text = f.read()

    # Mirrors cover_plan_builder.build_plan's exact real production call.
    profile = build_jd_profile_deterministic(jd_text)
    ranked_needs = extract_ranked_needs(jd_text, profile)
    proofs = pick_cover_proofs(catalog, ranked_needs, profile, jd_text, k=4)
    proof_ids = [p.claim_id for p in proofs]
    ai_signal = has_ai_signal(jd_text)

    return {
        "slug": slug,
        "ranked_needs": ranked_needs,
        "proof_ids": proof_ids,
        "ai_signal": ai_signal,
    }


def run_resume_path(slug: str, catalog):
    jd_path = os.path.join(ARCHIVE_SUBMISSIONS_DIR, slug, "Original_JD.txt")
    with open(jd_path, encoding="utf-8") as f:
        jd_text = f.read()
    profile = build_jd_profile_deterministic(jd_text)
    scored = score_all_claims(profile, catalog, jd_text)
    ranked_ids = [rec.claim_id for rec, _score in scored]
    return ranked_ids, {rec.claim_id: s for rec, s in scored}


def main():
    catalog = load_catalog()

    print("=" * 100)
    print("ACC-401-AITOOLS: cover-letter proof path (pick_cover_proofs, real production call)")
    print("=" * 100)
    for slug in AITOOLS_SLUGS:
        r = run_cover_path(slug, catalog)
        got_slot = "ACC-401-AITOOLS" in r["proof_ids"]
        idx = r["proof_ids"].index("ACC-401-AITOOLS") if got_slot else None
        print(f"\n### {slug}")
        print(f"  ranked_needs: {r['ranked_needs']}")
        print(f"  proof slots (k=4): {r['proof_ids']}")
        print(f"  has_ai_signal(jd_text): {r['ai_signal']}")
        print(f"  ACC-401-AITOOLS got a cover-letter proof slot: {got_slot}" + (f" (slot index {idx})" if got_slot else ""))
        if got_slot:
            has_metric = _has_metric(catalog, "ACC-401-AITOOLS")
            print(f"  ACC-401-AITOOLS has a metric/digit in body: {has_metric} (claim has none by design)")
            if idx is not None and idx <= 1 and r["ai_signal"] and not has_metric:
                print("  GUARD CONDITIONS MET: has_ai_signal=True, claim in slot 0 or 1, no metric present "
                      "-> _protected_ai_slot would have exempted this slot from the metric-density swap-out. "
                      "Without the guard, this claim (no digit) would very likely have been replaced by the "
                      "metric-density check that runs immediately after initial proof selection.")

    print("\n" + "=" * 100)
    print("ACC-204: cover-letter proof path (pick_cover_proofs, real production call) -- expect NEVER a slot")
    print("=" * 100)
    for slug in ACC204_SLUGS:
        r = run_cover_path(slug, catalog)
        got_qa = "ACC-204-QA" in r["proof_ids"]
        got_global = "ACC-204-GLOBAL" in r["proof_ids"]
        print(f"\n### {slug}")
        print(f"  ranked_needs: {r['ranked_needs']}")
        print(f"  proof slots (k=4): {r['proof_ids']}")
        print(f"  has_ai_signal(jd_text): {r['ai_signal']}")
        print(f"  ACC-204-QA got a slot: {got_qa}   ACC-204-GLOBAL got a slot: {got_global}")
        print("  No _protected_ai_slot-equivalent guard exists for ACC-204 (confirmed by grep -- zero "
              "'ACC-204' references in cover_claim_picker.py).")

    print("\n" + "=" * 100)
    print("Resume-side / fallback ranking path (score_all_claims, NO guard on either consumer)")
    print("=" * 100)
    print("\n--- ACC-401-AITOOLS ---")
    for slug in AITOOLS_SLUGS:
        ranked_ids, scores = run_resume_path(slug, catalog)
        rank = ranked_ids.index("ACC-401-AITOOLS") + 1
        print(f"  {slug:16} resume-side rank={rank:3}  score={scores['ACC-401-AITOOLS']:4}  "
              f"(top-5 threshold at rank 5)")

    print("\n--- ACC-204 (both variants) ---")
    for slug in ACC204_SLUGS:
        ranked_ids, scores = run_resume_path(slug, catalog)
        rank_qa = ranked_ids.index("ACC-204-QA") + 1
        rank_global = ranked_ids.index("ACC-204-GLOBAL") + 1
        print(f"  {slug:22} ACC-204-QA rank={rank_qa:3} score={scores['ACC-204-QA']:4}   "
              f"ACC-204-GLOBAL rank={rank_global:3} score={scores['ACC-204-GLOBAL']:4}")


if __name__ == "__main__":
    main()
