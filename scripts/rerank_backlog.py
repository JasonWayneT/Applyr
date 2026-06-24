import sqlite3
import argparse
import sys
import json
from local_embeddings import get_embedding, cosine_similarity

DB_PATH = "data/jobagent.sqlite"

def rerank_backlog(query: str, threshold: float = 0.82):
    print(f"Generating query vector for: '{query}'...")
    query_vector = get_embedding(query)
    if not query_vector:
        print("Failed to generate query vector.")
        sys.exit(1)

    print("Connecting to database...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Fetch all jobs that have a vector
        cursor.execute("SELECT id, company, title, jd_vector, status FROM jobs WHERE jd_vector IS NOT NULL")
        rows = cursor.fetchall()
        
        matches = []
        for row in rows:
            job_id, company, title, vec_str, status = row
            try:
                job_vector = json.loads(vec_str)
                sim = cosine_similarity(query_vector, job_vector)
                if sim >= threshold:
                    matches.append((sim, job_id, company, title, status))
            except Exception:
                continue

        matches.sort(key=lambda x: x[0], reverse=True)
        
        print(f"\nFound {len(matches)} jobs matching query (Threshold: {threshold}):")
        print("-" * 80)
        
        resurrected = 0
        for sim, job_id, company, title, status in matches:
            print(f"[{sim:.3f}] {company} - {title} (Current Status: {status})")
            # If it was rejected or backlog, we could optionally resurrect it
            if status in ['Rejected', 'Archived', 'Backlog']:
                cursor.execute("UPDATE jobs SET status = 'New', score = 85 WHERE id = ?", (job_id,))
                resurrected += 1
                
        if resurrected > 0:
            print(f"\nResurrected {resurrected} previously rejected/archived jobs to 'New' status.")
            conn.commit()
            
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rerank and resurrect ATS backlog jobs using vector similarity.")
    parser.add_argument("query", help="The profile or niche you want to search for (e.g. 'Senior Product Manager B2B SaaS Platform')")
    parser.add_argument("--threshold", type=float, default=0.82, help="Cosine similarity threshold (default 0.82)")
    args = parser.parse_args()
    
    rerank_backlog(args.query, args.threshold)
