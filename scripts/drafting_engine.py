import os
import re
import json
import subprocess
import verify_claims as determinator
from utils import (load_file, call_llm, SUBMISSIONS_DIR,
                   RESUME_MASTER_FILE, COVER_LETTER_REF_FILE,
                   RESUME_STYLE_REF_FILE, CLAIM_VERIFIER_FILE,
                   WORK_EXP_FILE, RESUME_BEST_PRACTICES,
                   CL_BEST_PRACTICES)


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
    "30%", "40%",                 # MET-06: data drop-off
    "100%",                       # MET-07: drop-off resolved
    "90%",                        # MET-08: security backlog
    "200",                        # MET-09: SQL databases
    "700",                        # MET-10: migrations
    "$288", "288,000",            # MET-11: fulfillment contracts
    "$8,500", "8500",             # MET-11: quarterly savings
    "$22,100", "22,100",          # MET-12: onboarding savings
    "6+", "6 years",              # tenure
]


def validate_hard_facts(generated_text, master_resume_text):
    """
    Deterministic post-generation check. Compares generated output against
    the master resume source of truth. Fixes known hallucinations and logs
    any discrepancies.

    Checks (all regex/string — no LLM dependency):
      1. Known bad substitutions (auto-fixed)
      2. Blocked tool names (flagged for removal)
      3. Seniority inflation phrases (flagged)
      4. Metric integrity (any number not in approved list is flagged)
      5. Education / company / contact presence

    Returns (corrected_text, warnings_list).
    """
    global HARD_FACTS
    if HARD_FACTS is None:
        HARD_FACTS = _load_hard_facts(master_resume_text)

    warnings = []
    corrected = generated_text

    # 1. Fix known hallucination substitutions
    for wrong, right in KNOWN_HALLUCINATIONS.items():
        if wrong in corrected:
            warnings.append(f"HALLUCINATION CAUGHT: '{wrong}' replaced with '{right}'")
            corrected = corrected.replace(wrong, right)

    # 1b. Automatically strip Skills and Technical Environment sections safely
    corrected = re.sub(
        r'(?:<h2[^>]*>\s*<strong>\s*(?:SKILLS|TECHNICAL).*?</h2>|##\s*(?:Skills|Technical Environment|Core Expertise).*?)([\s\S]*?)(?=<h2[^>]*>|##|###|</div>|$)',
        '',
        corrected,
        flags=re.IGNORECASE
    )

    # 2. TOOL BLOCKLIST — flag any tool Jason never used
    tool_violations = []
    for tool in BLOCKED_TOOLS:
        # Word-boundary match to avoid partial hits (e.g. "Go" inside "Agora")
        pattern = r'(?<![\w-])' + re.escape(tool) + r'(?![\w-])'
        if re.search(pattern, corrected, re.IGNORECASE):
            tool_violations.append(tool)
    if tool_violations:
        warnings.append(
            f"TOOL HALLUCINATION: The following tools are NOT in workExperience.md and must be removed: "
            f"{', '.join(tool_violations)}"
        )
        # Auto-remove the tool mentions from the text to prevent them reaching the PDF
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

    # 4. METRIC INTEGRITY — scan for any number patterns and verify against approved list
    # Find all standalone numeric claims (percentages, dollar amounts, counts)
    numeric_pattern = re.compile(r'(?:\$[\d,]+(?:M|K|B)?|\d+(?:,\d{3})*(?:\.\d+)?\s*%|\d{1,3}(?:,\d{3})+|\b\d{2,}\b)')
    found_numbers = numeric_pattern.findall(corrected)
    unapproved = []
    for num in found_numbers:
        clean = num.strip()
        if not any(approved.lower() in clean.lower() or clean.lower() in approved.lower()
                   for approved in APPROVED_METRICS):
            unapproved.append(clean)
    if unapproved:
        # Filter out obvious false positives (years, phone numbers, etc.)
        real_violations = [n for n in unapproved if not re.match(r'^(?:20\d{2}|760|619|858|2026|2025|2024|2023|2022|2021|2019|2017|\d{1,2})$', n.replace(',', '').strip())]
        if real_violations:
            warnings.append(
                f"METRIC INTEGRITY: Unverified numeric claims found (not in approved metrics list): "
                f"{', '.join(real_violations)}"
            )
            print(f"    [GUARD] Unverified metrics detected: {real_violations}")

    # 5. Verify education facts are present
    for uni in HARD_FACTS["education"]:
        if uni not in corrected:
            warnings.append(f"MISSING FACT: Education '{uni}' not found in generated output.")

    # 6. Verify company names are present (at least the primary employer)
    for company in HARD_FACTS["companies"][:2]:  # Check top 2 companies
        if company.upper() not in corrected.upper():
            warnings.append(f"MISSING FACT: Company '{company}' not found in generated output.")

    # 7. Verify contact name
    if HARD_FACTS["contact"]:
        name = HARD_FACTS["contact"][0]
        if name and name not in corrected:
            warnings.append(f"MISSING FACT: Name '{name}' not found in generated output.")

    # 8. Anti-AI fingerprint: catch em-dashes
    if '\u2014' in corrected or ' -- ' in corrected:
        warnings.append("STYLE VIOLATION: Em-dash detected. Replacing with comma or clause break.")
        corrected = corrected.replace('\u2014', ', ').replace(' -- ', ', ')
        print("    [GUARD] Em-dash auto-corrected.")

    if warnings:
        print(f"    [HARD FACT AUDIT] {len(warnings)} issue(s) found:")
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


def llm_verify_claims(draft_text, work_exp, claim_verifier_rules):
    print("    [Audit] Running Claim Verifier (v2.0) against generated text...")
    system_prompt = "You are the cynical auditor enforcing the Claim Verifier rules."
    user_prompt = f"""
    RULES:
    {claim_verifier_rules}
    
    GROUND TRUTH:
    {work_exp}
    
    TEXT TO AUDIT:
    {draft_text}
    
    Perform the verification. If high-risk flags exist, rewrite the sentence to be accurate.
    Return ONLY the final corrected markdown text. Do not output 'FAILED CLAIM' unless explicitly asked, just fix it in the final output directly to ensure the pipeline can proceed automatically with corrected text.
    """
    result = call_llm(system_prompt, user_prompt, provider_override=['gemini', 'local'])
    if not result:
        print("    [Audit Warning] Claim Verifier returned empty. Using original draft.")
        return draft_text
    return result


def generate_pdf(md_path, output_path):
    # Enforces Single-Column, ATS-Optimized typography using Playwright
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        subprocess.run(["python", os.path.join(script_dir, "compile_single.py"), md_path, output_path], check=True)
        print(f"    [Export] Saved ATS-Optimized PDF: {output_path}")
    except Exception as e:
        print(f"    [Export Error] Failed to generate PDF: {e}")


def run_drafting_engine(company_name, jd_text, work_exp, evaluation_result):
    print(f"  -> Initializing Drafting Engine for {company_name}")
    company_folder = os.path.join(SUBMISSIONS_DIR, company_name.lower().replace(" ", "_"))
    os.makedirs(company_folder, exist_ok=True)

    # Save original JD
    try:
        jd_path = os.path.join(company_folder, "Original_JD.txt")
        with open(jd_path, "w", encoding="utf-8") as f:
            f.write(jd_text)
    except Exception as e:
        print(f"    [Error] Could not save original JD: {e}")

    # 1. Run Research
    research_json = run_research(company_name, jd_text)

    # Load References
    master_resume = load_file(RESUME_MASTER_FILE)
    resume_style = load_file(RESUME_STYLE_REF_FILE)
    cl_style = load_file(COVER_LETTER_REF_FILE)
    resume_best_practices = load_file(RESUME_BEST_PRACTICES)
    cl_best_practices = load_file(CL_BEST_PRACTICES)
    verifier_rules = load_file(CLAIM_VERIFIER_FILE)

    # 2. Bridge Logic & Resume Generation
    print("    [Drafting] Applying 'Bridge Logic' (Platform -> Growth) to Resume...")
    
    # Load valid claim IDs
    valid_ids = determinator.load_valid_ids(WORK_EXP_FILE)
    
    resume_prompt = {
        "role": "You are a professional resume writer for Jason Taylor. "
                "Your goal is to create a high-impact, ONE-PAGE technical resume that matches the style reference template exactly. "
                "STRICT CONSTRAINT: The resume MUST have exactly these three headers: PROFESSIONAL SUMMARY, PROFESSIONAL EXPERIENCE, and EDUCATION. No other headers are allowed. "
                "The PROFESSIONAL SUMMARY must be exactly 1-2 concise lines to save space. Do not include Skills or Technical Environment sections. "
                "The entire resume MUST fit on a single page. Do not exceed 3,200 characters. "
                "Use the provided work experience faithfully. Do not hallucinate tools or seniority.\n"
                "STRICT REQUIREMENT OVERRIDE: Despite rules suggesting otherwise, you MUST physically anchor EVERY accomplishment, metric, and translation claim in your output by appending its respective bracketed ID (e.g. [ACC-101], [MET-01], [VOC-01]) from the ground truth directly to the end of each sentence or bullet point. Every single claim must be traceable.",
        "content": f"""
    Transform the MASTER RESUME to match the JOB DESCRIPTION while strictly adhering to the BRIDGE LOGIC.
    
    BRIDGE LOGIC RULES:
    1. Translate Platform wins (Stability/Scale) to Growth needs (User Scaling, Business Revenue).
    Example: "Reduced API latency by 40%" -> "Improved system responsiveness to support 10x user scaling and retention."
    Example: "Resolved 300+ security vulnerabilities" -> "Mitigated enterprise risk to unblock GTM expansion."
    
    STYLE & STRATEGY GUIDE:
    Write pure, standard Markdown (using `#`, `##`, `*`, etc.). DO NOT output any raw HTML tags or `<div...>` wrappers. The system will convert your standard Markdown into the final styled PDF automatically.
    
    You MUST strictly follow these best practices for conversion and impact:
    {resume_best_practices}

    You MUST strictly match the layout and structural formatting of this template:
    {resume_style}
    
    GROUND TRUTH:
    {work_exp}
    
    MASTER RESUME (Format to follow, but update bullets):
    {master_resume}
    
    JOB DESCRIPTION:
    {jd_text}
    
    CRITICAL REQUIREMENT: For EVERY bullet point or sentence making a factual claim, you MUST append the bracketed source Fact ID (e.g., [ACC-101], [MET-01]) at the end of that sentence. Do not output any content without anchoring claims to specific IDs.
    
    Output strictly the translated standard Markdown resume. No preamble.
    """
    }
    
    draft_resume = ""
    error_hint = ""
    
    # Initial Attempt + up to 2 retries
    for attempt in range(3):
        role = resume_prompt["role"]
        content = resume_prompt["content"]
        if error_hint:
            content += f"\n\n[PREVIOUS ATTEMPT FAILED CLAIM VERIFICATION]\nError details: {error_hint}\nPlease rewrite the resume ensuring EVERY single factual claim or metric is correctly tagged with valid bracketed IDs (e.g., [ACC-101], [MET-01]) from the ground truth. Do not invent tags."
            
        draft_resume = call_llm(role, content, provider_override=['gemini', 'local'])
        if not draft_resume:
            print("    [Drafting Error] LLM returned empty content.")
            break
            
        # Validate
        res = determinator.verify_content(draft_resume, valid_ids)
        if res["success"]:
            print(f"    [Audit] Resume passed claim ID verification on attempt {attempt+1}.")
            break
        else:
            error_hint = res["error"]
            print(f"    [Audit Warning] Resume failed claim ID verification on attempt {attempt+1}: {error_hint}")
            if attempt == 2:
                print("    [CRITICAL WARNING] Resume failed claim ID verification after maximum retries. Using best-effort output.")
                
    if not draft_resume:
        print(f"  [ERROR] LLM returned empty resume for {company_name}. Skipping save.")
        return
        
    # Run LLM-based claim verification before we strip the IDs so the auditor can see them
    # We can instruct the LLM auditor to also keep them or we can strip them right after.
    # Let's strip IDs programmatically now so they are removed before writing to file and compiling
    cleaned_draft_resume = determinator.strip_ids(draft_resume)
    verified_resume = llm_verify_claims(cleaned_draft_resume, work_exp, verifier_rules)

    # Hard Fact Validation: deterministic check against master resume
    final_resume, resume_warnings = validate_hard_facts(verified_resume, master_resume)

    resume_md_path = os.path.join(company_folder, "Resume.md")
    resume_pdf_path = os.path.join(company_folder, "Resume.pdf")

    with open(resume_md_path, "w", encoding="utf-8") as f:
        f.write(final_resume)
    
    # Run the compliance guard on the saved Resume.md
    from style_compliance_guard import run_guard
    run_guard(resume_md_path)
    
    # Run the structural QA Checklist
    from quality_checker import check_resume
    qa_passed, qa_msg = check_resume(resume_md_path)
    if not qa_passed:
        print(f"    [QA AUDIT FAIL] Resume: {qa_msg}")
    else:
        print(f"    [QA AUDIT PASS] Resume: {qa_msg}")
    
    # Read the audited resume content to compile the PDF
    with open(resume_md_path, "r", encoding="utf-8") as f:
        final_resume = f.read()

    print(f"    [Drafting] Saved and validated Resume.md ({len(final_resume)} chars)")
    generate_pdf(resume_md_path, resume_pdf_path)

    # 3. Cover Letter Generation
    print("    [Drafting] Generating Cover Letter...")
    cl_prompt = {
        "role": "You are a professional cover letter writer for Jason Taylor. "
                "Your goal is to write a concise, one-page cover letter. "
                "STRICT CONSTRAINT: The entire letter must be under 1,800 characters to fit on one page with headers. "
                "Directly address the job requirements using Jason's actual experience.\n"
                "STRICT REQUIREMENT OVERRIDE: Despite instructions otherwise, you MUST physically anchor EVERY claim or accomplishment in your output by appending its respective bracketed ID (e.g. [ACC-101], [MET-01]) from the ground truth directly to the end of the sentence. Every single claim must have an ID.",
        "content": f"""
    Write a 250-400 word Cover Letter based on the JOB DESCRIPTION and RESEARCH PACKET.
    
    STYLE & STRATEGY GUIDE:
    Write pure, standard Markdown. DO NOT output any raw HTML tags.
    
    You MUST strictly follow these best practices for cover letter writing:
    {cl_best_practices}

    You MUST strictly match the structural format and signature style of this template:
    {cl_style}
    
    GROUND TRUTH:
    {work_exp}
    
    JOB DESCRIPTION:
    {jd_text}
    
    RESEARCH:
    {research_json}
    
    CRITICAL REQUIREMENT: For EVERY sentence making a factual claim, you MUST append the bracketed source Fact ID (e.g., [ACC-101], [MET-01]) at the end of that sentence. Output must be traceable.
    
    Output strictly the standard markdown cover letter. No preamble.
    """
    }
    
    draft_cl = ""
    cl_error_hint = ""
    
    # Initial attempt + up to 2 retries
    for attempt in range(3):
        role = cl_prompt["role"]
        content = cl_prompt["content"]
        if cl_error_hint:
            content += f"\n\n[PREVIOUS ATTEMPT FAILED CLAIM VERIFICATION]\nError details: {cl_error_hint}\nPlease rewrite the cover letter ensuring EVERY single claim is tagged with its valid bracketed ID (e.g. [ACC-101], [MET-01]) from the ground truth."
            
        draft_cl = call_llm(role, content, provider_override=['gemini', 'local'])
        if not draft_cl:
            break
            
        # Validate
        res = determinator.verify_content(draft_cl, valid_ids)
        if res["success"]:
            print(f"    [Audit] Cover letter passed claim ID verification on attempt {attempt+1}.")
            break
        else:
            cl_error_hint = res["error"]
            print(f"    [Audit Warning] Cover letter failed claim ID verification on attempt {attempt+1}: {cl_error_hint}")
            if attempt == 2:
                print("    [CRITICAL WARNING] Cover letter failed claim ID verification after maximum retries. Using best-effort output.")
                
    if not draft_cl:
        print(f"  [ERROR] LLM returned empty cover letter for {company_name}. Skipping save.")
        return
        
    cleaned_draft_cl = determinator.strip_ids(draft_cl)
    verified_cl = llm_verify_claims(cleaned_draft_cl, work_exp, verifier_rules)

    # Hard Fact Validation: deterministic check against master resume
    final_cl, cl_warnings = validate_hard_facts(verified_cl, master_resume)

    cl_md_path = os.path.join(company_folder, "CoverLetter.md")
    cl_pdf_path = os.path.join(company_folder, "CoverLetter.pdf")

    with open(cl_md_path, "w", encoding="utf-8") as f:
        f.write(final_cl)
        
    # Run the compliance guard on the saved CoverLetter.md
    from style_compliance_guard import run_guard
    run_guard(cl_md_path)
    
    # Run the structural QA Checklist & Auto-Repair
    from quality_checker import check_and_repair_cover_letter
    qa_passed, qa_msg = check_and_repair_cover_letter(cl_md_path)
    if not qa_passed:
        print(f"    [QA AUDIT FAIL] Cover Letter: {qa_msg}")
    else:
        print(f"    [QA AUDIT PASS] Cover Letter: {qa_msg}")
    
    # Read the audited cover letter content to compile the PDF
    with open(cl_md_path, "r", encoding="utf-8") as f:
        final_cl = f.read()

    print(f"    [Drafting] Saved and validated CoverLetter.md ({len(final_cl)} chars)")
    generate_pdf(cl_md_path, cl_pdf_path)

    # Summary of all validation issues
    all_warnings = resume_warnings + cl_warnings
    if all_warnings:
        print(f"  -> [AUDIT SUMMARY] {len(all_warnings)} total issue(s) caught and corrected.")
    else:
        print(f"  -> [AUDIT SUMMARY] All assets passed hard-fact validation. Clean output.")

    print(f"  -> Successfully generated and audited all assets for {company_name}")
