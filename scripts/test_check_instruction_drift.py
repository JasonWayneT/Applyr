"""Tests for the CR-111 instruction-authority drift guard."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import check_instruction_drift as drift


class TestInstructionDrift(unittest.TestCase):
    """Exercise clean and deliberately broken instruction layouts."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self._write_clean_layout()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_clean_layout(self) -> None:
        self._write("AGENTS.md", "canonical rules\n")
        self._write("CLAUDE.md", "@AGENTS.md\n")
        self._write("docs/AGENTS.md", "engineering module\n")
        for pointer, canonical in drift.POINTERS.items():
            self._write(pointer.as_posix(), f"Read {canonical.as_posix()}.\n")
            self._write(
                canonical.as_posix(),
                "Canonical copy for this harness.\n",
            )

    def test_clean_layout_passes(self) -> None:
        self.assertEqual(drift.check_drift(self.root), [])

    def test_regrown_pointer_fails(self) -> None:
        pointer = self.root / ".claude/skills/generate-submission/SKILL.md"
        pointer.write_text(
            pointer.read_text(encoding="utf-8") + "\n".join(["extra"] * 20),
            encoding="utf-8",
        )
        findings = drift.check_drift(self.root)
        self.assertTrue(any("exceeds" in finding for finding in findings))

    def test_missing_canonical_fails(self) -> None:
        canonical = self.root / ".codex/skills/generate-submission/SKILL.md"
        canonical.unlink()
        findings = drift.check_drift(self.root)
        self.assertTrue(any("Missing canonical skill" in finding for finding in findings))

    def test_absolute_file_url_fails(self) -> None:
        self._write("docs/AGENTS.md", "See file:///c:/old/Applyr/AGENTS.md\n")
        findings = drift.check_drift(self.root)
        self.assertTrue(any("Absolute file URL" in finding for finding in findings))

    def test_byte_identical_edit_instruction_fails(self) -> None:
        self._write(
            ".claude/agents/engineering-manager.md",
            "CLAUDE.md and AGENTS.md edited byte-identically if either changes.\n",
        )
        findings = drift.check_drift(self.root)
        self.assertTrue(any("Byte-identical" in finding for finding in findings))

    def test_legacy_state_assignment_fails(self) -> None:
        self._write(
            ".claude/agents/workflow.md",
            "status: WAITING_FOR_HUMAN\n",
        )
        findings = drift.check_drift(self.root)
        self.assertTrue(any("WAITING_FOR_HUMAN" in finding for finding in findings))

    def test_hardcoded_active_cr_list_fails(self) -> None:
        self._write(
            ".claude/agents/tech-lead.md",
            "The active work is currently CR-053.\n",
        )
        findings = drift.check_drift(self.root)
        self.assertTrue(any("active-CR" in finding for finding in findings))


if __name__ == "__main__":
    unittest.main()
