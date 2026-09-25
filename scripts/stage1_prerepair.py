"""Deterministic Stage 1 pre-repair. No model call."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from author_from_packet import _normalize_provenance_unit
from pm_years import parse_pm_years_of_experience, pm_years_hard_constraint
from submission_linter import (
    _DRAFT_DAY_RE,
    _DRAFT_WEEK_RE,
    _DRAFTING_CONTEXT_RE,
    _MET13_PAIR_RE,
    _hedge_units,
    lint_document,
)

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


def collapse_hedged_100k(folder: Path) -> list[dict[str, str]]:
    """Rewrite a hedged $100,000 to $100K.

    The career figure is roughly $100K. A precise $100,000 is unapproved.
    A sentence with no hedge word is left alone. Implements FR-403.
    """
    applied: list[dict[str, str]] = []
    for name in ("Resume.md", "CoverLetter.md"):
        path = folder / name
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        updated = _collapse_hedged_100k_text(original)
        if updated == original:
            continue
        path.write_text(updated, encoding="utf-8")
        applied.append(
            {"rule_id": "FR-403", "file": name, "from": "$100,000", "to": "$100K"}
        )
    return applied


def _collapse_hedged_100k_text(text: str) -> str:
    """Return text with a hedged $100,000 written as $100K."""
    hedge = re.compile(r"\b(?:roughly|about|estimated|approximately)\b", re.IGNORECASE)

    def _span(index: int) -> str:
        breaks = [text.rfind(mark, 0, index) for mark in ".!?\n"]
        start = max(breaks) + 1
        ends = [text.find(mark, index) for mark in ".!?\n"]
        ends = [pos for pos in ends if pos >= 0]
        stop = min(ends) + 1 if ends else len(text)
        return text[start:stop]

    pieces: list[str] = []
    cursor = 0
    for match in re.finditer(r"\$100,000\b", text):
        if not hedge.search(_span(match.start())):
            continue
        pieces.append(text[cursor:match.start()])
        pieces.append("$100K")
        cursor = match.end()
    pieces.append(text[cursor:])
    return "".join(pieces)


_OWNERSHIP_TO_CONTRIBUTED = re.compile(
    r"\b(?:designed and built|built and designed|designed|built)\b",
    re.IGNORECASE,
)


def soften_contributed_ownership(folder: Path) -> list[dict[str, str]]:
    """Reword a contributed claim that uses designed or built.

    The warning still fires on the original wording. An owned claim is left
    unchanged. Implements FR-407.
    """
    from submission_linter import check_attribution_verb_strength, collect_fidelity_hard_blocks

    resume_path = folder / "Resume.md"
    letter_path = folder / "CoverLetter.md"
    resume = resume_path.read_text(encoding="utf-8") if resume_path.is_file() else ""
    letter = letter_path.read_text(encoding="utf-8") if letter_path.is_file() else ""
    hits = check_attribution_verb_strength(resume, letter)
    if not hits:
        return []
    new_resume = resume
    new_letter = letter
    applied: list[dict[str, str]] = []
    resume_changes: list[dict[str, str]] = []
    letter_changes: list[dict[str, str]] = []
    for hit in hits:
        match = re.search(r'"([^"]+)"\s*$', hit.message or "")
        if not match:
            continue
        unit = match.group(1)
        if not _OWNERSHIP_TO_CONTRIBUTED.search(unit):
            continue
        revised = _OWNERSHIP_TO_CONTRIBUTED.sub("contributed to", unit)
        if revised == unit:
            continue
        if unit in new_resume:
            new_resume = new_resume.replace(unit, revised, 1)
            resume_changes.append({"from": unit, "to": revised})
            applied.append({"rule_id": "LW-028", "file": "Resume.md", "from": unit, "to": revised})
        elif unit in new_letter:
            new_letter = new_letter.replace(unit, revised, 1)
            letter_changes.append({"from": unit, "to": revised})
            applied.append(
                {"rule_id": "LW-028", "file": "CoverLetter.md", "from": unit, "to": revised}
            )
    if not applied:
        return []
    before_ids = {item.rule_id for item in collect_fidelity_hard_blocks(resume, letter)}
    after_ids = {item.rule_id for item in collect_fidelity_hard_blocks(new_resume, new_letter)}
    if after_ids - before_ids:
        return []
    if new_resume != resume and resume_path.is_file():
        resume_path.write_text(new_resume, encoding="utf-8")
        _resync_provenance(folder, "resume", resume_changes)
    if new_letter != letter and letter_path.is_file():
        letter_path.write_text(new_letter, encoding="utf-8")
        _resync_provenance(folder, "cover_letter", letter_changes)
    return applied


def rewrite_bypass_ingestion(folder: Path) -> list[dict[str, str]]:
    """Rename an ingestion phrase in the 40% drop-off story.

    That story is not an ingestion pipeline. The 40% outcome stays.
    A sentence without that story is left unchanged. Implements FR-406.
    """
    from submission_linter import (
        _ACC102_INGESTION_RE,
        _ACC102_METRIC_RE,
        _ACC102_STORY_RE,
        _split_resume_bullets,
        _split_sentences,
    )

    def _replacement(match: re.Match[str]) -> str:
        word = match.group(0).lower()
        if word.endswith("pipelines"):
            return "ETL paths"
        if word.endswith("loss"):
            return "data loss"
        return "ETL path"

    def _rewrite_unit(unit: str) -> str:
        if not (_ACC102_METRIC_RE.search(unit) and _ACC102_STORY_RE.search(unit)):
            return unit
        if not _ACC102_INGESTION_RE.search(unit):
            return unit
        return _ACC102_INGESTION_RE.sub(_replacement, unit)

    applied: list[dict[str, str]] = []
    resume_path = folder / "Resume.md"
    letter_path = folder / "CoverLetter.md"
    resume = resume_path.read_text(encoding="utf-8") if resume_path.is_file() else ""
    letter = letter_path.read_text(encoding="utf-8") if letter_path.is_file() else ""
    new_resume = resume
    new_letter = letter
    resume_changes: list[dict[str, str]] = []
    letter_changes: list[dict[str, str]] = []
    for unit in _split_resume_bullets(resume):
        revised = _rewrite_unit(unit)
        if revised == unit or unit not in new_resume:
            continue
        new_resume = new_resume.replace(unit, revised, 1)
        resume_changes.append({"from": unit, "to": revised})
        applied.append({"rule_id": "LR-038", "file": "Resume.md", "from": unit, "to": revised})
    if letter:
        for paragraph in re.split(r"\n\s*\n", letter):
            for unit in _split_sentences(paragraph):
                revised = _rewrite_unit(unit)
                if revised == unit or unit not in new_letter:
                    continue
                new_letter = new_letter.replace(unit, revised, 1)
                letter_changes.append({"from": unit, "to": revised})
                applied.append(
                    {"rule_id": "LR-038", "file": "CoverLetter.md", "from": unit, "to": revised}
                )
    if new_resume != resume and resume_path.is_file():
        resume_path.write_text(new_resume, encoding="utf-8")
        _resync_provenance(folder, "resume", resume_changes)
    if new_letter != letter and letter_path.is_file():
        letter_path.write_text(new_letter, encoding="utf-8")
        _resync_provenance(folder, "cover_letter", letter_changes)
    return applied


def strip_unverified_partner_clauses(folder: Path) -> list[dict[str, str]]:
    """Remove a partner clause that names a group outside the verified list.

    A verified partner such as engineering stays. The warning still fires on
    the original wording. Implements FR-405.
    """
    from submission_linter import _check_unverified_partner, collect_fidelity_hard_blocks

    applied: list[dict[str, str]] = []
    resume_path = folder / "Resume.md"
    letter_path = folder / "CoverLetter.md"
    originals = {
        "Resume.md": resume_path.read_text(encoding="utf-8") if resume_path.is_file() else "",
        "CoverLetter.md": letter_path.read_text(encoding="utf-8") if letter_path.is_file() else "",
    }
    updated = dict(originals)
    doc_changes: dict[str, list[dict[str, str]]] = {"Resume.md": [], "CoverLetter.md": []}
    for name, text in originals.items():
        if not text or not _check_unverified_partner(text):
            continue
        kept_lines: list[str] = []
        for line in text.splitlines():
            if not _check_unverified_partner(line):
                kept_lines.append(line)
                continue
            stripped = _UNVERIFIED_PARTNER_CLAUSE.sub("", line)
            stripped = re.sub(r"\s{2,}", " ", stripped)
            stripped = re.sub(r"\s+([.!?])", r"\1", stripped).rstrip()
            body = re.sub(r"^\s*[*-]\s+", "", stripped).strip(" .")
            if len(body.split()) < 4:
                applied.append({"rule_id": "LW-005", "file": name, "from": line.strip(), "to": ""})
                continue
            if stripped == line:
                kept_lines.append(line)
                continue
            if not stripped.endswith((".", "!", "?")):
                stripped += "."
            kept_lines.append(stripped)
            applied.append({"rule_id": "LW-005", "file": name, "from": line.strip(), "to": stripped.strip()})
            doc_changes[name].append({"from": line.strip(), "to": stripped.strip()})
        updated[name] = "\n".join(kept_lines).rstrip() + "\n"
    if not applied:
        return []
    before_ids = {
        item.rule_id
        for item in collect_fidelity_hard_blocks(originals["Resume.md"], originals["CoverLetter.md"])
    }
    after_ids = {
        item.rule_id
        for item in collect_fidelity_hard_blocks(updated["Resume.md"], updated["CoverLetter.md"])
    }
    if after_ids - before_ids:
        return []
    for name, path in (("Resume.md", resume_path), ("CoverLetter.md", letter_path)):
        if updated[name] != originals[name] and path.is_file():
            path.write_text(updated[name], encoding="utf-8")
            doc_type = "resume" if name == "Resume.md" else "cover_letter"
            _resync_provenance(folder, doc_type, doc_changes[name])
    return applied


_UNVERIFIED_PARTNER_CLAUSE = re.compile(
    r",?\s*(?:partner(?:ed|ing)?\s+with\s+|collaborat(?:ed|ing)\s+with\s+"
    r"|work(?:ed|ing)?\s+with\s+the\s+)[^.!?\n]*",
    re.IGNORECASE,
)


def _only_agile_epic_tool(line: str) -> bool:
    """True when LR-026's only hit on this line is the word epic. Implements FR-402."""
    from blocked_tools import hard_blocked_tools_lint_alternation

    tokens = [
        match.group(0).lower().rstrip("s")
        for match in re.finditer(hard_blocked_tools_lint_alternation(), line, re.IGNORECASE)
    ]
    return bool(tokens) and all(token == "epic" for token in tokens)


def _load_provenance(folder: Path) -> dict[str, Any] | None:
    """Return claim_provenance.json, or None when it is missing or invalid."""
    path = folder / "claim_provenance.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _blocked_snippets(
    resume_text: str,
    letter_text: str,
    provenance: dict[str, Any] | None = None,
) -> list[tuple[str, str]]:
    """Return (rule id, snippet) for hard blocks that name a line. Implements FR-402."""
    from submission_linter import collect_fidelity_hard_blocks, lint_document

    found: list[tuple[str, str]] = []
    for item in collect_fidelity_hard_blocks(resume_text, letter_text, provenance):
        for quoted in re.findall(r'"([^"]{12,})"', item.message or ""):
            found.append((item.rule_id, quoted))
    for doc_type, text in (("resume", resume_text), ("cover_letter", letter_text)):
        lines = text.splitlines()
        for item in lint_document(text, doc_type).blocks:
            if not item.line or not (1 <= item.line <= len(lines)):
                continue
            raw = lines[item.line - 1]
            if raw.strip().startswith("#"):
                continue
            if item.rule_id == "LR-026" and _only_agile_epic_tool(raw):
                continue
            found.append((item.rule_id, raw))
    return found


def _snippet_hits_unit(unit: str, snippet: str) -> bool:
    """True when a hard-block snippet and a draft unit are the same line."""
    from author_from_packet import _normalize_provenance_unit

    left = _normalize_provenance_unit(unit)
    right = _normalize_provenance_unit(snippet)
    if len(left) < 12 or len(right) < 12:
        return False
    return left in right or right in left


def _cover_body_sentences(text: str) -> list[str]:
    """Return cover-letter body sentences, including lines that state no personal fact."""
    body = (text or "").split("Dear Hiring Manager,", 1)[-1]
    body = re.split(r"\n\s*(?:Best regards|Regards|Sincerely),", body, maxsplit=1)[0]
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", re.sub(r"\n+", " ", body))
        if sentence.strip()
    ]


def drop_blocked_units(folder: Path) -> list[dict[str, str]]:
    """Remove a cited bullet or sentence that is itself a hard block.

    A removal that creates a new fidelity hard block is refused. The blocked
    phrase stays a hard block. This only deletes the line that already fails.
    Cover sentences that do not state a personal fact are included. A cited
    contradiction is visible because the cite file is loaded. Implements FR-402 / FR-408.
    """
    from submission_linter import collect_fidelity_hard_blocks

    resume_path = folder / "Resume.md"
    letter_path = folder / "CoverLetter.md"
    if not resume_path.is_file() or not letter_path.is_file():
        return []
    resume_text = resume_path.read_text(encoding="utf-8")
    letter_text = letter_path.read_text(encoding="utf-8")
    provenance = _load_provenance(folder)
    snippets = _blocked_snippets(resume_text, letter_text, provenance)
    if not snippets:
        return []
    applied: list[dict[str, str]] = []
    kept_resume: list[str] = []
    in_experience = False
    for line in resume_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_experience = stripped[3:].strip().casefold() == "professional experience"
        rule_id = ""
        if in_experience and stripped.startswith(("* ", "- ")):
            for candidate, snippet in snippets:
                if _snippet_hits_unit(stripped, snippet):
                    rule_id = candidate
                    break
        if rule_id:
            applied.append({"rule_id": rule_id, "file": "Resume.md", "from": stripped, "to": ""})
            continue
        kept_resume.append(line)
    new_resume = resume_text
    if any(row["file"] == "Resume.md" for row in applied):
        new_resume = "\n".join(kept_resume).rstrip() + "\n"
    new_letter = letter_text
    for sentence in _cover_body_sentences(letter_text):
        rule_id = ""
        for candidate, snippet in snippets:
            if _snippet_hits_unit(sentence, snippet):
                rule_id = candidate
                break
        if not rule_id or sentence not in new_letter:
            continue
        new_letter = new_letter.replace(sentence, "", 1)
        applied.append(
            {"rule_id": rule_id, "file": "CoverLetter.md", "from": sentence, "to": ""}
        )
    if any(row["file"] == "CoverLetter.md" for row in applied):
        new_letter = re.sub(r"[ \t]{2,}", " ", new_letter)
        new_letter = re.sub(r"\n{3,}", "\n\n", new_letter)
        if not new_letter.endswith("\n"):
            new_letter += "\n"
    if not applied:
        return []
    before_ids = {item.rule_id for item in collect_fidelity_hard_blocks(resume_text, letter_text, provenance)}
    after_ids = {item.rule_id for item in collect_fidelity_hard_blocks(new_resume, new_letter, provenance)}
    if after_ids - before_ids:
        return []
    if new_resume != resume_text:
        resume_path.write_text(new_resume, encoding="utf-8")
    if new_letter != letter_text:
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


def name_past_employer(folder: Path, *, force: bool = False) -> list[dict[str, str]]:
    """Add one cited sentence when the letter names no past employer.

    The sentence is a cited resume bullet with the employer named. It does
    not invent a fact. force=True adds the sentence even when an uncited
    employer mention is already present. Implements FR-386.
    """
    from submission_linter import check_letter_names_employer, collect_fidelity_hard_blocks

    letter_path = folder / "CoverLetter.md"
    resume_path = folder / "Resume.md"
    prov_path = folder / "claim_provenance.json"
    if not letter_path.is_file() or not resume_path.is_file() or not prov_path.is_file():
        return []
    letter = letter_path.read_text(encoding="utf-8")
    if not force and not check_letter_names_employer(letter):
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


_EMPLOYER_TOKEN = re.compile(r"\b(?:cision|sterkly|zero[\s-]+to[\s-]+sixty)\b", re.IGNORECASE)


def _covered_letter_sentences(provenance: dict[str, Any]) -> set[str]:
    """Return normalized cover sentences that already carry a cite."""
    covered: set[str] = set()
    for row in provenance.get("cover_letter_claims") or []:
        if not isinstance(row, dict) or not row.get("claim_ids"):
            continue
        sentence = row.get("sentence")
        if isinstance(sentence, str) and sentence.strip():
            covered.add(_normalize_provenance_unit(sentence))
    return covered


def _sole_required_sentences(folder: Path, provenance: dict[str, Any]) -> set[str]:
    """Return normalized sentences that are the only cite for a required claim."""
    packet_path = folder / "authoring_packet.json"
    if not packet_path.is_file():
        return set()
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    required: set[str] = set()
    for row in packet.get("evidence_map") or []:
        if isinstance(row, dict) and row.get("bucket") == "required":
            required.update(
                claim_id
                for claim_id in (row.get("claim_ids") or [])
                if isinstance(claim_id, str) and claim_id.strip()
            )
    counts: dict[str, int] = {}
    owners: dict[str, str] = {}
    for row in provenance.get("cover_letter_claims") or []:
        if not isinstance(row, dict):
            continue
        sentence = row.get("sentence")
        if not isinstance(sentence, str) or not sentence.strip():
            continue
        key = _normalize_provenance_unit(sentence)
        for claim_id in row.get("claim_ids") or []:
            if not isinstance(claim_id, str) or claim_id not in required:
                continue
            counts[claim_id] = counts.get(claim_id, 0) + 1
            owners[claim_id] = key
    return {owners[claim_id] for claim_id, count in counts.items() if count == 1}


def trim_cover_to_page(folder: Path) -> list[dict[str, str]]:
    """Drop cover sentences until the letter fits one page.

    Uncited sentences go first. The only past-employer sentence stays, and so
    does the only cite for a required claim. The character limit is unchanged.
    Implements FR-410.
    """
    from cover_phrasing import CHAR_MAX
    from submission_linter import collect_fidelity_hard_blocks

    letter_path = folder / "CoverLetter.md"
    resume_path = folder / "Resume.md"
    if not letter_path.is_file():
        return []
    letter = letter_path.read_text(encoding="utf-8")
    if len(letter) <= CHAR_MAX:
        return []
    provenance = _load_provenance(folder) or {}
    resume = resume_path.read_text(encoding="utf-8") if resume_path.is_file() else ""
    applied: list[dict[str, str]] = []
    refused: set[str] = set()
    while len(letter) > CHAR_MAX:
        sentences = _cover_body_sentences(letter)
        employer_keys = [
            _normalize_provenance_unit(sentence)
            for sentence in sentences
            if _EMPLOYER_TOKEN.search(sentence)
        ]
        only_employer = employer_keys[0] if len(employer_keys) == 1 else ""
        covered = _covered_letter_sentences(provenance)
        protected = _sole_required_sentences(folder, provenance)
        if only_employer:
            protected.add(only_employer)
        ranked = sorted(sentences, key=len, reverse=True)
        uncited = [
            sentence
            for sentence in ranked
            if _normalize_provenance_unit(sentence) not in covered
            and _normalize_provenance_unit(sentence) not in protected
            and sentence not in refused
        ]
        cited = [
            sentence
            for sentence in ranked
            if _normalize_provenance_unit(sentence) in covered
            and _normalize_provenance_unit(sentence) not in protected
            and sentence not in refused
        ]
        choice = uncited[0] if uncited else (cited[0] if cited else "")
        if not choice:
            break
        new_letter = re.sub(r"[ \t]{2,}", " ", letter.replace(choice, "", 1))
        new_letter = re.sub(r"\n{3,}", "\n\n", new_letter)
        if not new_letter.endswith("\n"):
            new_letter += "\n"
        before_ids = {
            item.rule_id for item in collect_fidelity_hard_blocks(resume, letter, provenance)
        }
        after_ids = {
            item.rule_id for item in collect_fidelity_hard_blocks(resume, new_letter, provenance)
        }
        if after_ids - before_ids:
            refused.add(choice)
            continue
        letter = new_letter
        key = _normalize_provenance_unit(choice)
        rows = provenance.get("cover_letter_claims")
        if isinstance(rows, list):
            provenance["cover_letter_claims"] = [
                row
                for row in rows
                if not (
                    isinstance(row, dict)
                    and _normalize_provenance_unit(str(row.get("sentence") or "")) == key
                )
            ]
        applied.append({"rule_id": "CL-006", "file": "CoverLetter.md", "from": choice, "to": ""})
    if not applied:
        return []
    letter_path.write_text(letter, encoding="utf-8")
    prov_path = folder / "claim_provenance.json"
    if prov_path.is_file():
        prov_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return applied


def _cover_body_words(letter: str) -> int:
    """Return the cover-letter word count the length warning uses."""
    from submission_linter import _word_count

    body = letter.split("Dear Hiring Manager,", 1)[-1] if "Dear Hiring Manager," in letter else letter
    return _word_count(body)


def extend_thin_cover(folder: Path) -> list[dict[str, str]]:
    """Add a cited resume sentence when the letter is under 220 words.

    The sentence is a bullet that already has a cite. The letter stops at the
    first sentence that reaches the floor, and it does not pass 450 words or
    2800 characters. Implements FR-411.
    """
    from cover_phrasing import CHAR_MAX
    from submission_linter import collect_fidelity_hard_blocks

    letter_path = folder / "CoverLetter.md"
    resume_path = folder / "Resume.md"
    prov_path = folder / "claim_provenance.json"
    if not letter_path.is_file() or not resume_path.is_file() or not prov_path.is_file():
        return []
    letter = letter_path.read_text(encoding="utf-8")
    if "Best regards," not in letter or _cover_body_words(letter) >= 220:
        return []
    provenance = _load_provenance(folder)
    if not provenance:
        return []
    resume = resume_path.read_text(encoding="utf-8")
    applied: list[dict[str, str]] = []
    used: set[str] = set()
    while _cover_body_words(letter) < 220:
        choice: tuple[str, list[str]] | None = None
        for row in provenance.get("resume_claims") or []:
            if not isinstance(row, dict):
                continue
            bullet = str(row.get("bullet") or "").strip()
            claim_ids = [str(item) for item in (row.get("claim_ids") or []) if str(item).strip()]
            key = _normalize_provenance_unit(bullet)
            if not bullet or not claim_ids or not key or key in used:
                continue
            if key in _normalize_provenance_unit(letter):
                used.add(key)
                continue
            employer = ""
            for heading, bullets in _experience_roles(resume):
                if any(_normalize_provenance_unit(item) == key for item in bullets):
                    for name, pattern in _PAST_EMPLOYER_HEADS:
                        if pattern.search(heading):
                            employer = name
                            break
            sentence = _employer_sentence(employer, bullet) if employer else bullet.strip()
            if not sentence.endswith("."):
                sentence += "."
            trial = letter.replace("Best regards,", sentence + "\n\nBest regards,", 1)
            if _cover_body_words(trial) > 450 or len(trial) > CHAR_MAX:
                used.add(key)
                continue
            before_ids = {
                item.rule_id for item in collect_fidelity_hard_blocks(resume, letter, provenance)
            }
            after_ids = {
                item.rule_id for item in collect_fidelity_hard_blocks(resume, trial, provenance)
            }
            if after_ids - before_ids:
                used.add(key)
                continue
            choice = (sentence, claim_ids)
            used.add(key)
            break
        if choice is None:
            break
        sentence, claim_ids = choice
        letter = letter.replace("Best regards,", sentence + "\n\nBest regards,", 1)
        rows = provenance.get("cover_letter_claims")
        if not isinstance(rows, list):
            rows = []
            provenance["cover_letter_claims"] = rows
        rows.append({"sentence": sentence, "claim_ids": claim_ids})
        applied.append({"rule_id": "LW-001", "file": "CoverLetter.md", "from": "", "to": sentence})
    if not applied:
        return []
    letter_path.write_text(letter, encoding="utf-8")
    prov_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return applied


def anchor_uncited_employer(folder: Path) -> list[dict[str, str]]:
    """Add a cited employer sentence when every employer mention is uncited.

    The uncited sentence can then be removed without leaving the letter with
    no past employer. Implements FR-404.
    """
    from author_from_packet import _cover_factual_sentences, _normalize_provenance_unit

    letter_path = folder / "CoverLetter.md"
    prov_path = folder / "claim_provenance.json"
    if not letter_path.is_file() or not prov_path.is_file():
        return []
    try:
        provenance = json.loads(prov_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(provenance, dict):
        return []
    covered = set()
    for row in provenance.get("cover_letter_claims") or []:
        if not isinstance(row, dict) or not row.get("claim_ids"):
            continue
        sentence = row.get("sentence")
        if isinstance(sentence, str) and sentence.strip():
            covered.add(_normalize_provenance_unit(sentence))
    letter = letter_path.read_text(encoding="utf-8")
    employer_sentences = [
        sentence
        for sentence in _cover_factual_sentences(letter)
        if any(pattern.search(sentence) for _name, pattern in _PAST_EMPLOYER_HEADS)
    ]
    if not employer_sentences:
        return []
    if any(_normalize_provenance_unit(sentence) in covered for sentence in employer_sentences):
        return []
    return name_past_employer(folder, force=True)


def _with_estimate_hedge(unit: str) -> str:
    """Return the unit with an estimate hedge inserted ahead of the figure."""
    updated = unit
    if re.search(r"estimat", updated, re.IGNORECASE):
        return updated
    drafting = (
        _DRAFT_WEEK_RE.search(updated)
        and _DRAFT_DAY_RE.search(updated)
        and _DRAFTING_CONTEXT_RE.search(updated)
    )
    if drafting:
        counted = re.search(
            r"(?i)\b(?:one|two|three|four|five|several|\d+)\s+weeks?\b",
            updated,
        )
        week = counted or _DRAFT_WEEK_RE.search(updated)
        if week:
            updated = f"{updated[:week.start()]}an estimated {updated[week.start():]}"
    if not re.search(r"estimat", updated, re.IGNORECASE) and _MET13_PAIR_RE.search(updated):
        money = _MET13_PAIR_RE.search(updated)
        if money:
            updated = f"{updated[:money.start()]}an estimated {updated[money.start():]}"
    return updated


def keep_required_hedges(folder: Path) -> list[dict[str, str]]:
    """Insert the estimate hedge on the existing line and keep its cite.

    Repair was rewriting the line, which broke the provenance match, and the
    uncited-line deletion then removed the proof. Implements FR-386.
    """
    resume_path = folder / "Resume.md"
    letter_path = folder / "CoverLetter.md"
    resume = resume_path.read_text(encoding="utf-8") if resume_path.is_file() else ""
    letter = letter_path.read_text(encoding="utf-8") if letter_path.is_file() else ""
    texts = {"resume": resume, "cover_letter": letter}
    changes: dict[str, list[dict[str, str]]] = {"resume": [], "cover_letter": []}
    applied: list[dict[str, str]] = []
    for unit in _hedge_units(resume, letter):
        if re.search(r"estimat", unit, re.IGNORECASE):
            continue
        drafting = (
            _DRAFT_WEEK_RE.search(unit)
            and _DRAFT_DAY_RE.search(unit)
            and _DRAFTING_CONTEXT_RE.search(unit)
        )
        if not drafting and not _MET13_PAIR_RE.search(unit):
            continue
        revised = _with_estimate_hedge(unit)
        if revised == unit:
            continue
        if unit in texts["resume"]:
            doc = "resume"
            filename = "Resume.md"
        elif unit in texts["cover_letter"]:
            doc = "cover_letter"
            filename = "CoverLetter.md"
        else:
            continue
        texts[doc] = texts[doc].replace(unit, revised, 1)
        changes[doc].append({"from": unit, "to": revised})
        applied.append({"rule_id": "LR-047", "file": filename, "from": unit, "to": revised})
    if texts["resume"] != resume and resume_path.is_file():
        resume_path.write_text(texts["resume"], encoding="utf-8")
    if texts["cover_letter"] != letter and letter_path.is_file():
        letter_path.write_text(texts["cover_letter"], encoding="utf-8")
    for doc_type, doc_changes in changes.items():
        if doc_changes:
            _resync_provenance(folder, doc_type, doc_changes)
    return applied


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
    for change in collapse_hedged_100k(folder):
        applied.append(change)
    for change in anchor_uncited_employer(folder):
        applied.append(change)
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
    for change in keep_required_hedges(folder):
        applied.append(change)
    for change in drop_uncited_units(folder):
        applied.append(change)
    for change in rewrite_bypass_ingestion(folder):
        applied.append(change)
    for change in soften_contributed_ownership(folder):
        applied.append(change)
    for change in drop_blocked_units(folder):
        applied.append(change)
    for change in strip_unverified_partner_clauses(folder):
        applied.append(change)
    for change in name_past_employer(folder):
        applied.append(change)
    for change in trim_cover_to_page(folder):
        applied.append(change)
    for change in extend_thin_cover(folder):
        applied.append(change)
    return {
        "applied": applied,
        "skipped": skipped,
        "changed": bool(applied),
        "years_constraint": years_constraint,
    }
