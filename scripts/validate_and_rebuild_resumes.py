import os
import re
from utils import load_file, call_llm
from markdown_pdf import MarkdownPdf, Section

RESUME_STYLE_FILE = "data/Resume_Style_Reference.md"
SUBMISSIONS_DIR = "submissions"

def rebuild_resume(folder):
    md_path = os.path.join(SUBMISSIONS_DIR, folder, "Resume.md")
    pdf_path = os.path.join(SUBMISSIONS_DIR, folder, "Resume.pdf")
    
    if not os.path.exists(md_path):
        return

    print(f"Rebuilding resume for: {folder} to enforce template")
    current_content = load_file(md_path)
    template = load_file(RESUME_STYLE_FILE)

    prompt = f"""
You are a technical resume writer. Your job is to restructure the candidate's current resume to follow the target template style exactly.

TARGET TEMPLATE STYLE:
{template}

CURRENT RESUME CONTENT TO RESTRUCTURE:
{current_content}

INSTRUCTIONS:
1. You MUST output exactly the three headers in the template: PROFESSIONAL SUMMARY, PROFESSIONAL EXPERIENCE, and EDUCATION. No other sections or headers are allowed.
2. The PROFESSIONAL SUMMARY must be exactly 1-2 concise sentences.
3. Keep the entire resume very concise so it fits easily on a single page. Use the exact HTML wrapping from the template: `<div style="font-size: 11pt; line-height: 1.15;">` and `</div>`.
4. Return ONLY the finished, template-compliant markdown output with HTML tags. No other commentary or preamble.
"""

    restructured = call_llm(
        system_prompt="You are a professional resume writer for Jason Taylor.",
        user_prompt=prompt
    )

    if restructured and "PROFESSIONAL SUMMARY" in restructured:
        # Clean up excess blank lines
        restructured = re.sub(r'\n{3,}', '\n\n', restructured)
        
        # Strip code fences if returned by LLM
        if restructured.strip().startswith("```"):
            restructured = re.sub(r"^```(?:markdown)?\n|```$", "", restructured.strip(), flags=re.MULTILINE)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(restructured)

        try:
            pdf = MarkdownPdf(toc_level=0)
            pdf.add_section(Section(restructured))
            pdf.save(pdf_path)
            print(f"Successfully rebuilt and saved template-perfect resume for {folder}!")
        except Exception as e:
            print(f"Error generating PDF for {folder}: {e}")
    else:
        print(f"LLM returned empty or non-compliant restructure for {folder}. Skipping.")

if __name__ == "__main__":
    if os.path.exists(SUBMISSIONS_DIR):
        for f in os.listdir(SUBMISSIONS_DIR):
            if os.path.isdir(os.path.join(SUBMISSIONS_DIR, f)):
                rebuild_resume(f)
