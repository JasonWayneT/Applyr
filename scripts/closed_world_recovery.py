#!/usr/bin/env python3
"""CR-112 Story 3.6 — closed-world recovery after extra-packet detection.

Implements FR-315 / AC-412. Detection stays in packet_closed_world.py.
This module plans and (optionally) applies recovery. It never writes
workflow_state.json or stage_receipts/. The orchestrator is the sole
receipt writer.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from evidence_dominance import compare_pair
from packet_closed_world import extra_packet_claim_ids, extra_packet_findings
_REPO_ROOT = _SCRIPT_DIR.parent
_WORKFLOW_FILES = frozenset({"workflow_state.json"})
_RECEIPT_DIR = "stage_receipts"
LEAKED_DIR = "leaked_draft"
REPORT_NAME = "closed_world_recovery.json"

AUTO_ACTIONS = frozenset({"REMOVE_EXTRA", "REWRITE_UNSUPPORTED", "WIDEN_PACKET"})
PAUSE_ACTIONS = frozenset({"QUALITATIVE_REVIEW", "HUMAN_COMPARE"})
OMITTED_REASONS = frozenset({"top2_cutoff", "project_slot_cap"})


def _load_json(path: Path) -> Any | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_claims(claims: dict[str, dict] | None = None) -> dict[str, dict]:
    if claims is not None:
        return claims
    for name in ("master_claims_tags_only.json", "master_claims.json"):
        path = _REPO_ROOT / "data" / name
        payload = _load_json(path)
        if isinstance(payload, dict):
            records = payload.get("claims") if isinstance(payload.get("claims"), dict) else payload
            if isinstance(records, dict):
                return {
                    str(cid): rec
                    for cid, rec in records.items()
                    if isinstance(rec, dict)
                }
    return {}


def _trace_bindings(trace: dict[str, Any] | None, cid: str) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    if not isinstance(trace, dict):
        return bindings
    for item in trace.get("items") or []:
        if not isinstance(item, dict):
            continue
        for candidate in item.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            if candidate.get("claim_id") != cid:
                continue
            reason = candidate.get("reason")
            if reason not in OMITTED_REASONS:
                continue
            try:
                score = int(candidate.get("score") or 0)
            except (TypeError, ValueError):
                score = 0
            picked = [c for c in (item.get("picked") or []) if isinstance(c, str)]
            score_by_id = {}
            for row in item.get("candidates") or []:
                if isinstance(row, dict) and isinstance(row.get("claim_id"), str):
                    try:
                        score_by_id[row["claim_id"]] = int(row.get("score") or 0)
                    except (TypeError, ValueError):
                        score_by_id[row["claim_id"]] = 0
            bindings.append(
                {
                    "jd_item": str(item.get("jd_item") or ""),
                    "bucket": str(item.get("bucket") or ""),
                    "reason": str(reason),
                    "score": score,
                    "picked": picked,
                    "score_by_id": score_by_id,
                }
            )
    return bindings


def _packet_picked_ids(packet: dict[str, Any]) -> list[str]:
    picked: list[str] = []
    for row in packet.get("evidence_map") or []:
        if not isinstance(row, dict):
            continue
        for cid in row.get("claim_ids") or []:
            if isinstance(cid, str) and cid:
                picked.append(cid)
    return picked


def _counts_from_packet(
    packet: dict[str, Any], claims: dict[str, dict]
) -> tuple[dict[str, int], dict[str, int]]:
    project_counts: dict[str, int] = {}
    employer_counts: dict[str, int] = {}
    for cid in _packet_picked_ids(packet):
        rec = claims.get(cid) or {}
        proj = str(rec.get("project_id") or cid)
        emp = str(rec.get("employer") or "").strip().lower()
        project_counts[proj] = project_counts.get(proj, 0) + 1
        if emp:
            employer_counts[emp] = employer_counts.get(emp, 0) + 1
    return project_counts, employer_counts


def _plan_one(
    cid: str,
    *,
    packet: dict[str, Any],
    trace: dict[str, Any] | None,
    claims: dict[str, dict],
    catalog_missing: bool,
) -> dict[str, Any]:
    rec = claims.get(cid) or {}
    if catalog_missing:
        return {
            "claim_id": cid,
            "action": "HUMAN_COMPARE",
            "comparator_decision": None,
            "reason": "missing_catalog",
            "bindings": [],
        }
    if not rec or rec.get("disabled") is True or rec.get("prohibited") is True:
        return {
            "claim_id": cid,
            "action": "REWRITE_UNSUPPORTED",
            "comparator_decision": "INELIGIBLE",
            "reason": "unsupported_or_prohibited",
            "bindings": [],
        }
    constraints = packet.get("claim_constraints") or {}
    if isinstance(constraints, dict):
        for row in constraints.values():
            if not isinstance(row, dict):
                continue
            prohibited = [str(item) for item in (row.get("prohibited_claims") or [])]
            if cid in prohibited:
                return {
                    "claim_id": cid,
                    "action": "HUMAN_COMPARE",
                    "comparator_decision": None,
                    "reason": "we_constraint_conflict",
                    "bindings": [],
                }

    bindings = _trace_bindings(trace, cid)
    if not bindings:
        return {
            "claim_id": cid,
            "action": "REMOVE_EXTRA",
            "comparator_decision": None,
            "reason": "not_in_trace_omitted",
            "bindings": [],
        }

    project_counts, employer_counts = _counts_from_packet(packet, claims)
    packet_picked = _packet_picked_ids(packet)
    decisions: list[dict[str, Any]] = []
    for bind in bindings:
        picked = bind["picked"]
        if not picked:
            decisions.append({"decision": "KEEP", "bind": bind, "result": None})
            continue
        scores = bind["score_by_id"]
        cid_b = min(picked, key=lambda item: (scores.get(item, 0), item))
        result = compare_pair(
            cid_a=cid,
            score_a=bind["score"],
            cid_b=cid_b,
            score_b=scores.get(cid_b, 0),
            claims=claims,
            jd_item=bind["jd_item"],
            jd_text="",
            packet_picked_ids=packet_picked,
            employer_counts=employer_counts,
            project_counts=project_counts,
            max_slots_per_project=4,
            omitted_reason=bind["reason"],
            class_kind=2,
        )
        decisions.append({"decision": result["decision"], "bind": bind, "result": result})

    labels = [row["decision"] for row in decisions]
    if any(label == "INELIGIBLE" for label in labels):
        action = "REWRITE_UNSUPPORTED"
        reason = "ineligible"
    elif labels and all(label == "REPLACE" for label in labels):
        action = "WIDEN_PACKET"
        reason = "same_item_trace_replace"
    elif any(label == "AMBIGUOUS" for label in labels):
        sibling_or_redundant = any(
            ((row["result"] or {}).get("axes") or {}).get("distinctiveness") == "B_better"
            for row in decisions
        )
        if sibling_or_redundant:
            action = "REMOVE_EXTRA"
            reason = "not_distinctive"
        else:
            action = "QUALITATIVE_REVIEW"
            reason = "ambiguous_class2"
    else:
        action = "REMOVE_EXTRA"
        reason = "not_stronger"

    first = next((row["result"] for row in decisions if row["result"]), None)
    return {
        "claim_id": cid,
        "action": action,
        "comparator_decision": first["decision"] if first else labels[0] if labels else None,
        "anchor_id": first.get("anchor_id") if first else None,
        "axes": first.get("axes") if first else {},
        "candidate_id": cid,
        "reason": reason,
        "bindings": [
            {
                "jd_item": row["bind"]["jd_item"],
                "anchor_id": (row["result"] or {}).get("anchor_id"),
                "decision": row["decision"],
                "axes": (row["result"] or {}).get("axes") or {},
            }
            for row in decisions
        ],
    }


def plan_recovery(
    folder: Path,
    *,
    claims: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """Plan recovery. Does not edit drafts, packets, or workflow files."""
    packet = _load_json(folder / "authoring_packet.json")
    provenance = _load_json(folder / "claim_provenance.json")
    if not isinstance(packet, dict) or not isinstance(provenance, dict):
        return {
            "schema_version": "1.0",
            "status": "PAUSE_REVIEW",
            "items": [
                {
                    "claim_id": "unknown",
                    "action": "HUMAN_COMPARE",
                    "reason": "unreadable_packet_or_provenance",
                }
            ],
        }

    catalog = _load_claims(claims)
    catalog_missing = claims is None and not catalog
    trace = _load_json(folder / "evidence_selection_trace.json")
    extras = extra_packet_claim_ids(packet, provenance)
    findings = extra_packet_findings(packet, provenance)
    items = [
        _plan_one(
            cid,
            packet=packet,
            trace=trace if isinstance(trace, dict) else None,
            claims=catalog,
            catalog_missing=catalog_missing,
        )
        for cid in extras
    ]
    existing = _load_json(folder / REPORT_NAME)
    if isinstance(existing, dict):
        prior = {
            str(row.get("claim_id")): row.get("human_decision")
            for row in (existing.get("items") or [])
            if isinstance(row, dict) and row.get("human_decision")
        }
        for item in items:
            decision = prior.get(item["claim_id"])
            if decision in AUTO_ACTIONS:
                item["human_decision"] = decision
                item["action"] = decision
    pause = any(item["action"] in PAUSE_ACTIONS for item in items)
    status = "PAUSE_REVIEW" if pause else "READY_TO_APPLY"
    if not items and not findings:
        status = "NO_EXTRAS"
    return {
        "schema_version": "1.0",
        "status": status,
        "items": items,
        "finding_ids": [row.get("id") for row in findings],
    }


def _drop_text_unit(doc: str, unit: str) -> str:
    unit = (unit or "").strip()
    if not unit or not doc:
        return doc
    lines = doc.splitlines(keepends=True)
    kept: list[str] = []
    skipped = False
    for line in lines:
        stripped = re.sub(r"^\s*[*-]\s+", "", line).strip()
        if stripped.rstrip(".!?") == unit.rstrip(".!?"):
            skipped = True
            continue
        if unit in stripped and len(unit) > 12:
            skipped = True
            continue
        kept.append(line)
    if skipped:
        return "".join(kept)
    return doc.replace(unit, "")


def _apply_remove_or_rewrite(folder: Path, extra_ids: set[str]) -> None:
    provenance = _load_json(folder / "claim_provenance.json")
    if not isinstance(provenance, dict):
        return
    resume = (folder / "Resume.md").read_text(encoding="utf-8") if (folder / "Resume.md").exists() else ""
    cover = (
        (folder / "CoverLetter.md").read_text(encoding="utf-8")
        if (folder / "CoverLetter.md").exists()
        else ""
    )
    new_prov = dict(provenance)
    for section, path_name in (
        ("resume_claims", "Resume.md"),
        ("cover_letter_claims", "CoverLetter.md"),
    ):
        kept_rows = []
        doc = resume if path_name == "Resume.md" else cover
        for row in provenance.get(section) or []:
            if not isinstance(row, dict):
                continue
            ids = [cid for cid in (row.get("claim_ids") or []) if isinstance(cid, str)]
            extras_here = [cid for cid in ids if cid in extra_ids]
            if not extras_here:
                kept_rows.append(row)
                continue
            remaining = [cid for cid in ids if cid not in extra_ids]
            unit = str(row.get("bullet") or row.get("text") or "")
            if remaining:
                new_row = dict(row)
                new_row["claim_ids"] = remaining
                kept_rows.append(new_row)
            else:
                doc = _drop_text_unit(doc, unit)
        new_prov[section] = kept_rows
        if path_name == "Resume.md":
            resume = doc
        else:
            cover = doc
    if (folder / "Resume.md").exists():
        (folder / "Resume.md").write_text(resume, encoding="utf-8")
    if (folder / "CoverLetter.md").exists():
        (folder / "CoverLetter.md").write_text(cover, encoding="utf-8")
    _write_json(folder / "claim_provenance.json", new_prov)


def _invalidate_leaked_draft(folder: Path) -> None:
    dest = folder / LEAKED_DIR
    dest.mkdir(exist_ok=True)
    for name in ("Resume.md", "CoverLetter.md", "claim_provenance.json"):
        src = folder / name
        if src.exists():
            src.replace(dest / name)


def _apply_widen(folder: Path, item: dict[str, Any], claims: dict[str, dict]) -> None:
    packet = _load_json(folder / "authoring_packet.json")
    trace = _load_json(folder / "evidence_selection_trace.json")
    if not isinstance(packet, dict):
        return
    cid_a = item["claim_id"]
    bindings = item.get("bindings") or []
    leaked_resume = (
        (folder / "Resume.md").read_text(encoding="utf-8") if (folder / "Resume.md").exists() else ""
    )
    for bind in bindings:
        if bind.get("decision") != "REPLACE":
            continue
        jd_item = bind.get("jd_item")
        cid_b = bind.get("anchor_id")
        for row in packet.get("evidence_map") or []:
            if not isinstance(row, dict) or row.get("jd_item") != jd_item:
                continue
            picked = [cid for cid in (row.get("claim_ids") or []) if isinstance(cid, str)]
            row["claim_ids"] = [cid_a if cid == cid_b else cid for cid in picked]
            omitted = [
                entry
                for entry in (row.get("omitted_reasons") or [])
                if isinstance(entry, dict) and entry.get("claim_id") != cid_a
            ]
            if cid_b:
                omitted.append({"claim_id": cid_b, "reason": "displaced_by_dominance"})
            row["omitted_reasons"] = omitted
        if isinstance(trace, dict):
            for trow in trace.get("items") or []:
                if trow.get("jd_item") != jd_item:
                    continue
                trow["picked"] = [
                    cid_a if cid == cid_b else cid for cid in (trow.get("picked") or [])
                ]
                trow["decision"] = "REPLACE"
                trow["candidate_id"] = cid_a
                trow["anchor_id"] = cid_b
                trow["axes"] = bind.get("axes") or {}
                for candidate in trow.get("candidates") or []:
                    if candidate.get("claim_id") == cid_a:
                        candidate["reason"] = "picked"
                    elif candidate.get("claim_id") == cid_b:
                        candidate["reason"] = "displaced_by_dominance"
    excerpts = packet.setdefault("excerpts", {})
    if isinstance(excerpts, dict) and cid_a not in excerpts:
        rec = claims.get(cid_a) or {}
        from build_authoring_packet import (
            _excerpt_for_claim,
            _load_source_texts,
            build_claim_constraints,
        )
        we_text, ai_text = _load_source_texts()
        excerpt = _excerpt_for_claim(cid_a, rec, we_text, ai_text)
        if leaked_resume and excerpt and excerpt in leaked_resume:
            excerpt = _excerpt_for_claim(cid_a, rec, "", "")
        excerpts[cid_a] = excerpt
        constraints = packet.setdefault("claim_constraints", {})
        if isinstance(constraints, dict):
            constraints.update(
                build_claim_constraints({cid_a: excerpt}, claims, we_text)
            )
    _write_json(folder / "authoring_packet.json", packet)
    if isinstance(trace, dict):
        _write_json(folder / "evidence_selection_trace.json", trace)
    _invalidate_leaked_draft(folder)


def apply_recovery(
    folder: Path,
    plan: dict[str, Any],
    *,
    claims: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """Apply auto recovery actions. Never writes workflow receipts."""
    if plan.get("status") == "PAUSE_REVIEW":
        _write_json(folder / REPORT_NAME, plan)
        return {"status": "PAUSE_REVIEW", "applied": False, "report": plan}

    catalog = _load_claims(claims)
    remove_ids = {
        item["claim_id"]
        for item in plan.get("items") or []
        if item.get("action") in {"REMOVE_EXTRA", "REWRITE_UNSUPPORTED"}
    }
    if remove_ids:
        _apply_remove_or_rewrite(folder, remove_ids)
    widened = False
    for item in plan.get("items") or []:
        if item.get("action") == "WIDEN_PACKET":
            _apply_widen(folder, item, catalog)
            widened = True
    applied_plan = dict(plan)
    applied_plan["status"] = "WAITING_FOR_LLM" if widened else "APPLIED"
    for item in applied_plan.get("items") or []:
        if item.get("action") in AUTO_ACTIONS:
            item["recovery_state"] = "APPLIED"
    _write_json(folder / REPORT_NAME, applied_plan)
    return {
        "status": applied_plan["status"],
        "applied": True,
        "report": applied_plan,
    }


def recover_stage1_extras(
    folder: Path,
    *,
    claims: dict[str, dict] | None = None,
    apply: bool = True,
) -> dict[str, Any]:
    """Orchestrator entry: plan, optionally apply, never mint receipts."""
    plan = plan_recovery(folder, claims=claims)
    _write_json(folder / REPORT_NAME, plan)
    if not apply or plan.get("status") in {"NO_EXTRAS", "PAUSE_REVIEW"}:
        return {
            "status": plan.get("status") or "NO_EXTRAS",
            "applied": False,
            "report": plan,
        }
    return apply_recovery(folder, plan, claims=claims)


def recover_stage1_extras_guarded(
    folder: Path,
    *,
    claims: dict[str, dict] | None = None,
    apply: bool = True,
) -> dict[str, Any]:
    before_state = (
        (folder / "workflow_state.json").read_text(encoding="utf-8")
        if (folder / "workflow_state.json").exists()
        else ""
    )
    receipt_dir = folder / _RECEIPT_DIR
    before_receipts = (
        {p.name: p.read_bytes() for p in receipt_dir.glob("*.json")} if receipt_dir.exists() else {}
    )
    result = recover_stage1_extras(folder, claims=claims, apply=apply)
    after_state = (
        (folder / "workflow_state.json").read_text(encoding="utf-8")
        if (folder / "workflow_state.json").exists()
        else ""
    )
    after_receipts = (
        {p.name: p.read_bytes() for p in receipt_dir.glob("*.json")} if receipt_dir.exists() else {}
    )
    if after_state != before_state:
        raise RuntimeError("closed_world_recovery must not write workflow_state.json")
    if after_receipts != before_receipts:
        raise RuntimeError("closed_world_recovery must not write stage_receipts/")
    return result


def _main() -> None:
    parser = argparse.ArgumentParser(description="CR-112 Story 3.6 closed-world recovery")
    parser.add_argument("folder")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    folder = Path(args.folder)
    result = recover_stage1_extras_guarded(folder, apply=args.apply)
    print(json.dumps({"status": result["status"], "applied": result["applied"]}, indent=2))


if __name__ == "__main__":
    sys.path.insert(0, str(_SCRIPT_DIR))
    _main()
