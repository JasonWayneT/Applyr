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
    clean_company_field,
    sanitize,
    validate_row,
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


class TestCleanCompanyField(unittest.TestCase):
    def test_strips_trailing_title(self) -> None:
        self.assertEqual(
            clean_company_field("ESO Product Manager", "Product Manager"),
            "ESO",
        )
        self.assertEqual(sanitize("ESO"), "eso")
        self.assertEqual(
            sanitize(clean_company_field("ESO Product Manager", "Product Manager")),
            "eso",
        )
        self.assertNotEqual(sanitize("ESO Product Manager"), "eso")

    def test_strips_separated_and_at_forms(self) -> None:
        self.assertEqual(clean_company_field("ESO - Product Manager", "Product Manager"), "ESO")
        self.assertEqual(clean_company_field("ESO | Product Manager", "Product Manager"), "ESO")
        self.assertEqual(
            clean_company_field("Businessolver Product Manager Remote", "Product Manager (Remote)"),
            "Businessolver",
        )
        self.assertEqual(
            clean_company_field(
                "Velera Product Manager Shared Branch",
                "Product Manager - Shared Branch",
            ),
            "Velera",
        )
        self.assertEqual(
            clean_company_field(
                "Binance Product Manager Social Features Content",
                "Product Manager - Social Features (Content)",
            ),
            "Binance",
        )
        self.assertEqual(
            clean_company_field("ESO\nProduct Manager", "Product Manager"),
            "ESO",
        )

    def test_leaves_clean_company_alone(self) -> None:
        self.assertEqual(clean_company_field("ESO", "Product Manager"), "ESO")
        self.assertEqual(clean_company_field("Product Management Inc", "Product Manager"), "Product Management Inc")

    def test_title_only_company_is_empty(self) -> None:
        self.assertEqual(clean_company_field("Product Manager", "Product Manager"), "")
        ok, code = validate_row(
            {
                "Company": "Product Manager",
                "Position": "Product Manager",
                "URL": "https://example.test/eso",
                "Job Description": "Owns the platform roadmap for a B2B product used by enterprise teams. " * 8,
            }
        )
        self.assertFalse(ok)
        self.assertEqual(code, EMPTY_COMPANY)


if __name__ == "__main__":
    unittest.main()
