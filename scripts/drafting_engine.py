import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types
import subprocess
from markdown_pdf import MarkdownPdf, Section

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

DATA_DIR = "data"
AGENT_DIR = ".agent"
RULES_DIR = os.path.join(AGENT_DIR, "rules")
SUBMISSIONS_DIR = "submissions"

RESUME_MASTER = os.path.join(DATA_DIR, "Resume.md")
COVER_LETTER_REF = os.path.join(DATA_DIR, "Cover_Letter_Reference.md")
RESUME_STYLE_REF = os.path.join(DATA_DIR, "Resume_Style_Reference.md")
CLAIM_VERIFIER = os.path.join(RULES_DIR, "claim_verifier.md")
RESEARCH_CONTRACT = os.path.join(RULES_DIR, "Research_Packet_Contract.md")

def load_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return ""

def run_research(company_name, jd_text):
    print(f"    [Research] Pulling Perplexity intelligence for {company_name}...")
    try:
        # We invoke the existing script
        subprocess.run(["python", "scripts/research-engine.py", company_name, "Product Manager"], check=True)
        # The script saves it to submissions/{company_name}/Research_Packet.json
        folder = os.path.join(SUBMISSIONS_DIR, company_name.lower().replace(" ", "_"))
        packet_path = os.path.join(folder, "Research_Packet.json")
        if os.path.exists(packet_path):
            return load_file(packet_path)
    except Exception as e:
        print(f"    [Research Error] {e}")
    return "No research data available."

def call_llm(system_prompt, user_prompt):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2
                )
            )
            return response.text.strip()
        except Exception as e:
            err_str = str(e)
            if "retryDelay" in err_str or "429" in err_str or "quota" in err_str.lower() or "exhausted" in err_str.lower():
                print(f"    -> LLM Rate limit hit. Waiting 45s before retry {attempt+1}/{max_retries}...")
                time.sleep(45)
            else:
                print(f"LLM Call Error: {e}")
                return ""
    return ""

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
    master_resume = load_file(RESUME_MASTER)
    resume_style = load_file(RESUME_STYLE_REF)
    cl_style = load_file(COVER_LETTER_REF)
    verifier_rules = load_file(CLAIM_VERIFIER)
    
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
