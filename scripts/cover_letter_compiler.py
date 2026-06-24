"""Independent cover letter compiler (CR-024). Does not read Resume.md."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional

from claim_catalog import load_catalog
from cover_claim_picker import dedupe_cover_proofs, pick_cover_proofs
from cover_letter_audit import audit_cover_letter
from cover_letter_plan import CoverLetterPlan
from cover_letter_renderer import render_cover_letter, word_count_report
from cover_plan_builder import build_cover_plan
from tone_guard import sanitize_submission_tone


@dataclass
class CoverLetterResult:
    markdown: str
    plan: CoverLetterPlan
    audit_grade: str
    audit_score: int
    audit_issues: List[str]
    word_count: int


def _claim_corpus(catalog) -> str:
    parts = list(catalog.raw_truth_lines.values())
    for rec in catalog.claims.values():
        if rec.cover_story:
            parts.append(rec.cover_story)
    return "\n".join(parts)


def apply_cover_retry_fixes(markdown: str, issues: List[str]) -> str:
    import re
    out = markdown
    for issue in issues:
        if "Forbidden opener pattern" in issue or "Opening should state application intent" in issue:
            out = re.sub(r"\bI am writing to express my interest in the\b", "I am applying for the", out, flags=re.I)
            out = re.sub(r"\bI am writing to express my interest in\b", "I am applying for", out, flags=re.I)
            out = re.sub(r"\bI am writing to express my interest\b", "I am applying", out, flags=re.I)
            out = re.sub(r"\bI am writing to apply for the\b", "I am applying for the", out, flags=re.I)
            out = re.sub(r"\bI am writing to apply for\b", "I am applying for", out, flags=re.I)
            out = re.sub(r"\bI am writing to apply\b", "I am applying", out, flags=re.I)
            out = re.sub(r"\b(?:is hiring a|is hiring)\b", "seeks a", out, flags=re.I)
        
        if "Buzzword:" in issue:
            m = re.search(r"Buzzword:\s*(.+)", issue)
            if m:
                bw = m.group(1).strip()
                if bw.lower() == "proven track record":
                    out = re.sub(r"\bproven track record\b", "track record", out, flags=re.I)
                elif bw.lower() == "seamless":
                    out = re.sub(r"\bseamlessly\b", "successfully", out, flags=re.I)
                    out = re.sub(r"\bseamless\b", "direct", out, flags=re.I)
                elif bw.lower() == "transformative":
                    out = re.sub(r"\btransformative\b", "meaningful", out, flags=re.I)
                elif bw.lower() == "innovative":
                    out = re.sub(r"\binnovative\b", "new", out, flags=re.I)
                elif bw.lower() == "leverage":
                    out = re.sub(r"\bleverage\b", "utilize", out, flags=re.I)
                elif bw.lower() == "synergy":
                    out = re.sub(r"\bsynergy\b", "collaboration", out, flags=re.I)
                elif bw.lower() == "rockstar":
                    out = re.sub(r"\brockstar\b", "key", out, flags=re.I)
                elif bw.lower() == "thought leader":
                    out = re.sub(r"\bthought leader\b", "expert", out, flags=re.I)
                elif bw.lower() == "results-driven":
                    out = re.sub(r"\bresults-driven\b", "focused", out, flags=re.I)
    return out


def compile_cover_letter(
    jd_text: str,
    company_display: str,
    research_packet_path: Optional[str] = None,
    max_retries: int = 2,
    bullet_corpus: str = "",
) -> CoverLetterResult:
    catalog = load_catalog()
    plan = build_cover_plan(
        jd_text,
        company_display,
        catalog,
        research_packet_path,
        bullet_corpus=bullet_corpus,
    )
    plan.proofs = dedupe_cover_proofs(plan.proofs)
    corpus = _claim_corpus(catalog)
    target_k = max(len(plan.proofs), 3)

    best_md = None
    best_score = -1
    best_audit = None
    best_wc = 0

    for attempt in range(max_retries + 1):
        md = render_cover_letter(plan, catalog, jd_text=jd_text)
        md = sanitize_submission_tone(md)
        
        if attempt > 0 and best_audit and best_audit.issues:
            md = apply_cover_retry_fixes(md, best_audit.issues)
            
        audit = audit_cover_letter(md, plan, jd_text, corpus)
        wc, _in_band = word_count_report(md)
        
        if audit.score > best_score:
            best_score = audit.score
            best_md = md
            best_audit = audit
            best_wc = wc

        if audit.passed and not any(
            "Invented numbers" in i for i in audit.issues
        ):
            return CoverLetterResult(
                markdown=md,
                plan=plan,
                audit_grade=audit.grade,
                audit_score=audit.score,
                audit_issues=audit.issues,
                word_count=wc,
            )
        if attempt < max_retries:
            from jd_tailoring import build_jd_profile_deterministic

            profile = build_jd_profile_deterministic(jd_text)
            alt_proofs = pick_cover_proofs(
                catalog, plan.ranked_needs, profile, jd_text, k=target_k
            )
            if alt_proofs:
                plan.proofs = dedupe_cover_proofs(alt_proofs)
                continue
        break

    md = best_md if best_md is not None else render_cover_letter(plan, catalog, jd_text=jd_text)
    md = sanitize_submission_tone(md)
    audit = best_audit if best_audit is not None else audit_cover_letter(md, plan, jd_text, corpus)
    wc, _ = word_count_report(md)
    _CRITICAL_WORD_COUNT = 80
    if wc < _CRITICAL_WORD_COUNT:
        from drafting_errors import DraftingPipelineError

        raise DraftingPipelineError(
            f"Cover letter body is critically short ({wc} words, minimum {_CRITICAL_WORD_COUNT}). "
            "Likely caused by empty proof list — check ranked_needs extraction and catalog coverage."
        )
    return CoverLetterResult(
        markdown=md,
        plan=plan,
        audit_grade=audit.grade,
        audit_score=audit.score,
        audit_issues=audit.issues,
        word_count=wc,
    )


def write_cover_bundle(
    company_folder: str,
    result: CoverLetterResult,
) -> None:
    cl_path = os.path.join(company_folder, "CoverLetter.md")
    with open(cl_path, "w", encoding="utf-8") as f:
        f.write(result.markdown)

    manifest_path = os.path.join(company_folder, "cover_letter_plan.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(result.plan.to_dict(), f, indent=2)
