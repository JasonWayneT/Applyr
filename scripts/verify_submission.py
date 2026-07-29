"""
Single required verification entry point for a submission folder.

Why this exists (2026-07-23): a cross-harness run found that "run the Required
Verification commands" as prose left every harness free to invoke pieces
differently -- one harness ran lint on the cover letter only and silently
dropped the resume-side result under the same filename, and a rubric_score
got hand-typed into draft_manifest.json byte-identical across 8 different
companies without anyone (or anything) noticing. Both harnesses reading the
same SKILL.md did not prevent either failure. This script is the fix: one
command, one output shape, run by whichever harness is doing the drafting --
Claude Code, Antigravity, or anything else pointed at this repo.

What this script does NOT do: assign the qualitative rubric_score itself
(R1-R8 resume / C1-C5 cover letter against data/conversion_rubric.md). That
still requires real judgment reading the actual document against the actual
JD -- a script can't fake being a hiring-manager read, and pretending to
mechanize it would just move the fabrication risk into the script instead of
out of it. What this script DOES do: run every genuinely mechanical check in
one place so nothing gets silently skipped, and catch the specific failure
mode of a harness asserting a passing rubric score without doing the work --
via --audit mode's duplicate-score detector, which flags near-impossible
coincidences (byte-identical scores across different JDs) rather than trying
to verify judgment quality directly.

Usage:
    python scripts/verify_submission.py data/submissions/{company}
    python scripts/verify_submission.py data/submissions/{c1} data/submissions/{c2} ...
    python scripts/verify_submission.py --audit data/submissions/{company} [...]
        Reads each folder's draft_manifest.json (must already exist -- run
        this in --audit mode AFTER the rubric_score has been filled in, not
        instead of the plain mode above), checks its rubric_score against a
        running cross-session history log so templating is caught even when
        companies are drafted one at a time across separate sessions, not
        just when several are checked together in one invocation.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _SCRIPT_DIR)  # so this runs regardless of invocation cwd

import submission_linter  # noqa: E402
import quality_checker  # noqa: E402
import approved_metrics  # noqa: E402

HISTORY_PATH = os.path.join(_REPO_ROOT, "data", ".rubric_score_history.json")


def _load_candidate_keywords() -> set:
    prefs_path = os.path.join(_REPO_ROOT, "data", "candidate_preferences.json")
    try:
        with open(prefs_path, encoding="utf-8") as f:
            prefs = json.load(f)
    except OSError:
        return set()
    kws = set(k.lower() for k in prefs.get("jd_required_keywords", []))
    kws |= set(k.lower() for k in prefs.get("signal_keywords", []))
    return kws


def _keyword_coverage(jd_text: str, resume_text: str, keywords: set) -> dict | None:
    jd_lower = jd_text.lower()
    resume_lower = resume_text.lower()
    jd_present = {k for k in keywords if k in jd_lower}
    if not jd_present:
        return None
    covered = {k for k in jd_present if k in resume_lower}
    return {
        "jd_keywords_present": sorted(jd_present),
        "covered_in_resume": sorted(covered),
        "coverage_pct": round(100 * len(covered) / len(jd_present), 1),
    }


def _pdf_page_count(pdf_path: str):
    if not os.path.exists(pdf_path):
        return None
    try:
        out = subprocess.run(["pdfinfo", pdf_path], capture_output=True, text=True, timeout=15)
        for line in out.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split(":", 1)[1].strip())
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"
    return None


def verify_one(folder: str) -> dict:
    folder = folder.rstrip("/\\")
    company = os.path.basename(folder)
    resume_md = os.path.join(folder, "Resume.md")
    cover_md = os.path.join(folder, "CoverLetter.md")
    jd_path = os.path.join(folder, "Original_JD.txt")

    receipt: dict = {"submission": company, "generated_by": "scripts/verify_submission.py"}

    # Full-folder lint -- both documents plus the resume/cover-letter pair
    # checks (LW-008-PAIR, LW-009-PAIR). Calling lint_document() on a single
    # file and saving that as "the" lint result is exactly what dropped the
    # resume side silently before; lint_folder() is the only call that covers
    # everything the pipeline actually requires.
    lint_results = submission_linter.lint_folder(folder)
    receipt["lint"] = [
        {
            "document": r["document"],
            "doc_type": r["doc_type"],
            "status": r["status"],
            "blocks": [{"rule_id": v.rule_id, "message": v.message} for v in r["result"].blocks],
            "warns": [{"rule_id": v.rule_id, "message": v.message} for v in r["result"].warns],
            "infos": [{"rule_id": v.rule_id, "message": v.message} for v in r["result"].infos],
        }
        for r in lint_results
    ]
    receipt["lint_all_clean"] = all(len(r["blocks"]) == 0 for r in receipt["lint"])

    if os.path.exists(resume_md):
        try:
            ok, msg = quality_checker.check_resume(resume_md)
        except Exception as e:  # noqa: BLE001 -- check_resume raises on hard fail, doesn't return
            ok, msg = False, str(e)
        receipt["check_resume"] = {"passed": ok, "message": msg}
    else:
        receipt["check_resume"] = {"passed": False, "message": "Resume.md not found"}

    if os.path.exists(cover_md):
        try:
            ok, msg = quality_checker.check_and_repair_cover_letter(cover_md)
        except Exception as e:  # noqa: BLE001
            ok, msg = False, str(e)
        receipt["check_cover_letter"] = {"passed": ok, "message": msg}
    else:
        receipt["check_cover_letter"] = {"passed": False, "message": "CoverLetter.md not found"}

    unapproved = {}
    for name, path in [("Resume.md", resume_md), ("CoverLetter.md", cover_md)]:
        if os.path.exists(path):
            text = open(path, encoding="utf-8").read()
            unapproved[name] = approved_metrics.find_unapproved_metrics(text)
    receipt["unapproved_metrics"] = unapproved
    receipt["unapproved_metrics_clean"] = all(len(v) == 0 for v in unapproved.values())

    receipt["page_counts"] = {
        "Resume.pdf": _pdf_page_count(os.path.join(folder, "Resume.pdf")),
        "CoverLetter.pdf": _pdf_page_count(os.path.join(folder, "CoverLetter.pdf")),
    }
    receipt["page_counts_ok"] = (
        receipt["page_counts"]["Resume.pdf"] == 1 and receipt["page_counts"]["CoverLetter.pdf"] == 1
    )

    # A real, computed number -- not a substitute for genuine rubric judgment
    # (R2 in conversion_rubric.md still needs a human/LLM read), but a floor
    # that can't be templated identically across different JDs the way a
    # hand-typed rubric_score can.
    if os.path.exists(jd_path) and os.path.exists(resume_md):
        jd_text = open(jd_path, encoding="utf-8").read()
        resume_text = open(resume_md, encoding="utf-8").read()
        receipt["jd_keyword_coverage"] = _keyword_coverage(jd_text, resume_text, _load_candidate_keywords())
    else:
        receipt["jd_keyword_coverage"] = None

    receipt["rubric_score"] = (
        "NOT SCORED BY THIS SCRIPT -- score by hand against data/conversion_rubric.md, "
        "one evidence citation (a specific sentence or bullet) per criterion, and write "
        "the result into draft_manifest.json. Then run this script again with --audit "
        "before telling Jason the submission is verified."
    )

    receipt["mechanically_verified"] = (
        receipt["lint_all_clean"]
        and receipt["check_resume"]["passed"]
        and receipt["check_cover_letter"]["passed"]
        and receipt["unapproved_metrics_clean"]
        and receipt["page_counts_ok"]
    )

    return receipt


def _load_history() -> dict:
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _save_history(history: dict) -> None:
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def audit_rubric_scores(folders: list[str]) -> list[str]:
    """Cross-session duplicate-score tripwire. Real per-document rubric
    scoring essentially never produces byte-identical sub-scores across
    different JDs -- if it does, that's evidence of templating, not
    coincidence. Checked against a persistent log so this catches
    companies drafted one at a time across separate sessions, not only
    ones checked together in one batch."""
    history = _load_history()
    warnings: list[str] = []

    for folder in folders:
        folder = folder.rstrip("/\\")
        company = os.path.basename(folder)
        manifest_path = os.path.join(folder, "draft_manifest.json")
        if not os.path.exists(manifest_path):
            warnings.append(f"{company}: no draft_manifest.json found -- nothing to audit.")
            continue
        try:
            manifest = json.load(open(manifest_path, encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            warnings.append(f"{company}: could not read draft_manifest.json ({e}).")
            continue

        score = manifest.get("rubric_score")
        if not score or not isinstance(score, dict):
            warnings.append(f"{company}: rubric_score missing or not a real score object.")
            continue

        key = json.dumps(score, sort_keys=True)
        prior = history.get(key)
        if prior and prior != company:
            warnings.append(
                f"{company}: rubric_score is BYTE-IDENTICAL to {prior}'s. "
                f"Almost certainly templated, not genuine per-document scoring. Re-score both for real."
            )
        history[key] = company

    _save_history(history)
    return warnings


def main() -> None:
    args = sys.argv[1:]
    audit_mode = "--audit" in args
    folders = [a for a in args if a != "--audit"]

    if not folders:
        print(__doc__)
        sys.exit(1)

    if audit_mode:
        warnings = audit_rubric_scores(folders)
        if warnings:
            print("*** RUBRIC SCORE AUDIT - issues found ***")
            for w in warnings:
                print(f"  - {w}")
            sys.exit(1)
        print(f"Rubric score audit clean for: {', '.join(os.path.basename(f.rstrip('/\\')) for f in folders)}")
        return

    for folder in folders:
        receipt = verify_one(folder)
        out_path = os.path.join(folder.rstrip("/\\"), "verification_receipt.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(receipt, f, indent=2)
        status = "MECHANICALLY CLEAN" if receipt["mechanically_verified"] else "FAILED -- see verification_receipt.json"
        print(f"{receipt['submission']}: {status} (rubric_score still needs manual entry + --audit pass)")


if __name__ == "__main__":
    main()
