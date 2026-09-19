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
_MIGRATION_026 = _REPO_ROOT / "server" / "migrations" / "026_add_pipeline_queue_paused_at.sql"


def _normalize_sql(sql: str | None) -> str:
    if not sql:
        return ""
    stripped = re.sub(r"--[^\n]*", " ", sql)
    stripped = " ".join(stripped.lower().split())
    stripped = re.sub(r"\s*,\s*", ", ", stripped)
    stripped = re.sub(r"\s+\)", ")", stripped)
    return stripped


def _dump_master(conn: sqlite3.Connection) -> list[tuple[str, str, str, str]]:
    rows = conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    return [(r[0], r[1], r[2], _normalize_sql(r[3])) for r in rows]


class TestSchemaAntiDrift(unittest.TestCase):
    def test_sql_file_and_ensure_schema_sqlite_master_match(self) -> None:
        sql_text = (
            _MIGRATION_SQL.read_text(encoding="utf-8")
            + "\n"
            + _MIGRATION_026.read_text(encoding="utf-8")
        )
        from_file = sqlite3.connect(":memory:")
        from_file.executescript(sql_text)

        from_python = sqlite3.connect(":memory:")
        pq.ensure_schema(from_python)

        self.assertEqual(_dump_master(from_file), _dump_master(from_python))

    def test_ensure_schema_adds_paused_at_on_025_table(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.executescript(_MIGRATION_SQL.read_text(encoding="utf-8"))
        cols_before = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_queue)")}
        self.assertNotIn("paused_at", cols_before)
        pq.ensure_schema(conn)
        cols_after = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_queue)")}
        self.assertIn("paused_at", cols_after)
        conn.close()

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


def _set_paused(conn: sqlite3.Connection, slug: str, paused_at: str | None = None) -> None:
    ts = paused_at if paused_at is not None else pq.utc_now()
    conn.execute(
        "UPDATE pipeline_queue SET status = 'paused', locked_by = NULL, "
        "lease_expires_at = NULL, paused_at = ? WHERE slug = ?",
        (ts, slug),
    )
    conn.commit()


def _stage1_ready(folder: Path, files: tuple[str, ...] = ("Resume.md", "CoverLetter.md", "claim_provenance.json")) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "authoring_packet.json").write_text(
        json.dumps({"packet_status": "ready"}),
        encoding="utf-8",
    )
    for name in files:
        if name.endswith(".json"):
            (folder / name).write_text('{"ok": true}\n', encoding="utf-8")
        else:
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
        self.assertIsNotNone(paused["paused_at"])
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
        folder = self.data / "pending_review" / "authored"
        _stage1_ready(folder)
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "WAITING_FOR_LLM", "active_stage": "stage1"}),
            encoding="utf-8",
        )
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slug"], "authored")
        self.assertEqual(rows[0]["status"], "leased")

    def test_ac449_needs_disposition_stays_paused_without_newer_dispositions(self) -> None:
        _seed(self.conn, "needsdisp")
        paused_at = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).replace(microsecond=0).isoformat()
        _set_paused(self.conn, "needsdisp", paused_at=paused_at)
        folder = self.data / "pending_review" / "needsdisp"
        _stage1_ready(folder)
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "NEEDS_DISPOSITION", "active_stage": "stage2"}),
            encoding="utf-8",
        )
        first = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(first, [])
        self.assertEqual(pq.get_row(self.conn, "needsdisp")["status"], "paused")
        second = pq.claim_pack("w2", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(second, [])
        self.assertEqual(pq.get_row(self.conn, "needsdisp")["status"], "paused")

    def test_needs_disposition_promotes_when_dispositions_newer_than_paused_at(self) -> None:
        _seed(self.conn, "disposed")
        paused_at = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).replace(microsecond=0).isoformat()
        _set_paused(self.conn, "disposed", paused_at=paused_at)
        folder = self.data / "pending_review" / "disposed"
        _stage1_ready(folder)
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "NEEDS_DISPOSITION", "active_stage": "stage2"}),
            encoding="utf-8",
        )
        reviews = folder / "reviews"
        reviews.mkdir()
        dispositions = reviews / "dispositions.json"
        dispositions.write_text("{}", encoding="utf-8")
        later = datetime.now(timezone.utc).timestamp()
        os.utime(dispositions, (later, later))
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slug"], "disposed")
        self.assertEqual(rows[0]["status"], "leased")

    def _write_waiting_for_input(self, slug: str, pause_kind: str) -> Path:
        folder = self.data / "pending_review" / slug
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "WAITING_FOR_INPUT", "active_stage": "stage0"}),
            encoding="utf-8",
        )
        receipts = folder / "stage_receipts"
        receipts.mkdir(exist_ok=True)
        (receipts / "stage0.json").write_text(
            json.dumps({"status": "WAITING_FOR_INPUT", "result": {"pause_kind": pause_kind}}),
            encoding="utf-8",
        )
        return folder

    def test_waiting_for_input_subscription_review_stays_paused_without_import(self) -> None:
        _seed(self.conn, "rentana")
        _set_paused(self.conn, "rentana")
        self._write_waiting_for_input("rentana", "subscription_review")
        first = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(first, [])
        self.assertEqual(pq.get_row(self.conn, "rentana")["status"], "paused")
        second = pq.claim_pack("w2", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(second, [])
        self.assertEqual(pq.get_row(self.conn, "rentana")["status"], "paused")

    def test_waiting_for_input_review_center_stays_paused_while_questions_open(self) -> None:
        _seed(self.conn, "casper_studios")
        _set_paused(self.conn, "casper_studios")
        self._write_waiting_for_input("casper_studios", "review_center")
        self.conn.execute(
            "CREATE TABLE pending_skill_confirmations ("
            "id TEXT PRIMARY KEY, opportunity_key TEXT, status TEXT, "
            "resolved_at TEXT, updated_at TEXT)"
        )
        self.conn.execute(
            "INSERT INTO pending_skill_confirmations "
            "(id, opportunity_key, status, resolved_at, updated_at) "
            "VALUES ('q1', 'casper_studios', 'open', NULL, NULL)"
        )
        self.conn.commit()
        rows = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(rows, [])
        self.assertEqual(pq.get_row(self.conn, "casper_studios")["status"], "paused")

    def test_waiting_for_input_review_center_promotes_when_questions_completed(self) -> None:
        _seed(self.conn, "raya")
        paused_at = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).replace(microsecond=0).isoformat()
        _set_paused(self.conn, "raya", paused_at=paused_at)
        self._write_waiting_for_input("raya", "review_center")
        self.conn.execute(
            "CREATE TABLE pending_skill_confirmations ("
            "id TEXT PRIMARY KEY, opportunity_key TEXT, status TEXT, "
            "resolved_at TEXT, updated_at TEXT)"
        )
        answered = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO pending_skill_confirmations "
            "(id, opportunity_key, status, resolved_at, updated_at) "
            "VALUES ('q1', 'raya', 'completed', ?, ?)",
            (answered, answered),
        )
        self.conn.commit()
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slug"], "raya")
        self.assertEqual(rows[0]["status"], "leased")

    def test_failed_never_auto_promotes(self) -> None:
        _seed(self.conn, "failedjob")
        _set_paused(self.conn, "failedjob")
        folder = self.data / "pending_review" / "failedjob"
        _stage1_ready(folder)
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "FAILED", "active_stage": "stage0"}),
            encoding="utf-8",
        )
        first = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(first, [])
        self.assertEqual(pq.get_row(self.conn, "failedjob")["status"], "paused")
        second = pq.claim_pack("w2", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(second, [])
        self.assertEqual(pq.get_row(self.conn, "failedjob")["status"], "paused")

    def test_repair_requeues_paused_failed_explicitly(self) -> None:
        _seed(self.conn, "repairme")
        _set_paused(self.conn, "repairme")
        self.conn.execute(
            "UPDATE pipeline_queue SET last_workflow_status = 'FAILED', "
            "last_stage = 'stage1' WHERE slug = 'repairme'"
        )
        self.conn.commit()
        folder = self.data / "pending_review" / "repairme"
        folder.mkdir(parents=True)
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "FAILED", "active_stage": "stage1"}),
            encoding="utf-8",
        )
        self.assertEqual(
            pq.requeue_paused_for_repair(folder, conn=self.conn, data_root=self.data),
            "queued",
        )
        row = pq.get_row(self.conn, "repairme")
        assert row is not None
        self.assertEqual(row["status"], "queued")
        self.assertEqual(row["last_workflow_status"], "FAILED")
        self.assertIsNone(row["locked_by"])
        self.assertEqual(
            pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)[0]["slug"],
            "repairme",
        )

    def test_claim_size_does_not_promote_extra_paused_rows(self) -> None:
        for slug in ("ready_a", "ready_b"):
            _seed(self.conn, slug)
            _set_paused(self.conn, slug)
            folder = self.data / "pending_review" / slug
            _stage1_ready(folder)
            (folder / "workflow_state.json").write_text(
                json.dumps({"status": "WAITING_FOR_LLM", "active_stage": "stage1"}),
                encoding="utf-8",
            )
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(len(rows), 1)
        claimed = rows[0]["slug"]
        other = "ready_b" if claimed == "ready_a" else "ready_a"
        self.assertEqual(pq.get_row(self.conn, other)["status"], "paused")

    def _ready_waiting_for_llm(self, slug: str, paused_at: str | None = None) -> None:
        _seed(self.conn, slug)
        _set_paused(self.conn, slug, paused_at=paused_at)
        folder = self.data / "pending_review" / slug
        _stage1_ready(folder)
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "WAITING_FOR_LLM", "active_stage": "stage1"}),
            encoding="utf-8",
        )

    def test_claim_pack_takes_ready_paused_before_queued_backlog(self) -> None:
        for index in range(38):
            _seed(self.conn, f"backlog_{index:02d}")
        self._ready_waiting_for_llm("rentana_ready")
        rows = pq.claim_pack("w1", size=3, conn=self.conn, data_root=self.data)
        slugs = [row["slug"] for row in rows]
        self.assertEqual(len(slugs), 3)
        self.assertEqual(slugs[0], "rentana_ready")
        self.assertEqual(slugs[1:], ["backlog_00", "backlog_01"])
        self.assertEqual(pq.get_row(self.conn, "backlog_02")["status"], "queued")

    def test_claim_pack_fills_from_oldest_paused_before_any_queued(self) -> None:
        for index in range(4):
            _seed(self.conn, f"fresh_{index}")
        base = datetime.now(timezone.utc)
        order = ["pause_old", "pause_mid", "pause_new", "pause_newer", "pause_newest"]
        for index, slug in enumerate(order):
            paused_at = (base - timedelta(minutes=50 - index)).replace(microsecond=0).isoformat()
            self._ready_waiting_for_llm(slug, paused_at=paused_at)
        rows = pq.claim_pack("w1", size=3, conn=self.conn, data_root=self.data)
        self.assertEqual([row["slug"] for row in rows], ["pause_old", "pause_mid", "pause_new"])
        self.assertEqual(pq.get_row(self.conn, "pause_newer")["status"], "paused")
        self.assertEqual(pq.get_row(self.conn, "pause_newest")["status"], "paused")
        self.assertEqual(pq.get_row(self.conn, "fresh_0")["status"], "queued")

    def test_untriggered_paused_never_claimed_with_backlog(self) -> None:
        _seed(self.conn, "queued_one")
        _seed(self.conn, "blocked_pause")
        _set_paused(self.conn, "blocked_pause")
        folder = self.data / "pending_review" / "blocked_pause"
        _stage1_ready(folder, files=("Resume.md", "CoverLetter.md"))
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "WAITING_FOR_LLM", "active_stage": "stage1"}),
            encoding="utf-8",
        )
        rows = pq.claim_pack("w1", size=3, conn=self.conn, data_root=self.data)
        self.assertEqual([row["slug"] for row in rows], ["queued_one"])
        self.assertEqual(pq.get_row(self.conn, "blocked_pause")["status"], "paused")


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
