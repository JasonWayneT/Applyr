#!/usr/bin/env python3
"""
Regression test: utils.py's header/placeholder helpers must preserve the real name's casing,
not force uppercase (2026-08-09, Jason's explicit call).

Why this exists: format_contact_header_block() used to render "# JASON TAYLOR" (force-uppercased)
with a blank line before the contact line -- a different convention than the CR-074 packet path
(apply_resume_header.py), which uses workExperience.md's real casing ("Jason Taylor") and
CLAUDE.md's documented Required Document Structure (name line, contact line on the very next
line, no blank line between). The inconsistency was latent until a real, already-CR-074-authored
submission (camunda) went through style_compliance_guard.py's normalize_resume_headers() for the
first time via the editor-save route and got its header silently rewritten to the wrong case --
confirmed live, reverted by hand on that folder; this test guards the underlying function so it
can't recur elsewhere.

Run with:
    python scripts/test_utils_header_casing.py
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import contact_placeholder_map, format_contact_header_block

_PROFILE = {
    "name": "Jason Taylor",
    "email": "[REDACTED_EMAIL]",
    "phone": "[REDACTED_PHONE]",
    "location": "San Diego, CA",
    "linkedin": "linkedin.com/in/redacted-linkedin-slug",
    "portfolio": "Taylorbuilt.me",
}


class TestHeaderCasingPreserved(unittest.TestCase):
    def test_header_block_preserves_real_casing(self):
        block = format_contact_header_block(_PROFILE)
        self.assertIn("# Jason Taylor", block)
        self.assertNotIn("JASON TAYLOR", block)

    def test_header_block_has_no_blank_line_before_contact(self):
        """CLAUDE.md's Required Document Structure: name line, contact line immediately after."""
        block = format_contact_header_block(_PROFILE)
        lines = block.split("\n")
        self.assertEqual(lines[0], "# Jason Taylor")
        self.assertEqual(lines[1], "San Diego, CA | [REDACTED_PHONE] | [REDACTED_EMAIL] | linkedin.com/in/redacted-linkedin-slug | Taylorbuilt.me")

    def test_placeholder_map_preserves_real_casing(self):
        placeholders = contact_placeholder_map(_PROFILE)
        self.assertEqual(placeholders["[Your Name]"], "Jason Taylor")
        self.assertEqual(placeholders["[Full Name]"], "Jason Taylor")
        self.assertEqual(placeholders["## [Your Name]"], "# Jason Taylor")
        for value in placeholders.values():
            self.assertNotEqual(value, "JASON TAYLOR")


if __name__ == "__main__":
    unittest.main(verbosity=2)
