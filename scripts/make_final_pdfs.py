"""
Generates PDFs for all .md files across all submission folders.
Reads dynamically from submissions/ directory instead of a hardcoded list.
"""
import os
import json
import shutil
from markdown_pdf import MarkdownPdf, Section
from utils import SUBMISSIONS_DIR, JOBS_DIR, DB_FILE


def generate_pdf(markdown_text, output_path):
    pdf = MarkdownPdf(toc_level=0)
    pdf.add_section(Section(markdown_text))
    pdf.save(output_path)


def main(status_filter=None):
    """
    Generate PDFs for all submissions, optionally filtered by status.
    If status_filter is provided (e.g. "Drafted"), only process jobs with that status.
    """
    # Load database to get status info
    db = {}
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            db = json.load(f)

    # Build a set of folder paths for filtered statuses
    target_folders = set()
    if status_filter and db:
        for job_id, job in db.items():
            if job['status'].startswith(status_filter) and job.get('folder_path'):
                target_folders.add(os.path.basename(job['folder_path']))
    
    if not os.path.exists(SUBMISSIONS_DIR):
        print(f"Submissions directory not found: {SUBMISSIONS_DIR}")
        return

    processed = 0
    for folder_name in os.listdir(SUBMISSIONS_DIR):
        folder_path = os.path.join(SUBMISSIONS_DIR, folder_name)
        if not os.path.isdir(folder_path):
            continue

        # Apply filter if set
        if status_filter and target_folders and folder_name not in target_folders:
            continue

        for file_name in os.listdir(folder_path):
            if file_name.endswith('.md'):
                md_path = os.path.join(folder_path, file_name)
                pdf_path = os.path.join(folder_path, file_name.replace('.md', '.pdf'))
                try:
                    with open(md_path, 'r', encoding='utf-8') as f:
                        generate_pdf(f.read(), pdf_path)
                    processed += 1
                except Exception as e:
                    print(f"Error generating PDF for {md_path}: {e}")

    print(f"Generated {processed} PDFs across submissions.")


if __name__ == "__main__":
    import sys
    # Optional: pass a status filter as an argument
    # Usage: python make_final_pdfs.py [Drafted|Applied|...]
    filt = sys.argv[1] if len(sys.argv) > 1 else None
    main(status_filter=filt)
