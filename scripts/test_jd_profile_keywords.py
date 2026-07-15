"""Tests for CR-066: build_jd_profile_deterministic's `keywords` field, frequency-sorted
(alphabetically tie-broken) instead of alphabetical.

Pins the exact mechanism from CR-066's Decision item 1: same [a-z]{5,} length filter, same
5-word stopword set, same _jd_body_for_themes() source text, same [:12] cutoff -- only the
sort key (descending in-body frequency, alphabetical tie-break) changes. Asserts directly
against build_jd_profile_deterministic()'s real output, not an extracted helper (CR-066
tracker Open Question 1 resolution), so it fails if the production path reverts to
alphabetical sorting or silently changes the stopword set / length filter / cutoff.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jd_tailoring import build_jd_profile_deterministic


class TestJdProfileKeywordsFrequencySort(unittest.TestCase):
    def test_frequent_defining_noun_outranks_alphabetically_earlier_rare_word(self):
        # "identity" (defining, repeated) must outrank "adoption" (generic, appears once)
        # even though "adoption" sorts alphabetically before "identity". Alphabetical
        # selection would put "adoption" ahead; frequency selection must not.
        jd_text = (
            "We care about adoption of the platform. Our identity platform needs "
            "identity focus, identity policy, and identity ownership."
            # trailing filler pushes the 72%-of-text theme-source cutoff
            # (_jd_body_for_themes) past all real content above, instead of
            # truncating mid-word, so the assertions below test frequency
            # ranking, not an incidental truncation artifact.
            + " zzzz" * 40
        )
        profile = build_jd_profile_deterministic(jd_text)
        self.assertIn("identity", profile.keywords)
        self.assertIn("adoption", profile.keywords)
        self.assertLess(
            profile.keywords.index("identity"),
            profile.keywords.index("adoption"),
            "frequency-sorted keywords must rank the more frequent, defining term "
            "('identity') ahead of a less frequent, alphabetically-earlier term "
            "('adoption'); got: %r" % (profile.keywords,),
        )

    def test_ties_broken_alphabetically(self):
        # "amber" and "bunch" and "cabin" each appear exactly once (frequency tie);
        # alphabetical tie-break must order them a < b < c relative to each other.
        jd_text = "cabin bunch amber cabin bunch amber cabin bunch amber"
        # each word appears 3 times -- true 3-way tie -- so tie-break must be alphabetical
        profile = build_jd_profile_deterministic(jd_text)
        tied_present = [w for w in ["amber", "bunch", "cabin"] if w in profile.keywords]
        self.assertEqual(tied_present, sorted(tied_present))

    def test_stopwords_excluded(self):
        jd_text = (
            "about about about their their their would would would "
            "should should should other other other platform platform"
        )
        profile = build_jd_profile_deterministic(jd_text)
        for stopword in ("about", "their", "would", "should", "other"):
            self.assertNotIn(stopword, profile.keywords)

    def test_length_filter_excludes_short_tokens(self):
        jd_text = "AI ML UX API platform platform platform data data"
        profile = build_jd_profile_deterministic(jd_text)
        for short_token in ("ai", "ml", "ux", "api"):
            self.assertNotIn(short_token, profile.keywords)

    def test_cutoff_is_twelve(self):
        # 15 distinct length>=5 words, each with a distinct frequency so ranking is
        # deterministic; only the top 12 by frequency should be kept. Frequency is
        # assigned in REVERSE alphabetical order (victor highest, alpha lowest) so
        # alphabetical selection and frequency selection disagree on which 3 get
        # dropped -- this is what makes the test actually discriminate between the
        # two mechanisms (an earlier version assigned frequency in alphabetical
        # order, so both old alphabetical code and new frequency code happened to
        # keep/drop the identical 12/3 split -- QA caught that it passed under both
        # pre-fix and post-fix code and therefore proved nothing; fixed here).
        words = [
            "alpha", "bravo", "charlie", "delta", "foxtrot", "hotel", "india",
            "juliet", "november", "oscar", "quebec", "sierra", "tango", "uniform",
            "victor",
        ]
        # victor highest frequency, alpha lowest -- exact reverse of alphabetical order
        freqs = {w: i + 1 for i, w in enumerate(words)}
        max_freq = max(freqs.values())
        # interleaved round-robin so every word appears near the start of the text --
        # avoids _jd_body_for_themes()'s 72%-of-text truncation incidentally dropping
        # the low-frequency words before they're even counted.
        tokens = [w for round_i in range(max_freq) for w in words if freqs[w] > round_i]
        jd_text = " ".join(tokens)
        profile = build_jd_profile_deterministic(jd_text)
        self.assertEqual(len(profile.keywords), 12)
        # Alphabetical selection would keep alpha..sierra and drop tango/uniform/victor
        # (the 3 lowest-frequency words here) -- frequency selection must do the
        # opposite: keep the 3 highest-frequency words (victor, uniform, tango) and
        # drop the 3 lowest-frequency, alphabetically-earliest words instead.
        for kept in ("tango", "uniform", "victor"):
            self.assertIn(
                kept, profile.keywords,
                "frequency-sorted keywords must keep high-frequency word %r even "
                "though alphabetical selection would have dropped it; got: %r"
                % (kept, profile.keywords),
            )
        for dropped in ("alpha", "bravo", "charlie"):
            self.assertNotIn(
                dropped, profile.keywords,
                "frequency-sorted keywords must drop low-frequency word %r even "
                "though alphabetical selection would have kept it; got: %r"
                % (dropped, profile.keywords),
            )


if __name__ == "__main__":
    unittest.main()
