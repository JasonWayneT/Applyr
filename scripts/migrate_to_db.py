import os
import json
import re

SUBMISSIONS_DIR = "submissions"
DATA_DIR = "data"
DB_FILE = os.path.join(DATA_DIR, "job_database.json")
LOG_FILE = os.path.join(DATA_DIR, "scouted_jobs_log.txt")

def get_job_info(folder_path):
    company = os.path.basename(folder_path).replace('_', ' ').title()
    title = "Product Manager"
    url = "#"
    
    metadata_path = os.path.join(folder_path, 'metadata.json')
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            meta = json.load(f)
            url = meta.get('source_url', '#')
            title = meta.get('title', title)
    
    packet_path = os.path.join(folder_path, 'Research_Packet.md')
    if os.path.exists(packet_path):
        with open(packet_path, 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'## Role:\s*(.*)', content)
            if match:
                title = match.group(1).strip()
            
            match_comp = re.search(r'# Research Packet:\s*(.*)\s*\(v2.0\)', content)
            if match_comp:
                company = match_comp.group(1).strip()

    return company, title, url

def migrate():
    db = {}
    
    # 1. Migrate from Submissions (Already Evaluated/Drafted)
    if os.path.exists(SUBMISSIONS_DIR):
        folders = [f for f in os.listdir(SUBMISSIONS_DIR) if os.path.isdir(os.path.join(SUBMISSIONS_DIR, f))]
        for folder in folders:
            folder_path = os.path.join(SUBMISSIONS_DIR, folder)
            company, title, url = get_job_info(folder_path)
            
            job_key = f"{company} - {title}"
            db[job_key] = {
                "company": company,
                "title": title,
                "url": url,
                "status": "Drafted",  # Assume drafted since it's in submissions
                "folder_path": folder_path,
                "score": 0 # We'd need to parse this from a log if available
            }
            print(f"Migrated submission: {job_key}")

    # 2. Sync with Log File (Scouted jobs)
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            for line in f:
                job_id = line.strip()
                if not job_id: continue
                
                if job_id not in db:
                    # Parse company and title if possible, else use ID
                    parts = job_id.split(' - ', 1)
                    company = parts[0] if len(parts) > 1 else job_id
                    title = parts[1] if len(parts) > 1 else "Product Manager"
                    
                    db[job_id] = {
                        "company": company,
                        "title": title,
                        "url": "#",
                        "status": "Scouted",
                        "folder_path": None,
                        "score": 0
                    }
                    print(f"Logged scouted job: {job_id}")

    # 3. Save to DB
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4)
    print(f"\nMigration complete. Database saved to {DB_FILE}")

if __name__ == "__main__":
    migrate()
