#!/usr/bin/env python3
"""Join Agy smoke cache labels to leftover JD lines for human review (CR-114)."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

from build_stage0_fit_gate import _collect_nlp_section_candidates
from evidence_scale import build_evidence_context
from smoke_stage0_agy_archive import (
    _ARCHIVE,
    _CACHE,
    _EVIDENCE_EXCERPT_CHARS,
    _EVIDENCE_PREFERRED,
    _EVIDENCE_REQUIRED,
    _EXTRACTION_CHUNK,
    _WORK_EXP,
    _chunks,
    _clean_jd,
    _pick_jds,
)
from stage0_subscription_adapter import AdapterConfig, Stage0Item, cache_key

OUT = _ROOT / "data" / "stage0_agy_label_review.txt"
REQ_LIKE = re.compile(r"requir|qualification|must", re.I)
PREF_LIKE = re.compile(r"prefer|nice to have|bonus", re.I)
RESP_LIKE = re.compile(r"responsib|what you.?ll do|the role", re.I)
CULT_LIKE = re.compile(r"culture|benefit|perks|about us|equal opportunity|diversity", re.I)


def _load(task: str, items: list, config: AdapterConfig) -> dict | None:
    """Read one adapter cache file for a chunk."""
    extra = f"{config.model}:{config.effort}"
    key = cache_key(task, items, profile=config.profile, extra=extra)
    path = _CACHE / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    """Write a gitignored review packet and print a short scoreboard."""
    config = AdapterConfig(
        profile="agy-default",
        model="gemini-3.8-flash-medium",
        effort="medium",
    )
    work_exp = ""
    if _WORK_EXP.exists():
        work_exp = _WORK_EXP.read_text(encoding="utf-8", errors="replace")
    extract_rows: list[dict] = []
    evidence_rows: list[dict] = []
    for folder in _pick_jds(8):
        raw = (folder / "Original_JD.txt").read_text(encoding="utf-8", errors="replace")
        collected = _collect_nlp_section_candidates(_clean_jd(raw))
        if collected is None:
            continue
        buckets, leftovers = collected
        extract_items = [
            Stage0Item(f"{folder.name}:e{idx}", combo)
            for idx, (combo, _bullet, _header) in enumerate(leftovers)
        ]
        by_id: dict[str, str] = {}
        for chunk in _chunks(extract_items, _EXTRACTION_CHUNK):
            payload = _load("extraction", chunk, config)
            for row in (payload or {}).get("results") or []:
                by_id[str(row.get("item_id"))] = str(row.get("bucket") or "")
        for idx, (_combo, bullet, header) in enumerate(leftovers):
            item_id = f"{folder.name}:e{idx}"
            extract_rows.append(
                {
                    "slug": folder.name,
                    "item_id": item_id,
                    "header": header,
                    "line": bullet,
                    "agy": by_id.get(item_id, ""),
                }
            )
        ev_items: list[Stage0Item] = []
        ev_meta: list[tuple[str, str]] = []
        for idx, line in enumerate(buckets.get("required", [])[:_EVIDENCE_REQUIRED]):
            ev_items.append(
                Stage0Item(
                    f"{folder.name}:req:{idx}",
                    bucket="required",
                    requirement=line,
                    evidence_excerpt=build_evidence_context(
                        line, work_exp, k=4, max_chars=_EVIDENCE_EXCERPT_CHARS
                    ),
                )
            )
            ev_meta.append(("required", line))
        for idx, line in enumerate(buckets.get("preferred", [])[:_EVIDENCE_PREFERRED]):
            ev_items.append(
                Stage0Item(
                    f"{folder.name}:pref:{idx}",
                    bucket="preferred",
                    requirement=line,
                    evidence_excerpt=build_evidence_context(
                        line, work_exp, k=4, max_chars=_EVIDENCE_EXCERPT_CHARS
                    ),
                )
            )
            ev_meta.append(("preferred", line))
        if not ev_items:
            continue
        payload = _load("evidence", ev_items, config)
        results = {row["item_id"]: row for row in (payload or {}).get("results") or []}
        for item, (bucket, line) in zip(ev_items, ev_meta):
            row = results.get(item.item_id) or {}
            evidence_rows.append(
                {
                    "slug": folder.name,
                    "item_id": item.item_id,
                    "nlp_bucket": bucket,
                    "line": line,
                    "gate": row.get("gate"),
                    "level": row.get("evidence_level"),
                    "confidence": row.get("confidence"),
                    "gap_source": row.get("gap_source"),
                    "reasoning": (row.get("reasoning") or "")[:320],
                }
            )

    extract_flags = []
    for row in extract_rows:
        header = row["header"] or ""
        agy = row["agy"]
        flag = ""
        if REQ_LIKE.search(header) and agy in {"culture", "responsibilities"}:
            flag = "header looks required-ish, Agy did not say required"
        elif PREF_LIKE.search(header) and agy == "required":
            flag = "header looks preferred-ish, Agy said required"
        elif CULT_LIKE.search(header) and agy == "required":
            flag = "header looks culture-ish, Agy said required"
        elif RESP_LIKE.search(header) and agy == "required":
            flag = "header looks responsibilities-ish, Agy said required"
        if flag:
            extract_flags.append({**row, "flag": flag})

    hard = [row for row in evidence_rows if row["gate"] == "HARD"]
    pref_hard = [row for row in hard if row["nlp_bucket"] == "preferred"]
    zero = [row for row in evidence_rows if row["level"] == 0]
    four = [row for row in evidence_rows if row["level"] == 4]
    lines = [
        "Agy Flash-medium leftover label review",
        "Not gold. Mark each flagged line right/wrong.",
        "",
        f"extraction lines: {len(extract_rows)}",
        f"extraction buckets: {dict(Counter(row['agy'] for row in extract_rows))}",
        f"extraction header disagreements: {len(extract_flags)}",
        f"evidence lines: {len(evidence_rows)}",
        f"evidence levels: {dict(Counter(row['level'] for row in evidence_rows))}",
        f"HARD: {len(hard)} preferred HARD: {len(pref_hard)}",
        "",
        "== Extraction header disagreements ==",
    ]
    for row in extract_flags:
        lines.append(
            f"- [{row['slug']}] header={row['header']!r} agy={row['agy']} :: {row['line']}"
        )
    lines.append("")
    lines.append("== Evidence HARD ==")
    for row in hard:
        lines.append(
            f"- [{row['item_id']}] {row['nlp_bucket']} gap={row['gap_source']} "
            f"lvl={row['level']} :: {row['line']}"
        )
        lines.append(f"  {row['reasoning']}")
    lines.append("")
    lines.append("== Evidence level 0 ==")
    for row in zero:
        lines.append(f"- [{row['item_id']}] :: {row['line']}")
        lines.append(f"  {row['reasoning']}")
    lines.append("")
    lines.append("== Evidence level 4 ==")
    for row in four:
        lines.append(f"- [{row['item_id']}] :: {row['line']}")
        lines.append(f"  {row['reasoning']}")
    lines.append("")
    lines.append("== All leftover extraction labels ==")
    for row in extract_rows:
        lines.append(
            f"- [{row['slug']}] header={row['header']!r} agy={row['agy']} :: {row['line']}"
        )
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"extraction {len(extract_rows)} buckets={dict(Counter(row['agy'] for row in extract_rows))}")
    print(f"header disagreements {len(extract_flags)}")
    print(f"evidence {len(evidence_rows)} HARD={len(hard)} pref_HARD={len(pref_hard)} L0={len(zero)} L4={len(four)}")
    print(f"levels {dict(Counter(row['level'] for row in evidence_rows))}")
    print(f"wrote {OUT}")
    for row in extract_flags:
        print("FLAG", row["slug"], row["agy"], row["flag"], row["line"][:120])
    for row in hard:
        print("HARD", row["item_id"], row["gap_source"], row["line"][:120])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
