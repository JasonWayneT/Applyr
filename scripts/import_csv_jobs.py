import csv
import os
import sqlite3
import uuid
import re

def get_id():
    return uuid.uuid4().hex[:8]

def sanitize_filename(name):
    # Remove special chars, spaces to underscores
    return re.sub(r'[\W_]+', '_', name).strip('_')

def import_jobs():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jobagent.sqlite")
    jobs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jobs")
    os.makedirs(jobs_dir, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    csv1_path = 'C:/Users/Jason/Downloads/Job Evaluation 1 - Sheet1 (1).csv'
    csv2_path = 'C:/Users/Jason/Downloads/Job Evaluation 2 - Sheet1.csv'
    
    imported_count = 0
    
    # Load and process CSV 1 (Company,Position,URL,Job Description)
    if os.path.exists(csv1_path):
        print(f"Processing {csv1_path}...")
        with open(csv1_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                company = row.get('Company', '').strip()
                position = row.get('Position', '').strip()
                url = row.get('URL', '').strip()
                jd = row.get('Job Description', '').strip()
                
                if not company or not jd:
                    continue
                    
                if not url:
                    url = f"local://{sanitize_filename(company)}_{get_id()}"
                    
                # Check uniqueness in DB
                cursor.execute("SELECT id FROM jobs WHERE url = ?", (url,))
                if cursor.fetchone():
                    continue
                    
                job_id = get_id()
                
                # Insert into SQLite
                try:
                    cursor.execute(
                        "INSERT INTO jobs (id, company, title, url, status) VALUES (?, ?, ?, ?, 'New')",
                        (job_id, company, position, url)
                    )
                    
                    # Write TXT file
                    slug = sanitize_filename(company)
                    txt_filename = f"{slug}_{job_id}.txt"
                    with open(os.path.join(jobs_dir, txt_filename), 'w', encoding='utf-8') as jf:
                        jf.write(jd)
                        
                    imported_count += 1
                except sqlite3.IntegrityError:
                    pass # Already exists
                    
    # Load and process CSV 2 (Company,Position,Job Description)
    if os.path.exists(csv2_path):
        print(f"Processing {csv2_path}...")
        with open(csv2_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                company = row.get('Company', '').strip()
                position = row.get('Position', '').strip()
                jd = row.get('Job Description', '').strip()
                
                if not company or not jd:
                    continue
                    
                job_id = get_id()
                url = f"local://{sanitize_filename(company)}_{job_id}"
                
                # Insert into SQLite
                try:
                    cursor.execute(
                        "INSERT INTO jobs (id, company, title, url, status) VALUES (?, ?, ?, ?, 'New')",
                        (job_id, company, position, url)
                    )
                    
                    # Write TXT file
                    slug = sanitize_filename(company)
                    txt_filename = f"{slug}_{job_id}.txt"
                    with open(os.path.join(jobs_dir, txt_filename), 'w', encoding='utf-8') as jf:
                        jf.write(jd)
                        
                    imported_count += 1
                except sqlite3.IntegrityError:
                    pass # Already exists
                    
    conn.commit()
    conn.close()
    print(f"Successfully imported {imported_count} new jobs into the pipeline.")

if __name__ == "__main__":
    import_jobs()
