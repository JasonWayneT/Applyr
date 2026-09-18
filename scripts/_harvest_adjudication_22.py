#!/usr/bin/env python3
"""Harvest leftover lines for the class-weighted 22. Implements FR-327 / FR-329.

NLP leftover queue only. No Agy, Groq, Gemini, or gold manufacture.
your_mark stays blank. agy_proposed is visa/travel junk or empty.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import warnings
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

from build_stage0_fit_gate import _collect_nlp_section_candidates
from smoke_stage0_agy_archive import _clean_jd
from stage0_prefs_gate import run_prefs_gate
from utils import load_candidate_preferences

OUT_MD = _ROOT / "data" / "stage0_adjudication_22.md"
OUT_CSV = _ROOT / "data" / "stage0_adjudication_22_extraction.csv"
OUT_SKIP = _ROOT / "data" / "stage0_adjudication_22_skip.csv"

_VISA_TRAVEL_RE = re.compile(
    r"(?i)visa|sponsor|work authoriz|citizenship|travel\s*:|%\s*travel|"
    r"travel may be required|\bup to\s+\d+%\s+travel"
)

OVER_SKIP_SUSPECTS = (
    "smartlight_analytics",
    "yara_ai",
    "metlife",
    "aegon",
)
YEARS_REPRESENTATIVES = ("civicplus", "realm_alliance", "aegon")

SITTING_22: list[tuple[str, str]] = [
    ("harbor_compliance", "0-to-1"),
    ("alinea_invest", "solo/founding"),
    ("versa_ai", "solo/founding"),
    ("eso", "people"),
    ("smartlight_analytics", "people; over-skip suspect"),
    ("funnel_leasing", "revenue"),
    ("enlyte", "revenue"),
    ("ss_c_technologies", "AI/ML ownership"),
    ("the_blue_venture_fund", "AI/ML ownership"),
    ("remote", "blocked company"),
    ("unity", "blocked company"),
    ("invision", "placeholder"),
    ("afresh", "travel"),
    ("yara_ai", "network page; over-skip suspect"),
    ("wellsky", "blocked title"),
    ("metlife", "blocked title; over-skip suspect"),
    ("csi", "hard_gap"),
    ("sundayy", "hard_gap"),
    ("civicplus", "years_ceiling representative"),
    ("aegon", "years+people; over-skip suspect"),
    ("realm_alliance", "years+solo representative"),
    ("indotronix_avani_group", "Jason override"),
]


def _jd_path(slug: str) -> Path:
    """Resolve Original_JD.txt, skipped folder first when both exist."""
    candidates = [
        _ROOT / "data" / "archive" / "skipped" / slug / "Original_JD.txt",
        _ROOT / "data" / "archive" / "submissions" / slug / "Original_JD.txt",
        _ROOT / "data" / "pending_review" / slug / "Original_JD.txt",
    ]
    for path in candidates:
        if path.exists():
            return path
    matches = list((_ROOT / "data").glob(f"archive/*/{slug}/Original_JD.txt"))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"Original_JD.txt missing for {slug}")


def _hist_skip(slug: str, path: Path) -> str:
    """Read historical Stage 0 skip/pass from the folder's fit-gate file."""
    gate = path.parent / "stage0_fit_gate.json"
    if not gate.exists():
        return ""
    try:
        payload = json.loads(gate.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    decision = str(payload.get("decision") or payload.get("verdict") or "")
    code = str(payload.get("skip_reason_code") or payload.get("reason_code") or "")
    return f"{decision} {code}".strip()


def _nlp_pred(pipeline, classes: list[str], combo_text: str) -> str:
    """Format leftover NLP guess as bucket@confidence. Not gold."""
    pred = pipeline.predict([combo_text])[0]
    proba = pipeline.predict_proba([combo_text])[0]
    conf = float(proba[list(classes).index(pred)])
    return f"{pred}@{conf:.2f}"


def _extraction_rows(slug: str, jd_text: str, pipeline, classes: list[str]) -> list[dict]:
    """Harvest leftover lines for one JD. your_mark stays blank."""
    collected = _collect_nlp_section_candidates(jd_text)
    if collected is None:
        raise RuntimeError(f"NLP leftover harvest unavailable for {slug}")
    _buckets, leftover = collected
    rows: list[dict] = []
    for index, (combo_text, line, header) in enumerate(leftover):
        nlp = _nlp_pred(pipeline, classes, combo_text)
        if _VISA_TRAVEL_RE.search(line or ""):
            proposed, note = "junk", "logistics; prefs/location gate already skips. not scored."
        else:
            proposed, note = "", ""
        rows.append(
            {
                "slug": slug,
                "item_id": f"{slug}:e{index}",
                "header": header or "",
                "line": line,
                "agy_draft": nlp,
                "agy_proposed": proposed,
                "status": "NEEDS_MARK",
                "source": "nlp",
                "your_mark": "",
                "note": note,
            }
        )
    return rows


def _skip_row(slug: str, why: str, jd_text: str, path: Path, prefs: dict) -> dict:
    """Prefs skip proposal with blank your_mark. Not gold."""
    with patch(
        "industry_semantic.classify_industry_safe",
        return_value={"blocked_industry": "", "confidence": "high", "reasoning": "harvest"},
    ):
        verdict = run_prefs_gate(slug.replace("_", " "), jd_text, prefs)
    codes = [item.get("code", "") for item in verdict.get("rejects") or []]
    hist = _hist_skip(slug, path)
    flags = []
    if slug in OVER_SKIP_SUSPECTS:
        flags.append("OVER_SKIP_SUSPECT")
    if slug in YEARS_REPRESENTATIVES:
        flags.append("YEARS_REPRESENTATIVE")
    note_bits = [why, "prefs=" + (",".join(codes) if codes else "PASS")]
    if hist:
        note_bits.append("hist=" + hist)
    note_bits.extend(flags)
    return {
        "slug": slug,
        "status": "NEEDS_MARK",
        "source": "prefs",
        "your_mark": "",
        "note": " | ".join(note_bits),
    }


def build() -> tuple[list[dict], list[dict]]:
    """Build extraction leftover rows and skip rows for the locked 22."""
    import joblib

    model_path = _ROOT / "data" / "stage0_classifier.pkl"
    if not model_path.exists():
        raise FileNotFoundError("data/stage0_classifier.pkl is required for leftover harvest")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Trying to unpickle estimator")
        pipeline = joblib.load(model_path)
    classes = list(pipeline.classes_)
    prefs = load_candidate_preferences()
    extract: list[dict] = []
    skips: list[dict] = []
    for slug, why in SITTING_22:
        path = _jd_path(slug)
        jd_text = _clean_jd(path.read_text(encoding="utf-8", errors="replace"))
        extract.extend(_extraction_rows(slug, jd_text, pipeline, classes))
        skips.append(_skip_row(slug, why, jd_text, path, prefs))
    return extract, skips


def _load_csv(path: Path) -> list[dict]:
    """Read a sitting CSV if it exists."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _merge_extract_marks(new_rows: list[dict], old_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Keep prior marks by slug+line. Flag inherited-heading changes. Implements FR-334."""
    old_by_line: dict[tuple[str, str], dict] = {}
    for row in old_rows:
        key = ((row.get("slug") or "").strip(), (row.get("line") or "").strip())
        old_by_line[key] = row
    changed: list[dict] = []
    for row in new_rows:
        key = (row["slug"], (row.get("line") or "").strip())
        old = old_by_line.get(key)
        if not old:
            row["heading_changed"] = ""
            continue
        old_header = (old.get("header") or "").strip()
        new_header = (row.get("header") or "").strip()
        if old_header != new_header:
            row["heading_changed"] = "yes"
            changed.append(
                {
                    "slug": row["slug"],
                    "item_id": row.get("item_id"),
                    "line": row.get("line"),
                    "old_header": old_header,
                    "new_header": new_header,
                }
            )
        else:
            row["heading_changed"] = ""
        mark = (old.get("your_mark") or "").strip()
        if mark:
            row["your_mark"] = mark
            row["status"] = old.get("status") or row.get("status")
            source = (old.get("source") or "").strip()
            if source == "claude_review":
                row["source"] = "claude_opus_jason_approved"
            else:
                row["source"] = source or row.get("source")
            if old.get("note"):
                row["note"] = old.get("note")
    return new_rows, changed


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    """Write a sitting CSV. Implements FR-327."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_md(extract: list[dict], skips: list[dict]) -> str:
    """Sitting 2/3 harvest report. Not gold. Skip-dense 30 is intentional."""
    leftover_by_slug = {}
    for row in extract:
        leftover_by_slug[row["slug"]] = leftover_by_slug.get(row["slug"], 0) + 1
    lines = [
        "# Stage 0 adjudication — sittings 2 and 3 harvest",
        "",
        "Not gold. `agy_proposed` is not a mark. Blank `your_mark` never means",
        "agreement. No Agy/Groq/Gemini. Production switch stays off.",
        "",
        "## The 30 is skip-dense on purpose",
        "",
        "Sitting 1 already passed all eight Pass-shaped JDs. These 22 are",
        "class-weighted toward skip codes so the adjudicated 30 can prove",
        "`false_skips = 0`. That shape does **not** resemble the live pipeline",
        "distribution. Do not read the final 30 as a representative sample.",
        "It is the right instrument for false-skip proof and the wrong",
        "instrument for base-rate claims.",
        "",
        "Skip-class weighting does not distort `training_data_approved.csv`.",
        "Extraction labels are per line. A 0-to-1 JD's leftover lines bucket",
        "the same way a years_ceiling JD's do. Weighting only moves the replay.",
        "",
        "`years_ceiling` is 70 percent of the skip population. It is not",
        "hand-marked at volume. Arithmetic across the full class lives in",
        "`data/stage0_years_ceiling_audit.md`. This sitting keeps three",
        "representatives so leftover lines still get a bucket check:",
        "`civicplus`, `realm_alliance`, and `aegon`. The four over-skip",
        "suspects stay in: `smartlight_analytics`, `yara_ai`, `metlife`, `aegon`.",
        "",
        f"- Leftover lines harvested: {len(extract)}",
        f"- Skip rows: {len(skips)} (all `your_mark` blank)",
        "",
        "## Leftover counts",
        "",
        "| slug | leftover | why |",
        "|---|---|---|",
    ]
    why_by_slug = {slug: why for slug, why in SITTING_22}
    for slug, _why in SITTING_22:
        lines.append(
            f"| `{slug}` | {leftover_by_slug.get(slug, 0)} | {why_by_slug[slug]} |"
        )
    lines.extend(["", "## Skip rows to mark", ""])
    for row in skips:
        lines.append(f"- `{row['slug']}` — {row['note']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Re-harvest leftover lines. Never overwrite jason skip marks."""
    extract, skips = build()
    old_extract = _load_csv(OUT_CSV)
    extract, heading_changes = _merge_extract_marks(extract, old_extract)
    _write_csv(
        OUT_CSV,
        extract,
        [
            "slug",
            "item_id",
            "header",
            "line",
            "agy_draft",
            "agy_proposed",
            "status",
            "source",
            "your_mark",
            "note",
            "heading_changed",
        ],
    )
    existing_skip = _load_csv(OUT_SKIP)
    jason_skip = [row for row in existing_skip if (row.get("source") or "").strip() == "jason"]
    if jason_skip:
        print(f"kept {len(jason_skip)} jason skip marks; did not overwrite {OUT_SKIP.name}")
    else:
        _write_csv(
            OUT_SKIP,
            skips,
            ["slug", "status", "source", "your_mark", "note"],
        )
    change_path = _ROOT / "data" / "stage0_adjudication_22_heading_changes.csv"
    _write_csv(
        change_path,
        heading_changes,
        ["slug", "item_id", "line", "old_header", "new_header"],
    )
    OUT_MD.write_text(render_md(extract, existing_skip or skips), encoding="utf-8")
    print(f"harvested leftover={len(extract)} heading_changed={len(heading_changes)}")
    print(f"  {OUT_CSV}")
    print(f"  {change_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
