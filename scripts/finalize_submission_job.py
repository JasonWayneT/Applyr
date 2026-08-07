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


class NotReadyToFinalizeError(Exception):
    """Raised when --slug's folder hasn't cleared contracts.check_finalize_ready.

    Why this lives in the script itself (2026-08-06), not just as an instruction to whichever
    agent calls it: a prompt telling an agent to "run verify_submission.py first" can be
    skipped under pressure -- that's the exact failure this whole process exists to close. A
    check enforced in the function itself can't be skipped by an agent in a hurry; it can only
    be explicitly overridden with --force, which is a visible, deliberate choice, not a silent
    omission.
    """


def _require_ready(slug: str, force: bool) -> None:
    ok, errors = contracts.check_finalize_ready(os.path.join(_SUBMISSIONS_DIR, slug))
    if ok or force:
        return
    detail = "\n".join(f"  - {e}" for e in errors)
    raise NotReadyToFinalizeError(
        f"data/submissions/{slug} is not ready to finalize:\n{detail}\n"
        f"Fix these (usually: re-run scripts/verify_submission.py, fill in draft_manifest.json's "
        f"rubric_score, re-run --audit) or pass --force if this is a deliberate override "
        f"(e.g. correcting an already-verified row's title/casing)."
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

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    jd_text = ""
    if slug:
        parsed_url, jd_text = _read_jd(slug)
        url = url or parsed_url

    display_title = f"[Reach Out] {title}" if reach_out else title

    cur.execute("SELECT id FROM jobs WHERE lower(company) = ?", (company.lower(),))
    row = cur.fetchone()
    if row:
        job_id = row[0]
        cur.execute(
            "UPDATE jobs SET company = ?, title = ? WHERE id = ?",
            (company, display_title, job_id),
        )
        conn.commit()
        conn.close()
        return f"updated: {company} (id={job_id}) -> title={display_title!r}"

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
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(_run_cli(sys.argv[1:]))
