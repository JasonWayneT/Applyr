import os
import re
from markdown_pdf import MarkdownPdf, Section

SUBMISSIONS_DIR = "submissions"

def trim_resume(folder_name):
    folder_path = os.path.join(SUBMISSIONS_DIR, folder_name)
    md_path = os.path.join(folder_path, "Resume.md")
    pdf_path = os.path.join(folder_path, "Resume.pdf")
    
    if not os.path.exists(md_path):
        return

    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Normalize line breaks
    lines = content.splitlines()

    # Step 1: Detect and trim Summary / Professional Summary section
    trimmed_lines = []
    in_summary = False
    
    # We will identify the header for Summary and the next header
    for line in lines:
        # Match standard HTML template for PROFESSIONAL SUMMARY
        if re.search(r"PROFESSIONAL\s+SUMMARY", line, re.IGNORECASE) or re.search(r"^##\s+Summary", line, re.IGNORECASE):
            in_summary = True
            continue
        
        # End of summary section when we see next section header
        if in_summary and (re.search(r"PROFESSIONAL\s+EXPERIENCE", line, re.IGNORECASE) or re.search(r"^##\s+Experience", line, re.IGNORECASE)):
            in_summary = False
            trimmed_lines.append(line)
            continue
            
        if not in_summary:
            trimmed_lines.append(line)

    # Step 2: Trim bullet points under Cision to 4 bullets max
    cleaned_lines = []
    bullet_count = 0
    in_cision = False

    for line in trimmed_lines:
        # Detect Cision header
        if re.search(r"Cision", line, re.IGNORECASE):
            in_cision = True
            cleaned_lines.append(line)
            continue
            
        # If we see next company or skills, end Cision
        if in_cision and (re.search(r"Sterkly", line, re.IGNORECASE) or re.search(r"SKILLS", line, re.IGNORECASE) or re.search(r"^##\s+Skills", line, re.IGNORECASE)):
            in_cision = False
            cleaned_lines.append(line)
            continue
            
        if in_cision:
            if line.strip().startswith('*') or line.strip().startswith('-'):
                if bullet_count < 4:
                    cleaned_lines.append(line)
                    bullet_count += 1
            else:
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)

    final_content = "\n".join(cleaned_lines)

    # Automatically strip Skills and Technical Environment sections
    final_content = re.sub(
        r'(?:<h2[^>]*>\s*<strong>\s*(?:SKILLS|TECHNICAL).*?</h2>|##\s*(?:Skills|Technical Environment).*?)([\s\S]*?)(?=<h2[^>]*>|##\s*Education|</div>|$)',
        '',
        final_content,
        flags=re.IGNORECASE
    )

    # Clean up excess blank lines
    final_content = re.sub(r'\n{3,}', '\n\n', final_content)

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(final_content)
        
    # Step 3: Recompile the PDF
    try:
        pdf = MarkdownPdf(toc_level=0)
        # MarkdownPdf converts md format with simple section
        # But if it has raw backticks at the start (as in case_iq), strip them.
        stripped_md = final_content.strip()
        if stripped_md.startswith("```markdown"):
            stripped_md = re.sub(r"^```markdown\n|```$", "", stripped_md, flags=re.MULTILINE)
        pdf.add_section(Section(stripped_md))
        pdf.save(pdf_path)
        print(f"Enforced single page for {folder_name}!")
    except Exception as e:
        print(f"Error compiling PDF for {folder_name}: {e}")

if __name__ == "__main__":
    if os.path.exists(SUBMISSIONS_DIR):
        for f in os.listdir(SUBMISSIONS_DIR):
            if os.path.isdir(os.path.join(SUBMISSIONS_DIR, f)):
                trim_resume(f)
