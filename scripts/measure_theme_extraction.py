"""
CR-063 Round 1 baseline measurement — not part of the main pipeline.

For each of the 16 JDs in docs/reports/jd-theme-claim-eval-set.md, runs the deterministic
JD-profiling + full-catalog claim-scoring path (build_jd_profile_deterministic -> score_all_claims)
and reports whether each eval-set "should surface" claim landed in the top-5.
"""
from __future__ import annotations

import json
import os
import re

from claim_catalog import load_catalog
from jd_tailoring import build_jd_profile_deterministic, score_all_claims
from utils import PROJECT_ROOT

SUBMISSIONS_DIR = os.path.join(PROJECT_ROOT, "data", "submissions")

# company display name -> (folder slug, should-surface codes as written in the eval set)
EVAL_SET = [
    ("Cresta", "cresta", ["ACC-107", "ACC-103", "ACC-101"]),
    ("SailPoint", "sailpoint", ["ACC-107", "ACC-103", "ACC-401-AITOOLS"]),
    ("Group 1001", "group_1001", ["ACC-101", "ACC-103", "ACC-105", "ACC-107", "ACC-113"]),
    ("OneStream", "onestream_software", ["ACC-107"]),
    ("Buyers Edge Platform", "buyers_edge_platform", ["ACC-109", "ACC-204"]),
    ("Ontra", "ontra", ["ACC-401-AITOOLS", "ACC-103"]),
    ("Remote", "remote", ["ACC-401-AITOOLS", "ACC-106"]),
    ("Tilt", "tilt", ["ACC-101", "ACC-104"]),
    ("Covideo", "covideo", ["ACC-401-AITOOLS", "ACC-105"]),
    ("DataGrail", "datagrail", ["ACC-107", "ACC-401-AITOOLS", "ACC-103"]),
    ("MyTime", "mytime", ["ACC-401-AITOOLS", "ACC-104", "ACC-105"]),
    ("PAR", "par", ["ACC-105", "ACC-204", "ACC-109"]),
    ("ParkingPass.com", "parkingpass_com", ["ACC-101", "ACC-103", "ACC-109"]),
    ("PointClickCare", "pointclickcare", ["ACC-101", "ACC-102", "ACC-109", "ACC-401-AITOOLS"]),
    ("Redox", "redox", ["ACC-101", "ACC-103", "ACC-109"]),
    ("Lumos", "lumos", ["ACC-102", "ACC-107-LEGAL", "ACC-103", "ACC-101"]),
]

TOP_N = 5


def project_id(claim_id: str) -> str:
    m = re.match(r"^(ACC-\d+)", claim_id or "")
    return m.group(1) if m else (claim_id or "")


def code_hits_top5(code: str, top5_ids: list) -> bool:
    if re.match(r"^ACC-\d+$", code):
        # bare project-id-style code: hit if any suffixed variant sharing this project_id is in top5
        return any(project_id(cid) == code for cid in top5_ids)
    # fully-suffixed code: exact match required
    return code in top5_ids


def main():
    catalog = load_catalog()
    rows = []
    total_codes = 0
    total_hits = 0

    for company, slug, should_surface in EVAL_SET:
        jd_path = os.path.join(SUBMISSIONS_DIR, slug, "Original_JD.txt")
        with open(jd_path, encoding="utf-8") as f:
            jd_text = f.read()

        profile = build_jd_profile_deterministic(jd_text)
        scored = score_all_claims(profile, catalog, jd_text)
        top5 = scored[:TOP_N]
        top5_ids = [rec.claim_id for rec, _score in top5]

        hits = {code: code_hits_top5(code, top5_ids) for code in should_surface}
        total_codes += len(should_surface)
        total_hits += sum(1 for v in hits.values() if v)

        rows.append({
            "company": company,
            "themes": profile.priority_themes,
            "top5": [(rec.claim_id, score) for rec, score in top5],
            "should_surface": should_surface,
            "hits": hits,
        })

    print("=" * 100)
    for r in rows:
        print(f"\n### {r['company']}")
        print(f"Themes: {r['themes']}")
        print(f"Top-5: {r['top5']}")
        for code, hit in r["hits"].items():
            print(f"  should-surface {code}: {'HIT' if hit else 'MISS'}")

    print("\n" + "=" * 100)
    print(f"Aggregate: {total_hits}/{total_codes} should-surface codes present in top-5 across 16 JDs")

    # per-company all-or-nothing pass (all should-surface codes landed)
    per_company_pass = sum(1 for r in rows if all(r["hits"].values()))
    print(f"Per-company full pass (ALL should-surface codes hit): {per_company_pass}/16")

    out_path = os.path.join(PROJECT_ROOT, "docs", "reports", "cr063-round1-raw-output.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
    print(f"\nRaw output written to {out_path}")


if __name__ == "__main__":
    main()
