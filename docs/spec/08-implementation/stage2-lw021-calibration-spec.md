# Stage 2 Improvement #3 — LW-021 Cross-Employer Audience Bleed Calibration

**Status:** Packaged for empirical testing (not yet implemented)
**Date:** 2026-09-01
**Risk:** MEDIUM (implement carefully with empirical testing)

## Problem

`LW-021` (`check_cross_employer_audience_bleed` in `scripts/submission_linter.py`)
flags the target JD's distinctive audience/domain vocabulary appearing inside a
resume bullet or cover-letter paragraph narrating a DIFFERENT, past employer's story.

The rule was already calibrated once on 2026-08-18:
- `min_count` raised from 2 to 3
- `_CROSS_JD_GENERIC_WORDS` stopword list massively expanded (~50 false positives
  in one 6-company batch were all generic PM/business vocabulary)

Despite that calibration, the rule still has two known weakness modes:

1. **Sense-disambiguation false positives**: a word like "design" or "support"
   has a legitimate different sense in the JD vs. the past employer's context.
   The rule can't distinguish "prompt design" (JD sense) from "designed the
   export tooling" (Cision sense) — both contain "design", but only the first
   is audience/domain bleed.

2. **Stopword list whack-a-mole**: each new JD domain introduces new generic
   words that slip through the stopword list. The current approach (manually
   expanding `_CROSS_JD_GENERIC_WORDS` after each batch) is reactive, not
   proactive.

## Proposed Calibration Approaches (for empirical testing)

### Approach A: Domain-aware stopword expansion

Instead of a static stopword list, derive stopwords from the JD's own structure:
- Words appearing in the JD's "About the Company" / "What you'll do" boilerplate
  sections are less distinctive than words in the "Requirements" / "Nice to have"
  sections. Weight the word's distinctiveness by which JD section it appears in.
- **Risk:** Section parsing is fragile across JD formats. Needs a robust parser
  or a fallback to the current flat-frequency approach.

### Approach B: POS-tag filtering

Use part-of-speech tagging to filter out words that are likely generic verbs/
adjectives rather than domain nouns. "Teachers", "patients", "classroom" are
nouns; "design", "support", "drive" are verbs that are already in the stopword
list but keep slipping through in different forms.
- **Risk:** Requires a POS tagger dependency (NLTK or spaCy), which is not
  currently in `requirements.txt`. Could use a lightweight rule-based approach
  instead (e.g., filter words ending in "-ing" that are verb gerunds).

### Approach C: Employer-vocabulary cross-check

Before flagging a word, check whether it appears in `workExperience.md` under
the SAME past employer's section. If "support" appears in Cision's own WE
section, it's Cision's real vocabulary, not bleed from the target JD.
- **Risk:** WE parsing is non-trivial (section boundaries, multi-employer
  sections). But this is the most principled approach — it directly tests
  whether the word is the past employer's own vocabulary or not.

### Approach D: Confidence-scored WARN

Instead of binary flag/no-flag, assign a confidence score to each finding:
- +2 if the word is a noun (domain-specific)
- +1 if the word appears 3+ times in the JD
- -1 if the word also appears in the past employer's WE section
- -1 if the word is in the current stopword list
- Only flag if score >= 2
- **Risk:** Tuning the threshold requires empirical testing against real
  submissions. But this is the most flexible approach.

## Empirical Testing Plan

1. **Baseline**: Run LW-021 against all 15 real submissions in
   `data/submissions/` with the current implementation. Record:
   - Total findings
   - True positives (genuine audience bleed)
   - False positives (shared word, different sense)
   - False negatives (known bleed missed by the rule)

2. **Test each approach**: Implement each approach behind a flag, re-run
   against the same 15 submissions, and compare:
   - False positive rate (target: < 10% of findings)
   - True positive rate (target: 100% of known bleed cases caught)
   - New false negatives introduced

3. **Select the approach** with the best false-positive reduction while
   maintaining zero new false negatives.

4. **Update tests**: `scripts/test_submission_linter.py` lines 497-551 have
   LW-021/LW-026 tests. Any calibration change must keep these passing and
   add new regression fixtures for the false-positive classes it fixes.

## Files to Touch (when implementing)

- `scripts/submission_linter.py` — `check_cross_employer_audience_bleed()`,
  `_jd_distinctive_words()`, `_CROSS_JD_GENERIC_WORDS`
- `scripts/test_submission_linter.py` — LW-021 test cases
- `CHANGELOG.md` — entry for the calibration change

## Not in Scope

- LW-026 (JD-specificity floor) shares `_jd_distinctive_words()` with LW-021
  but intentionally keeps `min_count=2`. Any calibration must not change
  LW-026's behavior unless separately tested.
- The rule's WARN severity (not HARD_BLOCK) is correct and should not change.
  A human read is still the right disposition for a heuristic that can't
  perfectly distinguish bleed from coincidence.
