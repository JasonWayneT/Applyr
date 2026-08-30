#!/usr/bin/env python3
"""
Automated sanity check for JD training data.
Reads data/training_data_raw.csv and flags potential outliers based on heuristic rules.
"""

import csv
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_INPUT_CSV = _REPO_ROOT / "data" / "training_data_raw.csv"

def is_likely_culture(text):
    text_lower = text.lower()
    culture_keywords = ["401k", "401(k)", "pto", "paid time off", "dental", "vision", "health insurance", "benefits package", "commuter benefits", "equity", "stock options", "parental leave", "unlimited vacation"]
    return any(k in text_lower for k in culture_keywords)

def is_likely_required(text):
    text_lower = text.lower()
    req_keywords = ["years of experience", "bachelor's", "master's", "degree in", "proficiency in", "must have", "required:"]
    return any(k in text_lower for k in req_keywords)

def is_likely_preferred(text):
    text_lower = text.lower()
    pref_keywords = ["bonus points", "nice to have", "plus", "preferred:", "ideally"]
    return any(k in text_lower for k in pref_keywords)

def main():
    outliers = []
    
    with open(_INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row["text"]
            label = row["label"]
            
            # Check 1: Culture stuff in non-culture buckets
            if label != "culture" and is_likely_culture(text):
                outliers.append({"text": text, "current_label": label, "reason": "Contains culture/benefits keywords"})
                
            # Check 2: Required stuff in culture bucket
            if label == "culture" and is_likely_required(text):
                outliers.append({"text": text, "current_label": label, "reason": "Contains requirement keywords"})
                
            # Check 3: Preferred stuff in required bucket
            if label == "required" and is_likely_preferred(text):
                # Only if it starts with or heavily emphasizes it
                if any(text.lower().startswith(p) for p in ["bonus", "nice to have", "plus", "preferred"]):
                    outliers.append({"text": text, "current_label": label, "reason": "Starts with preferred keywords"})
                    
            # Check 4: Extremely short items
            words = len(re.findall(r"\w+", text))
            if words < 4:
                outliers.append({"text": text, "current_label": label, "reason": f"Very short ({words} words)"})

    print(f"Found {len(outliers)} potential outliers.")
    
    # Print up to 30 for the agent to review
    for i, outlier in enumerate(outliers[:30]):
        print(f"\n[{i+1}] LABEL: {outlier['current_label']} | REASON: {outlier['reason']}")
        print(f"TEXT: {outlier['text'].encode('ascii', 'replace').decode('ascii')}")
        
    if len(outliers) > 30:
        print(f"\n... and {len(outliers) - 30} more outliers not shown.")

if __name__ == "__main__":
    main()
