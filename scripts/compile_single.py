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

        # Experience headers: Title | Company | Dates (three segments).
        # Use flex layout — float:right breaks print order (company/title sink to page bottom).
        def _role_header_three(match):
            title = match.group(1).strip()
            company = match.group(2).strip()
            dates = match.group(3).strip()
            return (
                '<h3 class="role-header">'
                f'<span class="role-left"><span class="role-title">{title}</span>'
                f'<span class="role-sep"> | </span>'
                f'<span class="role-company">{company}</span></span>'
                f'<span class="role-dates">{dates}</span>'
                '</h3>'
            )

        html_content = re.sub(
            r'<h3>\s*(?:<strong[^>]*>)?(.*?)(?:</strong>)?\s*\|\s*'
            r'(?:<strong[^>]*>)?(.*?)(?:</strong>)?\s*\|\s*'
            r'(?:<strong[^>]*>)?(.*?)(?:</strong>)?\s*</h3>',
            _role_header_three,
            html_content,
            flags=re.IGNORECASE,
        )

        # Legacy two-segment headers: Title | Dates
        html_content = re.sub(
            r'<h3(?![^>]*class="role-header")\s*>\s*'
            r'(?:<strong[^>]*>)?(.*?)(?:</strong>)?\s*(?:\||—|-)\s*'
            r'(?:<strong[^>]*>)?(.*?)(?:</strong>)?\s*</h3>',
            r'<h3 class="role-header"><span class="role-left"><span class="role-title">\1</span></span>'
            r'<span class="role-dates">\2</span></h3>',
            html_content,
            flags=re.IGNORECASE,
        )

        # Location line under each role header (Full Remote, San Diego, CA)
        html_content = re.sub(
            r'(<h3 class="role-header">.*?</h3>)\s*<p>',
            r'\1<p class="role-location">',
            html_content,
            flags=re.IGNORECASE,
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
        }}
        h2 + h3 {{
            margin-top: 6px;
        }}
        h3.role-header {{
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: baseline;
            gap: 4px 12px;
            clear: both;
        }}
        h3.role-header .role-left {{
            flex: 1 1 auto;
            min-width: 0;
        }}
        h3.role-header .role-title,
        h3.role-header .role-company {{
            font-weight: 700;
            color: #2d3748;
        }}
        h3.role-header .role-sep {{
            font-weight: 500;
            color: #4a5568;
        }}
        h3.role-header .role-dates {{
            flex: 0 0 auto;
            font-weight: 500;
            color: #4a5568;
            font-size: 9.5pt;
            white-space: nowrap;
        }}
        p.role-location {{
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
            
            # Initial render at 100%
            page.pdf(
                path=pdf_path,
                format="Letter",
                print_background=True,
                prefer_css_page_size=True,
                scale=1.0
            )
            
            # Implement Responsive PDF Layout Feedback dynamically
            def get_pdf_page_count(path):
                import re
                try:
                    with open(path, 'rb') as f:
                        return len(re.findall(b'/Type\\s*/Page\\b', f.read()))
                except:
                    return 1
                    
            if get_pdf_page_count(pdf_path) > 1:
                # Scale down by 10% to try and fit it onto 1 page
                page.pdf(
                    path=pdf_path,
                    format="Letter",
                    print_background=True,
                    prefer_css_page_size=True,
                    scale=0.9
                )
                
            browser.close()

        print("SUCCESS")
    except Exception as e:
        print(f"Error compiling PDF via Playwright: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
