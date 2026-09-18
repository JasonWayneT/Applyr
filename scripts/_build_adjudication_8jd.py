#!/usr/bin/env python3
"""Build the first-slice CR-114 adjudication sheet from the 8-JD Agy cache.

Not gold. your_mark blank means unmarked, never agreement. Agy is a draft.
Claude review hints are source=claude_review and are not jason marks.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

from evidence_scale import build_evidence_context, retrieval_coverage
from smoke_stage0_agy_archive import (
    _CACHE,
    _EVIDENCE_EXCERPT_CHARS,
    _WORK_EXP,
)

OUT_MD = _ROOT / "data" / "stage0_adjudication_8jd.md"
OUT_CSV = _ROOT / "data" / "stage0_adjudication_8jd_extraction.csv"
OUT_EV = _ROOT / "data" / "stage0_adjudication_8jd_evidence.csv"
OUT_SKIP = _ROOT / "data" / "stage0_adjudication_8jd_skip.csv"

_VISA_TRAVEL_RE = re.compile(
    r"(?i)visa|sponsor|work authoriz|citizenship|travel\s*:|%\s*travel|"
    r"travel may be required|\bup to\s+\d+%\s+travel"
)
_WINDOW_TOKENS = ("agentic", "ai-built", "claude", "llm", "mcp")
_SKIP_RULE = (
    "Skip at Stage 0 when a prefs / exclusion-zone gate fires. That includes "
    "a hard unhedged years-in-industry requirement or explicit early-career "
    "language; the solo / founding PM trap; 0-to-1 / greenfield / build-from-scratch "
    "as implemented in stage0_prefs_gate._ZERO_TO_ONE_RE (not 'ship MVPs' or "
    "'build an OS'); people management; revenue/billing ownership; AI/ML model "
    "training or ownership; blocked company, industry, or title; and the travel "
    "ceiling. Exclusion zones are skip-eligible at Stage 0. They are that gate, "
    "not a sheet-only rule. Do not skip on over-qualification, a soft industry "
    "gap, or an authoring overclaim (a required line that cannot go on a resume) "
    "unless that line already matches an exclusion-zone pattern. Visa/travel "
    "leftover being junk is not the skip decision."
)

# Claude-relayed bucket corrections from the prior review. Not jason gold.
_CLAUDE_EXTRACT: list[tuple[str, str, str]] = [
    ("cannot leave it alone", "culture", "disposition, not a credential"),
    ("vibe codes prototypes", "culture", "work-style, not a gate"),
    ("tries every new ai tool", "culture", "habit, not a gate"),
    ("loves storytelling", "culture", "enthusiasm, not a checkable skill"),
    ("excited to work in a startup", "culture", "culture-fit, not a requirement"),
    ("curiosity and building instinct", "culture", "trait, not a requirement"),
    ("user empathy:", "culture", "value/orientation, not a hard-gated skill"),
    ("has shipped ai-enabled products", "required", "checkable shipped credential"),
    ("has been building with llms", "required", "checkable builder credential"),
    ("agentic fluency:", "required", "checkable daily agent practice"),
    ("written communication: a core requirement", "required", "explicit core requirement"),
    ("technical depth: working knowledge", "required", "checkable working knowledge"),
    ("ai and automation: hands-on", "required", "checkable hands-on tools"),
    ("stakeholder management: a track record", "required", "checkable track record"),
    (
        "recognized as an expert in product adoption",
        "required",
        "qualification, not a duty",
    ),
    ("drives research into adoption", "responsibilities", "duty verb"),
]

# Jason named these in sitting 1. your_mark is filled. Implements FR-327.
_JASON_EXTRACT: list[tuple[str, str, str]] = [
    (
        "competency in using sql, looker",
        "preferred",
        "line says is a plus",
    ),
    (
        "strong desire for fostering inclusivity",
        "culture",
        "disposition, not a credential",
    ),
    (
        "interest in progressive politics",
        "culture",
        "politics/values, not a skill",
    ),
    (
        "equivalent combination of education",
        "junk",
        "relaxes a requirement rather than being one. nothing scorable.",
    ),
    (
        "discover the opportunity to grow your career here",
        "junk",
        "employer-brand boilerplate. interchangeable. never a hook.",
    ),
    (
        "health data & interoperability solutions",
        "junk",
        "board taxonomy fragment, not hook material.",
    ),
    (
        "enjoy unpacking complex problems",
        "culture",
        "disposition, not a credential",
    ),
    (
        "attention to detail for the design and usability",
        "culture",
        "trait-without-duty, not a checkable qualification",
    ),
]

# Sitting-1 evidence overrides Jason named. Not a gold set for the other rows.
_JASON_EVIDENCE: dict[str, tuple[str, str]] = {
    "acquia:req:3": (
        "4",
        "ACC-119 names Confluence and Jira; ACC-108 Jira priority-score. such as is illustrative.",
    ),
    "acquia:req:0": (
        "3",
        "WE line 254 / ACC-109 quarterly roadmap to 200-300 including CEOs. briefing is not decision-making.",
    ),
    "accuity:req:0": (
        "drop",
        "heading double-counts the BBA already at accuity:req:1.",
    ),
    "1uphealth:req:0": (
        "drop",
        "board metadata, not a requirement.",
    ),
    "1uphealth:req:2": (
        "drop",
        "severed clause, not a standalone requirement.",
    ),
    "accertify:req:1": (
        "1",
        "flat 0 contradicts 1uphealth:req:2 scoring 2 off the same API evidence.",
    ),
}


def _parse_review_leftovers(path: Path) -> list[dict]:
    """Read the v2 leftover set Jason already reviewed. Implements FR-328."""
    text = path.read_text(encoding="utf-8")
    marker = "== All leftover extraction labels =="
    body = text.split(marker, 1)[-1]
    pattern = re.compile(
        r"^- \[([^\]]+)\] header=(['\"])(.*)\2 agy=(\S+) :: (.*)$",
        re.M,
    )
    rows: list[dict] = []
    counts: dict[str, int] = {}
    for match in pattern.finditer(body):
        slug, _quote, header, agy, line = match.groups()
        idx = counts.get(slug, 0)
        counts[slug] = idx + 1
        rows.append(
            {
                "slug": slug,
                "item_id": f"{slug}:e{idx}",
                "header": header,
                "line": line,
                "agy_draft": agy,
            }
        )
    return rows


def _parse_review_evidence_lines(path: Path) -> dict[str, str]:
    """Map item_id to JD line from the human review packet."""
    text = path.read_text(encoding="utf-8")
    found: dict[str, str] = {}
    pattern = re.compile(r"^- \[([a-z0-9_]+:(?:req|pref):\d+)\] :: (.*)$", re.M | re.I)
    for item_id, line in pattern.findall(text):
        found[item_id] = line
    return found


def _load_all_evidence_cache() -> dict[str, dict]:
    """Newest evidence cache row per item_id. Schema bumps change keys."""
    by_id: dict[str, dict] = {}
    files = sorted(_CACHE.glob("evidence-*.json"), key=lambda path: path.stat().st_mtime)
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("results") or []:
            item_id = str(row.get("item_id") or "")
            if item_id:
                by_id[item_id] = row
    return by_id


_KNOWN_EVIDENCE_LINES = {
    "1uphealth:req:0": "Mid and Senior level",
    "1uphealth:req:2": "experiences that involve data, APIs and/or systems",
    "accuity:req:0": "Education and Credentials",
    "accuity:req:1": (
        "Bachelor's degree in business, healthcare administration, technology, "
        "analytics, product management, or a related field preferred."
    ),
    "acquia:pref:0": (
        "Hands-on experience building or shipping with AI agents, LLM applications, "
        "or agentic coding tools, as a builder and not only an observer"
    ),
    "acquia:req:3": "Proficiency with product management tools such as Jira, Confluence, and Aha!.",
}


def _line_from_reasoning(reasoning: str) -> str:
    """Pull the quoted JD requirement, not a work-history excerpt."""
    text = reasoning or ""
    match = re.search(
        r"(?:preferred )?requirement\s+"
        r"(?:asks for|calls for|specifies|lists|seeks|requests|is for)\s+"
        r"'([^']{8,240})'",
        text,
        re.I,
    )
    if match:
        return match.group(1)
    skip = re.compile(
        r"(?i)not a 0-to-1|within a larger|bachelor of business|"
        r"data integrity & ingestion|pendo certification"
    )
    for quote in re.findall(r"'([^']{8,240})'", text):
        if not skip.search(quote):
            return quote
    return ""


def _is_heading_or_fragment(line: str) -> bool:
    """JD chrome/heading/truncated fragment named in sitting 1. Implements FR-330."""
    lower = (line or "").strip().lower()
    return lower in {
        "education and credentials",
        "mid and senior level",
        "experiences that involve data, apis and/or systems",
    }


def _level(row: dict) -> int | None:
    """Coerce Agy evidence_level for stratified sampling."""
    raw = row.get("agy_level", row.get("level"))
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _window_ok(line: str, excerpt: str) -> bool:
    """False only on an AI/LLM/agent/MCP line whose excerpt lacks those tokens."""
    ai_line = bool(re.search(r"\b(ai|llm|agentic|mcp)\b", line or "", re.I))
    if not ai_line:
        return True
    excerpt_low = (excerpt or "").lower()
    return any(token in excerpt_low for token in _WINDOW_TOKENS)


def _extract_row(line: str, agy: str) -> tuple[str, str, str, str]:
    """Return agy_proposed, status, source, note. Blank your_mark unless jason."""
    lower = (line or "").lower()
    for needle, bucket, note in _JASON_EXTRACT:
        if needle in lower:
            return bucket, "JASON_MARK", "jason", note
    if _VISA_TRAVEL_RE.search(line or ""):
        return (
            "junk",
            "JASON_MARK",
            "jason",
            "logistics; prefs/location gate already skips. not scored.",
        )
    for needle, bucket, note in _CLAUDE_EXTRACT:
        if needle in lower:
            return (
                bucket,
                "CLAUDE_HINT",
                "claude_review",
                note + " Fill your_mark to confirm or override. Not jason gold.",
            )
    return agy or "", "NEEDS_MARK", "agy", ""


def _sample_evidence(rows: list[dict]) -> list[dict]:
    """Pick evidence across levels, req/pref, window-risk, and heading/fragment."""
    picked: list[dict] = []
    seen: set[str] = set()

    def add(row: dict, sample_class: str) -> None:
        item_id = str(row.get("item_id") or "")
        if not item_id or item_id in seen:
            return
        seen.add(item_id)
        picked.append({**row, "sample_class": sample_class})

    for row in rows:
        if _level(row) in {0, 1}:
            add(row, "l0_l1")
    for row in rows:
        if _is_heading_or_fragment(row.get("line") or ""):
            add(row, "heading_fragment")
        if str(row.get("item_id") or "") == "accuity:req:1":
            add(row, "credential_pair")
    for row in rows:
        line = (row.get("line") or "").lower()
        if "ai agents" in line or "jira, confluence" in line:
            add(row, "window_risk")
    for level in (2, 3, 4):
        at_level = [row for row in rows if _level(row) == level]
        req = [row for row in at_level if row.get("nlp_bucket") == "required"]
        pref = [row for row in at_level if row.get("nlp_bucket") == "preferred"]
        if req and not any(
            _level(item) == level and item.get("nlp_bucket") == "required" for item in picked
        ):
            add(req[0], "stratified")
        if pref and not any(
            _level(item) == level and item.get("nlp_bucket") == "preferred" for item in picked
        ):
            add(pref[0], "stratified")
        elif at_level and not req:
            add(at_level[0], "stratified")
    return picked


def _evidence_note(row: dict) -> tuple[str, str, str, str]:
    """Return agy_proposed overlay, status, source, note. your_mark only for jason."""
    item_id = str(row.get("item_id") or "")
    if item_id in _JASON_EVIDENCE:
        mark, note = _JASON_EVIDENCE[item_id]
        return mark, "JASON_MARK", "jason", note
    line = (row.get("line") or "").lower()
    if "visa" in line or "sponsor" in line:
        return (
            "drop",
            "JASON_MARK",
            "jason",
            "work-auth logistics. not a skill 0. junk/prefs, do not score.",
        )
    if "education and credentials" in line:
        return (
            "",
            "NEEDS_MARK",
            "agy",
            "heading scored as required L4 and matched to BBA. same class as leftover junk.",
        )
    if "ai agents" in line or "agentic coding" in line:
        return (
            "",
            "NEEDS_MARK",
            "agy",
            "v1 level 0 was WE-only truncated excerpt, not a gap. v2 scored 3. confirm 3 vs 4.",
        )
    if "jira, confluence" in line:
        return (
            "",
            "NEEDS_MARK",
            "agy",
            "possible excerpt-window 0, same class as Acquia AI v1",
        )
    if _is_heading_or_fragment(row.get("line") or ""):
        return (
            "",
            "NEEDS_MARK",
            "agy",
            "heading/fragment class. leftover junks this shape; scored path does not.",
        )
    return "", "NEEDS_MARK", "agy", ""


def _preserve_marks(
    path: Path,
    rows: list[dict],
    key: str = "item_id",
    *,
    keep_notes: bool = True,
) -> None:
    """Keep filled sitting marks unless this build names a jason override."""
    if not path.exists():
        return
    with path.open(encoding="utf-8", newline="") as handle:
        existing = {row.get(key, ""): row for row in csv.DictReader(handle)}
    for row in rows:
        old = existing.get(row.get(key, ""))
        if not old:
            continue
        if row.get("source") == "jason":
            continue
        mark = (old.get("your_mark") or "").strip()
        if not mark:
            continue
        row["your_mark"] = mark
        row["status"] = old.get("status") or row.get("status")
        row["source"] = old.get("source") or row.get("source")
        if keep_notes and old.get("note"):
            row["note"] = old["note"]


def main() -> int:
    """Write gitignored 8-JD adjudication markdown and csv."""
    review_path = _ROOT / "data" / "stage0_agy_label_review.txt"
    work_exp = ""
    if _WORK_EXP.exists():
        work_exp = _WORK_EXP.read_text(encoding="utf-8", errors="replace")

    extract_rows: list[dict] = []
    for raw in _parse_review_leftovers(review_path):
        proposed, status, source, note = _extract_row(raw["line"], raw["agy_draft"])
        extract_rows.append(
            {
                **raw,
                "agy_proposed": proposed,
                "status": status,
                "source": source,
                "your_mark": proposed if status == "JASON_MARK" else "",
                "note": note,
            }
        )

    slugs = {row["slug"] for row in extract_rows}
    review_lines = _parse_review_evidence_lines(review_path)
    cache_rows = _load_all_evidence_cache()
    evidence_rows: list[dict] = []
    for item_id, cached in sorted(cache_rows.items()):
        slug = item_id.split(":", 1)[0]
        if slug not in slugs:
            continue
        parts = item_id.split(":")
        prefix = parts[1] if len(parts) >= 3 else ""
        if prefix == "req":
            bucket = "required"
        elif prefix == "pref":
            bucket = "preferred"
        else:
            continue
        line = (
            _KNOWN_EVIDENCE_LINES.get(item_id)
            or review_lines.get(item_id)
            or _line_from_reasoning(str(cached.get("reasoning") or ""))
        )
        excerpt = ""
        prefix = work_exp[:_EVIDENCE_EXCERPT_CHARS] if work_exp else ""
        if line and work_exp:
            excerpt = build_evidence_context(
                line, work_exp, k=4, max_chars=_EVIDENCE_EXCERPT_CHARS
            )
        coverage_ok, missing = retrieval_coverage(line, excerpt, work_exp)
        evidence_rows.append(
            {
                "slug": slug,
                "item_id": item_id,
                "nlp_bucket": bucket,
                "line": line,
                "agy_level": cached.get("evidence_level"),
                "agy_gate": cached.get("gate"),
                "window_ok": _window_ok(line, excerpt),
                "prefix_ok": _window_ok(line, prefix),
                "coverage_ok": coverage_ok,
                "coverage_missing": ",".join(missing),
                "reasoning": (cached.get("reasoning") or "")[:280],
            }
        )

    sampled = _sample_evidence(evidence_rows)
    sampled.sort(
        key=lambda row: (
            _level(row) is None,
            _level(row) if _level(row) is not None else 99,
            str(row.get("nlp_bucket") or ""),
            str(row.get("item_id") or ""),
        )
    )
    for row in sampled:
        proposed, status, source, note = _evidence_note(row)
        row["agy_proposed"] = proposed
        row["status"] = status
        row["source"] = source
        row["your_mark"] = proposed if status == "JASON_MARK" else ""
        extras = []
        if note:
            extras.append(note)
        if row.get("window_ok") is False:
            extras.append("scored excerpt starved AI evidence")
        if row.get("prefix_ok") is False and row.get("window_ok") is not False:
            extras.append("blind WE prefix would starve AI evidence (v1 truncated class)")
        if row.get("coverage_ok") is False:
            extras.append(
                "coverage_ok False: distinctive WE tokens missing from excerpt "
                f"({row.get('coverage_missing')})"
            )
        row["note"] = " ".join(extras).strip()

    _preserve_marks(OUT_CSV, extract_rows)
    _preserve_marks(OUT_EV, sampled)

    jason_n = sum(1 for row in extract_rows if row["status"] == "JASON_MARK")
    claude_n = sum(1 for row in extract_rows if row["status"] == "CLAUDE_HINT")
    needs_n = sum(1 for row in extract_rows if row["status"] == "NEEDS_MARK")
    ev_jason = sum(1 for row in sampled if row.get("status") == "JASON_MARK")
    ev_needs = sum(1 for row in sampled if row.get("status") == "NEEDS_MARK")
    sample_cells: dict[str, int] = {}
    class_cells: dict[str, int] = {}
    for row in sampled:
        key = f"L{_level(row)} {row['nlp_bucket']}"
        sample_cells[key] = sample_cells.get(key, 0) + 1
        cls = str(row.get("sample_class") or "")
        class_cells[cls] = class_cells.get(cls, 0) + 1
    cell_summary = ", ".join(f"{key}={count}" for key, count in sorted(sample_cells.items()))
    class_summary = ", ".join(f"{key}={count}" for key, count in sorted(class_cells.items()))
    window_false = sum(1 for row in sampled if row.get("window_ok") is False)
    prefix_false = sum(1 for row in sampled if row.get("prefix_ok") is False)
    coverage_false = sum(1 for row in sampled if row.get("coverage_ok") is False)
    skip_rows = []
    sitting1_note = (
        "Sitting 1 lock: PASS. Skip only when a prefs / exclusion-zone gate fires. "
        "No skip for authoring overclaim. Accelerant is PASS under _ZERO_TO_ONE_RE."
    )
    for slug in sorted(slugs):
        skip_rows.append(
            {
                "slug": slug,
                "status": "JASON_MARK",
                "source": "jason",
                "your_mark": "PASS",
                "note": sitting1_note,
            }
        )

    lines = [
        "# Stage 0 adjudication sheet — 8-JD first slice",
        "",
        "Sitting 1 of 3. Not gold. Agy is a draft.",
        "Blank `your_mark` means unmarked, never agreement. `agy_proposed` is a draft suggestion, not gold.",
        "Do not copy rows into `training_data_approved.csv` except via `scripts/export_stage0_adjudication.py`.",
        "That exporter writes only `source=jason` rows with a non-blank `your_mark`. "
        "`source=claude_review` cannot reach the retrain split, even when `your_mark` is filled.",
        "Buckets: `required` | `preferred` | `responsibilities` | `culture` | `junk`.",
        "",
        "## Provenance",
        "",
        "- `source=agy`: untouched Agy draft. `agy_proposed` copies `agy_draft`. `your_mark` is blank.",
        "- `source=claude_review`: Claude's bucket correction from the prior review, relayed here. Status is `CLAUDE_HINT`. `your_mark` may be filled as a hint. These rows cannot reach `training_data_approved.csv` until you promote `source` to `jason`.",
        "- `source=jason`: you named the mark in this sitting. Status is `JASON_MARK`. Overwrite `your_mark` if it is wrong.",
        "",
        "## Locked from this sitting",
        "",
        "- `junk` is ATS chrome **or** visa / sponsorship / travel-% logistics the prefs/location gate already auto-skips. Junk is visible on the fit gate, never scored, never a culture hook.",
        "- Personality / \"you are a person who\" is `culture`, not `required`. Culture is hook material. Never scored.",
        "- A trait-without-duty that is a **checkable qualification** is `required`.",
        "- Evidence sample is **not** uniform random. Every level-0 and level-1 line is in. Then one required and one preferred at levels 2, 3, and 4 when that cell exists, preferring a heading/fragment at L4 required over years-in-PM. Plus window-risk lines and the heading/fragment class (Education and Credentials, Mid and Senior level, truncated fragments) and the Accuity degree line that shares the same BBA.",
        "",
        "## Curation for sittings 2 and 3",
        "",
        "All eight JDs in this sitting are Pass under the reprinted Stage 0 skip rule "
        "(Accelerant included, unless you add a new skip for authoring overclaim). "
        "`false_skips = 0` is untestable on this slice. Sittings 2 and 3 must carry "
        "every skip case in the corpus. Weight the next 22 toward skips rather than "
        "sampling for balance across all three sittings. Do not curate those 22 until "
        "this sitting's skip marks are settled.",
        "",
        "## Scored path vs leftover junk",
        "",
        "They share `_is_boilerplate_item` / `_is_orphan_header_item` **before** the leftover split. "
        "CR-115 now also drops heading/fragment/board-metadata chrome from required/preferred "
        "before evidence scoring. Leftover `junk` semantics stay unchanged: visible, never a "
        "culture hook, never scored.",
        "",
        "## How to mark",
        "",
        "1. Fill `your_mark` on every row you are settling. Leave it blank if you have not marked it.",
        "2. A `CLAUDE_HINT` row is not yours until `source=jason`. Filling `your_mark` alone does not export it.",
        "3. Evidence: `your_mark` is a 0-4 level or `drop`. Visa/sponsorship evidence is `drop`, not skill-gap 0.",
        "4. Skip/pass uses the rule printed above that table. One mark per company. "
        "Sitting 1 is fully marked PASS, including Accelerant.",
        "",
        f"Extraction rows: {len(extract_rows)} (JASON_MARK {jason_n}, CLAUDE_HINT {claude_n}, NEEDS_MARK {needs_n})",
        f"Evidence universe: {len(evidence_rows)} scored req/pref lines from the v2 cache.",
        f"Evidence sample: {len(sampled)} (JASON_MARK {ev_jason}, NEEDS_MARK {ev_needs}). Cells: {cell_summary}. Classes: {class_summary}.",
        f"window_ok False: {window_false} of {len(sampled)}. prefix_ok False: {prefix_false} of {len(sampled)}. "
        f"coverage_ok False: {coverage_false} of {len(sampled)}.",
        "",
        "## Extraction",
        "",
    ]
    current = ""
    for row in extract_rows:
        if row["slug"] != current:
            current = row["slug"]
            lines.append(f"### {current}")
            lines.append("")
            lines.append(
                "| item_id | status | source | agy_draft | agy_proposed | your_mark | header | line | note |"
            )
            lines.append("|---|---|---|---|---|---|---|---|---|")
        cell = row["line"].replace("|", "/").replace("\n", " ")
        header = (row["header"] or "").replace("|", "/")
        note = (row["note"] or "").replace("|", "/")
        lines.append(
            f"| {row['item_id']} | {row['status']} | {row['source']} | {row['agy_draft']} | "
            f"{row['agy_proposed']} | {row['your_mark'] or ''} | {header} | {cell} | {note} |"
        )
    lines.append("")
    lines.append("## Evidence sample")
    lines.append("")
    lines.append(
        "Sampling rule: every level-0 and level-1 line; one required and one preferred "
        "at levels 2-4 when that cell exists, with L4 required preferring a heading/fragment; "
        "plus window-risk (Acquia AI-agents, Jira/Confluence 0); plus heading/fragment class "
        "and the Accuity BBA credential pair. Not a random draw."
    )
    lines.append("")
    lines.append(
        "`window_ok` is False only when the JD line matches AI/LLM/agentic/MCP **and** "
        "the excerpt used for scoring lacks those tokens. Non-AI lines are True by definition, "
        "which is why Acquia Jira and executive-briefing scored 0 with window_ok True. "
        "`coverage_ok` is the non-AI check: distinctive requirement tokens that exist in "
        "workExperience.md must appear in the excerpt. `prefix_ok` repeats the AI-token "
        f"check against a blind {_EVIDENCE_EXCERPT_CHARS}-char WE prefix (v1 truncated class)."
    )
    lines.append("")
    lines.append(
        "| item_id | class | bucket | agy_lvl | window_ok | prefix_ok | coverage_ok | agy_proposed | status | source | your_mark | line | note |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for row in sampled:
        cell = (row["line"] or "").replace("|", "/").replace("\n", " ")
        note = (row.get("note") or "").replace("|", "/")
        lines.append(
            f"| {row['item_id']} | {row.get('sample_class','')} | {row['nlp_bucket']} | "
            f"{row['agy_level']} | {row['window_ok']} | {row['prefix_ok']} | "
            f"{row.get('coverage_ok','')} | "
            f"{row.get('agy_proposed','')} | {row.get('status','')} | {row.get('source','')} | "
            f"{row.get('your_mark') or ''} | {cell} | {note} |"
        )
    lines.append("")
    lines.append("## Skip / pass (one mark per JD)")
    lines.append("")
    lines.append(_SKIP_RULE)
    lines.append("")
    lines.append("| slug | status | source | your_mark (PASS or SKIP) | note |")
    lines.append("|---|---|---|---|---|")
    for row in skip_rows:
        lines.append(
            f"| {row['slug']} | {row['status']} | {row['source']} | {row.get('your_mark') or ''} | {row['note']} |"
        )
    lines.append("")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "slug", "item_id", "header", "line", "agy_draft",
                "agy_proposed", "status", "source", "your_mark", "note",
            ],
        )
        writer.writeheader()
        writer.writerows(extract_rows)
    with OUT_EV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "slug", "item_id", "nlp_bucket", "line", "agy_level", "agy_gate",
                "window_ok", "prefix_ok", "coverage_ok", "coverage_missing",
                "sample_class", "agy_proposed",
                "status", "source", "your_mark", "note", "reasoning",
            ],
        )
        writer.writeheader()
        writer.writerows(sampled)
    with OUT_SKIP.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["slug", "status", "source", "your_mark", "note"],
        )
        writer.writeheader()
        writer.writerows(skip_rows)
    print(f"wrote {OUT_MD}")
    print(f"wrote {OUT_CSV}")
    print(f"wrote {OUT_EV}")
    print(f"wrote {OUT_SKIP}")
    print(
        f"extraction {len(extract_rows)} JASON_MARK={jason_n} "
        f"CLAUDE_HINT={claude_n} NEEDS_MARK={needs_n}"
    )
    print(f"evidence universe {len(evidence_rows)}")
    print(f"evidence sample {len(sampled)} JASON_MARK={ev_jason} NEEDS_MARK={ev_needs}")
    print(f"sample cells {cell_summary}")
    print(f"sample classes {class_summary}")
    print(f"window_ok False={window_false} prefix_ok False={prefix_false} coverage_ok False={coverage_false}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
