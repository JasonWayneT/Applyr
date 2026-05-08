import os
import sys
import markdown
from style_compliance_guard import run_guard
from playwright.sync_api import sync_playwright

# Define path constants
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBMISSIONS_DIR = os.path.join(PROJECT_ROOT, "submissions")

import re

def compile_pdf(md_path, pdf_path):
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()

        html_content = markdown.markdown(md_text, extensions=['extra', 'tables'])

        html_content = re.sub(
            r'<h3>\s*(?:<strong[^>]*>)?(.*?)(?:</strong>)?\s*(?:\||—|-)\s*(?:<strong[^>]*>)?(.*?)(?:</strong>)?\s*</h3>',
            r'<h3>\1 <span class="date">\2</span></h3>',
            html_content
        )

        is_cover_letter = "CoverLetter" in os.path.basename(md_path) or "cover" in os.path.basename(md_path).lower()

        if is_cover_letter:
            page_margin = "0.85in 0.95in 0.85in 0.95in"
            body_line_height = "1.5"
            p_margin = "0 0 16px 0"
            p_font_size = "10.5pt"
            header_margin_bottom = "24px"
        else:
            page_margin = "0.45in 0.55in 0.45in 0.55in"
            body_line_height = "1.35"
            p_margin = "0 0 5px 0"
            p_font_size = "9.5pt"
            header_margin_bottom = "10px"

        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        @page {{
            size: letter;
            margin: {page_margin};
        }}
        body {{
            font-family: 'Inter', sans-serif;
            color: #2d3748;
            margin: 0;
            padding: 0;
            background-color: #ffffff;
            line-height: {body_line_height};
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}
        h1 {{
            font-size: 18pt;
            font-weight: 700;
            color: #1a202c;
            text-align: center;
            margin: 0 0 4px 0;
            padding: 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        h1 + p {{
            text-align: center;
            font-size: 9.5pt;
            color: #4a5568;
            margin: 0 0 {header_margin_bottom} 0;
            border-bottom: 2px solid #2b6cb0;
            padding-bottom: 6px;
        }}
        h2 {{
            font-size: 11pt;
            font-weight: 700;
            color: #2b6cb0;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 2px;
            margin: 16px 0 6px 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        h3 {{
            font-size: 10pt;
            font-weight: 700;
            color: #2d3748;
            margin: 20px 0 3px 0;
            display: block;
            position: relative;
        }}
        h2 + h3 {{
            margin-top: 8px;
        }}
        h3 span.date {{
            float: right;
            font-weight: 500;
            color: #4a5568;
            font-size: 9.5pt;
        }}
        /* Job Title paragraph directly following h3 */
        h3 + p {{
            font-size: 9.5pt;
            font-weight: 500;
            color: #4a5568;
            margin: 0 0 6px 0;
        }}
        p {{
            font-size: {p_font_size};
            margin: {p_margin};
            color: #2d3748;
        }}
        ul {{
            margin: 0 0 8px 0;
            padding-left: 15px;
        }}
        li {{
            font-size: 9.5pt;
            margin-bottom: 5px;
            color: #2d3748;
            line-height: 1.4;
        }}
        strong {{
            font-weight: 600;
            color: #1a202c;
        }}
        a {{
            color: inherit;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(full_html)
            page.evaluate("document.fonts.ready")
            page.pdf(
                path=pdf_path,
                format="Letter",
                print_background=True,
                prefer_css_page_size=True
            )
            browser.close()
        return True
    except Exception as e:
        print(f"      [COMPILE ERROR] Failed to compile {os.path.basename(pdf_path)} via Playwright: {e}", file=sys.stderr)
        return False

def main():
    if not os.path.exists(SUBMISSIONS_DIR):
        print(f"Error: Submissions directory '{SUBMISSIONS_DIR}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    print("==================================================================", file=sys.stderr)
    print("  AUDITING ALL EXISTING SUBMISSIONS FOR STYLE COMPLIANCE", file=sys.stderr)
    print("==================================================================", file=sys.stderr)
    
    subdirs = [d for d in os.listdir(SUBMISSIONS_DIR) if os.path.isdir(os.path.join(SUBMISSIONS_DIR, d))]
    subdirs.sort()
    
    total_resumes = 0
    total_cl = 0
    
    for folder in subdirs:
        folder_path = os.path.join(SUBMISSIONS_DIR, folder)
        resume_md = os.path.join(folder_path, "Resume.md")
        resume_pdf = os.path.join(folder_path, "Resume.pdf")
        cl_md = os.path.join(folder_path, "CoverLetter.md")
        cl_pdf = os.path.join(folder_path, "CoverLetter.pdf")
        
        has_resume = os.path.exists(resume_md)
        has_cl = os.path.exists(cl_md)
        
        if has_resume or has_cl:
            print(f"\n[Folder: {folder}]", file=sys.stderr)
            
        if has_resume:
            print("  -> Auditing Resume.md...", file=sys.stderr)
            run_guard(resume_md)
            
            from quality_checker import check_resume
            qa_passed, qa_msg = check_resume(resume_md)
            if not qa_passed:
                print(f"  [QA FAIL] {qa_msg}", file=sys.stderr)
            else:
                print(f"  [QA OK] {qa_msg}", file=sys.stderr)
                
            if compile_pdf(resume_md, resume_pdf):
                print("  [SUCCESS] Resume.pdf successfully re-compiled.", file=sys.stderr)
                total_resumes += 1
                
        if has_cl:
            print("  -> Auditing CoverLetter.md...", file=sys.stderr)
            run_guard(cl_md)
            
            from quality_checker import check_and_repair_cover_letter
            qa_passed, qa_msg = check_and_repair_cover_letter(cl_md)
            if not qa_passed:
                print(f"  [QA FAIL] {qa_msg}", file=sys.stderr)
            else:
                print(f"  [QA OK] {qa_msg}", file=sys.stderr)
                
            if compile_pdf(cl_md, cl_pdf):
                print("  [SUCCESS] CoverLetter.pdf successfully re-compiled.", file=sys.stderr)
                total_cl += 1
                
    print("\n==================================================================", file=sys.stderr)
    print(f"  AUDIT COMPLETE: Audited and compiled {total_resumes} Resumes and {total_cl} Cover Letters.", file=sys.stderr)
    print("==================================================================", file=sys.stderr)

if __name__ == "__main__":
    main()
