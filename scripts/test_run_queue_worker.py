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
        self.assertEqual(len(self.cmds), 1)

    def test_waiting_for_llm_with_prompt_runs_author_then_resume(self) -> None:
        _seed(self.conn, "authorco")
        folder = self._write_state("authorco", "WAITING_FOR_LLM", "stage1")
        (folder / "authoring_prompt.md").write_text("PROMPT", encoding="utf-8")
        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=self._spawn,
            heartbeat_s=0.05,
        )
        row = pq.get_row(self.conn, "authorco")
        assert row is not None
        self.assertEqual(row["status"], "paused")
        self.assertEqual(row["last_workflow_status"], "WAITING_FOR_LLM")
        self.assertEqual(len(self.cmds), 3)
        self.assertTrue(self.cmds[0][-1] == "--resume")
        self.assertIn("run_stage1_author.py", self.cmds[1][1])
        self.assertEqual(self.cmds[1][-1], str(folder))
        self.assertTrue(self.cmds[2][-1] == "--resume")

    def test_waiting_for_llm_with_resume_does_not_author(self) -> None:
        _seed(self.conn, "hasresume")
        folder = self._write_state("hasresume", "WAITING_FOR_LLM", "stage1")
        (folder / "authoring_prompt.md").write_text("PROMPT", encoding="utf-8")
        (folder / "Resume.md").write_text("# Name\n", encoding="utf-8")
        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=self._spawn,
            heartbeat_s=0.05,
        )
        self.assertEqual(len(self.cmds), 1)
        self.assertNotIn("run_stage1_author.py", " ".join(self.cmds[0]))

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

    def test_conversion_risk_maps_paused_reason(self) -> None:
        mapped, reason, mirror = worker.map_run_result(
            {
                "status": "WAITING_FOR_INPUT",
                "active_stage": "stage0",
                "metadata": {"pause_kind": pq.PAUSE_KIND_CONVERSION_RISK},
            }
        )
        self.assertEqual(mapped, "paused")
        self.assertEqual(reason, pq.PAUSED_REASON_CONVERSION_RISK)
        self.assertEqual(mirror, "WAITING_FOR_INPUT")

    def test_stage2_rubric_hook_off_without_env(self) -> None:
        folder = self.pending / "scoreco"
        folder.mkdir()
        (folder / "Resume.md").write_text("resume\n", encoding="utf-8")
        (folder / "CoverLetter.md").write_text("cover\n", encoding="utf-8")
        self.assertFalse(worker.needs_stage2_rubric(folder))

    def test_stage2_rubric_hook_skips_when_scorecard_current(self) -> None:
        import hashlib

        folder = self.pending / "scored"
        folder.mkdir()
        resume = b"# Name\nresume\n"
        cover = b"Dear Hiring Manager,\n"
        (folder / "Resume.md").write_bytes(resume)
        (folder / "CoverLetter.md").write_bytes(cover)
        reviews = folder / "reviews"
        reviews.mkdir()
        (reviews / "rubric_scorecard.json").write_text(
            json.dumps(
                [
                    {
                        "document_sha256": {
                            "resume": hashlib.sha256(resume).hexdigest(),
                            "cover_letter": hashlib.sha256(cover).hexdigest(),
                        }
                    }
                ]
            ),
            encoding="utf-8",
        )
        with unittest.mock.patch.dict(os.environ, {"APPLYR_STAGE2_AGY_RUBRIC": "1"}):
            self.assertFalse(worker.needs_stage2_rubric(folder))

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
        self.assertEqual(len(self.cmds), 1)

    def test_stage1_verify_fail_with_resume_runs_repair_then_resume(self) -> None:
        _seed(self.conn, "repairco")
        folder = self._write_state("repairco", "FAILED", "stage1")
        state = {
            "status": "FAILED",
            "active_stage": "stage1",
            "stages": {"stage1": {"status": "FAILED"}},
        }
        (folder / "workflow_state.json").write_text(json.dumps(state), encoding="utf-8")
        (folder / "Resume.md").write_text("# Name\n", encoding="utf-8")

        def spawn(cmd: list[str]) -> ImmediateHandle:
            self.cmds.append(cmd)
            if any(part.endswith("build_stage1_repair_prompt.py") for part in cmd):
                (folder / "stage1_repair_prompt.md").write_text("repair\n", encoding="utf-8")
            return ImmediateHandle(cmd)

        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=spawn,
            heartbeat_s=0.05,
        )
        joined = [" ".join(cmd) for cmd in self.cmds]
        self.assertEqual(len(self.cmds), 4)
        self.assertIn("run_submission.py", joined[0])
        self.assertIn("build_stage1_repair_prompt.py", joined[1])
        self.assertIn("run_stage1_repair.py", joined[2])
        self.assertTrue(self.cmds[3][-1] == "--resume")

    def test_worse_repair_restores_previous_draft_and_resumes(self) -> None:
        _seed(self.conn, "repairco")
        folder = self._write_state("repairco", "FAILED", "stage1")
        state = {
            "status": "FAILED",
            "active_stage": "stage1",
            "stages": {"stage1": {"status": "FAILED"}},
        }
        (folder / "workflow_state.json").write_text(json.dumps(state), encoding="utf-8")
        (folder / "Resume.md").write_text("original draft\n", encoding="utf-8")

        def spawn(cmd: list[str]) -> ImmediateHandle:
            self.cmds.append(cmd)
            if any(part.endswith("build_stage1_repair_prompt.py") for part in cmd):
                (folder / "stage1_repair_prompt.md").write_text("repair\n", encoding="utf-8")
            if any(part.endswith("run_stage1_repair.py") for part in cmd):
                (folder / "Resume.md").write_text("rewritten draft\n", encoding="utf-8")
            return ImmediateHandle(cmd)

        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=spawn,
            heartbeat_s=0.05,
        )
        self.assertEqual((folder / "Resume.md").read_text(encoding="utf-8"), "original draft\n")
        self.assertEqual(len(self.cmds), 5)
        self.assertTrue(self.cmds[4][-1] == "--resume")
        repair_state = json.loads(
            (folder / "stage1_repair_state.json").read_text(encoding="utf-8")
        )
        self.assertEqual(repair_state["last_outcome"], "no_progress_blocking")

    def test_stage2_complete_stage3_ready_tries_to_save_then_stops(self) -> None:
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
        self.assertEqual(row["paused_reason"], pq.PAUSED_REASON_FINALIZE_FAILED)
        self.assertIsNone(row["locked_by"])
        self.assertIsNone(row["lease_expires_at"])
        self.assertEqual(row["last_workflow_status"], pq.MIRROR_READY_TO_FINALIZE)
        self.assertEqual(row["last_stage"], "stage3")
        self.assertTrue(any(cmd[-1] == "--finalize" for cmd in self.cmds))
        again = pq.claim_pack("w1", size=8, conn=self.conn, data_root=self.data)
        self.assertEqual(again, [])

    def test_finished_packet_is_marked_done_when_save_completes(self) -> None:
        _seed(self.conn, "savedco")
        folder = self.pending / "savedco"
        folder.mkdir(parents=True)
        state = {
            "status": "IN_PROGRESS",
            "active_stage": "stage3",
            "stages": {
                "stage2": {"status": "COMPLETE"},
                "stage3": {"status": "READY"},
            },
        }
        (folder / "workflow_state.json").write_text(json.dumps(state), encoding="utf-8")

        def spawn(cmd: list[str]) -> ImmediateHandle:
            self.cmds.append(cmd)
            if cmd[-1] == "--finalize":
                done = dict(state)
                done["status"] = "COMPLETE"
                (folder / "workflow_state.json").write_text(
                    json.dumps(done), encoding="utf-8"
                )
            return ImmediateHandle(cmd)

        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=spawn,
            heartbeat_s=0.05,
        )
        row = pq.get_row(self.conn, "savedco")
        assert row is not None
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["last_workflow_status"], "COMPLETE")

    def test_finalize_already_done_does_not_transition_again(self) -> None:
        _seed(self.conn, "twice")
        folder = self._write_state("twice", "COMPLETE", "stage3")
        leased = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)[0]
        running = pq.transition(
            "twice",
            "in_progress",
            worker="w1",
            token=int(leased["fencing_token"]),
            conn=self.conn,
        )
        pq.transition(
            "twice",
            "done",
            worker="w1",
            token=int(running["fencing_token"]),
            conn=self.conn,
            last_workflow_status="COMPLETE",
        )
        row = worker.apply_run_result(
            "twice",
            conn=self.conn,
            worker="w1",
            token=int(running["fencing_token"]),
            data_root=self.data,
            original=folder,
            exit_code=0,
            finalize_attempted=True,
        )
        assert row is not None
        self.assertEqual(row["status"], "done")

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

    def test_already_handled_workflow_maps_to_done(self) -> None:
        """FR-365 / AC-474: ALREADY_HANDLED is a DONE_WORKFLOW status."""
        mapped, reason, mirror = worker.map_run_result({"status": "ALREADY_HANDLED"})
        self.assertEqual(mapped, "done")
        self.assertIsNone(reason)
        self.assertEqual(mirror, "ALREADY_HANDLED")

    def test_already_handled_run_pack_closes_queue(self) -> None:
        _seed(self.conn, "handledco")
        self._write_state("handledco", "ALREADY_HANDLED")
        worker.run_pack(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=self._spawn,
            heartbeat_s=0.05,
        )
        row = pq.get_row(self.conn, "handledco")
        assert row is not None
        self.assertEqual(row["status"], "done")
        self.assertEqual(row["last_workflow_status"], "ALREADY_HANDLED")


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


_JOBS_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT,
  company TEXT,
  title TEXT,
  url TEXT,
  status TEXT
);
"""


class TestCr123WorkerAlreadyHandled(WorkerHarness):
    """CR-123 Story 2.3: worker pre-invoke refuse (FR-363, AC-472)."""

    def setUp(self) -> None:
        super().setUp()
        self.conn.executescript(_JOBS_DDL)
        self.conn.commit()

    def _seed_applied_leased(self, slug: str, *, worker_id: str = "w1") -> dict:
        """Insert one synthetic Applied+ job, queue it, and lease it to worker_id."""
        from stage0_skip_ledger import normalize_url, posting_key

        company = f"Synth Worker {slug} Co"
        title = "Platform Product Manager"
        url = f"https://example.test/jobs/{slug}"
        pq.upsert_queued(
            self.conn,
            slug=slug,
            company=company,
            title=title,
            url=url,
            url_key=normalize_url(url),
            posting_key=posting_key(company, title),
            networking_contacts_raw=None,
            source_sha256=None,
            source_line=None,
            folder_root="pending_review",
        )
        self.conn.execute(
            "INSERT INTO jobs (id, company, title, url, status) VALUES (?, ?, ?, ?, ?)",
            (slug, company, title, url, "Applied"),
        )
        self.conn.commit()
        return pq.transition(slug, "leased", worker=worker_id, token=0, conn=self.conn)

    def test_applied_plus_leased_is_done_and_spawn_never_invoked(self) -> None:
        leased = self._seed_applied_leased("synth_worker_applied")
        self.assertEqual(leased["status"], "leased")
        self.assertEqual(leased["locked_by"], "w1")
        outcome = worker.process_slug(
            leased,
            worker="w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            spawn=self._spawn,
            heartbeat_s=0.05,
        )
        self.assertEqual(outcome, "already_handled")
        self.assertEqual(self.cmds, [])
        after = pq.get_row(self.conn, "synth_worker_applied")
        assert after is not None
        self.assertEqual(after["status"], "done")


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


class TestDrain(WorkerHarness):
    def test_drain_takes_the_next_batch_until_nothing_can_move(self) -> None:
        _seed(self.conn, "firstco")
        _seed(self.conn, "secondco")
        self._write_state("firstco", "WAITING_FOR_LLM", "stage1")
        self._write_state("secondco", "WAITING_FOR_LLM", "stage1")
        summaries = worker.drain_until_idle(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            size=1,
            spawn=self._spawn,
            heartbeat_s=0.05,
        )
        claimed = [slug for summary in summaries for slug in summary["claimed"]]
        self.assertEqual(claimed, ["firstco", "secondco"])
        self.assertEqual(summaries[-1]["claimed"], [])
        self.assertEqual(pq.get_row(self.conn, "firstco")["status"], "paused")
        self.assertEqual(pq.get_row(self.conn, "secondco")["status"], "paused")

    def test_once_stops_while_another_job_can_still_move(self) -> None:
        _seed(self.conn, "firstco")
        _seed(self.conn, "secondco")
        self._write_state("firstco", "WAITING_FOR_LLM", "stage1")
        self._write_state("secondco", "WAITING_FOR_LLM", "stage1")
        summaries = worker.drain_until_idle(
            "w1",
            conn=self.conn,
            data_root=self.data,
            lock_dir=self.lock_dir,
            size=1,
            spawn=self._spawn,
            heartbeat_s=0.05,
            once=True,
        )
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["claimed"], ["firstco"])
        self.assertEqual(pq.get_row(self.conn, "secondco")["status"], "queued")

    def test_release_returns_unstarted_rows_before_the_next_run(self) -> None:
        _seed(self.conn, "heldco")
        leased = pq.claim_pack("w1", size=1, conn=self.conn, data_root=self.data)
        self.assertEqual(leased[0]["status"], "leased")
        released = pq.release("w1", conn=self.conn)
        self.assertEqual([row["slug"] for row in released], ["heldco"])
        self.assertEqual(pq.get_row(self.conn, "heldco")["status"], "queued")


class TestRepairRollback(unittest.TestCase):
    """A repair that changes the blocking findings is kept. FR-375."""

    def test_unchanged_findings_roll_back(self) -> None:
        self.assertTrue(
            worker._repair_findings_unchanged(
                ["FAIL [optimization_bar]: required evidence unused"],
                ["FAIL [optimization_bar]: required evidence unused"],
            )
        )

    def test_changed_findings_are_kept(self) -> None:
        self.assertFalse(
            worker._repair_findings_unchanged(
                ["FAIL [optimization_bar]: required evidence unused"],
                ["FAIL [stage1_quality]: summary stacks proof sentences"],
            )
        )


if __name__ == "__main__":
    unittest.main()
