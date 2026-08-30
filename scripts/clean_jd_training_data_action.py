#!/usr/bin/env python3
"""
Clean JD training data by removing obvious outliers and noisy short lines.
Outputs to data/training_data_clean.csv
"""

import csv
import re
from pathlib import Path
from collections import defaultdict

_REPO_ROOT = Path(__file__).parent.parent
_INPUT_CSV = _REPO_ROOT / "data" / "training_data_raw.csv"
_OUTPUT_CSV = _REPO_ROOT / "data" / "training_data_clean.csv"

def is_benefit_noise(text, label):
    if label == "culture":
        return False
    
    text_lower = text.lower()
    culture_keywords = ["401k", "401(k)", "pto", "paid time off", "dental", "health insurance", "benefits package", "commuter benefits", "parental leave", "unlimited vacation"]
    return any(k in text_lower for k in culture_keywords)

def main():
    cleaned_dataset = []
    dropped = 0
    
    with open(_INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row["text"]
            label = row["label"]
            
            words = len(re.findall(r"\w+", text))
            
            # Rule 1: Drop very short lines (mostly stray headers like "Required Skills:")
            if words < 5:
                dropped += 1
                continue
                
            # Rule 2: Drop lines in non-culture buckets that talk about explicit benefits
            if is_benefit_noise(text, label):
                dropped += 1
                continue
                
            # Rule 3: Drop culture lines that explicitly mandate requirements
            if label == "culture" and any(k in text.lower() for k in ["years of experience", "bachelor's", "master's"]):
                dropped += 1
                continue

            cleaned_dataset.append(row)
            
    print(f"Cleaned dataset: kept {len(cleaned_dataset)} items, dropped {dropped} outliers.")
    
    stats = defaultdict(int)
    for row in cleaned_dataset:
        stats[row['label']] += 1
    
    for bucket, count in stats.items():
        print(f"  {bucket}: {count}")

    with open(_OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label", "company", "source_file"])
        writer.writeheader()
        writer.writerows(cleaned_dataset)
        
    print(f"\nSaved cleaned dataset to: {_OUTPUT_CSV.relative_to(_REPO_ROOT)}")

if __name__ == "__main__":
    main()
