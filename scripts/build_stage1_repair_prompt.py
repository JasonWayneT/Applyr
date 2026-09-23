#!/usr/bin/env python3
"""Build a compact Stage 1 repair prompt from a failed verify pass.

A failed draft must not trigger a full fresh authoring resample. The repair
prompt carries ranked findings (rule, file, line, offending text, suggestion),
the full current Resume.md and CoverLetter.md, the digest sections those rules
need, and packet excerpts for any cited claim IDs. It does not re-send the
full authoring prompt or the packet.

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
REPAIR_PROMPT_BYTE_TARGET = 16_000
AUTHOR_OUTPUT_DIR = "stage1_author_output"
FORWARDED_NOTES = "stage1_forwarded_findings.json"
REQUIRED_FILES = (
    "authoring_prompt.md",
    "Resume.md",
    "CoverLetter.md",
    "claim_provenance.json",
)
_BLOCKING_RE = re.compile(
    r"fabrication|invent|attribution|employer mismatch|LR-006|LR-013|LR-014|LR-015|"
    r"semicolon|em dash|page count|one page|_pdf_page_count|"
    r"optimization_bar|required evidence unused|extra_packet|identity|"
    r"HARD_BLOCK|forbidden punctuation",
    re.I,
)
_FINDING_RE = re.compile(r"^(FAIL|WARN)\b", re.I)
_RULE_RE = re.compile(r"\[([A-Z]{1,3}-\d+)\]")
_CLAIM_RE = re.compile(r"\b(?:ACC|MET|VOC|SKL)-\d+\b")


def _resolve_claim_ids(raw_ids: list[str], keys: object) -> list[str]:
    """Expand bare short-form IDs ("ACC-101") to the full excerpt-dict key(s)
    they actually appear as ("ACC-101-SCOPE"). Real packet excerpts are keyed
    on the full form (checked against 17 live packets on 2026-09-19; every
    ACC key carried a suffix, MET/VOC keys did not). A finding mentioning only
    the bare numeric ID would otherwise never match `excerpts.get(claim_id)`,
    silently dropping the excerpt the repair needed most.
    """
    if not isinstance(keys, dict):
        return raw_ids
    resolved: list[str] = []
    for raw in raw_ids:
        if raw in keys:
            resolved.append(raw)
            continue
        prefix = raw + "-"
        resolved.extend(k for k in keys if k.startswith(prefix))
    return list(dict.fromkeys(resolved)) or raw_ids
_LINE_RE = re.compile(r"\bline\s+(\d+)\b", re.I)
_LINT_FILE_RE = re.compile(r"\[lint/([^\]]+)\]")
_DIGEST_FOR_RULE = {
    "LR-013": (
        "11. Before You Finish — Self-Check",
        "2. Resume Structure",
    ),
    "LR-014": ("7. Forbidden Formatting",),
    "LR-006": ("7. Forbidden Formatting",),
    "LR-015": ("7. Forbidden Formatting",),
    "LR-016": ("5. Cover Letter Argument Rules",),
    "LR-031": ("2. Resume Structure",),
    "LW-039": ("10. Collaboration Framing",),
    "LR-020": ("2. Resume Structure",),
    "LR-021": ("2. Resume Structure",),
    "optimization_bar": ("1b. Optimization bar (hard — Round 4)",),
    "evidence_utilization": (
        "1. Closed-World Rule (hardest constraint)",
        "1b. Optimization bar (hard — Round 4)",
    ),
    "stage1_quality": (
        "2. Resume Structure",
        "9. Exclusion Zones — What Jason Is NOT",
    ),
    "identity": ("2. Resume Structure",),
    "extra_packet": ("1. Closed-World Rule (hardest constraint)",),
}
_DEFAULT_DIGEST = ("11. Before You Finish — Self-Check",)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_repair_state(folder: Path) -> dict:
    path = folder / REPAIR_STATE_NAME
    default = {
        "attempts": 0,
        "previous_findings_hash": "",
        "pending_findings_hash": "",
        "last_outcome": "",
        "blocking": [],
        "forwarded": [],
        "auto_fixes": [],
        "auto_fix_skipped": [],
        "no_progress_streak": 0,
        "timeout_attempts": 0,
        "next_retry_at": None,
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
    try:
        streak = int(payload.get("no_progress_streak") or 0)
    except (TypeError, ValueError):
        streak = 0
    try:
        timeout_attempts = int(payload.get("timeout_attempts") or 0)
    except (TypeError, ValueError):
        timeout_attempts = 0
    default.update(
        {
            "attempts": max(0, attempts),
            "previous_findings_hash": str(payload.get("previous_findings_hash") or ""),
            "pending_findings_hash": str(payload.get("pending_findings_hash") or ""),
            "last_outcome": str(payload.get("last_outcome") or ""),
            "blocking": list(payload.get("blocking") or []),
            "forwarded": list(payload.get("forwarded") or []),
            "auto_fixes": list(payload.get("auto_fixes") or []),
            "auto_fix_skipped": list(payload.get("auto_fix_skipped") or []),
            "no_progress_streak": max(0, streak),
            "timeout_attempts": max(0, timeout_attempts),
            "next_retry_at": payload.get("next_retry_at"),
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


def _strip_rank(raw: str) -> str:
    return re.sub(r"^\s*\d+\.\s*", "", raw).rstrip()


def _finding_lines(findings: str) -> list[str]:
    kept: list[str] = []
    pending = ""
    for raw in findings.splitlines():
        line = _strip_rank(raw)
        stripped = line.strip()
        if not stripped:
            if pending:
                kept.append(pending)
                pending = ""
            continue
        if _FINDING_RE.match(stripped) or stripped.startswith("FAIL [") or stripped.startswith("WARN ["):
            if pending:
                kept.append(pending)
            pending = stripped
            continue
        if pending and (
            stripped.startswith("[")
            or stripped.lower().startswith(("suggestion:", "offending:", "line "))
        ):
            pending = pending + " | " + stripped
            continue
        if pending:
            kept.append(pending)
            pending = ""
            if _FINDING_RE.match(stripped):
                pending = stripped
    if pending:
        kept.append(pending)
    return kept


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


def _load_digest() -> str:
    try:
        from generate_authoring_rule_digest import generate_digest

        content, _version = generate_digest()
        return content
    except Exception:
        path = _REPO_ROOT / "data" / "authoring_rule_digest.md"
        if path.is_file():
            return path.read_text(encoding="utf-8")
        return ""


def _load_packet(folder: Path) -> dict:
    path = folder / "authoring_packet.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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


def _maybe_requeue_repair(
    folder: Path,
    *,
    queue_conn: object | None = None,
    data_root: Path | None = None,
) -> None:
    from pipeline_queue import requeue_paused_for_repair

    requeue_paused_for_repair(folder, conn=queue_conn, data_root=data_root)


def _is_lint_summary(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith(("FAIL [lint/", "WARN [lint/")):
        return False
    if _RULE_RE.search(stripped) and _LINE_RE.search(stripped):
        return False
    return "hard block" in stripped.lower() or stripped.startswith("WARN [lint/")


def _format_lint_item(kind: str, filename: str, item: object, text: str) -> str:
    from author_from_packet import _format_lint_item as shared

    return shared(kind, filename, item, text)


def expand_lint_findings(findings: str, drafts: dict[str, str]) -> str:
    """Replace summary-only lint FAIL lines with rule/line/suggestion/offending rows."""
    rows = findings.splitlines()
    if not any(_is_lint_summary(_strip_rank(row)) for row in rows):
        return findings.strip()
    from submission_linter import lint_document

    lint_lines: list[str] = []
    for name, doc_type in (("Resume.md", "resume"), ("CoverLetter.md", "cover_letter")):
        text = drafts.get(name) or ""
        if not text:
            continue
        result = lint_document(text, doc_type, filename=name)
        for block in result.blocks:
            lint_lines.append(_format_lint_item("FAIL", name, block, text))
    kept: list[str] = []
    skip_indent = False
    for raw in rows:
        line = _strip_rank(raw)
        stripped = line.strip()
        if _is_lint_summary(stripped):
            skip_indent = True
            continue
        if skip_indent and stripped.startswith("["):
            continue
        skip_indent = False
        if stripped:
            kept.append(stripped)
    return "\n".join(lint_lines + kept).strip()


def _digest_sections(digest_text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    if not digest_text.strip():
        return sections
    parts = re.split(r"\n(?=## )", digest_text)
    for part in parts:
        match = re.match(r"##\s+(.+)", part)
        if not match:
            continue
        sections[match.group(1).strip()] = part.strip()
    return sections


def _rules_in_findings(findings: str) -> set[str]:
    rules = set(_RULE_RE.findall(findings))
    lower = findings.lower()
    for token in (
        "optimization_bar",
        "evidence_utilization",
        "stage1_quality",
        "identity",
        "extra_packet",
    ):
        if token in lower:
            rules.add(token)
    return rules


def _relevant_digest(findings: str, digest_text: str) -> str:
    sections = _digest_sections(digest_text)
    wanted: list[str] = []
    for rule in sorted(_rules_in_findings(findings)):
        for title in _DIGEST_FOR_RULE.get(rule, ()):
            if title not in wanted:
                wanted.append(title)
    if not wanted:
        wanted.extend(_DEFAULT_DIGEST)
    chunks = [sections[title] for title in wanted if title in sections]
    return "\n\n".join(chunks).strip()


def _paragraph_at(text: str, line_no: int) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    idx = max(0, min(line_no - 1, len(lines) - 1))
    start = idx
    end = idx
    while start > 0 and lines[start - 1].strip():
        start -= 1
    while end + 1 < len(lines) and lines[end + 1].strip():
        end += 1
    heading = start - 1
    while heading >= 0 and not lines[heading].strip():
        heading -= 1
    if heading >= 0 and lines[heading].lstrip().startswith("#"):
        start = heading
        prior = heading - 1
        while prior >= 0 and not lines[prior].strip():
            prior -= 1
        if prior >= 0 and lines[prior].lstrip().startswith("#"):
            start = prior
    return "\n".join(lines[start : end + 1]).strip()


def _search_paragraph(text: str, needles: list[str]) -> str:
    lowered = text.lower()
    for needle in needles:
        if not needle or len(needle) < 4:
            continue
        pos = lowered.find(needle.lower())
        if pos < 0:
            continue
        line_no = text[:pos].count("\n") + 1
        return _paragraph_at(text, line_no)
    return ""


def _needles_for_line(line: str) -> list[str]:
    offending = ""
    match = re.search(r" offending: (.+)$", line)
    if match:
        offending = match.group(1).strip().strip("'\"")
    needles = []
    if offending:
        needles.append(offending[:80])
    needles.extend(re.findall(r"[A-Za-z][A-Za-z0-9'’.-]{5,}", line))
    return needles


def _files_for_line(line: str) -> list[str]:
    match = _LINT_FILE_RE.search(line)
    if match:
        name = match.group(1).strip()
        if name in ("Resume.md", "CoverLetter.md", "claim_provenance.json"):
            return [name]
        if "resume" in name.lower() and "cover" not in name.lower():
            return ["Resume.md"]
        if "cover" in name.lower():
            return ["CoverLetter.md"]
    names: list[str] = []
    if "resume" in line.lower():
        names.append("Resume.md")
    if "cover" in line.lower() or "letter" in line.lower():
        names.append("CoverLetter.md")
    if "provenance" in line.lower():
        names.append("claim_provenance.json")
    return names


def _local_context(drafts: dict[str, str], findings: str) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for line in _finding_lines(findings):
        line_match = _LINE_RE.search(line)
        files = _files_for_line(line) or ["Resume.md", "CoverLetter.md"]
        snippet = ""
        if line_match:
            for name in files:
                text = drafts.get(name) or ""
                if not text:
                    continue
                snippet = _paragraph_at(text, int(line_match.group(1)))
                if snippet:
                    key = name + "::" + snippet
                    if key not in seen:
                        seen.add(key)
                        parts.append(f"### {name}\n\n{snippet}")
                    break
            if snippet:
                continue
        needles = _needles_for_line(line)
        for name in files:
            text = drafts.get(name) or ""
            snippet = _search_paragraph(text, needles)
            if snippet:
                key = name + "::" + snippet
                if key not in seen:
                    seen.add(key)
                    parts.append(f"### {name}\n\n{snippet}")
                break
        else:
            for name in files:
                text = (drafts.get(name) or "").strip()
                if text and len(text) <= 1500:
                    key = name + "::all"
                    if key not in seen:
                        seen.add(key)
                        parts.append(f"### {name}\n\n{text}")
    return "\n\n".join(parts).strip()


_UNCITED_RE = re.compile(
    r"uncited (?:bullet|factual sentence)\s*[:\"]?\s*\"([^\"]+)\"", re.I
)


def _has_uncited_finding(findings: str) -> bool:
    return bool(_UNCITED_RE.search(findings))


def _packet_support(findings: str, packet: dict | None) -> str:
    if not packet:
        return ""
    chunks: list[str] = []
    claims = list(dict.fromkeys(_CLAIM_RE.findall(findings)))
    excerpts = packet.get("excerpts") if isinstance(packet.get("excerpts"), dict) else {}
    constraints = (
        packet.get("claim_constraints")
        if isinstance(packet.get("claim_constraints"), dict)
        else {}
    )
    # A sentence_provenance failure ("uncited bullet/sentence") never names a
    # claim ID in its finding text -- that's the whole problem. Without this,
    # the repair has no real source material for that sentence, so it either
    # keeps regenerating an uncited paraphrase (whack-a-mole across rounds) or
    # invents something new. Packets are small (a few KB across ~15-20 claims),
    # so on an uncited finding we hand over every excerpt rather than try to
    # guess which one applies -- the model can match it, or find none apply
    # and remove the sentence instead of leaving it unsupported.
    if _has_uncited_finding(findings):
        for claim_id, excerpt in excerpts.items():
            if excerpt:
                chunks.append(f"{claim_id} excerpt:\n{excerpt.strip()}")
    else:
        for claim_id in _resolve_claim_ids(claims, excerpts):
            excerpt = excerpts.get(claim_id)
            if excerpt:
                chunks.append(f"{claim_id} excerpt:\n{excerpt.strip()}")
    for claim_id in _resolve_claim_ids(claims, constraints):
        constraint = constraints.get(claim_id)
        if constraint:
            chunks.append(
                f"{claim_id} constraints:\n{json.dumps(constraint, ensure_ascii=False)}"
            )
    rules = _rules_in_findings(findings)
    hard = packet.get("hard_constraints") if isinstance(packet.get("hard_constraints"), list) else []
    if "LR-013" in rules or re.search(r"\byears?\b", findings, re.I):
        for item in hard:
            text = str(item)
            if re.search(r"experience|years", text, re.I):
                chunks.append(text)
    return "\n\n".join(chunks).strip()


def _provenance_support(drafts: dict[str, str], findings: str) -> str:
    claims = list(dict.fromkeys(_CLAIM_RE.findall(findings)))
    if not claims:
        return ""
    raw = drafts.get("claim_provenance.json") or ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    all_rows: list[dict] = []
    known_ids: dict[str, None] = {}
    if isinstance(payload, dict):
        for rows in payload.values():
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                all_rows.append(row)
                for cid in row.get("claim_ids") or []:
                    known_ids[str(cid)] = None
    resolved = _resolve_claim_ids(claims, known_ids)
    kept: list[dict] = []
    for row in all_rows:
        ids = [str(x) for x in (row.get("claim_ids") or [])]
        if any(cid in ids for cid in resolved):
            kept.append(row)
    if not kept:
        return ""
    return json.dumps(kept, indent=2, ensure_ascii=False)


def build_repair_prompt(
    drafts: dict[str, str],
    findings: str,
    *,
    digest_text: str = "",
    packet: dict | None = None,
) -> str:
    ranked = rank_findings(findings)
    digest = _relevant_digest(findings, digest_text)
    packet_bits = _packet_support(findings, packet)
    resume = (drafts.get("Resume.md") or "").rstrip()
    letter = (drafts.get("CoverLetter.md") or "").rstrip()
    parts = [
        "# Stage 1 repair",
        "",
        "You are repairing an Applyr draft that failed mechanical validation.",
        "Fix ONLY the ranked findings listed below. Do not rewrite sections the findings do not name.",
        "Keep everything else.",
        "Return the full corrected Resume.md and CoverLetter.md as fenced blocks labeled Resume.md and CoverLetter.md.",
        "If a finding is an uncited bullet or sentence: find the claim ID below whose excerpt actually supports it, "
        "and include claim_provenance.json as a third fenced block adding or updating that sentence's citation to "
        "that claim ID. If no excerpt below actually supports it, remove the sentence -- do not invent a citation "
        "and do not leave it uncited. The same rule applies to any other sentence you add or reword: it must be "
        "backed by one of the excerpts below, and its citation must be in your claim_provenance.json output.",
        "If you did not touch any previously-cited or new factual sentence, omit claim_provenance.json to keep the current file.",
        "Don't use tools or files.",
        "Do not load workExperience.md, master_claims.json, AGENTS.md, or agent_context_pack.md.",
        "",
        "## Findings (ranked)",
        "",
        ranked,
        "",
        "## Current Resume.md",
        "",
        resume,
        "",
        "## Current CoverLetter.md",
        "",
        letter,
        "",
    ]
    if digest:
        parts.extend(["## Relevant digest", "", digest, ""])
    if packet_bits:
        parts.extend(["## Packet excerpts", "", packet_bits, ""])
    return "\n".join(parts).rstrip() + "\n"


def build_for_folder(
    folder: Path,
    *,
    findings_text: str | None = None,
    queue_conn: object | None = None,
    data_root: Path | None = None,
) -> tuple[int, str]:
    folder = folder.resolve()
    missing = [name for name in REQUIRED_FILES if not (folder / name).is_file()]
    if missing:
        return 1, "missing required files: " + ", ".join(missing)

    findings = collect_findings(folder, findings_text)
    from stage1_prerepair import apply_mechanical_fixes

    auto = apply_mechanical_fixes(folder)
    state = load_repair_state(folder)
    state["auto_fixes"] = auto.get("applied") or []
    state["auto_fix_skipped"] = auto.get("skipped") or []
    if auto.get("changed") and findings_text is None:
        findings = collect_findings(folder, None)
        if not findings:
            state["last_outcome"] = "auto_fixed"
            state["blocking"] = []
            save_repair_state(folder, state)
            _maybe_requeue_repair(folder, queue_conn=queue_conn, data_root=data_root)
            return 0, "AUTO_FIXED — mechanical findings cleared without Agy"
    if not findings:
        return 0, "no repair needed — verify produced no findings"

    drafts = _load_drafts(folder)
    findings = expand_lint_findings(findings, drafts)
    fingerprint = findings_fingerprint(findings)
    blocking, forwarded = classify_findings(findings)
    if (
        state.get("last_outcome") == "wrote"
        and fingerprint
        and fingerprint == str(state.get("pending_findings_hash") or "")
    ):
        return 0, (
            f"WROTE {REPAIR_PROMPT_NAME} — already waiting for sandboxed repair. "
            "Run python scripts/run_stage1_repair.py. Do not requeue until artifacts exist."
        )
    if state["attempts"] > 0 and fingerprint and fingerprint == state["previous_findings_hash"]:
        _merge_forwarded(folder, forwarded)
        state["last_outcome"] = "no_progress_blocking" if blocking else "no_progress_forward"
        state["blocking"] = blocking
        state["forwarded"] = forwarded
        if blocking:
            # The findings did not change, so another identical repair will not
            # either. Park the job instead of claiming it again. Implements FR-378.
            try:
                streak = int(state.get("no_progress_streak") or 0)
            except (TypeError, ValueError):
                streak = 0
            state["no_progress_streak"] = max(streak, 2)
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

    prompt = build_repair_prompt(
        drafts,
        findings,
        digest_text=_load_digest(),
        packet=_load_packet(folder),
    )
    (folder / REPAIR_PROMPT_NAME).write_text(prompt, encoding="utf-8")
    attempts = state["attempts"] + 1
    save_repair_state(
        folder,
        {
            **state,
            "attempts": attempts,
            "pending_findings_hash": fingerprint,
            "last_outcome": "wrote",
            "blocking": blocking,
            "forwarded": forwarded,
        },
    )
    return 0, (
        f"WROTE {REPAIR_PROMPT_NAME} — repair round {attempts}. "
        "Run python scripts/run_stage1_repair.py. Requeue only after valid "
        "repaired files are written."
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
