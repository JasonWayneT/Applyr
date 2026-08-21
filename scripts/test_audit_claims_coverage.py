"""Tests for scripts/audit_claims_coverage.py (CR-088)."""
from __future__ import annotations

import importlib.util
import os
import re
import sys
import unittest

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)


def _load_mod():
    path = os.path.join(_SCRIPT_DIR, "audit_claims_coverage.py")
    spec = importlib.util.spec_from_file_location("audit_claims_coverage", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _acc_from_unclaimed_detail(detail: str) -> str:
    m = re.search(r"(ACC-\d+)", detail or "")
    return m.group(1) if m else ""


class AuditClaimsCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_mod()

    def test_live_catalog_error_tier_clean(self):
        import json

        import we_acc_index as wai

        claims_path = os.path.join(_REPO_ROOT, "data", "master_claims.json")
        we_path = os.path.join(_REPO_ROOT, "data", "workExperience.md")
        with open(claims_path, encoding="utf-8") as f:
            claims = json.load(f)
        with open(we_path, encoding="utf-8") as f:
            we_text = f.read()
        we_acc = self.mod._load_we_acc_ids(we_path)
        result = self.mod.audit(claims, we_acc, we_text=we_text)
        classes = wai.classify_we_acc_ids(we_text)
        non_story_unclaimed = [
            e
            for e in result["errors"]
            if e["code"] == "we_unclaimed"
            and classes.get(_acc_from_unclaimed_detail(e["detail"]), "") != wai.CLASS_STORY
        ]
        self.assertEqual(
            non_story_unclaimed,
            [],
            msg=f"Attribution/DNC/tools flagged as we_unclaimed: {non_story_unclaimed}",
        )
        story_unclaimed = [
            e for e in result["errors"] if e["code"] == "we_unclaimed"
        ]
        self.assertEqual(
            story_unclaimed,
            [],
            msg=f"Indexable WE stories still missing claim rows: {story_unclaimed}",
        )
        self.assertEqual(
            result["errors"],
            [],
            msg=f"Live catalog ERROR-tier must be clean: {result['errors']}",
        )

    def test_attrib_and_dnc_ids_are_not_we_unclaimed(self):
        we_text = (
            "* **[ACC-101] Story**: did the work.\n"
            "* **[ACC-191] Attribution:** **OWNED** — owned it.\n"
            "* **[ACC-192] DO NOT CLAIM:** sole causation.\n"
        )
        claims = {
            "ACC-101-TECH": {
                "project_id": "ACC-101",
                "tags": ["x"],
                "attribution": "OWNED",
                "prohibited_claims": ["sole causation"],
            }
        }
        we_acc = self.mod._BRACKET_ACC_RE.findall(we_text)
        result = self.mod.audit(claims, set(we_acc), we_text=we_text)
        self.assertEqual(result["errors"], [])

    def test_story_without_claim_still_we_unclaimed(self):
        we_text = "* **[ACC-122] Storage monitoring**: watched disk.\n"
        claims = {
            "ACC-101-TECH": {"project_id": "ACC-101", "tags": ["x"]}
        }
        result = self.mod.audit(
            claims, {"ACC-122", "ACC-101"}, we_text=we_text
        )
        codes = {e["code"] for e in result["errors"]}
        self.assertIn("we_unclaimed", codes)
        self.assertTrue(any("ACC-122" in e["detail"] for e in result["errors"]))

    def test_substory_and_nonclaimable_are_not_we_unclaimed(self):
        we_text = (
            "* **[ACC-101] Story**: did the work.\n"
            "* **[ACC-122] What Jason drove:** monitoring.\n"
            "* **[ACC-154] Not owned:** next-gen import.\n"
            "* **[ACC-173] Glacier — Considered, Not Implemented**: talk only.\n"
        )
        claims = {
            "ACC-101-TECH": {
                "project_id": "ACC-101",
                "tags": ["x"],
                "attribution": "OWNED",
                "prohibited_claims": ["no"],
            }
        }
        result = self.mod.audit(
            claims, {"ACC-101", "ACC-122", "ACC-154", "ACC-173"}, we_text=we_text
        )
        self.assertEqual(result["errors"], [])

    def test_miskey_detected(self):
        claims = {
            "ACC-101-RETENTION": {
                "project_id": "ACC-116",
                "tags": ["x"],
                "text": "rollup",
            }
        }
        result = self.mod.audit(claims, we_acc={"ACC-101"}, side_corpus=frozenset())
        codes = {e["code"] for e in result["errors"]}
        self.assertIn("miskey", codes)
        self.assertIn("phantom_project", codes)

    def test_acc119_allowlisted(self):
        claims = {
            "ACC-101-TECH": {
                "project_id": "ACC-101",
                "tags": ["x"],
                "text": "t",
                "attribution": "OWNED",
                "prohibited_claims": ["no"],
            }
        }
        result = self.mod.audit(
            claims,
            we_acc={"ACC-101", "ACC-119"},
            high_risk=frozenset(),
        )
        self.assertEqual(result["errors"], [])

    def test_side_corpus_acc401_allowed(self):
        claims = {
            "ACC-401-AITOOLS": {
                "project_id": "ACC-401",
                "tags": ["AI"],
                "text": "side",
                "attribution": "OWNED",
                "prohibited_claims": ["overclaim"],
            }
        }
        result = self.mod.audit(claims, we_acc=set(), high_risk=frozenset({"ACC-401"}))
        self.assertEqual(result["errors"], [])

    def test_high_risk_warn_without_attribution(self):
        claims = {
            "ACC-204-QA": {
                "project_id": "ACC-204",
                "tags": ["QA"],
                "text": "qa",
            }
        }
        result = self.mod.audit(claims, we_acc={"ACC-204"})
        warn_codes = {w["code"] for w in result["warns"]}
        self.assertIn("missing_attribution", warn_codes)
        self.assertIn("missing_prohibited", warn_codes)
        self.assertEqual(result["errors"], [])


if __name__ == "__main__":
    unittest.main()
