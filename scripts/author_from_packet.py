#!/usr/bin/env python3
"""
author_from_packet.py — CR-074 Epic 5, Stories 5.2 + 5.3.
# Implements FR-254

Assembles a paste-ready authoring_prompt.md from a ready authoring_packet.json
and the lean rule digest (data/authoring_rule_digest.md), so a human can paste
both into a fresh Cursor/Claude session to compose Resume.md + CoverLetter.md.

Default mode (--prompt-only / no flags):
    Load authoring_packet.json + digest from the target folder.
    Fail with exit 1 if:
      - authoring_packet.json is missing
      - packet_status != "ready"
      - rule_digest_version in packet doesn't match current digest (unless --force)
    Write authoring_prompt.md + authoring_prompt_meta.json into the folder.
    Print: PROMPT_READY — {company} — ~{tokens} input — paste authoring_prompt.md into a fresh agent

Verify mode (--verify-only):
    First enforces Stage 1 exit (CR-075): authoring_packet.json with packet_status=ready
    plus Resume.md and CoverLetter.md must exist -- no --force override for this gate.
    Then runs apply_resume_header.py (deterministic PII/header/education patch — packet
    intentionally has no name/contact fields), then the post-author mechanical gate: lint,
    ground-truth coverage, and JD term checks against those documents.
    Exit 0 on clean pass; exit 1 on Stage 1 gate failure or any hard block.

Fix-loop protocol (as per CR-074-authoring-prompt.md):
    After composing, run --verify-only. If FAIL, the agent re-edits using
    packet + digest only — no additional context files. Maximum 2 fix rounds
    before escalating to Jason.

Usage:
    # Prefer the orchestrator for normal progression/completion:
    #   python scripts/run_submission.py data/submissions/COMPANY [--resume|--finalize]
    # This script remains a debug/worker CLI the orchestrator calls:
    python scripts/author_from_packet.py data/submissions/COMPANY
    python scripts/author_from_packet.py data/submissions/COMPANY --force
    python scripts/author_from_packet.py data/submissions/COMPANY --verify-only
    python scripts/author_from_packet.py data/submissions/COMPANY --invoke  (requires env key)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent

sys.path.insert(0, str(_SCRIPT_DIR))
import contracts  # noqa: E402
import stage_gate  # noqa: E402
from authoring_defect_categories import category_for_rule  # noqa: E402
from authoring_examples import format_learned_examples  # noqa: E402
from packet_evidence_utilization import rank_packet_evidence  # noqa: E402
from stage_gate import StageGateForceError  # noqa: E402

_RULE_DIGEST_PATH = _REPO_ROOT / "data" / "authoring_rule_digest.md"
_RULE_DIGEST_VERSION_PATH = _REPO_ROOT / "data" / "authoring_rule_digest.version"

# ---------------------------------------------------------------------------
# Prompt assembly (Story 5.2)
# ---------------------------------------------------------------------------

_PREAMBLE = """\
You are authoring a Resume.md and a CoverLetter.md for a job application.

CLOSED-WORLD RULE: use ONLY the claim_ids, excerpts, and claim_constraints in the packet below.
Excerpts are retrieved workExperience.md (or aiProjects.md) spans, not catalog text.
Do not invent any metric, tool, company, team name, or date not present in the packet.
Do not load any external file. Do not call any tool (tools are not needed for v1).
Obey claim_constraints: never round CONTRIBUTED into OWNED; never use a Prohibited line as a story.

FIXED CHROME: Do not invent name, contact, education, role titles, dates,
locations, the greeting, or the sign-off. Write the Professional Summary,
optional Core Competencies, experience bullets, and cover-letter body.
Keep `## PROFESSIONAL SUMMARY`, optional `## CORE COMPETENCIES`,
`## PROFESSIONAL EXPERIENCE`, `## EDUCATION`, and three `###` role markers
in order (Cision, Sterkly, Zero To Sixty). A later injector overwrites
header, role headings, location lines, education, greeting, and sign-off
from workExperience.md.

The packet field `packet_status` MUST be "ready" before you proceed.
If it is not "ready", stop and print the incomplete_reasons — do not draft.

`jd_buckets` below only lists culture/values items (not tied to specific evidence).
Required, preferred, and responsibility JD items appear in `evidence_map` together with
their claim_ids — there is no separate list of them elsewhere in this packet.

BULLET PRIORITIZATION: The resume must fit on exactly one page. Prioritize the
strongest, most JD-relevant evidence over completeness. Within each role section,
order bullets by JD-relevance: claims mapping to `required` evidence_map items come
before `preferred` or `responsibilities`. When a bullet carries a hard metric, put
the number near the verb, not trailing at the end of a long clause. Bullet counts:
most recent role (Cision) 5-6 bullets; earlier roles (Sterkly, Zero To Sixty) 2-3
bullets each. If there are more high-priority claims than available bullet slots,
prefer claims mapping to `required` items over `preferred` items. When a JD item
has two mapped claim_ids, use the stronger one (higher attribution tier: OWNED
beats CONTRIBUTED) in the resume bullet; the second can support a cover-letter
proof point for the same JD item if the letter benefits from it. Some excerpt cards
may be present to satisfy the 3-role resume rule but may not map to any JD item.
Use these only if a role section needs a bullet and no JD-mapped claim is available
for that employer. Do not force a low-relevance claim into a bullet over a
higher-relevance claim from the same employer.

COVER LETTER SHAPE: Build the letter around 1-2 strongest stories. Choose each
because it covers several of the role's top requirements at once, not one story
per requirement. Tell them with context the resume bullets cannot carry. Never
restate resume bullets. Optionally one plain sentence bridging a soft gap.
Never list requirements. No T-letter format. A forwarded unused high-priority
claim goes in only if it is one of those strongest stories.

COVER LETTER VOICE: end the letter on the last concrete fact. Do not add a recap
kicker that labels the paragraph ("That's genuine...", "That's how I treated...",
"lives or dies on"). Do not use negative listing ("Not X. A Y.").
Never print "closed-lost". Say lost subscriptions or lost subscription opportunities.
Never claim a design team. Jason has not worked with design.
Never open by calling the role interesting, compelling, or exciting; name the
concrete company action, product, or operating problem instead.
GEOGRAPHY: mention countries, team locations, time zones, or "global/distributed"
only when Original_JD.txt asks for global, international, distributed,
cross-timezone, or multi-region work. Otherwise describe the collaboration
itself (who, what was aligned, what shipped).

Output exactly three fenced code blocks in this order:
  1. A block labeled "Resume.md" containing the full resume Markdown.
  2. A block labeled "CoverLetter.md" containing the full cover letter Markdown.
  3. A block labeled "claim_provenance.json" containing a JSON object that records, for every
     resume bullet and factual cover-letter sentence you just drafted, which packet claim_ids
     you used to back it. You
     are already choosing this evidence from the packet's evidence_map as you write each
     bullet — this block just records the choice you already made, it is not new work. Exact
     schema:
       {
         "company": "<packet's company>",
         "resume_claims": [
          {"bullet": "<full exact bullet text>", "claim_ids": ["ACC-104", "MET-10"]},
           ...
         ],
         "cover_letter_claims": [
          {"sentence": "<full exact factual sentence>", "claim_ids": ["ACC-117"]},
           ...
         ]
       }
     Use only claim_ids present in the packet below. Every resume bullet and every cover
     factual letter sentence needs at least one claim_id. Company/JD observations and the
     professional closing do not need claim_ids. Do not combine several sentences into one row.

Write each block to its own file in this submission folder, named exactly after the block's
label: Resume.md, CoverLetter.md, and claim_provenance.json.

Do not output anything else between the three blocks.\
"""


def _load_current_digest_version(
    version_path: Path | None = None,
    digest_path: Path | None = None,
) -> str:
    """Return the current rule_digest_version from disk, mirroring build_authoring_packet logic."""
    import hashlib

    vp = version_path or _RULE_DIGEST_VERSION_PATH
    dp = digest_path or _RULE_DIGEST_PATH

    if vp.exists():
        v = vp.read_text(encoding="utf-8").strip()
        if v:
            return v

    if dp.exists():
        content = dp.read_text(encoding="utf-8")
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    return ""


def _load_digest_text(digest_path: Path | None = None) -> str:
    dp = digest_path or _RULE_DIGEST_PATH
    if not dp.exists():
        raise FileNotFoundError(f"Rule digest not found at {dp}")
    return dp.read_text(encoding="utf-8")


def _load_packet(folder: Path) -> dict:
    p = folder / "authoring_packet.json"
    if not p.exists():
        raise FileNotFoundError(
            f"authoring_packet.json not found in {folder}. "
            "Run: python scripts/build_authoring_packet.py <folder>"
        )
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"authoring_packet.json is not valid JSON: {exc}") from exc


def _check_packet_ready(
    packet: dict,
    force: bool = False,
    digest_version_path: Path | None = None,
    digest_path: Path | None = None,
) -> None:
    """Raise ValueError with a clear message if the packet cannot be used for authoring."""
    status = packet.get("packet_status", "incomplete")
    if status != "ready":
        reasons = packet.get("incomplete_reasons") or ["(no reasons listed)"]
        reasons_text = "\n  ".join(reasons)
        raise ValueError(
            f"Packet status is '{status}' — cannot author.\n"
            f"Incomplete reasons:\n  {reasons_text}"
        )

    current_version = _load_current_digest_version(digest_version_path, digest_path)
    packet_version = packet.get("rule_digest_version", "")

    if current_version and packet_version != current_version:
        if not force:
            raise ValueError(
                f"rule_digest_version mismatch: packet was built with '{packet_version}', "
                f"current digest is '{current_version}'.\n"
                "Rebuild the packet (python scripts/build_authoring_packet.py <folder>) "
                "or re-run with --force to override."
            )
        print(
            f"WARNING: rule_digest_version mismatch (packet={packet_version}, "
            f"current={current_version}). Continuing because --force was passed.",
            file=sys.stderr,
        )

    current_bank = _example_bank_version()
    packet_bank = packet.get("example_bank_version") or ""
    if current_bank and packet_bank and packet_bank != current_bank:
        # CR-097 Story 3.6: the bank is advisory few-shot content. A packet
        # built one bank version ago is still correct — warn, never raise,
        # and do not extend the digest's hard-fail to cover it.
        print(
            f"WARNING: example_bank_version mismatch (packet={packet_bank}, "
            f"current={current_bank}). Authoring anyway; rebuild the packet "
            "to pick up the latest examples.",
            file=sys.stderr,
        )


def build_authoring_prompt(
    folder: Path,
    force: bool = False,
    digest_path: Path | None = None,
    digest_version_path: Path | None = None,
) -> tuple[str, dict]:
    """Build the prompt markdown string and metadata dict.

    Returns (prompt_markdown, meta_dict).
    Raises FileNotFoundError or ValueError if the packet is missing or not ready.
    """
    packet = _load_packet(folder)
    _check_packet_ready(packet, force=force, digest_version_path=digest_version_path, digest_path=digest_path)

    digest_text = _load_digest_text(digest_path)

    # Token estimates (chars / 4 approximation, consistent with packet builder)
    system_tokens = len(digest_text.encode("utf-8")) // 4
    packet_json = json.dumps(packet, indent=2, ensure_ascii=False)
    examples_block = format_learned_examples(packet.get("learned_examples") or [])
    utilization = rank_packet_evidence(packet)
    priority_claims = [
        row["claim_id"]
        for row in utilization["claims"]
        if row["high_priority"]
    ]
    priority_instruction = ""
    if priority_claims:
        priority_instruction = (
            "\n\nEVIDENCE PRIORITY: These packet claims each support multiple "
            "important JD items: "
            + ", ".join(priority_claims)
            + ". Do not force every one into the resume. For each required JD item, "
            "use the strongest mapped claim as the lead bullet in the matching role. "
            "Unused high-priority claims are forwarded for the letter and Stage 2. "
            "A forwarded claim belongs in the letter only if it is one of the 1-2 "
            "strongest stories."
        )
    ats_terms = [
        row["term"]
        for row in packet.get("ats_term_contract") or []
        if isinstance(row, dict) and isinstance(row.get("term"), str) and row["term"].strip()
    ]
    ats_instruction = ""
    if ats_terms:
        ats_instruction = (
            "\n\nATS TERM CONTRACT: Use each of these exact, packet-supported JD terms "
            "naturally in Resume.md and keep the supporting claim in "
            "claim_provenance.json: " + ", ".join(ats_terms) + "."
        )
    user_body = f"{_PREAMBLE}{priority_instruction}{ats_instruction}\n\n```json\n{packet_json}\n```"
    if examples_block:
        user_body = f"{user_body}\n\n{examples_block}"
    user_tokens = len(user_body.encode("utf-8")) // 4
    total_tokens = system_tokens + user_tokens

    prompt_md = (
        "<!-- CR-074 authoring prompt — generated by author_from_packet.py -->\n"
        "<!-- Paste SYSTEM BLOCK into the system-prompt field of a fresh agent. -->\n"
        "<!-- Paste USER BLOCK into the first user message.                     -->\n"
        "\n"
        "---\n"
        "## SYSTEM BLOCK (paste into System Prompt / system message)\n"
        "---\n\n"
        f"{digest_text}\n"
        "\n"
        "---\n"
        "## USER BLOCK (paste into the first user message)\n"
        "---\n\n"
        f"{user_body}\n"
    )

    meta: dict = {
        "company": packet.get("company", ""),
        "role_title": packet.get("role_title", ""),
        "slug": packet.get("slug", ""),
        "rule_digest_version": packet.get("rule_digest_version", ""),
        "packet_estimated_tokens": packet.get("estimated_tokens", 0),
        "system_tokens": system_tokens,
        "user_tokens": user_tokens,
        "total_estimated_tokens": total_tokens,
        "example_bank_version": packet.get("example_bank_version") or "",
    }

    return prompt_md, meta


# ---------------------------------------------------------------------------
# Post-author gate (Story 5.3)
# ---------------------------------------------------------------------------

def _apply_resume_header_if_available(folder: Path) -> str:
    """Deterministic PII/header/education patch (Cluster C item 11).

    Packet intentionally omits name/contact/location/education/dates so cloud
    authoring never receives real PII. Placeholders left by closed-world compose
    are substituted from workExperience.md via apply_resume_header.py before lint.
    Synthetic mode skips this patch so tests never ingest live WE.
    """
    if os.environ.get("APPLYR_SYNTHETIC_IDENTITY") == "1":
        return "SKIP [apply_resume_header] — synthetic identity mode"

    try:
        from apply_resume_header import load_real_header, patch_file  # type: ignore
    except Exception as exc:
        return (
            "FAIL [identity] - workExperience.md missing or malformed; "
            "set APPLYR_SYNTHETIC_IDENTITY=1 for test/eval mode, "
            "or copy workExperience.md into this worktree "
            f"(identity_source=missing); import failed: {exc}"
        )

    try:
        header = load_real_header()
    except Exception:
        return (
            "FAIL [identity] - workExperience.md missing or malformed; "
            "set APPLYR_SYNTHETIC_IDENTITY=1 for test/eval mode, "
            "or copy workExperience.md into this worktree "
            "(identity_source=missing)"
        )

    parts: list[str] = []
    for fname in ("Resume.md", "CoverLetter.md"):
        path = folder / fname
        if not path.exists():
            continue
        result = patch_file(str(path), header)
        parts.append(f"{fname}: {result}")
    if not parts:
        return "SKIP [apply_resume_header] — no Resume.md/CoverLetter.md"
    return "PASS [apply_resume_header]: " + "; ".join(parts)


def _run_subprocess_check(script: str, folder: Path) -> tuple[bool, str]:
    """Run a script against folder; return (passed, summary_line).

    Coverage/term scripts exit 1 on ATTENTION (judgment signal). Callers that
    want WARN-not-FAIL for that case should inspect the returned summary.
    """
    script_path = _SCRIPT_DIR / script
    if not script_path.exists():
        return True, f"SKIP [{script}] — script not found"
    result = subprocess.run(
        [sys.executable, str(script_path), str(folder)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if result.returncode != 0:
        detail = stdout or stderr
        if "ATTENTION" in detail:
            # First line of stdout is usually the ATTENTION summary.
            head = detail.splitlines()[0] if detail else "ATTENTION"
            return False, f"WARN [{script}] — {head}"
        summary = f"FAIL [{script}] — exit {result.returncode}"
        if detail:
            summary += f": {detail[:200]}"
        return False, summary
    return True, f"PASS [{script}]" + (f": {stdout[:120]}" if stdout else "")


def _sha256_file(path: Path) -> str:
    """Return sha256 hex of *path*'s bytes, or '' if the file is missing."""
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _example_bank_version() -> str:
    """Current authoring-example bank version, or '' until Epic 3 ships the module."""
    try:
        from authoring_examples import bank_version  # type: ignore
    except ImportError:
        return ""
    try:
        return bank_version() or ""
    except Exception:
        return ""


def _offending_excerpt(text: str, line: int | None) -> str:
    if not line:
        return ""
    rows = text.splitlines()
    if 1 <= int(line) <= len(rows):
        return rows[int(line) - 1].strip()[:240]
    return ""


def _format_lint_item(kind: str, filename: str, item: object, text: str) -> str:
    line = getattr(item, "line", None)
    rule_id = str(getattr(item, "rule_id", "") or "")
    message = str(getattr(item, "message", "") or "")
    suggestion = str(getattr(item, "suggestion", "") or "").strip()
    excerpt = _offending_excerpt(text, line)
    line_bit = f" line {line}" if line else ""
    out = f"{kind} [lint/{filename}] [{rule_id}]{line_bit}: {message}"
    if suggestion:
        out += f" (suggestion: {suggestion})"
    if excerpt:
        out += f" offending: {excerpt}"
    return out


def _violation_row(violation: object, doc: str) -> dict:
    """Project a lint violation into the verify_history schema (CR-097 Story 1.2)."""
    rule_id = str(getattr(violation, "rule_id", "") or "")
    return {
        "rule_id": rule_id,
        "severity": str(getattr(violation, "severity", "") or ""),
        "doc": doc,
        "line": getattr(violation, "line", None),
        "category": category_for_rule(rule_id),
    }


def _record_verify_attempt(
    folder: Path,
    *,
    passed: bool,
    violations: list[dict],
) -> None:
    """Append one verify_history.json entry (CR-097 1.2/1.4)."""
    dest_dir = folder / "stage1_first_draft"
    dest_dir.mkdir(parents=True, exist_ok=True)
    history_path = dest_dir / "verify_history.json"

    resume = folder / "Resume.md"
    letter = folder / "CoverLetter.md"
    resume_sha = _sha256_file(resume)
    cover_sha = _sha256_file(letter)

    existing: list = []
    if history_path.exists():
        try:
            loaded = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = loaded
        except (OSError, json.JSONDecodeError):
            existing = []

    for entry in existing:
        if (
            entry.get("resume_sha256") == resume_sha
            and entry.get("cover_sha256") == cover_sha
        ):
            return

    existing.append(
        {
            "attempt": len(existing) + 1,
            "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "passed": passed,
            "resume_sha256": resume_sha,
            "cover_sha256": cover_sha,
            "rule_digest_version": _load_current_digest_version(),
            "example_bank_version": _example_bank_version(),
            "violations": violations,
        }
    )
    history_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _snapshot_author_output(folder: Path) -> None:
    """Copy author artifacts before verifier mutation so repair can read them."""
    dest = folder / "stage1_author_output"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("Resume.md", "CoverLetter.md", "claim_provenance.json"):
        src = folder / name
        if src.exists():
            shutil.copy2(src, dest / name)


def _snapshot_first_draft(source: Path, record_to: Path) -> None:
    """Keep the untouched author output before verification edits it."""
    dest = record_to / "stage1_first_draft"
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("Resume.md", "CoverLetter.md"):
        snapshot = dest / name
        if not snapshot.exists():
            shutil.copy2(source / name, snapshot)


def run_verify_only(folder: Path, *, record_to: Path | None = None) -> bool:
    """
    Post-author mechanical gate (Story 5.3).

    Checks:
      1. Resume.md and CoverLetter.md exist.
      2. submission_linter on Resume.md + CoverLetter.md only — no HARD_BLOCK.
      3. check_ground_truth_coverage.py — ATTENTION is reported as WARN (judgment).
      4. jd_term_extractor.py — ATTENTION is reported as WARN (judgment).

    Returns True if no hard failures, False otherwise.
    Prints a PASS/FAIL summary.

    When *record_to* is set (CR-097 Story 1.2), append a structured entry to
    ``{record_to}/stage1_first_draft/verify_history.json``. Existing callers
    keep today's signature and bool return. Append is idempotent on the
    (resume_sha256, cover_sha256) pair. On the first recorded attempt only,
    copy the untouched Resume.md and CoverLetter.md into that directory
    before deterministic verification edits (write-once).

    Always copies Resume.md / CoverLetter.md / claim_provenance.json into
    ``{folder}/stage1_author_output/`` before header injection or quality
    repair, so a Stage 1 repair pass can consume the author's bytes.

    Fix-loop protocol: if FAIL, run build_stage1_repair_prompt.py and paste
    that prompt into a fresh Agy session. Loop until verify passes or a round
    makes no progress. Do not load workExperience.md, claims, AGENTS.md, or
    the context pack.
    """
    passed = True
    lines: list[str] = []
    violations: list[dict] = []

    try:
        # 1. File existence
        resume = folder / "Resume.md"
        letter = folder / "CoverLetter.md"
        missing = [f for f in [resume, letter] if not f.exists()]
        if missing:
            for m in missing:
                lines.append(f"FAIL: {m.name} not found in {folder}")
            passed = False

        if not passed:
            print("\n".join(lines))
            print("\nVERIFY RESULT: FAIL")
            return False

        # A repair map of bullet text to claim id is the same cites. Store them
        # as resume_claims before the snapshot, or every bullet looks uncited.
        # Implements FR-265.
        from run_stage1_repair import heal_provenance_file

        heal_provenance_file(folder)

        if record_to is not None:
            _snapshot_first_draft(folder, record_to)
        _snapshot_author_output(folder)

        # 1b. Deterministic header/education/title/date substitution (PII stays out of packet).
        header_line = _apply_resume_header_if_available(folder)
        lines.append(header_line)
        if header_line.startswith("FAIL"):
            passed = False
            print("\n".join(lines))
            print("\nVERIFY RESULT: FAIL")
            return False

        # Implements FR-265: Stage 1 owns deterministic document quality.
        # These checks used to
        # run only in Stage 2, which let overlong bullets and missing professional
        # closing transitions survive the first draft.
        try:
            sys.path.insert(0, str(_SCRIPT_DIR))
            from quality_checker import (  # type: ignore
                check_and_repair_cover_letter,
                check_resume,
            )

            resume_ok, resume_message = check_resume(str(resume))
            letter_ok, letter_message = check_and_repair_cover_letter(str(letter))
            if resume_ok and letter_ok:
                lines.append("PASS [stage1_quality]: resume and cover-letter structure")
            else:
                passed = False
                lines.append(
                    "FAIL [stage1_quality]: "
                    f"resume={resume_message}; cover_letter={letter_message}"
                )
        except Exception as exc:
            passed = False
            lines.append(f"FAIL [stage1_quality]: {exc}")

        # 2. Lint Resume.md + CoverLetter.md only (never authoring_prompt.md —
        # that file lists forbidden phrases as negative examples and would false-fail).
        try:
            sys.path.insert(0, str(_SCRIPT_DIR))
            from submission_linter import (  # type: ignore
                check_cross_document_repetition,
                check_customer_discovery,
                check_jd_specificity_floor,
                check_unsolicited_geography,
                lint_document,
            )

            texts: dict[str, str] = {}
            for path, doc_type in ((resume, "resume"), (letter, "cover_letter")):
                text = path.read_text(encoding="utf-8")
                texts[doc_type] = text
                result = lint_document(text, doc_type, filename=path.name)
                for item in (*result.blocks, *result.warns):
                    violations.append(_violation_row(item, doc_type))
                if result.passed:
                    lines.append(f"PASS [lint/{path.name}]: {len(result.warns)} warn(s)")
                else:
                    passed = False
                    lines.append(
                        f"FAIL [lint/{path.name}]: {len(result.blocks)} hard block(s), "
                        f"{len(result.warns)} warn(s)"
                    )
                    for b in result.blocks:
                        lines.append(_format_lint_item("FAIL", path.name, b, text))
                    for w in result.warns[:8]:
                        lines.append(_format_lint_item("WARN", path.name, w, text))

            discovery_blocks = check_customer_discovery(
                texts.get("resume", ""),
                texts.get("cover_letter", ""),
            )
            if discovery_blocks:
                # LR-039 is a false experience claim. Stage 2 used to be the
                # first place it blocked, which parked the queue. Repair it
                # here. Implements FR-370.
                passed = False
                lines.append(
                    "FAIL [lint/customer discovery]: "
                    f"{len(discovery_blocks)} hard block(s)"
                )
                for block in discovery_blocks:
                    lines.append(f"  FAIL LR-039: {block.message}")

            if "resume" in texts and "cover_letter" in texts:
                pair_warns = check_cross_document_repetition(
                    texts["resume"], texts["cover_letter"]
                )
                for item in pair_warns:
                    violations.append(_violation_row(item, "resume+cover_letter"))
                if pair_warns:
                    # LW-009-PAIR is a WARN. Failing Stage 1 here sends the
                    # draft into repair, which can drop citations. Stage 2
                    # still sees the finding. Implements FR-375.
                    lines.append(
                        "WARN [lint/resume+cover_letter (pair)]: "
                        f"{len(pair_warns)} substantive repeated phrase(s)"
                    )
                else:
                    lines.append("PASS [lint/resume+cover_letter (pair)]: 0 warn(s)")

                jd_path = folder / "Original_JD.txt"
                jd_text = jd_path.read_text(encoding="utf-8") if jd_path.exists() else ""
                company_name = folder.name
                thin_jd = False
                gate_path = folder / "stage0_fit_gate.json"
                if gate_path.exists():
                    try:
                        gate_data = json.loads(gate_path.read_text(encoding="utf-8"))
                        company_name = str(gate_data.get("company") or company_name)
                        thin_jd = bool(gate_data.get("thin_jd", False))
                    except (OSError, json.JSONDecodeError):
                        pass
                specificity_warns = check_jd_specificity_floor(
                    texts["cover_letter"], jd_text, company_name=company_name, thin_jd=thin_jd
                )
                for item in specificity_warns:
                    violations.append(_violation_row(item, "cover_letter"))
                if specificity_warns:
                    passed = False
                    lines.append(
                        "FAIL [lint/LW-026 specificity]: cover letter does not meet "
                        "the packet-specific JD detail floor"
                    )
                else:
                    lines.append("PASS [lint/LW-026 specificity]")

                geo_any = False
                for path, doc_type in ((resume, "resume"), (letter, "cover_letter")):
                    geo_warns = check_unsolicited_geography(
                        texts[doc_type], jd_text, doc_type
                    )
                    for item in geo_warns:
                        violations.append(_violation_row(item, doc_type))
                    if geo_warns:
                        geo_any = True
                        passed = False
                        lines.append(
                            f"FAIL [lint/LW-039 geography]: {path.name} names "
                            "geography the JD never asked for"
                        )
                        for w in geo_warns:
                            lines.append(
                                _format_lint_item("WARN", path.name, w, texts[doc_type])
                            )
                if not geo_any:
                    lines.append("PASS [lint/LW-039 geography]")

                from submission_linter import (
                    _load_folder_provenance,
                    collect_fidelity_hard_blocks,
                )

                # These hard blocks used to appear first in the hiring-manager
                # pass. That pass cannot repair, so an unsupervised run stops.
                # Stage 1 repair is the retry. Implements FR-386.
                fidelity_blocks = collect_fidelity_hard_blocks(
                    texts.get("resume", ""),
                    texts.get("cover_letter", ""),
                    _load_folder_provenance(folder),
                )
                if fidelity_blocks:
                    passed = False
                    lines.append(
                        "FAIL [lint/span fidelity]: "
                        f"{len(fidelity_blocks)} hard block(s)"
                    )
                    for block in fidelity_blocks:
                        lines.append(f"FAIL [{block.rule_id}]: {block.message}")
                        violations.append(_violation_row(block, "submission"))
                else:
                    lines.append("PASS [lint/span fidelity]")
        except ImportError:
            lines.append("SKIP [lint] — submission_linter not importable; run manually")
        except Exception as exc:
            lines.append(f"SKIP [lint] — unexpected error: {exc}")

        # 3–4. Coverage / term scripts: ATTENTION exits 1 by design (judgment required),
        # so treat ATTENTION as WARN and only fail on true script errors.
        for script in ("check_ground_truth_coverage.py", "jd_term_extractor.py"):
            ok, summary = _run_subprocess_check(script, folder)
            if ok or summary.startswith("WARN"):
                lines.append(summary)
            else:
                passed = False
                lines.append(summary)

        # 5. Round 4 optimization bar — soft_gap + required evidence_map claim_ids
        # must appear in claim_provenance.json (fail-closed; coverage ATTENTION stays WARN).
        opt_ok, opt_lines = _check_optimization_bar_provenance(folder)
        lines.extend(opt_lines)
        if not opt_ok:
            passed = False

        utilization_ok, utilization_lines = _check_packet_evidence_utilization(folder)
        lines.extend(utilization_lines)
        if not utilization_ok:
            passed = False

        ats_ok, ats_lines = _check_packet_ats_term_contract(folder)
        lines.extend(ats_lines)
        if not ats_ok:
            passed = False

        sentence_ok, sentence_lines = _check_sentence_level_provenance(folder)
        lines.extend(sentence_lines)
        if not sentence_ok:
            passed = False

        extra_ok, extra_lines = _check_extra_packet_provenance(folder)
        lines.extend(extra_lines)
        if not extra_ok:
            passed = False

        # Summary
        print("\n".join(lines))
        verdict = "PASS" if passed else "FAIL"
        print(f"\nVERIFY RESULT: {verdict} — {folder.name}")
        return passed
    finally:
        if record_to is not None:
            _record_verify_attempt(
                record_to, passed=passed, violations=violations
            )


def _check_extra_packet_provenance(folder: Path) -> tuple[bool, list[str]]:
    """CR-112 Story 3.1: FAIL when provenance cites IDs the packet never offered.

    Exact ID match only. Prefix overlap (ACC-101-SAVINGS vs ACC-101-PM) does
    not clear. Detection only: does not rank, recover, or rewrite.
    Implements FR-312. Recovery is Story 3.6.
    """
    from packet_closed_world import extra_packet_findings

    packet_path = folder / "authoring_packet.json"
    prov_path = folder / "claim_provenance.json"
    unreadable = (
        "FAIL [extra_packet]: packet or provenance missing or unreadable. "
        "recovery_state=CLOSED_WORLD_UNREADABLE extra_ids=unknown. "
        "Stage 1 incomplete until a readable authoring_packet.json and "
        "claim_provenance.json exist. Detection only. Story 3.6 recovery "
        "cannot run yet. Do not dispose as ACCEPTED_AS_CORRECT, "
        "FALSE_POSITIVE, NOT_APPLICABLE, or HUMAN_ACCEPTED_RISK."
    )
    if not packet_path.exists() or not prov_path.exists():
        return False, [unreadable]
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        provenance = json.loads(prov_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, [unreadable]
    if not isinstance(packet, dict) or not isinstance(provenance, dict):
        return False, [unreadable]
    findings = extra_packet_findings(packet, provenance)
    if not findings:
        return True, ["PASS [extra_packet]: no extra-packet provenance IDs"]
    extra_ids = ",".join(row["claim_id"] for row in findings)
    lines = [
        f"FAIL [{row['id']}]: provenance cites {row['claim_id']} which is not "
        "in packet excerpts/evidence_map/soft_gaps (exact match; prefix, sibling "
        "lens, ordinal, substring, and distinctive-tag similarity do not count). "
        f"extra_ids={extra_ids} recovery_state={row['recovery_state']} "
        "next=story36_recovery (remove/rewrite, remove-extra, widen+reauthor, "
        "or qualitative compare). Detection only: no rank, swap, widen, or "
        "rewrite. Do not dispose as ACCEPTED_AS_CORRECT, FALSE_POSITIVE, "
        "NOT_APPLICABLE, or HUMAN_ACCEPTED_RISK."
        for row in findings
    ]
    return False, lines


def _normalize_provenance_unit(text: str) -> str:
    text = re.sub(r"^\s*[*-]\s+", "", text or "")
    return re.sub(r"\s+", " ", text).strip().rstrip(".!?").lower()


def _professional_experience_bullets(resume_text: str) -> list[str]:
    """Return only PROFESSIONAL EXPERIENCE bullet lines.

    Found 2026-09-19 on a fresh healthstream draft: `## CORE COMPETENCIES`
    rendered as a bulleted list ("* Product Strategy & Roadmap Planning")
    rather than the comma-separated inline form other drafts happened to use.
    Nothing in the digest requires either format. The old blanket "any line
    starting with '* '/'- ' in the whole document" extraction treated those
    skill/category labels as factual accomplishment bullets needing a
    citation, which they are not -- they are not claims, the same way an ATS
    skills row isn't. Only PROFESSIONAL EXPERIENCE bullets need sentence-level
    provenance; EDUCATION and PROFESSIONAL SUMMARY use no bullets at all.
    """
    lines = resume_text.splitlines()
    in_experience = False
    bullets: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_experience = stripped[3:].strip().casefold() == "professional experience"
            continue
        if in_experience and stripped.startswith(("* ", "- ")):
            bullets.append(stripped[2:].strip())
    return bullets


def _cover_factual_sentences(text: str) -> list[str]:
    """Return candidate-fact sentences, excluding JD framing and the close."""
    body = (text or "").split("Dear Hiring Manager,", 1)[-1]
    body = re.split(r"\n\s*(?:Best regards|Regards|Sincerely),", body, maxsplit=1)[0]
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", re.sub(r"\n+", " ", body))
        if sentence.strip()
    ]
    factual: list[str] = []
    for sentence in sentences:
        lower = sentence.lower()
        first_person = re.search(r"\bi\b", lower) and not re.search(
            r"\bi would\b|\bi am (?:drawn|interested|applying|glad)\b",
            lower,
        )
        named_history = re.search(r"\b(?:cision|sterkly|zero to sixty)\b", lower)
        experience_claim = re.search(
            r"\bmy (?:experience|background|work|role|record|contribution)\b", lower
        )
        anaphoric_result = re.match(
            r"^(?:that|this|the) (?:work|result(?:ing)?|program|project|analysis|plan)\b",
            lower,
        )
        attributed_outcome = re.match(
            r"^(?:account managers|customers|the (?:platform|product|initiative|"
            r"project|program|result))\b",
            lower,
        )
        if (
            first_person
            or named_history
            or experience_claim
            or anaphoric_result
            or attributed_outcome
        ):
            factual.append(sentence)
    return factual


def _check_sentence_level_provenance(folder: Path) -> tuple[bool, list[str]]:
    """Require FR-265 exact unit-level provenance for packets rebuilt under v2."""
    packet_path = folder / "authoring_packet.json"
    prov_path = folder / "claim_provenance.json"
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True, ["SKIP [sentence_provenance]: packet unavailable"]

    contract = packet.get("provenance_contract") or {}
    version = contract.get("version") if isinstance(contract, dict) else None
    if not isinstance(version, int) or version < 2:
        return True, ["SKIP [sentence_provenance]: legacy packet"]
    try:
        provenance = json.loads(prov_path.read_text(encoding="utf-8"))
        resume_text = (folder / "Resume.md").read_text(encoding="utf-8")
        letter_text = (folder / "CoverLetter.md").read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"FAIL [sentence_provenance]: could not parse inputs: {exc}"]

    def _covered(section: str, field: str) -> set[str]:
        covered: set[str] = set()
        for row in provenance.get(section) or []:
            if not isinstance(row, dict) or not row.get("claim_ids"):
                continue
            value = row.get(field)
            if isinstance(value, str) and value.strip():
                covered.add(_normalize_provenance_unit(value))
        return covered

    resume_units = _professional_experience_bullets(resume_text)
    cover_units = _cover_factual_sentences(letter_text)
    covered_resume = _covered("resume_claims", "bullet")
    covered_cover = _covered("cover_letter_claims", "sentence")

    missing_resume = [
        unit for unit in resume_units
        if _normalize_provenance_unit(unit) not in covered_resume
    ]
    missing_cover = [
        unit for unit in cover_units
        if _normalize_provenance_unit(unit) not in covered_cover
    ]
    if not missing_resume and not missing_cover:
        return True, [
            "PASS [sentence_provenance]: every resume bullet and factual "
            "cover-letter sentence has exact claim coverage"
        ]

    lines = []
    for unit in missing_resume[:5]:
        lines.append(f'FAIL [sentence_provenance/resume]: uncited bullet "{unit}"')
    for unit in missing_cover[:5]:
        lines.append(f'FAIL [sentence_provenance/cover_letter]: uncited factual sentence "{unit}"')
    return False, lines


def _mapping_can_prove(item: str, claim_ids: list[str], excerpts: dict) -> bool:
    """True when a mapped claim shares real wording with the JD line.

    A remote or travel posting term, a limitation claim, and a mapping with
    no distinctive overlap are not proof obligations. Stage 1 must not park a
    draft for leaving those out. Implements FR-381 / FR-375.
    """
    from build_authoring_packet import (  # local: packet builder is heavy
        _distinctive_overlap,
        _force_empty_claim_scoring,
    )

    if _force_empty_claim_scoring(item) is not None:
        return False
    item_words = set(re.findall(r"[a-z]{4,}", (item or "").lower()))
    saw_excerpt = False
    for claim_id in claim_ids:
        if "LIMITATION" in claim_id.upper():
            continue
        excerpt = excerpts.get(claim_id) if isinstance(excerpts, dict) else ""
        if not isinstance(excerpt, str) or not excerpt.strip():
            continue
        saw_excerpt = True
        overlap = _distinctive_overlap(
            item_words,
            set(re.findall(r"[a-z]{4,}", excerpt.lower())),
        )
        if overlap:
            return True
    # No excerpt text means we cannot show the mapping is noise. Keep the cite.
    return not saw_excerpt


def _check_optimization_bar_provenance(folder: Path) -> tuple[bool, list[str]]:
    """Fail when a mapped claim that can prove the line is unused."""
    lines: list[str] = []
    packet_path = folder / "authoring_packet.json"
    prov_path = folder / "claim_provenance.json"
    if not packet_path.exists():
        lines.append("FAIL [optimization_bar]: authoring_packet.json not found")
        return False, lines
    if not prov_path.exists():
        lines.append(
            "FAIL [optimization_bar]: claim_provenance.json not found — every soft_gap "
            "and required evidence_map claim_id must be cited before Stage 1 exit"
        )
        return False, lines

    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        provenance = json.loads(prov_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        lines.append(f"FAIL [optimization_bar]: could not parse packet/provenance: {exc}")
        return False, lines

    cited: set[str] = set()
    for section in ("resume_claims", "cover_letter_claims"):
        for row in provenance.get(section) or []:
            if not isinstance(row, dict):
                continue
            for cid in row.get("claim_ids") or []:
                if isinstance(cid, str) and cid.strip():
                    cited.add(cid.strip())
                    # Also accept base ACC-107 when provenance cites ACC-107-COMPLIANCE
                    base = cid.split("-")
                    if len(base) >= 2:
                        cited.add("-".join(base[:2]) if base[0] in ("ACC", "MET", "VOC") else cid)

    def _id_used(cid: str) -> bool:
        if cid in cited:
            return True
        # packet may use ACC-107-COMPLIANCE while provenance cites ACC-107
        parts = cid.split("-")
        if len(parts) >= 2 and parts[0] in ("ACC", "MET", "VOC"):
            base = f"{parts[0]}-{parts[1]}"
            if base in cited:
                return True
            if any(c.startswith(base) for c in cited):
                return True
        return any(c.startswith(cid) or cid.startswith(c) for c in cited)

    excerpts = packet.get("excerpts") if isinstance(packet.get("excerpts"), dict) else {}
    ok = True
    for sg in packet.get("soft_gaps") or []:
        if not isinstance(sg, dict):
            continue
        if (sg.get("class") or "SOFT") == "HARD":
            continue
        full_item = sg.get("item") or ""
        item = full_item[:80]
        ids = [c for c in (sg.get("claim_ids") or []) if isinstance(c, str) and c.strip()]
        if not ids:
            # extraction_empty / incomplete packet — surface but don't double-fail here
            if "empty buckets" in (sg.get("item") or "").lower():
                continue
            # Packet Rule 7 parity (2026-08-11): empty claim_ids are allowed when an
            # explicit honesty/bridge note is present. The incomplete filler
            # "Soft gap flagged…" is NOT enough — that fails Rule 7 at packet build.
            # Also accept legacy honesty phrases from force-empty evidence bridges.
            note = (sg.get("note") or "").strip()
            note_l = note.lower()
            if note and not note.startswith("Soft gap flagged"):
                continue
            if (
                "named tool not in verified" in note_l
                or "not a skill claim" in note_l
                or "administratively satisfied" in note_l
            ):
                continue
            lines.append(
                f"FAIL [optimization_bar]: soft_gap has no claim_ids — {item}"
            )
            ok = False
            continue
        unused = [c for c in ids if not _id_used(c)]
        # Soft gap passes if at least one mapped claim_id is cited.
        # A mapping that cannot prove the line is left out. FR-381.
        if len(unused) == len(ids) and _mapping_can_prove(full_item, ids, excerpts):
            lines.append(
                f"FAIL [optimization_bar]: soft_gap bridge unused — {item} "
                f"(need one of: {', '.join(ids)})"
            )
            ok = False

    for row in packet.get("evidence_map") or []:
        if not isinstance(row, dict):
            continue
        if row.get("bucket") != "required":
            continue
        ids = [c for c in (row.get("claim_ids") or []) if isinstance(c, str) and c.strip()]
        if not ids:
            continue
        full_item = row.get("jd_item") or ""
        if all(not _id_used(c) for c in ids) and _mapping_can_prove(
            full_item, ids, excerpts
        ):
            item = full_item[:80]
            lines.append(
                f"FAIL [optimization_bar]: required evidence unused — {item} "
                f"(need one of: {', '.join(ids)})"
            )
            ok = False

    if ok:
        lines.append("PASS [optimization_bar]: soft_gap/required claim_ids cited in provenance")
    return ok, lines


def _check_packet_evidence_utilization(folder: Path) -> tuple[bool, list[str]]:
    """Forward unused high-priority claims; do not block Stage 1 or pad the resume."""
    packet_path = folder / "authoring_packet.json"
    prov_path = folder / "claim_provenance.json"
    notes_path = folder / "stage1_forwarded_findings.json"
    if not packet_path.exists() or not prov_path.exists():
        return True, ["SKIP [evidence_utilization]: packet or provenance missing"]
    try:
        report = rank_packet_evidence(
            json.loads(packet_path.read_text(encoding="utf-8")),
            json.loads(prov_path.read_text(encoding="utf-8")),
        )
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"FAIL [evidence_utilization]: could not parse input: {exc}"]

    unused = report["high_priority_unused"]
    payload = {
        "schema": "stage1_forwarded_findings/v1",
        "source": "evidence_utilization",
        "unused_high_priority_claims": unused,
        "high_priority_score": report["high_priority_score"],
        "note": (
            "Do not force these into the resume. The cover letter may use one "
            "only if it is among the 1-2 strongest stories."
        ),
    }
    notes_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if unused:
        return True, [
            "WARN [evidence_utilization]: unused high-priority claims forwarded "
            f"(score >= {report['high_priority_score']}): {', '.join(unused)}"
        ]
    return True, [
        "PASS [evidence_utilization]: all high-priority packet claims are cited"
    ]


def _resume_proof_text(resume_text: str) -> str:
    """Experience bullets. The summary and Core Competencies are not claim rows."""
    parts = re.split(r"(?im)^## professional experience\s*$", resume_text, maxsplit=1)
    if len(parts) == 1:
        return resume_text
    tail = re.split(r"(?im)^## education\s*$", parts[1], maxsplit=1)
    return tail[0]


def _provenance_row_supports_term(provenance: dict, term: str) -> bool:
    """True when a cited resume or letter row already contains the term."""
    from jd_term_extractor import _term_present_stemmed

    needle = term.lower()
    for section, field in (("resume_claims", "bullet"), ("cover_letter_claims", "sentence")):
        for row in provenance.get(section) or []:
            if not isinstance(row, dict):
                continue
            text = str(row.get(field) or "")
            claim_ids = [
                claim_id for claim_id in row.get("claim_ids") or []
                if isinstance(claim_id, str) and claim_id.strip()
            ]
            if text and claim_ids and _term_present_stemmed(needle, text.lower()):
                return True
    return False


def _check_packet_ats_term_contract(folder: Path) -> tuple[bool, list[str]]:
    """Fail when a packet term is in the proof text without a cited row.

    A term only in the summary or Core Competencies is not a proof sentence.
    A term missing from the resume fails only when the contract names no claim.
    A named claim that was left out stays left out. Implements FR-377 / FR-381.
    """
    packet_path = folder / "authoring_packet.json"
    resume_path = folder / "Resume.md"
    provenance_path = folder / "claim_provenance.json"
    if not packet_path.exists() or not resume_path.exists():
        return True, ["SKIP [ats_term_contract]: packet or resume missing"]
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"FAIL [ats_term_contract]: could not parse packet: {exc}"]

    contract = packet.get("ats_term_contract")
    if contract is None:
        return True, ["SKIP [ats_term_contract]: legacy packet has no contract"]
    if contract and not provenance_path.exists():
        return False, ["FAIL [ats_term_contract]: claim_provenance.json missing"]
    try:
        from jd_term_extractor import _term_present_stemmed  # type: ignore
        resume_text = resume_path.read_text(encoding="utf-8").lower()
        provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if contract else {}
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"FAIL [ats_term_contract]: could not read inputs: {exc}"]

    from submission_linter import ats_term_conflicts_with_hard_block

    proof_text = _resume_proof_text(resume_text)
    missing: list[str] = []
    unsupported: list[str] = []
    for row in contract:
        if not isinstance(row, dict) or not isinstance(row.get("term"), str):
            continue
        term = row["term"].strip()
        if not term or ats_term_conflicts_with_hard_block(term):
            continue
        support_ids = [
            claim_id for claim_id in row.get("claim_ids") or []
            if isinstance(claim_id, str) and claim_id.strip()
        ]
        present = _term_present_stemmed(term.lower(), resume_text)
        if not present:
            # No named claim means the contract required the word itself.
            # A named claim that was left out of the draft stays left out.
            if not support_ids:
                missing.append(term)
            continue
        if not _term_present_stemmed(term.lower(), proof_text):
            continue
        if not _provenance_row_supports_term(provenance, term):
            unsupported.append(term)
    if missing:
        return False, [
            "FAIL [ats_term_contract]: packet-supported JD terms missing from Resume.md: "
            + ", ".join(missing)
        ]
    if unsupported:
        return False, [
            "FAIL [ats_term_contract]: terms lack a supporting resume provenance claim: "
            + ", ".join(unsupported)
        ]
    return True, ["PASS [ats_term_contract]: all packet-supported JD terms are in Resume.md"]


def _claim_employers() -> dict[str, str]:
    """Map claim id to employer slug. Empty when the catalog is absent."""
    path = _REPO_ROOT / "data" / "master_claims.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    employers: dict[str, str] = {}
    for claim_id, row in payload.items():
        if isinstance(row, dict):
            employers[str(claim_id)] = str(row.get("employer") or "").strip().lower()
    return employers


def attach_unsupported_ats_cites(
    folder: Path,
    employers: dict[str, str] | None = None,
) -> list[str]:
    """Cite a packet claim on the bullet that already contains an unsupported term.

    Only adds an id whose employer matches a claim already on that bullet.
    Does not add a sentence and does not call a model. Returns the terms it
    attached. Implements FR-377.
    """
    from jd_term_extractor import _term_present_stemmed

    packet_path = folder / "authoring_packet.json"
    provenance_path = folder / "claim_provenance.json"
    if not packet_path.is_file() or not provenance_path.is_file():
        return []
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    contract = packet.get("ats_term_contract") if isinstance(packet, dict) else None
    claims = provenance.get("resume_claims") if isinstance(provenance, dict) else None
    if not isinstance(contract, list) or not isinstance(claims, list):
        return []
    if employers is None:
        employers = _claim_employers()
    attached: list[str] = []
    changed = False
    for row in contract:
        if not isinstance(row, dict) or not isinstance(row.get("term"), str):
            continue
        term = row["term"].strip()
        support_ids = [
            claim_id
            for claim_id in row.get("claim_ids") or []
            if isinstance(claim_id, str) and claim_id.strip()
        ]
        if not term or not support_ids:
            continue
        for entry in claims:
            if not isinstance(entry, dict):
                continue
            bullet = str(entry.get("bullet") or "")
            if not bullet or not _term_present_stemmed(term.lower(), bullet.lower()):
                continue
            current = [
                claim_id
                for claim_id in entry.get("claim_ids") or []
                if isinstance(claim_id, str) and claim_id.strip()
            ]
            current_employers = {
                employers.get(claim_id, "")
                for claim_id in current
                if employers.get(claim_id, "")
            }
            if not current_employers:
                continue
            already = any(
                cited == support
                or cited.startswith(support)
                or support.startswith(cited)
                or "-".join(cited.split("-")[:2]) == "-".join(support.split("-")[:2])
                for support in support_ids
                for cited in current
            )
            if already:
                break
            matches = [
                support
                for support in support_ids
                if employers.get(support, "") in current_employers
            ]
            term_tokens = [
                token
                for token in re.findall(r"[a-z0-9]+", term.lower())
                if len(token) > 3
            ]

            def _overlap(support: str) -> int:
                lowered = support.lower()
                return sum(1 for token in term_tokens if token in lowered)

            overlapped = [support for support in matches if _overlap(support) > 0]
            if overlapped:
                chosen = max(overlapped, key=_overlap)
            elif len(matches) == 1:
                chosen = matches[0]
            else:
                chosen = ""
            if not chosen:
                continue
            entry["claim_ids"] = [*current, chosen]
            attached.append(term)
            changed = True
            break
    if changed:
        provenance_path.write_text(
            json.dumps(provenance, indent=2) + "\n",
            encoding="utf-8",
        )
    return attached


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_folder(raw: str) -> Path:
    p = Path(raw)
    if p.is_dir():
        return p
    for base in (
        _REPO_ROOT / "data" / "submissions",
        _REPO_ROOT / "data" / "context_pack_validation",
    ):
        cand = base / raw
        if cand.is_dir():
            return cand
    return p


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Author-from-packet runner and post-author gate (CR-074 Epic 5).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build prompt for manual paste:
  python scripts/author_from_packet.py data/submissions/limble

  # Build prompt, ignoring digest version mismatch:
  python scripts/author_from_packet.py data/submissions/limble --force

  # Run post-author gate after Resume.md / CoverLetter.md have been written:
  python scripts/author_from_packet.py data/submissions/limble --verify-only
""",
    )
    parser.add_argument("folder", help="Path or slug to a submission folder.")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Run post-author mechanical gate only (no prompt written).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Compose mode: ignore rule_digest_version mismatch. "
            "Verify-only mode (CR-075 Stage 2): with --force-reason, override a failed "
            "Stage 2 gate when a rubric_score is present (AC10). Bare --force alone is "
            "rejected at Stage 2."
        ),
    )
    parser.add_argument(
        "--force-reason",
        default=None,
        help="Required with --force at Stage 2 (--verify-only) when overriding check_stage2_ready.",
    )
    parser.add_argument(
        "--invoke",
        action="store_true",
        help=(
            "Invoke the cloud API directly (requires ANTHROPIC_API_KEY or OPENAI_API_KEY "
            "in environment). Not implemented in v1 — pass to document the intent."
        ),
    )
    args = parser.parse_args()

    folder = _resolve_folder(args.folder)
    if not folder.is_dir():
        print(f"ERROR: '{folder}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    # --verify-only mode
    if args.verify_only:
        # CR-075 Story 4.3 / AC3: Stage 1 exit gate before mechanical checks.
        # No --force override for packet_status (OQ-1) -- call contracts directly,
        # not stage_gate.require_stage_ready, so there is no force path at all.
        stage1_ok, stage1_errors = contracts.check_stage1_ready(str(folder))
        if not stage1_ok:
            print(f"{folder} is not ready for Stage 1 exit / Stage 2 entry:")
            for err in stage1_errors:
                print(f"  - {err}")
            print(
                "Fix the items above (ready authoring_packet.json + Resume.md + "
                "CoverLetter.md). There is no --force override for this gate (AC3)."
            )
            sys.exit(1)
        ok = run_verify_only(folder)

        # CR-075 Story 5.3: same Stage 2 verdict + force policy as verify_submission.py.
        # --verify-only does not rewrite verification_receipt.json; it evaluates whatever
        # receipt is already on disk (or reports INCOMPLETE if none).
        any_failed = not ok
        try:
            gate_failed = stage_gate.apply_stage2_verdict(
                str(folder),
                force=bool(args.force),
                force_reason=args.force_reason,
                argv=sys.argv,
            )
        except StageGateForceError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        if gate_failed:
            any_failed = True
        sys.exit(1 if any_failed else 0)

    # --invoke guard (v1: not implemented)
    if args.invoke:
        has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
        has_openai = bool(os.environ.get("OPENAI_API_KEY"))
        if not (has_anthropic or has_openai):
            print(
                "ERROR: --invoke requires ANTHROPIC_API_KEY or OPENAI_API_KEY in environment.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(
            "ERROR: --invoke API call not implemented in v1. "
            "Paste authoring_prompt.md into a fresh Cursor/Claude session manually.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Prompt packaging mode (default)
    try:
        prompt_md, meta = build_authoring_prompt(folder, force=args.force)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR (unexpected): {exc}", file=sys.stderr)
        sys.exit(1)

    # Write outputs
    prompt_path = folder / "authoring_prompt.md"
    meta_path = folder / "authoring_prompt_meta.json"

    prompt_path.write_text(prompt_md, encoding="utf-8")
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    company = meta.get("company", folder.name)
    total_tokens = meta.get("total_estimated_tokens", 0)
    enc = sys.stdout.encoding or "utf-8"
    msg = (
        f"PROMPT_READY — {company} — ~{total_tokens} input tokens — "
        f"paste {prompt_path.name} into a fresh agent"
    )
    print(msg.encode(enc, errors="replace").decode(enc, errors="replace"))
    sys.exit(0)


if __name__ == "__main__":
    from workflow.entry_warning import warn_worker_cli
    warn_worker_cli("author_from_packet.py")
    _main()
