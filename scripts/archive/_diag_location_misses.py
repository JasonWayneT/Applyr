#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""One-off diagnostic: location-related self-rejects scored >=72."""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(__file__))
from zero_shot_classifier import classify_onsite, resolve_location_verdict

DB = os.path.join(os.path.dirname(__file__), "..", "data", "jobagent.sqlite")

def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT company, title, score, outcome_notes, jd_text
        FROM jobs
        WHERE rejection_type='Self-Rejected' AND score >= 72
        ORDER BY score DESC
        """
    ).fetchall()
    loc_rows = [
        r for r in rows
        if r["outcome_notes"]
        and any(
            k in (r["outcome_notes"] or "").lower()
            for k in (
                "location", "hybrid", "onsite", "on-site", "on site",
                "remote", "canada", "nyc", "new york", "chicago", "san francisco",
                "in-person", "in person", "not remote",
            )
        )
    ]
    print(f"location-related self-rejects: {len(loc_rows)}")
    for r in loc_rows[:20]:
        jd = r["jd_text"] or ""
        verdict, detail = resolve_location_verdict(jd)
        reject, reason = classify_onsite(jd)
        print("---")
        print(r["company"], "|", r["title"], "|", r["score"])
        print("notes:", (r["outcome_notes"] or "")[:120])
        print(f"verdict={verdict} reject={reject} detail={detail[:80]!r}")
        print(f"jd_len={len(jd)}")

if __name__ == "__main__":
    main()
