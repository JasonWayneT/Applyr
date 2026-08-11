"""
Stage 3 finalize helper: insert or update the `jobs` DB row for a drafted submission.

Why this exists (2026-08-05): the app's own reconcileOrphanSubmissionFolders() auto-creates
a Backlog row for any submission folder with Resume+Cover PDFs and no matching jobs row --
but its title-parsing heuristic (server/submissionFolders.ts readJdMeta()) reads whichever
short, period-less line comes first in the JD text. On a real 9-company batch this produced
wrong titles for 5 of 9: a "Location: Remote..." line, a "PLEASE APPLY HERE: <url>" line (a
URL as the job title), two "Job Summary" section headers, and one marketing tagline. Company
casing was also wrong for 3 of 9 (its slug->title-case pass can't recover "ArcSite"/
"iConsultera"/"ConnectWise" from lowercased folder names).

The agent doing Stage 0 already knows the real title (it read the JD). This script writes
that known-correct data directly instead of leaving it to the heuristic to guess after the
fact -- inserts a new row if none exists for the company, or corrects company/title on an
existing one (e.g. one the heuristic already created wrong).

2026-08-07: company-only UPDATE is unsafe when the same employer has multiple postings.
Prefer URL match. Only update a single company row when status is still Backlog/Drafted and
the URL is empty or equal to this finalize URL; otherwise insert. Found live: Thermo Fisher
Digital PM finalize retitled a Closed Gas Analyzers row and left its Builtin URL.

Usage:
    python scripts/finalize_submission_job.py "Asurion" "Sr Product Manager" \\
        --url "https://www.linkedin.com/jobs/view/4391081682/" --slug asurion
    python scripts/finalize_submission_job.py "AcuityMD" "Product Manager" --reach-out

2026-08-06: when --slug is given, this now refuses to run (exit 1, DB untouched) unless
data/submissions/{slug} has cleared scripts/contracts.py's check_finalize_ready -- a passing,
freshly-generated verification_receipt.json plus a draft_manifest.json with
verification_passed=true. This is enforced here, in the script, not left to whichever agent
is calling it to have checked first -- see NotReadyToFinalizeError below for why. Pass --force
to override deliberately (e.g. correcting an already-verified row's title/casing).
"""
from __future__ import annotations

import argparse
import os
import re
import secrets
import sqlite3
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
_DB_PATH = os.path.join(_REPO_ROOT, "data", "jobagent.sqlite")
_SUBMISSIONS_DIR = os.path.join(_REPO_ROOT, "data", "submissions")

sys.path.insert(0, _SCRIPT_DIR)
import contracts  # noqa: E402
import stage_gate  # noqa: E402


class NotReadyToFinalizeError(Exception):
    """Raised when --slug's folder hasn't cleared contracts.check_finalize_ready.

    Why this lives in the script itself (2026-08-06), not just as an instruction to whichever
    agent calls it: a prompt telling an agent to "run verify_submission.py first" can be
    skipped under pressure -- that's the exact failure this whole process exists to close. A
    check enforced in the function itself can't be skipped by an agent in a hurry; it can only
    be explicitly overridden with --force, which is a visible, deliberate choice, not a silent
    omission.
    """


class ImplausibleJobTitleError(Exception):
    """Raised when finalize would write JD chrome (section header / CTA) as jobs.title.

    Found live 2026-08-11: LeafLink finalized as 'The Role', Camunda as 'Register Here!'.
    Not bypassable with --force — pass the real role title instead.
    """


def _require_plausible_title(title: str) -> None:
    from seniority_gate import is_implausible_job_title

    if is_implausible_job_title(title):
        raise ImplausibleJobTitleError(
            f"Refusing to finalize with implausible job title {title!r}. "
            f"Stage 0 likely captured JD chrome (section header / apply CTA). "
            f"Pass the real role title (e.g. 'Product Manager') via CLI --title / "
            f"orchestrator --title, or fix stage0_fit_gate.json 'role'."
        )


def _require_ready(slug: str, force: bool) -> None:
    """Stage 3 gate. Semantics unchanged (bare --force, NotReadyToFinalizeError).

    CR-075 Story 4.4: when --force bypasses a real failure, append to the durable
    override log via stage_gate.log_force_override. Do not route through
    require_stage_ready -- keep this gate's existing error type and message.

    Stabilization (2026-08-11): if the folder is adopted into workflow authority
    (workflow_state.json present), also require an orchestrator-issued Stage 2
    COMPLETE receipt. This closes the direct-CLI path that could DB-finalize a
    folder still WAITING_FOR_LLM / mid Stage 2 while only clearing
    check_finalize_ready. Legacy non-adopted folders (no workflow_state) keep
    the prior CR-075-only gate so already-verified submissions stay finalizable.
    """
    folder = os.path.join(_SUBMISSIONS_DIR, slug)
    ok, errors = contracts.check_finalize_ready(folder)
    if not ok:
        if force:
            stage_gate.log_force_override("stage3", folder, reason=None, argv=sys.argv)
            return
        detail = "\n".join(f"  - {e}" for e in errors)
        raise NotReadyToFinalizeError(
            f"data/submissions/{slug} is not ready to finalize:\n{detail}\n"
            f"Fix these (usually: re-run scripts/verify_submission.py, fill in draft_manifest.json's "
            f"rubric_score, re-run --audit) or pass --force if this is a deliberate override "
            f"(e.g. correcting an already-verified row's title/casing)."
        )

    state_path = os.path.join(folder, "workflow_state.json")
    if not os.path.exists(state_path):
        return

    s2_path = os.path.join(folder, "stage_receipts", "stage2.json")
    s2, s2err = contracts.load_json(s2_path) if os.path.exists(s2_path) else (None, "missing")
    s2_ok = (
        isinstance(s2, dict)
        and s2.get("status") == "COMPLETE"
        and s2.get("issued_by") == "scripts/run_submission.py"
    )
    if s2_ok:
        return

    if force:
        stage_gate.log_force_override("stage3", folder, reason=None, argv=sys.argv)
        return

    state, _ = contracts.load_json(state_path)
    status = (state or {}).get("status")
    detail = s2err or (
        f"status={s2.get('status')!r}, issued_by={s2.get('issued_by')!r}"
        if isinstance(s2, dict)
        else "unreadable"
    )
    raise NotReadyToFinalizeError(
        f"data/submissions/{slug} is adopted into workflow authority "
        f"(workflow status={status!r}) but Stage 2 is not COMPLETE under "
        f"scripts/run_submission.py ({detail}). Finish Stage 2 via "
        f"`python scripts/run_submission.py data/submissions/{slug} --resume` "
        f"then `--finalize`, or pass --force for a deliberate override."
    )


def _read_jd(slug: str) -> tuple[str | None, str]:
    """Return (url, jd_text) from a submission folder's Original_JD.txt, if present."""
    jd_path = os.path.join(_SUBMISSIONS_DIR, slug, "Original_JD.txt")
    if not os.path.exists(jd_path):
        return None, ""
    with open(jd_path, encoding="utf-8") as f:
        raw = f.read()
    m = re.match(r"^URL:\s*(\S+)\s*\n\n(.*)$", raw, flags=re.DOTALL)
    if m:
        return m.group(1), m.group(2)
    return None, raw


def finalize(company: str, title: str, slug: str | None = None, url: str | None = None,
             reach_out: bool = False, db_path: str = _DB_PATH, force: bool = False) -> str:
    """Insert or correct the jobs row for `company`. Returns 'inserted' or 'updated'.

    Raises NotReadyToFinalizeError if --slug is given and its folder hasn't cleared
    contracts.check_finalize_ready (a passing, fresh verification_receipt.json plus a
    draft_manifest.json with verification_passed=true) -- unless force=True. Without a slug
    there's no folder to check against, so the gate doesn't apply (this script is occasionally
    used for a bare title/company correction with no folder involved).
    """
    if slug:
        _require_ready(slug, force)

    _require_plausible_title(title)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    jd_text = ""
    if slug:
        parsed_url, jd_text = _read_jd(slug)
        url = url or parsed_url

    display_title = f"[Reach Out] {title}" if reach_out else title

    # Company-only match is unsafe when the same employer has multiple postings
    # (found 2026-08-07: Thermo Fisher Digital PM finalize retitled a Closed Gas
    # Analyzers row and left its Builtin URL). Prefer URL match; only update an
    # existing company row when it is still an active pipeline status and either
    # has no URL yet or shares this finalize URL. Otherwise insert.
    _ACTIVE = ("Backlog", "Drafted")
    match_id = None
    if url:
        cur.execute(
            "SELECT id FROM jobs WHERE lower(company) = ? AND url = ?",
            (company.lower(), url),
        )
        url_row = cur.fetchone()
        if url_row:
            match_id = url_row[0]
        if match_id is None:
            # URL is unique in jobs — if another row already owns this posting URL,
            # update that row rather than failing INSERT with UNIQUE constraint.
            cur.execute("SELECT id, company FROM jobs WHERE url = ?", (url,))
            by_url = cur.fetchone()
            if by_url:
                match_id = by_url[0]
    if match_id is None:
        cur.execute(
            "SELECT id, url, status FROM jobs WHERE lower(company) = ?",
            (company.lower(),),
        )
        company_rows = cur.fetchall()
        if len(company_rows) == 1:
            job_id, existing_url, status = company_rows[0]
            status_ok = (status or "") in _ACTIVE
            url_ok = (not existing_url) or (not url) or (existing_url == url)
            if status_ok and url_ok:
                match_id = job_id

    if match_id is not None:
        cur.execute(
            "UPDATE jobs SET company = ?, title = ?, url = COALESCE(?, url), "
            "jd_text = COALESCE(?, jd_text) WHERE id = ?",
            (company, display_title, url, jd_text or None, match_id),
        )
        conn.commit()
        conn.close()
        return (
            f"updated: {company} (id={match_id}) -> title={display_title!r}, url={url}"
        )

    job_id = secrets.token_hex(4)
    summary = f"Ready to apply -- {company} (assets on disk; linked from submissions/)."
    cur.execute(
        """
        INSERT INTO jobs (id, company, title, url, score, status, summary, jd_text, retry_count)
        VALUES (?, ?, ?, ?, 80, 'Backlog', ?, ?, 0)
        """,
        (job_id, company, display_title, url, summary, jd_text or None),
    )
    conn.commit()
    conn.close()
    return f"inserted: {company} (id={job_id}) -> title={display_title!r}, url={url}"


def _run_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("company", help="Company name, correctly capitalized (e.g. 'ArcSite')")
    parser.add_argument("title", help="Real job title from the JD, e.g. 'Sr Product Manager'")
    parser.add_argument("--slug", help="Submission folder name under data/submissions/, to pull URL/JD text from")
    parser.add_argument("--url", help="Job posting URL (overrides --slug's parsed URL if both given)")
    parser.add_argument("--reach-out", action="store_true", help="Prefix the title with [Reach Out]")
    parser.add_argument("--force", action="store_true",
                         help="Bypass the finalize-ready contract check (contracts.check_finalize_ready). "
                              "Only for deliberate overrides, e.g. correcting an already-verified row's "
                              "title/casing -- not a routine flag.")
    args = parser.parse_args(argv)

    try:
        result = finalize(args.company, args.title, slug=args.slug, url=args.url,
                           reach_out=args.reach_out, force=args.force)
    except NotReadyToFinalizeError as e:
        print(str(e))
        return 1
    except ImplausibleJobTitleError as e:
        print(str(e))
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    from workflow.entry_warning import warn_worker_cli
    warn_worker_cli("finalize_submission_job.py")
    sys.exit(_run_cli(sys.argv[1:]))
