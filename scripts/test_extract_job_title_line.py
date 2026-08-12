#!/usr/bin/env python3
"""Regression: extract_job_title_line must not finalize JD chrome as the role title."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seniority_gate import extract_job_title_line, is_implausible_job_title


LEAFLINK_SNIPPET = """URL: https://builtin.com/job/product-manager/10046894

About LeafLink

LeafLink is the largest unified B2B cannabis platform, providing licensed cannabis businesses a suite of tools to manage their business more effectively, sell or order from their favorite brands and accelerate growth.

The Role

LeafLink is seeking a Product Manager to help define and deliver the next generation of products that power cannabis commerce.
"""

CAMUNDA_SNIPPET = """URL: https://jobs.ashbyhq.com/camunda/example

Register Here!

Camunda is the enterprise platform for agentic orchestration.

About The Role

We are seeking a talented and technically proficient Senior Product Manager to lead the development and evolution of our Core Platform.
"""


class ExtractJobTitleLineTests(unittest.TestCase):
    def test_rejects_known_chrome(self):
        for junk in ("The Role", "Register Here!", "Apply Now", "Job Summary"):
            self.assertTrue(is_implausible_job_title(junk), junk)
        self.assertFalse(is_implausible_job_title("Product Manager"))
        self.assertFalse(is_implausible_job_title("Senior Product Manager"))

    def test_leaflink_skips_the_role_header(self):
        title = extract_job_title_line(LEAFLINK_SNIPPET)
        self.assertEqual(title.lower(), "product manager")
        self.assertFalse(is_implausible_job_title(title))

    def test_camunda_skips_register_here_cta(self):
        title = extract_job_title_line(CAMUNDA_SNIPPET)
        self.assertIn("product manager", title.lower())
        self.assertIn("senior", title.lower())
        self.assertFalse(is_implausible_job_title(title))

    def test_explicit_title_header_wins(self):
        jd = "Title: Sr Product Manager\n\nThe Role\n\nWe build software."
        self.assertEqual(extract_job_title_line(jd), "Sr Product Manager")

    def test_compugroup_slogan_extracts_embedded_pm(self):
        jd = (
            "URL: https://cgm.wd3.myworkdayjobs.com/de-DE/cgm/job/Remote/"
            "Product-Manager_JR109379-1?source=LinkedIn\n\n"
            "Create the future of e-health together with us by becoming a Product Manager\n\n"
            "At CompuGroup Medical we have the mission of building ground-breaking solutions.\n"
        )
        slogan = "Create the future of e-health together with us by becoming a Product Manager"
        self.assertTrue(is_implausible_job_title(slogan))
        title = extract_job_title_line(jd)
        self.assertEqual(title.lower(), "product manager")
        self.assertFalse(is_implausible_job_title(title))

    def test_rejects_qualification_lead_line(self):
        junk = "Proven ability to lead teams and work in a highly collaborative environment"
        self.assertTrue(is_implausible_job_title(junk))

    def test_pinterest_falls_back_to_url_slug(self):
        jd = (
            "URL: https://www.pinterestcareers.com/jobs/7901910/"
            "product-manager-ii-content-compliance/?gh_src=dv1g0b1\n\n"
            "About Pinterest\n\n"
            "Proven ability to lead teams and work in a highly collaborative environment\n"
        )
        title = extract_job_title_line(jd)
        self.assertIn("product manager", title.lower())
        self.assertIn("ii", title.lower())
        self.assertFalse(is_implausible_job_title(title))


if __name__ == "__main__":
    unittest.main()
