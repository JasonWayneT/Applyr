import os
import re
import time
from utils import load_file, call_llm, SUBMISSIONS_DIR, WORK_EXP_FILE
from markdown_pdf import MarkdownPdf, Section

RESUME_STYLE_FILE = "data/Resume_Style_Reference.md"
COVER_LETTER_STYLE_FILE = "data/Cover_Letter_Reference.md"

def regenerate_submission(folder_name):
    folder_path = os.path.join(SUBMISSIONS_DIR, folder_name)
    jd_path = os.path.join(folder_path, "Original_JD.txt")
    
    if not os.path.exists(jd_path):
        print(f"Original JD doesn't exist for {folder_name}")
        return

    print(f"\n===== Regenerating Submission: {folder_name} =====")
    jd_text = load_file(jd_path)
    work_exp = load_file(WORK_EXP_FILE)
    resume_style = load_file(RESUME_STYLE_FILE)
    cl_style = load_file(COVER_LETTER_STYLE_FILE)
    
    # 1. Generate Resume
    print(f"  -> Drafting Resume for {folder_name}")
    resume_prompt = {
        "role": "You are a professional resume writer for Jason Taylor. "
                "Your goal is to create a high-impact, ONE-PAGE technical resume that matches the style reference template exactly. "
                "STRICT CONSTRAINT: The resume MUST have exactly these three headers: PROFESSIONAL SUMMARY, PROFESSIONAL EXPERIENCE, and EDUCATION. No other headers are allowed. "
                "The PROFESSIONAL SUMMARY must be exactly 1-2 concise lines to save space. Do not include Skills or Technical Environment sections. "
                "The entire resume MUST fit on a single page. Do not exceed 3,200 characters. "
                "Use the provided work experience faithfully. Do not hallucinate tools or seniority.",
        "content": f"""
    Transform the MASTER RESUME to match the JOB DESCRIPTION while strictly adhering to the BRIDGE LOGIC.
    
    STYLE GUIDE:
    You MUST output the resume wrapped in the exact HTML `<div style="font-size: 11pt; line-height: 1.15;">` and use the exact HTML `<h>` tags specified in this template exactly. Do not use standard markdown `#` for headers.
    
    {resume_style}
    
    GROUND TRUTH:
    {work_exp}
    
    JOB DESCRIPTION:
    {jd_text}
    
    Output strictly the translated Markdown resume with the HTML formatting tags. No preamble. No code fences.
    """
    }
    
    draft_resume = call_llm(resume_prompt["role"], resume_prompt["content"])
    if draft_resume:
        # Strip code fences if present
        if draft_resume.strip().startswith("```"):
            draft_resume = re.sub(r"^```(?:markdown)?\n|```$", "", draft_resume.strip(), flags=re.MULTILINE)
        
        # Strip Skills section just in case
        draft_resume = re.sub(
            r'(?:<h2[^>]*>\s*<strong>\s*(?:SKILLS|TECHNICAL).*?</h2>|##\s*(?:Skills|Technical Environment).*?)([\s\S]*?)(?=<h2[^>]*>|##\s*Education|</div>|$)',
            '',
            draft_resume,
            flags=re.IGNORECASE
        )
        
        # Clean up blank lines
        draft_resume = re.sub(r'\n{3,}', '\n\n', draft_resume)

        resume_md_path = os.path.join(folder_path, "Resume.md")
        resume_pdf_path = os.path.join(folder_path, "Resume.pdf")
        
        with open(resume_md_path, "w", encoding="utf-8") as f:
            f.write(draft_resume)
            
        try:
            pdf = MarkdownPdf(toc_level=0)
            pdf.add_section(Section(draft_resume))
            pdf.save(resume_pdf_path)
            print(f"  [Saved] Resume for {folder_name}")
        except Exception as e:
            print(f"Error compiling PDF for resume of {folder_name}: {e}")

    time.sleep(3)

    # 2. Generate Cover Letter
    print(f"  -> Drafting Cover Letter for {folder_name}")
    cl_prompt = {
        "role": "You are a professional cover letter writer for Jason Taylor. "
                "Your goal is to write a concise, one-page cover letter. "
                "STRICT CONSTRAINT: The entire letter must be under 1,800 characters to fit on one page with headers. "
                "Directly address the job requirements using Jason's actual experience.",
        "content": f"""
    Write a concise, professional cover letter based on the JOB DESCRIPTION.
    
    STYLE:
    You MUST output the cover letter wrapped in the exact HTML `<div style="font-size: 11pt; line-height: 1.15;">` and use the exact HTML header and 'Sincerely' sign-off specified in this template exactly. Do not use standard markdown `#` for headers.
    
    {cl_style}
    
    GROUND TRUTH:
    {work_exp}
    
    JOB DESCRIPTION:
    {jd_text}
    
    Output strictly the markdown cover letter with HTML formatting tags. No preamble. No code fences.
    """
    }
    
    draft_cl = call_llm(cl_prompt["role"], cl_prompt["content"])
    if draft_cl:
        # Strip code fences if present
        if draft_cl.strip().startswith("```"):
            draft_cl = re.sub(r"^```(?:markdown)?\n|```$", "", draft_cl.strip(), flags=re.MULTILINE)
        
        # Clean up blank lines
        draft_cl = re.sub(r'\n{3,}', '\n\n', draft_cl)

        cl_md_path = os.path.join(folder_path, "CoverLetter.md")
        cl_pdf_path = os.path.join(folder_path, "CoverLetter.pdf")
        
        with open(cl_md_path, "w", encoding="utf-8") as f:
            f.write(draft_cl)
            
        try:
            pdf = MarkdownPdf(toc_level=0)
            pdf.add_section(Section(draft_cl))
            pdf.save(cl_pdf_path)
            print(f"  [Saved] Cover Letter for {folder_name}")
        except Exception as e:
            print(f"Error compiling PDF for cover letter of {folder_name}: {e}")

if __name__ == "__main__":
    regenerate_submission("onedigital_health")
