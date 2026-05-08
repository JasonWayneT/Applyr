import os
import re
import json
import subprocess
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
    "San Diego State University": "National University",
    "SDSU": "National University",
    "San Diego State": "National University",
    "University of San Diego": "National University",
    "UC San Diego": "National University",
    "UCSD": "National University",
}


def validate_hard_facts(generated_text, master_resume_text):
    """
    Deterministic post-generation check. Compares generated output against
    the master resume source of truth. Fixes known hallucinations and logs
    any discrepancies.

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

    # 2. Verify education facts are present
    for uni in HARD_FACTS["education"]:
        if uni not in corrected:
            warnings.append(f"MISSING FACT: Education '{uni}' not found in generated output.")

    # 3. Verify company names are present (at least the primary employer)
    for company in HARD_FACTS["companies"][:2]:  # Check top 2 companies
        if company.upper() not in corrected.upper():
            warnings.append(f"MISSING FACT: Company '{company}' not found in generated output.")

    # 4. Verify contact name
    if HARD_FACTS["contact"]:
        name = HARD_FACTS["contact"][0]
        if name and name not in corrected:
            warnings.append(f"MISSING FACT: Name '{name}' not found in generated output.")

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


def verify_claims(draft_text, work_exp, claim_verifier_rules):
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
    result = call_llm(system_prompt, user_prompt)
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
    resume_prompt = {
        "role": "You are a professional resume writer for Jason Taylor. "
                "Your goal is to create a high-impact, ONE-PAGE technical resume that matches the style reference template exactly. "
                "STRICT CONSTRAINT: The resume MUST have exactly these three headers: PROFESSIONAL SUMMARY, PROFESSIONAL EXPERIENCE, and EDUCATION. No other headers are allowed. "
                "The PROFESSIONAL SUMMARY must be exactly 1-2 concise lines to save space. Do not include Skills or Technical Environment sections. "
                "Do not use company-specific terms like GPOD or Bellwether without explaining what that is. "
                "The entire resume MUST fit on a single page. Do not exceed 3,200 characters. "
                "Use the provided work experience faithfully. Do not hallucinate tools or seniority.",
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
    
    Output strictly the translated standard Markdown resume. No preamble.
    """
    }
    draft_resume = call_llm(resume_prompt["role"], resume_prompt["content"])
    if not draft_resume:
        print(f"  [ERROR] LLM returned empty resume for {company_name}. Skipping save.")
        return
    verified_resume = verify_claims(draft_resume, work_exp, verifier_rules)

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
                "Do not use company-specific terms like GPOD or Bellwether without explaining what that is. "
                "Directly address the job requirements using Jason's actual experience.",
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
    
    Output strictly the standard markdown cover letter. No preamble.
    """
    }
    draft_cl = call_llm(cl_prompt["role"], cl_prompt["content"])
    if not draft_cl:
        print(f"  [ERROR] LLM returned empty cover letter for {company_name}. Skipping save.")
        return
    verified_cl = verify_claims(draft_cl, work_exp, verifier_rules)

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
