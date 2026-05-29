"""
Unified draft compiler — single pipeline for all LLM providers.

Implements FR-089, FR-092, FR-100–FR-104 (CR-014, CR-017);
FR-136–FR-138, FR-140, FR-142, FR-145 (CR-021 compose hardening).

Documents are compiled from claims; JdProfile/cover hooks respect JD_PROFILE_MODE and COVER_HOOK_MODE.
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
    RESUME_CHAR_BUDGET,
    assemble_cover_letter_deterministic,
    audit_text_against_bullet_corpus,
    enforce_resume_char_budget,
    ensure_employer_quotas,
    experience_skeleton,
    normalize_employer_job_titles,
    select_claims_deterministic,
    select_claims_per_employer_local,
)
from pipeline_env import resume_bullet_quotas, resume_only_mode
from quality_checker import HEADER_BLOCK, check_resume, check_and_repair_cover_letter, repair_resume_markdown
from company_slug import company_submission_dir
from utils import (
    load_file,
    load_llm_settings,
    _get_configured_providers,
    WORK_EXP_FILE,
    RESUME_STYLE_REF_FILE,
    RESUME_MASTER_FILE,
    SUBMISSIONS_DIR,
)

PIPELINE_VERSION = "CR-024-cover-engine"


def _cover_engine_v1() -> bool:
    return os.environ.get("COVER_ENGINE", "v1").lower() in ("1", "v1", "true", "yes")


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
    return experience_skeleton()


def _assemble_resume(
    summary: str,
    bullets_by_company: Dict[str, List[str]],
    education_block: str,
    skeleton: dict,
    bullets_with_ids: Optional[Dict[str, str]] = None,
) -> str:
    import copy
    local_bullets = copy.deepcopy(bullets_by_company)
    id_map = copy.deepcopy(bullets_with_ids) if bullets_with_ids else {}
    min_keep = resume_bullet_quotas()
    from tone_guard import sanitize_submission_tone

    def _render() -> str:
        parts = [
            HEADER_BLOCK.strip(),
            "",
            "## PROFESSIONAL SUMMARY",
            sanitize_submission_tone(summary.strip()),
            "",
            "## PROFESSIONAL EXPERIENCE",
            "",
        ]
        for key in EMPLOYERS:
            parts.append(skeleton[key])
            if id_map:
                for cid, text in sorted(
                    [(c, t) for c, t in id_map.items() if _employer_for(c) == key],
                    key=lambda x: x[0],
                ):
                    parts.append(f"* {sanitize_submission_tone(text)}")
            else:
                for b in local_bullets.get(key, [])[:5]:
                    parts.append(f"* {sanitize_submission_tone(b)}")
            parts.append("")
        parts.append(education_block.strip())
        return "\n".join(parts).strip() + "\n"

    result = _render()
    
    prune_order = ["zero_to_sixty", "sterkly", "cision"]

    while len(result) > RESUME_CHAR_BUDGET:
        pruned = False
        for employer in prune_order:
            floor = min_keep.get(employer, 1)
            if id_map:
                emp_bullets = [(c, t) for c, t in id_map.items() if _employer_for(c) == employer]
                if len(emp_bullets) > floor:
                    emp_bullets.sort(key=lambda x: x[0])
                    del id_map[emp_bullets[-1][0]]
                    pruned = True
                    break
            else:
                blist = local_bullets.get(employer, [])
                if len(blist) > floor:
                    blist.pop()
                    pruned = True
                    break
        if not pruned:
            break
        result = _render()

    return result


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
    quotas = resume_bullet_quotas()
    min_total = sum(quotas.get(e, 3) for e in EMPLOYERS)
    selected = select_claims_per_employer_local(jd_text, valid_ids, quotas=quotas)
    if len(selected) < min_total - 2:
        print("    [Compiler] Stage 2: thin selection — keyword fallback.")
        selected = select_claims_deterministic(jd_text, valid_ids, quotas=quotas)
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
    company_folder = company_folder or company_submission_dir(SUBMISSIONS_DIR, company_name)
    os.makedirs(company_folder, exist_ok=True)

    print(f"    [Compiler] CR-017 compose pipeline v{PIPELINE_VERSION} for {display}")

    style_md = load_file(RESUME_STYLE_REF_FILE)
    master_resume = load_file(RESUME_MASTER_FILE)
    catalog = load_catalog()
    valid_ids = catalog.truth_map() if catalog.claims else determinator.load_valid_ids(WORK_EXP_FILE)
    fit = _fit_summary(evaluation_result)

    from jd_tailoring import load_cached_jd_profile_from_folder, save_cached_jd_profile

    profile = load_cached_jd_profile_from_folder(company_folder, jd_text)
    if not profile:
        profile = build_jd_profile(jd_text, fit)
        save_cached_jd_profile(jd_text, profile, company_folder)
    print(f"    [Compiler] Stage 1 JdProfile ({profile.source}): {len(profile.priority_themes)} themes")

    quotas = resume_bullet_quotas()
    selected = _select_claims(jd_text, valid_ids, profile)
    jd_scores = {cid: score_claim_for_jd(valid_ids.get(cid, ""), profile, jd_text) for cid in selected}
    print(f"    [Compiler] Stage 2: {len(selected)} claims selected")

    bullets, fallback_count = generate_bullets_for_claims(selected, valid_ids, jd_text, profile=profile)
    bullets = ensure_employer_quotas(bullets, valid_ids, jd_text, fallback_bullet, quotas=quotas)
    print(f"    [Compiler] Stage 3: {len(bullets)} bullets ({fallback_count} fallbacks)")

    bullets_by_company = _bullets_by_company_ordered(bullets, valid_ids, profile, jd_text)
    bullet_corpus = "\n".join(bullets.values())
    for emp in EMPLOYERS:
        have = len(bullets_by_company.get(emp, []))
        want = quotas.get(emp, 3)
        print(f"    [Compiler] Bullets {emp}: {have}/{want}")

    from pipeline_env import cover_only_mode, resume_only_mode

    skip_cover = resume_only_mode()
    cover_only = cover_only_mode()
    if cover_only:
        skip_cover = False
    resume_md_path = os.path.join(company_folder, "Resume.md")
    skeleton = _experience_skeleton()
    education = _extract_education_from_style(style_md)

    if cover_only:
        resume_md = load_file(resume_md_path)
        if not resume_md or len(resume_md.strip()) < 200:
            raise DraftingPipelineError("COVER_ONLY requires existing Resume.md")
        summary = ""
        print("    [Compiler] COVER_ONLY=1 — keeping existing Resume.md")
    else:
        from local_draft_stages import build_summary_deterministic

        summary = build_summary_deterministic(
            bullets_by_company, jd_text, profile, fit_summary=fit
        )
        ok, err = audit_text_against_bullet_corpus(summary, bullet_corpus)
        if not ok:
            print(f"    [Compiler] Stage 4 summary audit: {err} — safe default.")
            summary = build_summary_deterministic(bullets_by_company, "", None)

        resume_md = _assemble_resume(summary, bullets_by_company, education, skeleton, bullets_with_ids=bullets)
        resume_md = repair_resume_markdown(resume_md, education)
        resume_md = normalize_employer_job_titles(resume_md)
        resume_md = enforce_resume_char_budget(resume_md)
        resume_md = strip_all_metadata_tokens(resume_md)
        with open(resume_md_path, "w", encoding="utf-8") as f:
            f.write(resume_md)

    verify_body = _assemble_resume(summary, bullets_by_company, education, skeleton, bullets_with_ids={
        cid: f"{text} [{cid}]" for cid, text in bullets.items()
    })
    vres = determinator.verify_content(verify_body, valid_ids)
    if not vres["success"]:
        raise DraftingPipelineError(f"verify_content failed: {vres.get('error')}")

    cl_md_path = os.path.join(company_folder, "CoverLetter.md")
    cl_stripped = ""
    cover_plan_dict = None
    if not skip_cover:
        claim_corpus = (
            "\n".join(catalog.raw_truth_lines.values())
            if catalog.claims
            else bullet_corpus
        )
        if _cover_engine_v1():
            from cover_letter_compiler import compile_cover_letter

            research_path = os.path.join(company_folder, "Research_Packet.json")
            rp = research_path if os.path.exists(research_path) else None
            cover_result = compile_cover_letter(jd_text, display, research_packet_path=rp)
            cl_raw = cover_result.markdown
            cover_plan_dict = cover_result.plan.to_dict()
            print(
                f"    [Compiler] Cover engine v1: audit={cover_result.audit_grade} "
                f"score={cover_result.audit_score} words={cover_result.word_count}"
            )
            if cover_result.audit_issues:
                print(f"    [Compiler] Cover audit notes: {cover_result.audit_issues[:3]}")
        else:
            proof = pick_cover_bullets(bullets, valid_ids, profile, jd_text, k=2)
            try:
                cl_raw = assemble_cover_letter_deterministic(
                    display, jd_text, bullets, HEADER_BLOCK, proof_bullets=proof, profile=profile
                )
            except ValueError as e:
                raise DraftingPipelineError(str(e)) from e

        cl_ok_audit, cl_audit_err = audit_text_against_bullet_corpus(
            cl_raw, f"{claim_corpus}\n{HEADER_BLOCK}"
        )
        if not cl_ok_audit:
            raise DraftingPipelineError(f"Cover letter numeric audit: {cl_audit_err}")

        cl_stripped = strip_all_metadata_tokens(determinator.strip_ids(cl_raw))
        with open(cl_md_path, "w", encoding="utf-8") as f:
            f.write(cl_stripped)
        if cover_plan_dict is not None:
            plan_path = os.path.join(company_folder, "cover_letter_plan.json")
            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump(cover_plan_dict, f, indent=2)

    from style_compliance_guard import run_guard

    if not cover_only:
        run_guard(resume_md_path)
    if not skip_cover and os.path.exists(cl_md_path):
        run_guard(cl_md_path)

    try:
        if skip_cover:
            from verification_chain import verify_resume_only_bundle

            final_resume, _warnings = verify_resume_only_bundle(
                resume_md,
                verify_body,
                valid_ids,
                master_resume,
                display,
                resume_md_path,
                bullets_by_company,
                jd_text,
                bullet_corpus,
            )
            final_cl = load_file(cl_md_path) if os.path.exists(cl_md_path) else ""
        elif cover_only:
            from verification_chain import verify_cover_only_bundle

            cover_verify_corpus = (
                claim_corpus if _cover_engine_v1() and catalog.claims else bullet_corpus
            )
            final_cl, _warnings = verify_cover_only_bundle(
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
                cover_verify_corpus,
            )
            final_resume = resume_md
        else:
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

    if not cover_only:
        with open(resume_md_path, "w", encoding="utf-8") as f:
            f.write(final_resume)
    if not skip_cover:
        with open(cl_md_path, "w", encoding="utf-8") as f:
            f.write(final_cl)

    try:
        from draft_linter import lint_draft_text

        lint_docs = [("resume", final_resume)]
        if not skip_cover and final_cl:
            lint_docs.append(("cover_letter", final_cl))
        for label, doc in lint_docs:
            lint_r = lint_draft_text(doc, label)
            if lint_r.get("issues"):
                print(f"    [Compiler] Lint ({label}): {lint_r['issues'][:3]}")
    except Exception:
        pass

    if not cover_only:
        qa_ok, qa_msg = check_resume(resume_md_path)
        if not qa_ok:
            raise DraftingPipelineError(f"Resume QA failed: {qa_msg}")
        print(f"    [Compiler] Resume QA: {qa_msg}")
        resume_pdf = os.path.join(company_folder, "Resume.pdf")
        generate_pdf(resume_md_path, resume_pdf)
    else:
        print("    [Compiler] COVER_ONLY=1 — resume PDF unchanged.")

    if not skip_cover:
        cl_ok, cl_msg = check_and_repair_cover_letter(cl_md_path)
        if not cl_ok:
            raise DraftingPipelineError(f"Cover letter QA failed: {cl_msg}")
        print(f"    [Compiler] Cover QA: {cl_msg}")
        cover_pdf = os.path.join(company_folder, "CoverLetter.pdf")
        generate_pdf(cl_md_path, cover_pdf)
    elif resume_only_mode():
        print("    [Compiler] RESUME_ONLY=1 — cover letter files left unchanged.")

    if not cover_only and not os.path.isfile(os.path.join(company_folder, "Resume.pdf")):
        raise DraftingPipelineError("Resume PDF missing after export")
    if not skip_cover and not cover_only and not os.path.isfile(os.path.join(company_folder, "CoverLetter.pdf")):
        raise DraftingPipelineError("Cover letter PDF missing after export")

    import hashlib

    jd_hash = hashlib.sha256(jd_text.encode("utf-8")).hexdigest()[:16]
    manifest = {
        "pipeline_version": PIPELINE_VERSION,
        "draft_mode": os.environ.get("DRAFT_MODE", "compose"),
        "jd_profile_mode": os.environ.get("JD_PROFILE_MODE", "deterministic"),
        "cover_hook_mode": os.environ.get("COVER_HOOK_MODE", "template"),
        "cover_engine": "v1" if _cover_engine_v1() else "legacy",
        "cover_letter_plan": cover_plan_dict,
        "display_company": display,
        "jd_hash": jd_hash,
        "jd_profile": profile.to_dict(),
        "selected_claim_ids": selected,
        "claim_sources": {
            cid: catalog.raw_truth_lines.get(cid, "")[:200] for cid in bullets
        },
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
