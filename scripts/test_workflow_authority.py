#!/usr/bin/env python3
"""
CR-076 workflow authority tests.

Run:
  .venv\\Scripts\\python.exe -m unittest scripts.test_workflow_authority -v
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

import contracts  # noqa: E402
from workflow import receipts as receipts_mod  # noqa: E402
from workflow.policy import evaluate_packet, evaluate_stage0  # noqa: E402
from workflow.receipts import (  # noqa: E402
    ISSUED_BY,
    build_receipt,
    commit_stage,
    load_receipt,
    write_receipt,
    write_state,
)
from workflow.runner import (  # noqa: E402
    WorkflowError,
    adopt_existing,
    run_stage0,
    run_stage1_validate,
    run_until_stage1_complete,
    run_until_waiting_for_llm,
)
from workflow.state import init_state, load_state  # noqa: E402
from workflow.transitions import new_state  # noqa: E402
from workflow.invalidate import reconcile_state_against_receipts  # noqa: E402


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


class WorkflowAuthorityTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.folder = Path(self._tmpdir.name) / "testco"
        self.folder.mkdir()

    def test_receipt_issued_by_is_run_submission(self):
        r = build_receipt(
            stage="stage0",
            status="COMPLETE",
            mode="production",
            input_hashes={"Original_JD.txt": "abc"},
            output_hashes={"stage0_fit_gate.json": "def"},
        )
        self.assertEqual(r["issued_by"], ISSUED_BY)
        self.assertTrue(r["receipt_id"].startswith("stage0:"))

    def test_commit_stage_writes_receipt_then_state(self):
        state = init_state(str(self.folder), mode="production")
        write_state(str(self.folder), state)
        receipt = build_receipt(
            stage="stage0",
            status="COMPLETE",
            mode="production",
            input_hashes={},
            output_hashes={"stage0_fit_gate.json": "x" * 64},
            result={"tier": "Tier 1"},
        )
        new = commit_stage(
            str(self.folder),
            state,
            receipt,
            workflow_status="IN_PROGRESS",
            active_stage="stage1",
        )
        self.assertEqual(new["status"], "IN_PROGRESS")
        loaded = load_receipt(str(self.folder), "stage0")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["receipt_id"], receipt["receipt_id"])
        self.assertTrue((self.folder / "stage_receipts" / "stage0.json").exists())

    def test_workers_must_not_be_receipt_writer_module(self):
        """Authority boundary: only workflow.receipts exposes write_receipt/commit_stage."""
        import workflow.receipts as wr

        self.assertTrue(hasattr(wr, "write_receipt"))
        self.assertTrue(hasattr(wr, "commit_stage"))
        # Domain workers should not define these names
        import build_stage0_fit_gate as s0
        import build_authoring_packet as pkt
        import author_from_packet as afp

        for mod in (s0, pkt, afp):
            self.assertFalse(hasattr(mod, "write_receipt"))
            self.assertFalse(hasattr(mod, "commit_stage"))
            self.assertFalse(hasattr(mod, "write_state"))

    def test_policy_skip_and_pass(self):
        self.assertEqual(evaluate_stage0(_valid_stage0(tier="Skip", decision="SKIP"))["verdict"], "SKIP")
        self.assertEqual(evaluate_stage0(_valid_stage0())["verdict"], "PASS")
        self.assertEqual(evaluate_packet({"packet_status": "ready"})["verdict"], "PASS")
        self.assertEqual(
            evaluate_packet({"packet_status": "incomplete", "incomplete_reasons": ["x"]})["verdict"],
            "FAIL",
        )

    def test_check_workflow_complete_waiting_for_llm(self):
        state = init_state(str(self.folder))
        state["status"] = "WAITING_FOR_LLM"
        write_state(str(self.folder), state)
        ok, errors = contracts.check_workflow_complete(str(self.folder))
        self.assertFalse(ok)
        self.assertTrue(any("WAITING_FOR_LLM" in e for e in errors))

    def test_check_workflow_complete_skipped(self):
        state = init_state(str(self.folder))
        state["status"] = "SKIPPED"
        write_state(str(self.folder), state)
        ok, errors = contracts.check_workflow_complete(str(self.folder))
        self.assertFalse(ok)
        self.assertTrue(any("SKIPPED" in e for e in errors))

    def test_adopt_stage0_pass(self):
        _write(self.folder, "Original_JD.txt", "Product Manager\n\nRequirements:\n- Own roadmap\n")
        _write(self.folder, "stage0_fit_gate.json", _valid_stage0())
        state = adopt_existing(str(self.folder), mode="production")
        self.assertIn(state["status"], ("IN_PROGRESS", "WAITING_FOR_LLM"))
        r0 = load_receipt(str(self.folder), "stage0")
        self.assertIsNotNone(r0)
        self.assertEqual(r0["status"], "COMPLETE")
        self.assertEqual(r0["issued_by"], ISSUED_BY)

    def test_adopt_stage0_skip(self):
        _write(self.folder, "Original_JD.txt", "Skip me\n")
        _write(
            self.folder,
            "stage0_fit_gate.json",
            _valid_stage0(tier="Skip", decision="SKIP", skip_reason="DB reject"),
        )
        state = adopt_existing(str(self.folder), mode="production")
        self.assertEqual(state["status"], "SKIPPED")
        r0 = load_receipt(str(self.folder), "stage0")
        self.assertEqual(r0["status"], "SKIPPED")

    def test_run_stage0_skip_via_mock(self):
        _write(self.folder, "Original_JD.txt", "Whatever\n")
        state = init_state(str(self.folder))
        write_state(str(self.folder), state)
        skip_gate = _valid_stage0(tier="Skip", decision="SKIP", skip_reason="prefs")
        with mock.patch("workflow.runner.build_stage0_fit_gate", return_value=skip_gate):
            out = run_stage0(str(self.folder), state)
        self.assertEqual(out["status"], "SKIPPED")
        self.assertEqual(load_receipt(str(self.folder), "stage0")["status"], "SKIPPED")

    def test_force_reruns_previously_skipped_stage0(self):
        _write(self.folder, "Original_JD.txt", "Whatever\n")
        state = init_state(str(self.folder))
        state["status"] = "SKIPPED"
        state["stages"]["stage0"]["status"] = "SKIPPED"
        write_state(str(self.folder), state)
        rebuilt = new_state("production")
        rebuilt["status"] = "SKIPPED"
        rebuilt["stages"]["stage0"]["status"] = "SKIPPED"
        with mock.patch("workflow.runner.run_stage0", return_value=rebuilt) as run:
            with mock.patch(
                "workflow.runner._place_after_stage0", return_value=str(self.folder)
            ):
                out = run_until_waiting_for_llm(
                    str(self.folder), mode="production", adopt=False, force=True
                )
        run.assert_called_once()
        self.assertEqual(out["status"], "SKIPPED")

    def test_crash_resume_receipt_without_state_pointer(self):
        """If receipt exists but state lags, adopt path / load_receipt still see receipt."""
        state = init_state(str(self.folder))
        receipt = build_receipt(
            stage="stage0",
            status="COMPLETE",
            mode="production",
            input_hashes={},
            output_hashes={"stage0_fit_gate.json": "a" * 64},
        )
        write_receipt(str(self.folder), receipt)
        write_state(str(self.folder), state)
        loaded = load_receipt(str(self.folder), "stage0")
        self.assertEqual(loaded["receipt_id"], receipt["receipt_id"])
        _write(self.folder, "stage0_fit_gate.json", _valid_stage0())
        _write(self.folder, "Original_JD.txt", "JD\n")
        from workflow.invalidate import sha256_file

        digest = sha256_file(str(self.folder / "stage0_fit_gate.json"))
        receipt2 = build_receipt(
            stage="stage0",
            status="COMPLETE",
            mode="production",
            input_hashes={},
            output_hashes={"stage0_fit_gate.json": digest},
            result={"recovered": True},
        )
        commit_stage(
            str(self.folder),
            state,
            receipt2,
            workflow_status="IN_PROGRESS",
            active_stage="stage1",
        )
        st = load_state(str(self.folder))
        self.assertEqual(st["stages"]["stage0"]["receipt_id"], receipt2["receipt_id"])


class RunUntilWaitingTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.folder = Path(self._tmpdir.name) / "acme"
        self.folder.mkdir()
        _write(self.folder, "Original_JD.txt", "Product Manager\n\n## Requirements\n- Own roadmap\n")

    def test_full_slice_with_mocks(self):
        gate = _valid_stage0()
        packet = {
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

        def fake_build_packet(folder, no_hook=True):
            return packet

        def fake_prompt(folder, force=False):
            return ("# prompt\n", {"company": "Acme", "total_estimated_tokens": 10})

        with mock.patch("workflow.runner.build_stage0_fit_gate", return_value=gate):
            with mock.patch("workflow.runner.build_packet", side_effect=fake_build_packet):
                with mock.patch("workflow.runner.build_authoring_prompt", side_effect=fake_prompt):
                    with mock.patch("workflow.runner.require_stage_ready"):
                        state = run_until_waiting_for_llm(
                            str(self.folder),
                            mode="production",
                            adopt=False,
                            no_hook=True,
                        )
        self.assertEqual(state["status"], "WAITING_FOR_LLM")
        self.assertTrue((self.folder / "authoring_prompt.md").exists())
        self.assertTrue((self.folder / "stage_receipts" / "stage1.json").exists())
        ok, _ = contracts.check_workflow_complete(str(self.folder))
        self.assertFalse(ok)


class Stage1CompleteAndStaleTests(unittest.TestCase):
    """CR-077: Stage 1 COMPLETE chaining + hash cascade."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.folder = Path(self._tmpdir.name) / "acme"
        self.folder.mkdir()
        _write(self.folder, "Original_JD.txt", "Product Manager\n\n## Requirements\n- Own roadmap\n")
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

    def _reach_waiting(self):
        def fake_build_packet(folder, no_hook=True):
            return self.packet

        def fake_prompt(folder, force=False):
            return ("# prompt\n", {"company": "Acme", "total_estimated_tokens": 10})

        with mock.patch("workflow.runner.build_stage0_fit_gate", return_value=self.gate):
            with mock.patch("workflow.runner.build_packet", side_effect=fake_build_packet):
                with mock.patch("workflow.runner.build_authoring_prompt", side_effect=fake_prompt):
                    with mock.patch("workflow.runner.require_stage_ready"):
                        return run_until_waiting_for_llm(
                            str(self.folder),
                            mode="production",
                            adopt=False,
                            no_hook=True,
                        )

    def test_stage1_complete_chains_and_unlocks_stage2(self):
        waiting = self._reach_waiting()
        self.assertEqual(waiting["status"], "WAITING_FOR_LLM")
        waiting_receipt = load_receipt(str(self.folder), "stage1")
        self.assertEqual(waiting_receipt["status"], "WAITING_FOR_LLM")

        _write(self.folder, "Resume.md", "# Name\n\n## PROFESSIONAL SUMMARY\nOne. Two. Three.\n")
        _write(self.folder, "CoverLetter.md", "# Name\n\nDear Hiring Manager,\n\nBody.\n\nBest regards,\n\nName\n")
        _write(self.folder, "claim_provenance.json", {"claims": []})

        with mock.patch("workflow.runner.run_verify_only", return_value=True):
            state = run_until_stage1_complete(
                str(self.folder),
                mode="production",
                adopt=False,
                no_hook=True,
            )

        self.assertEqual(state["status"], "IN_PROGRESS")
        self.assertEqual(state["active_stage"], "stage2")
        self.assertEqual(state["stages"]["stage1"]["status"], "COMPLETE")
        self.assertEqual(state["stages"]["stage2"]["status"], "READY")
        r1 = load_receipt(str(self.folder), "stage1")
        self.assertEqual(r1["status"], "COMPLETE")
        # Stage 1 COMPLETE must cite Stage 0's receipt_id (cross-stage chain),
        # not the Stage 1 WAITING receipt (same-stage intermediate).
        # check_workflow_complete expects stage N → stage N-1 chaining.
        r0 = load_receipt(str(self.folder), "stage0")
        self.assertEqual(r1["prior_receipt_id"], r0["receipt_id"])
        self.assertIn("Resume.md", r1["output_hashes"])
        self.assertIn("CoverLetter.md", r1["output_hashes"])
        ok, _ = contracts.check_workflow_complete(str(self.folder))
        self.assertFalse(ok)  # Stage 2+ not yet complete

    def test_edit_resume_marks_stage1_stale_locks_stage2(self):
        self._reach_waiting()
        _write(self.folder, "Resume.md", "# Name\nv1\n")
        _write(self.folder, "CoverLetter.md", "# Name\nletter\n")
        # CR-092 (2026-08-15): claim_provenance.json is now part of the
        # Stage 1 gate too -- see test_stage1_complete_chains_and_unlocks_
        # stage2's equivalent fixture, above, for the full reasoning.
        _write(self.folder, "claim_provenance.json", {"claims": []})
        with mock.patch("workflow.runner.run_verify_only", return_value=True) as mocked:
            state = run_stage1_validate(str(self.folder), load_state(str(self.folder)))
        mocked.assert_called_once()
        self.assertEqual(
            mocked.call_args.kwargs.get("record_to"),
            Path(self.folder),
        )
        self.assertEqual(state["stages"]["stage1"]["status"], "COMPLETE")
        self.assertEqual(state["stages"]["stage2"]["status"], "READY")

        # Mutate authored output after receipt
        _write(self.folder, "Resume.md", "# Name\nv2 EDITED\n")
        state = load_state(str(self.folder))
        new_state, reasons = reconcile_state_against_receipts(
            str(self.folder), state, load_receipt
        )
        self.assertTrue(reasons)
        self.assertEqual(new_state["stages"]["stage1"]["status"], "STALE")
        self.assertEqual(new_state["stages"]["stage2"]["status"], "LOCKED")
        self.assertIsNone(new_state["stages"]["stage2"]["receipt_id"])
        self.assertEqual(new_state["status"], "STALE")

    def test_resume_revalidates_after_stale(self):
        self._reach_waiting()
        _write(self.folder, "Resume.md", "# Name\nv1\n")
        _write(self.folder, "CoverLetter.md", "# Name\nletter\n")
        # CR-092 (2026-08-15): claim_provenance.json is now part of the
        # Stage 1 gate too -- see test_stage1_complete_chains_and_unlocks_
        # stage2's equivalent fixture, above, for the full reasoning.
        _write(self.folder, "claim_provenance.json", {"claims": []})
        with mock.patch("workflow.runner.run_verify_only", return_value=True):
            run_stage1_validate(str(self.folder), load_state(str(self.folder)))

        _write(self.folder, "Resume.md", "# Name\nv2\n")
        with mock.patch("workflow.runner.run_verify_only", return_value=True):
            with mock.patch("workflow.runner.build_stage0_fit_gate", return_value=self.gate):
                with mock.patch("workflow.runner.build_packet", return_value=self.packet):
                    with mock.patch(
                        "workflow.runner.build_authoring_prompt",
                        return_value=("# prompt\n", {"company": "Acme"}),
                    ):
                        with mock.patch("workflow.runner.require_stage_ready"):
                            state = run_until_stage1_complete(
                                str(self.folder),
                                mode="production",
                                adopt=False,
                                no_hook=True,
                            )
        self.assertEqual(state["stages"]["stage1"]["status"], "COMPLETE")
        self.assertEqual(state["stages"]["stage2"]["status"], "READY")
        self.assertEqual(state["status"], "IN_PROGRESS")

    def test_verify_only_failure_does_not_write_complete(self):
        self._reach_waiting()
        _write(self.folder, "Resume.md", "# bad\n")
        _write(self.folder, "CoverLetter.md", "# bad\n")
        with mock.patch("workflow.runner.run_verify_only", return_value=False):
            with self.assertRaises(WorkflowError):
                run_stage1_validate(str(self.folder), load_state(str(self.folder)))
        r1 = load_receipt(str(self.folder), "stage1")
        self.assertEqual(r1["status"], "WAITING_FOR_LLM")


class TruthReviewTests(unittest.TestCase):
    """CR-079: Truth findings + dispositions + subphase COMPLETE."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.folder = Path(self._tmpdir.name) / "acme"
        self.folder.mkdir()
        _write(self.folder, "Original_JD.txt", "Product Manager\n\n## Requirements\n- Own roadmap\n")
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

    def _reach_stage1_complete(self):
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
        _write(self.folder, "Resume.md", "# Name\nv1\n")
        _write(self.folder, "CoverLetter.md", "# Name\nletter\n")
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
            return run_stage1_validate(str(self.folder), load_state(str(self.folder)))

    def test_truth_settled_resolves_bare_slug_before_stage2(self):
        """--resume with a slug must not look for ./slug under cwd.

        Found 2026-08-14: run_until_stage1_complete resolved data/submissions/{slug},
        then run_until_truth_settled passed the bare slug into run_stage2_truth,
        which reconciled a newly created repo-root folder and raised
        'Stage 1 receipt missing'.
        """
        from workflow import runner as runner_mod

        resolved = str(self.folder)
        complete_state = {
            "status": "IN_PROGRESS",
            "stages": {
                "stage1": {"status": "COMPLETE"},
                "stage2": {
                    "status": "READY",
                    "subphases": {"truth": {"status": "READY"}},
                },
            },
        }
        waiting_state = {
            "status": "NEEDS_DISPOSITION",
            "stages": {
                "stage1": {"status": "COMPLETE"},
                "stage2": {
                    "subphases": {"truth": {"status": "NEEDS_DISPOSITION"}},
                },
            },
        }
        with mock.patch.object(
            runner_mod, "run_until_stage1_complete", return_value=complete_state
        ):
            with mock.patch.object(
                runner_mod, "run_stage2_truth", return_value=waiting_state
            ) as truth:
                with mock.patch.object(
                    runner_mod, "_resolve_folder", return_value=resolved
                ) as resolve:
                    runner_mod.run_until_truth_settled("skyflow")
        resolve.assert_called_with("skyflow")
        self.assertEqual(truth.call_args[0][0], resolved)

    def test_truth_clean_passes_and_unlocks_ats(self):
        from workflow.runner import run_stage2_truth, run_until_truth_settled

        self._reach_stage1_complete()
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
                state = run_stage2_truth(str(self.folder), load_state(str(self.folder)))
        self.assertEqual(state["status"], "IN_PROGRESS")
        truth = state["stages"]["stage2"]["subphases"]["truth"]
        self.assertEqual(truth["status"], "COMPLETE")
        self.assertEqual(state["stages"]["stage2"]["subphases"]["ats"]["status"], "READY")
        self.assertTrue((self.folder / "reviews" / "truth_findings.json").exists())
        # No Stage 2 receipt yet
        self.assertFalse((self.folder / "stage_receipts" / "stage2.json").exists())
        ok, _ = contracts.check_workflow_complete(str(self.folder))
        self.assertFalse(ok)

    def test_truth_open_findings_wait_for_human(self):
        from workflow.runner import run_stage2_truth

        self._reach_stage1_complete()
        with mock.patch(
            "workflow.runner.check_claim_provenance", return_value=(True, [])
        ):
            with mock.patch(
                "workflow.runner.check_ground_truth_folder",
                return_value={
                    "submission": "acme",
                    "clean": False,
                    "jd_relevant_claims_possibly_unused": [
                        {"project_id": "ACC-102", "matched_tags": ["data"], "metrics": []}
                    ],
                    "jd_relevant_but_unverified_claims": [],
                },
            ):
                state = run_stage2_truth(str(self.folder), load_state(str(self.folder)))
        self.assertEqual(state["status"], "NEEDS_DISPOSITION")
        self.assertEqual(
            state["stages"]["stage2"]["subphases"]["truth"]["status"], "NEEDS_DISPOSITION"
        )
        disp = json.loads((self.folder / "reviews" / "dispositions.json").read_text(encoding="utf-8"))
        self.assertIn("truth.coverage.unused.ACC-102", disp["by_finding_id"])
        self.assertIsNone(disp["by_finding_id"]["truth.coverage.unused.ACC-102"])

    def test_truth_disposition_clears_wait(self):
        from workflow.runner import run_stage2_truth

        self._reach_stage1_complete()
        with mock.patch(
            "workflow.runner.check_claim_provenance", return_value=(True, [])
        ):
            with mock.patch(
                "workflow.runner.check_ground_truth_folder",
                return_value={
                    "submission": "acme",
                    "clean": False,
                    "jd_relevant_claims_possibly_unused": [
                        {"project_id": "ACC-102", "matched_tags": ["data"], "metrics": []}
                    ],
                    "jd_relevant_but_unverified_claims": [],
                },
            ):
                run_stage2_truth(str(self.folder), load_state(str(self.folder)))
                # Human disposes
                disp_path = self.folder / "reviews" / "dispositions.json"
                data = json.loads(disp_path.read_text(encoding="utf-8"))
                data["by_finding_id"]["truth.coverage.unused.ACC-102"] = "FALSE_POSITIVE"
                disp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                state = run_stage2_truth(str(self.folder), load_state(str(self.folder)))
        self.assertEqual(state["stages"]["stage2"]["subphases"]["truth"]["status"], "COMPLETE")
        self.assertEqual(state["status"], "IN_PROGRESS")

    def test_stale_disposition_cleared_when_finding_content_changes(self):
        """Invariant: disposition binds to findings content, not just stable finding id.

        Same finding id with different message/payload must re-open NEEDS_DISPOSITION
        rather than letting a prior FALSE_POSITIVE complete Truth against new content.
        """
        from workflow.runner import run_stage2_truth

        self._reach_stage1_complete()
        coverage_v1 = {
            "submission": "acme",
            "clean": False,
            "jd_relevant_claims_possibly_unused": [
                {
                    "project_id": "ACC-102",
                    "matched_tags": ["data"],
                    "metrics": ["old-metric"],
                }
            ],
            "jd_relevant_but_unverified_claims": [],
        }
        coverage_v2 = {
            "submission": "acme",
            "clean": False,
            "jd_relevant_claims_possibly_unused": [
                {
                    "project_id": "ACC-102",
                    "matched_tags": ["data", "sql"],
                    "metrics": ["new-metric-MET-09"],
                }
            ],
            "jd_relevant_but_unverified_claims": [],
        }
        with mock.patch(
            "workflow.runner.check_claim_provenance", return_value=(True, [])
        ):
            with mock.patch(
                "workflow.runner.check_ground_truth_folder",
                return_value=coverage_v1,
            ):
                run_stage2_truth(str(self.folder), load_state(str(self.folder)))
                disp_path = self.folder / "reviews" / "dispositions.json"
                data = json.loads(disp_path.read_text(encoding="utf-8"))
                self.assertIn("bound_findings_hashes", data)
                self.assertIn("truth", data["bound_findings_hashes"])
                data["by_finding_id"]["truth.coverage.unused.ACC-102"] = "FALSE_POSITIVE"
                disp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                # Same findings content — disposition must still clear the wait
                state = run_stage2_truth(str(self.folder), load_state(str(self.folder)))
                self.assertEqual(
                    state["stages"]["stage2"]["subphases"]["truth"]["status"], "COMPLETE"
                )

            with mock.patch(
                "workflow.runner.check_ground_truth_folder",
                return_value=coverage_v2,
            ):
                # Finding id unchanged, payload changed — disposition must invalidate
                state = run_stage2_truth(str(self.folder), load_state(str(self.folder)))
        self.assertEqual(state["status"], "NEEDS_DISPOSITION")
        self.assertEqual(
            state["stages"]["stage2"]["subphases"]["truth"]["status"],
            "NEEDS_DISPOSITION",
        )
        disp = json.loads(
            (self.folder / "reviews" / "dispositions.json").read_text(encoding="utf-8")
        )
        self.assertIsNone(disp["by_finding_id"]["truth.coverage.unused.ACC-102"])

    def test_block_finding_rejects_false_positive(self):
        from workflow.policy import evaluate_truth_findings

        verdict = evaluate_truth_findings(
            {
                "findings": [
                    {
                        "id": "truth.provenance.0",
                        "severity": "BLOCK",
                        "message": "fabricated",
                    }
                ]
            },
            {"by_finding_id": {"truth.provenance.0": "FALSE_POSITIVE"}},
        )
        self.assertEqual(verdict["verdict"], "FAIL")

    def test_human_accepted_risk_marks_overridden(self):
        from workflow.policy import evaluate_truth_findings

        verdict = evaluate_truth_findings(
            {
                "findings": [
                    {
                        "id": "truth.provenance.0",
                        "severity": "BLOCK",
                        "message": "fabricated",
                    }
                ]
            },
            {"by_finding_id": {"truth.provenance.0": "HUMAN_ACCEPTED_RISK"}},
        )
        self.assertEqual(verdict["verdict"], "PASS")
        self.assertEqual(verdict["integrity"], "OVERRIDDEN")


class AtsReviewTests(unittest.TestCase):
    """CR-080: ATS findings after Truth COMPLETE."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.folder = Path(self._tmpdir.name) / "acme"
        self.folder.mkdir()
        _write(self.folder, "Original_JD.txt", "Product Manager\n\n## Requirements\n- Own roadmap\n")
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

    def _reach_truth_complete(self):
        from workflow.runner import run_stage1_validate, run_stage2_truth

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
        _write(self.folder, "Resume.md", "# Name\nv1\n")
        _write(self.folder, "CoverLetter.md", "# Name\nletter\n")
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
                return run_stage2_truth(str(self.folder), load_state(str(self.folder)))

    def test_ats_clean_unlocks_hm(self):
        from workflow.runner import run_stage2_ats

        self._reach_truth_complete()
        with mock.patch(
            "workflow.runner.check_jd_term_folder",
            return_value={
                "submission": "acme",
                "missing_from_resume": [],
                "cover_letter_only_mentions": [],
            },
        ):
            state = run_stage2_ats(str(self.folder), load_state(str(self.folder)))
        self.assertEqual(state["stages"]["stage2"]["subphases"]["ats"]["status"], "COMPLETE")
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "READY")
        self.assertTrue((self.folder / "reviews" / "ats_findings.json").exists())
        self.assertFalse((self.folder / "stage_receipts" / "stage2.json").exists())

    def test_ats_gap_waits_for_human(self):
        from workflow.runner import run_stage2_ats

        self._reach_truth_complete()
        with mock.patch(
            "workflow.runner.check_jd_term_folder",
            return_value={
                "submission": "acme",
                "missing_from_resume": ["SQL"],
                "cover_letter_only_mentions": [],
            },
        ):
            state = run_stage2_ats(str(self.folder), load_state(str(self.folder)))
        self.assertEqual(state["status"], "NEEDS_DISPOSITION")
        self.assertEqual(
            state["stages"]["stage2"]["subphases"]["ats"]["status"], "NEEDS_DISPOSITION"
        )


class Stage2PolicyTests(unittest.TestCase):
    """CR-081: HM → mech → Stage 2 COMPLETE receipt."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.folder = Path(self._tmpdir.name) / "acme"
        self.folder.mkdir()
        _write(self.folder, "Original_JD.txt", "Product Manager\n\n## Requirements\n- Own roadmap\n")
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
        _write(self.folder, "Resume.md", "# Name\nv1\n")
        _write(self.folder, "CoverLetter.md", "# Name\nletter\n")
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

    def test_hm_requires_critical_read_disposition(self):
        from workflow.runner import run_stage2_hm

        class FakeLint:
            blocks = []
            warns = []

        self._reach_ats_complete()
        with mock.patch(
            "workflow.runner.submission_linter.lint_folder",
            return_value=[{"document": "Resume.md", "result": FakeLint()}],
        ):
            state = run_stage2_hm(str(self.folder), load_state(str(self.folder)))
        self.assertEqual(state["status"], "NEEDS_DISPOSITION")
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "NEEDS_DISPOSITION")

    def test_stage2_receipt_after_policy(self):
        from workflow.runner import run_stage2_hm, run_stage2_mech, run_stage2_policy

        class FakeLint:
            blocks = []
            warns = []

        self._reach_ats_complete()
        with mock.patch(
            "workflow.runner.submission_linter.lint_folder",
            return_value=[{"document": "Resume.md", "result": FakeLint()}],
        ):
            run_stage2_hm(str(self.folder), load_state(str(self.folder)))
        disp = json.loads((self.folder / "reviews" / "dispositions.json").read_text(encoding="utf-8"))
        disp["by_finding_id"]["hm.critical_read"] = "ACCEPTED_AS_CORRECT"
        (self.folder / "reviews" / "dispositions.json").write_text(
            json.dumps(disp, indent=2), encoding="utf-8"
        )
        with mock.patch(
            "workflow.runner.submission_linter.lint_folder",
            return_value=[{"document": "Resume.md", "result": FakeLint()}],
        ):
            state = run_stage2_hm(str(self.folder), load_state(str(self.folder)))
        self.assertEqual(state["stages"]["stage2"]["subphases"]["hm"]["status"], "COMPLETE")

        _write(self.folder, "Resume.pdf", "pdf")
        _write(self.folder, "CoverLetter.pdf", "pdf")
        _write(
            self.folder,
            "draft_manifest.json",
            {
                "rubric_score": {
                    "resume": {"total": 75, "breakdown": {}},
                    "cover_letter": {"total": 70, "breakdown": {}},
                }
            },
        )
        with mock.patch("workflow.runner._compile_pdfs"):
            with mock.patch(
                "workflow.runner.verify_one",
                return_value={
                    "submission": "acme",
                    "mechanically_verified": True,
                    "lint_all_clean": True,
                    "page_counts_ok": True,
                    "page_counts": {"Resume.pdf": 1, "CoverLetter.pdf": 1},
                },
            ):
                state = run_stage2_mech(
                    str(self.folder), load_state(str(self.folder)), compile_pdfs=True
                )
        # rubric finding may still wait
        if state["status"] == "NEEDS_DISPOSITION":
            disp = json.loads(
                (self.folder / "reviews" / "dispositions.json").read_text(encoding="utf-8")
            )
            for k in list(disp["by_finding_id"]):
                if disp["by_finding_id"][k] is None:
                    disp["by_finding_id"][k] = "ACCEPTED_AS_CORRECT"
            (self.folder / "reviews" / "dispositions.json").write_text(
                json.dumps(disp, indent=2), encoding="utf-8"
            )
            with mock.patch("workflow.runner._compile_pdfs"):
                with mock.patch(
                    "workflow.runner.verify_one",
                    return_value={
                        "submission": "acme",
                        "mechanically_verified": True,
                        "lint_all_clean": True,
                        "page_counts_ok": True,
                        "page_counts": {"Resume.pdf": 1, "CoverLetter.pdf": 1},
                    },
                ):
                    state = run_stage2_mech(
                        str(self.folder), load_state(str(self.folder)), compile_pdfs=False
                    )
        self.assertEqual(state["stages"]["stage2"]["subphases"]["mech"]["status"], "COMPLETE")

        with mock.patch(
            "workflow.runner.contracts.check_stage2_ready", return_value=(True, [])
        ):
            with mock.patch("workflow.runner._run_advisory_defect_scan") as scan:
                state = run_stage2_policy(str(self.folder), load_state(str(self.folder)))
        scan.assert_called_once()
        self.assertEqual(state["stages"]["stage2"]["status"], "COMPLETE")
        self.assertEqual(state["stages"]["stage3"]["status"], "READY")
        self.assertTrue((self.folder / "stage_receipts" / "stage2.json").exists())
        r2 = load_receipt(str(self.folder), "stage2")
        self.assertEqual(r2["status"], "COMPLETE")
        self.assertEqual(r2["issued_by"], ISSUED_BY)

    def test_advisory_defect_scan_warning_does_not_raise(self):
        from contextlib import redirect_stdout
        from io import StringIO

        from workflow.runner import _run_advisory_defect_scan

        buf = StringIO()
        with mock.patch(
            "scan_authoring_defects.run_advisory_scan",
            side_effect=RuntimeError("boom"),
        ):
            with redirect_stdout(buf):
                _run_advisory_defect_scan()
        self.assertIn("[defect_scan, status: warning] boom", buf.getvalue())


class Stage3FinalizeTests(unittest.TestCase):
    """CR-084: Stage 3 finalize receipt + terminal workflow status."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.folder = Path(self._tmpdir.name) / "acme"
        self.folder.mkdir()
        _write(self.folder, "Original_JD.txt", "Product Manager\n")
        _write(self.folder, "Resume.md", "# Name\n")
        _write(self.folder, "CoverLetter.md", "# Name\n")
        _write(self.folder, "verification_receipt.json", {"mechanically_verified": True})
        _write(self.folder, "stage0_fit_gate.json", _valid_stage0(company="Acme", role="Product Manager"))

    def _seed_stage2_complete(self, mode="production"):
        from workflow.invalidate import sha256_file
        from workflow.receipts import file_hash_map

        state = init_state(str(self.folder), mode=mode)
        write_state(str(self.folder), state)
        prior_id = None
        for stage, status in (("stage0", "COMPLETE"), ("stage1", "COMPLETE")):
            r = build_receipt(
                stage=stage,
                status=status,
                mode=mode,
                input_hashes={},
                output_hashes={"Resume.md": sha256_file(str(self.folder / "Resume.md"))},
                prior_receipt_id=prior_id,
            )
            commit_stage(
                str(self.folder),
                load_state(str(self.folder)),
                r,
                workflow_status="IN_PROGRESS",
                active_stage="stage2" if stage == "stage1" else "stage1",
            )
            prior_id = r["receipt_id"]
        out = file_hash_map(
            str(self.folder),
            ["Resume.md", "CoverLetter.md", "verification_receipt.json"],
        )
        r2 = build_receipt(
            stage="stage2",
            status="COMPLETE",
            mode=mode,
            input_hashes={},
            output_hashes=out,
            result={},
            checks={"contracts.check_stage2_ready": True},
            prior_receipt_id=prior_id,
        )
        state = commit_stage(
            str(self.folder),
            load_state(str(self.folder)),
            r2,
            workflow_status="IN_PROGRESS",
            active_stage="stage3",
        )
        state["stages"]["stage3"]["status"] = "READY"
        write_state(str(self.folder), state)
        return state

    def test_practice_finalize_no_db(self):
        from workflow.runner import run_stage3_finalize

        self._seed_stage2_complete(mode="practice")
        with mock.patch("workflow.runner.finalize_job") as fin:
            state = run_stage3_finalize(
                str(self.folder), load_state(str(self.folder))
            )
            fin.assert_not_called()
        self.assertEqual(state["status"], "PRACTICE_COMPLETE")
        r3 = load_receipt(str(self.folder), "stage3")
        self.assertEqual(r3["status"], "COMPLETE")
        self.assertEqual(r3["issued_by"], ISSUED_BY)
        ok, errors = contracts.check_workflow_complete(str(self.folder))
        self.assertFalse(ok)
        self.assertTrue(any("PRACTICE_COMPLETE" in e for e in errors))

    def test_production_finalize_writes_complete(self):
        from workflow.runner import run_stage3_finalize

        self._seed_stage2_complete(mode="production")
        with mock.patch(
            "workflow.runner.finalize_job", return_value="inserted: Acme (id=abcd)"
        ) as fin:
            state = run_stage3_finalize(
                str(self.folder), load_state(str(self.folder))
            )
            fin.assert_called_once()
            kwargs = fin.call_args.kwargs
            self.assertEqual(kwargs["company"], "Acme")
            self.assertEqual(kwargs["title"], "Product Manager")
            self.assertEqual(kwargs["slug"], "acme")
        self.assertEqual(state["status"], "COMPLETE")
        self.assertTrue((self.folder / "stage_receipts" / "stage3.json").exists())
        ok, errors = contracts.check_workflow_complete(str(self.folder))
        self.assertTrue(ok, errors)

    def test_override_integrity_sets_complete_with_override(self):
        from workflow.runner import run_stage3_finalize

        state = self._seed_stage2_complete(mode="production")
        state["stages"]["stage2"]["integrity"] = "OVERRIDDEN"
        write_state(str(self.folder), state)
        with mock.patch(
            "workflow.runner.finalize_job", return_value="updated: Acme"
        ):
            out = run_stage3_finalize(
                str(self.folder), load_state(str(self.folder))
            )
        self.assertEqual(out["status"], "COMPLETE_WITH_OVERRIDE")
        ok, _ = contracts.check_workflow_complete(str(self.folder))
        self.assertTrue(ok)

    def test_forged_receipt_id_fails_workflow_complete(self):
        """Invariant: COMPLETE with a tampered receipt_id is not workflow-complete."""
        from workflow.runner import run_stage3_finalize

        self._seed_stage2_complete(mode="production")
        with mock.patch(
            "workflow.runner.finalize_job", return_value="inserted: Acme"
        ):
            run_stage3_finalize(str(self.folder), load_state(str(self.folder)))
        ok, _ = contracts.check_workflow_complete(str(self.folder))
        self.assertTrue(ok)

        r3_path = self.folder / "stage_receipts" / "stage3.json"
        receipt = json.loads(r3_path.read_text(encoding="utf-8"))
        receipt["receipt_id"] = "stage3:" + ("0" * 64)
        r3_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        # Keep state pointer matching the forged id so the failure is the digest check
        state = load_state(str(self.folder))
        state["stages"]["stage3"]["receipt_id"] = receipt["receipt_id"]
        write_state(str(self.folder), state)

        ok, errors = contracts.check_workflow_complete(str(self.folder))
        self.assertFalse(ok)
        self.assertTrue(
            any("does not match receipt body" in e for e in errors),
            errors,
        )

    def test_stale_output_hash_fails_workflow_complete(self):
        """Invariant: editing a receipt-tracked output after COMPLETE demotes completeness."""
        from workflow.runner import run_stage3_finalize

        self._seed_stage2_complete(mode="production")
        with mock.patch(
            "workflow.runner.finalize_job", return_value="inserted: Acme"
        ):
            run_stage3_finalize(str(self.folder), load_state(str(self.folder)))
        ok, _ = contracts.check_workflow_complete(str(self.folder))
        self.assertTrue(ok)

        _write(self.folder, "Resume.md", "# Name\nedited after complete\n")
        ok, errors = contracts.check_workflow_complete(str(self.folder))
        self.assertFalse(ok)
        self.assertTrue(any("hash mismatch" in e for e in errors), errors)

    def test_mode_mismatch_refuses_without_force(self):
        from workflow.runner import run_until_waiting_for_llm

        state = init_state(str(self.folder), mode="production")
        write_state(str(self.folder), state)
        with self.assertRaises(WorkflowError) as ctx:
            run_until_waiting_for_llm(
                str(self.folder), mode="practice", adopt=False, no_hook=True
            )
        self.assertIn("workflow mode is 'production'", str(ctx.exception))
        self.assertIn("practice", str(ctx.exception))

    def test_mode_mismatch_rewrites_with_force(self):
        from workflow.runner import run_until_waiting_for_llm

        state = init_state(str(self.folder), mode="production")
        write_state(str(self.folder), state)
        # Force rewrite, then stop early — Original_JD may be missing so Stage 0
        # can fail; we only assert mode was rewritten before that. This test doesn't
        # mock build_stage0_fit_gate (unlike the rest of this file) and doesn't care what
        # Stage 0 actually extracts, only that `mode` got rewritten first — so it must
        # force the regex extractor rather than let it reach the real NLP path, which
        # would make a real Groq/Gemini call and write real rows to
        # data/training_data_feedback.csv (CR-105 -- found via a real polluted test run).
        with mock.patch.dict(os.environ, {"STAGE0_SECTION_MODE": "deterministic"}):
            try:
                run_until_waiting_for_llm(
                    str(self.folder),
                    mode="practice",
                    adopt=False,
                    force=True,
                    no_hook=True,
                )
            except WorkflowError:
                pass
        reloaded = load_state(str(self.folder))
        self.assertEqual(reloaded.get("mode"), "practice")


class EndToEndChainIntegrityTests(unittest.TestCase):
    """Verify check_workflow_complete returns True for a workflow produced
    by the actual run_stage1_validate code path (not the manual _seed helper).

    Found 2026-08-30: 6 of 12 real COMPLETE submissions failed
    check_workflow_complete because run_stage1_validate set Stage 1's
    prior_receipt_id to the WAITING receipt's ID instead of Stage 0's.
    The existing Stage 3 tests used _seed_stage2_complete which manually
    built the correct chain, bypassing run_stage1_validate entirely.
    """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.folder = Path(self._tmpdir.name) / "acme"
        self.folder.mkdir()
        _write(self.folder, "Original_JD.txt", "Product Manager\n\n## Requirements\n- Own roadmap\n")
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

    def _reach_waiting(self):
        def fake_build_packet(folder, no_hook=True):
            return self.packet

        def fake_prompt(folder, force=False):
            return ("# prompt\n", {"company": "Acme", "total_estimated_tokens": 10})

        with mock.patch("workflow.runner.build_stage0_fit_gate", return_value=self.gate):
            with mock.patch("workflow.runner.build_packet", side_effect=fake_build_packet):
                with mock.patch("workflow.runner.build_authoring_prompt", side_effect=fake_prompt):
                    with mock.patch("workflow.runner.require_stage_ready"):
                        return run_until_waiting_for_llm(
                            str(self.folder),
                            mode="production",
                            adopt=False,
                            no_hook=True,
                        )

    def test_check_workflow_complete_passes_after_actual_stage1_validate(self):
        """The full Stage 0 → Stage 1 validate path must produce a receipt
        chain that check_workflow_complete accepts (Stage 1 prior = Stage 0)."""
        from workflow.invalidate import sha256_file
        from workflow.receipts import file_hash_map
        from workflow.runner import run_stage1_validate, run_stage3_finalize
        from workflow.reviews import default_stage2_subphases

        self._reach_waiting()
        _write(self.folder, "Resume.md", "# Name\n\n## PROFESSIONAL SUMMARY\nOne. Two. Three.\n")
        _write(self.folder, "CoverLetter.md", "# Name\n\nDear Hiring Manager,\n\nBody.\n\nBest regards,\n\nName\n")
        _write(self.folder, "claim_provenance.json", {"claims": []})

        with mock.patch("workflow.runner.run_verify_only", return_value=True):
            state = run_stage1_validate(str(self.folder), load_state(str(self.folder)))

        # Stage 1 should be COMPLETE with prior = Stage 0
        r1 = load_receipt(str(self.folder), "stage1")
        r0 = load_receipt(str(self.folder), "stage0")
        self.assertEqual(r1["prior_receipt_id"], r0["receipt_id"])

        # Seed Stage 2 COMPLETE using the actual Stage 1 receipt (not manual)
        out = file_hash_map(
            str(self.folder),
            ["Resume.md", "CoverLetter.md", "verification_receipt.json"],
        )
        r2 = build_receipt(
            stage="stage2",
            status="COMPLETE",
            mode="production",
            input_hashes={},
            output_hashes=out,
            result={},
            checks={"contracts.check_stage2_ready": True},
            prior_receipt_id=r1["receipt_id"],
        )
        state = commit_stage(
            str(self.folder),
            load_state(str(self.folder)),
            r2,
            workflow_status="IN_PROGRESS",
            active_stage="stage3",
        )
        state["stages"]["stage2"]["subphases"] = default_stage2_subphases()
        for sub in state["stages"]["stage2"]["subphases"].values():
            if isinstance(sub, dict):
                sub["status"] = "COMPLETE"
        state["stages"]["stage3"]["status"] = "READY"
        write_state(str(self.folder), state)

        # Finalize
        with mock.patch(
            "workflow.runner.finalize_job", return_value="inserted: Acme (id=abcd)"
        ):
            run_stage3_finalize(str(self.folder), load_state(str(self.folder)))

        # The authoritative DONE oracle must pass
        ok, errors = contracts.check_workflow_complete(str(self.folder))
        self.assertTrue(ok, f"check_workflow_complete failed: {errors}")

    def test_reconcile_detects_broken_chain_after_stage0_rerun(self):
        """reconcile should mark Stage 1 STALE when Stage 0 is re-run
        (new receipt_id) after Stage 1 was already COMPLETE — the chain
        is broken even if file hashes still match."""
        from workflow.invalidate import sha256_file

        self._reach_waiting()
        _write(self.folder, "Resume.md", "# Name\nv1\n")
        _write(self.folder, "CoverLetter.md", "# Name\nletter\n")
        _write(self.folder, "claim_provenance.json", {"claims": []})
        with mock.patch("workflow.runner.run_verify_only", return_value=True):
            run_stage1_validate(str(self.folder), load_state(str(self.folder)))

        r0_old = load_receipt(str(self.folder), "stage0")
        r1 = load_receipt(str(self.folder), "stage1")
        self.assertEqual(r1["prior_receipt_id"], r0_old["receipt_id"])

        # Simulate a Stage 0 re-run: write a new Stage 0 receipt with a
        # different receipt_id but same output_hashes (file content unchanged).
        new_r0 = build_receipt(
            stage="stage0",
            status="COMPLETE",
            mode="production",
            input_hashes=file_hash_map(str(self.folder), ["Original_JD.txt"]) if False else {},
            output_hashes={"stage0_fit_gate.json": sha256_file(str(self.folder / "stage0_fit_gate.json"))},
            result={"tier": "Tier 1", "decision": "PASS", "reasons": []},
            checks={"contracts.check_stage0_fit_gate": True, "policy.evaluate_stage0": "PASS"},
        )
        write_receipt(str(self.folder), new_r0)
        state = load_state(str(self.folder))
        state["stages"]["stage0"]["receipt_id"] = new_r0["receipt_id"]
        write_state(str(self.folder), state)

        # Reconcile should detect the broken chain (Stage 1's prior != new Stage 0)
        new_state, reasons = reconcile_state_against_receipts(
            str(self.folder), state, load_receipt
        )
        self.assertTrue(reasons, f"Expected chain-break reasons, got: {reasons}")
        self.assertEqual(new_state["stages"]["stage1"]["status"], "STALE")
        self.assertEqual(new_state["status"], "STALE")


if __name__ == "__main__":
    unittest.main()
