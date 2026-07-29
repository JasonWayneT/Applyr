"""
CR-069 Round 1 Step 2 — vocabulary-gap table (Decision item 2 -> AC 2).

Read-only: for each of the 8 should-surface (claim, JD) pairs, lists which
JD-stated skill terms (manually identified from Original_JD.txt by grep, cited
inline below) have zero literal substring presence anywhere in the relevant
claim's body + tags in data/master_claims.json. No production edits, no
instrumentation — pure substring check against real catalog text.

Not part of the main pipeline.
"""
from __future__ import annotations

import json
import os

from utils import PROJECT_ROOT

MASTER_CLAIMS_PATH = os.path.join(PROJECT_ROOT, "data", "master_claims.json")

with open(MASTER_CLAIMS_PATH, encoding="utf-8") as f:
    _CLAIMS = json.load(f)


def claim_blob(claim_id: str) -> str:
    rec = _CLAIMS[claim_id]
    return (rec.get("text", "") + " " + " ".join(rec.get("tags", []))).lower()


AITOOLS_BLOB = claim_blob("ACC-401-AITOOLS")
ACC204_QA_BLOB = claim_blob("ACC-204-QA")
ACC204_GLOBAL_BLOB = claim_blob("ACC-204-GLOBAL")
ACC204_COMBINED_BLOB = ACC204_QA_BLOB + " " + ACC204_GLOBAL_BLOB

# JD-stated skill terms, manually identified via grep of each Original_JD.txt
# for AI/LLM/scrum-family vocabulary (see CR-069 tracker Round 1 Step 2 log for
# the raw grep output these are drawn from).
AITOOLS_JD_TERMS = {
    "ontra": ["AI development", "LLMs", "AI capabilities", "cutting edge of AI"],
    "remote": ["Cursor", "Claude Code", "autonomously build", "debug", "ship functional code"],
    "covideo": ["AI-driven video content creation", "leverage AI", "AI-Fluent", "AI tools", "workflow automation"],
    "datagrail": [
        "ML practitioners", "AI tools", "ML-powered", "AI-first", "AI throughout the product",
        "Vera AI", "AI direction",
    ],
    "mytime": ["Gen AI", "LLM technologies", "AI-powered features"],
    "pointclickcare": ["AI/ML-powered product features", "leveraging AI", "intelligent logic", "AI, automation"],
}

ACC204_JD_TERMS = {
    "buyers_edge_platform": [
        "sprint planning", "backlog management", "sprint ceremonies", "Agile methodologies",
        "Agile/Scrum teams", "Certified Scrum Master",
    ],
    "par_technology": [
        "agile environment", "scrum teams", "sprint objectives", "Agile development processes, especially SCRUM",
        "Backlog Management", "Agile Leadership", "Scrum related events",
    ],
}


import re

_WORD_RE = re.compile(r"[a-z]{5,}")


def has_substring(term: str, blob: str) -> bool:
    return term.lower() in blob


def word_level_hits(term: str, blob: str) -> list:
    """Individual >=5-char words inside `term` that DO appear as a substring in
    `blob` -- this is the granularity score_claim_for_jd's loops actually match
    at (single lowercase tokens via [a-z]{5,}), not whole-phrase matching."""
    return [w for w in _WORD_RE.findall(term.lower()) if w in blob]


def report(title: str, jd_terms: dict, blob_lookup):
    print("=" * 100)
    print(title)
    print("=" * 100)
    for company, terms in jd_terms.items():
        blob = blob_lookup(company)
        print(f"\n### {company}")
        gaps = []
        present = []
        for t in terms:
            if has_substring(t, blob):
                present.append(t)
            else:
                gaps.append(t)
        print(f"  Present in claim body/tags (literal PHRASE substring): {present or '(none)'}")
        print(f"  ZERO phrase-substring match in claim body/tags: {gaps or '(none)'}")
        # Word-level breakdown (what score_claim_for_jd's [a-z]{5,} token loops actually see)
        for t in gaps:
            hits = word_level_hits(t, blob)
            if hits:
                print(f"    -> but individual word(s) DO match at token level: {t!r} contains {hits}")


def main():
    report("ACC-401-AITOOLS vocabulary gap (claim blob = body + tags)", AITOOLS_JD_TERMS, lambda c: AITOOLS_BLOB)
    print(f"\nACC-401-AITOOLS claim blob: {AITOOLS_BLOB!r}")

    report(
        "ACC-204 vocabulary gap (claim blob = ACC-204-QA body+tags UNION ACC-204-GLOBAL body+tags)",
        ACC204_JD_TERMS,
        lambda c: ACC204_COMBINED_BLOB,
    )
    print(f"\nACC-204-QA claim blob: {ACC204_QA_BLOB!r}")
    print(f"ACC-204-GLOBAL claim blob: {ACC204_GLOBAL_BLOB!r}")


if __name__ == "__main__":
    main()
