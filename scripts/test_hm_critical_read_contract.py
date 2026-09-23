#!/usr/bin/env python3
"""HM critical-read disposition contract tests (CR-112 Story 8.3 + 8.3.1).

Tests that hm.critical_read requires a structured review artifact with
document hashes, reviewer role enum, per-document observations grounded
in verifiable document spans, and ISO-8601 timestamps. The contract
prevents silent self-certification with filler strings, bare labels,
no-op edits, fabricated locations, or automated human-acceptance.

Story 8.3.1 (2026-09-16): RESOLVED_EDIT's edit proof derives from the
Stage 1 COMPLETE receipt's prior_output_hashes — committed workflow
state minted only by workflow/receipts.py — not from reviewer-supplied
hashes. Reviewer-supplied prior_document_hashes in the payload are
display-only and untrusted. The adversarial controls below attempt the
bypasses a self-reported prior hash enabled (invented prior hashes,
unrelated edits, reordered metadata, copied reviews, stale receipts,
duplicate receipts, role relabeling) and prove each is blocked by the
HM edit-proof invariant, not by an unrelated missing artifact.

Implements FR-319 / AC-417.

Run:
    python -m unittest scripts.test_hm_critical_read_contract -v
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("APPLYR_SYNTHETIC_IDENTITY", "1")

from workflow import receipts as receipts_mod  # noqa: E402
from workflow import state as wf_state  # noqa: E402
from workflow.policy import evaluate_truth_findings  # noqa: E402
from workflow.receipts import (  # noqa: E402
    ISSUED_BY,
    build_receipt,
    commit_stage,
    file_hash_map,
    load_receipt,
    write_receipt,
    write_state,
)
from workflow.reviews import (  # noqa: E402
    findings_content_hash,
    sync_dispositions_for_phase,
    load_dispositions,
)
from workflow.runner import (  # noqa: E402
    WorkflowError,
    run_stage2_hm,
    run_until_waiting_for_llm,
)
from workflow.state import init_state, load_state  # noqa: E402


def _write(folder: Path, name: str, content: str | dict) -> Path:
    path = folder / name
    if isinstance(content, dict):
        path.write_text(json.dumps(content, indent=2), encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8")
    return path


def _valid_stage0(**overrides) -> dict:
    data = {
        "company": "TestCo",
        "role": "Product Manager",
        "decision": "PASS",
        "tier": "Tier 1",
        "reach_out": False,
        "required": ["Own roadmap"],
        "preferred": [],
        "responsibilities": ["Ship features"],
        "culture": [],
        "flagged_gaps": [],
        "stage_signal": "unknown",
        "thin_jd": False,
        "exclusion_zone_check": "clear",
        "notes": "",
    }
    data.update(overrides)
    return data


def _sha256_file(path: str | Path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# Test document content with real spans that observations can quote.
_RESUME_TEXT = "# Jane Doe\ncontact info\n\n## PROFESSIONAL SUMMARY\nProduct manager with 7 years building data-driven B2B SaaS platforms. Owns roadmap priorities across engineering and data teams. Ships features that reduce manual ops work.\n"
_COVER_TEXT = "# Jane Doe\ncontact info\n\nDear Hiring Manager,\n\nAcme's data remediation challenge mirrors the platform data integrity work I led at Cision. I reduced manual ops by 40 percent through automated validation pipelines.\n"
_JD_TEXT = "Product Manager\n\n## Requirements\n- Own roadmap and prioritize features across teams\n- Drive data-driven decision making\n- Experience with B2B SaaS platforms\n"


class FakeLint:
    """Minimal lint result with no blocks or warns."""
    blocks: list = []
    warns: list = []


class HMContractTestBase(unittest.TestCase):
    """Shared setup: reach Stage 2 HM entry point via mock chain."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.folder = Path(self._tmpdir.name) / "acme"
        self.folder.mkdir()
        _write(self.folder, "Original_JD.txt", _JD_TEXT)
        self.gate = _valid_stage0()
        self.packet = {
            "schema_version": "1.0",
            "company": "Acme",
            "role_title": "Product Manager",
            "slug": "acme",
            "tier": "Tier 1",
            "packet_status": "ready",
            "jd_buckets": {"required": [], "preferred": [], "responsibilities": [], "culture": []},
            "evidence_map": [],
            "excerpts": {},
            "soft_gaps": [],
            "hard_constraints": [],
            "hook_fact": None,
            "rule_digest_version": "test",
            "estimated_tokens": 100,
        }

    def _reach_ats_complete(self):
        """Build the full mock chain through Stage 0 -> Stage 1 -> Truth -> ATS COMPLETE."""
        from workflow.runner import run_stage1_validate, run_stage2_ats, run_stage2_truth

        def fake_build_packet(folder, no_hook=True):
            return self.packet

        def fake_prompt(folder, force=False):
            return ("# prompt\n", {"company": "Acme", "total_estimated_tokens": 10})

        with mock.patch("workflow.runner.build_stage0_fit_gate", return_value=self.gate):
            with mock.patch("workflow.runner.build_packet", side_effect=fake_build_packet):
                with mock.patch("workflow.runner.build_authoring_prompt", side_effect=fake_prompt):
                    with mock.patch("workflow.runner.require_stage_ready"):
                        run_until_waiting_for_llm(
                            str(self.folder), mode="production", adopt=False, no_hook=True
                        )
        _write(self.folder, "Resume.md", _RESUME_TEXT)
        _write(self.folder, "CoverLetter.md", _COVER_TEXT)
        _write(
            self.folder,
            "claim_provenance.json",
            {
                "company": "Acme",
                "resume_claims": [{"bullet": "x", "claim_ids": ["ACC-101"]}],
                "cover_letter_claims": [{"proof_point": "y", "claim_ids": ["ACC-101"]}],
            },
        )
        with mock.patch("workflow.runner.run_verify_only", return_value=True):
            run_stage1_validate(str(self.folder), load_state(str(self.folder)))
        with mock.patch(
            "workflow.runner.check_claim_provenance", return_value=(True, [])
        ):
            with mock.patch(
                "workflow.runner.check_ground_truth_folder",
                return_value={
                    "submission": "acme",
                    "clean": True,
                    "jd_relevant_claims_possibly_unused": [],
                    "jd_relevant_but_unverified_claims": [],
                },
            ):
                run_stage2_truth(str(self.folder), load_state(str(self.folder)))
        with mock.patch(
            "workflow.runner.check_jd_term_folder",
            return_value={
                "submission": "acme",
                "missing_from_resume": [],
                "cover_letter_only_mentions": [],
            },
        ):
            return run_stage2_ats(str(self.folder), load_state(str(self.folder)))

    def _run_hm_get_disposition(self) -> dict:
        """Run HM subphase and return the dispositions.json content."""
        with mock.patch(
            "workflow.runner.submission_linter.lint_folder",
            return_value=[{"document": "Resume.md", "result": FakeLint()}],
        ):
            state = run_stage2_hm(str(self.folder), load_state(str(self.folder)))
        self.assertEqual(state["status"], "NEEDS_DISPOSITION")
        disp_path = self.folder / "reviews" / "dispositions.json"
        return json.loads(disp_path.read_text(encoding="utf-8"))

    def _dispose_and_rerun_hm(self, finding_id: str, disposition_value) -> dict:
        """Write a disposition for the given finding, then re-run HM."""
        disp_path = self.folder / "reviews" / "dispositions.json"
        data = json.loads(disp_path.read_text(encoding="utf-8"))
        data["by_finding_id"][finding_id] = disposition_value
        disp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        with mock.patch(
            "workflow.runner.submission_linter.lint_folder",
            return_value=[{"document": "Resume.md", "result": FakeLint()}],
        ):
            return run_stage2_hm(str(self.folder), load_state(str(self.folder)))

    def _edit_and_revalidate(self, doc: str = "Resume.md", new_content=None) -> None:
        """Edit a document, then re-run the canonical Stage 1 validate → Truth → ATS chain.

        CR-112 Story 8.3.1: this is the ONLY way RESOLVED_EDIT gains committed
        pre-edit hashes — the re-validation writes a new Stage 1 COMPLETE receipt
        whose prior_output_hashes are the pre-edit hashes preserved from the
        previous COMPLETE receipt. The appended suffix keeps every existing
        quotable span intact so review observations stay verifiable.
        """
        from workflow.runner import run_stage1_validate, run_stage2_ats, run_stage2_truth

        if new_content is None:
            append = "\n\nAdditional revised statement positioning this role's delivery experience.\n"
            cur = (self.folder / doc).read_text(encoding="utf-8")
            new_content = cur + append
        _write(self.folder, doc, new_content)
        with mock.patch("workflow.runner.run_verify_only", return_value=True):
            run_stage1_validate(str(self.folder), load_state(str(self.folder)))
        with mock.patch(
            "workflow.runner.check_claim_provenance", return_value=(True, [])
        ):
            with mock.patch(
                "workflow.runner.check_ground_truth_folder",
                return_value={
                    "submission": "acme",
                    "clean": True,
                    "jd_relevant_claims_possibly_unused": [],
                    "jd_relevant_but_unverified_claims": [],
                },
            ):
                run_stage2_truth(str(self.folder), load_state(str(self.folder)))
        with mock.patch(
            "workflow.runner.check_jd_term_folder",
            return_value={
                "submission": "acme",
                "missing_from_resume": [],
                "cover_letter_only_mentions": [],
            },
        ):
            run_stage2_ats(str(self.folder), load_state(str(self.folder)))

    def _revalidate_no_edit(self) -> None:
        """Re-run Stage 1 validate → Truth → ATS without changing any document.

        Used by no-op controls: the new Stage 1 receipt preserves the previous
        output_hashes as prior_output_hashes even when nothing changed, so the
        receipt-derived edit proof correctly reports "no change".
        """
        from workflow.runner import run_stage1_validate, run_stage2_ats, run_stage2_truth

        with mock.patch("workflow.runner.run_verify_only", return_value=True):
            run_stage1_validate(str(self.folder), load_state(str(self.folder)))
        with mock.patch(
            "workflow.runner.check_claim_provenance", return_value=(True, [])
        ):
            with mock.patch(
                "workflow.runner.check_ground_truth_folder",
                return_value={
                    "submission": "acme",
                    "clean": True,
                    "jd_relevant_claims_possibly_unused": [],
                    "jd_relevant_but_unverified_claims": [],
                },
            ):
                run_stage2_truth(str(self.folder), load_state(str(self.folder)))
        with mock.patch(
            "workflow.runner.check_jd_term_folder",
            return_value={
                "submission": "acme",
                "missing_from_resume": [],
                "cover_letter_only_mentions": [],
            },
        ):
            run_stage2_ats(str(self.folder), load_state(str(self.folder)))

    def _replace_stage1_receipt(self, receipt: dict) -> None:
        """Overwrite stage_receipts/stage1.json with an arbitrary receipt (adversarial use)."""
        rec_dir = self.folder / "stage_receipts"
        rec_dir.mkdir(exist_ok=True)
        (rec_dir / "stage1.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    def _valid_structured_review(self) -> dict:
        """Build a valid structured HM review artifact with verifiable spans."""
        resume_hash = _sha256_file(self.folder / "Resume.md")
        cover_hash = _sha256_file(self.folder / "CoverLetter.md")
        jd_hash = _sha256_file(self.folder / "Original_JD.txt")
        now = datetime.now(timezone.utc).isoformat()
        return {
            "disposition": "ACCEPTED_AS_CORRECT",
            "reasoning": (
                "Resume summary positions platform PM with data integrity scope. "
                "Cover letter opens with Acme's data remediation challenge. "
                "JD requires roadmap ownership; resume references roadmap priorities."
            ),
            "hm_review": {
                "reviewed_document_hashes": {
                    "Resume.md": resume_hash,
                    "CoverLetter.md": cover_hash,
                    "Original_JD.txt": jd_hash,
                },
                "reviewer_role": "reviewer",
                "review_timestamp": now,
                "observations": [
                    {
                        "document": "Resume.md",
                        "location": "PROFESSIONAL SUMMARY section",
                        "finding": "3 sentences positioning platform PM with data integrity scope",
                        "jd_relevance": "JD requires 'Own roadmap' and the summary references roadmap priorities",
                        "document_span": "Owns roadmap priorities across engineering and data teams",
                        "jd_span": "Own roadmap and prioritize features across teams",
                        "recommendation": "pass",
                    },
                    {
                        "document": "CoverLetter.md",
                        "location": "opening paragraph after greeting",
                        "finding": "Opens with Acme's data remediation challenge, not generic enthusiasm",
                        "jd_relevance": "JD requires data-driven decision making and the hook references data work",
                        "document_span": "Acme's data remediation challenge mirrors the platform data integrity work",
                        "jd_span": "Drive data-driven decision making",
                        "recommendation": "pass",
                    },
                ],
                "verdict": "pass",
                "overall_reasoning": "Both documents demonstrate specific engagement with the JD.",
            },
        }

    def _valid_resolved_edit_review(self) -> dict:
        """Build a valid RESOLVED_EDIT review.

        CR-112 Story 8.3.1: prior_document_hashes in the payload are
        display-only and UNTRUSTED — the validator derives the edit proof
        from the Stage 1 receipt's prior_output_hashes instead. The payload
        fields are kept here to prove they neither help nor hurt: a fabricated
        prior hash must NOT clear the finding on its own.
        """
        review = self._valid_structured_review()
        review["disposition"] = "RESOLVED_EDIT"
        review["reasoning"] = "Edited Resume.md summary and re-reviewed the documents after re-validation."
        review["hm_review"]["verdict"] = "pass"
        # Display-only prior: the validator ignores these for the edit proof.
        review["hm_review"]["prior_document_hashes"] = {
            "Resume.md": hashlib.sha256(b"# Jane Doe\nold content\n").hexdigest(),
            "CoverLetter.md": _sha256_file(self.folder / "CoverLetter.md"),
            "Original_JD.txt": _sha256_file(self.folder / "Original_JD.txt"),
        }
        review["hm_review"]["resolution_summary"] = (
            "Revised the professional summary from 2 sentences to 3, "
            "adding roadmap ownership language to match the JD requirement."
        )
        return review

    def _valid_human_accepted_risk_review(self) -> dict:
        """Build a valid HUMAN_ACCEPTED_RISK review with human_reviewer role and risk_explanation."""
        review = self._valid_structured_review()
        review["disposition"] = "HUMAN_ACCEPTED_RISK"
        review["reasoning"] = "Reviewer notes weak hook but Jason accepts the risk."
        review["risk_explanation"] = (
            "The cover letter hook is generic for this role, but Jason "
            "prefers to send as-is rather than delay the application."
        )
        review["hm_review"]["reviewer_role"] = "human_reviewer"
        review["hm_review"]["verdict"] = "revise"
        review["hm_review"]["observations"][1]["recommendation"] = "revise"
        return review


# ===========================================================================
# Acceptance tests: bare / filler dispositions must NOT clear hm.critical_read
# ===========================================================================

class TestBareAndFillerDispositionsFail(HMContractTestBase):

    def test_resolved_edit_bare_string_does_not_clear(self):
        """Bare 'RESOLVED_EDIT' must not clear hm.critical_read."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        state = self._dispose_and_rerun_hm("hm.critical_read", "RESOLVED_EDIT")
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_resolved_edit_filler_does_not_clear(self):
        """'RESOLVED_EDIT' with filler reasoning must not clear hm.critical_read."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        state = self._dispose_and_rerun_hm(
            "hm.critical_read",
            {"disposition": "RESOLVED_EDIT", "reasoning": "fixed it"},
        )
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_ten_char_filler_does_not_clear(self):
        """'looks fine' (10 chars) must not clear hm.critical_read."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        state = self._dispose_and_rerun_hm(
            "hm.critical_read",
            {"disposition": "ACCEPTED_AS_CORRECT", "reasoning": "looks fine"},
        )
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_generic_template_without_hm_review_does_not_clear(self):
        """Generic templated reasoning without hm_review must not clear."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        state = self._dispose_and_rerun_hm(
            "hm.critical_read",
            {
                "disposition": "ACCEPTED_AS_CORRECT",
                "reasoning": "Documents reviewed and acceptable for this role.",
            },
        )
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_not_applicable_does_not_clear(self):
        """NOT_APPLICABLE must not clear hm.critical_read (always required)."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        with self.assertRaises(WorkflowError) as ctx:
            self._dispose_and_rerun_hm("hm.critical_read", "NOT_APPLICABLE")
        self.assertIn("not allowed", str(ctx.exception))

    def test_false_positive_does_not_clear(self):
        """FALSE_POSITIVE must not clear hm.critical_read (not a mechanical check)."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        with self.assertRaises(WorkflowError) as ctx:
            self._dispose_and_rerun_hm("hm.critical_read", "FALSE_POSITIVE")
        self.assertIn("not allowed", str(ctx.exception))


# ===========================================================================
# Acceptance tests: valid structured review clears hm.critical_read
# ===========================================================================

class TestValidStructuredReviewClears(HMContractTestBase):

    def test_valid_structured_review_clears_hm(self):
        """A valid structured review with verifiable spans clears hm.critical_read."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")

    def test_valid_resolved_edit_with_review_clears(self):
        """RESOLVED_EDIT with a committed receipt prior proving the edit clears hm.critical_read."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        # The canonical fix loop: edit the implicated document, re-validate so
        # the Stage 1 receipt records prior_output_hashes, then dispose.
        self._edit_and_revalidate("Resume.md")
        review = self._valid_resolved_edit_review()
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")

    def test_valid_human_accepted_risk_with_review_clears(self):
        """HUMAN_ACCEPTED_RISK with human_reviewer role and risk_explanation clears."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_human_accepted_risk_review()
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")
        self.assertEqual(state["stages"]["stage2"].get("integrity"), "OVERRIDDEN")


# ===========================================================================
# Acceptance tests: staleness via document changes
# ===========================================================================

class TestStalenessViaDocumentChange(HMContractTestBase):
    """Document changes after HM disposition are caught by Stage 0/1 receipt hash chain."""

    def test_resume_change_blocks_hm(self):
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        state = self._dispose_and_rerun_hm("hm.critical_read", self._valid_structured_review())
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")
        _write(self.folder, "Resume.md", "# Name\nCOMPLETELY DIFFERENT CONTENT\n")
        with mock.patch(
            "workflow.runner.submission_linter.lint_folder",
            return_value=[{"document": "Resume.md", "result": FakeLint()}],
        ):
            with self.assertRaises(WorkflowError) as ctx:
                run_stage2_hm(str(self.folder), load_state(str(self.folder)))
        self.assertIn("Stage 1 outputs stale", str(ctx.exception))

    def test_cover_letter_change_blocks_hm(self):
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        state = self._dispose_and_rerun_hm("hm.critical_read", self._valid_structured_review())
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")
        _write(self.folder, "CoverLetter.md", "# Name\nCOMPLETELY DIFFERENT LETTER\n")
        with mock.patch(
            "workflow.runner.submission_linter.lint_folder",
            return_value=[{"document": "Resume.md", "result": FakeLint()}],
        ):
            with self.assertRaises(WorkflowError) as ctx:
                run_stage2_hm(str(self.folder), load_state(str(self.folder)))
        self.assertIn("Stage 1 outputs stale", str(ctx.exception))

    def test_jd_change_blocks_hm(self):
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        state = self._dispose_and_rerun_hm("hm.critical_read", self._valid_structured_review())
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")
        _write(self.folder, "Original_JD.txt", "Product Manager\n\n## Requirements\n- DIFFERENT\n")
        with mock.patch(
            "workflow.runner.submission_linter.lint_folder",
            return_value=[{"document": "Resume.md", "result": FakeLint()}],
        ):
            with self.assertRaises(WorkflowError):
                run_stage2_hm(str(self.folder), load_state(str(self.folder)))

    def test_stale_hash_in_review_artifact_does_not_clear(self):
        """A review artifact with stale document hashes must not clear hm.critical_read."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        review["hm_review"]["reviewed_document_hashes"]["Resume.md"] = "0" * 64
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")


# ===========================================================================
# Acceptance tests: malformed review evidence fails closed
# ===========================================================================

class TestMalformedReviewFailsClosed(HMContractTestBase):

    def test_missing_hm_review_fails_closed(self):
        """Disposition with reasoning but no hm_review object fails closed."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        state = self._dispose_and_rerun_hm(
            "hm.critical_read",
            {
                "disposition": "ACCEPTED_AS_CORRECT",
                "reasoning": "Documents reviewed and acceptable for this role.",
            },
        )
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_hm_review_missing_document_hash_fails(self):
        """hm_review missing one document hash fails closed."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        del review["hm_review"]["reviewed_document_hashes"]["CoverLetter.md"]
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_hm_review_missing_resume_observation_fails(self):
        """hm_review with no Resume.md observation fails closed."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        review["hm_review"]["observations"] = [
            obs for obs in review["hm_review"]["observations"] if obs["document"] != "Resume.md"
        ]
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_hm_review_short_location_fails(self):
        """Observation location shorter than 5 chars fails closed."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        review["hm_review"]["observations"][0]["location"] = "x"
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_hm_review_short_finding_fails(self):
        """Observation finding shorter than 15 chars fails closed."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        review["hm_review"]["observations"][0]["finding"] = "too short"
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_hm_review_missing_reviewer_role_fails(self):
        """hm_review missing reviewer_role fails closed."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        del review["hm_review"]["reviewer_role"]
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_verdict_disposition_mismatch_fails(self):
        """ACCEPTED_AS_CORRECT with verdict='reject' fails closed."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        review["hm_review"]["verdict"] = "reject"
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")


# ===========================================================================
# Acceptance tests: timestamp validation (ISO-8601 with timezone)
# ===========================================================================

class TestTimestampValidation(HMContractTestBase):

    def test_malformed_timestamp_fails(self):
        """A non-ISO-8601 timestamp must not clear hm.critical_read."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        review["hm_review"]["review_timestamp"] = "not a date"
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_naive_timestamp_fails(self):
        """A timestamp without timezone info must not clear hm.critical_read."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        review["hm_review"]["review_timestamp"] = "2026-09-13T12:00:00"
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_future_timestamp_fails(self):
        """A timestamp more than 1 hour in the future must not clear hm.critical_read."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        review["hm_review"]["review_timestamp"] = future.isoformat()
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_valid_iso_timestamp_with_z_passes(self):
        """A valid ISO-8601 timestamp with Z suffix clears (positive control)."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        review["hm_review"]["review_timestamp"] = "2026-09-13T12:00:00Z"
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")


# ===========================================================================
# Acceptance tests: RESOLVED_EDIT must prove an edit
# ===========================================================================

class TestResolvedEditProof(HMContractTestBase):
    """CR-112 Story 8.3.1: RESOLVED_EDIT edit proof comes from the Stage 1 receipt."""

    def test_noop_resolved_edit_with_unchanged_documents_fails(self):
        """RESOLVED_EDIT where committed prior == current (no real change) must not clear."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        # Re-validate without editing: the receipt honestly records prior == current.
        self._revalidate_no_edit()
        review = self._valid_resolved_edit_review()
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_resolved_edit_without_committed_prior_fails(self):
        """RESOLVED_EDIT on a first-validation receipt (no prior_output_hashes) must not clear."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_resolved_edit_review()
        del review["hm_review"]["prior_document_hashes"]
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_resolved_edit_without_resolution_summary_fails(self):
        """RESOLVED_EDIT without resolution_summary must not clear."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        self._edit_and_revalidate("Resume.md")
        review = self._valid_resolved_edit_review()
        del review["hm_review"]["resolution_summary"]
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_resolved_edit_with_changed_resume_clears(self):
        """RESOLVED_EDIT with a real Resume.md edit (committed prior) clears (positive control)."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        self._edit_and_revalidate("Resume.md")
        review = self._valid_resolved_edit_review()
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")

    def test_resolved_edit_with_changed_cover_letter_clears(self):
        """RESOLVED_EDIT with a real CoverLetter.md edit (committed prior) clears (positive control)."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        self._edit_and_revalidate("CoverLetter.md")
        review = self._valid_resolved_edit_review()
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")


# ===========================================================================
# CR-112 Story 8.3.1: adversarial controls — receipt-derived edit proof
# ===========================================================================

class TestResolvedEditAdversarial(HMContractTestBase):
    """Bypass attempts against the receipt-derived edit proof must fail closed.

    Each test names the bypass, shows it is blocked, and (where the negative
    control is meaningful) shows that providing the legitimate committed
    history — with the SAME fabricated payload — clears, proving the receipt,
    not the payload, is the deciding factor.
    """

    def test_invented_prior_document_hashes_do_not_clear(self):
        """Fabricated prior hashes in the payload cannot clear without committed history."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        # No re-validation happened: the Stage 1 receipt has no prior_output_hashes.
        review = self._valid_resolved_edit_review()  # payload claims a change it never made
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")
        # Negative control: mint the committed history, reuse the same fabricated
        # payload prior, and the disposition clears — the receipt was the blocker.
        self._edit_and_revalidate("Resume.md")
        review2 = self._valid_resolved_edit_review()  # fresh hashes, same fabricated prior shape
        state = self._dispose_and_rerun_hm("hm.critical_read", review2)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")

    def test_unrelated_document_edit_does_not_clear(self):
        """A change to a non-implicated file cannot satisfy RESOLVED_EDIT."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        # Only claim_provenance.json changes — Resume.md and CoverLetter.md are untouched.
        self._edit_and_revalidate(
            "claim_provenance.json",
            new_content={
                "company": "Acme",
                "resume_claims": [{"bullet": "x", "claim_ids": ["ACC-101", "MET-01"]}],
                "cover_letter_claims": [{"proof_point": "y", "claim_ids": ["ACC-101"]}],
            },
        )
        review = self._valid_resolved_edit_review()
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_reorders_receipt_hashes_without_recomputing_id_does_not_clear(self):
        """Hand-editing receipt hashes without recomputing receipt_id fails at anti-forgery.

        The agent rewrites the edit-proof metadata (copies the current
        output_hashes over the prior slot so prior == current) without
        recomputing the canonical receipt_id. The body no longer matches the
        id, so the validator fails closed on a forged receipt — before the
        freshness gate even needs to decide whether the edit was real.
        """
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        self._edit_and_revalidate("Resume.md")
        receipt = load_receipt(str(self.folder), "stage1")
        # output_hashes stay intact (== disk) so the runner's freshness gate
        # still passes; only the prior slot is rewritten, changing the body.
        receipt["prior_output_hashes"] = dict(receipt["output_hashes"])
        self._replace_stage1_receipt(receipt)
        review = self._valid_resolved_edit_review()
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_restored_pre_edit_receipt_does_not_clear(self):
        """Duplicating the pre-edit receipt back into place fails the freshness chain."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        pre_edit_receipt = load_receipt(str(self.folder), "stage1")
        self._edit_and_revalidate("Resume.md")
        # Agent overwrites the committed post-edit receipt with the old one.
        self._replace_stage1_receipt(pre_edit_receipt)
        review = self._valid_resolved_edit_review()
        with self.assertRaises(WorkflowError) as ctx:
            self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertIn("Stage 1 outputs stale", str(ctx.exception))

    def test_missing_receipt_fails_closed(self):
        """Deleting the Stage 1 receipt blocks RESOLVED_EDIT at the freshness chain."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        self._edit_and_revalidate("Resume.md")
        (self.folder / "stage_receipts" / "stage1.json").unlink()
        review = self._valid_resolved_edit_review()
        with self.assertRaises(WorkflowError) as ctx:
            self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertIn("Stage 1 receipt missing", str(ctx.exception))

    def test_no_edit_with_honest_receipt_and_fabricated_payload_fails(self):
        """An honest receipt recording no change defeats a payload claiming a change."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        self._revalidate_no_edit()  # committed prior == current
        review = self._valid_resolved_edit_review()  # payload fabricates a different prior
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")
        # Negative control: the legitimate committed change (same payload shape) clears.
        self._edit_and_revalidate("Resume.md")
        review2 = self._valid_resolved_edit_review()
        state = self._dispose_and_rerun_hm("hm.critical_read", review2)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")

    def test_relabeled_role_cannot_unlock_proof_free_resolved_edit(self):
        """Declaring reviewer_role=human_reviewer does not waive the edit proof."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_resolved_edit_review()
        review["hm_review"]["reviewer_role"] = "human_reviewer"
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_multi_edit_carries_original_prior_forward(self):
        """A second edit preserves the ORIGINAL prior (v1), not the intermediate (v2)."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        self._edit_and_revalidate("Resume.md")          # v1 -> v2, prior records v1
        first_prior = load_receipt(str(self.folder), "stage1")["prior_output_hashes"]
        self._edit_and_revalidate("Resume.md")          # v2 -> v3: prior must still be v1
        r1 = load_receipt(str(self.folder), "stage1")
        self.assertIn("prior_output_hashes", r1)
        self.assertEqual(
            r1["prior_output_hashes"]["Resume.md"],
            first_prior["Resume.md"],
            "the ORIGINAL pre-edit base must survive re-validation chains",
        )
        self.assertNotEqual(
            r1["prior_output_hashes"]["Resume.md"],
            r1["output_hashes"]["Resume.md"],
            "prior and current must still differ after the second edit",
        )
        # The carried-forward original prior still proves a real change: v3 != v1.
        review = self._valid_resolved_edit_review()
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")


# ===========================================================================
# Acceptance tests: reviewer role validation
# ===========================================================================

class TestReviewerRoleValidation(HMContractTestBase):

    def test_invalid_reviewer_role_fails(self):
        """A reviewer_role not in the enum must not clear hm.critical_read."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        review["hm_review"]["reviewer_role"] = "independent_reviewer"  # not in enum
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_author_cannot_accept_as_correct(self):
        """An author role may not use ACCEPTED_AS_CORRECT (must be reviewer or human_reviewer)."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        review["hm_review"]["reviewer_role"] = "author"
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_author_can_resolve_edit(self):
        """An author role may use RESOLVED_EDIT (they made the edit) once it is receipt-proven."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        self._edit_and_revalidate("Resume.md")
        review = self._valid_resolved_edit_review()
        review["hm_review"]["reviewer_role"] = "author"
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")

    def test_automated_human_accepted_risk_fails(self):
        """HUMAN_ACCEPTED_RISK with reviewer_role='reviewer' must not clear."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_human_accepted_risk_review()
        review["hm_review"]["reviewer_role"] = "reviewer"  # not human_reviewer
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_human_accepted_risk_without_risk_explanation_fails(self):
        """HUMAN_ACCEPTED_RISK without risk_explanation must not clear."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_human_accepted_risk_review()
        del review["risk_explanation"]
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")


# ===========================================================================
# Acceptance tests: filler resistance (document_span and jd_span verification)
# ===========================================================================

class TestFillerResistance(HMContractTestBase):

    def test_fabricated_document_span_fails(self):
        """A document_span not found in the document must not clear hm.critical_read."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        review["hm_review"]["observations"][0]["document_span"] = "This text does not appear anywhere in the resume"
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_fabricated_jd_span_fails(self):
        """A jd_span not found in Original_JD.txt must not clear hm.critical_read."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        review["hm_review"]["observations"][0]["jd_span"] = "This requirement does not appear in the JD"
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_missing_document_span_fails(self):
        """An observation without document_span must not clear hm.critical_read."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        del review["hm_review"]["observations"][0]["document_span"]
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_missing_jd_span_fails(self):
        """An observation without jd_span must not clear hm.critical_read."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        del review["hm_review"]["observations"][0]["jd_span"]
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")


# ===========================================================================
# Acceptance tests: idempotency and practice/production parity
# ===========================================================================

class TestIdempotencyAndParity(HMContractTestBase):

    def test_rerun_hm_with_unchanged_documents_keeps_complete(self):
        """Re-running HM with unchanged documents and valid evidence stays COMPLETE."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")
        with mock.patch(
            "workflow.runner.submission_linter.lint_folder",
            return_value=[{"document": "Resume.md", "result": FakeLint()}],
        ):
            state2 = run_stage2_hm(str(self.folder), load_state(str(self.folder)))
        self.assertEqual(state2["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")

    def test_practice_mode_uses_same_hm_contract(self):
        """Practice and production use the same HM evidence contract."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        review = self._valid_structured_review()
        state = self._dispose_and_rerun_hm("hm.critical_read", review)
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")
        # Bare RESOLVED_EDIT should fail in practice too
        disp_path = self.folder / "reviews" / "dispositions.json"
        data = json.loads(disp_path.read_text(encoding="utf-8"))
        data["by_finding_id"]["hm.critical_read"] = "RESOLVED_EDIT"
        disp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        with mock.patch(
            "workflow.runner.submission_linter.lint_folder",
            return_value=[{"document": "Resume.md", "result": FakeLint()}],
        ):
            state2 = run_stage2_hm(str(self.folder), load_state(str(self.folder)))
        self.assertEqual(state2["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")


# ===========================================================================
# Acceptance tests: --force cannot bypass, Truth behavior not weakened
# ===========================================================================

class TestForceAndTruthIsolation(HMContractTestBase):

    def test_force_cannot_bypass_hm_contract(self):
        """--force does not bypass the HM review artifact requirement."""
        self._reach_ats_complete()
        self._run_hm_get_disposition()
        disp_path = self.folder / "reviews" / "dispositions.json"
        data = json.loads(disp_path.read_text(encoding="utf-8"))
        data["by_finding_id"]["hm.critical_read"] = "RESOLVED_EDIT"
        disp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        with mock.patch(
            "workflow.runner.submission_linter.lint_folder",
            return_value=[{"document": "Resume.md", "result": FakeLint()}],
        ):
            state = run_stage2_hm(str(self.folder), load_state(str(self.folder)))
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_truth_disposition_behavior_not_weakened(self):
        """Truth findings still use the existing disposition policy (not affected by HM contract)."""
        findings_doc = {
            "findings": [
                {"id": "truth.provenance.0", "severity": "WARN", "message": "gap"}
            ]
        }
        dispositions = {
            "by_finding_id": {
                "truth.provenance.0": {
                    "disposition": "ACCEPTED_AS_CORRECT",
                    "reasoning": "finding misfired, metric is present in line 3",
                }
            }
        }
        verdict = evaluate_truth_findings(findings_doc, dispositions)
        self.assertEqual(verdict["verdict"], "PASS")

    def test_truth_resolved_edit_still_works_without_reasoning(self):
        """Truth RESOLVED_EDIT with no reasoning still passes (existing behavior preserved)."""
        findings_doc = {
            "findings": [
                {"id": "truth.provenance.0", "severity": "WARN", "message": "gap"}
            ]
        }
        dispositions = {
            "by_finding_id": {
                "truth.provenance.0": "RESOLVED_EDIT"
            }
        }
        verdict = evaluate_truth_findings(findings_doc, dispositions)
        self.assertEqual(verdict["verdict"], "PASS")


# ===========================================================================
# Unit tests for hm_review_contract.validate_hm_review
# ===========================================================================

class TestValidateHMReviewUnit(unittest.TestCase):
    """Unit tests for the hm_review_contract validator."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.folder = Path(self._tmpdir.name)
        (self.folder / "Resume.md").write_text(_RESUME_TEXT, encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text(_COVER_TEXT, encoding="utf-8")
        (self.folder / "Original_JD.txt").write_text(_JD_TEXT, encoding="utf-8")

    def _valid_review(self) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "disposition": "ACCEPTED_AS_CORRECT",
            "reasoning": "Documents reviewed and acceptable for this role.",
            "hm_review": {
                "reviewed_document_hashes": {
                    "Resume.md": _sha256_file(self.folder / "Resume.md"),
                    "CoverLetter.md": _sha256_file(self.folder / "CoverLetter.md"),
                    "Original_JD.txt": _sha256_file(self.folder / "Original_JD.txt"),
                },
                "reviewer_role": "reviewer",
                "review_timestamp": now,
                "observations": [
                    {
                        "document": "Resume.md",
                        "location": "SUMMARY section heading",
                        "finding": "Three sentences positioning platform PM scope",
                        "jd_relevance": "JD requires roadmap ownership",
                        "document_span": "Owns roadmap priorities across engineering and data teams",
                        "jd_span": "Own roadmap and prioritize features across teams",
                        "recommendation": "pass",
                    },
                    {
                        "document": "CoverLetter.md",
                        "location": "opening paragraph after greeting",
                        "finding": "Opens with company-specific challenge not generic",
                        "jd_relevance": "JD emphasizes data-driven decision making",
                        "document_span": "Acme's data remediation challenge mirrors the platform data integrity work",
                        "jd_span": "Drive data-driven decision making",
                        "recommendation": "pass",
                    },
                ],
                "verdict": "pass",
                "overall_reasoning": "Both documents engage specifically with the JD.",
            },
        }

    def test_valid_review_passes(self):
        from hm_review_contract import validate_hm_review
        ok, errors = validate_hm_review(str(self.folder), self._valid_review())
        self.assertTrue(ok, errors)

    def test_bare_string_fails(self):
        from hm_review_contract import validate_hm_review
        ok, errors = validate_hm_review(str(self.folder), "RESOLVED_EDIT")
        self.assertFalse(ok)
        self.assertTrue(any("structured review artifact" in e for e in errors))

    def test_missing_hm_review_fails(self):
        from hm_review_contract import validate_hm_review
        review = self._valid_review()
        del review["hm_review"]
        ok, errors = validate_hm_review(str(self.folder), review)
        self.assertFalse(ok)

    def test_stale_hash_fails(self):
        from hm_review_contract import validate_hm_review
        review = self._valid_review()
        review["hm_review"]["reviewed_document_hashes"]["Resume.md"] = "0" * 64
        ok, errors = validate_hm_review(str(self.folder), review)
        self.assertFalse(ok)
        self.assertTrue(any("stale review" in e for e in errors))

    def test_short_reasoning_fails(self):
        from hm_review_contract import validate_hm_review
        review = self._valid_review()
        review["reasoning"] = "looks fine"
        ok, errors = validate_hm_review(str(self.folder), review)
        self.assertFalse(ok)

    def test_single_observation_fails(self):
        from hm_review_contract import validate_hm_review
        review = self._valid_review()
        review["hm_review"]["observations"] = review["hm_review"]["observations"][:1]
        ok, errors = validate_hm_review(str(self.folder), review)
        self.assertFalse(ok)

    def test_fabricated_span_fails(self):
        from hm_review_contract import validate_hm_review
        review = self._valid_review()
        review["hm_review"]["observations"][0]["document_span"] = "fabricated text not in document"
        ok, errors = validate_hm_review(str(self.folder), review)
        self.assertFalse(ok)
        self.assertTrue(any("not found in" in e for e in errors))

    def test_naive_timestamp_fails(self):
        from hm_review_contract import validate_hm_review
        review = self._valid_review()
        review["hm_review"]["review_timestamp"] = "2026-09-13T12:00:00"
        ok, errors = validate_hm_review(str(self.folder), review)
        self.assertFalse(ok)
        self.assertTrue(any("timezone" in e for e in errors))

    def test_invalid_role_fails(self):
        from hm_review_contract import validate_hm_review
        review = self._valid_review()
        review["hm_review"]["reviewer_role"] = "super_reviewer"
        ok, errors = validate_hm_review(str(self.folder), review)
        self.assertFalse(ok)
        self.assertTrue(any("reviewer_role" in e for e in errors))

    def test_noop_resolved_edit_fails(self):
        """RESOLVED_EDIT where committed prior == current (no real change) fails closed."""
        from hm_review_contract import validate_hm_review
        from workflow.receipts import build_receipt, file_hash_map, write_receipt

        # Mint a Stage 1 COMPLETE receipt whose prior_output_hashes equal the
        # current on-disk hashes — the honest record of a re-validation with
        # no edit. The validator must report the no-op, not clear it.
        receipt = build_receipt(
            stage="stage1",
            status="COMPLETE",
            mode="production",
            input_hashes={},
            output_hashes=file_hash_map(
                str(self.folder), ["Resume.md", "CoverLetter.md", "Original_JD.txt"]
            ),
            prior_output_hashes=file_hash_map(
                str(self.folder), ["Resume.md", "CoverLetter.md"]
            ),
            prior_receipt_id="stage0:not-used-by-this-unit",
        )
        write_receipt(str(self.folder), receipt)
        review = self._valid_review()
        review["disposition"] = "RESOLVED_EDIT"
        review["reasoning"] = "Edited Resume.md summary to 3 sentences."
        review["hm_review"]["resolution_summary"] = "Fixed the summary to 3 sentences."
        ok, errors = validate_hm_review(str(self.folder), review)
        self.assertFalse(ok)
        self.assertTrue(any("no-op" in e for e in errors), errors)


class TestQueueHmReviewQuotesLiveLines(unittest.TestCase):
    """The queue hiring-manager read must quote the files it claims to have read."""

    def test_review_spans_match_the_documents(self) -> None:
        from hm_review_contract import validate_hm_review
        from workflow.runner import _queue_hm_review_value

        folder = Path(tempfile.mkdtemp(prefix="hm-queue-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        (folder / "Resume.md").write_text(
            "# Name\nSan Diego, CA | 555 | a@b.c\n\n"
            "* Owned the roadmap for a data platform used by enterprise accounts.\n",
            encoding="utf-8",
        )
        (folder / "CoverLetter.md").write_text(
            "# Name\n\nDear Hiring Manager,\n\n"
            "The platform work was sequencing a data remediation before the renewal date.\n\n"
            "Best regards,\n\nName\n",
            encoding="utf-8",
        )
        (folder / "Original_JD.txt").write_text(
            "URL: https://example.test/job\n\n"
            "Experience owning a product area and roadmap.\n",
            encoding="utf-8",
        )
        review = _queue_hm_review_value(str(folder))
        self.assertIsNotNone(review)
        ok, errors = validate_hm_review(str(folder), review)
        self.assertTrue(ok, errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
