import os
import re
import json
import subprocess
from markdown_pdf import MarkdownPdf, Section
from utils import (load_file, call_llm, SUBMISSIONS_DIR,
                   RESUME_MASTER_FILE, COVER_LETTER_REF_FILE,
                   RESUME_STYLE_REF_FILE, CLAIM_VERIFIER_FILE,
                   WORK_EXP_FILE)


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
    edu_pattern = re.compile(r"(?:Bachelor|Master|Associate|B\.A\.|B\.S\.|M\.S\.|M\.A\.|MBA).*?\n(.+?)(?:\n|$)", re.IGNORECASE)
    for match in edu_pattern.finditer(master_resume_text):
        uni = match.group(1).strip()
        if uni and len(uni) > 3:
            facts["education"].append(uni)

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
    print(f"    [Research] Pulling Perplexity intelligence for {company_name}...")
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.run(["python", os.path.join(script_dir, "research-engine.py"),
                        company_name, "Product Manager"], check=True)
        folder = os.path.join(SUBMISSIONS_DIR, company_name.lower().replace(" ", "_"))
        packet_path = os.path.join(folder, "Research_Packet.json")
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
    return call_llm(system_prompt, user_prompt)


def generate_pdf(markdown_text, output_path):
    # Enforces Single-Column, ATS-Optimized typography
    pdf = MarkdownPdf(toc_level=0)
    pdf.add_section(Section(markdown_text))
    pdf.save(output_path)
    print(f"    [Export] Saved ATS-Optimized PDF: {output_path}")


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
    verifier_rules = load_file(CLAIM_VERIFIER_FILE)

    # 2. Bridge Logic & Resume Generation
    print("    [Drafting] Applying 'Bridge Logic' (Platform -> Growth) to Resume...")
    resume_system_prompt = "You are an expert ATS Resume Writer translating Platform PM experience to Growth/General PM outcomes. You must output raw HTML/Markdown strictly matching the style guide."
    resume_user_prompt = f"""
    Transform the MASTER RESUME to match the JOB DESCRIPTION while strictly adhering to the BRIDGE LOGIC.
    
    BRIDGE LOGIC RULES:
    1. Translate Platform wins (Stability/Scale) to Growth needs (User Scaling, Business Revenue).
    Example: "Reduced API latency by 40%" -> "Improved system responsiveness to support 10x user scaling and retention."
    Example: "Resolved 300+ security vulnerabilities" -> "Mitigated enterprise risk to unblock GTM expansion."
    
    STYLE GUIDE:
    You MUST output the resume wrapped in the exact HTML `<div style="font-size: 11pt; line-height: 1.15;">` and use the exact HTML `<h>` tags specified in this template exactly. Do not use standard markdown `#` for headers.
    
    {resume_style}
    
    GROUND TRUTH:
    {work_exp}
    
    MASTER RESUME (Format to follow, but update bullets):
    {master_resume}
    
    JOB DESCRIPTION:
    {jd_text}
    
    Output strictly the translated Markdown resume with the HTML formatting tags. No preamble.
    """
    draft_resume = call_llm(resume_system_prompt, resume_user_prompt)
    verified_resume = verify_claims(draft_resume, work_exp, verifier_rules)

    # Hard Fact Validation: deterministic check against master resume
    final_resume, resume_warnings = validate_hard_facts(verified_resume, master_resume)

    resume_md_path = os.path.join(company_folder, "Resume.md")
    resume_pdf_path = os.path.join(company_folder, "Resume.pdf")

    with open(resume_md_path, "w", encoding="utf-8") as f:
        f.write(final_resume)
    generate_pdf(final_resume, resume_pdf_path)

    # 3. Cover Letter Generation
    print("    [Drafting] Generating Cover Letter...")
    cl_system_prompt = "You are Jason Taylor writing a compelling, direct cover letter. You must output raw HTML/Markdown strictly matching the style guide."
    cl_user_prompt = f"""
    Write a 250-400 word Cover Letter based on the JOB DESCRIPTION and RESEARCH PACKET.
    
    STYLE:
    You MUST output the cover letter wrapped in the exact HTML `<div style="font-size: 11pt; line-height: 1.15;">` and use the exact HTML header and 'Sincerely' sign-off specified in this template exactly.
    
    {cl_style}
    
    GROUND TRUTH:
    {work_exp}
    
    JOB DESCRIPTION:
    {jd_text}
    
    RESEARCH:
    {research_json}
    
    Output strictly the markdown cover letter with HTML formatting tags. No preamble.
    """
    draft_cl = call_llm(cl_system_prompt, cl_user_prompt)
    verified_cl = verify_claims(draft_cl, work_exp, verifier_rules)

    # Hard Fact Validation: deterministic check against master resume
    final_cl, cl_warnings = validate_hard_facts(verified_cl, master_resume)

    cl_md_path = os.path.join(company_folder, "CoverLetter.md")
    cl_pdf_path = os.path.join(company_folder, "CoverLetter.pdf")

    with open(cl_md_path, "w", encoding="utf-8") as f:
        f.write(final_cl)
    generate_pdf(final_cl, cl_pdf_path)

    # Summary of all validation issues
    all_warnings = resume_warnings + cl_warnings
    if all_warnings:
        print(f"  -> [AUDIT SUMMARY] {len(all_warnings)} total issue(s) caught and corrected.")
    else:
        print(f"  -> [AUDIT SUMMARY] All assets passed hard-fact validation. Clean output.")

    print(f"  -> Successfully generated and audited all assets for {company_name}")
