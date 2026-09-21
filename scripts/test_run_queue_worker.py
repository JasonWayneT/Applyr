#!/usr/bin/env python3
"""CR-119 queue worker mapping, abort, and AC-444 tests.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_run_queue_worker -v
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pipeline_queue as pq  # noqa: E402
import run_queue_worker as worker  # noqa: E402
from queue_lock import SlugLockUnavailable, acquire_slug_lock  # noqa: E402


class ImmediateProc:
    def __init__(self) -> None:
        self.pid = 4242
        self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def poll(self) -> int:
        return 0

    def kill(self) -> None:
        return None


class ImmediateHandle(worker.RunnerHandle):
    def __init__(self, cmd: list[str]) -> None:
        super().__init__(proc=ImmediateProc())
        self.cmd = cmd


def _seed(conn: sqlite3.Connection, slug: str) -> None:
    pq.upsert_queued(
        conn,
        slug=slug,
        company=slug,
        title="PM",
        url=None,
        url_key=None,
        posting_key=f"{slug}||pm",
        networking_contacts_raw=None,
        source_sha256=None,
        source_line=None,
        folder_root="pending_review",
    )


class WorkerHarness(unittest.TestCase):
    def setUp(self) -> None:
        worker.reset_abort()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = Path(self._tmpdir.name)
        self.data = self.root / "data"
        self.lock_dir = self.data / "queue_locks"
        self.pending = self.data / "pending_review"
        self.pending.mkdir(parents=True)
        (self.data / "submissions").mkdir()
        (self.data / "archive" / "skipped").mkdir(parents=True)
        self.lock_dir.mkdir()
        self.db = self.root / "jobagent.sqlite"
        self.conn = pq.connect(self.db)
        self.cmds: list[list[str]] = []

    def tearDown(self) -> None:
        worker.reset_abort()
        self.conn.close()

    def _spawn(self, cmd: list[str]) -> ImmediateHandle:
        self.cmds.append(cmd)
        return ImmediateHandle(cmd)

    def _write_state(self, slug: str, status: str, stage: str = "stage0") -> Path:
        folder = self.pending / slug
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": status, "active_stage": stage}),
            encoding="utf-8",
        )
        return folder


class TestMapping(WorkerHarness):
    def test_waiting_for_llm_maps_to_paused_and_releases_lease(self) -> None:
        _seed(self.conn, "waitco")
        self._write_state("waitco", "WAITING_FOR_LLM", "stage1")
        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=self._spawn,
            heartbeat_s=0.05,
        )
        row = pq.get_row(self.conn, "waitco")
        assert row is not None
        self.assertEqual(row["status"], "paused")
        self.assertIsNone(row["locked_by"])
        self.assertEqual(row["last_workflow_status"], "WAITING_FOR_LLM")
        self.assertTrue(self.cmds[0][-1] == "--resume")
        self.assertEqual(self.cmds[0][-2], "waitco")

    def test_complete_maps_to_done(self) -> None:
        _seed(self.conn, "doneco")
        self._write_state("doneco", "COMPLETE")
        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=self._spawn,
            heartbeat_s=0.05,
        )
        row = pq.get_row(self.conn, "doneco")
        assert row is not None
        self.assertEqual(row["status"], "done")

    def test_needs_disposition_maps_to_paused(self) -> None:
        _seed(self.conn, "dispco")
        self._write_state("dispco", "NEEDS_DISPOSITION", "stage2")
        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=self._spawn,
            heartbeat_s=0.05,
        )
        self.assertEqual(pq.get_row(self.conn, "dispco")["status"], "paused")

    def test_waiting_for_input_maps_to_paused_and_releases_lease(self) -> None:
        _seed(self.conn, "agyco")
        self._write_state("agyco", "WAITING_FOR_INPUT", "stage0")
        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=self._spawn,
            heartbeat_s=0.05,
        )
        row = pq.get_row(self.conn, "agyco")
        assert row is not None
        self.assertEqual(row["status"], "paused")
        self.assertIsNone(row["locked_by"])
        self.assertEqual(row["last_workflow_status"], "WAITING_FOR_INPUT")

    def test_failed_maps_to_paused_and_releases_lease(self) -> None:
        _seed(self.conn, "failco")
        self._write_state("failco", "FAILED", "stage1")
        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=self._spawn,
            heartbeat_s=0.05,
        )
        row = pq.get_row(self.conn, "failco")
        assert row is not None
        self.assertEqual(row["status"], "paused")
        self.assertIsNone(row["locked_by"])
        self.assertEqual(row["last_workflow_status"], "FAILED")
        self.assertTrue(self.cmds[0][-1] == "--resume")

    def test_stage2_complete_stage3_ready_maps_to_ready_to_finalize(self) -> None:
        _seed(self.conn, "rentana")
        folder = self.pending / "rentana"
        folder.mkdir(parents=True)
        (folder / "workflow_state.json").write_text(
            json.dumps(
                {
                    "status": "IN_PROGRESS",
                    "active_stage": "stage3",
                    "stages": {
                        "stage2": {"status": "COMPLETE"},
                        "stage3": {"status": "READY"},
                    },
                }
            ),
            encoding="utf-8",
        )
        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=self._spawn,
            heartbeat_s=0.05,
        )
        row = pq.get_row(self.conn, "rentana")
        assert row is not None
        self.assertEqual(row["status"], "paused")
        self.assertEqual(row["paused_reason"], pq.PAUSED_REASON_READY_TO_FINALIZE)
        self.assertIsNone(row["locked_by"])
        self.assertIsNone(row["lease_expires_at"])
        self.assertEqual(row["last_workflow_status"], pq.MIRROR_READY_TO_FINALIZE)
        self.assertEqual(row["last_stage"], "stage3")

    def test_generic_in_progress_does_not_map_to_paused(self) -> None:
        _seed(self.conn, "midco")
        self._write_state("midco", "IN_PROGRESS", "stage2")
        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=self._spawn,
            heartbeat_s=0.05,
        )
        row = pq.get_row(self.conn, "midco")
        assert row is not None
        self.assertEqual(row["status"], "in_progress")
        self.assertIsNotNone(row["locked_by"])
        self.assertIsNone(row["paused_reason"])

    def test_first_run_omits_resume(self) -> None:
        _seed(self.conn, "freshco")
        (self.pending / "freshco").mkdir()
        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=self._spawn,
            heartbeat_s=0.05,
        )
        self.assertNotIn("--resume", self.cmds[0])
        self.assertEqual(self.cmds[0][-1], "freshco")

    def test_exit_code_is_not_the_mapping_key(self) -> None:
        _seed(self.conn, "skipco")
        self._write_state("skipco", "SKIPPED")

        class NonZero(ImmediateProc):
            def wait(self, timeout: float | None = None) -> int:
                self.returncode = 2
                return 2

        def spawn(cmd: list[str]) -> worker.RunnerHandle:
            self.cmds.append(cmd)
            return worker.RunnerHandle(proc=NonZero())

        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=spawn,
            heartbeat_s=0.05,
        )
        self.assertEqual(pq.get_row(self.conn, "skipco")["status"], "done")


class TestAbort(WorkerHarness):
    def test_abort_releases_unstarted_and_leaves_inflight_state(self) -> None:
        _seed(self.conn, "one")
        _seed(self.conn, "two")
        folder = self._write_state("one", "WAITING_FOR_LLM")
        inflight_state = (folder / "workflow_state.json").read_bytes()
        started = {"n": 0}

        def spawn(cmd: list[str]) -> ImmediateHandle:
            started["n"] += 1
            self.cmds.append(cmd)
            worker.request_abort()
            return ImmediateHandle(cmd)

        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=spawn,
            heartbeat_s=0.05,
        )
        self.assertEqual(started["n"], 1)
        self.assertEqual(pq.get_row(self.conn, "two")["status"], "queued")
        self.assertEqual(pq.get_row(self.conn, "one")["status"], "in_progress")
        self.assertEqual((folder / "workflow_state.json").read_bytes(), inflight_state)
        cmd = worker.build_runner_command("one", folder)
        self.assertEqual(cmd[-2:], ["one", "--resume"])
        self.assertTrue(cmd[-2] == "one")


class TestAc444(WorkerHarness):
    def test_second_worker_does_not_spawn_while_lock_held(self) -> None:
        _seed(self.conn, "race")
        w1 = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)[0]
        spawns: list[list[str]] = []

        def spawn(cmd: list[str]) -> ImmediateHandle:
            spawns.append(cmd)
            return ImmediateHandle(cmd)

        with acquire_slug_lock("race", "w1", w1["fencing_token"], lock_dir=self.lock_dir):
            self.conn.execute(
                "UPDATE pipeline_queue SET lease_expires_at = ? WHERE slug = ?",
                ("2000-01-01T00:00:00+00:00", "race"),
            )
            self.conn.commit()
            w2 = pq.claim_pack("w2", size=1, conn=self.conn, data_root=self.data)
            self.assertEqual(len(w2), 1)
            outcome = worker.process_slug(
                w2[0],
                worker="w2",
                conn=self.conn,
                data_root=self.data,
                lock_dir=self.lock_dir,
                spawn=spawn,
                heartbeat_s=0.05,
            )
            self.assertEqual(outcome, "lock_unavailable")
            self.assertEqual(spawns, [])
            self.assertTrue((self.lock_dir / "race.lock").exists())
        with acquire_slug_lock("race", "w2", w2[0]["fencing_token"], lock_dir=self.lock_dir):
            pass

    def test_terminateprocess_kills_job_child(self) -> None:
        if os.name != "nt":
            handle = worker.spawn_runner(
                [sys.executable, "-c", "import time; time.sleep(30)"]
            )
            child_pid = handle.pid
            holder = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                start_new_session=True,
            )
            # POSIX analogue is covered below via kill_tree on the handle.
            handle.kill_tree()
            holder.kill()
            holder.wait(timeout=5)
            deadline = time.time() + 5
            while time.time() < deadline and _pid_alive(child_pid):
                time.sleep(0.05)
            self.assertFalse(_pid_alive(child_pid))
            return

        holder_src = r"""
import sys, time
sys.path.insert(0, sys.argv[1])
from run_queue_worker import spawn_runner
handle = spawn_runner([sys.executable, "-c", "import time; time.sleep(60)"])
sys.stdout.write(f"ready {handle.pid}\n")
sys.stdout.flush()
time.sleep(60)
"""
        holder = subprocess.Popen(
            [sys.executable, "-c", holder_src, os.path.dirname(__file__)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert holder.stdout is not None
        line = ""
        deadline = time.time() + 10
        while time.time() < deadline:
            if holder.poll() is not None:
                err = holder.stderr.read() if holder.stderr else ""
                self.fail(f"holder exited early: {holder.returncode} {err}")
            line = holder.stdout.readline()
            if line.startswith("ready "):
                break
        self.assertTrue(line.startswith("ready "), line)
        child_pid = int(line.split()[1])
        self.assertTrue(_pid_alive(child_pid))
        _terminate_process(holder.pid)
        holder.wait(timeout=5)
        deadline = time.time() + 8
        while time.time() < deadline and _pid_alive(child_pid):
            time.sleep(0.05)
        self.assertFalse(_pid_alive(child_pid), "Job Object did not kill the child")
        if holder.stdout:
            holder.stdout.close()
        if holder.stderr:
            holder.stderr.close()


class TestUtf8ChildEnv(unittest.TestCase):
    """FIXQUEUE 2026-09-18 item #4: spawned pipeline child must run in
    Python UTF-8 mode regardless of the host's default locale codepage."""

    def test_utf8_child_env_sets_both_vars_without_mutating_ambient_environ(self) -> None:
        before = dict(os.environ)
        env = worker._utf8_child_env()
        self.assertEqual(env.get("PYTHONUTF8"), "1")
        self.assertEqual(env.get("PYTHONIOENCODING"), "utf-8")
        self.assertEqual(env.get("APPLYR_STAGE0_SUBSCRIPTION_ADAPTER"), "1")
        self.assertEqual(os.environ, before, "must not mutate the worker's own environ")

    def test_spawned_child_reports_utf8_mode_active(self) -> None:
        # spawn_runner() does not pipe the child's stdout (it inherits the
        # console), so the child reports its own encoding state to a temp
        # file instead of relying on captured output.
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "encoding_report.txt"
            script = (
                "import sys, pathlib; "
                "pathlib.Path(sys.argv[1]).write_text("
                "f'{sys.flags.utf8_mode}\\n{sys.stdout.encoding}\\n', encoding='utf-8')"
            )
            handle = worker.spawn_runner(
                [sys.executable, "-c", script, str(out_path)]
            )
            proc = handle.proc
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                raise
            self.assertTrue(out_path.exists(), "child did not run to completion")
            lines = out_path.read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(len(lines), 2, lines)
        self.assertEqual(lines[0].strip(), "1", "sys.flags.utf8_mode must be on in the child")
        self.assertEqual(lines[1].strip().lower(), "utf-8")


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        STILL_ACTIVE = 259
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _terminate_process(pid: int) -> None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        PROCESS_TERMINATE = 0x0001
        handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not kernel32.TerminateProcess(handle, 1):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel32.CloseHandle(handle)
        return
    os.kill(pid, 9)


if __name__ == "__main__":
    unittest.main()
