#!/usr/bin/env python3
"""CR-112 Story 6.1/6.2 eval harness tests."""
from __future__ import annotations

import builtins
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_cr112_eval import (  # noqa: E402
    _DEFAULT_OUT,
    _FIXTURES,
    _sqlite_is_production,
    build_parser,
    materialize_eval_set,
    run_eval,
)

EXPECTED_SLUGS = {
    "jd_01_northwind_platform",
    "jd_02_contoso_data",
    "jd_03_fabrikam_compliance",
    "jd_04_adventure_ops",
    "jd_05_wideworld_admin",
}


class ImportGuard:
    """Fail the test if a forbidden import is attempted."""

    def __init__(self, *blocked: str) -> None:
        self._blocked = set(blocked)
        self._real_import = builtins.__import__

    def __call__(self, name: str, *args: object, **kwargs: object) -> object:
        root = name.split(".", 1)[0]
        if root in self._blocked:
            raise AssertionError(f"forbidden import attempted: {name}")
        return self._real_import(name, *args, **kwargs)


class TestCr112Story61(unittest.TestCase):
    """Acceptance tests for the sanitized CR-112 eval harness."""

    def test_fixture_source_has_five_fictional_slug_directories(self) -> None:
        folders = sorted(path.name for path in _FIXTURES.iterdir() if path.is_dir())
        self.assertEqual(set(folders), EXPECTED_SLUGS)
        self.assertEqual(len(folders), 5)

    def test_materialize_eval_set_copies_only_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "eval"
            folders = materialize_eval_set(dest)
            self.assertEqual({folder.name for folder in folders}, EXPECTED_SLUGS)
            for folder in folders:
                names = sorted(path.name for path in folder.iterdir())
                self.assertEqual(names, ["Original_JD.txt", "stage0_fit_gate.json"])

    def test_materialized_jds_are_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "eval"
            folders = materialize_eval_set(dest)
            for folder in folders:
                text = (folder / "Original_JD.txt").read_text(encoding="utf-8").lower()
                self.assertNotIn("jason", text)
                self.assertNotIn("@", text)
                self.assertTrue((folder / "stage0_fit_gate.json").is_file())

    def test_sqlite_guard_flags_production_basename_and_refuses_run(self) -> None:
        self.assertTrue(_sqlite_is_production(Path("jobagent.sqlite")))
        self.assertTrue(_sqlite_is_production(Path("C:/tmp/jobagent.sqlite")))
        self.assertFalse(_sqlite_is_production(Path("eval_redirect.sqlite")))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                run_eval(
                    Path(tmp) / "eval",
                    paid_llm=False,
                    assemble_packets=False,
                    sqlite_path=Path("jobagent.sqlite"),
                )

    def test_parser_defaults_to_sanitized_default_out_and_assemble_off(self) -> None:
        args = build_parser().parse_args([])
        self.assertEqual(args.out, _DEFAULT_OUT)
        self.assertFalse(args.paid_llm)
        self.assertFalse(args.assemble_packets)

    def test_default_eval_never_imports_build_authoring_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            guard = ImportGuard("build_authoring_packet")
            with mock.patch("builtins.__import__", side_effect=guard):
                summary = run_eval(
                    Path(tmp) / "eval",
                    paid_llm=False,
                    assemble_packets=False,
                    sqlite_path=None,
                )
            self.assertEqual(summary["paid_calls"], 0)
            self.assertEqual(summary["totals"]["harness_spawn_count"], 0)

    def test_main_paid_flag_without_budget_returns_exit_2(self) -> None:
        from run_cr112_eval import main

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {}, clear=False):
                code = main(["--paid-llm", "--out", str(Path(tmp) / "eval")])
        self.assertEqual(code, 2)

    def test_paid_flag_with_budget_still_never_imports_or_calls_call_llm(self) -> None:
        from run_cr112_eval import main

        with tempfile.TemporaryDirectory() as tmp:
            guard = ImportGuard("call_llm")
            with mock.patch("builtins.__import__", side_effect=guard):
                with mock.patch.dict(
                    os.environ,
                    {"APPLYR_CR112_PAID_BUDGET": "25"},
                    clear=False,
                ):
                    code = main(["--paid-llm", "--out", str(Path(tmp) / "eval")])
            self.assertEqual(code, 0)
            summary = json.loads((Path(tmp) / "eval" / "metrics.json").read_text(encoding="utf-8"))
        self.assertTrue(summary["paid_llm"])
        self.assertEqual(summary["paid_calls"], 0)
        self.assertEqual(summary["totals"]["call_llm_invocations"], 0)

    def test_run_eval_keeps_token_and_cost_columns_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "eval"
            summary = run_eval(
                dest,
                paid_llm=False,
                assemble_packets=False,
                sqlite_path=None,
            )
            totals = summary["totals"]
            self.assertEqual(totals["call_llm_invocations"], 0)
            self.assertEqual(totals["harness_spawn_count"], 0)
            self.assertEqual(totals["api_cents"], 0)
            self.assertEqual(totals["subscription_minutes"], 0)
            self.assertIn("prompt_meta_estimated_tokens", totals)
            self.assertEqual(summary["cost_rule"], "Never add subscription_minutes to api_cents.")
            self.assertEqual(summary["token_method"], "bytes_div_4_estimate")
            self.assertEqual(
                totals["prompt_meta_estimated_tokens"],
                sum(int(row["prompt_meta_estimated_tokens"]) for row in summary["folders"]),
            )

    def test_each_folder_writes_complete_observability_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "eval"
            summary = run_eval(
                dest,
                paid_llm=False,
                assemble_packets=False,
                sqlite_path=None,
            )
            for row in summary["folders"]:
                events_path = dest / row["slug"] / "observability" / "run_events.jsonl"
                self.assertTrue(events_path.is_file(), row["slug"])
                events = [
                    json.loads(line)
                    for line in events_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                self.assertEqual([event["event"] for event in events], ["start", "complete"])
                self.assertTrue(all(event["stage"] == "eval" for event in events))

    def test_metrics_json_is_written_to_requested_temp_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "eval"
            summary = run_eval(
                dest,
                paid_llm=False,
                assemble_packets=False,
                sqlite_path=None,
            )
            metrics_path = dest / "metrics.json"
            self.assertTrue(metrics_path.is_file())
            persisted = json.loads(metrics_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["totals"], summary["totals"])
            self.assertEqual({row["slug"] for row in persisted["folders"]}, EXPECTED_SLUGS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
