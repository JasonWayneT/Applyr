import os
from markdown_pdf import MarkdownPdf, Section

SUBMISSIONS_DIR = "submissions"

def recreate_resume(folder_name):
    folder_path = os.path.join(SUBMISSIONS_DIR, folder_name)
    md_path = os.path.join(folder_path, "Resume.md")
    pdf_path = os.path.join(folder_path, "Resume.pdf")
    
    if not os.path.exists(folder_path):
        return

    # Clean display name conversion
    display_company = " ".join([word.capitalize() for word in folder_name.split("_")])
    if folder_name.lower() == "ge_healthcare":
        display_company = "GE Healthcare"

    resume_content = f"""<div style="font-size: 11pt; line-height: 1.25;">

<h1 style="margin: 0; padding: 0; font-size: 16pt;"><strong>Jason Taylor</strong></h1>
San Diego, CA | [REDACTED_PHONE] | [REDACTED_EMAIL] | linkedin.com/in/redacted-linkedin-slug

<h2 style="margin: 12px 0 6px 0; padding: 0; font-size: 12pt;"><strong>PROFESSIONAL SUMMARY</strong></h2>
High-impact Product Manager with 6+ years of experience specializing in platform stability, legacy system modernization, and B2B SaaS optimization. Proven success driving complex technical roadmaps, aligning engineering squads with business objectives, and optimizing data integrity and internal workflows to maximize enterprise value.

<h2 style="margin: 12px 0 6px 0; padding: 0; font-size: 12pt;"><strong>PROFESSIONAL EXPERIENCE</strong></h2>

<h3 style="margin: 6px 0 2px 0; padding: 0; font-size: 11pt;"><strong>Product Manager</strong></h3>
Cision | September 2021 - January 2026

* Managed the end-to-end product strategy and roadmap for Legacy C3 and CPRE platforms, serving over 3,500 active accounts and generating $40M ARR.
* Led the Bellwether initiative (an architectural data integration that bypassed legacy ETL pipelines), which eliminated 30-40% contact data loss.
* Built direct integrations between GPOD (contact source of truth database) and C3 (customer platform) to ensure data freshness and minimize systemic churn.
* Designed and executed voluntary, phased migration tooling to support safe, retention-focused transitions to newer platforms.
* Guided cross-functional alignment across 15+ software engineers, DBAs, and DevOps to reduce a 300-item security backlog by 90%.
* Supervised the secure ingestion and indexing of premium content data partners such as LexisNexis to improve core enterprise features.

<h3 style="margin: 8px 0 2px 0; padding: 0; font-size: 11pt;"><strong>Product Manager</strong></h3>
Sterkly Services | February 2019 - August 2021

* Led modernization initiatives across internal operations platforms, resolving legacy architectural bottlenecks to unblock development teams.
* Facilitated structured requirements workshops with executive leaders and account managers to turn complex strategies into actionable engineering tasks.
* Partnered with agile engineering teams to validate early technical feasibility, reducing rework and increasing total product delivery throughput.
* Developed new workflow automation processes that streamlined customer data processing and minimized manual overhead.

<h3 style="margin: 8px 0 2px 0; padding: 0; font-size: 11pt;"><strong>Account Manager / Product Owner</strong></h3>
Zero To Sixty Media | June 2017 - January 2019

* Co-created and launched automated onboarding and client lifecycle tools that directly increased delivery capacity and client retention.
* Streamlined a comprehensive laptop fulfillment program handling ~$288,000 in contracts, building automation that saved $8,500 per quarter.
* Formed partnerships with executives, account teams, and developers to build custom Salesforce integrations, saving $22,100 annually in processing overhead.

<h2 style="margin: 12px 0 6px 0; padding: 0; font-size: 12pt;"><strong>EDUCATION</strong></h2>
Bachelor of Business Administration | National University

</div>
"""

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(resume_content)
        
    try:
        pdf = MarkdownPdf(toc_level=0)
        pdf.add_section(Section(resume_content))
        pdf.save(pdf_path)
        print(f"Successfully generated high-quality Resume for {folder_name}!")
    except Exception as e:
        print(f"Error compiling Resume PDF for {folder_name}: {e}")

if __name__ == "__main__":
    if os.path.exists(SUBMISSIONS_DIR):
        for f in os.listdir(SUBMISSIONS_DIR):
            if os.path.isdir(os.path.join(SUBMISSIONS_DIR, f)):
                recreate_resume(f)
