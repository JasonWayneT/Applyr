#!/usr/bin/env python3
"""CR-106 tests for the smart rate-limit cascade decision (Groq/Claude/Perplexity) and the
real user-visible notification it now writes, instead of a stderr-only print, when a provider
is actually rate-limited or a self-counted daily cap trips.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_llm_provider_cascade -v
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import utils  # noqa: E402


def _make_activity_log_db() -> str:
    """Same activity_log shape as server/db.ts's real schema (id, timestamp, level, source,
    message, meta) -- utils.py writes directly into the same SQLite file the Node server owns."""
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            level TEXT NOT NULL,
            source TEXT NOT NULL,
            message TEXT NOT NULL,
            meta TEXT
        )
        """
    )
    conn.commit()
    conn.close()
    return path


def _notification_rows(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT message, meta FROM activity_log WHERE source = 'LLM_Call' AND meta IS NOT NULL"
    ).fetchall()
    conn.close()
    return [{"message": r[0], "meta": json.loads(r[1])} for r in rows]


class TestLogProviderNotification(unittest.TestCase):
    def setUp(self):
        self.db_path = _make_activity_log_db()
        self._patch = mock.patch.object(utils, "DB_PATH", self.db_path)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        os.remove(self.db_path)

    def test_writes_a_notification_with_the_expected_shape(self):
        utils._log_provider_notification("groq", "Groq is rate-limited.", reason="rate_limited_cascade")
        rows = _notification_rows(self.db_path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["meta"]["event"], "llm_provider_cascade")
        self.assertEqual(rows[0]["meta"]["provider"], "groq")
        self.assertEqual(rows[0]["meta"]["reason"], "rate_limited_cascade")

    def test_dedupe_true_skips_a_second_write_within_24h_for_the_same_provider_and_reason(self):
        utils._log_provider_notification(
            "groq", "first", reason="daily_cap_exhausted", dedupe=True, extra={"daily_calls": 14000}
        )
        utils._log_provider_notification(
            "groq", "second", reason="daily_cap_exhausted", dedupe=True, extra={"daily_calls": 14001}
        )
        rows = _notification_rows(self.db_path)
        self.assertEqual(len(rows), 1, "second call within the dedupe window must not insert again")
        self.assertEqual(rows[0]["message"], "first")

    def test_dedupe_does_not_cross_providers(self):
        utils._log_provider_notification("groq", "groq msg", reason="daily_cap_exhausted", dedupe=True)
        utils._log_provider_notification("gemini", "gemini msg", reason="daily_cap_exhausted", dedupe=True)
        rows = _notification_rows(self.db_path)
        self.assertEqual(len(rows), 2)

    def test_dedupe_false_writes_every_time(self):
        utils._log_provider_notification("groq", "one", reason="rate_limited_cascade")
        utils._log_provider_notification("groq", "two", reason="rate_limited_cascade")
        rows = _notification_rows(self.db_path)
        self.assertEqual(len(rows), 2)


class TestCheckRateLimitsNotifies(unittest.TestCase):
    def setUp(self):
        self.db_path = _make_activity_log_db()
        self._patch = mock.patch.object(utils, "DB_PATH", self.db_path)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        os.remove(self.db_path)

    def _seed_daily_calls(self, provider: str, count: int):
        conn = sqlite3.connect(self.db_path)
        conn.executemany(
            "INSERT INTO activity_log (level, source, message) VALUES ('INFO', 'LLM_Call', ?)",
            [(f"[{provider}] API request initiated",)] * count,
        )
        conn.commit()
        conn.close()

    def test_daily_cap_trip_returns_false_and_notifies_once(self):
        self._seed_daily_calls("groq", 14000)  # daily_warn threshold from _RATE_LIMIT_THRESHOLDS
        self.assertFalse(utils.check_rate_limits("groq"))
        self.assertFalse(utils.check_rate_limits("groq"))  # tripped again on a later call
        rows = [r for r in _notification_rows(self.db_path) if r["meta"]["reason"] == "daily_cap_exhausted"]
        self.assertEqual(len(rows), 1, "the daily-cap notification must not repeat on every subsequent call")

    def test_under_threshold_returns_true_and_does_not_notify(self):
        self._seed_daily_calls("groq", 5)
        self.assertTrue(utils.check_rate_limits("groq"))
        rows = _notification_rows(self.db_path)
        self.assertEqual(rows, [])


def _mock_response(status_code: int, headers: dict | None = None, json_body: dict | None = None):
    resp = mock.Mock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.text = "error body"
    if json_body is not None:
        resp.json.return_value = json_body
    return resp


class TestProviderCascadeDecision(unittest.TestCase):
    """A long Retry-After means cascade now (no sleep, notify); a short one means retry the same
    provider (sleep, no notify) -- the same distinction _call_groq made before CR-106, now shared
    by _call_claude and _call_perplexity too."""

    def setUp(self):
        self.db_path = _make_activity_log_db()
        self._db_patch = mock.patch.object(utils, "DB_PATH", self.db_path)
        self._db_patch.start()
        self._sleep_patch = mock.patch("time.sleep")
        self.mock_sleep = self._sleep_patch.start()

    def tearDown(self):
        self._db_patch.stop()
        self._sleep_patch.stop()
        os.remove(self.db_path)

    def test_call_groq_cascades_immediately_on_a_long_retry_after(self):
        with mock.patch("requests.post", return_value=_mock_response(429, {"retry-after": "3600"})):
            result = utils._call_groq({}, "sys", "user", None, 0.2, max_retries=3)
        self.assertIsNone(result)
        self.mock_sleep.assert_not_called()
        rows = [r for r in _notification_rows(self.db_path) if r["meta"]["provider"] == "groq"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["meta"]["reason"], "rate_limited_cascade")

    def test_call_groq_retries_same_provider_on_a_short_retry_after(self):
        responses = [
            _mock_response(429, {"retry-after": "2"}),
            _mock_response(200, json_body={"choices": [{"message": {"content": "ok"}}]}),
        ]
        with mock.patch("requests.post", side_effect=responses):
            result = utils._call_groq({}, "sys", "user", None, 0.2, max_retries=3)
        self.assertEqual(result, "ok")
        self.mock_sleep.assert_called_once_with(2.0)
        self.assertEqual(_notification_rows(self.db_path), [])

    def test_call_claude_cascades_immediately_on_a_long_retry_after(self):
        with mock.patch("requests.post", return_value=_mock_response(429, {"retry-after": "120"})):
            result = utils._call_claude({}, "sys", "user", None, 0.2, max_retries=3)
        self.assertIsNone(result)
        self.mock_sleep.assert_not_called()
        rows = [r for r in _notification_rows(self.db_path) if r["meta"]["provider"] == "claude"]
        self.assertEqual(len(rows), 1)

    def test_call_perplexity_cascades_immediately_on_a_long_retry_after(self):
        with mock.patch("requests.post", return_value=_mock_response(429, {"retry-after": "90"})):
            result = utils._call_perplexity({}, "sys", "user", 0.2, max_retries=3)
        self.assertIsNone(result)
        self.mock_sleep.assert_not_called()
        rows = [r for r in _notification_rows(self.db_path) if r["meta"]["provider"] == "perplexity"]
        self.assertEqual(len(rows), 1)

    def test_call_claude_without_a_retry_after_header_falls_back_to_the_old_exponential_estimate(self):
        # No retry-after header at all -- must not crash, and must still use the pre-CR-106
        # 60s-times-attempt estimate as its wait guess (still long enough to cascade on attempt 1).
        with mock.patch("requests.post", return_value=_mock_response(429, {})):
            result = utils._call_claude({}, "sys", "user", None, 0.2, max_retries=1)
        self.assertIsNone(result)
        self.mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
