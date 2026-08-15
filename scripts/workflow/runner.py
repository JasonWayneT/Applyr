"""CR-076 stage runner: wraps existing workers; never reimplements Stage 0/1 builders."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import contracts  # noqa: E402
from author_from_packet import build_authoring_prompt, run_verify_only  # noqa: E402
from build_authoring_packet import build_packet  # noqa: E402
from build_stage0_fit_gate import build_stage0_fit_gate  # noqa: E402
from stage_gate import StageGateNotReadyError, require_stage_ready  # noqa: E402

from claim_provenance import check_claim_provenance  # noqa: E402
from check_ground_truth_coverage import check_folder as check_ground_truth_folder  # noqa: E402
from finalize_submission_job import (  # noqa: E402
    ImplausibleJobTitleError,
    NotReadyToFinalizeError,
    finalize as finalize_job,
)
from jd_term_extractor import check_folder as check_jd_term_folder  # noqa: E402
from verify_submission import verify_one  # noqa: E402
import submission_linter  # noqa: E402

from workflow import policy  # noqa: E402
from workflow.invalidate import hashes_match, reconcile_state_against_receipts  # noqa: E402
from workflow.receipts import (  # noqa: E402
    build_receipt,
    commit_stage,
    file_hash_map,
    load_receipt,
    write_state,
)
from workflow.reviews import (  # noqa: E402
    ensure_stage2_subphases,
    findings_content_hash,
    sync_dispositions_for_phase,
    write_ats_findings,
    write_hm_findings,
    write_truth_findings,
)
from workflow.state import init_state, load_state, utc_now  # noqa: E402


class WorkflowError(Exception):
    """Visible workflow failure (non-zero CLI)."""


def _resolve_folder(folder: str) -> str:
    path = Path(folder)
    if not path.is_absolute():
        root = Path(_SCRIPT_DIR).parent
        for base in ("submissions", "pending_review"):
            cand = root / "data" / base / folder
            if cand.is_dir():
                return str(cand.resolve())
    if not path.is_dir():
        raise WorkflowError(f"folder not found: {folder}")
    return str(path.resolve())


def _load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise WorkflowError(f"{os.path.basename(path)} is not a JSON object")
    return data


def _place_after_stage0(folder: str, state: dict[str, Any]) -> str:
    """Move Skip folders out of submissions/pending_review; promote PASS from pending.

    # Implements FR-264
    """
    from stage0_placement import apply_stage0_placement

    gate_path = os.path.join(folder, "stage0_fit_gate.json")
    if not os.path.exists(gate_path):
        return folder
    result = _load_json(gate_path)
    mode = state.get("mode") or "production"
    new_folder = apply_stage0_placement(folder, result, mode=mode)
    return str(new_folder)


def _ensure_caller_mode(
    folder: str,
    state: dict[str, Any],
    mode: str,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Refuse silent mode drift (practice vs production).

    Existing workflow_state keeps its mode unless force=True rewrites it.
    Practice pressure-tests must not quietly inherit production mode (finalize
    would write the jobs DB).
    """
    existing = (state.get("mode") or "production").strip() or "production"
    requested = (mode or "production").strip() or "production"
    if existing == requested:
        return state
    if not force:
        raise WorkflowError(
            f"workflow mode is {existing!r} but caller requested {requested!r} — "
            "pass force=True to rewrite mode, or match the existing mode"
        )
    state = dict(state)
    state["mode"] = requested
    write_state(folder, state)
    return state


def adopt_existing(folder: str, mode: str = "production") -> dict[str, Any]:
    """Create workflow_state + receipts from valid on-disk artifacts (no rebuild)."""
    state = load_state(folder) or init_state(folder, mode=mode)
    write_state(folder, state)

    stage0_path = os.path.join(folder, "stage0_fit_gate.json")
    if os.path.exists(stage0_path):
        ok, errors = contracts.check_stage0_fit_gate(folder)
        if ok:
            existing = load_receipt(folder, "stage0")
            out_hashes = file_hash_map(folder, ["stage0_fit_gate.json"])
            in_hashes = file_hash_map(folder, ["Original_JD.txt"])
            if existing and existing.get("output_hashes") == out_hashes:
                # already adopted
                pass
            else:
                gate = _load_json(stage0_path)
                verdict = policy.evaluate_stage0(gate)
                status = "SKIPPED" if verdict["verdict"] == "SKIP" else "COMPLETE"
                wf_status = "SKIPPED" if status == "SKIPPED" else "IN_PROGRESS"
                active = None if status == "SKIPPED" else "stage1"
                receipt = build_receipt(
                    stage="stage0",
                    status=status,
                    mode=mode,
                    input_hashes=in_hashes,
                    output_hashes=out_hashes,
                    result={
                        "tier": verdict["tier"],
                        "decision": verdict["decision"],
                        "adopted": True,
                    },
                    checks={"contracts.check_stage0_fit_gate": True},
                )
                if status == "COMPLETE":
                    state = commit_stage(
                        folder,
                        state,
                        receipt,
                        workflow_status=wf_status,
                        active_stage="stage1",
                    )
                    state["stages"]["stage1"]["status"] = "READY"
                    write_state(folder, state)
                else:
                    state = commit_stage(
                        folder,
                        state,
                        receipt,
                        workflow_status=wf_status,
                        active_stage=active,
                    )

    # Prompt-ready mid-state
    packet_path = os.path.join(folder, "authoring_packet.json")
    prompt_path = os.path.join(folder, "authoring_prompt.md")
    state = load_state(folder) or state
    if (
        state.get("status") != "SKIPPED"
        and os.path.exists(packet_path)
        and os.path.exists(prompt_path)
    ):
        packet = _load_json(packet_path)
        if packet.get("packet_status") == "ready":
            out_hashes = file_hash_map(
                folder, ["authoring_packet.json", "authoring_prompt.md"]
            )
            prior = load_receipt(folder, "stage0")
            receipt = build_receipt(
                stage="stage1",
                status="WAITING_FOR_LLM",
                mode=mode,
                input_hashes=file_hash_map(folder, ["stage0_fit_gate.json"]),
                output_hashes=out_hashes,
                result={"adopted": True, "packet_status": "ready"},
                checks={"packet_status_ready": True},
                prior_receipt_id=(prior or {}).get("receipt_id"),
            )
            state = commit_stage(
                folder,
                state,
                receipt,
                workflow_status="WAITING_FOR_LLM",
                active_stage="stage1",
            )
    return load_state(folder) or state


def run_stage0(folder: str, state: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    """Build/validate Stage 0 via existing worker; write receipt."""
    jd = os.path.join(folder, "Original_JD.txt")
    if not os.path.exists(jd):
        raise WorkflowError("Original_JD.txt not found")

    gate_path = os.path.join(folder, "stage0_fit_gate.json")
    result = build_stage0_fit_gate(folder, ignore_skip_ledger=force)
    protected = False
    if os.path.exists(gate_path) and not force:
        try:
            existing = _load_json(gate_path)
            protected = bool(existing.get("extraction_override"))
        except (OSError, json.JSONDecodeError, WorkflowError):
            protected = False
    if not protected:
        with open(gate_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            f.write("\n")
    else:
        result = _load_json(gate_path)

    ok, errors = contracts.check_stage0_fit_gate(folder)
    if not ok:
        raise WorkflowError("stage0_fit_gate.json failed contract:\n  - " + "\n  - ".join(errors))

    verdict = policy.evaluate_stage0(result)
    mode = state.get("mode") or "production"
    receipt = build_receipt(
        stage="stage0",
        status="SKIPPED" if verdict["verdict"] == "SKIP" else "COMPLETE",
        mode=mode,
        input_hashes=file_hash_map(folder, ["Original_JD.txt"]),
        output_hashes=file_hash_map(folder, ["stage0_fit_gate.json"]),
        result={
            "tier": verdict["tier"],
            "decision": verdict["decision"],
            "reasons": verdict["reasons"],
        },
        checks={"contracts.check_stage0_fit_gate": True, "policy.evaluate_stage0": verdict["verdict"]},
    )

    if verdict["verdict"] == "SKIP":
        return commit_stage(
            folder,
            state,
            receipt,
            workflow_status="SKIPPED",
            active_stage=None,
        )
    if verdict["verdict"] != "PASS":
        failed = dict(receipt)
        failed["status"] = "FAILED"
        # Rebuild receipt_id for FAILED status
        failed = build_receipt(
            stage="stage0",
            status="FAILED",
            mode=mode,
            input_hashes=receipt["input_hashes"],
            output_hashes=receipt["output_hashes"],
            result=receipt["result"],
            checks=receipt["checks"],
        )
        commit_stage(
            folder,
            state,
            failed,
            workflow_status="FAILED",
            active_stage="stage0",
        )
        raise WorkflowError("Stage 0 policy FAIL: " + "; ".join(verdict["reasons"]))

    state = commit_stage(
        folder,
        state,
        receipt,
        workflow_status="IN_PROGRESS",
        active_stage="stage1",
    )
    state["stages"]["stage1"]["status"] = "READY"
    write_state(folder, state)
    return state


def run_stage1_prompt(folder: str, state: dict[str, Any], *, no_hook: bool = True) -> dict[str, Any]:
    """Build packet + authoring prompt; stop at WAITING_FOR_LLM."""
    # CR-075 safety net — still live under the new layer
    try:
        require_stage_ready("stage0", folder, force=False)
    except StageGateNotReadyError as exc:
        raise WorkflowError(str(exc)) from exc

    r0 = load_receipt(folder, "stage0")
    if not r0 or r0.get("status") != "COMPLETE":
        raise WorkflowError("Stage 0 receipt missing or not COMPLETE — run Stage 0 first")
    ok, errs = hashes_match(folder, r0.get("output_hashes") or {})
    if not ok:
        raise WorkflowError("Stage 0 outputs stale:\n  - " + "\n  - ".join(errs))

    packet = build_packet(Path(folder), no_hook=no_hook)
    packet_path = os.path.join(folder, "authoring_packet.json")
    with open(packet_path, "w", encoding="utf-8") as f:
        json.dump(packet, f, indent=2, ensure_ascii=False)
        f.write("\n")

    verdict = policy.evaluate_packet(packet)
    if verdict["verdict"] != "PASS":
        raise WorkflowError(
            "authoring_packet.json not ready (no --force for packet_status):\n  - "
            + "\n  - ".join(verdict["reasons"])
        )

    prompt_md, meta = build_authoring_prompt(Path(folder), force=False)
    prompt_path = os.path.join(folder, "authoring_prompt.md")
    meta_path = os.path.join(folder, "authoring_prompt_meta.json")
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt_md)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        f.write("\n")

    mode = state.get("mode") or "production"
    receipt = build_receipt(
        stage="stage1",
        status="WAITING_FOR_LLM",
        mode=mode,
        input_hashes=file_hash_map(folder, ["stage0_fit_gate.json"]),
        output_hashes=file_hash_map(
            folder,
            ["authoring_packet.json", "authoring_prompt.md", "authoring_prompt_meta.json"],
        ),
        result={"packet_status": "ready", "meta": meta},
        checks={
            "contracts.require_stage_ready.stage0": True,
            "packet_status_ready": True,
        },
        prior_receipt_id=r0.get("receipt_id"),
    )
    return commit_stage(
        folder,
        state,
        receipt,
        workflow_status="WAITING_FOR_LLM",
        active_stage="stage1",
    )


def _docs_present(folder: str) -> bool:
    return os.path.exists(os.path.join(folder, "Resume.md")) and os.path.exists(
        os.path.join(folder, "CoverLetter.md")
    )


def reconcile(folder: str, state: dict[str, Any]) -> dict[str, Any]:
    """Apply hash cascade; persist if anything went STALE."""
    new_state, reasons = reconcile_state_against_receipts(folder, state, load_receipt)
    if reasons:
        write_state(folder, new_state)
        for r in reasons:
            print(f"STALE: {r}", file=sys.stderr)
    return new_state


def run_stage1_validate(folder: str, state: dict[str, Any]) -> dict[str, Any]:
    """CR-077: after LLM compose, run verify-only and write Stage 1 COMPLETE receipt."""
    state = reconcile(folder, state)
    s1 = (state.get("stages") or {}).get("stage1") or {}
    if s1.get("status") == "STALE":
        # Re-validate is allowed — treat as READY for validate path
        state["stages"]["stage1"]["status"] = "READY"
        state["status"] = "IN_PROGRESS"
        write_state(folder, state)

    if not _docs_present(folder):
        raise WorkflowError(
            "Resume.md and/or CoverLetter.md missing — still WAITING_FOR_LLM"
        )

    # CR-075 safety: packet_status ready + docs (no force)
    ok, errors = contracts.check_stage1_ready(folder)
    if not ok:
        raise WorkflowError(
            "check_stage1_ready failed:\n  - " + "\n  - ".join(errors)
        )

    # Prior: Stage 0 must still be COMPLETE + fresh
    r0 = load_receipt(folder, "stage0")
    if not r0 or r0.get("status") != "COMPLETE":
        raise WorkflowError("Stage 0 receipt missing or not COMPLETE")
    ok, errs = hashes_match(folder, r0.get("output_hashes") or {})
    if not ok:
        raise WorkflowError("Stage 0 outputs stale:\n  - " + "\n  - ".join(errs))

    # Optional: waiting receipt for prior_receipt_id chain preference
    r1_waiting = load_receipt(folder, "stage1")
    prior_id = None
    if r1_waiting and r1_waiting.get("status") == "WAITING_FOR_LLM":
        prior_id = r1_waiting.get("receipt_id")
    else:
        prior_id = r0.get("receipt_id")

    verify_ok = run_verify_only(Path(folder))
    if not verify_ok:
        raise WorkflowError(
            "author_from_packet.run_verify_only FAILED — fix docs using packet+digest only"
        )

    mode = state.get("mode") or "production"
    out_files = [
        "Resume.md",
        "CoverLetter.md",
        "authoring_packet.json",
    ]
    if os.path.exists(os.path.join(folder, "claim_provenance.json")):
        out_files.append("claim_provenance.json")

    receipt = build_receipt(
        stage="stage1",
        status="COMPLETE",
        mode=mode,
        input_hashes=file_hash_map(
            folder,
            ["stage0_fit_gate.json", "authoring_packet.json", "authoring_prompt.md"],
        ),
        output_hashes=file_hash_map(folder, out_files),
        result={"verify_only": True},
        checks={
            "contracts.check_stage1_ready": True,
            "author_from_packet.run_verify_only": True,
        },
        prior_receipt_id=prior_id,
    )
    state = commit_stage(
        folder,
        state,
        receipt,
        workflow_status="IN_PROGRESS",
        active_stage="stage2",
    )
    # Unlock Stage 2 READY only — no Stage 2 work in CR-077
    state["stages"]["stage2"]["status"] = "READY"
    state["stages"]["stage2"]["receipt_id"] = None
    write_state(folder, state)
    return state


def collect_truth_findings(folder: str) -> dict[str, Any]:
    """Run mechanical Truth workers and aggregate into reviews/truth_findings.json."""
    findings: list[dict[str, Any]] = []

    # 1. Claim provenance — fabricated/disabled IDs are BLOCK
    prov_ok, prov_errors = check_claim_provenance(folder)
    if not prov_ok:
        for i, err in enumerate(prov_errors):
            findings.append(
                {
                    "id": f"truth.provenance.{i}",
                    "source": "claim_provenance",
                    "severity": "BLOCK",
                    "message": err,
                }
            )

    # 2. Ground-truth coverage — unused JD-relevant claims are WARN
    coverage = check_ground_truth_folder(folder)
    cov_path = os.path.join(folder, "ground_truth_coverage.json")
    with open(cov_path, "w", encoding="utf-8") as f:
        json.dump(coverage, f, indent=2)
        f.write("\n")
    if coverage.get("error"):
        findings.append(
            {
                "id": "truth.coverage.error",
                "source": "check_ground_truth_coverage",
                "severity": "BLOCK",
                "message": coverage["error"],
            }
        )
    else:
        for i, item in enumerate(coverage.get("jd_relevant_claims_possibly_unused") or []):
            pid = item.get("project_id") or f"unused_{i}"
            findings.append(
                {
                    "id": f"truth.coverage.unused.{pid}",
                    "source": "check_ground_truth_coverage",
                    "severity": "WARN",
                    "message": (
                        f"JD-relevant claim {pid} may be unused in Resume/CL "
                        f"(tags: {', '.join(item.get('matched_tags') or [])})"
                    ),
                    "detail": item,
                }
            )
        for i, item in enumerate(coverage.get("jd_relevant_but_unverified_claims") or []):
            pid = item.get("project_id") or f"unverified_{i}"
            findings.append(
                {
                    "id": f"truth.coverage.unverified.{pid}",
                    "source": "check_ground_truth_coverage",
                    "severity": "WARN",
                    "message": (
                        f"JD-relevant but unverified claim {pid} — do not use until confirmed"
                    ),
                    "detail": item,
                }
            )

    payload = {
        "schema_version": 1,
        "phase": "truth",
        "generated_at": utc_now(),
        "generated_by": "scripts/run_submission.py",
        "findings": findings,
        "checks": {
            "claim_provenance_ok": prov_ok,
            "ground_truth_coverage_clean": bool(coverage.get("clean"))
            if not coverage.get("error")
            else False,
        },
    }
    write_truth_findings(folder, payload)
    return payload


def run_stage2_truth(folder: str, state: dict[str, Any]) -> dict[str, Any]:
    """CR-079: Stage 2A Truth/Evidence — findings + dispositions; never Stage 2 COMPLETE."""
    folder = _resolve_folder(folder)
    state = reconcile(folder, state)
    state = ensure_stage2_subphases(state)

    # Require Stage 1 COMPLETE + fresh
    r1 = load_receipt(folder, "stage1")
    if not r1 or r1.get("status") != "COMPLETE":
        raise WorkflowError("Stage 1 receipt missing or not COMPLETE — finish Stage 1 first")
    ok, errs = hashes_match(folder, r1.get("output_hashes") or {})
    if not ok:
        raise WorkflowError("Stage 1 outputs stale:\n  - " + "\n  - ".join(errs))

    s2 = state["stages"]["stage2"]
    if s2.get("status") == "LOCKED":
        # Stage 1 COMPLETE unlocks Stage 2 to READY; adopt edge cases may still say LOCKED
        s2["status"] = "READY"

    # Collect findings (re-run mechanical truth every attempt)
    findings_doc = collect_truth_findings(folder)
    dispositions = sync_dispositions_for_phase(folder, "truth", findings_doc)
    verdict = policy.evaluate_truth_findings(findings_doc, dispositions)

    fhash = findings_content_hash(findings_doc)
    truth = s2["subphases"]["truth"]

    if verdict["verdict"] == "FAIL":
        truth["status"] = "FAILED"
        truth["findings_hash"] = fhash
        s2["status"] = "FAILED"
        state["status"] = "FAILED"
        state["active_stage"] = "stage2"
        write_state(folder, state)
        raise WorkflowError(
            "Truth policy FAIL:\n  - " + "\n  - ".join(verdict.get("reasons") or [])
        )

    if verdict["verdict"] == "WAITING_FOR_HUMAN":
        truth["status"] = "WAITING_FOR_HUMAN"
        truth["findings_hash"] = fhash
        s2["status"] = "WAITING_FOR_HUMAN"
        # Carry integrity only when we later PASS; keep CLEAN while waiting
        state["status"] = "WAITING_FOR_HUMAN"
        state["active_stage"] = "stage2"
        write_state(folder, state)
        return state

    # PASS — mark 2A COMPLETE, unlock ATS for CR-080 (LOCKED until then is wrong —
    # unlock to READY so next CR can pick up)
    truth["status"] = "COMPLETE"
    truth["findings_hash"] = fhash
    truth["integrity"] = verdict.get("integrity") or "CLEAN"
    s2["subphases"]["ats"]["status"] = "READY"
    s2["status"] = "RUNNING"
    if verdict.get("integrity") == "OVERRIDDEN":
        s2["integrity"] = "OVERRIDDEN"
    state["status"] = "IN_PROGRESS"
    state["active_stage"] = "stage2"
    write_state(folder, state)
    return state


def collect_ats_findings(folder: str) -> dict[str, Any]:
    """Run mechanical ATS collectors and aggregate into reviews/ats_findings.json."""
    findings: list[dict[str, Any]] = []
    gaps = check_jd_term_folder(folder)
    gaps_path = os.path.join(folder, "jd_term_gaps.json")
    with open(gaps_path, "w", encoding="utf-8") as f:
        json.dump(gaps, f, indent=2)
        f.write("\n")

    if gaps.get("error"):
        findings.append(
            {
                "id": "ats.jd_terms.error",
                "source": "jd_term_extractor",
                "severity": "BLOCK",
                "message": gaps["error"],
            }
        )
    else:
        for term in gaps.get("missing_from_resume") or []:
            safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(term)).strip("_") or "term"
            findings.append(
                {
                    "id": f"ats.jd_terms.missing.{safe}",
                    "source": "jd_term_extractor",
                    "severity": "WARN",
                    "message": (
                        f"JD term {term!r} is true of Jason and in the JD but "
                        "missing from Resume.md (ATS coverage gap)"
                    ),
                    "detail": {"term": term},
                }
            )

    payload = {
        "schema_version": 1,
        "phase": "ats",
        "generated_at": utc_now(),
        "generated_by": "scripts/run_submission.py",
        "findings": findings,
        "checks": {
            "jd_term_gaps_clean": not findings,
        },
    }
    write_ats_findings(folder, payload)
    return payload


def run_stage2_ats(folder: str, state: dict[str, Any]) -> dict[str, Any]:
    """CR-080: Stage 2B ATS/AI — findings + dispositions; never Stage 2 COMPLETE."""
    folder = _resolve_folder(folder)
    state = reconcile(folder, state)
    state = ensure_stage2_subphases(state)

    r1 = load_receipt(folder, "stage1")
    if not r1 or r1.get("status") != "COMPLETE":
        raise WorkflowError("Stage 1 receipt missing or not COMPLETE")
    ok, errs = hashes_match(folder, r1.get("output_hashes") or {})
    if not ok:
        raise WorkflowError("Stage 1 outputs stale:\n  - " + "\n  - ".join(errs))

    truth = state["stages"]["stage2"]["subphases"]["truth"]
    if truth.get("status") != "COMPLETE":
        raise WorkflowError("Truth subphase not COMPLETE — finish Stage 2A first")

    s2 = state["stages"]["stage2"]
    if s2.get("status") == "LOCKED":
        s2["status"] = "RUNNING"

    findings_doc = collect_ats_findings(folder)
    dispositions = sync_dispositions_for_phase(folder, "ats", findings_doc)
    verdict = policy.evaluate_truth_findings(findings_doc, dispositions)

    fhash = findings_content_hash(findings_doc)
    ats = s2["subphases"]["ats"]

    if verdict["verdict"] == "FAIL":
        ats["status"] = "FAILED"
        ats["findings_hash"] = fhash
        s2["status"] = "FAILED"
        state["status"] = "FAILED"
        state["active_stage"] = "stage2"
        write_state(folder, state)
        raise WorkflowError(
            "ATS policy FAIL:\n  - " + "\n  - ".join(verdict.get("reasons") or [])
        )

    if verdict["verdict"] == "WAITING_FOR_HUMAN":
        ats["status"] = "WAITING_FOR_HUMAN"
        ats["findings_hash"] = fhash
        s2["status"] = "WAITING_FOR_HUMAN"
        state["status"] = "WAITING_FOR_HUMAN"
        state["active_stage"] = "stage2"
        write_state(folder, state)
        return state

    ats["status"] = "COMPLETE"
    ats["findings_hash"] = fhash
    ats["integrity"] = verdict.get("integrity") or "CLEAN"
    s2["subphases"]["hm"]["status"] = "READY"
    s2["status"] = "RUNNING"
    if verdict.get("integrity") == "OVERRIDDEN" or s2.get("integrity") == "OVERRIDDEN":
        s2["integrity"] = "OVERRIDDEN"
    state["status"] = "IN_PROGRESS"
    state["active_stage"] = "stage2"
    write_state(folder, state)
    return state


def _require_stage1_fresh(folder: str) -> Any:
    r1 = load_receipt(folder, "stage1")
    if not r1 or r1.get("status") != "COMPLETE":
        raise WorkflowError("Stage 1 receipt missing or not COMPLETE")
    ok, errs = hashes_match(folder, r1.get("output_hashes") or {})
    if not ok:
        raise WorkflowError("Stage 1 outputs stale:\n  - " + "\n  - ".join(errs))
    return r1


def _apply_subphase_verdict(
    folder: str,
    state: dict[str, Any],
    *,
    phase: str,
    findings_doc: dict[str, Any],
    next_phase: str | None,
    fail_label: str,
) -> dict[str, Any]:
    """Shared disposition → subphase COMPLETE / WAITING / FAIL helper."""
    dispositions = sync_dispositions_for_phase(folder, phase, findings_doc)
    verdict = policy.evaluate_truth_findings(findings_doc, dispositions)
    fhash = findings_content_hash(findings_doc)
    s2 = state["stages"]["stage2"]
    phase_rec = s2["subphases"][phase]

    if verdict["verdict"] == "FAIL":
        phase_rec["status"] = "FAILED"
        phase_rec["findings_hash"] = fhash
        s2["status"] = "FAILED"
        state["status"] = "FAILED"
        state["active_stage"] = "stage2"
        write_state(folder, state)
        raise WorkflowError(
            f"{fail_label} policy FAIL:\n  - "
            + "\n  - ".join(verdict.get("reasons") or [])
        )

    if verdict["verdict"] == "WAITING_FOR_HUMAN":
        phase_rec["status"] = "WAITING_FOR_HUMAN"
        phase_rec["findings_hash"] = fhash
        s2["status"] = "WAITING_FOR_HUMAN"
        state["status"] = "WAITING_FOR_HUMAN"
        state["active_stage"] = "stage2"
        write_state(folder, state)
        return state

    phase_rec["status"] = "COMPLETE"
    phase_rec["findings_hash"] = fhash
    phase_rec["integrity"] = verdict.get("integrity") or "CLEAN"
    if next_phase:
        s2["subphases"][next_phase]["status"] = "READY"
    s2["status"] = "RUNNING"
    if verdict.get("integrity") == "OVERRIDDEN" or s2.get("integrity") == "OVERRIDDEN":
        s2["integrity"] = "OVERRIDDEN"
    state["status"] = "IN_PROGRESS"
    state["active_stage"] = "stage2"
    write_state(folder, state)
    return state


def collect_hm_findings(folder: str) -> dict[str, Any]:
    """HM-facing mechanical signals: lint WARNs + hard blocks (should be rare post-Stage1)."""
    findings: list[dict[str, Any]] = []
    lint_results = submission_linter.lint_folder(folder)
    for r in lint_results:
        doc = r.get("document") or r.get("doc_type") or "doc"
        result = r["result"]
        for i, v in enumerate(result.blocks):
            findings.append(
                {
                    "id": f"hm.lint.block.{doc}.{v.rule_id}.{i}",
                    "source": "submission_linter",
                    "severity": "BLOCK",
                    "message": f"[{v.rule_id}] {v.message}",
                }
            )
        for i, v in enumerate(result.warns):
            findings.append(
                {
                    "id": f"hm.lint.warn.{doc}.{v.rule_id}.{i}",
                    "source": "submission_linter",
                    "severity": "WARN",
                    "message": f"[{v.rule_id}] {v.message}",
                }
            )

    # Explicit critical-read gate: Jason confirms a hiring-manager read happened.
    findings.append(
        {
            "id": "hm.critical_read",
            "source": "workflow",
            "severity": "WARN",
            "message": (
                "Confirm a hiring-manager read of Resume.md + CoverLetter.md "
                "(conversion_rubric C1–C5 / qualitative Pass 3). "
                "Dispose ACCEPTED_AS_CORRECT when done."
            ),
        }
    )

    payload = {
        "schema_version": 1,
        "phase": "hm",
        "generated_at": utc_now(),
        "generated_by": "scripts/run_submission.py",
        "findings": findings,
        "checks": {"lint_docs": len(lint_results)},
    }
    write_hm_findings(folder, payload)
    return payload


def run_stage2_hm(folder: str, state: dict[str, Any]) -> dict[str, Any]:
    """CR-081: Stage 2C Critical HM review."""
    folder = _resolve_folder(folder)
    state = reconcile(folder, state)
    state = ensure_stage2_subphases(state)
    _require_stage1_fresh(folder)

    ats = state["stages"]["stage2"]["subphases"]["ats"]
    if ats.get("status") != "COMPLETE":
        raise WorkflowError("ATS subphase not COMPLETE — finish Stage 2B first")

    findings_doc = collect_hm_findings(folder)
    return _apply_subphase_verdict(
        folder,
        state,
        phase="hm",
        findings_doc=findings_doc,
        next_phase="mech",
        fail_label="HM",
    )


def _compile_pdfs(folder: str) -> None:
    """Shell out to compile_single.py for Resume + CoverLetter (existing worker)."""
    py = sys.executable
    script = os.path.join(_SCRIPT_DIR, "compile_single.py")
    for md_name, pdf_name in (("Resume.md", "Resume.pdf"), ("CoverLetter.md", "CoverLetter.pdf")):
        md = os.path.join(folder, md_name)
        pdf = os.path.join(folder, pdf_name)
        if not os.path.exists(md):
            raise WorkflowError(f"{md_name} missing — cannot compile")
        import subprocess

        proc = subprocess.run(
            [py, script, md, pdf],
            cwd=os.path.dirname(_SCRIPT_DIR),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise WorkflowError(
                f"compile_single failed for {md_name}:\n{proc.stderr or proc.stdout}"
            )


def collect_mech_findings(folder: str, *, compile_pdfs: bool = True) -> dict[str, Any]:
    """Compile PDFs + verify_one; surface failures as findings."""
    findings: list[dict[str, Any]] = []
    if compile_pdfs:
        try:
            _compile_pdfs(folder)
        except WorkflowError as exc:
            findings.append(
                {
                    "id": "mech.compile.error",
                    "source": "compile_single",
                    "severity": "BLOCK",
                    "message": str(exc),
                }
            )
            payload = {
                "schema_version": 1,
                "phase": "mech",
                "generated_at": utc_now(),
                "generated_by": "scripts/run_submission.py",
                "findings": findings,
                "checks": {"compiled": False},
            }
            # Write under reviews for consistency
            path = os.path.join(folder, "reviews", "mech_findings.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                f.write("\n")
            return payload

    receipt = verify_one(folder)
    receipt_path = os.path.join(folder, "verification_receipt.json")
    with open(receipt_path, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)
        f.write("\n")

    if not receipt.get("mechanically_verified"):
        findings.append(
            {
                "id": "mech.verify.failed",
                "source": "verify_submission",
                "severity": "BLOCK",
                "message": "verify_one: mechanically_verified is False — see verification_receipt.json",
            }
        )
        if not receipt.get("lint_all_clean"):
            findings.append(
                {
                    "id": "mech.verify.lint",
                    "source": "verify_submission",
                    "severity": "BLOCK",
                    "message": "lint_all_clean is False",
                }
            )
        if not receipt.get("page_counts_ok"):
            findings.append(
                {
                    "id": "mech.verify.pages",
                    "source": "verify_submission",
                    "severity": "BLOCK",
                    "message": f"page_counts not ok: {receipt.get('page_counts')}",
                }
            )

    # Rubric still required for Stage 2 policy / check_stage2_ready
    manifest_path = os.path.join(folder, "draft_manifest.json")
    rubric_ok = False
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
            score = manifest.get("rubric_score")
            if isinstance(score, dict) and isinstance(score.get("resume"), dict):
                rubric_ok = True
        except (OSError, json.JSONDecodeError):
            rubric_ok = False
    if not rubric_ok:
        findings.append(
            {
                "id": "mech.rubric_score_required",
                "source": "workflow",
                "severity": "WARN",
                "message": (
                    "draft_manifest.json rubric_score missing or incomplete — "
                    "hand-score against conversion_rubric.md, then --resume. "
                    "Dispose ACCEPTED_AS_CORRECT after score is written."
                ),
            }
        )

    payload = {
        "schema_version": 1,
        "phase": "mech",
        "generated_at": utc_now(),
        "generated_by": "scripts/run_submission.py",
        "findings": findings,
        "checks": {
            "mechanically_verified": bool(receipt.get("mechanically_verified")),
            "rubric_present": rubric_ok,
        },
    }
    path = os.path.join(folder, "reviews", "mech_findings.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return payload


def run_stage2_mech(
    folder: str, state: dict[str, Any], *, compile_pdfs: bool = True
) -> dict[str, Any]:
    """CR-081: Stage 2D final mechanical verify."""
    folder = _resolve_folder(folder)
    state = reconcile(folder, state)
    state = ensure_stage2_subphases(state)
    _require_stage1_fresh(folder)

    hm = state["stages"]["stage2"]["subphases"]["hm"]
    if hm.get("status") != "COMPLETE":
        raise WorkflowError("HM subphase not COMPLETE — finish Stage 2C first")

    findings_doc = collect_mech_findings(folder, compile_pdfs=compile_pdfs)
    return _apply_subphase_verdict(
        folder,
        state,
        phase="mech",
        findings_doc=findings_doc,
        next_phase="policy",
        fail_label="Mech",
    )


def run_stage2_policy(folder: str, state: dict[str, Any]) -> dict[str, Any]:
    """CR-081: Stage 2E — write Stage 2 COMPLETE receipt when all subphases + check_stage2_ready."""
    folder = _resolve_folder(folder)
    state = reconcile(folder, state)
    state = ensure_stage2_subphases(state)
    r1 = _require_stage1_fresh(folder)

    s2 = state["stages"]["stage2"]
    sub = s2["subphases"]
    for name in ("truth", "ats", "hm", "mech"):
        if (sub.get(name) or {}).get("status") != "COMPLETE":
            raise WorkflowError(f"Stage 2 policy blocked — {name} not COMPLETE")

    ok, errors = contracts.check_stage2_ready(folder)
    if not ok:
        sub["policy"]["status"] = "WAITING_FOR_HUMAN"
        sub["policy"]["blockers"] = errors
        s2["status"] = "WAITING_FOR_HUMAN"
        state["status"] = "WAITING_FOR_HUMAN"
        state["active_stage"] = "stage2"
        write_state(folder, state)
        path = os.path.join(folder, "reviews", "policy_findings.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "schema_version": 1,
                    "phase": "policy",
                    "generated_at": utc_now(),
                    "findings": [
                        {
                            "id": f"policy.stage2_ready.{i}",
                            "severity": "WARN",
                            "message": e,
                        }
                        for i, e in enumerate(errors)
                    ],
                    "note": (
                        "Fix the blockers (usually rubric_score in draft_manifest.json), "
                        "then --resume. No disposition required for policy gate — "
                        "check_stage2_ready must pass."
                    ),
                },
                f,
                indent=2,
            )
            f.write("\n")
        return state

    # All clear — mint Stage 2 COMPLETE receipt
    mode = state.get("mode") or "production"
    integrity = s2.get("integrity") or "CLEAN"
    out_files = [
        "Resume.md",
        "CoverLetter.md",
        "verification_receipt.json",
    ]
    if os.path.exists(os.path.join(folder, "Resume.pdf")):
        out_files.append("Resume.pdf")
    if os.path.exists(os.path.join(folder, "CoverLetter.pdf")):
        out_files.append("CoverLetter.pdf")
    if os.path.exists(os.path.join(folder, "draft_manifest.json")):
        out_files.append("draft_manifest.json")

    receipt = build_receipt(
        stage="stage2",
        status="COMPLETE",
        mode=mode,
        integrity=integrity,
        input_hashes=file_hash_map(
            folder, ["Resume.md", "CoverLetter.md", "claim_provenance.json"]
        ),
        output_hashes=file_hash_map(folder, [p for p in out_files if os.path.exists(os.path.join(folder, p))]),
        result={
            "subphases": {
                k: {"status": (sub.get(k) or {}).get("status")}
                for k in ("truth", "ats", "hm", "mech", "policy")
            }
        },
        checks={"contracts.check_stage2_ready": True},
        prior_receipt_id=r1.get("receipt_id"),
    )
    sub["policy"]["status"] = "COMPLETE"
    # Keep subphases across commit (apply_stage_update replaces stage2 dict)
    state = commit_stage(
        folder,
        state,
        receipt,
        workflow_status="IN_PROGRESS",
        active_stage="stage3",
    )
    state["stages"]["stage2"]["subphases"] = sub
    state["stages"]["stage2"]["status"] = "COMPLETE"
    state["stages"]["stage2"]["receipt_id"] = receipt["receipt_id"]
    state["stages"]["stage2"]["integrity"] = integrity
    state["stages"]["stage3"]["status"] = "READY"
    state["status"] = "IN_PROGRESS"
    state["active_stage"] = "stage3"
    write_state(folder, state)
    return state


def _integrity_any_overridden(state: dict[str, Any]) -> bool:
    for name in ("stage0", "stage1", "stage2", "stage3"):
        info = (state.get("stages") or {}).get(name) or {}
        if info.get("integrity") == "OVERRIDDEN":
            return True
        # Stage 2 subphases may carry OVERRIDDEN too
        for sub in (info.get("subphases") or {}).values():
            if isinstance(sub, dict) and sub.get("integrity") == "OVERRIDDEN":
                return True
    return False


def run_stage3_finalize(
    folder: str,
    state: dict[str, Any],
    *,
    company: str | None = None,
    title: str | None = None,
    reach_out: bool | None = None,
    force: bool = False,
    db_path: str | None = None,
) -> dict[str, Any]:
    """CR-084: Stage 3 — wrap finalize_submission_job; mint stage3 receipt; terminal status."""
    state = reconcile(folder, state)
    folder = _resolve_folder(folder)
    slug = os.path.basename(folder.rstrip("/\\"))

    r2 = load_receipt(folder, "stage2")
    if not r2 or r2.get("status") != "COMPLETE":
        raise WorkflowError("Stage 2 receipt missing or not COMPLETE — finish Stage 2 first")
    ok, errs = hashes_match(folder, r2.get("output_hashes") or {})
    if not ok:
        raise WorkflowError("Stage 2 outputs stale:\n  - " + "\n  - ".join(errs))

    s3 = (state.get("stages") or {}).get("stage3") or {}
    if s3.get("status") == "LOCKED":
        raise WorkflowError("Stage 3 LOCKED — Stage 2 must be COMPLETE first")
    if s3.get("status") not in ("READY", "RUNNING", "STALE", "FAILED", "COMPLETE"):
        state["stages"]["stage3"]["status"] = "READY"

    gate_path = os.path.join(folder, "stage0_fit_gate.json")
    if not os.path.exists(gate_path):
        raise WorkflowError("stage0_fit_gate.json missing — cannot resolve company/title")
    gate = _load_json(gate_path)
    company = company or str(gate.get("company") or "").strip()
    title = title or str(gate.get("role") or gate.get("role_title") or "").strip()
    if reach_out is None:
        reach_out = bool(gate.get("reach_out"))
    if not company or not title:
        raise WorkflowError(
            "company/title unresolved — pass --company/--title or fix stage0_fit_gate.json"
        )

    from seniority_gate import is_implausible_job_title

    if is_implausible_job_title(title):
        raise WorkflowError(
            f"Implausible job title {title!r} (JD chrome, not a role). "
            f"Pass --title with the real role name, or fix stage0_fit_gate.json 'role'."
        )

    mode = state.get("mode") or "production"
    finalize_result = None

    if mode == "practice":
        # No DB write in practice mode
        finalize_result = {"skipped_db": True, "reason": "practice mode"}
        checks = {"practice_no_db": True}
    else:
        # Existing Stage 3 worker — still enforces check_finalize_ready unless force
        try:
            kwargs: dict[str, Any] = {
                "company": company,
                "title": title,
                "slug": slug,
                "reach_out": bool(reach_out),
                "force": force,
            }
            if db_path:
                kwargs["db_path"] = db_path
            msg = finalize_job(**kwargs)
            finalize_result = {"message": msg}
            checks = {
                "finalize_submission_job": True,
                "contracts.check_finalize_ready": (not force),
            }
        except NotReadyToFinalizeError as exc:
            raise WorkflowError(str(exc)) from exc
        except ImplausibleJobTitleError as exc:
            raise WorkflowError(str(exc)) from exc

    integrity = "OVERRIDDEN" if _integrity_any_overridden(state) else (
        (state.get("stages") or {}).get("stage2", {}).get("integrity") or "CLEAN"
    )
    if integrity != "OVERRIDDEN" and force and mode == "production":
        integrity = "OVERRIDDEN"

    out_hashes = file_hash_map(
        folder,
        [
            p
            for p in (
                "Resume.md",
                "CoverLetter.md",
                "verification_receipt.json",
                "draft_manifest.json",
                "stage0_fit_gate.json",
            )
            if os.path.exists(os.path.join(folder, p))
        ],
    )

    in_files = []
    sp2 = os.path.join(folder, "stage_receipts", "stage2.json")
    if os.path.exists(sp2):
        in_files.append("stage_receipts/stage2.json")
    if os.path.exists(os.path.join(folder, "verification_receipt.json")):
        in_files.append("verification_receipt.json")
    if not in_files:
        in_files = ["verification_receipt.json"]

    receipt = build_receipt(
        stage="stage3",
        status="COMPLETE",
        mode=mode,
        integrity=integrity,
        input_hashes=file_hash_map(folder, in_files),
        output_hashes=out_hashes,
        result={
            "company": company,
            "title": title,
            "reach_out": bool(reach_out),
            "finalize": finalize_result,
        },
        checks=checks,
        prior_receipt_id=r2.get("receipt_id"),
        override={"force": True, "reason": "finalize --force"} if force else None,
    )

    if mode == "practice":
        wf_status = "PRACTICE_COMPLETE"
    elif integrity == "OVERRIDDEN":
        wf_status = "COMPLETE_WITH_OVERRIDE"
    else:
        wf_status = "COMPLETE"

    # Preserve stage2 subphases across commit of stage3
    s2_sub = ((state.get("stages") or {}).get("stage2") or {}).get("subphases")
    state = commit_stage(
        folder,
        state,
        receipt,
        workflow_status=wf_status,
        active_stage=None,
    )
    if s2_sub:
        state["stages"]["stage2"]["subphases"] = s2_sub
        # commit_stage may have left stage2 pointer alone; ensure COMPLETE preserved
        if state["stages"]["stage2"].get("status") != "COMPLETE":
            state["stages"]["stage2"]["status"] = "COMPLETE"
            state["stages"]["stage2"]["receipt_id"] = r2.get("receipt_id")
    write_state(folder, state)
    return state


def run_until_stage1_complete(
    folder: str,
    *,
    mode: str = "production",
    adopt: bool = True,
    no_hook: bool = True,
    force: bool = False,
    stop_at_waiting: bool = False,
) -> dict[str, Any]:
    """CR-077: progress through Stage 1 COMPLETE when docs exist; else WAITING_FOR_LLM."""
    folder = _resolve_folder(folder)

    if adopt and load_state(folder) is None:
        state = adopt_existing(folder, mode=mode)
    else:
        state = load_state(folder) or init_state(folder, mode=mode)
        state = _ensure_caller_mode(folder, state, mode, force=force)
        write_state(folder, state)

    state = reconcile(folder, state)

    if state.get("status") == "SKIPPED":
        return state

    s0 = (state.get("stages") or {}).get("stage0") or {}
    if s0.get("status") == "STALE":
        state = run_stage0(folder, state, force=force)
        folder = _place_after_stage0(folder, state)
        state = load_state(folder) or state
        if state.get("status") == "SKIPPED":
            return state

    s0 = (state.get("stages") or {}).get("stage0") or {}
    s1 = (state.get("stages") or {}).get("stage1") or {}

    # Need Stage 0 COMPLETE before prompt/validate
    if s0.get("status") not in ("COMPLETE", "SKIPPED"):
        state = run_until_waiting_for_llm(
            folder, mode=mode, adopt=False, no_hook=no_hook, force=force
        )
        state = reconcile(folder, state)
        s1 = (state.get("stages") or {}).get("stage1") or {}

    # Stage 1 already COMPLETE + fresh → unlock Stage 2 READY and stop
    if s1.get("status") == "COMPLETE":
        r1 = load_receipt(folder, "stage1")
        if r1 and r1.get("status") == "COMPLETE":
            ok, _ = hashes_match(folder, r1.get("output_hashes") or {})
            if ok:
                state["stages"]["stage2"]["status"] = "READY"
                state["status"] = "IN_PROGRESS"
                state["active_stage"] = "stage2"
                write_state(folder, state)
                return state

    if stop_at_waiting and not _docs_present(folder):
        if state.get("status") == "WAITING_FOR_LLM":
            return state
        return run_until_waiting_for_llm(
            folder, mode=mode, adopt=False, no_hook=no_hook, force=force
        )

    # Docs on disk → validate to Stage 1 COMPLETE
    if _docs_present(folder):
        # Ensure packet/prompt exist (WAITING receipt) before validate
        if not os.path.exists(os.path.join(folder, "authoring_packet.json")) or not os.path.exists(
            os.path.join(folder, "authoring_prompt.md")
        ):
            state = run_stage1_prompt(folder, state, no_hook=no_hook)
        return run_stage1_validate(folder, state)

    # No docs yet — reach / stay WAITING_FOR_LLM
    if state.get("status") == "WAITING_FOR_LLM":
        return state
    if s1.get("status") in ("WAITING_FOR_LLM",):
        state["status"] = "WAITING_FOR_LLM"
        state["active_stage"] = "stage1"
        write_state(folder, state)
        return state

    return run_until_waiting_for_llm(
        folder, mode=mode, adopt=False, no_hook=no_hook, force=force
    )


def run_until_truth_settled(
    folder: str,
    *,
    mode: str = "production",
    adopt: bool = True,
    no_hook: bool = True,
    force: bool = False,
    stop_at_waiting: bool = False,
    stop_after_stage1: bool = False,
    stop_after_truth: bool = False,
    stop_after_ats: bool = False,
    stop_after_hm: bool = False,
    stop_after_mech: bool = False,
    compile_pdfs: bool = True,
    do_finalize: bool = False,
    finalize_company: str | None = None,
    finalize_title: str | None = None,
    finalize_reach_out: bool | None = None,
    finalize_force: bool = False,
    finalize_db_path: str | None = None,
) -> dict[str, Any]:
    """CR-079–084: Stage 1 → … → Stage 2 policy; optional Stage 3 finalize."""
    folder = _resolve_folder(folder)
    state = run_until_stage1_complete(
        folder,
        mode=mode,
        adopt=adopt,
        no_hook=no_hook,
        force=force,
        stop_at_waiting=stop_at_waiting,
    )
    if stop_after_stage1:
        return state
    if state.get("status") in ("SKIPPED", "WAITING_FOR_LLM", "FAILED", "STALE"):
        return state

    s1 = (state.get("stages") or {}).get("stage1") or {}
    if s1.get("status") != "COMPLETE":
        return state

    state = run_stage2_truth(folder, state)
    if stop_after_truth:
        return state
    if state.get("status") in ("FAILED", "STALE", "SKIPPED"):
        return state
    truth = (state.get("stages") or {}).get("stage2", {}).get("subphases", {}).get("truth") or {}
    if truth.get("status") != "COMPLETE":
        return state

    state = run_stage2_ats(folder, state)
    if stop_after_ats:
        return state
    if state.get("status") in ("FAILED", "STALE", "SKIPPED"):
        return state
    ats = (state.get("stages") or {}).get("stage2", {}).get("subphases", {}).get("ats") or {}
    if ats.get("status") != "COMPLETE":
        return state

    state = run_stage2_hm(folder, state)
    if stop_after_hm:
        return state
    if state.get("status") in ("FAILED", "STALE", "SKIPPED"):
        return state
    hm = (state.get("stages") or {}).get("stage2", {}).get("subphases", {}).get("hm") or {}
    if hm.get("status") != "COMPLETE":
        return state

    state = run_stage2_mech(folder, state, compile_pdfs=compile_pdfs)
    if stop_after_mech:
        return state
    if state.get("status") in ("FAILED", "STALE", "SKIPPED"):
        return state
    mech = (state.get("stages") or {}).get("stage2", {}).get("subphases", {}).get("mech") or {}
    if mech.get("status") != "COMPLETE":
        return state

    state = run_stage2_policy(folder, state)
    if not do_finalize:
        return state
    if state.get("status") in ("FAILED", "STALE", "SKIPPED", "WAITING_FOR_HUMAN"):
        return state
    s2 = (state.get("stages") or {}).get("stage2") or {}
    if s2.get("status") != "COMPLETE":
        return state

    return run_stage3_finalize(
        folder,
        state,
        company=finalize_company,
        title=finalize_title,
        reach_out=finalize_reach_out,
        force=finalize_force,
        db_path=finalize_db_path,
    )


def run_until_waiting_for_llm(
    folder: str,
    *,
    mode: str = "production",
    adopt: bool = True,
    no_hook: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """CR-076 vertical slice entry: Stage 0 then Stage 1 prompt, then stop."""
    folder = _resolve_folder(folder)

    if adopt and load_state(folder) is None:
        state = adopt_existing(folder, mode=mode)
    else:
        state = load_state(folder) or init_state(folder, mode=mode)
        state = _ensure_caller_mode(folder, state, mode, force=force)
        write_state(folder, state)

    state = reconcile(folder, state)

    # Already waiting with fresh prompt?
    if state.get("status") == "WAITING_FOR_LLM":
        r1 = load_receipt(folder, "stage1")
        if r1 and r1.get("status") == "WAITING_FOR_LLM":
            ok, _ = hashes_match(folder, r1.get("output_hashes") or {})
            if ok:
                return state

    if state.get("status") == "SKIPPED":
        return state

    s0 = (state.get("stages") or {}).get("stage0") or {}
    if s0.get("status") == "STALE" or s0.get("status") not in ("COMPLETE", "SKIPPED"):
        state = run_stage0(folder, state, force=force)
        folder = _place_after_stage0(folder, state)
        state = load_state(folder) or state
        if state.get("status") == "SKIPPED":
            return state

    if state.get("status") == "WAITING_FOR_LLM":
        return state

    return run_stage1_prompt(folder, state, no_hook=no_hook)
