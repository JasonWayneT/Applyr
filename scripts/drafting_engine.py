import os
import json
import subprocess
from markdown_pdf import MarkdownPdf, Section
from utils import (load_file, call_llm, SUBMISSIONS_DIR,
                   RESUME_MASTER_FILE, COVER_LETTER_REF_FILE,
                   RESUME_STYLE_REF_FILE, CLAIM_VERIFIER_FILE,
                   WORK_EXP_FILE)


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

    resume_md_path = os.path.join(company_folder, "Resume.md")
    resume_pdf_path = os.path.join(company_folder, "Resume.pdf")

    with open(resume_md_path, "w", encoding="utf-8") as f:
        f.write(verified_resume)
    generate_pdf(verified_resume, resume_pdf_path)

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

    cl_md_path = os.path.join(company_folder, "CoverLetter.md")
    cl_pdf_path = os.path.join(company_folder, "CoverLetter.pdf")

    with open(cl_md_path, "w", encoding="utf-8") as f:
        f.write(verified_cl)
    generate_pdf(verified_cl, cl_pdf_path)

    print(f"  -> Successfully generated and audited all assets for {company_name}")
