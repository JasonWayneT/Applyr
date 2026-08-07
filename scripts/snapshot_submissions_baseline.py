import os
import json
import subprocess
import sys

def main():
    submissions_dir = os.path.join("data", "submissions")
    baseline_file = os.path.join("data", "test_baselines.json")
    
    if not os.path.exists(submissions_dir):
        print(f"Error: {submissions_dir} not found.")
        sys.exit(1)
        
    baselines = {}
    
    for company in os.listdir(submissions_dir):
        company_dir = os.path.join(submissions_dir, company)
        if not os.path.isdir(company_dir):
            continue
            
        print(f"Snapshotting {company}...")
        try:
            subprocess.run(
                [sys.executable, "scripts/verify_submission.py", company_dir],
                capture_output=True,
                text=True,
                check=False
            )
            
            receipt_path = os.path.join(company_dir, "verification_receipt.json")
            if os.path.exists(receipt_path):
                with open(receipt_path, "r") as f:
                    receipt = json.load(f)
                    baselines[company] = receipt
        except Exception as e:
            print(f"Failed to process {company}: {e}")
            
    with open(baseline_file, "w") as f:
        json.dump(baselines, f, indent=2)
        
    print(f"Baseline saved to {baseline_file}")

if __name__ == "__main__":
    main()
