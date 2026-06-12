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
    has_ai_signal,
    pick_cover_bullets,
    score_claim_for_jd,
)
from local_draft_stages import (
    EMPLOYERS,
    RESUME_CHAR_BUDGET,
    assemble_cover_letter_deterministic,
    audit_text_against_bullet_corpus,
    build_projects_section,
    build_skills_section,
    enforce_resume_char_budget,
    ensure_employer_quotas,
    experience_skeleton,
    normalize_employer_job_titles,
    select_claims_deterministic,
    select_claims_per_employer_local,
)
from pipeline_env import apply_submission_defaults, resume_bullet_quotas, resume_only_mode

# Enforce all strict guards early when SUBMISSION_MODE=1
apply_submission_defaults()
from quality_checker import HEADER_BLOCK, check_resume, check_and_repair_cover_letter, check_conversion_signals, check_cl_conversion_signals, repair_resume_markdown
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
    jd_text: str = "",
    profile=None,
) -> str:
    import copy
    local_bullets = copy.deepcopy(bullets_by_company)
    id_map = copy.deepcopy(bullets_with_ids) if bullets_with_ids else {}
    min_keep = resume_bullet_quotas()
    from tone_guard import sanitize_submission_tone

    def _render() -> str:
        skills_block = build_skills_section(
            id_map or {},
            jd_text=jd_text,
            profile=profile,
        )
        parts = [
            HEADER_BLOCK.strip(),
            "",
            "## PROFESSIONAL SUMMARY",
            sanitize_submission_tone(summary.strip()),
            "",
        ]
        if skills_block:
            parts.append(skills_block)
        parts += [
            "## PROFESSIONAL EXPERIENCE",
            "",
        ]
        for key in EMPLOYERS:
            parts.append(skeleton[key])
            if id_map:
                from conversion_framing import has_outcome_metric, is_outcome_bullet

                emp_items = [(c, t) for c, t in id_map.items() if _employer_for(c) == key]
                emp_items.sort(
                    key=lambda x: (
                        0 if has_outcome_metric(x[1]) else 1,
                        0 if is_outcome_bullet(x[1]) else 1,
                        x[0],
                    )
                )
                for cid, text in emp_items:
                    parts.append(f"* {sanitize_submission_tone(text)}")
            else:
                for b in local_bullets.get(key, [])[:5]:
                    parts.append(f"* {sanitize_submission_tone(b)}")
            parts.append("")
        if projects_injected[0] and has_ai_signal(jd_text):
            projects_block = build_projects_section(jd_text)
            if projects_block:
                parts.append("")
                parts.append(projects_block.strip())
        parts.append("")
        parts.append(education_block.strip())
        return "\n".join(parts).strip() + "\n"

    projects_injected = [has_ai_signal(jd_text)]  # mutable flag for pruning

    result = _render()

    from candidate_context import load_employers_ordered
    prune_order = list(reversed(load_employers_ordered()))

    # First pruning pass: remove PROJECTS section if over budget before touching bullets
    if len(result) > RESUME_CHAR_BUDGET and projects_injected[0]:
        projects_injected[0] = False
        result = _render()

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
    if "_" in display and " " not in display:
        display = display.replace("_", " ").title()
    company_folder = company_folder or company_submission_dir(SUBMISSIONS_DIR, company_name)
    os.makedirs(company_folder, exist_ok=True)

    print(f"    [Compiler] CR-017 compose pipeline v{PIPELINE_VERSION} for {display}")

    style_md = load_file(RESUME_STYLE_REF_FILE)
    master_resume = load_file(RESUME_MASTER_FILE)
    catalog = load_catalog()
    from catalog_validator import validate_catalog
    from pipeline_env import block_cover_pdf_on_audit_fail, strict_catalog_drift, strict_cover_audit

    cat_val = validate_catalog()
    if not cat_val.ok:
        preview = "; ".join(cat_val.errors[:3])
        if strict_catalog_drift():
            raise DraftingPipelineError(f"Catalog validation failed: {preview}")
        print(f"    [Compiler] Catalog validation warnings: {preview}")

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
    from theme_primaries import inject_theme_primaries

    prior = set(selected)
    selected = inject_theme_primaries(selected, valid_ids, jd_text, profile, quotas=quotas)
    added = [c for c in selected if c not in prior]
    if added:
        print(f"    [Compiler] Theme primaries: {', '.join(added[:4])}")
    jd_scores = {cid: score_claim_for_jd(valid_ids.get(cid, ""), profile, jd_text) for cid in selected}
    print(f"    [Compiler] Stage 2: {len(selected)} claims selected")

    bullets, fallback_count = generate_bullets_for_claims(selected, valid_ids, jd_text, profile=profile)
    bullets = ensure_employer_quotas(bullets, valid_ids, jd_text, fallback_bullet, quotas=quotas)
    from local_draft_stages import enforce_metric_bullet_floor
    from conversion_framing import enforce_conversion_framing

    bullets = enforce_metric_bullet_floor(bullets, valid_ids, jd_text, fallback_bullet)
    bullets = enforce_conversion_framing(bullets, valid_ids, jd_text, fallback_bullet)
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

        # Stale-resume guard: warn if Resume.md is newer than the last
        # draft_manifest.json, which means it may have been manually edited
        # after the last pipeline run and is now unverified.
        manifest_path = os.path.join(company_folder, "draft_manifest.json")
        try:
            if os.path.exists(manifest_path) and os.path.exists(resume_md_path):
                manifest_mtime = os.path.getmtime(manifest_path)
                resume_mtime = os.path.getmtime(resume_md_path)
                if resume_mtime > manifest_mtime + 5:  # 5s grace for near-simultaneous writes
                    from pipeline_env import submission_mode
                    msg = (
                        "COVER_ONLY warning: Resume.md is newer than draft_manifest.json — "
                        "it may have been manually edited and is unverified. "
                        "Run a full pipeline pass before submitting."
                    )
                    if submission_mode():
                        raise DraftingPipelineError(msg)
                    print(f"    [Compiler] *** {msg} ***")
        except DraftingPipelineError:
            raise
        except Exception:
            pass

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

        resume_md = _assemble_resume(
            summary, bullets_by_company, education, skeleton,
            bullets_with_ids=bullets, jd_text=jd_text, profile=profile,
        )
        resume_md = repair_resume_markdown(resume_md, education)
        resume_md = normalize_employer_job_titles(resume_md)
        resume_md = enforce_resume_char_budget(resume_md)
        resume_md = strip_all_metadata_tokens(resume_md)
        with open(resume_md_path, "w", encoding="utf-8") as f:
            f.write(resume_md)

    verify_body = _assemble_resume(
        summary, bullets_by_company, education, skeleton,
        bullets_with_ids={cid: f"{text} [{cid}]" for cid, text in bullets.items()},
        jd_text=jd_text, profile=profile,
    )
    vres = determinator.verify_content(verify_body, valid_ids)
    if not vres["success"]:
        raise DraftingPipelineError(f"verify_content failed: {vres.get('error')}")

    cl_md_path = os.path.join(company_folder, "CoverLetter.md")
    cl_stripped = ""
    cover_plan_dict = None
    cover_result = None
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
            cover_result = compile_cover_letter(
                jd_text,
                display,
                research_packet_path=rp,
                bullet_corpus=bullet_corpus,
            )
            cl_raw = cover_result.markdown
            cover_plan_dict = cover_result.plan.to_dict()
            print(
                f"    [Compiler] Cover engine v1: audit={cover_result.audit_grade} "
                f"score={cover_result.audit_score} words={cover_result.word_count}"
            )
            if cover_result.audit_issues:
                print(f"    [Compiler] Cover audit notes: {cover_result.audit_issues[:3]}")
            if strict_cover_audit() and cover_result.audit_grade != "Pass":
                issues = "; ".join(cover_result.audit_issues[:5]) or "audit grade below Pass"
                raise DraftingPipelineError(
                    f"Cover letter audit failed (STRICT_COVER_AUDIT=1): {cover_result.audit_grade} — {issues}"
                )
        else:
            proof = pick_cover_bullets(bullets, valid_ids, profile, jd_text, k=2)
            try:
                cl_raw = assemble_cover_letter_deterministic(
                    display, jd_text, bullets, HEADER_BLOCK, proof_bullets=proof, profile=profile
                )
            except ValueError as e:
                raise DraftingPipelineError(str(e)) from e

        if cover_plan_dict and catalog.claims:
            story_lines = []
            for slot in cover_plan_dict.get("proofs") or []:
                cid = slot.get("claim_id") if isinstance(slot, dict) else ""
                rec = catalog.claims.get(cid or "")
                if rec and rec.cover_story:
                    story_lines.append(rec.cover_story)
            if story_lines:
                claim_corpus = f"{claim_corpus}\n" + "\n".join(story_lines)

        cover_audit_corpus = f"{bullet_corpus}\n{claim_corpus}\n{HEADER_BLOCK}"
        cl_ok_audit, cl_audit_err = audit_text_against_bullet_corpus(
            cl_raw, cover_audit_corpus
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
            cover_verify_corpus = (
                f"{bullet_corpus}\n{claim_corpus}"
                if _cover_engine_v1() and catalog.claims
                else bullet_corpus
            )
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
                cover_verify_corpus,
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

    rubric_result = None
    conversion_critique = None
    if not cover_only:
        qa_ok, qa_msg = check_resume(resume_md_path)
        if not qa_ok:
            raise DraftingPipelineError(f"Resume QA failed: {qa_msg}")
        print(f"    [Compiler] Resume QA: {qa_msg}")

        try:
            from resume_rubric import score_resume
            rubric_result = score_resume(
                load_file(resume_md_path) or "",
                jd_text,
                bullets_by_company,
            )
            flag = " [BELOW THRESHOLD — review recommended]" if rubric_result["threshold_flag"] else ""
            print(
                f"    [Compiler] Rubric score: {rubric_result['overall']}/100"
                f" (summary {rubric_result['summary']['score']}"
                f" / exp {rubric_result['experience']['score']}){flag}"
            )
        except Exception as _rub_err:
            # threshold_flag is None (unknown), not False — a scoring error
            # is not evidence the resume is above threshold.
            rubric_result = {"overall": None, "threshold_flag": None, "error": str(_rub_err)}
            print(f"    [Compiler] Rubric scoring error (score unavailable): {_rub_err}")

        from drafting_engine import get_pdf_page_count
        from pipeline_env import conversion_retry_max, strict_conversion_critique
        from critique_retry import (
            apply_critique_fixes,
            extract_failing_codes,
            format_critique_failure,
            has_fixable,
        )
        from quality_checker import check_conversion_critique

        resume_pdf = os.path.join(company_folder, "Resume.pdf")
        from candidate_context import load_employers_ordered
        _pdf_prune_order = list(reversed(load_employers_ordered()))
        retry_log: List[dict] = []
        retry_state: Dict = {"retry_opts": {}}
        max_attempts = conversion_retry_max()

        def _post_format_resume(text: str) -> str:
            """Post-compile formatting guard (Track C — audit improvements).

            1. Normalize location line spacing and state code casing.
            2. Warn if 'Partnered closely' appears more than once.
            3. Strip trailing commas on bullet lines.
            """
            import sys

            # 1. Normalize header location: 'City,St' → 'City, ST'
            text = re.sub(r'([A-Za-z]),([A-Za-z])', r'\1, \2', text)
            # Uppercase two-letter state codes after comma+space in the header area
            text = re.sub(
                r'(,\s*)([A-Za-z]{2})(\s*\|)',
                lambda m: f"{m.group(1)}{m.group(2).upper()}{m.group(3)}",
                text,
            )

            # 2. Warn on repeated "Partnered closely"
            partnered_count = len(re.findall(r'[Pp]artnered closely', text))
            if partnered_count > 1:
                print(
                    f"    [PostFormat] WARNING: 'Partnered closely' appears {partnered_count}x — consider varying.",
                    file=sys.stderr,
                )

            # 3. Strip trailing commas on bullet lines: '- Foo, bar,' → '- Foo, bar'
            def _strip_trailing_comma(line: str) -> str:
                stripped = line.rstrip()
                if stripped.endswith(','):
                    return stripped[:-1]
                return line

            lines = text.split('\n')
            lines = [
                _strip_trailing_comma(l) if l.lstrip().startswith('*') or l.lstrip().startswith('-')
                else l
                for l in lines
            ]
            return '\n'.join(lines)

        def _assemble_and_write_resume() -> str:
            nonlocal final_resume
            md = _assemble_resume(
                summary,
                bullets_by_company,
                education,
                skeleton,
                bullets_with_ids=bullets,
                jd_text=jd_text,
                profile=profile,
            )
            md = repair_resume_markdown(md, education)
            md = normalize_employer_job_titles(md)
            md = enforce_resume_char_budget(md)
            md = strip_all_metadata_tokens(md)
            md = _post_format_resume(md)
            with open(resume_md_path, "w", encoding="utf-8") as _f:
                _f.write(md)
            final_resume = md
            return md

        def _pdf_page_prune() -> int:
            attempts = 0
            while get_pdf_page_count(resume_pdf) > 1 and attempts < 8:
                attempts += 1
                pruned = False
                for employer in _pdf_prune_order:
                    floor = quotas.get(employer, 1)
                    emp_cids = [c for c in bullets if _employer_for(c) == employer]
                    if len(emp_cids) > floor:
                        jd_lower = jd_text.lower()
                        worst = min(
                            emp_cids,
                            key=lambda c: sum(
                                1 for w in set(re.findall(r"[a-z]{4,}", jd_lower))
                                if w in bullets.get(c, "").lower()
                            ),
                        )
                        del bullets[worst]
                        pruned = True
                        break
                if not pruned:
                    print("    [Compiler] Page-count guard: cannot prune further (floor reached).")
                    break
                nonlocal bullets_by_company
                bullets_by_company = _bullets_by_company_ordered(
                    bullets, valid_ids, profile, jd_text
                )
                _assemble_and_write_resume()
                generate_pdf(resume_md_path, resume_pdf)
            if attempts:
                pages_final = get_pdf_page_count(resume_pdf)
                status = "OK" if pages_final == 1 else f"STILL {pages_final} pages"
                print(
                    f"    [Compiler] Page-count guard: {attempts} prune(s) — {status}."
                )
            return attempts

        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                _assemble_and_write_resume()
                qa_ok, qa_msg = check_resume(resume_md_path)
                if not qa_ok:
                    print(f"    [Compiler] Retry {attempt}: Resume QA failed — {qa_msg}")
                    break

            generate_pdf(resume_md_path, resume_pdf)
            _pdf_page_prune()

            try:
                conversion_critique = check_conversion_critique(
                    load_file(resume_md_path) or "",
                    pdf_path=resume_pdf,
                    bullets_by_company=bullets_by_company,
                    jd_text=jd_text,
                )
                conversion_critique["attempts"] = attempt
                conversion_critique["retry_log"] = list(retry_log)
                if not conversion_critique.get("pass"):
                    conversion_critique["final_codes"] = extract_failing_codes(
                        conversion_critique.get("issues") or []
                    )

                if conversion_critique.get("issues"):
                    print(
                        f"    [Compiler] Conversion critique attempt {attempt} "
                        f"({conversion_critique['issue_count']} issue(s)):"
                    )
                    for issue in conversion_critique["issues"][:5]:
                        print(f"      {issue}")
                if conversion_critique.get("strengths"):
                    print(
                        "    [Compiler] Conversion strengths: "
                        + "; ".join(conversion_critique["strengths"][:3])
                    )
                if conversion_critique.get("pass"):
                    print(f"    [Compiler] Conversion critique: PASS (attempt {attempt}).")
                    break

                print(
                    f"    [Compiler] Conversion critique: FAIL (attempt {attempt}/{max_attempts})."
                )
                if attempt >= max_attempts or not has_fixable(conversion_critique):
                    break

                codes = extract_failing_codes(conversion_critique.get("issues") or [])
                fix = apply_critique_fixes(
                    codes,
                    bullets=bullets,
                    valid_ids=valid_ids,
                    jd_text=jd_text,
                    fallback_bullet_fn=fallback_bullet,
                    retry_state=retry_state,
                    attempt=attempt,
                )
                if not fix.get("changed"):
                    break
                if fix.get("log_entry"):
                    retry_log.append(fix["log_entry"])
                    print(
                        f"    [Compiler] Conversion retry {attempt}: "
                        f"{fix['log_entry']['action']} for {', '.join(codes)}"
                    )

                bullets = fix["bullets"]
                if fix.get("reframe_bullets") or fix.get("rebuild_summary"):
                    bullets_by_company = _bullets_by_company_ordered(
                        bullets, valid_ids, profile, jd_text
                    )
                if fix.get("rebuild_summary"):
                    from local_draft_stages import build_summary_deterministic

                    summary = build_summary_deterministic(
                        bullets_by_company,
                        jd_text,
                        profile,
                        fit_summary=fit,
                        retry_opts=fix.get("retry_opts"),
                    )
                if fix.get("pdf_only"):
                    continue
            except Exception as _crit_err:
                conversion_critique = {"pass": None, "error": str(_crit_err), "attempts": attempt}
                print(f"    [Compiler] Conversion critique error: {_crit_err}")
                break

        if (
            strict_conversion_critique()
            and conversion_critique
            and conversion_critique.get("pass") is False
        ):
            raise DraftingPipelineError(
                format_critique_failure(conversion_critique, retry_log)
            )
        if conversion_critique and not conversion_critique.get("pass") and not strict_conversion_critique():
            print("    [Compiler] Conversion critique: FAIL — review recommended.")
    else:
        print("    [Compiler] COVER_ONLY=1 — resume PDF unchanged.")

    if not skip_cover:
        cl_ok, cl_msg = check_and_repair_cover_letter(cl_md_path)
        if not cl_ok:
            raise DraftingPipelineError(f"Cover letter QA failed: {cl_msg}")
        print(f"    [Compiler] Cover QA: {cl_msg}")
        cover_pdf = os.path.join(company_folder, "CoverLetter.pdf")
        cover_audit_failed = (
            cover_result is not None and cover_result.audit_grade != "Pass"
        )
        if cover_audit_failed and block_cover_pdf_on_audit_fail():
            print(
                f"    [Compiler] Cover PDF skipped — audit grade "
                f"{cover_result.audit_grade} (score {cover_result.audit_score})"
            )
        else:
            generate_pdf(cl_md_path, cover_pdf)
    elif resume_only_mode():
        print("    [Compiler] RESUME_ONLY=1 — cover letter files left unchanged.")

    if not cover_only and not os.path.isfile(os.path.join(company_folder, "Resume.pdf")):
        raise DraftingPipelineError("Resume PDF missing after export")
    cover_pdf_expected = (
        not skip_cover
        and not cover_only
        and not (
            cover_result is not None
            and cover_result.audit_grade != "Pass"
            and block_cover_pdf_on_audit_fail()
        )
    )
    if cover_pdf_expected and not os.path.isfile(
        os.path.join(company_folder, "CoverLetter.pdf")
    ):
        raise DraftingPipelineError("Cover letter PDF missing after export")

    import hashlib

    from claim_composer import strip_bridge_prefix

    claim_strength: dict[str, str] = {}
    for cid, text in bullets.items():
        raw = (catalog.raw_truth_lines.get(cid) or "").strip()
        stripped = strip_bridge_prefix(text).strip()
        if stripped != text.strip() and text.strip() != raw:
            claim_strength[cid] = "reasonable_reframe"
        else:
            claim_strength[cid] = "verified"

    from pipeline_env import allow_fit_summary

    jd_hash = hashlib.sha256(jd_text.encode("utf-8")).hexdigest()[:16]
    cover_audit_meta = None
    if cover_result is not None:
        cover_audit_meta = {
            "grade": cover_result.audit_grade,
            "score": cover_result.audit_score,
            "passed": cover_result.audit_grade == "Pass",
            "issues": cover_result.audit_issues[:5],
        }
    conversion_warnings = check_conversion_signals(
        load_file(resume_md_path) or "",
        bullets_by_company,
        jd_text=jd_text,
    )
    if conversion_warnings:
        print(f"    [Compiler] Conversion warnings ({len(conversion_warnings)}): "
              + " | ".join(conversion_warnings[:3]))

    cl_cover_path = os.path.join(company_folder, "CoverLetter.md")
    cl_conversion_warnings = check_cl_conversion_signals(
        load_file(cl_cover_path) or "",
        jd_text,
    )
    if cl_conversion_warnings:
        print(f"    [Compiler] CL conversion warnings ({len(cl_conversion_warnings)}): "
              + " | ".join(cl_conversion_warnings[:2]))

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
        "fit_summary_used": bool(fit) and allow_fit_summary(),
        "claim_strength": claim_strength,
        "cover_audit": cover_audit_meta,
        "verification_passed": True,
        "conversion_warnings": conversion_warnings,
        "conversion_critique": conversion_critique,
        "cl_conversion_warnings": cl_conversion_warnings,
        "rubric_score": rubric_result if not cover_only else None,
    }
    manifest_path = os.path.join(company_folder, "draft_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"    [Compiler] Complete — manifest: {manifest_path}")
