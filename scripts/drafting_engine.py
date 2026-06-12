import os
import re
import subprocess
import verify_claims as determinator
from utils import (
    contact_placeholder_map,
    format_contact_header_block,
    load_file,
    SUBMISSIONS_DIR,
    RESUME_MASTER_FILE,
    WORK_EXP_FILE,
)
from company_slug import company_submission_dir
# --- Hard Fact Validation (Deterministic Post-Generation Guard) ---
# Extracts known ground-truth facts from the master resume and verifies
# they were not hallucinated or substituted in the generated output.

# These are literal strings that MUST appear in any generated resume.
# If they are missing, the output is flagged and corrected.
HARD_FACTS = None  # Loaded lazily from master resume


def _load_hard_facts(master_resume_text):
    """Extract deterministic facts from the master resume."""
    facts = {
        "education": [],
        "companies": [],
        "contact": [],
    }
    # Education: look for university names
    if "national university" in master_resume_text.lower():
        facts["education"].append("National University")

    # Company names from ## headers
    company_pattern = re.compile(r"^## \*\*(.+?)\*\*", re.MULTILINE)
    for match in company_pattern.finditer(master_resume_text):
        facts["companies"].append(match.group(1).strip())

    # Contact info (name, email)
    lines = master_resume_text.split("\n")
    if lines:
        facts["contact"].append(lines[0].replace("#", "").replace("*", "").strip())  # Name

    return facts


# Common hallucination substitutions the LLM tends to make
KNOWN_HALLUCINATIONS = {
    # Education substitutions
    "San Diego State University": "National University",
    "SDSU": "National University",
    "San Diego State": "National University",
    "University of San Diego": "National University",
    "UC San Diego": "National University",
    "UCSD": "National University",
    "California State University": "National University",
    "CSUSM": "National University",
    # Company name corrections
    "PR Newswire": "Cision",
    "Cision Ltd": "Cision",
    "Cision Inc": "Cision",
}

# Tools Jason has NEVER used — block any mention in generated output
# Source: workExperience.md — if it isn't there, it doesn't exist.
BLOCKED_TOOLS = [
    "Snowflake", "Tableau", "Looker", "dbt", "Airflow", "Spark", "Kafka",
    "Kubernetes", "Docker", "Terraform", "Helm", "Jenkins", "CircleCI",
    "FHIR", "HL7", "HIPAA", "SOC2", "SOC 2", "ISO 27001",
    "Databricks", "Redshift", "BigQuery", "Fivetran", "Segment",
    "Amplitude", "Mixpanel", "Pendo", "LaunchDarkly",
    "React", "Node.js", "GraphQL", "Rust", "Go",
    "TensorFlow", "PyTorch", "LangChain", "RAG", "LLM pipeline",
    "AWS", "Azure", "GCP", "Heroku",
]

# Seniority inflation phrases — flag if any appear in the resume
SENIORITY_INFLATION_PHRASES = [
    "Led a team of", "Led team of",
    "Managed a team", "Managed team",
    "Director of", "Vice President", " VP ", "Head of",
    "Hired and", "Hire and", "Supervised",
    "People management", "Direct reports",
    "P&L ownership", "Revenue owner", "Owned billing",
    "Shipped AI", "Shipped ML", "Trained model", "Deployed model",
    "Built ML", "Built AI", "AI pipeline", "ML pipeline",
]

from approved_metrics import APPROVED_METRICS, find_unapproved_metrics, metric_integrity_message


def validate_hard_facts(generated_text, master_resume_text, target_company=None, doc_type='resume'):
    """
    Deterministic post-generation check. Compares generated output against
    the master resume source of truth. Fixes known hallucinations and logs
    any discrepancies.

    Checks (all regex/string — no LLM dependency):
      0. Header normalization to required standard headings
      1. Known bad substitutions (auto-fixed)
      2. Blocked tool names (flagged for removal)
      3. Seniority inflation phrases (flagged)
      4. Metric integrity (any number not in approved list is flagged)
      5. Education / company / contact presence (resume only)
      6. Enhanced placeholder and bracket healing

    Args:
        doc_type: 'resume' or 'cover_letter' — gates checks that only apply to resumes.

    Returns (corrected_text, warnings_list).
    """
    global HARD_FACTS
    if HARD_FACTS is None:
        HARD_FACTS = _load_hard_facts(master_resume_text)

    warnings = []
    corrected = generated_text

    # 0. Header Normalization Guard (Option A Standard)
    header_mappings = [
        (r'^#{2,3}\s*(?:\*\*)?PROFESSIONAL\s+SUMMARY(?:\*\*)?', '## PROFESSIONAL SUMMARY'),
        (r'^#{2,3}\s*(?:\*\*)?SUMMARY(?:\*\*)?', '## PROFESSIONAL SUMMARY'),
        (r'^#{2,3}\s*(?:\*\*)?PROFESSIONAL\s+EXPERIENCE(?:\*\*)?', '## PROFESSIONAL EXPERIENCE'),
        (r'^#{2,3}\s*(?:\*\*)?EXPERIENCE(?:\*\*)?', '## PROFESSIONAL EXPERIENCE'),
        (r'^#{2,3}\s*(?:\*\*)?WORK\s+EXPERIENCE(?:\*\*)?', '## PROFESSIONAL EXPERIENCE'),
        (r'^#{2,3}\s*(?:\*\*)?EMPLOYMENT\s+HISTORY(?:\*\*)?', '## PROFESSIONAL EXPERIENCE'),
        (r'^#{2,3}\s*(?:\*\*)?EDUCATION(?:\s+.*)?(?:\*\*)?', '## EDUCATION'),
    ]

    if doc_type == 'cover_letter':
        header_mappings = [
            m for m in header_mappings
            if 'EDUCATION' not in m[1]
        ]
    
    header_fixed = False
    for pat, replacement in header_mappings:
        # Apply replacement line by line or multiline safely
        new_text = re.sub(pat, replacement, corrected, flags=re.MULTILINE | re.IGNORECASE)
        if new_text != corrected:
            corrected = new_text
            header_fixed = True
    
    if header_fixed:
         print("    [GUARD] Normalized layout section headers to standard uppercase format.")

    # 1. Fix known hallucination substitutions
    for wrong, right in KNOWN_HALLUCINATIONS.items():
        if wrong in corrected:
            warnings.append(f"HALLUCINATION CAUGHT: '{wrong}' replaced with '{right}'")
            corrected = corrected.replace(wrong, right)

    # 1b. Automatically strip Skills and Technical Environment sections safely (bulletproof variants)
    corrected = re.sub(
        r'(?:<h2[^>]*>\s*<strong>\s*(?:SKILLS|TECHNICAL).*?</h2>|##\s*(?:Skills|Technical Skills|Technical Environment|Core Expertise|Skills & Tools).*?)([\s\S]*?)(?=<h2[^>]*>|##|###|</div>|$)',
        '',
        corrected,
        flags=re.IGNORECASE
    )

    # 2. TOOL BLOCKLIST — flag any tool Jason never used
    tool_violations = []
    for tool in BLOCKED_TOOLS:
        pattern = r'(?<![\w-])' + re.escape(tool) + r'(?![\w-])'
        if re.search(pattern, corrected, re.IGNORECASE):
            tool_violations.append(tool)
    if tool_violations:
        warnings.append(
            f"TOOL HALLUCINATION: The following tools are NOT in workExperience.md and must be removed: "
            f"{', '.join(tool_violations)}"
        )
        for tool in tool_violations:
            pattern = r'(?<![\w-])' + re.escape(tool) + r'(?![\w-])'
            corrected = re.sub(pattern, '', corrected, flags=re.IGNORECASE)
        corrected = re.sub(r'\[REDACTED\]\s*', '', corrected, flags=re.IGNORECASE)
        corrected = re.sub(r'\|\s*\|', '|', corrected)
        corrected = re.sub(r'[ \t]{2,}', ' ', corrected)
        print(f"    [GUARD] Auto-redacted {len(tool_violations)} blocked tool(s): {tool_violations}")

    # 3. SENIORITY INFLATION — flag leadership/management claims
    seniority_violations = []
    for phrase in SENIORITY_INFLATION_PHRASES:
        if phrase.lower() in corrected.lower():
            seniority_violations.append(phrase)
    if seniority_violations:
        warnings.append(
            f"SENIORITY INFLATION: The following phrases imply leadership/management Jason did not hold: "
            f"{', '.join(seniority_violations)}"
        )
        print(f"    [GUARD] Seniority inflation detected: {seniority_violations}")

    from tone_guard import sanitize_submission_tone, tone_violations

    tone_hits = tone_violations(corrected)
    if tone_hits:
        warnings.append(
            f"TONE (FR-096): Workforce-reduction language must use constraints framing: "
            f"{', '.join(sorted(set(tone_hits)))}"
        )
        print(f"    [GUARD] Blocked tone detected; rewriting to constraints language.")
    corrected = sanitize_submission_tone(corrected)

    from local_draft_stages import normalize_employer_job_titles

    before_titles = corrected
    corrected = normalize_employer_job_titles(corrected)
    if corrected != before_titles:
        print("    [GUARD] Normalized employer job titles (single role per company).")

    # 4. METRIC INTEGRITY — scan for any number patterns and verify against approved list
    unapproved = find_unapproved_metrics(corrected)
    if unapproved:
        warnings.append(metric_integrity_message(unapproved))
        print(f"    [GUARD] Unverified metrics detected: {unapproved}")

    # 5. Verify education facts are present & Auto-heal if missing (resume only)
    if doc_type == 'resume':
        missing_edu = False
        for uni in HARD_FACTS["education"]:
            if uni not in corrected:
                missing_edu = True
                warnings.append(f"MISSING FACT: Education '{uni}' not found in generated output. Triggering self-healing injection.")

        if missing_edu:
            corrected = re.sub(r'##\s*Education\s*(?:\n\s*)*', '', corrected, flags=re.IGNORECASE)
            corrected = re.sub(r'##\s*Certifications\s*(?:\n\s*)*', '', corrected, flags=re.IGNORECASE)
            corrected = re.sub(r'##\s*Education & Certifications\s*(?:\n\s*)*', '', corrected, flags=re.IGNORECASE)

            edu_cert_block = "\n\n## EDUCATION\n\n" \
                             "* **Bachelor of Business Administration, Major in Management** — National University, San Diego, California, 2019\n"
            corrected = corrected.rstrip() + edu_cert_block
            print("    [GUARD] Auto-injected verified Education block.")

        # 6. Verify company names are present (resume only)
        for company in HARD_FACTS["companies"][:2]:
            if company.upper() not in corrected.upper():
                warnings.append(f"MISSING FACT: Company '{company}' not found in generated output.")

    # 7. Auto-heal Contact & Template Info Placeholders (Hyper-Aggressive Local fallback sweeping)
    placeholders = contact_placeholder_map(target_company=target_company)
    if HARD_FACTS["education"]:
        uni = HARD_FACTS["education"][0]
        placeholders["[University Name]"] = uni
        placeholders["[University]"] = uni
        
    placeholder_triggered = False
    for ph, val in placeholders.items():
        # Case-insensitive safe sweep for common variations
        if ph.lower() in corrected.lower():
            # Perform literal replacement on matching keys
            pattern = re.compile(re.escape(ph), re.IGNORECASE)
            corrected = pattern.sub(val, corrected)
            placeholder_triggered = True
            
    if placeholder_triggered:
        print("    [GUARD] Resolved model template placeholders and bracket tags to actual ground truth.")

    # 7b. Verify contact name is at the very top
    if HARD_FACTS["contact"]:
        name = HARD_FACTS["contact"][0]
        if name and name.upper() not in corrected[:300].upper():
            warnings.append(f"MISSING FACT: Name '{name}' not found at top of resume. Repairing header.")
            header = format_contact_header_block()
            corrected = header + corrected.lstrip()
            print("    [GUARD] Prepend-repaired missing Name/Contact header.")

    # 8. Anti-AI fingerprint: catch em-dashes
    if '\u2014' in corrected or ' -- ' in corrected:
        warnings.append("STYLE VIOLATION: Em-dash detected. Replacing with comma or clause break.")
        corrected = corrected.replace('\u2014', ', ').replace(' -- ', ', ')
        print("    [GUARD] Em-dash auto-corrected.")

    if warnings:
        print(f"    [HARD FACT AUDIT] {len(warnings)} issue(s) found & actively defended:")
        for w in warnings:
            print(f"      - {w}")
    else:
        print("    [HARD FACT AUDIT] All ground-truth facts verified. Clean output.")

    return corrected, warnings


def run_research(company_name, jd_text):
    from pipeline_env import research_mode

    folder = company_submission_dir(SUBMISSIONS_DIR, company_name)
    packet_path = os.path.join(folder, "Research_Packet.json")
    if os.path.exists(packet_path):
        print(f"    [Research] Found cached intelligence for {company_name}. Using local packet.")
        return load_file(packet_path)

    mode = research_mode()
    if mode == "skip":
        print(f"    [Research] Skipped (RESEARCH_MODE=skip). Template cheat sheet only.")
        return "No research data available."

    print(f"    [Research] Fetching intelligence ({mode}) for {company_name}...")
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        env = os.environ.copy()
        env["RESEARCH_MODE"] = mode
        subprocess.run(
            ["python", os.path.join(script_dir, "research-engine.py"), company_name, "Product Manager"],
            check=False,
            env=env,
        )
        if os.path.exists(packet_path):
            return load_file(packet_path)
    except Exception as e:
        print(f"    [Research Error] {e}")
    return "No research data available."


def get_pdf_page_count(pdf_path: str) -> int:
    """Return the page count of a PDF file, or -1 on error."""
    try:
        import pypdf
        return len(pypdf.PdfReader(pdf_path).pages)
    except Exception:
        return -1


def generate_pdf(md_path, output_path):
    # Enforces Single-Column, ATS-Optimized typography using Playwright
    script_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.run(
        ["python", os.path.join(script_dir, "compile_single.py"), md_path, output_path],
        check=True,
    )
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
        raise RuntimeError(f"PDF export failed or empty: {output_path}")
    print(f"    [Export] Saved ATS-Optimized PDF: {output_path}")


def run_drafting_engine(company_name, jd_text, work_exp, evaluation_result, display_name=None):
    """Unified entry: draft compiler only. Implements FR-089, FR-103 (CR-014, CR-017)."""
    display = (display_name or company_name).strip()
    print(f"  -> Initializing Drafting Engine for {display}")
    company_folder = company_submission_dir(SUBMISSIONS_DIR, company_name)
    os.makedirs(company_folder, exist_ok=True)

    try:
        jd_path = os.path.join(company_folder, "Original_JD.txt")
        with open(jd_path, "w", encoding="utf-8") as f:
            f.write(jd_text)
    except Exception as e:
        print(f"    [Error] Could not save original JD: {e}")

    # Research for cheat sheet / interview prep only — not injected into resume/cover (CR-014)
    run_research(company_name, jd_text)

    from draft_compiler import run as run_compiler
    run_compiler(
        company_name,
        jd_text,
        work_exp,
        evaluation_result,
        company_folder,
        display_name=display,
    )
    print(f"  -> Successfully generated and audited all assets for {company_name}")

