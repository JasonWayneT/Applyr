"""Smoke tests for CR-014 draft compiler (no LLM required for deterministic paths)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jd_tailoring import build_jd_profile_deterministic, score_claim_for_jd, _substring_valid
from local_draft_stages import (
    assert_summary_grounded,
    build_summary_deterministic,
    employer_for_claim_id,
    validate_bullet_for_local,
)
from pipeline_env import cover_hook_mode, jd_profile_mode, draft_mode, resume_bullet_quotas
from local_draft_stages import project_id_for_claim, select_claims_deterministic
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
    assert employer_for_claim_id("ACC-203") == "sterkly"
    assert employer_for_claim_id("ACC-301") == "zero_to_sixty"
    assert employer_for_claim_id("ACC-101") == "cision"


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
    assert title_blocked(title, ["Lead", "Senior"]) == "Lead"


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
    q = resume_bullet_quotas()
    assert q.get("cision") == 5
    assert q.get("sterkly") == 3
    assert q.get("zero_to_sixty") == 3


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
    bullets = {"cision": ["Led platform roadmap for $40M ARR ecosystem."]}
    bad = build_summary_deterministic(bullets, "data migration", None)
    ok, _ = assert_summary_grounded(bad, bullets)
    assert ok or "Product Manager" in bad


def test_summary_no_chained_theme_ands():
    from jd_tailoring import JdProfile

    bullets = {
        "cision": [
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


def test_cover_proof_format_and_picker():
    from claim_composer import format_cover_proof_sentence
    from jd_tailoring import build_jd_profile_deterministic, pick_cover_bullets

    raw = "Prioritized delivery against roadmap goals: enforced strict prioritization."
    fmt = format_cover_proof_sentence(raw)
    assert fmt.startswith("Enforced")
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
    from local_draft_stages import normalize_employer_job_titles, experience_skeleton

    sk = experience_skeleton()
    assert "Product Owner / Account Manager" not in sk["zero_to_sixty"]
    assert "Product Owner | Zero to Sixty" in sk["zero_to_sixty"]
    assert sk["cision"].startswith("### Product Manager | Cision")
    assert sk["sterkly"].startswith("### Product Manager | Sterkly")

    raw = "### Product Owner / Account Manager | Zero to Sixty | June 2017 - January 2019\n"
    fixed = normalize_employer_job_titles(raw)
    assert "Account Manager" not in fixed
    assert "Product Owner | Zero to Sixty" in fixed

    cision = "### Product Owner / Product Manager | Cision | 2021\n"
    assert "Product Manager | Cision" in normalize_employer_job_titles(cision)


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

    header = "San Diego, CA | [REDACTED_PHONE] | [REDACTED_EMAIL]"
    assert find_unapproved_metrics(header) == []
    bad = find_unapproved_metrics("Delivered $999M in savings.")
    assert bad


def test_anti_claim_hints_load():
    from catalog_validator import load_anti_claim_hints

    hints = load_anti_claim_hints()
    assert isinstance(hints, list)


def test_catalog_validate_example():
    from catalog_validator import validate_catalog

    result = validate_catalog()
    assert result.ok, result.errors[:3]


def test_strict_flags_default_off():
    from pipeline_env import strict_anti_claims, strict_cover_audit, strict_metrics

    assert strict_cover_audit() is False
    assert strict_metrics() is False
    assert strict_anti_claims() is False


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
    test_verify_editor_rejects_invented_metric()
    test_tone_guard_rewrites_layoffs()
    print("smoke_draft_compiler: all passed")
