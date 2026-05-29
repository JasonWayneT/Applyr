import json
import os
import sqlite3

from local_embeddings import get_embedding, cosine_similarity

STANDARD_TAGS = [
    "HealthTech", "FinTech", "Remote", "Senior", "Machine Learning",
    "Data Engineering", "Product Management", "Cybersecurity", "Startup", "B2B SaaS"
]

_TAG_VECTORS: dict[str, list] | None = None


def _tag_vectors() -> dict[str, list]:
    global _TAG_VECTORS
    if _TAG_VECTORS is None:
        _TAG_VECTORS = {}
        for tag in STANDARD_TAGS:
            vec = get_embedding(tag)
            if vec:
                _TAG_VECTORS[tag] = vec
    return _TAG_VECTORS


def tag_job_metadata(db_path: str, job_id_prefix: str, company_name: str, jd_text: str):
    """
    Rapid Metadata Tagging using Cosine Similarity.
    Matches the JD text against standard tags using local vector math.
    """
    try:
        if os.environ.get("SKIP_METADATA_TAGGER", "").lower() in ("1", "true", "yes"):
            return
        try:
            from pipeline_env import skip_metadata_tagger
            if skip_metadata_tagger():
                return
        except ImportError:
            pass

        if not jd_text or len(jd_text) < 100:
            return

        jd_vector = get_embedding(jd_text[:1500])
        if not jd_vector:
            return

        applied_tags = []
        for tag, tag_vec in _tag_vectors().items():
            if cosine_similarity(jd_vector, tag_vec) > 0.45:
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
