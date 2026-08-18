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

# Fake fixture data (2026-08-19) -- this file is a public tracked test, not a real contact
# record. Any real name/email/phone/LinkedIn belongs only in the gitignored workExperience.md,
# per AGENTS.md's PII rule; a prior version of this fixture used real values and failed
# scripts/audit_public_repo.py's public-repo PII scan. Only the casing behavior under test
# matters here, so a fake mixed-case name exercises the same code path.
_PROFILE = {
    "name": "Alex Example",
    "email": "alex.example@example.com",
    "phone": "555-010-1234",
    "location": "San Diego, CA",
    "linkedin": "linkedin.com/in/alexexample",
    "portfolio": "alexexample.dev",
}


class TestHeaderCasingPreserved(unittest.TestCase):
    def test_header_block_preserves_real_casing(self):
        block = format_contact_header_block(_PROFILE)
        self.assertIn("# Alex Example", block)
        self.assertNotIn("ALEX EXAMPLE", block)

    def test_header_block_has_no_blank_line_before_contact(self):
        """CLAUDE.md's Required Document Structure: name line, contact line immediately after."""
        block = format_contact_header_block(_PROFILE)
        lines = block.split("\n")
        self.assertEqual(lines[0], "# Alex Example")
        self.assertEqual(lines[1], "San Diego, CA | 555-010-1234 | alex.example@example.com | linkedin.com/in/alexexample | alexexample.dev")

    def test_placeholder_map_preserves_real_casing(self):
        placeholders = contact_placeholder_map(_PROFILE)
        self.assertEqual(placeholders["[Your Name]"], "Alex Example")
        self.assertEqual(placeholders["[Full Name]"], "Alex Example")
        self.assertEqual(placeholders["## [Your Name]"], "# Alex Example")
        for value in placeholders.values():
            self.assertNotEqual(value, "ALEX EXAMPLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
