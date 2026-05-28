import sqlite3
import argparse
import sys

def prune_stale_data(db_path: str, days_old: int = 45):
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # We null out jd_text and jd_vector for old Rejected jobs to save space, but keep the metadata.
        print(f"Pruning jd_text and jd_vector for jobs older than {days_old} days...")
        
        cursor.execute(f"""
            UPDATE jobs 
            SET jd_text = NULL, jd_vector = NULL
            WHERE status IN ('Rejected', 'Archived', 'Closed', 'No Longer Available')
            AND created_at < datetime('now', '-{days_old} days')
            AND jd_vector IS NOT NULL
        """)
        
        affected = cursor.rowcount
        conn.commit()
        
        if affected > 0:
            print(f"Cleared heavy blob data for {affected} stale jobs.")
            print("Vacuuming database to reclaim space...")
            cursor.execute("VACUUM")
            conn.commit()
            print("Vacuum complete.")
        else:
            print("No stale blobs found to prune.")
            
        conn.close()
    except Exception as e:
        print(f"Failed to prune database: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-prune stale JD blobs to keep DB lightweight.")
    parser.add_argument("--db", default="jobagent.sqlite", help="Path to SQLite DB")
    parser.add_argument("--days", type=int, default=45, help="Age in days to consider stale")
    args = parser.parse_args()
    
    prune_stale_data(args.db, args.days)
