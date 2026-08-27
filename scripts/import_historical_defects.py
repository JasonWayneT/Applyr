#!/usr/bin/env python3
"""Import structured historical defect evidence into a separate baseline (CR-099).

This command never writes the live CR-097 ledger or example bank. Historical
records remain informational until explicitly confirmed by a human, and even
confirmed records are excluded from live promotion and post-launch metrics.

Examples:
    python scripts/import_historical_defects.py --scan
    python scripts/import_historical_defects.py --status
    python scripts/import_historical_defects.py --confirm HIST-001 --note "..."
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from authoring_defect_categories import CATEGORIES, category_for_rule

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent
DEFAULT_ROOT = _REPO_ROOT / "data" / "archive" / "submissions"
DEFAULT_BASELINE = _REPO_ROOT / "data" / "authoring_defect_historical_baseline.json"
SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _stable_id(slug: str, source_ref: str, attempt: Any, rule_id: str, doc: str, line: Any) -> str:
    raw = f"{slug}|{source_ref}|{attempt}|{rule_id}|{doc}|{line}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10].upper()
    return f"HIST-{digest}"


def _empty() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "records": [],
    }


def _historical_records(root: Path) -> list[dict]:
    """Read only structured verify_history.json artifacts.

    In particular, this deliberately does not search Resume.md, CoverLetter.md,
    or free-form manifest prose. A final document cannot prove that its defect
    existed in the first draft.
    """
    records: list[dict] = []
    if not root.is_dir():
        return records
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        history_path = folder / "stage1_first_draft" / "verify_history.json"
        loaded = _load(history_path)
        if not isinstance(loaded, list):
            continue
        source_ref = history_path.relative_to(_REPO_ROOT).as_posix() if history_path.is_relative_to(_REPO_ROOT) else history_path.as_posix()
        for entry in loaded:
            if not isinstance(entry, dict):
                continue
            for violation in entry.get("violations") or []:
                if not isinstance(violation, dict):
                    continue
                rule_id = str(violation.get("rule_id") or "")
                category = violation.get("category") or category_for_rule(rule_id)
                if category not in CATEGORIES:
                    continue
                doc = str(violation.get("doc") or "")
                line = violation.get("line")
                record_id = _stable_id(
                    folder.name, source_ref, entry.get("attempt", 1), rule_id, doc, line
                )
                records.append(
                    {
                        "id": record_id,
                        "status": "needs_review",
                        "category": category,
                        "rule_id": rule_id,
                        "source_submission": folder.name,
                        "source_files": [source_ref],
                        "evidence_type": "historical_verify_history",
                        "evidence_ref": f"{source_ref}#attempt={entry.get('attempt', 1)}",
                        "evidence_excerpt": f"{rule_id} in {doc} at line {line}",
                        "observed_at": entry.get("observed_at") or "",
                        "imported_at": _now(),
                        "confidence": "high",
                        "review_note": "",
                        "confirmed_by": "",
                        "live_promotion_eligible": False,
                        "post_launch_metric_eligible": False,
                    }
                )
    return records


def scan(root: Path, baseline_path: Path) -> dict:
    existing = _load(baseline_path)
    if not isinstance(existing, dict):
        existing = _empty()
    current = {r.get("id"): r for r in existing.get("records", []) if isinstance(r, dict)}
    for record in _historical_records(root):
        current.setdefault(record["id"], record)
    baseline = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "records": list(current.values()),
    }
    _write(baseline_path, baseline)
    return baseline


def confirm(record_id: str, note: str, confirmer: str, baseline_path: Path) -> dict:
    if not note.strip():
        raise ValueError("--confirm requires --note")
    if not confirmer.strip():
        raise ValueError("--confirm requires --by")
    baseline = _load(baseline_path)
    if not isinstance(baseline, dict):
        raise ValueError(f"baseline not found: {baseline_path}")
    record = next((r for r in baseline.get("records", []) if r.get("id") == record_id), None)
    if not isinstance(record, dict):
        raise ValueError(f"historical record not found: {record_id}")
    record["status"] = "human_confirmed"
    record["review_note"] = note.strip()
    record["confirmed_by"] = confirmer.strip()
    record["confirmed_at"] = _now()
    record["live_promotion_eligible"] = False
    record["post_launch_metric_eligible"] = False
    _write(baseline_path, baseline)
    return record


def format_status(baseline: dict) -> str:
    records = [r for r in baseline.get("records", []) if isinstance(r, dict)]
    counts = {status: sum(r.get("status") == status for r in records) for status in ("needs_review", "human_confirmed")}
    lines = [
        f"historical defect baseline: {len(records)} record(s), "
        f"{counts['needs_review']} needs review, {counts['human_confirmed']} confirmed"
    ]
    for record in records:
        lines.append(
            f"{record.get('id')}  {record.get('status')}  "
            f"{record.get('category')}  {record.get('source_submission')}  "
            f"{record.get('evidence_ref')}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None, *, root: Path | None = None, baseline_path: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a separate, non-live historical defect baseline.")
    parser.add_argument("--scan", action="store_true", help="Import structured historical verify_history records.")
    parser.add_argument("--status", action="store_true", help="Show baseline records without scanning.")
    parser.add_argument("--confirm", metavar="RECORD_ID", help="Confirm one candidate with an explicit human note.")
    parser.add_argument("--note", default="", help="Required confirmation rationale.")
    parser.add_argument("--by", default="", help="Required human confirmer identifier.")
    parser.add_argument("--root", type=Path, default=root or DEFAULT_ROOT)
    parser.add_argument("--baseline", type=Path, default=baseline_path or DEFAULT_BASELINE)
    args = parser.parse_args(argv)
    if sum(bool(value) for value in (args.scan, args.status, args.confirm)) != 1:
        parser.error("choose exactly one of --scan, --status, or --confirm")
    if args.scan:
        print(format_status(scan(args.root, args.baseline)))
        return 0
    if args.confirm:
        try:
            record = confirm(args.confirm, args.note, args.by, args.baseline)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"CONFIRMED {record['id']} (historical baseline only)")
        return 0
    baseline = _load(args.baseline)
    print(format_status(baseline if isinstance(baseline, dict) else _empty()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
