"""HM critical-read review artifact validation (CR-112 Story 8.3).

Validates that a disposition for hm.critical_read includes a structured
review artifact demonstrating specific engagement with both documents
and the JD. This is a substance gate, not a character-count gate —
the structured observations (document span, finding, jd span per
document) are the primary proof, with minimum lengths as a backstop.

Implements FR-319 / AC-417.
"""
from __future__ import annotations

import hashlib
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


def validate_hm_review(folder: str, disposition_value: Any) -> tuple[bool, list[str]]:
    """Validate an hm.critical_read disposition's structured review artifact.

    Args:
        folder: Path to the submission folder containing Resume.md,
                CoverLetter.md, and Original_JD.txt.
        disposition_value: The disposition entry from dispositions.json
            by_finding_id["hm.critical_read"]. May be a bare string or
            a dict with "disposition", "reasoning", and "hm_review".

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

    # --- RESOLVED_EDIT: must prove an edit occurred ---
    if disposition == "RESOLVED_EDIT":
        prior_hashes = hm_review.get("prior_document_hashes")
        if not isinstance(prior_hashes, dict):
            errors.append(
                "RESOLVED_EDIT requires hm_review.prior_document_hashes showing "
                "the document hashes before the edit (at least Resume.md or "
                "CoverLetter.md must differ from reviewed_document_hashes)"
            )
        else:
            reviewed_hashes = hm_review.get("reviewed_document_hashes") or {}
            changed = False
            for doc_name in ("Resume.md", "CoverLetter.md"):
                prior = prior_hashes.get(doc_name)
                current = reviewed_hashes.get(doc_name)
                if (isinstance(prior, str) and isinstance(current, str)
                        and prior != current and len(prior) == 64):
                    changed = True
                elif prior is not None and prior == current:
                    pass  # unchanged document — allowed
                elif prior is not None and prior != current and len(prior) != 64:
                    errors.append(
                        f"hm_review.prior_document_hashes.{doc_name} "
                        "must be a 64-char sha256 hex string"
                    )
            if not changed:
                errors.append(
                    "RESOLVED_EDIT requires at least one document (Resume.md or "
                    "CoverLetter.md) to have changed from prior_document_hashes to "
                    "reviewed_document_hashes — a no-op edit is not a resolution"
                )

        # RESOLVED_EDIT must specifically confirm the original concern was resolved
        resolution_note = hm_review.get("resolution_summary")
        if not isinstance(resolution_note, str) or len(resolution_note.strip()) < HM_REASONING_MIN_CHARS:
            errors.append(
                "RESOLVED_EDIT requires hm_review.resolution_summary (>= "
                f"{HM_REASONING_MIN_CHARS} chars) confirming the original "
                "concern was resolved"
            )

    return len(errors) == 0, errors
