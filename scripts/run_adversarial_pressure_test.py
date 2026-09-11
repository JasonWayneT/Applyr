#!/usr/bin/env python3
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path
from unittest import mock

# Ensure scripts directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import contracts
from workflow import runner
from workflow import state as wf_state
from workflow import receipts as wf_receipts

# --- INVARIANT ASSERTIONS ---

def assert_invariant(condition: bool, invariant_id: str, message: str):
    if not condition:
        raise AssertionError(f"Invariant Violation [{invariant_id}]: {message}")

def expect_workflow_error(fn, *, must_contain: str, invariant_id: str, context: str):
    """CR-112 Story 4.3: the named invariant must fire, not any WorkflowError."""
    try:
        fn()
    except runner.WorkflowError as exc:
        msg = str(exc)
        assert_invariant(
            must_contain in msg,
            invariant_id,
            f"{context}: expected {must_contain!r} in {msg!r}",
        )
        return
    assert_invariant(False, invariant_id, f"{context}: no WorkflowError raised")


def check_state_001_downstream_no_receipt(folder: Path):
    """STATE-001: Downstream stages MUST NOT execute without valid, COMPLETE upstream receipts."""
    state = wf_state.load_state(str(folder))
    expect_workflow_error(
        lambda: runner.run_stage1_validate(str(folder), state),
        must_contain="Stage 0 receipt missing",
        invariant_id="STATE-001",
        context="missing Stage 0 receipt",
    )


def check_state_001_negative_has_receipt(folder: Path):
    """Negative control: with a Stage 0 receipt, STATE-001's specific error must not fire."""
    state = wf_state.load_state(str(folder))
    try:
        runner.run_stage1_validate(str(folder), state)
    except runner.WorkflowError as exc:
        assert_invariant(
            "Stage 0 receipt missing" not in str(exc),
            "STATE-001",
            f"Stage 0 is complete but STATE-001 message still fired: {exc}",
        )
        return
    # Validate may succeed on a healthy folder; that is also a valid negative.

def check_state_002_skip_halts(folder: Path):
    """STATE-002: A Stage 0 policy SKIP MUST permanently halt the execution pipeline."""
    state = wf_state.load_state(str(folder))
    assert_invariant(state["status"] == "SKIPPED", "STATE-002", "State is not SKIPPED")
    try:
        runner.run_until_waiting_for_llm(str(folder), mode="production", adopt=True, no_hook=True)
    except runner.WorkflowError:
        pass
    
    # Assert still skipped
    state = wf_state.load_state(str(folder))
    assert_invariant(state["status"] == "SKIPPED", "STATE-002", "State transitioned out of SKIPPED")

def check_state_003_hash_stale(folder: Path):
    """STATE-003: If any file hash diverges from the output_hashes recorded in its receipt, the workflow MUST transition to STALE."""
    state = wf_state.load_state(str(folder))
    new_state, reasons = runner.reconcile_state_against_receipts(str(folder), state, wf_receipts.load_receipt)
    assert_invariant(new_state["status"] == "STALE", "STATE-003", f"Workflow did not transition to STALE, status is {new_state['status']}")

def check_state_004_incomplete_fails_check(folder: Path):
    """STATE-004: An execution with a FAILED, STALE, or WAITING_* status MUST NOT pass check_workflow_complete."""
    ok, errors = contracts.check_workflow_complete(str(folder))
    assert_invariant(not ok, "STATE-004", "check_workflow_complete returned True for incomplete workflow")


def check_state_004_complete_with_chained_receipts(folder: Path):
    """STATE-004 inverse: real chained receipts must make check_workflow_complete True.

    Does not mock contracts.check_workflow_complete. Implements FR-308 / AC-405.
    """
    ok, errors = contracts.check_workflow_complete(str(folder))
    assert_invariant(
        ok,
        "STATE-004",
        f"chained COMPLETE receipts must pass check_workflow_complete: {errors}",
    )

def check_doc_001_resume_sections(folder: Path):
    """DOC-001: Resume.md MUST contain exactly the required sections in the required order."""
    ok, _ = contracts.check_stage1_ready(str(folder))
    assert_invariant(not ok, "DOC-001", "Stage 1 ready check passed despite missing resume sections")

def check_truth_001_hallucinated_claims(folder: Path):
    """TRUTH-001: All claim IDs referenced in claim_provenance.json MUST exist in the verified workExperience.md corpus."""
    import claim_provenance
    ok, reasons = claim_provenance.check_claim_provenance(str(folder))
    assert_invariant(not ok, "TRUTH-001", "Claim provenance check passed despite hallucinated claims")

def check_doc_003_forbidden_punctuation(folder: Path):
    """DOC-003: Resume.md MUST NOT contain LR-014/LR-015. Assert the linter
    invariant directly; do not treat an unrelated WorkflowError as coverage.
    """
    import submission_linter

    resume = (folder / "Resume.md").read_text(encoding="utf-8")
    result = submission_linter.lint_document(resume, doc_type="resume", filename="Resume.md")
    punct = [b for b in result.blocks if getattr(b, "rule_id", "") in ("LR-014", "LR-015")]
    assert_invariant(
        len(punct) > 0,
        "DOC-003",
        "Linter did not emit LR-014/LR-015 on the forbidden-punctuation resume",
    )


def check_doc_003_negative_clean_punctuation(folder: Path):
    """Negative control: a resume without LR-014/LR-015 must not trip DOC-003."""
    import submission_linter

    resume = (folder / "Resume.md").read_text(encoding="utf-8")
    result = submission_linter.lint_document(resume, doc_type="resume", filename="Resume.md")
    punct = [b for b in result.blocks if getattr(b, "rule_id", "") in ("LR-014", "LR-015")]
    assert_invariant(
        len(punct) == 0,
        "DOC-003",
        f"Clean resume still flagged punctuation: {punct}",
    )

# --- CORPUS SETUP ---

def get_valid_stage0_data():
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
    return data

def create_valid_stage0(folder: Path):
    data = get_valid_stage0_data()
    (folder / "stage0_fit_gate.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (folder / "Original_JD.txt").write_text("Product Manager\nRequirements:\n- Own roadmap", encoding="utf-8")

def create_valid_stage1_output(folder: Path):
    (folder / "Resume.md").write_text("# Name\n[contact line]\n\n## PROFESSIONAL SUMMARY\nOne. Two. Three.\n\n## PROFESSIONAL EXPERIENCE\n### Title | Company | 2020 - Present\nLocation\n* Did a thing\n\n## EDUCATION\nBS\n", encoding="utf-8")
    (folder / "CoverLetter.md").write_text("# Name\n\nDear Hiring Manager,\n\nBody.\n\nBest regards,\n\nName\n", encoding="utf-8")
    (folder / "claim_provenance.json").write_text('{"company": "TestCo", "resume_claims": [], "cover_letter_claims": []}', encoding="utf-8")

# --- TEST CASES ---

def case_stale_hash(folder: Path):
    create_valid_stage0(folder)
    state = runner.init_state(str(folder), mode="production")
    runner.write_state(str(folder), state)
    
    with mock.patch("workflow.runner.build_stage0_fit_gate", return_value=get_valid_stage0_data()):
        runner.run_stage0(str(folder), state)
    
    # Mutate a file after receipt is issued
    (folder / "stage0_fit_gate.json").write_text(json.dumps({"company": "Hacked"}), encoding="utf-8")
    
    return lambda: check_state_003_hash_stale(folder)

def case_downstream_no_receipt(folder: Path):
    create_valid_stage0(folder)
    create_valid_stage1_output(folder)
    (folder / "authoring_packet.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "company": "TestCo",
                "role_title": "Product Manager",
                "slug": "testco",
                "packet_status": "ready",
                "incomplete_reasons": [],
            }
        ),
        encoding="utf-8",
    )
    state = runner.init_state(str(folder), mode="production")
    state["status"] = "IN_PROGRESS"
    state["active_stage"] = "stage1"
    runner.write_state(str(folder), state)

    # Stage 0 is incomplete, receipt missing. Docs + ready packet are present so
    # validate reaches the named STATE-001 error instead of an earlier docs miss.
    return lambda: check_state_001_downstream_no_receipt(folder)

def case_skip_halts(folder: Path):
    create_valid_stage0(folder)
    data = json.loads((folder / "stage0_fit_gate.json").read_text(encoding="utf-8"))
    data["decision"] = "SKIP"
    data["tier"] = "Skip"
    data["skip_reason"] = "Just because"
    (folder / "stage0_fit_gate.json").write_text(json.dumps(data), encoding="utf-8")
    
    
    state = runner.init_state(str(folder), mode="production")
    runner.write_state(str(folder), state)
    with mock.patch("workflow.runner.build_stage0_fit_gate", return_value=data):
        runner.run_stage0(str(folder), state)
    
    return lambda: check_state_002_skip_halts(folder)

def case_missing_resume_section(folder: Path):
    create_valid_stage0(folder)
    state = runner.init_state(str(folder), mode="production")
    runner.write_state(str(folder), state)
    with mock.patch("workflow.runner.build_stage0_fit_gate", return_value=get_valid_stage0_data()):
        runner.run_stage0(str(folder), state)
    
    create_valid_stage1_output(folder)
    # Break the resume
    (folder / "Resume.md").write_text("# Name\nMissing sections here\n", encoding="utf-8")
    
    return lambda: check_doc_001_resume_sections(folder)

def case_hallucinated_claim(folder: Path):
    create_valid_stage0(folder)
    state = runner.init_state(str(folder), mode="production")
    runner.write_state(str(folder), state)
    with mock.patch("workflow.runner.build_stage0_fit_gate", return_value=get_valid_stage0_data()):
        runner.run_stage0(str(folder), state)
    
    create_valid_stage1_output(folder)
    # Add fake claim
    (folder / "claim_provenance.json").write_text('{"company": "TestCo", "resume_claims": [{"bullet": "x", "claim_ids": ["FAKE-999"]}], "cover_letter_claims": []}', encoding="utf-8")
    
    return lambda: check_truth_001_hallucinated_claims(folder)

def case_forbidden_punctuation(folder: Path):
    create_valid_stage0(folder)
    state = runner.init_state(str(folder), mode="production")
    runner.write_state(str(folder), state)
    with mock.patch("workflow.runner.build_stage0_fit_gate", return_value=get_valid_stage0_data()):
        runner.run_stage0(str(folder), state)
    
    create_valid_stage1_output(folder)
    # Break punctuation (LR-014 semicolon and LR-015 colon whitespace letter)
    (folder / "Resume.md").write_text("# Name\n[contact line]\n\n## PROFESSIONAL SUMMARY\nOne; Two. Three: bad.\n\n## PROFESSIONAL EXPERIENCE\n### Title | Company | 2020 - Present\nLocation\n* Did a thing\n\n## EDUCATION\nBS\n", encoding="utf-8")
    
    return lambda: check_doc_003_forbidden_punctuation(folder)


def case_state_001_negative(folder: Path):
    """Negative control: Stage 0 receipt present, STATE-001's missing-receipt error must not fire."""
    create_valid_stage0(folder)
    state = runner.init_state(str(folder), mode="production")
    runner.write_state(str(folder), state)
    with mock.patch("workflow.runner.build_stage0_fit_gate", return_value=get_valid_stage0_data()):
        runner.run_stage0(str(folder), state)
    create_valid_stage1_output(folder)
    return lambda: check_state_001_negative_has_receipt(folder)


def case_doc_003_negative(folder: Path):
    """Negative control: clean punctuation must not trip LR-014/LR-015."""
    create_valid_stage0(folder)
    create_valid_stage1_output(folder)
    return lambda: check_doc_003_negative_clean_punctuation(folder)


def case_state_004_incomplete(folder: Path):
    create_valid_stage0(folder)
    state = runner.init_state(str(folder), mode="production")
    state["status"] = "WAITING_FOR_LLM"
    runner.write_state(str(folder), state)
    return lambda: check_state_004_incomplete_fails_check(folder)


def case_state_004_complete(folder: Path):
    """Build a real receipt chain, then assert STATE-004 inverse without mocking the oracle."""
    from workflow.invalidate import sha256_file
    from workflow.receipts import build_receipt, commit_stage, file_hash_map, write_state
    from workflow.runner import run_stage3_finalize
    from workflow.state import load_state

    create_valid_stage0(folder)
    create_valid_stage1_output(folder)
    (folder / "verification_receipt.json").write_text(
        json.dumps({"mechanically_verified": True}), encoding="utf-8"
    )
    state = runner.init_state(str(folder), mode="production")
    runner.write_state(str(folder), state)
    prior_id = None
    for stage in ("stage0", "stage1"):
        r = build_receipt(
            stage=stage,
            status="COMPLETE",
            mode="production",
            input_hashes={},
            output_hashes={"Resume.md": sha256_file(str(folder / "Resume.md"))},
            prior_receipt_id=prior_id,
        )
        commit_stage(
            str(folder),
            load_state(str(folder)),
            r,
            workflow_status="IN_PROGRESS",
            active_stage="stage2" if stage == "stage1" else "stage1",
        )
        prior_id = r["receipt_id"]
    out = file_hash_map(
        str(folder),
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
        prior_receipt_id=prior_id,
    )
    state = commit_stage(
        str(folder),
        load_state(str(folder)),
        r2,
        workflow_status="IN_PROGRESS",
        active_stage="stage3",
    )
    state["stages"]["stage3"]["status"] = "READY"
    write_state(str(folder), state)
    with mock.patch(
        "workflow.runner.finalize_job", return_value="inserted: TestCo (id=eval)"
    ):
        run_stage3_finalize(str(folder), load_state(str(folder)))
    return lambda: check_state_004_complete_with_chained_receipts(folder)


# --- RUNNER LOGIC ---

# Audited programmatic checks (CR-112 Story 4.3 / FR-309):
# - STATE-001: named substring "Stage 0 receipt missing" + negative control.
# - DOC-003: linter LR-014/LR-015 directly + negative control.
# - STATE-003: production reconcile, not a bare WorkflowError.
# - STATE-004: incomplete False, chained receipts True; oracle not mocked.
# - STATE-002: asserts SKIPPED lock via status after the call; does not treat
#   a bare WorkflowError as proof of the skip invariant.
# - DOC-001 / TRUTH-001: production checkers, not WorkflowError catch-alls.

CASES = {
    "case_stale_hash": case_stale_hash,
    "case_downstream_no_receipt": case_downstream_no_receipt,
    "case_skip_halts": case_skip_halts,
    "case_missing_resume_section": case_missing_resume_section,
    "case_hallucinated_claim": case_hallucinated_claim,
    "case_forbidden_punctuation": case_forbidden_punctuation,
    "case_state_001_negative": case_state_001_negative,
    "case_doc_003_negative": case_doc_003_negative,
    "case_state_004_incomplete": case_state_004_incomplete,
    "case_state_004_complete": case_state_004_complete,
}

FIXTURE_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "adversarial" / "workflow_cases"

FIXTURE_SKIP_COVERED_BY_PROGRAMMATIC = {
    "case_stale_hash": "STATE-003 covered by programmatic case_stale_hash",
}


def run_fixture_case(case_dir: Path) -> dict:
    """Fail closed on unknown fixture names. Implements FR-307 / AC-404."""
    meta_file = case_dir / "case_meta.json"
    if not meta_file.exists():
        return None
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    name = meta["name"]
    inv_id = meta.get("invariant_id", "UNKNOWN")

    if name in FIXTURE_SKIP_COVERED_BY_PROGRAMMATIC:
        return {
            "case": name,
            "invariant_id": inv_id,
            "status": "SKIPPED",
            "reason": FIXTURE_SKIP_COVERED_BY_PROGRAMMATIC[name],
        }

    if name == "case_missing_resume_section":
        resume_file = case_dir / "Resume.md"
        content = resume_file.read_text(encoding="utf-8")
        is_valid_structure = "## EDUCATION" in content and "## PROFESSIONAL SUMMARY" in content and "## PROFESSIONAL EXPERIENCE" in content
        assert_invariant(not is_valid_structure, inv_id, "Resume structure check passed despite missing EDUCATION section")
    elif name == "case_forbidden_punctuation":
        # Fixture-tier smoke only: any hard block is enough. Programmatic
        # case_doc_003_negative / check_doc_003_forbidden_punctuation are the
        # authoritative LR-014/LR-015 coverage.
        resume_file = case_dir / "Resume.md"
        content = resume_file.read_text(encoding="utf-8")
        import submission_linter
        res = submission_linter.lint_document(content, doc_type="resume")
        hard_blocks = res.blocks
        assert_invariant(len(hard_blocks) > 0, inv_id, "Linter failed to flag LR-014 or LR-015 forbidden punctuation violations")
    elif name == "case_hallucinated_claim":
        prov_file = case_dir / "claim_provenance.json"
        prov_data = json.loads(prov_file.read_text(encoding="utf-8"))
        import claim_provenance
        valid_claims, _ = claim_provenance.load_valid_claim_ids()
        fake_claims = [c for item in prov_data.get("resume_claims", []) for c in item.get("claim_ids", []) if c not in valid_claims]
        assert_invariant(len(fake_claims) > 0, inv_id, "Claim validation failed to catch fake claim IDs")
    else:
        assert_invariant(
            False,
            inv_id,
            f"unhandled fixture name {name!r} — fail closed, never PASS",
        )
    return {"case": name, "invariant_id": inv_id, "status": "PASS"}

def main():
    json_output = "--json" in sys.argv
    if not json_output:
        print(f"Running Adversarial Pressure Test (Programmatic Cases: {len(CASES)})")
        print("-" * 80)
    
    results = []
    
    with tempfile.TemporaryDirectory() as tmpdir:
        for name, setup_fn in CASES.items():
            test_folder = Path(tmpdir) / name
            test_folder.mkdir()
            
            try:
                # Setup
                assert_fn = setup_fn(test_folder)
                # Execute
                assert_fn()
                
                if not json_output:
                    print(f"PASS: {name}")
                results.append({"case": name, "status": "PASS"})
            except AssertionError as e:
                if not json_output:
                    print(f"FAIL: {name} - {str(e)}")
                results.append({"case": name, "status": "FAIL", "error": str(e)})
            except Exception as e:
                if not json_output:
                    print(f"ERROR: {name} - Unexpected exception: {str(e)}")
                    traceback.print_exc()
                results.append({"case": name, "status": "ERROR", "error": str(e)})

    # Also run file-based fixtures
    if FIXTURE_DIR.exists():
        for case_dir in FIXTURE_DIR.iterdir():
            if not case_dir.is_dir():
                continue
            try:
                res = run_fixture_case(case_dir)
                if not res:
                    if not json_output:
                        print(f"SKIP [Fixture]: {case_dir.name} (no case_meta.json, not counted as pass)")
                    continue
                status = res.get("status", "ERROR")
                if status == "SKIPPED":
                    if not json_output:
                        print(f"SKIP [Fixture]: {case_dir.name} ({res.get('reason')})")
                    results.append(res)
                elif status == "PASS":
                    if not json_output:
                        print(f"PASS [Fixture]: {case_dir.name} ({res['invariant_id']})")
                    results.append(res)
                else:
                    if not json_output:
                        print(f"{status} [Fixture]: {case_dir.name}")
                    results.append(res)
            except AssertionError as e:
                if not json_output:
                    print(f"FAIL [Fixture]: {case_dir.name} - {str(e)}")
                results.append({"case": case_dir.name, "status": "FAIL", "error": str(e)})
            except Exception as e:
                if not json_output:
                    print(f"ERROR [Fixture]: {case_dir.name} - {str(e)}")
                results.append({"case": case_dir.name, "status": "ERROR", "error": str(e)})
                
    counted = [r for r in results if r.get("status") != "SKIPPED"]
    passes = sum(1 for r in counted if r["status"] == "PASS")
    failures = [r for r in counted if r["status"] in ("FAIL", "ERROR")]
    total = len(counted)

    if json_output:
        print(json.dumps({"total": total, "passed": passes, "skipped": len(results) - total, "results": results}, indent=2))
    else:
        print("-" * 80)
        print(f"Results: {passes}/{total} passed ({len(failures)} fail/error, SKIPPED excluded)")
    
    if failures:
        sys.exit(1)

if __name__ == "__main__":
    main()

