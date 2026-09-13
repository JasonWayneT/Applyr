"""HM critical-read review artifact validation (CR-112 Story 8.3 + 8.3.1).

Validates that a disposition for hm.critical_read includes a structured
review artifact demonstrating specific engagement with both documents
and the JD. This is a substance gate, not a character-count gate —
the structured observations (document span, finding, jd span per
document) are the primary proof, with minimum lengths as a backstop.

Implements FR-319 / AC-417. Story 8.3.1 (2026-09-16): RESOLVED_EDIT's
edit proof derives from committed workflow state (the Stage 1 COMPLETE
receipt's prior_output_hashes), not from reviewer-supplied hashes —
a self-reported prior hash proves nothing, because an agent can invent
one. Receipts are minted only by workflow/receipts.py via run_submission,
so a receipt-derived prior is an authoritative, non-narration source.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Any

# Minimum character counts for substantive content.
HM_REASONING_MIN_CHARS = 20
OBS_LOCATION_MIN_CHARS = 5
OBS_FINDING_MIN_CHARS = 15
OBS_JD_RELEVANCE_MIN_CHARS = 10
OBS_DOCUMENT_SPAN_MIN_CHARS = 10
OBS_JD_SPAN_MIN_CHARS = 10
RISK_EXPLANATION_MIN_CHARS = 20

REQUIRED_HASH_DOCS = ("Resume.md", "CoverLetter.md", "Original_JD.txt")
VALID_RECOMMENDATIONS = frozenset({"pass", "revise", "reject"})
VALID_VERDICTS = frozenset({"pass", "revise", "reject"})

# Harness-agnostic reviewer roles. Role identity is declarative — the
# contract does not claim cryptographic independence. It prevents an
# "author" from silently masquerading as an independent reviewer.
VALID_REVIEWER_ROLES = frozenset({"author", "reviewer", "human_reviewer"})

# Role-disposition matrix: which roles may use which dispositions.
# author: may clear RESOLVED_EDIT (they made the edit).
# reviewer: may clear ACCEPTED_AS_CORRECT and RESOLVED_EDIT.
# human_reviewer: may clear all three including HUMAN_ACCEPTED_RISK.
_ROLE_ALLOWED_DISPOSITIONS = {
    "author": frozenset({"RESOLVED_EDIT"}),
    "reviewer": frozenset({"ACCEPTED_AS_CORRECT", "RESOLVED_EDIT"}),
    "human_reviewer": frozenset({"ACCEPTED_AS_CORRECT", "RESOLVED_EDIT", "HUMAN_ACCEPTED_RISK"}),
}

# Dispositions that require an hm_review artifact for hm.critical_read.
HM_REVIEW_DISPOSITIONS = frozenset({"ACCEPTED_AS_CORRECT", "RESOLVED_EDIT", "HUMAN_ACCEPTED_RISK"})

# Dispositions that are not allowed for hm.critical_read at all.
HM_DISALLOWED_DISPOSITIONS = frozenset({"NOT_APPLICABLE", "FALSE_POSITIVE"})

# Verdict-disposition consistency: which verdicts are allowed per disposition.
# ACCEPTED_AS_CORRECT and RESOLVED_EDIT imply the review found no issues (pass).
# HUMAN_ACCEPTED_RISK allows any verdict since the reviewer may disagree.
_VERDICT_BY_DISPOSITION = {
    "ACCEPTED_AS_CORRECT": frozenset({"pass"}),
    "RESOLVED_EDIT": frozenset({"pass"}),
    "HUMAN_ACCEPTED_RISK": frozenset({"pass", "revise", "reject"}),
}

# Maximum clock skew tolerance for timestamps (1 hour ahead of now).
_TIMESTAMP_FUTURE_TOLERANCE = timedelta(hours=1)


def _sha256_file(path: str) -> str | None:
    """Return sha256 hex of a file's bytes, or None if the file doesn't exist."""
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _read_file(path: str) -> str | None:
    """Read a file as UTF-8 text, or None if it doesn't exist."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def _normalize_span(text: str) -> str:
    """Normalize whitespace in a span for substring matching."""
    return " ".join(text.split())


def _validate_timestamp(timestamp: str) -> str | None:
    """Validate an ISO-8601 timestamp with timezone info.

    Returns None if valid, or an error message string if invalid.
    Rejects: non-strings, unparseable formats, naive timestamps (no tz),
    and timestamps implausibly far in the future (> 1 hour ahead).
    Does not require exact clock synchronization.
    """
    if not isinstance(timestamp, str) or not timestamp.strip():
        return "review_timestamp must be a non-empty string"
    ts = timestamp.strip()
    # Replace trailing 'Z' with '+00:00' for fromisoformat compatibility.
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return f"review_timestamp {timestamp!r} is not a valid ISO-8601 timestamp"
    if parsed.tzinfo is None:
        return f"review_timestamp {timestamp!r} lacks timezone info (use ISO-8601 with offset or Z)"
    now = datetime.now(timezone.utc)
    if parsed > now + _TIMESTAMP_FUTURE_TOLERANCE:
        return f"review_timestamp {timestamp!r} is implausibly in the future"
    return None


IMPLICATED_DOCS_DEFAULT = ("Resume.md", "CoverLetter.md")


def _normalize_implicated_documents(value: Any) -> tuple[str, ...] | None:
    """Return a tuple of implicated document names, or None if the value is unusable."""
    if value is None:
        return IMPLICATED_DOCS_DEFAULT
    if isinstance(value, list) and value:
        norm = [str(v).strip() for v in value if isinstance(v, str) and v.strip()]
        if norm:
            return tuple(norm)
    return None


def _read_stage1_receipt(folder: str) -> dict[str, Any] | None:
    """Read stage_receipts/stage1.json as a dict, or None if missing/unreadable."""
    path = os.path.join(folder, "stage_receipts", "stage1.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _receipt_id_matches_body(receipt: dict[str, Any]) -> bool:
    """Anti-forgery: recompute receipt_id from the canonical body.

    Mirrors workflow.receipts.build_receipt and
    contracts.check_workflow_complete (sort_keys, compact separators).
    A handwritten or corrupted receipt whose receipt_id does not match its
    body fails closed.
    """
    rid = receipt.get("receipt_id")
    stage = receipt.get("stage")
    if not isinstance(rid, str) or not isinstance(stage, str):
        return False
    body = {k: v for k, v in receipt.items() if k != "receipt_id"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    expected = f"{stage}:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
    return rid == expected


def _validate_resolved_edit_edit_proof(
    folder: str,
    errors: list[str],
    implicated_documents: Any,
) -> None:
    """Append errors proving an edit occurred, using receipt-derived prior hashes.

    CR-112 Story 8.3.1: the edit proof comes from the Stage 1 COMPLETE
    receipt's prior_output_hashes (workflow-minted committed state), never
    from the reviewer payload. A self-reported prior hash proves nothing —
    an agent can invent one. Fails closed on missing/stale/ambiguous/
    contradictory history; only implicated documents count toward the change,
    so an unrelated edit cannot clear the finding.
    """
    implicated = _normalize_implicated_documents(implicated_documents)
    if implicated is None:
        errors.append(
            "hm.critical_read finding's implicated_documents is unusable — "
            "RESOLVED_EDIT cannot prove which documents must have changed"
        )
        return

    receipt = _read_stage1_receipt(folder)
    if receipt is None:
        errors.append(
            "RESOLVED_EDIT cannot be validated: stage_receipts/stage1.json is "
            "missing or unreadable — no authoritative pre-edit state exists. "
            "Re-run run_submission so a Stage 1 COMPLETE receipt is present."
        )
        return

    # Anti-forgery: only workflow-minted receipts carry a matching receipt_id.
    if not _receipt_id_matches_body(receipt):
        errors.append(
            "stage_receipts/stage1.json receipt_id does not match its canonical "
            "body — forged or corrupted receipt; RESOLVED_EDIT fails closed"
        )
        return
    if receipt.get("issued_by") != "scripts/run_submission.py":
        errors.append(
            "stage_receipts/stage1.json was not issued by run_submission — "
            "receipt not workflow-minted; RESOLVED_EDIT fails closed"
        )
        return
    if receipt.get("status") != "COMPLETE":
        errors.append(
            f"stage_receipts/stage1.json status is {receipt.get('status')!r}, "
            "expected COMPLETE; RESOLVED_EDIT fails closed on non-committed history"
        )
        return
    if receipt.get("stage") != "stage1":
        errors.append(
            f"stage_receipts/stage1.json stage field is {receipt.get('stage')!r}, "
            "expected stage1 — duplicated or misplaced receipt from another stage; "
            "RESOLVED_EDIT fails closed"
        )
        return

    prior = receipt.get("prior_output_hashes")
    if not isinstance(prior, dict) or not prior:
        errors.append(
            "Stage 1 receipt has no prior_output_hashes — no committed pre-edit "
            "state to prove a change against. This is expected on the first "
            "validation; RESOLVED_EDIT requires a re-validation that preserved "
            "the prior COMPLETE receipt's hashes."
        )
        return

    # Receipt staleness: declared current output hashes must match disk, else
    # the committed state is not authoritative at validation time.
    output_hashes = receipt.get("output_hashes")
    if isinstance(output_hashes, dict):
        for rel, want in output_hashes.items():
            if not isinstance(rel, str) or not isinstance(want, str):
                continue
            on_disk = _sha256_file(os.path.join(folder, rel))
            if on_disk is None:
                errors.append(
                    f"stage_receipts/stage1.json output {rel} missing on disk — "
                    "receipt history is stale; RESOLVED_EDIT fails closed"
                )
            elif on_disk != want:
                errors.append(
                    f"stage_receipts/stage1.json output {rel} no longer matches "
                    "disk (hash mismatch) — receipt history is stale; "
                    "RESOLVED_EDIT fails closed"
                )

    # Edit proof: at least one implicated document must differ prior -> disk now.
    changed = False
    for doc in implicated:
        prior_hash = prior.get(doc)
        if not isinstance(prior_hash, str) or len(prior_hash) != 64:
            errors.append(
                f"resolved-edit prior history for {doc} is missing or malformed "
                "in stage_receipts/stage1.json — ambiguous history; "
                "RESOLVED_EDIT fails closed"
            )
            continue
        now_hash = _sha256_file(os.path.join(folder, doc))
        if now_hash is None:
            errors.append(f"{doc} missing on disk — cannot verify the edit")
        elif now_hash != prior_hash:
            changed = True

    if not changed:
        errors.append(
            "RESOLVED_EDIT requires at least one implicated document "
            f"({', '.join(implicated)}) to differ from the Stage 1 receipt's "
            "prior_output_hashes — the committed pre-edit state shows no change, "
            "so an edit cannot be proven. A no-op or unrelated edit is not a "
            "resolution."
        )


def validate_hm_review(
    folder: str,
    disposition_value: Any,
    implicated_documents: Any = None,
) -> tuple[bool, list[str]]:
    """Validate an hm.critical_read disposition's structured review artifact.

    Args:
        folder: Path to the submission folder containing Resume.md,
                CoverLetter.md, Original_JD.txt, and stage_receipts/.
        disposition_value: The disposition entry from dispositions.json
            by_finding_id["hm.critical_read"]. May be a bare string or
            a dict with "disposition", "reasoning", and "hm_review".
        implicated_documents: Optional list of document names bound to the
            finding (from the finding's own implicated_documents field).
            Defaults to ("Resume.md", "CoverLetter.md"). RESOLVED_EDIT's
            edit proof only counts a change to an implicated document, so
            an unrelated file edit cannot clear the finding.

    Returns:
        (ok, errors) where ok is True if the review artifact is valid
        and errors is a list of human-readable validation errors.
    """
    errors: list[str] = []

    if not isinstance(disposition_value, dict):
        errors.append(
            "hm.critical_read requires a structured review artifact "
            '(object with "disposition", "reasoning", and "hm_review"), '
            f"got {type(disposition_value).__name__}"
        )
        return False, errors

    disposition = disposition_value.get("disposition")
    if disposition not in HM_REVIEW_DISPOSITIONS:
        errors.append(
            f"hm.critical_read disposition must be one of {sorted(HM_REVIEW_DISPOSITIONS)} "
            f"(got {disposition!r})"
        )
        return False, errors

    # Check reasoning
    reasoning = disposition_value.get("reasoning")
    if not isinstance(reasoning, str) or len(reasoning.strip()) < HM_REASONING_MIN_CHARS:
        errors.append(
            f"hm.critical_read reasoning must be >= {HM_REASONING_MIN_CHARS} chars "
            f"(got {len(reasoning.strip()) if isinstance(reasoning, str) else 0})"
        )

    # HUMAN_ACCEPTED_RISK requires a separate risk_explanation field.
    if disposition == "HUMAN_ACCEPTED_RISK":
        risk_exp = disposition_value.get("risk_explanation")
        if not isinstance(risk_exp, str) or len(risk_exp.strip()) < RISK_EXPLANATION_MIN_CHARS:
            errors.append(
                f"HUMAN_ACCEPTED_RISK requires a risk_explanation field "
                f"(>= {RISK_EXPLANATION_MIN_CHARS} chars) stating the specific risk accepted"
            )

    # Check hm_review presence
    hm_review = disposition_value.get("hm_review")
    if not isinstance(hm_review, dict):
        errors.append(
            "hm.critical_read requires an 'hm_review' object with "
            "document hashes, observations, and verdict"
        )
        return False, errors

    # --- Check reviewed_document_hashes ---
    doc_hashes = hm_review.get("reviewed_document_hashes")
    if not isinstance(doc_hashes, dict):
        errors.append(
            "hm_review.reviewed_document_hashes must be an object with "
            f"{', '.join(REQUIRED_HASH_DOCS)} keys"
        )
    else:
        for doc_name in REQUIRED_HASH_DOCS:
            stored = doc_hashes.get(doc_name)
            if not isinstance(stored, str) or len(stored) != 64:
                errors.append(
                    f"hm_review.reviewed_document_hashes.{doc_name} "
                    "must be a 64-char sha256 hex string"
                )
                continue
            on_disk = _sha256_file(os.path.join(folder, doc_name))
            if on_disk is None:
                errors.append(
                    f"hm_review.reviewed_document_hashes.{doc_name} "
                    "references a file that does not exist on disk"
                )
            elif on_disk != stored:
                errors.append(
                    f"hm_review.reviewed_document_hashes.{doc_name} "
                    "does not match on-disk file (stale review — "
                    "document changed since review)"
                )

    # --- Check reviewer_role (enum, not any string) ---
    reviewer_role = hm_review.get("reviewer_role")
    if reviewer_role not in VALID_REVIEWER_ROLES:
        errors.append(
            f"hm_review.reviewer_role must be one of {sorted(VALID_REVIEWER_ROLES)} "
            f"(got {reviewer_role!r}) — role is declarative, not cryptographic"
        )
    else:
        # Enforce role-disposition matrix
        allowed_disps = _ROLE_ALLOWED_DISPOSITIONS.get(reviewer_role, frozenset())
        if disposition not in allowed_disps:
            errors.append(
                f"reviewer_role {reviewer_role!r} may not use disposition {disposition!r} "
                f"(allowed: {sorted(allowed_disps)})"
            )

    # HUMAN_ACCEPTED_RISK must have human_reviewer role
    if disposition == "HUMAN_ACCEPTED_RISK" and reviewer_role != "human_reviewer":
        errors.append(
            "HUMAN_ACCEPTED_RISK requires reviewer_role 'human_reviewer' — "
            "an automated reviewer must not mint human acceptance"
        )

    # --- Check review_timestamp (ISO-8601 with timezone) ---
    review_timestamp = hm_review.get("review_timestamp")
    ts_error = _validate_timestamp(review_timestamp if isinstance(review_timestamp, str) else "")
    if ts_error:
        errors.append(f"hm_review.{ts_error}")

    # --- Check observations ---
    observations = hm_review.get("observations")
    if not isinstance(observations, list) or len(observations) < 2:
        errors.append(
            "hm_review.observations must be a list with >= 2 entries "
            "(at least one per document: Resume.md and CoverLetter.md)"
        )
    else:
        # Read document texts for span verification
        resume_text = _read_file(os.path.join(folder, "Resume.md")) or ""
        cover_text = _read_file(os.path.join(folder, "CoverLetter.md")) or ""
        jd_text = _read_file(os.path.join(folder, "Original_JD.txt")) or ""
        resume_norm = _normalize_span(resume_text)
        cover_norm = _normalize_span(cover_text)
        jd_norm = _normalize_span(jd_text)

        docs_seen: set[str] = set()
        for i, obs in enumerate(observations):
            if not isinstance(obs, dict):
                errors.append(f"hm_review.observations[{i}] must be an object")
                continue

            doc = obs.get("document")
            if doc not in ("Resume.md", "CoverLetter.md"):
                errors.append(
                    f"hm_review.observations[{i}].document must be "
                    f"'Resume.md' or 'CoverLetter.md' (got {doc!r})"
                )
            else:
                docs_seen.add(doc)

            location = obs.get("location")
            if not isinstance(location, str) or len(location.strip()) < OBS_LOCATION_MIN_CHARS:
                errors.append(
                    f"hm_review.observations[{i}].location must be >= "
                    f"{OBS_LOCATION_MIN_CHARS} chars"
                )

            finding = obs.get("finding")
            if not isinstance(finding, str) or len(finding.strip()) < OBS_FINDING_MIN_CHARS:
                errors.append(
                    f"hm_review.observations[{i}].finding must be >= "
                    f"{OBS_FINDING_MIN_CHARS} chars"
                )

            # --- Filler resistance: document_span must appear in the document ---
            doc_span = obs.get("document_span")
            if not isinstance(doc_span, str) or len(doc_span.strip()) < OBS_DOCUMENT_SPAN_MIN_CHARS:
                errors.append(
                    f"hm_review.observations[{i}].document_span must be >= "
                    f"{OBS_DOCUMENT_SPAN_MIN_CHARS} chars (a quoted span from the document)"
                )
            else:
                span_norm = _normalize_span(doc_span.strip())
                target_norm = resume_norm if doc == "Resume.md" else cover_norm
                if span_norm not in target_norm:
                    errors.append(
                        f"hm_review.observations[{i}].document_span not found in {doc} — "
                        "the span must be a verbatim quote from the current document"
                    )

            jd_relevance = obs.get("jd_relevance")
            if not isinstance(jd_relevance, str) or len(jd_relevance.strip()) < OBS_JD_RELEVANCE_MIN_CHARS:
                errors.append(
                    f"hm_review.observations[{i}].jd_relevance must be >= "
                    f"{OBS_JD_RELEVANCE_MIN_CHARS} chars"
                )

            # --- Filler resistance: jd_span must appear in the JD ---
            jd_span = obs.get("jd_span")
            if not isinstance(jd_span, str) or len(jd_span.strip()) < OBS_JD_SPAN_MIN_CHARS:
                errors.append(
                    f"hm_review.observations[{i}].jd_span must be >= "
                    f"{OBS_JD_SPAN_MIN_CHARS} chars (a quoted span from Original_JD.txt)"
                )
            else:
                jd_span_norm = _normalize_span(jd_span.strip())
                if jd_span_norm not in jd_norm:
                    errors.append(
                        f"hm_review.observations[{i}].jd_span not found in Original_JD.txt — "
                        "the span must be a verbatim quote from the current JD"
                    )

            recommendation = obs.get("recommendation")
            if recommendation not in VALID_RECOMMENDATIONS:
                errors.append(
                    f"hm_review.observations[{i}].recommendation must be "
                    f"one of {sorted(VALID_RECOMMENDATIONS)} (got {recommendation!r})"
                )

        # Check document coverage
        for required_doc in ("Resume.md", "CoverLetter.md"):
            if required_doc not in docs_seen:
                errors.append(
                    f"hm_review.observations must include at least one "
                    f"observation for {required_doc}"
                )

    # --- Check verdict ---
    verdict = hm_review.get("verdict")
    if verdict not in VALID_VERDICTS:
        errors.append(
            f"hm_review.verdict must be one of {sorted(VALID_VERDICTS)} "
            f"(got {verdict!r})"
        )
    else:
        # Verdict-disposition consistency check
        allowed = _VERDICT_BY_DISPOSITION.get(disposition)
        if allowed is not None and verdict not in allowed:
            errors.append(
                f"hm_review.verdict {verdict!r} is not consistent with "
                f"disposition {disposition!r} (allowed: {sorted(allowed)})"
            )

    # --- Check overall_reasoning ---
    overall_reasoning = hm_review.get("overall_reasoning")
    if not isinstance(overall_reasoning, str) or not overall_reasoning.strip():
        errors.append("hm_review.overall_reasoning must be a non-empty string")

    # --- RESOLVED_EDIT: must prove an edit, from committed workflow state ---
    if disposition == "RESOLVED_EDIT":
        # CR-112 Story 8.3.1: reviewer-supplied prior_document_hashes are
        # display-only and untrusted. The edit proof is the Stage 1 receipt's
        # prior_output_hashes — workflow-minted, fresh, and bound to the
        # finding's implicated documents.
        _validate_resolved_edit_edit_proof(folder, errors, implicated_documents)

        # RESOLVED_EDIT must specifically confirm the original concern was resolved
        resolution_note = hm_review.get("resolution_summary")
        if not isinstance(resolution_note, str) or len(resolution_note.strip()) < HM_REASONING_MIN_CHARS:
            errors.append(
                "RESOLVED_EDIT requires hm_review.resolution_summary (>= "
                f"{HM_REASONING_MIN_CHARS} chars) confirming the original "
                "concern was resolved"
            )

    return len(errors) == 0, errors
