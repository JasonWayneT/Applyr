#!/usr/bin/env python3
"""CR-119 inbox ingest: quarantine, dedup, ledger, CLI.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_ingest_csv_queue -v
"""
from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from csv_ingest import (  # noqa: E402
    EMPTY_COMPANY,
    JD_TOO_SHORT,
    NO_DEDUP_KEY,
    validate_row,
)
from ingest_csv_queue import ingest_inbox, main as ingest_main  # noqa: E402
import pipeline_queue as pq  # noqa: E402
from stage0_skip_ledger import normalize_url, posting_key, record_skip  # noqa: E402

CONTACTS_SQL = """
CREATE TABLE IF NOT EXISTS contacts (
  id TEXT PRIMARY KEY,
  job_id TEXT,
  company TEXT NOT NULL,
  contact_name TEXT NOT NULL,
  contact_title TEXT,
  contact_type TEXT NOT NULL,
  source TEXT,
  message_sent_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  next_follow_up_due TEXT,
  last_touch_at TEXT NOT NULL DEFAULT (datetime('now')),
  follow_up_count INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  confirmed BOOLEAN NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

JD_MARKER = "SYNTHETIC_JD_BODY_DO_NOT_LOG"
CONTACT_MARKER = "SYNTHETIC_CONTACT_DO_NOT_LOG"


def _jd(extra: str = "") -> str:
    body = (
        "This is a synthetic job description used only in CR-119 ingest tests. "
        "It describes platform product work across operations, compliance, and "
        "customer-facing workflows without copying any real posting. "
    )
    text = (body * 8) + extra
    return text[:240]


class IngestHarness(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = Path(self._tmpdir.name)
        self.inbox = self.root / "inbox"
        self.pending = self.root / "pending_review"
        self.submissions = self.root / "submissions"
        self.archive_submissions = self.root / "archive" / "submissions"
        self.archive_skipped = self.root / "archive" / "skipped"
        self.inbox.mkdir()
        self.pending.mkdir()
        self.submissions.mkdir()
        self.archive_submissions.mkdir(parents=True)
        self.archive_skipped.mkdir(parents=True)
        (self.inbox / "archive").mkdir()
        (self.inbox / "quarantine").mkdir()
        self.db = self.root / "jobagent.sqlite"
        self._pending_patch = mock.patch("csv_ingest.PENDING_REVIEW", self.pending)
        self._sub_patch = mock.patch("csv_ingest.SUBMISSIONS", self.submissions)
        self._arch_sub_patch = mock.patch(
            "csv_ingest.ARCHIVE_SUBMISSIONS", self.archive_submissions
        )
        self._arch_skip_patch = mock.patch(
            "csv_ingest.ARCHIVE_SKIPPED", self.archive_skipped
        )
        self._pending_patch.start()
        self._sub_patch.start()
        self._arch_sub_patch.start()
        self._arch_skip_patch.start()
        self.addCleanup(self._pending_patch.stop)
        self.addCleanup(self._sub_patch.stop)
        self.addCleanup(self._arch_sub_patch.stop)
        self.addCleanup(self._arch_skip_patch.stop)

    def _write_csv(self, name: str, rows: list[dict[str, str]]) -> Path:
        path = self.inbox / name
        fieldnames: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    fieldnames.append(key)
                    seen.add(key)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _ingest(self) -> dict[str, int]:
        return ingest_inbox(
            self.inbox,
            self.db,
            pending_root=self.pending,
            submissions_root=self.submissions,
            sleep_s=0,
        )

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        return conn


class TestValidateRow(IngestHarness):
    def test_validate_row_order(self) -> None:
        ok, code = validate_row({"Company": "", "Job Description": _jd(), "URL": "https://x.test"})
        self.assertFalse(ok)
        self.assertEqual(code, EMPTY_COMPANY)
        ok, code = validate_row(
            {"Company": "Acme", "Job Description": "short", "Position": "PM"}
        )
        self.assertFalse(ok)
        self.assertEqual(code, JD_TOO_SHORT)
        ok, code = validate_row(
            {"Company": "Acme", "Job Description": _jd(), "URL": "", "Position": ""}
        )
        self.assertFalse(ok)
        self.assertEqual(code, NO_DEDUP_KEY)
        ok, code = validate_row(
            {"Company": "Acme", "Job Description": _jd(), "Position": "PM"}
        )
        self.assertTrue(ok)
        self.assertIsNone(code)


class TestRowQuarantine(IngestHarness):
    def test_bad_rows_quarantined_good_row_lands(self) -> None:
        self._write_csv(
            "mixed.csv",
            [
                {
                    "Company": "",
                    "Position": "PM",
                    "URL": "https://example.test/empty-co",
                    "Job Description": _jd(),
                },
                {
                    "Company": "ShortCo",
                    "Position": "PM",
                    "URL": "https://example.test/short",
                    "Job Description": "x" * 150,
                },
                {
                    "Company": "NoKeyCo",
                    "Position": "",
                    "URL": "",
                    "Job Description": _jd(),
                },
                {
                    "Company": "GoodCo",
                    "Position": "Product Manager",
                    "URL": "https://example.test/good",
                    "Job Description": _jd(),
                    "Networking Contacts": CONTACT_MARKER,
                },
            ],
        )
        counts = self._ingest()
        self.assertEqual(counts["quarantined_rows"], 3)
        self.assertEqual(counts["queued"], 1)
        conn = self._conn()
        try:
            codes = [
                r["error_code"]
                for r in conn.execute(
                    "SELECT error_code FROM csv_quarantine ORDER BY line_number"
                )
            ]
            self.assertEqual(codes, [EMPTY_COMPANY, JD_TOO_SHORT, NO_DEDUP_KEY])
            queued = list(conn.execute("SELECT slug, company FROM pipeline_queue"))
            self.assertEqual(len(queued), 1)
            self.assertEqual(queued[0]["company"], "GoodCo")
        finally:
            conn.close()
        self.assertTrue((self.pending / "goodco" / "Original_JD.txt").exists())
        self.assertFalse((self.pending / "shortco").exists())
        self.assertFalse((self.pending / "nokeyco").exists())

    def test_title_appended_to_company_uses_company_slug(self) -> None:
        self._write_csv(
            "eso.csv",
            [
                {
                    "Company": "ESO Product Manager",
                    "Position": "Product Manager",
                    "URL": "https://example.test/eso",
                    "Job Description": _jd(),
                }
            ],
        )
        counts = self._ingest()
        self.assertEqual(counts["queued"], 1)
        conn = self._conn()
        try:
            row = conn.execute("SELECT slug, company, title FROM pipeline_queue").fetchone()
        finally:
            conn.close()
        self.assertEqual(row["slug"], "eso")
        self.assertEqual(row["company"], "ESO")
        self.assertEqual(row["title"], "Product Manager")
        self.assertTrue((self.pending / "eso" / "Original_JD.txt").exists())
        self.assertFalse((self.pending / "eso_product_manager").exists())


class TestDedupResolver(IngestHarness):
    def test_url_less_same_company_title_one_row(self) -> None:
        row = {
            "Company": "TwinCo",
            "Position": "Operations PM",
            "URL": "",
            "Job Description": _jd(" file-a"),
        }
        self._write_csv("a.csv", [{**row, "Note": "first"}])
        self._ingest()
        self._write_csv(
            "b.csv",
            [{**row, "Job Description": _jd(" file-b"), "Note": "second"}],
        )
        counts = self._ingest()
        self.assertEqual(counts["queued"], 0)
        self.assertEqual(counts["reused"], 1)
        conn = self._conn()
        try:
            n = conn.execute("SELECT COUNT(*) AS n FROM pipeline_queue").fetchone()["n"]
        finally:
            conn.close()
        self.assertEqual(n, 1)
        folders = [p for p in self.pending.iterdir() if p.is_dir()]
        self.assertEqual(len(folders), 1)

    def test_skip_ledger_url_writes_nothing(self) -> None:
        record_skip(
            url="https://example.test/skipped",
            company="SkipCo",
            title="Product Manager",
            skip_reason="prior skip",
            db_path=self.db,
        )
        self._write_csv(
            "skip.csv",
            [
                {
                    "Company": "SkipCo",
                    "Position": "Product Manager",
                    "URL": "https://example.test/skipped?utm_source=li",
                    "Job Description": _jd(),
                }
            ],
        )
        counts = self._ingest()
        self.assertEqual(counts["skipped_ledger"], 1)
        self.assertEqual(counts["queued"], 0)
        self.assertEqual(list(self.pending.iterdir()), [])
        conn = self._conn()
        try:
            n = conn.execute("SELECT COUNT(*) AS n FROM pipeline_queue").fetchone()["n"]
        finally:
            conn.close()
        self.assertEqual(n, 0)

    def test_existing_pending_review_url_reused_without_rewrite(self) -> None:
        from csv_ingest import write_jd

        original = write_jd(
            "existco",
            "https://example.test/exist",
            "Product Manager",
            _jd(" original"),
            dest_root=self.pending,
        )
        before = original.read_bytes()
        mtime = original.stat().st_mtime
        self._write_csv(
            "exist.csv",
            [
                {
                    "Company": "ExistCo",
                    "Position": "Product Manager",
                    "URL": "https://example.test/exist",
                    "Job Description": _jd(" replacement-must-not-land"),
                }
            ],
        )
        counts = self._ingest()
        self.assertEqual(counts["reused"], 1)
        self.assertEqual(original.read_bytes(), before)
        self.assertEqual(original.stat().st_mtime, mtime)


class TestFileLedger(IngestHarness):
    def test_same_content_two_names_second_is_noop(self) -> None:
        rows = [
            {
                "Company": "HashCo",
                "Position": "PM",
                "URL": "https://example.test/hash",
                "Job Description": _jd(),
            }
        ]
        first = self._write_csv("applyr_jobs.csv", rows)
        payload = first.read_bytes()
        self._ingest()
        second = self.inbox / "applyr_jobs (1).csv"
        second.write_bytes(payload)
        counts = self._ingest()
        self.assertEqual(counts["files_duplicate_hash"], 1)
        self.assertEqual(counts["queued"], 0)
        conn = self._conn()
        try:
            n = conn.execute("SELECT COUNT(*) AS n FROM pipeline_queue").fetchone()["n"]
            ledgers = conn.execute("SELECT COUNT(*) AS n FROM csv_ingest_ledger").fetchone()["n"]
        finally:
            conn.close()
        self.assertEqual(n, 1)
        self.assertEqual(ledgers, 1)

    def test_broken_file_does_not_block_valid_file(self) -> None:
        (self.inbox / "broken.csv").write_bytes(b"\xff\xfe\x00not-utf8")
        self._write_csv(
            "valid.csv",
            [
                {
                    "Company": "ValidCo",
                    "Position": "PM",
                    "URL": "https://example.test/valid",
                    "Job Description": _jd(),
                }
            ],
        )
        counts = self._ingest()
        self.assertEqual(counts["files_quarantined"], 1)
        self.assertEqual(counts["queued"], 1)
        self.assertTrue((self.inbox / "quarantine" / "broken.csv").exists())
        self.assertTrue((self.pending / "validco" / "Original_JD.txt").exists())


class TestIngestCli(IngestHarness):
    def test_no_contacts_row_and_idempotent_rerun(self) -> None:
        self._write_csv(
            "once.csv",
            [
                {
                    "Company": "OnceCo",
                    "Position": "PM",
                    "URL": "https://example.test/once",
                    "Job Description": _jd(JD_MARKER),
                    "Networking Contacts": CONTACT_MARKER,
                }
            ],
        )
        conn = sqlite3.connect(str(self.db))
        conn.executescript(CONTACTS_SQL)
        conn.commit()
        conn.close()
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            ingest_main(["--inbox", str(self.inbox), "--db", str(self.db)])
        printed = buf.getvalue()
        self.assertNotIn(JD_MARKER, printed)
        self.assertNotIn(CONTACT_MARKER, printed)
        self.assertNotIn("raw_payload", printed)
        buf_json = io.StringIO()
        with mock.patch("sys.stdout", buf_json):
            ingest_main(["--inbox", str(self.inbox), "--db", str(self.db), "--json"])
        json_line = buf_json.getvalue().strip()
        self.assertTrue(json_line.startswith("{"))
        parsed = json.loads(json_line)
        self.assertEqual(set(parsed), {"queued", "duplicate", "quarantined"})
        self.assertNotIn(JD_MARKER, json_line)
        self.assertNotIn(CONTACT_MARKER, json_line)
        conn = self._conn()
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0], 0)
            contacts_raw = conn.execute(
                "SELECT networking_contacts_raw FROM pipeline_queue"
            ).fetchone()[0]
            self.assertEqual(contacts_raw, CONTACT_MARKER)
            first_folders = [p.name for p in self.pending.iterdir() if p.is_dir()]
            first_rows = conn.execute("SELECT COUNT(*) FROM pipeline_queue").fetchone()[0]
        finally:
            conn.close()
        payload = (self.inbox / "archive" / "once.csv").read_bytes()
        replay = self.inbox / "once.csv"
        replay.write_bytes(payload)
        second = self._ingest()
        self.assertEqual(second["queued"], 0)
        self.assertEqual(second["files_duplicate_hash"], 1)
        conn = self._conn()
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM pipeline_queue").fetchone()[0],
                first_rows,
            )
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0], 0)
        finally:
            conn.close()
        self.assertEqual(
            [p.name for p in self.pending.iterdir() if p.is_dir()],
            first_folders,
        )


_JOBS_DDL = """
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  company TEXT,
  title TEXT,
  url TEXT,
  status TEXT
);
"""


class TestCr123IngestReconcile(IngestHarness):
    """CR-123 Story 5.1: ingest / CLI hook for reconcile (FR-366, AC-475)."""

    def setUp(self) -> None:
        super().setUp()
        conn = pq.connect(self.db)
        conn.executescript(_JOBS_DDL)
        conn.commit()
        conn.close()

    def _ingest(self) -> dict[str, int]:
        return ingest_inbox(
            self.inbox,
            self.db,
            pending_root=self.pending,
            submissions_root=self.submissions,
            archive_submissions_root=self.archive_submissions,
            archive_skipped_root=self.archive_skipped,
            data_root=self.root,
            sleep_s=0,
        )

    def _seed_paused(
        self,
        slug: str,
        *,
        company: str,
        title: str,
        url: str,
        folder_root: str = "pending_review",
    ) -> None:
        """Insert one paused synthetic queue row. Returns None."""
        conn = pq.connect(self.db)
        pq.upsert_queued(
            conn,
            slug=slug,
            company=company,
            title=title,
            url=url,
            url_key=normalize_url(url),
            posting_key=posting_key(company, title),
            networking_contacts_raw=None,
            source_sha256=None,
            source_line=None,
            folder_root=folder_root,
        )
        conn.execute(
            "UPDATE pipeline_queue SET status = 'paused', locked_by = NULL, "
            "lease_expires_at = NULL, paused_at = ? WHERE slug = ?",
            (pq.utc_now(), slug),
        )
        conn.commit()
        conn.close()

    def test_already_handled_ingest_closes_existing_paused_applied_row(self) -> None:
        """Ingest of an Applied+ row closes the existing paused queue row."""
        slug = "synth_recon_ingest_co"
        company = "Synth Recon Ingest Co"
        title = "Platform Product Manager"
        url = "https://example.test/jobs/recon-ingest"
        conn = pq.connect(self.db)
        conn.execute(
            "INSERT INTO jobs (id, company, title, url, status) VALUES (?, ?, ?, ?, ?)",
            (slug, company, title, url, "Applied"),
        )
        conn.commit()
        conn.close()
        self._seed_paused(slug, company=company, title=title, url=url)
        self._write_csv(
            "recon-ingest.csv",
            [
                {
                    "Company": company,
                    "Position": title,
                    "URL": f"{url}?utm_source=board",
                    "Job Description": _jd(" recon-ingest"),
                }
            ],
        )
        counts = self._ingest()
        self.assertEqual(counts["already_handled"], 1)
        self.assertEqual(counts["queued"], 0)
        self.assertFalse((self.pending / slug).exists())
        conn = pq.connect(self.db)
        try:
            self.assertEqual(pq.get_row(conn, slug)["status"], "done")
            claimed = pq.claim_pack("w1", size=1, conn=conn, data_root=self.root)
        finally:
            conn.close()
        self.assertEqual(claimed, [])

    def test_cli_reconcile_already_handled_with_no_inbox_files(self) -> None:
        """--reconcile-already-handled closes AC-475 shapes with an empty inbox."""
        applied_slug = "synth_cli_applied"
        skipped_slug = "synth_cli_skipped"
        archived_slug = "synth_cli_archived"
        applied_company = "Synth Cli Applied Co"
        skipped_company = "Synth Cli Skipped Co"
        archived_company = "Synth Cli Archive Co"
        title = "Platform Product Manager"
        applied_url = "https://example.test/jobs/cli-applied"
        skipped_folder = self.archive_skipped / skipped_slug
        skipped_folder.mkdir()
        (skipped_folder / "Original_JD.txt").write_text(
            "synthetic skipped marker\n", encoding="utf-8"
        )
        archived_folder = self.archive_submissions / archived_slug
        archived_folder.mkdir()
        (archived_folder / "Original_JD.txt").write_text(
            "synthetic archived marker\n", encoding="utf-8"
        )
        conn = pq.connect(self.db)
        conn.execute(
            "INSERT INTO jobs (id, company, title, url, status) VALUES (?, ?, ?, ?, ?)",
            (applied_slug, applied_company, title, applied_url, "Applied"),
        )
        conn.commit()
        conn.close()
        self._seed_paused(
            applied_slug, company=applied_company, title=title, url=applied_url
        )
        self._seed_paused(
            skipped_slug,
            company=skipped_company,
            title=title,
            url="https://example.test/jobs/cli-skipped",
            folder_root="archive/skipped",
        )
        self._seed_paused(
            archived_slug,
            company=archived_company,
            title=title,
            url="https://example.test/jobs/cli-archived",
        )
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            rc = ingest_main(
                [
                    "--inbox",
                    str(self.inbox),
                    "--db",
                    str(self.db),
                    "--reconcile-already-handled",
                ]
            )
        self.assertEqual(rc, 0)
        self.assertEqual(list(self.inbox.glob("*.csv")), [])
        conn = pq.connect(self.db)
        try:
            self.assertEqual(pq.get_row(conn, applied_slug)["status"], "done")
            self.assertEqual(pq.get_row(conn, skipped_slug)["status"], "done")
            self.assertEqual(pq.get_row(conn, archived_slug)["status"], "done")
            claimed = pq.claim_pack("w1", size=3, conn=conn, data_root=self.root)
        finally:
            conn.close()
        self.assertEqual(claimed, [])
        self.assertTrue(skipped_folder.is_dir())
        self.assertTrue(archived_folder.is_dir())


if __name__ == "__main__":
    unittest.main()
