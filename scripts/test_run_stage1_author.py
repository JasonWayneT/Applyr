#!/usr/bin/env python3
"""Tests for the sandboxed Stage 1 fresh-author Agy call (run_stage1_author.py).

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_run_stage1_author -v
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

import run_stage1_author as author  # noqa: E402


def _event(payload: dict) -> str:
    return json.dumps(payload) + "\n"


class _RecordingStdin:
    """Records what was written even after close(), unlike a real StringIO."""

    def __init__(self) -> None:
        self.written = ""

    def write(self, text: str) -> None:
        self.written += text

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class FakeProc:
    """Mimics a subprocess.Popen with a real init handshake, like the agy CLI."""

    def __init__(self, post_init_events: list[str]) -> None:
        self.stdout = io.StringIO(_event({"event": "init"}) + "".join(post_init_events))
        self.stdin = _RecordingStdin()
        self.stderr = io.StringIO("")
        self._killed = False

    def poll(self) -> int | None:
        return 1 if self._killed else None

    def kill(self) -> None:
        self._killed = True

    def wait(self, timeout: float | None = None) -> int:
        return 1


class TestRunAuthorProcess(unittest.TestCase):
    def _spawn_factory(self, post_init_events: list[str]):
        proc = FakeProc(post_init_events)

        def spawn(cmd: list[str], cwd: Path) -> FakeProc:
            self.assertIn("--sandbox", cmd)
            self.assertIn("--input-format", cmd)
            self.assertIn("stream-json", cmd)
            return proc

        return spawn, proc

    def test_successful_call_sends_prompt_on_stdin_and_returns_text(self) -> None:
        rows = [_event({"event": "result", "result": {"status": "SUCCESS", "output": "hello"}})]
        spawn, proc = self._spawn_factory(rows)
        with mock.patch.object(author, "_agy_cmd", return_value="agy"):
            result = author.run_author_process("PROMPT BODY", wall_seconds=30, spawn=spawn)
        self.assertEqual(result["outcome"], "ok")
        self.assertIn("hello", result["text"])
        sent = json.loads(proc.stdin.written.strip())
        self.assertEqual(sent["event"], "user")
        self.assertIn(author.SANDBOX_INSTRUCTION, sent["message"]["content"])
        self.assertIn("PROMPT BODY", sent["message"]["content"])

    def test_missing_init_event_is_author_failed(self) -> None:
        proc = FakeProc([])
        proc.stdout = io.StringIO(_event({"event": "not_init"}))

        def spawn(cmd: list[str], cwd: Path) -> FakeProc:
            return proc

        with mock.patch.object(author, "_agy_cmd", return_value="agy"):
            result = author.run_author_process("PROMPT", wall_seconds=30, spawn=spawn)
        self.assertEqual(result["outcome"], "author_failed")
        self.assertEqual(result["reason"], "missing_init_event")

    def test_tool_request_is_author_failed(self) -> None:
        rows = [
            _event(
                {
                    "event": "step_update",
                    "step_update": {"step_type": "tool_use", "tool_name": "view_file"},
                }
            )
        ]
        spawn, _ = self._spawn_factory(rows)
        with mock.patch.object(author, "_agy_cmd", return_value="agy"):
            result = author.run_author_process("PROMPT", wall_seconds=30, spawn=spawn)
        self.assertEqual(result["outcome"], "author_failed")


class TestRunForFolder(unittest.TestCase):
    def test_missing_prompt_file_is_author_failed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            result = author.run_for_folder(folder, spawn=lambda cmd, cwd: None)
        self.assertEqual(result["outcome"], "author_failed")
        self.assertEqual(result["reason"], "missing_prompt")
        self.assertFalse(result["wrote_files"])

    def test_complete_three_block_response_writes_all_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "authoring_prompt.md").write_text("# prompt\n", encoding="utf-8")
            text = (
                "```Resume.md\n# Name\n## PROFESSIONAL SUMMARY\nBody.\n```\n"
                "```CoverLetter.md\nDear Hiring Manager,\nLetter body.\n```\n"
                "```claim_provenance.json\n"
                '{"company": "Acme", "resume_claims": [{"bullet": "x", "claim_ids": ["ACC-101"]}]}\n'
                "```\n"
            )
            rows = [_event({"event": "result", "result": {"status": "SUCCESS", "output": text}})]

            def spawn(cmd: list[str], cwd: Path) -> FakeProc:
                return FakeProc(rows)

            with mock.patch.object(author, "_agy_cmd", return_value="agy"):
                result = author.run_for_folder(folder, wall_seconds=30, spawn=spawn)
            self.assertEqual(result["outcome"], "ok")
            self.assertTrue(result["wrote_files"])
            self.assertIn("Body.", (folder / "Resume.md").read_text(encoding="utf-8"))
            self.assertIn("Letter body.", (folder / "CoverLetter.md").read_text(encoding="utf-8"))
            provenance = json.loads((folder / "claim_provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(provenance["company"], "Acme")
            attempts = list((folder / "stage1_author_attempts").glob("*.txt"))
            self.assertEqual(len(attempts), 1)

    def test_missing_provenance_block_is_incomplete_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "authoring_prompt.md").write_text("# prompt\n", encoding="utf-8")
            text = (
                "```Resume.md\n# Name\n## PROFESSIONAL SUMMARY\nBody.\n```\n"
                "```CoverLetter.md\nDear Hiring Manager,\nLetter body.\n```\n"
            )
            rows = [_event({"event": "result", "result": {"status": "SUCCESS", "output": text}})]

            def spawn(cmd: list[str], cwd: Path) -> FakeProc:
                return FakeProc(rows)

            with mock.patch.object(author, "_agy_cmd", return_value="agy"):
                result = author.run_for_folder(folder, wall_seconds=30, spawn=spawn)
            self.assertEqual(result["outcome"], "author_failed")
            self.assertEqual(result["reason"], "invalid_or_incomplete_artifacts")
            self.assertFalse(result["wrote_files"])
            self.assertFalse((folder / "Resume.md").exists())

    def test_crlf_language_fences_are_classified_and_written(self) -> None:
        """Live miss 2026-09-22 sourcegraph: ```markdown\\r / ```json\\r (FR-344)."""
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "authoring_prompt.md").write_text("# prompt\n", encoding="utf-8")
            text = (
                "```markdown\r\n"
                "## PROFESSIONAL SUMMARY\r\n"
                "Product manager body.\r\n"
                "```\r\n"
                "```markdown\r\n"
                "Sourcegraph solves a hard engineering problem in code search.\r\n"
                "```\r\n"
                "```json\r\n"
                '{"company": "Sourcegraph", "resume_claims": '
                '[{"bullet": "x", "claim_ids": ["ACC-101"]}]}\r\n'
                "```\r\n"
            )
            rows = [_event({"event": "result", "result": {"status": "SUCCESS", "output": text}})]

            def spawn(cmd: list[str], cwd: Path) -> FakeProc:
                return FakeProc(rows)

            with mock.patch.object(author, "_agy_cmd", return_value="agy"):
                result = author.run_for_folder(folder, wall_seconds=30, spawn=spawn)
            self.assertEqual(result["outcome"], "ok")
            self.assertTrue(result["wrote_files"])
            self.assertIn("PROFESSIONAL SUMMARY", (folder / "Resume.md").read_text(encoding="utf-8"))
            self.assertIn("Sourcegraph solves", (folder / "CoverLetter.md").read_text(encoding="utf-8"))
            provenance = json.loads((folder / "claim_provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(provenance["company"], "Sourcegraph")


if __name__ == "__main__":
    unittest.main()
