"""Smoke tests for CR-014 draft compiler (no LLM required for deterministic paths)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import init_pipeline_prefs
init_pipeline_prefs()

from jd_tailoring import build_jd_profile_deterministic, score_claim_for_jd, _substring_valid
from local_draft_stages import (
    assert_summary_grounded,
    build_summary_deterministic,
    employer_for_claim_id,
    validate_bullet_for_local,
)
from pipeline_env import cover_hook_mode, jd_profile_mode, draft_mode, resume_bullet_quotas
from local_draft_stages import EMPLOYERS, project_id_for_claim, select_claims_deterministic
from bullet_generation import fallback_bullet
from claim_catalog import load_catalog
from bullet_fit import fit_bullet_to_budget, is_incomplete_bullet
from claim_composer import compose_bullet, strip_bridge_prefix
from seniority_gate import (
    check_years_gate,
    extract_job_title_line,
    parse_max_years_required,
    passes_title_gate,
    title_blocked,
)
from verify_claims import strip_ids


def test_catalog_loads_acc():
    cat = load_catalog()
    assert any(k.startswith("ACC-101") for k in cat.claims)
    assert any(k.startswith("ACC-203") for k in cat.claims)
    assert len(cat.claims) >= 10


def test_strip_ids_pipe_tokens():
    raw = "Scaled platform | MET-02 | and [ACC-101] work."
    out = strip_ids(raw)
    assert "MET-02" not in out
    assert "ACC-101" not in out


def test_compose_bullet_no_ids():
    cat = load_catalog()
    jd = "platform stability data migration roadmap"
    cid = next((k for k in cat.claims if k.startswith("ACC-102")), None)
    assert cid
    b = compose_bullet(cid, cat, jd)
    assert b
    assert "ACC-" not in b
    assert "MET-" not in b


def test_jd_profile_validation():
    jd = "We need a Product Manager for data integrity and platform migration."
    profile = build_jd_profile_deterministic(jd)
    assert len(profile.priority_themes) >= 1
    assert _substring_valid("data integrity", jd)


def test_employer_routing():
    cat = load_catalog()
    for cid in ("ACC-203-TECH", "ACC-301-AUTO", "ACC-101-TECH"):
        if cid not in cat.claims:
            continue
        assert employer_for_claim_id(cid) == cat.claims[cid].employer


def test_bullet_gate_blocks_kubernetes():
    src = "Stabilized platform for 25,000 users [MET-03]."
    bad = "Deployed Kubernetes cluster for 25,000 users."
    ok, _ = validate_bullet_for_local(src, bad)
    assert not ok
    fb = fallback_bullet(src)
    ok2, _ = validate_bullet_for_local(src, fb)
    assert ok2 or len(fb) > 10


def test_senior_title_allowed():
    jd = "Senior Product Manager\n\nRequires 3-5 years of product management experience."
    prefs = {"blocked_titles": ["Lead", "Director"], "experience_range": {"max": 7}}
    ok, _ = passes_title_gate(jd, prefs)
    assert ok
    ok_y, _ = check_years_gate(jd, prefs)
    assert ok_y


def test_lead_title_blocked():
    title = "Lead Product Manager"
    prefs = {"blocked_role_titles": ["Lead", "Senior"]}
    assert title_blocked(title, prefs) == "Lead"


def test_years_gate_rejects_high_requirement():
    jd = "Product Manager\n\nMinimum 10 years of experience required."
    prefs = {"experience_range": {"max": 7}}
    ok, reason = check_years_gate(jd, prefs)
    assert not ok
    assert "10" in reason
    assert parse_max_years_required(jd) == 10


def test_fit_bullet_sentence_boundary():
    long = (
        "Led platform stabilization across ingestion pipelines and customer migrations, "
        "reducing incident volume while improving roadmap throughput for enterprise SaaS teams."
    )
    fitted = fit_bullet_to_budget(long, max_words=12)
    assert fitted.endswith(".")
    assert not is_incomplete_bullet(fitted)


def test_strip_bridge_prefix():
    bridged = "Data integrity and ingestion: Led platform roadmap for migrations."
    stripped = strip_bridge_prefix(bridged)
    assert stripped.startswith("Led")
    assert "Data integrity and ingestion:" not in stripped


def test_score_claim():
    jd = "data pipeline migration roadmap"
    profile = build_jd_profile_deterministic(jd)
    high = score_claim_for_jd("Resolved data pipeline drop-off for migration tooling.", profile, jd)
    low = score_claim_for_jd("Built landing page.", profile, jd)
    assert high >= low


def test_pipeline_env_defaults():
    assert draft_mode() == "compose" or os.environ.get("DRAFT_MODE")
    assert jd_profile_mode() in ("deterministic", "llm")
    assert cover_hook_mode() in ("template", "llm")


def test_resume_bullet_quotas_default():
    from candidate_context import load_employers_ordered

    q = resume_bullet_quotas()
    ordered = load_employers_ordered()
    if ordered:
        assert q.get(ordered[0]) == 5
        for slug in ordered[1:]:
            assert q.get(slug) == 3


def test_project_id_for_claim():
    assert project_id_for_claim("ACC-102-TECH") == "ACC-102"
    assert project_id_for_claim("ACC-203") == "ACC-203"


def test_select_claims_meets_quota():
    cat = load_catalog()
    truth = cat.truth_map()
    if len(truth) < 20:
        return
    jd = "platform data integrity ingestion roadmap agile ceremonies user stories KPI"
    picked = select_claims_deterministic(jd, truth)
    cision = [c for c in picked if c.startswith("ACC-1")]
    assert len(cision) >= 5


def test_summary_grounding_fallback():
    from candidate_context import primary_employer_slug
    bullets = {primary_employer_slug(): ["Led platform roadmap for $40M ARR ecosystem."]}
    bad = build_summary_deterministic(bullets, "data migration", None)
    ok, _ = assert_summary_grounded(bad, bullets)
    assert ok or "Product Manager" in bad


def test_summary_no_chained_theme_ands():
    from candidate_context import primary_employer_slug
    from jd_tailoring import JdProfile

    bullets = {
        primary_employer_slug(): [
            "Engineered a structural bypass of failing legacy ETL pipelines, eliminating a 40% data drop-off rate.",
        ]
    }
    profile = JdProfile(
        priority_themes=[
            "platform reliability and scale",
            "data integrity and ingestion",
            "roadmap prioritization and execution",
        ]
    )
    summary = build_summary_deterministic(bullets, "platform data rankings", profile)
    assert " and scale and data " not in summary.lower()
    assert " and ingestion" not in summary.lower() or summary.lower().count(" and ingestion") <= 1
    assert "platform reliability and data integrity" in summary.lower()


def test_theme_primaries_inject_security_claim():
    from theme_primaries import inject_theme_primaries, primary_claim_ids_for_jd
    from jd_tailoring import build_jd_profile_deterministic

    cat = load_catalog()
    truth = cat.truth_map()
    if "ACC-103-ROADMAP" not in truth:
        return
    jd = "Product Manager owning security vulnerability backlog and compliance risk reduction."
    prof = build_jd_profile_deterministic(jd)
    prim = primary_claim_ids_for_jd(jd, prof, truth)
    assert "ACC-103-ROADMAP" in prim
    base = [c for c in truth if c.startswith("ACC-1")][:5]
    merged = inject_theme_primaries(base, truth, jd, prof)
    assert "ACC-103-ROADMAP" in merged


def test_cover_proof_format_and_picker():
    from claim_composer import format_cover_proof_sentence
    from jd_tailoring import build_jd_profile_deterministic, pick_cover_bullets

    raw = "Prioritized delivery against roadmap goals: enforced strict prioritization."
    fmt = format_cover_proof_sentence(raw)
    # 2026-07-18 fix: cover-letter proof sentences need a subject ("I enforced...")
    # since resume-bullet-style verb-first text ("Enforced...") reads as a sentence
    # fragment when spliced into cover-letter prose. Real defect found and fixed
    # during a real-archive sweep (CR-070) - a snapsheet cover letter contained
    # exactly this fragment ("Presented the consolidated quarterly roadmap...").
    assert fmt.startswith("I enforced")
    assert fmt.endswith(".")

    jd = (
        "Forbes Intelligence platform rankings and list franchises. "
        "monetization and media products. migration to structured data."
    )
    prof = build_jd_profile_deterministic(jd)
    bullets = {
        "ACC-105": "Roadmap prioritization for platform delivery.",
        "ACC-104": "Executed migration of accounts to a new corporate platform.",
        "ACC-202": "Translated business constraints into specs.",
    }
    valid = {k: v for k, v in bullets.items()}
    picked = pick_cover_bullets(bullets, valid, prof, jd, k=2)
    assert any("migrat" in p.lower() for p in picked)


def test_employer_job_title_normalization():
    from candidate_context import DEFAULT_EMPLOYER_HEADERS, load_employers
    from local_draft_stages import normalize_employer_job_titles, experience_skeleton

    sk = experience_skeleton()
    employers = load_employers()
    assert employers
    assert all(slug in sk for slug in employers)

    raw = "### Product Owner / Account Manager | Example Co | June 2017 - January 2019\n"
    fixed = normalize_employer_job_titles(raw)
    assert "Account Manager" not in fixed
    assert "Product Owner" in fixed
    assert "Example Co" in fixed

    hybrid = "### Product Owner / Product Manager | Example Co | 2021\n"
    normalized = normalize_employer_job_titles(hybrid)
    assert "Product Manager" in normalized
    assert "Example Co" in normalized
    assert DEFAULT_EMPLOYER_HEADERS


def test_tone_guard_rewrites_layoffs():
    from tone_guard import sanitize_submission_tone, tone_violations, assert_submission_tone_clean

    raw = (
        "Maintained continuity through multiple rounds of layoffs and attrition "
        "by driving knowledge sharing."
    )
    cleaned = sanitize_submission_tone(raw)
    assert "layoff" not in cleaned.lower()
    assert "attrition" not in cleaned.lower()
    assert "constraints" in cleaned.lower()
    assert not tone_violations(cleaned)
    assert assert_submission_tone_clean(cleaned)[0]

    ok, err = validate_bullet_for_local(raw, raw)
    assert not ok and "Blocked tone" in (err or "")


def test_approved_metrics_excludes_phone_fragments():
    from approved_metrics import find_unapproved_metrics

    header = "City, State | email@example.com | linkedin.com/in/example"
    assert find_unapproved_metrics(header) == []
    bad = find_unapproved_metrics("Delivered $999M in savings.")
    assert bad


def test_anti_claim_hints_load():
    from catalog_validator import load_anti_claim_hints

    hints = load_anti_claim_hints()
    assert isinstance(hints, list)


def test_catalog_validate_example():
    from catalog_validator import validate_catalog
    from claim_catalog import MASTER_CLAIMS_FILE
    from utils import WORK_EXP_FILE

    data_dir = os.path.dirname(MASTER_CLAIMS_FILE)
    result = validate_catalog(
        os.path.join(data_dir, "master_claims.example.json"),
        os.path.join(data_dir, "workExperience.example.md"),
    )
    assert result.ok, result.errors[:3]


def test_strict_flags_default_off():
    from pipeline_env import (
        strict_anti_claims,
        strict_conversion_critique,
        strict_cover_audit,
        strict_metrics,
    )

    assert strict_cover_audit() is False
    assert strict_metrics() is False
    assert strict_anti_claims() is False
    assert strict_conversion_critique() is False


def _group_bullets_by_company(bullets: dict) -> dict:
    grouped = {e: [] for e in EMPLOYERS}
    for cid, text in bullets.items():
        grouped[employer_for_claim_id(cid)].append(text)
    return grouped


def _assemble_smoke_resume(summary: str, bullets_by_company: dict) -> str:
    from candidate_context import build_contact_header
    from local_draft_stages import experience_skeleton, EMPLOYERS
    from tone_guard import sanitize_submission_tone

    sk = experience_skeleton()
    parts = [
        build_contact_header().strip(),
        "",
        "## PROFESSIONAL SUMMARY",
        sanitize_submission_tone(summary.strip()),
        "",
        "## PROFESSIONAL EXPERIENCE",
        "",
    ]
    for key in EMPLOYERS:
        parts.append(sk[key])
        for b in bullets_by_company.get(key, []):
            parts.append(f"* {sanitize_submission_tone(b)}")
        parts.append("")
    parts.append("## EDUCATION\n\n* **BBA** — Example University, 2019\n")
    return "\n".join(parts)


def _build_archetype_resume(jd_text: str):
    from jd_tailoring import build_jd_profile_deterministic
    from conversion_framing import enforce_conversion_framing
    from local_draft_stages import build_summary_deterministic, ensure_employer_quotas, EMPLOYERS
    from bullet_generation import generate_bullets_for_claims
    from resume_conversion_eval import evaluate_resume_conversion

    cat = load_catalog()
    truth = cat.truth_map()
    if len(truth) < 15:
        return None, None, {"pass": True, "issues": []}
    profile = build_jd_profile_deterministic(jd_text)
    selected = select_claims_deterministic(jd_text, truth)
    quotas = resume_bullet_quotas()
    bullets, _ = generate_bullets_for_claims(selected, truth, jd_text, profile=profile)
    bullets = ensure_employer_quotas(bullets, truth, jd_text, fallback_bullet, quotas=quotas)
    from local_draft_stages import enforce_metric_bullet_floor

    bullets = enforce_metric_bullet_floor(bullets, truth, jd_text, fallback_bullet)
    bullets = enforce_conversion_framing(bullets, truth, jd_text, fallback_bullet)
    bullets_by_company = _group_bullets_by_company(bullets)
    summary = build_summary_deterministic(bullets_by_company, jd_text, profile)
    resume_md = _assemble_smoke_resume(summary, bullets_by_company)
    critique = evaluate_resume_conversion(
        resume_md, bullets_by_company=bullets_by_company, jd_text=jd_text
    )
    return resume_md, bullets_by_company, critique


def test_archetype_conversion_critique_pass():
    """FR-231: synthetic JD archetypes should pass conversion critique (no PDF)."""
    fixtures_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
    names = (
        "jd_archetype_analytics.txt",
        "jd_archetype_platform.txt",
        "jd_archetype_generic_pm.txt",
    )
    for fname in names:
        path = os.path.join(fixtures_dir, fname)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            jd_text = f.read()
        _md, _bbc, critique = _build_archetype_resume(jd_text)
        assert critique.get("pass"), f"{fname} failed: {critique.get('issues', [])[:3]}"


def test_verify_editor_rejects_invented_metric():
    from verify_editor_save import verify_editor_save
    import tempfile

    cat = load_catalog()
    if not cat.raw_truth_lines:
        return
    with tempfile.TemporaryDirectory() as tmp:
        ok, _err = verify_editor_save(
            "I saved $999 trillion by deploying Kubernetes everywhere.",
            "Resume.md",
            tmp,
        )
        assert not ok


if __name__ == "__main__":
    test_pipeline_env_defaults()
    test_catalog_loads_acc()
    test_strip_ids_pipe_tokens()
    test_compose_bullet_no_ids()
    test_jd_profile_validation()
    test_employer_routing()
    test_bullet_gate_blocks_kubernetes()
    test_senior_title_allowed()
    test_lead_title_blocked()
    test_years_gate_rejects_high_requirement()
    test_fit_bullet_sentence_boundary()
    test_strip_bridge_prefix()
    test_score_claim()
    test_resume_bullet_quotas_default()
    test_project_id_for_claim()
    test_select_claims_meets_quota()
    test_summary_grounding_fallback()
    test_cover_proof_format_and_picker()
    test_employer_job_title_normalization()
    test_approved_metrics_excludes_phone_fragments()
    test_anti_claim_hints_load()
    test_catalog_validate_example()
    test_strict_flags_default_off()
    test_archetype_conversion_critique_pass()
    test_verify_editor_rejects_invented_metric()
    test_tone_guard_rewrites_layoffs()
    print("smoke_draft_compiler: all passed")
