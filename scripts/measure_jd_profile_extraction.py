"""
CR-065 Round 1 — JD-profile extraction diagnostic, NOT part of the main pipeline.

For each of the 13 eval-set companies available in data/archive/submissions/ (see tracker for the
missing 3: tilt, par, parkingpass_com), calls the unmodified build_jd_profile_deterministic(jd_text)
and logs the full profile -- priority_themes, requirements, AND keywords together -- the gap
measure_theme_extraction.py leaves open (it only logs priority_themes).

Also implements the two candidate-defect comparisons named in the CR-065 spec, as pure diagnostics
that do not touch scripts/jd_tailoring.py:
  - keywords: current alphabetical top-12 vs. a frequency-sorted top-12 (same length>=5, same
    5-stopword filter, same _jd_body_for_themes() source text, only the sort key changes).
  - requirements: current whole-JD line-scan vs. the same line-scan applied only to the
    extract_req_section()-scoped subsection.
  - ranking-impact spike: constructs a corrected JdProfile (same themes, frequency-sorted keywords,
    section-scoped requirements) and re-scores it through the unmodified score_all_claims(), comparing
    ACC-105-EXECUTION's rank/top-5 membership against the current deterministic profile.

Run as a script (`python measure_jd_profile_extraction.py`) to print everything; individual pieces are
also importable for ad hoc use during the tracker's Round 1 write-up.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter

from claim_catalog import load_catalog
from jd_tailoring import (
    JdProfile,
    build_jd_profile_deterministic,
    extract_req_section,
    score_all_claims,
    _jd_body_for_themes,
)
from measure_theme_extraction import EVAL_SET, code_hits_top5, project_id
from utils import PROJECT_ROOT

ARCHIVE_SUBMISSIONS_DIR = os.path.join(PROJECT_ROOT, "data", "archive", "submissions")

# Same stopword set build_jd_profile_deterministic uses for `keywords` (jd_tailoring.py:140).
_KEYWORD_STOPWORDS = {"about", "their", "would", "should", "other"}

TARGET_CLAIM = "ACC-105-EXECUTION"


def available_eval_set():
    """EVAL_SET rows filtered to the companies actually present in the archive."""
    rows = []
    for company, slug, should_surface in EVAL_SET:
        jd_path = os.path.join(ARCHIVE_SUBMISSIONS_DIR, slug, "Original_JD.txt")
        if os.path.exists(jd_path):
            rows.append((company, slug, should_surface))
    return rows


def load_jd_text(slug: str) -> str:
    jd_path = os.path.join(ARCHIVE_SUBMISSIONS_DIR, slug, "Original_JD.txt")
    with open(jd_path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Part A — full profile extraction (priority_themes + requirements + keywords)
# ---------------------------------------------------------------------------

def extract_all_profiles():
    """Return {company: {"slug":..., "profile": JdProfile, "should_surface": [...]}}."""
    out = {}
    for company, slug, should_surface in available_eval_set():
        jd_text = load_jd_text(slug)
        profile = build_jd_profile_deterministic(jd_text)
        out[company] = {"slug": slug, "profile": profile, "should_surface": should_surface}
    return out


def print_part_a(profiles: dict):
    print("=" * 100)
    print("PART A — full JD-profile extraction (priority_themes + requirements + keywords)")
    print("=" * 100)
    for company, data in profiles.items():
        p = data["profile"]
        print(f"\n### {company} ({data['slug']})")
        print(f"priority_themes: {p.priority_themes}")
        print(f"requirements ({len(p.requirements)}):")
        for r in p.requirements:
            print(f"  - {r!r}")
        print(f"keywords ({len(p.keywords)}): {p.keywords}")


# ---------------------------------------------------------------------------
# Part C — keywords: alphabetical (current) vs. frequency-sorted
# ---------------------------------------------------------------------------

def keywords_frequency_sorted(jd_text: str) -> list:
    """Same extraction shape as build_jd_profile_deterministic's `keywords` field
    (jd_tailoring.py:139-140) -- same source text (_jd_body_for_themes), same
    length>=5 regex, same 5-stopword filter, same [:12] cutoff -- but sorted by
    descending in-body frequency instead of alphabetically. Ties broken
    alphabetically for determinism.
    """
    theme_source = _jd_body_for_themes(jd_text)
    jd_lower = theme_source.lower()
    tokens = re.findall(r"[a-z]{5,}", jd_lower)
    counts = Counter(t for t in tokens if t not in _KEYWORD_STOPWORDS)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _c in ranked[:12]]


def keywords_alphabetical_current(jd_text: str) -> list:
    """Reproduces the current code path exactly (jd_tailoring.py:139-140), for
    side-by-side diffing. Does not call build_jd_profile_deterministic directly
    so this stays a pure, isolated comparison of just the keywords mechanism.
    """
    theme_source = _jd_body_for_themes(jd_text)
    jd_lower = theme_source.lower()
    words = set(re.findall(r"[a-z]{5,}", jd_lower))
    return sorted(w for w in words if w not in _KEYWORD_STOPWORDS)[:12]


# ---------------------------------------------------------------------------
# Part D — requirements: current whole-JD line-scan vs. extract_req_section()-scoped
# ---------------------------------------------------------------------------

def _line_scan(text: str, limit: int = 6) -> list:
    """Same line-scan shape as build_jd_profile_deterministic's `requirements`
    field (jd_tailoring.py:132-137): 20-120 char lines starting alphanumeric,
    first `limit` matches, in document order.
    """
    out = []
    for line in text.splitlines():
        line = line.strip().lstrip("-•*").strip()
        if 20 <= len(line) <= 120 and line[0].isalnum():
            out.append(line[:120])
    return out[:limit]


def requirements_current(jd_text: str) -> list:
    """The exact current-code output (whole-JD scan)."""
    return _line_scan(jd_text)


def requirements_section_scoped(jd_text: str) -> list:
    """Same line-scan, applied only to extract_req_section()'s output."""
    section = extract_req_section(jd_text)
    return _line_scan(section)


# ---------------------------------------------------------------------------
# Part E — ranking-impact spike
# ---------------------------------------------------------------------------

def rank_of(claim_id: str, scored: list) -> int:
    """1-indexed rank of claim_id in a score_all_claims()-style descending list."""
    for i, (rec, _score) in enumerate(scored, start=1):
        if rec.claim_id == claim_id:
            return i
    return -1


def ranking_spike(company: str, slug: str, catalog, should_surface: list):
    jd_text = load_jd_text(slug)
    current_profile = build_jd_profile_deterministic(jd_text)

    corrected_profile = JdProfile(
        priority_themes=list(current_profile.priority_themes),
        requirements=requirements_section_scoped(jd_text),
        keywords=keywords_frequency_sorted(jd_text),
        source="corrected",
    )

    scored_current = score_all_claims(current_profile, catalog, jd_text)
    scored_corrected = score_all_claims(corrected_profile, catalog, jd_text)

    rank_current = rank_of(TARGET_CLAIM, scored_current)
    rank_corrected = rank_of(TARGET_CLAIM, scored_corrected)

    top5_current_ids = [rec.claim_id for rec, _s in scored_current[:5]]
    top5_corrected_ids = [rec.claim_id for rec, _s in scored_corrected[:5]]

    target_top5_current = code_hits_top5(TARGET_CLAIM, top5_current_ids)
    target_top5_corrected = code_hits_top5(TARGET_CLAIM, top5_corrected_ids)

    watch_codes = [c for c in should_surface if project_id(c) in ("ACC-401", "ACC-204")]
    watch_moves = {}
    for code in watch_codes:
        hit_before = code_hits_top5(code, top5_current_ids)
        hit_after = code_hits_top5(code, top5_corrected_ids)
        watch_moves[code] = {"before": hit_before, "after": hit_after}

    return {
        "company": company,
        "slug": slug,
        "rank_current": rank_current,
        "rank_corrected": rank_corrected,
        "top5_current": target_top5_current,
        "top5_corrected": target_top5_corrected,
        "top5_current_ids": top5_current_ids,
        "top5_corrected_ids": top5_corrected_ids,
        "watch_moves": watch_moves,
    }


# ---------------------------------------------------------------------------
# --full mode (CR-066) -- full-sample aggregate hit-rate + ACC-105-EXECUTION
# top-5 count, against whatever build_jd_profile_deterministic() currently does.
# Run unmodified (pre-fix) to lock the baseline, then re-run after the fix
# lands to measure the same metric on the same named sample (Acceptance
# Criteria 3/4/9). Does not alter Part A's existing main() path.
# ---------------------------------------------------------------------------

def full_sample_hit_rate(catalog, rows, target_claim: str = TARGET_CLAIM):
    """Run the should-surface hit-rate accounting (code_hits_top5-style) plus the
    target_claim top-5 appearance count across `rows`, using the current
    build_jd_profile_deterministic() (whatever it does at call time -- this is
    intentionally the real production function, not a diagnostic spike, so the
    same call site measures both the pre-fix and post-fix behavior).
    """
    detail = []
    total_hits = 0
    total_codes = 0
    target_top5_count = 0
    for company, slug, should_surface in rows:
        jd_text = load_jd_text(slug)
        profile = build_jd_profile_deterministic(jd_text)
        scored = score_all_claims(profile, catalog, jd_text)
        top5_ids = [rec.claim_id for rec, _s in scored[:5]]
        hits = {code: code_hits_top5(code, top5_ids) for code in should_surface}
        total_codes += len(should_surface)
        total_hits += sum(1 for v in hits.values() if v)
        target_hit = target_claim in top5_ids
        if target_hit:
            target_top5_count += 1
        detail.append({
            "company": company,
            "slug": slug,
            "top5": top5_ids,
            "hits": hits,
            "target_top5": target_hit,
        })
    return {
        "detail": detail,
        "total_hits": total_hits,
        "total_codes": total_codes,
        "target_top5_count": target_top5_count,
        "sample_size": len(rows),
    }


def print_full_sample_report():
    catalog = load_catalog()
    rows = available_eval_set()

    print("=" * 100)
    print(f"FULL-SAMPLE MEASUREMENT (--full) -- {len(rows)}/16 eval-set companies available")
    print("=" * 100)

    result = full_sample_hit_rate(catalog, rows)
    for d in result["detail"]:
        print(f"\n### {d['company']} ({d['slug']})")
        print(f"top5: {d['top5']}")
        for code, hit in d["hits"].items():
            print(f"  should-surface {code}: {'HIT' if hit else 'MISS'}")
        print(f"  {TARGET_CLAIM} in top5: {d['target_top5']}")

    print("\n" + "=" * 100)
    print(f"Aggregate should-surface hit rate: {result['total_hits']}/{result['total_codes']}")
    print(f"{TARGET_CLAIM} top-5 appearance count: {result['target_top5_count']}/{result['sample_size']}")
    return result


def main():
    import sys

    if "--full" in sys.argv:
        print_full_sample_report()
        return

    profiles = extract_all_profiles()
    print_part_a(profiles)

    print("\n" + "=" * 100)
    print(f"Total companies available: {len(profiles)}/13")


if __name__ == "__main__":
    main()
