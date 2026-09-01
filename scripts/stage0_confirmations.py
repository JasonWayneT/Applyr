#!/usr/bin/env python3
"""Shared SQLite confirmation boundary for Stage 0 and harness adapters (CR-108)."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from blocked_tools import HARD_BLOCKED_TOOLS, load_skills_catalog_terms, looks_like_named_tool


_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB = _ROOT / "data" / "jobagent.sqlite"
_MIGRATIONS = (
    _ROOT / "server" / "migrations" / "018_add_review_center.sql",
    _ROOT / "server" / "migrations" / "020_add_review_answer_history.sql",
    _ROOT / "server" / "migrations" / "021_add_evidence_promotion_proposals.sql",
)
SkillDecision = Literal[
    "CONFIRMED_USE",
    "NOT_PRESENT",
    "UNSURE_NO_REASK",
    "VERIFIED_EVIDENCE",
]
SkillAnswer = Literal["CONFIRMED_USE", "NOT_PRESENT", "UNSURE_NO_REASK"]


@dataclass(frozen=True)
class NamedSkillCandidate:
    """A conservative named-skill candidate found in a JD line."""

    skill_key: str
    display_name: str


@dataclass(frozen=True)
class ConfirmationResult:
    """Result of creating or finding a pending confirmation occurrence."""

    created: bool
    review_key: str


@dataclass(frozen=True)
class AnswerResult:
    """Result of resolving a confirmation key."""

    status: Literal["open", "completed"]
    promotion_id: str | None = None


def canonical_skill_key(value: str) -> str:
    """Normalize a displayed skill name into the shared durable key."""
    normalized = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower())
    return normalized.strip("_")


def _catalog_keys(known_terms: set[str] | None) -> set[str]:
    """Return canonical catalog keys plus conservative base-name aliases."""
    terms = known_terms if known_terms is not None else set(load_skills_catalog_terms())
    keys: set[str] = set()
    for term in terms:
        keys.add(canonical_skill_key(term))
        keys.add(canonical_skill_key(re.sub(r"\s*\([^)]*\)", "", term)))
    # These are spelling aliases already present in the verified work history.
    keys.update({"google_workspace", "google_suite", "aws_s3"})
    return keys


def named_skill_candidates(
    lines: list[str],
    *,
    known_terms: set[str] | None = None,
    internal_terms: list[str] | None = None,
) -> list[NamedSkillCandidate]:
    """Find explicit, unverified named tools without treating role prose as tools."""
    known_keys = _catalog_keys(known_terms)
    internal_keys = {
        canonical_skill_key(term)
        for term in (internal_terms or [])
        if canonical_skill_key(term)
    }
    blocked_keys = {canonical_skill_key(term) for term in HARD_BLOCKED_TOOLS}
    seen: set[str] = set()
    candidates: list[NamedSkillCandidate] = []
    for line in lines:
        for surface in looks_like_named_tool(line or ""):
            display_name = surface.strip()
            skill_key = canonical_skill_key(display_name)
            if not skill_key or skill_key in seen:
                continue
            # A longer candidate may include a verified base product plus an
            # employer-specific suffix. Keep it out of the confirmation queue
            # when the whole candidate or its first token is already verified.
            first_key = canonical_skill_key(display_name.split()[0])
            if (
                skill_key in known_keys
                or first_key in known_keys
                or skill_key in internal_keys
                or skill_key in blocked_keys
            ):
                continue
            seen.add(skill_key)
            candidates.append(NamedSkillCandidate(skill_key, display_name))
    return candidates


def _connect(db_path: str | Path | None) -> sqlite3.Connection:
    """Open the shared database and ensure the additive confirmation schema exists."""
    path = Path(db_path) if db_path is not None else _DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=30.0)
    connection.row_factory = sqlite3.Row
    for migration in _MIGRATIONS:
        connection.executescript(migration.read_text(encoding="utf-8"))
    return connection


def get_skill_memory(skill_key: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    """Read durable skill memory for a canonical skill key."""
    key = canonical_skill_key(skill_key)
    if not key:
        return None
    connection = _connect(db_path)
    try:
        row = connection.execute(
            """
            SELECT skill_key, display_name, decision, evidence_level, details_json,
                   source, created_at, updated_at
            FROM skill_memory
            WHERE skill_key = ?
            """,
            (key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def create_skill_confirmation(
    *,
    db_path: str | Path | None = None,
    skill_key: str,
    display_name: str,
    requirement: str,
    opportunity_key: str,
    opportunity_company: str,
    opportunity_title: str,
    opportunity_status: str | None = None,
    evidence_excerpt: str | None = None,
) -> ConfirmationResult:
    """Create one idempotent skill-presence occurrence for an opportunity."""
    key = canonical_skill_key(skill_key or display_name)
    opportunity = (opportunity_key or "").strip()
    if not key:
        raise ValueError("skill_key is required")
    if not opportunity:
        raise ValueError("opportunity_key is required")
    review_key = f"skill:{key}"
    connection = _connect(db_path)
    try:
        existing = connection.execute(
            """
            SELECT id
            FROM pending_skill_confirmations
            WHERE review_key = ? AND opportunity_key = ?
              AND question_type = 'skill_presence' AND status = 'open'
            """,
            (review_key, opportunity),
        ).fetchone()
        if existing:
            return ConfirmationResult(False, review_key)
        now = _utc_now()
        with connection:
            connection.execute(
                """
                INSERT INTO pending_skill_confirmations (
                  id, review_key, question_type, skill_key, status, title,
                  question, summary, requirement, evidence_excerpt,
                  opportunity_key, opportunity_company, opportunity_title,
                  opportunity_status, created_at, updated_at
                ) VALUES (?, ?, 'skill_presence', ?, 'open', ?, ?, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    review_key,
                    key,
                    (display_name or key).strip(),
                    f"Have you used {(display_name or key).strip()} in your work?",
                    "Applyr needs your input before this opportunity can continue.",
                    (requirement or "").strip() or None,
                    (evidence_excerpt or "").strip() or None,
                    opportunity,
                    (opportunity_company or "").strip() or "Unknown company",
                    (opportunity_title or "").strip() or "Untitled opportunity",
                    (opportunity_status or "").strip() or None,
                    now,
                    now,
                ),
            )
        return ConfirmationResult(True, review_key)
    finally:
        connection.close()


def create_hard_gate_review(
    *,
    db_path: str | Path | None = None,
    item_key: str,
    requirement: str,
    opportunity_key: str,
    opportunity_company: str,
    opportunity_title: str,
    evidence_excerpt: str | None = None,
) -> ConfirmationResult:
    """Create one idempotent hard-gate review for an opportunity and item."""
    opportunity = (opportunity_key or "").strip()
    if not opportunity:
        raise ValueError("opportunity_key is required")
    review_key = f"hard:{opportunity}:{item_key}"
    connection = _connect(db_path)
    try:
        existing = connection.execute(
            """
            SELECT id
            FROM pending_skill_confirmations
            WHERE review_key = ? AND status = 'open'
            """,
            (review_key,),
        ).fetchone()
        if existing:
            return ConfirmationResult(False, review_key)
        now = _utc_now()
        with connection:
            connection.execute(
                """
                INSERT INTO pending_skill_confirmations (
                  id, review_key, question_type, status, title, question,
                  summary, requirement, evidence_excerpt, opportunity_key,
                  opportunity_company, opportunity_title, created_at, updated_at
                ) VALUES (?, ?, 'hard_gate_review', 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    review_key,
                    "Review a possible hard requirement",
                    "Should this requirement disqualify the opportunity?",
                    "Applyr will not disqualify this opportunity without your explicit decision.",
                    (requirement or "").strip() or None,
                    (evidence_excerpt or "").strip() or None,
                    opportunity,
                    (opportunity_company or "").strip() or "Unknown company",
                    (opportunity_title or "").strip() or "Untitled opportunity",
                    now,
                    now,
                ),
            )
        return ConfirmationResult(True, review_key)
    finally:
        connection.close()


def get_hard_gate_decision(
    review_key: str,
    db_path: str | Path | None = None,
) -> str | None:
    """Read a completed hard-gate action for a review key."""
    connection = _connect(db_path)
    try:
        row = connection.execute(
            """
            SELECT answer
            FROM pending_skill_confirmations
            WHERE review_key = ? AND question_type = 'hard_gate_review'
              AND status = 'completed'
            """,
            ((review_key or "").strip(),),
        ).fetchone()
        return str(row["answer"]) if row and row["answer"] else None
    finally:
        connection.close()


def answer_hard_gate_review(
    *,
    db_path: str | Path | None = None,
    review_key: str,
    answer: str,
) -> AnswerResult:
    """Resolve a hard-gate review with an explicit documented action."""
    if answer not in {"KEEP_ELIGIBLE", "CONFIRM_HARD", "NEEDS_MORE_INFO"}:
        raise ValueError("invalid hard-gate review answer")
    connection = _connect(db_path)
    try:
        row = connection.execute(
            """
            SELECT question_type
            FROM pending_skill_confirmations
            WHERE review_key = ?
            """,
            ((review_key or "").strip(),),
        ).fetchone()
        if not row or row["question_type"] != "hard_gate_review":
            raise KeyError("hard-gate review not found")
        completed = answer != "NEEDS_MORE_INFO"
        now = _utc_now()
        with connection:
            connection.execute(
                """
                UPDATE pending_skill_confirmations
                SET status = ?, answer = ?, updated_at = ?, resolved_at = ?
                WHERE review_key = ?
                """,
                (
                    "completed" if completed else "open",
                    answer,
                    now,
                    now if completed else None,
                    review_key,
                ),
            )
            connection.execute(
                """
                INSERT INTO review_answer_history (
                  id, review_key, question_type, answer, details_json, answered_at
                ) VALUES (?, ?, 'hard_gate_review', ?, NULL, ?)
                """,
                (str(uuid.uuid4()), review_key, answer, now),
            )
        return AnswerResult("completed" if completed else "open")
    finally:
        connection.close()


def list_pending_for_opportunity(
    opportunity_key: str,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """List open confirmation rows for one opportunity in creation order."""
    connection = _connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT id, review_key, question_type, skill_key, status, title,
                   question, summary, requirement, evidence_excerpt,
                   opportunity_key, opportunity_company, opportunity_title,
                   opportunity_status, answer, answer_details_json,
                   created_at, updated_at, resolved_at
            FROM pending_skill_confirmations
            WHERE opportunity_key = ? AND status = 'open'
            ORDER BY created_at ASC
            """,
            ((opportunity_key or "").strip(),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def list_open_confirmations(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    """List every open confirmation occurrence for the harness queue."""
    connection = _connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT id, review_key, question_type, skill_key, status, title,
                   question, summary, requirement, evidence_excerpt,
                   opportunity_key, opportunity_company, opportunity_title,
                   opportunity_status, answer, answer_details_json,
                   created_at, updated_at, resolved_at
            FROM pending_skill_confirmations
            WHERE status = 'open'
            ORDER BY created_at ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def answer_confirmation(
    *,
    db_path: str | Path | None = None,
    review_key: str,
    answer: SkillAnswer,
    details: dict[str, Any] | None = None,
    promote_to_verified_evidence: bool = False,
) -> AnswerResult:
    """Resolve a skill confirmation and maintain its durable memory."""
    if answer not in {"CONFIRMED_USE", "NOT_PRESENT", "UNSURE_NO_REASK"}:
        raise ValueError("invalid skill confirmation answer")
    connection = _connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT id, skill_key, title, question_type, opportunity_key,
                   opportunity_company, opportunity_title, opportunity_status,
                   requirement, evidence_excerpt
            FROM pending_skill_confirmations
            WHERE review_key = ?
            """,
            ((review_key or "").strip(),),
        ).fetchall()
        if not rows:
            raise KeyError("confirmation not found")
        if any(
            row["question_type"] not in {"skill_presence", "evidence_enrichment"}
            for row in rows
        ):
            raise ValueError("review key is not a skill confirmation")
        is_presence = all(row["question_type"] == "skill_presence" for row in rows)
        skill_key = str(rows[0]["skill_key"] or "")
        payload = details if isinstance(details, dict) else {}
        if promote_to_verified_evidence and (
            answer != "CONFIRMED_USE"
            or not all(
                str(payload.get(field) or "").strip()
                for field in ("context", "activity", "timeframe")
            )
        ):
            raise ValueError(
                "verified evidence requires a Yes answer plus context, activity, and timeframe"
            )
        now = _utc_now()
        serialized = json.dumps(payload, ensure_ascii=False) if payload else None
        existing_promotion = None
        if promote_to_verified_evidence:
            existing_promotion = connection.execute(
                """
                SELECT id, status
                FROM evidence_promotion_proposals
                WHERE skill_key = ? AND status IN ('PENDING_SOURCE_UPDATE', 'VERIFIED')
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (skill_key,),
            ).fetchone()
        decision: SkillDecision = (
            "VERIFIED_EVIDENCE"
            if existing_promotion and existing_promotion["status"] == "VERIFIED"
            else answer
        )
        evidence_level = (
            2 if decision == "VERIFIED_EVIDENCE"
            else 1 if decision == "CONFIRMED_USE"
            else 0
        )
        completed = True
        promotion_id: str | None = None
        with connection:
            connection.execute(
                """
                UPDATE pending_skill_confirmations
                SET status = 'completed', answer = ?, answer_details_json = ?,
                    updated_at = ?, resolved_at = ?
                WHERE review_key = ?
                """,
                (answer, serialized, now, now, review_key),
            )
            if is_presence:
                connection.execute(
                    """
                    INSERT INTO skill_memory (
                      skill_key, display_name, decision, evidence_level,
                      details_json, source, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'user_confirmation', ?, ?)
                    ON CONFLICT(skill_key) DO UPDATE SET
                      display_name = excluded.display_name,
                      decision = excluded.decision,
                      evidence_level = excluded.evidence_level,
                      details_json = excluded.details_json,
                      updated_at = excluded.updated_at
                    """,
                    (
                        skill_key,
                        rows[0]["title"],
                        decision,
                        evidence_level,
                        serialized,
                        now,
                        now,
                    ),
                )
            if promote_to_verified_evidence:
                promotion_id = (
                    str(existing_promotion["id"])
                    if existing_promotion
                    else str(uuid.uuid4())
                )
                if existing_promotion is None:
                    connection.execute(
                        """
                        INSERT INTO evidence_promotion_proposals (
                          id, skill_key, review_key, details_json, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (promotion_id, skill_key, review_key, serialized or "{}", now, now),
                    )
            if is_presence and answer == "CONFIRMED_USE" and not promote_to_verified_evidence:
                for row in rows:
                    _create_evidence_enrichment(connection, row, now)
            if answer in {"NOT_PRESENT", "UNSURE_NO_REASK"}:
                connection.execute(
                    """
                    UPDATE pending_skill_confirmations
                    SET status = 'completed', answer = ?, updated_at = ?, resolved_at = ?
                    WHERE skill_key = ? AND question_type = 'evidence_enrichment'
                      AND status = 'open'
                    """,
                    (answer, now, now, skill_key),
                )
            connection.execute(
                """
                INSERT INTO review_answer_history (
                  id, review_key, question_type, answer, details_json, answered_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    review_key,
                    rows[0]["question_type"],
                    answer,
                    serialized,
                    now,
                ),
            )
        return AnswerResult("completed" if completed else "open", promotion_id)
    finally:
        connection.close()


def _create_evidence_enrichment(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    now: str,
) -> None:
    """Create one optional evidence occurrence when a skill presence is confirmed."""
    skill_key = str(row["skill_key"] or "")
    review_key = f"skill:{skill_key}:evidence"
    existing = connection.execute(
        """
        SELECT id
        FROM pending_skill_confirmations
        WHERE review_key = ? AND opportunity_key = ? AND status = 'open'
        """,
        (review_key, row["opportunity_key"]),
    ).fetchone()
    if existing:
        return
    connection.execute(
        """
        INSERT INTO pending_skill_confirmations (
          id, review_key, question_type, skill_key, status, title, question,
          summary, requirement, evidence_excerpt, opportunity_key,
          opportunity_company, opportunity_title, opportunity_status,
          created_at, updated_at
        ) VALUES (?, ?, 'evidence_enrichment', ?, 'open', ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            review_key,
            skill_key,
            row["title"],
            f"Add details about your {row['title']} experience.",
            "Optional: add where, what, and when so stronger requirements can be evaluated accurately.",
            row["requirement"],
            row["evidence_excerpt"],
            row["opportunity_key"],
            row["opportunity_company"],
            row["opportunity_title"],
            row["opportunity_status"],
            now,
            now,
        ),
    )


def _utc_now() -> str:
    """Return the current UTC timestamp in the format shared by server records."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def verify_evidence_promotion(
    promotion_id: str,
    *,
    source_path: str | Path | None = None,
    db_path: str | Path | None = None,
) -> bool:
    """Verify proposal details in local work experience and mark them authorable."""
    connection = _connect(db_path)
    try:
        row = connection.execute(
            """
            SELECT id, skill_key, details_json, status
            FROM evidence_promotion_proposals
            WHERE id = ?
            """,
            (promotion_id,),
        ).fetchone()
        if not row:
            return False
        if row["status"] == "VERIFIED":
            return True
        if row["status"] != "PENDING_SOURCE_UPDATE":
            return False
        path = Path(source_path) if source_path else _ROOT / "data" / "workExperience.md"
        try:
            source = path.read_text(encoding="utf-8") if path.exists() else ""
            details = json.loads(row["details_json"])
        except (OSError, TypeError, json.JSONDecodeError):
            return False
        if not isinstance(details, dict):
            return False
        required = [
            str(details.get(field) or "").strip()
            for field in ("context", "activity", "timeframe")
        ]
        if not all(value and value.casefold() in source.casefold() for value in required):
            return False
        if connection.execute(
            "SELECT 1 FROM skill_memory WHERE skill_key = ?",
            (row["skill_key"],),
        ).fetchone() is None:
            return False
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        now = _utc_now()
        with connection:
            connection.execute(
                """
                UPDATE evidence_promotion_proposals
                SET status = 'VERIFIED', source_digest = ?, updated_at = ?, verified_at = ?
                WHERE id = ?
                """,
                (digest, now, now, promotion_id),
            )
            connection.execute(
                """
                UPDATE skill_memory
                SET decision = 'VERIFIED_EVIDENCE', evidence_level = 2,
                    details_json = ?, updated_at = ?
                WHERE skill_key = ?
                """,
                (row["details_json"], now, row["skill_key"]),
            )
        return True
    finally:
        connection.close()
