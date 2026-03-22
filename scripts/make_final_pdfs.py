import os
import glob
import shutil
import json
from markdown_pdf import MarkdownPdf, Section

COMPANIES = [
    "Panorama Education - Product Manager",
    "Perceptyx - Product Manager",
    "Coinbase - Product Manager"
]

def generate_pdf(markdown_text, output_path):
    pdf = MarkdownPdf(toc_level=0)
    pdf.add_section(Section(markdown_text))
    pdf.save(output_path)

def main():
    for company_name in COMPANIES:
        folder_name = company_name.lower().replace(" ", "_")
        folder_path = os.path.join("submissions", folder_name)
        
        # Ensure the folder exists
        os.makedirs(folder_path, exist_ok=True)
        
        # 1. Copy Original JD
        jd_path = f"processed_jobs/{company_name}.txt"
        if not os.path.exists(jd_path):
            jd_path = f"jobs/{company_name}.txt"
            
        if os.path.exists(jd_path):
            shutil.copy(jd_path, os.path.join(folder_path, "Original_JD.txt"))
            
        # 2. Touch Research Packet
        research_path = os.path.join(folder_path, "Research_Packet.json")
        if not os.path.exists(research_path):
            with open(research_path, "w") as f:
                json.dump({}, f)
                
        # 3. Convert MD to PDF
        resume_md = os.path.join(folder_path, "Resume.md")
        resume_pdf = os.path.join(folder_path, "Resume.pdf")
        if os.path.exists(resume_md):
            with open(resume_md, "r", encoding="utf-8") as f:
                generate_pdf(f.read(), resume_pdf)
                
        cl_md = os.path.join(folder_path, "CoverLetter.md")
        cl_pdf = os.path.join(folder_path, "CoverLetter.pdf")
        if os.path.exists(cl_md):
            with open(cl_md, "r", encoding="utf-8") as f:
                generate_pdf(f.read(), cl_pdf)
                
        print(f"Generated PDFs for {company_name}")

if __name__ == "__main__":
    main()
