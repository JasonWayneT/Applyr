# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""
CR-069 Round 1 Step 1 — fresh baseline hit-rate measurement for ACC-401-AITOOLS
and ACC-204, against current shipped code. Standalone diagnostic script, no
production edits (imports and calls production functions only).

Adapted from CR-063's measure_theme_extraction.py:
  - repointed from data/submissions/ (now empty) to data/archive/submissions/
  - PAR's folder slug corrected to par_technology
  - scoped to only the 8 should-surface (claim, JD) pairs this CR measures
    (6 ACC-401-AITOOLS + 2 ACC-204; SailPoint excluded, not in the archive)

Not part of the main pipeline. Read-only against data/archive/submissions/ and
data/master_claims.json.
"""
from __future__ import annotations

import json
import os
import re

from claim_catalog import load_catalog
from jd_tailoring import build_jd_profile_deterministic, score_all_claims
from utils import PROJECT_ROOT

ARCHIVE_SUBMISSIONS_DIR = os.path.join(PROJECT_ROOT, "data", "archive", "submissions")

# company display name -> (folder slug, should-surface codes as written in the eval set)
AITOOLS_EVAL_SET = [
    ("Ontra", "ontra", ["ACC-401-AITOOLS"]),
    ("Remote", "remote", ["ACC-401-AITOOLS"]),
    ("Covideo", "covideo", ["ACC-401-AITOOLS"]),
    ("DataGrail", "datagrail", ["ACC-401-AITOOLS"]),
    ("MyTime", "mytime", ["ACC-401-AITOOLS"]),
    ("PointClickCare", "pointclickcare", ["ACC-401-AITOOLS"]),
]
# SailPoint is eval-set should-surface for ACC-401-AITOOLS too, but its folder is
# gone from data/archive/submissions/ (confirmed 2026-07-15) — excluded, not measured.
SAILPOINT_EXCLUDED_NOTE = (
    "SailPoint — EXCLUDED, folder not present in data/archive/submissions/ "
    "(eval set names ACC-401-AITOOLS should-surface on 7 companies total, not 6; "
    "this script measures the 6 that are actually present)"
)

ACC204_EVAL_SET = [
    ("Buyers Edge Platform", "buyers_edge_platform", ["ACC-204"]),
    ("PAR", "par_technology", ["ACC-204"]),
]

TOP_N = 5


def project_id(claim_id: str) -> str:
    m = re.match(r"^(ACC-\d+)", claim_id or "")
    return m.group(1) if m else (claim_id or "")


def code_hits_top5(code: str, top5_ids: list) -> bool:
    if re.match(r"^ACC-\d+$", code):
        # bare project-id-style code: hit if any suffixed variant sharing this project_id is in top5
        return any(project_id(cid) == code for cid in top5_ids)
    return code in top5_ids


def measure(eval_set):
    catalog = load_catalog()
    rows = []
    total_codes = 0
    total_hits = 0

    for company, slug, should_surface in eval_set:
        jd_path = os.path.join(ARCHIVE_SUBMISSIONS_DIR, slug, "Original_JD.txt")
        with open(jd_path, encoding="utf-8") as f:
            jd_text = f.read()

        profile = build_jd_profile_deterministic(jd_text)
        scored = score_all_claims(profile, catalog, jd_text)
        top5 = scored[:TOP_N]
        top5_ids = [rec.claim_id for rec, _score in top5]

        # also find the should-surface claim's own rank/score even if outside top-5
        full_ids = [rec.claim_id for rec, _score in scored]
        full_scores = {rec.claim_id: score for rec, score in scored}

        hits = {code: code_hits_top5(code, top5_ids) for code in should_surface}
        total_codes += len(should_surface)
        total_hits += sum(1 for v in hits.values() if v)

        rank_info = {}
        for code in should_surface:
            if re.match(r"^ACC-\d+$", code):
                variants = [cid for cid in full_ids if project_id(cid) == code]
            else:
                variants = [code] if code in full_ids else []
            variant_ranks = {
                cid: {"rank": full_ids.index(cid) + 1, "score": full_scores[cid]}
                for cid in variants
            }
            rank_info[code] = variant_ranks

        rows.append({
            "company": company,
            "slug": slug,
            "themes": profile.priority_themes,
            "top5": [(rec.claim_id, score) for rec, score in top5],
            "should_surface": should_surface,
            "hits": hits,
            "rank_info": rank_info,
            "cutoff_score_top5": top5[-1][1] if len(top5) == TOP_N else None,
        })

    return rows, total_hits, total_codes


def main():
    print("=" * 100)
    print("ACC-401-AITOOLS baseline (6 measurable companies; SailPoint excluded)")
    print(SAILPOINT_EXCLUDED_NOTE)
    print("=" * 100)
    aitools_rows, aitools_hits, aitools_codes = measure(AITOOLS_EVAL_SET)
    for r in aitools_rows:
        print(f"\n### {r['company']} ({r['slug']})")
        print(f"Themes: {r['themes']}")
        print(f"Top-5: {r['top5']}")
        print(f"Top-5 cutoff score (5th place): {r['cutoff_score_top5']}")
        for code, hit in r["hits"].items():
            print(f"  should-surface {code}: {'HIT' if hit else 'MISS'}  rank/score detail: {r['rank_info'][code]}")

    print(f"\nAITOOLS aggregate: {aitools_hits}/{aitools_codes} should-surface hits in top-5 (6 measurable companies)")

    print("\n" + "=" * 100)
    print("ACC-204 baseline (2 companies)")
    print("=" * 100)
    acc204_rows, acc204_hits, acc204_codes = measure(ACC204_EVAL_SET)
    for r in acc204_rows:
        print(f"\n### {r['company']} ({r['slug']})")
        print(f"Themes: {r['themes']}")
        print(f"Top-5: {r['top5']}")
        print(f"Top-5 cutoff score (5th place): {r['cutoff_score_top5']}")
        for code, hit in r["hits"].items():
            print(f"  should-surface {code}: {'HIT' if hit else 'MISS'}  rank/score detail: {r['rank_info'][code]}")

    print(f"\nACC-204 aggregate: {acc204_hits}/{acc204_codes} should-surface hits in top-5 (2 companies)")

    out_path = os.path.join(PROJECT_ROOT, "docs", "reports", "cr069-round1-baseline-raw-output.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "aitools_rows": aitools_rows,
            "aitools_hits": aitools_hits,
            "aitools_codes": aitools_codes,
            "sailpoint_excluded_note": SAILPOINT_EXCLUDED_NOTE,
            "acc204_rows": acc204_rows,
            "acc204_hits": acc204_hits,
            "acc204_codes": acc204_codes,
        }, f, indent=2)
    print(f"\nRaw output written to {out_path}")


if __name__ == "__main__":
    main()
