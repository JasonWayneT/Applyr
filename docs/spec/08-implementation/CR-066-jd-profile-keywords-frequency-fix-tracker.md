---
status: complete
created: 2026-07-14
spec: ../05-change-requests/CR-066-jd-profile-keywords-frequency-fix.md
eval_set: ../../reports/jd-theme-claim-eval-set.md
predecessor_tracker: CR-065-jd-profile-extraction-diagnostic-tracker.md
---

# CR-066 Tracker — JD-Profile `keywords` Fix, Alphabetical to Frequency-Sorted (`build_jd_profile_deterministic`)

Resumable round-by-round log, same discipline as its predecessors CR-063/CR-064/CR-065. **Read the
Session Handoff block at the very bottom of this file first** — if a prior session left one filled in,
that block tells you exactly where to pick up, and you should trust it over re-deriving state from the
round logs yourself. Right now the handoff block is pre-filled with the starting state (this CR hasn't
had a working session yet) — treat it as the literal first thing to do, not a template to ignore.

**This is the FIRST production code change in the CR-063 -> 064 -> 065 -> 066 arc.** CR-063/064/065 were
all diagnostic-only against standalone scripts; this CR edits `scripts/jd_tailoring.py`'s
`build_jd_profile_deterministic` directly, a function with 9 real call sites (4 live pipeline, 5
test/measurement — all confirmed below). That raises the risk profile: the guardrail set here is the full
CR-064-era battery (pytest baseline, cover-letter-side hand-check, full eval-set re-measurement), not the
`git diff --stat`-only check CR-065 could get away with. The fix mechanism itself is not being
re-litigated — CR-065 Round 1 measured it cleanly (universal in Part B, isolated in 5/6 Part E companies,
independently reproduced by Security Review and QA the same day). This CR ships that measured fix; it does
not re-open whether the fix is right.

Read `CR-066-jd-profile-keywords-frequency-fix.md` first if you haven't this session — it has the full
Problem, the exact Decision code change, all 9 Acceptance Criteria, the Out-of-Scope list (which reserves
the `requirements`/`extract_req_section()` defect for CR-067 and explicitly keeps it out of this CR), and
the two operational Open Questions this tracker resolves below. Then read the predecessor tracker
`CR-065-jd-profile-extraction-diagnostic-tracker.md`'s Session Handoff block — that is the finding this CR
acts on.

## Checkpointing protocol — this work may span multiple sessions, plan for it

Same four rules CR-063/CR-064/CR-065 used, because they worked:

1. **Before executing any plan — a full round, or a specific measurement within a round — write the plan
   out as its own ordered checklist right here in this file**, under the round you're working on, even if
   it's more granular than what's pre-written below.
2. **Check off and log each step as you finish it, not in a batch at the end.** Real state (the actual
   per-company before/after numbers, the actual selected cover-letter claims and order), not a stale
   unchecked list or a reconstructed-from-memory summary. The pre-fix baseline number and the post-fix
   number must both be written into this file against the *same named company set*, not summarized away.
3. **If you sense you're running low on context or session time, stop at the nearest checkpoint boundary.**
   A cleanly stopped, fully logged step beats a rushed, unlogged batch. Natural boundaries here: after the
   pre-fix baseline is logged (before touching code); after the fix + unit test land and pytest is green;
   after the full-sample re-measurement; after the cover-letter hand-check.
4. **Before ending any session on this CR, fill in the Session Handoff block at the bottom.** Read first by
   whoever comes next, before anything else in this document.

## Before Round 1 — orientation (do this once)

Tech-lead pre-verified the four items below during CR-066 setup (2026-07-14). They are marked `[x]` with
the state found at that time. **The eval-set membership item (and only that item) must be re-confirmed by
whoever executes this CR at the start of their own session** — the archive is not immune to the same sync
churn that made SailPoint vanish within hours during CR-065 (CR-064 Round 5 finding, repeated CR-065 QA
pass). The other three items are stable code/behavior facts and do not need re-running unless the code has
moved.

- [x] **Read the spec in full** (`CR-066-jd-profile-keywords-frequency-fix.md`) — Problem, Decision (8
      items, with the exact `Counter`-based replacement code), 9 Acceptance Criteria, Out of Scope (CR-067
      reserved for the `requirements` defect; do NOT touch `extract_req_section()`), 2 Open Questions
      (resolved below), Traceability Mapping.
- [x] **Confirm all 9 real call sites of `build_jd_profile_deterministic` — verified accurate at
      approximately the spec's stated lines (tech-lead, 2026-07-14).** The signature
      (`(jd_text: str, fit_summary: str = "") -> JdProfile`) is unchanged by this CR, so none of these
      requires any edit; they are listed only to prove that claim before close-out (Acceptance Criterion 2):
      - Live pipeline: `local_draft_stages.py:377` (import at :375), `cover_jd_needs.py:397` (import at :7),
        `cover_letter_compiler.py:129` (import at :127), `cover_plan_builder.py:50` (import at :13).
      - Test/measurement: `measure_semantic_rerank.py:36`, `measure_theme_extraction.py:67`,
        `smoke_draft_compiler.py:60` (and :126/:204/:225/:361), `test_ai_signal_routing.py:50` (and :59),
        `test_cover_claim_picker.py:35` (and :44). Plus `measure_jd_profile_extraction.py:73/:164` (the
        CR-065 diagnostic script this CR extends).
- [x] **Confirm the current eval-set membership in `data/archive/submissions/` — 12/16 present as of
      2026-07-14 (tech-lead setup run).** Ran `available_eval_set()` (in
      `measure_jd_profile_extraction.py`) against the live `EVAL_SET` (16 rows in `measure_theme_extraction.py`):
      - **Present (12):** `buyers_edge_platform`, `covideo`, `cresta`, `datagrail`, `group_1001`, `lumos`,
        `mytime`, `onestream_software`, `ontra`, `pointclickcare`, `redox`, `remote`.
      - **Missing (4):** `sailpoint`, `tilt`, `par`, `parkingpass_com`. `tilt`/`par`/`parkingpass_com` were
        never in the archive this session-arc; **`sailpoint` is the one that regressed** — present during
        CR-065 Round 1 execution, gone by CR-065's QA pass, still gone now. So this CR's working sample is
        **12, not the "13/13" CR-065 language carries.** The archive also contains `par_technology`, a
        *different* folder from the eval-set `par` slug — do NOT substitute it.
      - **RE-CONFIRM THIS AT EXECUTION TIME.** If SailPoint has returned, the sample is 13; log whichever it
        is, and run BOTH the pre-fix and post-fix measurements against that same named set (Acceptance
        Criterion 9). Do not carry forward a number from setup without re-checking.
- [x] **Confirm `keywords_frequency_sorted()` (`measure_jd_profile_extraction.py:96-108`) matches the
      spec's Decision item 1 exactly — verified byte-for-byte (tech-lead, 2026-07-14).** Same
      `_jd_body_for_themes(jd_text)` source text, same `.lower()`, same `re.findall(r"[a-z]{5,}", ...)`,
      same 5-word stopword set (`_KEYWORD_STOPWORDS = {"about", "their", "would", "should", "other"}` at
      line 43, identical to `jd_tailoring.py:140`'s inline set), same `Counter`, same
      `sorted(..., key=lambda kv: (-kv[1], kv[0]))` (descending frequency, alphabetical tie-break), same
      `[:12]` cutoff. The Decision code is this function's body moved inline into
      `build_jd_profile_deterministic` — the only production edit is swapping the two `keywords` lines
      (139-140) plus adding `from collections import Counter` at the top of `jd_tailoring.py`.
- [x] **Record the pytest baseline once — confirmed 28 failed / 190 passed / 1 skipped (tech-lead,
      2026-07-14), matching the CR-064/065 baseline the spec cites.** Command:
      `python -m pytest -q --ignore=test_domain_gate.py --ignore=test_fit_policy.py --ignore=test_llm.py`
      (run from `scripts/`). This is the pre-existing-failure floor: Round 1's post-fix run must show the
      *same* 28F/190P/1S plus the new unit test(s) from Acceptance Criterion 7, all passing. Any other
      movement must be explained, not assumed benign (Acceptance Criterion 6). The 28 pre-existing failures
      are unrelated to this CR's surface area (cover word-padding, gap-detector, submission-linter, etc.);
      do not "fix" them here — that is scope creep against a CR with a deliberately narrow diff.

## Open Questions — resolved by tech-lead at setup (do not re-decide ad hoc)

Both of the spec's Open Questions are operational implementation-sequencing calls, not product-behavior
decisions, and the spec explicitly delegates them to whoever executes the CR. Resolved here so the choice
is recorded once rather than made silently mid-implementation:

1. **Where the new unit test(s) live (spec OQ1) — RESOLVED: a new dedicated test file
   `scripts/test_jd_profile_keywords.py`, asserting directly against `build_jd_profile_deterministic()`'s
   `.keywords` output. Do NOT extract a separate keyword-selection helper.** Rationale: (a) Minimum
   footprint — not extracting a helper keeps the `jd_tailoring.py` diff to exactly the two `keywords` lines
   plus the `Counter` import, which is precisely what Acceptance Criterion 8's `git diff --stat` check
   expects to see and nothing more. Extracting a helper widens the diff and invites unrelated churn. (b)
   Testing the production entry point directly (not an extracted helper) is the most faithful regression
   guard — it fails if *anything* in the real path reverts to alphabetical sorting, changes the stopword
   set, the `[a-z]{5,}` length filter, or the `[:12]` cutoff, which is exactly what Acceptance Criterion 7
   asks for. A new file (rather than appending to an existing `test_*.py`) keeps the traceability clean and
   the diff attributable.
2. **Extend `measure_jd_profile_extraction.py` in place vs. new script (spec OQ2) — RESOLVED: extend in
   place, via an additive `--full` mode (or expanded `main()`), NOT a new script.** Rationale: that script
   already owns every function this CR's full-sample measurement needs — `available_eval_set()`,
   `keywords_frequency_sorted()`, `ranking_spike()` (`:162`), and the imported `code_hits_top5` — so a new
   script would fork that measurement logic and risk the two drifting out of sync (the exact DRY failure
   mode this session-arc has been disciplined about). A `--full` flag is purely additive: it does not alter
   the existing Part A `main()` path CR-065 reviewed and signed off on, which satisfies the "don't disturb a
   reviewed script" concern behind the question. QA's CR-065 finding (Parts C/D/E lack a single-command
   entry point) is resolved by this same extension.

## Round 1 — implement the fix, test-first, with pre-fix baseline locked before any code change

Ordered checklist covering the spec's 9 Acceptance Criteria. **Sequence matters: the pre-fix baseline
(step 2) MUST be captured and logged BEFORE the code changes (step 4)**, per spec Decision item 5 — a
post-hoc baseline from a different sample is not apples-to-apples and does not satisfy Acceptance Criterion
3/9. Write real numbers into this file as each step completes.

- [x] **1. Re-confirm eval-set membership at execution start.** Re-run `available_eval_set()` (or an `ls`
      of `data/archive/submissions/` against the 16 EVAL_SET slugs). Log the actual present/missing lists
      and the count (12 or 13) HERE, dated. This named set is what both the pre-fix and post-fix
      measurements run against (Acceptance Criterion 9). Setup found 12 (SailPoint missing); confirm whether
      that still holds.
      **Result (2026-07-14, senior engineer):** Still 12/16. Present: `cresta`, `group_1001`,
      `onestream_software`, `buyers_edge_platform`, `ontra`, `remote`, `covideo`, `datagrail`, `mytime`,
      `pointclickcare`, `redox`, `lumos`. Missing (unchanged): `sailpoint`, `tilt`, `par`,
      `parkingpass_com`. No drift since tech-lead's setup run.
- [x] **2. Establish the pre-fix baseline on the CURRENT (unfixed) code, on the confirmed sample.** Before
      touching `jd_tailoring.py`, run the full-sample measurement (the `--full` extension from step 3 can be
      landed first as pure measurement code, since it does not alter production behavior — or run the
      existing helpers ad hoc) against the unmodified `build_jd_profile_deterministic`. Record: (a)
      `ACC-105-EXECUTION`'s top-5 appearance count across the sample (spec expects ~9/13 range; on 12
      companies the exact number is TBD at execution), and (b) the full `code_hits_top5`-style
      per-company + aggregate should-surface hit-rate table. This is THIS CR's own baseline — cite the
      CR-064-era 10/14 and CR-065 Part C 9/13 numbers for context only; neither is the apples-to-apples
      baseline (spec Decision item 5). Log the full table here.
      **Result: pre-fix baseline = ACC-105-EXECUTION 9/12 top-5, aggregate should-surface hit rate 10/34.**
      Full per-company table in "Round 1 results" below.
- [x] **3. Extend `measure_jd_profile_extraction.py` with a `--full` mode** (per resolved OQ2) that runs the
      frequency-keywords ranking spike and the aggregate hit-rate accounting across the full available
      sample in one command. Additive only — do not alter the existing Part A `main()` path. (This can land
      before or alongside step 2 since it is measurement-only, non-production code.)
      **Result:** Added `full_sample_hit_rate()` + `print_full_sample_report()` + a `--full` CLI flag in
      `main()`. Runs `build_jd_profile_deterministic()` (the real production function) across
      `available_eval_set()`, so the same command measures pre-fix when run against unfixed code and
      post-fix when run against fixed code — no separate spike duplication needed since this CR edits the
      real function directly. Part A's existing `main()` path is untouched.
- [x] **4. Write the failing unit test first (test-first)** in the new
      `scripts/test_jd_profile_keywords.py` (per resolved OQ1): assert `build_jd_profile_deterministic()`'s
      `.keywords` is frequency-sorted (a crafted JD where a defining noun repeats should rank it above an
      alphabetically-earlier generic word that appears once), with a case pinning alphabetical tie-break,
      the 5-word stopword exclusion, the `[a-z]{5,}` length filter, and the `[:12]` cutoff. Confirm it FAILS
      against the current alphabetical code first (proves the test has teeth).
      **Result:** 5 tests written. Against unfixed code:
      `test_frequent_defining_noun_outranks_alphabetically_earlier_rare_word` and `test_cutoff_is_twelve`
      FAILED (2 failed, 3 passed — the tie-break/stopword/length-filter cases pass under alphabetical too,
      which is correct, they're still valid regression guards). After a first draft of the frequency test
      had a self-inflicted bug (a false failure caused by `_jd_body_for_themes()`'s 72%-of-text truncation
      clipping a low-frequency word out of the source text before counting, not by the production code),
      the test text was fixed to interleave/pad so all crafted words land inside the retained 72% — see
      code comments in the test file. Re-ran against unfixed code afterward and got the clean single-cause
      failure above before implementing.
- [x] **5. Implement the fix in `scripts/jd_tailoring.py`.** Add `from collections import Counter` at the
      top; replace lines 139-140 with the spec Decision item 1 code (frequency-sorted, alphabetically
      tie-broken, same length filter / stopword set / `_jd_body_for_themes` source / `[:12]` cutoff). Change
      NOTHING else — not `priority_themes`, not the `requirements` line-scan, not `extract_req_section()`,
      not `THEME_KEYWORDS`, not `score_claim_for_jd` (Acceptance Criterion 8, Out of Scope). Confirm the
      unit test from step 4 now passes.
      **Result:** Implemented exactly per spec Decision item 1. All 5 new tests pass.
- [x] **6. Re-measure full-sample, post-fix, on the SAME named set as step 2.** Run the `--full`
      measurement again. Record the post-fix `ACC-105-EXECUTION` top-5 count (Acceptance Criterion 3: must
      drop from the step-2 baseline) and the full post-fix `code_hits_top5` table. **Diff it against step 2
      per company:** any claim that correctly surfaced in top-5 pre-fix and stops surfacing post-fix, for a
      company where CR-065 did NOT already document that exact effect, must be logged and explained here
      before close-out — not silently absorbed into "the fix worked" (Acceptance Criterion 4).
      `ACC-105-EXECUTION` dropping where it was an over-representation is expected and fine.
      **Result: post-fix = ACC-105-EXECUTION 5/12 top-5 (dropped from 9/12, as expected), aggregate
      should-surface hit rate 11/34 (improved from 10/34, zero regressions).** Full diff in "Round 1
      results" below.
- [x] **7. Cover-letter-side hand-check on 2-3 eval-set JDs, before and after.** `keywords` also feeds
      `pick_cover_bullets` / `cover_claim_picker.py`'s `_proof_score` via the same `JdProfile`. For at least
      2-3 companies, log the actual selected cover-letter proof-point claims AND their relative order,
      pre-fix and post-fix, in a table here (Acceptance Criterion 5). This is the CR-064-established
      discipline that `measure_theme_extraction.py` alone does not exercise.
      **Result:** Hand-checked Cresta, DataGrail, Redox. Cresta and Redox: identical claim selection and
      order pre/post. DataGrail: 3rd proof changed `ACC-115-RETENTION` -> `ACC-109-SYNTHESIS` (1st and 2nd
      unchanged). Table in "Round 1 results" below.
- [x] **8. Pytest regression check.** Re-run
      `python -m pytest -q --ignore=test_domain_gate.py --ignore=test_fit_policy.py --ignore=test_llm.py`
      from `scripts/`. Must show 28 failed / 190 passed / 1 skipped (the setup-confirmed baseline) PLUS the
      new `test_jd_profile_keywords.py` test(s) passing — i.e. passed count rises by exactly the number of
      new tests, failed stays 28, skipped stays 1. Any other movement gets explained here before close-out
      (Acceptance Criterion 6).
      **Result: 28 failed / 195 passed / 1 skipped** (190 + 5 new tests, all passing). Additionally
      verified via `git stash` that the same 28 failures by exact test name exist both pre-fix and post-fix
      -- zero new failures caused by this change, zero pre-existing failures fixed incidentally.
- [x] **9. `git diff --stat` scope confirmation.** Confirm the diff shows exactly: the `keywords`-selection
      lines + `Counter` import in `scripts/jd_tailoring.py`, the additive `--full` code in
      `scripts/measure_jd_profile_extraction.py`, the new `scripts/test_jd_profile_keywords.py`, and the
      tracker/spec/registry docs. Zero changes to `priority_themes` construction, `extract_req_section()`,
      `THEME_KEYWORDS`, `score_claim_for_jd`, or `data/master_claims.json` (Acceptance Criterion 8).
      **Result:** `git diff -- scripts/jd_tailoring.py` shows exactly the `Counter` import (+1 line) and
      the 2-line-to-3-line `keywords` selection swap (net +6/-2 lines). Nothing else in that file changed.
      `measure_jd_profile_extraction.py` and `test_jd_profile_keywords.py` are new/untracked files (the
      former already existed from CR-065 and is extended, not newly created).
      `docs/spec/05-change-requests/README.md`'s CR-066 row was already added at tech-lead setup (predates
      this session). No changes anywhere to `priority_themes`, `extract_req_section()`, `THEME_KEYWORDS`,
      `score_claim_for_jd`, or `data/master_claims.json`.
- [x] **10. Update docs on close-out.** Set this tracker's frontmatter `status`, update the CR-066 registry
      row status in `docs/spec/05-change-requests/README.md`, and fill the Session Handoff block below.
      (No connector/gate changed, so the CLAUDE.md pipeline-behavior doc checklist rows do not apply here —
      but confirm that judgment at close-out.)
      **Result:** Done below. Confirmed no connector/gate touched, so the CLAUDE.md doc-update checklist
      rows do not apply to this CR.

## Round 1 results

**Eval-set sample (12/16, re-confirmed 2026-07-14):** `cresta`, `group_1001`, `onestream_software`,
`buyers_edge_platform`, `ontra`, `remote`, `covideo`, `datagrail`, `mytime`, `pointclickcare`, `redox`,
`lumos`. Missing: `sailpoint`, `tilt`, `par`, `parkingpass_com`.

### Pre-fix baseline (current alphabetical code, `python measure_jd_profile_extraction.py --full`)

| Company | top5 | should-surface hits | ACC-105-EXECUTION top5? |
|---|---|---|---|
| Cresta | ACC-112-COMPLIANCE, ACC-105-EXECUTION, ACC-105-PROCESS, ACC-106-DATA, ACC-101-RETENTION | ACC-107 MISS, ACC-103 MISS, ACC-101 HIT | True |
| Group 1001 | ACC-113-MIGRATION, ACC-109-PROCESS, ACC-202-REQUIREMENTS, ACC-105-EXECUTION, ACC-102-INT | ACC-101 MISS, ACC-103 MISS, ACC-105 HIT, ACC-107 MISS, ACC-113 HIT | True |
| OneStream | ACC-103-SEC, ACC-112-COMPLIANCE, ACC-103-ROADMAP, ACC-102-LEAD, ACC-105-EXECUTION | ACC-107 MISS | True |
| Buyers Edge Platform | ACC-109-PROCESS, ACC-112-COMPLIANCE, ACC-102-INT, ACC-113-MIGRATION, ACC-108-OPS | ACC-109 HIT, ACC-204 MISS | False |
| Ontra | ACC-202-REQUIREMENTS, ACC-102-INT, ACC-113-MIGRATION, ACC-112-PIPELINE, ACC-112-COMPLIANCE | ACC-401-AITOOLS MISS, ACC-103 MISS | False |
| Remote | ACC-112-COMPLIANCE, ACC-102-INT, ACC-107-PLATFORM, ACC-113-MIGRATION, ACC-109-PROCESS | ACC-401-AITOOLS MISS, ACC-106 MISS | False |
| Covideo | ACC-108-SUPPORT, ACC-111-SCOPE, ACC-105-EXECUTION, ACC-111-ENTERPRISE, ACC-113-ADOPTION | ACC-401-AITOOLS MISS, ACC-105 HIT | True |
| DataGrail | ACC-105-EXECUTION, ACC-111-ENTERPRISE, ACC-103-SEC, ACC-103-ROADMAP, ACC-107-COMPLIANCE | ACC-107 HIT, ACC-401-AITOOLS MISS, ACC-103 HIT | True |
| MyTime | ACC-202-REQUIREMENTS, ACC-105-EXECUTION, ACC-109-EXEC, ACC-201-ALIGNMENT, ACC-202-DELIVERY | ACC-401-AITOOLS MISS, ACC-104 MISS, ACC-105 HIT | True |
| PointClickCare | ACC-109-PROCESS, ACC-112-PIPELINE, ACC-112-COMPLIANCE, ACC-105-EXECUTION, ACC-109-EXEC | ACC-101 MISS, ACC-102 MISS, ACC-109 HIT, ACC-401-AITOOLS MISS | True |
| Redox | ACC-112-COMPLIANCE, ACC-109-PROCESS, ACC-105-EXECUTION, ACC-111-ENTERPRISE, ACC-113-MIGRATION | ACC-101 MISS, ACC-103 MISS, ACC-109 HIT | True |
| Lumos | ACC-112-COMPLIANCE, ACC-105-EXECUTION, ACC-106-DATA, ACC-113-MIGRATION, ACC-111-ENTERPRISE | ACC-102 MISS, ACC-107-LEGAL MISS, ACC-103 MISS, ACC-101 MISS | True |

**Pre-fix ACC-105-EXECUTION top-5 count: 9/12. Pre-fix aggregate should-surface hit rate: 10/34.** (This
CR's own baseline — the CR-064-era 10/14 and CR-065 Part C 9/13 numbers are cited in the spec for context
only, not reused here per Decision item 5.)

### Post-fix (frequency-sorted keywords, same `--full` command, same sample)

| Company | top5 | should-surface hits | ACC-105-EXECUTION top5? |
|---|---|---|---|
| Cresta | ACC-112-COMPLIANCE, ACC-105-EXECUTION, ACC-105-PROCESS, ACC-106-DATA, ACC-101-RETENTION | ACC-107 MISS, ACC-103 MISS, ACC-101 HIT | True |
| Group 1001 | ACC-113-MIGRATION, ACC-109-PROCESS, ACC-202-REQUIREMENTS, ACC-105-EXECUTION, ACC-106-DATA | ACC-101 MISS, ACC-103 MISS, ACC-105 HIT, ACC-107 MISS, ACC-113 HIT | True |
| OneStream | ACC-103-SEC, ACC-112-COMPLIANCE, ACC-103-ROADMAP, ACC-105-EXECUTION, ACC-102-LEAD | ACC-107 MISS | True |
| Buyers Edge Platform | ACC-109-PROCESS, ACC-112-COMPLIANCE, ACC-102-INT, ACC-113-MIGRATION, ACC-108-OPS | ACC-109 HIT, ACC-204 MISS | False |
| Ontra | ACC-202-REQUIREMENTS, ACC-102-INT, ACC-112-PIPELINE, ACC-113-MIGRATION, ACC-107-PLATFORM | ACC-401-AITOOLS MISS, ACC-103 MISS | False |
| Remote | ACC-112-COMPLIANCE, ACC-107-PLATFORM, ACC-112-PIPELINE, ACC-113-MIGRATION, ACC-102-INT | ACC-401-AITOOLS MISS, ACC-106 MISS | False |
| Covideo | ACC-111-SCOPE, ACC-105-EXECUTION, ACC-111-ENTERPRISE, ACC-113-ADOPTION, ACC-105-PROCESS | ACC-401-AITOOLS MISS, ACC-105 HIT | True |
| DataGrail | ACC-111-ENTERPRISE, ACC-103-SEC, ACC-103-ROADMAP, ACC-106-EVIDENCE, ACC-107-COMPLIANCE | ACC-107 HIT, ACC-401-AITOOLS MISS, ACC-103 HIT | **False (was True)** |
| MyTime | ACC-202-REQUIREMENTS, ACC-105-EXECUTION, ACC-201-ALIGNMENT, ACC-105-PROCESS, ACC-109-EXEC | ACC-401-AITOOLS MISS, ACC-104 MISS, ACC-105 HIT | True |
| PointClickCare | ACC-109-PROCESS, ACC-112-COMPLIANCE, ACC-112-PIPELINE, ACC-109-EXEC, ACC-102-MODERN | ACC-101 MISS, **ACC-102 HIT (was MISS)**, ACC-109 HIT, ACC-401-AITOOLS MISS | **False (was True)** |
| Redox | ACC-109-PROCESS, ACC-112-COMPLIANCE, ACC-111-ENTERPRISE, ACC-113-MIGRATION, ACC-401-AITOOLS | ACC-101 MISS, ACC-103 MISS, ACC-109 HIT | **False (was True)** |
| Lumos | ACC-112-COMPLIANCE, ACC-106-DATA, ACC-113-MIGRATION, ACC-111-ENTERPRISE, ACC-105-PROCESS | ACC-102 MISS, ACC-107-LEGAL MISS, ACC-103 MISS, ACC-101 MISS | **False (was True)** |

**Post-fix ACC-105-EXECUTION top-5 count: 5/12 (down from 9/12, satisfies Acceptance Criterion 3).
Post-fix aggregate should-surface hit rate: 11/34 (up from 10/34).**

**Per-company regression check (Acceptance Criterion 4):** 4 companies lost `ACC-105-EXECUTION` from
top-5 (DataGrail, PointClickCare, Redox, Lumos). For every one of those 4, `ACC-105` (bare or suffixed) is
**not** in that company's own `should_surface` list (`measure_theme_extraction.EVAL_SET`) — DataGrail's
list is `[ACC-107, ACC-401-AITOOLS, ACC-103]`, PointClickCare's is `[ACC-101, ACC-102, ACC-109,
ACC-401-AITOOLS]`, Redox's is `[ACC-101, ACC-103, ACC-109]`, Lumos's is `[ACC-102, ACC-107-LEGAL, ACC-103,
ACC-101]` — none include ACC-105. So every drop is the "over-representation dropping out where it wasn't
should-surface for that company" case the spec explicitly calls expected and acceptable, not a regression.
Checking the full should-surface hits table for **any** code that flipped HIT->MISS anywhere (not just the
target claim): none did. The only hit-table change anywhere is PointClickCare's `ACC-102` flipping
MISS->HIT, an improvement. **Zero regressions found — clean result, matches Acceptance Criterion 4.**

### Cover-letter-side hand-check (Acceptance Criterion 5)

Reconstructed the pre-fix profile via `measure_jd_profile_extraction.keywords_alphabetical_current()`
(byte-identical to the old production code) with the same post-fix `priority_themes`/`requirements`, fed
both through `extract_ranked_needs()` -> `pick_cover_proofs()` (k=3), for 3 eval-set companies:

| Company | Pre-fix proof order | Post-fix proof order |
|---|---|---|
| Cresta | ACC-401-AITOOLS, ACC-101-RETENTION, ACC-105-PROCESS | ACC-401-AITOOLS, ACC-101-RETENTION, ACC-105-PROCESS (unchanged) |
| DataGrail | ACC-401-AITOOLS, ACC-103-SEC, ACC-115-RETENTION | ACC-401-AITOOLS, ACC-103-SEC, **ACC-109-SYNTHESIS** (3rd slot changed) |
| Redox | ACC-401-AITOOLS, ACC-101-RETENTION, ACC-102-MODERN | ACC-401-AITOOLS, ACC-101-RETENTION, ACC-102-MODERN (unchanged) |

2 of 3 companies had identical cover-letter proof selection and order; DataGrail's 3rd proof point changed
from `ACC-115-RETENTION` to `ACC-109-SYNTHESIS` (1st/2nd proofs unchanged). No evidence of a broken or
degraded selection — this is the `keywords` field doing its job of shifting which claim scores highest as
DataGrail's actual defining vocabulary (`product`, `customers`, `engineering`, `management`,
`intelligence`, etc.) replaces the old alphabetical noise (`accelerate`, `balance`, `before`, `being`,
`brief`, etc.).

### Pytest regression check (Acceptance Criterion 6)

`python -m pytest -q --ignore=test_domain_gate.py --ignore=test_fit_policy.py --ignore=test_llm.py` from
`scripts/`:
- **Pre-fix (verified via `git stash` on `jd_tailoring.py` only, `test_jd_profile_keywords.py` ignored):
  28 failed / 190 passed / 1 skipped** — same 28 named failures as the tech-lead setup baseline, byte-for-byte.
- **Post-fix (fix restored via `git stash pop`, full suite including the 5 new tests): 28 failed / 195
  passed / 1 skipped** — same 28 failure names (confirmed identical test IDs pre- and post-fix), passed
  count up by exactly 5 (the new `test_jd_profile_keywords.py` tests, all passing).
- No pre-existing failure was fixed or newly broken by this change.

### `git diff --stat` scope confirmation (Acceptance Criterion 8)

```
scripts/jd_tailoring.py | 6 ++++--
1 file changed, 4 insertions(+), 2 deletions(-)
```
(Tracked-file diff only — `scripts/measure_jd_profile_extraction.py`'s `--full` addition and
`scripts/test_jd_profile_keywords.py` are new/untracked files, which `git diff --stat` on tracked paths
doesn't show; both were added by this session and confirmed via `git status`.) The `jd_tailoring.py` diff
is exactly the `Counter` import and the 2-line-to-3-line `keywords` selection swap — nothing else in that
file changed. `priority_themes` construction, `extract_req_section()`, `THEME_KEYWORDS`,
`score_claim_for_jd`, and `data/master_claims.json` are all untouched.

## Session Handoff — read this FIRST, fill it in before you stop

Whoever is reading this at the start of a session: check "Last updated" below.

- **Last updated:** 2026-07-14 — Engineering Manager close-out. CR-066 **APPROVED / complete.** Security
  Review CLEAR, QA PASS, and all headline numbers independently re-verified by the EM (pytest
  28F/195P/1S, `ACC-105-EXECUTION` 5/12, aggregate 11/34, diff scope, pre-fix `test_cutoff_is_twelve`
  behavior). See `../../pipeline-log.md`, "Engineering Manager — CR-066 Close-out".
- **Current stage:** **COMPLETE.** The fix is shipped in `scripts/jd_tailoring.py`
  (`build_jd_profile_deterministic`'s `keywords` field): `Counter`-based descending-frequency sort with
  alphabetical tie-break, same length filter / stopword set / `_jd_body_for_themes()` source / `[:12]`
  cutoff, signature unchanged. Measured clean: `ACC-105-EXECUTION` top-5 count 9/12 -> 5/12 as expected,
  aggregate should-surface hit rate 10/34 -> 11/34, zero regressions (every `ACC-105-EXECUTION` drop was
  for a company where it was never should-surface; the only should-surface flip anywhere was
  PointClickCare `ACC-102` MISS->HIT, an improvement), pytest 28F/190P/1S -> 28F/195P/1S (same 28 failure
  IDs, +5 new passing tests), cover-letter hand-check clean on 3 companies. All 9 Acceptance Criteria met.
- **Two residuals logged; the first has since been fixed post-close (same day), the second is informational
  only:**
  1. **RESOLVED — `test_jd_profile_keywords.py::test_cutoff_is_twelve` fixture rewritten to actually
     discriminate.** Original finding (QA Important, EM-reproduced): the test's fixture assigned frequency
     in the same order as alphabetical order, so alphabetical selection and frequency selection happened to
     keep/drop the identical 12/3 split — the test passed under both the old alphabetical code AND the new
     frequency code (1 failed / 4 passed pre-fix, not the "2 failed / 3 passed" the Round-1 log originally
     claimed), proving nothing about the actual fix. Fixed same day: frequency is now assigned in *reverse*
     alphabetical order (`victor` highest, `alpha` lowest), so the two mechanisms disagree on which 3 words
     survive the `[:12]` cutoff. Verified directly: re-run against pre-fix code (`git stash` on
     `jd_tailoring.py` only) now genuinely **fails** (`AssertionError: 'tango' not found in [...]`), and
     passes clean against the live post-fix code (5/5 in the file). AC7 was never actually at risk — the
     sibling `test_frequent_defining_noun_outranks_alphabetically_earlier_rare_word` correctly pinned the
     behavior throughout — this was a test-quality fix, not a behavior fix, and required no change to
     `scripts/jd_tailoring.py`.
  2. **Incomplete call-site inventory — `scripts/summary_builder.py:149-160` (`_select_focus_areas`) is a
     5th, order-sensitive consumer of `.keywords`** not in this CR's or Security Review's inventory. QA
     confirmed its output (`SummaryContext.focus_areas`) is never read downstream — dead field, zero
     current impact — so the fix is safe today. Noted so a future change that starts reading
     `focus_areas` re-checks ordering assumptions. No action required now.
- **Exact next action:** This CR is closed. Next in the "work down the pipeline" direction Jason set at
  CR-065 scoping: **CR-067** (the `requirements`/`extract_req_section()` boilerplate-capture defect —
  reserved but NOT yet scoped or diagnosed to the same rigor; CR-065 Part D found the obvious
  section-scoping fix resolved only 1 of 4 broken companies, so the real root cause is still unidentified)
  and the still-open **under-scoring `ACC-401-AITOOLS`/`ACC-204` problem** (explicitly out of CR-066's
  scope; no measured evidence any extraction fix addresses it — needs its own diagnostic phase before any
  fix is designed). Both are out of this CR's scope by design.
- **What's already verified (do not redo unless code moved):** all 9 call sites confirmed accurate;
  `keywords_frequency_sorted()` at `measure_jd_profile_extraction.py:96-108` confirmed byte-for-byte equal
  to the spec's Decision item 1; the production edit in `jd_tailoring.py` moves that logic inline (+
  `from collections import Counter`); pytest 28F/190P/1S pre-fix -> 28F/195P/1S post-fix, same 28 failure
  names both times (git-stash-verified).
- **Open Questions resolved at setup (do not re-decide):** (OQ1) new unit test in
  `scripts/test_jd_profile_keywords.py`, asserting against `build_jd_profile_deterministic()`'s output
  directly — no extracted helper. Implemented as specified. (OQ2) extended
  `measure_jd_profile_extraction.py` in place via an additive `--full` mode — no new measurement script.
  Implemented as specified.
- **Known data caveat:** working sample is 12/16 (`sailpoint`, `tilt`, `par`, `parkingpass_com` absent),
  re-confirmed unchanged from tech-lead's setup run. Both the pre-fix and post-fix measurements ran against
  this same named 12-company set (Acceptance Criterion 9 satisfied).
- **Hard scope boundary held:** this round touched ONLY the `keywords` sort in `jd_tailoring.py` (plus the
  additive `--full` measurement mode and the new test file). Confirmed via `git diff` that
  `priority_themes`, `extract_req_section()`, `THEME_KEYWORDS`, `score_claim_for_jd`, and
  `data/master_claims.json` are all untouched. The `requirements` / `extract_req_section()`
  boilerplate-capture defect remains reserved for CR-067, not started here.
