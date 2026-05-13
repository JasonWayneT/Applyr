import os
import shutil
import datetime
import sqlite3

def get_timestamp():
    return datetime.datetime.now().strftime("%Y_%m_%d_%H%M%S")

def archive_folder(company_slug):
    submissions_dir = "c:/Users/Jason/Desktop/Jason/Resource/CodeProjects/JobAgent/submissions"
    archive_dir = "c:/Users/Jason/Desktop/Jason/Resource/CodeProjects/JobAgent/archive/submissions"
    
    source_path = os.path.join(submissions_dir, company_slug)
    target_path = os.path.join(archive_dir, company_slug)
    
    if not os.path.exists(source_path):
        print(f"[Notice] Folder '{source_path}' does not exist. Skipping folder move.")
        return False
        
    os.makedirs(archive_dir, exist_ok=True)
    
    if os.path.exists(target_path):
        # Target already exists, create a backup of the archived folder first to avoid collision
        backup_target = f"{target_path}_backup_{get_timestamp()}"
        print(f"[Archive] Destination '{target_path}' already exists. Backing it up to '{backup_target}'")
        shutil.move(target_path, backup_target)
        
    # Move the active folder to the archive
    print(f"[Archive] Moving '{source_path}' to '{target_path}'")
    shutil.move(source_path, target_path)
    return True

def update_db_status(company_name):
    db_path = "c:/Users/Jason/Desktop/Jason/Resource/CodeProjects/JobAgent/jobagent.sqlite"
    if not os.path.exists(db_path):
        print("[Error] Database file not found.")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Find records matching
    cursor.execute("SELECT id, title, status FROM jobs WHERE LOWER(company) = LOWER(?)", (company_name,))
    rows = cursor.fetchall()
    
    if not rows:
        print(f"[DB] No job matching company '{company_name}' found.")
        conn.close()
        return
        
    for row in rows:
        job_id, title, current_status = row
        print(f"[DB] Updating '{company_name}' ({title}) from '{current_status}' to 'Applied'.")
        cursor.execute("UPDATE jobs SET status = 'Applied' WHERE id = ?", (job_id,))
        
    conn.commit()
    conn.close()

def print_pipeline_summary():
    db_path = "c:/Users/Jason/Desktop/Jason/Resource/CodeProjects/JobAgent/jobagent.sqlite"
    if not os.path.exists(db_path):
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n=== Pipeline Current Status ===")
    
    # Counts by status
    cursor.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status")
    counts = cursor.fetchall()
    print("Counts by Status:")
    for status, count in counts:
        print(f"  - {status}: {count}")
        
    # Recently added/updated New & Drafted items
    cursor.execute("SELECT company, title, score, status, created_at FROM jobs WHERE status IN ('New', 'Backlog') ORDER BY created_at DESC LIMIT 5")
    recent = cursor.fetchall()
    
    if recent:
        print("\nTop Recent Actionable Pipeline Items (New / Backlog):")
        for company, title, score, status, date in recent:
            score_str = f"Score: {score}" if score else "Unscored"
            print(f"  - {company} | {title} | {status} ({score_str})")
            
    conn.close()

def main():
    # 1. Archive auxilius
    print("--- Archiving Auxilius ---")
    moved_aux = archive_folder("auxilius")
    update_db_status("Auxilius")
    
    # 2. Archive softserve
    print("\n--- Archiving Softserve ---")
    moved_soft = archive_folder("softserve")
    update_db_status("Softserve")
    
    # 3. Print pipeline update
    print_pipeline_summary()

if __name__ == "__main__":
    main()
