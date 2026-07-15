---
status: complete
created: 2026-07-14
spec: ../05-change-requests/CR-068-requirements-section-extraction-fix.md
eval_set: ../../reports/jd-theme-claim-eval-set.md
predecessor_tracker: CR-066-jd-profile-keywords-frequency-fix-tracker.md
diagnostic_source: ../05-change-requests/CR-067-requirements-section-extraction-diagnostic.md
---

# CR-068 Tracker — `requirements` Section-Extraction Fix (`extract_req_section` / `build_jd_profile_deterministic`)

Resumable round-by-round log, same discipline as its predecessors CR-063/CR-064/CR-065/CR-066. **Read the
Session Handoff block at the very bottom of this file first** — if a prior session left one filled in, that
block tells you exactly where to pick up, and you should trust it over re-deriving state from the round logs
yourself. Right now the handoff block is pre-filled with the starting state (this CR hasn't had a working
session yet) — treat it as the literal first thing to do, not a template to ignore.

**Read `CR-068-requirements-section-extraction-fix.md` first if you haven't this session** — it has the full
Problem, the exact Round 1 code changes, the 7 Round-1 Acceptance Criteria, the deferred Round 2 scope, the
Out-of-Scope list, and the Open Questions. Then read the diagnostic this CR acts on,
`CR-067-requirements-section-extraction-diagnostic.md` — it is the hands-on root-cause analysis (3
compounding causes) that scoped this work, including the critical warning that **fixes 1+2 alone did NOT
produce a clear win** when CR-067's author tested them end-to-end.

**This is the SECOND production code change in the CR-063 → 064 → 065 → 066 → 067 → 068 arc** (CR-066 was
the first; CR-063/064/065/067 were diagnostic-only). It edits `scripts/jd_tailoring.py`'s
`_REQ_SECTION_RE` and `build_jd_profile_deterministic`'s `requirements` construction — the same shared
function CR-066 touched, with the same multiple live call sites. That keeps the risk profile high: the
guardrail set here is the full CR-066-era battery (pytest baseline, per-company hand-review of the actual
field output before/after, full-sample regression check), not a `git diff --stat`-only check.

## The one warning that governs this whole CR

**Do not execute Round 1 expecting it to fix all four broken companies.** CR-067's author already ran fixes
1+2 end-to-end and found: Ontra and Remote stayed broken (their no-blank-line-separator layout is root
cause 3, untouched by 1+2), and Covideo *changed to a different wrong answer* (benefits copy instead of
title/location copy, because the 120-char cap drops its long real bullets). Round 1's honest job is to
measure — per company — whether 1+2 helps, does nothing, or makes something worse, and whether any
currently-good company regressed. A zero or mixed result is a valid, publishable Round 1 finding, exactly
as CR-064's Round 2 zero-movement result was correctly logged rather than hidden. Round 2's scope is chosen
*from* Round 1's measurement — so measuring cleanly is the whole point of Round 1.

## Checkpointing protocol — this work may span multiple sessions, plan for it

Same four rules CR-063/CR-064/CR-065/CR-066 used, because they worked:

1. **Before executing any plan — a full round, or a specific measurement within a round — write the plan
   out as its own ordered checklist right here in this file**, under the round you're working on, even if
   it's more granular than what's pre-written below.
2. **Check off and log each step as you finish it, not in a batch at the end.** Real state — the actual
   per-company before/after `requirements` lists, verbatim — not a stale unchecked list or a
   reconstructed-from-memory summary. The pre-fix and post-fix `requirements` output must both be written
   into this file against the *same named company set*.
3. **If you sense you're running low on context or session time, stop at the nearest checkpoint boundary.**
   A cleanly stopped, fully logged step beats a rushed, unlogged batch. Natural boundaries here: after the
   pre-fix baseline is logged (before touching code); after the fix + unit test land and pytest is green;
   after the full-sample requirements hand-review.
4. **Before ending any session on this CR, fill in the Session Handoff block at the bottom.** Read first by
   whoever comes next, before anything else in this document.

## Before Round 1 — orientation (do this once)

Tech-lead pre-verified the items below during CR-068 setup (2026-07-14). They are marked `[x]` with the
state found at that time. **The eval-set membership item (and only that item) must be re-confirmed by
whoever executes this CR at the start of their own session** — the archive has churned repeatedly across
this arc (16→14→13→12 companies over one day; SailPoint vanished mid-session during CR-065). The other
items are stable code facts and do not need re-running unless the code has moved.

- [x] **Read the spec in full** (`CR-068-requirements-section-extraction-fix.md`) — Problem, Decision
      (Round 1 = fixes 1+2 as one coupled round; Round 2 deferred), 7 Round-1 Acceptance Criteria, Out of
      Scope, 3 Open Questions.
- [x] **Confirm CR-067's two validated code changes are still accurate against current code** (tech-lead,
      2026-07-14):
      - `_REQ_SECTION_RE` (`scripts/jd_tailoring.py:85-93`) — confirmed the alternation does NOT contain
        `who\s+you\s+are` or `required\s+education\s+and\s+experience`. It currently has: `requirements?`,
        `qualifications?`, `what you.{0,8}bring`, `what we.{0,8}looking`, `what you.{0,8}need`,
        `preferred/basic/required qualifications?`, `key requirements?`, `minimum qualifications?`,
        `must have`, `you bring`, `what you offer`. Fix 1 adds the two missing phrases to this alternation.
      - `requirements` construction (`scripts/jd_tailoring.py:133-138`) — confirmed it scans
        `for line in jd_text.splitlines():` directly (raw JD), does NOT call `extract_req_section()`. Fix 2
        sources the scan from `extract_req_section(jd_text)` instead. `extract_req_section()` is defined at
        line 101 and already falls back to the full JD when no heading matches.
      - `_NEXT_SECTION_RE` (`scripts/jd_tailoring.py:95-98`) = `r"\n\s*\n[A-Z][A-Z\s]{3,}\n|\n##\s"`
        (ALL-CAPS or markdown `##` only) and the 120-char cap (`20 <= len(line) <= 120`, line 136) are
        **Round 2 territory — do NOT touch them in Round 1.**
      - Note: `keywords` (lines 140-142) is already the CR-066 `Counter` frequency-sort — consistent with a
        committed CR-066; do not disturb it.
- [x] **Confirm the current eval-set membership in `data/archive/submissions/` — 12/16 present as of
      2026-07-14 (tech-lead setup run).** Checked the 16 `EVAL_SET` slugs (`measure_theme_extraction.py:21-38`)
      against the archive:
      - **Present (12):** `cresta`, `group_1001`, `onestream_software`, `buyers_edge_platform`, `ontra`,
        `remote`, `covideo`, `datagrail`, `mytime`, `pointclickcare`, `redox`, `lumos`.
      - **Missing (4):** `sailpoint`, `tilt`, `par`, `parkingpass_com`. Unchanged from CR-066's sample.
        `par_technology` is present but is a **different** folder from the eval-set `par` slug — do NOT
        substitute it.
      - **All 4 originally-broken companies (OneStream, Remote, Covideo, Ontra) ARE present**, so Round 1's
        core AC-3 measurement is runnable in full.
      - **RE-CONFIRM THIS AT EXECUTION TIME.** Log whichever count is actually present, and run BOTH the
        pre-fix and post-fix measurements against that same named set (AC 6).
- [x] **Confirm the measurement precedent** — `scripts/measure_jd_profile_extraction.py` (from CR-065,
      extended in CR-066) already dumps the full per-company profile including `requirements` via its Part A
      path, sourcing JDs from `data/archive/submissions/`. Reuse that Part A per-company dump for the
      `requirements` hand-review; extend the script only additively if a dedicated requirements-quality view
      helps (do not disturb the Part A `main()` path CR-065/066 reviewed).
- [x] **Record the pytest baseline at execution start.** Command:
      `python -m pytest -q --ignore=test_domain_gate.py --ignore=test_fit_policy.py --ignore=test_llm.py`
      (from `scripts/`). Expected per CR-066 close-out: **28 failed / 195 passed / 1 skipped** (the 28F/190P
      floor plus CR-066's 5 keywords tests). Re-run and record the actual counts HERE before touching code —
      if it differs, something changed in the repo since CR-066; note it before proceeding. Round 1's
      post-fix run must show the same failed count plus the new Round 1 test(s) passing.
      **(NOT pre-run by tech-lead — this is the executing session's first action, so the baseline is
      captured against the exact repo state Round 1 ships from.)**

## Open Questions — resolved by tech-lead at setup (do not re-decide ad hoc)

1. **Where the Round 1 unit test lives — RESOLVED: a new dedicated
   `scripts/test_jd_profile_requirements.py`**, asserting against `build_jd_profile_deterministic().requirements`
   and `_REQ_SECTION_RE` directly (no extracted helper). Mirrors CR-066's `test_jd_profile_keywords.py`
   precedent: keeps the `jd_tailoring.py` diff to exactly the two validated changes, and tests the real
   production entry point so it fails if anything in the real path reverts.
2. **Round 2 scope (narrow Title-Case-only vs. broad no-separator handling) — DELIBERATELY NOT RESOLVED.**
   Routed to Round 1's measured result per the spec Decision. This is the one genuine open scoping question
   and it is intentionally deferred, not decided at setup — because whether Round 2 needs to handle just
   Title-Case boundaries or also no-separator single-line-heading layouts depends on which companies Round 1
   leaves broken and by which mechanism.

## Round 1 — implement fixes 1+2, test-first, with pre-fix baseline locked before any code change

Ordered checklist covering the spec's 7 Round-1 Acceptance Criteria. **Sequence matters: the pre-fix
`requirements` baseline (step 3) MUST be captured and logged BEFORE the code changes (step 5)** — a
post-hoc baseline is not apples-to-apples. Write real per-company `requirements` lists into this file as
each step completes.

- [x] **1. Re-confirm eval-set membership at execution start.** Re-run the 16-slug presence check against
      `data/archive/submissions/`. Log the actual present/missing lists and count HERE, dated. This named
      set is what both the pre-fix and post-fix measurements run against (AC 6). Setup found 12/16; confirm
      whether that still holds and that OneStream/Remote/Covideo/Ontra are all still present.
      **Confirmed 2026-07-14 (senior-engineer): still 12/16, identical to tech-lead's setup finding.**
      Present: Cresta, Group 1001, OneStream, Buyers Edge Platform, Ontra, Remote, Covideo, DataGrail,
      MyTime, PointClickCare, Redox, Lumos. Missing: SailPoint, Tilt, PAR, ParkingPass.com. All 4
      originally-broken companies present.
- [x] **2. Record the pytest baseline** (the orientation item above). Log actual failed/passed/skipped here.
      **Confirmed 2026-07-14: 28 failed / 195 passed / 1 skipped** — matches the expected CR-066-close-out
      floor exactly, no drift.
- [x] **3. Establish the pre-fix `requirements` baseline on the CURRENT (unfixed) code, on the confirmed
      sample.** Before touching `jd_tailoring.py`, run `measure_jd_profile_extraction.py`'s Part A dump (or
      call `build_jd_profile_deterministic()` per company) and record the verbatim pre-fix `requirements`
      list for every company in the sample — at minimum the 4 originally-broken (OneStream, Remote, Covideo,
      Ontra) and the previously-good set (Cresta, Group 1001, Buyers Edge, DataGrail, MyTime, PointClickCare,
      Redox, Lumos). Log the full per-company table in "Round 1 results" below.
      **Done — see "Round 1 results" below for the verbatim per-company table.**
- [x] **4. Write the failing unit test first (test-first)** in the new
      `scripts/test_jd_profile_requirements.py` (per resolved OQ1): (a) assert `_REQ_SECTION_RE` matches the
      strings "Who You Are" and "Required Education and Experience"; (b) build a crafted JD with an early
      boilerplate block, then a "Who You Are" heading, then short (<120-char) blank-line-separated real
      requirement bullets, then an ALL-CAPS next-section heading (a layout Fixes 1+2 CAN bound — deliberately
      NOT a root-cause-3 layout), and assert `build_jd_profile_deterministic(jd).requirements` yields those
      bullets, not the earlier boilerplate. Confirm BOTH assertions FAIL against current code first (proves
      the test has teeth) — (a) fails because the phrases aren't in the pattern yet; (b) fails because
      `requirements` scans raw `jd_text` and captures the earlier boilerplate.
      **Done — all 3 assertions (2 regex-match tests + 1 end-to-end test) confirmed FAILING against pre-fix
      code, then confirmed PASSING after the fix. Verbatim pre-fix failure: `_REQ_SECTION_RE.search("Who You
      Are")` and `.search("Required Education and Experience")` both returned `None`; the end-to-end test
      failed on `assertNotIn("Location: Remote, USA", profile.requirements)` because pre-fix code scanned raw
      `jd_text` and captured the earlier boilerplate line.**
- [x] **5. Implement fixes 1+2 in `scripts/jd_tailoring.py`.** Fix 1: add `who\s+you\s+are` and
      `required\s+education\s+and\s+experience` to `_REQ_SECTION_RE`'s alternation (lines 85-93). Fix 2:
      change lines 133-138 to `req_source = extract_req_section(jd_text)` then scan `req_source.splitlines()`
      instead of `jd_text.splitlines()`. Change NOTHING else — not `_NEXT_SECTION_RE`, not the 120-char cap,
      not `keywords`/`priority_themes`, not `score_claim_for_jd`, not `THEME_KEYWORDS` (AC 1, AC 7, Out of
      Scope). Confirm the unit test from step 4 now passes.
      **Done exactly as scoped. Unit test confirmed passing post-fix (3/3).**
- [x] **6. Re-measure the full-sample `requirements` field, post-fix, on the SAME named set as step 3.**
      Record the verbatim post-fix `requirements` list per company. **Diff it against step 3 per company**
      and give a plain verdict (CR-065 Part B method): for the 4 originally-broken companies, did
      `requirements` become real requirement content, stay boilerplate, or change to a *different* wrong
      answer (the Covideo benefits-copy risk CR-067 flagged — check explicitly)? Log the full before/after
      table and per-company verdicts in "Round 1 results" (AC 3).
      **Done — see "Round 1 results" below.**
- [x] **7. Regression check across the previously-good companies (AC 4).** For each company CR-065 Part B
      judged `requirements`-good, confirm post-fix did not regress. Check the specific `.search()`-shift risk:
      any JD with a "Who You Are" intro *before* its real "Requirements" section could now match the earlier
      heading — verify none of the good companies fell into this. Log any company whose `requirements`
      changed at all, with a better/worse/lateral judgment, before close-out.
      **Done — see "Round 1 results" below. Zero regressions; 2 companies (Cresta, Group 1001) measurably
      improved via Fix 2 alone (their matched heading was already "What We're Looking For", not the new
      "who you are" phrase — confirmed by direct regex inspection); the "who you are"-matches-too-early risk
      the tracker named did NOT materialize for any of the 8 named previously-good companies (checked
      directly per company below).**
- [x] **8. Pytest regression check (AC 5).** Re-run the baseline command. Must show the same failed count as
      step 2 PLUS the new `test_jd_profile_requirements.py` test(s) passing — passed count up by exactly the
      number of new tests, failed unchanged. Verify via `git stash` (as CR-066 did) that the same failure
      set exists pre- and post-fix. Any other movement gets explained here before close-out.
      **Confirmed: 28 failed / 198 passed / 1 skipped post-fix (198 = 195 + 3 new tests). Verified via a
      targeted `git stash push -- scripts/jd_tailoring.py` (a full-repo `git stash` was tried first and
      rejected — this repo's working tree carries a large amount of unrelated uncommitted in-flight work, and
      a full stash pulled in unrelated files, breaking an unrelated test file's import; the targeted
      single-file stash avoided that) that the pre-fix run with `jd_tailoring.py` reverted to HEAD shows the
      identical 28-failure set (`test_audit_convergence`, `test_cover_claim_picker`, `test_cover_dignifi` x3,
      `test_cover_everbridge` x2, `test_cover_letter_slots` x9, `test_cover_splash_golden` x3,
      `test_cover_structure_universal` x2, `test_cover_word_padding`, `test_gap_detector`,
      `test_submission_linter` x2) plus the 3 new `test_jd_profile_requirements.py` tests failing (31 total),
      confirming the 28-failure floor is unmoved and the only delta is the 3 new tests flipping from fail to
      pass.**
- [x] **9. `git diff --stat` scope confirmation (AC 7).** Confirm the production diff is confined to
      `_REQ_SECTION_RE` and the `requirements` line-scan source in `scripts/jd_tailoring.py`. Zero changes to
      `_NEXT_SECTION_RE`, the 120-char cap, `keywords`/`priority_themes`, `score_claim_for_jd`,
      `THEME_KEYWORDS`, or `data/master_claims.json`.
      **Confirmed: `git diff --stat -- scripts/jd_tailoring.py` shows `1 file changed, 4 insertions(+), 2
      deletions(-)`. The full diff is exactly the two scoped hunks (the `_REQ_SECTION_RE` alternation
      addition and the `req_source = extract_req_section(jd_text)` line-scan rewire). Plus one new file,
      `scripts/test_jd_profile_requirements.py`.**
- [x] **10. Write the Round 1 finding — honestly.** State, per company, whether fixes 1+2 helped, did
      nothing, or made it worse, and name explicitly which companies (if any) still show broken
      `requirements` and by which of the two remaining mechanisms (Title-Case boundary miss, no-separator
      layout, or 120-char length-cap drop). This finding is what scopes Round 2 — do NOT write a
      "Round 1 fixed it" summary if the measurement says otherwise. If Round 1 shows zero or mixed movement,
      that is the correct, publishable result (CR-064 Round 2 precedent).
      **Done — see "Round 1 results" below. Mixed result, exactly as CR-067 predicted for 3/4 companies, with
      one important mechanism refinement for Ontra/Remote (see below).**
- [x] **11. Update docs on close-out.** Set this tracker's frontmatter `status`, update the CR-068 registry
      row in `docs/spec/05-change-requests/README.md`, append the round result to `pipeline-log.md`, and
      fill the Session Handoff block below. Confirm no connector/gate changed, so the CLAUDE.md
      pipeline-behavior doc checklist rows do not apply (confirm this judgment at close-out).
      **Done. Confirmed this CR touches only `scripts/jd_tailoring.py` (a pipeline scoring/extraction
      internal, not a connector or a gate) — the CLAUDE.md "Documentation Update Checklist" connector/gate
      rows do not apply.**

## Round 1 results

**Executed 2026-07-14, senior-engineer.** Sample: 12/16 eval-set companies present in
`data/archive/submissions/` (Cresta, Group 1001, OneStream, Buyers Edge Platform, Ontra, Remote, Covideo,
DataGrail, MyTime, PointClickCare, Redox, Lumos — SailPoint/Tilt/PAR/ParkingPass.com absent, unchanged from
setup). Pre-fix baseline captured via a targeted `git stash push -- scripts/jd_tailoring.py` against the
current archive sample (not a reconstructed summary — same command, same sample, run twice).

### The 4 originally-broken companies — verbatim before/after

**OneStream (onestream_software) — FIXED, clean win.**
- Before: `['Location:...Remote, USA', 'Employment Type:...Full-Time', 'Benefits Offered:...Vision, Medical, Life, Dental, 401K', 'Gross annual base salary: USD 114,000-148,000', 'Primary Duties and Responsibilities', 'Define and track success measures and KPIs related to adoption, quality, delivery predictability, and ecosystem health.']`
- After: `['Demonstrated experience owning and delivering complex, multi-phase product roadmaps for B2B SaaS platforms.', 'Strong understanding of modern web platforms, APIs, cloud services, and enterprise software ecosystems.', 'Experience working closely with engineering teams in Agile/Scrum environments.', 'Preferred Education and Experience', 'Experience with marketplaces, partner ecosystems, developer platforms, or enterprise integrations.', 'Familiarity with identity, entitlements, licensing, and access management models.']`
- Verdict: **FIXED.** All location/employment-type/benefits/salary boilerplate is gone, replaced with real
  requirement content. One heading fragment remains ("Preferred Education and Experience" — a real section
  heading, not garbage) but this is a clear, unambiguous win. Mechanism: OneStream's real bullets are all
  under 120 chars, so the heading-phrase fix (`required education and experience`) plus the
  `extract_req_section()` wiring were sufficient on their own.

**Ontra (ontra) — STILL BROKEN, mechanism refined from CR-067's prediction.**
- Before (3 items): `['What the job involves', 'Ontra is seeking a Senior Product Manager reporting to our VP of Product, GM', "We're looking for a bold, senior product manager ready to solve complex problems on our flagship product"]`
- After (4 items): `['What the job involves', 'Ontra is seeking a Senior Product Manager reporting to our VP of Product, GM', "We're looking for a bold, senior product manager ready to solve complex problems on our flagship product", 'Cross-Functional Collaboration: Establish robust relationships across functions, collaborating on strateg']`
- Verdict: **STILL BROKEN**, confirming CR-067's headline prediction, but the underlying mechanism is
  different from what the tracker/spec named. Direct inspection (`_REQ_SECTION_RE.search()`) shows the regex
  now matches `"Who you are"` at character 5 (the JD literally opens `"Role\nWho you are\n..."`), and
  `extract_req_section()`'s no-blank-line-separator fallback (`remainder[:2000]`) **correctly returns the
  real "Who You Are" content** — `'Product Experience: 5+ years in product management with demonstrated
  ability...'`, `'Educational Background: ...'`, `'Strategic Development: ...'`, `'Technical Aptitude:
  ...'`, `'Product Launch: ...'` are all present in `extract_req_section()`'s output. **The actual blocker is
  the unchanged 120-char line-length cap**: every one of these 5 real bullets is 130-148 characters (measured
  directly), so all 5 get silently dropped by the `20 <= len(line) <= 120` filter, and the line-scan falls
  through past them into "What the job involves" and beyond — the same boilerplate as before, plus one new
  item. **This means root cause 3 (boundary/no-separator handling) is NOT what's keeping Ontra broken — the
  boundary detection and fallback already work correctly here. Root cause 4 (the 120-char cap) is the actual
  and sole blocker for Ontra.**

**Remote (remote) — STILL BROKEN (partially improved, not clean), same refined mechanism as Ontra.**
- Before (6 items): `['Customer Focus: Deep empathy for customers and a strong sense of what matters most in their day-to-day workflows', 'Language: Business-level proficiency writing and speaking English', 'What the job involves', "You'll report to: Senior Group Product Manager", 'Start date: As soon as possible', 'Interview with recruiter']`
- After (4 items): `['Customer Focus: Deep empathy for customers and a strong sense of what matters most in their day-to-day workflows', 'Language: Business-level proficiency writing and speaking English', 'What the job involves', 'Working closely with']`
- Verdict: **STILL BROKEN**, matching CR-067's prediction that Remote stays broken, but again via the
  120-char cap, not a pure boundary miss. Remote's JD also opens `"Role\nWho you are\n..."` (regex matches at
  char 5) and `extract_req_section()`'s fallback correctly returns the real section (`'Senior-Level
  Experience: Track record as a Product Manager...'` (124 chars), `'Customer Focus: ...'` (112 chars),
  `'Partner-Facing Experience: ...'` (156 chars), `'Stakeholder Management: ...'` (157 chars), `'Strong UX
  Sensibilities: ...'` (177 chars), `'Proficiency in Cursor and/or Claude Code (Required): ...'` (241
  chars)). Only "Customer Focus" (112 chars) and one other short line survive the 120-char cap; the other 4
  real bullets, all over 120 chars, get dropped, so the line-scan falls through into the next section's
  process/interview copy — a partial improvement (2 of the worst boilerplate items, "Start date" and
  "Interview with recruiter", dropped out) but the field still does not reflect Remote's real qualifications
  cleanly. Same mechanism as Ontra: **the 120-char cap, not the boundary/separator detection, is the actual
  blocker.**

**Covideo (covideo) — CHANGED TO A DIFFERENT WRONG ANSWER, exactly as CR-067 warned.**
- Before: `['Senior Product Manager', 'Indianapolis, IN Remote (US)', 'Key Responsibilities', 'The autonomy to truly own and shape high-impact product initiatives.', "A fast, collaborative environment where your work directly impacts the company's trajectory.", 'Competitive salary, comprehensive benefits, and a culture built around innovation, trust, and speed.']`
- After: `['The autonomy to truly own and shape high-impact product initiatives.', "A fast, collaborative environment where your work directly impacts the company's trajectory.", 'Competitive salary, comprehensive benefits, and a culture built around innovation, trust, and speed.', '401k plan with matching', 'Comprehensive health insurance (including vision and dental)', 'Flexible paid time off']`
- Verdict: **CHANGED TO A DIFFERENT, ARGUABLY WORSE WRONG ANSWER.** Before, `requirements` was a mix of
  title/location/responsibilities boilerplate; after, it is now 100% benefits/offer copy (401k, health
  insurance, PTO). Direct measurement confirms the mechanism CR-067 predicted: Covideo's real "Who You Are"
  bullets (5 of them, e.g. `'An Auto-Tech Expert: You have 4+ years of product management experience...'`)
  are 145-207 characters each — all dropped entirely by the 120-char cap — so the line-scan falls through
  the (correctly-bounded, blank-line-separated) captured span into "What We Offer"/"Benefits:" content
  further down. This is the single clearest confirmation that **Round 2 needs to address the 120-char cap**,
  independent of whatever it does about section boundaries.

### The 8 previously-good companies — regression check

- **Buyers Edge Platform, DataGrail, MyTime, PointClickCare, Redox, Lumos (6/8): byte-identical before and
  after.** No regression. For these 6, `_REQ_SECTION_RE` either found no match (Buyers Edge Platform) or
  matched `"Who you are"` at the very start of the document (char 5, same `"Role\nWho you are\n..."` layout
  as Ontra/Remote) where the real content happens to already be short enough to pass the 120-char cap and
  already appears first in raw-document order — so the pre-fix whole-JD scan and the post-fix
  section-scoped scan land on identical output by coincidence of document layout, not because the fix is
  inert for them.
- **Cresta, Group 1001 (2/8): measurably IMPROVED, not regressed.** Direct regex inspection shows both
  matched `"What We're Looking For"` (an *existing* pattern, already in `_REQ_SECTION_RE` before this CR) —
  **not** the new `who\s+you\s+are` phrase — so the improvement here is attributable entirely to Fix 2 (the
  `extract_req_section()` wiring), not Fix 1. Cresta's before list mixed real bullets with a bare heading
  fragment (`"What We're Looking For"`); after, all 6 items are clean, full requirement bullets. Group 1001's
  before list included 2 heading-fragment lines (`"Why This Role Matters:"`, `"This is a role for someone
  who:"`); after, all 6 items are clean, concrete requirement bullets (`"4+ years of product management
  experience..."`, `"Comfortable owning a product area end to end..."`, etc.).
- **The specific regression risk the tracker named — a "Who You Are" intro appearing *before* the real
  requirements section, causing the `.search()` to lock onto the wrong, earlier heading — was checked
  directly (regex match position + matched text logged per company above) and did NOT materialize for any of
  the 8 named previously-good companies.** Where `"who you are"` newly matches (5 of the 8), it happens to
  be the correct, intended heading, not a spurious earlier one — every one of these 5 JDs opens directly
  with `"Role\nWho you are\n<real content>"` as its very first lines, so there is no "earlier, wrong" heading
  for the new phrase to out-compete.

### Pytest

Pre-fix (`jd_tailoring.py` reverted via targeted `git stash`, `test_jd_profile_requirements.py` present but
failing): **31 failed / 195 passed / 1 skipped** (28 pre-existing + 3 new tests failing).
Post-fix: **28 failed / 198 passed / 1 skipped** (same 28 pre-existing failures, unchanged set, + 3 new
tests now passing). Confirms AC 5.

### Diff scope

`git diff --stat -- scripts/jd_tailoring.py` → `1 file changed, 4 insertions(+), 2 deletions(-)`, confined
to exactly the two scoped hunks (the `_REQ_SECTION_RE` alternation addition, the `req_source =
extract_req_section(jd_text)` rewire). Plus the new file `scripts/test_jd_profile_requirements.py`. Confirms
AC 7 — zero changes to `_NEXT_SECTION_RE`, the 120-char cap, `keywords`/`priority_themes`,
`score_claim_for_jd`, `THEME_KEYWORDS`, or `data/master_claims.json`.

### Honest Round 1 finding

**Mixed result, as CR-067 predicted for 3 of the 4 originally-broken companies — not a clean win.**
1/4 fixed cleanly (OneStream). 2/4 stayed broken (Ontra, Remote). 1/4 changed to a different, arguably worse
wrong answer (Covideo). Zero regressions among the 8 previously-good companies; 2 of them measurably
improved as an incidental benefit of Fix 2 alone.

**The one correction to CR-067's own diagnosis this round's measurement surfaces:** CR-067 attributed
Ontra/Remote's continued brokenness to root cause 3 (`_NEXT_SECTION_RE`'s no-blank-line-separator
blindness) and attributed the 120-char-cap failure mode only to Covideo. Direct measurement this round shows
`extract_req_section()`'s no-separator fallback (`remainder[:2000]`) actually works correctly for Ontra and
Remote — it returns their real "Who You Are" content. **The 120-char cap is the actual and sole blocker for
all 3 still-broken/wrong-answer companies (Ontra, Remote, Covideo)**, not a boundary-detection gap for
2 of the 3. This matters for Round 2 scoping: it suggests the 120-char cap fix alone (raise it, or
truncate-not-drop) may be sufficient to resolve Ontra, Remote, and Covideo without also needing the
Title-Case/no-separator boundary rework CR-067's Decision bundled in as part of "root cause 3." Round 2
should test the 120-char cap fix in isolation first (one-hypothesis-at-a-time, per this arc's established
discipline) and only add boundary-detection rework if the cap fix alone doesn't fully resolve these 3
companies — do not assume both are needed until measured.

**Round 2 is confirmed necessary** (2/4 originally-broken companies still broken; 1/4 arguably worse). Its
first-priority target, per this round's refined evidence, is the 120-char line-length cap, tested in
isolation before any boundary-detection changes.

## Round 2 — line-length-cap raise (PLANNED 2026-07-14, tech-lead; ready for senior-engineer)

Round 1's measurement narrowed root cause 3 down to a single mechanism: the 120-char line-length cap on
the `requirements` line-scan (`build_jd_profile_deterministic`, `scripts/jd_tailoring.py`, currently
`if 20 <= len(line) <= 120 and line[0].isalnum(): requirements.append(line[:120])`, ~line 138). Round 1
proved the cap — NOT boundary detection — is the actual and sole blocker for all 3 still-broken/wrong-answer
companies (Ontra, Remote, Covideo). This round is therefore a length-cap change ONLY. `_NEXT_SECTION_RE` is
NOT touched — Round 1 confirmed `extract_req_section()`'s no-separator fallback already returns the correct
"Who You Are" content for all 3 targets; the boundary detection is not the failure. Reopen boundary work
only if this round's own measurement contradicts that (it should not).

### The decided mechanism — raise the cap to 250, move truncation in lockstep

**Change exactly two numbers on the one filter line:** `120` → `250` in BOTH the upper-bound test and the
`line[:N]` slice, so the line reads:

```python
if 20 <= len(line) <= 250 and line[0].isalnum():
    requirements.append(line[:250])
```

Nothing else on the line or in the function changes. The `[:6]` cap on the final list stays (it is a
protection, not a defect — see below). The lower bound (20) stays.

**Why 250, specifically, and why not a higher or lower figure — this is measured, not a round guess:**
- The longest *real* requirement bullet found anywhere in the eval sample is 245 chars (Remote's "Domain
  Expertise (HRIS/Payroll…)" at 245 and "Proficiency in Cursor and/or Claude Code (Required)…" at 241;
  Lumos has a 245 too). A tech-lead scan of the *entire* 259-folder archive (read-only, via the current
  committed `extract_req_section()` + the existing filter) confirms the real single-requirement-bullet
  population tops out right at ~245-250 (bitsight 248, donorbox 245, hudu 246, first_advantage 250). Real
  requirement bullets are one sentence, or a labeled trait plus one sentence; they do not run longer than
  ~250 chars.
- Above 250 the line population flips character almost entirely to *multi-sentence paragraphs* — "About the
  company" / mission prose, EEO statements, benefits prose, comp-philosophy paragraphs (the archive's >250
  band is 417 lines and is dominated by exactly this boilerplate class). That is precisely the content the
  original cap existed to exclude.
- So 250 is the empirical break point between the real-bullet population and the paragraph-boilerplate
  population — the smallest value that admits essentially the entire real-bullet population while still
  rejecting the paragraph class. Going higher (260/280/300) buys near-zero additional real bullets and
  readmits progressively more paragraph boilerplate; going lower re-drops real bullets. It is round by
  coincidence, not by arbitrary choice.

**Why bound == truncation (both 250), not admit-high-then-truncate-low:** the truncation slice's only job
is to bound stored length. If we admit lines up to 250 but keep the store-slice at 120, an admitted 245-char
real bullet would be silently chopped back to 120 chars, and downstream claim scoring
(`score_all_claims` / keyword matching) would lose half the bullet's distinguishing vocabulary — defeating
the point of admitting it. So the store-slice moves to 250 in lockstep (at that point `line[:250]` is a
no-op belt-and-suspenders, since the filter already guarantees `len(line) <= 250`, but it keeps the two
numbers coherent and defensive against future edits). The rejected "admit-high-truncate-low" alternative
would readmit the paragraph-boilerplate class and store half of it — strictly worse. Over-limit (>250) lines
are still DROPPED entirely, exactly as today; only the threshold moves.

### The boilerplate-readmit risk is real but bounded — do NOT add a content filter to manage it

The archive scan confirms the 121-250 band does contain some boilerplate (EEO statements, comp ranges, visa
sponsorship, benefits prose) that the 120 cap currently drops and a 250 cap will admit. Two existing
mechanisms bound this, and they are why this stays a pure cap change:
1. **`extract_req_section()` scoping (shipped Round 1)** already restricts the scan to the requirements
   subsection, so most trailing EEO/comp/benefits boilerplate is outside the scanned span entirely.
2. **`requirements[:6]`** keeps only the first 6 qualifying lines, and real requirement bullets lead the
   requirements section — so raising the cap fills the 6 slots with real content *before* the scan reaches
   any trailing boilerplate. Tech-lead simulation confirms this holds for all 3 targets (see expected
   result below).

**Do NOT add a boilerplate keyword blocklist / content filter in this round.** That is a different class of
change (content classification, not length), it reintroduces exactly the ever-growing-pattern-list
whack-a-mole risk flagged in Open Question 3, and it is out of the length-cap-only scope this round is
deliberately held to. If the full-archive regression (step 6 below) surfaces a company where the raised cap
pulls boilerplate into the first 6 slots *ahead of* real requirements, log it as a candidate for a separate
Round 3 (boundary/ordering or content-filter) decision — do not fix it inline here.

### Round 2 ordered checklist (test-first, same discipline as Round 1)

- [x] **1. Re-confirm eval-set membership + pytest baseline at session start.** Re-run the 16-slug presence
      check against `data/archive/submissions/` (setup + Round 1 both found 12/16 — `sailpoint`, `tilt`,
      `par`, `parkingpass_com` absent; `par_technology` present but distinct, do NOT substitute). Confirm
      Ontra/Remote/Covideo all still present. Record the pytest baseline
      (`python -m pytest -q --ignore=test_domain_gate.py --ignore=test_fit_policy.py --ignore=test_llm.py`
      from `scripts/`) — expected 28 failed / 198 passed / 1 skipped (Round 1 close-out floor). Log actual.
      **Confirmed 2026-07-14: 12/16 unchanged (same present/missing list as Round 1). Ontra/Remote/Covideo
      all present. Pytest baseline: 28 failed / 198 passed / 1 skipped — exact match to the expected Round 1
      close-out floor.**
- [x] **2. Establish the pre-change `requirements` baseline for Ontra/Remote/Covideo on CURRENT code**
      (cap still 120, Fixes 1+2 live). This is the Round-1-post-fix state — re-capture it verbatim here so
      Round 2's before/after is against the exact shipping code, not Round 1's log. Confirm it matches Round
      1's post-fix tables (Ontra 0/6 real, Remote 2/6 real, Covideo 100% benefits copy). If it does not
      match, STOP — the code moved since Round 1; investigate before proceeding.
      **Confirmed 2026-07-14: byte-identical to Round 1's post-fix tables (encoding-artifact aside — the
      apostrophe in "Ontra is seeking..." rendered as a mojibake glyph in one console dump due to a
      terminal/codepage issue, not a content difference). No drift since Round 1; safe to proceed.**
- [x] **3. Write the failing unit test first**, added to the existing `scripts/test_jd_profile_requirements.py`
      (do not create a second file): (a) **kept-line test** — a crafted JD with a requirements heading
      followed by a genuine ~150-200-char requirement bullet (blank-line-separated, ALL-CAPS next-section
      heading so the boundary is clean), assert that bullet now appears in
      `build_jd_profile_deterministic(jd).requirements`. Confirm it FAILS against current (cap=120) code
      because the bullet is dropped. (b) **still-rejected test** — the SAME JD also contains a >250-char
      multi-sentence "About the company" paragraph inside the scanned span; assert that paragraph is NOT in
      `.requirements`. This pins that the cap was *raised*, not *removed* — the paragraph-boilerplate class
      is still excluded by the finite 250 bound. Confirm both assertions behave correctly (a fails pre-fix,
      b passes both pre- and post-fix since >250 is dropped at either cap).
      **Done — added `TestRequirementsLineLengthCapRaisedTo250` with 2 tests to
      `scripts/test_jd_profile_requirements.py`. Pre-fix (cap=120): test (a) confirmed FAILING —
      `AssertionError: 'Proven experience owning complex, multi-phase B2B SaaS product roadmaps...' not
      found in ['Comfortable partnering directly with engineering and design']` (the 185-char real bullet
      was dropped, only the short trailing bullet survived); test (b) confirmed PASSING pre-fix (>250-char
      paragraph already excluded at the old 120 cap too, so it has no discriminating power pre-fix — its
      value is purely as a post-fix pin that the cap wasn't removed).**
- [x] **4. Implement the cap change** in `scripts/jd_tailoring.py`: `120` → `250` in both the upper-bound
      comparison and the `line[:120]` slice on the single filter line. Change NOTHING else — not
      `_REQ_SECTION_RE`, not `_NEXT_SECTION_RE`, not `extract_req_section`, not the `20` lower bound, not
      `requirements[:6]`, not `keywords`/`priority_themes`, not `score_claim_for_jd`, not `THEME_KEYWORDS`,
      not `data/master_claims.json`. Confirm the step-3 test now passes.
      **Done exactly as scoped — `if 20 <= len(line) <= 250 and line[0].isalnum(): requirements.append(line[:250])`.
      All 5 tests in `test_jd_profile_requirements.py` pass post-fix (5/5).**
- [x] **5. Re-measure Ontra/Remote/Covideo, post-change, verbatim.** Record the full post-change
      `requirements[:6]` per company and diff against step 2. Give a plain per-company verdict: how many of
      the 6 slots are now real requirement bullets vs. residual heading-fragment/offer lines. (Tech-lead
      simulation expects: Ontra 5/6 real + 1 heading fragment; Remote 6/6 real; Covideo 5/6 real + 1 offer
      line — see "Expected result" below. Report the ACTUAL measured output, not this expectation.)
      **Done — see "Round 2 results" below. MEASURED result matches the tech-lead's simulation exactly for
      all 3 companies: Ontra 5/6 real + 1 heading fragment, Remote 6/6 real, Covideo 5/6 real + 1 offer
      line.**
- [x] **6. Full-archive regression check — the whole available sample, not just the Round-1 12.** The
      archive currently holds 259 submission folders (tech-lead count 2026-07-14; re-confirm — includes
      several `*_backup_*` folders, harmless to include). For every folder with an `Original_JD.txt`,
      capture `requirements[:6]` at cap=120 (pre) and cap=250 (post) and diff. The specific risk to hunt:
      any company where the raised cap pulls a boilerplate line (EEO / comp range / visa / benefits prose)
      into the first 6 slots *ahead of* a real requirement it displaced — i.e., a genuine regression, not
      just a longer-but-still-real bullet now appearing. Log every company whose first-6 changed, with a
      better/worse/lateral judgment. A company gaining a longer real bullet is "better/lateral"; a company
      where boilerplate displaced a real bullet is "worse" and must be named explicitly. Reuse the read-only
      probe approach (`extract_req_section()` + the filter at each cap) — do NOT edit archived JDs.
      **Done — see "Round 2 results" below. 259 folders total in the archive; 250 have `Original_JD.txt` (9
      do not — e.g. some `_backup_*` folders lack the file). Of the 250 checked, 156 had a changed first-6.
      A rule-based classifier (boilerplate-keyword regex: EEO/comp-range/visa/benefits/401k/background-check/
      etc.) plus a "was PRE already full at 6, did a non-boilerplate PRE item disappear from POST, did a
      NEW boilerplate item appear in POST" filter found exactly ONE genuine regression: `visionaire_partners`
      (a Dice-job-board-scrape JD already ~5/6 boilerplate pre-fix; the raised cap displaced its one
      surviving real-ish bullet, "Own and manage team backlog(s)", with a benefits-package sentence). Every
      other changed company was better or lateral (real bullet gained/lengthened, or a heading-fragment/
      compensation-heading/pay-transparency-statement line displaced OUT of the top 6 in favor of real
      content) — used a throwaway read-only probe script (`extract_req_section()` + the filter at each cap,
      never editing archived JDs), deleted after use so it doesn't pollute the diff.**
- [x] **7. Pytest regression check.** Re-run the baseline command. Must show the same failed count as step 1
      PLUS the new step-3 test(s) passing (passed count up by exactly the number of new tests, failed
      unchanged). Use a targeted `git stash push -- scripts/jd_tailoring.py` (NOT a full-repo stash — see
      the process note in the Session Handoff; a full stash pulls in unrelated in-flight work and breaks an
      unrelated test import) to confirm the same pre-existing-failure set exists pre- and post-change.
      **Done, with one honest process caveat.** Post-change (current live code, Round 1 + Round 2 both
      applied): **28 failed / 200 passed / 1 skipped** (200 = 198 Round-1-close-out floor + 2 new Round 2
      tests). A targeted `git stash push -- scripts/jd_tailoring.py` reverts the file to the last commit —
      but since Round 1's `jd_tailoring.py` changes are ALSO still uncommitted (same file, one diff), the
      stash reverts BOTH rounds at once, not Round 2 in isolation; there is no clean commit boundary between
      them to stash against. Reverted-state run: **32 failed / 196 passed / 1 skipped** (28 pre-existing +
      4 of the 5 `test_jd_profile_requirements.py` tests failing — the 2 Round 1 tests, the Round 1
      end-to-end test, and the Round 2 "kept-line" test all fail without the code; the Round 2 "still-
      rejected" test passes regardless, since >250-char content was already excluded at the old cap too).
      **Named-set diff, not just counts:** extracted the full failure list from both runs (excluding the
      5 `test_jd_profile_requirements.py` entries, which are expected to differ), sorted, and diffed —
      **byte-identical 28-item sets in both states.** This confirms the pre-existing 28-failure floor is
      unmoved by Round 2 (and, incidentally, reconfirms it was already unmoved by Round 1, consistent with
      Round 1's own close-out finding).
- [x] **8. `git diff --stat` scope confirmation.** The production diff must be confined to the single
      `requirements` filter line in `scripts/jd_tailoring.py` (`120` → `250`, twice). Zero changes to
      `_REQ_SECTION_RE`, `_NEXT_SECTION_RE`, `extract_req_section`, `keywords`/`priority_themes`,
      `score_claim_for_jd`, `THEME_KEYWORDS`, or `data/master_claims.json`. Plus the additive test edit to
      `scripts/test_jd_profile_requirements.py`.
      **Confirmed, with the same honest caveat as step 7: `git diff --stat -- scripts/jd_tailoring.py`
      against the last commit shows `1 file changed, 6 insertions(+), 4 deletions(-)`, but that diff
      contains Round 1's uncommitted changes too (the `_REQ_SECTION_RE` alternation addition and the
      `req_source` routing), since neither round is committed yet. Round 2's OWN edit — verified directly
      against this session's own tool-call record, exactly one `Edit` call to `scripts/jd_tailoring.py` —
      was precisely the single filter line's two-number change (`120`→`250` in the comparison, `120`→`250`
      in the slice), nothing else. No other line in the file was touched this round. The additive test edit
      to `scripts/test_jd_profile_requirements.py` (2 new test methods, no changes to the 3 existing Round 1
      tests) is the only other file touched.**
- [x] **9. Write the Round 2 finding honestly** in a "Round 2 results" section: per target company, how many
      real requirement bullets now surface vs. before, and name any residual non-requirement line still in
      the 6 (e.g. Ontra's "What the job involves" heading fragment, Covideo's one offer line — these are
      ordering artifacts, NOT length-cap issues, and are out of this round's scope; note them, do not fix
      them here). State the full-archive regression verdict: zero worse / N worse (named). Do not write a
      "fully fixed" summary if any target still shows majority-boilerplate or any good company regressed.
      **Done — see "Round 2 results" below.**
- [x] **10. Update docs on close-out.** Set frontmatter `status`, update the CR-068 registry row in
      `docs/spec/05-change-requests/README.md`, append the round result to `pipeline-log.md`, fill the
      Session Handoff block. Confirm no connector/gate changed (this touches only `scripts/jd_tailoring.py`,
      a scoring/extraction internal) — the CLAUDE.md pipeline-behavior doc checklist rows do not apply.
      **Done — see below.**

### Expected result (tech-lead simulation 2026-07-14 — report the MEASURED result, this is the hypothesis)

Read-only simulation at cap=250 (using the already-live `extract_req_section()` + the filter with 250 in
place of 120), against the current archived JDs:

- **Ontra:** 5/6 slots become the real "Who You Are" bullets ("Product Experience: 5+ years…",
  "Educational Background…", "Strategic Development…", "Technical Aptitude: Experience with AI development…",
  "Product Launch…"); slot 6 is the residual "What the job involves" heading fragment (an ordering artifact,
  not a cap issue). Was 0/6 real.
- **Remote:** 6/6 slots become real requirement bullets ("Senior-Level Experience…", "Customer Focus…",
  "Partner-Facing Experience…", "Stakeholder Management…", "Strong UX Sensibilities…", "Proficiency in
  Cursor and/or Claude Code (Required)…" — the last at 241 chars, previously dropped). Was 2/6 real.
- **Covideo:** 5/6 slots become the real bullets ("An Auto-Tech Expert…", "AI-Fluent…", "A High-Velocity
  Builder…", "A Cross-Functional Partner…", "Data-Driven & Customer-Centric…"); slot 6 is one residual
  offer line ("The autonomy to truly own…"). Was 0/6 real (100% benefits/offer copy).

### Honest expectation — will this fully resolve all 3?

**Expected to substantially resolve all 3, with one honest caveat.** The cap raise turns all 3 from
0-2 real bullets to 5-6 real bullets — a decisive improvement, and the primary goal (downstream claim
scoring receiving the real requirement signal) is met for all three. But it is NOT a perfectly clean 6/6
for Ontra or Covideo: each retains one residual non-requirement line in slot 6 (Ontra a heading fragment,
Covideo an offer line). Those residuals are section-boundary/ordering artifacts, not length-cap failures,
and are explicitly out of this round's length-cap-only scope. So the honest framing for the senior-engineer
and for close-out: Remote → expected clean 6/6; Ontra and Covideo → expected 5/6 real (functionally
resolved, one residual artifact each). Do NOT assume a flawless 6/6/6 result, and if the measured output is
worse than this simulation (e.g. the archive has churned and the ordering shifted), report the real numbers.
The full-archive regression (step 6) is the one genuinely unknown outcome — the simulation only checked the
3 targets and the eval-set diff, not all 259 folders' first-6 for boilerplate displacement; that check is
why step 6 exists and must be run, not assumed benign.

## Round 2 results

**Executed 2026-07-14, senior-engineer.** Change: `requirements` line-length filter cap raised from
`120` to `250` (both the upper-bound check and the store-slice), in `build_jd_profile_deterministic`
(`scripts/jd_tailoring.py`). No other line changed.

### The 3 target companies — verbatim before/after, measured against the tech-lead's simulation

**Ontra — MEASURED result matches simulation exactly.**
- Before (cap=120, 4 items): `['What the job involves', 'Ontra is seeking a Senior Product Manager
  reporting to our VP of Product, GM', "We're looking for a bold, senior product manager ready to solve
  complex problems on our flagship product", 'Cross-Functional Collaboration: Establish robust
  relationships across functions, collaborating on strateg']`
- After (cap=250, 6 items): `['Product Experience: 5+ years in product management with demonstrated
  ability to drive product vision and execute strategies effectively', "Educational Background:
  Bachelor's degree or higher in a relevant field, showcasing a strong foundation in product management
  principles", 'Strategic Development: Proven expertise in developing and executing product strategy,
  with a particular focus on platform products', 'Technical Aptitude: Experience with AI development,
  demonstrating a robust technical understanding and ability to collaborate with engineering teams',
  'Product Launch: Successful track record of launching new products, with a strong understanding of
  market needs and consumer behavior', 'What the job involves']`
- Verdict: **5/6 real requirement bullets** (items 1-5, all genuine "Who You Are" content, 130-148 chars
  each — exactly the population the 120-char cap was dropping). Slot 6 is a residual "What the job
  involves" heading fragment — a section-boundary/ordering artifact, explicitly out of this round's
  length-cap-only scope, not fixed here. Matches the tech-lead's simulated prediction exactly (5/6 real +
  1 heading fragment). Was 0/6 real before.

**Remote — MEASURED result matches simulation exactly.**
- Before (cap=120, 4 items): `['Customer Focus: Deep empathy for customers and a strong sense of what
  matters most in their day-to-day workflows', 'Language: Business-level proficiency writing and speaking
  English', 'What the job involves', 'Working closely with']`
- After (cap=250, 6 items): `['Senior-Level Experience: Track record as a Product Manager with a strong
  focus on Integrations, APIs, or Platform ecosystems', 'Customer Focus: Deep empathy for customers and a
  strong sense of what matters most in their day-to-day workflows', 'Partner-Facing Experience: Proven
  experience building trusted relationships with external organizations and communicating clearly in
  partner-facing settings', 'Stakeholder Management: Strong ability to align cross-functional stakeholders,
  navigate trade-offs, and keep teams focused on what matters most for customers', 'Strong UX
  Sensibilities: A passion for effortless experiences. You believe that data syncing, even at scale across
  jurisdictions, should feel simple and seamless to the end user', 'Proficiency in Cursor and/or Claude
  Code (Required): You must be able to autonomously build, debug, and ship functional code and prototypes
  — not just write specs. You can understand sample code, API responses, and integration flows hands-on']`
- Verdict: **6/6 real requirement bullets**, clean. All 6 are genuine "Who You Are" content (112-241 chars
  each, including the 241-char "Proficiency in Cursor and/or Claude Code" bullet the tech-lead specifically
  flagged as the longest real bullet in the eval sample). Matches the simulation exactly. Was 2/6 real
  before (only the two shortest bullets survived the old cap).

**Covideo — MEASURED result matches simulation exactly.**
- Before (cap=120, 6 items, 100% benefits/offer copy): `['The autonomy to truly own and shape high-impact
  product initiatives.', "A fast, collaborative environment where your work directly impacts the company's
  trajectory.", 'Competitive salary, comprehensive benefits, and a culture built around innovation, trust,
  and speed.', '401k plan with matching', 'Comprehensive health insurance (including vision and dental)',
  'Flexible paid time off']`
- After (cap=250, 6 items): `['An Auto-Tech Expert: You have 4+ years of product management experience
  specifically within the automotive technology, automotive SaaS, or dealership software space.',
  'AI-Fluent: You have significant hands-on experience leveraging AI tools for your own productivity,
  workflow automation, and process optimization.', 'A High-Velocity Builder: You have a proven track
  record of shipping major features or solutions quickly. You value progress, momentum, and continuous
  improvement over endless documentation.', 'A Cross-Functional Partner: You collaborate seamlessly across
  Engineering, Design, and Marketing, while working closely with Sales and Customer Success (CS) to gather
  user insights and ensure team alignment.', 'Data-Driven & Customer-Centric: You are comfortable digging
  into user metrics and feedback to guide your decisions and identify growth opportunities for the
  platform.', 'The autonomy to truly own and shape high-impact product initiatives.']`
- Verdict: **5/6 real requirement bullets** (items 1-5, all genuine "Who You Are" content, 145-207 chars
  each). Slot 6 is one residual offer line ("The autonomy to truly own...") — an ordering artifact, not a
  length-cap issue, explicitly out of scope for this round. Matches the tech-lead's simulated prediction
  exactly (5/6 real + 1 offer line). The 100%-benefits-copy wrong answer from Round 1 is fully corrected.

**All 3 targets match the tech-lead's simulation exactly — the simulation's read-only estimate held up
against the live measured function with zero deviation.**

### Full-archive regression check (259 folders total, 250 with `Original_JD.txt`)

156 of 250 checked folders had a changed `requirements[:6]` between cap=120 and cap=250. A rule-based
classifier (boilerplate-keyword regex covering EEO/comp-range/visa/benefits/401k/PTO/background-check/
pay-transparency/etc., cross-referenced against which PRE items disappeared vs. which POST items are new)
found the true-regression pattern the tracker asked to hunt for — a NEW boilerplate line displacing a real
bullet that was present in a PRE list that was already full (6/6) — in exactly **one** company:

- **`visionaire_partners` — the one named regression.** This is a Dice job-board scrape JD whose
  `requirements[:6]` was already ~5/6 boilerplate before this round (`'Hybrid in St. Louis, MO, US •
  Posted 3 days ago...'`, `'Dice Job Match Score™'`, `'6-month contract to hire'`, `'Hybrid in St. Louis,
  MO (3 days/week in-office)'`, `'Pay range: $80-91/hour W2'` — all job-board chrome, a pre-existing
  extraction failure unrelated to the cap). The one surviving real-ish item, `'Own and manage team
  backlog(s)'` (a short, generic responsibility line), got displaced post-fix by a newly-admitted 161-char
  benefits sentence (`'Visionaire Partners offers all full-time W2 contractors a comprehensive benefits
  package for the contractor, their spouses/domestic partners, and dependents.'`). Net effect: this
  already-badly-broken company went from 1/6 real to 0/6 real. Real, but marginal — the field was providing
  almost no signal either way.

Every other one of the 156 changed companies was **better or lateral**, confirmed by direct per-company
inspection of a sample spanning the full list plus targeted checks on every company the boilerplate regex
flagged (dailypay, workday, sago, zumper, koalafi, randstad_digital, openrouter, protege, kbr, adaptive):
- Several companies (dailypay, workday, sago, zumper, openrouter) had benefits/pay-transparency/comp-range
  boilerplate **displaced OUT of the top 6 in favor of real content** — a clean improvement, the same
  mechanism OneStream/Ontra/Remote/Covideo benefited from.
- `randstad_digital` gained 2 new real bullets AND one EEO-statement line was newly admitted — but its
  PRE list only had 3 items total (not full), so the EEO line filled a previously-empty slot rather than
  displacing any real content. Logged as the one case where boilerplate readmission is visible but does
  not meet the tracker's own "worse" bar (no real bullet displaced).
- `kbr` and `visionaire_partners`'s sibling scrape artifacts were already garbage pre-fix (Dice/Adzuna
  job-board chrome, not real JD prose) — a pre-existing extraction failure unrelated to this round's cap
  change, not something this round introduced or is scoped to fix.
- Companies like `adaptive`, `sago`, `zumper` already had benefits boilerplate present even at cap=120
  (short lines pass regardless of cap); the cap raise displaced that pre-existing boilerplate with newly-
  admitted longer real bullets, not the other way around.

**The 8 previously-good companies from Round 1 (Buyers Edge Platform, DataGrail, MyTime, PointClickCare,
Redox, Lumos, Cresta, Group 1001) — zero regressions.** 2 byte-identical (PointClickCare, Group 1001). The
other 6 changed, and every change was neutral-to-positive: real bullets got longer/more specific, or a
heading-fragment/compensation-section-heading line ("What the job involves", "Compensation At Cresta")
dropped out of the top 6 in favor of additional real content. No company in this set had a real bullet
displaced by boilerplate.

### Pytest

Post-change (current live code): **28 failed / 200 passed / 1 skipped** (200 = 198 Round-1-close-out floor
+ 2 new Round 2 tests). Reverted state (`git stash push -- scripts/jd_tailoring.py`, which reverts BOTH
Round 1 and Round 2 together since neither is committed — see the process note in step 7 above): **32
failed / 196 passed / 1 skipped**. Named-set diff of the 28 non-`test_jd_profile_requirements.py` failures
between the two runs: **byte-identical**. Confirms AC (no regression to the pre-existing failure floor).

### Diff scope

`git diff --stat -- scripts/jd_tailoring.py` against the last commit shows `1 file changed, 6
insertions(+), 4 deletions(-)` — but that diff spans both Round 1 and Round 2's uncommitted changes to the
same file (no commit boundary exists between them yet). Verified via this session's own tool-call record
that Round 2's actual edit was exactly the single filter line's two-number change (`120`→`250` in the
comparison, `120`→`250` in the slice) — no other line in `jd_tailoring.py` was touched this round. Plus the
additive edit to `scripts/test_jd_profile_requirements.py` (2 new test methods appended; the 3 existing
Round 1 tests are untouched).

### Honest Round 2 finding

**Round 2 resolves all 3 remaining companies to the "functionally resolved, real signal restored" bar the
tech-lead's simulation predicted — not a flawless 6/6/6, but a decisive fix.** Ontra and Covideo land at
5/6 real + 1 residual ordering artifact each (heading fragment / offer line, respectively — both explicitly
named as out-of-scope boundary/ordering issues, not length-cap failures). Remote lands at a clean 6/6 real.
All 3 measured results match the tech-lead's simulated prediction exactly — no deviation, no surprises.

**The full-archive regression check — the one genuinely unmeasured risk — surfaces exactly one named
regression: `visionaire_partners`**, and it is a marginal one (an already near-100%-boilerplate,
job-board-scrape JD losing its single remaining generic real-ish line to a benefits sentence). Zero
regressions among the Round 1 8-good set. This is a clean, honest, mostly-positive result with one small
named exception — not a "flawless, zero-risk" claim, and not smoothed over.

### Carry-forward open question (OQ3)

The residual slot-6 artifacts above are the boundary/ordering mechanism, not length. If a Round 3 is opened
to chase them and it starts needing an ever-growing `_NEXT_SECTION_RE` pattern list (the whack-a-mole shape
CR-063's `THEME_KEYWORDS` rounds took), that is the signal to raise "is regex the wrong tool for section
detection" with Jason before sinking more rounds into incremental patches — flagged, not resolved here.

## Guardrails (apply this whole CR, no exceptions)

- **Round 1 touches ONLY `_REQ_SECTION_RE` and the `requirements` line-scan source in
  `scripts/jd_tailoring.py`, plus the new test file.** `_NEXT_SECTION_RE`, the 120-char cap,
  `keywords`/`priority_themes`, `score_claim_for_jd`, `THEME_KEYWORDS`, and `data/master_claims.json` are
  all off-limits in Round 1. Confirm via `git diff --stat` at close-out.
- **Test-first, real before/after numbers logged as you go**, not a reconstructed summary. The per-company
  `requirements` lists pre- and post-fix are the evidence; they must appear verbatim in this file.
- **Source JDs from `data/archive/submissions/`, never `data/submissions/`** (the sync-unstable live
  location). If the archive churns mid-session, log it as a data caveat — same honesty standard the whole
  arc used.
- **Do not regenerate or edit any archived submission** — JDs are fixed, read-only test input.
- **A zero or mixed Round 1 result is valid and must be logged as-is.** Do not tune, expand scope, or reach
  into Round 2 mid-Round-1 to manufacture a cleaner-looking win.

---

## Session Handoff — read this FIRST, fill it in before you stop

Whoever is reading this at the start of a session: check "Last updated" below.

- **Last updated:** 2026-07-15 — engineering-manager, CR-068 CLOSED as **complete / APPROVED**. Both rounds
  cleared every gate: Security Review CLEAR (both rounds), QA PASS (both rounds), and EM independent
  re-verification confirmed the pytest floor (28F/200P/1S), the 4-company final state, the shipped code, the
  scope boundary, and the single `visionaire_partners` regression. See `../../pipeline-log.md`,
  "Engineering Manager — CR-068 Close-out". Frontmatter `status: complete`.
- **Current stage:** **CLOSED — complete, APPROVED.** The two shipped changes (Round 1: `who you are` +
  `required education and experience` added to `_REQ_SECTION_RE`, `requirements` scan rewired through
  `extract_req_section()`; Round 2: line-length cap 120→250 on both the bound and the store-slice) are live
  and uncommitted in `scripts/jd_tailoring.py`. Final measured state, EM-reproduced: OneStream substantively
  fixed (5 real bullets + 1 "Preferred Education and Experience" heading fragment, all boilerplate gone),
  Remote clean 6/6 real, Ontra 5/6 real + 1 "What the job involves" heading fragment, Covideo 5/6 real + 1
  "The autonomy to truly own..." offer line. All 4 originally-broken companies substantially improved; the
  Round 1 Covideo "different wrong answer" regression is fully corrected. One honestly-disclosed marginal
  regression across the full 250-folder archive (`visionaire_partners`, an already near-100%-boilerplate
  Dice-scrape JD whose one generic real-ish line was displaced — the field was giving near-zero signal either
  way). Zero regressions among the 8 previously-good companies. Pytest 28F/200P/1S, same 28-item pre-existing
  floor. Docs completed at close-out: tracker frontmatter → complete, README registry row → Complete,
  CHANGELOG `### Fixed` CR-068 entry added (consistent with CR-066's close-out convention for this arc).
- **Exact next action:** none required for CR-068 itself — the work is done and approved. The remaining
  decision is Jason's: **commit** Round 1 + Round 2 (one combined diff to `scripts/jd_tailoring.py`, since
  neither round was committed mid-arc — no clean commit boundary exists to split them) plus the new
  `scripts/test_jd_profile_requirements.py`, and close the CR as Accepted; **keep open** only if Jason wants
  a Round 3 to chase the residual ordering artifacts (see OQ3 below); or **hold** as-is. EM recommendation is
  to close as Accepted — the residuals are out-of-scope boundary/ordering artifacts, not length failures, and
  chasing them risks the regex whack-a-mole OQ3 warns about.

### Carry-forward pointers for the next session (open threads, none blocking CR-068's close)

1. **OQ3 — residual slot-6 ordering artifacts + regex whack-a-mole risk.** Ontra ("What the job involves"
   heading fragment) and Covideo ("The autonomy to truly own..." offer line) each keep one non-requirement
   line in slot 6. These are a *different mechanism* (section-boundary/ordering, not length) and were
   explicitly out of Round 2's length-cap-only scope. If a Round 3 is opened to chase them and it starts
   needing an ever-growing `_NEXT_SECTION_RE` pattern list, that is the signal to raise "is regex the wrong
   tool for section detection" with Jason before sinking more rounds into incremental patches. Flagged, not
   resolved.
2. **`ACC-401-AITOOLS` / `ACC-204` under-scoring** — separate, still-open thread carried from CR-065/066
   Out-of-Scope. No evidence any `requirements` fix addresses it; unrelated to CR-068.
3. **`cover_claim_picker.py` flat-bonus calibration** — still-open question from CR-064's close-out: the
   flat 3-8pt proof bonuses were tuned against the pre-CR-064 score scale and may be mis-calibrated against
   the reworked scale. Jason-gated calibration follow-up, deliberately not folded into any CR in this arc.
   (Note: `scripts/cover_claim_picker.py` carries unrelated uncommitted arc work in the current tree — that
   is CR-061/CR-064 territory, not CR-068.)
- **The Round 1 result, honestly:** Mixed, as CR-067 predicted for 3/4 originally-broken companies.
  1/4 fixed cleanly (OneStream). 2/4 stayed broken (Ontra, Remote). 1/4 changed to a different, arguably
  worse wrong answer (Covideo, now 100% benefits copy). Zero regressions among the 8 previously-good
  companies; 2 of them (Cresta, Group 1001) measurably improved as an incidental benefit of Fix 2 alone (not
  Fix 1 — their matched heading was `"What We're Looking For"`, an existing pattern, not the new `who you
  are` phrase). Full verbatim before/after tables and per-company verdicts are in "Round 1 results" above —
  read that section before planning Round 2, don't reconstruct from memory.
- **The one correction to CR-067's own diagnosis this round surfaced:** CR-067 attributed Ontra/Remote's
  continued brokenness to root cause 3 (`_NEXT_SECTION_RE`'s no-blank-line-separator blindness) and treated
  the 120-char-cap failure as Covideo-specific. Direct measurement this round shows `extract_req_section()`'s
  no-separator fallback actually works correctly for Ontra and Remote (it returns their real "Who You Are"
  content) — **the 120-char cap is the actual and sole blocker for all 3 still-broken/wrong-answer companies
  (Ontra, Remote, Covideo)**, not a boundary-detection gap for 2 of the 3. This changes Round 2's likely
  priority: test the 120-char cap fix (raise or truncate-not-drop) in isolation FIRST, one-hypothesis-at-a-
  time, before assuming the Title-Case/no-separator boundary rework is also needed — it may not be, for this
  sample.
- **What's confirmed for Round 2 (do not redo unless code moves):** the 120-char cap
  (`20 <= len(line) <= 120`, `jd_tailoring.py` requirements line-scan) and `_NEXT_SECTION_RE`
  (ALL-CAPS/markdown-only boundary detection) are both still exactly as CR-067 described them — neither was
  touched in Round 1.
- **Open Questions resolved at setup (still hold):** (OQ1) Round 1 unit test lived in the new
  `scripts/test_jd_profile_requirements.py`, done. (OQ2) Round 2 scope — now informed by Round 1's
  measurement: cap fix first, boundary rework only if the cap fix alone leaves companies broken. (OQ3, "is
  regex the wrong tool") still open, still worth raising with Jason if Round 2's pattern list keeps growing.
- **Known data caveat:** working sample re-confirmed 12/16 this session (`sailpoint`, `tilt`, `par`,
  `parkingpass_com` absent, unchanged); `par_technology` present but distinct from `par` — do not substitute.
  Re-confirm again at the start of whichever session runs Round 2.
- **Process note for whoever runs Round 2:** a full-repo `git stash` is unsafe in this repo right now — the
  working tree carries a large amount of unrelated uncommitted in-flight work across many files, and a
  full-repo stash pulled in unrelated changes and broke an unrelated test file's import
  (`test_jd_completeness.py` importing a name from `batch_pipeline.py` that only exists in the uncommitted
  version). Use a targeted `git stash push -- <specific file>` instead, as this session did for the pytest
  regression check.
