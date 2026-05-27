"""
Unified draft compiler — single pipeline for all LLM providers.

Implements FR-089, FR-092, FR-100–FR-104 (CR-014, CR-017).

Documents are compiled from claims; local-first stages optional for JdProfile/selection.
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

import verify_claims as determinator
from drafting_errors import DraftingPipelineError
from bullet_generation import fallback_bullet, generate_bullets_for_claims
from drafting_engine import generate_pdf, validate_hard_facts
from jd_tailoring import (
    JdProfile,
    build_jd_profile,
    pick_cover_bullets,
    score_claim_for_jd,
)
from local_draft_stages import (
    EMPLOYERS,
    assemble_cover_letter_deterministic,
    audit_text_against_bullet_corpus,
    enforce_resume_char_budget,
    ensure_minimum_bullets_per_employer,
    select_claims_deterministic,
    select_claims_per_employer_local,
)
from quality_checker import HEADER_BLOCK, check_resume, check_and_repair_cover_letter, repair_resume_markdown
from utils import (
    load_file,
    load_llm_settings,
    _get_configured_providers,
    WORK_EXP_FILE,
    RESUME_STYLE_REF_FILE,
    RESUME_MASTER_FILE,
    SUBMISSIONS_DIR,
)

PIPELINE_VERSION = "CR-017-1"


def _fit_summary(evaluation_result) -> str:
    if not evaluation_result or not isinstance(evaluation_result, dict):
        return ""
    return str(evaluation_result.get("Summary", "") or "")


def _extract_education_from_style(style_md: str) -> str:
    m = re.search(
        r"(##\s*EDUCATION\s*\n)([\s\S]*?)(?=\n##|\Z)",
        style_md,
        re.IGNORECASE,
    )
    if m:
        return "## EDUCATION\n" + m.group(2).strip() + "\n"
    return (
        "## EDUCATION\n\n"
        "* **Bachelor of Business Administration, Major in Management** — "
        "National University, San Diego, California, 2019\n"
    )


def _experience_skeleton() -> dict:
    return {
        "cision": (
            "### Product Manager (Platform & Ingestion Systems) | Cision | September 2021 - January 2026\n"
            "Full Remote\n"
        ),
        "sterkly": (
            "### Product Manager | Sterkly | February 2019 - August 2021\n"
            "San Diego, CA\n"
        ),
        "zero_to_sixty": (
            "### Product Owner / Account Manager | Zero to Sixty | June 2017 - January 2019\n"
            "San Diego, CA\n"
        ),
    }


def _assemble_resume(
    summary: str,
    bullets_by_company: Dict[str, List[str]],
    education_block: str,
    skeleton: dict,
    bullets_with_ids: Optional[Dict[str, str]] = None,
) -> str:
    parts = [HEADER_BLOCK.strip(), "", "## PROFESSIONAL SUMMARY", summary.strip(), "", "## PROFESSIONAL EXPERIENCE", ""]
    id_map = bullets_with_ids or {}
    for key in EMPLOYERS:
        parts.append(skeleton[key])
        for cid, text in sorted(
            [(c, t) for c, t in id_map.items() if _employer_for(c) == key],
            key=lambda x: x[0],
        ):
            parts.append(f"* {text}")
        if not id_map:
            for b in bullets_by_company.get(key, [])[:5]:
                parts.append(f"* {b}")
        parts.append("")
    parts.append(education_block.strip())
    return "\n".join(parts).strip() + "\n"


def _employer_for(claim_id: str) -> str:
    from local_draft_stages import employer_for_claim_id
    return employer_for_claim_id(claim_id)


def _rank_selected_ids(selected: List[str], valid_ids: dict, profile: JdProfile, jd_text: str) -> List[str]:
    return sorted(
        selected,
        key=lambda cid: score_claim_for_jd(valid_ids.get(cid, ""), profile, jd_text),
        reverse=True,
    )


def _select_claims(jd_text: str, valid_ids: dict, profile: JdProfile) -> List[str]:
    selected = select_claims_per_employer_local(jd_text, valid_ids)
    if len(selected) < 6:
        print("    [Compiler] Stage 2: thin selection — keyword fallback.")
        selected = select_claims_deterministic(jd_text, valid_ids, per_employer=3)
    return _rank_selected_ids(list(dict.fromkeys(selected)), valid_ids, profile, jd_text)


def _bullets_by_company_ordered(
    bullets: Dict[str, str], valid_ids: dict, profile: JdProfile, jd_text: str
) -> Dict[str, List[str]]:
    ranked_ids = _rank_selected_ids(list(bullets.keys()), valid_ids, profile, jd_text)
    grouped: Dict[str, List[str]] = {e: [] for e in EMPLOYERS}
    for cid in ranked_ids:
        grouped[_employer_for(cid)].append(bullets[cid])
    return grouped


def run(
    company_name: str,
    jd_text: str,
    work_exp: str,
    evaluation_result=None,
    company_folder: Optional[str] = None,
    display_name: Optional[str] = None,
):
    """
    Unified draft compiler. Raises DraftingPipelineError on failure.
    """
    from claim_catalog import load_catalog
    from verification_chain import strip_all_metadata_tokens, verify_document_bundle

    settings = load_llm_settings()
    if not _get_configured_providers(settings):
        raise DraftingPipelineError("No LLM provider configured for drafting")

    display = (display_name or company_name).strip()
    company_folder = company_folder or os.path.join(
        SUBMISSIONS_DIR, company_name.lower().replace(" ", "_")
    )
    os.makedirs(company_folder, exist_ok=True)

    print(f"    [Compiler] CR-017 compose pipeline v{PIPELINE_VERSION} for {display}")

    style_md = load_file(RESUME_STYLE_REF_FILE)
    master_resume = load_file(RESUME_MASTER_FILE)
    catalog = load_catalog()
    valid_ids = catalog.truth_map() if catalog.claims else determinator.load_valid_ids(WORK_EXP_FILE)
    fit = _fit_summary(evaluation_result)

    profile = build_jd_profile(jd_text, fit)
    print(f"    [Compiler] Stage 1 JdProfile ({profile.source}): {len(profile.priority_themes)} themes")

    selected = _select_claims(jd_text, valid_ids, profile)
    jd_scores = {cid: score_claim_for_jd(valid_ids.get(cid, ""), profile, jd_text) for cid in selected}
    print(f"    [Compiler] Stage 2: {len(selected)} claims selected")

    bullets, fallback_count = generate_bullets_for_claims(selected, valid_ids, jd_text, profile=profile)
    bullets = ensure_minimum_bullets_per_employer(bullets, valid_ids, jd_text, fallback_bullet)
    print(f"    [Compiler] Stage 3: {len(bullets)} bullets ({fallback_count} fallbacks)")

    bullets_by_company = _bullets_by_company_ordered(bullets, valid_ids, profile, jd_text)
    bullet_corpus = "\n".join(bullets.values())

    from local_draft_stages import build_summary_deterministic

    summary = build_summary_deterministic(bullets_by_company, jd_text, profile)
    ok, err = audit_text_against_bullet_corpus(summary, bullet_corpus)
    if not ok:
        print(f"    [Compiler] Stage 4 summary audit: {err} — safe default.")
        summary = build_summary_deterministic(bullets_by_company, "", None)

    skeleton = _experience_skeleton()
    education = _extract_education_from_style(style_md)
    resume_md = _assemble_resume(summary, bullets_by_company, education, skeleton, bullets_with_ids=bullets)
    resume_md = repair_resume_markdown(resume_md, education)
    resume_md = enforce_resume_char_budget(resume_md)

    verify_body = _assemble_resume(summary, bullets_by_company, education, skeleton, bullets_with_ids={
        cid: f"{text} [{cid}]" for cid, text in bullets.items()
    })
    vres = determinator.verify_content(verify_body, valid_ids)
    if not vres["success"]:
        raise DraftingPipelineError(f"verify_content failed: {vres.get('error')}")

    resume_md = strip_all_metadata_tokens(resume_md)
    resume_md_path = os.path.join(company_folder, "Resume.md")

    proof = pick_cover_bullets(bullets, valid_ids, profile, jd_text, k=2)
    try:
        cl_raw = assemble_cover_letter_deterministic(
            display, jd_text, bullets, HEADER_BLOCK, proof_bullets=proof, profile=profile
        )
    except ValueError as e:
        raise DraftingPipelineError(str(e)) from e

    cl_ok_audit, cl_audit_err = audit_text_against_bullet_corpus(
        cl_raw, f"{bullet_corpus}\n{HEADER_BLOCK}"
    )
    if not cl_ok_audit:
        raise DraftingPipelineError(f"Cover letter numeric audit: {cl_audit_err}")

    cl_md_path = os.path.join(company_folder, "CoverLetter.md")
    cl_stripped = strip_all_metadata_tokens(determinator.strip_ids(cl_raw))

    with open(resume_md_path, "w", encoding="utf-8") as f:
        f.write(resume_md)
    with open(cl_md_path, "w", encoding="utf-8") as f:
        f.write(cl_stripped)

    from style_compliance_guard import run_guard
    run_guard(resume_md_path)
    run_guard(cl_md_path)

    try:
        final_resume, final_cl, _warnings = verify_document_bundle(
            resume_md,
            cl_stripped,
            verify_body,
            valid_ids,
            master_resume,
            display,
            company_name,
            resume_md_path,
            cl_md_path,
            bullets_by_company,
            jd_text,
            bullet_corpus,
        )
    except ValueError as e:
        raise DraftingPipelineError(str(e)) from e

    with open(resume_md_path, "w", encoding="utf-8") as f:
        f.write(final_resume)
    with open(cl_md_path, "w", encoding="utf-8") as f:
        f.write(final_cl)

    qa_ok, qa_msg = check_resume(resume_md_path)
    if not qa_ok:
        raise DraftingPipelineError(f"Resume QA failed: {qa_msg}")
    print(f"    [Compiler] Resume QA: {qa_msg}")
    generate_pdf(resume_md_path, os.path.join(company_folder, "Resume.pdf"))

    cl_ok, cl_msg = check_and_repair_cover_letter(cl_md_path)
    if not cl_ok:
        raise DraftingPipelineError(f"Cover letter QA failed: {cl_msg}")
    print(f"    [Compiler] Cover QA: {cl_msg}")
    generate_pdf(cl_md_path, os.path.join(company_folder, "CoverLetter.pdf"))

    manifest = {
        "pipeline_version": PIPELINE_VERSION,
        "draft_mode": os.environ.get("DRAFT_MODE", "compose"),
        "display_company": display,
        "jd_profile": profile.to_dict(),
        "selected_claim_ids": selected,
        "jd_scores": jd_scores,
        "bullet_claim_ids": list(bullets.keys()),
        "fallback_bullet_count": fallback_count,
        "employer_counts": {
            e: sum(1 for cid in bullets if _employer_for(cid) == e) for e in EMPLOYERS
        },
        "fit_summary_used": bool(fit),
        "verification_passed": True,
    }
    manifest_path = os.path.join(company_folder, "draft_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"    [Compiler] Complete — manifest: {manifest_path}")
