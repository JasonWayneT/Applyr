"""Claude-native replacement for audit_and_improve.py's tailoring + safety net
(CR-070 Epic 3). Reuses the existing deterministic guards unchanged - only the
three call_llm functions (analyze_company_context, improve_resume_summary,
improve_cover_letter) are replaced, by having Claude produce new_summary/
new_cover_letter as arguments during a live skill turn instead of a subprocess
LLM call. scripts/audit_and_improve.py itself is untouched and stays reachable
as an opt-in legacy path.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from drafting_engine import validate_hard_facts
from local_draft_stages import audit_text_against_bullet_corpus


@dataclass
class AuditImproveResult:
    """Same contract shape as audit_and_improve.AuditImproveResult."""

    converged: bool
    attempts: int = 1
    final_issues: list[str] = field(default_factory=list)
    skipped: bool = False


def _count_summary_sentences(summary_text: str) -> int:
    clean = re.sub(
        r'\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec|vs|approx|eg|ie|ca|Inc|Co|B2B|SaaS|PM|PMs)\.',
        r'\1', summary_text, flags=re.IGNORECASE,
    )
    return len([s for s in re.split(r'\.(?:\s+|$)', clean) if s.strip()])


def apply_claude_native_improvement(
    context: dict,
    new_summary: str,
    new_cover_letter: str,
    master_resume_text: str,
    bullets: str,
    company_name: str,
) -> AuditImproveResult:
    """Validate a Claude-authored summary/cover-letter pair against the same
    deterministic guards audit_and_improve_company uses, minus the retry loop
    (the caller re-invokes this after re-reasoning, rather than this function
    looping internally).

    Does NOT write any files - returns a verdict only. The caller (a skill
    step) is responsible for writing Resume.md/CoverLetter.md and compiling
    PDFs once converged=True, and for producing a revised new_summary/
    new_cover_letter and calling this again if converged=False.
    """
    issues: list[str] = []

    corrected_summary, summary_warnings = validate_hard_facts(
        new_summary, master_resume_text, company_name, 'resume',
    )
    corrected_cl, cl_warnings = validate_hard_facts(
        new_cover_letter, master_resume_text, company_name, 'cover_letter',
    )

    cl_ok, cl_err = audit_text_against_bullet_corpus(corrected_cl, bullets)
    if not cl_ok:
        issues.append(f"Cover letter metric error: {cl_err}")

    summary_ok, summary_err = audit_text_against_bullet_corpus(corrected_summary, bullets)
    if not summary_ok:
        issues.append(f"Summary metric error: {summary_err}")

    sentence_count = _count_summary_sentences(corrected_summary)
    if sentence_count != 3:
        issues.append(
            f"Summary has {sentence_count} sentence(s), expected exactly 3."
        )

    if summary_warnings:
        issues.extend(f"Summary hard-fact warning: {w}" for w in summary_warnings)
    if cl_warnings:
        issues.extend(f"Cover letter hard-fact warning: {w}" for w in cl_warnings)

    if issues:
        return AuditImproveResult(converged=False, final_issues=issues)

    return AuditImproveResult(converged=True, final_issues=[])
