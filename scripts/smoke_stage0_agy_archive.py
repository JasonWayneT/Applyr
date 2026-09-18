#!/usr/bin/env python3
"""CR-114 Story 7: 5-10 archived-JD Agy schema smoke.

Runs leftover extraction and a bounded evidence sample through native Agy.
Does not set APPLYR_STAGE0_SUBSCRIPTION_ADAPTER, does not write SQLite or
production submissions, and does not manufacture gold labels.

Usage:
  python scripts/smoke_stage0_agy_archive.py
  python scripts/smoke_stage0_agy_archive.py --limit 8
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

_ARCHIVE = _ROOT / "data" / "archive" / "submissions"
_WORK_EXP = _ROOT / "data" / "workExperience.md"
_REPORT = _ROOT / "data" / "stage0_agy_archive_smoke_medium.json"
_CACHE = _ROOT / "data" / "stage0_agy_archive_smoke_cache_medium"
_EXTRACTION_CHUNK = 20
_EVIDENCE_REQUIRED = 4
_EVIDENCE_PREFERRED = 2
_EVIDENCE_EXCERPT_CHARS = 3000
_EVIDENCE_CHUNK = 3


def _parse_url_and_jd(raw_text: str) -> str:
    """Return JD body, dropping the optional URL header line."""
    if raw_text.startswith("URL: "):
        lines = raw_text.split("\n", 2)
        return lines[2] if len(lines) > 2 else ""
    return raw_text


def _clean_jd(raw_text: str) -> str:
    """Strip HTML leftovers from an archived JD body."""
    jd_text = _parse_url_and_jd(raw_text)
    for _ in range(3):
        unescaped = html.unescape(jd_text)
        if unescaped == jd_text:
            break
        jd_text = unescaped
    jd_text = re.sub(r"<[^>]+>", " ", jd_text)
    return re.sub(r"[ \t]{2,}", " ", jd_text)


def _pick_jds(limit: int) -> list[Path]:
    """Pick archived JDs with Original_JD.txt, excluding backups."""
    folders = sorted(
        path
        for path in _ARCHIVE.iterdir()
        if path.is_dir()
        and "backup" not in path.name
        and (path / "Original_JD.txt").exists()
    )
    return folders[:limit]


def _chunks(items: list, size: int) -> list[list]:
    """Split items into bounded adapter batches."""
    return [items[index : index + size] for index in range(0, len(items), size)]


def _summarize(result) -> dict:
    """Keep smoke telemetry without JD or work-history text."""
    return {
        "outcome": result.outcome,
        "reason": result.reason,
        "calls": result.calls,
        "elapsed_seconds": round(result.elapsed_seconds, 3),
        "subscription_minutes": round(result.subscription_minutes, 4),
        "api_cents": result.api_cents,
        "result_count": len(result.results),
        "missing_item_ids": list(result.missing_item_ids),
    }


def _run_task(task: str, items: list, config, budget, session=None) -> dict:
    """Run one adapter task and return redacted telemetry."""
    from stage0_subscription_adapter import run_stage0_subscription

    empty = {
        "outcome": "skipped",
        "reason": "no items",
        "calls": 0,
        "elapsed_seconds": 0.0,
        "subscription_minutes": 0.0,
        "api_cents": None,
        "result_count": 0,
        "missing_item_ids": [],
        "item_count": 0,
        "silent_line_loss": False,
        "unresolved_ids": [],
        "wall_seconds": 0.0,
    }
    if not items:
        return empty
    started = time.monotonic()
    start_calls = budget.calls
    rows: list[dict] = []
    outcomes: list[str] = []
    reasons: list[str] = []
    elapsed = 0.0
    minutes = 0.0
    chunk_size = _EXTRACTION_CHUNK if task == "extraction" else _EVIDENCE_CHUNK
    for chunk in _chunks(items, chunk_size):
        result = run_stage0_subscription(
            task, chunk, config=config, budget=budget, session=session
        )
        rows.extend(result.results)
        outcomes.append(result.outcome)
        if result.reason:
            reasons.append(result.reason)
        elapsed += result.elapsed_seconds
        minutes += result.subscription_minutes
        if result.outcome in {"exhausted", "disabled"}:
            break
    if "exhausted" in outcomes:
        outcome = "exhausted"
    elif "disabled" in outcomes:
        outcome = "disabled"
    elif "review" in outcomes:
        outcome = "review"
    else:
        outcome = "ok"
    sent_ids = [item.item_id for item in items]
    returned_ids = {str(row.get("item_id") or "") for row in rows}
    unresolved = [item_id for item_id in sent_ids if item_id not in returned_ids]
    return {
        "outcome": outcome,
        "reason": "; ".join(reasons) if reasons else None,
        "calls": budget.calls - start_calls,
        "elapsed_seconds": round(elapsed, 3),
        "subscription_minutes": round(minutes, 4),
        "api_cents": None,
        "result_count": len(rows),
        "missing_item_ids": unresolved,
        "item_count": len(items),
        "silent_line_loss": bool(unresolved) and outcome in {"ok", "cache_hit"},
        "unresolved_ids": unresolved,
        "wall_seconds": round(time.monotonic() - started, 3),
    }


def main() -> int:
    """Run the bounded Agy archive smoke and write gitignored telemetry."""
    parser = argparse.ArgumentParser(description="CR-114 Agy 5-10 JD schema smoke")
    parser.add_argument("--limit", type=int, default=8, help="Archived JDs to smoke (5-10)")
    args = parser.parse_args()
    limit = max(5, min(10, args.limit))

    os.environ.pop("APPLYR_STAGE0_SUBSCRIPTION_ADAPTER", None)
    if not _ARCHIVE.exists():
        print(f"Archive not found: {_ARCHIVE}", file=sys.stderr)
        return 1

    from build_stage0_fit_gate import _collect_nlp_section_candidates
    from evidence_scale import build_evidence_context
    from stage0_subscription_adapter import AdapterBudget, AdapterConfig, AgySession, Stage0Item

    work_exp = ""
    if _WORK_EXP.exists():
        work_exp = _WORK_EXP.read_text(encoding="utf-8", errors="replace")

    folders = _pick_jds(limit)
    config = AdapterConfig(
        enabled=True,
        harness="agy",
        profile="agy-default",
        model="gemini-3.8-flash-medium",
        effort="medium",
        timeout_seconds=120,
        max_calls=24,
        max_wall_seconds=1200,
        cache_dir=_CACHE,
    )
    budget = AdapterBudget(config)
    started = time.monotonic()
    prepared: list[dict] = []

    print(
        f"Agy archive smoke: {len(folders)} JDs, model={config.model}, "
        f"effort={config.effort}, sticky session, switch unset",
        flush=True,
    )
    for folder in folders:
        raw = (folder / "Original_JD.txt").read_text(encoding="utf-8", errors="replace")
        collected = _collect_nlp_section_candidates(_clean_jd(raw))
        if collected is None:
            prepared.append({"slug": folder.name, "error": "nlp_unavailable"})
            print(f"  {folder.name}: NLP unavailable", flush=True)
            continue
        buckets, leftovers = collected
        extract_items = [
            Stage0Item(f"{folder.name}:e{idx}", combo)
            for idx, (combo, _bullet, _header) in enumerate(leftovers)
        ]
        evidence_items: list[Stage0Item] = []
        for idx, line in enumerate(buckets.get("required", [])[:_EVIDENCE_REQUIRED]):
            evidence_items.append(
                Stage0Item(
                    f"{folder.name}:req:{idx}",
                    bucket="required",
                    requirement=line,
                    evidence_excerpt=build_evidence_context(
                        line, work_exp, k=4, max_chars=_EVIDENCE_EXCERPT_CHARS
                    ),
                )
            )
        for idx, line in enumerate(buckets.get("preferred", [])[:_EVIDENCE_PREFERRED]):
            evidence_items.append(
                Stage0Item(
                    f"{folder.name}:pref:{idx}",
                    bucket="preferred",
                    requirement=line,
                    evidence_excerpt=build_evidence_context(
                        line, work_exp, k=4, max_chars=_EVIDENCE_EXCERPT_CHARS
                    ),
                )
            )
        prepared.append(
            {
                "slug": folder.name,
                "slug_hash": hashlib.sha256(folder.name.encode("utf-8")).hexdigest()[:12],
                "confident_required": len(buckets.get("required", [])),
                "confident_preferred": len(buckets.get("preferred", [])),
                "leftover_lines": len(leftovers),
                "extract_items": extract_items,
                "evidence_items": evidence_items,
            }
        )

    extract_session = None
    evidence_session = None
    try:
        extract_session = AgySession("extraction", config)
        print("Extraction session started", flush=True)
        for row in prepared:
            if "extract_items" not in row:
                continue
            row["extraction"] = _run_task(
                "extraction", row["extract_items"], config, budget, extract_session
            )
            print(
                f"  {row['slug']}: leftovers={row['leftover_lines']} "
                f"extract={row['extraction']['outcome']}",
                flush=True,
            )
        extract_session.close()
        extract_session = None
        print("Evidence sessions start per JD", flush=True)
        for row in prepared:
            if "evidence_items" not in row:
                continue
            session = AgySession("evidence", config)
            try:
                row["evidence"] = _run_task(
                    "evidence", row["evidence_items"], config, budget, session
                )
            finally:
                session.close()
            print(
                f"  {row['slug']}: evidence={row['evidence']['outcome']}",
                flush=True,
            )
    finally:
        if extract_session is not None:
            extract_session.close()
        if evidence_session is not None:
            evidence_session.close()

    per_jd: list[dict] = []
    for row in prepared:
        per_jd.append(
            {
                "slug_hash": row.get("slug_hash") or hashlib.sha256(
                    str(row.get("slug") or "").encode("utf-8")
                ).hexdigest()[:12],
                "confident_required": row.get("confident_required", 0),
                "confident_preferred": row.get("confident_preferred", 0),
                "leftover_lines": row.get("leftover_lines", 0),
                "extraction": row.get("extraction") or {"outcome": row.get("error", "skipped")},
                "evidence": row.get("evidence") or {"outcome": row.get("error", "skipped")},
            }
        )

    report = {
        "schema_version": "stage0-agy-archive-smoke-v1",
        "jd_count": len(per_jd),
        "production_switch": os.environ.get("APPLYR_STAGE0_SUBSCRIPTION_ADAPTER"),
        "sqlite_writes": False,
        "gold_labels": False,
        "model": "gemini-3.8-flash-medium",
        "effort": "medium",
        "sticky_session": True,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "jds": per_jd,
    }
    outcomes = [row.get("extraction", {}).get("outcome") for row in per_jd]
    evidence_outcomes = [row.get("evidence", {}).get("outcome") for row in per_jd]
    report["extraction_ok"] = sum(1 for outcome in outcomes if outcome in {"ok", "cache_hit", "skipped"})
    report["extraction_review"] = sum(1 for outcome in outcomes if outcome == "review")
    report["evidence_ok"] = sum(
        1 for outcome in evidence_outcomes if outcome in {"ok", "cache_hit", "skipped"}
    )
    report["evidence_review"] = sum(1 for outcome in evidence_outcomes if outcome == "review")
    report["silent_line_loss"] = any(
        row.get("extraction", {}).get("silent_line_loss") or row.get("evidence", {}).get("silent_line_loss")
        for row in per_jd
        if isinstance(row.get("extraction"), dict)
    )
    _REPORT.parent.mkdir(parents=True, exist_ok=True)
    _REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "jds"}, indent=2))
    print(f"Wrote {_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
