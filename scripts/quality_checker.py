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

    # Check for length (Rule CL-006: Keep it under 1 page / 1,800 characters)
    char_count = len(content)
    if char_count > 1800:
        messages.append(f"[CL-006 WARNING] Cover letter length ({char_count} chars) exceeds the 1,800-char single-page threshold.")
        
    if repaired:
        return True, " | ".join(messages)
    elif any("[CL-008 FAIL]" in msg for msg in messages):
        return False, " | ".join(messages)
    elif messages:
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
        
    # Check that all three core career history experiences are present (Rule R-005: Use Standard Section Headings and Content)
    lower_content = content.lower()
    if "cision" not in lower_content:
        messages.append("[R-005 FAIL] Missing core career history experience: Cision")
    if "sterkly" not in lower_content:
        messages.append("[R-005 FAIL] Missing core career history experience: Sterkly")
    if "zero to sixty" not in lower_content and "zero to 60" not in lower_content and "account manager" not in lower_content:
        messages.append("[R-005 FAIL] Missing core career history experience: Zero to Sixty")

    if any("[R-005 FAIL]" in msg or "[R-008 FAIL]" in msg for msg in messages):
        return False, " | ".join(messages)
    elif messages:
        return True, " | ".join(messages)
    return True, "[R-001 PASS] Resume passed all best practice checks."

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
