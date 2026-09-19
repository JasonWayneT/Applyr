#!/usr/bin/env python3
"""Build a Stage 1 repair prompt from a failed verify pass.

A failed draft must not trigger a full fresh authoring resample. This script
assembles one isolated prompt: the original authoring_prompt.md, the failed
Resume.md / CoverLetter.md / claim_provenance.json, and a ranked findings
list. The repair session still never receives workExperience.md, claims,
AGENTS.md, or the context pack.

Loop until verify passes or a round makes no progress (same findings as the
previous round). On no progress, truth/format blocks stay blocking and are
logged. Everything else is forwarded to Stage 2.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))

REPAIR_STATE_NAME = "stage1_repair_state.json"
REPAIR_PROMPT_NAME = "stage1_repair_prompt.md"
AUTHOR_OUTPUT_DIR = "stage1_author_output"
FORWARDED_NOTES = "stage1_forwarded_findings.json"
REQUIRED_FILES = (
    "authoring_prompt.md",
    "Resume.md",
    "CoverLetter.md",
    "claim_provenance.json",
)
_BLOCKING_RE = re.compile(
    r"fabrication|invent|attribution|employer mismatch|LR-006|LR-014|LR-015|"
    r"semicolon|em dash|page count|one page|_pdf_page_count|"
    r"optimization_bar|required evidence unused|extra_packet|identity|"
    r"HARD_BLOCK|forbidden punctuation",
    re.I,
)
_FINDING_RE = re.compile(r"^(FAIL|WARN)\b", re.I)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_repair_state(folder: Path) -> dict:
    path = folder / REPAIR_STATE_NAME
    default = {
        "attempts": 0,
        "previous_findings_hash": "",
        "last_outcome": "",
        "blocking": [],
        "forwarded": [],
    }
    if not path.is_file():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    if not isinstance(payload, dict):
        return default
    try:
        attempts = int(payload.get("attempts") or 0)
    except (TypeError, ValueError):
        attempts = 0
    default.update(
        {
            "attempts": max(0, attempts),
            "previous_findings_hash": str(payload.get("previous_findings_hash") or ""),
            "last_outcome": str(payload.get("last_outcome") or ""),
            "blocking": list(payload.get("blocking") or []),
            "forwarded": list(payload.get("forwarded") or []),
        }
    )
    return default


def save_repair_state(folder: Path, payload: dict) -> None:
    body = dict(payload)
    body["updated_at"] = _utc_now()
    (folder / REPAIR_STATE_NAME).write_text(
        json.dumps(body, indent=2) + "\n", encoding="utf-8"
    )


def collect_findings(folder: Path, findings_text: str | None) -> str:
    if findings_text is not None:
        return findings_text.strip()
    from author_from_packet import run_verify_only

    buf = io.StringIO()
    with redirect_stdout(buf):
        passed = run_verify_only(folder)
    text = buf.getvalue().strip()
    if passed:
        return ""
    return text


def _finding_lines(findings: str) -> list[str]:
    lines: list[str] = []
    for raw in findings.splitlines():
        line = re.sub(r"^\s*\d+\.\s*", "", raw).strip()
        if _FINDING_RE.match(line) or line.startswith("FAIL [") or line.startswith("WARN ["):
            lines.append(line)
    return lines


def findings_fingerprint(findings: str) -> str:
    kept = sorted(_finding_lines(findings))
    return hashlib.sha256("\n".join(kept).encode("utf-8")).hexdigest()


def classify_findings(findings: str) -> tuple[list[str], list[str]]:
    blocking: list[str] = []
    forwarded: list[str] = []
    for line in _finding_lines(findings):
        if line.startswith("WARN [") and not _BLOCKING_RE.search(line):
            forwarded.append(line)
            continue
        if _BLOCKING_RE.search(line) or line.startswith("FAIL ["):
            blocking.append(line)
        else:
            forwarded.append(line)
    return blocking, forwarded


def rank_findings(findings: str) -> str:
    blocking, forwarded = classify_findings(findings)
    ranked = blocking + forwarded
    if not ranked:
        body = findings.strip() or "(no findings text)"
        return body
    return "\n".join(f"{i}. {line}" for i, line in enumerate(ranked, 1))


def _load_drafts(folder: Path) -> dict[str, str]:
    snapshot = folder / AUTHOR_OUTPUT_DIR
    source = snapshot if all((snapshot / name).is_file() for name in REQUIRED_FILES[1:]) else folder
    return {
        name: (source / name).read_text(encoding="utf-8")
        for name in ("Resume.md", "CoverLetter.md", "claim_provenance.json")
    }


def _merge_forwarded(folder: Path, forwarded: list[str]) -> None:
    path = folder / FORWARDED_NOTES
    existing: dict = {}
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                existing = payload
        except (OSError, json.JSONDecodeError):
            existing = {}
    notes = list(existing.get("repair_forwarded") or [])
    for line in forwarded:
        if line not in notes:
            notes.append(line)
    existing.setdefault("schema", "stage1_forwarded_findings/v1")
    existing["repair_forwarded"] = notes
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")


def build_repair_prompt(authoring_prompt: str, drafts: dict[str, str], findings: str) -> str:
    ranked = rank_findings(findings)
    parts = [
        "# Stage 1 repair",
        "",
        "You are repairing an Applyr draft that failed mechanical validation.",
        "Fix ONLY the ranked findings listed below. Do not rewrite sections the findings do not name.",
        "Keep everything else. Return the full Resume.md, CoverLetter.md, and claim_provenance.json.",
        "Do not load workExperience.md, master_claims.json, AGENTS.md, or agent_context_pack.md.",
        "Do not use tools. Do not read other files.",
        "",
        "## Findings (ranked)",
        "",
        ranked,
        "",
        "## Original authoring prompt",
        "",
        authoring_prompt.strip(),
        "",
        "## Current Resume.md",
        "",
        drafts["Resume.md"].rstrip(),
        "",
        "## Current CoverLetter.md",
        "",
        drafts["CoverLetter.md"].rstrip(),
        "",
        "## Current claim_provenance.json",
        "",
        drafts["claim_provenance.json"].rstrip(),
        "",
    ]
    return "\n".join(parts)


def build_for_folder(
    folder: Path,
    *,
    findings_text: str | None = None,
) -> tuple[int, str]:
    folder = folder.resolve()
    missing = [name for name in REQUIRED_FILES if not (folder / name).is_file()]
    if missing:
        return 1, "missing required files: " + ", ".join(missing)

    findings = collect_findings(folder, findings_text)
    if not findings:
        return 0, "no repair needed — verify produced no findings"

    state = load_repair_state(folder)
    fingerprint = findings_fingerprint(findings)
    blocking, forwarded = classify_findings(findings)
    if state["attempts"] > 0 and fingerprint and fingerprint == state["previous_findings_hash"]:
        _merge_forwarded(folder, forwarded)
        state["last_outcome"] = "no_progress_blocking" if blocking else "no_progress_forward"
        state["blocking"] = blocking
        state["forwarded"] = forwarded
        save_repair_state(folder, state)
        if blocking:
            return 2, (
                "NO_PROGRESS — same findings as the previous repair round. "
                "Blocking: " + "; ".join(blocking)
            )
        return 0, (
            "NO_PROGRESS — remaining findings forwarded to "
            f"{FORWARDED_NOTES}. Continue to Stage 2."
        )

    drafts = _load_drafts(folder)
    prompt = build_repair_prompt(
        (folder / "authoring_prompt.md").read_text(encoding="utf-8"),
        drafts,
        findings,
    )
    (folder / REPAIR_PROMPT_NAME).write_text(prompt + "\n", encoding="utf-8")
    attempts = state["attempts"] + 1
    save_repair_state(
        folder,
        {
            "attempts": attempts,
            "previous_findings_hash": fingerprint,
            "last_outcome": "wrote",
            "blocking": blocking,
            "forwarded": forwarded,
        },
    )
    return 0, (
        f"WROTE {REPAIR_PROMPT_NAME} — repair round {attempts}. "
        "Paste that file only into a fresh Agy session. Loop until verify "
        "passes or a round makes no progress."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build an isolated Stage 1 repair prompt from verify findings."
    )
    parser.add_argument("folder", help="Submission folder (pending_review or submissions)")
    parser.add_argument(
        "--findings",
        help="Optional findings text file. Default: run author_from_packet --verify-only.",
    )
    args = parser.parse_args(argv)
    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"ERROR: {folder} is not a directory", file=sys.stderr)
        return 1
    findings_text = None
    if args.findings:
        findings_path = Path(args.findings)
        findings_text = findings_path.read_text(encoding="utf-8")
    code, message = build_for_folder(folder, findings_text=findings_text)
    print(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
