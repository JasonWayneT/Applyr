#!/usr/bin/env python3
"""Measure conservative direct-evidence routing against existing Stage 0 judgments.

This is evaluation-only. It reads stage0_fit_gate.json files and never changes
workflow artifacts, fit scores, tiers, or skip decisions.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "data" / "master_claims_tags_only.json"
SKILLS = ROOT / "data" / "skills_catalog.json"


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _phrase_match(phrase: str, text: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, re.I))


def load_verified_phrases(
    claims_path: Path = CLAIMS, skills_path: Path = SKILLS
) -> dict[str, set[str]]:
    """Exact phrases with verified provenance.

    A phrase must occur literally in a requirement. This is retrieval only,
    not semantic matching: a miss makes no claim about the candidate.
    """
    phrases: dict[str, set[str]] = defaultdict(set)
    claims = json.loads(claims_path.read_text(encoding="utf-8"))
    for claim_id, claim in claims.items():
        if claim.get("disabled"):
            continue
        for tag in claim.get("tags") or []:
            phrase = _norm(tag)
            if len(phrase) >= 3:
                phrases[phrase].add(claim_id)

    skills = json.loads(skills_path.read_text(encoding="utf-8"))
    for group, terms in skills.items():
        for term in terms or []:
            phrase = _norm(term)
            if len(phrase) >= 3:
                phrases[phrase].add(f"skill:{group}")
    return dict(phrases)


def direct_evidence_candidate(item: str, phrases: dict[str, set[str]]) -> dict | None:
    """Return an exact-evidence candidate only when a specific phrase is present.

    Generic one-word capability tags are intentionally excluded. The router
    proposes a candidate only, and callers must compare it with the current
    LLM result before considering any bypass.
    """
    text = _norm(item)
    matches = [
        (phrase, sorted(provenance))
        for phrase, provenance in phrases.items()
        if (" " in phrase or phrase in {"jira", "sql", "pendo", "amplitude"})
        and _phrase_match(phrase, text)
    ]
    if not matches:
        return None
    matches.sort(key=lambda row: (-len(row[0]), row[0]))
    return {
        "item": item,
        "matched_phrases": [phrase for phrase, _ in matches],
        "provenance": {phrase: provenance for phrase, provenance in matches},
    }


def evaluate_gate(gate: dict, phrases: dict[str, set[str]]) -> list[dict]:
    rows: list[dict] = []
    for bucket in ("required", "preferred"):
        for judgment in gate.get(bucket) or []:
            candidate = direct_evidence_candidate(judgment.get("item", ""), phrases)
            if not candidate:
                continue
            scored_by_llm = isinstance(judgment.get("evidence_level"), int)
            actual_direct = (
                scored_by_llm
                and
                judgment.get("gap_class") is None
                and judgment.get("evidence_level") in (3, 4)
            )
            rows.append({
                "company": gate.get("company"),
                "role": gate.get("role"),
                "bucket": bucket,
                **candidate,
                "llm_evidence_level": judgment.get("evidence_level"),
                "llm_gap_class": judgment.get("gap_class"),
                "scored_by_llm": scored_by_llm,
                "agrees_direct": actual_direct,
            })
    return rows


def _gate_files(roots: list[Path]) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        if root.exists():
            found.update(root.rglob("stage0_fit_gate.json"))
    return sorted(found)


def run(roots: list[Path]) -> dict:
    phrases = load_verified_phrases()
    candidates: list[dict] = []
    for path in _gate_files(roots):
        try:
            candidates.extend(evaluate_gate(json.loads(path.read_text(encoding="utf-8")), phrases))
        except (OSError, json.JSONDecodeError):
            continue
    comparable = [row for row in candidates if row["scored_by_llm"]]
    agreement = sum(row["agrees_direct"] for row in comparable)
    return {
        "schema_version": 1,
        "mode": "shadow_only",
        "gate_files": len(_gate_files(roots)),
        "candidate_count": len(candidates),
        "comparable_candidate_count": len(comparable),
        "legacy_unscored_candidate_count": len(candidates) - len(comparable),
        "agreement_count": agreement,
        "false_satisfaction_count": len(comparable) - agreement,
        "candidates": candidates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate exact direct-evidence routing.")
    parser.add_argument(
        "--root",
        action="append",
        type=Path,
        default=[],
        help="Root to scan; defaults to submissions and archived skips.",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    roots = args.root or [ROOT / "data" / "submissions", ROOT / "data" / "archive" / "skipped"]
    report = run(roots)
    output = args.output or ROOT / "data" / "reports" / "stage0_direct_evidence_shadow.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "gate_files", "candidate_count", "comparable_candidate_count",
        "legacy_unscored_candidate_count", "agreement_count", "false_satisfaction_count"
    )}))
    print(f"report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
