"""Practice-run the holdout folders. Prints status counts only.

Copies each archive Original_JD.txt without reading it. Every run_submission
call uses --mode practice. Does not claim queue rows. If a practice finalize
marks an overlapping queue row done, that row is restored from the snapshot
taken at start.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))

from author_from_packet import attach_unsupported_ats_cites  # noqa: E402
from run_queue_worker import (  # noqa: E402
    _block_further_repair,
    _release_repair_progress,
    _repair_blocking,
    _repair_findings_unchanged,
    _restore_pre_repair,
    _snapshot_pre_repair,
    _stage1_still_failed,
    is_ready_to_finalize,
    needs_stage1_author,
    needs_stage1_repair,
    read_workflow_state,
)

BASELINE_CALLS = 44
# Default stays 200. A later run sets APPLYR_LOOP_CALL_CAP only after an explicit lift.
CALL_CAP = int(os.environ.get("APPLYR_LOOP_CALL_CAP", "200"))
HOLD = os.environ.get("APPLYR_LOOP_HOLDOUT", "h1")
OUT = ROOT / "data" / "loop_holdout" / HOLD
COUNTS = ROOT / "docs" / "loop" / "evidence" / HOLD / "counts.json"
DB = ROOT / "data" / "jobagent.sqlite"
PY = sys.executable
DONE = frozenset(
    {
        "COMPLETE",
        "COMPLETE_WITH_OVERRIDE",
        "PRACTICE_COMPLETE",
        "SKIPPED",
        "ALREADY_HANDLED",
    }
)


def _holdout_slugs() -> list[str]:
    """Return the holdout slug list from STATE.json. Does not print it."""
    state = json.loads((ROOT / "docs" / "loop" / "STATE.json").read_text(encoding="utf-8"))
    slugs = state.get("holdout_slugs")
    if not isinstance(slugs, list) or len(slugs) != 60:
        raise SystemExit("holdout list is not 60")
    return [str(slug) for slug in slugs]


def _snapshot_queue(slugs: list[str]) -> dict[str, dict]:
    """Save overlapping pipeline_queue rows. Returns the saved rows."""
    saved: dict[str, dict] = {}
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        for slug in slugs:
            row = conn.execute(
                "SELECT * FROM pipeline_queue WHERE slug = ?", (slug,)
            ).fetchone()
            if row is not None:
                saved[slug] = dict(row)
    finally:
        conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "queue_snapshot.json").write_text(
        json.dumps(saved, indent=2) + "\n", encoding="utf-8"
    )
    return saved


def _restore_queue(saved: dict[str, dict]) -> int:
    """Put back any overlapping row whose status changed. Returns how many."""
    if not saved:
        return 0
    restored = 0
    conn = sqlite3.connect(DB)
    try:
        for slug, before in saved.items():
            current = conn.execute(
                "SELECT status FROM pipeline_queue WHERE slug = ?", (slug,)
            ).fetchone()
            if current is None or current[0] == before.get("status"):
                continue
            columns = [name for name in before if name != "slug"]
            if not columns or not all(name.replace("_", "").isalnum() for name in columns):
                raise RuntimeError("queue column name refused")
            assignments = ", ".join(f"{name} = ?" for name in columns)
            values = [before[name] for name in columns]
            conn.execute(
                f"UPDATE pipeline_queue SET {assignments} WHERE slug = ?",
                [*values, slug],
            )
            restored += 1
        conn.commit()
    finally:
        conn.close()
    return restored


def _call_count() -> int:
    """Count Agy call receipts written under this holdout run."""
    total = 0
    if not OUT.is_dir():
        return 0
    for path in OUT.glob("*/observability/agy_quota.jsonl"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if '"type": "call"' in line or '"type":"call"' in line:
                total += 1
    return total


def _publish(by_status: dict[str, int], calls: int, stopped: str | None) -> None:
    """Write slug-free counts and print them."""
    payload = {
        "seen": sum(by_status.values()),
        "by_status": by_status,
        "calls": calls,
        "stopped": stopped,
    }
    COUNTS.parent.mkdir(parents=True, exist_ok=True)
    COUNTS.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    parts = " ".join(f"{key}={by_status[key]}" for key in sorted(by_status))
    print(
        f"seen={payload['seen']} calls={calls} stopped={stopped or '-'} {parts}",
        flush=True,
    )


def _run(args: list[str], log: Path, timeout: int) -> str:
    """Run one command. Returns the exit code, or TIMEOUT."""
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as handle:
        handle.write(("\n$ " + " ".join(args) + "\n").encode("utf-8", errors="replace"))
        try:
            completed = subprocess.run(
                args,
                stdout=handle,
                stderr=subprocess.STDOUT,
                cwd=ROOT,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            handle.write(b"\nTIMEOUT\n")
            return "TIMEOUT"
    return str(completed.returncode)


def _practice(folder: Path, resume: bool, log: Path, timeout: int) -> str:
    """Run the orchestrator in practice mode."""
    args = [PY, "scripts/run_submission.py", str(folder), "--mode", "practice"]
    if resume:
        args.append("--resume")
    return _run(args, log, timeout)


def _one(slug: str, saved: dict[str, dict]) -> str:
    """Advance one holdout folder to a terminal status. Returns that status."""
    src = ROOT / "data" / "archive" / "submissions" / slug / "Original_JD.txt"
    folder = OUT / slug
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "Original_JD.txt"
    if not target.is_file():
        if not src.is_file():
            return "MISSING_JD"
        shutil.copy2(src, target)
    log = folder / "driver.log"
    state = read_workflow_state(folder)
    if state.get("status") in DONE:
        return str(state.get("status"))
    authored = False
    repaired = False
    for _step in range(8):
        state = read_workflow_state(folder)
        status = state.get("status")
        if status in DONE:
            return str(status)
        if status in {"NEEDS_DISPOSITION", "WAITING_FOR_INPUT"}:
            return str(status)
        if needs_stage1_author(folder) and not authored:
            authored = True
            code = _run(
                [PY, "scripts/run_stage1_author.py", str(folder), "--wall-seconds", "500"],
                log,
                560,
            )
            _restore_queue(saved)
            if code == "TIMEOUT":
                return "TIMEOUT"
            code = _practice(folder, True, log, 1200)
            _restore_queue(saved)
            if code == "TIMEOUT":
                return "TIMEOUT"
            continue
        if needs_stage1_repair(folder) and not repaired:
            repaired = True
            if attach_unsupported_ats_cites(folder):
                code = _practice(folder, True, log, 1200)
                _restore_queue(saved)
                if code == "TIMEOUT":
                    return "TIMEOUT"
            if needs_stage1_repair(folder):
                _snapshot_pre_repair(folder)
                code = _run(
                    [PY, "scripts/build_stage1_repair_prompt.py", str(folder)],
                    log,
                    180,
                )
                _restore_queue(saved)
                if code == "TIMEOUT":
                    return "TIMEOUT"
                prompt = folder / "stage1_repair_prompt.md"
                if prompt.is_file() and needs_stage1_repair(folder):
                    before = _repair_blocking(folder)
                    code = _run(
                        [PY, "scripts/run_stage1_repair.py", str(folder)],
                        log,
                        500,
                    )
                    _restore_queue(saved)
                    if code == "TIMEOUT":
                        return "TIMEOUT"
                    code = _practice(folder, True, log, 1200)
                    _restore_queue(saved)
                    if code == "TIMEOUT":
                        return "TIMEOUT"
                    after = _repair_blocking(folder)
                    if (
                        _stage1_still_failed(folder)
                        and _repair_findings_unchanged(before, after)
                        and _restore_pre_repair(folder)
                    ):
                        _block_further_repair(folder)
                        code = _practice(folder, True, log, 1200)
                        _restore_queue(saved)
                        if code == "TIMEOUT":
                            return "TIMEOUT"
                    elif _stage1_still_failed(folder) and not _repair_findings_unchanged(
                        before, after
                    ):
                        _release_repair_progress(folder)
            continue
        if is_ready_to_finalize(read_workflow_state(folder)):
            code = _run(
                [
                    PY,
                    "scripts/run_submission.py",
                    str(folder),
                    "--mode",
                    "practice",
                    "--finalize",
                ],
                log,
                300,
            )
            _restore_queue(saved)
            if code == "TIMEOUT":
                return "TIMEOUT"
            state = read_workflow_state(folder)
            return str(state.get("status") or "UNKNOWN")
        resume = (folder / "workflow_state.json").is_file()
        code = _practice(folder, resume, log, 1200)
        _restore_queue(saved)
        if code == "TIMEOUT":
            return "TIMEOUT"
        new_status = read_workflow_state(folder).get("status")
        if new_status == status and new_status not in (None, ""):
            return str(new_status)
    return str(read_workflow_state(folder).get("status") or "UNKNOWN")


def main() -> None:
    """Run every holdout folder until the call cap or the list ends."""
    os.environ["APPLYR_STAGE0_SUBSCRIPTION_ADAPTER"] = "1"
    os.environ.pop("APPLYR_STAGE0_CLOUD_LLM", None)
    os.environ.pop("APPLYR_STAGE2_AGY_RUBRIC", None)
    slugs = _holdout_slugs()
    OUT.mkdir(parents=True, exist_ok=True)
    saved = _snapshot_queue(slugs)
    by_status: dict[str, int] = {}
    stopped: str | None = None
    for slug in slugs:
        calls = BASELINE_CALLS + _call_count()
        if calls >= CALL_CAP - 11:
            stopped = "call_cap"
            break
        folder = OUT / slug
        existing = read_workflow_state(folder).get("status") if folder.is_dir() else None
        if existing in DONE or existing in {"NEEDS_DISPOSITION", "WAITING_FOR_INPUT", "FAILED"}:
            status = str(existing)
        else:
            try:
                status = _one(slug, saved)
            except Exception:
                status = "CRASH"
                crash_log = folder / "driver.log"
                crash_log.parent.mkdir(parents=True, exist_ok=True)
                with crash_log.open("ab") as handle:
                    handle.write(traceback.format_exc().encode("utf-8", errors="replace"))
            _restore_queue(saved)
        by_status[status] = by_status.get(status, 0) + 1
        _publish(by_status, BASELINE_CALLS + _call_count(), stopped)
    if stopped is None and sum(by_status.values()) == 60:
        stopped = "list_done"
    _publish(by_status, BASELINE_CALLS + _call_count(), stopped)


if __name__ == "__main__":
    main()
