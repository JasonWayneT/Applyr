"""
Handoff-contract validation for the generate-submission process's canonical artifacts.

Why this exists (2026-08-06): every stage in this pipeline already writes a JSON artifact for
the next stage to read (stage0_fit_gate.json -> draft_manifest.json -> verification_receipt.json),
but nothing has ever actually validated those files' shape before trusting them. Every existing
read (in verify_submission.py, finalize_submission_job.py) is a plain `.get()` with a silent
fallback to None or empty -- a malformed or missing artifact doesn't block anything, it just
produces a quieter wrong answer downstream. That's the exact failure mode a handoff contract is
supposed to prevent: a stage should refuse to proceed on a bad upstream artifact, not improvise
around it. See the SESSION conversation this came out of (2026-08-06) for the fuller reasoning --
short version: prose instructions to "run the verification steps" have failed silently three
times in this project's history (case-sensitivity bug, dropped resume lint, byte-identical
rubric scores); the fix each time was a mechanical artifact the process can't improvise past.
This module is that same fix applied one layer earlier -- at the artifact handoffs themselves,
not just the final verification gate.

Two kinds of check per artifact:
  1. Structural -- required keys present, right type, non-empty where that matters.
  2. Freshness (verification_receipt.json only) -- is it newer than the documents it claims to
     have verified? A receipt older than Resume.md/CoverLetter.md means the documents changed
     after the last real verification pass -- stale, not passing.

This module does NOT decide whether every stage has run yet -- see check_submission_status.py
for that (it computes overall done/not-done from the filesystem, independent of any agent's
self-report, and uses these functions as its building blocks).

Usage:
    python scripts/contracts.py data/submissions/{company} [...]
        Runs every check that applies to whichever of the three artifacts exist in each folder.
        A file that doesn't exist yet (e.g. draft_manifest.json before Stage 2 has run) is not
        itself a failure here -- this is a shape/freshness check on what IS present, not a
        "has every stage run" check. Exits 1 if any EXISTING artifact fails its contract.

Also importable:
    check_stage0_fit_gate(folder) -> (ok, errors)
    check_draft_manifest(folder) -> (ok, errors)
    check_verification_receipt(folder) -> (ok, errors)
    check_freshness(folder) -> (ok, errors)
    check_finalize_ready(folder) -> (ok, errors)   # the combined gate finalize_submission_job.py uses
    check_stage1_ready(folder) -> (ok, errors)     # CR-075 Epic 3: Stage 1 exit / Stage 2 entry gate
    check_stage2_ready(folder) -> (ok, errors)     # CR-075 Epic 3: Stage 2 completion gate
    check_workflow_complete(folder) -> (ok, errors)  # CR-076: authoritative DONE oracle
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_json(path: str) -> tuple[dict | None, str | None]:
    """Returns (data, error). error is None on success."""
    if not os.path.exists(path):
        return None, f"{os.path.basename(path)} not found"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return None, f"{os.path.basename(path)} could not be read/parsed: {e}"
    if not isinstance(data, dict):
        return None, f"{os.path.basename(path)} is not a JSON object"
    return data, None


# ---------------------------------------------------------------------------
# stage0_fit_gate.json
# ---------------------------------------------------------------------------

_STAGE0_REQUIRED_LIST_KEYS = ["required", "preferred", "responsibilities", "flagged_gaps"]


def check_stage0_fit_gate(folder: str) -> tuple[bool, list[str]]:
    """Per SKILL.md Stage 0 step 5: 'required list, preferred list, responsibilities list,
    flagged gaps, stage signal, thin-JD flag' -- persisted as this file. Stage 1 depends on
    all of these existing, not just required/preferred (the responsibilities list was silently
    missing from every real file for a while before that was caught -- see SKILL.md Stage 0
    step 5's own history note)."""
    path = os.path.join(folder, "stage0_fit_gate.json")
    data, err = load_json(path)
    if err:
        return False, [err]

    errors: list[str] = []
    if not data.get("company"):
        errors.append("stage0_fit_gate.json: missing or empty 'company'")
    for key in _STAGE0_REQUIRED_LIST_KEYS:
        val = data.get(key)
        if not isinstance(val, list):
            errors.append(f"stage0_fit_gate.json: '{key}' must be a list (got {type(val).__name__})")
    if not data.get("stage_signal"):
        errors.append("stage0_fit_gate.json: missing or empty 'stage_signal' (use 'unknown' if the JD doesn't state one -- never omit the key)")
    if "thin_jd" not in data or not isinstance(data.get("thin_jd"), bool):
        errors.append("stage0_fit_gate.json: 'thin_jd' must be present and a real boolean")

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# draft_manifest.json
# ---------------------------------------------------------------------------

def _check_rubric_score_shape(score) -> list[str]:
    errors = []
    if not isinstance(score, dict):
        return ["'rubric_score' must be an object with 'resume' and 'cover_letter' sub-scores"]
    for side in ("resume", "cover_letter"):
        sub = score.get(side)
        if not isinstance(sub, dict) or not isinstance(sub.get("total"), (int, float)):
            errors.append(f"'rubric_score.{side}.total' must be a real number -- a genuinely scored document always has one")
    return errors


def check_draft_manifest(folder: str) -> tuple[bool, list[str]]:
    """Per SKILL.md Stage 3: 'draft_manifest.json with verification_passed/rubric_score
    populated (same field shape the old draft_compiler.py wrote)'."""
    path = os.path.join(folder, "draft_manifest.json")
    data, err = load_json(path)
    if err:
        return False, [err]

    errors: list[str] = []
    if not data.get("company"):
        errors.append("draft_manifest.json: missing or empty 'company'")
    if not data.get("title"):
        errors.append("draft_manifest.json: missing or empty 'title'")
    else:
        try:
            from seniority_gate import is_implausible_job_title
            if is_implausible_job_title(str(data.get("title") or "")):
                errors.append(
                    "draft_manifest.json: 'title' looks like JD chrome "
                    f"({data.get('title')!r}), not a real role name"
                )
        except Exception:
            pass
    if "verification_passed" not in data or not isinstance(data.get("verification_passed"), bool):
        errors.append("draft_manifest.json: 'verification_passed' must be present and a real boolean")
    errors.extend(f"draft_manifest.json: {e}" for e in _check_rubric_score_shape(data.get("rubric_score")))

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# verification_receipt.json
# ---------------------------------------------------------------------------

_RECEIPT_BOOL_KEYS = [
    "mechanically_verified",
    "lint_all_clean",
    "unapproved_metrics_clean",
    "page_counts_ok",
]


def check_verification_receipt(folder: str) -> tuple[bool, list[str]]:
    """Structural check AND a pass/fail check -- a receipt that parses fine but reports
    mechanically_verified=False is not a satisfied contract for anything downstream. Callers
    that only care about shape (not about whether it passed) should read the file directly."""
    path = os.path.join(folder, "verification_receipt.json")
    data, err = load_json(path)
    if err:
        return False, [err]

    errors: list[str] = []
    if not data.get("submission"):
        errors.append("verification_receipt.json: missing or empty 'submission'")
    for key in _RECEIPT_BOOL_KEYS:
        if key not in data or not isinstance(data.get(key), bool):
            errors.append(f"verification_receipt.json: '{key}' must be present and a real boolean")
    for key in ("check_resume", "check_cover_letter"):
        sub = data.get(key)
        if not isinstance(sub, dict) or "passed" not in sub:
            errors.append(f"verification_receipt.json: '{key}.passed' missing")

    if errors:
        return False, errors

    if data.get("mechanically_verified") is not True:
        return False, ["verification_receipt.json: mechanically_verified is False -- re-run scripts/verify_submission.py and fix what it flags, this is not a passing receipt"]

    return True, []


def _sha256_hex(path: str) -> str | None:
    """sha256 of a file's raw bytes, or None if the file doesn't exist. Mirrors
    verify_submission.py's own _sha256_hex -- not imported from there to keep this module a
    dependency-free predicate library (see the module docstring's "pure predicate library" note),
    but the digest must match byte-for-byte or hash comparisons against a real receipt would
    never agree."""
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def check_freshness(folder: str) -> tuple[bool, list[str]]:
    """Is verification_receipt.json newer than the documents it claims to have verified? An
    edit made after the last real verification pass leaves a stale receipt on disk that still
    reads as passing -- this is the mtime-based version of the artifact-lineage problem (a
    downstream artifact silently referencing a stale upstream one).

    CR-075 Epic 2 Story 2.3: when the receipt carries a `content_hashes` field (written by
    verify_submission.py since Story 2.2), that signal is strictly stronger than mtime -- mtime
    is fooled both ways: a `touch`/checkout can bump a document's mtime with no content change
    (would misread as stale), and an edit can land without ever moving the mtime forward past the
    receipt's own mtime (would misread as fresh). The mtime comparison below still runs first,
    for every document, exactly as before -- it stays as a cheap pre-check, not deleted. When a
    stored hash exists for a given document, the hash comparison is authoritative for that
    document's verdict and overrides whatever the mtime pre-check alone would have said. Legacy
    receipts with no `content_hashes` field (everything written before Story 2.2) fall back to
    exactly today's mtime-only behavior, per this CR's "legacy receipts keep mtime semantics"
    decision -- unchanged."""
    receipt_path = os.path.join(folder, "verification_receipt.json")
    if not os.path.exists(receipt_path):
        return False, ["verification_receipt.json not found -- nothing to check freshness against"]
    receipt_mtime = os.path.getmtime(receipt_path)

    content_hashes = None
    try:
        with open(receipt_path, encoding="utf-8") as f:
            receipt_data = json.load(f)
        if isinstance(receipt_data, dict):
            ch = receipt_data.get("content_hashes")
            if isinstance(ch, dict):
                content_hashes = ch
    except (OSError, json.JSONDecodeError):
        content_hashes = None  # malformed receipt -- fall back to mtime-only behavior below

    errors: list[str] = []
    for doc in ("Resume.md", "CoverLetter.md"):
        doc_path = os.path.join(folder, doc)
        if not os.path.exists(doc_path):
            continue
        mtime_stale = os.path.getmtime(doc_path) > receipt_mtime  # cheap pre-check, kept as-is

        stored_hash = content_hashes.get(doc) if content_hashes else None
        if stored_hash:
            if _sha256_hex(doc_path) != stored_hash:
                errors.append(
                    f"{doc} content does not match the hash recorded in verification_receipt.json "
                    f"-- stale receipt (edited since last verification), re-run scripts/verify_submission.py"
                )
            # else: hash matches -- fresh, regardless of what the mtime pre-check said (a touch
            # or checkout can bump mtime without changing content; the hash is the real signal).
            continue

        # No stored hash for this document (legacy receipt, or the doc didn't exist when the
        # receipt was written) -- fall back to the original mtime-only check.
        if mtime_stale:
            errors.append(
                f"{doc} was edited after verification_receipt.json was generated -- stale receipt, "
                f"re-run scripts/verify_submission.py"
            )

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Combined finalize gate
# ---------------------------------------------------------------------------

def check_finalize_ready(folder: str) -> tuple[bool, list[str]]:
    """The gate finalize_submission_job.py enforces before it will write to the DB: a passing,
    fresh verification receipt AND a draft_manifest.json that says verification_passed."""
    errors: list[str] = []

    _, errs = check_verification_receipt(folder)
    errors.extend(errs)

    _, errs = check_freshness(folder)
    errors.extend(errs)

    _, errs = check_draft_manifest(folder)
    errors.extend(errs)
    manifest_path = os.path.join(folder, "draft_manifest.json")
    manifest, _ = load_json(manifest_path)
    if manifest is not None and manifest.get("verification_passed") is not True:
        errors.append("draft_manifest.json: verification_passed is not True")

    gate_path = os.path.join(folder, "stage0_fit_gate.json")
    if os.path.exists(gate_path):
        gate, _ = load_json(gate_path)
        if gate is not None:
            role = str(gate.get("role") or gate.get("role_title") or "").strip()
            try:
                from seniority_gate import is_implausible_job_title
                if role and is_implausible_job_title(role):
                    errors.append(
                        "stage0_fit_gate.json: 'role' looks like JD chrome "
                        f"({role!r}) — fix extraction / set the real title before finalize"
                    )
            except Exception:
                pass

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Stage 1 exit / Stage 2 entry gate (CR-075 Epic 3, Story 3.1)
# ---------------------------------------------------------------------------

def check_stage1_ready(folder: str) -> tuple[bool, list[str]]:
    """Is Stage 1 (authoring) actually done for this folder? Per CR-075's Decision item 2,
    this is the Stage 1 *exit* condition, enforced at `author_from_packet.py --verify-only`
    (its real position in the flow -- Stage 1 exit / Stage 2 entry). Requires:
      - authoring_packet.json present with packet_status == "ready" (CR-074's five fail-closed
        conditions -- content-safety gates, not staleness ones; see the epics doc's OQ-1
        resolution for why this has no --force override anywhere in this CR).
      - Resume.md, CoverLetter.md, and claim_provenance.json all present in the folder
        (Stage 1's actual promised output -- see CR-092 below for why the third file is
        checked here now).

    Does NOT check packet freshness/version (author_from_packet.py's own _check_packet_ready
    already owns that, with its own --force), and does NOT read verification_receipt.json or
    draft_manifest.json -- those are Stage 2's concern (check_stage2_ready), not Stage 1's.

    CR-092 (2026-08-15): claim_provenance.json used to be checked only conditionally
    downstream (workflow/runner.py reads it "if os.path.exists(...)") and its *content*
    findings are correctly WARN-tier by design (AC9) -- but the file's mere *existence*
    had no gate at all. Stage 1 is a human/agent pasting authoring_prompt.md into a fresh
    session and saving three promised fenced-code-block outputs to three files; nothing
    mechanically enforced the third file actually landed, so a run could advance past
    Stage 1 with only two of three files present and no signal that anything was missed.
    Confirmed real on 2 of 4 real submissions in one batch (mercury_insurance, mckesson)
    the same day this was found. Adding it here converts "silently missing" into "Stage 1
    won't report ready until the human notices and re-runs the author session or
    `author_from_packet.py --verify-only`" -- the same fail-closed posture already used
    for Resume.md/CoverLetter.md, not a new one. This is an existence check only; content
    validity (unknown/disabled claim IDs) stays WARN-tier via check_claim_provenance(),
    not promoted to a hard gate here -- that would be a different, larger change than the
    silent-missing-file bug this fixes."""
    errors: list[str] = []

    packet_path = os.path.join(folder, "authoring_packet.json")
    packet, err = load_json(packet_path)
    if err:
        errors.append(err)
    else:
        status = packet.get("packet_status")
        if status != "ready":
            reasons = packet.get("incomplete_reasons")
            if isinstance(reasons, list) and reasons:
                for reason in reasons:
                    errors.append(f"authoring_packet.json: packet_status is '{status}' -- {reason}")
            else:
                errors.append(
                    f"authoring_packet.json: packet_status is '{status}', expected 'ready' "
                    "(no incomplete_reasons recorded)"
                )

    for doc in ("Resume.md", "CoverLetter.md", "claim_provenance.json"):
        if not os.path.exists(os.path.join(folder, doc)):
            errors.append(f"{doc} not found -- Stage 1 has not produced this document yet")

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Stage 2 completion gate (CR-075 Epic 3, Story 3.2)
# ---------------------------------------------------------------------------

def check_stage2_ready(folder: str) -> tuple[bool, list[str]]:
    """Is Stage 2 (verification) actually done for this folder?

    Composed entirely from existing primitives plus fields verify_submission.py already writes
    (or will write, once Epic 5 lands) into verification_receipt.json -- this function never
    shells out and never re-runs submission_linter.py, claim_provenance.py, or anything else
    itself. That is a locked architecture decision (see the epics doc's "Architecture decisions
    locked in this pass"), for the same reason contracts.py stays a pure predicate library:
    the audit and provenance checks are *run by the producing script and recorded*, this
    function only reads what was recorded.

    Deliberately does NOT require draft_manifest.json's `verification_passed` (that stays
    check_finalize_ready's job, per the locked decision -- requiring it here would be circular
    against AC6's own "audit gates on verification_passed" rule) and does NOT chain
    check_stage1_ready() (chaining would make the many packet-less legacy folders permanently
    un-verifiable, which is blast radius this CR did not ask for).

    Requires:
      - check_verification_receipt() passing (structural + mechanically_verified is True).
      - check_freshness() passing (hash-aware where the receipt has content_hashes, mtime
        fallback otherwise).
      - draft_manifest.json present with a populated rubric_score (reused _check_rubric_score_shape
        shape check -- both resume.total and cover_letter.total must be real numbers).
      - Zero linter HARD_BLOCKs: the receipt's own lint_all_clean AND an explicit per-document
        'blocks' emptiness check (both, not just the derived boolean -- defensive against a
        future receipt where the two disagree).
      - The receipt's recorded rubric_audit result is clean (Story 5.1's field). A receipt
        written before Epic 5 lands has no rubric_audit key at all -- that reads as not-yet-run,
        not a crash, with an error telling the caller to re-run verify_submission.py.
      - The receipt's claim_provenance field is *present* (Story 5.2's field). Presence only --
        its content (ok: true/false, findings) never affects this function's result. That is
        AC9: claim_provenance is a WARN-tier signal for a human to read, not a blocking gate.
        Same "re-run verify_submission.py" treatment when the key is absent (pre-Epic-5 receipt).
    """
    errors: list[str] = []

    ok, errs = check_verification_receipt(folder)
    if not ok:
        errors.extend(errs)

    ok, errs = check_freshness(folder)
    if not ok:
        errors.extend(errs)

    manifest_path = os.path.join(folder, "draft_manifest.json")
    manifest, err = load_json(manifest_path)
    if err:
        errors.append(err)
    else:
        errors.extend(
            f"draft_manifest.json: {e}" for e in _check_rubric_score_shape(manifest.get("rubric_score"))
        )

    # Load the receipt directly (rather than relying on check_verification_receipt()'s internal
    # load) for the additional fields below. If the receipt is missing/unparseable,
    # check_verification_receipt() already reported that above -- skip the rest silently rather
    # than re-reporting the same "not found" a second time.
    receipt_path = os.path.join(folder, "verification_receipt.json")
    receipt, _ = load_json(receipt_path)

    if receipt is not None:
        if receipt.get("lint_all_clean") is not True:
            errors.append(
                "verification_receipt.json: lint_all_clean is not True -- at least one document "
                "has a linter HARD_BLOCK, fix it and re-run scripts/verify_submission.py"
            )
        lint_entries = receipt.get("lint")
        if isinstance(lint_entries, list):
            for entry in lint_entries:
                if not isinstance(entry, dict):
                    continue
                blocks = entry.get("blocks")
                if blocks:
                    doc_name = entry.get("document", "a document")
                    errors.append(
                        f"verification_receipt.json: {doc_name} has {len(blocks)} linter "
                        "HARD_BLOCK(s) recorded -- fix and re-run scripts/verify_submission.py"
                    )
        else:
            errors.append(
                "verification_receipt.json: 'lint' field missing or not a list -- "
                "re-run scripts/verify_submission.py"
            )

        rubric_audit = receipt.get("rubric_audit")
        if not isinstance(rubric_audit, dict):
            errors.append(
                "verification_receipt.json: 'rubric_audit' not found -- re-run "
                "scripts/verify_submission.py (it must run again after rubric_score is entered "
                "into draft_manifest.json so it can perform the duplicate-score audit)"
            )
        elif rubric_audit.get("ran") is not True:
            errors.append(
                "verification_receipt.json: rubric_audit has not run yet -- re-run "
                "scripts/verify_submission.py now that rubric_score is entered"
            )
        elif rubric_audit.get("clean") is not True:
            errors.append(
                "verification_receipt.json: rubric_audit is not clean -- rubric_score may be "
                "templated/duplicated across submissions, re-score for real and re-run "
                "scripts/verify_submission.py"
            )

        if "claim_provenance" not in receipt:
            errors.append(
                "verification_receipt.json: 'claim_provenance' not found -- re-run "
                "scripts/verify_submission.py (presence only is required here; its findings are "
                "WARN-tier and do not block this gate)"
            )

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Workflow authority (CR-076) — single DONE oracle (full COMPLETE in later CRs)
# ---------------------------------------------------------------------------

def check_workflow_complete(folder: str) -> tuple[bool, list[str]]:
    """Authoritative production-complete predicate (CR-076 foundation).

    Production COMPLETE / COMPLETE_WITH_OVERRIDE requires Stage 0-3 receipts that:
      - exist with status COMPLETE and issued_by = run_submission
      - have receipt_id matching the canonical body (anti-forgery)
      - chain via prior_receipt_id (stage N cites stage N-1)
      - match workflow_state.json stage receipt_id pointers
      - have output_hashes that still match on-disk bytes (freshness)

    Mid-states (WAITING_FOR_LLM, SKIPPED, IN_PROGRESS) are reported via errors
    for humans/CLIs; they are not treated as complete.
    """
    errors: list[str] = []
    state_path = os.path.join(folder, "workflow_state.json")
    if not os.path.exists(state_path):
        return False, ["workflow_state.json not found — run scripts/run_submission.py"]

    state, err = load_json(state_path)
    if err:
        return False, [err]
    assert state is not None

    mode = state.get("mode") or "production"
    status = state.get("status")

    if status == "SKIPPED":
        return False, ["workflow SKIPPED (Stage 0 Skip) — not an application complete"]
    if status == "WAITING_FOR_LLM":
        return False, [
            "workflow WAITING_FOR_LLM — paste authoring_prompt.md; Stage 1 not finished"
        ]
    if status == "NEEDS_DISPOSITION":
        return False, [
            "workflow NEEDS_DISPOSITION — dispose Truth/ATS/HM findings then --resume"
        ]
    if status == "PRACTICE_COMPLETE":
        if mode == "practice":
            return False, ["PRACTICE_COMPLETE is not production workflow complete"]
        return False, ["PRACTICE_COMPLETE unexpected in production mode"]
    if status == "FAILED":
        return False, ["workflow FAILED"]
    if status == "STALE":
        return False, ["workflow STALE — reconcile hashes / re-run from earliest stale stage"]
    if status not in ("COMPLETE", "COMPLETE_WITH_OVERRIDE"):
        return False, [
            f"workflow status is {status!r} — production complete requires "
            "COMPLETE or COMPLETE_WITH_OVERRIDE (later CRs)"
        ]

    stage_order = ("stage0", "stage1", "stage2", "stage3")
    receipts: dict[str, dict] = {}
    prior_id: str | None = None
    stages_state = state.get("stages") if isinstance(state.get("stages"), dict) else {}

    for stage in stage_order:
        receipt_path = os.path.join(folder, "stage_receipts", f"{stage}.json")
        if not os.path.exists(receipt_path):
            errors.append(f"stage_receipts/{stage}.json missing")
            prior_id = None  # break chain continuity for later stages
            continue
        receipt, rerr = load_json(receipt_path)
        if rerr:
            errors.append(rerr)
            prior_id = None
            continue
        assert receipt is not None
        receipts[stage] = receipt

        if receipt.get("status") != "COMPLETE":
            errors.append(
                f"{stage} receipt status is {receipt.get('status')!r}, expected COMPLETE"
            )
        if receipt.get("issued_by") != "scripts/run_submission.py":
            errors.append(f"{stage} receipt issued_by is not run_submission (untrusted)")

        # Anti-forgery: receipt_id must be the digest of the canonical body.
        rid = receipt.get("receipt_id")
        body = {k: v for k, v in receipt.items() if k != "receipt_id"}
        canonical = json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        expected_id = (
            f"{stage}:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
        )
        if rid != expected_id:
            errors.append(
                f"{stage} receipt_id does not match receipt body "
                "(forged or corrupted receipt)"
            )

        # Chain: each stage cites the previous stage's receipt_id (stage0 has none).
        expected_prior = prior_id
        got_prior = receipt.get("prior_receipt_id")
        if got_prior != expected_prior:
            errors.append(
                f"{stage} prior_receipt_id is {got_prior!r}, expected {expected_prior!r} "
                "(broken receipt chain)"
            )
        prior_id = rid if isinstance(rid, str) else None

        # State pointer must match the on-disk receipt.
        stage_info = stages_state.get(stage) if isinstance(stages_state.get(stage), dict) else {}
        state_rid = stage_info.get("receipt_id")
        if state_rid != rid:
            errors.append(
                f"{stage} workflow_state receipt_id {state_rid!r} != "
                f"receipt file {rid!r}"
            )

        # Freshness: declared output hashes must still match disk.
        output_hashes = receipt.get("output_hashes") or {}
        if isinstance(output_hashes, dict):
            for rel, want in output_hashes.items():
                if not isinstance(rel, str) or not isinstance(want, str):
                    continue
                path = os.path.join(folder, rel)
                if not os.path.exists(path):
                    errors.append(
                        f"{stage} output {rel} missing (receipt claims hash {want[:12]}...)"
                    )
                    continue
                try:
                    with open(path, "rb") as f:
                        got = hashlib.sha256(f.read()).hexdigest()
                except OSError as e:
                    errors.append(f"{stage} output {rel} unreadable: {e}")
                    continue
                if got != want:
                    errors.append(
                        f"{stage} output {rel} hash mismatch (stale vs receipt)"
                    )

    if mode != "production" and status == "COMPLETE":
        errors.append("production COMPLETE requires mode=production")

    return len(errors) == 0, errors


def main() -> None:
    folders = sys.argv[1:]
    if not folders:
        print(__doc__)
        sys.exit(1)

    any_failed = False
    for folder in folders:
        folder = folder.rstrip("/\\")
        company = os.path.basename(folder)
        print(f"\n{company}:")

        checks = [
            ("stage0_fit_gate.json", check_stage0_fit_gate, "stage0_fit_gate.json"),
            ("draft_manifest.json", check_draft_manifest, "draft_manifest.json"),
            ("verification_receipt.json", check_verification_receipt, "verification_receipt.json"),
        ]
        for label, fn, filename in checks:
            if not os.path.exists(os.path.join(folder, filename)):
                print(f"  [SKIP] {label} -- not present yet")
                continue
            ok, errors = fn(folder)
            if ok:
                print(f"  [PASS] {label}")
            else:
                any_failed = True
                print(f"  [FAIL] {label}")
                for e in errors:
                    print(f"         - {e}")

        if os.path.exists(os.path.join(folder, "verification_receipt.json")):
            ok, errors = check_freshness(folder)
            if ok:
                print("  [PASS] freshness (receipt newer than Resume.md/CoverLetter.md)")
            else:
                any_failed = True
                print("  [FAIL] freshness")
                for e in errors:
                    print(f"         - {e}")

        if os.path.exists(os.path.join(folder, "authoring_packet.json")):
            ok, errors = check_stage1_ready(folder)
            if ok:
                print("  [PASS] check_stage1_ready (Stage 1 exit / Stage 2 entry)")
            else:
                any_failed = True
                print("  [FAIL] check_stage1_ready")
                for e in errors:
                    print(f"         - {e}")
        else:
            print("  [SKIP] check_stage1_ready -- authoring_packet.json not present yet")

        if os.path.exists(os.path.join(folder, "verification_receipt.json")):
            ok, errors = check_stage2_ready(folder)
            if ok:
                print("  [PASS] check_stage2_ready (Stage 2 completion gate)")
            else:
                any_failed = True
                print("  [FAIL] check_stage2_ready")
                for e in errors:
                    print(f"         - {e}")
        else:
            print("  [SKIP] check_stage2_ready -- verification_receipt.json not present yet")

    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
