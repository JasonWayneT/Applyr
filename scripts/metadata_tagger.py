import json
import sqlite3
import numpy as np
from local_embeddings import get_embedding, cosine_similarity

# Define a set of standard tags and pre-compute their vectors (in reality, we compute on first run)
STANDARD_TAGS = [
    "HealthTech", "FinTech", "Remote", "Senior", "Machine Learning",
    "Data Engineering", "Product Management", "Cybersecurity", "Startup", "B2B SaaS"
]

def tag_job_metadata(db_path: str, job_id_prefix: str, company_name: str, jd_text: str):
    """
    Rapid Metadata Tagging using Cosine Similarity.
    Matches the JD text against standard tags using local vector math.
    """
    try:
        if not jd_text or len(jd_text) < 100:
            return
        
        # Get vector for JD
        jd_vector = get_embedding(jd_text[:1500])
        if not jd_vector:
            return
            
        applied_tags = []
        # In a real heavy implementation, tag vectors would be cached
        for tag in STANDARD_TAGS:
            tag_vec = get_embedding(tag)
            if tag_vec and cosine_similarity(jd_vector, tag_vec) > 0.45: # Tuned threshold
                applied_tags.append(tag)
                
        if applied_tags:
            conn = sqlite3.connect(db_path, timeout=30.0)
            cursor = conn.cursor()
            tags_json = json.dumps(applied_tags)
            if job_id_prefix:
                cursor.execute("UPDATE jobs SET metadata_tags = ? WHERE id LIKE ?", (tags_json, f"{job_id_prefix}%"))
            else:
                cursor.execute("UPDATE jobs SET metadata_tags = ? WHERE LOWER(company) = LOWER(?)", (tags_json, company_name))
            conn.commit()
            conn.close()
            print(f"    [TAGGER] Applied tags: {', '.join(applied_tags)}")
            
    except Exception as e:
        print(f"    [TAGGER ERROR] {e}")

if __name__ == "__main__":
    pass
