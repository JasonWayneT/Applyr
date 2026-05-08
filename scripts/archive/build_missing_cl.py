import os
from utils import load_file, call_llm, WORK_EXP_FILE
from markdown_pdf import MarkdownPdf, Section

def build_cl(folder):
    company_folder = os.path.join("submissions", folder)
    os.makedirs(company_folder, exist_ok=True)
    
    jd_path = os.path.join("jobs", f"{folder.replace('_', ' ').capitalize()}.txt")
    if not os.path.exists(jd_path):
        for f in os.listdir("jobs"):
            if f.lower().startswith(folder.split('_')[0]):
                jd_path = os.path.join("jobs", f)
                break
                
    jd_text = ""
    if os.path.exists(jd_path):
        jd_text = load_file(jd_path)
    else:
        jd_text = "Mid-Level Product Manager role"

    work_exp = load_file(WORK_EXP_FILE)

    print(f"Calling LLM for cover letter for: {folder}")
    prompt = f"""
    Write a short, highly professional cover letter for {folder} for a Product Manager role.
    
    Jason Taylor's work experience:
    {work_exp}
    
    Job Description:
    {jd_text}
    
    Output ONLY the markdown cover letter without intro/outro text.
    """
    
    cl_text = call_llm(
        system_prompt="You are an expert recruiter matching a candidate to a job description.",
        user_prompt=prompt
    )
    
    if not cl_text:
        cl_text = f"# Cover Letter for {folder}\n\nDear Hiring Team,\n\nI am thrilled to apply for the Product Manager role at {folder}."

    md_path = os.path.join(company_folder, "CoverLetter.md")
    pdf_path = os.path.join(company_folder, "CoverLetter.pdf")
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(cl_text)
        
    pdf = MarkdownPdf(toc_level=0)
    pdf.add_section(Section(cl_text))
    pdf.save(pdf_path)
    print(f"Saved {md_path} and {pdf_path}")

# Always load the Resume too if missing for case_iq
if not os.path.exists("submissions/case_iq/Resume.md"):
    print("Regenerating Resume for case_iq")
    work_exp = load_file(WORK_EXP_FILE)
    resume_text = call_llm(
        system_prompt="You are a professional resume writer.",
        user_prompt=f"Generate a tailored markdown resume for case_iq based on this work experience:\n\n{work_exp}"
    )
    if resume_text:
        os.makedirs("submissions/case_iq", exist_ok=True)
        with open("submissions/case_iq/Resume.md", "w", encoding="utf-8") as f:
            f.write(resume_text)
        pdf = MarkdownPdf(toc_level=0)
        pdf.add_section(Section(resume_text))
        pdf.save("submissions/case_iq/Resume.pdf")

for f in ["case_iq"]:
    try:
        build_cl(f)
    except Exception as e:
        print(f"Error for {f}: {e}")
