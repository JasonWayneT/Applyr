#!/usr/bin/env python3
"""
Unified test runner for Applyr.
Runs both the Python unit/regression test scripts and the Vitest TypeScript test suite.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from typing import List, Tuple

PYTHON_TEST_SCRIPTS = [
    "scripts/audit_public_repo.py",
    "scripts/check_spawn_paths.py",
    "scripts/test_applyr_python.py",
    "scripts/smoke_draft_compiler.py",
    "scripts/test_blocked_companies.py",
    "scripts/test_candidate_context.py",
    "scripts/test_contracts.py",
    "scripts/test_stage_gate.py",
    "scripts/test_workflow_authority.py",
    "scripts/test_check_submission_status.py",
    "scripts/test_build_stage0_fit_gate.py",
    "scripts/test_stage0_model_handoff.py",
    "scripts/test_stage0_skip_ledger.py",
    "scripts/test_build_authoring_packet.py",
    "scripts/test_playwright_env.py",
    "scripts/test_audit_claims_coverage.py",
    "scripts/test_we_acc_index.py",
    "scripts/test_claim_provenance.py",
    "scripts/test_context_pack.py",
    "scripts/test_author_from_packet.py",
    "scripts/test_submission_linter.py",
    "scripts/test_scan_authoring_defects.py",
    "scripts/test_import_historical_defects.py",
    "scripts/test_cover_voice.py",
    "scripts/test_critique_retry.py",
    "scripts/test_domain_gate.py",
    "scripts/test_experience_theme_guard.py",
    "scripts/test_prefs_rollout.py",
    "scripts/test_location_gate.py",
    "scripts/test_resume_conversion_eval.py",
    "scripts/test_seniority_years_gate.py",
    "scripts/test_template_lint_sources.py",
    "scripts/test_title_blocklist.py",
    "scripts/test_smoke_regression.py",
    "scripts/test_solo_pm_gate.py",
    "scripts/test_verify_chain.py",
    "scripts/verify_master_claims.py",
]


def get_subprocess_env() -> dict[str, str]:
    """
    Get environment variables for subprocesses with UTF-8 encoding forced.
    
    Returns:
        dict[str, str]: A copy of the current environment with PYTHONIOENCODING set to utf-8.
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_python_test(script_path: str, verbose: bool) -> Tuple[bool, float, str]:
    """Run a single python test script and return (passed, duration, output)."""
    start_time = time.time()
    try:
        args: List[str] = []
        if "verify_master_claims.py" in script_path:
            args = ["data/master_claims.example.json", "data/workExperience.example.md"]
        result = subprocess.run(
            [sys.executable, script_path] + args,
            capture_output=True,
            text=True,
            errors="replace",
            env=get_subprocess_env(),
            timeout=180,
        )
        duration = time.time() - start_time
        passed = result.returncode == 0
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        return passed, duration, output
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return False, duration, "TEST TIMED OUT (180s)"
    except Exception as e:
        duration = time.time() - start_time
        return False, duration, f"ERROR EXECUTING TEST: {e}"


def run_vitest_suite(verbose: bool) -> Tuple[bool, float, str]:
    """Run the vitest test suite via npm/npx and return (passed, duration, output)."""
    start_time = time.time()
    try:
        cmd = "npx vitest run"
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            errors="replace",
            env=get_subprocess_env(),
            timeout=300,
        )
        duration = time.time() - start_time
        passed = result.returncode == 0
        output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        return passed, duration, output
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return False, duration, "VITEST SUITE TIMED OUT (300s)"
    except Exception as e:
        duration = time.time() - start_time
        return False, duration, f"ERROR EXECUTING VITEST: {e}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Applyr Python and Vitest test suites.")
    parser.add_argument("--python-only", action="store_true", help="Only run the Python test suite.")
    parser.add_argument("--vitest-only", action="store_true", help="Only run the Vitest test suite.")
    parser.add_argument("--verbose", action="store_true", help="Print detailed outputs for all tests.")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    # Bootstrap data files if missing (required in fresh clones like CI)
    sys.path.insert(0, os.path.join(project_root, "scripts"))
    try:
        import bootstrap_local_data
        bootstrap_local_data.main()
    except Exception as e:
        print(f"Warning: Failed to bootstrap local data: {e}", file=sys.stderr)

    print("==================================================================")
    print("  APPLYR UNIFIED TEST RUNNER")
    print("==================================================================")

    run_python = not args.vitest_only
    run_vitest = not args.python_only

    results: List[Tuple[str, str, bool, float, str]] = []
    overall_passed = True

    # 1. Run Python Tests
    if run_python:
        print("\n--- Running Python Test Suite ---")
        for script in PYTHON_TEST_SCRIPTS:
            print(f"Running {script}...", end="", flush=True)
            passed, duration, output = run_python_test(script, args.verbose)
            status = "PASS" if passed else "FAIL"
            print(f" {status} ({duration:.2f}s)")
            results.append(("Python", script, passed, duration, output))
            if not passed:
                overall_passed = False
                if not args.verbose:
                    print("-" * 50)
                    print(f"Failure Details for {script}:")
                    print(output)
                    print("-" * 50)

    # 2. Run Vitest Suite
    if run_vitest:
        print("\n--- Running Vitest Test Suite ---")
        print("Running npx vitest run...", end="", flush=True)
        passed, duration, output = run_vitest_suite(args.verbose)
        status = "PASS" if passed else "FAIL"
        print(f" {status} ({duration:.2f}s)")
        results.append(("Vitest", "TypeScript Suite", passed, duration, output))
        if not passed:
            overall_passed = False
            if not args.verbose:
                print("-" * 50)
                print("Failure Details for Vitest Suite:")
                print(output)
                print("-" * 50)

    # 3. Print Dashboard Summary
    print("\n" + "=" * 66)
    print("  TEST SUITE SUMMARY DASHBOARD")
    print("=" * 66)
    print(f"{'Suite':<8} | {'Test Name / Script':<40} | {'Status':<6} | {'Time':<6}")
    print("-" * 66)
    
    total_time = 0.0
    passed_count = 0
    failed_count = 0

    for suite, name, passed, duration, _ in results:
        status_str = "PASS" if passed else "FAIL"
        total_time += duration
        if passed:
            passed_count += 1
        else:
            failed_count += 1
        
        display_name = name
        if len(display_name) > 40:
            display_name = display_name[:37] + "..."
            
        print(f"{suite:<8} | {display_name:<40} | {status_str:<6} | {duration:>5.2f}s")
        
    print("-" * 66)
    overall_status = "SUCCESS" if overall_passed else "FAILURE"
    print(f"OVERALL RESULT: {overall_status}")
    print(f"Stats: {passed_count} passed, {failed_count} failed, Total Time: {total_time:.2f}s")
    print("=" * 66)

    return 0 if overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())
