import os
from markdown_pdf import MarkdownPdf, Section

def make_cl(company):
    folder = os.path.join("submissions", company)
    os.makedirs(folder, exist_ok=True)
    
    cl_text = f"""# Cover Letter

Dear Hiring Team at {company},

I am writing to express my strong interest in the Product Manager role. With over 6 years of experience in product management, B2B enterprise workflow scaling, and technical integrations, I have a proven track record of delivering high-impact solutions in regulated and structured environments.

I look forward to discussing how my background aligns with your team's current goals.

Sincerely,
Jason Taylor
"""
    
    md_path = os.path.join(folder, "CoverLetter.md")
    pdf_path = os.path.join(folder, "CoverLetter.pdf")
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(cl_text)
        
    pdf = MarkdownPdf(toc_level=0)
    pdf.add_section(Section(cl_text))
    pdf.save(pdf_path)
    print(f"Directly generated CoverLetter.md and CoverLetter.pdf for {company}")

for f in ["case_iq"]:
    make_cl(f)
