#!/usr/bin/env python3
"""CR-119 queue worker: claim, fence, lock, invoke run_submission.py.

# Implements FR-343 / FR-344 / AC-442 / AC-444 / AC-447
# Does not import scripts/workflow/ and does not edit run_submission.py.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pipeline_queue as pq
from queue_lock import SlugLockUnavailable, acquire_slug_lock

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent
RUN_SUBMISSION = _SCRIPT_DIR / "run_submission.py"
DEFAULT_HEARTBEAT_S = 300

PAUSE_WORKFLOW = frozenset(
    {"WAITING_FOR_LLM", "NEEDS_DISPOSITION", "WAITING_FOR_INPUT", "FAILED"}
)
DONE_WORKFLOW = frozenset(
    {"COMPLETE", "COMPLETE_WITH_OVERRIDE", "PRACTICE_COMPLETE", "SKIPPED"}
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


def is_ready_to_finalize(state: dict[str, Any]) -> bool:
    """Stage 2 COMPLETE / Stage 3 READY: waiting for Jason's --finalize, not stuck."""
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


def map_run_result(state: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Return (queue_status, paused_reason, last_workflow_status)."""
    if is_ready_to_finalize(state):
        return (
            "paused",
            pq.PAUSED_REASON_READY_TO_FINALIZE,
            pq.MIRROR_READY_TO_FINALIZE,
        )
    wf_status = state.get("status") if isinstance(state.get("status"), str) else None
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
    mapped, paused_reason, mirror_status = map_run_result(state)
    if mapped is None:
        update_mirror(
            conn,
            slug,
            last_workflow_status=wf_status,
            last_stage=last_stage,
            folder_root=folder_root,
        )
        return pq.get_row(conn, slug)
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
            cmd = build_runner_command(
                slug, folder, python_exe=python_exe, script_path=script_path
            )
            handle = spawn(cmd)
            lock.set_runner_pid(handle.pid)
            exit_code: int | None = None
            while True:
                if _abort_requested:
                    handle.kill_tree()
                    break
                try:
                    exit_code = handle.wait(timeout=heartbeat_s)
                    break
                except subprocess.TimeoutExpired:
                    pq.heartbeat(worker, conn=conn)
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
) -> dict[str, Any]:
    spawn_fn = spawn or spawn_runner
    claimed = pq.claim_pack(
        worker,
        size=size,
        lease_minutes=lease_minutes,
        conn=conn,
        data_root=data_root,
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
    conn = pq.connect(args.db)
    try:
        while not _abort_requested:
            summary = run_pack(
                args.worker,
                conn=conn,
                data_root=Path(args.data_root),
                lock_dir=Path(args.lock_dir),
                size=args.size,
                lease_minutes=args.lease_minutes,
                heartbeat_s=args.heartbeat_seconds,
            )
            print(
                "claimed={n} results={results}".format(
                    n=len(summary["claimed"]),
                    results=",".join(summary["results"]) or "none",
                )
            )
            if args.once or not summary["claimed"]:
                break
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
