import sys
import os
import re
import markdown
from playwright.sync_api import sync_playwright

def main():
    if len(sys.argv) < 3:
        print("Usage: python compile_single.py <md_path> <pdf_path>", file=sys.stderr)
        sys.exit(1)

    md_path = sys.argv[1]
    pdf_path = sys.argv[2]

    if not os.path.exists(md_path):
        print(f"Error: Markdown file does not exist at {md_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()

        # Ensure blank line before bullet lists that directly follow a paragraph line.
        # Python-Markdown requires a blank line between a <p> and a list; without it
        # the bullets get absorbed into the paragraph as literal text.
        # Match: a non-list, non-header line immediately followed by a "* " or "- " line.
        md_text = re.sub(r'(?m)^((?!\* |\- |#).+)\n(\* |\- )', r'\1\n\n\2', md_text)

        # Convert standard Markdown to HTML
        html_content = markdown.markdown(md_text, extensions=['extra', 'tables'])

        # Find the h1 element and format the contact info paragraph right below it
        # The contact info is typically the first paragraph after h1
        # Convert '<h3>Company — Dates</h3>' into side-by-side layout (float dates right)
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
            page_margin = "0.65in 0.75in 0.65in 0.75in"
            body_line_height = "1.35"
            p_margin = "0 0 5px 0"
            p_font_size = "9.5pt"
            header_margin_bottom = "10px"

        # Build professional ATS-optimized HTML layout wrapper with Google Inter Font
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
        /* Contact Info line directly under h1 */
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
            margin: 14px 0 2px 0;
            display: block;
            position: relative;
        }}
        h2 + h3 {{
            margin-top: 6px;
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
            margin: 0 0 5px 0;
            padding-left: 15px;
        }}
        li {{
            font-size: 9.5pt;
            margin-bottom: 3px;
            color: #2d3748;
            line-height: 1.35;
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

        print("SUCCESS")
    except Exception as e:
        print(f"Error compiling PDF via Playwright: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
