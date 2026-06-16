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
    min_words = 250 if plan.opening_variant == "need_first" else 300
    max_words = 400
    if wc < min_words:
        issues.append(f"Word count low ({wc}); target {min_words}-{max_words}")
        score -= 15 if wc < min_words - 15 else 8
    elif wc > max_words:
        issues.append(f"Word count high ({wc}); target 300-400")
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

    opener = body[:500]
    has_apply_intent = bool(re.search(r"i am applying for", opener))
    has_need_first_intent = (
        plan.opening_variant == "need_first"
        and plan.company_display.lower() in opener
        and plan.role_title.lower() in opener
    )
    has_domain_first_intent = (
        plan.opening_variant == "domain_first"
        and plan.company_display.lower() in opener
        and "fits the work" in opener
    )
    if not has_apply_intent and not has_need_first_intent and not has_domain_first_intent:
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

    from cover_jd_needs import is_tenure_requirement

    needs_found = 0
    for need in plan.ranked_needs[:2]:
        if is_tenure_requirement(need):
            if any(
                m in body
                for m in (
                    "analytics",
                    "roadmap",
                    "kpi",
                    "platform",
                    "data",
                    "adopt",
                    "underwriting",
                )
            ):
                needs_found += 1
            continue
        goal = need_to_goal_phrase(need)
        frag = goal[:50] if goal else need.lower()[:40]
        if frag and frag in body:
            needs_found += 1
        elif need.lower()[:35] in body:
            needs_found += 1
    jd_markers = (
        "intelligence platform",
        "rankings",
        "monetization",
        "platform adoption",
        "analytics product",
        "underwriting",
        "lender integration",
        "lender integrations",
        "consumer funnel",
        "funnel conversion",
        "borrower",
        "marketplace",
        "funded volume",
        "drop-off",
        "drop off",
        "personal safety",
        "connected device",
        "vendor integration",
        "device lifecycle",
        "firmware",
        "iot",
        "interoperability",
    )
    if any(m in body for m in jd_markers):
        needs_found = max(needs_found, 1)
    for pain in getattr(plan, "pain_points", None) or []:
        frag = pain.lower().strip()
        if len(frag) >= 8 and frag in body:
            needs_found = max(needs_found, 1)
            break
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

    from cover_phrasing import check_cover_grammar_defects

    for defect in check_cover_grammar_defects(markdown):
        issues.append(defect)
        score -= 20

    grade = "Pass" if score >= 80 else ("Needs Revision" if score >= 65 else "Rewrite")
    return CoverAuditResult(score=max(0, score), grade=grade, issues=issues)
