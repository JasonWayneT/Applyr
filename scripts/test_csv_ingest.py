#!/usr/bin/env python3
"""CR-119 csv_ingest helpers — AC-440 write_jd + CR-123 Applied+ / pre-apply.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_csv_ingest -v
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pipeline_queue as pq  # noqa: E402
from csv_ingest import (  # noqa: E402
    APPLIED_PLUS_STATUSES as INGEST_APPLIED_PLUS,
    EMPTY_COMPANY,
    ERROR_CODES,
    FILE_ENCODING,
    FILE_UNPARSEABLE,
    JD_TOO_SHORT,
    NO_DEDUP_KEY,
    PRE_APPLY_STATUSES as INGEST_PRE_APPLY,
    clean_company_field,
    lookup_applied_plus_job,
    resolve_opportunity,
    sanitize,
    validate_row,
    write_jd,
)
from ingest_csv_queue import ingest_inbox  # noqa: E402
from stage0_skip_ledger import (  # noqa: E402
    ensure_schema as ensure_skip_schema,
    normalize_url,
    posting_key,
)


class TestWriteJdFormat(unittest.TestCase):
    def test_write_jd_bytes_match_ac440(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            jd = "Owns the platform roadmap for a B2B product used by enterprise teams."
            path = write_jd(
                "synth_co",
                "https://example.test/jobs/42",
                "Product Manager",
                jd,
                dest_root=dest,
            )
            expected = (
                "URL: https://example.test/jobs/42\n"
                "\n"
                "Title: Product Manager\n"
                "\n"
                f"{jd}\n"
            )
            self.assertEqual(path.read_bytes(), expected.encode("utf-8"))

    def test_write_jd_omits_url_and_title_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            jd = "A job description body with no URL and no title header."
            path = write_jd("synth_co", "", "", jd, dest_root=dest)
            self.assertEqual(path.read_bytes(), f"{jd}\n".encode("utf-8"))

    def test_error_code_set_is_closed(self) -> None:
        self.assertEqual(
            ERROR_CODES,
            {
                EMPTY_COMPANY,
                JD_TOO_SHORT,
                NO_DEDUP_KEY,
                FILE_UNPARSEABLE,
                FILE_ENCODING,
            },
        )
        self.assertEqual(NO_DEDUP_KEY, "NO_DEDUP_KEY")


class TestCleanCompanyField(unittest.TestCase):
    def test_strips_trailing_title(self) -> None:
        self.assertEqual(
            clean_company_field("ESO Product Manager", "Product Manager"),
            "ESO",
        )
        self.assertEqual(sanitize("ESO"), "eso")
        self.assertEqual(
            sanitize(clean_company_field("ESO Product Manager", "Product Manager")),
            "eso",
        )
        self.assertNotEqual(sanitize("ESO Product Manager"), "eso")

    def test_strips_separated_and_at_forms(self) -> None:
        self.assertEqual(clean_company_field("ESO - Product Manager", "Product Manager"), "ESO")
        self.assertEqual(clean_company_field("ESO | Product Manager", "Product Manager"), "ESO")
        self.assertEqual(
            clean_company_field("Businessolver Product Manager Remote", "Product Manager (Remote)"),
            "Businessolver",
        )
        self.assertEqual(
            clean_company_field(
                "Velera Product Manager Shared Branch",
                "Product Manager - Shared Branch",
            ),
            "Velera",
        )
        self.assertEqual(
            clean_company_field(
                "Binance Product Manager Social Features Content",
                "Product Manager - Social Features (Content)",
            ),
            "Binance",
        )
        self.assertEqual(
            clean_company_field("ESO\nProduct Manager", "Product Manager"),
            "ESO",
        )

    def test_leaves_clean_company_alone(self) -> None:
        self.assertEqual(clean_company_field("ESO", "Product Manager"), "ESO")
        self.assertEqual(clean_company_field("Product Management Inc", "Product Manager"), "Product Management Inc")

    def test_title_only_company_is_empty(self) -> None:
        self.assertEqual(clean_company_field("Product Manager", "Product Manager"), "")
        ok, code = validate_row(
            {
                "Company": "Product Manager",
                "Position": "Product Manager",
                "URL": "https://example.test/eso",
                "Job Description": "Owns the platform roadmap for a B2B product used by enterprise teams. " * 8,
            }
        )
        self.assertFalse(ok)
        self.assertEqual(code, EMPTY_COMPANY)


# ---------------------------------------------------------------------------
# CR-123 Story 1.1 — Applied+ ingest refuse (FR-361 / AC-470)
# ---------------------------------------------------------------------------

_JOBS_DDL = """
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  company TEXT,
  title TEXT,
  url TEXT,
  status TEXT
);
"""

SYNTH_APPLIED_COMPANY = "Synth Applied Co"
SYNTH_APPLIED_TITLE = "Platform Product Manager"
SYNTH_APPLIED_URL = "https://example.test/jobs/applied-1"
SYNTH_APPLIED_URL_TRACKED = "https://example.test/jobs/applied-1?utm_source=board"
APPLIED_PLUS_STATUSES = (
    "Applied",
    "Recruiter Screen",
    "Core Interviews",
    "Offer and Negotiation",
)
PRE_APPLY_STATUSES = (
    "Backlog",
    "Drafted",
    "Needs Retry",
    "New",
)
SYNTH_PREAPPLY_COMPANY = "Synth Preapply Co"
SYNTH_PREAPPLY_TITLE = "Platform Product Manager"
SYNTH_PREAPPLY_URL = "https://example.test/jobs/preapply-1"
SYNTH_PREAPPLY_URL_TRACKED = "https://example.test/jobs/preapply-1?utm_source=board"
SYNTH_PREAPPLY_SLUG = "synth_preapply_co"


def _synth_jd(extra: str = "") -> str:
    """Return a synthetic JD over the 200-char ingest floor. No real posting text."""
    body = (
        "This is a synthetic job description used only in CR-123 ingest tests. "
        "It describes platform product work across operations, compliance, and "
        "customer-facing workflows without copying any real posting. "
    )
    return (body * 8) + extra


class AppliedPlusResolveHarness(unittest.TestCase):
    """Temp SQLite + folder roots for resolve_opportunity Applied+ cases."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = Path(self._tmpdir.name)
        self.pending = self.root / "pending_review"
        self.submissions = self.root / "submissions"
        self.archive_submissions = self.root / "archive" / "submissions"
        self.archive_skipped = self.root / "archive" / "skipped"
        self.inbox = self.root / "inbox"
        self.pending.mkdir()
        self.submissions.mkdir()
        self.archive_submissions.mkdir(parents=True)
        self.archive_skipped.mkdir(parents=True)
        self.inbox.mkdir()
        (self.inbox / "archive").mkdir()
        (self.inbox / "quarantine").mkdir()
        self.db = self.root / "jobagent.sqlite"
        self.conn = pq.connect(self.db)
        ensure_skip_schema(self.conn)
        self.conn.executescript(_JOBS_DDL)
        self.conn.commit()
        self.addCleanup(self.conn.close)

    def _insert_job(
        self,
        *,
        job_id: str,
        status: str,
        url: str | None,
        company: str = SYNTH_APPLIED_COMPANY,
        title: str = SYNTH_APPLIED_TITLE,
    ) -> None:
        """Insert one synthetic jobs row. Args are column values. Returns None."""
        self.conn.execute(
            "INSERT INTO jobs (id, company, title, url, status) VALUES (?, ?, ?, ?, ?)",
            (job_id, company, title, url, status),
        )
        self.conn.commit()

    def _resolve(self, url: str, company: str = SYNTH_APPLIED_COMPANY,
                 title: str = SYNTH_APPLIED_TITLE) -> tuple[str, str]:
        """Call resolve_opportunity against this harness. Returns (action, slug)."""
        return resolve_opportunity(
            company,
            title,
            url,
            self.conn,
            pending_root=self.pending,
            submissions_root=self.submissions,
            skip_db_path=self.db,
            archive_submissions_root=self.archive_submissions,
            archive_skipped_root=self.archive_skipped,
        )

    def _skip_count(self) -> int:
        """Return stage0_skips row count on the temp DB."""
        row = self.conn.execute("SELECT COUNT(*) FROM stage0_skips").fetchone()
        return int(row[0])

    def _write_csv(
        self,
        name: str,
        url: str,
        extra_jd: str = "",
        company: str = SYNTH_APPLIED_COMPANY,
        title: str = SYNTH_APPLIED_TITLE,
    ) -> Path:
        """Write one synthetic CSV row to inbox. Returns the CSV path."""
        path = self.inbox / name
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["Company", "Position", "URL", "Job Description"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "Company": company,
                    "Position": title,
                    "URL": url,
                    "Job Description": _synth_jd(extra_jd),
                }
            )
        return path

    def _ingest(self) -> dict[str, int]:
        """Run inbox ingest against this harness. Returns ingest counts."""
        return ingest_inbox(
            self.inbox,
            self.db,
            pending_root=self.pending,
            submissions_root=self.submissions,
            archive_submissions_root=self.archive_submissions,
            archive_skipped_root=self.archive_skipped,
            sleep_s=0,
        )


class TestResolveAppliedPlus(AppliedPlusResolveHarness):
    def test_applied_url_with_tracking_query_is_already_handled(self) -> None:
        self._insert_job(job_id="synth-applied-1", status="Applied", url=SYNTH_APPLIED_URL)
        action, slug = self._resolve(SYNTH_APPLIED_URL_TRACKED)
        self.assertEqual(action, "already_handled")
        self.assertNotEqual(action, "reuse")
        self.assertNotEqual(action, "skip_ledger")
        self.assertEqual(slug, sanitize(SYNTH_APPLIED_COMPANY))
        self.assertEqual(self._skip_count(), 0)

    def test_each_funnel_status_url_is_already_handled(self) -> None:
        for status in APPLIED_PLUS_STATUSES:
            with self.subTest(status=status):
                job_id = f"synth-{sanitize(status)}"
                self.conn.execute("DELETE FROM jobs")
                self.conn.commit()
                self._insert_job(job_id=job_id, status=status, url=SYNTH_APPLIED_URL)
                action, _slug = self._resolve(SYNTH_APPLIED_URL_TRACKED)
                self.assertEqual(action, "already_handled")
                self.assertNotEqual(action, "reuse")
                self.assertNotEqual(action, "skip_ledger")
                self.assertEqual(self._skip_count(), 0)

    def test_urlless_company_title_applied_is_already_handled(self) -> None:
        self._insert_job(job_id="synth-applied-urlless", status="Applied", url="")
        action, slug = self._resolve("")
        self.assertEqual(action, "already_handled")
        self.assertNotEqual(action, "reuse")
        self.assertNotEqual(action, "skip_ledger")
        self.assertEqual(slug, sanitize(SYNTH_APPLIED_COMPANY))
        self.assertEqual(self._skip_count(), 0)

    def test_ingest_applied_plus_writes_nothing_and_is_idempotent(self) -> None:
        self._insert_job(job_id="synth-applied-ingest", status="Applied", url=SYNTH_APPLIED_URL)
        first_action, _ = self._resolve(SYNTH_APPLIED_URL_TRACKED)
        self.assertEqual(first_action, "already_handled")
        self.assertEqual(self._skip_count(), 0)

        self._write_csv("applied-1.csv", SYNTH_APPLIED_URL_TRACKED, extra_jd=" first")
        first = self._ingest()
        self.assertEqual(first["already_handled"], 1)
        self.assertEqual(first["skipped_ledger"], 0)
        self.assertEqual(first["queued"], 0)
        self.assertEqual(first.get("reused", 0), 0)
        self.assertFalse((self.pending / sanitize(SYNTH_APPLIED_COMPANY)).exists())
        self.assertEqual(list(self.pending.iterdir()), [])
        queue_n = self.conn.execute("SELECT COUNT(*) FROM pipeline_queue").fetchone()[0]
        self.assertEqual(int(queue_n), 0)
        self.assertEqual(self._skip_count(), 0)

        second_action, _ = self._resolve(SYNTH_APPLIED_URL_TRACKED)
        self.assertEqual(second_action, "already_handled")

        self._write_csv("applied-2.csv", SYNTH_APPLIED_URL_TRACKED, extra_jd=" second")
        second = self._ingest()
        self.assertEqual(second["already_handled"], 1)
        self.assertEqual(second["skipped_ledger"], 0)
        self.assertEqual(second["queued"], 0)
        queue_n = self.conn.execute("SELECT COUNT(*) FROM pipeline_queue").fetchone()[0]
        self.assertEqual(int(queue_n), 0)
        self.assertEqual(list(self.pending.iterdir()), [])
        self.assertEqual(self._skip_count(), 0)


# ---------------------------------------------------------------------------
# CR-123 Story 1.2 — Pre-apply is not already-applied (FR-361 / AC-476)
# ---------------------------------------------------------------------------


class TestResolvePreApply(AppliedPlusResolveHarness):
    def _seed_queue(
        self,
        *,
        slug: str,
        company: str,
        title: str,
        url: str | None,
    ) -> None:
        """Insert one synthetic queued row. Args are posting fields. Returns None."""
        pq.upsert_queued(
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
            folder_root="pending_review",
        )

    def test_pre_apply_and_applied_plus_are_disjoint(self) -> None:
        self.assertTrue(INGEST_PRE_APPLY.isdisjoint(INGEST_APPLIED_PLUS))
        self.assertEqual(INGEST_PRE_APPLY, frozenset(PRE_APPLY_STATUSES))

    def test_each_pre_apply_status_url_is_not_already_handled(self) -> None:
        for status in PRE_APPLY_STATUSES:
            with self.subTest(status=status):
                self.conn.execute("DELETE FROM jobs")
                self.conn.commit()
                self._insert_job(
                    job_id=f"synth-preapply-{sanitize(status)}",
                    status=status,
                    url=SYNTH_PREAPPLY_URL,
                    company=SYNTH_PREAPPLY_COMPANY,
                    title=SYNTH_PREAPPLY_TITLE,
                )
                hit = lookup_applied_plus_job(
                    self.conn,
                    SYNTH_PREAPPLY_URL_TRACKED,
                    SYNTH_PREAPPLY_COMPANY,
                    SYNTH_PREAPPLY_TITLE,
                )
                self.assertIsNone(hit)
                action, _slug = self._resolve(
                    SYNTH_PREAPPLY_URL_TRACKED,
                    company=SYNTH_PREAPPLY_COMPANY,
                    title=SYNTH_PREAPPLY_TITLE,
                )
                self.assertEqual(action, "create")
                self.assertNotEqual(action, "already_handled")
                self.assertNotEqual(action, "skip_ledger")
                self.assertEqual(self._skip_count(), 0)

    def test_backlog_url_with_live_pending_folder_is_reuse(self) -> None:
        self._insert_job(
            job_id="synth-backlog-folder",
            status="Backlog",
            url=SYNTH_PREAPPLY_URL,
            company=SYNTH_PREAPPLY_COMPANY,
            title=SYNTH_PREAPPLY_TITLE,
        )
        write_jd(
            SYNTH_PREAPPLY_SLUG,
            SYNTH_PREAPPLY_URL,
            SYNTH_PREAPPLY_TITLE,
            _synth_jd(" live-folder"),
            dest_root=self.pending,
        )
        action, slug = self._resolve(
            SYNTH_PREAPPLY_URL_TRACKED,
            company=SYNTH_PREAPPLY_COMPANY,
            title=SYNTH_PREAPPLY_TITLE,
        )
        self.assertEqual(action, "reuse")
        self.assertEqual(slug, SYNTH_PREAPPLY_SLUG)
        self.assertNotEqual(action, "already_handled")
        self.assertEqual(self._skip_count(), 0)

    def test_backlog_url_with_existing_queue_row_is_reuse(self) -> None:
        self._insert_job(
            job_id="synth-backlog-queue",
            status="Backlog",
            url=SYNTH_PREAPPLY_URL,
            company=SYNTH_PREAPPLY_COMPANY,
            title=SYNTH_PREAPPLY_TITLE,
        )
        self._seed_queue(
            slug=SYNTH_PREAPPLY_SLUG,
            company=SYNTH_PREAPPLY_COMPANY,
            title=SYNTH_PREAPPLY_TITLE,
            url=SYNTH_PREAPPLY_URL,
        )
        action, slug = self._resolve(
            SYNTH_PREAPPLY_URL_TRACKED,
            company=SYNTH_PREAPPLY_COMPANY,
            title=SYNTH_PREAPPLY_TITLE,
        )
        self.assertEqual(action, "reuse")
        self.assertEqual(slug, SYNTH_PREAPPLY_SLUG)
        self.assertNotEqual(action, "already_handled")
        self.assertEqual(self._skip_count(), 0)
        queue_n = self.conn.execute("SELECT COUNT(*) FROM pipeline_queue").fetchone()[0]
        self.assertEqual(int(queue_n), 1)

    def test_urlless_pre_apply_company_title_is_not_already_handled(self) -> None:
        for status in PRE_APPLY_STATUSES:
            with self.subTest(status=status):
                self.conn.execute("DELETE FROM jobs")
                self.conn.commit()
                self._insert_job(
                    job_id=f"synth-preapply-urlless-{sanitize(status)}",
                    status=status,
                    url="",
                    company=SYNTH_PREAPPLY_COMPANY,
                    title=SYNTH_PREAPPLY_TITLE,
                )
                hit = lookup_applied_plus_job(
                    self.conn, "", SYNTH_PREAPPLY_COMPANY, SYNTH_PREAPPLY_TITLE
                )
                self.assertIsNone(hit)
                action, _slug = self._resolve(
                    "",
                    company=SYNTH_PREAPPLY_COMPANY,
                    title=SYNTH_PREAPPLY_TITLE,
                )
                self.assertEqual(action, "create")
                self.assertNotEqual(action, "already_handled")
                self.assertEqual(self._skip_count(), 0)

    def test_urlless_drafted_with_queue_row_is_reuse(self) -> None:
        self._insert_job(
            job_id="synth-drafted-urlless-queue",
            status="Drafted",
            url="",
            company=SYNTH_PREAPPLY_COMPANY,
            title=SYNTH_PREAPPLY_TITLE,
        )
        self._seed_queue(
            slug=SYNTH_PREAPPLY_SLUG,
            company=SYNTH_PREAPPLY_COMPANY,
            title=SYNTH_PREAPPLY_TITLE,
            url=None,
        )
        action, slug = self._resolve(
            "",
            company=SYNTH_PREAPPLY_COMPANY,
            title=SYNTH_PREAPPLY_TITLE,
        )
        self.assertEqual(action, "reuse")
        self.assertEqual(slug, SYNTH_PREAPPLY_SLUG)
        self.assertNotEqual(action, "already_handled")
        self.assertEqual(self._skip_count(), 0)

    def test_ingest_backlog_with_live_folder_reuses_and_writes_no_skip(self) -> None:
        self._insert_job(
            job_id="synth-backlog-ingest",
            status="Backlog",
            url=SYNTH_PREAPPLY_URL,
            company=SYNTH_PREAPPLY_COMPANY,
            title=SYNTH_PREAPPLY_TITLE,
        )
        write_jd(
            SYNTH_PREAPPLY_SLUG,
            SYNTH_PREAPPLY_URL,
            SYNTH_PREAPPLY_TITLE,
            _synth_jd(" before-ingest"),
            dest_root=self.pending,
        )
        before = (self.pending / SYNTH_PREAPPLY_SLUG / "Original_JD.txt").read_bytes()
        self._write_csv(
            "preapply-1.csv",
            SYNTH_PREAPPLY_URL_TRACKED,
            extra_jd=" must-not-rewrite",
            company=SYNTH_PREAPPLY_COMPANY,
            title=SYNTH_PREAPPLY_TITLE,
        )
        counts = self._ingest()
        self.assertEqual(counts.get("already_handled", 0), 0)
        self.assertEqual(counts["reused"], 1)
        self.assertEqual(counts["skipped_ledger"], 0)
        self.assertEqual(counts["queued"], 0)
        after = (self.pending / SYNTH_PREAPPLY_SLUG / "Original_JD.txt").read_bytes()
        self.assertEqual(after, before)
        self.assertEqual(self._skip_count(), 0)

    def test_ingest_backlog_without_live_folder_creates(self) -> None:
        self._insert_job(
            job_id="synth-backlog-create",
            status="Backlog",
            url=SYNTH_PREAPPLY_URL,
            company=SYNTH_PREAPPLY_COMPANY,
            title=SYNTH_PREAPPLY_TITLE,
        )
        self._write_csv(
            "preapply-create.csv",
            SYNTH_PREAPPLY_URL_TRACKED,
            extra_jd=" create-path",
            company=SYNTH_PREAPPLY_COMPANY,
            title=SYNTH_PREAPPLY_TITLE,
        )
        counts = self._ingest()
        self.assertEqual(counts.get("already_handled", 0), 0)
        self.assertEqual(counts["queued"], 1)
        self.assertEqual(counts["skipped_ledger"], 0)
        self.assertTrue((self.pending / SYNTH_PREAPPLY_SLUG).exists())
        self.assertEqual(self._skip_count(), 0)
        queue_n = self.conn.execute("SELECT COUNT(*) FROM pipeline_queue").fetchone()[0]
        self.assertEqual(int(queue_n), 1)
        row = pq.get_row(self.conn, SYNTH_PREAPPLY_SLUG)
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "queued")


# ---------------------------------------------------------------------------
# CR-123 Story 1.3 — Archive trees are already-handled, not reuse (FR-362 / AC-471)
# ---------------------------------------------------------------------------

SYNTH_ARCHIVE_COMPANY = "Synth Archive Co"
SYNTH_ARCHIVE_TITLE = "Platform Product Manager"
SYNTH_ARCHIVE_URL = "https://example.test/jobs/archive-1"
SYNTH_ARCHIVE_URL_TRACKED = "https://example.test/jobs/archive-1?utm_source=board"
SYNTH_ARCHIVE_SLUG = "synth_archive_co"

SYNTH_SKIPPED_COMPANY = "Synth Skipped Archive Co"
SYNTH_SKIPPED_TITLE = "Platform Product Manager"
SYNTH_SKIPPED_URL = "https://example.test/jobs/skipped-archive-1"
SYNTH_SKIPPED_URL_TRACKED = "https://example.test/jobs/skipped-archive-1?utm_source=board"
SYNTH_SKIPPED_SLUG = "synth_skipped_archive_co"


class ArchiveResolveHarness(AppliedPlusResolveHarness):
    """Temp archive/submissions + archive/skipped roots. Never uses data/archive."""

    def _resolve(
        self,
        url: str,
        company: str = SYNTH_ARCHIVE_COMPANY,
        title: str = SYNTH_ARCHIVE_TITLE,
    ) -> tuple[str, str]:
        """Call resolve_opportunity with temp archive roots. Returns (action, slug)."""
        return resolve_opportunity(
            company,
            title,
            url,
            self.conn,
            pending_root=self.pending,
            submissions_root=self.submissions,
            skip_db_path=self.db,
            archive_submissions_root=self.archive_submissions,
            archive_skipped_root=self.archive_skipped,
        )

    def _ingest(self) -> dict[str, int]:
        """Run inbox ingest against this harness. Returns ingest counts."""
        return ingest_inbox(
            self.inbox,
            self.db,
            pending_root=self.pending,
            submissions_root=self.submissions,
            archive_submissions_root=self.archive_submissions,
            archive_skipped_root=self.archive_skipped,
            sleep_s=0,
        )

    def _plant_archive_jd(
        self,
        dest_root: Path,
        slug: str,
        url: str,
        title: str,
        extra: str = " archive",
    ) -> None:
        """Write a synthetic Original_JD.txt under a temp archive root. Returns None."""
        write_jd(slug, url, title, _synth_jd(extra), dest_root=dest_root)


class TestResolveArchiveTrees(ArchiveResolveHarness):
    def test_archive_submissions_url_is_already_handled(self) -> None:
        self._plant_archive_jd(
            self.archive_submissions,
            SYNTH_ARCHIVE_SLUG,
            SYNTH_ARCHIVE_URL,
            SYNTH_ARCHIVE_TITLE,
        )
        action, slug = self._resolve(SYNTH_ARCHIVE_URL_TRACKED)
        self.assertEqual(action, "already_handled")
        self.assertNotEqual(action, "reuse")
        self.assertNotEqual(action, "skip_ledger")
        self.assertEqual(slug, SYNTH_ARCHIVE_SLUG)
        self.assertEqual(self._skip_count(), 0)

    def test_archive_skipped_url_is_already_handled(self) -> None:
        self._plant_archive_jd(
            self.archive_skipped,
            SYNTH_SKIPPED_SLUG,
            SYNTH_SKIPPED_URL,
            SYNTH_SKIPPED_TITLE,
        )
        action, slug = self._resolve(
            SYNTH_SKIPPED_URL_TRACKED,
            company=SYNTH_SKIPPED_COMPANY,
            title=SYNTH_SKIPPED_TITLE,
        )
        self.assertEqual(action, "already_handled")
        self.assertNotEqual(action, "reuse")
        self.assertNotEqual(action, "skip_ledger")
        self.assertEqual(slug, SYNTH_SKIPPED_SLUG)
        self.assertEqual(self._skip_count(), 0)

    def test_urlless_archive_company_title_is_already_handled(self) -> None:
        self._plant_archive_jd(
            self.archive_submissions,
            SYNTH_ARCHIVE_SLUG,
            "",
            SYNTH_ARCHIVE_TITLE,
            extra=" urlless-archive",
        )
        action, slug = self._resolve("")
        self.assertEqual(action, "already_handled")
        self.assertNotEqual(action, "reuse")
        self.assertNotEqual(action, "skip_ledger")
        self.assertEqual(slug, SYNTH_ARCHIVE_SLUG)
        self.assertEqual(self._skip_count(), 0)

    def test_live_pending_wins_reuse_over_archive(self) -> None:
        self._plant_archive_jd(
            self.archive_submissions,
            SYNTH_ARCHIVE_SLUG,
            SYNTH_ARCHIVE_URL,
            SYNTH_ARCHIVE_TITLE,
            extra=" archive-copy",
        )
        write_jd(
            SYNTH_ARCHIVE_SLUG,
            SYNTH_ARCHIVE_URL,
            SYNTH_ARCHIVE_TITLE,
            _synth_jd(" live-pending"),
            dest_root=self.pending,
        )
        action, slug = self._resolve(SYNTH_ARCHIVE_URL_TRACKED)
        self.assertEqual(action, "reuse")
        self.assertEqual(slug, SYNTH_ARCHIVE_SLUG)
        self.assertNotEqual(action, "already_handled")
        self.assertEqual(self._skip_count(), 0)

    def test_ingest_archive_url_writes_nothing_and_does_not_close_queue(self) -> None:
        self._plant_archive_jd(
            self.archive_submissions,
            SYNTH_ARCHIVE_SLUG,
            SYNTH_ARCHIVE_URL,
            SYNTH_ARCHIVE_TITLE,
        )
        first_action, _ = self._resolve(SYNTH_ARCHIVE_URL_TRACKED)
        self.assertEqual(first_action, "already_handled")
        self.assertEqual(self._skip_count(), 0)

        self._write_csv(
            "archive-1.csv",
            SYNTH_ARCHIVE_URL_TRACKED,
            extra_jd=" archive-ingest",
            company=SYNTH_ARCHIVE_COMPANY,
            title=SYNTH_ARCHIVE_TITLE,
        )
        counts = self._ingest()
        self.assertEqual(counts["already_handled"], 1)
        self.assertEqual(counts["skipped_ledger"], 0)
        self.assertEqual(counts["queued"], 0)
        self.assertEqual(counts.get("reused", 0), 0)
        self.assertFalse((self.pending / SYNTH_ARCHIVE_SLUG).exists())
        self.assertEqual(list(self.pending.iterdir()), [])
        queue_n = self.conn.execute("SELECT COUNT(*) FROM pipeline_queue").fetchone()[0]
        self.assertEqual(int(queue_n), 0)
        self.assertEqual(self._skip_count(), 0)

    def test_existing_queue_row_stays_reuse_and_is_not_closed(self) -> None:
        self._plant_archive_jd(
            self.archive_submissions,
            SYNTH_ARCHIVE_SLUG,
            SYNTH_ARCHIVE_URL,
            SYNTH_ARCHIVE_TITLE,
        )
        pq.upsert_queued(
            self.conn,
            slug=SYNTH_ARCHIVE_SLUG,
            company=SYNTH_ARCHIVE_COMPANY,
            title=SYNTH_ARCHIVE_TITLE,
            url=SYNTH_ARCHIVE_URL,
            url_key=normalize_url(SYNTH_ARCHIVE_URL),
            posting_key=posting_key(SYNTH_ARCHIVE_COMPANY, SYNTH_ARCHIVE_TITLE),
            networking_contacts_raw=None,
            source_sha256=None,
            source_line=None,
            folder_root="pending_review",
        )
        action, slug = self._resolve(SYNTH_ARCHIVE_URL_TRACKED)
        self.assertEqual(action, "reuse")
        self.assertEqual(slug, SYNTH_ARCHIVE_SLUG)
        self.assertNotEqual(action, "already_handled")
        row = pq.get_row(self.conn, SYNTH_ARCHIVE_SLUG)
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "queued")
        queue_n = self.conn.execute("SELECT COUNT(*) FROM pipeline_queue").fetchone()[0]
        self.assertEqual(int(queue_n), 1)
        self.assertEqual(self._skip_count(), 0)


if __name__ == "__main__":
    unittest.main()
