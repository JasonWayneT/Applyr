"""
Fail-closed verification chain for draft output.

Implements FR-102, FR-104 (CR-017).
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

import verify_claims as determinator
from claim_catalog import load_catalog
from drafting_engine import validate_hard_facts
from recruiter_qa import run_recruiter_qa

def _enforce_strict_warnings(warnings: List[str]) -> None:
    """Raise when STRICT_* pipeline flags are enabled (CR-031)."""
    from pipeline_env import strict_anti_claims, strict_metrics

    if strict_metrics():
        for w in warnings:
            if w.startswith("METRIC INTEGRITY"):
                raise ValueError(w)
    if strict_anti_claims():
        for w in warnings:
            if "Anti-claim" in w or "ANTI" in w.upper():
                raise ValueError(w)

JD_INFLATION = re.compile(
    r"(?:led|manage|managed|hire|hiring)\s+(?:a\s+)?team\s+of|"
    r"direct\s+reports|people\s+management|"
    r"(?:built|shipped|trained)\s+(?:an?\s+)?(?:ml|ai)\s+",
    re.IGNORECASE,
)


def strip_all_metadata_tokens(text: str) -> str:
    text = determinator.strip_ids(text)
    text = re.sub(r"\|\s*(ACC|MET|VOC)-\d+\s*\|", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(ACC|MET|VOC)-\d+\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"  +", " ", text)
    return text.strip()


def check_jd_inflation_in_output(text: str, jd_text: str) -> Optional[str]:
    if not JD_INFLATION.search(jd_text):
        return None
    if JD_INFLATION.search(text):
        return "Output echoes JD people-mgmt/AI phrases not supported in profile"
    return None


def check_jd_proper_noun_leak(
    bullets_by_employer: Dict[str, List[str]],
    jd_text: str,
    target_company: str,
) -> Optional[str]:
    """Block target company name appearing under wrong employer bullets."""
    tc = target_company.strip()
    if len(tc) < 4:
        return None
    for employer, blist in bullets_by_employer.items():
        if employer == "cision":
            continue
        for b in blist:
            if tc.lower() in b.lower():
                return f"Target company '{tc}' leaked into {employer} bullet"
    return None


def check_anti_claims(text: str, hints: List[str]) -> Optional[str]:
    """Block phrases catalogued as DO NOT claims (CR-021)."""
    lower = text.lower()
    for hint in hints:
        h = hint.lower().strip()
        if len(h) > 12 and h in lower:
            return f"Anti-claim phrase detected: {hint[:50]}"
    return None


def verify_document_bundle(
    resume_md: str,
    cover_md: str,
    verify_body: str,
    truth_map: dict,
    master_resume: str,
    display_company: str,
    target_company: str,
    resume_path: str,
    cover_path: str,
    bullets_by_company: Dict[str, List[str]],
    jd_text: str,
    bullet_corpus: str,
) -> Tuple[str, str, List[str]]:
    """
    Run full chain. Raises ValueError on hard failure.
    Returns (final_resume, final_cover, warnings).
    """
    warnings: List[str] = []

    vres = determinator.verify_content(verify_body, truth_map)
    if not vres["success"]:
        raise ValueError(f"verify_content failed: {vres.get('error')}")

    leak = check_jd_proper_noun_leak(bullets_by_company, jd_text, display_company)
    if leak:
        raise ValueError(leak)

    infl = check_jd_inflation_in_output(resume_md + cover_md, jd_text)
    if infl:
        raise ValueError(infl)

    catalog = load_catalog()
    anti = check_anti_claims(resume_md + "\n" + cover_md, catalog.anti_claim_hints)
    if anti:
        raise ValueError(anti)

    resume_md = strip_all_metadata_tokens(resume_md)
    cover_md = strip_all_metadata_tokens(cover_md)

    final_resume, w1 = validate_hard_facts(
        resume_md, master_resume, target_company=target_company, doc_type="resume"
    )
    warnings.extend(w1)

    final_cl, w2 = validate_hard_facts(
        cover_md, master_resume, target_company=target_company, doc_type="cover_letter"
    )
    warnings.extend(w2)

    _enforce_strict_warnings(w1)
    _enforce_strict_warnings(w2)

    from local_draft_stages import audit_text_against_bullet_corpus
    from quality_checker import HEADER_BLOCK

    resume_corpus = f"{bullet_corpus}\n{HEADER_BLOCK}"
    ok, err = audit_text_against_bullet_corpus(final_resume, resume_corpus)
    if not ok:
        raise ValueError(f"Resume numeric audit: {err}")

    cl_ok, cl_err = audit_text_against_bullet_corpus(
        final_cl, f"{bullet_corpus}\n{HEADER_BLOCK}"
    )
    if not cl_err:
        pass
    if not cl_ok:
        raise ValueError(f"Cover letter numeric audit: {cl_err}")

    qa_ok, qa_msg = run_recruiter_qa(resume_path, cover_path, display_company)
    if not qa_ok:
        raise ValueError(f"Recruiter QA: {qa_msg}")

    return final_resume, final_cl, warnings


def verify_resume_only_bundle(
    resume_md: str,
    verify_body: str,
    truth_map: dict,
    master_resume: str,
    display_company: str,
    resume_path: str,
    bullets_by_company: Dict[str, List[str]],
    jd_text: str,
    bullet_corpus: str,
) -> Tuple[str, List[str]]:
    """Resume-only regeneration path (skips cover letter QA)."""
    warnings: List[str] = []

    vres = determinator.verify_content(verify_body, truth_map)
    if not vres["success"]:
        raise ValueError(f"verify_content failed: {vres.get('error')}")

    leak = check_jd_proper_noun_leak(bullets_by_company, jd_text, display_company)
    if leak:
        raise ValueError(leak)

    infl = check_jd_inflation_in_output(resume_md, jd_text)
    if infl:
        raise ValueError(infl)

    catalog = load_catalog()
    anti = check_anti_claims(resume_md, catalog.anti_claim_hints)
    if anti:
        raise ValueError(anti)

    resume_md = strip_all_metadata_tokens(resume_md)

    from drafting_engine import validate_hard_facts

    final_resume, w1 = validate_hard_facts(
        resume_md, master_resume, target_company=display_company, doc_type="resume"
    )
    warnings.extend(w1)

    _enforce_strict_warnings(w1)

    from local_draft_stages import audit_text_against_bullet_corpus
    from quality_checker import HEADER_BLOCK

    resume_corpus = f"{bullet_corpus}\n{HEADER_BLOCK}"
    ok, err = audit_text_against_bullet_corpus(final_resume, resume_corpus)
    if not ok:
        raise ValueError(f"Resume numeric audit: {err}")

    from quality_checker import check_resume

    qa_ok, qa_msg = check_resume(resume_path)
    if not qa_ok:
        raise ValueError(f"Resume QA: {qa_msg}")

    return final_resume, warnings


def verify_cover_only_bundle(
    cover_md: str,
    verify_body: str,
    truth_map: dict,
    master_resume: str,
    display_company: str,
    target_company: str,
    resume_path: str,
    cover_path: str,
    bullets_by_company: Dict[str, List[str]],
    jd_text: str,
    bullet_corpus: str,
) -> Tuple[str, List[str]]:
    """Cover-letter-only regeneration (FR-096 tone guard + existing resume on disk)."""
    warnings: List[str] = []

    vres = determinator.verify_content(verify_body, truth_map)
    if not vres["success"]:
        raise ValueError(f"verify_content failed: {vres.get('error')}")

    leak = check_jd_proper_noun_leak(bullets_by_company, jd_text, display_company)
    if leak:
        raise ValueError(leak)

    catalog = load_catalog()
    anti = check_anti_claims(cover_md, catalog.anti_claim_hints)
    if anti:
        raise ValueError(anti)

    cover_md = strip_all_metadata_tokens(cover_md)

    from tone_guard import tone_violations

    tone_hits = tone_violations(cover_md)
    if tone_hits:
        raise ValueError(
            f"Cover letter tone (FR-096): forbidden workforce-reduction language: "
            f"{', '.join(sorted(set(tone_hits)))}"
        )

    final_cl, w2 = validate_hard_facts(
        cover_md, master_resume, target_company=target_company, doc_type="cover_letter"
    )
    warnings.extend(w2)

    _enforce_strict_warnings(w2)

    from local_draft_stages import audit_text_against_bullet_corpus
    from quality_checker import HEADER_BLOCK

    cl_ok, cl_err = audit_text_against_bullet_corpus(
        final_cl, f"{bullet_corpus}\n{HEADER_BLOCK}"
    )
    if not cl_ok:
        raise ValueError(f"Cover letter numeric audit: {cl_err}")

    infl = check_jd_inflation_in_output(final_cl, jd_text)
    if infl:
        raise ValueError(infl)

    if not os.path.exists(resume_path):
        raise ValueError(f"COVER_ONLY requires existing resume: {resume_path}")

    qa_ok, qa_msg = run_recruiter_qa(resume_path, cover_path, display_company)
    if not qa_ok:
        raise ValueError(f"Recruiter QA: {qa_msg}")

    return final_cl, warnings
