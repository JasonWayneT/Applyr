#!/usr/bin/env python3
"""Cluster C item 12 — [Location] must trip R-009 / CL-009 placeholder checks."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drafting_errors import SelfCorrectionError
from quality_checker import check_and_repair_cover_letter, check_resume


_MIN_RESUME = """# Real Name
San Diego, CA | 555 | a@b.com | linkedin.com/in/x

## PROFESSIONAL SUMMARY
**Product Manager**
Sentence one here. Sentence two here. Sentence three here.

## PROFESSIONAL EXPERIENCE
### Product Manager | Cision | September 2021 - January 2026
[Location]
* Did a thing with a metric of 40%.

### Product Manager / Product Owner | Sterkly | February 2019 - August 2021
* Another bullet.

### Account Manager / Product Owner | Zero To Sixty | June 2017 - January 2019
* Another bullet.

## EDUCATION
Degree line here
"""

_MIN_COVER = """# Real Name
San Diego, CA | 555 | a@b.com | linkedin.com/in/x

Dear Hiring Manager,

I want to discuss how my work maps to this role and thank you for your consideration of the application materials included here for review today with care.

Best regards,

Real Name
"""


class TestLocationPlaceholder(unittest.TestCase):
    def test_resume_location_placeholder_fails_r009(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Resume.md"
            path.write_text(_MIN_RESUME, encoding="utf-8")
            with self.assertRaises(SelfCorrectionError) as ctx:
                check_resume(str(path))
            self.assertIn("R-009", str(ctx.exception))
            self.assertIn("[Location]", str(ctx.exception))

    def test_cover_letter_location_placeholder_fails_cl009(self):
        body = _MIN_COVER.replace(
            "I want to discuss",
            "I want to discuss work from [Location] and",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CoverLetter.md"
            path.write_text(body, encoding="utf-8")
            with self.assertRaises(SelfCorrectionError) as ctx:
                check_and_repair_cover_letter(str(path))
            self.assertIn("CL-009", str(ctx.exception))
            self.assertIn("[Location]", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
