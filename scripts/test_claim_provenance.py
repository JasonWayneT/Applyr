"""Tests for claim_provenance valid-id filtering (CR-094)."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import claim_provenance as cp


class ProvenanceAccClassTests(unittest.TestCase):
    def test_sentence_level_cover_letter_entries_are_valid(self):
        with patch.object(cp, "load_valid_claim_ids", return_value=({"ACC-101"}, set())):
            folder = os.path.join(_SCRIPT_DIR, "_does_not_exist")
            with patch.object(cp.os.path, "exists", return_value=True), \
                 patch.object(cp, "open", unittest.mock.mock_open(read_data='{"company":"Acme","resume_claims":[{"bullet":"x","claim_ids":["ACC-101"]}],"cover_letter_claims":[{"sentence":"y","claim_ids":["ACC-101"]}]}')):
                ok, errors = cp.check_claim_provenance(folder)
        self.assertTrue(ok, errors)

    def test_legacy_proof_point_cover_letter_entries_remain_valid(self):
        with patch.object(cp, "load_valid_claim_ids", return_value=({"ACC-101"}, set())):
            folder = os.path.join(_SCRIPT_DIR, "_does_not_exist")
            with patch.object(cp.os.path, "exists", return_value=True), \
                 patch.object(cp, "open", unittest.mock.mock_open(read_data='{"company":"Acme","resume_claims":[{"bullet":"x","claim_ids":["ACC-101"]}],"cover_letter_claims":[{"proof_point":"y","claim_ids":["ACC-101"]}]}')):
                ok, errors = cp.check_claim_provenance(folder)
        self.assertTrue(ok, errors)

    def test_attrib_and_dnc_tokens_are_not_valid_fact_ids(self):
        we = (
            "* **[ACC-101] Story**: did the work.\n"
            "* **[ACC-191] Attribution:** **OWNED**.\n"
            "* **[ACC-192] DO NOT CLAIM:** sole causation.\n"
            "MET-01 is $40M ARR.\n"
        )
        claims = {
            "ACC-101-TECH": {"project_id": "ACC-101", "tags": ["x"]},
        }
        with patch.object(cp, "_read_master_claims", return_value=claims), \
             patch.object(cp, "_read_work_experience", return_value=we):
            valid, disabled = cp.load_valid_claim_ids()
        self.assertIn("ACC-101", valid)
        self.assertIn("ACC-101-TECH", valid)
        self.assertIn("MET-01", valid)
        self.assertNotIn("ACC-191", valid)
        self.assertNotIn("ACC-192", valid)

    def test_enabled_sibling_keeps_project_id_citable(self):
        claims = {
            "ACC-114-COST": {"project_id": "ACC-114", "disabled": True},
            "ACC-114-INGEST": {"project_id": "ACC-114", "tags": ["ingest"]},
        }
        with patch.object(cp, "_read_master_claims", return_value=claims), \
             patch.object(cp, "_read_work_experience", return_value=""):
            valid, disabled = cp.load_valid_claim_ids()
        self.assertIn("ACC-114-COST", disabled)
        self.assertNotIn("ACC-114", disabled)
        self.assertIn("ACC-114-INGEST", valid)
        self.assertNotIn("ACC-114-INGEST", disabled)


class ProvenanceCompanyFillTests(unittest.TestCase):
    def test_blank_company_is_filled_from_the_gate(self) -> None:
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "claim_provenance.json").write_text(
                json.dumps(
                    {
                        "resume_claims": [{"bullet": "x", "claim_ids": ["ACC-101"]}],
                        "cover_letter_claims": [{"sentence": "y", "claim_ids": ["ACC-101"]}],
                    }
                ),
                encoding="utf-8",
            )
            (folder / "stage0_fit_gate.json").write_text(
                json.dumps({"company": "Amplify"}),
                encoding="utf-8",
            )
            with patch.object(cp, "load_valid_claim_ids", return_value=({"ACC-101"}, set())):
                ok, errors = cp.check_claim_provenance(str(folder))
            self.assertTrue(ok, errors)
            saved = json.loads((folder / "claim_provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["company"], "Amplify")


class EmployerAttributionTests(unittest.TestCase):
    """CR-108 follow-up (2026-08-31, Papigen): a bullet drafted under one employer's role
    section citing a claim attributed to a different employer is a mechanical mismatch,
    independent of whether the cited claim ID itself is valid."""

    _RESUME = (
        "# Jason Taylor\n\n"
        "## PROFESSIONAL EXPERIENCE\n\n"
        "### Product Manager | Cision | 2021 - 2026\n"
        "San Diego, CA\n"
        "* Owned platform scope and delivery.\n\n"
        "### Product Owner | Sterkly | 2019 - 2021\n"
        "San Diego, CA\n"
        "* Coached team members on technical presentation prior to architecture reviews.\n"
    )

    def _run(self, prov_json: str, claims: dict):
        with patch.object(cp, "_read_master_claims", return_value=claims):
            with patch("builtins.open") as mock_open:
                def _side_effect(path, *a, **kw):
                    if str(path).endswith("Resume.md"):
                        return unittest.mock.mock_open(read_data=self._RESUME)()
                    return unittest.mock.mock_open(read_data=prov_json)()
                mock_open.side_effect = _side_effect
                with patch.object(cp.os.path, "exists", return_value=True):
                    return cp.check_employer_attribution("data/submissions/acme")

    def test_flags_bullet_citing_claim_from_a_different_employer(self):
        prov = (
            '{"company":"Acme","resume_claims":['
            '{"bullet":"Coached team members on technical presentation prior to architecture reviews.",'
            '"claim_ids":["ACC-118-COACHING"]}]}'
        )
        claims = {"ACC-118-COACHING": {"employer": "cision", "project_id": "ACC-118"}}
        ok, errors = self._run(prov, claims)
        self.assertFalse(ok)
        self.assertIn("cision", errors[0])
        self.assertIn("sterkly", errors[0])

    def test_passes_when_bullet_and_claim_employer_agree(self):
        prov = (
            '{"company":"Acme","resume_claims":['
            '{"bullet":"Owned platform scope and delivery.",'
            '"claim_ids":["ACC-101-ANCHOR"]}]}'
        )
        claims = {"ACC-101-ANCHOR": {"employer": "cision", "project_id": "ACC-101"}}
        ok, errors = self._run(prov, claims)
        self.assertTrue(ok, errors)

    def test_claim_with_no_employer_field_is_not_flagged(self):
        prov = (
            '{"company":"Acme","resume_claims":['
            '{"bullet":"Coached team members on technical presentation prior to architecture reviews.",'
            '"claim_ids":["ACC-999-GENERIC"]}]}'
        )
        claims = {"ACC-999-GENERIC": {"project_id": "ACC-999"}}
        ok, errors = self._run(prov, claims)
        self.assertTrue(ok, errors)


if __name__ == "__main__":
    unittest.main()
