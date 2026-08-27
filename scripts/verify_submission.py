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
    python scripts/verify_submission.py --force --force-reason "..." data/submissions/{company}
        Stage 2 gate override (CR-075 AC10): only when a rubric_score is present
        and check_stage2_ready fails. Bare --force without --force-reason is rejected.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _SCRIPT_DIR)  # so this runs regardless of invocation cwd

import approved_metrics  # noqa: E402
import claim_provenance  # noqa: E402
import contracts  # noqa: E402
import jd_term_extractor  # noqa: E402
import quality_checker  # noqa: E402
import stage_gate  # noqa: E402
import submission_linter  # noqa: E402
from stage_gate import StageGateForceError  # noqa: E402

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


def _check_reading_order(pdf_path: str, md_text: str) -> dict:
    """CR-073 Epic 1 (regression guard): confirm the compiled PDF's `##` section
    headings extract via pdftotext in the same relative order as the source
    Markdown. Investigated 2026-08-04 as a suspected live risk (CORE COMPETENCIES
    rendering as an HTML <table> that could scramble ATS reading order) -- direct
    check against real compiled PDFs found no <table> exists in current output
    (build_skills_section emits bold-label + comma text, not a pipe table), so
    this is not catching a known live defect. It stays in as a cheap standing
    guard in case the dead pipe-table code path in compile_single.py is ever
    reactivated. WARN-only -- does not affect `mechanically_verified`.
    """
    if not os.path.exists(pdf_path):
        return {"checked": False, "reason": "pdf not found"}
    headings = re.findall(r"(?m)^##\s+(.+?)\s*$", md_text)
    if len(headings) < 2:
        return {"checked": False, "reason": "fewer than 2 headings to order-check"}
    try:
        out = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"], capture_output=True, text=True, timeout=15
        )
        extracted = out.stdout.lower()
    except Exception as e:  # noqa: BLE001
        return {"checked": False, "reason": f"pdftotext error: {e}"}
    positions = [(h, extracted.find(h.strip().lower())) for h in headings]
    missing = [h for h, idx in positions if idx == -1]
    found = [(h, idx) for h, idx in positions if idx != -1]
    in_order = all(found[i][1] < found[i + 1][1] for i in range(len(found) - 1))
    return {
        "checked": True,
        "headings_found": [h for h, _ in found],
        "headings_missing": missing,
        "in_order": in_order,
        "ok": in_order and not missing,
    }


def _extract_pdf_text(pdf_path: str) -> tuple[str | None, str | None]:
    """Extract PDF text locally and return text plus an error, if any."""
    if not os.path.exists(pdf_path):
        return None, "pdf not found"
    try:
        out = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:  # noqa: BLE001
        return None, f"pdftotext error: {exc}"
    if out.returncode != 0:
        return None, (out.stderr or "pdftotext failed").strip()
    return out.stdout, None


def _normalise_extracted_field(value: str) -> str:
    """Normalize Markdown field text for conservative PDF substring checks."""
    value = re.sub(r"\*\*|__", "", value)
    value = re.sub(r"`", "", value)
    return re.sub(r"\s+", " ", value).strip().lower()


def _check_pdf_parseability(pdf_path: str, md_text: str, doc_type: str) -> dict:
    """Check required identity, structure, and role fields in extracted PDF text."""
    extracted, error = _extract_pdf_text(pdf_path)
    if error:
        return {"checked": False, "reason": error, "fields": {}, "missing": []}

    extracted_normalized = _normalise_extracted_field(extracted or "")
    fields: dict[str, bool] = {}

    h1 = re.search(r"(?m)^#\s+([^#].*?)\s*$", md_text)
    if h1:
        fields["name"] = _normalise_extracted_field(h1.group(1)) in extracted_normalized
        lines = md_text.splitlines()
        h1_index = next((i for i, line in enumerate(lines) if line == h1.group(0)), -1)
        contact = next(
            (line.strip() for line in lines[h1_index + 1 :] if line.strip()),
            "",
        )
        if contact and not contact.startswith("#"):
            fields["contact"] = _normalise_extracted_field(contact) in extracted_normalized

    for heading in re.findall(r"(?m)^##\s+(.+?)\s*$", md_text):
        fields[f"section:{heading.strip()}"] = (
            _normalise_extracted_field(heading) in extracted_normalized
        )

    if doc_type == "resume":
        for index, match in enumerate(
            re.finditer(r"(?m)^###\s+(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*$", md_text)
        ):
            title, company, dates = match.groups()
            for label, value in (
                ("title", title),
                ("company", company),
                ("dates", dates),
            ):
                fields[f"experience[{index}].{label}"] = (
                    _normalise_extracted_field(value) in extracted_normalized
                )
    else:
        greeting = re.search(r"(?mi)^(dear\s+.+?,?)\s*$", md_text)
        if greeting:
            fields["greeting"] = (
                _normalise_extracted_field(greeting.group(1)) in extracted_normalized
            )
        signoff = re.search(
            r"(?mi)^((?:best|kind|sincerely|respectfully)\s+regards?,?)\s*$",
            md_text,
        )
        if signoff:
            fields["signoff"] = (
                _normalise_extracted_field(signoff.group(1)) in extracted_normalized
            )

    missing = [name for name, present in fields.items() if not present]
    return {
        "checked": True,
        "fields": fields,
        "missing": missing,
        "ok": not missing,
        "extracted_characters": len(extracted or ""),
    }


def _check_packet_ats_contract(folder: str, resume_text: str) -> dict:
    """Report packet-supported ATS terms and whether each appears in the resume."""
    packet_path = os.path.join(folder.rstrip("/\\"), "authoring_packet.json")
    if not os.path.exists(packet_path):
        return {"checked": False, "reason": "authoring_packet.json not found", "terms": []}
    try:
        with open(packet_path, encoding="utf-8") as f:
            packet = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return {"checked": False, "reason": f"packet unreadable: {exc}", "terms": []}

    terms = []
    for entry in packet.get("ats_term_contract") or []:
        if not isinstance(entry, dict) or not entry.get("term"):
            continue
        term = str(entry["term"])
        present = jd_term_extractor._term_present_stemmed(term.lower(), resume_text.lower())
        terms.append(
            {
                "term": term,
                "claim_ids": list(entry.get("claim_ids") or []),
                "jd_items": list(entry.get("jd_items") or []),
                "present_in_resume": present,
            }
        )
    return {
        "checked": True,
        "terms": terms,
        "missing_supported_terms": [
            entry["term"] for entry in terms if not entry["present_in_resume"]
        ],
    }


def _sha256_hex(path: str) -> str | None:
    """sha256 of a file's raw bytes, or None if the file doesn't exist. Hex digest,
    not base64, to match the conventional git/sha256sum representation."""
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


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

    # CR-073 Epic 1 -- WARN-only regression guard, does not affect mechanically_verified.
    if os.path.exists(resume_md):
        receipt["reading_order"] = _check_reading_order(
            os.path.join(folder, "Resume.pdf"), open(resume_md, encoding="utf-8").read()
        )
        resume_text = open(resume_md, encoding="utf-8").read()
        receipt["pdf_parseability"] = {
            "Resume.pdf": _check_pdf_parseability(
                os.path.join(folder, "Resume.pdf"), resume_text, "resume"
            ),
            "CoverLetter.pdf": _check_pdf_parseability(
                os.path.join(folder, "CoverLetter.pdf"),
                open(cover_md, encoding="utf-8").read() if os.path.exists(cover_md) else "",
                "cover_letter",
            ),
        }
        receipt["ats_retrieval"] = _check_packet_ats_contract(folder, resume_text)
    else:
        receipt["reading_order"] = {"checked": False, "reason": "Resume.md not found"}
        receipt["pdf_parseability"] = {}
        receipt["ats_retrieval"] = {
            "checked": False,
            "reason": "Resume.md not found",
            "terms": [],
        }

    # CR-075 Epic 5 Story 5.2 -- WARN-tier: does every drafted claim trace to a real Fact ID?
    # Deliberately NOT folded into mechanically_verified's conjunction below (AC9) -- a
    # provenance gap is something to review, not a hard block on an otherwise-clean submission.
    # Submissions authored after CR-075 Story 5.0 landed carry a real claim_provenance.json; the
    # legacy folders authored before it won't, and will correctly report
    # "claim_provenance.json not found" here -- that is expected, not a bug.
    cp_ok, cp_findings = claim_provenance.check_claim_provenance(folder)
    receipt["claim_provenance"] = {"ran": True, "ok": cp_ok, "findings": cp_findings}

    # A real, computed number -- not a substitute for genuine rubric judgment
    # (R2 in conversion_rubric.md still needs a human/LLM read), but a floor
    # that can't be templated identically across different JDs the way a
    # hand-typed rubric_score can.
    if os.path.exists(jd_path) and os.path.exists(resume_md):
        jd_text = open(jd_path, encoding="utf-8").read()
        resume_text = open(resume_md, encoding="utf-8").read()
        receipt["jd_keyword_coverage"] = _keyword_coverage(jd_text, resume_text, _load_candidate_keywords())
        # CR-073 Epic 2 -- per-JD literal hard-skill/tool coverage, distinct from the
        # generic static-list check above. WARN-level: informational, not a hard gate.
        cover_text = open(cover_md, encoding="utf-8").read() if os.path.exists(cover_md) else ""
        receipt["jd_literal_term_gaps"] = jd_term_extractor.find_jd_term_gaps(jd_text, resume_text, cover_text)
    else:
        receipt["jd_keyword_coverage"] = None
        receipt["jd_literal_term_gaps"] = None

    receipt["rubric_score"] = (
        "NOT SCORED BY THIS SCRIPT -- score by hand against data/conversion_rubric.md, "
        "one evidence citation (a specific sentence or bullet) per criterion, and write "
        "the result into draft_manifest.json. Then run this script again with --audit "
        "before telling Jason the submission is verified."
    )

    # CR-075 Epic 5 Story 5.1 (AC6) -- run the duplicate-score audit inline once a real score
    # exists, instead of relying on a separate --audit invocation actually happening. NOTE:
    # audit_rubric_scores() mutates data/.rubric_score_history.json (appends this company's score
    # fingerprint to the cross-session dedup log used to catch templated scores) -- re-running
    # verify_submission.py for the same company afterward is idempotent (history[key] = company
    # just re-writes the same mapping), so calling this on every verify pass is safe. When no
    # rubric_score has been hand-entered yet, this is the normal mid-flow state, not a failure.
    manifest_path = os.path.join(folder, "draft_manifest.json")
    manifest_rubric_score = None
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest_rubric_score = json.load(f).get("rubric_score")
        except (OSError, json.JSONDecodeError):
            manifest_rubric_score = None

    if manifest_rubric_score and isinstance(manifest_rubric_score, dict):
        audit_findings = audit_rubric_scores([folder])
        receipt["rubric_audit"] = {
            "ran": True,
            "clean": len(audit_findings) == 0,
            "findings": audit_findings,
        }
    else:
        receipt["rubric_audit"] = {"ran": False, "reason": "rubric_score not yet entered"}

    receipt["mechanically_verified"] = (
        receipt["lint_all_clean"]
        and receipt["check_resume"]["passed"]
        and receipt["check_cover_letter"]["passed"]
        and receipt["unapproved_metrics_clean"]
        and receipt["page_counts_ok"]
    )

    # CR-075 Epic 2 Story 2.2 -- proves *which bytes* this receipt verified, so a future
    # hash-comparison change (Story 2.3's check_freshness()) can detect an edit made after
    # verification even if mtime alone would misread it as fresh. Additive only: every key
    # above keeps its existing name, type and position.
    receipt["content_hashes"] = {
        "algorithm": "sha256",
        "Resume.md": _sha256_hex(resume_md),
        "CoverLetter.md": _sha256_hex(cover_md),
    }

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
    raw_args = sys.argv[1:]
    try:
        force, force_reason = stage_gate.parse_force_flags(raw_args)
    except StageGateForceError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    # Strip --force / --force-reason so folder parsing stays hand-rolled (multi-folder + --audit).
    args = stage_gate.strip_force_flags(raw_args)
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

    any_failed = False
    for folder in folders:
        folder = folder.rstrip("/\\")
        receipt = verify_one(folder)
        out_path = os.path.join(folder, "verification_receipt.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(receipt, f, indent=2)
        status = "MECHANICALLY CLEAN" if receipt["mechanically_verified"] else "FAILED -- see verification_receipt.json"
        print(f"{receipt['submission']}: {status} (rubric_score still needs manual entry + --audit pass)")
        if not receipt["mechanically_verified"]:
            any_failed = True

        # CR-075 Story 5.3: Stage 2 completion gate. Receipt must be on disk first so
        # check_stage2_ready can read the fields this pass just wrote (rubric_audit,
        # claim_provenance, content_hashes, lint). Exit non-zero on gate failure only
        # when a rubric_score is present (mid-flow stays informational).
        try:
            gate_failed = stage_gate.apply_stage2_verdict(
                folder,
                force=force,
                force_reason=force_reason,
                argv=sys.argv,
            )
        except StageGateForceError as exc:
            print(str(exc), file=sys.stderr)
            any_failed = True
            continue
        if gate_failed:
            any_failed = True

    # 2026-08-06: this used to return exit code 0 unconditionally, even when a receipt printed
    # FAILED -- the exit code was purely cosmetic and anything checking "did the command
    # succeed" instead of parsing the printed text got a false pass. That's the exact fail-open
    # bug this whole process exists to prevent, just one level lower than where it was already
    # being guarded against. Non-zero here now means what it should: at least one folder did not
    # pass mechanical verification (or a binding Stage 2 gate failed).
    if any_failed:
        sys.exit(1)


if __name__ == "__main__":
    from workflow.entry_warning import warn_worker_cli
    warn_worker_cli("verify_submission.py")
    main()
