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


# CR-092 (2026-08-15): a JD posted via a job-board mirror (e.g. AdaMarie
# republishing a Pinterest listing) carries the board's own name in the CSV
# "Company" column, not the real employer's -- the DB gate below only ever
# saw that column, so it ran against a company with zero history and missed
# a real 4-day-old Applied row at the actual employer for the identical
# posting. Job postings overwhelmingly self-identify their real employer in
# a small, predictable phrasing set ("About {Company}", "Why {Company}?",
# "{Company} is looking for", "Join {Company}") -- this mirrors the bound
# capitalized-token-run pattern the "culture" section header already uses in
# build_stage0_fit_gate.py for the same phrasing family, repurposed here to
# actually capture the name instead of just detecting the header line.
_NAME_TOKEN = r"[A-Z][\w'&.-]{1,30}(?:\s+[A-Z][\w'&.-]{1,30}){0,2}"
_SELF_ID_COMPANY_RE = re.compile(
    r"(?:"
    r"\babout\s+(?!us\b|you\b|your\b|the\s+role\b|the\s+team\b|this\s+role\b)"
    r"(?-i:(?P<name1>" + _NAME_TOKEN + r"))|"
    r"\bwhy\s+(?-i:(?P<name2>" + _NAME_TOKEN + r"))\s*[?!]|"
    r"\bjoin\s+(?-i:(?P<name3>" + _NAME_TOKEN + r"))\b|"
    r"\b(?-i:(?P<name4>" + _NAME_TOKEN + r"))\s+is\s+(?:looking\s+for|seeking|searching\s+for|hiring)\b"
    r")",
    re.I,
)

# Common non-company capitalized phrases these patterns would otherwise false-
# positive on (role/section words, not employer names).
_SELF_ID_STOPWORDS = frozenset({
    "we", "you", "your", "the", "this", "our", "us", "i", "product",
    "manager", "team", "role", "position", "job", "opportunity",
})


def extract_self_identified_company(jd_text: str) -> str | None:
    """Best-effort extraction of the employer's own self-identified name from
    JD body text (e.g. "About Pinterest", "Why Tenna?"). Returns None if no
    match -- a real, expected outcome for JDs that never self-identify
    (falls back to CSV-name-only DB checking, same as before this existed),
    not an error. Deliberately a lightweight pattern match, not NER --
    job postings self-identify in a small, predictable set of phrasings, so
    a heavier dependency isn't warranted for this specific shape of input."""
    for m in _SELF_ID_COMPANY_RE.finditer(jd_text):
        name = next((g for g in m.groups() if g), None)
        if not name:
            continue
        name = name.strip()
        if name.lower() in _SELF_ID_STOPWORDS:
            continue
        # Reject a single generic word (e.g. a stray "The Company") --
        # require either a multi-token name or a single token at least 3
        # chars that isn't purely a common English word start.
        if " " not in name and len(name) < 3:
            continue
        return name
    return None


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

def _evaluate_db_gate_core(
    company: str,
    role: str | None = None,
    db_path: Path | None = None,
    now: datetime | None = None,
    _conn: "sqlite3.Connection | None" = None,
) -> dict:
    """Query the jobs DB and decide whether *company* is gated.

    Renamed from evaluate_db_gate (CR-092, 2026-08-15) -- this is now the
    single-name core the public evaluate_db_gate() wrapper below calls once
    or twice (CSV name, and a JD-self-identified name if they differ).

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


def _find_active_applications(
    company: str,
    role: str | None,
    db_path: Path | None,
    _conn: "sqlite3.Connection | None",
) -> list[dict]:
    """Non-terminal (Applied/Backlog/Interviewing/etc.) rows for *company*,
    role-filtered the same way terminal rows already are.

    CR-092 follow-up (2026-08-15, Jason-supplied): the cooldown/reject gate
    above only ever looks at terminal rows (Rejected/Closed/Self-Rejected).
    An already-in-progress application (status "Applied") is a different,
    equally real duplicate signal it was never designed to catch -- this is
    what the real Pinterest/AdaMarie near-miss actually was (an Applied row,
    not a cooldown case), and Bug 5's company_mismatch fix alone doesn't
    close it since that only feeds the cooldown/reject path. Deliberately a
    flag, not an auto-Skip: per generate-submission/SKILL.md, an active-row
    duplicate ("Kroll-style") "belong[s] in Tier 2, not their own category"
    -- a human call, not an automatic reject, since an active row could be a
    stale/abandoned Backlog entry as easily as a genuine live application."""
    if _conn is not None:
        conn = _conn
        close_after = False
    else:
        path = db_path or _DEFAULT_DB
        if not Path(path).exists():
            return []
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        close_after = True

    try:
        cur = conn.execute(
            "SELECT status, title, company FROM jobs WHERE lower(company) LIKE ?",
            (f"%{company.lower().strip()}%",),
        )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        if close_after:
            conn.close()

    active = []
    for r in rows:
        status = (r.get("status") or "").strip()
        if not status or status in _TERMINAL_STATUSES or status == "Self-Rejected":
            continue
        if not company_token_match(company, r.get("company", "")):
            continue
        if role and r.get("title") and is_different_role(role, r["title"]):
            continue  # positively a different role -- not the same posting
        active.append({"status": status, "title": r.get("title"), "company": r.get("company")})
    return active


# Action severity, most restrictive first -- used to pick one result when a
# company_mismatch means two names were checked and they disagree.
_ACTION_SEVERITY = {"reject": 0, "reapply_flag": 1, "clear": 2}


def evaluate_db_gate(
    company: str,
    role: str | None = None,
    db_path: Path | None = None,
    now: datetime | None = None,
    _conn: "sqlite3.Connection | None" = None,
    jd_text: str | None = None,
) -> dict:
    """Query the jobs DB and decide whether *company* is gated -- checking
    both *company* and, if *jd_text* is given and self-identifies a
    different real employer, that employer too (CR-092, 2026-08-15).

    Why: a job-board mirror (a third-party board republishing another
    company's listing under its own brand) carries the board's name in
    whatever "company" field the caller has, not the real employer's --
    confirmed real: a Pinterest posting mirrored via "AdaMarie" missed a real
    4-day-old Applied row at Pinterest because the DB check only ever ran
    against "AdaMarie", a company with zero history. See
    extract_self_identified_company() for the extraction itself.

    When the two names genuinely disagree (company_token_match says no) and
    both have DB history, this returns whichever result is more restrictive
    (reject > reapply_flag > clear) -- conservative-default, matching this
    pipeline's existing fail-closed posture elsewhere (Stage 0's NULL-date
    cooldown handling does the same thing). *matched_rows* is the union of
    both lookups' rows. A `company_mismatch` key is always present: None if
    no jd_text was given or nothing was extracted/it matched *company*;
    otherwise {"csv": company, "jd_self_identified": <name>} -- surfaced even
    when neither name has DB history, since "this posting is a board mirror"
    is useful on its own regardless of dedup outcome."""
    primary = _evaluate_db_gate_core(company, role=role, db_path=db_path, now=now, _conn=_conn)

    self_identified = extract_self_identified_company(jd_text) if jd_text else None

    # Active-application flag: checked under whichever name(s) are in play,
    # independent of the cooldown/reject action above (see
    # _find_active_applications' own note for why this is a separate check).
    active = _find_active_applications(company, role, db_path, _conn)
    if self_identified and not company_token_match(self_identified, company):
        for row in _find_active_applications(self_identified, role, db_path, _conn):
            if row not in active:
                active.append(row)
    if active:
        primary["active_application"] = active

    if not self_identified or company_token_match(self_identified, company):
        primary["company_mismatch"] = None
        return primary

    secondary = _evaluate_db_gate_core(self_identified, role=role, db_path=db_path, now=now, _conn=_conn)

    merged_rows = list(primary.get("matched_rows") or [])
    seen = {(r.get("company"), r.get("title"), r.get("status")) for r in merged_rows}
    for r in secondary.get("matched_rows") or []:
        key = (r.get("company"), r.get("title"), r.get("status"))
        if key not in seen:
            merged_rows.append(r)
            seen.add(key)

    winner = primary if _ACTION_SEVERITY.get(primary["action"], 1) <= _ACTION_SEVERITY.get(secondary["action"], 1) else secondary
    result = dict(winner)
    result["matched_rows"] = merged_rows
    result["company_mismatch"] = {"csv": company, "jd_self_identified": self_identified}
    if active:  # active_application was computed once against both names above -- always preserve it
        result["active_application"] = active
    if winner is not primary:
        result["reason"] = (
            f"(via self-identified employer '{self_identified}', CSV said '{company}') " + result["reason"]
        )
    return result


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
