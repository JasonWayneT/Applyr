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

from drafting_engine import validate_hard_facts
from local_draft_stages import audit_text_against_bullet_corpus


@dataclass
class AuditImproveResult:
    """Same contract shape as audit_and_improve.AuditImproveResult, plus the
    healed text so a caller can actually persist what passed validation."""

    converged: bool
    attempts: int = 1
    final_issues: list[str] = field(default_factory=list)
    skipped: bool = False
    corrected_resume: str = ""
    corrected_cover_letter: str = ""


def _count_summary_sentences(summary_text: str) -> int:
    clean = re.sub(
        r'\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec|vs|approx|eg|ie|ca|Inc|Co|B2B|SaaS|PM|PMs)\.',
        r'\1', summary_text, flags=re.IGNORECASE,
    )
    return len([s for s in re.split(r'\.(?:\s+|$)', clean) if s.strip()])


def apply_claude_native_improvement(
    updated_resume: str,
    updated_cl: str,
    master_resume_text: str,
    bullets: str,
    company_name: str,
) -> AuditImproveResult:
    """Validate a Claude-authored resume/cover-letter pair against the same
    deterministic guards audit_and_improve_company uses, minus the retry loop
    (the caller re-invokes this after re-reasoning, rather than this function
    looping internally).

    updated_resume / updated_cl MUST be FULL documents (contact header plus
    the rest of the section content), with the new summary/body already
    spliced in by the caller - this matches audit_and_improve.py's calling
    convention exactly: improve_resume_summary returns
    resume_md.replace(current_summary, new_summary) and improve_cover_letter
    returns header_block + new_body + signoff. validate_hard_facts checks
    whether the candidate's name appears in the first 300 characters of the
    text it's given, and prepends a repaired contact header (plus a blocking
    "MISSING FACT: Name" warning) when it doesn't. Calling it on a bare
    summary/body fragment with no header would trigger that repair on every
    invocation, regardless of content quality - so the caller must splice
    before calling this function, not after.

    Does NOT write any files - returns a verdict only. The caller (a skill
    step) is responsible for writing Resume.md/CoverLetter.md and compiling
    PDFs once converged=True (using result.corrected_resume /
    result.corrected_cover_letter, the healed text that actually passed
    validation), and for producing a revised updated_resume/updated_cl and
    calling this again if converged=False.
    """
    issues: list[str] = []

    corrected_resume, res_warnings = validate_hard_facts(
        updated_resume, master_resume_text, company_name, 'resume',
    )
    corrected_cl, cl_warnings = validate_hard_facts(
        updated_cl, master_resume_text, company_name, 'cover_letter',
    )

    from quality_checker import HEADER_BLOCK
    cover_audit_corpus = f"{bullets}\n{HEADER_BLOCK}"
    cl_ok, cl_err = audit_text_against_bullet_corpus(corrected_cl, cover_audit_corpus)
    if not cl_ok:
        issues.append(f"Cover letter metric error: {cl_err}")

    summary_section = updated_resume.split("## PROFESSIONAL SUMMARY")[1].split("\n##")[0].strip()
    summary_ok, summary_err = audit_text_against_bullet_corpus(summary_section, bullets)
    if not summary_ok:
        issues.append(f"Summary metric error: {summary_err}")

    sentence_count = _count_summary_sentences(summary_section)
    if sentence_count != 3:
        issues.append(
            f"Summary has {sentence_count} sentence(s), expected exactly 3."
        )

    if res_warnings:
        issues.extend(f"Resume hard-fact warning: {w}" for w in res_warnings)
    if cl_warnings:
        issues.extend(f"Cover letter hard-fact warning: {w}" for w in cl_warnings)

    if issues:
        return AuditImproveResult(converged=False, final_issues=issues)

    return AuditImproveResult(
        converged=True,
        final_issues=[],
        corrected_resume=corrected_resume,
        corrected_cover_letter=corrected_cl,
    )
