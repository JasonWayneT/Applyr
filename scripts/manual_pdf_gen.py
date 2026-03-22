import os
from markdown_pdf import MarkdownPdf, Section

def generate_pdf(md_path, pdf_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()
    
    pdf = MarkdownPdf(toc_level=0)
    pdf.add_section(Section(md_text))
    pdf.save(pdf_path)

submissions_dir = 'submissions'
for folder_name in os.listdir(submissions_dir):
    folder_path = os.path.join(submissions_dir, folder_name)
    if os.path.isdir(folder_path):
        for file_name in os.listdir(folder_path):
            if file_name.endswith('.md'):
                md_path = os.path.join(folder_path, file_name)
                pdf_path = os.path.join(folder_path, file_name.replace('.md', '.pdf'))
                generate_pdf(md_path, pdf_path)
print("Successfully generated PDFs for all submissions.")
