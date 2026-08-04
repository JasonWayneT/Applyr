# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""List PM rejections (7 days) that have JD text — review queue."""
import json
import sqlite3
from datetime import datetime, timedelta

cutoff = (datetime(2026, 6, 2) - timedelta(days=7)).strftime("%Y-%m-%d")
PM = [
    "product manager", "product owner", "technical product manager",
    "platform product manager", "digital product manager", "senior product manager",
    "associate product manager", "lead product manager", "group product manager",
    "product management",
]


def looks_pm(title):
    t = (title or "").lower()
    return any(p in t for p in PM)


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

conn = sqlite3.connect("data/jobagent.sqlite")
conn.row_factory = sqlite3.Row
rows = conn.execute(
    """
  SELECT id, company, title, url, score, pre_score, summary, source_site,
         created_at, LENGTH(jd_text) AS jd_len
  FROM jobs
  WHERE status = 'Rejected'
    AND date(created_at) >= date(?)
    AND jd_text IS NOT NULL
    AND LENGTH(TRIM(jd_text)) >= 100
  ORDER BY created_at DESC
""",
    (cutoff,),
).fetchall()
conn.close()

queue = []
for r in rows:
    if not looks_pm(r["title"]):
        continue
    j = dict(r)
    j["category"] = categorize(j)
    queue.append(j)

queue.sort(key=lambda j: (ORDER.index(j["category"]) if j["category"] in ORDER else 99, j.get("created_at") or ""))

by_cat = {}
for j in queue:
    by_cat[j["category"]] = by_cat.get(j["category"], 0) + 1
print(json.dumps({"count": len(queue), "by_category": by_cat}, indent=2))
for i, j in enumerate(queue, 1):
    print(f"{i:3}. [{j['category']}] {j['company']} — {j['title']} (score={j['score']}, jd={j['jd_len']})")
