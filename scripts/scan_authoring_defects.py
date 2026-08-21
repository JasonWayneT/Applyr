#!/usr/bin/env python3
"""Cross-submission authoring-defect ledger and 2-occurrence trigger (CR-097 Epic 2).

Reads Stage 1 verify_history.json files (primary) and Stage 2 RESOLVED_EDIT
dispositions (secondary). Writes data/authoring_defect_ledger.json. Never
blocks a submission — advisory only.

Run from repo root:
    python scripts/scan_authoring_defects.py
    python scripts/scan_authoring_defects.py --status
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from authoring_defect_categories import CATEGORIES, category_for_rule, rule_ids_for_category

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent
_DEFAULT_SUBMISSIONS = _REPO_ROOT / "data" / "submissions"
_DEFAULT_LEDGER = _REPO_ROOT / "data" / "authoring_defect_ledger.json"
_DEFAULT_BANK = _REPO_ROOT / "data" / "authoring_example_bank.json"

SCHEMA_VERSION = 1
EXIT_PENDING = 3
_RULE_ID_RE = re.compile(r"L[RW]-\d+[A-Z-]*")
_STAGE2_FINDING_FILES = (
    "truth_findings.json",
    "ats_findings.json",
    "hm_findings.json",
    "mech_findings.json",
)
_RESOLVED_EDIT = "RESOLVED_EDIT"


def _utc_now() -> str:
    """Return an ISO-8601 UTC timestamp with a Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> Any | None:
    """Return parsed JSON or None if missing/malformed — never raise."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _occurrence_key(
    slug: str,
    stage: str,
    attempt: str | int,
    rule_id: str,
    doc: str,
    line: Any,
) -> str:
    """Stable idempotency key for one observed defect."""
    line_part = "" if line is None else str(line)
    return f"{slug}|{stage}|{attempt}|{rule_id}|{doc}|{line_part}"


def _stage1_occurrences(submissions_root: Path) -> list[dict]:
    """Collect mapped violations from every folder's verify_history.json."""
    rows: list[dict] = []
    if not submissions_root.is_dir():
        return rows
    for folder in sorted(p for p in submissions_root.iterdir() if p.is_dir()):
        history_path = folder / "stage1_first_draft" / "verify_history.json"
        loaded = _load_json(history_path)
        if not isinstance(loaded, list):
            continue
        slug = folder.name
        rel = history_path.as_posix()
        for entry in loaded:
            if not isinstance(entry, dict):
                continue
            attempt = entry.get("attempt", 1)
            observed_at = entry.get("observed_at") or ""
            digest = entry.get("rule_digest_version") or ""
            bank = entry.get("example_bank_version") or ""
            for v in entry.get("violations") or []:
                if not isinstance(v, dict):
                    continue
                rule_id = str(v.get("rule_id") or "")
                category = v.get("category") or category_for_rule(rule_id)
                if category not in CATEGORIES:
                    continue
                doc = str(v.get("doc") or "")
                line = v.get("line")
                rows.append(
                    {
                        "key": _occurrence_key(
                            slug, "stage1", attempt, rule_id, doc, line
                        ),
                        "slug": slug,
                        "category": category,
                        "rule_id": rule_id,
                        "stage": "stage1",
                        "doc": doc,
                        "line": line,
                        "observed_at": observed_at,
                        "rule_digest_version": digest,
                        "example_bank_version": bank,
                        "evidence_ref": rel,
                    }
                )
    return rows


def _extract_rule_id(finding: dict) -> str:
    """Pull an LR/LW rule id from a finding id or message (CR-097 Story 2.2)."""
    blob = " ".join(
        str(finding.get(k) or "") for k in ("id", "message", "rule_id")
    )
    matches = _RULE_ID_RE.findall(blob)
    return matches[-1] if matches else ""


def _stage2_occurrences(submissions_root: Path) -> list[dict]:
    """Collect RESOLVED_EDIT dispositions whose rule id maps to a target category."""
    rows: list[dict] = []
    if not submissions_root.is_dir():
        return rows
    for folder in sorted(p for p in submissions_root.iterdir() if p.is_dir()):
        reviews = folder / "reviews"
        disp = _load_json(reviews / "dispositions.json")
        if not isinstance(disp, dict):
            continue
        by_id = disp.get("by_finding_id") or {}
        if not isinstance(by_id, dict):
            continue
        slug = folder.name
        for fname in _STAGE2_FINDING_FILES:
            findings_path = reviews / fname
            payload = _load_json(findings_path)
            if not isinstance(payload, dict):
                continue
            for finding in payload.get("findings") or []:
                if not isinstance(finding, dict):
                    continue
                fid = str(finding.get("id") or "")
                if by_id.get(fid) != _RESOLVED_EDIT:
                    continue
                rule_id = _extract_rule_id(finding)
                category = category_for_rule(rule_id)
                if category not in CATEGORIES:
                    continue
                doc = str(finding.get("doc") or finding.get("document") or "")
                line = finding.get("line")
                rows.append(
                    {
                        "key": _occurrence_key(
                            slug, "stage2", 0, rule_id, doc, line
                        ),
                        "slug": slug,
                        "category": category,
                        "rule_id": rule_id,
                        "stage": "stage2",
                        "doc": doc,
                        "line": line,
                        "observed_at": str(payload.get("generated_at") or ""),
                        "rule_digest_version": "",
                        "example_bank_version": "",
                        "evidence_ref": findings_path.as_posix(),
                    }
                )
    return rows


def _merge_occurrences(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Keep existing rows; append incoming keys that are not already present."""
    seen = {row.get("key") for row in existing if isinstance(row, dict)}
    merged = [row for row in existing if isinstance(row, dict) and row.get("key")]
    for row in incoming:
        if row["key"] in seen:
            continue
        merged.append(row)
        seen.add(row["key"])
    return merged


def _open_reviews(occurrences: list[dict], reviews: list[dict]) -> list[dict]:
    """Append a pending_review when 2+ uncovered slugs share a category (SR-09)."""
    by_category: dict[str, set[str]] = {}
    for row in occurrences:
        cat = row.get("category")
        slug = row.get("slug")
        if cat in CATEGORIES and slug:
            by_category.setdefault(cat, set()).add(slug)

    next_reviews = [r for r in reviews if isinstance(r, dict)]
    for category, slugs in by_category.items():
        prior = [
            r
            for r in next_reviews
            if r.get("category") == category
            and r.get("status") in ("promoted", "declined")
        ]
        pending = [
            r
            for r in next_reviews
            if r.get("category") == category and r.get("status") == "pending_review"
        ]
        covered: set[str] = set()
        for r in prior:
            for s in r.get("distinct_slugs") or []:
                covered.add(s)
        uncovered = sorted(slugs - covered)
        if len(uncovered) < 2 or pending:
            continue
        next_reviews.append(
            {
                "id": f"R-{len(next_reviews) + 1:03d}",
                "category": category,
                "distinct_slugs": uncovered,
                "opened_at": _utc_now(),
                "status": "pending_review",
                "bank_entry_id": None,
                "resolution_note": None,
            }
        )
    return next_reviews


def _empty_ledger() -> dict:
    """Return a fresh ledger document."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "occurrences": [],
        "reviews": [],
    }


def scan_ledger(submissions_root: Path, ledger_path: Path) -> dict:
    """Scan submissions, update the ledger on disk, and return it.

    Missing or malformed per-folder files are skipped, never raised
    (same posture as fit_rubric_examples.load_few_shot_examples).
    """
    existing = _load_json(ledger_path)
    if not isinstance(existing, dict):
        existing = _empty_ledger()

    incoming = _stage1_occurrences(submissions_root) + _stage2_occurrences(
        submissions_root
    )
    occurrences = _merge_occurrences(existing.get("occurrences") or [], incoming)
    reviews = _open_reviews(occurrences, existing.get("reviews") or [])
    ledger = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "occurrences": occurrences,
        "reviews": reviews,
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return ledger


def pending_reviews(ledger: dict) -> list[dict]:
    """Return reviews still waiting on a human promote/decline decision."""
    return [
        r
        for r in (ledger.get("reviews") or [])
        if isinstance(r, dict) and r.get("status") == "pending_review"
    ]


def format_status(ledger: dict) -> str:
    """Printable --status body: each pending review plus evidence paths."""
    pending = pending_reviews(ledger)
    if not pending:
        return "No pending authoring-defect reviews."
    lines: list[str] = []
    occs = ledger.get("occurrences") or []
    for review in pending:
        slugs = ", ".join(review.get("distinct_slugs") or [])
        lines.append(
            f"{review.get('id')}  {review.get('category')}  slugs=[{slugs}]"
        )
        refs = sorted(
            {
                o.get("evidence_ref")
                for o in occs
                if o.get("category") == review.get("category")
                and o.get("slug") in set(review.get("distinct_slugs") or [])
                and o.get("evidence_ref")
            }
        )
        for ref in refs:
            lines.append(f"  evidence: {ref}")
    return "\n".join(lines)


def format_report(ledger: dict, last_n: int = 10) -> str:
    """Per-category occurrence counts for the N most recent first-draft slugs (SR-05)."""
    occs = [o for o in (ledger.get("occurrences") or []) if isinstance(o, dict)]
    by_slug: dict[str, str] = {}
    for row in occs:
        slug = row.get("slug") or ""
        when = row.get("observed_at") or ""
        if slug and (slug not in by_slug or when > by_slug[slug]):
            by_slug[slug] = when
    recent = sorted(by_slug, key=lambda s: by_slug[s], reverse=True)[:last_n]
    recent_set = set(recent)
    lines = [
        f"authoring-defect report - last {len(recent)} submission(s) by first-draft date:"
    ]
    if not recent:
        lines.append("(no verify_history occurrences yet)")
        return "\n".join(lines)
    lines.append("slugs: " + ", ".join(recent))
    for category in CATEGORIES:
        with_bank: list[str] = []
        without: list[str] = []
        for row in occs:
            if row.get("category") != category or row.get("slug") not in recent_set:
                continue
            slug = row.get("slug") or ""
            bank = str(row.get("example_bank_version") or "").strip()
            if bank:
                with_bank.append(slug)
            else:
                without.append(slug)
        lines.append(
            f"{category}: with-bank={len(with_bank)} {with_bank} "
            f"without-bank={len(without)} {without}"
        )
    return "\n".join(lines)


def format_summary(ledger: dict) -> str:
    """One-line default-scan summary."""
    n_occ = len(ledger.get("occurrences") or [])
    n_pending = len(pending_reviews(ledger))
    return (
        f"authoring-defect ledger: {n_occ} occurrence(s), "
        f"{n_pending} pending review(s)"
    )


def run_advisory_scan(
    submissions_root: Path | None = None,
    ledger_path: Path | None = None,
) -> int:
    """Scan and print; return pending count. Raises on unexpected errors.

    Called from the orchestrator inside try/except — never changes a
    submission's workflow status or exit code (CR-097 Story 2.5).
    """
    ledger = scan_ledger(
        submissions_root or _DEFAULT_SUBMISSIONS,
        ledger_path or _DEFAULT_LEDGER,
    )
    n_pending = len(pending_reviews(ledger))
    print(f"[defect_scan, status: ok] {n_pending} pending review(s)")
    return n_pending


def _applies_when_for(category: str) -> dict:
    """Default applies_when for a promoted skeleton (gap confession is conditional)."""
    if category == "gap_confession":
        return {"mode": "packet_condition", "condition": "soft_gaps_present"}
    return {"mode": "always"}


def _write_json(path: Path, payload: dict) -> None:
    """Write pretty JSON with a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def promote_review(
    review_id: str,
    *,
    ledger_path: Path | None = None,
    bank_path: Path | None = None,
) -> dict:
    """Append a TODO skeleton to the bank and mark the review promoted (Story 4.1).

    few_shot_eligible stays false — flipping it is a human edit.
    """
    ledger_path = ledger_path or _DEFAULT_LEDGER
    bank_path = bank_path or _DEFAULT_BANK
    ledger = _load_json(ledger_path)
    if not isinstance(ledger, dict):
        raise ValueError(f"ledger not found: {ledger_path}")
    review = next(
        (
            r
            for r in (ledger.get("reviews") or [])
            if isinstance(r, dict) and r.get("id") == review_id
        ),
        None,
    )
    if review is None:
        raise ValueError(f"review not found: {review_id}")
    if review.get("status") != "pending_review":
        raise ValueError(
            f"review {review_id} is {review.get('status')}, not pending_review"
        )

    category = str(review.get("category") or "")
    slugs = list(review.get("distinct_slugs") or [])
    entry_id = f"{category}-{_utc_now()[:10]}-{review_id.lower()}"
    entry = {
        "id": entry_id,
        "category": category,
        "rule_ids": rule_ids_for_category(category),
        "added_date": _utc_now()[:10],
        "source_slugs": slugs,
        "confirmed_by": "",
        "status": "active",
        "few_shot_eligible": False,
        "applies_when": _applies_when_for(category),
        "match_text": "TODO",
        "before": "TODO",
        "after": "TODO",
        "why": "TODO",
    }
    bank = _load_json(bank_path)
    if not isinstance(bank, dict):
        bank = {
            "schema_version": 1,
            "description": "",
            "categories": list(CATEGORIES),
            "entries": [],
        }
    entries = bank.get("entries")
    if not isinstance(entries, list):
        entries = []
        bank["entries"] = entries
    entries.append(entry)
    _write_json(bank_path, bank)

    review["status"] = "promoted"
    review["bank_entry_id"] = entry_id
    _write_json(ledger_path, ledger)
    print(f"PROMOTED {review_id} -> {bank_path} entry {entry_id}")
    print("few_shot_eligible is false until a human flips it.")
    for slug in slugs:
        print(f"  evidence slug: {slug}")
    return entry


def decline_review(
    review_id: str,
    note: str,
    *,
    ledger_path: Path | None = None,
) -> dict:
    """Mark a pending review declined with a required note (Story 4.1)."""
    if not (note or "").strip():
        raise ValueError("--decline requires --note")
    ledger_path = ledger_path or _DEFAULT_LEDGER
    ledger = _load_json(ledger_path)
    if not isinstance(ledger, dict):
        raise ValueError(f"ledger not found: {ledger_path}")
    review = next(
        (
            r
            for r in (ledger.get("reviews") or [])
            if isinstance(r, dict) and r.get("id") == review_id
        ),
        None,
    )
    if review is None:
        raise ValueError(f"review not found: {review_id}")
    review["status"] = "declined"
    review["resolution_note"] = note.strip()
    _write_json(ledger_path, ledger)
    print(f"DECLINED {review_id}: {note.strip()}")
    return review


def main(
    argv: list[str] | None = None,
    *,
    submissions_root: Path | None = None,
    ledger_path: Path | None = None,
) -> int:
    """CLI entry. --status exits 3 when anything is pending, 0 when clean."""
    parser = argparse.ArgumentParser(
        description="Scan Stage 1/2 authoring defects into a cross-submission ledger."
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print pending reviews (exit 3 if any, 0 if clean). Does not rescan.",
    )
    parser.add_argument(
        "--promote",
        metavar="REVIEW_ID",
        default=None,
        help="Append a TODO bank skeleton for this pending review (few_shot_eligible stays false).",
    )
    parser.add_argument(
        "--decline",
        metavar="REVIEW_ID",
        default=None,
        help="Mark this pending review declined. Requires --note.",
    )
    parser.add_argument(
        "--note",
        default="",
        help="Resolution note (required with --decline).",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print per-category counts for the most recent submissions (see --last).",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=10,
        metavar="N",
        help="With --report, how many recent submissions to include (default 10).",
    )
    args = parser.parse_args(argv)
    root = submissions_root or _DEFAULT_SUBMISSIONS
    path = ledger_path or _DEFAULT_LEDGER

    if args.promote and args.decline:
        print("ERROR: --promote and --decline are mutually exclusive.", file=sys.stderr)
        return 1
    if args.promote:
        promote_review(args.promote, ledger_path=path)
        return 0
    if args.decline:
        decline_review(args.decline, args.note, ledger_path=path)
        return 0

    if args.status:
        ledger = _load_json(path)
        if not isinstance(ledger, dict):
            ledger = _empty_ledger()
        print(format_status(ledger))
        return EXIT_PENDING if pending_reviews(ledger) else 0

    if args.report:
        ledger = _load_json(path)
        if not isinstance(ledger, dict):
            ledger = scan_ledger(root, path)
        print(format_report(ledger, last_n=max(1, args.last)))
        return 0

    ledger = scan_ledger(root, path)
    print(format_summary(ledger))
    pending = pending_reviews(ledger)
    if pending:
        print(format_status(ledger))
    return 0


if __name__ == "__main__":
    sys.exit(main())
