#!/usr/bin/env python3
"""Tests for sandboxed Stage 1 repair stream caps.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_run_stage1_repair -v
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_stage1_repair as repair  # noqa: E402


def _event(payload: dict) -> str:
    return json.dumps(payload) + "\n"


class TestRepairStreamCaps(unittest.TestCase):
    def test_event_cap_kills_long_running_stream(self) -> None:
        killed: list[bool] = []

        def lines() -> list[str]:
            rows = [_event({"event": "init", "init": {"tools": ["view_file"]}})]
            for index in range(40):
                rows.append(
                    _event(
                        {
                            "event": "step_update",
                            "step_update": {
                                "step_index": index,
                                "state": "ACTIVE",
                                "step_type": "agent_response",
                                "text_delta": f"chunk-{index}",
                            },
                        }
                    )
                )
            return rows

        result = repair.consume_repair_stream(
            lines(),
            wall_seconds=60,
            max_events=5,
            kill=lambda: killed.append(True),
        )
        self.assertEqual(result["outcome"], "repair_timeout")
        self.assertEqual(result["reason"], "event_count")
        self.assertEqual(result["event_count"], 6)
        self.assertEqual(killed, [True])
        self.assertNotIn("chunk-20", result["text"])

    def test_wall_time_kills_slow_stream(self) -> None:
        clock = {"t": 0.0}
        killed: list[bool] = []

        def now() -> float:
            return clock["t"]

        def lines():
            yield _event({"event": "init"})
            clock["t"] = 0.5
            yield _event(
                {
                    "event": "step_update",
                    "step_update": {
                        "step_index": 1,
                        "state": "ACTIVE",
                        "step_type": "agent_response",
                    },
                }
            )
            clock["t"] = 10.0
            yield _event(
                {
                    "event": "step_update",
                    "step_update": {
                        "step_index": 2,
                        "state": "ACTIVE",
                        "step_type": "agent_response",
                    },
                }
            )

        result = repair.consume_repair_stream(
            lines(),
            wall_seconds=3,
            max_events=100,
            kill=lambda: killed.append(True),
            clock=now,
            started_at=0.0,
        )
        self.assertEqual(result["outcome"], "repair_timeout")
        self.assertEqual(result["reason"], "wall_time")
        self.assertEqual(killed, [True])

    def test_tool_request_is_a_failed_call(self) -> None:
        killed: list[bool] = []
        lines = [
            _event({"event": "init", "init": {"tools": ["view_file"]}}),
            _event(
                {
                    "event": "step_update",
                    "step_update": {
                        "step_index": 2,
                        "state": "ACTIVE",
                        "step_type": "tool",
                        "tool_name": "view_file",
                    },
                }
            ),
        ]
        result = repair.consume_repair_stream(
            lines,
            wall_seconds=60,
            max_events=20,
            kill=lambda: killed.append(True),
        )
        self.assertEqual(result["outcome"], "repair_failed")
        self.assertEqual(result["reason"], "tool_or_permission")
        self.assertEqual(killed, [True])

    def test_permission_denial_is_a_failed_call(self) -> None:
        lines = [
            _event({"event": "init"}),
            _event(
                {
                    "event": "step_update",
                    "step_update": {
                        "step_index": 10,
                        "state": "DONE",
                        "step_type": "tool",
                        "tool_name": "run_command",
                        "tool_info": {
                            "output": "Get-ChildItem: Access to the path "
                            "'C:\\\\Users\\\\Jason\\\\Desktop\\\\Jason' is denied."
                        },
                    },
                }
            ),
        ]
        result = repair.consume_repair_stream(
            lines, wall_seconds=60, max_events=20
        )
        self.assertEqual(result["outcome"], "repair_failed")
        self.assertEqual(result["reason"], "tool_or_permission")

    def test_successful_result_without_tools(self) -> None:
        lines = [
            _event({"event": "init"}),
            _event(
                {
                    "event": "step_update",
                    "step_update": {
                        "step_index": 1,
                        "state": "DONE",
                        "step_type": "agent_response",
                        "text_delta": "```Resume.md\n# Name\n```\n",
                    },
                }
            ),
            _event(
                {
                    "event": "result",
                    "result": {"status": "SUCCESS", "output": "done"},
                }
            ),
        ]
        result = repair.consume_repair_stream(
            lines, wall_seconds=60, max_events=20
        )
        self.assertEqual(result["outcome"], "ok")
        self.assertIn("Resume.md", result["text"])

    def test_command_is_sandboxed_print_with_no_workspace_files(self) -> None:
        with mock.patch.object(repair, "_agy_cmd", return_value="agy"):
            command = repair.build_repair_command("# Stage 1 repair\n", wall_seconds=180)
        self.assertIn("--sandbox", command)
        self.assertIn("--disable-slash-commands", command)
        self.assertIn("--print", command)
        self.assertIn("--new-project", command)
        self.assertIn(repair.SANDBOX_INSTRUCTION, command[-1])
        self.assertNotIn("--add-dir", command)

    def test_records_timeout_on_folder_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "stage1_repair_prompt.md").write_text(
                "# Stage 1 repair\n", encoding="utf-8"
            )

            class FakeProc:
                def __init__(self) -> None:
                    rows = [_event({"event": "init"})]
                    for index in range(30):
                        rows.append(
                            _event(
                                {
                                    "event": "step_update",
                                    "step_update": {
                                        "step_index": index,
                                        "state": "ACTIVE",
                                        "step_type": "agent_response",
                                    },
                                }
                            )
                        )
                    self.stdout = io.StringIO("".join(rows))
                    self.stderr = io.StringIO("")
                    self._killed = False

                def poll(self) -> int | None:
                    return 1 if self._killed else None

                def kill(self) -> None:
                    self._killed = True

                def wait(self, timeout: float | None = None) -> int:
                    return 1

            def spawn(cmd: list[str], cwd: Path) -> FakeProc:
                self.assertTrue(cwd.exists())
                self.assertEqual(list(cwd.iterdir()), [])
                self.assertIn("--sandbox", cmd)
                return FakeProc()

            with mock.patch.object(repair, "_agy_cmd", return_value="agy"):
                result = repair.run_for_folder(
                    folder, max_events=5, wall_seconds=60, spawn=spawn
                )
            self.assertEqual(result["outcome"], "repair_timeout")
            state = json.loads(
                (folder / "stage1_repair_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["last_outcome"], "repair_timeout")
            self.assertEqual(state["last_repair_reason"], "event_count")


if __name__ == "__main__":
    unittest.main()
