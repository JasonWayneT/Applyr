#!/usr/bin/env python3
"""Emit and resolve CR-108 Review Center confirmations for agent harnesses."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from stage0_confirmations import (
    answer_confirmation,
    answer_hard_gate_review,
    list_open_confirmations,
)


def question_envelope(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Build the shared machine-readable question envelope from grouped rows."""
    if not rows:
        return None
    first = rows[0]
    question_type = str(first.get("question_type") or "")
    if question_type == "hard_gate_review":
        question_name = "stage0_hard_gate_review"
        options = ["KEEP_ELIGIBLE", "CONFIRM_HARD", "NEEDS_MORE_INFO"]
    else:
        question_name = "stage0_skill_confirmation"
        # Implements FR-287: BAD_DATA flags an extraction false positive so the
        # candidate is never asked again (durable bad-data learning loop).
        options = ["CONFIRMED_USE", "NOT_PRESENT", "UNSURE_NO_REASK", "BAD_DATA"]
    affected = list(dict.fromkeys(str(row["opportunity_key"]) for row in rows))
    envelope: dict[str, Any] = {
        "type": question_name,
        "question_type": question_type,
        "confirmation_id": str(first["id"]),
        "review_key": str(first["review_key"]),
        "question": str(first["question"]),
        "affected_opportunities": affected,
        "options": options,
    }
    if first.get("skill_key"):
        envelope["skill_key"] = str(first["skill_key"])
        envelope["evidence_requested"] = question_type == "skill_presence"
    if first.get("requirement"):
        envelope["requirement"] = str(first["requirement"])
    return envelope


def next_question(db_path: str | Path | None) -> dict[str, Any] | None:
    """Return the oldest open grouped question for an agent harness."""
    rows = list_open_confirmations(db_path)
    if not rows:
        return None
    review_key = rows[0]["review_key"]
    return question_envelope([row for row in rows if row["review_key"] == review_key])


def _parse_details(raw: str | None) -> dict[str, Any]:
    """Parse optional evidence details from a JSON object argument."""
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("--details-json must contain a JSON object")
    return value


def _main() -> int:
    """Run the harness question or answer command."""
    parser = argparse.ArgumentParser(description="Applyr Stage 0 Review Center harness adapter")
    parser.add_argument("--db", default=None, help="Optional SQLite path for tests or diagnostics")
    subparsers = parser.add_subparsers(dest="command", required=True)
    next_parser = subparsers.add_parser("next", help="Emit the oldest open question as JSON")
    next_parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    answer_parser = subparsers.add_parser("answer", help="Resolve a question through the shared store")
    answer_parser.add_argument("--review-key", required=True)
    answer_parser.add_argument("--answer", required=True)
    answer_parser.add_argument("--details-json", default=None)
    answer_parser.add_argument("--promote-to-verified-evidence", action="store_true")
    args = parser.parse_args()

    try:
        if args.command == "next":
            question = next_question(args.db)
            print(json.dumps(question, ensure_ascii=False, indent=2 if args.pretty else None))
            return 0
        if args.answer in {"KEEP_ELIGIBLE", "CONFIRM_HARD", "NEEDS_MORE_INFO"}:
            result = answer_hard_gate_review(
                db_path=args.db,
                review_key=args.review_key,
                answer=args.answer,
            )
        else:
            result = answer_confirmation(
                db_path=args.db,
                review_key=args.review_key,
                answer=args.answer,
                details=_parse_details(args.details_json),
                promote_to_verified_evidence=args.promote_to_verified_evidence,
            )
        print(json.dumps({"success": True, "status": result.status}))
        return 0
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.exit(_main())
