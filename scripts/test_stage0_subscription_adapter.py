"""CR-114 Story 2: Stage 0 subscription adapter. No live harness calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stage0_subscription_adapter as adapter


def _items() -> list[adapter.Stage0Item]:
    return [
        adapter.Stage0Item("e0", "5+ years of B2B SaaS product management"),
        adapter.Stage0Item("e1", "Experience with Jira and SQL"),
    ]


def _ok_extract(stdout: str | None = None) -> subprocess.CompletedProcess[str]:
    body = stdout or json.dumps({
        "results": [
            {"item_id": "e0", "bucket": "required"},
            {"item_id": "e1", "bucket": "preferred"},
        ]
    })
    return subprocess.CompletedProcess(["npx"], 0, body, "")


def _ok_evidence() -> subprocess.CompletedProcess[str]:
    body = json.dumps({
        "results": [{
            "item_id": "e0",
            "gate": "NONE",
            "gap_source": "",
            "evidence_level": 3,
            "confidence": "high",
            "reasoning": "Exact Jira match in reviewed evidence.",
        }]
    })
    return subprocess.CompletedProcess(["npx"], 0, body, "")


class Stage0SubscriptionAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.pop(adapter.ENABLED_ENV, None)
        self._npx = patch.object(adapter, "_npx_cmd", return_value="npx.cmd")
        self._npx.start()
        self.addCleanup(self._npx.stop)

    def tearDown(self) -> None:
        if self._env is None:
            os.environ.pop(adapter.ENABLED_ENV, None)
        else:
            os.environ[adapter.ENABLED_ENV] = self._env

    def _config(self, **kwargs) -> adapter.AdapterConfig:
        tmp = Path(tempfile.mkdtemp())
        defaults = {
            "enabled": True,
            "cache_dir": tmp / "cache",
            "workspace": tmp,
            "timeout_seconds": 5,
            "max_calls": 4,
            "max_wall_seconds": 30,
        }
        defaults.update(kwargs)
        return adapter.AdapterConfig(**defaults)

    def test_disabled_by_default(self) -> None:
        result = adapter.run_stage0_subscription("extraction", _items())
        self.assertEqual(result.outcome, "disabled")
        self.assertEqual(result.missing_item_ids, ["e0", "e1"])
        self.assertIsNone(result.api_cents)

    def test_env_enables_adapter(self) -> None:
        os.environ[adapter.ENABLED_ENV] = "1"
        calls: list[list[str]] = []

        def runner(command, **_kwargs):
            calls.append(command)
            return _ok_extract()

        result = adapter.run_stage0_subscription(
            "extraction", _items(), config=self._config(enabled=False), runner=runner
        )
        self.assertEqual(result.outcome, "ok")
        self.assertEqual(len(calls), 1)

    def test_extraction_ok_uses_item_ids_not_indexes(self) -> None:
        captured: dict = {}

        def runner(command, **kwargs):
            captured["command"] = command
            captured["kwargs"] = kwargs
            return _ok_extract()

        result = adapter.run_stage0_subscription(
            "extraction", _items(), config=self._config(), runner=runner
        )
        self.assertEqual(result.outcome, "ok")
        self.assertEqual([row["item_id"] for row in result.results], ["e0", "e1"])
        self.assertFalse(result.missing_item_ids)
        self.assertIn("claudexor@3.12.1", captured["command"])
        self.assertIn("--access", captured["command"])
        self.assertIn("readonly", captured["command"])
        self.assertIn("--no-review", captured["command"])
        self.assertIn("--json", captured["command"])
        self.assertIn("--web", captured["command"])
        self.assertIn("off", captured["command"])
        self.assertIn("--output-schema", captured["command"])
        self.assertIs(captured["kwargs"]["shell"], False)
        self.assertGreaterEqual(result.subscription_minutes, 0.0)
        self.assertIsNone(result.api_cents)
        self.assertNotIn("groq", " ".join(captured["command"]).lower())
        self.assertNotIn("gemini", " ".join(captured["command"]).lower())
        telemetry = result.to_telemetry()
        self.assertIn("subscription_minutes", telemetry)
        self.assertIsNone(telemetry["api_cents"])

    def test_evidence_schema_is_distinct(self) -> None:
        extract = adapter.schema_for("extraction")
        evidence = adapter.schema_for("evidence")
        self.assertNotEqual(extract, evidence)
        self.assertIn("bucket", json.dumps(extract))
        self.assertIn("gate", json.dumps(evidence))
        result = adapter.run_stage0_subscription(
            "evidence",
            [adapter.Stage0Item("e0", "Experience with Jira")],
            config=self._config(),
            runner=lambda *a, **k: _ok_evidence(),
        )
        self.assertEqual(result.outcome, "ok")
        self.assertEqual(result.results[0]["gate"], "NONE")

    def test_malformed_json_goes_to_review(self) -> None:
        result = adapter.run_stage0_subscription(
            "extraction",
            _items(),
            config=self._config(),
            runner=lambda *a, **k: subprocess.CompletedProcess(["npx"], 0, "not json", ""),
        )
        self.assertEqual(result.outcome, "review")
        self.assertEqual(result.missing_item_ids, ["e0", "e1"])
        self.assertIn("invalid harness output", result.reason or "")

    def test_timeout_goes_to_review(self) -> None:
        def runner(*_a, **_k):
            raise subprocess.TimeoutExpired(cmd=["npx"], timeout=1)

        result = adapter.run_stage0_subscription(
            "extraction", _items(), config=self._config(), runner=runner
        )
        self.assertEqual(result.outcome, "review")
        self.assertEqual(result.reason, "harness timed out")
        self.assertEqual(result.missing_item_ids, ["e0", "e1"])

    def test_partial_mapping_preserves_missing_ids(self) -> None:
        body = json.dumps({"results": [{"item_id": "e0", "bucket": "required"}]})
        result = adapter.run_stage0_subscription(
            "extraction",
            _items(),
            config=self._config(),
            runner=lambda *a, **k: subprocess.CompletedProcess(["npx"], 0, body, ""),
        )
        self.assertEqual(result.outcome, "review")
        self.assertEqual(result.missing_item_ids, ["e1"])
        self.assertEqual(result.results[0]["item_id"], "e0")

    def test_cache_hit_does_not_spawn_again(self) -> None:
        calls = {"n": 0}

        def runner(*_a, **_k):
            calls["n"] += 1
            return _ok_extract()

        cfg = self._config()
        first = adapter.run_stage0_subscription("extraction", _items(), config=cfg, runner=runner)
        second = adapter.run_stage0_subscription("extraction", _items(), config=cfg, runner=runner)
        self.assertEqual(first.outcome, "ok")
        self.assertEqual(second.outcome, "cache_hit")
        self.assertEqual(calls["n"], 1)
        self.assertEqual(first.cache_key, second.cache_key)
        self.assertEqual(second.calls, 0)

    def test_call_ceiling_exhausted(self) -> None:
        cfg = self._config(max_calls=1)
        budget = adapter.AdapterBudget(cfg)
        budget.calls = 1
        result = adapter.run_stage0_subscription(
            "extraction", _items(), config=cfg, budget=budget, runner=lambda *a, **k: _ok_extract()
        )
        self.assertEqual(result.outcome, "exhausted")
        self.assertEqual(result.missing_item_ids, ["e0", "e1"])

    def test_extraction_and_evidence_cache_keys_differ(self) -> None:
        items = [adapter.Stage0Item("e0", "Experience with Jira")]
        extract_key = adapter.cache_key("extraction", items, profile="cursor-default")
        evidence_key = adapter.cache_key("evidence", items, profile="cursor-default")
        other_profile = adapter.cache_key("extraction", items, profile="claude-default")
        self.assertNotEqual(extract_key, evidence_key)
        self.assertNotEqual(extract_key, other_profile)

    def test_prompt_redacts_pii(self) -> None:
        items = [adapter.Stage0Item("e0", "Email jane@example.com or call (415) 555-0100")]
        prompt = adapter._prompt("extraction", items)
        self.assertIn("[REDACTED_EMAIL]", prompt)
        self.assertIn("[REDACTED_PHONE]", prompt)
        self.assertNotIn("jane@example.com", prompt)
        self.assertNotIn("415", prompt)

    def test_unknown_item_ids_are_ignored(self) -> None:
        body = json.dumps({
            "results": [
                {"item_id": "e0", "bucket": "required"},
                {"item_id": "e1", "bucket": "preferred"},
                {"item_id": "invented", "bucket": "required"},
            ]
        })
        result = adapter.run_stage0_subscription(
            "extraction",
            _items(),
            config=self._config(),
            runner=lambda *a, **k: subprocess.CompletedProcess(["npx"], 0, body, ""),
        )
        self.assertEqual(result.outcome, "ok")
        self.assertEqual([row["item_id"] for row in result.results], ["e0", "e1"])

    def test_invalid_bucket_goes_to_review(self) -> None:
        body = json.dumps({"results": [{"item_id": "e0", "bucket": "skip"}]})
        result = adapter.run_stage0_subscription(
            "extraction",
            [adapter.Stage0Item("e0", "Must have SQL")],
            config=self._config(),
            runner=lambda *a, **k: subprocess.CompletedProcess(["npx"], 0, body, ""),
        )
        self.assertEqual(result.outcome, "review")
        self.assertIn("invalid bucket", result.reason or "")

    def test_groq_profile_never_spawns(self) -> None:
        spawned = {"n": 0}

        def runner(*_a, **_k):
            spawned["n"] += 1
            return _ok_extract()

        result = adapter.run_stage0_subscription(
            "extraction",
            _items(),
            config=self._config(profile="groq"),
            runner=runner,
        )
        self.assertEqual(result.outcome, "review")
        self.assertIn("forbidden", result.reason or "")
        self.assertEqual(spawned["n"], 0)

    def test_npx_missing_goes_to_review(self) -> None:
        with patch.object(adapter, "_npx_cmd", side_effect=FileNotFoundError("npx is not available")):
            result = adapter.run_stage0_subscription(
                "extraction", _items(), config=self._config(), runner=lambda *a, **k: _ok_extract()
            )
        self.assertEqual(result.outcome, "review")
        self.assertIn("harness unavailable", result.reason or "")

    def test_nonzero_exit_goes_to_review(self) -> None:
        result = adapter.run_stage0_subscription(
            "extraction",
            _items(),
            config=self._config(),
            runner=lambda *a, **k: subprocess.CompletedProcess(["npx"], 1, "", "boom"),
        )
        self.assertEqual(result.outcome, "review")
        self.assertEqual(result.missing_item_ids, ["e0", "e1"])

    def test_wrapped_answer_json_is_accepted(self) -> None:
        wrapped = json.dumps({
            "ok": True,
            "answer": {"results": [{"item_id": "e0", "bucket": "required"}, {"item_id": "e1", "bucket": "culture"}]},
        })
        result = adapter.run_stage0_subscription(
            "extraction",
            _items(),
            config=self._config(),
            runner=lambda *a, **k: subprocess.CompletedProcess(["npx"], 0, wrapped, ""),
        )
        self.assertEqual(result.outcome, "ok")
        self.assertEqual(result.results[1]["bucket"], "culture")

    def test_inspect_primary_output_is_accepted(self) -> None:
        envelope = {
            "primaryOutput": {
                "text": json.dumps({
                    "results": [
                        {"item_id": "e0", "bucket": "required"},
                        {"item_id": "e1", "bucket": "preferred"},
                    ]
                })
            },
            "contract": {"access": {"effective_profile": "readonly"}},
            "telemetry": {"attempts": [{"harness_id": "cursor"}]},
        }
        result = adapter.run_stage0_subscription(
            "extraction",
            _items(),
            config=self._config(),
            runner=lambda *a, **k: subprocess.CompletedProcess(["npx"], 0, json.dumps(envelope), ""),
        )
        self.assertEqual(result.outcome, "ok")

    def test_harness_substitution_goes_to_review(self) -> None:
        envelope = {
            "primaryOutput": {
                "text": json.dumps({
                    "results": [
                        {"item_id": "e0", "bucket": "required"},
                        {"item_id": "e1", "bucket": "preferred"},
                    ]
                })
            },
            "contract": {"access": {"effective_profile": "readonly"}},
            "telemetry": {"attempts": [{"harness_id": "codex"}]},
        }
        result = adapter.run_stage0_subscription(
            "extraction",
            _items(),
            config=self._config(),
            runner=lambda *a, **k: subprocess.CompletedProcess(["npx"], 0, json.dumps(envelope), ""),
        )
        self.assertEqual(result.outcome, "review")
        self.assertIn("substituted", result.reason or "")
        self.assertEqual(result.missing_item_ids, ["e0", "e1"])

    def test_non_readonly_access_goes_to_review(self) -> None:
        envelope = {
            "results": [
                {"item_id": "e0", "bucket": "required"},
                {"item_id": "e1", "bucket": "preferred"},
            ],
            "contract": {"access": {"effective_profile": "workspace_write"}},
            "telemetry": {"attempts": [{"harness_id": "cursor"}]},
        }
        result = adapter.run_stage0_subscription(
            "extraction",
            _items(),
            config=self._config(),
            runner=lambda *a, **k: subprocess.CompletedProcess(["npx"], 0, json.dumps(envelope), ""),
        )
        self.assertEqual(result.outcome, "review")
        self.assertIn("workspace_write", result.reason or "")

    def test_spawn_cwd_is_not_repo_root_by_default(self) -> None:
        captured: dict = {}

        def runner(command, **kwargs):
            captured["cwd"] = kwargs.get("cwd")
            return _ok_extract()

        result = adapter.run_stage0_subscription(
            "extraction",
            _items(),
            config=adapter.AdapterConfig(
                enabled=True,
                cache_dir=Path(tempfile.mkdtemp()) / "cache",
            ),
            runner=runner,
        )
        self.assertEqual(result.outcome, "ok")
        cwd = Path(captured["cwd"]).resolve()
        self.assertNotEqual(cwd, Path(".").resolve())
        self.assertFalse((cwd / "scripts" / "stage0_subscription_adapter.py").exists())


if __name__ == "__main__":
    unittest.main()
