#!/usr/bin/env python3
"""
Tests for scripts/stage0_db_gate.py — no real DB required.

All fixtures use in-memory SQLite connections so the tests are portable and
have zero external dependencies.  Each test helper creates its own connection,
inserts rows, then passes the connection into evaluate_db_gate via the _conn
kwarg so the function skips its own open/close lifecycle.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stage0_db_gate import (
    company_token_match,
    evaluate_db_gate,
    is_different_role,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    status TEXT DEFAULT 'New',
    rejection_type TEXT,
    outcome_notes TEXT,
    status_changed_at DATETIME
)
"""


def _make_conn() -> sqlite3.Connection:
    """Return a fresh in-memory connection with the jobs table."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(_DDL)
    conn.commit()
    return conn


def _insert(conn: sqlite3.Connection, **kwargs) -> None:
    """Insert a single row; *id* is auto-generated if omitted."""
    row = {
        "id": kwargs.get("id", f"row-{id(kwargs)}"),
        "company": kwargs["company"],
        "title": kwargs.get("title", "PM"),
        "status": kwargs.get("status", "New"),
        "rejection_type": kwargs.get("rejection_type", None),
        "outcome_notes": kwargs.get("outcome_notes", None),
        "status_changed_at": kwargs.get("status_changed_at", None),
    }
    conn.execute(
        "INSERT INTO jobs (id,company,title,status,rejection_type,outcome_notes,status_changed_at)"
        " VALUES (:id,:company,:title,:status,:rejection_type,:outcome_notes,:status_changed_at)",
        row,
    )
    conn.commit()


def _dt(days_ago: float) -> str:
    """ISO-8601 UTC string for a datetime *days_ago* days in the past."""
    t = datetime.now(tz=timezone.utc) - timedelta(days=days_ago)
    return t.isoformat()


# ---------------------------------------------------------------------------
# company_token_match tests
# ---------------------------------------------------------------------------

class TestCompanyTokenMatch(unittest.TestCase):
    def test_kin_does_not_match_draftkings(self):
        self.assertFalse(company_token_match("Kin", "DraftKings"))

    def test_kin_insurance_matches_kin_insurance(self):
        self.assertTrue(company_token_match("Kin Insurance", "Kin Insurance"))

    def test_case_insensitive(self):
        self.assertTrue(company_token_match("acme corp", "Acme Corp"))

    def test_partial_word_no_match(self):
        # "Pro" should not match "Procore"
        self.assertFalse(company_token_match("Pro", "Procore"))

    def test_full_word_matches(self):
        self.assertTrue(company_token_match("Procore", "Procore Technologies"))

    def test_empty_query(self):
        self.assertFalse(company_token_match("", "Anything"))

    def test_multi_token_all_present(self):
        self.assertTrue(company_token_match("Acme Corp", "Acme Corp Solutions"))

    def test_multi_token_partial_fail(self):
        self.assertFalse(company_token_match("Acme Widget", "Acme Corp"))


# ---------------------------------------------------------------------------
# evaluate_db_gate tests
# ---------------------------------------------------------------------------

class TestSelfRejected(unittest.TestCase):
    """Story test: Self-Rejected → reject (permanent)."""

    def test_self_rejected_permanent_block(self):
        conn = _make_conn()
        _insert(conn, company="Acme Corp", status="Self-Rejected",
                status_changed_at=_dt(500))  # far in the past — still blocked
        result = evaluate_db_gate("Acme Corp", _conn=conn)
        self.assertEqual(result["action"], "reject")
        self.assertEqual(result["reason_code"], "self_rejected")

    def test_self_rejected_no_date_still_blocked(self):
        conn = _make_conn()
        _insert(conn, company="Acme Corp", status="Self-Rejected",
                status_changed_at=None)
        result = evaluate_db_gate("Acme Corp", _conn=conn)
        self.assertEqual(result["action"], "reject")
        self.assertEqual(result["reason_code"], "self_rejected")


class TestIsDifferentRole(unittest.TestCase):
    """Found 2026-08-08 (thermo_fisher_scientific): a self-rejected 'Gas
    Analyzers' PM posting permanently blocked an unrelated 'Digital Product
    Manager' role at the same company. is_different_role() is the heuristic
    that tells the two apart -- conservative by design (stays blocking) unless
    it can positively prove the roles differ."""

    def test_gas_analyzers_differs_from_digital_pm(self):
        self.assertTrue(is_different_role(
            "Digital Product Manager", "Product Manager, Gas Analyzers"
        ))

    def test_identical_titles_not_different(self):
        self.assertFalse(is_different_role(
            "Digital Product Manager", "Digital Product Manager"
        ))

    def test_generic_both_sides_stays_conservative(self):
        # Neither title has a non-generic remainder -- can't prove different.
        self.assertFalse(is_different_role("Product Manager", "Senior Product Manager"))

    def test_missing_row_title_stays_conservative(self):
        self.assertFalse(is_different_role("Digital Product Manager", ""))

    def test_missing_query_role_stays_conservative(self):
        self.assertFalse(is_different_role("", "Product Manager, Gas Analyzers"))

    def test_shared_distinguishing_token_not_different(self):
        # Both sides specifically call out "Healthcare" -- same domain, same role family.
        self.assertFalse(is_different_role(
            "Healthcare Product Manager", "Senior Product Manager, Healthcare Platform"
        ))


class TestRoleScopedDbGate(unittest.TestCase):
    """evaluate_db_gate(role=...) end-to-end: a positively-different-role prior
    row no longer blocks, but stays visible in matched_rows, and the default
    (role=None or ambiguous titles) behaves exactly as before -- company-wide."""

    def test_different_role_self_reject_does_not_block(self):
        conn = _make_conn()
        _insert(conn, company="Thermo Fisher Scientific", title="Product Manager, Gas Analyzers",
                status="Self-Rejected", status_changed_at=_dt(60))
        result = evaluate_db_gate(
            "Thermo Fisher Scientific", role="Digital Product Manager", _conn=conn
        )
        self.assertNotEqual(result["action"], "reject")
        self.assertEqual(len(result["matched_rows"]), 1, "row stays visible even though not blocking")

    def test_same_role_self_reject_still_blocks(self):
        conn = _make_conn()
        _insert(conn, company="Thermo Fisher Scientific", title="Digital Product Manager",
                status="Self-Rejected", status_changed_at=_dt(60))
        result = evaluate_db_gate(
            "Thermo Fisher Scientific", role="Digital Product Manager", _conn=conn
        )
        self.assertEqual(result["action"], "reject")
        self.assertEqual(result["reason_code"], "self_rejected")

    def test_no_role_passed_keeps_prior_company_wide_behavior(self):
        conn = _make_conn()
        _insert(conn, company="Thermo Fisher Scientific", title="Product Manager, Gas Analyzers",
                status="Self-Rejected", status_changed_at=_dt(60))
        result = evaluate_db_gate("Thermo Fisher Scientific", _conn=conn)  # no role kwarg
        self.assertEqual(result["action"], "reject")

    def test_different_role_cooldown_row_does_not_block(self):
        conn = _make_conn()
        _insert(conn, company="Thermo Fisher Scientific", title="Field Applications Scientist",
                status="Rejected", rejection_type="Rejected", status_changed_at=_dt(10))
        result = evaluate_db_gate(
            "Thermo Fisher Scientific", role="Digital Product Manager", _conn=conn
        )
        self.assertNotEqual(result["action"], "reject")
        self.assertEqual(result["reason_code"], "different_role_at_company")


class TestSelfRejectedPendingAssets(unittest.TestCase):
    """Self-Rejected with 'Pending-assets cleanup' prefix → 30-day no-signal cooldown."""

    def test_pending_assets_within_30d_rejects(self):
        conn = _make_conn()
        _insert(conn, company="Acme Corp", status="Self-Rejected",
                outcome_notes="Pending-assets cleanup — waiting on resume",
                status_changed_at=_dt(10))  # 10 days ago → within 30d
        result = evaluate_db_gate("Acme Corp", _conn=conn)
        self.assertEqual(result["action"], "reject")
        self.assertIn("cooldown", result["reason_code"])

    def test_pending_assets_past_30d_reapply_flag(self):
        conn = _make_conn()
        _insert(conn, company="Acme Corp", status="Self-Rejected",
                outcome_notes="Pending-assets cleanup — done",
                status_changed_at=_dt(40))  # 40 days ago → past 30d
        result = evaluate_db_gate("Acme Corp", _conn=conn)
        self.assertEqual(result["action"], "reapply_flag")


class TestGhostedCooldown(unittest.TestCase):
    """Ghosted → 30-day cooldown."""

    def test_ghosted_within_30d_rejects(self):
        conn = _make_conn()
        _insert(conn, company="Widgetco", status="Rejected",
                rejection_type="Ghosted", status_changed_at=_dt(15))
        result = evaluate_db_gate("Widgetco", _conn=conn)
        self.assertEqual(result["action"], "reject")

    def test_ghosted_40d_ago_reapply_flag(self):
        conn = _make_conn()
        _insert(conn, company="Widgetco", status="Rejected",
                rejection_type="Ghosted", status_changed_at=_dt(40))
        result = evaluate_db_gate("Widgetco", _conn=conn)
        self.assertEqual(result["action"], "reapply_flag")


class TestEvaluatedNoCooldown(unittest.TestCase):
    """Evaluated-no rejection types → 120-day cooldown."""

    def test_rejected_within_120d(self):
        conn = _make_conn()
        _insert(conn, company="BigCo", status="Rejected",
                rejection_type="Rejected", status_changed_at=_dt(60))
        result = evaluate_db_gate("BigCo", _conn=conn)
        self.assertEqual(result["action"], "reject")

    def test_rejected_130d_ago_reapply_flag(self):
        conn = _make_conn()
        _insert(conn, company="BigCo", status="Rejected",
                rejection_type="Rejected", status_changed_at=_dt(130))
        result = evaluate_db_gate("BigCo", _conn=conn)
        self.assertEqual(result["action"], "reapply_flag")

    def test_domain_mismatch_within_120d(self):
        conn = _make_conn()
        _insert(conn, company="BigCo", status="Closed",
                rejection_type="Domain Mismatch", status_changed_at=_dt(90))
        result = evaluate_db_gate("BigCo", _conn=conn)
        self.assertEqual(result["action"], "reject")

    def test_title_ceiling_within_120d(self):
        conn = _make_conn()
        _insert(conn, company="BigCo", status="Rejected",
                rejection_type="Title Ceiling", status_changed_at=_dt(30))
        result = evaluate_db_gate("BigCo", _conn=conn)
        self.assertEqual(result["action"], "reject")

    def test_unfit_within_120d(self):
        conn = _make_conn()
        _insert(conn, company="BigCo", status="Rejected",
                rejection_type="Unfit", status_changed_at=_dt(1))
        result = evaluate_db_gate("BigCo", _conn=conn)
        self.assertEqual(result["action"], "reject")


class TestNullStatusChangedAt(unittest.TestCase):
    """NULL status_changed_at → conservative: treat as within cooldown."""

    def test_null_date_ghosted_rejects(self):
        conn = _make_conn()
        _insert(conn, company="NullDate Co", status="Rejected",
                rejection_type="Ghosted", status_changed_at=None)
        result = evaluate_db_gate("NullDate Co", _conn=conn)
        self.assertEqual(result["action"], "reject")
        self.assertIn("cooldown", result["reason_code"])

    def test_null_date_evaluated_no_rejects(self):
        conn = _make_conn()
        _insert(conn, company="NullDate Co", status="Rejected",
                rejection_type="Rejected", status_changed_at=None)
        result = evaluate_db_gate("NullDate Co", _conn=conn)
        self.assertEqual(result["action"], "reject")


class TestClear(unittest.TestCase):
    """No terminal rows → clear."""

    def test_no_rows_at_all(self):
        conn = _make_conn()
        result = evaluate_db_gate("Brandnew Corp", _conn=conn)
        self.assertEqual(result["action"], "clear")
        self.assertEqual(result["reason_code"], "no_terminal_rows")

    def test_only_active_rows_clears(self):
        conn = _make_conn()
        _insert(conn, company="Brandnew Corp", status="Applied")
        result = evaluate_db_gate("Brandnew Corp", _conn=conn)
        self.assertEqual(result["action"], "clear")

    def test_token_mismatch_no_false_positive(self):
        # "Kin" in DB should not block a lookup for "DraftKings"
        conn = _make_conn()
        _insert(conn, company="Kin Insurance", status="Rejected",
                rejection_type="Rejected", status_changed_at=_dt(10))
        result = evaluate_db_gate("DraftKings", _conn=conn)
        self.assertEqual(result["action"], "clear")


class TestMatchedRowsIncluded(unittest.TestCase):
    """matched_rows should surface the classified rows for callers."""

    def test_matched_rows_present_on_reject(self):
        conn = _make_conn()
        _insert(conn, company="Acme", status="Rejected",
                rejection_type="Ghosted", status_changed_at=_dt(5))
        result = evaluate_db_gate("Acme", _conn=conn)
        self.assertIsInstance(result["matched_rows"], list)
        self.assertGreater(len(result["matched_rows"]), 0)

    def test_matched_rows_empty_on_clear(self):
        conn = _make_conn()
        result = evaluate_db_gate("Ghost Corp", _conn=conn)
        self.assertEqual(result["matched_rows"], [])


class TestNoLongerAvailable(unittest.TestCase):
    """'No Longer Available' is a no-signal type → 30d cooldown."""

    def test_nla_within_30d_rejects(self):
        conn = _make_conn()
        _insert(conn, company="Poof Inc", status="Closed",
                rejection_type="No Longer Available", status_changed_at=_dt(20))
        result = evaluate_db_gate("Poof Inc", _conn=conn)
        self.assertEqual(result["action"], "reject")

    def test_nla_past_30d_reapply_flag(self):
        conn = _make_conn()
        _insert(conn, company="Poof Inc", status="Closed",
                rejection_type="No Longer Available", status_changed_at=_dt(35))
        result = evaluate_db_gate("Poof Inc", _conn=conn)
        self.assertEqual(result["action"], "reapply_flag")


if __name__ == "__main__":
    unittest.main()
