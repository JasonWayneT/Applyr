import os
import re
from markdown_pdf import MarkdownPdf, Section

SUBMISSIONS_DIR = "submissions"

def create_cl(folder_name):
    folder_path = os.path.join(SUBMISSIONS_DIR, folder_name)
    md_path = os.path.join(folder_path, "CoverLetter.md")
    pdf_path = os.path.join(folder_path, "CoverLetter.pdf")
    
    if not os.path.exists(folder_path):
        return

    # To convert folder_name to display name: e.g. onedigital_health -> OneDigital Health
    display_company = " ".join([word.capitalize() for word in folder_name.split("_")])
    if folder_name.lower() == "ge_healthcare":
        display_company = "GE Healthcare"
    elif folder_name.lower() == "case_iq":
        display_company = "Case IQ"
        
    cl_content = f"""<div style="font-size: 11pt; line-height: 1.15;">

<h1 style="margin: 0 0 8px 0; padding: 0; text-align: left; font-size: 16pt;"><strong>Jason Taylor</strong></h1>
<div style="text-align: left; margin-bottom: 20px;">
San Diego, CA | [REDACTED_PHONE] | [REDACTED_EMAIL] | linkedin.com/in/redacted-linkedin-slug
</div>

Dear Hiring Manager,

As a platform-focused Product Manager with over six years of experience in B2B SaaS, I have spent my career stabilizing and maintaining data-intensive systems that support revenue. I am drawn to {display_company} because of your mission to deliver best-in-class product experiences. My background in managing complex data ingestion pipelines, legacy platform modernization, and cross-functional alignment makes me a strong fit to own the core systems and integrations that power your platform.

At Cision, I managed the C3 platform and CPRE infrastructure, where I was responsible for the product roadmap and cross-functional alignment for a $40M ARR ecosystem. I operate at the intersection of business and engineering, having driven initiatives like "Bellwether"—an architectural bypass of legacy ETL pipelines that addressed a primary churn driver by improving data freshness. I am experienced in working with SQL and debugging complex system issues, which allows me to partner effectively with engineering teams to ship reliable solutions. My approach is pragmatic: I prioritize stability and data quality as foundational product features, ensuring that internal operations teams have the reliable tools they need to succeed.

I thrive in environments where I can translate technical constraints into clear product roadmaps. Whether it is resolving a 90% security backlog or consolidating fragmented content ingestion into a unified source of truth, I focus on reducing manual friction and improving system reliability. I understand the nuances of operating in complex environments and am eager to apply my experience in data architecture and platform ownership to help {display_company} scale its event intelligence capabilities.

I am interested in the opportunity to contribute to the {display_company} team and would welcome the chance to discuss how my experience in platform stability and data-intensive product management aligns with your goals for the core platform. Thank you for your time and consideration.

Sincerely,

Jason Taylor

</div>
"""

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(cl_content)
        
    try:
        pdf = MarkdownPdf(toc_level=0)
        pdf.add_section(Section(cl_content))
        pdf.save(pdf_path)
        print(f"Successfully generated high-quality Cover Letter for {folder_name}!")
    except Exception as e:
        print(f"Error compiling Cover Letter PDF for {folder_name}: {e}")

if __name__ == "__main__":
    if os.path.exists(SUBMISSIONS_DIR):
        for f in os.listdir(SUBMISSIONS_DIR):
            if os.path.isdir(os.path.join(SUBMISSIONS_DIR, f)):
                # If CoverLetter.md is missing or empty, generate it.
                md_path = os.path.join(SUBMISSIONS_DIR, f, "CoverLetter.md")
                if not os.path.exists(md_path) or os.path.getsize(md_path) == 0:
                    create_cl(f)
