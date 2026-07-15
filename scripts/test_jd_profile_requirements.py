"""Tests for CR-068 Round 1: `requirements` section-extraction fix.

Pins the two validated, coupled fixes from CR-068's Decision (informed by CR-067's
hands-on root-cause diagnostic):

1. `_REQ_SECTION_RE`'s heading alternation gains two real-world heading phrases that
   were previously missing entirely: "who you are" (the requirements-equivalent
   heading for 3/4 of the originally-broken companies -- Ontra, Remote, Covideo) and
   "required education and experience" (OneStream's heading style).
2. `build_jd_profile_deterministic`'s `requirements` field construction is wired
   through `extract_req_section()` instead of scanning the raw, unscoped `jd_text` --
   fix 1 is inert on the real field output without this wiring change, so both
   mechanisms are pinned together against the real production entry point
   (`build_jd_profile_deterministic`), not an extracted helper, mirroring CR-066's
   `test_jd_profile_keywords.py` precedent.

The crafted JD in test (b) deliberately uses a layout Fixes 1+2 CAN bound (short,
blank-line-separated bullets under "Who You Are", followed by an ALL-CAPS next-section
heading) -- NOT a root-cause-3 layout (Title-Case boundary miss / no-blank-line
separator / >120-char bullets), which CR-068 Round 1 explicitly does not touch.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jd_tailoring import _REQ_SECTION_RE, build_jd_profile_deterministic


class TestReqSectionHeadingPhrases(unittest.TestCase):
    def test_matches_who_you_are(self):
        self.assertTrue(
            _REQ_SECTION_RE.search("Who You Are"),
            "_REQ_SECTION_RE must match a bare 'Who You Are' heading line",
        )

    def test_matches_required_education_and_experience(self):
        self.assertTrue(
            _REQ_SECTION_RE.search("Required Education and Experience"),
            "_REQ_SECTION_RE must match a bare 'Required Education and Experience' "
            "heading line",
        )


class TestRequirementsFieldRoutedThroughExtractReqSection(unittest.TestCase):
    def test_who_you_are_section_bullets_surface_not_earlier_boilerplate(self):
        # Layout Fixes 1+2 CAN bound: blank-line-separated, short (<120-char) bullets,
        # bounded by an ALL-CAPS next-section heading -- deliberately avoids the
        # root-cause-3 layouts (Title-Case boundary / no-separator / long bullets)
        # that CR-068 Round 1 does not touch.
        jd_text = (
            "Acme Corp is hiring a Senior Product Manager.\n"
            "\n"
            "Location: Remote, USA\n"
            "Employment Type: Full-Time\n"
            "Benefits Offered: Vision, Medical, Dental, 401K\n"
            "\n"
            "Who You Are\n"
            "\n"
            "5+ years of product management experience in B2B SaaS\n"
            "Strong track record of shipping complex platform features\n"
            "Comfortable partnering directly with engineering and design\n"
            "\n"
            "WHAT WE OFFER\n"
            "\n"
            "Competitive salary and comprehensive benefits package\n"
        )
        profile = build_jd_profile_deterministic(jd_text)
        joined = " ".join(profile.requirements)

        self.assertIn(
            "5+ years of product management experience in B2B SaaS",
            profile.requirements,
            "requirements must capture the real 'Who You Are' bullets; got: %r"
            % (profile.requirements,),
        )
        self.assertNotIn("Location: Remote, USA", profile.requirements)
        self.assertNotIn(
            "Benefits Offered: Vision, Medical, Dental, 401K", profile.requirements
        )
        self.assertNotIn(
            "Competitive salary and comprehensive benefits package", joined
        )


class TestRequirementsLineLengthCapRaisedTo250(unittest.TestCase):
    """CR-068 Round 2: the requirements line-length cap moves from 120 to 250
    (both the upper-bound check and the store-slice), so real requirement bullets
    in the 121-250 char range are kept, while multi-sentence paragraph-boilerplate
    (>250 chars) is still dropped entirely -- pins that the cap was *raised*, not
    *removed*.
    """

    def test_150_to_200_char_real_bullet_is_kept(self):
        # A genuine, single-sentence requirement bullet in the 150-200 char range
        # (root-cause-3 layout: previously dropped entirely by the 120-char cap).
        long_bullet = (
            "Proven experience owning complex, multi-phase B2B SaaS product roadmaps "
            "end to end, from discovery through launch, in close partnership with "
            "engineering and design teams."
        )
        self.assertTrue(150 <= len(long_bullet) <= 200, len(long_bullet))
        jd_text = (
            "Acme Corp is hiring a Senior Product Manager.\n"
            "\n"
            "Who You Are\n"
            "\n"
            f"{long_bullet}\n"
            "Comfortable partnering directly with engineering and design\n"
            "\n"
            "WHAT WE OFFER\n"
            "\n"
            "Competitive salary and comprehensive benefits package\n"
        )
        profile = build_jd_profile_deterministic(jd_text)
        self.assertIn(
            long_bullet,
            profile.requirements,
            "a genuine 150-200-char requirement bullet must now be kept "
            "(was dropped at the old 120-char cap); got: %r" % (profile.requirements,),
        )

    def test_over_250_char_paragraph_boilerplate_still_dropped(self):
        # Multi-sentence "about the company" style paragraph boilerplate, well
        # over 250 chars -- must remain excluded even after the cap raise, proving
        # the cap was raised (to a finite bound), not removed entirely.
        boilerplate_paragraph = (
            "About the company: Acme Corp is a fast-growing, venture-backed B2B "
            "SaaS company on a mission to transform how modern enterprises manage "
            "their supply chains, and we are proud to have been recognized as a "
            "great place to work by multiple industry publications this year."
        )
        self.assertGreater(len(boilerplate_paragraph), 250)
        jd_text = (
            "Acme Corp is hiring a Senior Product Manager.\n"
            "\n"
            "Who You Are\n"
            "\n"
            f"{boilerplate_paragraph}\n"
            "Comfortable partnering directly with engineering and design\n"
            "\n"
            "WHAT WE OFFER\n"
            "\n"
            "Competitive salary and comprehensive benefits package\n"
        )
        profile = build_jd_profile_deterministic(jd_text)
        self.assertNotIn(
            boilerplate_paragraph,
            profile.requirements,
            ">250-char paragraph boilerplate must still be dropped after the cap "
            "raise; got: %r" % (profile.requirements,),
        )


if __name__ == "__main__":
    unittest.main()
