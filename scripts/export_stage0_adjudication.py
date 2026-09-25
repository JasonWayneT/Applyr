#!/usr/bin/env python3
"""Export jason-marked adjudication rows to training_data_approved.csv.

Blank your_mark never means agreement. A blank mark cannot be written.
source=claude_review / source=agy cannot be written even when your_mark is
filled. Jason-approved Claude marks export as source=claude_opus_jason_approved,
not source=jason. Marked exportable count must equal written count. Implements FR-327 / AC-425.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_EXTRACT = _ROOT / "data" / "stage0_adjudication_8jd_extraction.csv"
_DEFAULT_OUT = _ROOT / "data" / "training_data_approved.csv"
_ALLOWED_MARKS = {
    "required",
    "preferred",
    "responsibilities",
    "culture",
    "junk",
}
# Keep in sync with retrain_stage0.FORBIDDEN_REVIEWERS.
FORBIDDEN_REVIEWERS = {
    "model",
    "llm",
    "harness",
    "fallback_api",
    "feedbackloop",
    "claude",
    "claude_review",
    "agy",
    "cursor",
    "xochitl",
}
ALLOWED_SOURCES = {
    "jason",
    "claude_opus_jason_approved",
}


class BlankMarkExportError(ValueError):
    """Raised when a blank your_mark would reach the approved training file."""


class NonJasonSourceExportError(ValueError):
    """Raised when a non-jason source row would reach the approved training file."""


def _exportable_marked_rows(path: Path) -> list[dict[str, str]]:
    """Return jason or claude_opus_jason_approved rows with a non-blank your_mark.

    claude_review / agy rows never export until rewritten to
    claude_opus_jason_approved. Implements FR-327.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    marked: list[dict[str, str]] = []
    for row in rows:
        mark = (row.get("your_mark") or "").strip()
        source = (row.get("source") or "").strip().casefold()
        if not mark:
            continue
        if source not in ALLOWED_SOURCES:
            continue
        marked.append(row)
    return marked


def approved_rows_from_marks(
    marked: list[dict[str, str]],
    *,
    reviewed_by: str,
    reviewed_at: str,
    out_name: str,
) -> list[dict[str, str]]:
    """Convert marked sheet rows to approved training rows. Hard-fail on blanks."""
    written: list[dict[str, str]] = []
    for row in marked:
        mark = (row.get("your_mark") or "").strip()
        if not mark:
            raise BlankMarkExportError(
                f"blank your_mark cannot reach {out_name} ({row.get('item_id')})"
            )
        if mark not in _ALLOWED_MARKS:
            raise ValueError(f"Invalid your_mark {mark!r} on {row.get('item_id')}")
        source = (row.get("source") or "").strip().casefold()
        if source not in ALLOWED_SOURCES:
            raise NonJasonSourceExportError(
                f"source={row.get('source')!r} cannot reach {out_name} "
                f"({row.get('item_id')}); export requires jason or "
                f"claude_opus_jason_approved"
            )
        written.append(
            {
                "text": (row.get("line") or "").strip(),
                "label": mark,
                "company": (row.get("slug") or "").strip(),
                "source_file": (row.get("item_id") or "").strip(),
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
                "suggestion_source": (row.get("source") or "").strip(),
            }
        )
    if any(not (row.get("label") or "").strip() for row in written):
        raise BlankMarkExportError(f"blank label cannot reach {out_name}")
    if len(written) != len(marked):
        raise BlankMarkExportError(
            f"marked count {len(marked)} != written count {len(written)}"
        )
    return written


def promote_claude_review_marks(path: Path) -> int:
    """Rewrite filled claude_review marks to claude_opus_jason_approved.

    Unmarked claude_review rows stay forbidden. Jason skip marks are not
    rewritten. Implements FR-327 / FR-339.
    """
    if not path.exists():
        return 0
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if not fieldnames:
        return 0
    changed = 0
    for row in rows:
        mark = (row.get("your_mark") or "").strip()
        source = (row.get("source") or "").strip()
        if mark and source == "claude_review":
            row["source"] = "claude_opus_jason_approved"
            changed += 1
    if changed:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    return changed


def export_approved(
    extract_csv: Path,
    out_csv: Path,
    *,
    reviewed_by: str = "jason",
    reviewed_at: str | None = None,
) -> list[dict[str, str]]:
    """Write only jason-marked extraction rows. Hard-fail on blank your_mark."""
    return export_approved_many(
        [extract_csv],
        out_csv,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
    )


def export_approved_many(
    extract_csvs: list[Path],
    out_csv: Path,
    *,
    reviewed_by: str = "jason",
    reviewed_at: str | None = None,
) -> list[dict[str, str]]:
    """Merge marked leftover CSVs into training_data_approved.csv. Implements FR-327."""
    reviewer = (reviewed_by or "").strip()
    if not reviewer or reviewer.casefold() in FORBIDDEN_REVIEWERS:
        raise ValueError("Export requires a human reviewed_by, not a model or harness")
    marked: list[dict[str, str]] = []
    for extract_csv in extract_csvs:
        marked.extend(_exportable_marked_rows(extract_csv))
    stamp = reviewed_at or datetime.now(timezone.utc).isoformat()
    written = approved_rows_from_marks(
        marked,
        reviewed_by=reviewer,
        reviewed_at=stamp,
        out_name=out_csv.name,
    )
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "text",
                "label",
                "company",
                "source_file",
                "reviewed_by",
                "reviewed_at",
                "suggestion_source",
            ],
        )
        writer.writeheader()
        writer.writerows(written)
    return written


def main() -> int:
    """Export marked extraction rows or fail closed."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extract",
        type=Path,
        nargs="+",
        default=[_DEFAULT_EXTRACT],
        help="One or more leftover extraction CSVs",
    )
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    parser.add_argument("--reviewed-by", default="jason")
    args = parser.parse_args()
    written = export_approved_many(args.extract, args.out, reviewed_by=args.reviewed_by)
    print(f"wrote {len(written)} marked rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
