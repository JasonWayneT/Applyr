#!/usr/bin/env python3
"""CR-112 Story 3.3 — advisory evidence-swap report.

Reads evidence_selection_trace.json (never authoring_prompt.md). Writes
evidence_swap_report.json. Never rewrites Resume.md / CoverLetter.md /
authoring_packet.json. Never blocks finalize. Not wired into Stage 1/2/3.

Implements FR-304 / AC-401.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent

REASON_TO_LABEL = {
    "top2_cutoff": "SWAP_CANDIDATE",
    "project_slot_cap": "INTENTIONAL_TRADEOFF",
    "score_zero": "INSUFFICIENT_PROOF",
}


def label_candidate(candidate: dict[str, Any], picked: list[str]) -> str | None:
    """Map a TRACE candidate reason to a report label, or None if skipped."""
    cid = candidate.get("claim_id")
    reason = candidate.get("reason")
    if not isinstance(cid, str) or cid in picked:
        return None
    if reason in REASON_TO_LABEL:
        return REASON_TO_LABEL[reason]
    return None


def _null_row(
    item: dict[str, Any],
    *,
    label: str,
    reason: str | None,
) -> dict[str, Any]:
    """Build a report row with no claim attached."""
    return {
        "jd_item": item.get("jd_item"),
        "bucket": item.get("bucket"),
        "claim_id": None,
        "label": label,
        "reason": reason,
        "score": None,
        "rank": None,
        "attribution": None,
    }


def build_swap_report(trace: dict[str, Any]) -> dict[str, Any]:
    """Turn a Story 3.2 selection trace into an advisory swap report."""
    rows: list[dict[str, Any]] = []
    for item in trace.get("items") or []:
        if not isinstance(item, dict):
            continue
        picked = [c for c in (item.get("picked") or []) if isinstance(c, str)]
        candidates = item.get("candidates") or []
        item_filter = item.get("filter")
        if item_filter == "boilerplate_filtered" and not picked and not candidates:
            rows.append(
                _null_row(
                    item,
                    label="INTENTIONAL_TRADEOFF",
                    reason="boilerplate_filtered",
                )
            )
            continue
        if not picked and not candidates:
            rows.append(
                _null_row(item, label="PACKET_MISSING", reason=None)
            )
            continue
        for rank, cand in enumerate(candidates, start=1):
            if not isinstance(cand, dict):
                continue
            label = label_candidate(cand, picked)
            if not label:
                continue
            rows.append(
                {
                    "jd_item": item.get("jd_item"),
                    "bucket": item.get("bucket"),
                    "claim_id": cand.get("claim_id"),
                    "label": label,
                    "reason": cand.get("reason"),
                    "score": cand.get("score"),
                    "rank": rank,
                    "attribution": cand.get("attribution"),
                }
            )
    return {
        "schema_version": "1.0",
        "packet_version": trace.get("packet_version") or trace.get("slug"),
        "slug": trace.get("slug"),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI: write evidence_swap_report.json beside the trace. Return 0/1."""
    parser = argparse.ArgumentParser(
        description="Write an advisory swap report from evidence_selection_trace.json."
    )
    parser.add_argument("folder", help="Submission folder containing the trace file.")
    args = parser.parse_args(argv)
    folder = Path(args.folder)
    if not folder.is_dir():
        cand = _REPO_ROOT / "data" / "submissions" / args.folder
        folder = cand if cand.is_dir() else folder
    trace_path = folder / "evidence_selection_trace.json"
    if not trace_path.is_file():
        print(f"No evidence_selection_trace.json in {folder}", file=sys.stderr)
        return 1
    try:
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"unreadable trace: {exc}", file=sys.stderr)
        return 1
    if not isinstance(trace, dict):
        print("trace is not an object", file=sys.stderr)
        return 1
    report = build_swap_report(trace)
    out = folder / "evidence_swap_report.json"
    out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {out} ({len(report['rows'])} row(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
