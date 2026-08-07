#!/usr/bin/env python3
"""
Tests for generate_authoring_rule_digest.py (CR-074 Epic 4.2–4.3).
# Implements FR-254, NFR-007

Run with:
    .venv\\Scripts\\python.exe -m unittest scripts.test_generate_authoring_rule_digest -v

No cloud calls; no PII files read; all file I/O uses tempdir.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_authoring_rule_digest import (
    _DIGEST_CONTENT,
    _HARD_CHAR_LIMIT,
    _version_from_content,
    generate_digest,
    write_digest,
)


class TestGenerateDigest(unittest.TestCase):
    """Unit tests for generate_digest() — no file I/O."""

    def test_returns_tuple_of_two_strings(self) -> None:
        """generate_digest() must return (str, str)."""
        content, version = generate_digest()
        self.assertIsInstance(content, str)
        self.assertIsInstance(version, str)

    def test_content_is_non_empty(self) -> None:
        """Digest content must not be empty."""
        content, _ = generate_digest()
        self.assertGreater(len(content), 100)

    def test_content_under_hard_limit(self) -> None:
        """Digest content must not exceed _HARD_CHAR_LIMIT chars."""
        content, _ = generate_digest()
        self.assertLessEqual(
            len(content),
            _HARD_CHAR_LIMIT,
            f"Digest is {len(content)} chars — over hard cap of {_HARD_CHAR_LIMIT}.",
        )

    def test_version_is_16_hex_chars(self) -> None:
        """Version string must be exactly 16 lowercase hex characters."""
        _, version = generate_digest()
        self.assertEqual(len(version), 16)
        self.assertRegex(version, r"^[0-9a-f]{16}$")

    def test_version_stable_on_identical_content(self) -> None:
        """Same content always produces the same version."""
        _, v1 = generate_digest()
        _, v2 = generate_digest()
        self.assertEqual(v1, v2)

    def test_version_changes_on_different_content(self) -> None:
        """Different content must produce a different version."""
        v1 = _version_from_content("hello world")
        v2 = _version_from_content("hello world!")
        self.assertNotEqual(v1, v2)

    def test_version_matches_sha256(self) -> None:
        """_version_from_content must equal sha256(content)[:16]."""
        sample = "some authoring rule text"
        expected = hashlib.sha256(sample.encode("utf-8")).hexdigest()[:16]
        self.assertEqual(_version_from_content(sample), expected)

    def test_raises_on_oversized_content(self) -> None:
        """generate_digest() must raise ValueError when content exceeds hard limit."""
        oversized = "x" * (_HARD_CHAR_LIMIT + 1)
        with patch("generate_authoring_rule_digest._DIGEST_CONTENT", oversized):
            with self.assertRaises(ValueError) as ctx:
                generate_digest()
            self.assertIn("hard limit", str(ctx.exception))

    def test_content_contains_required_sections(self) -> None:
        """Digest must include the key sections callers depend on."""
        content, _ = generate_digest()
        for section in [
            "Closed-World Rule",
            "Resume Structure",
            "Cover Letter Structure",
            "Forbidden Formatting",
            "Forbidden Words",
            "Exclusion Zones",
            "Attribution Tiers",
        ]:
            self.assertIn(section, content, f"Missing section: {section}")

    def test_no_pii_patterns(self) -> None:
        """Digest must not contain email addresses or phone-number patterns."""
        import re
        content, _ = generate_digest()
        # Email pattern
        self.assertIsNone(
            re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", content),
            "Digest contains an email address — PII leak.",
        )
        # North American phone pattern
        self.assertIsNone(
            re.search(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b", content),
            "Digest contains a phone number — PII leak.",
        )


class TestWriteDigest(unittest.TestCase):
    """Integration tests — write_digest() uses temp paths."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_writes_digest_file(self) -> None:
        """write_digest() must create the digest file."""
        dp = self.tmp / "authoring_rule_digest.md"
        vp = self.tmp / "authoring_rule_digest.version"
        write_digest(digest_path=dp, version_path=vp)
        self.assertTrue(dp.exists(), "Digest file not created.")

    def test_writes_version_file(self) -> None:
        """write_digest() must create the version file."""
        dp = self.tmp / "authoring_rule_digest.md"
        vp = self.tmp / "authoring_rule_digest.version"
        write_digest(digest_path=dp, version_path=vp)
        self.assertTrue(vp.exists(), "Version file not created.")

    def test_version_file_matches_digest_hash(self) -> None:
        """Version stored in .version must match sha256[:16] of digest content."""
        dp = self.tmp / "authoring_rule_digest.md"
        vp = self.tmp / "authoring_rule_digest.version"
        write_digest(digest_path=dp, version_path=vp)
        content = dp.read_text(encoding="utf-8")
        stored_version = vp.read_text(encoding="utf-8").strip()
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        self.assertEqual(stored_version, expected)

    def test_digest_file_content_under_size_cap(self) -> None:
        """Written digest must be under _HARD_CHAR_LIMIT chars."""
        dp = self.tmp / "authoring_rule_digest.md"
        vp = self.tmp / "authoring_rule_digest.version"
        write_digest(digest_path=dp, version_path=vp)
        n = len(dp.read_text(encoding="utf-8"))
        self.assertLessEqual(n, _HARD_CHAR_LIMIT)

    def test_idempotent(self) -> None:
        """Calling write_digest() twice produces the same content and version."""
        dp = self.tmp / "authoring_rule_digest.md"
        vp = self.tmp / "authoring_rule_digest.version"
        c1, v1 = write_digest(digest_path=dp, version_path=vp)
        c2, v2 = write_digest(digest_path=dp, version_path=vp)
        self.assertEqual(c1, c2)
        self.assertEqual(v1, v2)


class TestPacketBuilderPicksUpVersion(unittest.TestCase):
    """Story 4.3 — packet builder reads rule_digest_version from disk.

    Uses temp files to avoid touching real data/ files.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _import_load_rule_digest_version(self):
        """Import the helper from build_authoring_packet fresh each test."""
        import importlib
        import build_authoring_packet as bap
        importlib.reload(bap)
        return bap._load_rule_digest_version

    def test_reads_version_from_version_file(self) -> None:
        """_load_rule_digest_version returns value from .version file when present."""
        import build_authoring_packet as bap

        vp = self.tmp / "authoring_rule_digest.version"
        vp.write_text("abcd1234efgh5678", encoding="utf-8")

        with patch.object(bap, "_RULE_DIGEST_VERSION_PATH", vp):
            result = bap._load_rule_digest_version()

        self.assertEqual(result, "abcd1234efgh5678")

    def test_falls_back_to_digest_hash_when_version_file_missing(self) -> None:
        """When .version file is absent, falls back to hashing the digest file."""
        import build_authoring_packet as bap

        dp = self.tmp / "authoring_rule_digest.md"
        dp.write_text("some digest content", encoding="utf-8")
        vp = self.tmp / "authoring_rule_digest.version"
        # version file does NOT exist

        with patch.object(bap, "_RULE_DIGEST_VERSION_PATH", vp), \
             patch.object(bap, "_RULE_DIGEST_PATH", dp):
            result = bap._load_rule_digest_version()

        expected = hashlib.sha256("some digest content".encode()).hexdigest()[:16]
        self.assertEqual(result, expected)

    def test_falls_back_to_pending_epic_4_when_no_files(self) -> None:
        """When neither file exists, returns 'pending-epic-4' with stderr warning."""
        import build_authoring_packet as bap
        import io

        vp = self.tmp / "authoring_rule_digest.version"
        dp = self.tmp / "authoring_rule_digest.md"
        # Neither file exists

        stderr_capture = io.StringIO()
        with patch.object(bap, "_RULE_DIGEST_VERSION_PATH", vp), \
             patch.object(bap, "_RULE_DIGEST_PATH", dp), \
             patch("sys.stderr", stderr_capture):
            result = bap._load_rule_digest_version()

        self.assertEqual(result, "pending-epic-4")
        self.assertIn("pending-epic-4", stderr_capture.getvalue())

    def test_assemble_packet_stamps_version(self) -> None:
        """assemble_packet() embeds rule_digest_version from disk, not the literal fallback string."""
        import build_authoring_packet as bap

        # Write a known version file
        vp = self.tmp / "authoring_rule_digest.version"
        vp.write_text("testversion12345", encoding="utf-8")

        stage0 = {
            "tier": "Tier 1",
            "reach_out": False,
            "required": [],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
            "flagged_gaps": [],
        }

        with patch.object(bap, "_RULE_DIGEST_VERSION_PATH", vp), \
             patch.object(bap, "_RULE_DIGEST_PATH", self.tmp / "nope.md"):
            packet = bap.assemble_packet(
                stage0=stage0,
                evidence_map=[],
                excerpts={},
                disabled=set(),
                hook_fact=None,
                company="TestCo",
                role_title="Product Manager",
                slug="testco",
                url=None,
            )

        self.assertEqual(packet["rule_digest_version"], "testversion12345")


if __name__ == "__main__":
    unittest.main()
