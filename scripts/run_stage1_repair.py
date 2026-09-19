#!/usr/bin/env python3
"""Single-shot sandboxed Stage 1 Agy repair. Text in, text out. No tools."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Iterable, TextIO

DEFAULT_WALL_SECONDS = 180
DEFAULT_MAX_EVENTS = 20
DEFAULT_MODEL = "gemini-3.8-flash-medium"
ARTIFACT_NAMES = ("Resume.md", "CoverLetter.md", "claim_provenance.json")
SANDBOX_INSTRUCTION = (
    "Return only the corrected fenced blocks. Don't use tools or files."
)
_FENCE_RE = re.compile(r"```([^\n]*)\n(.*?)```", re.DOTALL)
TOOL_STEP_TYPES = frozenset(
    {"tool", "tool_use", "tool_request", "permission", "ask_permission"}
)
TOOL_EVENTS = frozenset(
    {
        "tool_request",
        "tool_call",
        "tool_use",
        "permission_request",
        "permission_denied",
    }
)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def repair_limits() -> tuple[int, int]:
    return (
        _env_int("APPLYR_REPAIR_WALL_SECONDS", DEFAULT_WALL_SECONDS),
        _env_int("APPLYR_REPAIR_MAX_EVENTS", DEFAULT_MAX_EVENTS),
    )


def _agy_cmd() -> str:
    found = shutil.which("agy.exe" if os.name == "nt" else "agy") or shutil.which("agy")
    if not found:
        raise FileNotFoundError("agy is not available")
    return found


def is_tool_or_permission_event(event: dict[str, Any]) -> bool:
    if not isinstance(event, dict):
        return False
    name = str(event.get("event") or "")
    if name in TOOL_EVENTS:
        return True
    step = event.get("step_update") if name == "step_update" else None
    if not isinstance(step, dict):
        return False
    step_type = str(step.get("step_type") or "")
    if step_type in TOOL_STEP_TYPES or step.get("tool_name"):
        return True
    info = step.get("tool_info") if isinstance(step.get("tool_info"), dict) else {}
    blob = " ".join(
        str(info.get(key) or "") for key in ("output", "error", "message")
    ).lower()
    if isinstance(info.get("error"), dict):
        blob += " " + " ".join(str(v) for v in info["error"].values()).lower()
    if "permission" in blob and "denied" in blob:
        return True
    if "access to the path" in blob and "denied" in blob:
        return True
    if "permission_denied" in blob or "ask_permission" in blob:
        return True
    return False


def consume_repair_stream(
    lines: Iterable[str],
    *,
    wall_seconds: int,
    max_events: int,
    kill: Callable[[], None] | None = None,
    clock: Callable[[], float] | None = None,
    started_at: float | None = None,
) -> dict[str, Any]:
    """Read a stream-json Agy session. Caps wall time and event count."""
    now = clock or time.monotonic
    start = started_at if started_at is not None else now()
    counted = 0
    text_bits: list[str] = []
    result_event: dict[str, Any] | None = None

    def _stop(outcome: str, reason: str) -> dict[str, Any]:
        if kill is not None:
            kill()
        return {
            "outcome": outcome,
            "reason": reason,
            "event_count": counted,
            "wall_seconds": round(now() - start, 3),
            "text": "".join(text_bits),
            "result": result_event,
        }

    for raw in lines:
        if now() - start >= wall_seconds:
            return _stop("repair_timeout", "wall_time")
        line = raw.strip() if isinstance(raw, str) else str(raw).strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("event") == "init":
            continue
        counted += 1
        if is_tool_or_permission_event(event):
            return _stop("repair_failed", "tool_or_permission")
        if counted > max_events:
            return _stop("repair_timeout", "event_count")
        step = event.get("step_update") if event.get("event") == "step_update" else None
        if isinstance(step, dict) and step.get("step_type") == "agent_response":
            delta = step.get("text_delta") or step.get("text") or ""
            if delta:
                text_bits.append(str(delta))
        if event.get("event") == "result":
            result_event = event
            payload = event.get("result") if isinstance(event.get("result"), dict) else {}
            output = payload.get("output") or payload.get("text") or ""
            if output:
                text_bits.append(str(output))
            break

    if result_event is None:
        return _stop("repair_failed", "no_result")
    return {
        "outcome": "ok",
        "reason": None,
        "event_count": counted,
        "wall_seconds": round(now() - start, 3),
        "text": "".join(text_bits),
        "result": result_event,
    }


def build_repair_command(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    wall_seconds: int | None = None,
) -> list[str]:
    limits_wall, _ = repair_limits()
    timeout = wall_seconds if wall_seconds is not None else limits_wall
    body = SANDBOX_INSTRUCTION + "\n\n" + prompt.strip() + "\n"
    return [
        _agy_cmd(),
        "--output-format",
        "stream-json",
        "--sandbox",
        "--disable-slash-commands",
        "--new-project",
        "--model",
        model,
        "--print-timeout",
        f"{timeout}s",
        "--print",
        body,
    ]


def _kill_proc(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _iter_stdout(pipe: TextIO) -> Iterable[str]:
    while True:
        line = pipe.readline()
        if line == "":
            return
        yield line


def run_repair_process(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    wall_seconds: int | None = None,
    max_events: int | None = None,
    spawn: Callable[[list[str], Path], subprocess.Popen[str]] | None = None,
) -> dict[str, Any]:
    limits_wall, limits_events = repair_limits()
    wall = wall_seconds if wall_seconds is not None else limits_wall
    events = max_events if max_events is not None else limits_events
    command = build_repair_command(prompt, model=model, wall_seconds=wall)
    tmp = tempfile.TemporaryDirectory(prefix="applyr-stage1-repair-")
    workspace = Path(tmp.name)

    def _spawn(cmd: list[str], cwd: Path) -> subprocess.Popen[str]:
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd),
            shell=False,
        )

    starter = spawn or _spawn
    proc = starter(command, workspace)
    assert proc.stdout is not None
    try:
        return consume_repair_stream(
            _iter_stdout(proc.stdout),
            wall_seconds=wall,
            max_events=events,
            kill=lambda: _kill_proc(proc),
        )
    finally:
        _kill_proc(proc)
        tmp.cleanup()


def extract_fenced_artifacts(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for header, body in _FENCE_RE.findall(text or ""):
        tokens = [part.strip().strip("`") for part in header.replace(":", " ").split()]
        label = ""
        for token in tokens:
            for name in ARTIFACT_NAMES:
                if token.lower() == name.lower():
                    label = name
                    break
            if label:
                break
        if not label:
            first = (body.lstrip().splitlines() or [""])[0].strip().lstrip("#").strip()
            for name in ARTIFACT_NAMES:
                if first.lower() == name.lower():
                    label = name
                    body = "\n".join(body.lstrip().splitlines()[1:])
                    break
        if label:
            found[label] = body.strip() + "\n"
    return found


def artifacts_are_valid(found: dict[str, str]) -> bool:
    if set(found.keys()) != set(ARTIFACT_NAMES):
        return False
    if not found["Resume.md"].strip() or not found["CoverLetter.md"].strip():
        return False
    try:
        payload = json.loads(found["claim_provenance.json"])
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and bool(payload)


def write_repair_artifacts(folder: Path, found: dict[str, str]) -> None:
    for name, body in found.items():
        (folder / name).write_text(body, encoding="utf-8")


def apply_repair_result(
    folder: Path,
    result: dict[str, Any],
    *,
    queue_conn: object | None = None,
    data_root: Path | None = None,
) -> dict[str, Any]:
    from build_stage1_repair_prompt import (
        _maybe_requeue_repair,
        load_repair_state,
        save_repair_state,
    )

    state = load_repair_state(folder)
    pending = str(state.get("pending_findings_hash") or state.get("previous_findings_hash") or "")
    payload = dict(result)
    if payload.get("outcome") == "ok":
        found = extract_fenced_artifacts(str(payload.get("text") or ""))
        if artifacts_are_valid(found):
            write_repair_artifacts(folder, found)
            payload["wrote_files"] = True
            state["previous_findings_hash"] = pending
            state["last_outcome"] = "repaired"
            state["last_repair_reason"] = None
            state["no_progress_streak"] = 0
            state["last_event_count"] = payload.get("event_count")
            state["last_wall_seconds"] = payload.get("wall_seconds")
            save_repair_state(folder, state)
            _maybe_requeue_repair(folder, queue_conn=queue_conn, data_root=data_root)
            return payload
        payload["outcome"] = "repair_failed"
        payload["reason"] = "invalid_artifacts"
    state["previous_findings_hash"] = pending
    state["last_outcome"] = payload.get("outcome")
    state["last_repair_reason"] = payload.get("reason")
    state["last_event_count"] = payload.get("event_count")
    state["last_wall_seconds"] = payload.get("wall_seconds")
    state["no_progress_streak"] = int(state.get("no_progress_streak") or 0) + 1
    payload["wrote_files"] = False
    save_repair_state(folder, state)
    return payload


def record_repair_call(folder: Path, result: dict[str, Any]) -> dict[str, Any]:
    apply_repair_result(folder, result)
    return result


def run_for_folder(
    folder: Path,
    *,
    model: str = DEFAULT_MODEL,
    wall_seconds: int | None = None,
    max_events: int | None = None,
    spawn: Callable[[list[str], Path], subprocess.Popen[str]] | None = None,
) -> dict[str, Any]:
    from build_stage1_repair_prompt import REPAIR_PROMPT_NAME

    folder = folder.resolve()
    prompt_path = folder / REPAIR_PROMPT_NAME
    if not prompt_path.is_file():
        result = {
            "outcome": "repair_failed",
            "reason": "missing_prompt",
            "event_count": 0,
            "wall_seconds": 0,
            "text": "",
            "result": None,
        }
        record_repair_call(folder, result)
        return result
    prompt = prompt_path.read_text(encoding="utf-8")
    result = run_repair_process(
        prompt,
        model=model,
        wall_seconds=wall_seconds,
        max_events=max_events,
        spawn=spawn,
    )
    return apply_repair_result(folder, result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a single-shot sandboxed Stage 1 Agy repair call."
    )
    parser.add_argument("folder", help="Submission folder with stage1_repair_prompt.md")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args(argv)
    folder = Path(args.folder)
    if not folder.is_dir():
        print(f"ERROR: {folder} is not a directory", file=sys.stderr)
        return 1
    result = run_for_folder(folder, model=args.model)
    print(
        f"{result['outcome']}"
        + (f" — {result['reason']}" if result.get("reason") else "")
        + f" events={result.get('event_count')} wall={result.get('wall_seconds')}s"
    )
    if result.get("outcome") == "ok":
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
