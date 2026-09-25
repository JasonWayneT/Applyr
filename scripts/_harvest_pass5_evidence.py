#!/usr/bin/env python3
"""Harvest stratified evidence rows for the five jason-PASS JDs.

your_mark stays blank. 17 skip JDs are not harvested. Native Agy evidence
only; production switch stays unset. Implements FR-329 / FR-339.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

from _build_adjudication_8jd import _sample_evidence, _window_ok
from _harvest_adjudication_22 import _jd_path
from evidence_scale import build_evidence_context, retrieval_coverage
from smoke_stage0_agy_archive import (
    _EVIDENCE_EXCERPT_CHARS,
    _WORK_EXP,
    _chunks,
    _clean_jd,
)
from stage0_subscription_adapter import AdapterBudget, AdapterConfig, AgySession, Stage0Item

PASS5 = (
    "eso",
    "smartlight_analytics",
    "remote",
    "yara_ai",
    "civicplus",
)
OUT_CSV = _ROOT / "data" / "stage0_adjudication_5pass_evidence.csv"
OUT_MD = _ROOT / "data" / "stage0_adjudication_5pass_evidence.md"
_CACHE = _ROOT / "data" / "stage0_agy_pass5_evidence_cache"


def _extract_scored_lines(slug: str, jd_text: str) -> list[dict]:
    """Required and preferred lines for evidence sampling."""
    os.environ.setdefault("APPLYR_STAGE0_SECTION_MODE", "deterministic")
    from build_stage0_fit_gate import _extract_sections

    buckets = _extract_sections(jd_text)
    rows: list[dict] = []
    for prefix, key in (("req", "required"), ("pref", "preferred")):
        for idx, line in enumerate(buckets.get(key) or []):
            rows.append(
                {
                    "slug": slug,
                    "item_id": f"{slug}:{prefix}:{idx}",
                    "nlp_bucket": key,
                    "line": line,
                }
            )
    return rows


def _agy_levels(rows: list[dict], work_exp: str) -> dict[str, dict]:
    """Score harvested lines through native Agy evidence. Switch unset."""
    if os.environ.get("APPLYR_STAGE0_SUBSCRIPTION_ADAPTER", "").strip():
        raise RuntimeError("APPLYR_STAGE0_SUBSCRIPTION_ADAPTER must stay unset")
    from stage0_subscription_adapter import run_stage0_subscription

    items: list[Stage0Item] = []
    for row in rows:
        items.append(
            Stage0Item(
                row["item_id"],
                bucket=row["nlp_bucket"],
                requirement=row["line"],
                evidence_excerpt=build_evidence_context(
                    row["line"], work_exp, k=4, max_chars=_EVIDENCE_EXCERPT_CHARS
                )
                if work_exp
                else "",
            )
        )
    config = AdapterConfig(
        enabled=True,
        harness="agy",
        profile="agy-default",
        model="gemini-3.8-flash-medium",
        effort="medium",
        timeout_seconds=300,
        max_calls=40,
        max_wall_seconds=1800,
        cache_dir=_CACHE,
    )
    budget = AdapterBudget(config)
    by_id: dict[str, dict] = {}
    session = AgySession("evidence", config)
    try:
        for chunk in _chunks(items, 3):
            result = run_stage0_subscription(
                "evidence", chunk, config=config, budget=budget, session=session
            )
            if result.outcome not in {"ok", "cache_hit"}:
                raise RuntimeError(
                    f"Agy evidence harvest outcome={result.outcome} reason={result.reason}"
                )
            if result.missing_item_ids:
                raise RuntimeError(f"silent line loss: {result.missing_item_ids}")
            for row in result.results:
                by_id[str(row.get("item_id") or "")] = row
    finally:
        session.close()
    return by_id


def main() -> int:
    """Write a blank-mark evidence sheet for the five PASS JDs."""
    if os.environ.get("APPLYR_STAGE0_SUBSCRIPTION_ADAPTER", "").strip():
        raise SystemExit("APPLYR_STAGE0_SUBSCRIPTION_ADAPTER must stay unset")
    work_exp = _WORK_EXP.read_text(encoding="utf-8") if _WORK_EXP.exists() else ""
    all_rows: list[dict] = []
    for slug in PASS5:
        path = _jd_path(slug)
        jd_text = _clean_jd(path.read_text(encoding="utf-8", errors="replace"))
        all_rows.extend(_extract_scored_lines(slug, jd_text))
    if not all_rows:
        raise SystemExit("no required/preferred lines extracted for the five PASS JDs")
    levels = _agy_levels(all_rows, work_exp)
    prefix = work_exp[:_EVIDENCE_EXCERPT_CHARS] if work_exp else ""
    evidence_rows: list[dict] = []
    for row in all_rows:
        cached = levels.get(row["item_id"]) or {}
        line = row["line"]
        excerpt = (
            build_evidence_context(line, work_exp, k=4, max_chars=_EVIDENCE_EXCERPT_CHARS)
            if work_exp
            else ""
        )
        coverage_ok, missing = retrieval_coverage(line, excerpt, work_exp) if work_exp else (True, [])
        evidence_rows.append(
            {
                **row,
                "agy_level": cached.get("evidence_level", cached.get("level")),
                "agy_gate": cached.get("gate"),
                "window_ok": _window_ok(line, excerpt),
                "prefix_ok": _window_ok(line, prefix),
                "coverage_ok": coverage_ok,
                "coverage_missing": ",".join(missing),
                "reasoning": (cached.get("reasoning") or "")[:280],
            }
        )
    sampled = _sample_evidence(evidence_rows)
    for row in sampled:
        row["agy_proposed"] = ""
        row["status"] = "NEEDS_MARK"
        row["source"] = "agy"
        row["your_mark"] = ""
        row["note"] = "jason PASS JD. 17 skips not harvested. Blank your_mark is unmarked."
    fieldnames = [
        "slug",
        "item_id",
        "nlp_bucket",
        "line",
        "agy_level",
        "agy_gate",
        "window_ok",
        "prefix_ok",
        "coverage_ok",
        "coverage_missing",
        "sample_class",
        "agy_proposed",
        "status",
        "source",
        "your_mark",
        "note",
        "reasoning",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sampled)
    lines = [
        "# Evidence marks needed: 5 jason-PASS JDs",
        "",
        "Blank `your_mark` is unmarked. Fill 0-4 or `drop`. Source is Agy, not gold.",
        "The 17 skip JDs are not in this sheet.",
        "",
        f"Sampled rows: {len(sampled)}",
        "",
        "| item_id | class | bucket | level | line |",
        "|---|---|---|---|---|",
    ]
    for row in sampled:
        line = (row.get("line") or "").replace("|", "/")[:120]
        lines.append(
            f"| `{row['item_id']}` | {row.get('sample_class')} | {row.get('nlp_bucket')} | "
            f"{row.get('agy_level')} | {line} |"
        )
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {len(sampled)} blank evidence rows to {OUT_CSV}")
    print(f"  {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
