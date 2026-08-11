#!/usr/bin/env python3
"""
Eval Stage 0 boilerplate filtering against archived (and live) Original_JD.txt files.

Compares legacy extraction (no ignore-headers / no item denylist) vs current
`_extract_sections`, scoring how much ATS/policy junk leaves the required+preferred
buckets and whether hire-looking lines were over-filtered.

Usage:
    python scripts/eval_stage0_boilerplate.py
    python scripts/eval_stage0_boilerplate.py --roots data/archive/submissions data/submissions
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from build_stage0_fit_gate import (  # noqa: E402
    _IGNORE_SECTION_HEADERS,
    _SECTION_HEADERS,
    _extract_sections,
    _is_boilerplate_item,
    _normalize_jd_punctuation,
)

# Independent junk detector for measurement (superset of the filter's intent).
_JUNK_SCORE_RE = re.compile(
    r"(?i)(?:"
    r"relocation|"
    r"pinflex|"
    r"equal\s+opportunity|"
    r"commitment\s+to\s+inclusion|"
    r"without\s+regard\s+to\s+race|"
    r"us[\s-]?based\s+applicants|"
    r"by\s+submitting\s+this\s+application|"
    r"base\s+salary|"
    r"discretionary\s+bonus|"
    r"annual\s+base\s+salary|"
    r"eligible\s+for\s+equity|"
    r"#li-|"
    r"in-?office\s+requirement|"
    r"protected\s+veteran|"
    r"\$[\d,]+\s*[—–\-to]+\s*\$[\d,]+|"
    r"benefits\s+available\s+for\s+this\s+position|"
    r"information\s+regarding\s+the\s+culture|"
    r"dice\s+id|"
    r"create\s+job\s+alert|"
    r"search\s+all\s+similar\s+jobs|"
    r"our\s+interview\s+process|"
    r"gone\s+through\s+the\s+interview\s+process|"
    r"during\s+the\s+interview\s+process|"
    r"completed\s+interview\s+process|"
    r"hiring\s+and\s+interview\s+process"
    r")"
)

# Lines that look like real hire criteria — used to spot false positives.
_HIRE_SIGNAL_RE = re.compile(
    r"(?i)(?:"
    r"\d\+?\s*years?|"
    r"product\s+manag|"
    r"bachelor|master\b|degree|"
    r"experience\s+(?:with|in|building|leading)|"
    r"roadmap|backlog|stakeholder|agile|scrum|"
    r"ai/?ml|machine\s+learning|"
    r"sql|api|saas|b2b|"
    r"priorit|"
    r"cross[-\s]?functional"
    r")"
)


def _extract_sections_legacy(jd_text: str) -> dict[str, list[str]]:
    """Pre-filter extraction (headers only, no ignore/denylist)."""
    buckets: dict[str, list[str]] = {
        "required": [],
        "preferred": [],
        "responsibilities": [],
        "culture": [],
    }
    lines = _normalize_jd_punctuation(jd_text).splitlines()
    current_bucket: str | None = None
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        matched_bucket: str | None = None
        for bucket_name, header_re in _SECTION_HEADERS:
            if header_re.match(line):
                matched_bucket = bucket_name
                break
        if matched_bucket is not None:
            current_bucket = matched_bucket
            continue
        if current_bucket is None:
            continue
        clean = line.lstrip("-•*◦▪▸→").strip()
        if 15 <= len(clean) <= 300 and (clean[0].isalnum() or clean[0] in "\"'"):
            buckets[current_bucket].append(clean)
    return buckets


def _quals(buckets: dict[str, list[str]]) -> list[str]:
    return list(buckets.get("required") or []) + list(buckets.get("preferred") or [])


def _junk_items(items: list[str]) -> list[str]:
    return [x for x in items if _JUNK_SCORE_RE.search(x)]


def _hire_looking(items: list[str]) -> list[str]:
    return [x for x in items if _HIRE_SIGNAL_RE.search(x)]


def _iter_jds(roots: list[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("Original_JD.txt")):
            key = str(path.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(path)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roots",
        nargs="+",
        default=[
            "data/archive/submissions",
            "data/submissions",
            "data/authored_drafts",
            "data/pending_review",
        ],
        help="Directories to scan for Original_JD.txt",
    )
    parser.add_argument(
        "--json-out",
        default="data/reports/stage0_boilerplate_eval.json",
        help="Write full per-file findings here",
    )
    parser.add_argument("--top", type=int, default=25, help="Print top N residual / FP cases")
    args = parser.parse_args(argv)

    roots = [Path(r) for r in args.roots]
    paths = _iter_jds(roots)
    if not paths:
        print("No Original_JD.txt files found under:", roots)
        return 1

    summary = {
        "n_files": len(paths),
        "legacy_junk_items": 0,
        "filtered_junk_items": 0,
        "legacy_qual_items": 0,
        "filtered_qual_items": 0,
        "files_with_legacy_junk": 0,
        "files_with_residual_junk": 0,
        "false_positive_removals": 0,
        "files_emptied_required": 0,
        "residual": [],
        "false_positives": [],
        "cleared_examples": [],
    }

    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        legacy = _extract_sections_legacy(text)
        current = _extract_sections(text)
        leg_q = _quals(legacy)
        cur_q = _quals(current)
        leg_junk = _junk_items(leg_q)
        cur_junk = _junk_items(cur_q)

        summary["legacy_qual_items"] += len(leg_q)
        summary["filtered_qual_items"] += len(cur_q)
        summary["legacy_junk_items"] += len(leg_junk)
        summary["filtered_junk_items"] += len(cur_junk)
        if leg_junk:
            summary["files_with_legacy_junk"] += 1
        if cur_junk:
            summary["files_with_residual_junk"] += 1
            summary["residual"].append(
                {
                    "path": str(path).replace("\\", "/"),
                    "junk": cur_junk[:8],
                    "required_n": len(current.get("required") or []),
                }
            )

        removed = [x for x in leg_q if x not in cur_q]
        # True FP concern: long hire-criteria bullets removed, not junk/chrome.
        fp_review = [
            x
            for x in removed
            if _hire_looking([x])
            and not _is_boilerplate_item(x)
            and not _JUNK_SCORE_RE.search(x)
            and len(x) >= 60
            and re.search(r"(?i)(?:\d\+?\s*years?|experience|bachelor|degree|responsib)", x)
        ]
        if fp_review:
            summary["false_positive_removals"] += len(fp_review)
            summary["false_positives"].append(
                {
                    "path": str(path).replace("\\", "/"),
                    "removed": fp_review[:6],
                }
            )

        leg_req_real = [x for x in (legacy.get("required") or []) if not _is_boilerplate_item(x)]
        if leg_req_real and not (current.get("required") or []):
            summary["files_emptied_required"] += 1

        if leg_junk and not cur_junk:
            summary["cleared_examples"].append(
                {
                    "path": str(path).replace("\\", "/"),
                    "cleared_n": len(leg_junk),
                    "sample": leg_junk[:3],
                }
            )

    legacy_junk = summary["legacy_junk_items"]
    filtered_junk = summary["filtered_junk_items"]
    cleared = legacy_junk - filtered_junk
    rate = (cleared / legacy_junk) if legacy_junk else 1.0

    print(f"files scanned:              {summary['n_files']}")
    print(f"qual items (legacy->now):    {summary['legacy_qual_items']} -> {summary['filtered_qual_items']}")
    print(f"junk-in-quals (legacy->now): {legacy_junk} -> {filtered_junk}  (cleared {cleared}, {rate:.1%})")
    print(f"files with junk (leg->now):  {summary['files_with_legacy_junk']} -> {summary['files_with_residual_junk']}")
    print(f"hire-looking removals:      {summary['false_positive_removals']} item(s) across {len(summary['false_positives'])} files")
    print(f"required emptied (nonempty→empty): {summary['files_emptied_required']}")

    print(f"\n--- top residual junk (n={min(args.top, len(summary['residual']))}) ---")
    for row in summary["residual"][: args.top]:
        print(f"* {row['path']}")
        for j in row["junk"][:3]:
            print(f"    - {j[:140]}")

    print(f"\n--- top hire-looking removals (n={min(args.top, len(summary['false_positives']))}) ---")
    for row in summary["false_positives"][: args.top]:
        print(f"* {row['path']}")
        for j in row["removed"][:3]:
            print(f"    - {j[:140]}")

    print(f"\n--- sample cleared (n={min(10, len(summary['cleared_examples']))}) ---")
    for row in summary["cleared_examples"][:10]:
        print(f"* {row['path']} cleared={row['cleared_n']}")
        for j in row["sample"]:
            print(f"    - {j[:120]}")

    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Keep JSON lean: truncate long lists
    dump = dict(summary)
    dump["residual"] = summary["residual"][:100]
    dump["false_positives"] = summary["false_positives"][:100]
    dump["cleared_examples"] = summary["cleared_examples"][:50]
    dump["clear_rate"] = rate
    out_path.write_text(json.dumps(dump, indent=2), encoding="utf-8")
    print(f"\nwrote {out_path}")

    # Soft confidence gate: residual junk rare, no real required-section wipe,
    # and almost no long hire-criteria bullets removed.
    ok = (
        summary["files_emptied_required"] == 0
        and filtered_junk <= max(2, int(0.05 * max(legacy_junk, 1)))
        and summary["false_positive_removals"] <= max(5, int(0.01 * max(summary["legacy_qual_items"], 1)))
        and rate >= 0.90
    )
    print("confidence_gate:", "PASS" if ok else "FAIL")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
