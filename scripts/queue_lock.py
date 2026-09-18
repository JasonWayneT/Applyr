#!/usr/bin/env python3
"""CR-119 per-slug OS lock at data/queue_locks/{slug}.lock.

# Implements FR-343 / AC-444
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent
DEFAULT_LOCK_DIR = _REPO_ROOT / "data" / "queue_locks"

_HELD_SLUGS: set[str] = set()

if os.name == "nt":
    import msvcrt

    def _lock_fd(fd: int) -> None:
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _unlock_fd(fd: int) -> None:
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock_fd(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_fd(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


class SlugLockUnavailable(RuntimeError):
    """The OS lock for this slug is already held."""


class SlugLock:
    def __init__(self, handle: Any, path: Path, payload: dict[str, Any]) -> None:
        self.handle = handle
        self.path = path
        self.payload = payload

    def write_payload(self) -> None:
        encoded = json.dumps(self.payload, separators=(",", ":")).encode("utf-8")
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(encoded)
        self.handle.flush()

    def set_runner_pid(self, pid: int) -> None:
        self.payload["runner_pid"] = pid
        self.write_payload()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def acquire_slug_lock(
    slug: str,
    worker_id: str,
    fencing_token: int,
    lock_dir: Path | str | None = None,
) -> Iterator[SlugLock]:
    if slug in _HELD_SLUGS:
        raise SlugLockUnavailable(slug)
    directory = Path(lock_dir) if lock_dir is not None else DEFAULT_LOCK_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{slug}.lock"
    handle = open(path, "a+b")
    locked = False
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() < 1:
            handle.write(b" ")
            handle.flush()
        handle.seek(0)
        try:
            _lock_fd(handle.fileno())
        except OSError as exc:
            raise SlugLockUnavailable(slug) from exc
        locked = True
        _HELD_SLUGS.add(slug)
        lock = SlugLock(
            handle,
            path,
            {
                "worker_id": worker_id,
                "fencing_token": fencing_token,
                "runner_pid": None,
                "slug": slug,
                "acquired_at": _now(),
            },
        )
        lock.write_payload()
        yield lock
    finally:
        _HELD_SLUGS.discard(slug)
        if locked:
            try:
                handle.seek(0)
                _unlock_fd(handle.fileno())
            except OSError:
                pass
        handle.close()
