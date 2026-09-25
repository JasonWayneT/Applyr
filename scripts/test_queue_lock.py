#!/usr/bin/env python3
"""CR-119 per-slug OS lock tests.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_queue_lock -v
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from queue_lock import SlugLockUnavailable, acquire_slug_lock  # noqa: E402


class TestSlugLock(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.lock_dir = Path(self._tmpdir.name)

    def test_second_in_process_acquire_raises(self) -> None:
        with acquire_slug_lock("alpha", "w1", 1, lock_dir=self.lock_dir):
            with self.assertRaises(SlugLockUnavailable):
                with acquire_slug_lock("alpha", "w2", 2, lock_dir=self.lock_dir):
                    pass

    def test_live_child_holds_lock_then_releases_on_exit(self) -> None:
        child_code = r"""
import sys, time
sys.path.insert(0, sys.argv[1])
from queue_lock import acquire_slug_lock
with acquire_slug_lock("beta", "child", 1, lock_dir=sys.argv[2]):
    sys.stdout.write("held\n")
    sys.stdout.flush()
    time.sleep(float(sys.argv[3]))
"""
        proc = subprocess.Popen(
            [sys.executable, "-c", child_code, os.path.dirname(__file__), str(self.lock_dir), "8"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            line = ""
            assert proc.stdout is not None
            deadline = time.time() + 8
            while time.time() < deadline:
                if proc.poll() is not None:
                    stderr = proc.stderr.read() if proc.stderr else ""
                    self.fail(f"child exited early: {proc.returncode} {stderr}")
                line = proc.stdout.readline()
                if line.strip() == "held":
                    break
            self.assertEqual(line.strip(), "held")
            with self.assertRaises(SlugLockUnavailable):
                with acquire_slug_lock("beta", "parent", 2, lock_dir=self.lock_dir):
                    pass
            proc.kill()
            proc.wait(timeout=5)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()
        acquired = False
        last_exc: Exception | None = None
        for _ in range(20):
            try:
                with acquire_slug_lock("beta", "parent", 3, lock_dir=self.lock_dir) as lock:
                    self.assertEqual(lock.payload["slug"], "beta")
                    acquired = True
                    break
            except SlugLockUnavailable as exc:
                last_exc = exc
                time.sleep(0.05)
        self.assertTrue(acquired, f"lock not acquirable after child exit: {last_exc}")


if __name__ == "__main__":
    unittest.main()
