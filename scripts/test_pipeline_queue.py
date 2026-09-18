#!/usr/bin/env python3
"""CR-119 pipeline_queue schema, claim/lease, and CLI tests.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_pipeline_queue -v
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pipeline_queue as pq  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MIGRATION_SQL = _REPO_ROOT / "server" / "migrations" / "025_add_pipeline_queue.sql"


def _normalize_sql(sql: str | None) -> str:
    if not sql:
        return ""
    stripped = re.sub(r"--[^\n]*", " ", sql)
    return " ".join(stripped.lower().split())


def _dump_master(conn: sqlite3.Connection) -> list[tuple[str, str, str, str]]:
    rows = conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    return [(r[0], r[1], r[2], _normalize_sql(r[3])) for r in rows]


class TestSchemaAntiDrift(unittest.TestCase):
    def test_sql_file_and_ensure_schema_sqlite_master_match(self) -> None:
        sql_text = _MIGRATION_SQL.read_text(encoding="utf-8")
        from_file = sqlite3.connect(":memory:")
        from_file.executescript(sql_text)

        from_python = sqlite3.connect(":memory:")
        pq.ensure_schema(from_python)

        self.assertEqual(_dump_master(from_file), _dump_master(from_python))

    def test_connect_sets_row_factory_and_busy_timeout(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA busy_timeout = 0")
        pq.ensure_schema(conn)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_queue'").fetchone()
        self.assertEqual(row["name"], "pipeline_queue")
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        self.assertEqual(timeout, 5000)
        conn.close()


def _seed(conn: sqlite3.Connection, slug: str, title: str = "PM") -> dict:
    return pq.upsert_queued(
        conn,
        slug=slug,
        company=slug,
        title=title,
        url=None,
        url_key=None,
        posting_key=f"{slug}||{title.lower()}",
        networking_contacts_raw="SECRET_CONTACT_DO_NOT_PRINT",
        source_sha256=None,
        source_line=None,
        folder_root="pending_review",
    )


def _set_paused(conn: sqlite3.Connection, slug: str) -> None:
    conn.execute(
        "UPDATE pipeline_queue SET status = 'paused', locked_by = NULL, lease_expires_at = NULL WHERE slug = ?",
        (slug,),
    )
    conn.commit()


def _stage1_ready(folder: Path, files: tuple[str, ...] = ("Resume.md", "CoverLetter.md", "claim_provenance.json")) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "authoring_packet.json").write_text(
        json.dumps({"packet_status": "ready"}),
        encoding="utf-8",
    )
    for name in files:
        (folder / name).write_text("x", encoding="utf-8")


class QueueHarness(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = Path(self._tmpdir.name)
        self.db = self.root / "jobagent.sqlite"
        self.data = self.root / "data"
        (self.data / "pending_review").mkdir(parents=True)
        (self.data / "submissions").mkdir()
        (self.data / "archive" / "skipped").mkdir(parents=True)
        self.conn = pq.connect(self.db)

    def tearDown(self) -> None:
        self.conn.close()


class TestTransitions(QueueHarness):
    def test_legal_and_illegal_transitions(self) -> None:
        _seed(self.conn, "alpha")
        leased = pq.transition("alpha", "leased", worker="w1", token=0, conn=self.conn)
        self.assertEqual(leased["status"], "leased")
        self.assertEqual(leased["fencing_token"], 1)
        running = pq.transition(
            "alpha", "in_progress", worker="w1", token=1, conn=self.conn
        )
        self.assertEqual(running["status"], "in_progress")
        paused = pq.transition("alpha", "paused", worker="w1", token=1, conn=self.conn)
        self.assertEqual(paused["status"], "paused")
        self.assertIsNone(paused["locked_by"])
        queued = pq.transition("alpha", "queued", worker="", token=1, conn=self.conn)
        self.assertEqual(queued["status"], "queued")

        _seed(self.conn, "beta")
        leased = pq.transition("beta", "leased", worker="w1", token=0, conn=self.conn)
        running = pq.transition("beta", "in_progress", worker="w1", token=1, conn=self.conn)
        done = pq.transition("beta", "done", worker="w1", token=1, conn=self.conn)
        self.assertEqual(done["status"], "done")

        _seed(self.conn, "gamma")
        leased = pq.transition("gamma", "leased", worker="w1", token=0, conn=self.conn)
        released = pq.transition("gamma", "queued", worker="w1", token=1, conn=self.conn)
        self.assertEqual(released["status"], "queued")

        with self.assertRaises(pq.IllegalTransition):
            pq.transition("gamma", "done", worker="", token=1, conn=self.conn)
        _seed(self.conn, "delta")
        with self.assertRaises(pq.IllegalTransition):
            pq.transition("delta", "paused", worker="", token=0, conn=self.conn)
        _seed(self.conn, "epsilon")
        pq.transition("epsilon", "leased", worker="w1", token=0, conn=self.conn)
        pq.transition("epsilon", "in_progress", worker="w1", token=1, conn=self.conn)
        pq.transition("epsilon", "paused", worker="w1", token=1, conn=self.conn)
        with self.assertRaises(pq.IllegalTransition):
            pq.transition("epsilon", "done", worker="", token=1, conn=self.conn)


class TestClaimPack(QueueHarness):
    def test_size_bounds_and_token_increment(self) -> None:
        for i in range(3):
            _seed(self.conn, f"pack{i}")
        with self.assertRaises(pq.PackSizeError):
            pq.claim_pack("w1", size=11, conn=self.conn, data_root=self.data)
        with self.assertRaises(pq.PackSizeError):
            pq.claim_pack("w1", size=0, conn=self.conn, data_root=self.data)
        rows = pq.claim_pack("w1", size=2, conn=self.conn, data_root=self.data)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["status"] == "leased" for r in rows))
        self.assertTrue(all(r["fencing_token"] == 1 for r in rows))
        self.assertTrue(all(r["locked_by"] == "w1" for r in rows))

    def test_paused_does_not_occupy_slot_until_promoted(self) -> None:
        _seed(self.conn, "ready_one")
        _seed(self.conn, "still_paused")
        _set_paused(self.conn, "still_paused")
        folder = self.data / "pending_review" / "still_paused"
        _stage1_ready(folder, files=("Resume.md", "CoverLetter.md"))
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "WAITING_FOR_LLM", "active_stage": "stage1"}),
            encoding="utf-8",
        )
        rows = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        slugs = {r["slug"] for r in rows}
        self.assertEqual(slugs, {"ready_one"})
        self.assertEqual(pq.get_row(self.conn, "still_paused")["status"], "paused")

    def test_ac448_two_of_three_files_stay_paused(self) -> None:
        _seed(self.conn, "partial")
        _set_paused(self.conn, "partial")
        folder = self.data / "pending_review" / "partial"
        _stage1_ready(folder, files=("Resume.md", "CoverLetter.md"))
        rows = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(rows, [])
        self.assertEqual(pq.get_row(self.conn, "partial")["status"], "paused")

    def test_paused_promotes_when_stage1_ready(self) -> None:
        _seed(self.conn, "authored")
        _set_paused(self.conn, "authored")
        _stage1_ready(self.data / "pending_review" / "authored")
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slug"], "authored")
        self.assertEqual(rows[0]["status"], "leased")


class TestHeartbeatReleaseExpiry(QueueHarness):
    def test_heartbeat_extends_and_release_returns_leased(self) -> None:
        _seed(self.conn, "hb1")
        claimed = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        before = claimed[0]["lease_expires_at"]
        pq.heartbeat("w1", lease_minutes=40, conn=self.conn)
        after = pq.get_row(self.conn, "hb1")["lease_expires_at"]
        self.assertGreater(after, before)
        released = pq.release("w1", conn=self.conn)
        self.assertEqual(released[0]["status"], "queued")
        self.assertIsNone(released[0]["locked_by"])

    def test_expiry_second_worker_and_stale_token_rejected(self) -> None:
        _seed(self.conn, "race")
        first = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        old_token = first[0]["fencing_token"]
        expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(
            microsecond=0
        ).isoformat()
        self.conn.execute(
            "UPDATE pipeline_queue SET lease_expires_at = ? WHERE slug = ?",
            (expired, "race"),
        )
        self.conn.commit()
        second = pq.claim_pack("w2", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(second[0]["locked_by"], "w2")
        snapshot = dict(pq.get_row(self.conn, "race") or {})
        with self.assertRaises(pq.FenceRejected):
            pq.transition(
                "race",
                "in_progress",
                worker="w1",
                token=old_token,
                conn=self.conn,
            )
        after = dict(pq.get_row(self.conn, "race") or {})
        self.assertEqual(after, snapshot)


class TestQueueClaimCli(QueueHarness):
    def test_cli_claim_status_never_prints_contacts(self) -> None:
        from queue_claim import main

        _seed(self.conn, "cli1")
        self.conn.close()
        buf = __import__("io").StringIO()
        with mock.patch("sys.stdout", buf):
            rc = main(
                ["--db", str(self.db), "claim", "--worker", "harness-1", "--size", "1"]
            )
        self.assertEqual(rc, 0)
        text = buf.getvalue()
        self.assertNotIn("SECRET_CONTACT_DO_NOT_PRINT", text)
        self.assertNotIn("networking_contacts_raw", text)
        buf2 = __import__("io").StringIO()
        with mock.patch("sys.stdout", buf2):
            rc = main(["--db", str(self.db), "status"])
        self.assertEqual(rc, 0)
        self.assertNotIn("SECRET_CONTACT_DO_NOT_PRINT", buf2.getvalue())
        rc = main(["--db", str(self.db), "claim", "--worker", "harness-1", "--size", "11"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
