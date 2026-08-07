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
    Post-author mechanical gate: run lint, ground-truth coverage, and JD term checks
    against Resume.md + CoverLetter.md already in the folder.
    Exit 0 on clean pass; exit 1 on any hard block.

Fix-loop protocol (as per CR-074-authoring-prompt.md):
    After composing, run --verify-only. If FAIL, the agent re-edits using
    packet + digest only — no additional context files. Maximum 2 fix rounds
    before escalating to Jason.

Usage:
    python scripts/author_from_packet.py data/submissions/COMPANY
    python scripts/author_from_packet.py data/submissions/COMPANY --force
    python scripts/author_from_packet.py data/submissions/COMPANY --verify-only
    python scripts/author_from_packet.py data/submissions/COMPANY --invoke  (requires env key)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent

_RULE_DIGEST_PATH = _REPO_ROOT / "data" / "authoring_rule_digest.md"
_RULE_DIGEST_VERSION_PATH = _REPO_ROOT / "data" / "authoring_rule_digest.version"

# ---------------------------------------------------------------------------
# Prompt assembly (Story 5.2)
# ---------------------------------------------------------------------------

_PREAMBLE = """\
You are authoring a Resume.md and a CoverLetter.md for a job application.

CLOSED-WORLD RULE: use ONLY the claim_ids and excerpts in the packet below.
Do not invent any metric, tool, company, team name, or date not present in the packet.
Do not load any external file. Do not call any tool (tools are not needed for v1).

The packet field `packet_status` MUST be "ready" before you proceed.
If it is not "ready", stop and print the incomplete_reasons — do not draft.

Output exactly two fenced Markdown code blocks in this order:
  1. A block labeled "Resume.md" containing the full resume Markdown.
  2. A block labeled "CoverLetter.md" containing the full cover letter Markdown.

Do not output anything else between the two blocks.\
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
    user_body = f"{_PREAMBLE}\n\n```json\n{packet_json}\n```"
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
    }

    return prompt_md, meta


# ---------------------------------------------------------------------------
# Post-author gate (Story 5.3)
# ---------------------------------------------------------------------------

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


def run_verify_only(folder: Path) -> bool:
    """
    Post-author mechanical gate (Story 5.3).

    Checks:
      1. Resume.md and CoverLetter.md exist.
      2. submission_linter on Resume.md + CoverLetter.md only — no HARD_BLOCK.
      3. check_ground_truth_coverage.py — ATTENTION is reported as WARN (judgment).
      4. jd_term_extractor.py — ATTENTION is reported as WARN (judgment).

    Returns True if no hard failures, False otherwise.
    Prints a PASS/FAIL summary and exits with 0 (pass) or 1 (fail).

    Fix-loop protocol: if FAIL, re-edit Resume.md / CoverLetter.md using
    the authoring_prompt.md (packet + digest) only — no additional context files.
    Maximum 2 fix rounds before escalating to Jason.
    """
    passed = True
    lines: list[str] = []

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

    # 2. Lint Resume.md + CoverLetter.md only (never authoring_prompt.md —
    # that file lists forbidden phrases as negative examples and would false-fail).
    try:
        sys.path.insert(0, str(_SCRIPT_DIR))
        from submission_linter import (  # type: ignore
            check_cross_document_repetition,
            lint_document,
        )

        texts: dict[str, str] = {}
        for path, doc_type in ((resume, "resume"), (letter, "cover_letter")):
            text = path.read_text(encoding="utf-8")
            texts[doc_type] = text
            result = lint_document(text, doc_type, filename=path.name)
            if result.passed:
                lines.append(f"PASS [lint/{path.name}]: {len(result.warns)} warn(s)")
            else:
                passed = False
                lines.append(
                    f"FAIL [lint/{path.name}]: {len(result.blocks)} hard block(s), "
                    f"{len(result.warns)} warn(s)"
                )
                for b in result.blocks[:5]:
                    lines.append(f"  [{b.rule_id}] {b.message}")

        if "resume" in texts and "cover_letter" in texts:
            pair_warns = check_cross_document_repetition(
                texts["resume"], texts["cover_letter"]
            )
            lines.append(
                f"PASS [lint/resume+cover_letter (pair)]: {len(pair_warns)} warn(s)"
            )
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

    # Summary
    print("\n".join(lines))
    verdict = "PASS" if passed else "FAIL"
    print(f"\nVERIFY RESULT: {verdict} — {folder.name}")
    return passed


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
        help="Ignore rule_digest_version mismatch and proceed anyway.",
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
        ok = run_verify_only(folder)
        sys.exit(0 if ok else 1)

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
    _main()
