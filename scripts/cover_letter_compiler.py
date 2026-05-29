"""Independent cover letter compiler (CR-024). Does not read Resume.md."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional

from claim_catalog import load_catalog
from cover_claim_picker import pick_cover_proofs
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
    return "\n".join(catalog.raw_truth_lines.values())


def compile_cover_letter(
    jd_text: str,
    company_display: str,
    research_packet_path: Optional[str] = None,
    max_retries: int = 2,
) -> CoverLetterResult:
    catalog = load_catalog()
    plan = build_cover_plan(jd_text, company_display, catalog, research_packet_path)
    corpus = _claim_corpus(catalog)

    for attempt in range(max_retries + 1):
        md = render_cover_letter(plan, catalog, jd_text=jd_text)
        md = sanitize_submission_tone(md)
        audit = audit_cover_letter(md, plan, jd_text, corpus)
        wc, _in_band = word_count_report(md)
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
        if attempt < max_retries and len(plan.proofs) >= 2:
            from jd_tailoring import build_jd_profile_deterministic

            profile = build_jd_profile_deterministic(jd_text)
            alt_proofs = pick_cover_proofs(
                catalog, plan.ranked_needs, profile, jd_text, k=2
            )
            if alt_proofs and alt_proofs[-1].claim_id != plan.proofs[-1].claim_id:
                plan.proofs[-1] = alt_proofs[-1]
                continue
        break

    md = render_cover_letter(plan, catalog, jd_text=jd_text)
    md = sanitize_submission_tone(md)
    audit = audit_cover_letter(md, plan, jd_text, corpus)
    wc, _ = word_count_report(md)
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
