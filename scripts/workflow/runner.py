"""CR-076 stage runner: wraps existing workers; never reimplements Stage 0/1 builders."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

_SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import contracts  # noqa: E402
from author_from_packet import build_authoring_prompt, run_verify_only  # noqa: E402
from build_authoring_packet import build_packet  # noqa: E402
from build_stage0_fit_gate import (  # noqa: E402
    Stage0CostAuthorizationNeeded,
    Stage0ExtractError,
    Stage0NeedsInput,
    Stage0RequirementExtractionReviewNeeded,
    build_stage0_fit_gate,
)
from stage_gate import StageGateNotReadyError, require_stage_ready  # noqa: E402

from claim_provenance import check_claim_provenance, check_employer_attribution  # noqa: E402
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
    parse_disposition,
    sync_dispositions_for_phase,
    write_ats_findings,
    write_hm_findings,
    write_truth_findings,
)
from workflow.state import init_state, load_state, utc_now  # noqa: E402
from workflow.observability import append_event, new_run_id  # noqa: E402


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


def _waiting_for_input_has_new_work(folder: str) -> bool:
    """True when a WAITING_FOR_INPUT pause has new input and should resume Stage 0.

    No new input means return the existing receipt and do not re-run Agy.
    """
    receipt = load_receipt(folder, "stage0") or {}
    result = (receipt.get("result") or {}) if isinstance(receipt, dict) else {}
    kind = result.get("pause_kind")
    if kind == "subscription_review":
        if os.path.isfile(os.path.join(folder, "stage0_cascade_import.json")):
            return True
        # Item 9k: a harness-side item-ID omission is a transient, retriable
        # extraction failure, not one that requires a human to paste a
        # manual cascade import -- classify_requirements_batch re-asks only
        # the missing items from spool/cache on its own. Gate only the
        # genuine cost-authorization pauses (no missing_item_ids, no
        # omission reason) behind the manual-import file.
        reason = str(result.get("reason") or "")
        if result.get("missing_item_ids") or "omitted item_ids" in reason:
            return True
        return False
    if kind == "requirement_extraction_review":
        if os.path.isfile(
            os.path.join(folder, "stage0_requirement_extraction_review.json")
        ):
            return True
        # Adapter-off packs paused here with extraction_reason=no_provider.
        # Requeue must re-run Stage 0 once Agy is on; filling the template
        # is the wrong recovery. Same class as the omitted-item-ids retry.
        queue = result.get("queue") or []
        if (
            isinstance(queue, list)
            and queue
            and all(
                isinstance(item, dict)
                and str(item.get("extraction_reason") or "") == "no_provider"
                for item in queue
            )
        ):
            return True
        return False
    if kind == "cost_authorization":
        return False
    if kind == "conversion_risk":
        return os.path.isfile(
            os.path.join(folder, "conversion_risk_apply_anyway.json")
        )
    return True


def _conversion_risk_ready_to_author(folder: str, state: dict[str, Any]) -> bool:
    """True when a conversion_risk pause has apply_anyway and should author."""
    if state.get("status") != "WAITING_FOR_INPUT":
        return False
    receipt = load_receipt(folder, "stage0") or {}
    result = (receipt.get("result") or {}) if isinstance(receipt, dict) else {}
    if result.get("pause_kind") != "conversion_risk":
        return False
    return os.path.isfile(os.path.join(folder, "conversion_risk_apply_anyway.json"))


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


def _queue_db_path() -> Path | None:
    """Resolve the queue DB. Tests must not open production jobagent.sqlite."""
    sandbox = os.environ.get("APPLYR_SANDBOX_DB")
    if sandbox:
        return Path(sandbox)
    if os.environ.get("APPLYR_SYNTHETIC_IDENTITY") == "1":
        return None
    from pipeline_queue import DEFAULT_DB

    return Path(DEFAULT_DB)


def _try_mark_already_handled_queue(slug: str) -> None:
    """Close an unlocked queue row after ALREADY_HANDLED. Implements FR-365.

    No-op if no row or no DB. Leave a live lease (locked_by set or FenceRejected).
    """
    from pipeline_queue import FenceRejected, connect, get_row, mark_done

    db_path = _queue_db_path()
    if db_path is None or not db_path.exists():
        return
    conn = connect(db_path)
    try:
        row = get_row(conn, slug)
        if row is None or row.get("locked_by"):
            return
        mark_done(
            slug,
            conn=conn,
            last_workflow_status="ALREADY_HANDLED",
            last_stage=None,
        )
    except FenceRejected:
        return
    finally:
        conn.close()


def _commit_already_handled(
    folder: str,
    state: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    """Commit the ALREADY_HANDLED terminal. No Stage 1. Implements FR-365."""
    state = commit_stage(
        folder,
        state,
        receipt,
        workflow_status="ALREADY_HANDLED",
        active_stage=None,
    )
    state = dict(state)
    state["active_stage"] = None
    write_state(folder, state)
    slug = str(state.get("slug") or os.path.basename(folder.rstrip("/\\")))
    _try_mark_already_handled_queue(slug)
    return state


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


def _adopt_stage0_from_disk(
    folder: str, state: dict[str, Any], mode: str
) -> tuple[dict[str, Any], bool]:
    """Mint a Stage 0 receipt from an existing, contract-valid stage0_fit_gate.json
    already on disk, without re-running extraction. Returns (state, adopted).

    Why this exists as its own function, not inlined in adopt_existing() (CR-108,
    2026-08-31, found on ebanx_95710d65): a folder can have workflow_state.json
    claiming stage0 COMPLETE with a receipt_id while stage_receipts/stage0.json
    itself is missing on disk (a partial/legacy migration gap, not a real edit).
    reconcile_state_against_receipts() correctly marks that STALE ("receipt_id but
    file missing") -- but the STALE handler in run_until_stage1_complete() used to
    respond to *any* stage0 STALE, including this one, by calling run_stage0(),
    which unconditionally re-runs build_stage0_fit_gate()'s full NLP/LLM extraction
    and overwrites stage0_fit_gate.json. On ebanx_95710d65 that silently replaced a
    real, already-authored-against PASS gate with a garbled SKIP (Original_JD.txt
    itself is corrupted -- undecoded HTML entities, truncated mid-sentence -- so the
    fresh extraction mis-parsed it), which cascaded into archiving the folder as a
    genuine Stage 0 rejection. This function is the same "adopt what's already
    validated on disk" logic that already existed for the *bare* legacy-adoption
    case (no workflow_state.json at all) -- now reused for the *missing-receipt*
    case too, so a lost receipt file can never trigger real re-extraction on its own.
    Re-extraction should only ever happen when there is no valid gate file to adopt,
    or the caller explicitly forces it (see run_stage0's own `force` path).
    """
    stage0_path = os.path.join(folder, "stage0_fit_gate.json")
    if not os.path.exists(stage0_path):
        return state, False
    ok, errors = contracts.check_stage0_fit_gate(folder)
    if not ok:
        return state, False

    existing = load_receipt(folder, "stage0")
    out_hashes = file_hash_map(folder, ["stage0_fit_gate.json"])
    in_hashes = file_hash_map(folder, ["Original_JD.txt"])
    if existing and existing.get("output_hashes") == out_hashes:
        # already adopted
        return state, True

    gate = _load_json(stage0_path)
    verdict = policy.evaluate_stage0(gate)
    if verdict["verdict"] == "SKIP":
        status = "SKIPPED"
        wf_status = "SKIPPED"
        active: str | None = None
    elif verdict["verdict"] == "ALREADY_HANDLED":
        status = "ALREADY_HANDLED"
        wf_status = "ALREADY_HANDLED"
        active = None
    else:
        status = "COMPLETE"
        wf_status = "IN_PROGRESS"
        active = "stage1"
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
            folder, state, receipt, workflow_status=wf_status, active_stage="stage1"
        )
        state["stages"]["stage1"]["status"] = "READY"
        write_state(folder, state)
    elif status == "ALREADY_HANDLED":
        state = _commit_already_handled(folder, state, receipt)
    else:
        state = commit_stage(
            folder, state, receipt, workflow_status=wf_status, active_stage=active
        )
    return state, True


def adopt_existing(folder: str, mode: str = "production") -> dict[str, Any]:
    """Create workflow_state + receipts from valid on-disk artifacts (no rebuild)."""
    state = load_state(folder) or init_state(folder, mode=mode)
    write_state(folder, state)

    state, _ = _adopt_stage0_from_disk(folder, state, mode)

    # Prompt-ready mid-state
    packet_path = os.path.join(folder, "authoring_packet.json")
    prompt_path = os.path.join(folder, "authoring_prompt.md")
    state = load_state(folder) or state
    if (
        state.get("status") not in ("SKIPPED", "ALREADY_HANDLED")
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
    """Build/validate Stage 0 via existing worker; write receipt.

    Observability (2026-08-30 design): start time is captured here, at the top of the wrapper,
    not inside build_receipt -- build_receipt is only ever called after build_stage0_fit_gate()
    already returned, so it has no way to know when the stage's real work began. See
    docs/spec/08-implementation/OBSERVABILITY-DESIGN-2026-08-30-stage0-3-replay-reporting.md §4.1.
    """
    _run_id = new_run_id()
    _t0 = time.time()
    append_event(folder, _run_id, "stage0", "start")

    jd = os.path.join(folder, "Original_JD.txt")
    if not os.path.exists(jd):
        append_event(folder, _run_id, "stage0", "failed", reason="Original_JD.txt not found")
        _persist_stage0_failed(folder, state, "Original_JD.txt not found")
        raise WorkflowError("Original_JD.txt not found")

    gate_path = os.path.join(folder, "stage0_fit_gate.json")
    try:
        result = build_stage0_fit_gate(folder, ignore_skip_ledger=force)
    except Stage0NeedsInput as exc:
        mode = state.get("mode") or "production"
        _duration = round(time.time() - _t0, 3)
        receipt = build_receipt(
            stage="stage0",
            status="WAITING_FOR_INPUT",
            mode=mode,
            input_hashes=file_hash_map(folder, ["Original_JD.txt"]),
            output_hashes={},
            result={
                "pause_kind": "review_center",
                "opportunity_key": exc.opportunity_key,
                "pending_confirmations": exc.pending,
                "duration_seconds": _duration,
            },
            checks={"review_center_confirmations_persisted": True},
        )
        result_state = commit_stage(
            folder,
            state,
            receipt,
            workflow_status="WAITING_FOR_INPUT",
            active_stage="stage0",
        )
        append_event(
            folder,
            _run_id,
            "stage0",
            "waiting_for_input",
            duration_seconds=_duration,
            pending_confirmations=len(exc.pending),
        )
        return result_state
    except Stage0RequirementExtractionReviewNeeded as exc:
        # CR-112: receipt-only pause (PIN 1) -- fires before run_key/
        # request_hash/start_run exist, so no stage0_runs row is created and
        # mark_run_status is never called for this pause.
        mode = state.get("mode") or "production"
        _duration = round(time.time() - _t0, 3)
        receipt = build_receipt(
            stage="stage0",
            status="WAITING_FOR_INPUT",
            mode=mode,
            input_hashes=file_hash_map(
                folder, ["Original_JD.txt", "stage0_requirement_extraction_review.json"]
            ),
            output_hashes={},
            result={
                "pause_kind": "requirement_extraction_review",
                "opportunity_key": exc.opportunity_key,
                "queue": exc.queue,
                "duration_seconds": _duration,
            },
            checks={"requirement_extraction_review_recorded": True},
        )
        result_state = commit_stage(
            folder,
            state,
            receipt,
            workflow_status="WAITING_FOR_INPUT",
            active_stage="stage0",
        )
        append_event(
            folder,
            _run_id,
            "stage0",
            "waiting_for_input",
            duration_seconds=_duration,
            pause_kind="requirement_extraction_review",
            queue_size=len(exc.queue),
        )
        return result_state
    except Stage0CostAuthorizationNeeded as exc:
        mode = state.get("mode") or "production"
        _duration = round(time.time() - _t0, 3)
        pause_kind = exc.pause_kind()
        model_call = bool(exc.model_call_occurred) if pause_kind == "subscription_review" else False
        receipt = build_receipt(
            stage="stage0",
            status="WAITING_FOR_INPUT",
            mode=mode,
            input_hashes=file_hash_map(
                folder, ["Original_JD.txt", "stage0_cascade_import.json"]
            ),
            output_hashes={},
            result={
                "pause_kind": pause_kind,
                "stage": "stage0",
                "attempted_operation": "evidence_classification",
                "authorization_mode": exc.authorization_mode,
                "ineligible_providers": exc.ineligible_providers,
                "model_call_occurred": model_call,
                "cost_applicable": False,
                "cost_known": False,
                "cost_confidence": "unknown",
                "reason": exc.reason,
                "missing_item_ids": list(getattr(exc, "missing_item_ids", []) or []),
                "next_paths": exc.next_paths,
                "resume_command": f"python scripts/run_submission.py {folder} --resume",
                "import_path": os.path.join(folder, "stage0_cascade_import.json"),
                "duration_seconds": _duration,
                "cost_receipt": exc.cost_receipt,
            },
            checks={
                "cost_authorization_required": pause_kind == "cost_authorization",
                "model_call_occurred": model_call,
            },
        )
        result_state = commit_stage(
            folder,
            state,
            receipt,
            workflow_status="WAITING_FOR_INPUT",
            active_stage="stage0",
        )
        append_event(
            folder,
            _run_id,
            "stage0",
            "waiting_for_input",
            duration_seconds=_duration,
            pause_kind=pause_kind,
            reason=exc.reason,
        )
        return result_state
    except Stage0ExtractError as exc:
        append_event(folder, _run_id, "stage0", "failed", reason=str(exc)[:500])
        # 2026-09-21 (nava_benefits): raising here with no state write left
        # workflow_state.json at NOT_STARTED. map_run_result() only recognizes
        # a terminal status, so the queue worker left the row in_progress on
        # an active lease until expiry. Persist FAILED first, same as a
        # Stage 1 over-budget packet.
        _persist_stage0_failed(folder, state, str(exc))
        raise WorkflowError(str(exc)) from exc
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
    _duration = round(time.time() - _t0, 3)
    used_import = bool((result.get("cascade_import") or {}).get("used"))
    consumed_name = None
    if used_import:
        from stage0_evidence_cascade import consume_cascade_import

        consumed_name = consume_cascade_import(folder)
    input_files = ["Original_JD.txt"]
    if consumed_name:
        input_files.append(consumed_name)
    receipt_result = {
        "tier": verdict["tier"],
        "decision": verdict["decision"],
        "reasons": verdict["reasons"],
        "duration_seconds": _duration,
    }
    if used_import:
        receipt_result["cascade_import"] = dict(result.get("cascade_import") or {})
        receipt_result["model_call_occurred"] = False
        receipt_result["cost_applicable"] = False
    if verdict["verdict"] == "SKIP":
        receipt_status = "SKIPPED"
    elif verdict["verdict"] == "ALREADY_HANDLED":
        receipt_status = "ALREADY_HANDLED"
    else:
        receipt_status = "COMPLETE"
    receipt = build_receipt(
        stage="stage0",
        status=receipt_status,
        mode=mode,
        input_hashes=file_hash_map(folder, input_files),
        output_hashes=file_hash_map(folder, ["stage0_fit_gate.json"]),
        result=receipt_result,
        checks={"contracts.check_stage0_fit_gate": True, "policy.evaluate_stage0": verdict["verdict"]},
    )
    # M0.1-M0.3, M0.5, M0.7 signals — see the design doc's metric catalog.
    _event_fields = {
        "duration_seconds": _duration,
        "tier": result.get("tier"),
        "decision": verdict["decision"],
        "fit_score": result.get("fit_score"),
        "confidence_score": result.get("confidence_score"),
        "extraction_source": result.get("extraction_source"),
        "thin_jd": result.get("thin_jd"),
    }

    if verdict["verdict"] == "SKIP":
        append_event(folder, _run_id, "stage0", "skipped", **_event_fields)
        return commit_stage(
            folder,
            state,
            receipt,
            workflow_status="SKIPPED",
            active_stage=None,
        )
    if verdict["verdict"] == "ALREADY_HANDLED":
        append_event(folder, _run_id, "stage0", "already_handled", **_event_fields)
        return _commit_already_handled(folder, state, receipt)
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
        append_event(folder, _run_id, "stage0", "failed", reasons=verdict["reasons"], **_event_fields)
        raise WorkflowError("Stage 0 policy FAIL: " + "; ".join(verdict["reasons"]))

    from pipeline_queue import (
        CONVERSION_RISK_OVERRIDE_NAME,
        PAUSE_KIND_CONVERSION_RISK,
    )

    feasibility = result.get("conversion_feasibility") or {}
    override_path = os.path.join(folder, CONVERSION_RISK_OVERRIDE_NAME)
    if feasibility.get("verdict") == "risk" and not os.path.isfile(override_path):
        receipt_result["pause_kind"] = PAUSE_KIND_CONVERSION_RISK
        receipt_result["conversion_feasibility"] = feasibility
        receipt = build_receipt(
            stage="stage0",
            status="COMPLETE",
            mode=mode,
            input_hashes=file_hash_map(folder, input_files),
            output_hashes=file_hash_map(folder, ["stage0_fit_gate.json"]),
            result=receipt_result,
            checks={
                "contracts.check_stage0_fit_gate": True,
                "policy.evaluate_stage0": verdict["verdict"],
            },
        )
        state = dict(state)
        meta = dict(state.get("metadata") or {})
        meta["pause_kind"] = PAUSE_KIND_CONVERSION_RISK
        state["metadata"] = meta
        append_event(
            folder,
            _run_id,
            "stage0",
            "waiting_for_input",
            pause_kind=PAUSE_KIND_CONVERSION_RISK,
            **_event_fields,
        )
        return commit_stage(
            folder,
            state,
            receipt,
            workflow_status="WAITING_FOR_INPUT",
            active_stage="stage0",
        )

    state = commit_stage(
        folder,
        state,
        receipt,
        workflow_status="IN_PROGRESS",
        active_stage="stage1",
    )
    state["stages"]["stage1"]["status"] = "READY"
    write_state(folder, state)
    append_event(folder, _run_id, "stage0", "complete", **_event_fields)
    return state


_STAGE1_WAITING_OUTPUTS = (
    "authoring_packet.json",
    "authoring_prompt.md",
    "authoring_prompt_meta.json",
)


def _refresh_waiting_stage1_receipt(folder: str, state: dict[str, Any]) -> dict[str, Any]:
    """Keep a WAITING_FOR_LLM receipt aligned with rebuilt packet/prompt files."""
    r1 = load_receipt(folder, "stage1")
    if not r1 or r1.get("status") != "WAITING_FOR_LLM":
        return state
    packet_path = os.path.join(folder, "authoring_packet.json")
    prompt_path = os.path.join(folder, "authoring_prompt.md")
    if not os.path.exists(packet_path) or not os.path.exists(prompt_path):
        return state
    names = [name for name in _STAGE1_WAITING_OUTPUTS if os.path.exists(os.path.join(folder, name))]
    current = file_hash_map(folder, names)
    if current == (r1.get("output_hashes") or {}):
        return state
    r0 = load_receipt(folder, "stage0")
    receipt = build_receipt(
        stage="stage1",
        status="WAITING_FOR_LLM",
        mode=state.get("mode") or "production",
        input_hashes=file_hash_map(folder, ["stage0_fit_gate.json"]),
        output_hashes=current,
        result={**(r1.get("result") or {}), "refreshed_hashes": True},
        checks=r1.get("checks") or {"packet_status_ready": True},
        prior_receipt_id=(r0 or {}).get("receipt_id") or r1.get("prior_receipt_id"),
    )
    return commit_stage(
        folder,
        state,
        receipt,
        workflow_status="WAITING_FOR_LLM",
        active_stage="stage1",
    )


def run_stage1_prompt(folder: str, state: dict[str, Any], *, no_hook: bool = True) -> dict[str, Any]:
    """Build packet + authoring prompt; stop at WAITING_FOR_LLM.

    Observability note: this measures only the mechanical packet/prompt build. The real
    authoring happens in a separate LLM session outside this codebase (no call_llm anywhere in
    build_authoring_packet.py or build_authoring_prompt) — never attribute the elapsed time
    between this stage and run_stage1_validate to "LLM latency"; it's wall-clock time-to-draft,
    which includes whatever the external session took. See the design doc's §1 gap 5 / §3 M1.4.
    """
    _run_id = new_run_id()
    _t0 = time.time()
    append_event(folder, _run_id, "stage1.prompt", "start")
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

    from utils import IdentityError, resolve_identity

    try:
        _profile, identity_source = resolve_identity()
    except IdentityError as exc:
        raise WorkflowError(
            "FAIL [identity] - workExperience.md missing or malformed; "
            "set APPLYR_SYNTHETIC_IDENTITY=1 for test/eval mode, "
            "or copy workExperience.md into this worktree "
            "(identity_source=missing)"
        ) from exc
    state = dict(state)
    meta = dict(state.get("metadata") or {})
    meta["identity_source"] = identity_source
    state["metadata"] = meta

    from pipeline_queue import (
        is_retryable_stage1_budget_failure,
        write_stage1_budget_retry_marker,
    )

    if is_retryable_stage1_budget_failure(Path(folder)):
        write_stage1_budget_retry_marker(Path(folder))

    packet = build_packet(Path(folder), no_hook=no_hook)
    packet_path = os.path.join(folder, "authoring_packet.json")
    with open(packet_path, "w", encoding="utf-8") as f:
        json.dump(packet, f, indent=2, ensure_ascii=False)
        f.write("\n")

    verdict = policy.evaluate_packet(packet)
    if verdict["verdict"] != "PASS":
        reason = "authoring_packet.json not ready (no --force for packet_status):\n  - " + "\n  - ".join(
            verdict["reasons"]
        )
        # 2026-09-20 (clarion_events_inc_north_america, over token budget): this
        # used to raise straight through with no state write, leaving
        # workflow_state.json at whatever it was mid-run (IN_PROGRESS) --
        # map_run_result() only recognizes a terminal status, so the queue
        # worker had nothing to map and the row sat `in_progress` on an
        # active lease until it expired. Persist FAILED first, same as a
        # Stage 1 verify failure, so the worker releases the lease immediately.
        _persist_stage1_failed(folder, state, reason)
        raise WorkflowError(reason)

    prompt_md, meta = build_authoring_prompt(Path(folder), force=False)
    prompt_path = os.path.join(folder, "authoring_prompt.md")
    meta_path = os.path.join(folder, "authoring_prompt_meta.json")
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt_md)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        f.write("\n")

    mode = state.get("mode") or "production"
    _duration = round(time.time() - _t0, 3)
    receipt = build_receipt(
        stage="stage1",
        status="WAITING_FOR_LLM",
        mode=mode,
        input_hashes=file_hash_map(folder, ["stage0_fit_gate.json"]),
        output_hashes=file_hash_map(
            folder,
            ["authoring_packet.json", "authoring_prompt.md", "authoring_prompt_meta.json"],
        ),
        result={"packet_status": "ready", "meta": meta, "duration_seconds": _duration},
        checks={
            "contracts.require_stage_ready.stage0": True,
            "packet_status_ready": True,
        },
        prior_receipt_id=r0.get("receipt_id"),
    )
    result_state = commit_stage(
        folder,
        state,
        receipt,
        workflow_status="WAITING_FOR_LLM",
        active_stage="stage1",
    )
    append_event(folder, _run_id, "stage1.prompt", "waiting_for_llm", duration_seconds=_duration)
    return result_state


def _docs_present(folder: str) -> bool:
    for name in ("Resume.md", "CoverLetter.md"):
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            return False
        try:
            with open(path, encoding="utf-8") as handle:
                if not handle.read().strip():
                    return False
        except OSError:
            return False
    return True


def reconcile(folder: str, state: dict[str, Any]) -> dict[str, Any]:
    """Apply hash cascade; persist if anything went STALE."""
    new_state, reasons = reconcile_state_against_receipts(folder, state, load_receipt)
    if reasons:
        write_state(folder, new_state)
        for r in reasons:
            print(f"STALE: {r}", file=sys.stderr)
    return new_state


def _verify_attempt_count(folder: str) -> int | None:
    """Length of stage1_first_draft/verify_history.json, if present -- CR-097's own per-attempt
    log (see author_from_packet.py::run_verify_only), reused here rather than re-counted."""
    path = os.path.join(folder, "stage1_first_draft", "verify_history.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            history = json.load(f)
        return len(history) if isinstance(history, list) else None
    except (OSError, json.JSONDecodeError):
        return None


def _persist_stage0_failed(folder: str, state: dict[str, Any], reason: str) -> dict[str, Any]:
    """Queue mapping reads workflow status. Stage 0 extract failures must be FAILED."""
    state = dict(state)
    stages = dict(state.get("stages") or {})
    s0_failed = dict(stages.get("stage0") or {})
    s0_failed["status"] = "FAILED"
    stages["stage0"] = s0_failed
    state["stages"] = stages
    state["status"] = "FAILED"
    state["active_stage"] = "stage0"
    meta = dict(state.get("metadata") or {})
    meta["stage0_fail_reason"] = reason[:500]
    state["metadata"] = meta
    write_state(folder, state)
    return state


def _persist_stage1_failed(folder: str, state: dict[str, Any], reason: str) -> dict[str, Any]:
    """Queue mapping reads workflow status. Stage 1 verify/ready failures must be FAILED."""
    state = dict(state)
    stages = dict(state.get("stages") or {})
    s1_failed = dict(stages.get("stage1") or {})
    s1_failed["status"] = "FAILED"
    stages["stage1"] = s1_failed
    state["stages"] = stages
    state["status"] = "FAILED"
    state["active_stage"] = "stage1"
    meta = dict(state.get("metadata") or {})
    meta["stage1_fail_reason"] = reason[:500]
    state["metadata"] = meta
    write_state(folder, state)
    return state


def run_stage1_validate(folder: str, state: dict[str, Any]) -> dict[str, Any]:
    """CR-077: after LLM compose, run verify-only and write Stage 1 COMPLETE receipt."""
    _run_id = new_run_id()
    _t0 = time.time()
    append_event(folder, _run_id, "stage1.validate", "start")
    state = _refresh_waiting_stage1_receipt(folder, state)
    state = reconcile(folder, state)
    s1 = (state.get("stages") or {}).get("stage1") or {}
    if s1.get("status") in ("STALE", "FAILED"):
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
        reason = "check_stage1_ready failed:\n  - " + "\n  - ".join(errors)
        _persist_stage1_failed(folder, state, reason)
        raise WorkflowError(reason)

    # Prior: Stage 0 must still be COMPLETE + fresh
    r0 = load_receipt(folder, "stage0")
    if not r0 or r0.get("status") != "COMPLETE":
        raise WorkflowError("Stage 0 receipt missing or not COMPLETE")
    ok, errs = hashes_match(folder, r0.get("output_hashes") or {})
    if not ok:
        raise WorkflowError("Stage 0 outputs stale:\n  - " + "\n  - ".join(errs))

    # Chain: Stage 1 COMPLETE cites Stage 0's receipt_id (the previous stage),
    # not the Stage 1 WAITING_FOR_LLM receipt (a same-stage intermediate).
    # check_workflow_complete expects a cross-stage chain (stage N → stage N-1),
    # so the WAITING receipt is never part of the final chain.
    prior_id = r0.get("receipt_id")

    verify_ok = run_verify_only(Path(folder), record_to=Path(folder))
    from utils import IdentityError, resolve_identity

    try:
        _profile, identity_source = resolve_identity()
    except IdentityError:
        identity_source = "missing"
    state = dict(state)
    meta = dict(state.get("metadata") or {})
    meta["identity_source"] = identity_source
    state["metadata"] = meta
    # CR-097 Story 1.3: record inside run_verify_only so a failing attempt is
    # persisted before this runner raises WorkflowError.
    if not verify_ok:
        from closed_world_recovery import recover_stage1_extras_guarded
        from packet_closed_world import extra_packet_findings as extra_findings_fn

        packet = None
        provenance = None
        try:
            with open(os.path.join(folder, "authoring_packet.json"), encoding="utf-8") as handle:
                packet = json.load(handle)
            with open(os.path.join(folder, "claim_provenance.json"), encoding="utf-8") as handle:
                provenance = json.load(handle)
        except (OSError, json.JSONDecodeError):
            packet = None
            provenance = None
        extras = (
            extra_findings_fn(packet, provenance)
            if isinstance(packet, dict) and isinstance(provenance, dict)
            else []
        )
        if extras:
            recovery = recover_stage1_extras_guarded(Path(folder), apply=True)
            if recovery.get("status") == "WAITING_FOR_LLM":
                prompt_md, meta = build_authoring_prompt(Path(folder), force=True)
                prompt_path = os.path.join(folder, "authoring_prompt.md")
                meta_path = os.path.join(folder, "authoring_prompt_meta.json")
                with open(prompt_path, "w", encoding="utf-8") as handle:
                    handle.write(prompt_md)
                with open(meta_path, "w", encoding="utf-8") as handle:
                    json.dump(meta, handle, indent=2, ensure_ascii=False)
                    handle.write("\n")
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
                    result={"closed_world_widen": True},
                    checks={"closed_world_recovery.widen": True},
                    prior_receipt_id=prior_id,
                )
                result_state = commit_stage(
                    folder,
                    state,
                    receipt,
                    workflow_status="WAITING_FOR_LLM",
                    active_stage="stage1",
                )
                append_event(folder, _run_id, "stage1.validate", "closed_world_widen")
                return result_state
            if recovery.get("status") == "PAUSE_REVIEW":
                raise WorkflowError(
                    "closed-world recovery paused — see closed_world_recovery.json. "
                    "Record human_decision on the item (REMOVE_EXTRA or WIDEN_PACKET), "
                    "then --resume. This is not NEEDS_DISPOSITION."
                )
            if recovery.get("applied"):
                verify_ok = run_verify_only(Path(folder), record_to=Path(folder))
        if not verify_ok:
            from stage1_prerepair import apply_mechanical_fixes

            auto = apply_mechanical_fixes(Path(folder))
            if auto.get("changed"):
                from build_stage1_repair_prompt import load_repair_state, save_repair_state

                state_payload = load_repair_state(Path(folder))
                state_payload["auto_fixes"] = auto.get("applied") or []
                state_payload["auto_fix_skipped"] = auto.get("skipped") or []
                state_payload["last_outcome"] = "auto_fixed"
                save_repair_state(Path(folder), state_payload)
                verify_ok = run_verify_only(Path(folder), record_to=Path(folder))
        if not verify_ok:
            append_event(
                folder,
                _run_id,
                "stage1.validate",
                "verify_failed",
                duration_seconds=round(time.time() - _t0, 3),
                attempt=_verify_attempt_count(folder),
            )
            reason = "author_from_packet.run_verify_only FAILED — fix docs using packet+digest only"
            _persist_stage1_failed(folder, state, reason)
            raise WorkflowError(reason)

    mode = state.get("mode") or "production"
    out_files = [
        "Resume.md",
        "CoverLetter.md",
        "authoring_packet.json",
    ]
    if os.path.exists(os.path.join(folder, "claim_provenance.json")):
        out_files.append("claim_provenance.json")

    # CR-112 Story 8.3.1: preserve the authoritative pre-edit state on the
    # Stage 1 COMPLETE receipt. If this is a re-validation (Stage 1 was already
    # COMPLETE), the previous COMPLETE receipt's output_hashes become
    # prior_output_hashes on the new receipt, so a later RESOLVED_EDIT can
    # prove an implicated document actually changed since the HM finding —
    # sourced from committed workflow state, never from a reviewer-supplied
    # payload. First-validation folders (previous receipt is WAITING_FOR_LLM)
    # keep the field absent: there is no pre-edit state to cite. Once set, the
    # original prior is carried forward so multi-edit sequences never lose the
    # base against which "changed" is judged.
    prev_s1 = load_receipt(folder, "stage1")
    prior_output_hashes = None
    if prev_s1 and prev_s1.get("status") == "COMPLETE":
        prior_output_hashes = prev_s1.get("prior_output_hashes") or prev_s1.get("output_hashes")

    _duration = round(time.time() - _t0, 3)
    _attempt_count = _verify_attempt_count(folder)
    receipt = build_receipt(
        stage="stage1",
        status="COMPLETE",
        mode=mode,
        input_hashes=file_hash_map(
            folder,
            ["stage0_fit_gate.json", "authoring_packet.json", "authoring_prompt.md"],
        ),
        output_hashes=file_hash_map(folder, out_files),
        prior_output_hashes=prior_output_hashes,
        result={"verify_only": True, "duration_seconds": _duration, "verify_attempts": _attempt_count},
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
    # M1.1/M1.2 — fix-round count reuses CR-097's own verify_history.json rather than
    # re-tracking attempts here; run_verify_only's own docstring caps normal use at 2 fix
    # rounds before escalating, so >2 (attempt_count > 3) is out-of-policy, not just "high."
    append_event(
        folder,
        _run_id,
        "stage1.validate",
        "complete",
        duration_seconds=_duration,
        verify_attempts=_attempt_count,
    )
    write_state(folder, state)
    return state


def _finding_severity_counts(findings_doc: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings_doc.get("findings") or []:
        sev = str(f.get("severity") or "UNKNOWN")
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def _disposition_counts(folder: str, phase: str, findings_doc: dict[str, Any]) -> dict[str, int]:
    """M2.2 — disposition-type distribution for this phase's current findings.
    Reads reviews/dispositions.json directly rather than re-deriving from policy's verdict,
    since the verdict only distinguishes open-vs-resolved, not which enum value was chosen."""
    path = os.path.join(folder, "reviews", "dispositions.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    by_id = doc.get("by_finding_id") or {}
    ids_this_phase = {f.get("id") for f in findings_doc.get("findings") or []}
    counts: dict[str, int] = {}
    for fid, disp in by_id.items():
        if fid not in ids_this_phase:
            continue
        disp_s = str(disp)
        counts[disp_s] = counts.get(disp_s, 0) + 1
    return counts


def _emit_subphase_event(
    folder: str,
    run_id: str,
    phase: str,
    event: str,
    *,
    started_at: float,
    findings_doc: dict[str, Any],
    reasons: list[str] | None = None,
) -> None:
    """Shared Stage 2 subphase observability call — see design doc §3 M2.1/M2.2/M2.3.
    Used by both the inline truth/ats verdict logic and the shared _apply_subphase_verdict
    (hm/mech), so all four subphases get identical fields regardless of which code path they
    take internally."""
    fields: dict[str, Any] = {
        "duration_seconds": round(time.time() - started_at, 3),
        "findings_by_severity": _finding_severity_counts(findings_doc),
        "disposition_counts": _disposition_counts(folder, phase, findings_doc),
    }
    # CR-070 Story 7.1: surface PDF compile timing when available (Mech phase only).
    _pdf_secs = findings_doc.get("pdf_compile_seconds")
    if _pdf_secs is not None:
        fields["pdf_compile_seconds"] = _pdf_secs
    if reasons:
        fields["reasons"] = reasons
    append_event(folder, run_id, f"stage2.{phase}", event, **fields)


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

    # 2. Employer attribution — a bullet citing a claim attributed to a different
    #    employer than the role section it's drafted under is BLOCK, same tier as a
    #    fabricated citation: this is a mechanical mismatch (employer field vs. resume
    #    section), not a judgment call. See check_employer_attribution()'s docstring
    #    (2026-08-31, Papigen) for the real submission this was found on.
    emp_ok, emp_errors = check_employer_attribution(folder)
    if not emp_ok:
        for i, err in enumerate(emp_errors):
            findings.append(
                {
                    "id": f"truth.employer_attribution.{i}",
                    "source": "check_employer_attribution",
                    "severity": "BLOCK",
                    "message": err,
                }
            )

    # 3. Ground-truth coverage — unused JD-relevant claims are WARN
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
            "employer_attribution_ok": emp_ok,
            "ground_truth_coverage_clean": bool(coverage.get("clean"))
            if not coverage.get("error")
            else False,
        },
    }
    write_truth_findings(folder, payload)
    return payload


def run_stage2_truth(folder: str, state: dict[str, Any]) -> dict[str, Any]:
    """CR-079: Stage 2A Truth/Evidence — findings + dispositions; never Stage 2 COMPLETE."""
    _run_id = new_run_id()
    _t0 = time.time()
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
        _emit_subphase_event(folder, _run_id, "truth", "failed", started_at=_t0, findings_doc=findings_doc, reasons=verdict.get("reasons"))
        raise WorkflowError(
            "Truth policy FAIL:\n  - " + "\n  - ".join(verdict.get("reasons") or [])
        )

    if verdict["verdict"] == "NEEDS_DISPOSITION":
        truth["status"] = "NEEDS_DISPOSITION"
        truth["findings_hash"] = fhash
        s2["status"] = "NEEDS_DISPOSITION"
        # Carry integrity only when we later PASS; keep CLEAN while waiting
        state["status"] = "NEEDS_DISPOSITION"
        state["active_stage"] = "stage2"
        write_state(folder, state)
        _emit_subphase_event(folder, _run_id, "truth", "needs_disposition", started_at=_t0, findings_doc=findings_doc)
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
    _emit_subphase_event(folder, _run_id, "truth", "complete", started_at=_t0, findings_doc=findings_doc)
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
    _run_id = new_run_id()
    _t0 = time.time()
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
        _emit_subphase_event(folder, _run_id, "ats", "failed", started_at=_t0, findings_doc=findings_doc, reasons=verdict.get("reasons"))
        raise WorkflowError(
            "ATS policy FAIL:\n  - " + "\n  - ".join(verdict.get("reasons") or [])
        )

    if verdict["verdict"] == "NEEDS_DISPOSITION":
        ats["status"] = "NEEDS_DISPOSITION"
        ats["findings_hash"] = fhash
        s2["status"] = "NEEDS_DISPOSITION"
        state["status"] = "NEEDS_DISPOSITION"
        state["active_stage"] = "stage2"
        write_state(folder, state)
        _emit_subphase_event(folder, _run_id, "ats", "needs_disposition", started_at=_t0, findings_doc=findings_doc)
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
    _emit_subphase_event(folder, _run_id, "ats", "complete", started_at=_t0, findings_doc=findings_doc)
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
    run_id: str | None = None,
    started_at: float | None = None,
) -> dict[str, Any]:
    """Shared disposition → subphase COMPLETE / WAITING / FAIL helper.

    run_id/started_at are optional (default to a fresh id / now) so any caller that predates this
    instrumentation still works unchanged — only hm/mech pass real ones today."""
    _run_id = run_id or new_run_id()
    _t0 = started_at if started_at is not None else time.time()
    dispositions = sync_dispositions_for_phase(folder, phase, findings_doc)
    verdict = policy.evaluate_truth_findings(findings_doc, dispositions)
    fhash = findings_content_hash(findings_doc)
    s2 = state["stages"]["stage2"]
    phase_rec = s2["subphases"][phase]

    # CR-112 Story 8.3: hm.critical_read structured review artifact validation.
    # After the policy verdict, if phase is "hm" and the verdict is PASS,
    # validate that any hm.critical_read disposition includes a structured
    # review artifact. This is a substance gate — the existing policy only
    # checks reasoning length, not review evidence. Implements FR-319 / AC-417.
    if phase == "hm" and verdict["verdict"] == "PASS":
        from hm_review_contract import HM_REVIEW_DISPOSITIONS, validate_hm_review
        findings_list = findings_doc.get("findings") or []
        by_id = dispositions.get("by_finding_id") or {}
        hm_errors: list[str] = []
        for item in findings_list:
            if not isinstance(item, dict):
                continue
            fid = str(item.get("id") or "")
            if fid != "hm.critical_read":
                continue
            disp_value = by_id.get(fid)
            disp_s, _ = parse_disposition(disp_value)
            if disp_s in HM_REVIEW_DISPOSITIONS:
                # CR-112 Story 8.3.1: bind the finding's own implicated
                # documents into evidence validation so RESOLVED_EDIT must
                # prove a change to a document the finding actually covers.
                ok, errs = validate_hm_review(
                    folder, disp_value, implicated_documents=item.get("implicated_documents")
                )
                if not ok:
                    hm_errors.extend(errs)
        if hm_errors:
            verdict = {
                "verdict": "NEEDS_DISPOSITION",
                "integrity": "CLEAN",
                "open_finding_ids": ["hm.critical_read"],
                "reasons": hm_errors,
            }

    if verdict["verdict"] == "FAIL":
        phase_rec["status"] = "FAILED"
        phase_rec["findings_hash"] = fhash
        s2["status"] = "FAILED"
        state["status"] = "FAILED"
        state["active_stage"] = "stage2"
        write_state(folder, state)
        _emit_subphase_event(folder, _run_id, phase, "failed", started_at=_t0, findings_doc=findings_doc, reasons=verdict.get("reasons"))
        raise WorkflowError(
            f"{fail_label} policy FAIL:\n  - "
            + "\n  - ".join(verdict.get("reasons") or [])
        )

    if verdict["verdict"] == "NEEDS_DISPOSITION":
        phase_rec["status"] = "NEEDS_DISPOSITION"
        phase_rec["findings_hash"] = fhash
        s2["status"] = "NEEDS_DISPOSITION"
        state["status"] = "NEEDS_DISPOSITION"
        state["active_stage"] = "stage2"
        write_state(folder, state)
        _emit_subphase_event(folder, _run_id, phase, "needs_disposition", started_at=_t0, findings_doc=findings_doc)
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
    _emit_subphase_event(folder, _run_id, phase, "complete", started_at=_t0, findings_doc=findings_doc)
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
    # CR-112 Story 8.3.1: implicated_documents names the files covered by the
    # read (Resume.md + CoverLetter.md). It is stamped here from code, not
    # supplied by the reviewer, and binds evidence validation so a RESOLVED_EDIT
    # on the finding must prove a change to one of *these* documents — an
    # unrelated file edit cannot clear the gate.
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
            "implicated_documents": [doc if os.path.exists(os.path.join(folder, doc)) else f"{doc} (missing)" for doc in ("Resume.md", "CoverLetter.md")],
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
    _run_id = new_run_id()
    _t0 = time.time()
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
        run_id=_run_id,
        started_at=_t0,
    )


def _compile_pdfs(folder: str) -> None:
    """Shell out to compile_single.py for Resume + CoverLetter (existing worker).

    2026-09-01: compile both PDFs in parallel (two subprocess.Popen instances)
    instead of sequentially. Falls back to sequential if the parallel compile
    fails on either file, so a resource-contention failure is retried safely.
    """
    import subprocess

    py = sys.executable
    script = os.path.join(_SCRIPT_DIR, "compile_single.py")
    cwd = os.path.dirname(_SCRIPT_DIR)

    jobs: list[tuple[str, str, str, str]] = []  # (md_name, pdf_name, md_path, pdf_path)
    for md_name, pdf_name in (("Resume.md", "Resume.pdf"), ("CoverLetter.md", "CoverLetter.pdf")):
        md = os.path.join(folder, md_name)
        pdf = os.path.join(folder, pdf_name)
        if not os.path.exists(md):
            raise WorkflowError(f"{md_name} missing — cannot compile")
        jobs.append((md_name, pdf_name, md, pdf))

    # Parallel compile
    procs: list[tuple[str, subprocess.Popen]] = []
    for md_name, pdf_name, md, pdf in jobs:
        procs.append((md_name, subprocess.Popen(
            [py, script, md, pdf],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )))

    errors: list[str] = []
    for md_name, proc in procs:
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            errors.append(f"compile_single failed for {md_name}:\n{stderr or stdout}")

    if errors:
        # Fallback: retry failed files sequentially (resource contention recovery)
        if len(errors) == 1:
            # One succeeded, one failed — retry the failed one sequentially
            for md_name, pdf_name, md, pdf in jobs:
                if md_name == errors[0].split("for ")[1].split(":")[0]:
                    proc = subprocess.run(
                        [py, script, md, pdf], cwd=cwd, capture_output=True, text=True
                    )
                    if proc.returncode != 0:
                        raise WorkflowError(
                            f"compile_single failed for {md_name} (sequential retry):\n"
                            f"{proc.stderr or proc.stdout}"
                        )
                    return
        raise WorkflowError("\n".join(errors))


def _rubric_floor_findings(score: Any) -> list[dict[str, Any]]:
    """Emit BLOCK findings when numeric rubric totals sit below CONVERT-READY floors.

    Shape errors stay on mech.rubric_score_required (WARN). A leftover
    ACCEPTED_AS_CORRECT on that WARN cannot bind these ids.
    """
    # Implements FR-318 / AC-415
    shape = contracts._check_rubric_score_shape(score)
    if shape:
        return []
    findings: list[dict[str, Any]] = []
    for err in contracts.check_rubric_floors(score):
        side = "cover_letter" if "cover_letter" in err else "resume"
        findings.append(
            {
                "id": f"mech.rubric_floor.{side}",
                "source": "workflow",
                "severity": "BLOCK",
                "message": err,
            }
        )
    return findings


def _rubric_provenance_findings(folder: str, score: Any) -> list[dict[str, Any]]:
    # Implements FR-322 / AC-420. Only runs after shape and floor checks pass;
    # below-floor scores already have objective BLOCK findings.
    shape = contracts._check_rubric_score_shape(score)
    if shape or contracts.check_rubric_floors(score):
        return []
    findings: list[dict[str, Any]] = []
    for idx, err in enumerate(contracts.check_rubric_score_provenance(folder, score)):
        findings.append(
            {
                "id": f"mech.rubric_score_provenance.{idx}",
                "source": "workflow",
                "severity": "BLOCK",
                "message": err,
            }
        )
    return findings


def _require_completion_rubric_floors(folder: str) -> None:
    """Fail closed before minting Stage 3 when rubric totals are below floor.

    Shape first, then floors. Does not call check_finalize_ready (practice
    may skip freshness / verification_passed / DB extras). force=True cannot
    skip this helper.
    """
    # Implements FR-318 / AC-415
    manifest_path = os.path.join(folder, "draft_manifest.json")
    manifest, err = contracts.load_json(manifest_path)
    if err:
        raise WorkflowError(f"Cannot finalize: {err}")
    score = None if manifest is None else manifest.get("rubric_score")
    shape_errs = contracts._check_rubric_score_shape(score)
    floor_errs = [] if shape_errs else contracts.check_rubric_floors(score)
    provenance_errs = []
    if not shape_errs and not floor_errs:
        provenance_errs = contracts.check_rubric_score_provenance(folder, score)
    errs = [f"draft_manifest.json: {e}" for e in (shape_errs + floor_errs + provenance_errs)]
    if errs:
        raise WorkflowError(
            "Cannot finalize: CONVERT-READY rubric floors not met:\n  - "
            + "\n  - ".join(errs)
        )


def collect_mech_findings(folder: str, *, compile_pdfs: bool = True) -> dict[str, Any]:
    """Compile PDFs + verify_one; surface failures as findings."""
    findings: list[dict[str, Any]] = []
    _pdf_compile_seconds: float | None = None
    if compile_pdfs:
        _compile_t0 = time.time()
        try:
            _compile_pdfs(folder)
        except WorkflowError as exc:
            _pdf_compile_seconds = round(time.time() - _compile_t0, 3)
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
                "pdf_compile_seconds": _pdf_compile_seconds,
            }
            # Write under reviews for consistency
            path = os.path.join(folder, "reviews", "mech_findings.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                f.write("\n")
            return payload
        _pdf_compile_seconds = round(time.time() - _compile_t0, 3)

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
    score = None
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
    else:
        findings.extend(_rubric_floor_findings(score))
        findings.extend(_rubric_provenance_findings(folder, score))

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
        "pdf_compile_seconds": _pdf_compile_seconds,
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
    _run_id = new_run_id()
    _t0 = time.time()
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
        run_id=_run_id,
        started_at=_t0,
    )


def run_stage2_policy(folder: str, state: dict[str, Any]) -> dict[str, Any]:
    """CR-081: Stage 2E — write Stage 2 COMPLETE receipt when all subphases + check_stage2_ready."""
    _run_id = new_run_id()
    _t0 = time.time()
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
        sub["policy"]["status"] = "NEEDS_DISPOSITION"
        sub["policy"]["blockers"] = errors
        s2["status"] = "NEEDS_DISPOSITION"
        state["status"] = "NEEDS_DISPOSITION"
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
        append_event(
            folder, _run_id, "stage2.policy", "needs_disposition",
            duration_seconds=round(time.time() - _t0, 3), blockers=errors,
        )
        return state

    # All clear — mint Stage 2 COMPLETE receipt
    mode = state.get("mode") or "production"
    integrity = s2.get("integrity") or "CLEAN"
    # Resume.pdf/CoverLetter.pdf are deliberately NOT hashed into output_hashes:
    # Chromium's page.pdf() (compile_single.py) stamps a fresh /CreationDate and
    # /ModDate on every render, so a byte hash of the compiled PDF churns even when
    # the reviewed content is unchanged. That false churn was flipping already-COMPLETE
    # submissions to STALE (invalidate.py's reconcile cascade locks stage3) and failing
    # check_workflow_complete purely from an incidental recompile (see amphenol_rf,
    # replay_log.md entry 3 + follow-up). Content fidelity is still protected here via
    # the Resume.md/CoverLetter.md hashes below -- those are the documents Stage 2
    # actually reviewed, and they don't carry a render-time timestamp.
    out_files = [
        "Resume.md",
        "CoverLetter.md",
        "verification_receipt.json",
    ]
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
    _run_advisory_defect_scan()
    # M3.2 — integrity=OVERRIDDEN here is the real Stage 2 quality signal, not the plain
    # completion fact; keep it in the event, never averaged away in a batch report.
    append_event(
        folder, _run_id, "stage2.policy", "complete",
        duration_seconds=round(time.time() - _t0, 3), integrity=integrity,
    )
    return state


def _run_advisory_defect_scan() -> None:
    """CR-097 Story 2.5: best-effort ledger scan after Stage 2 COMPLETE.

    Prints only. Never writes workflow_state / receipts / subphase status,
    and never changes the command's exit code.
    """
    try:
        from scan_authoring_defects import run_advisory_scan

        run_advisory_scan()
    except Exception as exc:
        print(f"[defect_scan, status: warning] {exc}")


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
    _run_id = new_run_id()
    _t0 = time.time()
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

    # CR-112: floors are not skipped by practice mode or --force. Production
    # --force may still skip check_finalize_ready extras (freshness, etc.)
    # inside finalize_job; it cannot mint a below-floor Stage 3 receipt.
    _require_completion_rubric_floors(folder)

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
            append_event(folder, _run_id, "stage3", "failed", duration_seconds=round(time.time() - _t0, 3), reason=str(exc)[:500])
            raise WorkflowError(str(exc)) from exc
        except ImplausibleJobTitleError as exc:
            append_event(folder, _run_id, "stage3", "failed", duration_seconds=round(time.time() - _t0, 3), reason=str(exc)[:500])
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

    _duration = round(time.time() - _t0, 3)
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
            "duration_seconds": _duration,
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
    # M3.1/M3.2 — wf_status distinguishes COMPLETE from COMPLETE_WITH_OVERRIDE/PRACTICE_COMPLETE;
    # never collapse integrity into a plain "success" boolean in any downstream report.
    append_event(
        folder, _run_id, "stage3", "complete",
        duration_seconds=_duration, workflow_status=wf_status, integrity=integrity,
    )
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

    state = _refresh_waiting_stage1_receipt(folder, state)
    state = reconcile(folder, state)

    if state.get("status") in ("SKIPPED", "ALREADY_HANDLED"):
        return state

    s0 = (state.get("stages") or {}).get("stage0") or {}
    if s0.get("status") == "STALE":
        # CR-108: a STALE here can mean "receipt file missing, content on disk is
        # still valid" (a legacy-migration gap), not "the input actually changed".
        # Try adopting the existing stage0_fit_gate.json in place first -- only
        # fall through to a real re-extraction (run_stage0, which overwrites the
        # gate file) when there's nothing valid on disk to adopt. See
        # _adopt_stage0_from_disk's docstring for the incident this fixes.
        if not force:
            state, adopted = _adopt_stage0_from_disk(folder, state, state.get("mode") or "production")
        else:
            adopted = False
        if not adopted:
            state = run_stage0(folder, state, force=force)
        folder = _place_after_stage0(folder, state)
        state = load_state(folder) or state
        if state.get("status") in ("SKIPPED", "ALREADY_HANDLED"):
            return state

    s0 = (state.get("stages") or {}).get("stage0") or {}
    s1 = (state.get("stages") or {}).get("stage1") or {}

    # Need Stage 0 COMPLETE before prompt/validate
    if s0.get("status") not in ("COMPLETE", "SKIPPED", "ALREADY_HANDLED"):
        state = run_until_waiting_for_llm(
            folder, mode=mode, adopt=False, no_hook=no_hook, force=force
        )
        # Bug found live 2026-08-19: run_until_waiting_for_llm() moves the
        # folder internally (_place_after_stage0() promotes a Stage 0 PASS to
        # submissions/, or a SKIP to archive/skipped/) but only returns
        # `state`, not the new path -- this function's own `folder` local kept
        # pointing at the now-emptied pending_review location. The next line
        # used to be `reconcile(folder, state)` against that stale path: it
        # correctly has real receipt_ids (the promoted folder's), but the
        # receipt FILES live at the new location, so reconcile always found
        # them "missing" and marked stage0 STALE, which then made
        # run_stage0() below raise "Original_JD.txt not found" against the
        # same stale path -- on every single fresh JD that passed Stage 0,
        # not an edge case.
        if state.get("status") in ("SKIPPED", "ALREADY_HANDLED"):
            return state
        if state.get("status") == "WAITING_FOR_INPUT":
            return state
        # Re-resolve by slug (state["slug"] is always the bare folder name,
        # and _resolve_folder() checks submissions/ before pending_review/)
        # before doing anything else with `folder` -- lands on the real
        # current location for a PASS. A SKIPPED state returns above instead
        # of re-resolving: _resolve_folder() doesn't search archive/skipped/,
        # same as the STALE-branch a few lines up already handles this.
        # Fallback (2026-09-08, --mode practice run under data/authored_drafts/):
        # _place_after_stage0 never moves unmanaged folders, so when bare-slug
        # resolution fails (folder outside submissions|pending_review) the
        # original absolute `folder` is still valid -- keep it instead of
        # raising after Stage 1 receipts were already committed.
        try:
            folder = _resolve_folder(state.get("slug") or folder)
        except WorkflowError:
            if not os.path.isdir(folder):
                raise
        state = reconcile(folder, state)
        s1 = (state.get("stages") or {}).get("stage1") or {}

    if state.get("status") == "WAITING_FOR_INPUT":
        return state
    s0 = (state.get("stages") or {}).get("stage0") or {}
    if s0.get("status") == "WAITING_FOR_INPUT":
        return state

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


def _pre_collect_stage2_findings(folder: str, phases: list[str]) -> None:
    """2026-09-01: Pre-collect findings and sync dispositions for remaining Stage 2
    subphases so the agent can dispose all findings in one --resume cycle instead
    of one per subphase. Only collects for lightweight subphases (ats, hm) — Mech
    is skipped because it requires PDF compilation."""
    for phase in phases:
        if phase == "ats":
            findings_doc = collect_ats_findings(folder)
        elif phase == "hm":
            findings_doc = collect_hm_findings(folder)
        else:
            continue
        sync_dispositions_for_phase(folder, phase, findings_doc)


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
    if state.get("status") in (
        "SKIPPED",
        "ALREADY_HANDLED",
        "WAITING_FOR_LLM",
        "WAITING_FOR_INPUT",
        "FAILED",
        "STALE",
    ):
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
        # 2026-09-01: pre-collect findings from remaining subphases so the agent
        # can dispose all WARN findings in one --resume cycle instead of one per
        # subphase. Only for NEEDS_DISPOSITION (not FAILED/STALE/SKIPPED).
        if truth.get("status") == "NEEDS_DISPOSITION":
            _pre_collect_stage2_findings(folder, ["ats", "hm"])
        return state

    state = run_stage2_ats(folder, state)
    if stop_after_ats:
        return state
    if state.get("status") in ("FAILED", "STALE", "SKIPPED"):
        return state
    ats = (state.get("stages") or {}).get("stage2", {}).get("subphases", {}).get("ats") or {}
    if ats.get("status") != "COMPLETE":
        if ats.get("status") == "NEEDS_DISPOSITION":
            _pre_collect_stage2_findings(folder, ["hm"])
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
    if state.get("status") in ("FAILED", "STALE", "SKIPPED", "NEEDS_DISPOSITION"):
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

    # --force is the explicit recovery path for a prior Stage 0 decision,
    # such as a corrected gate rule. Do not let the terminal status return
    # before run_stage0 has a chance to rebuild the gate.
    if state.get("status") in ("SKIPPED", "ALREADY_HANDLED") and not force:
        return state

    if state.get("status") == "WAITING_FOR_INPUT" and not force:
        if not _waiting_for_input_has_new_work(folder):
            return state

    s0 = (state.get("stages") or {}).get("stage0") or {}
    if force or s0.get("status") == "STALE" or s0.get("status") not in (
        "COMPLETE",
        "SKIPPED",
        "ALREADY_HANDLED",
    ):
        # CR-108: same missing-receipt-vs-real-change distinction as
        # run_until_stage1_complete above -- try adopting an already-valid
        # stage0_fit_gate.json before falling through to real re-extraction.
        adopted = False
        if not force and s0.get("status") == "STALE":
            state, adopted = _adopt_stage0_from_disk(folder, state, state.get("mode") or "production")
        if not adopted:
            state = run_stage0(folder, state, force=force)
        folder = _place_after_stage0(folder, state)
        state = load_state(folder) or state
        if state.get("status") in ("SKIPPED", "ALREADY_HANDLED"):
            return state

    if state.get("status") in ("WAITING_FOR_LLM", "WAITING_FOR_INPUT"):
        if not _conversion_risk_ready_to_author(folder, state):
            return state

    return run_stage1_prompt(folder, state, no_hook=no_hook)
