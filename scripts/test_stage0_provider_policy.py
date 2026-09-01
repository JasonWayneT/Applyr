#!/usr/bin/env python3
"""Test Python Stage 0 policy normalization against the shared fixture (CR-108)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from stage0_evidence_cascade import normalize_stage0_evidence_policy


_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "stage0_provider_policy.json"
)


class TestStage0ProviderPolicy(unittest.TestCase):
    """Verify Python normalization matches the shared provider policy fixture."""

    def test_shared_fixture_cases(self) -> None:
        """Assert every fixture case produces the expected normalized policy."""
        fixture = json.loads(_FIXTURE.read_text(encoding="utf-8"))
        for case in fixture["cases"]:
            with self.subTest(case=case["name"]):
                self.assertEqual(normalize_stage0_evidence_policy(case["settings"]), case["expected"])


if __name__ == "__main__":
    unittest.main()
