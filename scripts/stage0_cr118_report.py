#!/usr/bin/env python3
"""CR-118 diagnostics: 41 full prefs, company-match history, in-office count, 30 replay.

No Groq/Gemini. Industry semantic is mocked fail-open so the keyword industry
gate still runs. Does not overwrite jason skip marks. Implements FR-337–FR-339.
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

from audit_years_ceiling import iter_archive_jd_paths, posting_url
from export_stage0_adjudication import promote_claude_review_marks
from seniority_gate import explain_years_requirement
from smoke_stage0_agy_archive import _clean_jd
from stage0_prefs_gate import _normalize_company_name, run_prefs_gate
from utils import load_candidate_preferences
from _harvest_adjudication_22 import SITTING_22, _jd_path

_SKIP_22 = _ROOT / "data" / "stage0_adjudication_22_skip.csv"
_SKIP_8 = _ROOT / "data" / "stage0_adjudication_8jd_skip.csv"
_EXTRACT_22 = _ROOT / "data" / "stage0_adjudication_22_extraction.csv"
_EXTRACT_8 = _ROOT / "data" / "stage0_adjudication_8jd_extraction.csv"
_FLIPS_MD = _ROOT / "data" / "stage0_years_ceiling_flips.md"
_BEFORE_CSV = _ROOT / "data" / "stage0_years_ceiling_audit.before.csv"
_SQLITE = _ROOT / "data" / "jobagent.sqlite"
_OUT_MD = _ROOT / "data" / "stage0_cr118_replay.md"
_OUT_CSV = _ROOT / "data" / "stage0_cr118_replay.csv"
_OUT_41 = _ROOT / "data" / "stage0_years_ceiling_full_prefs.md"

_INDUSTRY_PATCH = {
    "blocked_industry": "",
    "confidence": "high",
    "reasoning": "cr118-report-no-llm",
}

_JASON_REASON_WRONG = {
    "ss_c_technologies": (
        "5+ years of product management experience, with a focus on AI, "
        "plus build-and-launch. Not model training / AI-ML ownership."
    ),
    "aegon": (
        "Three office days a week in Philadelphia or Denver plus senior "
        "signals. Not the eight-year digital-experience and/or line."
    ),
}

_IN_OFFICE_RE = re.compile(
    r"(?is)"
    r"(?:"
    r"(?:\d+|two|three|four|five)\s*"
    r"(?:[-–]\s*(?:\d+|two|three|four|five))?\s*"
    r"days?\s+(?:a|per|/)\s*week.{0,70}"
    r"(?:office|on[- ]site|onsite|in[- ]office|hybrid)|"
    r"(?:hybrid|in[- ]office|on[- ]site|onsite|in\s+the\s+office).{0,50}"
    r"(?:\d+|two|three|four|five)\s*(?:[-–]\s*(?:\d+|two|three|four|five))?\s*"
    r"days?\s+(?:a|per|/)\s*week|"
    r"(?:must|required to|expected to|need to)\s+"
    r"(?:work|be|come|report).{0,40}"
    r"(?:in[- ](?:the[- ])?office|on[- ]site|onsite)\b"
    r")"
)
_IN_OFFICE_EXCLUDE_RE = re.compile(
    r"(?i)posted\s+\d+\s+days|updated\s+\d+\s+days|"
    r"sit,\s*walk,\s*stand|occasionally|periodically|as needed"
)
_OPTIONAL_OFFICE_RE = re.compile(
    r"(?i)\b(?:optional|optionally|flexible|from anywhere)\b",
)

_TITLE_RE = re.compile(r"(?i)^(?:job\s+)?(?:title|role|position)\s*:\s*(.+)$")
_COMPANY_LINE_RE = re.compile(r"(?i)^(?:company|employer)\s*:\s*(.+)$")


def _load_csv(path: Path) -> list[dict]:
    """Read a sitting CSV if present."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _company_from_slug(slug: str) -> str:
    """Folder slug as a company string. Implements FR-337 diagnostics."""
    return slug.replace("_", " ").strip()


_JUNK_TITLE = re.compile(
    r"(?i)^(about the (?:job|role|us|company|team)|who you are|overview|description)$"
)


def _title_from_jd(raw: str, cleaned: str) -> str:
    """Best-effort title from a JD header or first heading."""
    for line in raw.splitlines()[:25]:
        stripped = line.strip()
        match = _TITLE_RE.match(stripped)
        if match:
            return match.group(1).strip()[:160]
    for line in cleaned.splitlines()[:30]:
        stripped = line.strip(" #*")
        if _JUNK_TITLE.match(stripped):
            continue
        if 8 <= len(stripped) <= 120 and not stripped.lower().startswith("url:"):
            return stripped[:160]
    return ""


def _company_from_jd(raw: str, slug: str) -> str:
    """Prefer an explicit Company: line, else the slug."""
    for line in raw.splitlines()[:25]:
        match = _COMPANY_LINE_RE.match(line.strip())
        if match:
            return match.group(1).strip()[:160]
    return _company_from_slug(slug)


def _prefs_result(company: str, jd_text: str, prefs: dict) -> dict:
    """Full deterministic prefs gate with no paid industry LLM."""
    with patch(
        "industry_semantic.classify_industry_safe",
        return_value=_INDUSTRY_PATCH,
    ):
        return run_prefs_gate(company, jd_text, prefs)


def _old_blocked_kind(company: str, blocked: list) -> str:
    """Classify the pre-CR-118 substring matcher. blank / substring / exact / ''."""
    company_key = (company or "").strip().casefold()
    entries = [str(entry or "").strip().casefold() for entry in blocked if str(entry or "").strip()]
    if not company_key:
        return "blank" if entries else ""
    for entry_key in entries:
        if company_key == entry_key:
            return "exact"
        if company_key in entry_key or entry_key in company_key:
            return "substring"
    return ""


def _flip_slugs() -> list[str]:
    """Parse the 41 Skip-to-Pass years slugs from the flips report."""
    if not _FLIPS_MD.exists():
        return []
    slugs: list[str] = []
    for line in _FLIPS_MD.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\| `([^`]+)` \|", line)
        if match:
            slugs.append(match.group(1))
    return slugs


def _nsc_before(prefs: dict) -> dict:
    """What national_student_clearinghouse skipped on before the years fix."""
    out = {"years_before": "", "snippet": "", "years_now": "", "prefs_now": []}
    if _BEFORE_CSV.exists():
        for row in _load_csv(_BEFORE_CSV):
            if row.get("slug") == "national_student_clearinghouse":
                out["years_before"] = row.get("required") or ""
                out["snippet"] = (row.get("snippet") or "")[:240]
                out["winning_sources"] = row.get("winning_sources") or ""
                break
    try:
        path = _jd_path("national_student_clearinghouse")
    except FileNotFoundError:
        return out
    raw = path.read_text(encoding="utf-8", errors="replace")
    jd_text = _clean_jd(raw)
    explained = explain_years_requirement(jd_text, prefs)
    out["years_now"] = str(explained.get("required"))
    out["gate_passes"] = explained.get("gate_passes")
    company = _company_from_jd(raw, "national_student_clearinghouse")
    result = _prefs_result(company, jd_text, prefs)
    out["prefs_now"] = [item.get("code") for item in result.get("rejects") or []]
    out["passed_now"] = result.get("passed")
    return out


def _scan_41(prefs: dict) -> list[dict]:
    """Run the full prefs gate on every years Skip→Pass flip."""
    rows: list[dict] = []
    for slug in _flip_slugs():
        try:
            path = _jd_path(slug)
        except FileNotFoundError:
            rows.append(
                {
                    "slug": slug,
                    "passed": False,
                    "codes": ["missing_jd"],
                    "url": "",
                    "company": _company_from_slug(slug),
                    "title": "",
                }
            )
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        jd_text = _clean_jd(raw)
        company = _company_from_jd(raw, slug)
        result = _prefs_result(company, jd_text, prefs)
        codes = [item.get("code", "") for item in result.get("rejects") or []]
        rows.append(
            {
                "slug": slug,
                "passed": bool(result.get("passed")),
                "codes": codes,
                "url": posting_url(path),
                "company": company,
                "title": _title_from_jd(raw, jd_text),
            }
        )
    return rows


def _historical_company_counts(prefs: dict) -> dict:
    """Count past blocked_company hits from the old substring/blank matcher."""
    blocked = prefs.get("blocked_companies") or []
    archive_substring: list[str] = []
    archive_blank: list[str] = []
    for slug, paths in iter_archive_jd_paths():
        path = paths[0]
        raw = path.read_text(encoding="utf-8", errors="replace")
        company = _company_from_jd(raw, slug)
        kind = _old_blocked_kind(company, blocked)
        if kind == "substring":
            archive_substring.append(f"{slug} company={company!r}")
        elif kind == "blank":
            archive_blank.append(slug)
    ledger_substring: list[str] = []
    ledger_blank: list[str] = []
    if _SQLITE.exists():
        conn = sqlite3.connect(f"file:{_SQLITE.as_posix()}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT slug, company, skip_reason FROM stage0_skips"
            ).fetchall()
        except sqlite3.Error:
            rows = []
        finally:
            conn.close()
        for slug, company, reason in rows:
            kind = _old_blocked_kind(company or "", blocked)
            reason_ascii = (reason or "").encode("ascii", "replace").decode("ascii")
            label = f"{slug or ''} company={company!r} reason={reason_ascii!r}"
            if kind == "substring":
                ledger_substring.append(label)
            elif kind == "blank":
                ledger_blank.append(label)
    return {
        "archive_substring": archive_substring,
        "archive_blank": archive_blank,
        "ledger_substring": ledger_substring,
        "ledger_blank": ledger_blank,
    }


def _in_office_passing(prefs: dict) -> list[dict]:
    """Passing archived JDs whose posting requires regular in-office days."""
    hits: list[dict] = []
    for slug, paths in iter_archive_jd_paths():
        path = paths[0]
        raw = path.read_text(encoding="utf-8", errors="replace")
        jd_text = _clean_jd(raw)
        company = _company_from_jd(raw, slug)
        result = _prefs_result(company, jd_text, prefs)
        if not result.get("passed"):
            continue
        match = _IN_OFFICE_RE.search(jd_text)
        if not match:
            continue
        snippet = re.sub(r"\s+", " ", match.group(0)).strip()[:180]
        if _OPTIONAL_OFFICE_RE.search(snippet) or _IN_OFFICE_EXCLUDE_RE.search(snippet):
            continue
        hits.append({"slug": slug, "snippet": snippet, "url": posting_url(path)})
    return hits


def _replay_30(prefs: dict) -> list[dict]:
    """Replay sittings 1–3 with outcome and skip-reason agreement."""
    sitting8 = _load_csv(_SKIP_8)
    sitting22 = _load_csv(_SKIP_22)
    rows: list[dict] = []
    for sitting, source_rows, default_mark in (
        ("1", sitting8, "PASS"),
        ("2-3", sitting22, ""),
    ):
        marked_rows = source_rows
        if sitting == "2-3" and not marked_rows:
            marked_rows = [
                {"slug": slug, "your_mark": "", "source": "", "note": why}
                for slug, why in SITTING_22
            ]
        for item in marked_rows:
            slug = (item.get("slug") or "").strip()
            if not slug:
                continue
            mark = (item.get("your_mark") or "").strip().upper() or default_mark
            try:
                path = _jd_path(slug)
            except FileNotFoundError:
                rows.append(
                    {
                        "sitting": sitting,
                        "slug": slug,
                        "jason_mark": mark,
                        "gate": "missing_jd",
                        "codes": "missing_jd",
                        "flags": "",
                        "outcome_match": "no",
                        "reason_match": "no",
                        "note": "Original_JD.txt missing",
                    }
                )
                continue
            raw = path.read_text(encoding="utf-8", errors="replace")
            jd_text = _clean_jd(raw)
            company = _company_from_jd(raw, slug)
            result = _prefs_result(company, jd_text, prefs)
            codes = [row.get("code", "") for row in result.get("rejects") or []]
            flags = [row.get("code", "") for row in result.get("flags") or []]
            gate = "PASS" if result.get("passed") else "SKIP"
            if mark == "PASS":
                outcome_match = "yes" if gate == "PASS" else "no"
                reason_match = "n/a"
            elif mark == "SKIP":
                outcome_match = "yes" if gate == "SKIP" else "no"
                if slug in _JASON_REASON_WRONG:
                    reason_match = "no"
                else:
                    reason_match = "yes" if gate == "SKIP" else "no"
            else:
                outcome_match = "unmarked"
                reason_match = "unmarked"
            note = _JASON_REASON_WRONG.get(slug, item.get("note") or "")
            rows.append(
                {
                    "sitting": sitting,
                    "slug": slug,
                    "jason_mark": mark,
                    "gate": gate,
                    "codes": ",".join(codes) if codes else "",
                    "flags": ",".join(flags) if flags else "",
                    "outcome_match": outcome_match,
                    "reason_match": reason_match,
                    "note": note,
                }
            )
    return rows


def _render(
    flips: list[dict],
    nsc: dict,
    company_hist: dict,
    in_office: list[dict],
    replay: list[dict],
    promoted: dict[str, int],
) -> str:
    """Build the operator-facing CR-118 report."""
    full_pass = [row for row in flips if row["passed"]]
    still_skip = [row for row in flips if not row["passed"]]
    lines = [
        "# CR-118 replay and diagnostics",
        "",
        "Deterministic prefs only. Industry semantic mocked fail-open. "
        "No retrain, no production switch, jason skip marks untouched.",
        "",
        "## 41 years flips — full prefs",
        "",
        f"Years Skip→Pass: {len(flips)}. Full prefs PASS: {len(full_pass)}. "
        f"Still skipped by another code: {len(still_skip)}.",
        "",
        "### Now pass every gate",
        "",
    ]
    if not full_pass:
        lines.append("(none)")
    for row in full_pass:
        if row["url"]:
            lines.append(f"- `{row['slug']}` — {row['url']}")
        else:
            title = row["title"] or "(no title parsed)"
            lines.append(
                f"- `{row['slug']}` — no stored URL; company `{row['company']}`; title `{title}`"
            )
    lines.extend(["", "### Still skipped after the years fix", ""])
    if not still_skip:
        lines.append("(none)")
    for row in still_skip:
        lines.append(f"- `{row['slug']}` — {','.join(row['codes']) or 'unknown'}")
    lines.extend(
        [
            "",
            "## national_student_clearinghouse",
            "",
            f"- Years figure before the fix: `{nsc.get('years_before') or 'not in before CSV'}`",
            f"- Winning sources before: `{nsc.get('winning_sources') or ''}`",
            f"- Snippet: {nsc.get('snippet') or '(none)'}",
            f"- Years figure now: `{nsc.get('years_now')}` (gate_passes={nsc.get('gate_passes')})",
            f"- Full prefs now: {'PASS' if nsc.get('passed_now') else ','.join(nsc.get('prefs_now') or []) or 'SKIP'}",
            "",
            "## Past blocked_company false matches",
            "",
            "Old matcher: `entry in company` or `company in entry`, plus blank "
            "`\"\" in entry`. New matcher: exact normalized name, never blank.",
            "",
            f"- Archive slug/company substring (not exact): {len(company_hist['archive_substring'])}",
            f"- Archive blank company: {len(company_hist['archive_blank'])}",
            f"- Skip-ledger substring: {len(company_hist['ledger_substring'])}",
            f"- Skip-ledger blank: {len(company_hist['ledger_blank'])}",
            "",
        ]
    )
    for label, items in (
        ("Archive substring", company_hist["archive_substring"]),
        ("Archive blank", company_hist["archive_blank"]),
        ("Ledger substring", company_hist["ledger_substring"]),
        ("Ledger blank", company_hist["ledger_blank"]),
    ):
        if not items:
            continue
        lines.append(f"### {label}")
        lines.append("")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
    lines.extend(
        [
            "## Passing JDs that require regular in-office days",
            "",
            "Diagnostic only. No new gate. Count is among archived JDs that "
            "now pass the full deterministic prefs gate.",
            "",
            f"Count: {len(in_office)}",
            "",
        ]
    )
    for row in in_office:
        url = f" {row['url']}" if row["url"] else ""
        lines.append(f"- `{row['slug']}` — {row['snippet']}{url}")
    sitting1 = [row for row in replay if row["sitting"] == "1"]
    sitting23 = [row for row in replay if row["sitting"] == "2-3"]
    false_skips = [
        row for row in replay
        if row["jason_mark"] == "PASS" and row["gate"] == "SKIP"
    ]
    reason_mismatch = [row for row in replay if row["reason_match"] == "no"]
    lines.extend(
        [
            "",
            "## 30-JD replay (outcome + reason)",
            "",
            f"Sitting 1: {len(sitting1)}. Sittings 2–3: {len(sitting23)}. "
            f"False skips (PASS mark, gate SKIP): {len(false_skips)}. "
            f"Reason mismatches: {len(reason_mismatch)}.",
            "",
            "| sitting | slug | jason | gate | codes | flags | outcome | reason |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for row in replay:
        lines.append(
            f"| {row['sitting']} | `{row['slug']}` | {row['jason_mark']} | "
            f"{row['gate']} | {row['codes'] or '—'} | {row['flags'] or '—'} | "
            f"{row['outcome_match']} | {row['reason_match']} |"
        )
    lines.extend(
        [
            "",
            "### Reason-mismatch notes",
            "",
        ]
    )
    for slug, note in _JASON_REASON_WRONG.items():
        match = next((row for row in replay if row["slug"] == slug), None)
        codes = match["codes"] if match else ""
        lines.append(f"- `{slug}` gate codes `{codes}`. Jason: {note}")
    lines.extend(
        [
            "",
            "## Extraction source rewrite",
            "",
            f"- sitting 1 extract `claude_review` → `claude_opus_jason_approved`: {promoted.get('8', 0)}",
            f"- sitting 22 extract: {promoted.get('22', 0)}",
            "",
            "Skip CSV `source=jason` was not rewritten.",
            "",
        ]
    )
    change_path = _ROOT / "data" / "stage0_adjudication_22_heading_changes.csv"
    heading_rows = _load_csv(change_path)
    lines.extend(
        [
            "## Harvest heading changes",
            "",
            f"Lines whose inherited heading changed after the preferred-header fix: {len(heading_rows)}",
            "",
        ]
    )
    if not heading_rows:
        lines.append("(none)")
    for row in heading_rows:
        line = (row.get("line") or "")[:140]
        lines.append(
            f"- `{row.get('item_id')}` `{row.get('old_header')}` → `{row.get('new_header')}` — {line}"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    """Write CR-118 diagnostics. Never overwrite jason skip marks."""
    prefs = load_candidate_preferences()
    promoted = {
        "8": promote_claude_review_marks(_EXTRACT_8),
        "22": promote_claude_review_marks(_EXTRACT_22),
    }
    flips = _scan_41(prefs)
    nsc = _nsc_before(prefs)
    company_hist = _historical_company_counts(prefs)
    in_office = _in_office_passing(prefs)
    replay = _replay_30(prefs)
    _OUT_MD.write_text(
        _render(flips, nsc, company_hist, in_office, replay, promoted),
        encoding="utf-8",
    )
    with _OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "sitting",
                "slug",
                "jason_mark",
                "gate",
                "codes",
                "flags",
                "outcome_match",
                "reason_match",
                "note",
            ],
        )
        writer.writeheader()
        writer.writerows(replay)
    full_pass = [row for row in flips if row["passed"]]
    pass_lines = ["# Years flips that now pass every prefs gate", ""]
    for row in full_pass:
        if row["url"]:
            pass_lines.append(f"- `{row['slug']}` {row['url']}")
        else:
            pass_lines.append(
                f"- `{row['slug']}` no URL; {row['company']} / {row['title'] or '(no title)'}"
            )
    _OUT_41.write_text("\n".join(pass_lines) + "\n", encoding="utf-8")
    print(f"41 flips: {len(flips)} full-pass: {len(full_pass)}")
    print(f"in-office passing: {len(in_office)}")
    print(
        "company substring archive/ledger: "
        f"{len(company_hist['archive_substring'])}/{len(company_hist['ledger_substring'])}"
    )
    print(f"replay rows: {len(replay)} promoted_extract: {promoted}")
    print(f"  {_OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
