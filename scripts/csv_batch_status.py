"""Summarize status for CSV-imported companies."""
import os
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite")

COMPANIES = [
    "Ladders", "CentralSquare Technologies", "OptionMetrics", "MeridianLink",
    "Justrite Safety Group", "Cast & Crew", "FedEx Dataworks", "Solv.",
    "BRG", "Ad Hoc LLC", "Forbes", "Cart.com", "Trustpoint.One", "Bullhorn",
    "Edmunds", "Fabletics", "Fixify", "Noodle", "Velera", "Fingercheck",
]

def main():
    conn = sqlite3.connect(DB)
    print("=== CSV BATCH RESULTS ===\n")
    for co in COMPANIES:
        rows = conn.execute(
            "SELECT status, score, substr(COALESCE(summary,''),1,70) FROM jobs "
            "WHERE company = ? OR LOWER(company) = LOWER(?) ORDER BY score DESC",
            (co, co),
        ).fetchall()
        if not rows:
            print(f"  {co}: NOT FOUND")
            continue
        for status, score, summary in rows:
            print(f"  {co}: {status} | score={score} | {summary}")
    print("\n=== COUNTS ===")
    for status, n in conn.execute(
        "SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY COUNT(*) DESC"
    ):
        print(f"  {status}: {n}")
    conn.close()

if __name__ == "__main__":
    main()
