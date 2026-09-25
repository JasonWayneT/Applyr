#!/usr/bin/env python3
"""Audit years_ceiling skips for the right number, not self-consistent arithmetic.

Implements TEST-114D / FR-332. A range gates on its low end. Age, company
history, and tenure are not experience floors. Remaining skips are flagged
when the winning figure is a range top, an age, or company history.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

from seniority_gate import check_years_gate, explain_years_requirement
from smoke_stage0_agy_archive import _clean_jd

_ARCHIVE_SUBMISSIONS = _ROOT / "data" / "archive" / "submissions"
_ARCHIVE_SKIPPED = _ROOT / "data" / "archive" / "skipped"
_PREFS = _ROOT / "data" / "candidate_preferences.json"
_PREFS_EXAMPLE = _ROOT / "data" / "candidate_preferences.example.json"
_REPORT_MD = _ROOT / "data" / "stage0_years_ceiling_audit.md"
_REPORT_CSV = _ROOT / "data" / "stage0_years_ceiling_audit.csv"
_BEFORE_CSV = _ROOT / "data" / "stage0_years_ceiling_audit.before.csv"
_FLIPS_MD = _ROOT / "data" / "stage0_years_ceiling_flips.md"

_SITTING_YEARS = (
    "civicplus",
    "realm_alliance",
    "aegon",
    "harbor_compliance",
    "csi",
    "sundayy",
    "actblue",
)


def load_years_prefs() -> dict:
    """Load experience_range from live prefs, then the example file."""
    for path in (_PREFS, _PREFS_EXAMPLE):
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError("candidate_preferences.json and example are both missing")


def iter_archive_jd_paths() -> list[tuple[str, list[Path]]]:
    """Return (slug, Original_JD.txt copies) from submissions and skipped."""
    found: dict[str, list[Path]] = {}
    for root in (_ARCHIVE_SUBMISSIONS, _ARCHIVE_SKIPPED):
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*/Original_JD.txt")):
            if "backup" in path.parent.name:
                continue
            found.setdefault(path.parent.name, []).append(path)
    return sorted(found.items())


def posting_url(path: Path) -> str:
    """Return the Original_JD URL header if present."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    first = raw.splitlines()[0] if raw else ""
    if first.startswith("URL: "):
        return first[5:].strip()
    return ""


def _row_from_explain(slug: str, path: Path, explained: dict) -> dict:
    """Build one audit row from an explain payload."""
    winning = [hit for hit in explained["hits"] if hit["value"] == explained["required"]]
    snippet = winning[0]["snippet"] if winning else ""
    flags = explained.get("wrong_number_flags") or []
    return {
        "slug": slug,
        "required": explained["required"],
        "candidate_max": explained["candidate_max"],
        "gate_passes": explained["gate_passes"],
        "wrong_number_flags": ";".join(flags),
        "inferred": explained["inferred"],
        "inferred_reasons": ";".join(explained["inferred_reasons"]),
        "winning_sources": ";".join(explained["winning_sources"]),
        "snippet": snippet,
        "url": posting_url(path),
        "path": str(path),
    }


def _prefer_skip_row(current: dict | None, candidate: dict) -> dict:
    """Keep a years-skip copy; prefer a wrong-number flag if both skip."""
    if current is None:
        return candidate
    if candidate["gate_passes"] and not current["gate_passes"]:
        return current
    if current["gate_passes"] and not candidate["gate_passes"]:
        return candidate
    if candidate["wrong_number_flags"] and not current["wrong_number_flags"]:
        return candidate
    return current


def audit_archive_years_ceiling(prefs: dict | None = None) -> dict:
    """Scan archived JDs and flag winning figures that are the wrong number."""
    prefs = prefs or load_years_prefs()
    max_years = ((prefs.get("experience_range") or {}).get("max"))
    skip_rows: list[dict] = []
    all_rows: list[dict] = []
    slug_paths = iter_archive_jd_paths()
    copy_count = sum(len(paths) for _slug, paths in slug_paths)
    for slug, paths in slug_paths:
        chosen: dict | None = None
        for path in paths:
            jd_text = _clean_jd(path.read_text(encoding="utf-8", errors="replace"))
            explained = explain_years_requirement(jd_text, prefs)
            candidate = _row_from_explain(slug, path, explained)
            chosen = _prefer_skip_row(chosen, candidate)
        if chosen is None:
            continue
        all_rows.append(chosen)
        if not chosen["gate_passes"]:
            skip_rows.append(chosen)
    wrong_number_rows = [row for row in skip_rows if row["wrong_number_flags"]]
    return {
        "candidate_max": max_years,
        "archive_jd_count": copy_count,
        "archive_slug_count": len(slug_paths),
        "years_ceiling_count": len(skip_rows),
        "wrong_number_rows": wrong_number_rows,
        "skip_rows": skip_rows,
        "all_rows": all_rows,
        "rows": skip_rows,
    }


def load_before_slugs(path: Path = _BEFORE_CSV) -> set[str]:
    """Load the pre-fix years_ceiling skip slug set."""
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["slug"] for row in csv.DictReader(handle) if row.get("slug")}


def years_flips(audit: dict, before_slugs: set[str] | None = None) -> list[dict]:
    """Return slugs that were years skips and now pass the years gate."""
    before_slugs = before_slugs if before_slugs is not None else load_before_slugs()
    by_slug = {row["slug"]: row for row in audit["all_rows"]}
    flips: list[dict] = []
    for slug in sorted(before_slugs):
        row = by_slug.get(slug)
        if row is None:
            continue
        if row["gate_passes"]:
            flips.append(row)
    return flips


def sitting_years_rows(prefs: dict | None = None) -> list[dict]:
    """Explain the years rows Jason asked about before skip-marking."""
    prefs = prefs or load_years_prefs()
    by_slug = dict(iter_archive_jd_paths())
    rows: list[dict] = []
    for slug in _SITTING_YEARS:
        paths = by_slug.get(slug)
        if not paths:
            rows.append({"slug": slug, "required": None, "gate_passes": None, "note": "JD missing"})
            continue
        path = paths[-1] if any("skipped" in str(item) for item in paths) else paths[0]
        for item in paths:
            if "skipped" in str(item):
                path = item
                break
        jd_text = _clean_jd(path.read_text(encoding="utf-8", errors="replace"))
        explained = explain_years_requirement(jd_text, prefs)
        row = _row_from_explain(slug, path, explained)
        rows.append(row)
    return rows


def render_report(audit: dict, flips: list[dict] | None = None) -> str:
    """Render the right-number years audit. Implements TEST-114D."""
    wrong = audit["wrong_number_rows"]
    flips = flips if flips is not None else years_flips(audit)
    lines = [
        "# years_ceiling right-number audit",
        "",
        "A range gates on its low end. Age, company history, and tenure are",
        "not experience floors. This scan asks whether the winning figure is",
        "the right number. Comparing the gate to its own parse is not a check.",
        "",
        f"- Archive JD copies scanned: {audit['archive_jd_count']}",
        f"- Unique slugs: {audit.get('archive_slug_count', audit['archive_jd_count'])}",
        f"- years_ceiling skips now: {audit['years_ceiling_count']}",
        f"- Wrong-number flags on remaining skips: {len(wrong)}",
        f"- Skip-to-pass flips vs pre-fix list: {len(flips)}",
        "",
        "## Wrong-number flags on remaining skips",
        "",
    ]
    if not wrong:
        lines.append("None. Remaining skips are not range-top, age, or company history.")
    else:
        lines.append("| slug | required | flags | sources | snippet |")
        lines.append("|---|---|---|---|---|")
        for row in wrong:
            lines.append(
                f"| `{row['slug']}` | {row['required']} | {row['wrong_number_flags']} | "
                f"{row['winning_sources']} | {row['snippet']} |"
            )
    lines.extend(["", "## Skip to Pass flips", ""])
    if not flips:
        lines.append("None.")
    else:
        lines.append("| slug | required now | url | snippet |")
        lines.append("|---|---|---|---|")
        for row in flips:
            url = row.get("url") or ""
            lines.append(
                f"| `{row['slug']}` | {row['required']} | {url} | {row['snippet']} |"
            )
    lines.append("")
    return "\n".join(lines)


def render_flips(flips: list[dict]) -> str:
    """Standalone flip list with posting URLs."""
    lines = [
        "# years_ceiling Skip-to-Pass flips",
        "",
        "Pre-fix years skips that now pass the years gate after the low-end",
        "range rule and age/history rejection. Other prefs codes may still skip.",
        "",
        f"Count: {len(flips)}",
        "",
        "| slug | parsed now | url |",
        "|---|---|---|",
    ]
    for row in flips:
        url = row.get("url") or "(no URL header)"
        lines.append(f"| `{row['slug']}` | {row['required']} | {url} |")
    lines.append("")
    return "\n".join(lines)


def write_reports(
    audit: dict,
    md_path: Path = _REPORT_MD,
    csv_path: Path = _REPORT_CSV,
    flips_path: Path = _FLIPS_MD,
) -> list[dict]:
    """Write markdown and CSV reports. Implements TEST-114D."""
    flips = years_flips(audit)
    md_path.write_text(render_report(audit, flips), encoding="utf-8")
    flips_path.write_text(render_flips(flips), encoding="utf-8")
    fieldnames = [
        "slug",
        "required",
        "candidate_max",
        "gate_passes",
        "wrong_number_flags",
        "inferred",
        "inferred_reasons",
        "winning_sources",
        "snippet",
        "url",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(audit["skip_rows"])
    return flips


def main() -> int:
    """Run the archive years_ceiling right-number audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write data/ reports")
    args = parser.parse_args()
    if not _ARCHIVE_SUBMISSIONS.is_dir() and not _ARCHIVE_SKIPPED.is_dir():
        print("VERIFY-YEARS-AUDIT: no archive JDs present; skipped")
        return 0
    audit = audit_archive_years_ceiling()
    flips = years_flips(audit)
    sitting = sitting_years_rows()
    print(
        f"VERIFY-YEARS-AUDIT: n_skip={audit['years_ceiling_count']} "
        f"max={audit['candidate_max']} wrong_number={len(audit['wrong_number_rows'])} "
        f"flips={len(flips)}"
    )
    for row in sitting:
        print(
            f"  sitting {row['slug']}: required={row.get('required')} "
            f"pass={row.get('gate_passes')} flags={row.get('wrong_number_flags')!r} "
            f"src={row.get('winning_sources')!r} snippet={row.get('snippet', '')[:80]!r}"
        )
    if args.write:
        write_reports(audit)
        print(f"  wrote {_REPORT_MD.name}, {_REPORT_CSV.name}, {_FLIPS_MD.name}")
    if audit["wrong_number_rows"]:
        for row in audit["wrong_number_rows"]:
            print(
                f"  [FAIL] {row['slug']} required={row['required']} "
                f"flags={row['wrong_number_flags']}"
            )
        return 1
    print("  [PASS] remaining years skips are not range-top, age, or company history")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
