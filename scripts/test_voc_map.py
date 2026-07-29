"""Tests for VOC codename scrubbing (LR-011 prevention)."""
from claim_catalog import load_catalog, sanitize_claim_text
from catalog_validator import validate_catalog
from submission_linter import lint_document
from voc_map import apply_voc_replacements, contains_voc_codename
import os


def test_apply_voc_replacements_core_platform():
    raw = "Integrated the core B2B SaaS platform with upstream data."
    out = apply_voc_replacements(raw)
    assert "core B2B SaaS platform" not in out.lower()
    assert "customer-facing" in out.lower()


def test_sanitize_claim_text_strips_codename():
    catalog = load_catalog()
    raw = "Worked on the Core B2B SaaS Platform migration."
    clean = sanitize_claim_text(raw, catalog)
    assert not contains_voc_codename(clean)
    result = lint_document(f"## EXPERIENCE\n* {clean}", "resume")
    assert not any(v.rule_id == "LR-011" for v in result.blocks)


def test_catalog_validator_rejects_voc_in_claims_file():
    from utils import DATA_DIR

    result = validate_catalog(
        os.path.join(DATA_DIR, "master_claims.example.json"),
        os.path.join(DATA_DIR, "workExperience.example.md"),
    )
    assert result.ok, result.errors
