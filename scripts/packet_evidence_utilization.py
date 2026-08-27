"""Rank packet-selected evidence and detect high-priority unused claims.

This is a deterministic Stage 1 utilization guard. It does not decide whether a
candidate fits a role and never adds claims to a draft. It only identifies
packet claims that repeatedly support important JD items, so an author cannot
silently omit them after retrieval.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


_BUCKET_WEIGHTS = {
    "required": 100,
    "responsibilities": 60,
    "preferred": 25,
    "culture": 20,
}
_SOFT_GAP_BONUS = 40
_HIGH_PRIORITY_SCORE = 120


def _base_id(claim_id: str) -> str:
    parts = claim_id.split("-")
    if len(parts) >= 2 and parts[0] in {"ACC", "MET", "VOC"}:
        return "-".join(parts[:2])
    return claim_id


def _cited_claim_ids(provenance: dict[str, Any]) -> set[str]:
    cited: set[str] = set()
    for section in ("resume_claims", "cover_letter_claims"):
        for row in provenance.get(section) or []:
            if not isinstance(row, dict):
                continue
            for claim_id in row.get("claim_ids") or []:
                if isinstance(claim_id, str) and claim_id.strip():
                    cited.add(claim_id.strip())
    return cited


def _is_cited(claim_id: str, cited: set[str]) -> bool:
    base = _base_id(claim_id)
    return any(_base_id(candidate) == base for candidate in cited)


def rank_packet_evidence(
    packet: dict[str, Any],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return ranked packet claim usage, without changing any submission file."""
    scores: dict[str, int] = defaultdict(int)
    mapped_items: dict[str, list[dict[str, str]]] = defaultdict(list)
    representative_ids: dict[str, str] = {}

    for row in packet.get("evidence_map") or []:
        if not isinstance(row, dict):
            continue
        bucket = str(row.get("bucket") or "").lower()
        weight = _BUCKET_WEIGHTS.get(bucket, 0)
        item = str(row.get("jd_item") or "")
        for claim_id in row.get("claim_ids") or []:
            if not isinstance(claim_id, str) or not claim_id.strip():
                continue
            claim_id = claim_id.strip()
            key = _base_id(claim_id)
            scores[key] += weight
            representative_ids.setdefault(key, claim_id)
            mapped_items[key].append({"bucket": bucket, "jd_item": item})

    for gap in packet.get("soft_gaps") or []:
        if not isinstance(gap, dict) or (gap.get("class") or "SOFT") == "HARD":
            continue
        for claim_id in gap.get("claim_ids") or []:
            if isinstance(claim_id, str) and claim_id.strip():
                claim_id = claim_id.strip()
                key = _base_id(claim_id)
                scores[key] += _SOFT_GAP_BONUS
                representative_ids.setdefault(key, claim_id)

    cited = _cited_claim_ids(provenance or {})
    ranked = [
        {
            "claim_id": representative_ids[claim_key],
            "score": score,
            "mapped_items": mapped_items[claim_key],
            "used": _is_cited(claim_key, cited),
            "high_priority": score >= _HIGH_PRIORITY_SCORE,
        }
        for claim_key, score in scores.items()
    ]
    ranked.sort(key=lambda row: (-row["score"], row["claim_id"]))
    return {
        "high_priority_score": _HIGH_PRIORITY_SCORE,
        "claims": ranked,
        "high_priority_unused": [
            row["claim_id"] for row in ranked if row["high_priority"] and not row["used"]
        ],
    }
