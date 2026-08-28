"""Stop hook, shared across coding harnesses (2026-08-28, Jason-supplied): don't
let a turn end on an unverified completion claim about a real submission
folder. Wired for Claude Code (.claude/settings.json) and Factory.ai's droid
(.factory/hooks.json) -- confirmed as the tool behind a real repeating
incident. Both platforms' Stop event supports blocking (exit 2 -> stderr sent
back to the agent) with a documented anti-loop field (stop_hook_active).

This is Issue 8 from the Applyr Findings & Fixes report -- every Stage 0-3
completion gate Applyr has (CR-075's contracts.py / stage_gate.py,
scripts/check_submission_status.py) is real and code-enforced once it runs,
but nothing has ever forced it to actually run before an agent tells Jason a
stage is done. This hook closes that gap in-chat, for the harnesses wired
below (see server/submissionFolders.ts's isWorkflowComplete() for the
harness-agnostic version of the same fix, which holds regardless of which
tool touched the files -- that one is the real backstop; this is defense in
depth for catching it in the moment).

Deliberately narrow to avoid false-positive friction on ordinary multi-turn
work (Applyr's own Stage 0-3 flow spans many turns where "not done yet" is
completely normal and already honestly reported):
  1. Only look at data/submissions/ folders with real file activity in the
     last RECENT_WINDOW_MINUTES -- an untouched folder is not this turn's
     concern.
  2. Of those, only escalate a folder that check_submission_status.py itself
     says is NOT done.
  3. Even then, only block if the assistant's own last message contains
     completion-claiming language (see _CLAIM_RE) -- an honest "still
     WAITING_FOR_LLM" report should never be interrupted.
  4. Never re-block the same folder within DEBOUNCE_MINUTES (see
     _recently_debounced), independent of whatever loop-guard the platform
     itself provides -- a defensive second layer, not a substitute for
     stop_hook_active, in case a platform's own guard behaves differently
     than documented.

Two platforms, two ways of getting the assistant's own last words:
  - Claude Code puts it directly in the hook payload (last_assistant_message).
  - Factory's droid does not; it has to be read from the JSONL transcript at
    transcript_path instead (see _read_transcript_last_assistant_text()).
    Defensive by necessity: Factory's transcript line shape was not fully
    confirmed at write time, so this tries several plausible shapes and
    fails open (returns "", never blocks) rather than guess wrong and crash.

Disclosed limitation, same class as the Stage 0 reasoning-consistency check's
own honest limit: this is a keyword match on the final assistant message, not
real language understanding. A claim phrased in genuinely novel wording could
slip past uncaught. Given the failure mode this exists to catch (a flat "it's
done" when the files say otherwise), that's an acceptable gap, not a risk --
a miss here is no worse than today's status quo (a written reminder in
AGENTS.md with nothing enforcing it).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SUBMISSION_DIR = os.path.join(REPO_ROOT, "data", "submissions")
CHECK_SCRIPT = os.path.join(REPO_ROOT, "scripts", "check_submission_status.py")
PYTHON = os.path.join(REPO_ROOT, ".venv", "Scripts", "python.exe")
DEBOUNCE_FILE = os.path.join(REPO_ROOT, "data", ".stop_hook_debounce.json")

RECENT_WINDOW_MINUTES = 20
DEBOUNCE_MINUTES = 5


# 2026-08-28, second revision: the original version below matched bare words
# ("complete", "finished", "clean") anywhere in the message, and fired
# repeatedly during a real Factory Stage 0 batch run -- every "Stage 0 triage
# complete" / "batch gate finished" progress update got misread as a claim
# about a specific submission being ready, even though nobody claimed that.
# Real evidence, not guessed at: two live false-positive-shaped hits
# (allcares_3af2ed54, alphasense) during a real 23-company Stage 0-only
# triage run, both firing on ordinary triage narration. Tightened to require
# the claim to actually be about a submission/resume/cover letter being
# ready, or an explicit Stage 1-3 completion/finalize claim -- Stage 0
# passing is a cheap, frequent, low-stakes event this hook was never meant
# to gate on; the original incident this hook exists for was about
# submission-readiness claims, not triage-step narration.
_CLAIM_RE = re.compile(
    r"\b("
    r"(?:resume|cover\s*letter|submission|application)s?\s+(?:is|are)\s+"
    r"(?:complete|done|ready|verified)|"
    r"verif(?:ied|ication)\s+(?:passed|complete)|"
    r"ready to (?:send|apply|submit)|conversion.ready|"
    r"stage\s*[1-3]\s*(?:is\s*)?(?:complete|done)|"
    r"finaliz(?:e|ed|ing)"
    r")\b",
    re.I,
)


def _recently_touched_folders(window_minutes: int) -> list[str]:
    if not os.path.isdir(SUBMISSION_DIR):
        return []
    cutoff = time.time() - window_minutes * 60
    touched = []
    for name in os.listdir(SUBMISSION_DIR):
        folder = os.path.join(SUBMISSION_DIR, name)
        if not os.path.isdir(folder):
            continue
        try:
            newest = max(
                (os.path.getmtime(os.path.join(folder, f)) for f in os.listdir(folder)),
                default=0,
            )
        except OSError:
            continue
        if newest >= cutoff:
            touched.append(folder)
    return touched


def _is_done(folder: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [PYTHON, CHECK_SCRIPT, folder],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=30,
        )
    except Exception as exc:  # noqa: BLE001 -- never let a hook bug block the agent
        return True, f"(check_submission_status.py could not run: {exc} -- not blocking on a hook failure)"
    return result.returncode == 0, result.stdout.strip()


def _text_from_content(content) -> str:
    """content may be a bare string, or a list of blocks shaped like Anthropic's
    Messages API ({"type": "text", "text": "..."}) -- the shape both Claude
    Code's and (per its docs) Factory's transcripts are built on."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts)
    return ""


def _read_transcript_last_assistant_text(transcript_path: str) -> str:
    """Last assistant message text from a JSONL transcript (Factory's droid --
    its Stop event doesn't include the text directly, unlike Claude Code's).
    Tries a couple of plausible line shapes; returns "" on anything
    unexpected rather than guessing wrong. Reads from the end so one bad
    line elsewhere in a long transcript can't hide the real last message."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return ""
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return ""

    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue

        role = entry.get("role") or entry.get("type") or entry.get("event")
        if role != "assistant" and entry.get("message", {}).get("role") != "assistant":
            continue

        # Claude-Code-style: {"message": {"role": "assistant", "content": [...]}}
        message = entry.get("message")
        if isinstance(message, dict) and "content" in message:
            text = _text_from_content(message["content"])
            if text:
                return text
        # Flatter shape: {"role": "assistant", "content": ...}
        if "content" in entry:
            text = _text_from_content(entry["content"])
            if text:
                return text
        # Last resort: a plain "text" field.
        if isinstance(entry.get("text"), str):
            return entry["text"]

    return ""


def _last_assistant_text(payload: dict) -> str:
    direct = payload.get("last_assistant_message")
    if direct:
        return direct
    return _read_transcript_last_assistant_text(payload.get("transcript_path") or "")


def _load_debounce() -> dict:
    try:
        with open(DEBOUNCE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _recently_debounced(folder_name: str, debounce: dict) -> bool:
    last = debounce.get(folder_name)
    return isinstance(last, (int, float)) and (time.time() - last) < DEBOUNCE_MINUTES * 60


def _mark_debounced(folder_names: list[str], debounce: dict) -> None:
    now = time.time()
    for name in folder_names:
        debounce[name] = now
    try:
        os.makedirs(os.path.dirname(DEBOUNCE_FILE), exist_ok=True)
        with open(DEBOUNCE_FILE, "w", encoding="utf-8") as f:
            json.dump(debounce, f)
    except OSError:
        pass  # best-effort only -- a failed write just means no debounce this run


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:  # noqa: BLE001 -- malformed input must never hang a turn
        sys.exit(0)

    if payload.get("stop_hook_active"):
        sys.exit(0)  # platform's own re-entry guard -- never loop

    last_message = _last_assistant_text(payload)
    if not _CLAIM_RE.search(last_message or ""):
        sys.exit(0)  # no completion claim made -- nothing to hold this turn to

    debounce = _load_debounce()
    problems = []
    for folder in _recently_touched_folders(RECENT_WINDOW_MINUTES):
        name = os.path.basename(folder)
        if _recently_debounced(name, debounce):
            continue
        done, report = _is_done(folder)
        if not done:
            problems.append((name, report))

    if not problems:
        sys.exit(0)

    _mark_debounced([name for name, _ in problems], debounce)

    lines = [
        "This turn's own words claim something is complete/verified/ready, but "
        "scripts/check_submission_status.py disagrees for the folder(s) below. "
        "Run the real command yourself and report its actual output, or correct "
        "the claim to match what the files really say -- do not repeat the claim "
        "as-is.",
        "",
    ]
    for name, report in problems:
        lines.append(f"=== {name} ===")
        lines.append(report)
        lines.append("")
    print("\n".join(lines), file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
