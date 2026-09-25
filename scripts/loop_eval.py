"""Independent evaluator for practice resumes and cover letters.

This is not a pipeline gate. It reads work-experience boundaries and the
draft text. It does not import submission_linter. Implements the loop's
L1 and L2 checks for FR-386 measurement.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_VERIFIED_PARTNERS = {
    "engineering",
    "dba",
    "devops",
    "customer experience",
    "cx",
    "customer support",
    "sales",
    "account management",
    "legal",
    "infosec",
    "product marketing",
    "executive",
    "presidential",
    "upgrades",
}
_UNVERIFIED_PARTNER = re.compile(
    r"(?:,|\band)\s+operations\b|\bcompliance teams?\b|\b(?:design|ux)\s+teams?\b",
    re.IGNORECASE,
)
_DATA_MODEL = re.compile(r"\bdata models?\b|\bdata modeling\b", re.IGNORECASE)
_VISIBLE = re.compile(r"(?<=\s)Visible\b")
_CODENAMES = re.compile(r"\b(?:CPRE|PIC|Datagroups|Critical Save|GPOD|Bellwether|Airo)\b")
_PLACEHOLDER = re.compile(r"\bConfidential is\b|\bat Confidential\b")
_PROHIBITED = re.compile(
    r"\b(?:leverage|passionate|seamless|transformative|synergy)\b|"
    r"\bproven track record\b|\bI am excited\b",
    re.IGNORECASE,
)
_MONEY_8500 = re.compile(r"\$8,?500\b")
_QUARTER = re.compile(r"\b(?:per quarter|quarterly|a quarter|each quarter)\b", re.IGNORECASE)
_MET13 = re.compile(
    r"(?:\$\s*1\s*m\b|1\s+million).{0,48}(?:\$\s*3\s*m\b|3\s+million)",
    re.IGNORECASE,
)
_DRAFT_TIME = re.compile(r"\bweeks?\b", re.IGNORECASE)
_DRAFT_DAYS = re.compile(r"\bdays?\b", re.IGNORECASE)
_DRAFT_CONTEXT = re.compile(r"\b(?:draft\w*|epics?|stories|story)\b", re.IGNORECASE)
_ESTIMATED = re.compile(r"estimat", re.IGNORECASE)
_DISRUPT = re.compile(r"\bwithout(?:\s+\w+){0,3}\s+disrupt", re.IGNORECASE)
_INVERSION = re.compile(
    r"\bover custom tagging\b|\bportability over\b|\bqa lead\b|"
    r"\bhundreds of client\b|\bcompliance frameworks\b",
    re.IGNORECASE,
)
_OVERCLAIM: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ACC-107", re.compile(r"\bregulatory\b|\bdata governance\b|\baudit requirements\b|\bcompliance frameworks\b", re.I)),
    ("ACC-113", re.compile(r"\b(?:owned the end-to-end|end-to-end migration|leading the migration)\b", re.I)),
    ("ACC-102", re.compile(r"\bled the technical implementation\b|\btechnical implementation\b", re.I)),
    ("ACC-220", re.compile(r"\bleading the platform migration\b|\bled the (?:technical|platform) migration\b", re.I)),
    ("ACC-103", re.compile(r"\b(?:cleared|resolved)\b.{0,40}\bbacklog\b", re.I)),
    ("ACC-125", re.compile(r"\b(?:cleared|resolved)\b.{0,40}\bbacklog\b", re.I)),
    ("ACC-209", re.compile(r"\bqa lead\b", re.I)),
    ("ACC-155", re.compile(r"\bover custom tagging\b|\bportability over\b", re.I)),
    ("ACC-115", re.compile(r"\b(?:active usage|feature usage)\b", re.I)),
    ("ACC-303", re.compile(r"\bautomating lead capture\b|\bonboarding funnel\b", re.I)),
    ("ACC-203", re.compile(r"\bfunctional specifications\b|\bendpoint protection rules\b|\bnegotiated technical\b", re.I)),
)


def _id_prefix(claim_id: str) -> str:
    match = re.match(r"(ACC|MET|VOC)-\d+", claim_id or "")
    return match.group(0) if match else ""


def _units(resume_text: str, letter_text: str) -> list[tuple[str, str]]:
    """Return (doc, text) for resume bullets and cover-letter sentences."""
    units: list[tuple[str, str]] = []
    in_experience = False
    for line in (resume_text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_experience = stripped[3:].strip().casefold() == "professional experience"
            continue
        if in_experience and stripped.startswith(("* ", "- ")):
            units.append(("resume", stripped[2:].strip()))
    body = (letter_text or "").split("Dear Hiring Manager,", 1)[-1]
    body = re.split(r"\n\s*(?:Best regards|Regards|Sincerely),", body, maxsplit=1)[0]
    for sentence in re.split(r"(?<=[.!?])\s+", re.sub(r"\n+", " ", body)):
        sentence = sentence.strip()
        if sentence:
            units.append(("cover_letter", sentence))
    return units


def _claim_ids_for(unit: str, provenance: dict[str, Any] | None) -> list[str]:
    if not isinstance(provenance, dict):
        return []
    target = re.sub(r"\s+", " ", unit).strip().rstrip(".!?").lower()
    found: list[str] = []
    for section, field in (("resume_claims", "bullet"), ("cover_letter_claims", "sentence")):
        for row in provenance.get(section) or []:
            if not isinstance(row, dict):
                continue
            value = re.sub(r"\s+", " ", str(row.get(field) or "")).strip().rstrip(".!?").lower()
            if value and (value in target or target in value):
                found.extend(str(item) for item in (row.get("claim_ids") or []))
    return found


def _l1_flags(text: str) -> list[str]:
    """Return L1 rule ids for one sentence. Independent of claim ids."""
    flags: list[str] = []
    if _MONEY_8500.search(text) and not _QUARTER.search(text):
        flags.append("L1-metric-unit")
    if _MET13.search(text) and not _ESTIMATED.search(text):
        flags.append("L1-hedge-met13")
    if (
        _DRAFT_TIME.search(text)
        and _DRAFT_DAYS.search(text)
        and _DRAFT_CONTEXT.search(text)
        and not _ESTIMATED.search(text)
    ):
        flags.append("L1-hedge-draft")
    if _DATA_MODEL.search(text):
        flags.append("L1-data-model")
    if _VISIBLE.search(text) or _CODENAMES.search(text):
        flags.append("L1-codename")
    if _PLACEHOLDER.search(text):
        flags.append("L1-placeholder")
    if _PROHIBITED.search(text):
        flags.append("L1-prohibited")
    if _INVERSION.search(text):
        flags.append("L1-inversion")
    if _DISRUPT.search(text):
        flags.append("L1-disruption-hedge")
    for match in _UNVERIFIED_PARTNER.finditer(text):
        token = match.group(0).split()[-1].lower()
        if token not in _VERIFIED_PARTNERS:
            flags.append("L1-partner")
            break
    return flags


def _l2_flags(text: str, claim_ids: list[str]) -> list[str]:
    """Return L2 rule ids when the cited entry contradicts the sentence."""
    prefixes = {_id_prefix(item) for item in claim_ids}
    flags: list[str] = []
    for prefix, pattern in _OVERCLAIM:
        if prefix in prefixes and pattern.search(text):
            flags.append(f"L2-{prefix}")
    if "ACC-113" in prefixes and _DISRUPT.search(text):
        flags.append("L2-ACC-113-hedge")
    return flags


def evaluate_pair(
    resume_text: str,
    letter_text: str,
    provenance: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Return findings for one resume and cover letter.

    Each finding has doc, rule, and a short excerpt of the sentence.
    """
    findings: list[dict[str, str]] = []
    for doc, unit in _units(resume_text, letter_text):
        claim_ids = _claim_ids_for(unit, provenance)
        for rule in _l1_flags(unit) + _l2_flags(unit, claim_ids):
            findings.append({"doc": doc, "rule": rule, "text": unit, "excerpt": unit[:180]})
    if "## PROFESSIONAL EXPERIENCE" in (resume_text or ""):
        # An experience heading with no bullet under it is critical.
        chunks = re.split(r"(?m)^### ", resume_text)
        for chunk in chunks[1:]:
            heading = chunk.splitlines()[0] if chunk.splitlines() else ""
            if not re.search(r"(?m)^[*-] ", chunk):
                findings.append(
                    {
                        "doc": "resume",
                        "rule": "L1-empty-role",
                        "excerpt": heading[:180],
                    }
                )
    return findings


def evaluate_folder(folder: Path) -> list[dict[str, str]]:
    """Evaluate Resume.md and CoverLetter.md in a folder."""
    resume = (folder / "Resume.md").read_text(encoding="utf-8") if (folder / "Resume.md").is_file() else ""
    letter = (
        (folder / "CoverLetter.md").read_text(encoding="utf-8")
        if (folder / "CoverLetter.md").is_file()
        else ""
    )
    provenance = None
    prov_path = folder / "claim_provenance.json"
    if prov_path.is_file():
        try:
            payload = json.loads(prov_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            provenance = payload
    return evaluate_pair(resume, letter, provenance)
