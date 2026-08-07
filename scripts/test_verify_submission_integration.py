import os
import json
import subprocess
import sys

def filter_receipt(receipt):
    if isinstance(receipt, dict):
        filtered = {}
        for k, v in receipt.items():
            if k in ['timestamp', 'path', 'duration']:
                continue
            filtered[k] = filter_receipt(v)
        return filtered
    elif isinstance(receipt, list):
        return [filter_receipt(item) for item in receipt]
    else:
        return receipt

def main():
    submissions_dir = os.path.join("data", "submissions")
    baseline_file = os.path.join("data", "test_baselines.json")
    
    if not os.path.exists(baseline_file):
        print(f"Error: Baseline file {baseline_file} not found. Run snapshot script first.")
        sys.exit(1)
        
    with open(baseline_file, "r") as f:
        baselines = json.load(f)
        
    success = True
    for company, expected_receipt in baselines.items():
        company_dir = os.path.join(submissions_dir, company)
        if not os.path.isdir(company_dir):
            print(f"FAIL: {company} directory missing.")
            success = False
            continue
            
        print(f"Testing {company}...")
        subprocess.run(
            [sys.executable, "scripts/verify_submission.py", company_dir],
            capture_output=True,
            text=True,
            check=False
        )
        
        receipt_path = os.path.join(company_dir, "verification_receipt.json")
        if not os.path.exists(receipt_path):
            print(f"FAIL: {company} did not produce verification_receipt.json.")
            success = False
            continue
            
        with open(receipt_path, "r") as f:
            actual_receipt = json.load(f)
            
        expected_filtered = filter_receipt(expected_receipt)
        actual_filtered = filter_receipt(actual_receipt)
        
        if expected_filtered != actual_filtered:
            print(f"FAIL: {company} verification receipt drifted from baseline.")
            success = False
        else:
            print(f"PASS: {company}")
            
    if not success:
        print("Integration test FAILED.")
        sys.exit(1)
    else:
        print("Integration test PASSED.")
        sys.exit(0)

if __name__ == "__main__":
    main()
