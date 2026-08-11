#!/usr/bin/env python3
"""
Stage 0 DB cooldown / Self-Rejected gate — no LLM required.

Queries the jobs table to decide whether a company name is blocked by a
prior rejection cooldown or a permanent Self-Rejected entry before any
drafting work begins.

Usage (CLI):
    python scripts/stage0_db_gate.py "Company Name"

Exit codes:
    0 — always (clear, reapply_flag, and reject all exit 0).
    Callers should read the JSON "action" field to branch:
        "clear"        — no prior terminal rows, safe to proceed
        "reapply_flag" — prior rejections exist but all cooldowns have
                         expired; proceed with Tier 2 flag
        "reject"       — still within cooldown or Self-Rejected; do not draft
"""
# Implements FR-252
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent
_DEFAULT_DB = _REPO_ROOT / "data" / "jobagent.sqlite"

# --- Cooldown constants (days) ---
_COOLDOWN_EVALUATED_NO = 120  # Rejected / Domain Mismatch / Title Ceiling / Unfit / Mismatch
_COOLDOWN_NO_SIGNAL = 30      # Ghosted / No Longer Available / unset / null

_EVALUATED_NO_TYPES = frozenset(
    {"Rejected", "Domain Mismatch", "Title Ceiling", "Unfit", "Mismatch"}
)
_NO_SIGNAL_TYPES = frozenset({"Ghosted", "No Longer Available"})

_TERMINAL_STATUSES = frozenset({"Rejected", "Closed"})

_PENDING_ASSETS_PREFIX = "Pending-assets cleanup"


# ---------------------------------------------------------------------------
# Token / word-boundary match
# ---------------------------------------------------------------------------

def company_token_match(query: str, row_company: str) -> bool:
    """Return True if every token in *query* appears as a whole word in *row_company*.

    Case-insensitive.  Tokens are split on whitespace and punctuation so that
    short names like "Kin" do not match "DraftKings".

    >>> company_token_match("Kin", "DraftKings")
    False
    >>> company_token_match("Kin Insurance", "Kin Insurance")
    True
    """
    query_tokens = re.split(r"[\s\W]+", query.strip().lower())
    query_tokens = [t for t in query_tokens if t]
    if not query_tokens:
        return False
    row_lower = row_company.lower()
    for token in query_tokens:
        pattern = r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])"
        if not re.search(pattern, row_lower):
            return False
    return True


# Generic role words that carry no distinguishing signal on their own — a title
# reduced to only these (e.g. "Product Manager") is not specific enough to prove
# or disprove a role match, so it's treated as ambiguous (conservative: blocking).
_GENERIC_ROLE_WORDS = frozenset({
    "product", "manager", "owner", "senior", "sr", "jr", "junior", "lead",
    "principal", "staff", "associate", "director", "head", "vp", "of", "the",
    "a", "an", "and", "i", "ii", "iii", "iv",
})


def is_different_role(query_role: str, row_title: str) -> bool:
    """True only when both titles have a real, non-generic remainder after
    stripping generic PM words, and those remainders share no token — i.e. we
    can positively tell these are different roles at the same company, not
    just that we don't know.

    Found 2026-08-08 (session-005 R14/R15, thermo_fisher_scientific): the
    cooldown/self-reject gate matched by company name only, so a self-rejected
    "Product Manager, Gas Analyzers" posting permanently blocked an unrelated
    "Digital Product Manager" role at the same company. Ambiguous cases (no
    row title on record, or either title reduces to only generic words) stay
    conservative and are NOT treated as different — this only carves out roles
    that are clearly, distinguishably different, it never widens what counts
    as a match.
    """
    if not query_role or not row_title:
        return False

    def _remainder(text: str) -> set[str]:
        tokens = re.split(r"[\s\W]+", text.strip().lower())
        return {t for t in tokens if t and t not in _GENERIC_ROLE_WORDS}

    query_remainder = _remainder(query_role)
    row_remainder = _remainder(row_title)
    if not query_remainder or not row_remainder:
        return False  # nothing distinguishing on one side — stay conservative
    return query_remainder.isdisjoint(row_remainder)


# ---------------------------------------------------------------------------
# Row classifier
# ---------------------------------------------------------------------------

def classify_rejection_row(
    row: dict,
    now: datetime | None = None,
) -> dict:
    """Classify a single jobs-table row and return a verdict dict.

    Returns:
        {
            "company": str,
            "status": str,
            "rejection_type": str | None,
            "outcome_notes": str | None,
            "category": "evaluated_no" | "no_signal" | "self_rejected",
            "cooldown_days": int | None,   # None for permanent Self-Rejected
            "within_cooldown": bool,
            "reason_detail": str,
        }
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)

    status = (row.get("status") or "").strip()
    rejection_type = (row.get("rejection_type") or "").strip()
    outcome_notes = (row.get("outcome_notes") or "").strip()
    changed_at_raw = row.get("status_changed_at")
    title = row.get("title") or ""

    # --- Self-Rejected ---
    if status == "Self-Rejected":
        if outcome_notes.startswith(_PENDING_ASSETS_PREFIX):
            # Treat like "no real signal" — 30-day cooldown
            category = "no_signal"
            cooldown_days = _COOLDOWN_NO_SIGNAL
        else:
            return {
                "company": row.get("company", ""),
                "title": title or None,
                "status": status,
                "rejection_type": rejection_type or None,
                "outcome_notes": outcome_notes or None,
                "category": "self_rejected",
                "cooldown_days": None,
                "within_cooldown": True,  # permanent
                "reason_detail": "Self-Rejected (permanent block)",
            }
    elif status in _TERMINAL_STATUSES:
        if rejection_type in _EVALUATED_NO_TYPES:
            category = "evaluated_no"
            cooldown_days = _COOLDOWN_EVALUATED_NO
        elif rejection_type in _NO_SIGNAL_TYPES or not rejection_type:
            category = "no_signal"
            cooldown_days = _COOLDOWN_NO_SIGNAL
        else:
            # Unknown rejection_type — treat conservatively as no_signal
            category = "no_signal"
            cooldown_days = _COOLDOWN_NO_SIGNAL
    else:
        # Not a terminal row — should not reach here in normal usage
        return {
            "company": row.get("company", ""),
            "title": title or None,
            "status": status,
            "rejection_type": rejection_type or None,
            "outcome_notes": outcome_notes or None,
            "category": "non_terminal",
            "cooldown_days": None,
            "within_cooldown": False,
            "reason_detail": f"Status '{status}' is not terminal",
        }

    # --- Compute within_cooldown ---
    if changed_at_raw is None:
        # NULL status_changed_at — conservative: treat as still within cooldown
        within_cooldown = True
        reason_detail = (
            f"{category} | NULL status_changed_at → treated as within {cooldown_days}d cooldown"
        )
    else:
        try:
            if isinstance(changed_at_raw, str):
                changed_at = datetime.fromisoformat(changed_at_raw.replace("Z", "+00:00"))
            else:
                changed_at = changed_at_raw
            if changed_at.tzinfo is None:
                changed_at = changed_at.replace(tzinfo=timezone.utc)
            elapsed = now - changed_at
            within_cooldown = elapsed < timedelta(days=cooldown_days)
            reason_detail = (
                f"{category} | {elapsed.days}d elapsed vs {cooldown_days}d cooldown"
            )
        except (ValueError, TypeError):
            # Unparseable date — be conservative
            within_cooldown = True
            reason_detail = (
                f"{category} | unparseable status_changed_at → treated as within cooldown"
            )

    return {
        "company": row.get("company", ""),
        "title": title or None,
        "status": status,
        "rejection_type": rejection_type or None,
        "outcome_notes": outcome_notes or None,
        "category": category,
        "cooldown_days": cooldown_days,
        "within_cooldown": within_cooldown,
        "reason_detail": reason_detail,
    }


# ---------------------------------------------------------------------------
# Main gate function
# ---------------------------------------------------------------------------

def evaluate_db_gate(
    company: str,
    role: str | None = None,
    db_path: Path | None = None,
    now: datetime | None = None,
    _conn: "sqlite3.Connection | None" = None,
) -> dict:
    """Query the jobs DB and decide whether *company* is gated.

    # Implements FR-252

    Parameters
    ----------
    company:
        The company name to look up (matched with word-boundary logic).
    role:
        The current job's title/role, if known. When provided, a prior
        terminal row is only treated as blocking if its own title can't be
        positively distinguished from *role* (see is_different_role). A row
        whose title is clearly a different role at the same company (e.g. a
        self-rejected "Gas Analyzers" PM posting vs. a "Digital Product
        Manager" role) no longer blocks — found 2026-08-08, see R14/R15 in
        harness-bridge session-005. Ambiguous cases (no title on file, or
        either title reduces to only generic PM words) stay conservative and
        still block, matching the pre-existing company-wide behavior.
    db_path:
        Path to the SQLite file.  Defaults to ``data/jobagent.sqlite`` at
        repo root.  Ignored when *_conn* is provided.
    now:
        Datetime to use as "today" (defaults to UTC now).  Pass a fixed
        datetime in tests to make results deterministic.
    _conn:
        Inject an open sqlite3 connection (used by tests to pass in-memory
        fixtures).  When provided, *db_path* is ignored and the connection
        is NOT closed by this function.

    Returns
    -------
    dict with keys:
        action       — "clear" | "reject" | "reapply_flag"
        reason_code  — short code string
        reason       — human-readable explanation
        matched_rows — list of classified row dicts for every terminal row
                       whose company matched (all statuses, not just blocking)
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)
    if db_path is None:
        db_path = _DEFAULT_DB

    company_lower = company.lower().strip()
    close_after = False

    if _conn is not None:
        conn = _conn
    else:
        if not Path(db_path).exists():
            return {
                "action": "clear",
                "reason_code": "no_db",
                "reason": f"DB not found at {db_path}; treating as clear",
                "matched_rows": [],
            }
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        close_after = True

    try:
        cur = conn.execute(
            """
            SELECT status, rejection_type, status_changed_at, company, outcome_notes, title
            FROM jobs
            WHERE lower(company) LIKE ?
            """,
            (f"%{company_lower}%",),
        )
        raw_rows = cur.fetchall()
    finally:
        if close_after:
            conn.close()

    # Filter to rows whose company is a genuine token match
    matched_rows_raw = [
        dict(r) for r in raw_rows
        if company_token_match(company, dict(r).get("company", ""))
    ]

    # Only classify terminal rows
    terminal_raw = [
        r for r in matched_rows_raw
        if (r.get("status") or "") in _TERMINAL_STATUSES
        or (r.get("status") or "") == "Self-Rejected"
    ]

    if not terminal_raw:
        return {
            "action": "clear",
            "reason_code": "no_terminal_rows",
            "reason": f"No prior Rejected/Closed/Self-Rejected rows found for '{company}'",
            "matched_rows": [],
        }

    classified = [classify_rejection_row(r, now=now) for r in terminal_raw]

    # Rows whose title is positively a different role at the same company don't
    # count toward blocking — they're kept in matched_rows for visibility, just
    # excluded from perm_blocks/active_blocks below. See is_different_role().
    def _blocks(c: dict) -> bool:
        if role and c.get("title") and is_different_role(role, c["title"]):
            return False
        return True

    # Self-Rejected permanent blocks
    perm_blocks = [c for c in classified if c["category"] == "self_rejected" and _blocks(c)]
    if perm_blocks:
        return {
            "action": "reject",
            "reason_code": "self_rejected",
            "reason": (
                f"'{company}' has a permanent Self-Rejected entry "
                f"(row company: {perm_blocks[0]['company']!r})"
            ),
            "matched_rows": classified,
        }

    # Any row still within cooldown
    active_blocks = [c for c in classified if c.get("within_cooldown") and _blocks(c)]
    if active_blocks:
        first = active_blocks[0]
        return {
            "action": "reject",
            "reason_code": f"cooldown_{first['category']}",
            "reason": (
                f"'{company}' is within {first['cooldown_days']}-day cooldown "
                f"({first['reason_detail']})"
            ),
            "matched_rows": classified,
        }

    # All remaining blocking rows are either past cooldown, or were excluded
    # entirely because their title is a positively different role at this
    # company (never blocking in the first place, not "expired").
    blocking_candidates = [c for c in classified if _blocks(c)]
    if role and not blocking_candidates and classified:
        return {
            "action": "reapply_flag",
            "reason_code": "different_role_at_company",
            "reason": (
                f"'{company}' has prior terminal row(s), but title(s) on file "
                f"({', '.join(sorted({c['title'] for c in classified if c.get('title')}))}) "
                f"are a different role than '{role}'; proceed with Tier 2 reapply flag"
            ),
            "matched_rows": classified,
        }

    return {
        "action": "reapply_flag",
        "reason_code": "reapply_eligible",
        "reason": (
            f"'{company}' has prior terminal rows but all cooldowns have expired; "
            "proceed with Tier 2 reapply flag"
        ),
        "matched_rows": classified,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 0 DB gate: check if a company is blocked by a prior rejection."
    )
    parser.add_argument("company", help="Company name to look up")
    parser.add_argument(
        "--db",
        default=str(_DEFAULT_DB),
        help=f"Path to jobagent.sqlite (default: {_DEFAULT_DB})",
    )
    args = parser.parse_args()

    result = evaluate_db_gate(args.company, db_path=Path(args.db))
    print(json.dumps(result, indent=2, default=str))
    # Always exit 0 — callers read the "action" field to branch.
    # Rationale: exit-code branching on reject is fragile in pipelines that
    # might also raise on import errors (exit 1) or Python errors (exit 2).
    # Structured JSON is the stable interface.
    sys.exit(0)


if __name__ == "__main__":
    _main()
