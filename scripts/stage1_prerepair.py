"""Deterministic Stage 1 pre-repair. No model call."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from author_from_packet import _normalize_provenance_unit
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


def _strip_bullet_marker(line: str) -> str:
    return re.sub(r"^\s*[*-]\s+", "", line).strip()


def _resync_provenance(folder: Path, doc_type: str, line_changes: list[dict[str, str]]) -> bool:
    """Rewrite matching claim_provenance.json bullet/sentence text after a
    mechanical punctuation fix changes a line's wording (found live on obie,
    2026-09-20: an LR-015 colon-split silently desynced the provenance record,
    turning a fully-cited bullet into a false 'uncited' finding on the very
    next verify pass -- the same failure class already documented for Agy
    repair calls, but here the culprit is this module's own auto-fix, which
    changes the document text but never touched the provenance file)."""
    prov_path = folder / "claim_provenance.json"
    if not prov_path.is_file() or not line_changes:
        return False
    try:
        provenance = json.loads(prov_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(provenance, dict):
        return False
    section = "resume_claims" if doc_type == "resume" else "cover_letter_claims"
    field = "bullet" if doc_type == "resume" else "sentence"
    rows = provenance.get(section)
    if not isinstance(rows, list):
        return False
    changed = False
    for change in line_changes:
        old_text = _strip_bullet_marker(change["from"])
        new_text = _strip_bullet_marker(change["to"])
        old_norm = _normalize_provenance_unit(old_text)
        for row in rows:
            if not isinstance(row, dict):
                continue
            value = row.get(field)
            if isinstance(value, str) and _normalize_provenance_unit(value) == old_norm:
                row[field] = new_text
                changed = True
    if changed:
        prov_path.write_text(
            json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return changed


def drop_uncited_units(folder: Path) -> list[dict[str, str]]:
    """Remove factual lines that have no cite when the rest of the draft is cited.

    A text-to-id map must already be coerced to v2. An empty cite file deletes
    nothing. Implements FR-265.
    """
    from author_from_packet import (
        _cover_factual_sentences,
        _normalize_provenance_unit,
        _professional_experience_bullets,
    )
    from run_stage1_repair import heal_provenance_file

    heal_provenance_file(folder)
    prov_path = folder / "claim_provenance.json"
    resume_path = folder / "Resume.md"
    letter_path = folder / "CoverLetter.md"
    if not prov_path.is_file() or not resume_path.is_file() or not letter_path.is_file():
        return []
    try:
        provenance = json.loads(prov_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(provenance, dict):
        return []

    def _covered(section: str, field: str) -> set[str]:
        covered: set[str] = set()
        for row in provenance.get(section) or []:
            if not isinstance(row, dict) or not row.get("claim_ids"):
                continue
            value = row.get(field)
            if isinstance(value, str) and value.strip():
                covered.add(_normalize_provenance_unit(value))
        return covered

    resume_text = resume_path.read_text(encoding="utf-8")
    letter_text = letter_path.read_text(encoding="utf-8")
    original_letter = letter_text
    covered_resume = _covered("resume_claims", "bullet")
    covered_letter = _covered("cover_letter_claims", "sentence")
    if not covered_resume and not covered_letter:
        return []
    applied: list[dict[str, str]] = []
    resume_lines = resume_text.splitlines()
    kept_resume: list[str] = []
    in_experience = False
    for line in resume_lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_experience = stripped[3:].strip().casefold() == "professional experience"
        if (
            in_experience
            and stripped.startswith(("* ", "- "))
            and _normalize_provenance_unit(stripped) not in covered_resume
        ):
            applied.append({"rule_id": "sentence_provenance", "file": "Resume.md", "from": stripped, "to": ""})
            continue
        kept_resume.append(line)
    new_resume = resume_text
    if any(row["file"] == "Resume.md" for row in applied):
        new_resume = "\n".join(kept_resume).rstrip() + "\n"
    for sentence in _cover_factual_sentences(letter_text):
        if _normalize_provenance_unit(sentence) in covered_letter:
            continue
        if sentence not in letter_text:
            continue
        letter_text = letter_text.replace(sentence, "", 1)
        applied.append(
            {"rule_id": "sentence_provenance", "file": "CoverLetter.md", "from": sentence, "to": ""}
        )
    new_letter = letter_text
    if any(row["file"] == "CoverLetter.md" for row in applied):
        new_letter = re.sub(r"[ \t]{2,}", " ", letter_text)
        new_letter = re.sub(r"\n{3,}", "\n\n", new_letter)
        if not new_letter.endswith("\n"):
            new_letter += "\n"
    if not applied:
        return []
    # A drop that creates a new hard block is not a fix. The uncited line
    # stays so repair can cite it. Implements FR-386.
    from submission_linter import collect_fidelity_hard_blocks

    before_ids = {
        item.rule_id for item in collect_fidelity_hard_blocks(resume_text, original_letter)
    }
    after_ids = {
        item.rule_id for item in collect_fidelity_hard_blocks(new_resume, new_letter)
    }
    if after_ids - before_ids:
        return []
    if new_resume != resume_text:
        resume_path.write_text(new_resume, encoding="utf-8")
    if new_letter != original_letter:
        letter_path.write_text(new_letter, encoding="utf-8")
    return applied


_PAST_EMPLOYER_HEADS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Cision", re.compile(r"\bCision\b")),
    ("Sterkly", re.compile(r"\bSterkly\b")),
    ("Zero To Sixty", re.compile(r"\bZero[\s-]+To[\s-]+Sixty\b", re.IGNORECASE)),
)


def _experience_roles(resume_text: str) -> list[tuple[str, list[str]]]:
    """Return (heading, bullets) for each role under Professional Experience."""
    roles: list[tuple[str, list[str]]] = []
    heading = ""
    bullets: list[str] = []
    in_experience = False
    for line in (resume_text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_experience and heading:
                roles.append((heading, bullets))
            in_experience = stripped[3:].strip().casefold() == "professional experience"
            heading = ""
            bullets = []
            continue
        if not in_experience:
            continue
        if stripped.startswith("### "):
            if heading:
                roles.append((heading, bullets))
            heading = stripped[4:].strip()
            bullets = []
            continue
        if stripped.startswith(("* ", "- ")):
            bullets.append(stripped[2:].strip())
    if in_experience and heading:
        roles.append((heading, bullets))
    return roles


def _cited_ids_for_bullet(provenance: dict[str, Any], bullet: str) -> list[str]:
    """Return claim ids already attached to this resume bullet."""
    target = _normalize_provenance_unit(bullet)
    for row in provenance.get("resume_claims") or []:
        if not isinstance(row, dict):
            continue
        if _normalize_provenance_unit(str(row.get("bullet") or "")) != target:
            continue
        return [str(item) for item in (row.get("claim_ids") or []) if str(item).strip()]
    return []


def _employer_sentence(employer: str, bullet: str) -> str:
    """Turn a cited bullet into one letter sentence that names the employer."""
    text = bullet.strip().rstrip(".")
    if re.search(re.escape(employer), text, re.IGNORECASE):
        sentence = text
    else:
        sentence = f"At {employer}, I {text[0].lower()}{text[1:]}"
    if not sentence.endswith("."):
        sentence += "."
    return sentence


def name_past_employer(folder: Path) -> list[dict[str, str]]:
    """Add one cited sentence when the letter names no past employer.

    The sentence is a cited resume bullet with the employer named. It does
    not invent a fact. Implements FR-386.
    """
    from submission_linter import check_letter_names_employer, collect_fidelity_hard_blocks

    letter_path = folder / "CoverLetter.md"
    resume_path = folder / "Resume.md"
    prov_path = folder / "claim_provenance.json"
    if not letter_path.is_file() or not resume_path.is_file() or not prov_path.is_file():
        return []
    letter = letter_path.read_text(encoding="utf-8")
    if not check_letter_names_employer(letter):
        return []
    if "Dear Hiring Manager," not in letter:
        return []
    try:
        provenance = json.loads(prov_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(provenance, dict):
        return []
    resume = resume_path.read_text(encoding="utf-8")
    chosen: tuple[str, str, list[str]] | None = None
    roles = _experience_roles(resume)
    for employer, pattern in _PAST_EMPLOYER_HEADS:
        for heading, bullets in roles:
            if not pattern.search(heading):
                continue
            for bullet in bullets:
                claim_ids = _cited_ids_for_bullet(provenance, bullet)
                if claim_ids:
                    chosen = (employer, bullet, claim_ids)
                    break
            if chosen:
                break
        if chosen:
            break
    if chosen is None:
        return []
    employer, bullet, claim_ids = chosen
    sentence = _employer_sentence(employer, bullet)
    head, tail = letter.split("Dear Hiring Manager,", 1)
    rest = tail.lstrip("\n")
    new_letter = head + "Dear Hiring Manager,\n\n" + sentence + "\n\n" + rest
    if not new_letter.endswith("\n"):
        new_letter += "\n"
    before_ids = {item.rule_id for item in collect_fidelity_hard_blocks(resume, letter)}
    after_ids = {item.rule_id for item in collect_fidelity_hard_blocks(resume, new_letter)}
    if "LR-045" in after_ids or (after_ids - before_ids):
        return []
    rows = provenance.get("cover_letter_claims")
    if not isinstance(rows, list):
        rows = []
    rows.insert(0, {"sentence": sentence, "claim_ids": claim_ids})
    provenance["cover_letter_claims"] = rows
    letter_path.write_text(new_letter, encoding="utf-8")
    prov_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return [{"rule_id": "LR-045", "file": "CoverLetter.md", "from": "", "to": sentence}]


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
        doc_line_changes: list[dict[str, str]] = []
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
                doc_line_changes.append(change)
            for row in punct_skipped:
                skipped.append({"file": name, **row})
        if text != original:
            path.write_text(text, encoding="utf-8")
        if doc_line_changes:
            _resync_provenance(folder, doc_type, doc_line_changes)
    for change in drop_uncited_units(folder):
        applied.append(change)
    for change in name_past_employer(folder):
        applied.append(change)
    return {
        "applied": applied,
        "skipped": skipped,
        "changed": bool(applied),
        "years_constraint": years_constraint,
    }
