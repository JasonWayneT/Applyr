#!/usr/bin/env python3
"""
Authoritative submission workflow CLI (CR-076 → CR-084).

Agents perform work. This script (via scripts/workflow/) determines workflow state
and is the sole writer of workflow_state.json + stage_receipts/*.json.

Stage 3 finalize is explicit: pass --finalize (uses stage0 company/role unless overridden).
Practice mode --finalize writes PRACTICE_COMPLETE without DB writes.

Usage:
  python scripts/run_submission.py data/submissions/{slug}
  python scripts/run_submission.py {slug} --mode production|practice
  python scripts/run_submission.py {slug} --status
  python scripts/run_submission.py {slug} --adopt-only
  python scripts/run_submission.py {slug} --resume
  python scripts/run_submission.py {slug} --stop-at-waiting
  python scripts/run_submission.py {slug} --stop-after-stage1
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

import contracts  # noqa: E402
from workflow.runner import (  # noqa: E402
    WorkflowError,
    _resolve_folder,
    adopt_existing,
    run_stage3_finalize,
    run_until_stage1_complete,
    run_until_truth_settled,
    run_until_waiting_for_llm,
)
from workflow.state import load_state  # noqa: E402
from workflow.observability import read_events  # noqa: E402


def _fmt_duration(seconds) -> str:
    if seconds is None:
        return ""
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{seconds / 60:.0f}m"


def _print_console_summary(folder: str, before_count: int) -> None:
    """Epic D — the compact per-stage line from the observability design doc's §5.1. Reads back
    whatever this invocation just appended to run_events.jsonl rather than duplicating any
    stage-specific formatting logic here; every event's own fields already carry what matters."""
    events = read_events(folder)[before_count:]
    for e in events:
        stage = e.get("stage", "?")
        kind = e.get("event", "?")
        dur = _fmt_duration(e.get("duration_seconds"))
        bits = []
        for key in ("tier", "fit_score", "confidence_score", "extraction_source", "verify_attempts", "integrity", "workflow_status"):
            if e.get(key) is not None:
                bits.append(f"{key}={e[key]}")
        if e.get("findings_by_severity"):
            fs = e["findings_by_severity"]
            bits.append("findings=" + ",".join(f"{k}:{v}" for k, v in fs.items()))
        detail = "  ".join(bits)
        line = f"Stage {stage:<14} {kind:<17} {dur:>6}  {detail}".rstrip()
        enc = sys.stdout.encoding or "utf-8"
        print(line.encode(enc, errors="replace").decode(enc, errors="replace"))


def _print_status(folder: str) -> int:
    folder = _resolve_folder(folder)
    state = load_state(folder)
    complete, errors = contracts.check_workflow_complete(folder)
    print(f"folder: {folder}")
    if state is None:
        print("workflow_state: missing")
    else:
        print(f"status: {state.get('status')}")
        print(f"mode: {state.get('mode')}")
        print(f"active_stage: {state.get('active_stage')}")
        print(json.dumps(state.get("stages"), indent=2))
    print(f"check_workflow_complete: {'YES' if complete else 'NO'}")
    for e in errors:
        print(f"  - {e}")
    terminal = (
        "WAITING_FOR_LLM",
        "NEEDS_DISPOSITION",
        "SKIPPED",
        "COMPLETE",
        "COMPLETE_WITH_OVERRIDE",
        "PRACTICE_COMPLETE",
        "IN_PROGRESS",
        "STALE",
    )
    return 0 if (state and state.get("status") in terminal) else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Applyr authoritative submission workflow (CR-076/077/079)."
    )
    parser.add_argument(
        "folder", help="Submission folder path or slug under data/submissions/"
    )
    parser.add_argument(
        "--mode",
        choices=("production", "practice"),
        default="production",
        help="Workflow mode (immutable after first state write in later CRs; set on init).",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print workflow_state + check_workflow_complete; do not advance.",
    )
    parser.add_argument(
        "--adopt-only",
        action="store_true",
        help="Adopt existing artifacts into receipts/state without rebuilding Stage 0/1.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Re-enter from earliest READY/STALE/WAITING action (CR-077/079).",
    )
    parser.add_argument(
        "--stop-at-waiting",
        action="store_true",
        help="CR-076 behavior: stop at WAITING_FOR_LLM even if Resume/CL already exist.",
    )
    parser.add_argument(
        "--stop-after-stage1",
        action="store_true",
        help="Stop after Stage 1 COMPLETE / Stage 2 READY (skip Truth/ATS).",
    )
    parser.add_argument(
        "--stop-after-truth",
        action="store_true",
        help="Stop after Truth (2A).",
    )
    parser.add_argument(
        "--stop-after-ats",
        action="store_true",
        help="Stop after ATS (2B).",
    )
    parser.add_argument(
        "--stop-after-hm",
        action="store_true",
        help="Stop after HM (2C).",
    )
    parser.add_argument(
        "--stop-after-mech",
        action="store_true",
        help="Stop after Mech (2D).",
    )
    parser.add_argument(
        "--no-compile",
        action="store_true",
        help="Skip PDF compile in mech (tests / PDFs already present).",
    )
    parser.add_argument(
        "--no-hook",
        action="store_true",
        default=True,
        help="Pass no_hook to packet builder (default True).",
    )
    parser.add_argument(
        "--with-hook",
        action="store_true",
        help="Allow packet builder hook-fact research.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite stage0_fit_gate.json even when extraction_override is set.",
    )
    parser.add_argument(
        "--finalize",
        action="store_true",
        help="Run Stage 3 finalize after Stage 2 COMPLETE (explicit; writes DB in production).",
    )
    parser.add_argument("--finalize-company", default=None, help="Override Stage 3 company.")
    parser.add_argument("--finalize-title", default=None, help="Override Stage 3 job title.")
    parser.add_argument(
        "--finalize-reach-out",
        action="store_true",
        help="Force [Reach Out] title prefix on finalize.",
    )
    parser.add_argument(
        "--force-finalize",
        action="store_true",
        help="Pass force=True to finalize_submission_job (bypass check_finalize_ready).",
    )
    args = parser.parse_args()
    no_hook = not args.with_hook

    try:
        if args.status:
            sys.exit(_print_status(args.folder))
        if args.adopt_only:
            folder = _resolve_folder(args.folder)
            state = adopt_existing(folder, mode=args.mode)
            print(f"ADOPTED status={state.get('status')} active={state.get('active_stage')}")
            sys.exit(0)

        # Epic D (observability design): count events already on disk before this invocation
        # advances anything, so the console summary below prints only what *this* run produced.
        _folder_for_events = _resolve_folder(args.folder)
        _before_count = len(read_events(_folder_for_events))

        # Stage 3-only path when already Stage 2 COMPLETE
        if args.finalize and not args.stop_at_waiting and not args.stop_after_stage1:
            folder = _resolve_folder(args.folder)
            st = load_state(folder)
            if st and (st.get("stages") or {}).get("stage2", {}).get("status") == "COMPLETE":
                if st.get("status") in (
                    "COMPLETE",
                    "COMPLETE_WITH_OVERRIDE",
                    "PRACTICE_COMPLETE",
                ):
                    print(f"WORKFLOW already terminal status={st.get('status')}")
                    sys.exit(0)
                reach = True if args.finalize_reach_out else None
                state = run_stage3_finalize(
                    folder,
                    st,
                    company=args.finalize_company,
                    title=args.finalize_title,
                    reach_out=reach,
                    force=args.force_finalize,
                )
            else:
                state = run_until_truth_settled(
                    args.folder,
                    mode=args.mode,
                    adopt=True,
                    no_hook=no_hook,
                    force=args.force,
                    stop_at_waiting=False,
                    compile_pdfs=not args.no_compile,
                    do_finalize=True,
                    finalize_company=args.finalize_company,
                    finalize_title=args.finalize_title,
                    finalize_reach_out=True if args.finalize_reach_out else None,
                    finalize_force=args.force_finalize,
                )
        elif args.stop_at_waiting and not args.resume:
            state = run_until_waiting_for_llm(
                args.folder,
                mode=args.mode,
                adopt=True,
                no_hook=no_hook,
                force=args.force,
            )
        elif args.stop_after_stage1:
            state = run_until_stage1_complete(
                args.folder,
                mode=args.mode,
                adopt=True,
                no_hook=no_hook,
                force=args.force,
            )
        else:
            state = run_until_truth_settled(
                args.folder,
                mode=args.mode,
                adopt=True,
                no_hook=no_hook,
                force=args.force,
                stop_at_waiting=args.stop_at_waiting,
                stop_after_stage1=False,
                stop_after_truth=args.stop_after_truth,
                stop_after_ats=args.stop_after_ats,
                stop_after_hm=args.stop_after_hm,
                stop_after_mech=args.stop_after_mech,
                compile_pdfs=not args.no_compile,
                do_finalize=args.finalize,
                finalize_company=args.finalize_company,
                finalize_title=args.finalize_title,
                finalize_reach_out=True if args.finalize_reach_out else None,
                finalize_force=args.force_finalize,
            )

        _print_console_summary(_folder_for_events, _before_count)
        status = state.get("status")
        print(f"WORKFLOW status={status} active={state.get('active_stage')}")
        if status == "SKIPPED":
            print("Stage 0 Skip — no drafting. See stage_receipts/stage0.json.")
            sys.exit(2)
        if status == "WAITING_FOR_LLM":
            print(
                "WAITING_FOR_LLM — paste authoring_prompt.md into a fresh agent "
                "(SYSTEM=digest, USER=packet). Do not load agent_context_pack.md."
            )
            sys.exit(0)
        if status == "NEEDS_DISPOSITION":
            # CR-107: renamed from WAITING_FOR_HUMAN — a WARN finding here is the agent's own
            # call to make and retry in the same session (see AGENTS.md), never an actual stop.
            print(
                "NEEDS_DISPOSITION — findings need dispositions recorded in "
                "reviews/dispositions.json, then re-run with --resume immediately."
            )
            sys.exit(4)
        if status == "STALE":
            print(
                "STALE — hashes no longer match receipts; re-run without --status "
                "to rebuild from earliest STALE stage."
            )
            sys.exit(3)
        if status == "FAILED":
            sys.exit(1)
        if status == "COMPLETE":
            print("WORKFLOW COMPLETE — check_workflow_complete should be YES.")
            sys.exit(0)
        if status == "COMPLETE_WITH_OVERRIDE":
            print("WORKFLOW COMPLETE_WITH_OVERRIDE — integrity OVERRIDDEN somewhere in the chain.")
            sys.exit(0)
        if status == "PRACTICE_COMPLETE":
            print("PRACTICE_COMPLETE — no DB write; not production DONE.")
            sys.exit(0)
        s2 = (state.get("stages") or {}).get("stage2") or {}
        sub = s2.get("subphases") or {}
        if s2.get("status") == "COMPLETE":
            print(
                "Stage 2 COMPLETE — Stage 3 READY. "
                "Re-run with --finalize to mint Stage 3 receipt "
                "(production writes jobs DB via finalize_submission_job)."
            )
            sys.exit(0)
        ats = sub.get("ats") or {}
        truth = sub.get("truth") or {}
        hm = sub.get("hm") or {}
        mech = sub.get("mech") or {}
        if mech.get("status") == "COMPLETE":
            print("Mech COMPLETE — policy gate next / in progress.")
            sys.exit(0)
        if hm.get("status") == "COMPLETE":
            print("HM COMPLETE — Mech READY.")
            sys.exit(0)
        if ats.get("status") == "COMPLETE":
            print(
                "ATS COMPLETE — HM subphase READY (or in progress). "
                "check_workflow_complete remains NO."
            )
            sys.exit(0)
        if truth.get("status") == "COMPLETE":
            print(
                "Truth COMPLETE — ATS subphase READY (or in progress). "
                "check_workflow_complete remains NO."
            )
            sys.exit(0)
        s1 = (state.get("stages") or {}).get("stage1") or {}
        if s1.get("status") == "COMPLETE" and s2.get("status") == "READY":
            print(
                "Stage 1 COMPLETE — Stage 2 READY. "
                "check_workflow_complete remains NO until Stages 2–3 complete."
            )
            sys.exit(0)
        sys.exit(0)
    except WorkflowError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
