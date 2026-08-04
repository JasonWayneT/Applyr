# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""
CR-063 Final-round pilot — semantic re-ranking, NOT wired into the production pipeline.

Layers cosine-similarity (already-cached claim embeddings + a fresh JD embedding via Ollama's
nomic-embed-text) on top of the existing deterministic keyword score, as an additive bonus, and
re-measures the same 16-JD eval set used by measure_theme_extraction.py. Does not modify
score_claim_for_jd or any file the real pipeline calls.
"""
from __future__ import annotations

import json
import os

from claim_catalog import load_catalog
from jd_tailoring import build_jd_profile_deterministic, score_claim_for_jd
from local_embeddings import get_embedding, cosine_similarity
from measure_theme_extraction import EVAL_SET, SUBMISSIONS_DIR, TOP_N, code_hits_top5
from utils import PROJECT_ROOT

CACHE_PATH = os.path.join(PROJECT_ROOT, "docs", "reports", "cr063-semantic-scores-cache.json")


def build_cache():
    """Compute (kw_score, cosine_sim) for every (JD, claim) pair once and cache to disk.

    Separated from scale-sweeping so re-testing different SEMANTIC_SCALE values doesn't require
    re-hitting Ollama for JD embeddings each time.
    """
    catalog = load_catalog()
    cache = {}
    for company, slug, should_surface in EVAL_SET:
        jd_path = os.path.join(SUBMISSIONS_DIR, slug, "Original_JD.txt")
        with open(jd_path, encoding="utf-8") as f:
            jd_text = f.read()

        profile = build_jd_profile_deterministic(jd_text)
        jd_vec = get_embedding(jd_text[:2500])

        entries = []
        for claim_id, rec in catalog.claims.items():
            raw_text = catalog.raw_truth_lines.get(claim_id, "")
            if not raw_text:
                continue
            body = rec.body or raw_text
            kw_score = score_claim_for_jd(body, profile, jd_text)
            claim_vec = catalog.claim_embeddings.get(claim_id, [])
            sem = cosine_similarity(jd_vec, claim_vec) if (jd_vec and claim_vec) else 0.0
            entries.append({"claim_id": claim_id, "kw_score": kw_score, "cosine_sim": round(sem, 4)})

        cache[company] = {"slug": slug, "should_surface": should_surface, "entries": entries}

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)
    print(f"Cache written to {CACHE_PATH}")
    return cache


def evaluate_scale(cache: dict, scale: float, verbose: bool = True):
    total_codes = 0
    total_hits = 0
    per_company_pass = 0
    details = []

    for company, data in cache.items():
        entries = data["entries"]
        should_surface = data["should_surface"]
        scored = [
            (e["claim_id"], e["kw_score"], e["cosine_sim"], e["kw_score"] + round(e["cosine_sim"] * scale))
            for e in entries
        ]
        scored.sort(key=lambda x: x[3], reverse=True)
        top5_ids = [t[0] for t in scored[:TOP_N]]
        hits = {code: code_hits_top5(code, top5_ids) for code in should_surface}
        total_codes += len(should_surface)
        total_hits += sum(1 for v in hits.values() if v)
        if all(hits.values()):
            per_company_pass += 1
        details.append((company, top5_ids, hits))

    if verbose:
        print(f"\n--- SCALE={scale} ---")
        for company, top5_ids, hits in details:
            print(f"{company}: top5={top5_ids} hits={hits}")
        print(f"Aggregate: {total_hits}/{total_codes}, per-company pass: {per_company_pass}/16")

    return total_hits, total_codes, per_company_pass


if __name__ == "__main__":
    import sys

    if os.path.exists(CACHE_PATH) and "--rebuild" not in sys.argv:
        with open(CACHE_PATH, encoding="utf-8") as f:
            cache = json.load(f)
        print(f"Loaded cache from {CACHE_PATH} (pass --rebuild to recompute embeddings)")
    else:
        cache = build_cache()

    for scale in (0, 5, 8, 12, 20, 30):
        evaluate_scale(cache, scale)
