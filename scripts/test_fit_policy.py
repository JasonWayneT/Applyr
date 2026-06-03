"""Unit tests for fit_policy.py (CR-035 / FR-188) — no LLM required."""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from fit_policy import (
    ANCHOR_FLOOR_LOW,
    apply_anchor_floor,
    b2c_open_prompt_block,
    detect_optional_domain_note,
    gates_passed_rubric,
    is_open_to_b2c,
    score_on_transferable_skills,
    strip_location_risk_flags,
    transferable_skills_context_block,
)
from anchor_gate import count_anchor_hits

passed = 0
failed = 0


def assert_test(name, condition, msg=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name}: {msg}")
        failed += 1


# Optional domain
assert_test(
    "optional domain: nice plus",
    bool(detect_optional_domain_note("Any experience in healthcare is a nice plus!")),
)
assert_test(
    "optional domain: may not have experience",
    bool(detect_optional_domain_note("You may not have experience in this treatment area")),
)
assert_test(
    "optional domain: absent",
    not detect_optional_domain_note("5+ years healthcare experience required."),
)
assert_test(
    "optional domain: still detected alongside required vertical clause",
    bool(detect_optional_domain_note(
        "3-5 years of experience in the US healthcare industry. "
        "Any experience in healthcare is a nice plus!"
    )),
)

# Gates-passed rubric strip
_sample_rubric = """## 2) Stage A: The Fast Gate
### 2.1 Title
- Reject bad titles

### 2.3 Location
- Reject remote

---

## 3) Stage B: Full Scoring
### A) Org
"""
stripped = gates_passed_rubric(_sample_rubric)
assert_test("gates_passed_rubric removes Stage A body", "SKIPPED" in stripped and "## 3) Stage B" in stripped)
assert_test("gates_passed_rubric removes old 2.1", "Reject bad titles" not in stripped)

# Anchor floor
prefs = {"required_anchors": ["b2b saas", "platform", "cross-functional", "roadmap"]}
ophelia_snip = (
    "B2B paid-digital platform roadmap cross-functional agile remote "
    "You may not have experience in this treatment area. Any experience in healthcare is a nice plus!"
)
hits, matched = count_anchor_hits(ophelia_snip, prefs["required_anchors"])
assert_test("ophelia snippet has >=2 anchors", hits >= 2, f"hits={hits} matched={matched}")

borderline = {"Decision": "NO", "Score": 68, "Summary": "Domain gap", "RiskFlags": []}
floored = apply_anchor_floor(borderline, ophelia_snip, prefs, 72)
assert_test(
    "anchor floor promotes 68 to 72",
    floored and floored["Decision"] == "YES" and floored["Score"] == 72,
    str(floored),
)
assert_test(
    "anchor floor skips low score",
    apply_anchor_floor({"Decision": "NO", "Score": 50, "Summary": "x"}, ophelia_snip, prefs, 72)["Score"] == 50,
)

# Location risk strip
with_loc = {
    "Decision": "NO",
    "Score": 68,
    "RiskFlags": ["Remote role not suitable", "AI gap"],
    "TopFitReasons": ["Location mismatch"],
}
cleaned = strip_location_risk_flags(with_loc, "REMOTE_OK")
assert_test(
    "strip location risk flags",
    cleaned["RiskFlags"] == ["AI gap"] and cleaned["TopFitReasons"] == [],
)

_cotiviti_jd = (
    "3-5 years of experience in the US healthcare industry. B2B platform roadmap."
)
assert_test(
    "transferable skills context injected",
    "TRANSFERABLE SKILLS" in transferable_skills_context_block(_cotiviti_jd, {"preferences": {}}),
)
assert_test(
    "score_on_transferable_skills default true",
    score_on_transferable_skills({}),
)

assert_test(
    "b2c open note when preference set",
    bool(b2c_open_prompt_block({"preferences": {"open_to_b2c": True}})),
)
assert_test(
    "is_open_to_b2c reads nested preference",
    is_open_to_b2c({"preferences": {"open_to_b2c": True}}),
)

from utils import passes_keyword_gate

_ok, _reason = passes_keyword_gate(
    "Consumer mobile app product roadmap agile stakeholder.",
    {"signal_keywords": ["b2c", "consumer", "mobile", "app", "roadmap"]},
)
assert_test("consumer JD passes keyword gate without b2b", _ok, _reason)

print(f"\nfit_policy: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
