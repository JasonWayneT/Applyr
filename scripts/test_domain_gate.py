"""Unit tests for domain_gate.py (CR-039 / FR-192) — no LLM required."""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from domain_gate import (
    check_domain_gate,
    extract_required_domains,
    get_domain_gaps,
    has_required_domain_requirements,
    transferable_skills_prompt_block,
)

passed = 0
failed = 0

DEFAULT_PREFS = {
    "domain_experience": ["b2b saas", "enterprise software", "platform", "software"],
    "required_domain_min_years": 2,
}


def assert_test(name, condition, msg=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name}: {msg}")
        failed += 1


COTIVITI_SNIP = (
    "3-5 years of experience in the US healthcare industry, specifically in "
    "healthcare payment analytics, coordination of benefits, or payment integrity. "
    "Experience (1-3 years) in product management, preferably in the healthcare industry."
)

OPHELIA_SNIP = (
    "You may not have experience in this treatment area, but ideally, you'll have "
    "knowledge of the healthcare space. Any experience in healthcare is a nice plus!"
)

FINTECH_SNIP = "Minimum 5 years experience in the fintech industry required."

B2B_SNIP = "B2B SaaS platform roadmap cross-functional agile stakeholder."

assert_test(
    "cotiviti extracts required healthcare",
    any(c == "healthcare" for _, _, c in extract_required_domains(COTIVITI_SNIP)),
    str(extract_required_domains(COTIVITI_SNIP)),
)

assert_test(
    "cotiviti domain gate always passes (no hard reject)",
    check_domain_gate(COTIVITI_SNIP, DEFAULT_PREFS)[0],
    check_domain_gate(COTIVITI_SNIP, DEFAULT_PREFS)[1],
)

assert_test(
    "cotiviti reports domain gap info",
    any(g["vertical"] == "healthcare" for g in get_domain_gaps(COTIVITI_SNIP, DEFAULT_PREFS)),
    str(get_domain_gaps(COTIVITI_SNIP, DEFAULT_PREFS)),
)

assert_test(
    "ophelia has no required domain years",
    not has_required_domain_requirements(OPHELIA_SNIP),
)

assert_test(
    "ophelia domain gate passes",
    check_domain_gate(OPHELIA_SNIP, DEFAULT_PREFS)[0],
)

assert_test(
    "fintech gap detected but gate passes",
    check_domain_gate(FINTECH_SNIP, DEFAULT_PREFS)[0]
    and any(g["vertical"] == "fintech" for g in get_domain_gaps(FINTECH_SNIP, DEFAULT_PREFS)),
)

assert_test(
    "candidate with healthcare has no gap",
    not get_domain_gaps(
        COTIVITI_SNIP,
        {"domain_experience": ["b2b saas", "healthcare"], "required_domain_min_years": 2},
    ),
)

assert_test(
    "transferable skills block mentions vertical",
    "TRANSFERABLE SKILLS" in transferable_skills_prompt_block(COTIVITI_SNIP, DEFAULT_PREFS)
    and "healthcare" in transferable_skills_prompt_block(COTIVITI_SNIP, DEFAULT_PREFS).lower(),
)

assert_test(
    "generic b2b jd passes",
    check_domain_gate(B2B_SNIP, DEFAULT_PREFS)[0],
)

print(f"\ndomain_gate: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
