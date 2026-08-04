# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Extract CSV jobs for Stage 0 screening."""
import csv
import json
import re
from pathlib import Path

paths = [
    Path(r"C:\Users\Jason\Downloads\applyr_jobs (1).csv"),
    Path(r"C:\Users\Jason\Downloads\applyr_jobs (2).csv"),
]
jobs = []
for p in paths:
    with p.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            jobs.append(
                {
                    "source": p.name,
                    "company": (row.get("Company") or "").strip(),
                    "position": (row.get("Position") or "").strip(),
                    "jd": row.get("Job Description") or "",
                    "url": (row.get("URL") or "").strip(),
                }
            )

out = Path(__file__).resolve().parent.parent / "data" / "_tmp_stage0_batch.json"
out.write_text(json.dumps(jobs, indent=2), encoding="utf-8")
print(f"total={len(jobs)}")
for i, j in enumerate(jobs):
    print(f"{i+1:02d}. [{j['source']}] {j['company']} — {j['position']} ({len(j['jd'])} chars)")

# Print requirement-ish sections for each job (heuristic slices)
keywords = [
    r"requirement",
    r"qualificat",
    r"you.?ll need",
    r"we.?re looking",
    r"looking for",
    r"must have",
    r"minimum",
    r"years of",
    r"0.?1",
    r"0.?to.?1",
    r"greenfield",
    r"founding",
    r"travel",
    r"direct report",
    r"people manag",
    r"billing",
    r"payment",
    r"machine learning",
    r"\bAI/?ML\b",
    r"predictive",
    r"onsite",
    r"on-site",
    r"hybrid",
    r"remote",
    r"clearance",
    r"automotive",
    r"healthcare",
    r"FHIR",
    r"HIPAA",
]

print("\n=== SIGNAL HITS ===")
for i, j in enumerate(jobs):
    jd = j["jd"]
    jd_l = jd.lower()
    hits = []
    for pat in keywords:
        if re.search(pat, jd_l, re.I):
            hits.append(pat)
    # years mentions
    years = re.findall(r".{0,40}\d+\s*[–\-to]+\s*\d+\s*years?.{0,40}|.{0,40}\d+\+?\s*years?.{0,40}", jd, re.I)
    print(f"\n--- {i+1}. {j['company']} / {j['position']} ---")
    print("signals:", ", ".join(hits) if hits else "(none)")
    for y in years[:6]:
        print("  years:", " ".join(y.split()))
    # thin JD?
    print(f"  len={len(jd)} thin={len(jd) < 800}")
