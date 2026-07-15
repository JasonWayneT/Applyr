# CR-068: `requirements` Section-Extraction Fix (`extract_req_section` / `build_jd_profile_deterministic`)

## Metadata
- **Epic**: JD-profile extraction quality (CR-063 → 064 → 065 → 066 → 067 arc)
- **Status**: Scoped for implementation. Round 1 (validated fixes 1+2) ready for senior-engineer;
  Round 2 (boundary / length-cap rework) deferred pending Round 1's measured result.
- **Date**: 2026-07-14
- **Source**: Implementation follow-up to **CR-067** (`CR-067-requirements-section-extraction-diagnostic.md`),
  which root-caused the `requirements`-field boilerplate-capture defect to three independent, compounding
  causes in `scripts/jd_tailoring.py` and reverted its in-progress fix rather than ship it self-reviewed.
  This CR ships that fix under normal pipeline review, using the round-by-round discipline CR-067's Decision
  section explicitly recommended.
- **Predecessor findings this CR treats as settled (do not re-litigate):**
  - CR-065 Part D (as corrected by CR-067): `requirements` captures job-posting boilerplate instead of real
    requirements in **4/13** companies (OneStream, Remote, Covideo, Ontra), and the naive
    `extract_req_section()`-scoping fix resolves only 1 of them on its own.
  - CR-067: the defect has three root causes — (1) `_REQ_SECTION_RE`'s heading list misses common real
    headings; (2) `build_jd_profile_deterministic`'s `requirements` construction never calls
    `extract_req_section()` at all; (3) `_NEXT_SECTION_RE`'s boundary detection is blind to Title-Case
    headings and no-blank-line-separator layouts, compounded by the 120-char line-length cap silently
    dropping long real requirement bullets. Fixes 1+2 are validated 2-line changes; fix 3 is the harder,
    higher-regression-risk piece.

## Problem

`build_jd_profile_deterministic`'s `requirements` field is meant to hold the JD's real requirement/
qualification lines so downstream claim scoring (`score_all_claims`, `pick_cover_proofs`) can match against
what the role actually asks for. In 4/13 measured companies it instead holds job-posting boilerplate —
location, employment type, salary band, benefits copy, interview-process steps, or bare section headings —
because of the three compounding defects CR-067 root-caused (see Metadata). The two low-risk causes have
hands-verified fixes; the third needs its own measured round because loosening section-boundary detection
carries a real regression surface for the 8-9 companies where `requirements` already works today.

Per the arc's established discipline (CR-064 Rounds 2/3/5 changed dedup, then rarity, then the dampener as
separate measured steps; CR-066 shipped one isolated change with a full before/after measurement), this CR
does **not** ship a combined 3-part regex rewrite. It ships the coupled, validated fixes 1+2 as Round 1 with
a full-sample before/after measurement, then decides Round 2's scope from what Round 1 actually shows.

## Decision

### Round 1 — heading-phrase broadening + `extract_req_section()` wiring (this CR's shippable unit)

Fixes 1 and 2 are treated as **one round, not two**, because Fix 1 is inert on the `requirements` field
without Fix 2: broadening `_REQ_SECTION_RE` changes nothing that reaches
`build_jd_profile_deterministic`'s output until the field is actually routed through
`extract_req_section()`. They form a single testable hypothesis — *does broadening the heading list AND
wiring the requirements scan through `extract_req_section()` measurably improve `requirements` quality
without regressing the currently-good companies?* Fix 3 (the genuinely independent, higher-risk change) is
Round 2.

Two code changes to `scripts/jd_tailoring.py`, both validated by CR-067's author against real archived JD
text (re-confirmed against current code at this CR's setup — `who you are` and
`required education and experience` are still absent from `_REQ_SECTION_RE`; `requirements` still scans raw
`jd_text.splitlines()` at line 134):

1. **Broaden `_REQ_SECTION_RE`'s alternation** (lines 85-93) to add two validated heading phrases:
   `who\s+you\s+are` and `required\s+education\s+and\s+experience`. CR-067 confirmed by direct
   `re.search()` that adding these two makes the regex match all 4 originally-broken companies' real
   requirement headings (Ontra/Remote/Covideo use "Who You Are"; OneStream uses "Required Education and
   Experience").
2. **Wire `requirements` construction through `extract_req_section()`** (lines 133-138): source the
   line-scan from `req_source = extract_req_section(jd_text)` and iterate `req_source.splitlines()` instead
   of `jd_text.splitlines()`. CR-067 confirmed this is a 2-line change. `extract_req_section()` already
   falls back to the full JD when no heading matches, so this is safe for JDs where no heading is found
   (behavior identical to today).

**Change nothing else.** Not `_NEXT_SECTION_RE`, not the 120-char cap, not `keywords`/`priority_themes`
construction, not `score_claim_for_jd`, not `THEME_KEYWORDS`, not `data/master_claims.json`.

### Round 1 is measured honestly, not assumed to be a win

CR-067's author already found — by direct end-to-end test — that **fixes 1+2 alone do not produce a clear
win**: Ontra and Remote stayed broken (root cause 3 — no-blank-line-separator layout — is untouched by
1+2), and Covideo's `requirements` *changed to a different wrong answer* (benefits copy instead of title/
location copy, because the 120-char cap silently drops Covideo's long "Trait: elaboration" bullets). Round
1's measurement must therefore honestly report whichever of {measurably helps / does nothing / makes a
company worse} is true per company — a zero or mixed result is valid information, exactly as CR-064's Round
2 zero-movement result was correctly logged rather than hidden. **Do not write the tracker or the log as if
Round 1 is expected to fix all four companies.** The real question Round 1 answers is: on the full sample,
which companies does 1+2 measurably improve, which does it leave unchanged, and does it regress any of the
currently-good ones (including via the Covideo-style "different wrong answer" failure)?

### Round 2 — boundary / length-cap rework (DEFERRED, not scoped in detail here)

Root cause 3 (rework `_NEXT_SECTION_RE` to handle Title-Case headings and/or no-blank-line-separator
layouts, and reconsider the 120-char upper bound on the line-scan filter) is **explicitly deferred to a
later round.** Its scope is intentionally left open: whether the boundary rework should be narrow
(Title-Case detection only) or broad (also handle no-separator single-line-heading layouts), and whether
the length cap should be raised, removed, or switched to truncate-not-drop, should be decided from Round
1's measured result — specifically from *which* companies still show broken `requirements` after 1+2 and by
*which* of the two remaining mechanisms (Title-Case boundary miss vs. no-separator layout vs. length-cap
drop). Writing Round 2's plan in detail now would pre-commit a scope the measurement hasn't justified yet.
This deferral is itself the one-hypothesis-at-a-time discipline CR-067's Decision called for.

## Acceptance Criteria (Round 1 only)

1. **The two validated code changes ship**, exactly as scoped: `who\s+you\s+are` +
   `required\s+education\s+and\s+experience` added to `_REQ_SECTION_RE`, and `requirements` construction
   routed through `extract_req_section(jd_text)`. No other production behavior changed.
2. **Test-first.** A unit test is written and confirmed to FAIL against pre-fix code before the fix lands,
   then PASS after. It pins the two mechanisms directly (see Open Question 1 for placement): (a)
   `_REQ_SECTION_RE` matches the strings "Who You Are" and "Required Education and Experience"; (b) a
   crafted JD whose real requirement bullets sit under a "Who You Are" heading after an earlier boilerplate
   block — using a layout Fixes 1+2 can handle (short <120-char bullets, blank-line-separated, followed by
   an ALL-CAPS next-section heading so `_NEXT_SECTION_RE` can bound it) — yields those bullets as
   `.requirements`, not the earlier boilerplate. The crafted JD must deliberately avoid the root-cause-3
   layouts so the test isolates Fixes 1+2 and genuinely passes post-fix.
3. **Full-sample `requirements`-quality measurement, per-company hand-review, same method CR-065 Part B
   used**, run against the current archive sample (re-confirmed at execution — see AC 6). The before and
   after `requirements` list must be recorded per company for **at least the 4 originally-broken companies
   (OneStream, Remote, Covideo, Ontra)**, with a plain verdict (real requirements vs. boilerplate, and if
   changed, better/worse/lateral). Covideo's "different wrong answer" risk (benefits copy) must be checked
   for explicitly, not assumed away.
4. **Regression check across the previously-good companies.** For the 8-9 companies CR-065 Part B judged
   `requirements`-good (Cresta, Group 1001, Buyers Edge, DataGrail, MyTime, PointClickCare, Redox, Lumos —
   those present in the sample), record before/after and confirm none regressed. Adding `who you are` to a
   `.search()`-based regex can shift the matched heading *earlier* in a JD that has a "Who You Are" intro
   before its real "Requirements" section — this specific regression path must be checked, not assumed
   benign.
5. **Full pytest baseline maintained.**
   `python -m pytest -q --ignore=test_domain_gate.py --ignore=test_fit_policy.py --ignore=test_llm.py`
   (from `scripts/`) shows the same pre-existing-failure floor plus the new Round 1 test(s) passing — i.e.
   failed count unchanged, passed count up by exactly the number of new tests. Any other movement is
   explained before close-out. (Expected floor per CR-066 close-out: 28 failed / 195 passed / 1 skipped —
   re-confirm at execution; the arc has shown drift.)
6. **Eval-set membership re-confirmed at execution start** and logged with the actual present/missing lists
   and count (setup found 12/16 — see tracker). Before and after measurements run against the same named
   set.
7. **`git diff --stat` scope confirmation.** The production diff is confined to `_REQ_SECTION_RE` and the
   `requirements` line-scan source in `scripts/jd_tailoring.py`. Zero changes to `_NEXT_SECTION_RE`, the
   120-char cap, `keywords`/`priority_themes` construction, `score_claim_for_jd`, `THEME_KEYWORDS`, or
   `data/master_claims.json`.

## Out of Scope
- **Root cause 3 (Round 2): `_NEXT_SECTION_RE` boundary rework and the 120-char line-length cap.** Deferred
  to a later round, scoped from Round 1's measured result. Not implemented in Round 1 even if the Round 1
  measurement makes a specific fix look obvious.
- **`keywords` (CR-066, shipped), `priority_themes` / `THEME_KEYWORDS` (CR-063), and `score_claim_for_jd`
  (CR-064).** Not touched or reopened.
- **The under-scoring `ACC-401-AITOOLS` / `ACC-204` problem.** Separate, unrelated thread (CR-065/066
  Out-of-Scope); no evidence any `requirements` fix addresses it.
- **`data/master_claims.json` edits.** Not applicable.
- **Regenerating or editing any archived submission.** JDs are read-only test input.

## Open Questions (implementation-sequencing calls resolved by tech-lead at setup — see tracker)
1. **Where the Round 1 unit test lives.** RESOLVED in the tracker: a new dedicated
   `scripts/test_jd_profile_requirements.py`, asserting against `build_jd_profile_deterministic().requirements`
   and `_REQ_SECTION_RE` directly — mirroring CR-066's `test_jd_profile_keywords.py` precedent, keeping the
   diff attributable and narrow.
2. **Round 2 scope (narrow Title-Case-only vs. broad no-separator handling).** Deliberately NOT resolved —
   routed to Round 1's measured result per the Decision. This is the one genuine open scoping question and
   it is intentionally deferred, not decided at setup.
3. **Is regex fundamentally the wrong tool for section detection?** Carried forward from CR-067 Open
   Question 2: real JDs already show 3+ distinct layout conventions in a 12-13-company sample. If Round 2's
   boundary rework starts needing an ever-growing pattern list (the "whack-a-mole" shape CR-063's
   `THEME_KEYWORDS` rounds took), that is a signal to raise with Jason before sinking more rounds into
   incremental regex patches — flagged, not resolved, and explicitly a Round-2-or-later concern.

## Traceability Mapping

| File | Action |
|------|--------|
| `scripts/jd_tailoring.py` | Round 1 edits: `_REQ_SECTION_RE` alternation (lines 85-93) + `requirements` line-scan source (lines 133-138). `_NEXT_SECTION_RE` (lines 95-98) and the 120-char cap (line 136) are Round 2, untouched in Round 1. |
| `scripts/test_jd_profile_requirements.py` | New Round 1 unit test file (per Open Question 1). |
| `scripts/measure_jd_profile_extraction.py` | Reuse its existing Part A per-company profile dump for the `requirements` hand-review; extend in place only if a dedicated requirements-quality view is needed (additive, do not disturb the CR-065/066-reviewed paths). |
| `docs/spec/08-implementation/CR-068-requirements-section-extraction-fix-tracker.md` | The resumable round-by-round tracker (companion to this spec). |
| `docs/spec/05-change-requests/README.md` | CR-068 registry row added. |
| `docs/spec/08-implementation/CR-067-...` / `CR-065-...` | Predecessor findings; do not edit as part of this CR. |
