#!/usr/bin/env python3
"""CR-114: locked-30 evidence uses one Agy session per JD and chunks of 3."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from replay_stage0_locked30 import run_evidence_per_jd
from smoke_stage0_agy_archive import _EVIDENCE_CHUNK, _chunks
from stage0_subscription_adapter import Stage0Item


class _FakeSession:
    opened = 0
    closed = 0

    def __init__(self) -> None:
        type(self).opened += 1

    def close(self) -> None:
        type(self).closed += 1


class ReplayEvidenceSessionTests(unittest.TestCase):
    def test_evidence_chunk_size_is_three(self) -> None:
        self.assertEqual(_EVIDENCE_CHUNK, 3)
        items = list(range(7))
        sizes = [len(chunk) for chunk in _chunks(items, _EVIDENCE_CHUNK)]
        self.assertEqual(sizes, [3, 3, 1])

    def test_one_session_per_jd_with_items(self) -> None:
        _FakeSession.opened = 0
        _FakeSession.closed = 0
        calls: list[int] = []

        def run_task(_task, items, _config, _budget, session):
            calls.append(id(session))
            return {"outcome": "ok", "silent_line_loss": False}

        prepared = [
            {"slug": "eso", "evidence_items": [Stage0Item("eso:req:0", bucket="required")]},
            {"slug": "remote", "evidence_items": []},
            {
                "slug": "smartlight_analytics",
                "evidence_items": [Stage0Item("sma:req:0", bucket="required")],
            },
        ]
        run_evidence_per_jd(prepared, object(), object(), _FakeSession, run_task)
        self.assertEqual(_FakeSession.opened, 2)
        self.assertEqual(_FakeSession.closed, 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(prepared[1]["evidence"]["outcome"], "skipped")
        self.assertEqual(prepared[0]["evidence"]["outcome"], "ok")

    def test_retry_uses_a_second_session_when_ids_are_missing(self) -> None:
        _FakeSession.opened = 0
        _FakeSession.closed = 0
        attempts = {"n": 0}

        def run_task(_task, items, _config, _budget, session):
            attempts["n"] += 1
            if attempts["n"] == 1:
                return {
                    "outcome": "review",
                    "missing_item_ids": ["eso:req:0"],
                    "calls": 1,
                }
            return {"outcome": "ok", "missing_item_ids": [], "calls": 1}

        prepared = [
            {"slug": "eso", "evidence_items": [Stage0Item("eso:req:0", bucket="required")]},
        ]
        run_evidence_per_jd(prepared, object(), object(), _FakeSession, run_task)
        self.assertEqual(attempts["n"], 2)
        self.assertEqual(_FakeSession.opened, 2)
        self.assertEqual(prepared[0]["evidence"]["outcome"], "ok")
        self.assertEqual(prepared[0]["evidence"]["calls"], 2)


if __name__ == "__main__":
    unittest.main()
