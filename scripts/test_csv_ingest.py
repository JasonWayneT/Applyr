#!/usr/bin/env python3
"""CR-119 csv_ingest helpers — AC-440 write_jd format contract.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_csv_ingest -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from csv_ingest import (  # noqa: E402
    EMPTY_COMPANY,
    ERROR_CODES,
    FILE_ENCODING,
    FILE_UNPARSEABLE,
    JD_TOO_SHORT,
    NO_DEDUP_KEY,
    write_jd,
)


class TestWriteJdFormat(unittest.TestCase):
    def test_write_jd_bytes_match_ac440(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            jd = "Owns the platform roadmap for a B2B product used by enterprise teams."
            path = write_jd(
                "synth_co",
                "https://example.test/jobs/42",
                "Product Manager",
                jd,
                dest_root=dest,
            )
            expected = (
                "URL: https://example.test/jobs/42\n"
                "\n"
                "Title: Product Manager\n"
                "\n"
                f"{jd}\n"
            )
            self.assertEqual(path.read_bytes(), expected.encode("utf-8"))

    def test_write_jd_omits_url_and_title_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            jd = "A job description body with no URL and no title header."
            path = write_jd("synth_co", "", "", jd, dest_root=dest)
            self.assertEqual(path.read_bytes(), f"{jd}\n".encode("utf-8"))

    def test_error_code_set_is_closed(self) -> None:
        self.assertEqual(
            ERROR_CODES,
            {
                EMPTY_COMPANY,
                JD_TOO_SHORT,
                NO_DEDUP_KEY,
                FILE_UNPARSEABLE,
                FILE_ENCODING,
            },
        )
        self.assertEqual(NO_DEDUP_KEY, "NO_DEDUP_KEY")


if __name__ == "__main__":
    unittest.main()
