import os
import requests
import json
import traceback
import subprocess

import bootstrap_local_data
bootstrap_local_data.main()

from style_compliance_guard import clean_escapes
from utils import init_pipeline_prefs, load_candidate_preferences, CANDIDATE_PREFERENCES_FILE, load_file, PROJECT_ROOT

init_pipeline_prefs()

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

# REG-08–REG-14: Collection quality gates (CR-027 / CR-028) — no network
from industry_gate import scout_industry_blocked, batch_industry_blocked
from utils import passes_keyword_gate
from anchor_gate import count_anchor_hits, check_anchor_gate

blocked, term = scout_industry_blocked("Crypto.com", "Product Manager", "", {"blocked_industries": ["Crypto"]})
assert_test("REG-08: Scout industry block (company name)",
            blocked and term == "Crypto",
            f"Expected block Crypto, got blocked={blocked} term={term}")

blocked, term = scout_industry_blocked("Salesforce", "Product Manager", "", {"blocked_industries": ["Gaming"]})
assert_test("REG-09: Scout industry pass (B2B employer)",
            not blocked,
            f"Expected pass, got blocked={blocked} term={term}")

blocked, term = batch_industry_blocked("DraftKings", "Title: Product Manager\nAbout DraftKings sports betting platform.", {"blocked_industries": ["Sports Betting"]})
assert_test("REG-10: Batch industry block (header)",
            blocked and term == "Sports Betting",
            f"Expected Sports Betting, got {term}")

ok, reason = passes_keyword_gate("We use agile and roadmap practices.", {"must_have_keywords": ["saas", "b2b"]})
assert_test("REG-11: Must-have keywords AND gate reject",
            not ok and "missing_must_have" in reason,
            f"Expected missing_must_have, got ok={ok} reason={reason}")

ok, reason = passes_keyword_gate("B2B SaaS platform product roadmap.", {"must_have_keywords": ["saas", "b2b"]})
assert_test("REG-12: Must-have keywords AND gate pass",
            ok,
            f"Expected pass, got reason={reason}")

hits, matched = count_anchor_hits("B2B SaaS platform and cross-functional roadmap.", ["b2b saas", "platform", "cross-functional"])
assert_test("REG-13: Anchor hit counting",
            hits >= 2,
            f"Expected >=2 hits, got {hits} matched={matched}")

import os
os.environ["ANCHOR_GATE_ENABLED"] = "1"
ok, reason = check_anchor_gate("Only one anchor: platform.", {"required_anchors": ["platform", "roadmap", "b2b saas"]})
os.environ.pop("ANCHOR_GATE_ENABLED", None)
assert_test("REG-14: Anchor gate rejects <2 hits when enabled",
            not ok and "anchor_hits" in reason,
            f"Expected anchor_hits reject, got ok={ok} reason={reason}")

# REG-15: Title gate parity (batch path uses seniority_gate — same as ingest semantics)
from seniority_gate import passes_title_gate

_jd_director = "Title: Director of Product\nB2B SaaS roadmap."
_ok, _reason = passes_title_gate(_jd_director, {"blocked_titles": ["Director"]})
assert_test("REG-15: Batch title gate blocks Director",
            not _ok and "title_blocked" in _reason,
            f"Expected title_blocked, got ok={_ok} reason={_reason}")

_jd_pm = "Title: Product Manager\nB2B SaaS platform roadmap."
_ok2, _reason2 = passes_title_gate(_jd_pm, {"blocked_titles": ["Director"]})
assert_test("REG-15: Batch title gate passes PM",
            _ok2,
            f"Expected pass, got reason={_reason2}")

# REG-22: Broad PM title scope (CR-045 / FR-240)
result = subprocess.run(
    ["npx", "vitest", "run", "tests/unit/gates.test.ts", "-t", "passesBroadPmTitleScope"],
    capture_output=True, text=True, cwd=PROJECT_ROOT, shell=True
)
assert_test("REG-22: Broad PM title scope blocks adjacent roles",
            result.returncode == 0,
            result.stdout + result.stderr)

# REG-16–REG-17: Location verdict lock-in (multi-city + Remote)
from zero_shot_classifier import resolve_location_verdict, classify_onsite

_brown_jd = (
    "Brown & Brown is seeking Product Manager in Dallas, TX, Atlanta, GA, or Remote! "
    "Agile roadmap stakeholder product management."
)
_verdict, _detail = resolve_location_verdict(_brown_jd)
assert_test("REG-16: Multi-city + Remote resolves REMOTE_OK",
            _verdict == "REMOTE_OK",
            f"Expected REMOTE_OK, got {_verdict} ({_detail})")

_reject, _reason = classify_onsite(_brown_jd)
assert_test("REG-16: Multi-city + Remote does not onsite-reject",
            not _reject,
            f"Expected pass, got reject reason={_reason}")

_onsite_only = (
    "Title: Product Manager\nHybrid role based in Atlanta, GA. "
    "3 days per week in-office. B2B SaaS roadmap."
)
_v2, _ = resolve_location_verdict(_onsite_only)
_reject2, _reason2 = classify_onsite(_onsite_only)
assert_test("REG-17: Hybrid outside SD without Remote rejects",
            _v2 == "REJECT" and _reject2,
            f"Expected REJECT, got verdict={_v2} reject={_reject2} reason={_reason2}")

# REG-18–REG-19: Fit policy (CR-035 / FR-188)
from fit_policy import apply_anchor_floor, detect_optional_domain_note

_promoted = apply_anchor_floor(
    {"Decision": "NO", "Score": 68, "Summary": "borderline"},
    "B2B platform roadmap cross-functional agile",
    {"required_anchors": ["platform", "roadmap", "cross-functional", "b2b saas"]},
    72,
)
assert_test("REG-18: Anchor floor promotes 68 to 72",
            _promoted and _promoted["Decision"] == "YES" and _promoted["Score"] == 72,
            str(_promoted))

assert_test("REG-19: Optional domain note detected",
            bool(detect_optional_domain_note("Any experience in healthcare is a nice plus")),
            "expected optional domain note")

# REG-20–REG-21: Transferable skills / domain gaps (CR-039 / FR-192)
from domain_gate import check_domain_gate, get_domain_gaps

_cotiviti = (
    "3-5 years of experience in the US healthcare industry, specifically in "
    "healthcare payment analytics. B2B platform roadmap cross-functional."
)
_ok, _reason = check_domain_gate(_cotiviti, {"domain_experience": ["b2b saas", "platform"]})
assert_test("REG-20: Required healthcare does not zero-token reject",
            _ok,
            f"expected pass, got reason={_reason}")
_gaps = get_domain_gaps(_cotiviti, {"domain_experience": ["b2b saas", "platform"]})
assert_test("REG-20b: Healthcare gap reported for scoring context",
            any(g.get("vertical") == "healthcare" for g in _gaps),
            str(_gaps))

_ophelia = "You may not have experience in this treatment area. Any experience in healthcare is a nice plus!"
_ok2, _reason2 = check_domain_gate(_ophelia, {"domain_experience": ["b2b saas"]})
assert_test("REG-21: Optional healthcare language passes domain gate",
            _ok2,
            f"expected pass, got reason={_reason2}")

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
