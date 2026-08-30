#!/usr/bin/env python3
"""
Harvest job description lines from previously processed stage0_fit_gate.json
files across data/submissions and data/archive to build a training dataset
for the NLP classifier.

Outputs to data/training_data_raw.csv
"""

import json
import csv
import os
from pathlib import Path
from collections import defaultdict

_REPO_ROOT = Path(__file__).parent.parent
_DATA_DIR = _REPO_ROOT / "data"
_OUTPUT_CSV = _DATA_DIR / "training_data_raw.csv"

def extract_text(item):
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict) and "item" in item:
        return item["item"].strip()
    return None

def main():
    print("Harvesting JD lines from stage0_fit_gate.json files...")
    
    # We look in submissions, archive, and context_pack_validation
    search_dirs = [
        _DATA_DIR / "submissions",
        _DATA_DIR / "archive",
        _DATA_DIR / "context_pack_validation",
        _DATA_DIR / "pending_review"
    ]
    
    dataset = []
    stats = defaultdict(int)
    
    for directory in search_dirs:
        if not directory.exists():
            continue
            
        for path in directory.rglob("stage0_fit_gate.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Error reading {path}: {e}")
                continue
                
            company = data.get("company", "Unknown")
            
            # Buckets to extract
            buckets = ["required", "preferred", "responsibilities", "culture"]
            
            for bucket in buckets:
                items = data.get(bucket) or []
                for item in items:
                    text = extract_text(item)
                    if not text:
                        continue
                        
                    # Basic deduplication constraint: ignore empty strings or extremely short lines
                    if len(text) < 10:
                        continue
                        
                    dataset.append({
                        "text": text,
                        "label": bucket,
                        "company": company,
                        "source_file": str(path.relative_to(_REPO_ROOT))
                    })
                    stats[bucket] += 1

    # Remove duplicates (sometimes JDs have duplicate bullet points)
    unique_dataset = []
    seen = set()
    for row in dataset:
        if row["text"] not in seen:
            seen.add(row["text"])
            unique_dataset.append(row)

    print(f"Total unique items harvested: {len(unique_dataset)}")
    for bucket, count in stats.items():
        print(f"  {bucket}: {count}")

    with open(_OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label", "company", "source_file"])
        writer.writeheader()
        writer.writerows(unique_dataset)
        
    print(f"\nSaved raw dataset to: {_OUTPUT_CSV.relative_to(_REPO_ROOT)}")

if __name__ == "__main__":
    main()
