"""CR-114 Story 5: uncertain evidence uses the adapter when enabled."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stage0_evidence_cascade import (
    BatchItem,
    CascadeReviewNeeded,
    classify_requirements_batch,
)
import stage0_subscription_adapter as adapter


ITEMS = [
    BatchItem("required:0:abc", "required", "Experience with Jira", "Used Jira for sequencing"),
]


class SubscriptionEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.pop(adapter.ENABLED_ENV, None)

    def tearDown(self) -> None:
        if self._env is None:
            os.environ.pop(adapter.ENABLED_ENV, None)
        else:
            os.environ[adapter.ENABLED_ENV] = self._env

    def test_disabled_switch_does_not_call_adapter(self) -> None:
        with patch.object(adapter, "run_stage0_subscription") as run, patch(
            "utils.call_llm", return_value=None
        ):
            with self.assertRaises(Exception):
                classify_requirements_batch(ITEMS, settings={"stage0_evidence_classification": {}})
        run.assert_not_called()

    def test_enabled_switch_never_calls_llm(self) -> None:
        os.environ[adapter.ENABLED_ENV] = "1"
        result = adapter.AdapterResult(
            "ok",
            "evidence",
            [{
                "item_id": "required:0:abc",
                "gate": "NONE",
                "gap_source": "",
                "evidence_level": 3,
                "confidence": "high",
                "reasoning": "Jira is in both the requirement and the evidence excerpt.",
            }],
            [],
            None,
            1,
            0.2,
            0.003,
            None,
            "k",
            ["npx"],
        )
        with patch.object(adapter, "run_stage0_subscription", return_value=result) as run, patch(
            "utils.call_llm"
        ) as llm:
            classified = classify_requirements_batch(ITEMS)
        self.assertEqual(classified["required:0:abc"]["gate"], "NONE")
        self.assertEqual(classified["required:0:abc"]["evidence_level"], 3)
        run.assert_called_once()
        llm.assert_not_called()
        self.assertEqual(run.call_args.args[0], "evidence")

    def test_timeout_raises_review_needed(self) -> None:
        os.environ[adapter.ENABLED_ENV] = "1"
        result = adapter.AdapterResult(
            "review", "evidence", [], ["required:0:abc"], "harness timed out",
            1, 5.0, 5.0 / 60.0, None, "k", ["npx"],
        )
        with patch.object(adapter, "run_stage0_subscription", return_value=result), patch(
            "utils.call_llm"
        ) as llm:
            with self.assertRaises(CascadeReviewNeeded) as ctx:
                classify_requirements_batch(ITEMS)
        llm.assert_not_called()
        self.assertEqual(ctx.exception.missing_item_ids, ["required:0:abc"])

    def test_unsafe_hard_is_held_not_skipped(self) -> None:
        os.environ[adapter.ENABLED_ENV] = "1"
        result = adapter.AdapterResult(
            "ok",
            "evidence",
            [{
                "item_id": "required:0:abc",
                "gate": "HARD",
                "gap_source": "domain",
                "evidence_level": 0,
                "confidence": "low",
                "reasoning": "no overlap words here",
            }],
            [],
            None,
            1,
            0.1,
            0.001,
            None,
            "k",
            ["npx"],
        )
        with patch.object(adapter, "run_stage0_subscription", return_value=result):
            classified = classify_requirements_batch(ITEMS)
        self.assertEqual(classified["required:0:abc"]["gate"], "NONE")
        self.assertNotEqual(classified["required:0:abc"].get("gap_class"), "HARD")


if __name__ == "__main__":
    unittest.main()
