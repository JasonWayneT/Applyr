#!/usr/bin/env python3
"""CR-119 pipeline_queue schema, claim/lease, and CLI tests.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_pipeline_queue -v
"""
from __future__ import annotations

import json
import os
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
_MIGRATION_027 = _REPO_ROOT / "server" / "migrations" / "027_add_pipeline_queue_paused_reason.sql"
_MIGRATION_028 = _REPO_ROOT / "server" / "migrations" / "028_add_pipeline_queue_requeue_audit.sql"


def _table_info(conn: sqlite3.Connection, table: str) -> list[tuple[str, str, int, object, int]]:
    return [
        (row[1], row[2], row[3], row[5], row[4])
        for row in conn.execute(f"PRAGMA table_info({table})")
    ]


def _index_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows]


class TestSchemaAntiDrift(unittest.TestCase):
    def test_sql_file_and_ensure_schema_sqlite_master_match(self) -> None:
        sql_text = (
            _MIGRATION_SQL.read_text(encoding="utf-8")
            + "\n"
            + _MIGRATION_026.read_text(encoding="utf-8")
            + "\n"
            + _MIGRATION_027.read_text(encoding="utf-8")
            + "\n"
            + _MIGRATION_028.read_text(encoding="utf-8")
        )
        from_file = sqlite3.connect(":memory:")
        from_file.executescript(sql_text)

        from_python = sqlite3.connect(":memory:")
        pq.ensure_schema(from_python)

        for table in ("pipeline_queue", "csv_ingest_ledger", "csv_quarantine"):
            self.assertEqual(_table_info(from_file, table), _table_info(from_python, table))
        self.assertEqual(_index_names(from_file), _index_names(from_python))

    def test_ensure_schema_adds_paused_at_on_025_table(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.executescript(_MIGRATION_SQL.read_text(encoding="utf-8"))
        cols_before = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_queue)")}
        self.assertNotIn("paused_at", cols_before)
        pq.ensure_schema(conn)
        cols_after = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_queue)")}
        self.assertIn("paused_at", cols_after)
        conn.close()

    def test_ensure_schema_adds_paused_reason_on_025_table(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.executescript(_MIGRATION_SQL.read_text(encoding="utf-8"))
        cols_before = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_queue)")}
        self.assertNotIn("paused_reason", cols_before)
        pq.ensure_schema(conn)
        cols_after = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_queue)")}
        self.assertIn("paused_reason", cols_after)
        conn.close()

    def test_ensure_schema_adds_requeue_columns_on_025_table(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.executescript(_MIGRATION_SQL.read_text(encoding="utf-8"))
        cols_before = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_queue)")}
        self.assertNotIn("requeued_by", cols_before)
        pq.ensure_schema(conn)
        cols_after = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_queue)")}
        self.assertIn("requeued_by", cols_after)
        self.assertIn("requeue_reason", cols_after)
        self.assertIn("requeued_at", cols_after)
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

        # CR-123 FR-363 supersedes CR-119 Story 3.1 for queued→done only.
        closed = pq.transition("gamma", "done", worker="", token=1, conn=self.conn)
        self.assertEqual(closed["status"], "done")
        _seed(self.conn, "delta")
        with self.assertRaises(pq.IllegalTransition):
            pq.transition("delta", "paused", worker="", token=0, conn=self.conn)
        _seed(self.conn, "epsilon")
        pq.transition("epsilon", "leased", worker="w1", token=0, conn=self.conn)
        pq.transition("epsilon", "in_progress", worker="w1", token=1, conn=self.conn)
        paused = pq.transition("epsilon", "paused", worker="w1", token=1, conn=self.conn)
        done = pq.transition(
            "epsilon",
            "done",
            worker="",
            token=int(paused["fencing_token"]),
            conn=self.conn,
            paused_reason=pq.PAUSED_REASON_READY_TO_FINALIZE,
        )
        self.assertEqual(done["status"], "done")
        self.assertIsNone(done["paused_reason"])


class TestCr123CloseTransitions(QueueHarness):
    """CR-123 Story 2.1: queued→done / leased→done; widen mark_done (FR-363)."""

    def test_queued_to_done_via_mark_done(self) -> None:
        _seed(self.conn, "close_queued")
        row = pq.get_row(self.conn, "close_queued")
        assert row is not None
        self.assertEqual(row["status"], "queued")
        self.assertIsNone(row["locked_by"])
        done = pq.mark_done("close_queued", conn=self.conn)
        assert done is not None
        self.assertEqual(done["status"], "done")
        self.assertIsNone(done["locked_by"])

    def test_leased_to_done_via_mark_done(self) -> None:
        _seed(self.conn, "close_leased")
        leased = pq.transition(
            "close_leased", "leased", worker="w1", token=0, conn=self.conn
        )
        self.assertEqual(leased["status"], "leased")
        self.assertEqual(leased["locked_by"], "w1")
        done = pq.mark_done("close_leased", conn=self.conn)
        assert done is not None
        self.assertEqual(done["status"], "done")
        self.assertIsNone(done["locked_by"])

    def test_mismatched_token_on_leased_to_done_raises_fence_rejected(self) -> None:
        _seed(self.conn, "fence_leased")
        leased = pq.transition(
            "fence_leased", "leased", worker="w1", token=0, conn=self.conn
        )
        snapshot = dict(pq.get_row(self.conn, "fence_leased") or {})
        with self.assertRaises(pq.FenceRejected):
            pq.transition(
                "fence_leased",
                "done",
                worker="w1",
                token=int(leased["fencing_token"]) + 99,
                conn=self.conn,
            )
        after = dict(pq.get_row(self.conn, "fence_leased") or {})
        self.assertEqual(after["status"], "leased")
        self.assertEqual(after, snapshot)

    def test_mark_done_done_to_done_is_noop(self) -> None:
        _seed(self.conn, "already_done")
        pq.transition("already_done", "leased", worker="w1", token=0, conn=self.conn)
        pq.transition(
            "already_done", "in_progress", worker="w1", token=1, conn=self.conn
        )
        first = pq.mark_done("already_done", conn=self.conn)
        assert first is not None
        self.assertEqual(first["status"], "done")
        snapshot = dict(first)
        second = pq.mark_done("already_done", conn=self.conn)
        assert second is not None
        self.assertEqual(second["status"], "done")
        self.assertEqual(dict(second), snapshot)


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
        folder = self.data / "pending_review" / "needsdisp"
        _stage1_ready(folder)
        paused_at = (
            datetime.now(timezone.utc) + timedelta(seconds=5)
        ).replace(microsecond=0).isoformat()
        _set_paused(self.conn, "needsdisp", paused_at=paused_at)
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
        # updated_at (whole-second, matching utc_now()'s own precision) is what
        # actually drives promotion now -- see FIXQUEUE 2026-09-18 item #5.
        later = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        dispositions.write_text(json.dumps({"updated_at": later}), encoding="utf-8")
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slug"], "disposed")
        self.assertEqual(rows[0]["status"], "leased")

    def test_hm_left_open_promotes_when_the_warning_is_gone(self) -> None:
        _seed(self.conn, "stalehm")
        folder = self.data / "pending_review" / "stalehm"
        _stage1_ready(folder)
        (folder / "Resume.md").write_text(
            "## PROFESSIONAL SUMMARY\n\nBrought the teams into a unified roadmap.\n",
            encoding="utf-8",
        )
        (folder / "CoverLetter.md").write_text(
            "Dear Hiring Manager,\n\nThe roadmap is the proof.\n",
            encoding="utf-8",
        )
        (folder / "workflow_state.json").write_text(
            json.dumps(
                {
                    "status": "NEEDS_DISPOSITION",
                    "active_stage": "stage2",
                    "metadata": {"hm_queue_settle": "left_open"},
                    "stages": {
                        "stage2": {
                            "status": "NEEDS_DISPOSITION",
                            "subphases": {"hm": {"status": "NEEDS_DISPOSITION"}},
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        reviews = folder / "reviews"
        reviews.mkdir()
        (reviews / "hm_findings.json").write_text(
            json.dumps(
                {
                    "findings": [
                        {
                            "id": "hm.lint.warn.wrong-job company bleed.LW-032.0",
                            "severity": "WARN",
                            "message": "Wrong-job content bleed: documents name 'Unified'",
                        },
                        {
                            "id": "hm.critical_read",
                            "severity": "WARN",
                            "message": "Confirm a hiring-manager read",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        (reviews / "dispositions.json").write_text(
            json.dumps({"by_finding_id": {}, "updated_at": "2026-09-22T00:00:00Z"}),
            encoding="utf-8",
        )
        _set_paused(
            self.conn,
            "stalehm",
            paused_at=(datetime.now(timezone.utc) + timedelta(seconds=5))
            .replace(microsecond=0)
            .isoformat(),
        )
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual([row["slug"] for row in rows], ["stalehm"])

    def test_hm_left_open_stays_when_the_warning_is_still_live(self) -> None:
        _seed(self.conn, "livehm")
        folder = self.data / "pending_review" / "livehm"
        _stage1_ready(folder)
        (folder / "workflow_state.json").write_text(
            json.dumps(
                {
                    "status": "NEEDS_DISPOSITION",
                    "metadata": {"hm_queue_settle": "left_open"},
                    "stages": {
                        "stage2": {
                            "status": "NEEDS_DISPOSITION",
                            "subphases": {"hm": {"status": "NEEDS_DISPOSITION"}},
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        reviews = folder / "reviews"
        reviews.mkdir()
        (reviews / "hm_findings.json").write_text(
            json.dumps(
                {
                    "findings": [
                        {
                            "id": "hm.lint.warn.wrong-job company bleed.LW-032.0",
                            "severity": "WARN",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (reviews / "dispositions.json").write_text(
            json.dumps({"updated_at": "2026-09-22T00:00:00Z"}),
            encoding="utf-8",
        )
        _set_paused(
            self.conn,
            "livehm",
            paused_at=(datetime.now(timezone.utc) + timedelta(seconds=5))
            .replace(microsecond=0)
            .isoformat(),
        )

        class _Hit:
            rule_id = "LW-032"

        class _Result:
            warns = [_Hit()]
            blocks: list[object] = []

        with mock.patch(
            "submission_linter.lint_folder",
            return_value=[{"result": _Result()}],
        ):
            rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(rows, [])

    def test_stage1_rollback_promotes_once_more(self) -> None:
        _seed(self.conn, "retryrepair")
        folder = self.data / "pending_review" / "retryrepair"
        _stage1_ready(folder)
        (folder / "workflow_state.json").write_text(
            json.dumps(
                {
                    "status": "FAILED",
                    "active_stage": "stage1",
                    "stages": {"stage1": {"status": "FAILED"}},
                }
            ),
            encoding="utf-8",
        )
        (folder / "stage1_repair_state.json").write_text(
            json.dumps(
                {
                    "last_outcome": "no_progress_blocking",
                    "no_progress_streak": 1,
                }
            ),
            encoding="utf-8",
        )
        later = (
            datetime.now(timezone.utc) + timedelta(seconds=5)
        ).replace(microsecond=0).isoformat()
        _set_paused(self.conn, "retryrepair", paused_at=later)
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual([row["slug"] for row in rows], ["retryrepair"])

        _seed(self.conn, "stoprepair")
        stopped = self.data / "pending_review" / "stoprepair"
        _stage1_ready(stopped)
        (stopped / "workflow_state.json").write_text(
            (folder / "workflow_state.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (stopped / "stage1_repair_state.json").write_text(
            json.dumps(
                {
                    "last_outcome": "no_progress_blocking",
                    "no_progress_streak": 2,
                }
            ),
            encoding="utf-8",
        )
        _set_paused(self.conn, "stoprepair", paused_at=later)
        again = pq.claim_pack("w2", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(again, [])

    def test_timeout_waits_then_retries_and_stops_at_four(self) -> None:
        """FR-378: a provider timeout is claimed after the wait, not four times in a row."""
        from datetime import datetime, timedelta, timezone

        def _failed_draft(slug: str) -> Path:
            _seed(self.conn, slug)
            folder = self.data / "pending_review" / slug
            _stage1_ready(folder)
            (folder / "workflow_state.json").write_text(
                json.dumps(
                    {
                        "status": "FAILED",
                        "active_stage": "stage1",
                        "stages": {"stage1": {"status": "FAILED"}},
                    }
                ),
                encoding="utf-8",
            )
            return folder

        waiting = _failed_draft("timeoutwait")
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).replace(microsecond=0)
        (waiting / "stage1_repair_state.json").write_text(
            json.dumps(
                {
                    "last_outcome": "repair_timeout",
                    "timeout_attempts": 1,
                    "no_progress_streak": 0,
                    "next_retry_at": future.isoformat(),
                }
            ),
            encoding="utf-8",
        )
        _set_paused(self.conn, "timeoutwait", paused_at=future.isoformat())
        self.assertEqual(
            pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data),
            [],
        )

        ready = _failed_draft("timeoutready")
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(microsecond=0)
        (ready / "stage1_repair_state.json").write_text(
            json.dumps(
                {
                    "last_outcome": "repair_timeout",
                    "timeout_attempts": 1,
                    "no_progress_streak": 0,
                    "next_retry_at": past.isoformat(),
                }
            ),
            encoding="utf-8",
        )
        _set_paused(self.conn, "timeoutready", paused_at=past.isoformat())
        claimed = pq.claim_pack("w2", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual([row["slug"] for row in claimed], ["timeoutready"])

        stopped = _failed_draft("timeoutstop")
        (stopped / "stage1_repair_state.json").write_text(
            json.dumps(
                {
                    "last_outcome": "repair_timeout",
                    "timeout_attempts": 4,
                    "no_progress_streak": 0,
                    "next_retry_at": past.isoformat(),
                }
            ),
            encoding="utf-8",
        )
        _set_paused(self.conn, "timeoutstop", paused_at=past.isoformat())
        self.assertEqual(
            pq.claim_pack("w3", size=1, conn=self.conn, data_root=self.data),
            [],
        )

    def test_needs_disposition_does_not_promote_on_same_second_mtime_noise(self) -> None:
        """FIXQUEUE 2026-09-18 item #5 regression: a real production bug where a
        dispositions.json write in the *same wall-clock second* as the pause
        (the normal case -- the file is written moments before the row pauses)
        used to compare as "newer" than paused_at purely from sub-second
        filesystem mtime noise, because paused_at is truncated to whole
        seconds by utc_now(). This kept re-promoting crio/lexipol -- rows
        genuinely stuck on a non-disposable BLOCK -- for a full re-run of
        Truth->ATS->HM->Mech even though nothing had actually changed since
        the pause. Reading dispositions.json's own `updated_at` field (same
        whole-second precision as paused_at) must not promote here."""
        _seed(self.conn, "stuck")
        now = datetime.now(timezone.utc).replace(microsecond=0)
        paused_at = now.isoformat()
        _set_paused(self.conn, "stuck", paused_at=paused_at)
        folder = self.data / "pending_review" / "stuck"
        _stage1_ready(folder)
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "NEEDS_DISPOSITION", "active_stage": "stage2"}),
            encoding="utf-8",
        )
        reviews = folder / "reviews"
        reviews.mkdir()
        dispositions = reviews / "dispositions.json"
        # Same logical write as the pause itself: updated_at equals paused_at
        # exactly, but the file's OS mtime is set slightly *later* in
        # wall-clock time (same second, non-zero microseconds) to reproduce
        # the exact filesystem-noise condition that caused false promotion
        # before this fix -- the bug used to read st_mtime instead of this
        # field, so this line existing at all is the regression check.
        dispositions.write_text(json.dumps({"updated_at": paused_at}), encoding="utf-8")
        noisy_mtime = now.timestamp() + 0.734
        os.utime(dispositions, (noisy_mtime, noisy_mtime))
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(rows, [])
        self.assertEqual(pq.get_row(self.conn, "stuck")["status"], "paused")

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

    def test_conversion_risk_promotes_when_stored_reasons_are_chrome(self) -> None:
        _seed(self.conn, "amplify")
        _set_paused(self.conn, "amplify")
        folder = self._write_waiting_for_input("amplify", "conversion_risk")
        (folder / "stage0_fit_gate.json").write_text(
            json.dumps(
                {
                    "company": "Amplify",
                    "decision": "PASS",
                    "required": [
                        {
                            "item": "ideally within EdTech or a B2B2C environment",
                            "evidence_level": 0,
                        }
                    ],
                    "not_present_named_tools": [
                        {"skill_key": "edtech", "display_name": "EdTech"},
                        {"skill_key": "b2b2c", "display_name": "B2B2C"},
                    ],
                    "conversion_feasibility": {
                        "verdict": "risk",
                        "reasons": ["not_present_required_tool:EdTech"],
                    },
                }
            ),
            encoding="utf-8",
        )
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual([row["slug"] for row in rows], ["amplify"])

    def test_conversion_risk_promotes_when_example_list_is_anchored(self) -> None:
        _seed(self.conn, "eso")
        _set_paused(self.conn, "eso")
        folder = self._write_waiting_for_input("eso", "conversion_risk")
        (folder / "stage0_fit_gate.json").write_text(
            json.dumps(
                {
                    "company": "ESO",
                    "decision": "PASS",
                    "required": [
                        {
                            "item": (
                                "Hands-on experience using AI tools (for example, "
                                "Claude, Magic Patterns, or similar platforms)."
                            ),
                            "evidence_level": 0,
                        }
                    ],
                    "conversion_feasibility": {
                        "verdict": "risk",
                        "reasons": [
                            "not_present_required_tool:Magic Patterns",
                            "required_unproven_named_tool:Magic Patterns",
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )
        with mock.patch(
            "build_stage0_fit_gate._load_skills_catalog_terms_shared",
            return_value=frozenset({"Claude"}),
        ):
            rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual([row["slug"] for row in rows], ["eso"])

    def test_conversion_risk_missing_tool_promotes(self) -> None:
        """A required product missing from work experience is a card, not a pause."""
        _seed(self.conn, "velera")
        _set_paused(self.conn, "velera")
        folder = self._write_waiting_for_input("velera", "conversion_risk")
        (folder / "stage0_fit_gate.json").write_text(
            json.dumps(
                {
                    "company": "Velera",
                    "decision": "PASS",
                    "required": [
                        {
                            "item": "Experience with Microsoft Dynamics 365",
                            "evidence_level": 0,
                        }
                    ],
                    "not_present_named_tools": [
                        {"skill_key": "dynamics", "display_name": "Dynamics"},
                    ],
                    "conversion_feasibility": {
                        "verdict": "risk",
                        "reasons": ["required_unproven_named_tool:Dynamics"],
                    },
                }
            ),
            encoding="utf-8",
        )
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual([row["slug"] for row in rows], ["velera"])

    def test_conversion_risk_stays_paused_without_apply_anyway(self) -> None:
        _seed(self.conn, "velosio")
        _set_paused(self.conn, "velosio")
        self._write_waiting_for_input("velosio", "conversion_risk")
        first = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(first, [])
        self.assertEqual(pq.get_row(self.conn, "velosio")["status"], "paused")

    def test_conversion_risk_promotes_when_apply_anyway_newer(self) -> None:
        _seed(self.conn, "omnissa")
        paused_at = (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        ).replace(microsecond=0).isoformat()
        _set_paused(self.conn, "omnissa", paused_at=paused_at)
        folder = self._write_waiting_for_input("omnissa", "conversion_risk")
        (folder / pq.CONVERSION_RISK_OVERRIDE_NAME).write_text(
            json.dumps({"reason": "apply_anyway"}) + "\n",
            encoding="utf-8",
        )
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slug"], "omnissa")

    def test_open_hard_gate_card_does_not_hold_the_queue(self) -> None:
        """FR-381: an open hard-gate card is not a reason to stay paused."""
        _seed(self.conn, "casper_studios")
        _set_paused(self.conn, "casper_studios")
        self._write_waiting_for_input("casper_studios", "review_center")
        self.conn.execute(
            "CREATE TABLE pending_skill_confirmations ("
            "id TEXT PRIMARY KEY, opportunity_key TEXT, status TEXT, "
            "question_type TEXT, resolved_at TEXT, updated_at TEXT)"
        )
        self.conn.execute(
            "INSERT INTO pending_skill_confirmations "
            "(id, opportunity_key, status, question_type, resolved_at, updated_at) "
            "VALUES ('q1', 'casper_studios', 'open', 'hard_gate_review', NULL, NULL)"
        )
        self.conn.commit()
        rows = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual([row["slug"] for row in rows], ["casper_studios"])

    def test_decide_holds_skips_under_40_and_queues_a_pass(self) -> None:
        """FR-381: a stored score under 40 is a skip. 55 goes back to queued."""
        _seed(self.conn, "lowfit")
        _set_paused(self.conn, "lowfit")
        low = self._write_waiting_for_input("lowfit", "review_center")
        (low / "stage0_fit_gate.json").write_text(
            json.dumps({"decision": "PASS", "fit_score": 38, "required": []}),
            encoding="utf-8",
        )
        _seed(self.conn, "okfit")
        _set_paused(self.conn, "okfit")
        ok = self._write_waiting_for_input("okfit", "review_center")
        (ok / "stage0_fit_gate.json").write_text(
            json.dumps({"decision": "PASS", "fit_score": 55, "required": []}),
            encoding="utf-8",
        )
        _seed(self.conn, "broken")
        _set_paused(self.conn, "broken")
        self._write_waiting_for_input("broken", "review_center")
        self.conn.execute(
            "UPDATE pipeline_queue SET last_workflow_status = 'FAILED' WHERE slug = 'broken'"
        )
        self.conn.execute(
            "CREATE TABLE pending_skill_confirmations (id TEXT PRIMARY KEY)"
        )
        self.conn.commit()
        outcome = pq.decide_queue_holds(conn=self.conn, data_root=self.data)
        self.assertIn("lowfit", outcome["skip"])
        self.assertEqual(pq.get_row(self.conn, "lowfit")["paused_reason"], "decided_skip")
        self.assertIn("okfit", outcome["continue"])
        self.assertEqual(pq.get_row(self.conn, "okfit")["status"], "queued")
        self.assertIn("broken", outcome["leave"])
        self.assertEqual(pq.get_row(self.conn, "broken")["status"], "paused")
        claimed = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertNotIn("lowfit", [row["slug"] for row in claimed])

    def test_domain_years_on_the_jd_skips_without_a_stored_score(self) -> None:
        """FR-381: healthcare years on the posting skip even when the gate is empty."""
        _seed(self.conn, "healthco")
        _set_paused(self.conn, "healthco")
        folder = self._write_waiting_for_input("healthco", "review_center")
        (folder / "Original_JD.txt").write_text(
            "Minimum of 3 years of experience in healthcare technology is required.\n",
            encoding="utf-8",
        )
        (folder / "stage0_fit_gate.json").write_text("{}", encoding="utf-8")
        _seed(self.conn, "paymentsco")
        _set_paused(self.conn, "paymentsco")
        self._write_waiting_for_input("paymentsco", "review_center")
        self.conn.execute(
            "CREATE TABLE pending_skill_confirmations (id TEXT PRIMARY KEY)"
        )
        self.conn.commit()
        outcome = pq.decide_queue_holds(conn=self.conn, data_root=self.data)
        self.assertIn("healthco", outcome["skip"])
        self.assertEqual(
            pq.get_row(self.conn, "healthco")["paused_reason"], "decided_skip"
        )
        self.assertIn("paymentsco", outcome["continue"])
        self.assertEqual(pq.get_row(self.conn, "paymentsco")["status"], "queued")

    def test_waiting_for_input_review_center_promotes_when_only_skill_cards_open(self) -> None:
        """CR-122 / AC-469: open skill_presence does not hold the CSV queue."""
        _seed(self.conn, "employers")
        _set_paused(self.conn, "employers")
        self._write_waiting_for_input("employers", "review_center")
        self.conn.execute(
            "CREATE TABLE pending_skill_confirmations ("
            "id TEXT PRIMARY KEY, opportunity_key TEXT, status TEXT, "
            "question_type TEXT, resolved_at TEXT, updated_at TEXT)"
        )
        self.conn.execute(
            "INSERT INTO pending_skill_confirmations "
            "(id, opportunity_key, status, question_type, resolved_at, updated_at) "
            "VALUES ('q1', 'employers', 'open', 'skill_presence', NULL, NULL)"
        )
        self.conn.commit()
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slug"], "employers")
        self.assertEqual(rows[0]["status"], "leased")

    def test_live_pending_review_is_not_closed_by_archive_skipped_ghost(self) -> None:
        """A prior skip folder must not close a live pending_review of the same slug."""
        _seed(self.conn, "employers")
        _set_paused(self.conn, "employers")
        self._write_waiting_for_input("employers", "review_center")
        ghost = self.data / "archive" / "skipped" / "employers"
        ghost.mkdir(parents=True)
        (ghost / "Original_JD.txt").write_text("old skip\n", encoding="utf-8")
        self.conn.execute(
            "CREATE TABLE pending_skill_confirmations ("
            "id TEXT PRIMARY KEY, opportunity_key TEXT, status TEXT, "
            "question_type TEXT, resolved_at TEXT, updated_at TEXT)"
        )
        self.conn.commit()
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slug"], "employers")
        self.assertEqual(rows[0]["status"], "leased")
        self.assertNotEqual(pq.get_row(self.conn, "employers")["status"], "done")

    def test_archive_only_slug_still_closes_as_already_handled(self) -> None:
        _seed(self.conn, "oldskip")
        folder = self.data / "archive" / "skipped" / "oldskip"
        folder.mkdir(parents=True)
        (folder / "Original_JD.txt").write_text("archived\n", encoding="utf-8")
        self.conn.execute(
            "UPDATE pipeline_queue SET folder_root = ? WHERE slug = ?",
            ("archive/skipped", "oldskip"),
        )
        self.conn.commit()
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(rows, [])
        self.assertEqual(pq.get_row(self.conn, "oldskip")["status"], "done")

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
            "question_type TEXT, resolved_at TEXT, updated_at TEXT)"
        )
        answered = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO pending_skill_confirmations "
            "(id, opportunity_key, status, question_type, resolved_at, updated_at) "
            "VALUES ('q1', 'raya', 'completed', 'hard_gate_review', ?, ?)",
            (answered, answered),
        )
        self.conn.commit()
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slug"], "raya")
        self.assertEqual(rows[0]["status"], "leased")

    def test_review_center_resume_marker_blocks_another_claim(self) -> None:
        _seed(self.conn, "raya")
        _set_paused(self.conn, "raya")
        folder = self._write_waiting_for_input("raya", "review_center")
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS pending_skill_confirmations ("
            "id TEXT PRIMARY KEY, opportunity_key TEXT, status TEXT, "
            "question_type TEXT, resolved_at TEXT, updated_at TEXT)"
        )
        answered = "2026-09-22T12:00:00+00:00"
        self.conn.execute(
            "INSERT INTO pending_skill_confirmations "
            "(id, opportunity_key, status, question_type, resolved_at, updated_at) "
            "VALUES ('q-marker', 'raya', 'completed', 'skill_presence', ?, ?)",
            (answered, answered),
        )
        self.conn.commit()
        pq.write_review_center_resumed_marker(folder)
        rows = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(rows, [])
        self.assertEqual(pq.get_row(self.conn, "raya")["status"], "paused")

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

    def test_failed_over_budget_without_resume_promotes_once(self) -> None:
        """AC-459: packet-over-budget FAILED with no Resume.md is claimable once."""
        _seed(self.conn, "clarion")
        _set_paused(self.conn, "clarion")
        folder = self.data / "pending_review" / "clarion"
        folder.mkdir(parents=True)
        (folder / "authoring_packet.json").write_text(
            json.dumps(
                {
                    "packet_status": "incomplete",
                    "incomplete_reasons": ["Over token budget: 8565 > 8000"],
                }
            ),
            encoding="utf-8",
        )
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "FAILED", "active_stage": "stage1"}),
            encoding="utf-8",
        )
        first = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["slug"], "clarion")
        self.assertEqual(first[0]["status"], "leased")

    def test_failed_over_budget_retry_marker_blocks_second_claim(self) -> None:
        _seed(self.conn, "sourcegraph")
        _set_paused(self.conn, "sourcegraph")
        folder = self.data / "pending_review" / "sourcegraph"
        folder.mkdir(parents=True)
        (folder / "authoring_packet.json").write_text(
            json.dumps(
                {
                    "packet_status": "incomplete",
                    "incomplete_reasons": ["Over token budget: 8783 > 8000"],
                }
            ),
            encoding="utf-8",
        )
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "FAILED", "active_stage": "stage1"}),
            encoding="utf-8",
        )
        pq.write_stage1_budget_retry_marker(folder)
        first = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(first, [])
        self.assertEqual(pq.get_row(self.conn, "sourcegraph")["status"], "paused")

    def test_failed_ready_packet_without_resume_promotes_once(self) -> None:
        _seed(self.conn, "confidential")
        _set_paused(self.conn, "confidential")
        folder = self.data / "pending_review" / "confidential"
        folder.mkdir(parents=True)
        (folder / "authoring_packet.json").write_text(
            json.dumps({"packet_status": "ready"}),
            encoding="utf-8",
        )
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "FAILED", "active_stage": "stage1"}),
            encoding="utf-8",
        )
        first = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["slug"], "confidential")

    def test_failed_incomplete_not_budget_stays_paused(self) -> None:
        _seed(self.conn, "missingexcerpt")
        _set_paused(self.conn, "missingexcerpt")
        folder = self.data / "pending_review" / "missingexcerpt"
        folder.mkdir(parents=True)
        (folder / "authoring_packet.json").write_text(
            json.dumps(
                {
                    "packet_status": "incomplete",
                    "incomplete_reasons": ["Missing excerpt for ACC-1"],
                }
            ),
            encoding="utf-8",
        )
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "FAILED", "active_stage": "stage1"}),
            encoding="utf-8",
        )
        first = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(first, [])
        self.assertEqual(pq.get_row(self.conn, "missingexcerpt")["status"], "paused")

    def test_failed_text_to_id_provenance_is_claimed(self) -> None:
        """A cite map is not a finished failure. Verify can store it as rows."""
        _seed(self.conn, "amplify")
        _set_paused(self.conn, "amplify")
        folder = self.data / "pending_review" / "amplify"
        folder.mkdir(parents=True)
        (folder / "Resume.md").write_text("# Name\n\n* Shipped the workflow.\n", encoding="utf-8")
        (folder / "claim_provenance.json").write_text(
            json.dumps({"resume": {"Shipped the workflow.": "ACC-101"}}),
            encoding="utf-8",
        )
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "FAILED", "active_stage": "stage1"}),
            encoding="utf-8",
        )
        first = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["slug"], "amplify")

    def test_ready_to_finalize_is_claimed_so_it_can_be_saved(self) -> None:
        _seed(self.conn, "rentana")
        _set_paused(self.conn, "rentana")
        self.conn.execute(
            "UPDATE pipeline_queue SET paused_reason = ?, last_workflow_status = ? "
            "WHERE slug = ?",
            (pq.PAUSED_REASON_READY_TO_FINALIZE, pq.MIRROR_READY_TO_FINALIZE, "rentana"),
        )
        self.conn.commit()
        folder = self.data / "pending_review" / "rentana"
        folder.mkdir(parents=True)
        (folder / "workflow_state.json").write_text(
            json.dumps(
                {
                    "status": "IN_PROGRESS",
                    "active_stage": "stage3",
                    "stages": {
                        "stage2": {"status": "COMPLETE"},
                        "stage3": {"status": "READY"},
                    },
                }
            ),
            encoding="utf-8",
        )
        first = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual([row["slug"] for row in first], ["rentana"])
        row = pq.get_row(self.conn, "rentana")
        assert row is not None
        self.assertEqual(row["status"], "leased")
        self.assertIsNone(row["paused_reason"])

    def test_mark_done_from_ready_to_finalize(self) -> None:
        _seed(self.conn, "rentana")
        leased = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)[0]
        pq.transition(
            "rentana",
            "in_progress",
            worker="w1",
            token=int(leased["fencing_token"]),
            conn=self.conn,
        )
        paused = pq.transition(
            "rentana",
            "paused",
            worker="w1",
            token=int(pq.get_row(self.conn, "rentana")["fencing_token"]),
            conn=self.conn,
            last_workflow_status=pq.MIRROR_READY_TO_FINALIZE,
            last_stage="stage3",
            paused_reason=pq.PAUSED_REASON_READY_TO_FINALIZE,
        )
        self.assertEqual(paused["status"], "paused")
        self.assertIsNone(paused["locked_by"])
        done = pq.mark_done(
            "rentana",
            conn=self.conn,
            last_workflow_status="COMPLETE",
        )
        assert done is not None
        self.assertEqual(done["status"], "done")
        self.assertIsNone(done["paused_reason"])
        self.assertIsNone(done["locked_by"])
        self.assertEqual(done["last_workflow_status"], "COMPLETE")

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


class TestManualRequeue(QueueHarness):
    def _paused_failed(self, slug: str) -> None:
        _seed(self.conn, slug)
        _set_paused(self.conn, slug)
        self.conn.execute(
            "UPDATE pipeline_queue SET last_workflow_status = 'FAILED', "
            "last_stage = 'stage1' WHERE slug = ?",
            (slug,),
        )
        self.conn.commit()

    def _paused_subscription_review(self, slug: str) -> None:
        _seed(self.conn, slug)
        _set_paused(self.conn, slug)
        self.conn.execute(
            "UPDATE pipeline_queue SET last_workflow_status = 'WAITING_FOR_INPUT', "
            "last_stage = 'stage0' WHERE slug = ?",
            (slug,),
        )
        self.conn.commit()
        folder = self.data / "pending_review" / slug
        receipts = folder / "stage_receipts"
        receipts.mkdir(parents=True)
        (receipts / "stage0.json").write_text(
            json.dumps({"result": {"pause_kind": "subscription_review"}}),
            encoding="utf-8",
        )

    def _write_stage0_pause(self, slug: str, payload: dict) -> None:
        folder = self.data / "pending_review" / slug
        receipts = folder / "stage_receipts"
        receipts.mkdir(parents=True, exist_ok=True)
        (receipts / "stage0.json").write_text(json.dumps(payload), encoding="utf-8")

    def _paused_waiting(self, slug: str) -> None:
        _seed(self.conn, slug)
        _set_paused(self.conn, slug)
        self.conn.execute(
            "UPDATE pipeline_queue SET last_workflow_status = 'WAITING_FOR_INPUT', "
            "last_stage = 'stage0' WHERE slug = ?",
            (slug,),
        )
        self.conn.commit()

    def test_requeue_allows_paused_failed(self) -> None:
        self._paused_failed("healthstream")
        row = pq.requeue_paused(
            "healthstream",
            reason="retry Stage 1 after repair",
            worker="cursor",
            conn=self.conn,
            data_root=self.data,
        )
        self.assertEqual(row["status"], "queued")
        self.assertEqual(row["requeued_by"], "cursor")
        self.assertEqual(row["requeue_reason"], "retry Stage 1 after repair")
        self.assertIsNotNone(row["requeued_at"])
        self.assertIsNone(row["locked_by"])
        self.assertEqual(row["last_workflow_status"], "FAILED")

    def test_requeue_conversion_risk_requires_apply_anyway(self) -> None:
        self._paused_waiting("velosio")
        self._write_stage0_pause(
            "velosio",
            {"status": "COMPLETE", "result": {"pause_kind": "conversion_risk"}},
        )
        (self.data / "pending_review" / "velosio" / "workflow_state.json").write_text(
            json.dumps({"status": "WAITING_FOR_INPUT", "active_stage": "stage0"}),
            encoding="utf-8",
        )
        with self.assertRaises(pq.RequeueRefused) as err:
            pq.requeue_paused(
                "velosio",
                reason="please continue",
                conn=self.conn,
                data_root=self.data,
            )
        self.assertIn("apply_anyway", str(err.exception))
        self.assertEqual(pq.get_row(self.conn, "velosio")["status"], "paused")

    def test_requeue_chrome_only_conversion_risk_failed_does_not_need_apply_anyway(self) -> None:
        self._paused_failed("amplify")
        self._write_stage0_pause(
            "amplify",
            {"status": "COMPLETE", "result": {"pause_kind": "conversion_risk"}},
        )
        folder = self.data / "pending_review" / "amplify"
        (folder / "stage0_fit_gate.json").write_text(
            json.dumps(
                {
                    "company": "Amplify",
                    "conversion_feasibility": {
                        "verdict": "risk",
                        "reasons": ["not_present_required_tool:EdTech"],
                    },
                }
            ),
            encoding="utf-8",
        )
        row = pq.requeue_paused(
            "amplify",
            reason="stage 1 verify failed after chrome hold",
            conn=self.conn,
            data_root=self.data,
        )
        self.assertEqual(row["status"], "queued")
        self.assertFalse((folder / "conversion_risk_apply_anyway.json").exists())

    def test_requeue_conversion_risk_apply_anyway_writes_marker(self) -> None:
        self._paused_waiting("omnissa")
        self._write_stage0_pause(
            "omnissa",
            {"status": "COMPLETE", "result": {"pause_kind": "conversion_risk"}},
        )
        folder = self.data / "pending_review" / "omnissa"
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "WAITING_FOR_INPUT", "active_stage": "stage0"}),
            encoding="utf-8",
        )
        row = pq.requeue_paused(
            "omnissa",
            reason="apply_anyway",
            worker="cursor",
            conn=self.conn,
            data_root=self.data,
        )
        self.assertEqual(row["status"], "queued")
        marker = folder / pq.CONVERSION_RISK_OVERRIDE_NAME
        self.assertTrue(marker.is_file())

    def test_requeue_allows_subscription_review_pause(self) -> None:
        self._paused_subscription_review("casper_studios")
        row = pq.requeue_paused(
            "casper_studios",
            reason="retry omitted evidence ids",
            worker="cursor",
            conn=self.conn,
            data_root=self.data,
        )
        self.assertEqual(row["status"], "queued")
        self.assertEqual(row["requeued_by"], "cursor")
        self.assertEqual(row["requeue_reason"], "retry omitted evidence ids")

    def test_requeue_allows_no_provider_extraction_review(self) -> None:
        """Live miss 2026-09-21: outschool/omnissa/optum/origami_risk paused
        requirement_extraction_review because Groq was off (no_provider). Agy
        is on now. Filling the template is the wrong recovery. Requeue must
        be allowed so Stage 0 can call the adapter."""
        self._paused_waiting("outschool")
        self._write_stage0_pause(
            "outschool",
            {
                "result": {
                    "pause_kind": "requirement_extraction_review",
                    "queue": [
                        {"text": "Title: Product Manager", "extraction_reason": "no_provider"},
                        {"text": "About the company", "extraction_reason": "no_provider"},
                    ],
                }
            },
        )
        row = pq.requeue_paused(
            "outschool",
            reason="retry Stage 0 now that Agy adapter is on",
            worker="cursor",
            conn=self.conn,
            data_root=self.data,
        )
        self.assertEqual(row["status"], "queued")

    def test_requeue_allows_review_center_when_no_open_questions(self) -> None:
        """velosio/certara: cards completed, then a later Groq pause left
        paused_at newer than resolved_at so they never auto-promote."""
        self._paused_waiting("velosio")
        self._write_stage0_pause(
            "velosio",
            {"result": {"pause_kind": "review_center"}},
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS pending_skill_confirmations ("
            "opportunity_key TEXT, status TEXT, question_type TEXT, "
            "resolved_at TEXT, updated_at TEXT)"
        )
        self.conn.commit()
        row = pq.requeue_paused(
            "velosio",
            reason="retry Stage 0; Review Center cards already answered",
            worker="cursor",
            conn=self.conn,
            data_root=self.data,
        )
        self.assertEqual(row["status"], "queued")

    def test_requeue_refuses_real_extraction_review_and_open_review_center(self) -> None:
        self._paused_waiting("human_review")
        self._write_stage0_pause(
            "human_review",
            {
                "result": {
                    "pause_kind": "requirement_extraction_review",
                    "queue": [
                        {"text": "5+ years PM", "extraction_reason": "low_confidence"},
                    ],
                }
            },
        )
        with self.assertRaises(pq.RequeueRefused) as real_review:
            pq.requeue_paused(
                "human_review",
                reason="no",
                conn=self.conn,
                data_root=self.data,
            )
        self.assertIn("not an eligible pause", str(real_review.exception))

        self._paused_waiting("open_cards")
        self._write_stage0_pause(
            "open_cards",
            {"result": {"pause_kind": "review_center"}},
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS pending_skill_confirmations ("
            "opportunity_key TEXT, status TEXT, question_type TEXT, "
            "resolved_at TEXT, updated_at TEXT)"
        )
        self.conn.execute(
            "INSERT INTO pending_skill_confirmations "
            "(opportunity_key, status, question_type, resolved_at, updated_at) "
            "VALUES ('open_cards', 'open', 'hard_gate_review', NULL, NULL)"
        )
        self.conn.commit()
        released = pq.requeue_paused(
            "open_cards",
            reason="no",
            conn=self.conn,
            data_root=self.data,
        )
        self.assertEqual(released["status"], "queued")

    def test_requeue_refuses_leased_in_progress_done_and_ready_to_finalize(self) -> None:
        _seed(self.conn, "leased_job")
        pq.transition("leased_job", "leased", worker="w1", token=0, conn=self.conn)
        with self.assertRaises(pq.RequeueRefused) as leased:
            pq.requeue_paused(
                "leased_job",
                reason="no",
                conn=self.conn,
                data_root=self.data,
            )
        self.assertIn("status=leased", str(leased.exception))

        _seed(self.conn, "running_job")
        pq.transition("running_job", "leased", worker="w1", token=0, conn=self.conn)
        running = pq.transition(
            "running_job", "in_progress", worker="w1", token=1, conn=self.conn
        )
        with self.assertRaises(pq.RequeueRefused) as running_err:
            pq.requeue_paused(
                "running_job",
                reason="no",
                conn=self.conn,
                data_root=self.data,
            )
        self.assertIn("status=in_progress", str(running_err.exception))
        self.assertEqual(pq.get_row(self.conn, "running_job")["status"], "in_progress")
        self.assertEqual(
            int(running["fencing_token"]),
            int(pq.get_row(self.conn, "running_job")["fencing_token"]),
        )

        _seed(self.conn, "done_job")
        pq.transition("done_job", "leased", worker="w1", token=0, conn=self.conn)
        pq.transition("done_job", "in_progress", worker="w1", token=1, conn=self.conn)
        pq.transition("done_job", "done", worker="w1", token=1, conn=self.conn)
        with self.assertRaises(pq.RequeueRefused) as done:
            pq.requeue_paused(
                "done_job",
                reason="no",
                conn=self.conn,
                data_root=self.data,
            )
        self.assertIn("status=done", str(done.exception))

        _seed(self.conn, "finalize_job")
        _set_paused(self.conn, "finalize_job")
        self.conn.execute(
            "UPDATE pipeline_queue SET paused_reason = ?, last_workflow_status = ? "
            "WHERE slug = ?",
            (pq.PAUSED_REASON_READY_TO_FINALIZE, pq.MIRROR_READY_TO_FINALIZE, "finalize_job"),
        )
        self.conn.commit()
        with self.assertRaises(pq.RequeueRefused) as ready:
            pq.requeue_paused(
                "finalize_job",
                reason="no",
                conn=self.conn,
                data_root=self.data,
            )
        self.assertIn("ready_to_finalize", str(ready.exception))
        self.assertEqual(pq.get_row(self.conn, "finalize_job")["status"], "paused")

    def test_cli_requeue_allowed_and_refused(self) -> None:
        from queue_claim import main

        self._paused_failed("binance")
        self.conn.close()
        buf = __import__("io").StringIO()
        err = __import__("io").StringIO()
        with mock.patch("sys.stdout", buf), mock.patch("sys.stderr", err):
            rc = main(
                [
                    "--db",
                    str(self.db),
                    "requeue",
                    "--slug",
                    "binance",
                    "--reason",
                    "retry after repair",
                    "--worker",
                    "cursor",
                    "--data-root",
                    str(self.data),
                ]
            )
        self.assertEqual(rc, 0)
        self.assertIn("requeued=1", buf.getvalue())
        self.assertIn("by=cursor", buf.getvalue())

        conn = pq.connect(self.db)
        pq.transition("binance", "leased", worker="w1", token=0, conn=conn)
        conn.close()
        err2 = __import__("io").StringIO()
        with mock.patch("sys.stderr", err2):
            rc = main(
                [
                    "--db",
                    str(self.db),
                    "requeue",
                    "--slug",
                    "binance",
                    "--reason",
                    "no",
                    "--data-root",
                    str(self.data),
                ]
            )
        self.assertEqual(rc, 2)
        self.assertIn("status=leased", err2.getvalue())


_JOBS_DDL = """
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  company TEXT,
  title TEXT,
  url TEXT,
  status TEXT
);
"""


class TestCr123ClaimAlreadyHandled(QueueHarness):
    """CR-123 Story 2.2: claim refuses already-handled rows (FR-363, AC-472)."""

    def setUp(self) -> None:
        super().setUp()
        self.conn.executescript(_JOBS_DDL)
        self.conn.commit()
        (self.data / "archive" / "submissions").mkdir(parents=True, exist_ok=True)

    def _seed_applied(
        self,
        slug: str,
        *,
        job_status: str = "Applied",
        title: str = "Platform Product Manager",
    ) -> dict:
        """Insert one synthetic Applied+ job plus a matching queue row."""
        from stage0_skip_ledger import normalize_url, posting_key

        company = f"Synth Claim {slug} Co"
        url = f"https://example.test/jobs/{slug}"
        row = pq.upsert_queued(
            self.conn,
            slug=slug,
            company=company,
            title=title,
            url=url,
            url_key=normalize_url(url),
            posting_key=posting_key(company, title),
            networking_contacts_raw=None,
            source_sha256=None,
            source_line=None,
            folder_root="pending_review",
        )
        self.conn.execute(
            "INSERT INTO jobs (id, company, title, url, status) VALUES (?, ?, ?, ?, ?)",
            (slug, company, title, url, job_status),
        )
        self.conn.commit()
        return row

    def test_paused_applied_plus_becomes_done_and_is_not_claimed(self) -> None:
        self._seed_applied("synth_claim_paused")
        _set_paused(self.conn, "synth_claim_paused")
        folder = self.data / "pending_review" / "synth_claim_paused"
        _stage1_ready(folder)
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "WAITING_FOR_LLM", "active_stage": "stage1"}),
            encoding="utf-8",
        )
        _seed(self.conn, "synth_claim_remaining_paused")
        rows = pq.claim_pack("w1", size=2, conn=self.conn, data_root=self.data)
        slugs = [row["slug"] for row in rows]
        self.assertNotIn("synth_claim_paused", slugs)
        self.assertEqual(pq.get_row(self.conn, "synth_claim_paused")["status"], "done")
        self.assertIn("synth_claim_remaining_paused", slugs)

    def test_queued_applied_plus_becomes_done_and_is_not_claimed(self) -> None:
        self._seed_applied("synth_claim_queued")
        _seed(self.conn, "synth_claim_remaining_queued")
        rows = pq.claim_pack("w1", size=2, conn=self.conn, data_root=self.data)
        slugs = [row["slug"] for row in rows]
        self.assertNotIn("synth_claim_queued", slugs)
        self.assertEqual(pq.get_row(self.conn, "synth_claim_queued")["status"], "done")
        self.assertEqual(slugs, ["synth_claim_remaining_queued"])

    def test_expired_leased_applied_plus_becomes_done_not_re_leased(self) -> None:
        self._seed_applied("synth_claim_expired")
        leased = pq.transition(
            "synth_claim_expired", "leased", worker="w1", token=0, conn=self.conn
        )
        self.assertEqual(leased["status"], "leased")
        self.assertEqual(leased["locked_by"], "w1")
        expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(
            microsecond=0
        ).isoformat()
        self.conn.execute(
            "UPDATE pipeline_queue SET lease_expires_at = ? WHERE slug = ?",
            (expired, "synth_claim_expired"),
        )
        self.conn.commit()
        rows = pq.claim_pack("w2", size=1, conn=self.conn, data_root=self.data)
        slugs = [row["slug"] for row in rows]
        self.assertNotIn("synth_claim_expired", slugs)
        after = pq.get_row(self.conn, "synth_claim_expired")
        assert after is not None
        self.assertEqual(after["status"], "done")
        self.assertIsNone(after["locked_by"])
        self.assertNotEqual(after.get("locked_by"), "w2")

    def test_live_leased_applied_plus_is_not_returned_and_stays_leased(self) -> None:
        self._seed_applied("synth_claim_live")
        leased = pq.transition(
            "synth_claim_live", "leased", worker="w1", token=0, conn=self.conn
        )
        self.assertEqual(leased["status"], "leased")
        self.assertEqual(leased["locked_by"], "w1")
        snapshot = dict(pq.get_row(self.conn, "synth_claim_live") or {})
        rows = pq.claim_pack("w2", size=1, conn=self.conn, data_root=self.data)
        slugs = [row["slug"] for row in rows]
        self.assertNotIn("synth_claim_live", slugs)
        after = dict(pq.get_row(self.conn, "synth_claim_live") or {})
        self.assertEqual(after["status"], "leased")
        self.assertEqual(after["locked_by"], "w1")
        self.assertEqual(after, snapshot)


class TestCr123ReconcileAlreadyHandled(QueueHarness):
    """CR-123 Story 5.1: reconcile_already_handled (FR-366, AC-475)."""

    def setUp(self) -> None:
        super().setUp()
        self.conn.executescript(_JOBS_DDL)
        self.conn.commit()
        (self.data / "archive" / "submissions").mkdir(parents=True, exist_ok=True)

    def _seed_queue(
        self,
        slug: str,
        *,
        company: str,
        title: str = "Platform Product Manager",
        url: str | None = None,
        folder_root: str = "pending_review",
    ) -> dict:
        """Insert one synthetic queue row. Returns the stored row."""
        from stage0_skip_ledger import normalize_url, posting_key

        return pq.upsert_queued(
            self.conn,
            slug=slug,
            company=company,
            title=title,
            url=url,
            url_key=normalize_url(url) if url else None,
            posting_key=posting_key(company, title),
            networking_contacts_raw=None,
            source_sha256=None,
            source_line=None,
            folder_root=folder_root,
        )

    def _plant_archive(self, root: Path, slug: str) -> Path:
        """Create a synthetic archive folder. Does not copy live archive trees."""
        folder = root / slug
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "Original_JD.txt").write_text("synthetic archive marker\n", encoding="utf-8")
        return folder

    def test_reconcile_closes_paused_applied_plus(self) -> None:
        """AC-475 (a): paused + jobs Applied+ becomes done and is not claimable."""
        slug = "synth_recon_applied"
        company = "Synth Recon Applied Co"
        title = "Platform Product Manager"
        url = "https://example.test/jobs/recon-applied"
        self._seed_queue(slug, company=company, title=title, url=url)
        _set_paused(self.conn, slug)
        self.conn.execute(
            "INSERT INTO jobs (id, company, title, url, status) VALUES (?, ?, ?, ?, ?)",
            (slug, company, title, url, "Applied"),
        )
        self.conn.commit()
        _seed(self.conn, "synth_recon_remaining_a")

        closed = pq.reconcile_already_handled(self.conn, data_root=self.data)
        self.assertGreaterEqual(closed, 1)
        self.assertEqual(pq.get_row(self.conn, slug)["status"], "done")

        rows = pq.claim_pack("w1", size=2, conn=self.conn, data_root=self.data)
        slugs = [row["slug"] for row in rows]
        self.assertNotIn(slug, slugs)
        self.assertIn("synth_recon_remaining_a", slugs)

    def test_reconcile_closes_paused_archive_skipped(self) -> None:
        """AC-475 (b): paused + archive/skipped folder becomes done, not claimable."""
        slug = "synth_recon_skipped"
        company = "Synth Recon Skipped Co"
        folder = self._plant_archive(self.data / "archive" / "skipped", slug)
        self._seed_queue(
            slug,
            company=company,
            url="https://example.test/jobs/recon-skipped",
            folder_root="archive/skipped",
        )
        _set_paused(self.conn, slug)
        _seed(self.conn, "synth_recon_remaining_b")

        closed = pq.reconcile_already_handled(self.conn, data_root=self.data)
        self.assertGreaterEqual(closed, 1)
        self.assertEqual(pq.get_row(self.conn, slug)["status"], "done")
        self.assertTrue(folder.is_dir())

        rows = pq.claim_pack("w1", size=2, conn=self.conn, data_root=self.data)
        slugs = [row["slug"] for row in rows]
        self.assertNotIn(slug, slugs)
        self.assertIn("synth_recon_remaining_b", slugs)

    def test_reconcile_closes_paused_archive_submissions(self) -> None:
        """AC-475 (c): paused + archive/submissions folder becomes done, not claimable."""
        slug = "synth_recon_archived"
        company = "Synth Recon Archive Co"
        folder = self._plant_archive(self.data / "archive" / "submissions", slug)
        self._seed_queue(
            slug,
            company=company,
            url="https://example.test/jobs/recon-archived",
            folder_root="pending_review",
        )
        _set_paused(self.conn, slug)
        _seed(self.conn, "synth_recon_remaining_c")

        closed = pq.reconcile_already_handled(self.conn, data_root=self.data)
        self.assertGreaterEqual(closed, 1)
        self.assertEqual(pq.get_row(self.conn, slug)["status"], "done")
        self.assertTrue(folder.is_dir())

        rows = pq.claim_pack("w1", size=2, conn=self.conn, data_root=self.data)
        slugs = [row["slug"] for row in rows]
        self.assertNotIn(slug, slugs)
        self.assertIn("synth_recon_remaining_c", slugs)

    def test_reconcile_closes_expired_lease_and_leaves_live_lease(self) -> None:
        """Queued/paused close immediately; expired leased closes; live lease stays."""
        applied_url = "https://example.test/jobs/recon-lease"
        company = "Synth Recon Lease Co"
        title = "Platform Product Manager"
        self._seed_queue(
            "synth_recon_expired",
            company=company,
            title=title,
            url=applied_url,
        )
        self._seed_queue(
            "synth_recon_live",
            company="Synth Recon Live Co",
            title=title,
            url="https://example.test/jobs/recon-live",
        )
        self.conn.execute(
            "INSERT INTO jobs (id, company, title, url, status) VALUES (?, ?, ?, ?, ?)",
            ("synth_recon_expired", company, title, applied_url, "Applied"),
        )
        self.conn.execute(
            "INSERT INTO jobs (id, company, title, url, status) VALUES (?, ?, ?, ?, ?)",
            (
                "synth_recon_live",
                "Synth Recon Live Co",
                title,
                "https://example.test/jobs/recon-live",
                "Applied",
            ),
        )
        self.conn.commit()
        expired_row = pq.transition(
            "synth_recon_expired", "leased", worker="w1", token=0, conn=self.conn
        )
        live_row = pq.transition(
            "synth_recon_live", "leased", worker="w1", token=0, conn=self.conn
        )
        expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).replace(
            microsecond=0
        ).isoformat()
        self.conn.execute(
            "UPDATE pipeline_queue SET lease_expires_at = ? WHERE slug = ?",
            (expired, "synth_recon_expired"),
        )
        self.conn.commit()
        live_snapshot = dict(pq.get_row(self.conn, "synth_recon_live") or {})

        pq.reconcile_already_handled(self.conn, data_root=self.data)
        self.assertEqual(expired_row["status"], "leased")
        self.assertEqual(pq.get_row(self.conn, "synth_recon_expired")["status"], "done")
        after_live = dict(pq.get_row(self.conn, "synth_recon_live") or {})
        self.assertEqual(after_live["status"], "leased")
        self.assertEqual(after_live["locked_by"], "w1")
        self.assertEqual(after_live, live_snapshot)
        self.assertEqual(live_row["locked_by"], "w1")

        rows = pq.claim_pack("w2", size=2, conn=self.conn, data_root=self.data)
        slugs = [row["slug"] for row in rows]
        self.assertNotIn("synth_recon_expired", slugs)
        self.assertNotIn("synth_recon_live", slugs)


if __name__ == "__main__":
    unittest.main()
