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
from unittest import mock

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
    "learned_examples": [],
    "example_bank_version": "",
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


class TestOptimizationBarSoftGapHonesty(unittest.TestCase):
    """Packet Rule 7 parity: intentional empty soft_gap claim_ids must not fail verify."""

    def test_transferable_bridge_empty_claim_ids_passes(self):
        from author_from_packet import _check_optimization_bar_provenance

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            packet = {
                **_READY_PACKET,
                "soft_gaps": [
                    {
                        "item": "Strong command of Microsoft Office Suite.",
                        "class": "SOFT",
                        "note": (
                            "Soft gap — transferable-skill bridge; "
                            "see soft_gaps for detail."
                        ),
                        "claim_ids": [],
                    }
                ],
                "evidence_map": [],
            }
            (folder / "authoring_packet.json").write_text(
                json.dumps(packet), encoding="utf-8"
            )
            (folder / "claim_provenance.json").write_text(
                json.dumps({"resume_claims": [], "cover_letter_claims": []}),
                encoding="utf-8",
            )
            ok, lines = _check_optimization_bar_provenance(folder)
            self.assertTrue(ok, lines)
            self.assertFalse(any("soft_gap has no claim_ids" in ln for ln in lines))

    def test_soft_gap_flagged_filler_still_fails(self):
        from author_from_packet import _check_optimization_bar_provenance

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            packet = {
                **_READY_PACKET,
                "soft_gaps": [
                    {
                        "item": "Some soft gap without a real bridge",
                        "class": "SOFT",
                        "note": (
                            "Soft gap flagged at Stage 0; argue as "
                            "transferable-skill fit in cover letter."
                        ),
                        "claim_ids": [],
                    }
                ],
                "evidence_map": [],
            }
            (folder / "authoring_packet.json").write_text(
                json.dumps(packet), encoding="utf-8"
            )
            (folder / "claim_provenance.json").write_text(
                json.dumps({"resume_claims": [], "cover_letter_claims": []}),
                encoding="utf-8",
            )
            ok, lines = _check_optimization_bar_provenance(folder)
            self.assertFalse(ok)
            self.assertTrue(any("soft_gap has no claim_ids" in ln for ln in lines))


class TestPacketEvidenceUtilization(unittest.TestCase):
    """Repeated high-value packet evidence must be used, not merely retrieved."""

    def test_repeated_responsibility_claim_fails_when_unused(self):
        from author_from_packet import _check_packet_evidence_utilization

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            packet = {
                **_READY_PACKET,
                "evidence_map": [
                    {"jd_item": "Analyze outcomes", "bucket": "responsibilities", "claim_ids": ["ACC-106-DATA"]},
                    {"jd_item": "Partner commercially", "bucket": "responsibilities", "claim_ids": ["ACC-106-DATA"]},
                ],
            }
            (folder / "authoring_packet.json").write_text(json.dumps(packet), encoding="utf-8")
            (folder / "claim_provenance.json").write_text(
                json.dumps({"resume_claims": [], "cover_letter_claims": []}),
                encoding="utf-8",
            )
            ok, lines = _check_packet_evidence_utilization(folder)
            self.assertFalse(ok)
            self.assertIn("ACC-106-DATA", lines[0])

    def test_base_claim_variant_counts_as_used(self):
        from author_from_packet import _check_packet_evidence_utilization

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            packet = {
                **_READY_PACKET,
                "evidence_map": [
                    {"jd_item": "Analyze outcomes", "bucket": "responsibilities", "claim_ids": ["ACC-106-DATA"]},
                    {"jd_item": "Partner commercially", "bucket": "responsibilities", "claim_ids": ["ACC-106-DATA"]},
                ],
            }
            (folder / "authoring_packet.json").write_text(json.dumps(packet), encoding="utf-8")
            (folder / "claim_provenance.json").write_text(
                json.dumps(
                    {
                        "resume_claims": [
                            {"bullet": "Mobile audience metrics", "claim_ids": ["ACC-106-EVIDENCE"]}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            ok, lines = _check_packet_evidence_utilization(folder)
            self.assertTrue(ok, lines)


class TestPacketAtsTermContract(unittest.TestCase):
    """Packet-supported ATS terms must land in Resume.md before Stage 1 exits."""

    def test_missing_packet_term_fails(self):
        from author_from_packet import _check_packet_ats_term_contract

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "authoring_packet.json").write_text(
                json.dumps({**_READY_PACKET, "ats_term_contract": [{"term": "Engagement"}]}),
                encoding="utf-8",
            )
            (folder / "Resume.md").write_text("Customer adoption work.", encoding="utf-8")
            (folder / "claim_provenance.json").write_text(
                json.dumps({"resume_claims": []}),
                encoding="utf-8",
            )
            ok, lines = _check_packet_ats_term_contract(folder)
            self.assertFalse(ok)
            self.assertIn("Engagement", lines[0])

    def test_inflected_packet_term_passes(self):
        from author_from_packet import _check_packet_ats_term_contract

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "authoring_packet.json").write_text(
                json.dumps({**_READY_PACKET, "ats_term_contract": [{"term": "Support"}]}),
                encoding="utf-8",
            )
            (folder / "Resume.md").write_text("Supported customers through migration.", encoding="utf-8")
            (folder / "claim_provenance.json").write_text(
                json.dumps(
                    {
                        "resume_claims": [
                            {"bullet": "Supported customers", "claim_ids": ["ACC-105-AGILE"]}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            ok, lines = _check_packet_ats_term_contract(folder)
            self.assertTrue(ok, lines)

    def test_term_without_supporting_resume_claim_fails(self):
        from author_from_packet import _check_packet_ats_term_contract

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "authoring_packet.json").write_text(
                json.dumps(
                    {
                        **_READY_PACKET,
                        "ats_term_contract": [
                            {"term": "Engagement", "claim_ids": ["ACC-117-PENDO"]}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (folder / "Resume.md").write_text("Customer engagement work.", encoding="utf-8")
            (folder / "claim_provenance.json").write_text(
                json.dumps(
                    {
                        "resume_claims": [
                            {"bullet": "Other work", "claim_ids": ["ACC-105-AGILE"]}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            ok, lines = _check_packet_ats_term_contract(folder)
            self.assertFalse(ok)
            self.assertIn("Engagement", lines[0])


class TestAuthoringDefectCategories(unittest.TestCase):
    """CR-097 Story 1.1 — frozen rule_id → category map, no I/O."""

    def test_known_rules_map_to_locked_categories(self):
        from authoring_defect_categories import (
            CATEGORIES,
            category_for_rule,
            rule_ids_for_category,
        )

        self.assertEqual(category_for_rule("LR-016"), "gap_confession")
        self.assertEqual(category_for_rule("LR-006"), "forbidden_punctuation")
        self.assertEqual(category_for_rule("LR-014"), "forbidden_punctuation")
        self.assertEqual(category_for_rule("LR-015"), "forbidden_punctuation")
        self.assertIsNone(category_for_rule("LW-011"))
        self.assertIn("wrong_job_bleed", CATEGORIES)
        self.assertEqual(
            set(rule_ids_for_category("forbidden_punctuation")),
            {"LR-006", "LR-014", "LR-015"},
        )
        self.assertEqual(rule_ids_for_category("wrong_job_bleed"), ["LW-032"])
        self.assertIn("cover_voice_kicker", CATEGORIES)
        self.assertEqual(category_for_rule("LW-033"), "cover_voice_kicker")
        self.assertEqual(category_for_rule("LW-034"), "cover_voice_kicker")
        self.assertEqual(category_for_rule("LW-035"), "cover_voice_kicker")
        self.assertEqual(
            set(rule_ids_for_category("cover_voice_kicker")),
            {"LW-033", "LW-034", "LW-035"},
        )


class TestStage1VerifyHistory(unittest.TestCase):
    """CR-097 Stories 1.2 / 1.4 / 1.5 — persist verify results + write-once snapshot."""

    def _seed_folder(self, folder: Path, resume: str, letter: str) -> None:
        (folder / "Resume.md").write_text(resume, encoding="utf-8")
        (folder / "CoverLetter.md").write_text(letter, encoding="utf-8")

    def _history(self, folder: Path) -> list:
        path = folder / "stage1_first_draft" / "verify_history.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_semicolon_draft_records_punctuation_violation_and_snapshot(self):
        from author_from_packet import run_verify_only

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            resume = "Led the platform; split the work across engineering.\n"
            letter = "Dear Hiring Manager,\n\nI am applying because the role fits.\n"
            self._seed_folder(folder, resume, letter)

            passed = run_verify_only(folder, record_to=folder)
            self.assertFalse(passed)

            history = self._history(folder)
            self.assertEqual(len(history), 1)
            entry = history[0]
            self.assertEqual(entry["attempt"], 1)
            self.assertFalse(entry["passed"])
            self.assertIn("resume_sha256", entry)
            self.assertIn("cover_sha256", entry)
            punct = [
                v
                for v in entry["violations"]
                if v.get("category") == "forbidden_punctuation"
            ]
            self.assertEqual(len(punct), 1)
            self.assertEqual(punct[0]["rule_id"], "LR-014")
            self.assertEqual(punct[0]["doc"], "resume")
            self.assertEqual(punct[0]["severity"], "HARD_BLOCK")

            snap_dir = folder / "stage1_first_draft"
            self.assertEqual(
                (snap_dir / "Resume.md").read_text(encoding="utf-8"),
                (folder / "Resume.md").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                (snap_dir / "CoverLetter.md").read_text(encoding="utf-8"),
                (folder / "CoverLetter.md").read_text(encoding="utf-8"),
            )

    def test_rerun_on_identical_bytes_does_not_mint_second_attempt(self):
        from author_from_packet import run_verify_only

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self._seed_folder(
                folder,
                "Led the platform; split the work.\n",
                "Dear Hiring Manager,\n\nBody.\n",
            )
            run_verify_only(folder, record_to=folder)
            run_verify_only(folder, record_to=folder)
            self.assertEqual(len(self._history(folder)), 1)

    def test_rerun_after_edit_adds_attempt_two_and_leaves_snapshot(self):
        from author_from_packet import run_verify_only

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            original = "Led the platform; split the work.\n"
            self._seed_folder(folder, original, "Dear Hiring Manager,\n\nBody.\n")
            run_verify_only(folder, record_to=folder)
            first_snap = (
                (folder / "stage1_first_draft" / "Resume.md").read_text(encoding="utf-8")
            )

            (folder / "Resume.md").write_text(
                "Led the platform and split the work.\n", encoding="utf-8"
            )
            run_verify_only(folder, record_to=folder)

            history = self._history(folder)
            self.assertEqual(len(history), 2)
            self.assertEqual(history[1]["attempt"], 2)
            self.assertEqual(
                (folder / "stage1_first_draft" / "Resume.md").read_text(encoding="utf-8"),
                first_snap,
            )

    def test_record_to_none_writes_nothing(self):
        from author_from_packet import run_verify_only

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self._seed_folder(
                folder,
                "Led the platform; split the work.\n",
                "Dear Hiring Manager,\n\nBody.\n",
            )
            run_verify_only(folder)
            self.assertFalse((folder / "stage1_first_draft").exists())


class TestLearnedExamplesPrompt(unittest.TestCase):
    """CR-097 Stories 3.5 / 3.6 — prompt rendering and stale-bank WARN."""

    def test_empty_examples_do_not_add_before_after_block(self):
        prompt_md, meta = TestBuildAuthoringPrompt()._run()
        self.assertNotIn("BEFORE:", prompt_md)
        self.assertNotIn("real corrected drafts", prompt_md)
        self.assertEqual(meta.get("example_bank_version"), "")

    def test_fixture_examples_render_after_packet_json(self):
        packet = {
            **_READY_PACKET,
            "learned_examples": [
                {
                    "category": "forbidden_punctuation",
                    "before": "compelling: building",
                    "after": "The compelling work was building the export.",
                    "why": "LR-015 already forbids colon-as-elaboration.",
                }
            ],
            "example_bank_version": "",
        }
        prompt_md, meta = TestBuildAuthoringPrompt()._run(packet)
        json_end = prompt_md.rfind("```")
        self.assertIn("BEFORE:", prompt_md)
        self.assertIn("AFTER:", prompt_md)
        self.assertGreater(prompt_md.find("BEFORE:"), json_end)
        self.assertEqual(meta.get("example_bank_version"), "")

    def test_stale_bank_version_warns_instead_of_raising(self):
        import contextlib
        import io

        packet = {**_READY_PACKET, "example_bank_version": "deadbeefdeadbeef"}
        stderr_buf = io.StringIO()
        with tempfile.TemporaryDirectory() as tmpdir:
            _, version_path = _make_temp_digest(Path(tmpdir))
            with contextlib.redirect_stderr(stderr_buf):
                with mock.patch(
                    "author_from_packet._example_bank_version",
                    return_value="cafebabecafebabe",
                ):
                    _check_packet_ready(
                        packet, force=False, digest_version_path=version_path
                    )
        self.assertIn("example_bank_version mismatch", stderr_buf.getvalue())
        self.assertIn("WARNING", stderr_buf.getvalue())

class TestCoverVoiceKickerLint(unittest.TestCase):
    """CR-098: LW-034 / LW-035 catch recap kickers and negative listing."""

    def _letter(self, extra):
        return (
            "# JASON TAYLOR\n"
            "candidate@example.com\n\n"
            "Dear Hiring Manager,\n\n"
            "HubSpot shifted toward product-led growth.\n\n"
            f"{extra}\n\n"
            "Best regards,\n\n"
            "Jason Taylor\n"
        )

    def test_lw034_warns_on_thats_genuine(self):
        from submission_linter import lint_document
        text = self._letter("That's genuine, current, hands-on practice with the tools.")
        r = lint_document(text, "cover_letter")
        self.assertTrue(any(v.rule_id == "LW-034" for v in r.warns), r.warns)

    def test_lw034_warns_on_how_i_treated(self):
        from submission_linter import lint_document
        text = self._letter("That's how I treated Jira as the system of record.")
        r = lint_document(text, "cover_letter")
        self.assertTrue(any(v.rule_id == "LW-034" for v in r.warns), r.warns)

    def test_lw035_warns_on_not_a_opener(self):
        from submission_linter import lint_document
        text = self._letter("Not a SaaS specialist. I have shipped on a live data platform.")
        r = lint_document(text, "cover_letter")
        self.assertTrue(any(v.rule_id == "LW-035" for v in r.warns), r.warns)

    def test_preamble_names_cover_letter_voice(self):
        from author_from_packet import _PREAMBLE
        self.assertIn("COVER LETTER VOICE", _PREAMBLE)
        self.assertIn("lives or dies", _PREAMBLE)

    def test_lw036_warns_on_closed_lost(self):
        from submission_linter import lint_document
        text = self._letter("I prioritized the work from Salesforce closed-lost notes.")
        r = lint_document(text, "cover_letter")
        self.assertTrue(any(v.rule_id == "LW-036" for v in r.warns), r.warns)

    def test_lw037_warns_on_design_partner(self):
        from submission_linter import lint_document
        text = self._letter("I partner most closely with engineering, with design and marketing in the conversation.")
        r = lint_document(text, "resume")
        self.assertTrue(any(v.rule_id == "LW-037" for v in r.warns), r.warns)

    def test_lw037_allows_designed_a_formula(self):
        from submission_linter import lint_document
        text = self._letter("I designed a weighted formula over inbound issues.")
        r = lint_document(text, "cover_letter")
        self.assertFalse(any(v.rule_id == "LW-037" for v in r.warns), r.warns)


class TestSentenceLevelProvenance(unittest.TestCase):
    def _write_inputs(self, folder: Path, provenance: dict, *, version: int = 2) -> None:
        (folder / "authoring_packet.json").write_text(
            json.dumps({
                **_READY_PACKET,
                "provenance_contract": {"version": version},
            }),
            encoding="utf-8",
        )
        (folder / "Resume.md").write_text(
            "## PROFESSIONAL EXPERIENCE\n"
            "* Built a verified workflow with engineering.\n",
            encoding="utf-8",
        )
        (folder / "CoverLetter.md").write_text(
            "Dear Hiring Manager,\n\n"
            "This company serves patients.\n\n"
            "At Cision, I built a verified workflow with engineering. "
            "I would welcome a conversation.\n\n"
            "Best regards,\n\nJason\n",
            encoding="utf-8",
        )
        (folder / "claim_provenance.json").write_text(
            json.dumps(provenance),
            encoding="utf-8",
        )

    def test_exact_bullet_and_factual_sentence_pass(self):
        from author_from_packet import _check_sentence_level_provenance

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self._write_inputs(folder, {
                "resume_claims": [{
                    "bullet": "Built a verified workflow with engineering.",
                    "claim_ids": ["ACC-101"],
                }],
                "cover_letter_claims": [{
                    "sentence": "At Cision, I built a verified workflow with engineering.",
                    "claim_ids": ["ACC-101"],
                }],
            })
            ok, lines = _check_sentence_level_provenance(folder)
            self.assertTrue(ok, lines)

    def test_proof_point_summary_does_not_cover_sentence(self):
        from author_from_packet import _check_sentence_level_provenance

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self._write_inputs(folder, {
                "resume_claims": [{
                    "bullet": "Built a verified workflow with engineering.",
                    "claim_ids": ["ACC-101"],
                }],
                "cover_letter_claims": [{
                    "proof_point": "built workflow",
                    "claim_ids": ["ACC-101"],
                }],
            })
            ok, lines = _check_sentence_level_provenance(folder)
            self.assertFalse(ok)
            self.assertTrue(any("cover_letter" in line for line in lines), lines)

    def test_legacy_packet_skips(self):
        from author_from_packet import _check_sentence_level_provenance

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self._write_inputs(folder, {}, version=1)
            ok, lines = _check_sentence_level_provenance(folder)
            self.assertTrue(ok, lines)
            self.assertIn("legacy packet", lines[0])


class TestAuthoringExamplePriority(unittest.TestCase):
    def test_later_relevant_category_can_enter_three_example_budget(self):
        from authoring_examples import select_examples

        entries = []
        for index in range(3):
            entries.append({
                "id": f"old-{index}",
                "category": f"old-{index}",
                "status": "active",
                "few_shot_eligible": True,
                "added_date": "2026-01-01",
                "applies_when": {"mode": "always"},
                "match_text": "unrelated punctuation phrase",
                "before": "Before.",
                "after": "After.",
                "why": "Old.",
            })
        entries.append({
            "id": "solace-specificity",
            "category": "jd_specificity",
            "status": "active",
            "few_shot_eligible": True,
            "added_date": "2026-08-22",
            "applies_when": {"mode": "always"},
            "match_text": "patients advocates healthcare operations",
            "before": "Generic.",
            "after": "Specific.",
            "why": "Relevant.",
        })
        selected = select_examples(
            {
                "jd_buckets": {
                    "responsibilities": [
                        "Support patients and advocates through healthcare operations"
                    ]
                }
            },
            entries=entries,
        )
        self.assertIn("solace-specificity", [entry["id"] for entry in selected])


if __name__ == "__main__":
    unittest.main()
