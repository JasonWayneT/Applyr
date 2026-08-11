"""Tests for scripts/audit_claims_coverage.py (CR-088)."""
from __future__ import annotations

import importlib.util
import os
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


class AuditClaimsCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_mod()

    def test_live_catalog_error_tier_clean(self):
        import json

        claims_path = os.path.join(_REPO_ROOT, "data", "master_claims.json")
        with open(claims_path, encoding="utf-8") as f:
            claims = json.load(f)
        we_acc = self.mod._load_we_acc_ids(
            os.path.join(_REPO_ROOT, "data", "workExperience.md")
        )
        result = self.mod.audit(claims, we_acc)
        self.assertEqual(
            result["errors"],
            [],
            msg=f"ERROR-tier findings: {result['errors']}",
        )

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
