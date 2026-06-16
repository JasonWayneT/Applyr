"""Tests for company display name resolution (CR-048 / FR-103)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from company_slug import company_name_from_jd, resolve_company_display_name


class TestCompanyDisplayName(unittest.TestCase):
    def test_company_name_from_jd_first_line(self):
        jd = "CVS Health\nJobs\nProduct Manager\nJob Posted 5 Days Ago\n"
        self.assertEqual(company_name_from_jd(jd), "CVS Health")

    def test_resolve_from_original_jd_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            jd_path = os.path.join(tmp, "Original_JD.txt")
            with open(jd_path, "w", encoding="utf-8") as f:
                f.write("DAT Freight & Analytics\nProduct Manager\n")
            name = resolve_company_display_name(
                "dat_freight_analytics",
                company_folder=tmp,
            )
            self.assertEqual(name, "DAT Freight & Analytics")

    def test_slug_fallback_when_no_sources(self):
        self.assertEqual(
            resolve_company_display_name("cvs_health"),
            "Cvs Health",
        )


if __name__ == "__main__":
    unittest.main()
