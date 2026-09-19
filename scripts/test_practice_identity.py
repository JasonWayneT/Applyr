#!/usr/bin/env python3
"""CR-112 Story 8.2 — privacy-safe practice identity (SEC-006 / AC-416).

Synthetic fixtures only. Never read live workExperience.md. Never copy SQLite.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import (  # noqa: E402
    IdentityError,
    _SYNTHETIC_IDENTITY,
    load_identity_profile,
    resolve_identity,
)


_FAKE_WE_HEADER = {
    "name": "Alex Example",
    "email": "alex.example@example.com",
    "phone": "555-010-1234",
    "linkedin": "linkedin.com/in/alexexample",
    "location": "San Diego, CA",
    "education_line": "B.A. Example, Example University, San Diego, California, 2010",
}

_MISSING_WE = os.path.join(tempfile.gettempdir(), "applyr-missing-workExperience.md")


def _clear_synthetic_env() -> None:
    os.environ.pop("APPLYR_SYNTHETIC_IDENTITY", None)


class TestResolveIdentity(unittest.TestCase):
    def setUp(self):
        _clear_synthetic_env()
        self.addCleanup(_clear_synthetic_env)

    def test_identity_missing_fails_closed(self):
        with mock.patch("apply_resume_header._WORK_EXPERIENCE_PATH", _MISSING_WE):
            with self.assertRaises(IdentityError) as ctx:
                load_identity_profile()
        self.assertIn("APPLYR_SYNTHETIC_IDENTITY", str(ctx.exception))
        self.assertNotIn("John Doe", str(ctx.exception))

    def test_identity_synthetic_mode(self):
        os.environ["APPLYR_SYNTHETIC_IDENTITY"] = "1"
        with mock.patch(
            "apply_resume_header.load_real_header",
            side_effect=AssertionError("synthetic mode must not read WE"),
        ):
            profile, source = resolve_identity()
        self.assertEqual(source, "synthetic")
        self.assertEqual(profile["name"], _SYNTHETIC_IDENTITY["name"])
        self.assertEqual(profile["email"], _SYNTHETIC_IDENTITY["email"])

    def test_identity_we_source(self):
        with mock.patch("apply_resume_header.load_real_header", return_value=_FAKE_WE_HEADER):
            profile, source = resolve_identity()
        self.assertEqual(source, "we")
        self.assertEqual(profile["name"], "Alex Example")
        self.assertEqual(profile["email"], "alex.example@example.com")
        self.assertNotEqual(profile["name"], _SYNTHETIC_IDENTITY["name"])

    def test_no_pii_in_log_output(self):
        os.environ["APPLYR_SYNTHETIC_IDENTITY"] = "1"
        buf = io.StringIO()
        with redirect_stderr(buf):
            load_identity_profile()
        logged = buf.getvalue()
        self.assertIn("identity_source=synthetic", logged)
        for needle in (
            _SYNTHETIC_IDENTITY["name"],
            _SYNTHETIC_IDENTITY["email"],
            _SYNTHETIC_IDENTITY["phone"],
            _SYNTHETIC_IDENTITY["linkedin"],
        ):
            self.assertNotIn(needle, logged)


class TestApplyResumeHeaderIdentity(unittest.TestCase):
    def setUp(self):
        _clear_synthetic_env()
        self.addCleanup(_clear_synthetic_env)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.folder = Path(self._tmpdir.name)
        (self.folder / "Resume.md").write_text(
            "# [Name]\n[Location] | [Phone] | [Email] | [LinkedIn]\n",
            encoding="utf-8",
        )
        (self.folder / "CoverLetter.md").write_text(
            "# [Name]\n[Location] | [Phone] | [Email] | [LinkedIn]\n\n"
            "Dear Hiring Manager,\n\nBody text thanks for your consideration.\n\n"
            "Best regards,\n\nName\n",
            encoding="utf-8",
        )

    def test_apply_header_fails_without_identity(self):
        from author_from_packet import _apply_resume_header_if_available

        with mock.patch("apply_resume_header._WORK_EXPERIENCE_PATH", _MISSING_WE):
            line = _apply_resume_header_if_available(self.folder)
        self.assertTrue(line.startswith("FAIL [identity]"), line)
        self.assertIn("identity_source=missing", line)
        self.assertFalse(line.startswith("SKIP"))

    def test_apply_header_skips_in_synthetic_mode(self):
        from author_from_packet import _apply_resume_header_if_available

        os.environ["APPLYR_SYNTHETIC_IDENTITY"] = "1"
        with mock.patch(
            "apply_resume_header.load_real_header",
            side_effect=AssertionError("synthetic mode must not patch from WE"),
        ):
            line = _apply_resume_header_if_available(self.folder)
        self.assertTrue(line.startswith("SKIP [apply_resume_header]"), line)
        self.assertIn("synthetic", line.lower())

    def test_unbracketed_placeholder_header_is_replaced(self):
        from apply_resume_header import patch_file

        header = dict(_FAKE_WE_HEADER)
        self.folder.joinpath("CoverLetter.md").write_text(
            "# Jason\n"
            "Location | Email | Phone | LinkedIn\n\n"
            "Dear Hiring Manager,\n\nBody.\n",
            encoding="utf-8",
        )
        result = patch_file(str(self.folder / "CoverLetter.md"), header)
        text = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")

        self.assertIn("patched", result)
        self.assertIn("# Alex Example", text)
        self.assertIn("San Diego, CA | 555-010-1234 | alex.example@example.com", text)
        self.assertNotIn("Location | Email | Phone | LinkedIn", text)

    def test_invented_education_institution_is_overwritten(self):
        from apply_resume_header import patch_file

        header = dict(_FAKE_WE_HEADER)
        self.folder.joinpath("Resume.md").write_text(
            "# Alex Example\n"
            "San Diego, CA | 555-010-1234 | alex.example@example.com | linkedin.com/in/alexexample\n\n"
            "## PROFESSIONAL SUMMARY\n"
            "A product manager.\n\n"
            "## EDUCATION\n"
            "B.S. Computer Science, Made-Up Institute of Technology, 2018\n",
            encoding="utf-8",
        )
        result = patch_file(str(self.folder / "Resume.md"), header)
        text = (self.folder / "Resume.md").read_text(encoding="utf-8")
        self.assertIn("education", result)
        self.assertIn(header["education_line"], text)
        self.assertNotIn("Made-Up Institute of Technology", text)

    def test_wrong_role_date_is_overwritten(self):
        from apply_resume_header import patch_file

        header = dict(_FAKE_WE_HEADER)
        self.folder.joinpath("Resume.md").write_text(
            "# Alex Example\n"
            "San Diego, CA | 555-010-1234 | alex.example@example.com | linkedin.com/in/alexexample\n\n"
            "## PROFESSIONAL EXPERIENCE\n"
            "### Product Manager | Cision | January 2018 - Present\n"
            "Remote\n"
            "* Shipped a thing.\n",
            encoding="utf-8",
        )
        result = patch_file(str(self.folder / "Resume.md"), header)
        text = (self.folder / "Resume.md").read_text(encoding="utf-8")
        self.assertIn("role heading Cision", result)
        self.assertIn(
            "### Product Manager | Cision | September 2021 - January 2026",
            text,
        )
        self.assertNotIn("January 2018 - Present", text)
        self.assertIn("San Diego, CA\n* Shipped a thing.", text.replace("\r\n", "\n"))

    def test_missing_signoff_is_injected(self):
        from apply_resume_header import patch_file

        header = dict(_FAKE_WE_HEADER)
        self.folder.joinpath("CoverLetter.md").write_text(
            "# Wrong Name\n"
            "Austin, TX | 000 | wrong@example.com | linkedin.com/in/wrong\n\n"
            "Hello team,\n\n"
            "Body of the letter.\n",
            encoding="utf-8",
        )
        result = patch_file(str(self.folder / "CoverLetter.md"), header)
        text = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")
        self.assertIn("header", result)
        self.assertIn("greeting", result)
        self.assertIn("signoff", result)
        self.assertTrue(text.startswith("# Alex Example\n"))
        self.assertIn("Dear Hiring Manager,", text)
        self.assertIn("Best regards,", text)
        self.assertTrue(text.rstrip().endswith("Alex Example"))
        self.assertNotIn("Hello team,", text)
        self.assertNotIn("Wrong Name", text)

    def test_stacked_real_and_placeholder_header_is_stripped(self):
        from apply_resume_header import patch_file

        header = dict(_FAKE_WE_HEADER)
        self.folder.joinpath("CoverLetter.md").write_text(
            "# Alex Example\n"
            "San Diego, CA | 555-010-1234 | alex.example@example.com | linkedin.com/in/alexexample\n"
            "# Jason\n"
            "Location | Email | Phone | LinkedIn\n\n"
            "Dear Hiring Manager,\n\nBody.\n",
            encoding="utf-8",
        )
        result = patch_file(str(self.folder / "CoverLetter.md"), header)
        text = (self.folder / "CoverLetter.md").read_text(encoding="utf-8")

        self.assertIn("stripped stacked placeholder header", result)
        self.assertEqual(text.count("# Alex Example"), 1)
        self.assertNotIn("# Jason\nLocation | Email | Phone | LinkedIn", text)

    def test_verify_only_fails_on_identity_missing(self):
        from author_from_packet import run_verify_only

        with mock.patch("apply_resume_header._WORK_EXPERIENCE_PATH", _MISSING_WE):
            passed = run_verify_only(self.folder)
        self.assertFalse(passed)


class TestQualityCheckerIdentity(unittest.TestCase):
    def setUp(self):
        _clear_synthetic_env()
        self.addCleanup(_clear_synthetic_env)

    def test_quality_checker_no_john_doe_fallback(self):
        from quality_checker import _candidate_name_upper

        with mock.patch("apply_resume_header._WORK_EXPERIENCE_PATH", _MISSING_WE):
            with self.assertRaises(IdentityError):
                _candidate_name_upper()

    def test_h001_inject_uses_synthetic_not_default(self):
        from quality_checker import check_and_repair_cover_letter

        os.environ["APPLYR_SYNTHETIC_IDENTITY"] = "1"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CoverLetter.md"
            path.write_text(
                "Dear Hiring Manager,\n\nBody text thanks for your consideration.\n\n"
                "Best regards,\n\nName\n",
                encoding="utf-8",
            )
            ok, message = check_and_repair_cover_letter(str(path))
            self.assertTrue(ok, message)
            text = path.read_text(encoding="utf-8")
        self.assertIn("# John Doe", text)
        self.assertIn(_SYNTHETIC_IDENTITY["email"], text)


class TestStage1PromptIdentityGate(unittest.TestCase):
    def setUp(self):
        _clear_synthetic_env()
        self.addCleanup(_clear_synthetic_env)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.folder = Path(self._tmpdir.name) / "acme"
        self.folder.mkdir()

    def test_stage1_prompt_fails_before_waiting_without_identity(self):
        from workflow.runner import WorkflowError, run_stage1_prompt
        from workflow.state import init_state, load_state
        from workflow.receipts import build_receipt, commit_stage, write_state
        from workflow.invalidate import sha256_file

        jd = self.folder / "Original_JD.txt"
        jd.write_text("Product Manager\n", encoding="utf-8")
        gate = self.folder / "stage0_fit_gate.json"
        gate.write_text(
            '{"company":"Acme","role":"Product Manager","decision":"PASS",'
            '"tier":"Tier 1","reach_out":false,"required":["Own roadmap"],'
            '"preferred":[],"responsibilities":["Ship features"],"culture":[],'
            '"flagged_gaps":[],"stage_signal":"unknown","thin_jd":false,'
            '"exclusion_zone_check":"clear","notes":""}',
            encoding="utf-8",
        )
        state = init_state(str(self.folder), mode="practice")
        write_state(str(self.folder), state)
        digest = sha256_file(str(gate))
        receipt = build_receipt(
            stage="stage0",
            status="COMPLETE",
            mode="practice",
            input_hashes={},
            output_hashes={"stage0_fit_gate.json": digest},
            result={"tier": "Tier 1", "decision": "PASS", "reasons": []},
            checks={"contracts.check_stage0_fit_gate": True, "policy.evaluate_stage0": "PASS"},
        )
        state = commit_stage(
            str(self.folder),
            load_state(str(self.folder)),
            receipt,
            workflow_status="IN_PROGRESS",
            active_stage="stage1",
        )
        with mock.patch("apply_resume_header._WORK_EXPERIENCE_PATH", _MISSING_WE):
            with self.assertRaises(WorkflowError) as ctx:
                run_stage1_prompt(str(self.folder), state)
        self.assertIn("identity_source=missing", str(ctx.exception))
        self.assertFalse((self.folder / "authoring_prompt.md").exists())
        self.assertFalse((self.folder / "stage_receipts" / "stage1.json").exists())
        loaded = load_state(str(self.folder))
        self.assertNotEqual(loaded.get("status"), "WAITING_FOR_LLM")


if __name__ == "__main__":
    unittest.main(verbosity=2)
