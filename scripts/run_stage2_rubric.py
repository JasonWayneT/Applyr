#!/usr/bin/env python3
"""Sandboxed Stage 2 Agy rubric scorer (CR-121 / FR-356).

Writes CR-112 reviews/rubric_scorecard.json rows and copies the binding
totals into draft_manifest.json. Does not import utils.call_llm. Does not
set verification_passed True. Production worker hook stays off until
APPLYR_STAGE2_AGY_RUBRIC=1 and AC-464 frozen parks fail closed.

Boundary-band scores spawn a second independent_blind session. Disagree-low
binds. No averaging. No picking the high score.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contracts import (  # noqa: E402
    RUBRIC_BOUNDARY_BANDS,
    RUBRIC_BREAKDOWN_KEYS,
    RUBRIC_BREAKDOWN_MAX,
    RUBRIC_FLOOR_RESUME,
    RUBRIC_SCORECARD_PATH,
    _current_rubric_sha256,
    _score_total,
)
from run_stage1_author import run_author_process  # noqa: E402
from run_stage1_repair import _FENCE_RE  # noqa: E402

DEFAULT_MODEL = "gemini-3.8-flash-medium"
DEFAULT_EFFORT = "medium"
DEFAULT_WALL_SECONDS = 180
DEFAULT_MAX_EVENTS = 40
ATTEMPTS_DIR = "stage2_rubric_attempts"
SANDBOX_INSTRUCTION = (
    "Return one JSON object only as a fenced json block. "
    "Don't use tools or files. Do not dump workExperience.md."
)
_R_KEYS = {
    "r1": "R1",
    "r1_ats_integrity": "R1",
    "r2": "R2",
    "r2_jd_alignment": "R2",
    "r3": "R3",
    "r3_top_third_signal": "R3",
    "r4": "R4",
    "r4_metric_quality": "R4",
    "r5": "R5",
    "r5_pm_craft_coverage": "R5",
    "r6": "R6",
    "r6_seniority_altitude": "R6",
    "r7": "R7",
    "r7_internal_consistency": "R7",
    "r8": "R8",
    "r8_b2b_saas_legibility": "R8",
}
_C_KEYS = {
    "c1": "C1",
    "c1_opening_hook": "C1",
    "c2": "C2",
    "c2_proof_density": "C2",
    "c3": "C3",
    "c3_role_fit_logic": "C3",
    "c4": "C4",
    "c4_authenticity": "C4",
    "c5": "C5",
    "c5_length_structure": "C5",
}


def stage2_agy_rubric_enabled() -> bool:
    """True only when the production worker hook is explicitly armed."""
    return os.environ.get("APPLYR_STAGE2_AGY_RUBRIC", "").strip() == "1"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_document_hashes(folder: Path) -> dict[str, str] | None:
    """Return resume/cover hashes, or None when a document is missing."""
    resume = _sha256_file(folder / "Resume.md")
    cover = _sha256_file(folder / "CoverLetter.md")
    if not resume or not cover:
        return None
    return {"resume": resume, "cover_letter": cover}


def in_boundary_band(side: str, total: float) -> bool:
    """True when a total sits in the CR-112 independent-blind band."""
    lower, upper = RUBRIC_BOUNDARY_BANDS[side]
    return lower <= total <= upper


def needs_independent_blind(row: dict[str, Any]) -> bool:
    """True when either document total is in the CR-112 boundary band."""
    resume = _score_total(row, "resume")
    cover = _score_total(row, "cover_letter")
    if resume is not None and in_boundary_band("resume", resume):
        return True
    if cover is not None and in_boundary_band("cover_letter", cover):
        return True
    return False


def choose_binding_row(
    session: dict[str, Any],
    blind: dict[str, Any] | None,
) -> dict[str, Any]:
    """Disagree-low binds. No averaging. No picking the high score."""
    if blind is None:
        return session
    session_sum = (_score_total(session, "resume") or 0) + (
        _score_total(session, "cover_letter") or 0
    )
    blind_sum = (_score_total(blind, "resume") or 0) + (
        _score_total(blind, "cover_letter") or 0
    )
    return session if session_sum <= blind_sum else blind


def fail_closed_if_inflated(*, parked_resume: float, agy_resume: float) -> bool:
    """AC-464: a parked below-70 resume must not score CONVERT-READY."""
    if parked_resume < RUBRIC_FLOOR_RESUME and agy_resume >= RUBRIC_FLOOR_RESUME:
        return False
    return True


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Parse the first JSON object from fenced or raw model text."""
    if not text or not str(text).strip():
        return None
    raw = str(text).strip()
    for match in _FENCE_RE.finditer(raw):
        body = match.group(2).strip()
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number:  # NaN
        return None
    return number


def _normalize_breakdown(side: str, blob: dict[str, Any]) -> dict[str, float] | None:
    keys = RUBRIC_BREAKDOWN_KEYS[side]
    alias = _R_KEYS if side == "resume" else _C_KEYS
    found: dict[str, float] = {}
    nested = blob.get("breakdown") if isinstance(blob.get("breakdown"), dict) else {}
    sources = [nested, blob]
    for source in sources:
        if not isinstance(source, dict):
            continue
        for raw_key, value in source.items():
            mapped = alias.get(str(raw_key).strip().lower())
            if mapped is None:
                continue
            number = _finite_number(value)
            if number is None:
                return None
            found[mapped] = number
    if any(key not in found for key in keys):
        return None
    for key in keys:
        maximum = RUBRIC_BREAKDOWN_MAX[side][key]
        if found[key] < 0 or found[key] > maximum:
            return None
    return {key: found[key] for key in keys}


def parse_score_payload(text: str) -> dict[str, Any] | None:
    """Return resume/cover totals+breakdown from Agy text, or None."""
    payload = _extract_json_object(text)
    if payload is None:
        return None
    resume_blob = payload.get("resume")
    cover_blob = payload.get("cover_letter")
    if not isinstance(resume_blob, dict) or not isinstance(cover_blob, dict):
        return None
    resume_break = _normalize_breakdown("resume", resume_blob)
    cover_break = _normalize_breakdown("cover_letter", cover_blob)
    if resume_break is None or cover_break is None:
        return None
    resume_total = _finite_number(resume_blob.get("total"))
    cover_total = _finite_number(cover_blob.get("total"))
    if resume_total is None:
        resume_total = sum(resume_break.values())
    if cover_total is None:
        cover_total = sum(cover_break.values())
    if abs(resume_total - sum(resume_break.values())) > 1e-9:
        return None
    if abs(cover_total - sum(cover_break.values())) > 1e-9:
        return None
    resume_citations = resume_blob.get("citations")
    cover_citations = cover_blob.get("citations")
    if not isinstance(resume_citations, dict):
        resume_citations = {}
    if not isinstance(cover_citations, dict):
        cover_citations = {}
    return {
        "resume": {
            "total": resume_total,
            "breakdown": resume_break,
            "citations": resume_citations,
        },
        "cover_letter": {
            "total": cover_total,
            "breakdown": cover_break,
            "citations": cover_citations,
        },
    }


def bind_scorecard_row(
    parsed: dict[str, Any],
    *,
    hashes: dict[str, str],
    role: str,
    reviewer_run_id: str,
    scored_at: str | None = None,
) -> dict[str, Any]:
    """Attach CR-112 provenance fields to a parsed score payload."""
    rubric_sha = _current_rubric_sha256()
    if not rubric_sha:
        raise FileNotFoundError("data/conversion_rubric.md not found")
    return {
        "schema_version": 1,
        "rubric_sha256": rubric_sha,
        "scored_at": scored_at or datetime.now(timezone.utc).isoformat(),
        "reviewer_run_id": reviewer_run_id,
        "reviewer_role": role,
        "document_sha256": dict(hashes),
        "resume": parsed["resume"],
        "cover_letter": parsed["cover_letter"],
    }


def load_scorecards(folder: Path) -> list[dict[str, Any]]:
    """Read the append-only scorecard array, or empty if missing."""
    path = folder / RUBRIC_SCORECARD_PATH
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def has_current_hash_scorecard(folder: Path) -> bool:
    """True when a scorecard row already matches current document hashes."""
    hashes = current_document_hashes(folder)
    if hashes is None:
        return False
    for row in load_scorecards(folder):
        row_hashes = row.get("document_sha256") if isinstance(row, dict) else None
        if not isinstance(row_hashes, dict):
            continue
        if all(row_hashes.get(side) == digest for side, digest in hashes.items()):
            return True
    return False


def write_scorecards(folder: Path, rows: list[dict[str, Any]]) -> None:
    """Replace reviews/rubric_scorecard.json with the given rows."""
    dest = folder / "reviews"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "rubric_scorecard.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )


def copy_binding_into_manifest(folder: Path, row: dict[str, Any]) -> bool:
    """Copy binding totals into draft_manifest. Never set verification_passed True."""
    path = folder / "draft_manifest.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    data["rubric_score"] = {
        "resume": {
            "total": row["resume"]["total"],
            "breakdown": row["resume"]["breakdown"],
        },
        "cover_letter": {
            "total": row["cover_letter"]["total"],
            "breakdown": row["cover_letter"]["breakdown"],
        },
        "document_sha256": dict(row["document_sha256"]),
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True


def save_raw_attempt(folder: Path, text: str) -> Path:
    """Persist raw Agy text under stage2_rubric_attempts/."""
    dest = folder / ATTEMPTS_DIR
    dest.mkdir(parents=True, exist_ok=True)
    n = len(list(dest.glob("*.txt"))) + 1
    path = dest / f"{n}.txt"
    path.write_text(text or "", encoding="utf-8")
    return path


def build_score_prompt(folder: Path, *, independent: bool = False) -> str | None:
    """Build the no-tools scoring prompt from on-disk documents. No WE dump."""
    rubric = Path(__file__).resolve().parents[1] / "data" / "conversion_rubric.md"
    resume = folder / "Resume.md"
    cover = folder / "CoverLetter.md"
    jd = folder / "Original_JD.txt"
    if not rubric.is_file() or not resume.is_file() or not cover.is_file():
        return None
    excerpts = ""
    packet_path = folder / "authoring_packet.json"
    if packet_path.is_file():
        try:
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            packet = {}
        if isinstance(packet, dict) and packet.get("excerpts"):
            excerpts = json.dumps(packet.get("excerpts"), indent=2)[:8000]
    blind_line = (
        "You have not seen a prior score. Score independently.\n"
        if independent
        else ""
    )
    jd_text = jd.read_text(encoding="utf-8")[:12000] if jd.is_file() else ""
    return (
        f"{SANDBOX_INSTRUCTION}\n\n"
        f"{blind_line}"
        "Score Resume.md and CoverLetter.md against conversion_rubric.md.\n"
        "R3 is top-third signal including domain fit. R8 is B2B SaaS "
        "legibility, not domain-native identity.\n"
        "Return JSON with resume.total, resume.breakdown R1-R8, "
        "cover_letter.total, cover_letter.breakdown C1-C5. "
        "Breakdown values must sum to each total.\n\n"
        "## conversion_rubric.md\n"
        f"{rubric.read_text(encoding='utf-8')}\n\n"
        "## Original_JD.txt\n"
        f"{jd_text}\n\n"
        "## Resume.md\n"
        f"{resume.read_text(encoding='utf-8')}\n\n"
        "## CoverLetter.md\n"
        f"{cover.read_text(encoding='utf-8')}\n\n"
        "## packet excerpts\n"
        f"{excerpts}\n"
    )


def _run_score_session(
    prompt: str,
    *,
    spawn: Callable | None,
    model: str,
    effort: str,
    wall_seconds: int,
    max_events: int,
) -> dict[str, Any]:
    result = run_author_process(
        prompt,
        model=model,
        effort=effort,
        wall_seconds=wall_seconds,
        max_events=max_events,
        spawn=spawn,
        instruction=SANDBOX_INSTRUCTION,
    )
    if result.get("outcome") == "author_failed":
        result["outcome"] = "rubric_failed"
    elif result.get("outcome") == "author_timeout":
        result["outcome"] = "rubric_timeout"
    return result


def run_for_folder(
    folder: Path,
    *,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    wall_seconds: int | None = None,
    max_events: int | None = None,
    spawn: Callable | None = None,
    reviewer_run_id: str = "agy-stage2-rubric",
) -> dict[str, Any]:
    """Score a folder through sandboxed Agy and write the CR-112 scorecard."""
    folder = folder.resolve()
    hashes = current_document_hashes(folder)
    if hashes is None:
        return {
            "outcome": "rubric_failed",
            "reason": "missing_docs",
            "wrote_files": False,
        }
    prompt = build_score_prompt(folder)
    if prompt is None:
        return {
            "outcome": "rubric_failed",
            "reason": "missing_prompt_inputs",
            "wrote_files": False,
        }
    wall = wall_seconds if wall_seconds is not None else DEFAULT_WALL_SECONDS
    events = max_events if max_events is not None else DEFAULT_MAX_EVENTS
    session_result = _run_score_session(
        prompt,
        spawn=spawn,
        model=model,
        effort=effort,
        wall_seconds=wall,
        max_events=events,
    )
    save_raw_attempt(folder, str(session_result.get("text") or ""))
    if session_result.get("outcome") != "ok":
        session_result["wrote_files"] = False
        return session_result
    parsed = parse_score_payload(str(session_result.get("text") or ""))
    if parsed is None:
        return {
            "outcome": "rubric_failed",
            "reason": "invalid_score_json",
            "wrote_files": False,
            "text": session_result.get("text"),
        }
    session_row = bind_scorecard_row(
        parsed,
        hashes=hashes,
        role="authoring_session",
        reviewer_run_id=f"{reviewer_run_id}-session",
    )
    rows = [session_row]
    blind_row = None
    if needs_independent_blind(session_row):
        blind_prompt = build_score_prompt(folder, independent=True)
        assert blind_prompt is not None
        blind_result = _run_score_session(
            blind_prompt,
            spawn=spawn,
            model=model,
            effort=effort,
            wall_seconds=wall,
            max_events=events,
        )
        save_raw_attempt(folder, str(blind_result.get("text") or ""))
        if blind_result.get("outcome") != "ok":
            blind_result["wrote_files"] = False
            blind_result["reason"] = blind_result.get("reason") or "independent_blind_failed"
            return blind_result
        blind_parsed = parse_score_payload(str(blind_result.get("text") or ""))
        if blind_parsed is None:
            return {
                "outcome": "rubric_failed",
                "reason": "invalid_blind_score_json",
                "wrote_files": False,
            }
        blind_row = bind_scorecard_row(
            blind_parsed,
            hashes=hashes,
            role="independent_blind",
            reviewer_run_id=f"{reviewer_run_id}-blind",
        )
        rows.append(blind_row)
    binding = choose_binding_row(session_row, blind_row)
    write_scorecards(folder, rows)
    copy_binding_into_manifest(folder, binding)
    return {
        "outcome": "ok",
        "wrote_files": True,
        "binding_resume": binding["resume"]["total"],
        "binding_cover_letter": binding["cover_letter"]["total"],
        "independent_blind": blind_row is not None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a sandboxed Stage 2 Agy rubric score (CR-121)."
    )
    parser.add_argument("folder", help="Submission folder with Resume.md and CoverLetter.md")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--effort", default=DEFAULT_EFFORT)
    args = parser.parse_args(argv)
    result = run_for_folder(
        Path(args.folder),
        model=args.model,
        effort=args.effort,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "text"}, indent=2))
    return 0 if result.get("outcome") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
