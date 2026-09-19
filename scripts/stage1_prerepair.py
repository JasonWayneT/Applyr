"""Deterministic Stage 1 pre-repair. No model call."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pm_years import parse_pm_years_of_experience, pm_years_hard_constraint
from submission_linter import lint_document

_YEAR_WORDS = {
    4: "four",
    5: "five",
    6: "six",
}
_DOCS = (("Resume.md", "resume"), ("CoverLetter.md", "cover_letter"))
_PUNCT_RULES = ("LR-014", "LR-006", "LR-015")
_WE_PATH = Path(__file__).resolve().parents[1] / "data" / "workExperience.md"


def _target_years(we_text: str | None = None) -> tuple[int, str]:
    source = we_text
    if source is None:
        source = _WE_PATH.read_text(encoding="utf-8") if _WE_PATH.exists() else ""
    years = parse_pm_years_of_experience(source)
    word = {7: "seven", 8: "eight", 9: "nine", 10: "ten"}.get(years, str(years))
    return years, word


def _fix_years_text(text: str, years: int, word: str) -> tuple[str, list[dict[str, str]]]:
    changes: list[dict[str, str]] = []
    updated = text
    word_alts = "|".join(_YEAR_WORDS.values())
    digits = "|".join(str(n) for n in range(4, years))

    def record(old: str, new: str) -> str:
        if old != new:
            changes.append({"from": old, "to": new})
        return new

    patterns = [
        (
            re.compile(rf"\b({word_alts})\s+years\s+of\s+experience\b", re.I),
            lambda m: record(m.group(0), f"{word} years of experience"),
        ),
        (
            re.compile(rf"\b({digits})\+?\s+years\s+of\s+experience\b", re.I),
            lambda m: record(m.group(0), f"{years} years of experience"),
        ),
        (
            re.compile(rf"\b(last|past)\s+({word_alts}|{digits})\+?\s+years\b", re.I),
            lambda m: record(m.group(0), f"{m.group(1)} {word} years"),
        ),
        (
            re.compile(rf"\bwith\s+({word_alts})\s+years\b", re.I),
            lambda m: record(m.group(0), f"with {word} years"),
        ),
        (
            re.compile(rf"\bwith\s+({digits})\+?\s+years\b", re.I),
            lambda m: record(m.group(0), f"with {years} years"),
        ),
        (
            re.compile(rf"\b({word_alts})\s+years\b", re.I),
            lambda m: record(m.group(0), f"{word} years"),
        ),
        (
            re.compile(rf"\b({digits})\+?\s+years\b", re.I),
            lambda m: record(m.group(0), f"{years} years"),
        ),
    ]
    for regex, repl in patterns:
        updated = regex.sub(repl, updated)
    return updated, changes


def _capitalize_after(prefix: str, rest: str) -> str:
    stripped = rest.lstrip()
    if not stripped:
        return prefix + rest
    return prefix + stripped[0].upper() + stripped[1:]


def _fix_semicolons(line: str) -> tuple[str, bool]:
    if ";" not in line:
        return line, False
    if line.count(";") > 1:
        return line, False
    left, right = line.split(";", 1)
    if not right.strip() or not re.search(r"[A-Za-z]", right):
        return line, False
    return _capitalize_after(left.rstrip() + ". ", right), True


def _fix_em_dashes(line: str) -> tuple[str, bool]:
    if "—" in line:
        if line.count("—") > 1:
            return line, False
        left, right = line.split("—", 1)
        return _capitalize_after(left.rstrip() + ". ", right), True
    if "--" in line and "---" not in line:
        if line.count("--") > 1:
            return line, False
        left, right = line.split("--", 1)
        return _capitalize_after(left.rstrip() + ". ", right), True
    return line, False


def _fix_elaboration_colon(line: str) -> tuple[str, bool]:
    match = re.search(r":\s+[A-Za-z]", line)
    if not match:
        return line, False
    if line[: match.start()].rstrip().endswith("*"):
        return line, False
    if line.count(":") > 1:
        return line, False
    left, right = line.split(":", 1)
    if not right.strip():
        return line, False
    return _capitalize_after(left.rstrip() + ". ", right), True


def _fix_punct_text(text: str, rule_id: str) -> tuple[str, list[dict[str, str]], list[dict[str, str]]]:
    fixer = {
        "LR-014": _fix_semicolons,
        "LR-006": _fix_em_dashes,
        "LR-015": _fix_elaboration_colon,
    }[rule_id]
    applied: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    out_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        newline = "\n" if line.endswith("\n") else ""
        body = line[:-1] if newline else line
        if line.endswith("\r\n"):
            newline = "\r\n"
            body = line[:-2]
        fixed, ok = fixer(body)
        if ok and fixed != body:
            applied.append({"from": body, "to": fixed})
            out_lines.append(fixed + newline)
        elif rule_id == "LR-014" and ";" in body:
            skipped.append({"rule_id": rule_id, "text": body, "reason": "unsafe semicolon rewrite"})
            out_lines.append(line)
        elif rule_id == "LR-006" and ("—" in body or ("--" in body and "---" not in body)):
            skipped.append({"rule_id": rule_id, "text": body, "reason": "unsafe dash rewrite"})
            out_lines.append(line)
        elif rule_id == "LR-015" and re.search(r":\s+[A-Za-z]", body):
            skipped.append({"rule_id": rule_id, "text": body, "reason": "unsafe colon rewrite"})
            out_lines.append(line)
        else:
            out_lines.append(line)
    return "".join(out_lines), applied, skipped


def apply_mechanical_fixes(
    folder: Path,
    *,
    we_text: str | None = None,
) -> dict[str, Any]:
    """Fix mechanical lint blocks in place. Returns a log. Never calls a model."""
    years: int | None = None
    word = ""
    years_constraint = ""
    try:
        years, word = _target_years(we_text)
        years_constraint = pm_years_hard_constraint(years)
    except (OSError, ValueError):
        years = None
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for name, doc_type in _DOCS:
        path = folder / name
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        text = original
        result = lint_document(text, doc_type, filename=name)
        rule_ids = {item.rule_id for item in result.blocks}
        if years is not None and "LR-013" in rule_ids:
            text, year_changes = _fix_years_text(text, years, word)
            for change in year_changes:
                applied.append({"rule_id": "LR-013", "file": name, **change})
        for rule_id in _PUNCT_RULES:
            if rule_id not in rule_ids and rule_id not in {
                item.rule_id for item in lint_document(text, doc_type, filename=name).blocks
            }:
                continue
            text, punct_applied, punct_skipped = _fix_punct_text(text, rule_id)
            for change in punct_applied:
                applied.append({"rule_id": rule_id, "file": name, **change})
            for row in punct_skipped:
                skipped.append({"file": name, **row})
        if text != original:
            path.write_text(text, encoding="utf-8")
    return {
        "applied": applied,
        "skipped": skipped,
        "changed": bool(applied),
        "years_constraint": years_constraint,
    }
