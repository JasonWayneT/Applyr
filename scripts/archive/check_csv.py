# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import csv
import sys

for path in ['C:/Users/Jason/Downloads/Job Evaluation 1 - Sheet1 (1).csv', 'C:/Users/Jason/Downloads/Job Evaluation 2 - Sheet1.csv']:
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            rows = list(reader)
            print(f"{path}: {len(rows)} rows total (including header).")
            if len(rows) > 1:
                print(f"  Header: {rows[0]}")
                print(f"  First Data Row sample: {rows[1][0]}, {rows[1][1]}")
    except Exception as e:
        print(f"Error reading {path}: {e}")
