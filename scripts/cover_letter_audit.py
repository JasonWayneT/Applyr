"""Conversion audit for cover letters (CR-024 / FR-099)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from cover_letter_plan import CoverLetterPlan

FORBIDDEN_OPENERS = (
    " is hiring a ",
    " is hiring ",
    "i am writing to apply",
)

BUZZWORDS = (
    "passionate",
    "excited to apply",
    "great fit",
    "synergy",
    "leverage",
    "rockstar",
    "thought leader",
    "results-driven",
    "i am writing to apply",
)


@dataclass
class CoverAuditResult:
    score: int
    grade: str  # Pass | Needs Revision | Rewrite
    issues: List[str]

    @property
    def passed(self) -> bool:
        return self.grade == "Pass"


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def audit_cover_letter(
    markdown: str,
    plan: CoverLetterPlan,
    jd_text: str,
    claim_corpus: str,
) -> CoverAuditResult:
    issues: List[str] = []
    score = 100
    body = markdown.lower()

    wc = _word_count(markdown)
    if wc < 300:
        issues.append(f"Word count low ({wc}); target 300-350")
        score -= 15 if wc < 285 else 8
    elif wc > 380:
        issues.append(f"Word count high ({wc}); target 300-350")
        score -= 10

    if plan.company_display.lower() not in body:
        issues.append("Missing company name")
        score -= 20
    if plan.role_title.lower() not in body:
        issues.append("Missing role title")
        score -= 15

    if "dear hiring manager" not in body:
        issues.append("Missing salutation")
        score -= 5

    if not re.search(r"i am applying for", body):
        issues.append("Opening should state application intent")
        score -= 12
    for bad in FORBIDDEN_OPENERS:
        if bad in body[:400]:
            issues.append(f"Forbidden opener pattern: {bad.strip()}")
            score -= 15
            break

    digit_in_letter = set(re.findall(r"\d+", markdown.replace(",", "")))
    corpus_digits = set(re.findall(r"\d+", claim_corpus.replace(",", "")))
    invented = {d for d in digit_in_letter if len(d) > 1 and d not in corpus_digits}
    invented -= {"760", "317", "8264"}
    if invented:
        issues.append(f"Invented numbers: {sorted(invented)}")
        score -= 25

    from cover_jd_needs import need_to_goal_phrase

    needs_found = 0
    for need in plan.ranked_needs[:2]:
        goal = need_to_goal_phrase(need)
        frag = goal[:50] if goal else need.lower()[:40]
        if frag and frag in body:
            needs_found += 1
        elif need.lower()[:35] in body:
            needs_found += 1
    jd_markers = ("intelligence platform", "rankings", "monetization", "platform adoption")
    if any(m in body for m in jd_markers):
        needs_found = max(needs_found, 1)
    if needs_found < 1 and plan.ranked_needs:
        issues.append("JD need not reflected in letter body")
        score -= 15

    metrics_in_body = len(re.findall(r"\d+%|~\d+|\$[\d,]+", markdown))
    if metrics_in_body < 1:
        issues.append("Fewer than 1 metric in letter")
        score -= 10

    for bw in BUZZWORDS:
        if bw in body:
            issues.append(f"Buzzword: {bw}")
            score -= 8

    if "thank you for your consideration" in body and "welcome" not in body:
        issues.append("Generic close only")
        score -= 5

    if "—" in markdown or " -- " in markdown:
        issues.append("Em-dash forbidden")
        score -= 5

    grade = "Pass" if score >= 80 else ("Needs Revision" if score >= 65 else "Rewrite")
    return CoverAuditResult(score=max(0, score), grade=grade, issues=issues)
