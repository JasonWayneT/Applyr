"""
Merge CR-053/054/055 preference keys from example template into live prefs.

Non-destructive: never overwrites existing scalar values or list contents except
union-merge for blocked_companies.
"""
from __future__ import annotations

import json
import os
from typing import Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
EXAMPLE_PATH = os.path.join(DATA_DIR, "candidate_preferences.example.json")
LIVE_PATH = os.path.join(DATA_DIR, "candidate_preferences.json")

# Keys added by gate overhaul — copy whole value when missing on live prefs.
COPY_IF_MISSING = (
    "blocked_role_titles",
    "blocked_focus_area_words",
    "min_confidence_score",
)


def _load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _save_json(path: str, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def merge_gate_prefs(
    live: dict[str, Any] | None,
    example: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Return merged prefs and human-readable change lines."""
    out = dict(live or {})
    changes: list[str] = []

    for key in COPY_IF_MISSING:
        if key not in out and key in example:
            out[key] = example[key]
            changes.append(f"added {key} ({len(example[key]) if isinstance(example[key], list) else example[key]!r})")

    example_companies = [
        c.strip() for c in (example.get("blocked_companies") or []) if str(c).strip()
    ]
    if example_companies:
        live_companies = [str(c).strip() for c in (out.get("blocked_companies") or []) if str(c).strip()]
        seen = {c.lower() for c in live_companies}
        added: list[str] = []
        for company in example_companies:
            if company.lower() not in seen:
                live_companies.append(company)
                seen.add(company.lower())
                added.append(company)
        if added:
            out["blocked_companies"] = live_companies
            changes.append(f"union blocked_companies (+{', '.join(added)})")
        elif "blocked_companies" not in out:
            out["blocked_companies"] = list(example_companies)
            changes.append(f"added blocked_companies ({', '.join(example_companies)})")

    return out, changes


def apply_prefs_rollout(*, write: bool = True) -> tuple[bool, list[str]]:
    """
    Merge example gate keys into data/candidate_preferences.json.

    Returns (changed, change_lines).
    """
    if not os.path.isfile(EXAMPLE_PATH):
        return False, [f"missing template: {EXAMPLE_PATH}"]

    example = _load_json(EXAMPLE_PATH)
    live: dict[str, Any] | None = None
    if os.path.isfile(LIVE_PATH):
        live = _load_json(LIVE_PATH)

    merged, changes = merge_gate_prefs(live, example)
    if not changes:
        return False, ["candidate_preferences.json already has gate rollout keys"]

    if write:
        _save_json(LIVE_PATH, merged)
        changes.append(f"wrote {LIVE_PATH}")

    return True, changes
