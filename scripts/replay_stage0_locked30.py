#!/usr/bin/env python3
"""CR-114 Story 7: timed locked-30 adapter replay. Switch off. Native Agy.

Hash-bound to the candidate leftover model and the locked 30 slugs.
Does not promote, does not set APPLYR_STAGE0_SUBSCRIPTION_ADAPTER, does not
write SQLite or gold. Implements FR-328 / FR-329 / AC-426 / AC-427.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

from _harvest_adjudication_22 import SITTING_22, _jd_path
from evidence_scale import build_evidence_context
from smoke_stage0_agy_archive import (
    _EVIDENCE_EXCERPT_CHARS,
    _EVIDENCE_PREFERRED,
    _EVIDENCE_REQUIRED,
    _WORK_EXP,
    _clean_jd,
    _run_task,
)
from stage0_prefs_gate import run_prefs_gate
from utils import load_candidate_preferences

_SKIP_8 = _ROOT / "data" / "stage0_adjudication_8jd_skip.csv"
_SKIP_22 = _ROOT / "data" / "stage0_adjudication_22_skip.csv"
_CANDIDATE = _ROOT / "data" / "stage0_classifier.candidate.pkl"
_LIVE = _ROOT / "data" / "stage0_classifier.pkl"
_OUT = _ROOT / "data" / "stage0_locked30_replay.json"
_CACHE = _ROOT / "data" / "stage0_agy_locked30_cache"

_INDUSTRY_PATCH = {
    "blocked_industry": "",
    "confidence": "high",
    "reasoning": "locked30-replay-no-llm",
}


def _load_marks() -> list[dict]:
    """Locked 30 skip/pass marks. Sitting 1 then 22."""
    rows: list[dict] = []
    for sitting, path, default in (
        ("1", _SKIP_8, "PASS"),
        ("2-3", _SKIP_22, ""),
    ):
        if not path.exists():
            if sitting == "2-3":
                rows.extend(
                    {"slug": slug, "your_mark": "", "sitting": sitting}
                    for slug, _why in SITTING_22
                )
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                rows.append(
                    {
                        "slug": row.get("slug") or "",
                        "your_mark": (row.get("your_mark") or default).strip().upper(),
                        "sitting": sitting,
                    }
                )
    return [row for row in rows if row["slug"]]


def _slug_list_hash(slugs: list[str]) -> str:
    """Stable hash of the locked 30 identity."""
    payload = "\n".join(slugs)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    """SHA-256 of a file, or empty if missing."""
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prefs_row(slug: str, jd_text: str, mark: str, prefs: dict) -> dict:
    """Compare deterministic prefs to jason's skip/pass mark."""
    company = slug.replace("_", " ")
    with patch(
        "industry_semantic.classify_industry_safe",
        return_value=_INDUSTRY_PATCH,
    ):
        result = run_prefs_gate(company, jd_text, prefs)
    gate = "PASS" if result.get("passed") else "SKIP"
    codes = [item.get("code", "") for item in result.get("rejects") or []]
    false_skip = mark == "PASS" and gate == "SKIP"
    false_pass = mark == "SKIP" and gate == "PASS"
    return {
        "slug": slug,
        "jason_mark": mark,
        "gate": gate,
        "codes": codes,
        "false_skip": false_skip,
        "false_pass": false_pass,
    }


def main() -> int:
    """Run prefs + native Agy leftover/evidence replay for the locked 30."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=_CANDIDATE)
    parser.add_argument("--out", type=Path, default=_OUT)
    args = parser.parse_args()

    os.environ.pop("APPLYR_STAGE0_SUBSCRIPTION_ADAPTER", None)
    if os.environ.get("APPLYR_STAGE0_SUBSCRIPTION_ADAPTER"):
        print("APPLYR_STAGE0_SUBSCRIPTION_ADAPTER must stay unset", file=sys.stderr)
        return 1

    from build_stage0_fit_gate import _collect_nlp_section_candidates
    from stage0_subscription_adapter import AdapterBudget, AdapterConfig, AgySession, Stage0Item

    marks = _load_marks()
    slugs = [row["slug"] for row in marks]
    if len(slugs) != 30:
        print(f"locked 30 has {len(slugs)} rows, not 30", file=sys.stderr)
        return 1

    prefs = load_candidate_preferences()
    work_exp = _WORK_EXP.read_text(encoding="utf-8", errors="replace") if _WORK_EXP.exists() else ""
    candidate_sha = _file_sha(args.candidate)
    live_sha = _file_sha(_LIVE)
    locked_sha = _slug_list_hash(slugs)

    config = AdapterConfig(
        enabled=True,
        harness="agy",
        profile="agy-default",
        model="gemini-3.8-flash-medium",
        effort="medium",
        timeout_seconds=120,
        max_calls=96,
        max_wall_seconds=3600,
        cache_dir=_CACHE,
    )
    budget = AdapterBudget(config)
    started = time.monotonic()
    per_jd: list[dict] = []
    prefs_rows: list[dict] = []

    print(
        f"Locked-30 replay: {len(slugs)} JDs, switch unset, candidate={candidate_sha[:12]}",
        flush=True,
    )

    extract_session = AgySession("extraction", config)
    prepared: list[dict] = []
    try:
        for mark_row in marks:
            slug = mark_row["slug"]
            path = _jd_path(slug)
            raw = path.read_text(encoding="utf-8", errors="replace")
            jd_text = _clean_jd(raw)
            prefs_rows.append(_prefs_row(slug, jd_text, mark_row["your_mark"], prefs))
            collected = _collect_nlp_section_candidates(jd_text)
            row: dict = {
                "slug": slug,
                "slug_hash": hashlib.sha256(slug.encode("utf-8")).hexdigest()[:12],
            }
            if collected is None:
                row["error"] = "nlp_unavailable"
                row["extract_items"] = []
                row["evidence_items"] = []
                prepared.append(row)
                print(f"  {slug}: NLP unavailable", flush=True)
                continue
            buckets, leftovers = collected
            row["leftover_lines"] = len(leftovers)
            row["extract_items"] = [
                Stage0Item(f"{slug}:e{idx}", combo)
                for idx, (combo, _bullet, _header) in enumerate(leftovers)
            ]
            evidence_items: list[Stage0Item] = []
            for idx, line in enumerate(buckets.get("required", [])[:_EVIDENCE_REQUIRED]):
                evidence_items.append(
                    Stage0Item(
                        f"{slug}:req:{idx}",
                        bucket="required",
                        requirement=line,
                        evidence_excerpt=build_evidence_context(
                            line, work_exp, k=4, max_chars=_EVIDENCE_EXCERPT_CHARS
                        )
                        if work_exp
                        else "",
                    )
                )
            for idx, line in enumerate(buckets.get("preferred", [])[:_EVIDENCE_PREFERRED]):
                evidence_items.append(
                    Stage0Item(
                        f"{slug}:pref:{idx}",
                        bucket="preferred",
                        requirement=line,
                        evidence_excerpt=build_evidence_context(
                            line, work_exp, k=4, max_chars=_EVIDENCE_EXCERPT_CHARS
                        )
                        if work_exp
                        else "",
                    )
                )
            row["evidence_items"] = evidence_items
            prepared.append(row)

        for row in prepared:
            if row.get("error"):
                row["extraction"] = {
                    "outcome": "review",
                    "silent_line_loss": False,
                    "calls": 0,
                    "wall_seconds": 0.0,
                }
                continue
            jd_started = time.monotonic()
            row["extraction"] = _run_task(
                "extraction", row["extract_items"], config, budget, extract_session
            )
            row["extract_wall"] = round(time.monotonic() - jd_started, 3)
            print(
                f"  {row['slug']}: leftovers={row.get('leftover_lines', 0)} "
                f"extract={row['extraction']['outcome']}",
                flush=True,
            )
    finally:
        extract_session.close()

    evidence_session = AgySession("evidence", config)
    try:
        for row in prepared:
            if row.get("error"):
                row["evidence"] = {
                    "outcome": "skipped",
                    "silent_line_loss": False,
                    "calls": 0,
                    "wall_seconds": 0.0,
                }
                continue
            jd_started = time.monotonic()
            row["evidence"] = _run_task(
                "evidence", row["evidence_items"], config, budget, evidence_session
            )
            row["evidence_wall"] = round(time.monotonic() - jd_started, 3)
            print(
                f"  {row['slug']}: evidence={row['evidence']['outcome']}",
                flush=True,
            )
    finally:
        evidence_session.close()

    for row in prepared:
        per_jd.append(
            {
                "slug_hash": row["slug_hash"],
                "leftover_lines": row.get("leftover_lines", 0),
                "extract_items": len(row.get("extract_items") or []),
                "evidence_items": len(row.get("evidence_items") or []),
                "wall_seconds": round(
                    (row.get("extract_wall") or 0.0) + (row.get("evidence_wall") or 0.0),
                    3,
                ),
                "extraction": row.get("extraction")
                or {"outcome": row.get("error", "skipped")},
                "evidence": row.get("evidence") or {"outcome": "skipped"},
            }
        )

    false_skips = sum(1 for row in prefs_rows if row["false_skip"])
    silent_losses = sum(
        1
        for row in per_jd
        if row.get("extraction", {}).get("silent_line_loss")
        or row.get("evidence", {}).get("silent_line_loss")
    )
    walls = [row.get("wall_seconds") or 0.0 for row in per_jd]
    calls = [
        (row.get("extraction") or {}).get("calls", 0)
        + (row.get("evidence") or {}).get("calls", 0)
        for row in per_jd
    ]
    walls_sorted = sorted(walls)
    p95_wall = walls_sorted[max(0, int(0.95 * (len(walls_sorted) - 1)))] if walls_sorted else 0.0
    max_wall = max(walls) if walls else 0.0
    max_calls = max(calls) if calls else 0
    budgets = {
        "per_jd_wall_seconds": int(max(120, max_wall * 1.25 + 30)),
        "per_jd_calls": int(max(4, max_calls + 2)),
        "batch_wall_seconds": int(max(600, (time.monotonic() - started) * 1.25)),
        "batch_calls": int(max(32, budget.calls + 8)),
        "observed_max_wall_seconds": round(max_wall, 3),
        "observed_p95_wall_seconds": round(p95_wall, 3),
        "observed_max_calls": max_calls,
        "observed_batch_calls": budget.calls,
    }
    report = {
        "schema_version": "stage0-locked30-replay-v1",
        "jd_count": len(slugs),
        "locked_30_sha256": locked_sha,
        "candidate_sha256": candidate_sha,
        "live_model_sha256": live_sha,
        "live_model_unchanged": True,
        "production_switch": os.environ.get("APPLYR_STAGE0_SUBSCRIPTION_ADAPTER"),
        "sqlite_writes": False,
        "gold_labels": False,
        "harness": "agy",
        "model": config.model,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "false_skips": false_skips,
        "silent_losses": silent_losses,
        "prefs": prefs_rows,
        "jds": per_jd,
        "budgets": budgets,
        "rollback": [
            "Leave APPLYR_STAGE0_SUBSCRIPTION_ADAPTER unset.",
            "Do not copy data/stage0_classifier.candidate.pkl over data/stage0_classifier.pkl.",
            "If a promote ever ran, restore data/stage0_classifier.previous.pkl to data/stage0_classifier.pkl.",
            "Adapter cache lives in data/stage0_agy_locked30_cache/ and can be deleted.",
        ],
        "reviewed_by": "pending-jason",
        "reviewed_at": "",
    }
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"false_skips={false_skips} silent_losses={silent_losses} "
        f"elapsed={report['elapsed_seconds']}s wrote {args.out}",
        flush=True,
    )
    if false_skips != 0 or silent_losses != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
