#!/usr/bin/env python3
"""Catalog validator coverage for the CR-094 claims-index contract."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalog_validator import validate_catalog


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestCatalogValidator(unittest.TestCase):
    def test_empty_text_allowed_for_tagged_constrained_index_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claims = root / "claims.json"
            we = root / "workExperience.md"
            _write_json(
                claims,
                {
                    "ACC-215-RABBITMQ": {
                        "project_id": "ACC-215",
                        "tags": ["RabbitMQ", "Distributed Messaging"],
                        "text": "",
                        "allowed_claims": ["Owned RabbitMQ monitoring workflows."],
                        "prohibited_claims": ["owning infrastructure engineering"],
                    }
                },
            )
            we.write_text("[ACC-215] RabbitMQ monitoring workflow.\n", encoding="utf-8")

            result = validate_catalog(str(claims), str(we))

        self.assertTrue(result.ok, result.errors)

    def test_empty_text_without_index_fields_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claims = root / "claims.json"
            we = root / "workExperience.md"
            _write_json(
                claims,
                {"ACC-999-BAD": {"project_id": "ACC-999", "tags": [], "text": ""}},
            )
            we.write_text("[ACC-999] Placeholder.\n", encoding="utf-8")

            result = validate_catalog(str(claims), str(we))

        self.assertFalse(result.ok)
        self.assertIn("ACC-999-BAD: empty text", result.errors)

    def test_metric_ref_or_we_literal_anchors_catalog_metric(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claims = root / "claims.json"
            we = root / "workExperience.md"
            _write_json(
                claims,
                {
                    "ACC-114-INGEST": {
                        "project_id": "ACC-114",
                        "tags": ["Platform Deprecation", "Cost Reduction"],
                        "text": "",
                        "metrics": ["$800,000"],
                        "metric_ref": "MET-17",
                        "allowed_claims": ["Contributed to platform deprecation."],
                        "prohibited_claims": ["sole causation"],
                    },
                    "ACC-111-ENTERPRISE": {
                        "project_id": "ACC-111",
                        "tags": ["Enterprise Accounts"],
                        "text": "",
                        "metrics": ["38"],
                        "allowed_claims": ["Approximately 38 organizations."],
                        "prohibited_claims": ["user count"],
                    },
                },
            )
            we.write_text(
                "[ACC-114] Platform deprecation. [MET-17]\n"
                "[ACC-111] Approximately 38 enterprise organizations.\n",
                encoding="utf-8",
            )

            result = validate_catalog(str(claims), str(we))

        self.assertTrue(result.ok, result.errors)


if __name__ == "__main__":
    unittest.main()
