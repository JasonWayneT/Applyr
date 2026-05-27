import os
import re
import subprocess
import verify_claims as determinator
from utils import load_file, SUBMISSIONS_DIR, RESUME_MASTER_FILE, WORK_EXP_FILE
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

# Approved verified metrics from workExperience.md — exact values only
# Any numeric claim in the output must match one of these to pass.
APPROVED_METRICS = [
    "$40", "40M", "40,000,000",  # MET-01: $40M ARR
    "3,500", "3500",              # MET-02: 3,500 active accounts
    "25,000", "25000",            # MET-03: 25,000 active users
    "7%",                         # MET-04: 7% churn
    "$1M", "$2M", "1,000,000", "2,000,000",  # MET-05: infra savings
    "40%",                 # MET-06: data drop-off
    "100%",                       # MET-07: drop-off resolved
    "90%",                        # MET-08: security backlog
    "200",                        # MET-09: SQL databases
    "700",                        # MET-10: migrations
    "$288", "288,000",            # MET-11: fulfillment contracts
    "$8,500", "8500",             # MET-11: quarterly savings
    "$22,100", "22,100",          # MET-12: onboarding savings
    "6+", "6 years",              # tenure
]


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
            corrected = re.sub(pattern, '[REDACTED]', corrected, flags=re.IGNORECASE)
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

    # 3b. MANDATORY TITLE CONSISTENCY GUARD — Enforce Cision is strictly "Product Manager"
    lines = corrected.split('\n')
    new_lines = []
    cision_healed = False
    for line in lines:
        if 'cision' in line.lower() and any(kw in line.lower() for kw in ['product owner', 'functional product manager']):
            ugly_titles = [
                "Product Owner / Functional Product Manager",
                "Product Owner / Platform Product Manager",
                "Product Owner (Functionally Product Manager)",
                "Product Owner (Functional Scope)",
                "Product Owner → Product Manager (Functional Scope)",
                "Product Owner -> Product Manager (Functional Scope)",
                "Product Owner / Product Manager",
                "Product Owner"
            ]
            for ugly in ugly_titles:
                pattern = re.compile(re.escape(ugly), re.IGNORECASE)
                if pattern.search(line):
                    line = pattern.sub("Product Manager", line)
                    cision_healed = True
            
            line = re.sub(r'Product Manager\s*/\s*Product Manager', 'Product Manager', line, flags=re.IGNORECASE)
            line = re.sub(r'Product Manager\s*/\s*Platform Product Manager', 'Product Manager', line, flags=re.IGNORECASE)
            
        new_lines.append(line)
    
    if cision_healed:
        corrected = '\n'.join(new_lines)
        print("    [GUARD] Enforced strict 'Product Manager' title consistency for Cision.")

    # 4. METRIC INTEGRITY — scan for any number patterns and verify against approved list
    numeric_pattern = re.compile(r'(?:\$[\d,]+(?:M|K|B)?|\d+(?:,\d{3})*(?:\.\d+)?\s*%|\d{1,3}(?:,\d{3})+|\b\d{2,}\b)')
    found_numbers = numeric_pattern.findall(corrected)
    unapproved = []
    for num in found_numbers:
        clean = num.strip()
        if not any(approved.lower() in clean.lower() or clean.lower() in approved.lower()
                   for approved in APPROVED_METRICS):
            unapproved.append(clean)
    if unapproved:
        real_violations = [n for n in unapproved if not re.match(r'^(?:20\d{2}|760|619|858|2026|2025|2024|2023|2022|2021|2019|2017|\d{1,2})$', n.replace(',', '').strip())]
        if real_violations:
            warnings.append(
                f"METRIC INTEGRITY: Unverified numeric claims found (not in approved metrics list): "
                f"{', '.join(real_violations)}"
            )
            print(f"    [GUARD] Unverified metrics detected: {real_violations}")

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
    placeholders = {
        "[Your Name]": "JASON TAYLOR",
        "*[Your Name]*": "JASON TAYLOR",
        "[Full Name]": "JASON TAYLOR",
        "[Your Phone Number]": "[REDACTED_PHONE]",
        "[Phone Number]": "[REDACTED_PHONE]",
        "[Your Email Address]": "[REDACTED_EMAIL]",
        "[Your Email]": "[REDACTED_EMAIL]",
        "[Email Address]": "[REDACTED_EMAIL]",
        "[Your LinkedIn Profile URL]": "linkedin.com/in/redacted-linkedin-slug",
        "[LinkedIn Profile URL]": "linkedin.com/in/redacted-linkedin-slug",
        "[LinkedIn URL]": "linkedin.com/in/redacted-linkedin-slug",
        "[LinkedIn]": "linkedin.com/in/redacted-linkedin-slug",
        "## [Your Name]": "# JASON TAYLOR",
        "[University Name]": "National University",
        "[University]": "National University",
        "[Hiring Manager Name]": "Hiring Team",
        "[Hiring Manager]": "Hiring Team",
        "[Dates]": "",  # Safe collapse for leftover template debris
        "*[Dates]*": ""
    }
    if target_company:
        placeholders["[Company Name]"] = target_company
        placeholders["*[Company Name]*"] = target_company
        placeholders["[Target Company]"] = target_company
        
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
            header = f"# JASON TAYLOR\n\nSan Diego, CA | [REDACTED_PHONE] | [REDACTED_EMAIL] | linkedin.com/in/redacted-linkedin-slug\n\n"
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
    folder = os.path.join(SUBMISSIONS_DIR, company_name.lower().replace(" ", "_"))
    packet_path = os.path.join(folder, "Research_Packet.json")
    if os.path.exists(packet_path):
        print(f"    [Research] Found cached intelligence for {company_name}. Using local packet.")
        return load_file(packet_path)

    print(f"    [Research] Pulling Perplexity intelligence for {company_name}...")
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.run(["python", os.path.join(script_dir, "research-engine.py"),
                        company_name, "Product Manager"], check=True)
        if os.path.exists(packet_path):
            return load_file(packet_path)
    except Exception as e:
        print(f"    [Research Error] {e}")
    return "No research data available."


def generate_pdf(md_path, output_path):
    # Enforces Single-Column, ATS-Optimized typography using Playwright
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        subprocess.run(["python", os.path.join(script_dir, "compile_single.py"), md_path, output_path], check=True)
        print(f"    [Export] Saved ATS-Optimized PDF: {output_path}")
    except Exception as e:
        print(f"    [Export Error] Failed to generate PDF: {e}")


def run_drafting_engine(company_name, jd_text, work_exp, evaluation_result, display_name=None):
    """Unified entry: draft compiler only. Implements FR-089, FR-103 (CR-014, CR-017)."""
    display = (display_name or company_name).strip()
    print(f"  -> Initializing Drafting Engine for {display}")
    company_folder = os.path.join(SUBMISSIONS_DIR, company_name.lower().replace(" ", "_"))
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
    run_compiler(company_name, jd_text, work_exp, evaluation_result, company_folder, display_name=display)
    print(f"  -> Successfully generated and audited all assets for {company_name}")

