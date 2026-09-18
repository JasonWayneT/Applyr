"""Focused tests for CR-117 pilot case manifest validation."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from freeze_cr117_cases import INPUTS, inspect_cases, verify_existing


class FreezeCasesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / "fictional_case"
        self.folder.mkdir()
        self.digest = self.root / "digest.md"
        self.digest.write_text("Private rule text", encoding="utf-8")
        (self.folder / "Original_JD.txt").write_text("Fictional JD", encoding="utf-8")
        (self.folder / "stage0_fit_gate.json").write_text('{"decision":"PASS"}', encoding="utf-8")
        self.packet = {
            "packet_status": "ready", "estimated_tokens": 12,
            "excerpts": {"ACC-1": "Private candidate evidence"},
            "claim_constraints": {"ACC-1": {"employer": "Example"}},
        }
        self._write_packet()
        (self.folder / "authoring_prompt.md").write_text("Private prompt", encoding="utf-8")

    def _write_packet(self) -> None:
        (self.folder / "authoring_packet.json").write_text(json.dumps(self.packet), encoding="utf-8")

    def test_manifest_hashes_inputs_without_copying_private_text(self) -> None:
        result = inspect_cases(self.root, self.digest)
        self.assertEqual("frozen", result["status"])
        self.assertEqual("pilot", result["cases"][0]["split"])
        self.assertEqual(set(INPUTS), set(result["cases"][0]["hashes"]))
        self.assertNotIn("Private", json.dumps(result))

    def test_rejects_missing_constraints(self) -> None:
        self.packet["claim_constraints"] = {}
        self._write_packet()
        with self.assertRaisesRegex(ValueError, "claim constraints"):
            inspect_cases(self.root, self.digest)

    def test_rejects_incomplete_case(self) -> None:
        (self.folder / "authoring_prompt.md").unlink()
        with self.assertRaisesRegex(ValueError, "missing authoring_prompt.md"):
            inspect_cases(self.root, self.digest)

    def test_existing_snapshot_rejects_quiet_drift(self) -> None:
        path = self.root / "case_manifest.json"
        original = inspect_cases(self.root, self.digest)
        path.write_text(json.dumps(original), encoding="utf-8")
        self.assertFalse(verify_existing(path, original))
        (self.folder / "Original_JD.txt").write_text("Changed fictional JD", encoding="utf-8")
        changed = inspect_cases(self.root, self.digest)
        with self.assertRaisesRegex(ValueError, "Frozen case inputs changed"):
            verify_existing(path, changed)
        self.assertTrue(verify_existing(path, changed, refresh=True))


if __name__ == "__main__":
    unittest.main()
