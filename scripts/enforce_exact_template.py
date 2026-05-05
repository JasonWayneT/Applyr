import os
import re
from markdown_pdf import MarkdownPdf, Section

SUBMISSIONS_DIR = "submissions"

def enforce_template_on_resume(folder_name):
    folder_path = os.path.join(SUBMISSIONS_DIR, folder_name)
    md_path = os.path.join(folder_path, "Resume.md")
    pdf_path = os.path.join(folder_path, "Resume.pdf")
    
    if not os.path.exists(md_path):
        return

    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Strip the ```markdown or ``` wrapper if it exists (drift cleanup)
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:markdown)?\n|```$", "", content, flags=re.MULTILINE)

    # If the file already doesn't start with <div, let's inject it to look professional
    if not content.startswith("<div"):
        content = '<div style="font-size: 11pt; line-height: 1.15;">\n\n' + content + '\n\n</div>'

    # Check if PROFESSIONAL SUMMARY is missing
    if "PROFESSIONAL SUMMARY" not in content and "Summary" not in content:
        print(f"Injecting missing PROFESSIONAL SUMMARY into {folder_name}")
        # Insert it right before the PROFESSIONAL EXPERIENCE section
        summary_block = """<h2 style="margin: 8px 0 4px 0; padding: 0; font-size: 12pt;"><strong>PROFESSIONAL SUMMARY</strong></h2>
Product Manager with 6+ years of experience optimizing complex platform infrastructure and driving B2B SaaS modernization. Focused on user workflows, data integrity, and cross-functional team alignment to deliver scalable solutions.

"""
        # Inject it right before the PROFESSIONAL EXPERIENCE section or ## Experience
        if "PROFESSIONAL EXPERIENCE" in content:
            content = content.replace("<strong>PROFESSIONAL EXPERIENCE</strong>", "<strong>PROFESSIONAL EXPERIENCE</strong>", 1)
            content = content.replace("<h2", summary_block + "<h2", 1)
        elif "## Experience" in content:
            content = content.replace("## Experience", summary_block + "## Experience", 1)

    # 2. Normalize and strip any Skills section just in case
    content = re.sub(
        r'(?:<h2[^>]*>\s*<strong>\s*(?:SKILLS|TECHNICAL).*?</h2>|##\s*(?:Skills|Technical Environment).*?)([\s\S]*?)(?=<h2[^>]*>|##\s*Education|</div>|$)',
        '',
        content,
        flags=re.IGNORECASE
    )

    # 3. Clean up excess blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
    # Recompile PDF
    try:
        pdf = MarkdownPdf(toc_level=0)
        pdf.add_section(Section(content))
        pdf.save(pdf_path)
        print(f"Successfully enforced exact template for {folder_name}!")
    except Exception as e:
        print(f"Error compiling PDF for {folder_name}: {e}")

if __name__ == "__main__":
    if os.path.exists(SUBMISSIONS_DIR):
        for f in os.listdir(SUBMISSIONS_DIR):
            if os.path.isdir(os.path.join(SUBMISSIONS_DIR, f)):
                enforce_template_on_resume(f)
