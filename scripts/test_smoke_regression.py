import os
import requests
import json
import traceback

from style_compliance_guard import clean_escapes
from utils import load_candidate_preferences, CANDIDATE_PREFERENCES_FILE, load_file

print("==================================================================")
print("  STARTING QA SUITE: SMOKE & REGRESSION TESTS")
print("==================================================================")

passed = 0
failed = 0

def assert_test(name, condition, error_msg):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name}: {error_msg}")
        failed += 1

# -------------------------------------------------------------------
# REGRESSION TESTS (Layer 3: Compliance Guard)
# -------------------------------------------------------------------
print("\n--- Regression Tests ---")

# REG-01: Em-dash Guard
text_dash = "Managed a team—of 5 people--and won."
cleaned_dash = clean_escapes(text_dash)
assert_test("REG-01: Em-dash replacement", 
            "Managed a team, of 5 people, and won." in cleaned_dash,
            f"Expected commas, got: {cleaned_dash}")

# REG-04: Fact ID Removal
text_fact = "Improved metric by 40% [MET-05] and shipped feature [ACC-101]."
cleaned_fact = clean_escapes(text_fact)
assert_test("REG-04: Fact ID removal", 
            "Improved metric by 40% and shipped feature ." in cleaned_fact,
            f"Expected IDs stripped, got: {cleaned_fact}")

# REG-05: Dynamic Preferences Loading
prefs = load_candidate_preferences()
assert_test("REG-05: Dynamic preferences JSON structure",
            isinstance(prefs, dict) and "blocked_titles" in prefs,
            f"Expected dict with blocked_titles, got: {prefs}")

# -------------------------------------------------------------------
# SMOKE TESTS (Layer 3: API & Endpoints)
# -------------------------------------------------------------------
print("\n--- Smoke Tests ---")

API_BASE = "http://localhost:3000/api"

try:
    # SMOKE-01: GET /api/jobs
    r_jobs = requests.get(f"{API_BASE}/jobs")
    assert_test("SMOKE-01: GET /api/jobs returns 200", r_jobs.status_code == 200, f"Status code: {r_jobs.status_code}")
    
    # SMOKE-02: GET /api/experience
    r_exp = requests.get(f"{API_BASE}/experience")
    assert_test("SMOKE-02: GET /api/experience returns 200", r_exp.status_code == 200, f"Status code: {r_exp.status_code}")
    
    if r_exp.status_code == 200:
        exp_data = r_exp.json()
        content = exp_data.get('content', '')
        assert_test("SMOKE-03: Experience JSON contains content", len(content) > 0, "Content is empty")
        
        # Test auto-codifier with a dry run simulation if possible, or append a temp bullet
        # SMOKE-04: POST /api/experience (Auto-codifier doesn't mangle existing)
        original_content = content
        r_post_same = requests.post(f"{API_BASE}/experience", json={"content": original_content})
        assert_test("SMOKE-04: POST existing content returns 200", r_post_same.status_code == 200, f"Status code: {r_post_same.status_code}")
        
        # SMOKE-05: Auto-codifier REG-07 (Doesn't re-assign)
        new_content_resp = requests.get(f"{API_BASE}/experience").json().get('content', '')
        # We assume original had some [ACC-] tags and they shouldn't double up
        assert_test("REG-06/07: Auto-codifier preserves state", "[ACC-" in new_content_resp, "IDs were stripped or mangled")
        
except requests.exceptions.ConnectionError:
    print("  [WARN] Backend is not running on localhost:3000. Skipping API tests.")
except Exception as e:
    print(f"  [FAIL] API Tests Error: {e}")
    traceback.print_exc()

print("\n==================================================================")
print(f"  QA SUITE COMPLETE: {passed} Passed, {failed} Failed")
print("==================================================================")

if failed > 0:
    exit(1)
