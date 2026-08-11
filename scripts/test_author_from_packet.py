#!/usr/bin/env python3
"""
Tests for author_from_packet.py (CR-074 Epic 5, Stories 5.2 + 5.3).
# Implements FR-254

Run with:
    .venv\\Scripts\\python.exe -m unittest scripts.test_author_from_packet -v

No cloud LLM calls. All I/O uses temp directories.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from author_from_packet import (
    _check_packet_ready,
    _load_current_digest_version,
    _load_packet,
    build_authoring_prompt,
)
import contracts  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_DIGEST_VERSION = "testver1234567a"
_DIGEST_CONTENT = (
    "# Authoring Rule Digest — Test\n"
    "<!-- Generated for test -->\n"
    "Use ONLY claim_ids from packet. Never invent facts.\n"
)

_READY_PACKET: dict = {
    "schema_version": "1.0",
    "company": "TestCo",
    "role_title": "Product Manager",
    "slug": "testco",
    "url": None,
    "tier": "Tier 1",
    "reach_out": False,
    "jd_buckets": {
        "required": ["Define product roadmap"],
        "preferred": [],
        "responsibilities": [],
        "culture": [],
    },
    "evidence_map": [
        {
            "jd_item": "Define product roadmap",
            "bucket": "required",
            "claim_ids": ["ACC-105-AGILE"],
            "bridge": None,
        }
    ],
    "excerpts": {
        "ACC-105-AGILE": "Led quarterly PI planning for 200+ stakeholders across 8 scrum teams."
    },
    "soft_gaps": [],
    "hard_constraints": ["Use only claim_ids in excerpts."],
    "hook_fact": None,
    "rule_digest_version": _DIGEST_VERSION,
    "packet_status": "ready",
    "incomplete_reasons": [],
    "estimated_tokens": 500,
    "stage_signal": None,
    "thin_jd": False,
}


def _make_temp_folder_with_packet(packet: dict | None = None, write_packet: bool = True) -> tempfile.TemporaryDirectory:
    """Return a TemporaryDirectory containing an authoring_packet.json."""
    tmpdir = tempfile.TemporaryDirectory()
    if write_packet:
        p = Path(tmpdir.name) / "authoring_packet.json"
        p.write_text(json.dumps(packet or _READY_PACKET, indent=2), encoding="utf-8")
    return tmpdir


def _make_temp_digest(tmpdir_path: Path, content: str = _DIGEST_CONTENT, version: str = _DIGEST_VERSION) -> tuple[Path, Path]:
    """Write a temporary digest + version file; return (digest_path, version_path)."""
    digest_path = tmpdir_path / "authoring_rule_digest.md"
    version_path = tmpdir_path / "authoring_rule_digest.version"
    digest_path.write_text(content, encoding="utf-8")
    version_path.write_text(version, encoding="utf-8")
    return digest_path, version_path


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestLoadPacket(unittest.TestCase):
    """_load_packet raises FileNotFoundError when packet is missing."""

    def test_missing_packet_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            with self.assertRaises(FileNotFoundError) as ctx:
                _load_packet(folder)
            self.assertIn("authoring_packet.json not found", str(ctx.exception))

    def test_present_packet_loads(self):
        with _make_temp_folder_with_packet() as tmpdir:
            folder = Path(tmpdir)
            packet = _load_packet(folder)
            self.assertEqual(packet["company"], "TestCo")


class TestCheckPacketReady(unittest.TestCase):
    """_check_packet_ready raises ValueError for non-ready or version-mismatched packets."""

    def test_incomplete_status_raises(self):
        packet = {**_READY_PACKET, "packet_status": "incomplete", "incomplete_reasons": ["Skip tier"]}
        with self.assertRaises(ValueError) as ctx:
            _check_packet_ready(packet, force=False)
        self.assertIn("Skip tier", str(ctx.exception))

    def test_ready_status_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _, version_path = _make_temp_digest(Path(tmpdir))
            _check_packet_ready(_READY_PACKET, force=False, digest_version_path=version_path)
            # No exception raised → pass

    def test_version_mismatch_raises_without_force(self):
        packet = {**_READY_PACKET, "rule_digest_version": "old_version_aabbcc"}
        with tempfile.TemporaryDirectory() as tmpdir:
            _, version_path = _make_temp_digest(Path(tmpdir))
            with self.assertRaises(ValueError) as ctx:
                _check_packet_ready(packet, force=False, digest_version_path=version_path)
            self.assertIn("mismatch", str(ctx.exception))

    def test_version_mismatch_passes_with_force(self):
        packet = {**_READY_PACKET, "rule_digest_version": "old_version_aabbcc"}
        with tempfile.TemporaryDirectory() as tmpdir:
            _, version_path = _make_temp_digest(Path(tmpdir))
            # Should not raise — writes a warning to stderr but continues
            import io
            import contextlib
            stderr_buf = io.StringIO()
            with contextlib.redirect_stderr(stderr_buf):
                _check_packet_ready(packet, force=True, digest_version_path=version_path)
            self.assertIn("WARNING", stderr_buf.getvalue())

    def test_non_ready_overrides_force(self):
        """force does not bypass packet_status check — only the version check."""
        packet = {**_READY_PACKET, "packet_status": "incomplete", "incomplete_reasons": ["Over budget"]}
        with tempfile.TemporaryDirectory() as tmpdir:
            _, version_path = _make_temp_digest(Path(tmpdir))
            with self.assertRaises(ValueError) as ctx:
                _check_packet_ready(packet, force=True, digest_version_path=version_path)
            self.assertIn("Over budget", str(ctx.exception))


class TestBuildAuthoringPrompt(unittest.TestCase):
    """build_authoring_prompt writes a prompt file for a ready fixture."""

    def _run(self, packet: dict | None = None, force: bool = False) -> tuple[str, dict]:
        """Run build_authoring_prompt with temp digest files."""
        packet = packet or _READY_PACKET
        with tempfile.TemporaryDirectory() as folder_tmp:
            with tempfile.TemporaryDirectory() as digest_tmp:
                folder = Path(folder_tmp)
                digest_dir = Path(digest_tmp)

                # Write packet
                (folder / "authoring_packet.json").write_text(
                    json.dumps(packet, indent=2), encoding="utf-8"
                )

                # Write digest + version
                digest_path, version_path = _make_temp_digest(digest_dir)

                prompt_md, meta = build_authoring_prompt(
                    folder,
                    force=force,
                    digest_path=digest_path,
                    digest_version_path=version_path,
                )
                return prompt_md, meta

    def test_writes_prompt_for_ready_packet(self):
        prompt_md, meta = self._run()
        self.assertIn("## SYSTEM BLOCK", prompt_md)
        self.assertIn("## USER BLOCK", prompt_md)
        self.assertIn("CLOSED-WORLD RULE", prompt_md)
        self.assertIn("TestCo", prompt_md)

    def test_packet_json_embedded_in_user_block(self):
        prompt_md, meta = self._run()
        # The packet JSON should appear in the USER block section
        self.assertIn('"company": "TestCo"', prompt_md)
        self.assertIn('"packet_status": "ready"', prompt_md)

    def test_digest_content_in_system_block(self):
        prompt_md, meta = self._run()
        self.assertIn("Use ONLY claim_ids from packet", prompt_md)

    def test_meta_token_estimates_positive(self):
        _, meta = self._run()
        self.assertGreater(meta["system_tokens"], 0)
        self.assertGreater(meta["user_tokens"], 0)
        self.assertGreater(meta["total_estimated_tokens"], 0)
        self.assertEqual(meta["total_estimated_tokens"], meta["system_tokens"] + meta["user_tokens"])

    def test_meta_company_and_slug(self):
        _, meta = self._run()
        self.assertEqual(meta["company"], "TestCo")
        self.assertEqual(meta["slug"], "testco")

    def test_missing_packet_raises(self):
        with tempfile.TemporaryDirectory() as folder_tmp:
            with tempfile.TemporaryDirectory() as digest_tmp:
                folder = Path(folder_tmp)
                digest_path, version_path = _make_temp_digest(Path(digest_tmp))
                # No packet written
                with self.assertRaises(FileNotFoundError):
                    build_authoring_prompt(
                        folder,
                        digest_path=digest_path,
                        digest_version_path=version_path,
                    )

    def test_incomplete_packet_raises(self):
        packet = {**_READY_PACKET, "packet_status": "incomplete", "incomplete_reasons": ["Tier is Skip"]}
        with self.assertRaises(ValueError) as ctx:
            self._run(packet=packet)
        self.assertIn("Tier is Skip", str(ctx.exception))

    def test_version_mismatch_without_force_raises(self):
        packet = {**_READY_PACKET, "rule_digest_version": "stale_version_000"}
        with self.assertRaises(ValueError) as ctx:
            self._run(packet=packet, force=False)
        self.assertIn("mismatch", str(ctx.exception))

    def test_version_mismatch_with_force_succeeds(self):
        packet = {**_READY_PACKET, "rule_digest_version": "stale_version_000"}
        import io, contextlib
        stderr_buf = io.StringIO()
        with contextlib.redirect_stderr(stderr_buf):
            prompt_md, meta = self._run(packet=packet, force=True)
        self.assertIn("## SYSTEM BLOCK", prompt_md)
        self.assertIn("WARNING", stderr_buf.getvalue())


class TestLoadCurrentDigestVersion(unittest.TestCase):
    """_load_current_digest_version reads from version file or hashes digest."""

    def test_reads_version_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            version_path = Path(tmpdir) / "authoring_rule_digest.version"
            version_path.write_text("abc123digest", encoding="utf-8")
            digest_path = Path(tmpdir) / "authoring_rule_digest.md"
            digest_path.write_text("some content", encoding="utf-8")
            result = _load_current_digest_version(version_path, digest_path)
            self.assertEqual(result, "abc123digest")

    def test_falls_back_to_hash_when_version_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            version_path = Path(tmpdir) / "authoring_rule_digest.version"
            digest_path = Path(tmpdir) / "authoring_rule_digest.md"
            digest_path.write_text("digest content here", encoding="utf-8")
            # No version file
            result = _load_current_digest_version(version_path, digest_path)
            self.assertEqual(len(result), 16)  # sha256[:16]

    def test_returns_empty_when_neither_file_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            version_path = Path(tmpdir) / "authoring_rule_digest.version"
            digest_path = Path(tmpdir) / "authoring_rule_digest.md"
            result = _load_current_digest_version(version_path, digest_path)
            self.assertEqual(result, "")


class TestStage1VerifyOnlyGate(unittest.TestCase):
    """CR-075 Story 4.3: --verify-only calls check_stage1_ready before lint/coverage."""

    def _run_verify_only(self, folder: Path) -> "subprocess.CompletedProcess":
        import subprocess

        return subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent / "author_from_packet.py"),
                str(folder),
                "--verify-only",
            ],
            capture_output=True,
            text=True,
        )

    def test_missing_packet_exits_nonzero_with_itemized_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "Resume.md").write_text("# Name\n", encoding="utf-8")
            (folder / "CoverLetter.md").write_text("# Name\n", encoding="utf-8")
            result = self._run_verify_only(folder)
            self.assertNotEqual(result.returncode, 0)
            combined = (result.stdout + result.stderr).lower()
            self.assertIn("authoring_packet", combined)
            self.assertIn("no --force", combined)

    def test_incomplete_packet_not_bypassed_by_force_flag(self):
        """AC3 / OQ-1: --force on --verify-only must NOT bypass packet_status."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            packet = {
                **_READY_PACKET,
                "packet_status": "incomplete",
                "incomplete_reasons": ["unmapped required: Foo"],
            }
            (folder / "authoring_packet.json").write_text(
                json.dumps(packet), encoding="utf-8"
            )
            (folder / "Resume.md").write_text("# Name\n", encoding="utf-8")
            (folder / "CoverLetter.md").write_text("# Name\n", encoding="utf-8")
            import subprocess

            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).parent / "author_from_packet.py"),
                    str(folder),
                    "--verify-only",
                    "--force",
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            combined = (result.stdout + result.stderr).lower()
            self.assertIn("packet_status", combined)

    def test_check_stage1_ready_direct_for_missing_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "authoring_packet.json").write_text(
                json.dumps(_READY_PACKET), encoding="utf-8"
            )
            (folder / "CoverLetter.md").write_text("# Name\n", encoding="utf-8")
            ok, errors = contracts.check_stage1_ready(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("Resume.md" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
