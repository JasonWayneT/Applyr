#!/usr/bin/env python3
"""CR-091 Stage 0 skip ledger and folder placement tests.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_stage0_skip_ledger -v
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stage0_skip_ledger import (  # noqa: E402
    clear_skip,
    connect,
    lookup_skip,
    normalize_url,
    posting_key,
    record_skip,
)
import stage0_placement as placement  # noqa: E402
from stage0_placement import apply_stage0_placement  # noqa: E402


_SKIP_GATE = {
    "company": "Expel",
    "role": "Product Manager",
    "url": "https://job-boards.greenhouse.io/expel/jobs/123?gh_src=abc",
    "decision": "SKIP",
    "tier": "Skip",
    "skip_reason": "DB: prior Closed",
}

_PASS_GATE = {
    "company": "Skyflow",
    "role": "Product Manager",
    "url": "https://example.com/jobs/skyflow",
    "decision": "PASS",
    "tier": "Tier 1",
    "skip_reason": None,
}


class NormalizeUrlTests(unittest.TestCase):
    def test_strips_utm_and_gh_src(self):
        raw = "https://Job-Boards.Greenhouse.io/expel/jobs/123?gh_src=abc&utm_source=li"
        self.assertEqual(
            normalize_url(raw),
            "https://job-boards.greenhouse.io/expel/jobs/123",
        )

    def test_keeps_real_query(self):
        raw = "https://example.com/jobs/1?gh_jid=99"
        self.assertEqual(normalize_url(raw), "https://example.com/jobs/1?gh_jid=99")

    def test_empty_is_none(self):
        self.assertIsNone(normalize_url(""))
        self.assertIsNone(normalize_url(None))


class SkipLedgerTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.db = Path(self._tmpdir.name) / "test.sqlite"
        self.conn = connect(self.db)
        self.addCleanup(self.conn.close)

    def test_url_hit_ignores_tracking_params(self):
        record_skip(
            url="https://job-boards.greenhouse.io/expel/jobs/123",
            company="Expel",
            title="Product Manager",
            skip_reason="already applied",
            _conn=self.conn,
        )
        hit = lookup_skip(
            url="https://job-boards.greenhouse.io/expel/jobs/123?utm_medium=jobboard&gh_src=x",
            company="Expel",
            title="Product Manager",
            _conn=self.conn,
        )
        self.assertIsNotNone(hit)
        self.assertIn("already applied", hit["skip_reason"])

    def test_same_company_different_title_does_not_hit(self):
        record_skip(
            url="https://example.com/oracle/gpu-pm",
            company="Oracle",
            title="Principal Program Manager",
            skip_reason="seniority",
            _conn=self.conn,
        )
        miss = lookup_skip(
            url="https://example.com/oracle/ic-pm",
            company="Oracle",
            title="Product Manager",
            _conn=self.conn,
        )
        self.assertIsNone(miss)

    def test_company_title_fallback_when_url_missing(self):
        record_skip(
            url=None,
            company="RetailMeNot",
            title="Product Manager",
            skip_reason="incomplete draft",
            _conn=self.conn,
        )
        hit = lookup_skip(
            url=None,
            company="RetailMeNot",
            title="Product Manager",
            _conn=self.conn,
        )
        self.assertIsNotNone(hit)
        miss = lookup_skip(
            url=None,
            company="RetailMeNot",
            title="Engineering Manager",
            _conn=self.conn,
        )
        self.assertIsNone(miss)

    def test_clear_skip_after_force_pass(self):
        record_skip(
            url="https://example.com/jobs/1",
            company="Acme",
            title="PM",
            skip_reason="thin jd",
            _conn=self.conn,
        )
        self.assertTrue(
            clear_skip(url="https://example.com/jobs/1", company="Acme", title="PM", _conn=self.conn)
        )
        self.assertIsNone(
            lookup_skip(url="https://example.com/jobs/1", company="Acme", title="PM", _conn=self.conn)
        )

    def test_posting_key_shape(self):
        self.assertEqual(posting_key(" Oracle ", "Product Manager"), "oracle||product manager")


class PlacementTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        root = Path(self._tmpdir.name)
        self.pending = root / "pending_review"
        self.subs = root / "submissions"
        self.skipped = root / "archive" / "skipped"
        self.pending.mkdir()
        self.subs.mkdir()
        self.skipped.mkdir(parents=True)
        self.db = root / "test.sqlite"
        self._patches = [
            mock.patch.object(placement, "PENDING_DIR", self.pending),
            mock.patch.object(placement, "SUBMISSIONS_DIR", self.subs),
            mock.patch.object(placement, "SKIPPED_DIR", self.skipped),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def _write_folder(self, parent: Path, slug: str) -> Path:
        folder = parent / slug
        folder.mkdir()
        (folder / "Original_JD.txt").write_text("URL: https://example.com/x\n\nJD\n", encoding="utf-8")
        return folder

    def test_skip_moves_to_archive_and_records_ledger(self):
        folder = self._write_folder(self.pending, "expel")
        dest = apply_stage0_placement(folder, _SKIP_GATE, db_path=self.db)
        self.assertTrue(str(dest).startswith(str(self.skipped)))
        self.assertFalse(folder.exists())
        self.assertTrue((dest / "Original_JD.txt").exists())
        hit = lookup_skip(
            url=_SKIP_GATE["url"],
            company="Expel",
            title="Product Manager",
            db_path=self.db,
        )
        self.assertIsNotNone(hit)
        self.assertIn("prior Closed", hit["skip_reason"])

    def test_pass_from_pending_promotes_to_submissions(self):
        folder = self._write_folder(self.pending, "skyflow")
        dest = apply_stage0_placement(folder, _PASS_GATE, db_path=self.db)
        self.assertEqual(dest, self.subs / "skyflow")
        self.assertTrue((dest / "Original_JD.txt").exists())
        self.assertFalse(folder.exists())

    def test_pass_from_archive_recovers_to_submissions(self):
        folder = self._write_folder(self.skipped, "skyflow")
        record_skip(
            url=_PASS_GATE["url"],
            company="Skyflow",
            title="Product Manager",
            skip_reason="old decision",
            slug="skyflow",
            archive_path=str(folder),
            db_path=self.db,
        )
        dest = apply_stage0_placement(folder, _PASS_GATE, db_path=self.db)
        self.assertEqual(dest, self.subs / "skyflow")
        self.assertTrue((dest / "Original_JD.txt").exists())
        self.assertFalse(folder.exists())
        self.assertIsNone(
            lookup_skip(
                url=_PASS_GATE["url"],
                company="Skyflow",
                title="Product Manager",
                db_path=self.db,
            )
        )

    def test_unmanaged_temp_folder_is_not_moved(self):
        stray = Path(self._tmpdir.name) / "stray"
        stray.mkdir()
        (stray / "Original_JD.txt").write_text("JD\n", encoding="utf-8")
        dest = apply_stage0_placement(stray, _SKIP_GATE, db_path=self.db)
        self.assertEqual(dest, stray)
        self.assertTrue(stray.exists())
        self.assertIsNone(
            lookup_skip(url=_SKIP_GATE["url"], company="Expel", title="Product Manager", db_path=self.db)
        )

    def test_practice_mode_does_not_write_ledger(self):
        folder = self._write_folder(self.pending, "expel")
        dest = apply_stage0_placement(folder, _SKIP_GATE, mode="practice", db_path=self.db)
        self.assertEqual(dest, folder)
        self.assertTrue(folder.exists())
        self.assertIsNone(
            lookup_skip(url=_SKIP_GATE["url"], company="Expel", title="Product Manager", db_path=self.db)
        )

    def test_force_pass_clears_ledger(self):
        record_skip(
            url=_PASS_GATE["url"],
            company="Skyflow",
            title="Product Manager",
            skip_reason="old skip",
            db_path=self.db,
        )
        folder = self._write_folder(self.pending, "skyflow")
        apply_stage0_placement(folder, _PASS_GATE, db_path=self.db)
        self.assertIsNone(
            lookup_skip(
                url=_PASS_GATE["url"],
                company="Skyflow",
                title="Product Manager",
                db_path=self.db,
            )
        )


class ImportAndFitGateTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = Path(self._tmpdir.name)
        self.pending = self.root / "pending_review"
        self.pending.mkdir()
        self.db = self.root / "test.sqlite"

    def test_import_skips_ledger_url(self):
        import import_csv_to_submissions as imp

        record_skip(
            url="https://example.com/jobs/dup",
            company="DupCo",
            title="PM",
            skip_reason="prior skip",
            db_path=self.db,
        )
        csv_path = self.root / "jobs.csv"
        csv_path.write_text(
            "Company,Position,URL,Job Description\n"
            "DupCo,PM,https://example.com/jobs/dup?utm_source=li,A real job description here.\n",
            encoding="utf-8",
        )
        with mock.patch.object(imp, "PENDING_REVIEW", self.pending), mock.patch.object(
            imp, "SUBMISSIONS", self.root / "submissions"
        ), mock.patch.object(imp, "DB", self.db), mock.patch.object(
            imp, "ROOT", self.root
        ):
            (self.root / "submissions").mkdir()
            created = imp.import_csv(csv_path, set(), {})
        self.assertEqual(created, [])
        self.assertEqual(list(self.pending.iterdir()), [])

    def test_fit_gate_short_circuits_on_ledger_hit(self):
        from build_stage0_fit_gate import build_stage0_fit_gate

        record_skip(
            url="https://example.com/jobs/skipme",
            company="Skipme",
            title="Product Manager",
            skip_reason="people management",
            db_path=self.db,
        )
        folder = self.root / "skipme"
        folder.mkdir()
        (folder / "Original_JD.txt").write_text(
            "URL: https://example.com/jobs/skipme?utm_campaign=x\n\n"
            "Title: Product Manager\n\n"
            "We need a product manager to own the roadmap.\n",
            encoding="utf-8",
        )
        result = build_stage0_fit_gate(
            folder,
            db_gate_result={"action": "clear", "reason": "", "reason_code": "no_terminal_rows"},
            skip_ledger_db=self.db,
        )
        self.assertEqual(result["decision"], "SKIP")
        self.assertEqual(result["skip_reason_code"], "skip_ledger")
        self.assertIn("people management", result["skip_reason"])

    def test_force_does_not_short_circuit_on_ledger(self):
        from build_stage0_fit_gate import build_stage0_fit_gate

        record_skip(
            url="https://example.com/jobs/skipme",
            company="Skipme",
            title="Product Manager",
            skip_reason="people management",
            db_path=self.db,
        )
        folder = self.root / "skipme"
        folder.mkdir()
        (folder / "Original_JD.txt").write_text(
            "URL: https://example.com/jobs/skipme\n\n"
            "Title: Product Manager\n\n"
            "We need a product manager to own the roadmap with engineering.\n"
            "Requirements:\n- 5 years of product management\n",
            encoding="utf-8",
        )
        result = build_stage0_fit_gate(
            folder,
            db_gate_result={"action": "clear", "reason": "", "reason_code": "no_terminal_rows"},
            skip_ledger_db=self.db,
            ignore_skip_ledger=True,
        )
        self.assertNotEqual(result.get("skip_reason_code"), "skip_ledger")


if __name__ == "__main__":
    unittest.main()
