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


if __name__ == "__main__":
    unittest.main()
