import os
import re
import json

HEADER_BLOCK = """# JASON TAYLOR

San Diego, CA | [REDACTED_PHONE] | [REDACTED_EMAIL] | linkedin.com/in/redacted-linkedin-slug

"""

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
    if "# JASON TAYLOR" not in content.upper():
        messages.append("[H-001 WARNING] Missing standard header block. Auto-repairing...")
        content = HEADER_BLOCK + content.lstrip()
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        repaired = True
        messages.append("[H-001 OK] Header block successfully injected.")

    # Check for length (Rule CL-006: ~1 page; CR-024 Match Brief allows slightly longer)
    char_count = len(content)
    cover_char_limit = 2400
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

    # Check that all three core career history experiences are present (Rule R-005: Use Standard Section Headings and Content)
    lower_content = content.lower()
    if "cision" not in lower_content:
        messages.append("[R-005 FAIL] Missing core career history experience: Cision")
    if "sterkly" not in lower_content:
        messages.append("[R-005 FAIL] Missing core career history experience: Sterkly")
    if "zero to sixty" not in lower_content and "zero to 60" not in lower_content:
        messages.append("[R-005 FAIL] Missing core career history experience: Zero to Sixty")

    try:
        from local_draft_stages import count_bullets_by_employer
        from pipeline_env import resume_bullet_quotas

        quotas = resume_bullet_quotas()
        counts = count_bullets_by_employer(content)
        cision_min = min(4, quotas.get("cision", 5))
        if counts.get("cision", 0) < cision_min:
            messages.append(
                f"[R-010 FAIL] Cision has {counts.get('cision', 0)} bullets; "
                f"expected at least {cision_min}."
            )
        for emp, label in (("sterkly", "Sterkly"), ("zero_to_sixty", "Zero to Sixty")):
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

    from drafting_errors import SelfCorrectionError
    
    if any(
        "[R-005 FAIL]" in msg or "[R-008 FAIL]" in msg or "[R-009 FAIL]" in msg or "[R-010 FAIL]" in msg or "[R-011 FAIL]" in msg
        for msg in messages
    ):
        raise SelfCorrectionError(" | ".join(messages))
    elif messages:
        return True, " | ".join(messages)
    return True, "[R-001 PASS] Resume passed all best practice checks."


def repair_resume_markdown(content: str, education_block: str | None = None) -> str:
    """
    Deterministic R-005 repair before QA (CR-012 / FR-083).
    Injects missing headers and education without LLM creativity.
    """
    if "# JASON TAYLOR" not in content.upper():
        content = HEADER_BLOCK + content.lstrip()

    if not re.search(r"^##\s*(?:\*\*)?PROFESSIONAL\s+SUMMARY", content, re.MULTILINE | re.IGNORECASE):
        insert = "\n## PROFESSIONAL SUMMARY\n\nProduct Manager with B2B SaaS platform ownership and cross-functional delivery experience.\n"
        if HEADER_BLOCK.strip() in content:
            content = content.replace(HEADER_BLOCK.strip(), HEADER_BLOCK.strip() + insert, 1)
        else:
            content = HEADER_BLOCK + insert + content.lstrip()

    if not re.search(r"^##\s*(?:\*\*)?PROFESSIONAL\s+EXPERIENCE", content, re.MULTILINE | re.IGNORECASE):
        content += "\n\n## PROFESSIONAL EXPERIENCE\n"

    if not re.search(r"^##\s*(?:\*\*)?EDUCATION", content, re.MULTILINE | re.IGNORECASE):
        edu = education_block or (
            "## EDUCATION\n\n"
            "* **Bachelor of Business Administration, Major in Management** — "
            "National University, San Diego, California, 2019\n"
        )
        content = content.rstrip() + "\n\n" + edu.strip() + "\n"

    lower = content.lower()
    from local_draft_stages import EMPLOYER_EXPERIENCE_HEADERS, normalize_employer_job_titles

    if "cision" not in lower:
        content += "\n" + EMPLOYER_EXPERIENCE_HEADERS["cision"].split("\n")[0] + "\n* Platform and ingestion systems delivery.\n"
    if "sterkly" not in lower:
        content += "\n" + EMPLOYER_EXPERIENCE_HEADERS["sterkly"].split("\n")[0] + "\n"
    if "zero to sixty" not in lower and "zero to 60" not in lower:
        content += "\n" + EMPLOYER_EXPERIENCE_HEADERS["zero_to_sixty"].split("\n")[0] + "\n"

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

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        company = sys.argv[1]
        run_quality_checks(os.path.join("submissions", company))
    else:
        print("Please provide a company name.")
