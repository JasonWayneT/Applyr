"""
Manual PDF generation for all markdown files across all submission folders.
Uses shared utils for path constants.
"""
import os
from markdown_pdf import MarkdownPdf, Section
from utils import SUBMISSIONS_DIR


def generate_pdf(md_path, pdf_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    pdf = MarkdownPdf(toc_level=0)
    pdf.add_section(Section(md_text))
    pdf.save(pdf_path)


def main():
    count = 0
    for folder_name in os.listdir(SUBMISSIONS_DIR):
        folder_path = os.path.join(SUBMISSIONS_DIR, folder_name)
        if os.path.isdir(folder_path):
            for file_name in os.listdir(folder_path):
                if file_name.endswith('.md'):
                    md_path = os.path.join(folder_path, file_name)
                    pdf_path = os.path.join(folder_path, file_name.replace('.md', '.pdf'))
                    try:
                        generate_pdf(md_path, pdf_path)
                        count += 1
                    except Exception as e:
                        print(f"Error generating PDF for {md_path}: {e}")
    print(f"Successfully generated {count} PDFs across all submissions.")


if __name__ == "__main__":
    main()
