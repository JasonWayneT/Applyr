#!/usr/bin/env python3
"""CR-119 queue worker: claim, fence, lock, invoke run_submission.py.

# Implements FR-343 / FR-344 / AC-442 / AC-444 / AC-447 / AC-458
# Does not import scripts/workflow/ and does not edit run_submission.py.
# One in-lease run_stage1_author.py call when WAITING_FOR_LLM has a prompt
# and no Resume.md; then --resume. Partial Stage 1 files stay paused (AC-448).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pipeline_queue as pq
from queue_lock import SlugLockUnavailable, acquire_slug_lock

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent
RUN_SUBMISSION = _SCRIPT_DIR / "run_submission.py"
RUN_STAGE1_AUTHOR = _SCRIPT_DIR / "run_stage1_author.py"
RUN_STAGE1_REPAIR = _SCRIPT_DIR / "run_stage1_repair.py"
BUILD_STAGE1_REPAIR_PROMPT = _SCRIPT_DIR / "build_stage1_repair_prompt.py"
RUN_STAGE2_RUBRIC = _SCRIPT_DIR / "run_stage2_rubric.py"
DEFAULT_HEARTBEAT_S = 300

PAUSE_WORKFLOW = frozenset(
    {"WAITING_FOR_LLM", "NEEDS_DISPOSITION", "WAITING_FOR_INPUT", "FAILED"}
)
DONE_WORKFLOW = frozenset(
    {
        "COMPLETE",
        "COMPLETE_WITH_OVERRIDE",
        "PRACTICE_COMPLETE",
        "SKIPPED",
        "ALREADY_HANDLED",  # Implements FR-365 / AC-474
    }
)

_abort_requested = False


class TokenExhausted(RuntimeError):
    """Runner reported token exhaustion; abort the rest of the pack."""


@dataclass
class RunnerHandle:
    proc: Any
    job: Any = None
    pgid: int | None = None

    @property
    def pid(self) -> int:
        return int(self.proc.pid)

    def wait(self, timeout: float | None = None) -> int | None:
        return self.proc.wait(timeout=timeout)

    def poll(self) -> int | None:
        poll = getattr(self.proc, "poll", None)
        if poll is not None:
            return poll()
        return getattr(self.proc, "returncode", None)

    def kill_tree(self) -> None:
        if os.name == "nt":
            _close_job(self.job)
            self.job = None
            try:
                self.proc.kill()
            except OSError:
                pass
        else:
            target = self.pgid or self.pid
            try:
                os.killpg(target, signal.SIGKILL)
            except OSError:
                try:
                    self.proc.kill()
                except OSError:
                    pass


def _kernel32() -> Any:
    import ctypes

    return ctypes.WinDLL("kernel32", use_last_error=True)


def _create_kill_on_close_job() -> Any:
    import ctypes
    from ctypes import wintypes

    kernel32 = _kernel32()
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        kernel32.CloseHandle(job)
        raise ctypes.WinError(ctypes.get_last_error())
    return job


def _assign_pid_to_job(job: Any, pid: int) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = _kernel32()
    PROCESS_TERMINATE = 0x0001
    PROCESS_SET_QUOTA = 0x0100
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    handle = kernel32.OpenProcess(PROCESS_TERMINATE | PROCESS_SET_QUOTA, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        if not kernel32.AssignProcessToJobObject(job, handle):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel32.CloseHandle(handle)


def _close_job(job: Any) -> None:
    if not job:
        return
    try:
        _kernel32().CloseHandle(job)
    except OSError:
        pass


def _utf8_child_env() -> dict[str, str]:
    """Force Python UTF-8 mode (PEP 540) in the spawned pipeline process.

    Found 2026-09-20/21 root-causing the Stage 0 mojibake bug (FIXQUEUE
    2026-09-18 item #4, habiterre): this machine's default locale encoding
    is cp1252 (confirmed via `locale.getpreferredencoding()`), with neither
    PYTHONUTF8 nor PYTHONIOENCODING set anywhere in the ambient environment.
    Every direct file/subprocess encoding call in the Stage 0 path
    (build_stage0_fit_gate.py, stage0_subscription_adapter.py,
    stage0_requirement_extraction_review.py, stage0_checkpoint.py) was
    audited and already pins encoding="utf-8" explicitly, so the exact
    unpinned call responsible for the observed "SYMFONI+â„¢"
    corruption (UTF-8 bytes decoded as cp1252) could not be reproduced or
    isolated without a live subscription-adapter outage. Forcing UTF-8 mode
    for the whole spawned pipeline process closes this entire bug class --
    any current or future code path that omits an explicit encoding= now
    falls back to UTF-8 instead of the OS locale codepage, in this process
    and everywhere it imports. Scoped to the spawned child only (not this
    worker's own process, and not machine-wide) so the change is reversible
    via git and does not touch the user's environment.
    """
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    # Standing plan (FIXQUEUE / PLAN-2026-09-18 Task 3 / FR-328): Agy is the
    # Stage 0 LLM. Groq and Gemini are not in rotation. Force the adapter on
    # for the spawned pipeline child even if the worker's own shell left it
    # unset -- that miss is what sent the 2026-09-21 queue pack to Groq 429s.
    env["APPLYR_STAGE0_SUBSCRIPTION_ADAPTER"] = "1"
    return env


def spawn_runner(cmd: list[str], *, cwd: Path | None = None) -> RunnerHandle:
    env = _utf8_child_env()
    if os.name == "nt":
        job = _create_kill_on_close_job()
        proc = subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, env=env)
        try:
            _assign_pid_to_job(job, proc.pid)
        except OSError:
            proc.kill()
            _close_job(job)
            raise
        return RunnerHandle(proc=proc, job=job)
    proc = subprocess.Popen(
        cmd, cwd=str(cwd) if cwd else None, start_new_session=True, env=env
    )
    return RunnerHandle(proc=proc, pgid=proc.pid)


def find_folder(
    slug: str,
    data_root: Path,
    original: Path | None = None,
) -> Path | None:
    if original is not None and original.exists():
        return original
    for rel in ("pending_review", "submissions", str(Path("archive") / "skipped")):
        candidate = data_root / rel / slug
        if candidate.exists():
            return candidate
    return None


def folder_root_label(folder: Path, data_root: Path) -> str:
    try:
        relative = folder.resolve().relative_to(data_root.resolve())
    except ValueError:
        return "pending_review"
    parts = relative.parts
    if parts and parts[0] == "archive":
        return "archive/skipped"
    return parts[0] if parts else "pending_review"


def build_runner_command(
    slug: str,
    folder: Path | None,
    *,
    python_exe: str | None = None,
    script_path: Path | None = None,
) -> list[str]:
    cmd = [python_exe or sys.executable, str(script_path or RUN_SUBMISSION), slug]
    if folder is not None and (folder / "workflow_state.json").exists():
        cmd.append("--resume")
    return cmd


def build_author_command(
    folder: Path,
    *,
    python_exe: str | None = None,
) -> list[str]:
    """Invoke run_stage1_author.py for a WAITING_FOR_LLM folder."""
    return [python_exe or sys.executable, str(RUN_STAGE1_AUTHOR), str(folder)]


def build_repair_prompt_command(
    folder: Path,
    *,
    python_exe: str | None = None,
) -> list[str]:
    """Build the Stage 1 repair prompt for a verify failure. Implements FR-344."""
    return [python_exe or sys.executable, str(BUILD_STAGE1_REPAIR_PROMPT), str(folder)]


def build_repair_command(
    folder: Path,
    *,
    python_exe: str | None = None,
) -> list[str]:
    """Invoke the sandboxed Stage 1 repair call. Implements FR-344."""
    return [python_exe or sys.executable, str(RUN_STAGE1_REPAIR), str(folder)]


def build_rubric_command(
    folder: Path,
    *,
    python_exe: str | None = None,
) -> list[str]:
    """Invoke run_stage2_rubric.py for a folder waiting on a scorecard."""
    return [python_exe or sys.executable, str(RUN_STAGE2_RUBRIC), str(folder)]


def build_finalize_command(
    folder: Path,
    *,
    python_exe: str | None = None,
    script_path: Path | None = None,
) -> list[str]:
    """Save a finished packet into the app. Implements FR-371."""
    return [
        python_exe or sys.executable,
        str(script_path or RUN_SUBMISSION),
        str(folder),
        "--finalize",
    ]


def needs_stage2_rubric(folder: Path | None) -> bool:
    """True when the off-default Agy scorecard hook should run.

    AC-463 / AC-464: production stays off until APPLYR_STAGE2_AGY_RUBRIC=1
    and frozen parks fail closed. Missing docs or a current-hash scorecard
    does not call.
    """
    if os.environ.get("APPLYR_STAGE2_AGY_RUBRIC", "").strip() != "1":
        return False
    if folder is None:
        return False
    if not (folder / "Resume.md").is_file() or not (folder / "CoverLetter.md").is_file():
        return False
    from run_stage2_rubric import has_current_hash_scorecard

    return not has_current_hash_scorecard(folder)


_REPAIR_STOP_OUTCOMES = frozenset()


def _repair_state(folder: Path) -> dict[str, Any]:
    path = folder / "stage1_repair_state.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


_PRE_REPAIR_DIR = "stage1_pre_repair"
_PRE_REPAIR_FILES = ("Resume.md", "CoverLetter.md", "claim_provenance.json")


def _snapshot_pre_repair(folder: Path) -> None:
    """Copy the current draft before an in-lease repair can replace it."""
    dest = folder / _PRE_REPAIR_DIR
    dest.mkdir(exist_ok=True)
    for name in _PRE_REPAIR_FILES:
        src = folder / name
        if src.is_file():
            shutil.copy2(src, dest / name)


def _stage1_still_failed(folder: Path) -> bool:
    """True when workflow Stage 1 is still FAILED after a repair resume."""
    state = read_workflow_state(folder)
    if state.get("status") != "FAILED":
        return False
    stages = state.get("stages") if isinstance(state.get("stages"), dict) else {}
    stage1 = stages.get("stage1") if isinstance(stages.get("stage1"), dict) else {}
    return stage1.get("status") == "FAILED" or state.get("active_stage") == "stage1"


def _restore_pre_repair(folder: Path) -> bool:
    """Put the pre-repair draft back when the repair left different bytes.

    Returns True only when a file changed. Implements FR-375.
    """
    src_dir = folder / _PRE_REPAIR_DIR
    if not (src_dir / "Resume.md").is_file():
        return False
    changed = False
    for name in _PRE_REPAIR_FILES:
        src = src_dir / name
        if not src.is_file():
            continue
        dest = folder / name
        if dest.is_file() and dest.read_bytes() == src.read_bytes():
            continue
        shutil.copy2(src, dest)
        changed = True
    return changed


def _block_further_repair(folder: Path) -> None:
    """Count a rollback. The first one can be claimed again. Implements FR-375."""
    from build_stage1_repair_prompt import load_repair_state, save_repair_state

    state = load_repair_state(folder)
    try:
        streak = int(state.get("no_progress_streak") or 0)
    except (TypeError, ValueError):
        streak = 0
    state["last_outcome"] = "no_progress_blocking"
    state["no_progress_streak"] = streak + 1
    state["last_repair_reason"] = "repair left stage 1 failed; previous draft restored"
    save_repair_state(folder, state)


def _repair_blocking(folder: Path) -> list[str]:
    """Blocking lines stored for the current repair round."""
    repair = _repair_state(folder)
    return [str(item) for item in (repair.get("blocking") or [])]


def _repair_findings_unchanged(before: list[str], after: list[str]) -> bool:
    """True when a repair did not change the blocking lines. FR-375."""
    return list(before) == list(after)


def _release_repair_progress(folder: Path) -> None:
    """Keep a repair that changed the blocking findings. Implements FR-375."""
    from build_stage1_repair_prompt import load_repair_state, save_repair_state

    state = load_repair_state(folder)
    state["no_progress_streak"] = 0
    state["last_repair_reason"] = (
        "repair changed the blocking findings; new draft kept"
    )
    save_repair_state(folder, state)


def _parse_retry_at(value: object) -> datetime | None:
    """Parse a repair next_retry_at stamp. A blank value means try now."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _timeout_repair_can_run(repair: dict[str, Any]) -> bool:
    """True when a provider timeout still has attempts and the wait has elapsed.

    Four tries, then stop. A future next_retry_at leaves the row paused so the
    worker can claim a different job. Implements FR-378.
    """
    from run_stage1_repair import TIMEOUT_RETRY_CAP

    raw_attempts = repair.get("timeout_attempts")
    if raw_attempts is None:
        try:
            attempts = int(repair.get("no_progress_streak") or 1)
        except (TypeError, ValueError):
            attempts = 1
    else:
        try:
            attempts = int(raw_attempts)
        except (TypeError, ValueError):
            attempts = TIMEOUT_RETRY_CAP
    if attempts >= TIMEOUT_RETRY_CAP:
        return False
    retry_at = _parse_retry_at(repair.get("next_retry_at"))
    if retry_at is not None and datetime.now(timezone.utc) < retry_at:
        return False
    return True


def needs_stage1_repair(folder: Path | None) -> bool:
    """True when Stage 1 verify failed on an existing draft and repair can still run.

    A provider timeout can run again until four attempts, after its wait.
    Identical findings and a second content miss stay paused. Implements FR-344 / FR-378.
    """
    if folder is None or not (folder / "Resume.md").is_file():
        return False
    state = read_workflow_state(folder)
    if state.get("status") != "FAILED":
        return False
    stages = state.get("stages") if isinstance(state.get("stages"), dict) else {}
    stage1 = stages.get("stage1") if isinstance(stages.get("stage1"), dict) else {}
    stage1_status = stage1.get("status")
    if stage1_status != "FAILED" and state.get("active_stage") != "stage1":
        return False
    if stage1_status not in (None, "", "FAILED"):
        return False
    repair = _repair_state(folder)
    outcome = repair.get("last_outcome")
    if outcome == "repair_timeout":
        return _timeout_repair_can_run(repair)
    if outcome in _REPAIR_STOP_OUTCOMES:
        return False
    try:
        streak = int(repair.get("no_progress_streak") or 0)
    except (TypeError, ValueError):
        streak = 0
    if streak >= 2:
        return False
    return True


def needs_stage1_author(folder: Path | None) -> bool:
    """True when Stage 0 left WAITING_FOR_LLM with a prompt and no Resume.md.

    AC-458 / FR-344: one in-lease author attempt. Partial Stage 1 files stay
    paused (AC-448). Missing prompt is fail-closed: pause, do not author.
    """
    if folder is None:
        return False
    if read_workflow_state(folder).get("status") != "WAITING_FOR_LLM":
        return False
    if not (folder / "authoring_prompt.md").is_file():
        return False
    if (folder / "Resume.md").exists():
        return False
    return True


def wait_for_runner(
    handle: RunnerHandle,
    *,
    heartbeat_s: float,
    conn: Any,
    worker: str,
) -> int | None:
    """Wait for a spawned runner, heartbeating the lease until it exits."""
    while True:
        if _abort_requested:
            handle.kill_tree()
            return handle.poll()
        try:
            return handle.wait(timeout=heartbeat_s)
        except subprocess.TimeoutExpired:
            pq.heartbeat(worker, conn=conn)


def is_ready_to_finalize(state: dict[str, Any]) -> bool:
    """Stage 2 COMPLETE and Stage 3 READY: the packet can be saved into the app."""
    if not isinstance(state, dict):
        return False
    stages = state.get("stages") if isinstance(state.get("stages"), dict) else {}
    s2 = stages.get("stage2") if isinstance(stages.get("stage2"), dict) else {}
    s3 = stages.get("stage3") if isinstance(stages.get("stage3"), dict) else {}
    return (
        state.get("status") == "IN_PROGRESS"
        and state.get("active_stage") == "stage3"
        and s2.get("status") == "COMPLETE"
        and s3.get("status") == "READY"
    )


def map_workflow_status(workflow_status: str | None) -> str | None:
    if workflow_status in PAUSE_WORKFLOW:
        return "paused"
    if workflow_status in DONE_WORKFLOW:
        return "done"
    return None


def map_run_result(
    state: dict[str, Any],
    *,
    finalize_attempted: bool = False,
) -> tuple[str | None, str | None, str | None]:
    """Return (queue_status, paused_reason, last_workflow_status)."""
    if is_ready_to_finalize(state):
        # Implements FR-371 / AC-481. After a save attempt that left the packet
        # ready, stop. Do not hand the same packet back to the next claim.
        if finalize_attempted:
            return (
                "paused",
                pq.PAUSED_REASON_FINALIZE_FAILED,
                pq.MIRROR_READY_TO_FINALIZE,
            )
        return (
            "paused",
            pq.PAUSED_REASON_READY_TO_FINALIZE,
            pq.MIRROR_READY_TO_FINALIZE,
        )
    wf_status = state.get("status") if isinstance(state.get("status"), str) else None
    if wf_status == "WAITING_FOR_INPUT":
        kind = (state.get("metadata") or {}).get("pause_kind")
        if kind == pq.PAUSE_KIND_CONVERSION_RISK:
            return (
                "paused",
                pq.PAUSED_REASON_CONVERSION_RISK,
                wf_status,
            )
    mapped = map_workflow_status(wf_status)
    return mapped, None, wf_status


def read_workflow_state(folder: Path | None) -> dict[str, Any]:
    if folder is None:
        return {}
    path = folder / "workflow_state.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def update_mirror(
    conn: Any,
    slug: str,
    *,
    last_workflow_status: str | None,
    last_stage: str | None,
    folder_root: str | None = None,
) -> None:
    sets = ["updated_at = ?"]
    args: list[Any] = [pq.utc_now()]
    if last_workflow_status is not None:
        sets.append("last_workflow_status = ?")
        args.append(last_workflow_status)
    if last_stage is not None:
        sets.append("last_stage = ?")
        args.append(last_stage)
    if folder_root is not None:
        sets.append("folder_root = ?")
        args.append(folder_root)
    args.append(slug)
    conn.execute(
        f"UPDATE pipeline_queue SET {', '.join(sets)} WHERE slug = ?",
        args,
    )
    conn.commit()


def apply_run_result(
    slug: str,
    *,
    conn: Any,
    worker: str,
    token: int,
    data_root: Path,
    original: Path | None,
    exit_code: int | None,
    finalize_attempted: bool = False,
) -> dict[str, Any] | None:
    _ = exit_code  # recorded by caller; never the mapping key
    folder = find_folder(slug, data_root, original)
    if folder is not None and folder.name != slug:
        # Placement can rename the folder; keep the queue key unless we found it.
        pass
    state = read_workflow_state(folder)
    wf_status = state.get("status") if isinstance(state.get("status"), str) else None
    last_stage = state.get("active_stage") if isinstance(state.get("active_stage"), str) else None
    folder_root = folder_root_label(folder, data_root) if folder is not None else None
    mapped, paused_reason, mirror_status = map_run_result(
        state, finalize_attempted=finalize_attempted
    )
    if mapped is None:
        update_mirror(
            conn,
            slug,
            last_workflow_status=wf_status,
            last_stage=last_stage,
            folder_root=folder_root,
        )
        return pq.get_row(conn, slug)
    current = pq.get_row(conn, slug)
    # Finalize already marks the row done. A second done write is not a transition.
    if current is not None and current["status"] == "done" and mapped == "done":
        return current
    return pq.transition(
        slug,
        mapped,
        worker=worker,
        token=token,
        conn=conn,
        last_workflow_status=mirror_status,
        last_stage=last_stage,
        folder_root=folder_root,
        paused_reason=paused_reason,
    )


def abort_unstarted(
    worker: str,
    unstarted: list[dict[str, Any]],
    conn: Any,
) -> None:
    for row in unstarted:
        current = pq.get_row(conn, row["slug"])
        if current is None or current["status"] != "leased":
            continue
        try:
            pq.transition(
                row["slug"],
                "queued",
                worker=worker,
                token=current["fencing_token"],
                conn=conn,
            )
        except pq.FenceRejected:
            continue


def process_slug(
    row: dict[str, Any],
    *,
    worker: str,
    conn: Any,
    data_root: Path,
    lock_dir: Path,
    spawn: Callable[[list[str]], RunnerHandle],
    heartbeat_s: float,
    python_exe: str | None = None,
    script_path: Path | None = None,
) -> str:
    slug = row["slug"]
    fresh = pq.get_row(conn, slug)
    if fresh is None or fresh["fencing_token"] != row["fencing_token"]:
        return "stale_token"
    if fresh["locked_by"] != worker:
        return "stale_token"
    # Implements FR-363 / AC-472. Holder closes already-handled before invoke.
    if slug in pq._already_handled_slugs(conn, data_root):
        try:
            pq.transition(
                slug,
                "done",
                worker=worker,
                token=fresh["fencing_token"],
                conn=conn,
            )
        except pq.FenceRejected:
            return "stale_token"
        return "already_handled"
    try:
        with acquire_slug_lock(
            slug, worker, fresh["fencing_token"], lock_dir=lock_dir
        ) as lock:
            running = pq.transition(
                slug,
                "in_progress",
                worker=worker,
                token=fresh["fencing_token"],
                conn=conn,
            )
            folder = find_folder(slug, data_root)
            if folder is not None and pq._pause_kind(folder) == "review_center":
                # Implements FR-373. One resume of this pause per answer change.
                pq.write_review_center_resumed_marker(folder)
            cmd = build_runner_command(
                slug, folder, python_exe=python_exe, script_path=script_path
            )
            handle = spawn(cmd)
            lock.set_runner_pid(handle.pid)
            exit_code = wait_for_runner(
                handle, heartbeat_s=heartbeat_s, conn=conn, worker=worker
            )
            if not _abort_requested:
                folder = find_folder(slug, data_root, folder)
                if needs_stage1_author(folder):
                    # Implements AC-458 / FR-344: one in-lease author, then resume.
                    author_handle = spawn(
                        build_author_command(folder, python_exe=python_exe)
                    )
                    lock.set_runner_pid(author_handle.pid)
                    wait_for_runner(
                        author_handle,
                        heartbeat_s=heartbeat_s,
                        conn=conn,
                        worker=worker,
                    )
                    if not _abort_requested:
                        folder = find_folder(slug, data_root, folder)
                        resume_cmd = build_runner_command(
                            slug,
                            folder,
                            python_exe=python_exe,
                            script_path=script_path,
                        )
                        handle = spawn(resume_cmd)
                        lock.set_runner_pid(handle.pid)
                        exit_code = wait_for_runner(
                            handle,
                            heartbeat_s=heartbeat_s,
                            conn=conn,
                            worker=worker,
                        )
                folder = find_folder(slug, data_root, folder)
                if needs_stage1_repair(folder):
                    # Implements FR-344. A verify miss on an existing draft
                    # repairs in this lease, then resumes. A failed or
                    # no-progress repair still pauses FAILED. A rewrite that
                    # leaves Stage 1 failed with the same blocking findings is put
                    # back. A repair that changes those findings is kept. FR-375.
                    from author_from_packet import attach_unsupported_ats_cites

                    if attach_unsupported_ats_cites(folder):
                        # A present term was missing its cite. Resume before
                        # a full rewrite. Implements FR-377.
                        cite_cmd = build_runner_command(
                            slug,
                            folder,
                            python_exe=python_exe,
                            script_path=script_path,
                        )
                        cite_handle = spawn(cite_cmd)
                        lock.set_runner_pid(cite_handle.pid)
                        exit_code = wait_for_runner(
                            cite_handle,
                            heartbeat_s=heartbeat_s,
                            conn=conn,
                            worker=worker,
                        )
                        folder = find_folder(slug, data_root, folder)
                    prompt_handle = None
                    if folder is not None and needs_stage1_repair(folder):
                        _snapshot_pre_repair(folder)
                        prompt_handle = spawn(
                            build_repair_prompt_command(folder, python_exe=python_exe)
                        )
                        lock.set_runner_pid(prompt_handle.pid)
                        wait_for_runner(
                            prompt_handle,
                            heartbeat_s=heartbeat_s,
                            conn=conn,
                            worker=worker,
                        )
                    if prompt_handle is not None and not _abort_requested:
                        folder = find_folder(slug, data_root, folder)
                        prompt_ready = (
                            folder is not None
                            and (folder / "stage1_repair_prompt.md").is_file()
                            and needs_stage1_repair(folder)
                        )
                        if prompt_ready:
                            repair_handle = spawn(
                                build_repair_command(folder, python_exe=python_exe)
                            )
                            lock.set_runner_pid(repair_handle.pid)
                            wait_for_runner(
                                repair_handle,
                                heartbeat_s=heartbeat_s,
                                conn=conn,
                                worker=worker,
                            )
                            if not _abort_requested:
                                folder = find_folder(slug, data_root, folder)
                                trigger_blocking = (
                                    _repair_blocking(folder) if folder is not None else []
                                )
                                resume_cmd = build_runner_command(
                                    slug,
                                    folder,
                                    python_exe=python_exe,
                                    script_path=script_path,
                                )
                                handle = spawn(resume_cmd)
                                lock.set_runner_pid(handle.pid)
                                exit_code = wait_for_runner(
                                    handle,
                                    heartbeat_s=heartbeat_s,
                                    conn=conn,
                                    worker=worker,
                                )
                                folder = find_folder(slug, data_root, folder)
                                new_blocking = (
                                    _repair_blocking(folder) if folder is not None else []
                                )
                                findings_unchanged = _repair_findings_unchanged(
                                    trigger_blocking, new_blocking
                                )
                                if (
                                    folder is not None
                                    and _stage1_still_failed(folder)
                                    and findings_unchanged
                                    and _restore_pre_repair(folder)
                                ):
                                    _block_further_repair(folder)
                                    resume_cmd = build_runner_command(
                                        slug,
                                        folder,
                                        python_exe=python_exe,
                                        script_path=script_path,
                                    )
                                    handle = spawn(resume_cmd)
                                    lock.set_runner_pid(handle.pid)
                                    exit_code = wait_for_runner(
                                        handle,
                                        heartbeat_s=heartbeat_s,
                                        conn=conn,
                                        worker=worker,
                                    )
                                elif (
                                    folder is not None
                                    and _stage1_still_failed(folder)
                                    and not findings_unchanged
                                ):
                                    _release_repair_progress(folder)
                folder = find_folder(slug, data_root, folder)
                if needs_stage2_rubric(folder):
                    # Implements AC-463: off-default in-lease rubric, then resume.
                    rubric_handle = spawn(
                        build_rubric_command(folder, python_exe=python_exe)
                    )
                    lock.set_runner_pid(rubric_handle.pid)
                    wait_for_runner(
                        rubric_handle,
                        heartbeat_s=heartbeat_s,
                        conn=conn,
                        worker=worker,
                    )
                    if not _abort_requested:
                        folder = find_folder(slug, data_root, folder)
                        resume_cmd = build_runner_command(
                            slug,
                            folder,
                            python_exe=python_exe,
                            script_path=script_path,
                        )
                        handle = spawn(resume_cmd)
                        lock.set_runner_pid(handle.pid)
                        exit_code = wait_for_runner(
                            handle,
                            heartbeat_s=heartbeat_s,
                            conn=conn,
                            worker=worker,
                        )
            finalize_attempted = False
            if not _abort_requested:
                folder = find_folder(slug, data_root, folder)
                if folder is not None and is_ready_to_finalize(read_workflow_state(folder)):
                    # Implements FR-371 / AC-481. Save into the app in this same run.
                    finalize_attempted = True
                    finalize_handle = spawn(
                        build_finalize_command(
                            folder,
                            python_exe=python_exe,
                            script_path=script_path,
                        )
                    )
                    lock.set_runner_pid(finalize_handle.pid)
                    exit_code = wait_for_runner(
                        finalize_handle,
                        heartbeat_s=heartbeat_s,
                        conn=conn,
                        worker=worker,
                    )
                    folder = find_folder(slug, data_root, folder)
            if not _abort_requested:
                try:
                    apply_run_result(
                        slug,
                        conn=conn,
                        worker=worker,
                        token=running["fencing_token"],
                        data_root=data_root,
                        original=folder,
                        exit_code=exit_code,
                        finalize_attempted=finalize_attempted,
                    )
                except pq.FenceRejected:
                    pass
            return "ran"
    except SlugLockUnavailable:
        return "lock_unavailable"


def run_pack(
    worker: str,
    *,
    conn: Any,
    data_root: Path,
    lock_dir: Path,
    size: int = pq.DEFAULT_PACK_SIZE,
    lease_minutes: int = pq.DEFAULT_LEASE_MINUTES,
    spawn: Callable[[list[str]], RunnerHandle] | None = None,
    heartbeat_s: float = DEFAULT_HEARTBEAT_S,
    python_exe: str | None = None,
    script_path: Path | None = None,
    skip_slugs: set[str] | None = None,
) -> dict[str, Any]:
    spawn_fn = spawn or spawn_runner
    claimed = pq.claim_pack(
        worker,
        size=size,
        lease_minutes=lease_minutes,
        conn=conn,
        data_root=data_root,
        skip_slugs=skip_slugs,
    )
    unstarted = list(claimed)
    results: list[str] = []
    try:
        for row in claimed:
            if _abort_requested:
                break
            outcome = process_slug(
                row,
                worker=worker,
                conn=conn,
                data_root=data_root,
                lock_dir=lock_dir,
                spawn=spawn_fn,
                heartbeat_s=heartbeat_s,
                python_exe=python_exe,
                script_path=script_path,
            )
            results.append(outcome)
            if outcome == "ran":
                unstarted = [item for item in unstarted if item["slug"] != row["slug"]]
    finally:
        if _abort_requested:
            abort_unstarted(worker, unstarted, conn)
    return {"claimed": [row["slug"] for row in claimed], "results": results}


def drain_until_idle(
    worker: str,
    *,
    conn: Any,
    data_root: Path,
    lock_dir: Path,
    size: int = pq.DEFAULT_PACK_SIZE,
    lease_minutes: int = pq.DEFAULT_LEASE_MINUTES,
    spawn: Callable[[list[str]], RunnerHandle] | None = None,
    heartbeat_s: float = DEFAULT_HEARTBEAT_S,
    python_exe: str | None = None,
    script_path: Path | None = None,
    once: bool = False,
) -> list[dict[str, Any]]:
    """Keep claiming the next batch until nothing left can move. Implements FR-373.

    A slug already run in this process is not claimed again, so a job that
    pauses for the same reason does not spin. ``once`` stops after one batch.
    """
    attempted: set[str] = set()
    summaries: list[dict[str, Any]] = []
    while not _abort_requested:
        summary = run_pack(
            worker,
            conn=conn,
            data_root=data_root,
            lock_dir=lock_dir,
            size=size,
            lease_minutes=lease_minutes,
            spawn=spawn,
            heartbeat_s=heartbeat_s,
            python_exe=python_exe,
            script_path=script_path,
            skip_slugs=attempted,
        )
        summaries.append(summary)
        attempted.update(summary["claimed"])
        if once or not summary["claimed"]:
            break
    return summaries


def request_abort(_signum: int | None = None, _frame: Any = None) -> None:
    global _abort_requested
    _abort_requested = True


def reset_abort() -> None:
    global _abort_requested
    _abort_requested = False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run leased pipeline_queue packs.")
    parser.add_argument("--worker", required=True)
    parser.add_argument("--size", type=int, default=pq.DEFAULT_PACK_SIZE)
    parser.add_argument("--db", default=str(pq.DEFAULT_DB))
    parser.add_argument("--lease-minutes", type=int, default=pq.DEFAULT_LEASE_MINUTES)
    parser.add_argument("--heartbeat-seconds", type=int, default=DEFAULT_HEARTBEAT_S)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--lock-dir", default=str(pq.DATA_ROOT / "queue_locks"))
    parser.add_argument("--data-root", default=str(pq.DATA_ROOT))
    args = parser.parse_args(argv)
    signal.signal(signal.SIGINT, request_abort)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_abort)
    # Claim runs in this process. A missing rubric is not a hold on a queue
    # run, and that decision has to be visible here, not only in the child.
    # Implements FR-371. The Agy rubric stays off until AC-464.
    os.environ.setdefault("APPLYR_STAGE0_SUBSCRIPTION_ADAPTER", "1")
    conn = pq.connect(args.db)
    try:
        # A dead run with this same worker id leaves unstarted rows leased.
        # Heartbeats would keep those leases alive. Put them back first.
        pq.release(args.worker, conn=conn)
        summaries = drain_until_idle(
            args.worker,
            conn=conn,
            data_root=Path(args.data_root),
            lock_dir=Path(args.lock_dir),
            size=args.size,
            lease_minutes=args.lease_minutes,
            heartbeat_s=args.heartbeat_seconds,
            once=args.once,
        )
        for summary in summaries:
            print(
                "claimed={n} results={results}".format(
                    n=len(summary["claimed"]),
                    results=",".join(summary["results"]) or "none",
                )
            )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
