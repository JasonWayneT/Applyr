"""Re-evaluate a rejected job by DB id or queue index (JD-required queue)."""
import json
import sqlite3
import sys
from datetime import datetime, timedelta

PROJECT_ROOT = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))
sys.path.insert(0, __import__("os").path.join(PROJECT_ROOT, "scripts"))

from evaluate_jd_only import main as eval_main  # noqa: E402

PM = [
    "product manager", "product owner", "technical product manager",
    "platform product manager", "digital product manager", "senior product manager",
    "associate product manager", "lead product manager", "group product manager",
    "product management",
]


def categorize(job):
    s = (job.get("summary") or "").lower()
    score = job.get("score")
    if "duplicate" in s:
        return "duplicate_jd"
    if "keyword" in s or "title gate" in s or "zero-token" in s or "solo_pm" in s:
        return "zero_token_gate"
    if "on-site" in s or "onsite" in s or ("location" in s and "below" not in s):
        return "location_gate"
    if score == 28:
        return "llm_fit_score_28"
    if score is not None and score < 72:
        return "llm_fit_below_threshold"
    if score is None:
        return "rejected_null_score"
    return "other"


ORDER = [
    "llm_fit_score_28",
    "llm_fit_below_threshold",
    "location_gate",
    "zero_token_gate",
    "duplicate_jd",
    "other",
    "rejected_null_score",
]


def queue():
    cutoff = (datetime(2026, 6, 2) - timedelta(days=7)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(__import__("os").path.join(PROJECT_ROOT, "jobagent.sqlite"))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, company, title, score, pre_score, summary, jd_text, source_site, created_at
        FROM jobs WHERE status='Rejected' AND date(created_at) >= date(?)
          AND jd_text IS NOT NULL AND LENGTH(TRIM(jd_text)) >= 100
        ORDER BY created_at DESC
        """,
        (cutoff,),
    ).fetchall()
    conn.close()
    out = [dict(r) for r in rows if any(p in (r["title"] or "").lower() for p in PM)]
    for j in out:
        j["category"] = categorize(j)
    out.sort(key=lambda j: (ORDER.index(j["category"]) if j["category"] in ORDER else 99, j.get("created_at") or ""))
    return out


if __name__ == "__main__":
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    jobs = queue()
    if idx < 1 or idx > len(jobs):
        print(json.dumps({"error": f"index {idx} out of range 1-{len(jobs)}"}))
        sys.exit(2)
    job = jobs[idx - 1]
    path = __import__("os").path.join(PROJECT_ROOT, "data", "debug_review_current.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"Title: {job['title']}\nCompany: {job['company']}\n\n")
        f.write(job["jd_text"] or "")
    print(json.dumps({
        "queue_index": idx,
        "queue_total": len(jobs),
        "id": job["id"],
        "company": job["company"],
        "title": job["title"],
        "db_score": job["score"],
        "db_pre_score": job["pre_score"],
        "db_summary": job["summary"],
        "category": job.get("category"),
        "source": job.get("source_site"),
    }, indent=2))
    sys.argv = ["evaluate_jd_only.py", path, job["company"]]
    eval_main()
