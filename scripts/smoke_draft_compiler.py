"""Smoke tests for CR-014 draft compiler (no LLM required for deterministic paths)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jd_tailoring import build_jd_profile_deterministic, score_claim_for_jd, _substring_valid
from local_draft_stages import employer_for_claim_id, validate_bullet_for_local
from bullet_generation import fallback_bullet
from claim_catalog import load_catalog
from bullet_fit import fit_bullet_to_budget, is_incomplete_bullet
from claim_composer import compose_bullet, strip_bridge_prefix
from verify_claims import strip_ids


def test_catalog_loads_acc():
    cat = load_catalog()
    assert "ACC-101" in cat.claims
    assert "ACC-203" in cat.claims
    assert len(cat.claims) >= 10


def test_strip_ids_pipe_tokens():
    raw = "Scaled platform | MET-02 | and [ACC-101] work."
    out = strip_ids(raw)
    assert "MET-02" not in out
    assert "ACC-101" not in out


def test_compose_bullet_no_ids():
    cat = load_catalog()
    jd = "platform stability data migration roadmap"
    b = compose_bullet("ACC-102", cat, jd)
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


if __name__ == "__main__":
    test_catalog_loads_acc()
    test_strip_ids_pipe_tokens()
    test_compose_bullet_no_ids()
    test_jd_profile_validation()
    test_employer_routing()
    test_bullet_gate_blocks_kubernetes()
    test_fit_bullet_sentence_boundary()
    test_strip_bridge_prefix()
    test_score_claim()
    print("smoke_draft_compiler: all passed")
