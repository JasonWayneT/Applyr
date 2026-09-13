#!/usr/bin/env python3
"""CR-112 requirement-extraction-review artifact (pause_kind=requirement_extraction_review).

When `build_stage0_fit_gate`'s three-way qualification-risk gate (see
`stage0_qualification_risk_gate.py`) finds at least one QUALIFICATION_LIKELY
or AMBIGUOUS bullet in the NLP extractor's unresolved queue, Stage 0 pauses
and writes a non-authoritative template here for a human (or a harness
answering on a human's behalf) to fill in. This module owns generating that
template and validating the live answer.

Bucket-correction only -- same forbidden-keys discipline as
`stage0_evidence_cascade`'s cascade import template: an import here can
never set `fit_score`/`tier`/`decision`/workflow status. It only tells
`build_stage0_fit_gate` which real bucket (or "exclude") each queued item
belongs in; scoring happens through the normal path afterward.

No rubber-stamping (CR-112 "Do NOT fix this by" list): there is no
"accept all" response key, and every queued item's bucket must be set
explicitly -- a missing or invalid answer for even one item invalidates the
whole import (see `try_load_review_import`).

Exact-text binding: an import's echoed `text` for a given index must match
the real queued item text exactly, the same discipline
`stage0_evidence_cascade.try_load_cascade_import` applies to a batch import
-- otherwise a reviewer could answer about text they rewrote and nothing
would catch it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REVIEW_TEMPLATE_NAME = "stage0_requirement_extraction_review.template.json"
REVIEW_IMPORT_NAME = "stage0_requirement_extraction_review.json"
REVIEW_CONSUMED_NAME = "stage0_requirement_extraction_review.consumed.json"
REVIEW_SCHEMA_VERSION = 1

# "exclude" covers a genuinely non-requirement bullet a human confirms should
# not become a required/preferred/responsibilities/culture item at all (the
# manual equivalent of a NON_QUALIFICATION bypass, but recorded as an
# explicit human decision rather than the automatic gate's own call).
ALLOWED_BUCKETS = {"required", "preferred", "responsibilities", "culture", "exclude"}

_ALLOWED_KEYS = {
    "schema_version",
    "import_source",
    "submission_slug",
    "jd_sha256",
    "created_at",
    "items",
}
_FORBIDDEN_KEYS = {
    "fit_score",
    "tier",
    "decision",
    "workflow_status",
    "status",
    "receipts",
    "receipt_id",
    "stages",
    "active_stage",
    "issued_by",
    "pause_kind",
    "workflow_state",
    "mechanically_verified",
    "verification_passed",
    "cost",
    "cost_class",
    "cost_known",
    "cost_confidence",
    "api_cents",
    "model_call_occurred",
}


class RequirementExtractionReviewValidationError(ValueError):
    """A submitted requirement-extraction-review import cannot be trusted.

    ``fail_closed=True`` is for unreadable consumed reviews: the caller must
    not treat that as "no review yet" and silently re-pause. Binding
    mismatches still raise this class with ``fail_closed=False`` so a stale
    review can be answered again, with the message naming what changed.
    """

    def __init__(self, message: str, *, fail_closed: bool = False) -> None:
        super().__init__(message)
        self.fail_closed = fail_closed


def _item_key(index: int, text: str) -> str:
    digest = hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()[:12]
    return f"{index}:{digest}"


def render_review_template(
    *,
    submission_slug: str,
    jd_sha256: str,
    queue: list[dict[str, Any]],
) -> dict[str, Any]:
    """Bound review skeleton. Every item's bucket starts null -- must be set
    explicitly by whoever answers this; there is no accept-all default."""
    items = []
    for idx, entry in enumerate(queue):
        text = entry.get("text", "")
        items.append(
            {
                "index": idx,
                "item_key": _item_key(idx, text),
                "text": text,
                "header": entry.get("header", ""),
                "label": entry.get("label"),
                "reason_code": entry.get("reason_code"),
                "bucket": None,
            }
        )
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "import_source": "manual",
        "submission_slug": submission_slug,
        "jd_sha256": jd_sha256,
        "created_at": "audit-only-not-identity",
        "items": items,
    }


def write_review_template(
    folder: str | Path,
    *,
    submission_slug: str,
    jd_sha256: str,
    queue: list[dict[str, Any]],
) -> Path:
    """Write a non-authoritative template next to the live import name."""
    path = Path(folder) / REVIEW_TEMPLATE_NAME
    payload = render_review_template(
        submission_slug=submission_slug, jd_sha256=jd_sha256, queue=queue
    )
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def consume_review_import(folder: str | Path) -> str | None:
    """Rename a successfully used live import. Deterministic; no second live file."""
    live = Path(folder) / REVIEW_IMPORT_NAME
    if not live.is_file():
        return None
    consumed = Path(folder) / REVIEW_CONSUMED_NAME
    if consumed.exists():
        consumed.unlink()
    live.replace(consumed)
    return REVIEW_CONSUMED_NAME


def try_load_review_import(
    folder: str | Path,
    queue: list[dict[str, Any]],
    *,
    submission_slug: str,
    jd_sha256: str,
) -> dict[int, str] | None:
    """Load a bound manual bucket-correction import.

    Live file wins (deliberate correction). If live is absent, a valid
    consumed file for this slug + JD + exact queue is reused so a later
    Stage 0 restart (cost-authorization --resume) does not re-ask the same
    review. None if neither file exists.

    Present-but-invalid raises RequirementExtractionReviewValidationError.
    Unreadable consumed JSON sets ``fail_closed=True``. Does not write
    state, does not consume the file.

    Returns ``{index: bucket}`` only when every queued item has an explicit,
    valid, exact-text-bound bucket answer -- never a partial map.
    """
    live = Path(folder) / REVIEW_IMPORT_NAME
    consumed = Path(folder) / REVIEW_CONSUMED_NAME
    if live.is_file():
        path, source, unreadable_fail_closed = live, "live", False
    elif consumed.is_file():
        path, source, unreadable_fail_closed = consumed, "consumed", True
    else:
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except UnicodeDecodeError as exc:
        raise RequirementExtractionReviewValidationError(
            f"invalid {source} requirement-extraction-review encoding: {exc}",
            fail_closed=unreadable_fail_closed,
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RequirementExtractionReviewValidationError(
            f"invalid {source} requirement-extraction-review import: {exc}",
            fail_closed=unreadable_fail_closed,
        ) from exc
    if not isinstance(payload, dict):
        raise RequirementExtractionReviewValidationError(
            f"{source} requirement-extraction-review import must be a JSON object"
        )
    forbidden = set(payload) & _FORBIDDEN_KEYS
    if forbidden:
        raise RequirementExtractionReviewValidationError(
            "requirement-extraction-review import cannot set workflow/scoring "
            f"fields: {sorted(forbidden)}"
        )
    extra = set(payload) - _ALLOWED_KEYS
    if extra:
        raise RequirementExtractionReviewValidationError(
            f"requirement-extraction-review import has unsupported keys: {sorted(extra)}"
        )
    if payload.get("schema_version") != REVIEW_SCHEMA_VERSION:
        raise RequirementExtractionReviewValidationError(
            f"requirement-extraction-review schema_version must be {REVIEW_SCHEMA_VERSION}"
        )
    if payload.get("import_source") != "manual":
        raise RequirementExtractionReviewValidationError(
            "requirement-extraction-review import_source must be manual"
        )
    if str(payload.get("submission_slug") or "") != str(submission_slug):
        raise RequirementExtractionReviewValidationError(
            f"{source} requirement-extraction-review submission_slug does not "
            "match this folder; prior review cannot be reused"
        )
    if str(payload.get("jd_sha256") or "") != str(jd_sha256):
        raise RequirementExtractionReviewValidationError(
            f"{source} requirement-extraction-review jd_sha256 does not match "
            "this JD; prior review cannot be reused"
        )
    if "created_at" not in payload:
        raise RequirementExtractionReviewValidationError(
            "requirement-extraction-review created_at is required for audit"
        )

    items = payload.get("items")
    if not isinstance(items, list) or len(items) != len(queue):
        raise RequirementExtractionReviewValidationError(
            f"{source} requirement-extraction-review items do not match the "
            "queued item count; prior review cannot be reused"
        )

    resolved: dict[int, str] = {}
    for raw_item in items:
        if not isinstance(raw_item, dict):
            raise RequirementExtractionReviewValidationError(
                "requirement-extraction-review item must be an object"
            )
        try:
            index = int(raw_item.get("index"))
        except (TypeError, ValueError) as exc:
            raise RequirementExtractionReviewValidationError(
                "requirement-extraction-review item missing a valid index"
            ) from exc
        if index < 0 or index >= len(queue):
            raise RequirementExtractionReviewValidationError(
                f"requirement-extraction-review index out of range: {index}"
            )
        if index in resolved:
            raise RequirementExtractionReviewValidationError(
                f"duplicate requirement-extraction-review index: {index}"
            )
        expected_text = queue[index].get("text", "")
        expected_key = _item_key(index, expected_text)
        if str(raw_item.get("item_key") or "") != expected_key:
            raise RequirementExtractionReviewValidationError(
                f"{source} requirement-extraction-review item_key does not "
                f"match item {index}; prior review cannot be reused"
            )
        # Exact-text binding (same discipline as
        # stage0_evidence_cascade.try_load_cascade_import): a reviewer must
        # answer about the real item text, not text they rewrote.
        if str(raw_item.get("text") or "") != expected_text:
            raise RequirementExtractionReviewValidationError(
                f"{source} requirement-extraction-review echoed text does not "
                f"match item {index}; prior review cannot be reused"
            )
        bucket = raw_item.get("bucket")
        if bucket not in ALLOWED_BUCKETS:
            raise RequirementExtractionReviewValidationError(
                f"requirement-extraction-review item {index} bucket must be one "
                f"of {sorted(ALLOWED_BUCKETS)} (no default, no accept-all)"
            )
        resolved[index] = bucket

    missing = set(range(len(queue))) - set(resolved)
    if missing:
        raise RequirementExtractionReviewValidationError(
            f"requirement-extraction-review missing bucket answers for indices: {sorted(missing)}"
        )
    return resolved
