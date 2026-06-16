"""Tests for conversion framing guards (CR-050 / FR-248, FR-249)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from conversion_framing import (
    enforce_conversion_framing,
    ensure_sterkly_narrative_pass,
)
from resume_conversion_eval import check_sterkly_narrative_coherence


def _fallback(_text: str) -> str:
    return _text


class TestSterklyContextEnforcement(unittest.TestCase):
    def test_stripe_style_bullets_gain_context(self):
        valid = {
            "ACC-203-BUS": (
                "Protected an estimated $1M-$3M in at-risk product revenue by removing "
                "dependency on unreliable third-party vendors for software certificate delivery."
            ),
            "ACC-203-TECH": (
                "Internalized certificate procurement to reduce delivery lead times and "
                "save approximately $100 per certificate."
            ),
            "ACC-203-OPS": (
                "Resolved a critical distribution bottleneck for a macOS security product "
                "by architecting an in-house browser extension certificate procurement workflow."
            ),
            "ACC-202-DELIVERY": (
                "Led product coordination for a team of 5-8 developers, translating technical "
                "workflow requirements into prioritized delivery plans and acceptance criteria."
            ),
        }
        bullets = {
            "ACC-203-BUS": valid["ACC-203-BUS"],
            "ACC-203-TECH": valid["ACC-203-TECH"],
            "ACC-203-OPS": valid["ACC-203-OPS"],
        }
        out = ensure_sterkly_narrative_pass(bullets, valid, "platform reliability PM", _fallback)
        texts = list(out.values())
        self.assertTrue(
            any("developers" in t.lower() or "5-8" in t for t in texts),
            "Expected PM context bullet after enforcement",
        )

    def test_assembled_resume_passes_cw012(self):
        valid = {
            "ACC-203-BUS": (
                "Protected an estimated $1M-$3M in at-risk product revenue by removing "
                "dependency on unreliable third-party vendors for software certificate delivery."
            ),
            "ACC-203-TECH": (
                "Internalized certificate procurement to reduce delivery lead times and "
                "save approximately $100 per certificate."
            ),
            "ACC-203-OPS": (
                "Resolved a critical distribution bottleneck for a macOS security product "
                "by architecting an in-house browser extension certificate procurement workflow."
            ),
            "ACC-202-DELIVERY": (
                "Led product coordination for a team of 5-8 developers, translating technical "
                "workflow requirements into prioritized delivery plans and acceptance criteria."
            ),
        }
        bullets = dict(valid)
        del bullets["ACC-202-DELIVERY"]
        bullets = enforce_conversion_framing(
            {k: bullets[k] for k in ("ACC-203-BUS", "ACC-203-TECH", "ACC-203-OPS")},
            valid,
            "platform PM",
            _fallback,
        )
        resume = (
            "# JOHN DOE\n\n## PROFESSIONAL SUMMARY\n"
            "Product Manager with 6+ years. Experienced partnering with engineering teams. "
            "Known for translating complex constraints into prioritized roadmaps.\n\n"
            "## PROFESSIONAL EXPERIENCE\n\n"
            "### Product Manager | Cision | 2021 - 2026\nRemote\n\n* Cision bullet.\n\n"
            "### Product Manager | Sterkly | 2019 - 2021\nSan Diego, CA\n\n"
        )
        for text in bullets.values():
            resume += f"* {text}\n"
        issues = check_sterkly_narrative_coherence(resume)
        self.assertEqual(issues, [], issues)


if __name__ == "__main__":
    unittest.main()
