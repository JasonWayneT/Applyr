"""
Recruiter-facing QA gate before Backlog.

Implements FR-104 (CR-017), FR-105, FR-106 (CR-018).
"""
from __future__ import annotations

import os
import re
from typing import List, Tuple

from bullet_fit import is_incomplete_bullet
from claim_composer import strip_bridge_prefix
from jd_tailoring import load_bridge_phrases

ID_TOKEN = re.compile(r"\b(ACC|MET|VOC)-\d+\b|\|\s*(ACC|MET|VOC)-\d+\s*\|", re.IGNORECASE)
SLUG_COMPANY = re.compile(r"\b[A-Z][a-z]+(?:_[A-Z][a-z]+)+_?(?:Inc|LLC|Corp)?\b")
ARR_REPEAT = re.compile(r"\$?\s*40\s*[Mm](?:illion)?|\$40[,\s]*000[,\s]*000", re.IGNORECASE)


def check_text_tokens(text: str, label: str) -> List[str]:
    errs = []
    if ID_TOKEN.search(text):
        errs.append(f"{label}: internal fact ID tokens leaked")
    if "|" in text and re.search(r"\|\s*(MET|ACC|VOC)", text, re.I):
        errs.append(f"{label}: pipe-wrapped ID table leakage")
    return errs


def check_slug_company_name(text: str, display_name: str) -> List[str]:
    errs = []
    if "_" in display_name.replace(" ", "_") and display_name.count("_") >= 2:
        return errs
    for m in SLUG_COMPANY.findall(text):
        if "_" in m and m.lower() not in display_name.lower().replace(" ", "_"):
            errs.append(f"Cover/resume may use slug company name: {m}")
            break
    folder_slug = display_name.lower().replace(" ", "_")
    if folder_slug and folder_slug.replace("_", " ") not in text.lower():
        if re.search(rf"\b{re.escape(folder_slug)}\b", text, re.I):
            errs.append("Display name looks like folder slug in prose")
    return errs


def check_metric_spam(text: str) -> List[str]:
    hits = ARR_REPEAT.findall(text)
    if len(hits) > 3:
        return [f"Repeated $40M ARR metric ({len(hits)} times)"]
    return []


def check_incomplete_bullet(bullet: str) -> List[str]:
    if is_incomplete_bullet(bullet):
        return [f"Incomplete bullet ending: ...{bullet[-50:]}"]
    return []


def check_bridge_duplication(resume_md: str) -> List[str]:
    phrases = load_bridge_phrases()
    bridged = 0
    for line in resume_md.splitlines():
        if not line.strip().startswith("*"):
            continue
        for phrase in phrases.values():
            p = phrase.strip()
            if not p:
                continue
            prefix = p[0].upper() + p[1:] + ": "
            if line.strip().lower().startswith("* " + prefix.lower()):
                bridged += 1
                break
    if bridged > 1:
        return [f"Multiple bridge-prefixed bullets ({bridged})"]
    return []


def check_cover_no_bridge(cover_md: str) -> List[str]:
    """Bridge prefixes only (FR-106), not shared vocabulary in proof sentences."""
    phrases = load_bridge_phrases()
    cover_l = cover_md.lower()
    for phrase in phrases.values():
        p = phrase.strip()
        if not p:
            continue
        prefix = (p[0].upper() + p[1:] + ": ").lower()
        if prefix in cover_l:
            return [f"Cover letter contains bridge prefix: {p[:40]}..."]
    return []


def check_resume_employers(resume_md: str) -> List[str]:
    errs = []
    for emp in ("Cision", "Sterkly", "Zero"):
        if emp == "Zero" and "Zero" not in resume_md and "Sixty" not in resume_md:
            errs.append("Missing Zero to Sixty employer section content")
        elif emp != "Zero" and emp not in resume_md:
            errs.append(f"Missing employer mention: {emp}")
    bullets = len(re.findall(r"^\* ", resume_md, re.MULTILINE))
    if bullets < 4:
        errs.append(f"Too few resume bullets ({bullets})")
    return errs


def run_recruiter_qa(
    resume_path: str,
    cover_path: str,
    display_company: str,
) -> Tuple[bool, str]:
    errors: List[str] = []
    for path, label in ((resume_path, "Resume"), (cover_path, "Cover")):
        if not os.path.exists(path):
            errors.append(f"{label} missing: {path}")
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        errors.extend(check_text_tokens(text, label))
        if label == "Cover":
            errors.extend(check_slug_company_name(text, display_company))
        errors.extend(check_metric_spam(text))

    if os.path.exists(resume_path):
        with open(resume_path, encoding="utf-8") as f:
            resume_md = f.read()
        errors.extend(check_resume_employers(resume_md))
        errors.extend(check_bridge_duplication(resume_md))
        for line in resume_md.splitlines():
            if line.strip().startswith("*"):
                errors.extend(check_incomplete_bullet(line.lstrip("* ").strip()))

    if os.path.exists(cover_path):
        with open(cover_path, encoding="utf-8") as f:
            errors.extend(check_cover_no_bridge(f.read()))

    if errors:
        return False, "; ".join(errors)
    return True, "Recruiter QA passed"
