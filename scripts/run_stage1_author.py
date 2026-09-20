#!/usr/bin/env python3
"""Single-shot sandboxed Stage 1 fresh-author Agy call.

Reads authoring_prompt.md (SYSTEM digest + USER packet, already combined by
author_from_packet.py) and sends it as one turn to an isolated Agy session,
same sandbox/no-tools contract as run_stage1_repair.py's repair call. Unlike
repair, a fresh author call must produce all three artifacts -- there is no
existing draft to fall back on.

The prompt is sent over stdin as stream-json, not as a --print CLI argument:
a full authoring prompt (digest + packet) runs 40-50KB, and Windows rejects
a command line that long ("Argument list too long"). This is the isolated
call pattern used ad hoc for binance and healthstream during the 2026-09-19
Agy shakedown (FIXQUEUE-2026-09-18-agy-shakedown.md, item 9s follow-up) --
written up here as a real script instead of a hand-typed command each time.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable

from run_stage1_repair import (
    ARTIFACT_NAMES,
    _agy_cmd,
    _iter_stdout,
    _kill_proc,
    _valid_provenance_body,
    consume_repair_stream,
    document_is_structurally_sane,
    extract_fenced_artifacts,
)

DEFAULT_WALL_SECONDS = 400
DEFAULT_MAX_EVENTS = 60
DEFAULT_MODEL = "gemini-3.8-flash-medium"
DEFAULT_EFFORT = "medium"
PROMPT_NAME = "authoring_prompt.md"
ATTEMPTS_DIR = "stage1_author_attempts"
REQUIRED_ARTIFACT_NAMES = ("Resume.md", "CoverLetter.md", "claim_provenance.json")


def build_author_command(
    *,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    wall_seconds: int = DEFAULT_WALL_SECONDS,
) -> list[str]:
    return [
        _agy_cmd(),
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--sandbox",
        "--disable-slash-commands",
        "--new-project",
        "--model",
        model,
        "--effort",
        effort,
        "--print-timeout",
        f"{wall_seconds}s",
    ]


def _readline_timeout(pipe: Any, timeout_seconds: float) -> str:
    """Read one stdout line with a timeout. Windows pipes do not support select."""
    import queue

    lines: "queue.Queue[str]" = queue.Queue()

    def _reader() -> None:
        lines.put(pipe.readline())

    worker = threading.Thread(target=_reader, daemon=True)
    worker.start()
    try:
        return lines.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        raise subprocess.TimeoutExpired("agy", timeout_seconds) from exc


def _stopped(reason: str, *, event_count: int = 0, wall_seconds: float = 0.0) -> dict[str, Any]:
    return {
        "outcome": "author_failed",
        "reason": reason,
        "event_count": event_count,
        "wall_seconds": round(wall_seconds, 3),
        "text": "",
        "result": None,
    }


def run_author_process(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    wall_seconds: int | None = None,
    max_events: int | None = None,
    spawn: Callable[[list[str], Path], subprocess.Popen[str]] | None = None,
) -> dict[str, Any]:
    wall = wall_seconds if wall_seconds is not None else DEFAULT_WALL_SECONDS
    events = max_events if max_events is not None else DEFAULT_MAX_EVENTS
    command = build_author_command(model=model, effort=effort, wall_seconds=wall)
    tmp = tempfile.TemporaryDirectory(prefix="applyr-stage1-author-")
    workspace = Path(tmp.name)

    def _spawn(cmd: list[str], cwd: Path) -> subprocess.Popen[str]:
        return subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd),
            shell=False,
            bufsize=1,
        )

    starter = spawn or _spawn
    proc = starter(command, workspace)
    assert proc.stdin is not None and proc.stdout is not None
    start = time.monotonic()
    try:
        try:
            raw_init = _readline_timeout(proc.stdout, wall)
        except subprocess.TimeoutExpired:
            return _stopped("no_init_timeout", wall_seconds=time.monotonic() - start)
        if not raw_init:
            return _stopped("no_init", wall_seconds=time.monotonic() - start)
        try:
            init_event = json.loads(raw_init)
        except json.JSONDecodeError:
            return _stopped("bad_init", wall_seconds=time.monotonic() - start)
        if init_event.get("event") != "init":
            return _stopped("missing_init_event", wall_seconds=time.monotonic() - start)

        proc.stdin.write(json.dumps({"event": "user", "message": {"content": prompt}}) + "\n")
        proc.stdin.flush()
        proc.stdin.close()

        result = consume_repair_stream(
            _iter_stdout(proc.stdout),
            wall_seconds=wall,
            max_events=events,
            kill=lambda: _kill_proc(proc),
            started_at=start,
        )
        if result.get("outcome") == "repair_timeout":
            result["outcome"] = "author_timeout"
        elif result.get("outcome") == "repair_failed":
            result["outcome"] = "author_failed"
        return result
    finally:
        _kill_proc(proc)
        tmp.cleanup()


def artifacts_are_complete(found: dict[str, str]) -> bool:
    for name in REQUIRED_ARTIFACT_NAMES:
        body = found.get(name, "")
        if name == "claim_provenance.json":
            if _valid_provenance_body(body) is None:
                return False
        elif not document_is_structurally_sane(name, body):
            return False
    return True


def write_author_artifacts(folder: Path, found: dict[str, str]) -> None:
    for name in ("Resume.md", "CoverLetter.md"):
        (folder / name).write_text(found[name], encoding="utf-8")
    body = _valid_provenance_body(found["claim_provenance.json"])
    assert body is not None
    (folder / "claim_provenance.json").write_text(body, encoding="utf-8")


def save_raw_attempt(folder: Path, text: str) -> Path:
    dest = folder / ATTEMPTS_DIR
    dest.mkdir(parents=True, exist_ok=True)
    n = len(list(dest.glob("*.txt"))) + 1
    path = dest / f"{n}.txt"
    path.write_text(text or "", encoding="utf-8")
    return path


def run_for_folder(
    folder: Path,
    *,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    wall_seconds: int | None = None,
    max_events: int | None = None,
    spawn: Callable[[list[str], Path], subprocess.Popen[str]] | None = None,
) -> dict[str, Any]:
    folder = folder.resolve()
    prompt_path = folder / PROMPT_NAME
    if not prompt_path.is_file():
        return {
            "outcome": "author_failed",
            "reason": "missing_prompt",
            "event_count": 0,
            "wall_seconds": 0,
            "text": "",
            "result": None,
            "wrote_files": False,
        }
    prompt = prompt_path.read_text(encoding="utf-8")
    result = run_author_process(
        prompt,
        model=model,
        effort=effort,
        wall_seconds=wall_seconds,
        max_events=max_events,
        spawn=spawn,
    )
    save_raw_attempt(folder, str(result.get("text") or ""))
    if result.get("outcome") == "ok":
        found = extract_fenced_artifacts(str(result.get("text") or ""))
        if artifacts_are_complete(found):
            write_author_artifacts(folder, found)
            result["wrote_files"] = True
            return result
        result["outcome"] = "author_failed"
        result["reason"] = "invalid_or_incomplete_artifacts"
    result["wrote_files"] = False
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a single-shot sandboxed Stage 1 fresh-author Agy call."
    )
    parser.add_argument("folder", help="Submission folder with authoring_prompt.md")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--effort", default=DEFAULT_EFFORT)
    parser.add_argument("--wall-seconds", type=int, default=DEFAULT_WALL_SECONDS)
    args = parser.parse_args(argv)
    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"ERROR: {folder} is not a directory", file=sys.stderr)
        return 1
    result = run_for_folder(
        folder, model=args.model, effort=args.effort, wall_seconds=args.wall_seconds
    )
    print(
        f"{result['outcome']}"
        + (f" — {result['reason']}" if result.get("reason") else "")
        + f" events={result.get('event_count')} wall={result.get('wall_seconds')}s"
        + f" wrote_files={result.get('wrote_files')}"
    )
    return 0 if result.get("outcome") == "ok" and result.get("wrote_files") else 2


if __name__ == "__main__":
    raise SystemExit(main())
