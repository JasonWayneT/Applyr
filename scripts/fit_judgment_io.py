"""Deterministic I/O contract for Claude-native fit judgments (CR-070 Epic 2).

Separates the reasoning step (Claude writes a judgments JSON during a live
skill turn — not callable from a test) from the deterministic contract around
it (schema validation, file read/write), which is what gets unit tested here.
"""
import json
import os

JUDGMENT_FILENAME = "fit_judgment.json"

REQUIRED_CRITERIA_KEYS = {
    "title_seniority_fit",
    "pm_craft_overlap",
    "team_structure_fit",
    "execution_depth",
    "transition_potential",
}


def write_equivalence_judgment(folder_path: str, payload: dict) -> None:
    path = os.path.join(folder_path, JUDGMENT_FILENAME)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def read_equivalence_judgment(folder_path: str) -> dict | None:
    """Returns the judgments dict, or None if missing/malformed/incomplete.

    None triggers the existing _heuristic_judgments fallback in
    structured_fit.evaluate_structured_fit — same failure mode as an Ollama
    call returning nothing today.
    """
    path = os.path.join(folder_path, JUDGMENT_FILENAME)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if "must_haves" not in payload or "criteria" not in payload:
        return None
    if not isinstance(payload["criteria"], dict):
        return None
    if not REQUIRED_CRITERIA_KEYS.issubset(payload["criteria"].keys()):
        return None
    return payload
