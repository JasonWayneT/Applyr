"""Tests for import_csv_to_submissions.py's Windows console encoding fix.

Added 2026-08-18 -- this script crashed with UnicodeEncodeError on a real run
(Windows console cp1252 codec, a skip-reason string containing a non-ASCII arrow
character) and had zero test coverage. The fix (reconfiguring stdout/stderr to
utf-8 with errors="replace" at import time) had nothing regression-testing it.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def test_stdout_and_stderr_reconfigured_to_utf8():
    """Note: pytest's own capsys fixture replaces sys.stdout/stderr with a
    capture stream that tolerates unicode regardless of the real console
    codepage -- it can't reproduce the actual Windows cp1252 crash this fix
    addresses (confirmed directly: a real cp1252-wrapped TextIOWrapper does
    still raise UnicodeEncodeError on the same arrow character). This test
    only confirms the reconfigure call itself ran and took effect; the real
    crash reproduction (PYTHONIOENCODING unset, real console, exit code 0)
    was verified directly outside pytest, not here."""
    import import_csv_to_submissions  # noqa: F401  (import triggers the reconfigure)

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "encoding"):
            assert stream.encoding.lower().replace("-", "") == "utf8"
