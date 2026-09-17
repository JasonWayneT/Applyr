"""CR-114 Story 5: uncertain evidence is not connected to the adapter yet."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stage0_evidence_cascade as cascade
import stage0_subscription_adapter as adapter


class SubscriptionEvidenceNotWiredTests(unittest.TestCase):
    def test_cascade_source_does_not_import_adapter(self) -> None:
        source = Path(cascade.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import stage0_subscription_adapter", source)
        self.assertNotIn("from stage0_subscription_adapter", source)
        self.assertIn("call_llm(", source)

    def test_adapter_evidence_schema_exists_for_later_wiring(self) -> None:
        schema = adapter.schema_for("evidence")
        self.assertIn("gate", str(schema))
        self.assertNotEqual(schema, adapter.schema_for("extraction"))

    def test_production_switch_still_off(self) -> None:
        self.assertFalse(adapter.adapter_enabled())


if __name__ == "__main__":
    unittest.main()
