#!/usr/bin/env python3
"""CR-112 Story 3.5/3.6 — deterministic evidence dominance comparator.

Implements FR-313 / AC-410 (compare) and FR-314 / AC-411 (Class 1 swap).
No LLM calls. Detection stays in packet_closed_world.py. This module ranks
one omitted/extra candidate against one same-item anchor. It does not scan
live submissions and it does not rewrite drafts.
"""
from __future__ import annotations

import re
from math import ceil
from typing import Any, Literal

Axis = Literal["A_better", "tie", "B_better", "veto_A"]
Decision = Literal["REPLACE", "KEEP", "AMBIGUOUS", "INELIGIBLE"]

ATTR_RANK = {
    "owned": 4,
    "contributed": 3,
    "influenced": 2,
    "observed": 1,
}

OMITTED_ELIGIBLE_REASONS = frozenset({"top2_cutoff", "project_slot_cap"})
CISION_BULLET_CAP = 6
EARLIER_ROLE_CAP = 3
EARLIER_EMPLOYERS = frozenset({"sterkly", "zero_to_sixty", "zero to sixty"})

_WORD_RE = re.compile(r"[a-z0-9]{3,}")
_METRIC_RE = re.compile(
    r"\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?|\b\d+(?:\.\d+)?\s*%|\b\d+(?:\.\d+)?[kmb]\b",
    re.IGNORECASE,
)

_GENERIC_TAG_TOKENS = frozenset(
    {
        "able",
        "about",
        "across",
        "also",
        "based",
        "been",
        "data",
        "experience",
        "management",
        "platform",
        "product",
        "software",
        "team",
        "work",
    }
)

_EXCLUSION_NEEDLES = (
    "people manager",
    "direct report",
    "0-to-1",
    "0 to 1",
    "greenfield",
    "model training",
    "revenue ownership",
    "billing owner",
)

_TITLE_OVERCLAIM_NEEDLES = (
    "director",
    "head of",
    "principal",
    " vice president",
    " vp ",
    "staff pm",
    "group pm",
)


def attribution_rank(raw: Any) -> int | None:
    """Case-fold catalog attribution. Missing/unknown is None, not a rank."""
    if raw is None:
        return None
    key = str(raw).strip().lower()
    if not key:
        return None
    return ATTR_RANK.get(key)


def jd_priority_margin(score_b: int) -> int:
    return max(1, ceil(0.10 * max(int(score_b), 1)))


def axis_jd_priority(score_a: int, score_b: int) -> Axis:
    margin = jd_priority_margin(score_b)
    delta = int(score_a) - int(score_b)
    if delta >= margin:
        return "A_better"
    if -delta >= margin:
        return "B_better"
    return "tie"


def _words(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


def _claim_rec(claims: dict[str, dict], cid: str) -> dict[str, Any]:
    rec = claims.get(cid) or {}
    return rec if isinstance(rec, dict) else {}


def _tags(rec: dict[str, Any]) -> list[str]:
    tags = rec.get("tags") or []
    if not isinstance(tags, list):
        return []
    return [str(t) for t in tags if t is not None]


def _metrics(rec: dict[str, Any]) -> list[str]:
    metrics = rec.get("metrics") or []
    if not isinstance(metrics, list):
        return []
    return [str(m) for m in metrics if m is not None]


def _employer(rec: dict[str, Any]) -> str:
    return str(rec.get("employer") or "").strip().lower()


def _project_id(cid: str, rec: dict[str, Any]) -> str:
    return str(rec.get("project_id") or cid).strip() or cid


def _tag_tokens(rec: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for tag in _tags(rec):
        tokens |= _words(tag)
    return tokens


def _distinctive_jd_tags(rec: dict[str, Any], jd_blob: str) -> set[str]:
    jd_tokens = _words(jd_blob)
    out: set[str] = set()
    for tok in _tag_tokens(rec):
        if tok in _GENERIC_TAG_TOKENS:
            continue
        if tok in jd_tokens:
            out.add(tok)
    return out


def _metric_magnitudes(rec: dict[str, Any]) -> list[float]:
    blob = " ".join(_metrics(rec) + _tags(rec))
    values: list[float] = []
    for match in _METRIC_RE.finditer(blob):
        raw = match.group(0).lower().replace("$", "").replace(",", "").strip()
        multiplier = 1.0
        if raw.endswith("%"):
            raw = raw[:-1]
        elif raw.endswith("k"):
            multiplier = 1_000.0
            raw = raw[:-1]
        elif raw.endswith("m"):
            multiplier = 1_000_000.0
            raw = raw[:-1]
        elif raw.endswith("b"):
            multiplier = 1_000_000_000.0
            raw = raw[:-1]
        try:
            values.append(float(raw) * multiplier)
        except ValueError:
            continue
    return values


def _blob(rec: dict[str, Any], cid: str) -> str:
    parts = [cid, _project_id(cid, rec), " ".join(_tags(rec)), " ".join(_metrics(rec))]
    return " ".join(parts).lower()


def axis_attribution(rec_a: dict[str, Any], rec_b: dict[str, Any]) -> Axis:
    rank_a = attribution_rank(rec_a.get("attribution"))
    rank_b = attribution_rank(rec_b.get("attribution"))
    if rank_a is None or rank_b is None:
        return "tie"
    if rank_a < rank_b:
        return "veto_A"
    if rank_a > rank_b:
        return "A_better"
    return "tie"


def axis_evidence_strength(
    rec_a: dict[str, Any],
    rec_b: dict[str, Any],
    *,
    cid_a: str,
    cid_b: str,
    jd_blob: str,
) -> Axis:
    """Metric size alone cannot make A_better. Same-story weaker attribution cannot."""
    same_story = _project_id(cid_a, rec_a) == _project_id(cid_b, rec_b)
    rank_a = attribution_rank(rec_a.get("attribution"))
    rank_b = attribution_rank(rec_b.get("attribution"))
    weaker_same_story = (
        same_story
        and rank_a is not None
        and rank_b is not None
        and rank_a < rank_b
    )
    if weaker_same_story:
        return "B_better"

    spec_a = _distinctive_jd_tags(rec_a, jd_blob)
    spec_b = _distinctive_jd_tags(rec_b, jd_blob)
    mag_a = _metric_magnitudes(rec_a)
    mag_b = _metric_magnitudes(rec_b)
    larger_metric = bool(mag_a) and (not mag_b or max(mag_a) > max(mag_b))

    if len(spec_a) > len(spec_b) and not weaker_same_story:
        return "A_better"
    if len(spec_b) > len(spec_a):
        return "B_better"
    if larger_metric:
        return "tie"
    return "tie"


def axis_distinctiveness(
    rec_a: dict[str, Any],
    *,
    cid_a: str,
    packet_picked_ids: list[str],
    claims: dict[str, dict],
    jd_blob: str,
) -> Axis:
    """Sibling lens of a picked project_id is B_better and is not overridable."""
    project_a = _project_id(cid_a, rec_a)
    for picked_id in packet_picked_ids:
        if picked_id == cid_a:
            continue
        picked_rec = _claim_rec(claims, picked_id)
        if _project_id(picked_id, picked_rec) == project_a:
            return "B_better"

    picked_tags: set[str] = set()
    for picked_id in packet_picked_ids:
        picked_tags |= {
            tok
            for tok in _tag_tokens(_claim_rec(claims, picked_id))
            if tok not in _GENERIC_TAG_TOKENS
        }
    new_tags = _distinctive_jd_tags(rec_a, jd_blob) - picked_tags
    if new_tags:
        return "A_better"
    return "B_better"


def axis_domain_truth(
    rec_a: dict[str, Any],
    *,
    cid_a: str,
    jd_item: str,
    admin_skip: bool = False,
) -> Axis:
    if rec_a.get("exclusion_zone") or rec_a.get("gap_domain") or rec_a.get("title_overclaim"):
        return "veto_A"
    blob = f" {_blob(rec_a, cid_a)} "
    if any(needle in blob for needle in _EXCLUSION_NEEDLES):
        return "veto_A"
    if any(needle in blob for needle in _TITLE_OVERCLAIM_NEEDLES):
        return "veto_A"
    if admin_skip:
        return "veto_A"
    item_l = (jd_item or "").lower()
    if "roadmap" in blob and (
        "fingerprint" in item_l or "background check" in item_l
    ):
        return "veto_A"
    return "tie"


def axis_document_capacity(
    rec_a: dict[str, Any],
    rec_b: dict[str, Any],
    *,
    employer_counts: dict[str, int],
) -> Axis:
    emp_a = _employer(rec_a)
    emp_b = _employer(rec_b)
    if emp_a == emp_b:
        return "tie"
    next_count = employer_counts.get(emp_a, 0) + 1
    if emp_a == "cision" and next_count > CISION_BULLET_CAP:
        return "veto_A"
    if emp_a in EARLIER_EMPLOYERS and next_count > EARLIER_ROLE_CAP:
        return "veto_A"
    return "tie"


def slot_swap_allowed(
    cid_a: str,
    rec_a: dict[str, Any],
    cid_b: str,
    rec_b: dict[str, Any],
    *,
    project_counts: dict[str, int],
    max_slots_per_project: int,
    omitted_reason: str | None,
) -> bool:
    proj_a = _project_id(cid_a, rec_a)
    proj_b = _project_id(cid_b, rec_b)
    if proj_a == proj_b:
        return True
    current = project_counts.get(proj_a, 0)
    if omitted_reason == "project_slot_cap":
        return current < max_slots_per_project
    return current < max_slots_per_project


def is_ineligible(
    cid: str,
    rec: dict[str, Any],
    *,
    score: int,
    disabled: set[str] | None = None,
) -> bool:
    if not rec:
        return True
    if disabled and cid in disabled:
        return True
    if rec.get("disabled") is True:
        return True
    if rec.get("prohibited") is True:
        return True
    if int(score) <= 0:
        return True
    return False


def compare_pair(
    *,
    cid_a: str,
    score_a: int,
    cid_b: str,
    score_b: int,
    claims: dict[str, dict],
    jd_item: str,
    jd_text: str = "",
    packet_picked_ids: list[str],
    employer_counts: dict[str, int],
    project_counts: dict[str, int],
    max_slots_per_project: int,
    omitted_reason: str | None,
    class_kind: int = 1,
    disabled: set[str] | None = None,
    admin_skip: bool = False,
) -> dict[str, Any]:
    """Compare omitted/extra A to same-item anchor B. Never cross-item."""
    rec_a = _claim_rec(claims, cid_a)
    rec_b = _claim_rec(claims, cid_b)
    if is_ineligible(cid_a, rec_a, score=score_a, disabled=disabled):
        return {
            "decision": "INELIGIBLE",
            "candidate_id": cid_a,
            "anchor_id": cid_b,
            "axes": {},
            "class_kind": class_kind,
        }

    jd_blob = f"{jd_item} {jd_text}"
    axes: dict[str, Axis] = {
        "jd_priority": axis_jd_priority(score_a, score_b),
        "evidence_strength": axis_evidence_strength(
            rec_a, rec_b, cid_a=cid_a, cid_b=cid_b, jd_blob=jd_blob
        ),
        "attribution_safety": axis_attribution(rec_a, rec_b),
        "distinctiveness": axis_distinctiveness(
            rec_a,
            cid_a=cid_a,
            packet_picked_ids=packet_picked_ids,
            claims=claims,
            jd_blob=jd_blob,
        ),
        "domain_truth_risk": axis_domain_truth(
            rec_a, cid_a=cid_a, jd_item=jd_item, admin_skip=admin_skip
        ),
        "document_capacity": axis_document_capacity(
            rec_a, rec_b, employer_counts=employer_counts
        ),
    }
    if not slot_swap_allowed(
        cid_a,
        rec_a,
        cid_b,
        rec_b,
        project_counts=project_counts,
        max_slots_per_project=max_slots_per_project,
        omitted_reason=omitted_reason,
    ):
        axes["document_capacity"] = "veto_A"

    rank_a = attribution_rank(rec_a.get("attribution"))
    rank_b = attribution_rank(rec_b.get("attribution"))
    contributed_cannot_beat_missing = (
        rank_b is None
        and rank_a is not None
        and rank_a < ATTR_RANK["owned"]
    )

    veto = any(value == "veto_A" for value in axes.values())
    if veto:
        decision: Decision = "KEEP"
    elif (
        axes["jd_priority"] == "A_better"
        and axes["evidence_strength"] != "B_better"
        and axes["attribution_safety"] != "B_better"
        and axes["distinctiveness"] != "B_better"
        and axes["domain_truth_risk"] != "B_better"
        and axes["document_capacity"] != "B_better"
        and not contributed_cannot_beat_missing
    ):
        decision = "REPLACE"
    else:
        decision = "AMBIGUOUS"

    return {
        "decision": decision,
        "candidate_id": cid_a,
        "anchor_id": cid_b,
        "axes": axes,
        "class_kind": class_kind,
    }


def _score_map(candidates: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in candidates:
        cid = row.get("claim_id")
        if isinstance(cid, str) and cid:
            try:
                out[cid] = int(row.get("score") or 0)
            except (TypeError, ValueError):
                out[cid] = 0
    return out


def _recount_projects(
    evidence_map: list[dict[str, Any]], claims: dict[str, dict]
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in evidence_map:
        for cid in row.get("claim_ids") or []:
            if not isinstance(cid, str):
                continue
            proj = _project_id(cid, _claim_rec(claims, cid))
            counts[proj] = counts.get(proj, 0) + 1
    return counts


def _recount_employers(
    evidence_map: list[dict[str, Any]], claims: dict[str, dict]
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in evidence_map:
        for cid in row.get("claim_ids") or []:
            if not isinstance(cid, str):
                continue
            emp = _employer(_claim_rec(claims, cid))
            if not emp:
                continue
            counts[emp] = counts.get(emp, 0) + 1
    return counts


def _packet_picked_ids(evidence_map: list[dict[str, Any]]) -> list[str]:
    picked: list[str] = []
    for row in evidence_map:
        for cid in row.get("claim_ids") or []:
            if isinstance(cid, str) and cid:
                picked.append(cid)
    return picked


def apply_class1_dominance(
    evidence_map: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    claims: dict[str, dict],
    *,
    jd_text: str,
    max_slots_per_project: int,
    disabled: set[str] | None = None,
) -> None:
    """Post-Top-2 Class 1 pass. Mutates evidence_map and TRACE rows in place.

    REPLACE swaps A onto the same item only. AMBIGUOUS/KEEP leave picks
    unchanged. Packet omitted reason for a displaced ID is
    displaced_by_dominance. Scores stay on TRACE, not the packet.
    """
    trace_by_item: dict[tuple[str, str], dict[str, Any]] = {}
    for item in traces:
        key = (str(item.get("jd_item") or ""), str(item.get("bucket") or ""))
        trace_by_item[key] = item

    for row in evidence_map:
        jd_item = str(row.get("jd_item") or "")
        bucket = str(row.get("bucket") or "")
        trace = trace_by_item.get((jd_item, bucket))
        picked = [cid for cid in (row.get("claim_ids") or []) if isinstance(cid, str)]
        omitted = [
            item
            for item in (row.get("omitted_reasons") or [])
            if isinstance(item, dict)
        ]
        if not picked or not omitted or trace is None:
            continue
        candidates = [
            c for c in (trace.get("candidates") or []) if isinstance(c, dict)
        ]
        scores = _score_map(candidates)
        eligible = []
        for item in omitted:
            cid = item.get("claim_id")
            reason = item.get("reason")
            if not isinstance(cid, str) or reason not in OMITTED_ELIGIBLE_REASONS:
                continue
            score = scores.get(cid, 0)
            if score <= 0:
                continue
            rec = _claim_rec(claims, cid)
            if is_ineligible(cid, rec, score=score, disabled=disabled):
                continue
            eligible.append((cid, str(reason), score))
        if not eligible:
            continue

        cid_a, omitted_reason, score_a = max(eligible, key=lambda row: (row[2], row[0]))
        cid_b = min(picked, key=lambda cid: (scores.get(cid, 0), cid))
        score_b = scores.get(cid_b, 0)

        result = compare_pair(
            cid_a=cid_a,
            score_a=score_a,
            cid_b=cid_b,
            score_b=score_b,
            claims=claims,
            jd_item=jd_item,
            jd_text=jd_text,
            packet_picked_ids=_packet_picked_ids(evidence_map),
            employer_counts=_recount_employers(evidence_map, claims),
            project_counts=_recount_projects(evidence_map, claims),
            max_slots_per_project=max_slots_per_project,
            omitted_reason=omitted_reason,
            class_kind=1,
            disabled=disabled,
        )
        trace["decision"] = result["decision"]
        trace["candidate_id"] = result["candidate_id"]
        trace["anchor_id"] = result["anchor_id"]
        trace["axes"] = result["axes"]
        if result["decision"] == "AMBIGUOUS":
            trace["selection_review"] = True
        else:
            trace.pop("selection_review", None)

        if result["decision"] != "REPLACE":
            continue

        new_picked = [cid_a if cid == cid_b else cid for cid in picked]
        row["claim_ids"] = new_picked
        new_omitted = [
            item
            for item in omitted
            if item.get("claim_id") != cid_a
        ]
        new_omitted.append({"claim_id": cid_b, "reason": "displaced_by_dominance"})
        row["omitted_reasons"] = new_omitted
        trace["picked"] = list(new_picked)
        for candidate in candidates:
            if candidate.get("claim_id") == cid_a:
                candidate["reason"] = "picked"
            elif candidate.get("claim_id") == cid_b:
                candidate["reason"] = "displaced_by_dominance"
