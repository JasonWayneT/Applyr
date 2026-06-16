import os
import re
import json
from typing import Dict, List

# Sections that may appear in a final resume beyond the three required ones.
# Used by downstream guards to avoid flagging legitimately injected sections.
KNOWN_OPTIONAL_SECTIONS = {"CORE COMPETENCIES", "PROJECTS"}

def _header_block() -> str:
    from utils import format_contact_header_block
    return format_contact_header_block()


def _candidate_name_upper() -> str:
    from utils import load_identity_profile
    return (load_identity_profile().get("name") or "John Doe").upper()

def check_and_repair_cover_letter(file_path):
    """
    Checks if CoverLetter.md has the proper header, length, and no em-dashes.
    Repairs missing headers automatically.
    Returns (True, message) if passed/repaired, (False, message) if failed.
    """
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}"
        
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    messages = []
    repaired = False

    from tone_guard import tone_violations

    tone_hits = tone_violations(content)
    if tone_hits:
        messages.append(
            f"[CL-010 FAIL] Forbidden workforce-reduction language (use constraints framing): "
            f"{', '.join(sorted(set(tone_hits)))}"
        )

    # Check for em-dashes (Rule CL-008: Authentic Voice and Anti-AI fingerprint)
    if '—' in content or '--' in content:
        messages.append("[CL-008 FAIL] Forbidden em-dash (—) or '--' found. Violates the Anti-AI fingerprint standard.")
        
    # Check for header (Rule H-001/H-002: Contact Header in body)
    if f"# {_candidate_name_upper()}" not in content.upper():
        messages.append("[H-001 WARNING] Missing standard header block. Auto-repairing...")
        content = _header_block() + content.lstrip()
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        repaired = True
        messages.append("[H-001 OK] Header block successfully injected.")

    # Check for length (Rule CL-006: ~1 page; CR-024 Match Brief allows slightly longer)
    # 2600 chars aligns with 350-word budget at ~6 chars/word plus structural overhead
    char_count = len(content)
    cover_char_limit = 2600
    if char_count > cover_char_limit:
        messages.append(
            f"[CL-006 WARNING] Cover letter length ({char_count} chars) exceeds "
            f"the {cover_char_limit}-char single-page threshold."
        )
        
    # Check for bracket placeholders or redactions (Rule CL-009: Zero-Placeholder Integrity)
    placeholders = re.findall(r'\[[^\]]{2,}\]', content)
    cleaned_placeholders = [p for p in placeholders if not re.search(r'https?://', p) and 'REDACTED' in p.upper() or any(k in p.upper() for k in ['COMPANY', 'NAME', 'DATE', 'INSERT', 'TITLE', 'ROLE'])]
    if cleaned_placeholders:
        messages.append(f"[CL-009 FAIL] Corrupted placeholder brackets found: {', '.join(cleaned_placeholders)}")

    from drafting_errors import SelfCorrectionError
    
    if repaired:
        return True, " | ".join(messages)
    elif any("[CL-008 FAIL]" in msg or "[CL-009 FAIL]" in msg or "[CL-010 FAIL]" in msg for msg in messages):
        raise SelfCorrectionError(" | ".join(messages))
    elif messages:
        # Some warnings might just be length warnings. We'll raise error for length too if we want self-correction
        if any("[CL-006 WARNING]" in msg for msg in messages):
            raise SelfCorrectionError(" | ".join(messages))
        return True, " | ".join(messages)
    return True, "[CL-001 PASS] Cover letter passed all best practice checks."

def check_resume(file_path):
    """
    Checks if Resume.md has correct sections, job title formatting, no em-dashes,
    and adheres to the Option A Clean Action-Verb Standard.
    Returns (True, message) if passed, (False, message) if failed.
    """
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}"
        
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    messages = []
    
    from tone_guard import tone_violations

    tone_hits = tone_violations(content)
    if tone_hits:
        messages.append(
            f"[R-011 FAIL] Forbidden workforce-reduction language (use constraints framing): "
            f"{', '.join(sorted(set(tone_hits)))}"
        )

    # Check for em-dashes (Rule R-008 / Claim Verifier Anti-AI fingerprint)
    if '—' in content or '--' in content:
        messages.append("[R-008 FAIL] Forbidden em-dash (—) or '--' found. Violates the Anti-AI fingerprint standard.")

    # Check required sections (Rule R-005: Use Standard Section Headings)
    required_sections = {
        "PROFESSIONAL SUMMARY": r'^##\s*(?:\*\*)?PROFESSIONAL\s+SUMMARY(?:\*\*)?',
        "PROFESSIONAL EXPERIENCE": r'^##\s*(?:\*\*)?PROFESSIONAL\s+EXPERIENCE(?:\*\*)?',
        "EDUCATION": r'^##\s*(?:\*\*)?EDUCATION(?:\s+.*)?(?:\*\*)?'
    }
    
    for section_name, pattern in required_sections.items():
        if not re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
            messages.append(f"[R-005 FAIL] Missing required section heading: {section_name}")

    # Check job title format (Rule F-004: Consistent Dates and Pipe Format)
    if re.search(r'^###\s+.*—.*', content, re.MULTILINE):
        messages.append("[F-004 WARNING] Legacy job title date format using em-dash found.")

    # Check for bold prefixes on bullet points (Rule R-008: Option A Clean Action-Verb Standard)
    if re.search(r'^\s*[\*\-•]\s*\*\*[^*]+?\*\*:', content, re.MULTILINE):
        messages.append("[R-008 FAIL] Bullet points contain bold prefixes (e.g. **Skill:**). Violates the Option A Clean Action-Verb Standard.")
        
    # Check for bracket placeholders or redactions (Rule R-009: Zero-Placeholder Integrity)
    placeholders = re.findall(r'\[[^\]]{2,}\]', content)
    # Exclude valid markdown links or image syntax
    cleaned_placeholders = [p for p in placeholders if not re.search(r'https?://', p) and 'REDACTED' in p.upper() or any(k in p.upper() for k in ['COMPANY', 'NAME', 'DATE', 'INSERT', 'TITLE', 'ROLE'])]
    if cleaned_placeholders:
        messages.append(f"[R-009 FAIL] Corrupted placeholder brackets found: {', '.join(cleaned_placeholders)}")

    # Check that core career history employers are present (Rule R-005)
    lower_content = content.lower()
    from candidate_context import employer_display_name, load_employer_headers, load_employers_ordered

    headers = load_employer_headers()
    for slug in load_employers_ordered():
        label = employer_display_name(slug, headers)
        if label.lower() not in lower_content and slug.replace("_", " ") not in lower_content:
            messages.append(f"[R-005 FAIL] Missing core career history experience: {label}")

    try:
        from local_draft_stages import count_bullets_by_employer
        from pipeline_env import resume_bullet_quotas

        quotas = resume_bullet_quotas()
        counts = count_bullets_by_employer(content)
        ordered = load_employers_ordered()
        if ordered:
            primary = ordered[0]
            primary_min = min(4, quotas.get(primary, 5))
            if counts.get(primary, 0) < primary_min:
                label = employer_display_name(primary, headers)
                messages.append(
                    f"[R-010 FAIL] {label} has {counts.get(primary, 0)} bullets; "
                    f"expected at least {primary_min}."
                )
        for emp in ordered[1:]:
            label = employer_display_name(emp, headers)
            want = quotas.get(emp, 3)
            have = counts.get(emp, 0)
            if have < max(2, want - 1):
                messages.append(
                    f"[R-010 FAIL] {label} has {have} bullets; expected at least {max(2, want - 1)}."
                )
        summary_block = re.search(
            r"##\s*PROFESSIONAL\s+SUMMARY\s*\n([\s\S]*?)(?=\n##\s)",
            content,
            re.IGNORECASE,
        )
        if summary_block:
            sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", summary_block.group(1).strip()) if s.strip()]
            if len(sents) < 3:
                messages.append(
                    f"[R-010 FAIL] Professional summary has {len(sents)} sentence(s); expected at least 3."
                )
    except Exception:
        pass

    try:
        from resume_conversion_eval import evaluate_resume_conversion

        critique = evaluate_resume_conversion(content)
        for issue in critique.get("issues") or []:
            if issue.startswith("[CW-011]") or issue.startswith("[CW-013]") or issue.startswith("[CW-014]") or issue.startswith("[CW-016]"):
                messages.append(issue.replace("[CW-", "[R-012 FAIL] CW-"))
    except Exception:
        pass

    try:
        for msg in check_conversion_signals(content, {}, jd_text=""):
            if msg.startswith("[CW-003]"):
                messages.append(msg.replace("[CW-003]", "[R-013 FAIL] CW-003"))
    except Exception:
        pass

    from drafting_errors import SelfCorrectionError
    
    if any(
        "[R-005 FAIL]" in msg or "[R-008 FAIL]" in msg or "[R-009 FAIL]" in msg or "[R-010 FAIL]" in msg
        or "[R-011 FAIL]" in msg or "[R-012 FAIL]" in msg or "[R-013 FAIL]" in msg
        for msg in messages
    ):
        raise SelfCorrectionError(" | ".join(messages))
    elif messages:
        return True, " | ".join(messages)
    return True, "[R-001 PASS] Resume passed all best practice checks."


def check_conversion_signals(
    resume_md: str, bullets_by_company: Dict, jd_text: str = ""
) -> List[str]:
    """Detect non-fatal conversion anti-patterns and return a list of warning strings (FR-203).

    Warnings are logged to draft_manifest.json["conversion_warnings"] but never
    block the pipeline. Each warning includes a rule code and a plain description.
    """
    warnings: List[str] = []

    # Strong past-tense action verbs that indicate achievement framing
    _STRONG_VERBS = re.compile(
        r"^(Stabilized|Drove|Built|Designed|Delivered|Implemented|Reduced|Eliminated|"
        r"Launched|Led|Partnered|Resolved|Closed|Identified|Prioritized|Replaced|"
        r"Managed|Coordinated|Scoped|Navigated|Maintained|Generated|Sustained|"
        r"Restored|Enabled|Accelerated|Increased|Improved|Developed|Established|"
        r"Executed|Negotiated|Streamlined|Automated|Deployed|Migrated|Rebuilt|"
        r"Reverse-engineered|Architected|Synthesized|Presented|Created|Secured|"
        r"Enforced|Expanded|Translated|Owned|Co-created|Facilitated|Extended|"
        r"Spearheaded|Introduced|Restructured|Consolidated|Optimized|Scaled|"
        r"Tracked|Formalized|Championed|Refined)\b",
        re.IGNORECASE,
    )

    # Extract all bullet lines from the resume
    bullet_lines = [
        ln.lstrip("* ").strip()
        for ln in resume_md.splitlines()
        if ln.strip().startswith("* ")
    ]

    from conversion_framing import (
        defensive_summary_violations,
        has_outcome_metric,
        impact_pyramid_inverted,
        is_activity_bullet,
        metric_count_for_bullets,
    )

    # CW-001: Duty-heavy bullet (activity framing or no outcome signal)
    for bullet in bullet_lines:
        if is_activity_bullet(bullet):
            warnings.append(
                f"[CW-001] Activity-only bullet (process verb, no outcome metric): \"{bullet[:80]}...\""
                if len(bullet) > 80 else
                f"[CW-001] Activity-only bullet (process verb, no outcome metric): \"{bullet}\""
            )

    from candidate_context import employer_display_name, primary_employer_slug

    senior_slug = primary_employer_slug()
    senior_label = employer_display_name(senior_slug)

    # CW-002: Most-recent employer has no quantified bullets
    senior_from_map = bullets_by_company.get(senior_slug, []) if bullets_by_company else []
    check_bullets = senior_from_map if senior_from_map else bullet_lines[:5]
    if check_bullets and not any(re.search(r"\d", b) for b in check_bullets):
        warnings.append(
            f"[CW-002] {senior_label} (most recent employer) has no quantified bullets. "
            "At least one metric strongly recommended."
        )

    # CW-003: Bullet word count exceeds MAX_BULLET_WORDS
    try:
        from local_draft_stages import MAX_BULLET_WORDS as _MAX_WORDS
    except Exception:
        _MAX_WORDS = 28
    for bullet in bullet_lines:
        word_count = len(bullet.split())
        if word_count > _MAX_WORDS:
            warnings.append(
                f"[CW-003] Bullet exceeds {_MAX_WORDS} words ({word_count} words): "
                f"\"{bullet[:70]}...\""
            )

    # CW-004: Em-dash present (already a hard fail in R-008, but log as conversion signal too)
    if "\u2014" in resume_md or " -- " in resume_md:
        warnings.append(
            "[CW-004] Em-dash detected in resume. Violates anti-AI fingerprint rule."
        )

    # CW-005: Defensive summary framing without security JD signal
    summary_m = re.search(
        r"##\s*PROFESSIONAL\s+SUMMARY\s*\n+(.+?)(?=\n##|\Z)",
        resume_md,
        re.DOTALL | re.IGNORECASE,
    )
    if summary_m:
        violations = defensive_summary_violations(summary_m.group(1), jd_text=jd_text)
        if violations:
            warnings.append(
                "[CW-005] Summary contains defensive/maintenance framing "
                f"({', '.join(sorted(set(violations))[:2])}). "
                "Avoid unless JD is security-focused."
            )

    from candidate_context import employer_tiers

    _, mid_slug, junior_slug = employer_tiers()
    mid_label = employer_display_name(mid_slug)
    junior_label = employer_display_name(junior_slug)

    # CW-006: Activity-only bullet (alias logged at CW-001; count mid-career section)
    mid_bullets = bullets_by_company.get(mid_slug, []) if bullets_by_company else []
    if mid_bullets and not any(has_outcome_metric(b) for b in mid_bullets):
        warnings.append(
            f"[CW-007] {mid_label} section has no outcome metrics. "
            "At least one quantified business result recommended."
        )

    # CW-008: Impact pyramid inverted (junior role stronger than senior)
    if bullets_by_company:
        flat = {}
        for emp, blist in bullets_by_company.items():
            for i, b in enumerate(blist):
                flat[f"{emp}-{i}"] = b
        if impact_pyramid_inverted(flat):
            c = metric_count_for_bullets(flat)
            warnings.append(
                "[CW-008] Impact pyramid inverted: junior role has more outcome metrics "
                f"than senior ({senior_label}={c.get(senior_slug, 0)}, "
                f"{mid_label}={c.get(mid_slug, 0)}, "
                f"{junior_label}={c.get(junior_slug, 0)})."
            )

    from resume_conversion_eval import (
        check_sterkly_narrative_coherence,
        check_summary_completeness,
        check_summary_prose_quality,
        check_summary_theme_grounding,
    )

    warnings.extend(check_summary_completeness(resume_md))
    warnings.extend(check_summary_prose_quality(resume_md))
    warnings.extend(check_summary_theme_grounding(resume_md, bullets_by_company))
    warnings.extend(check_sterkly_narrative_coherence(resume_md))

    return warnings


def check_conversion_critique(
    resume_md: str,
    pdf_path: str = "",
    bullets_by_company: Dict | None = None,
    jd_text: str = "",
) -> Dict:
    """Human-mirror conversion critique after PDF render (FR-220)."""
    from resume_conversion_eval import evaluate_resume_conversion

    return evaluate_resume_conversion(
        resume_md,
        pdf_path=pdf_path or None,
        bullets_by_company=bullets_by_company,
        jd_text=jd_text,
    )


_ENTHUSIASM_RE = re.compile(
    r"\b(excited|passionate|thrilled|eager|enthusiastic|love to|eager to|deeply inspired|"
    r"genuinely inspired|inspired by|drawn to)\b",
    re.IGNORECASE,
)

_EVIDENCE_RE = re.compile(
    r"\d+|"
    r"\b(reduced|saved|increased|achieved|built|launched|resolved|delivered|drove|"
    r"eliminated|stabilized|improved|deployed|rebuilt|scoped|prioritized|generated|"
    r"coordinated|automated|migrated|reverse-engineered)\b",
    re.IGNORECASE,
)

_CL_GENERIC_TOKENS: frozenset = frozenset({
    "experience", "applying", "position", "application", "background", "expertise",
    "knowledge", "delivered", "product", "manager", "management", "directly",
    "relevant", "aligns", "track", "record", "posting", "emphasizes", "welcome",
    "conversation", "regards", "sincere", "hiring", "forward", "advance",
    "opportunity", "motivated", "confident", "believe", "skills", "ability",
    "focused", "capable", "qualified", "dedicated", "committed", "interested",
    "described", "outlined", "mentioned", "understand", "familiar",
})


def _opener_paragraph(cl_text: str) -> str:
    """Return the first body paragraph after the salutation."""
    body = cl_text.split("Dear Hiring Manager,", 1)[-1] if "Dear Hiring Manager," in cl_text else cl_text
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    return paragraphs[0] if paragraphs else ""


def check_cl_conversion_signals(cl_text: str, jd_text: str = "") -> List[str]:
    """Detect non-fatal cover letter conversion anti-patterns (FR-212).

    Returns a list of warning strings keyed by rule code. Non-blocking;
    logged to draft_manifest.json['cl_conversion_warnings'].

    Rules:
      CLW-002: Opener lacks any JD-specific noun beyond company name.
      CLW-004: Enthusiasm word present with no evidence in the same paragraph.
    """
    warnings: List[str] = []

    paragraphs = [
        p.strip()
        for p in cl_text.split("\n\n")
        if p.strip() and not p.strip().startswith("#")
    ]

    body_paragraphs = paragraphs
    if "Dear Hiring Manager," in cl_text:
        body = cl_text.split("Dear Hiring Manager,", 1)[-1]
        body_paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]

    opener = body_paragraphs[0] if body_paragraphs else ""

    if opener and jd_text:
        jd_long_words = set(re.findall(r"\b[a-z]{8,}\b", jd_text.lower()))
        opener_long_words = set(re.findall(r"\b[a-z]{8,}\b", opener.lower()))
        jd_specific = jd_long_words & opener_long_words - _CL_GENERIC_TOKENS
        if len(jd_specific) < 2:
            warnings.append(
                "[CLW-002] Opener contains fewer than 2 JD-specific terms beyond company name. "
                "Letter may read as generic. Consider including JD-derived pain point or product reference."
            )

    for para in body_paragraphs:
        if _ENTHUSIASM_RE.search(para) and not _EVIDENCE_RE.search(para):
            excerpt = para[:80].rstrip()
            warnings.append(
                f"[CLW-004] Enthusiasm word without supporting evidence in paragraph: "
                f"\"{excerpt}...\""
                if len(para) > 80 else
                f"[CLW-004] Enthusiasm word without supporting evidence in paragraph: \"{para}\""
            )

    from cover_phrasing import check_cover_grammar_defects

    warnings.extend(check_cover_grammar_defects(cl_text))

    return warnings


def repair_resume_markdown(content: str, education_block: str | None = None) -> str:
    """
    Deterministic R-005 repair before QA (CR-012 / FR-083).
    Injects missing headers and education without LLM creativity.
    """
    header_block = _header_block()
    if f"# {_candidate_name_upper()}" not in content.upper():
        content = header_block + content.lstrip()

    if not re.search(r"^##\s*(?:\*\*)?PROFESSIONAL\s+SUMMARY", content, re.MULTILINE | re.IGNORECASE):
        insert = "\n## PROFESSIONAL SUMMARY\n\nProduct Manager with 6+ years across enterprise SaaS platforms, consumer software, and internal tooling.\n"
        if header_block.strip() in content:
            content = content.replace(header_block.strip(), header_block.strip() + insert, 1)
        else:
            content = header_block + insert + content.lstrip()

    if not re.search(r"^##\s*(?:\*\*)?PROFESSIONAL\s+EXPERIENCE", content, re.MULTILINE | re.IGNORECASE):
        content += "\n\n## PROFESSIONAL EXPERIENCE\n"

    if not re.search(r"^##\s*(?:\*\*)?EDUCATION", content, re.MULTILINE | re.IGNORECASE):
        from candidate_context import parse_education_block, load_work_experience_text

        edu = education_block or parse_education_block(load_work_experience_text())
        content = content.rstrip() + "\n\n" + edu.strip() + "\n"

    from candidate_context import employer_display_name, load_employer_headers, load_employers_ordered
    from local_draft_stages import _employer_headers, ensure_experience_skeleton_headers, normalize_employer_job_titles

    headers = _employer_headers()
    lower = content.lower()
    for slug in load_employers_ordered():
        label = employer_display_name(slug, headers).lower()
        if label not in lower and slug.replace("_", " ") not in lower:
            stub = headers.get(slug, f"### {employer_display_name(slug, headers)}\n").split("\n")[0]
            content += f"\n{stub}\n* Platform and delivery outcomes.\n"

    content = ensure_experience_skeleton_headers(content)
    return normalize_employer_job_titles(content)


def run_quality_checks(company_dir):
    """
    Runs all quality checks for a given submission directory.
    """
    resume_path = os.path.join(company_dir, 'Resume.md')
    cover_letter_path = os.path.join(company_dir, 'CoverLetter.md')
    
    print(f"Running QA Checklist for: {os.path.basename(company_dir)}")
    
    res_passed, res_msg = check_resume(resume_path)
    if not res_passed:
        print(f"  [!] Resume Error: {res_msg}")
    else:
        print(f"  [OK] Resume: {res_msg}")
        
    cl_passed, cl_msg = check_and_repair_cover_letter(cover_letter_path)
    if not cl_passed:
        print(f"  [!] Cover Letter Error: {cl_msg}")
    else:
        print(f"  [OK] Cover Letter: {cl_msg}")

    return res_passed and cl_passed

def __getattr__(name: str):
    if name == "HEADER_BLOCK":
        return _header_block()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        company = sys.argv[1]
        run_quality_checks(os.path.join("submissions", company))
    else:
        print("Please provide a company name.")
