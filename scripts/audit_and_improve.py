import os
import re
import sys
import json
import subprocess
from dataclasses import dataclass, field
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from utils import (
    load_file,
    call_llm,
    SUBMISSIONS_DIR,
    RESUME_MASTER_FILE,
    WORK_EXP_FILE,
)
from drafting_engine import validate_hard_facts, generate_pdf
import verify_claims as determinator
from local_draft_stages import audit_text_against_bullet_corpus

# Load guidelines report
GUIDELINES_PATH = os.path.join(PROJECT_ROOT, "docs", "pm_resume_cover_letter_research_report.md")
if not os.path.exists(GUIDELINES_PATH):
    GUIDELINES_PATH = r"C:\Users\Jason\Desktop\Jason\Resource\AI Reusable Prompts\pm_resume_cover_letter_research_report.md"

GUIDELINES = load_file(GUIDELINES_PATH)
MASTER_RESUME = load_file(RESUME_MASTER_FILE)
VALID_IDS = determinator.load_valid_ids(WORK_EXP_FILE)

_ASSET_NAMES = ("Resume.md", "CoverLetter.md", "Resume.pdf", "CoverLetter.pdf")


@dataclass
class AuditImproveResult:
    """Return contract for post-drafting audit — Implements CR-054."""

    converged: bool
    attempts: int
    final_issues: list[str] = field(default_factory=list)
    skipped: bool = False


def _snapshot_submission_assets(folder_path: str) -> dict[str, Optional[bytes]]:
    """Capture pre-audit file bytes so failed runs can restore last-known-good."""
    snapshot: dict[str, Optional[bytes]] = {}
    for name in _ASSET_NAMES:
        path = os.path.join(folder_path, name)
        if os.path.isfile(path):
            with open(path, "rb") as fh:
                snapshot[name] = fh.read()
        else:
            snapshot[name] = None
    return snapshot


def _restore_submission_assets(folder_path: str, snapshot: dict[str, Optional[bytes]]) -> None:
    """Restore submission files from a pre-audit snapshot — Implements CR-054."""
    for name, content in snapshot.items():
        path = os.path.join(folder_path, name)
        if content is None:
            if os.path.isfile(path):
                os.remove(path)
            continue
        with open(path, "wb") as fh:
            fh.write(content)

def analyze_company_context(company_name, jd_text):
    """Classify the company stage, motion, and key info from the JD."""
    system_prompt = (
        "You are an expert recruiter and corporate intelligence analyst. "
        "Analyze the job description and output a JSON block with: "
        "1. company_stage: (e.g. Series B, Late-stage, Public, Growth, Startup)\n"
        "2. product_motion: (e.g. PLG, Sales-led Enterprise, Hybrid self-serve plus sales-assist)\n"
        "3. key_customer_segment: (e.g. Enterprise, Mid-Market, SMB, Developer)\n"
        "4. pain_points: (A brief list of key pain points they want this PM to solve)\n"
        "5. primary_partners: (e.g. Sales, Customer Success, Engineering, Compliance)\n"
        "Output ONLY the JSON object, nothing else."
    )
    user_prompt = f"Company: {company_name}\n\nJob Description:\n{jd_text[:3000]}"
    try:
        raw_res = call_llm(system_prompt, user_prompt, temperature=0.1, response_mime_type="application/json")
        match = re.search(r'\{.*\}', raw_res, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        print(f"      [Context Analysis Error] {e}")
    
    # Default fallback
    return {
        "company_stage": "Growth/Late-stage",
        "product_motion": "Enterprise B2B SaaS",
        "key_customer_segment": "Enterprise",
        "pain_points": ["Platform scale and reliability"],
        "primary_partners": ["Engineering", "Sales"]
    }

def improve_resume_summary(resume_md, context, jd_text, resume_bullets, feedback=""):
    """Tweak the Professional Summary to reflect company stage and motion."""
    # Find current summary
    summary_match = re.search(
        r"(## PROFESSIONAL SUMMARY\n+)([\s\S]*?)(?=\n##|\Z)",
        resume_md,
        re.IGNORECASE
    )
    if not summary_match:
        return resume_md, "No summary section found"

    header = summary_match.group(1)
    current_summary = summary_match.group(2).strip()

    # Ground truth constraints
    system_prompt = (
        "You are a professional B2B SaaS Resume Editor. Your task is to rewrite only the "
        "PROFESSIONAL SUMMARY section of the candidate's resume (Jason Taylor) to optimize it "
        "for the target company stage and product motion, adhering to the provided conversion guidelines.\n\n"
        "FACTUAL CONSTRAINTS (CRITICAL):\n"
        "- Jason Taylor is a B2B SaaS Platform PM with over 6 years of experience.\n"
        "- He is NOT a 0-to-1 greenfield builder (do not claim this).\n"
        "- He is NOT a people manager, AI/ML model developer, or revenue/billing owner.\n"
        "- YOU MUST ONLY USE NUMBERS, METRICS, AND TOOLS THAT ARE EXPLICITLY FOUND IN THE SELECTED EXPERIENCE BULLETS BELOW.\n"
        "- DO NOT invent any metrics. DO NOT use generic example numbers.\n\n"
        "STAGE-SPECIFIC INSTRUCTIONS:\n"
        f"- Target Company Stage: {context.get('company_stage')}\n"
        f"- Target Product Motion: {context.get('product_motion')}\n"
        "Rewrite the summary in EXACTLY 3 concise sentences. The first two sentences establish target alignment, years of experience, "
        "product motion, and internal partners. The third sentence is a single grounded proof metric (outcomes only) "
        "drawn from the provided experience bullets. Do NOT include em-dashes (—). Keep the language natural and authentic. "
        "Output ONLY the new 3-sentence summary paragraph."
    )

    user_prompt = (
        f"Conversion Guidelines:\n{GUIDELINES}\n\n"
        f"Current Summary:\n{current_summary}\n\n"
        f"Selected Experience Bullets (THE ONLY SOURCE OF METRICS/TOOLS):\n{resume_bullets}\n\n"
        f"Target Job Context:\n{json.dumps(context, indent=2)}\n\n"
        f"Job Description (snippet):\n{jd_text[:1500]}"
    )
    if feedback:
        user_prompt += f"\n\nCORRECTION FEEDBACK FROM PREVIOUS ATTEMPT:\n{feedback}\nPlease fix this error now."

    new_summary = call_llm(system_prompt, user_prompt, temperature=0.2).strip()
    # Clean output if it contains markdown headings
    new_summary = re.sub(r'^##\s+PROFESSIONAL\s+SUMMARY\n*', '', new_summary, flags=re.IGNORECASE)
    
    # Replace in resume
    improved_resume = resume_md.replace(current_summary, new_summary)
    return improved_resume, new_summary

def improve_cover_letter(cl_text, context, resume_bullets, jd_text, feedback=""):
    """Optimize cover letter for stage, motion, and length."""
    # Find opener and closer to preserve structure, rewrite the core body
    header_block = ""
    salutation = "Dear Hiring Manager,"
    
    if salutation in cl_text:
        parts = cl_text.split(salutation, 1)
        header_block = parts[0] + salutation + "\n\n"
        body_and_closer = parts[1].strip()
    else:
        body_and_closer = cl_text.strip()

    system_prompt = (
        "You are an expert Cover Letter writer for B2B SaaS PMs. Rewrite the body paragraphs of this cover letter "
        "to align perfectly with the target company's stage and product motion, using the provided guidelines.\n\n"
        "RULES:\n"
        "1. Open with a highly specific product/business reason why the candidate is drawn to this company, "
        "referencing their specific stage, ICP, or motion.\n"
        "2. Detail 1 or 2 specific accomplishments from Jason's background (platform stabilization, data remediation, "
        "or migration) that prove relevant fit. EVERY METRIC MUST be completely grounded in the resume bullets.\n"
        "3. Highlight a brief paragraph on how Jason's collaboration/work style maps to their internal partners "
        f"({', '.join(context.get('primary_partners', []))}).\n"
        "4. DO NOT use em-dashes (—) or '--'. Replace with commas.\n"
        "5. The entire letter must remain under 350 words and feel authentic, not AI-polished or generic.\n"
        "6. Do not include signature/header placeholder blocks. Output ONLY the rewritten body paragraphs.\n"
        "7. CRITICAL CRITICAL RULE: Discard all numbers/metrics found in the current cover letter body (e.g., 80+, 40M, 7%, etc.). "
        "You must ONLY use numbers/metrics that are explicitly present in the provided Resume Experience Bullets.\n"
        "8. Capitalize the first letter of every sentence and paragraph. Double-check that no paragraph starts with a lowercase letter.\n"
        "9. Conclude the body text with a dedicated transition paragraph expressing interest in discussing the role, looking forward to speaking, and thanking them for consideration (e.g., 'I would welcome the opportunity to discuss how my background in platform stabilization and data integrity could help your team deliver on its priorities. Thank you for your time and consideration.')."
    )

    user_prompt = (
        f"Conversion Guidelines:\n{GUIDELINES}\n\n"
        f"Target Company Context:\n{json.dumps(context, indent=2)}\n\n"
        f"Resume Bullets:\n{resume_bullets}\n\n"
        f"Current Body:\n{body_and_closer}\n\n"
        f"Job Description:\n{jd_text[:1500]}"
    )
    if feedback:
        user_prompt += f"\n\nCORRECTION FEEDBACK FROM PREVIOUS ATTEMPT:\n{feedback}\nPlease fix this error now."

    new_body = call_llm(system_prompt, user_prompt, temperature=0.2).strip()
    from utils import load_identity_profile
    candidate_name = (load_identity_profile().get("name") or "Jason Taylor").strip()
    signoff = f"\n\nRegards,\n\n{candidate_name}\n"
    improved_cl = header_block + new_body + signoff
    return improved_cl

def extract_bullets_text(resume_md):
    bullet_lines = [
        ln.lstrip("* ").strip()
        for ln in resume_md.splitlines()
        if ln.strip().startswith("* ")
    ]
    return "\n".join(bullet_lines)

def audit_and_improve_company(folder_path) -> AuditImproveResult:
    """Run post-drafting audit loop; return convergence contract — Implements CR-054."""
    company_name = os.path.basename(folder_path)
    resume_path = os.path.join(folder_path, "Resume.md")
    cl_path = os.path.join(folder_path, "CoverLetter.md")
    jd_path = os.path.join(folder_path, "Original_JD.txt")

    if not os.path.exists(resume_path) or not os.path.exists(cl_path) or not os.path.exists(jd_path):
        print(f"  [Skip] Missing files for {company_name}")
        return AuditImproveResult(
            converged=False,
            attempts=0,
            final_issues=["missing required submission files"],
            skipped=True,
        )

    print(f"Auditing & Improving {company_name}...")
    pre_audit_snapshot = _snapshot_submission_assets(folder_path)

    jd_text = load_file(jd_path)
    resume_md = load_file(resume_path)
    cl_md = load_file(cl_path)

    # 1. Analyze Context
    context = analyze_company_context(company_name, jd_text)
    print(f"    - Stage: {context.get('company_stage')} | Motion: {context.get('product_motion')}")

    # Loop for self-healing
    attempts = 3
    summary_feedback = ""
    cl_feedback = ""
    final_issues: list[str] = []
    for attempt in range(1, attempts + 1):
        print(f"    - Attempt {attempt} to generate and verify...")
        
        # Extract current bullets before editing summary
        bullets = extract_bullets_text(resume_md)
        
        # 2. Improve summary in Resume passing the extracted bullets and feedback
        updated_resume, _ = improve_resume_summary(resume_md, context, jd_text, bullets, summary_feedback)
        
        # 3. Improve Cover Letter passing the feedback
        updated_cl = improve_cover_letter(cl_md, context, bullets, jd_text, cl_feedback)

        # 4. Deterministic Fact / Metric / Blocklist Guards
        corrected_resume, res_warnings = validate_hard_facts(updated_resume, MASTER_RESUME, company_name, 'resume')
        corrected_cl, cl_warnings = validate_hard_facts(updated_cl, MASTER_RESUME, company_name, 'cover_letter')

        # 5. Cover letter numeric audit against resume + contact header
        from quality_checker import HEADER_BLOCK
        cover_audit_corpus = f"{bullets}\n{HEADER_BLOCK}"
        cl_ok_audit, cl_audit_err = audit_text_against_bullet_corpus(corrected_cl, cover_audit_corpus)
        if not cl_ok_audit:
            print(f"      [Audit Warning] Cover letter metric mismatch: {cl_audit_err}")
            cl_feedback = f"The previous cover letter draft contained metric errors: {cl_audit_err}. Remove or correct these numbers to match the resume bullets."
            final_issues = [cl_feedback]
            continue

        # 6. Verify summary against experience bullets and sentence count
        summary_section = updated_resume.split("## PROFESSIONAL SUMMARY")[1].split("\n##")[0].strip()
        summary_ok, summary_err = audit_text_against_bullet_corpus(summary_section, bullets)
        if not summary_ok:
            print(f"      [Audit Warning] Resume summary metric mismatch: {summary_err}")
            summary_feedback = f"The previous professional summary draft contained metric errors: {summary_err}. Remove or correct these numbers to match the experience bullets."
            final_issues = [summary_feedback]
            continue
            
        clean_summary = re.sub(r'\b(Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec|vs|approx|eg|ie|ca|Inc|Co|B2B|SaaS|PM|PMs)\.', r'\1', summary_section, flags=re.IGNORECASE)
        sentences = [s for s in re.split(r'\.(?:\s+|$)', clean_summary) if s.strip()]
        print(f"      [Debug] Summary Section:\n{summary_section}")
        print(f"      [Debug] Sentences ({len(sentences)}): {sentences}")
        if len(sentences) != 3:
            print(f"      [Audit Warning] Resume summary has {len(sentences)} sentence(s) (expected exactly 3). Retrying...")
            summary_feedback = f"The previous professional summary had {len(sentences)} sentence(s). You MUST write EXACTLY 3 sentences. Here is the split we detected: {sentences}."
            final_issues = [summary_feedback]
            continue

        # Saved if pass all checks
        print(f"    [Success] Verified and passed all conversion guards for {company_name}!")
        with open(resume_path, "w", encoding="utf-8") as f:
            f.write(corrected_resume)
        with open(cl_path, "w", encoding="utf-8") as f:
            f.write(corrected_cl)
        
        # Compile PDFs
        resume_pdf = os.path.join(folder_path, "Resume.pdf")
        cl_pdf = os.path.join(folder_path, "CoverLetter.pdf")
        generate_pdf(resume_path, resume_pdf)
        generate_pdf(cl_path, cl_pdf)
        return AuditImproveResult(converged=True, attempts=attempt, final_issues=[])

    print(f"    [Failed] Could not align assets within constraints for {company_name} after {attempts} attempts.")
    _restore_submission_assets(folder_path, pre_audit_snapshot)
    return AuditImproveResult(converged=False, attempts=attempts, final_issues=final_issues)

def main():
    if not os.path.exists(SUBMISSIONS_DIR):
        print("Submissions directory not found.")
        return 1

    target_filter = sys.argv[1] if len(sys.argv) > 1 else None

    folders = [
        os.path.join(SUBMISSIONS_DIR, d)
        for d in os.listdir(SUBMISSIONS_DIR)
        if os.path.isdir(os.path.join(SUBMISSIONS_DIR, d))
    ]

    success = 0
    total = 0
    for folder in folders:
        # Avoid processing other testing/placeholder directories
        if os.path.basename(folder) in ("browser_context", "thinking", "eval_brown_brown_pm"):
            continue
        if target_filter and os.path.basename(folder) != target_filter:
            continue
        total += 1
        result = audit_and_improve_company(folder)
        if result.converged:
            success += 1

    print(f"\nDone! Audited & improved {success} out of {total} company portfolios.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
