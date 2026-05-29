import json
import re
import sys

def verify_claims():
    with open('data/master_claims.json', 'r', encoding='utf-8') as f:
        claims = json.load(f)
        
    forbidden = ["manager", "director", "head of", "managed a team", "led a team"]
    
    # Ground Truth Metrics
    valid_metrics = {
        "40,000,000", "40m", "3,500", "25,000", "7%", "1,000,000", "2,000,000", "40%", 
        "100%", "90%", "300", "200", "700", "288,000", "8,500", "34,000", "22,100", 
        "1m", "3m", "100", "10", "100+", "0", "5"
    }
    
    errors = []
    
    for key, claim in claims.items():
        text = claim['text'].lower()
        for word in forbidden:
            if word in text:
                errors.append(f"Forbidden word '{word}' found in {key}")
                
        # Check if metrics match valid list
        # Extract numbers and compare
        for metric in claim.get('metrics', []):
            if str(metric).lower().replace('$', '') not in valid_metrics:
                errors.append(f"Invalid metric '{metric}' in {key}")
                
    if errors:
        print("Validation Failed:")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)
    else:
        print("Validation Passed. No forbidden words or invalid metrics found.")
        sys.exit(0)

if __name__ == "__main__":
    verify_claims()
