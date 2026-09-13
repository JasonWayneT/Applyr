"""Stage-0/early policy + Stage 2 Truth disposition policy (CR-079)."""
from __future__ import annotations

from typing import Any

from workflow.reviews import (
    ALL_DISPOSITIONS,
    BLOCKING_SEVERITIES,
    OVERRIDE_DISPOSITIONS,
    REASONING_REQUIRED,
    REASONING_MIN_CHARS,
    parse_disposition,
)
from hm_review_contract import HM_DISALLOWED_DISPOSITIONS

# hm.critical_read-specific: these dispositions are not allowed because
# a hiring-manager read is always required and is not a mechanical check
# that can misfire. Implements FR-319 / AC-417 (CR-112 Story 8.3).
# Single source of truth: HM_DISALLOWED_DISPOSITIONS in hm_review_contract.py.
HM_CRITICAL_READ_DISALLOWED = HM_DISALLOWED_DISPOSITIONS


def evaluate_stage0(gate: dict[str, Any]) -> dict[str, Any]:
    """Map stage0_fit_gate.json business fields to a policy verdict.

    Returns dict with keys: verdict (PASS|SKIP|FAIL), tier, decision, reasons.
    """
    tier = str(gate.get("tier") or "")
    decision = str(gate.get("decision") or "").upper()
    reasons: list[str] = []

    if tier == "Skip" or decision == "SKIP":
        reason = gate.get("skip_reason") or gate.get("notes") or "Stage 0 Skip"
        reasons.append(str(reason))
        return {
            "verdict": "SKIP",
            "tier": "Skip",
            "decision": "SKIP",
            "reasons": reasons,
        }

    if tier in ("Tier 1", "Tier 2") or decision == "PASS":
        return {
            "verdict": "PASS",
            "tier": tier or "Tier 1",
            "decision": "PASS",
            "reasons": reasons,
        }

    reasons.append(f"unrecognized Stage 0 tier/decision (tier={tier!r}, decision={decision!r})")
    return {
        "verdict": "FAIL",
        "tier": tier,
        "decision": decision or "UNKNOWN",
        "reasons": reasons,
    }


def evaluate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed on packet_status != ready."""
    status = packet.get("packet_status")
    if status == "ready":
        return {"verdict": "PASS", "reasons": []}
    reasons = packet.get("incomplete_reasons") or [f"packet_status={status!r}"]
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    return {"verdict": "FAIL", "reasons": [str(r) for r in reasons]}


def evaluate_truth_findings(
    findings_doc: dict[str, Any],
    dispositions_doc: dict[str, Any],
) -> dict[str, Any]:
    """Map Truth findings + human dispositions to a subphase verdict.

    Returns:
      verdict: PASS | NEEDS_DISPOSITION | FAIL
      integrity: CLEAN | OVERRIDDEN
      open_finding_ids: list
      reasons: list
    """
    findings = findings_doc.get("findings") or []
    if not isinstance(findings, list):
        return {
            "verdict": "FAIL",
            "integrity": "CLEAN",
            "open_finding_ids": [],
            "reasons": ["truth_findings.json: findings must be a list"],
        }

    by_id = (dispositions_doc or {}).get("by_finding_id") or {}
    if not isinstance(by_id, dict):
        by_id = {}

    open_ids: list[str] = []
    reasons: list[str] = []
    any_override = False

    if not findings:
        return {
            "verdict": "PASS",
            "integrity": "CLEAN",
            "open_finding_ids": [],
            "reasons": [],
        }

    for item in findings:
        if not isinstance(item, dict):
            reasons.append("finding entry is not an object")
            return {
                "verdict": "FAIL",
                "integrity": "CLEAN",
                "open_finding_ids": open_ids,
                "reasons": reasons,
            }
        fid = item.get("id")
        if not fid:
            reasons.append("finding missing id")
            return {
                "verdict": "FAIL",
                "integrity": "CLEAN",
                "open_finding_ids": open_ids,
                "reasons": reasons,
            }
        severity = str(item.get("severity") or "WARN").upper()
        disp_s, reasoning = parse_disposition(by_id.get(fid))
        if disp_s is None or disp_s == "":
            open_ids.append(str(fid))
            continue
        if disp_s not in ALL_DISPOSITIONS:
            reasons.append(f"{fid}: invalid disposition {by_id.get(fid)!r}")
            return {
                "verdict": "FAIL",
                "integrity": "CLEAN",
                "open_finding_ids": open_ids,
                "reasons": reasons,
            }
        # hm.critical_read-specific: disallow NOT_APPLICABLE and FALSE_POSITIVE
        # because a hiring-manager read is always required and is not a
        # mechanical check that can misfire. Implements FR-319 / AC-417.
        if str(fid) == "hm.critical_read" and disp_s in HM_CRITICAL_READ_DISALLOWED:
            reasons.append(
                f"{fid}: {disp_s} is not allowed for hm.critical_read — "
                "a hiring-manager read is always required; use "
                "ACCEPTED_AS_CORRECT with a structured hm_review artifact"
            )
            return {
                "verdict": "FAIL",
                "integrity": "CLEAN",
                "open_finding_ids": open_ids,
                "reasons": reasons,
            }
        if severity in BLOCKING_SEVERITIES and disp_s not in (
            "RESOLVED_EDIT",
            "HUMAN_ACCEPTED_RISK",
        ):
            reasons.append(
                f"{fid}: BLOCK finding cannot use {disp_s}; "
                "use RESOLVED_EDIT (fix docs) or HUMAN_ACCEPTED_RISK"
            )
            return {
                "verdict": "FAIL",
                "integrity": "CLEAN",
                "open_finding_ids": open_ids,
                "reasons": reasons,
            }
        # Require substantive reasoning for dispositions that claim the
        # finding was wrong or accept a risk (CR-110).
        if disp_s in REASONING_REQUIRED:
            if not reasoning or len(reasoning) < REASONING_MIN_CHARS:
                open_ids.append(str(fid))
                reasons.append(
                    f"{fid}: {disp_s} requires reasoning "
                    f"(>= {REASONING_MIN_CHARS} chars); "
                    "use {\"disposition\": \"...\", \"reasoning\": \"...\"}"
                )
                continue
        if disp_s in OVERRIDE_DISPOSITIONS:
            any_override = True

    if open_ids:
        detail = list(reasons)
        detail.append(f"{len(open_ids)} finding(s) need disposition")
        return {
            "verdict": "NEEDS_DISPOSITION",
            "integrity": "CLEAN",
            "open_finding_ids": open_ids,
            "reasons": detail,
        }

    if reasons:
        return {
            "verdict": "FAIL",
            "integrity": "CLEAN",
            "open_finding_ids": [],
            "reasons": reasons,
        }

    return {
        "verdict": "PASS",
        "integrity": "OVERRIDDEN" if any_override else "CLEAN",
        "open_finding_ids": [],
        "reasons": [],
    }
