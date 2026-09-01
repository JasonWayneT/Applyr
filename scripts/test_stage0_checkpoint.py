#!/usr/bin/env python3
"""Tests for durable Stage 0 run and judgment checkpoints (CR-108)."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stage0_checkpoint import (
    complete_judgment,
    get_completed_judgment,
    make_item_key,
    make_run_key,
    mark_run_status,
    start_run,
    write_spool,
)


_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS = (
    _ROOT / "server" / "migrations" / "018_add_review_center.sql",
    _ROOT / "server" / "migrations" / "019_add_stage0_checkpoints.sql",
)


class TestStage0Checkpoint(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.conn = sqlite3.connect(self.db_path)
        for migration in _MIGRATIONS:
            self.conn.executescript(migration.read_text(encoding="utf-8"))
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        os.unlink(self.db_path)

    def test_hash_keys_are_stable_and_content_sensitive(self) -> None:
        first = make_run_key("acme", "jd-hash", "v1", "policy", "index")
        self.assertEqual(first, make_run_key("acme", "jd-hash", "v1", "policy", "index"))
        self.assertNotEqual(first, make_run_key("acme", "different", "v1", "policy", "index"))
        item_key = make_item_key("required", "Experience with Trello", 0)
        self.assertTrue(item_key.startswith("required:0:"))
        self.assertGreater(len(item_key), len("required:0:"))

    def test_completed_judgment_is_reused_only_for_matching_request(self) -> None:
        run_key = make_run_key("acme", "jd", "v1", "policy", "index")
        start_run(
            self.db_path,
            run_key=run_key,
            opportunity_key="acme",
            jd_hash="jd",
            prompt_version="v1",
            provider_policy_hash="policy",
            evidence_index_hash="index",
            request_hash="request",
        )
        item_key = make_item_key("required", "Experience with Trello", 0)
        complete_judgment(
            self.db_path,
            judgment_key=f"{run_key}:{item_key}",
            run_key=run_key,
            opportunity_key="acme",
            item_key=item_key,
            item_text="Experience with Trello",
            bucket="required",
            request_hash="request",
            content_hash="content",
            evidence_index_hash="index",
            judgment={"evidence_level": 1},
        )
        found = get_completed_judgment(
            self.db_path,
            run_key=run_key,
            item_key=item_key,
            request_hash="request",
            content_hash="content",
            evidence_index_hash="index",
        )
        self.assertEqual(found["judgment"]["evidence_level"], 1)
        self.assertIsNone(
            get_completed_judgment(
                self.db_path,
                run_key=run_key,
                item_key=item_key,
                request_hash="new-request",
                content_hash="content",
                evidence_index_hash="index",
            )
        )

    def test_run_status_and_atomic_spool_are_durable(self) -> None:
        run_key = make_run_key("acme", "jd", "v1", "policy", "index")
        start_run(
            self.db_path,
            run_key=run_key,
            opportunity_key="acme",
            jd_hash="jd",
            prompt_version="v1",
            provider_policy_hash="policy",
            evidence_index_hash="index",
        )
        mark_run_status(self.db_path, run_key, "WAITING_FOR_INPUT")
        row = self.conn.execute(
            "SELECT status FROM stage0_runs WHERE run_key = ?", (run_key,)
        ).fetchone()
        self.assertEqual(row[0], "WAITING_FOR_INPUT")
        with tempfile.TemporaryDirectory() as folder:
            path, digest = write_spool(Path(folder), "request", run_key, {"items": []})
            self.assertTrue(Path(path).exists())
            self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()
