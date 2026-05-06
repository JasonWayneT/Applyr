import sys
import os
from markdown_pdf import MarkdownPdf, Section

def main():
    if len(sys.argv) < 3:
        print("Usage: python compile_single.py <md_path> <pdf_path>")
        sys.exit(1)

    md_path = sys.argv[1]
    pdf_path = sys.argv[2]

    if not os.path.exists(md_path):
        print(f"Error: Markdown file does not exist at {md_path}")
        sys.exit(1)

    try:
        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()

        # Compile markdown to PDF using MarkdownPdf
        pdf = MarkdownPdf(toc_level=0)
        pdf.add_section(Section(md_text))
        pdf.save(pdf_path)
        print("SUCCESS")
    except Exception as e:
        print(f"Error compiling PDF: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
