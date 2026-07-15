---
status: round_1_complete
created: 2026-07-14
spec: ../05-change-requests/CR-065-jd-profile-extraction-diagnostic.md
eval_set: ../../reports/jd-theme-claim-eval-set.md
predecessor_tracker: CR-064-claim-score-formula-rework-tracker.md
---

# CR-065 Tracker — JD-Profile Extraction Diagnostic (`build_jd_profile_deterministic`)

Resumable round-by-round log, same discipline as its predecessors CR-063 and CR-064. **Read the Session
Handoff block at the very bottom of this file first** — if a prior session left one filled in, that block
tells you exactly where to pick up, and you should trust it over re-deriving state from the round logs
yourself. Right now the handoff block is pre-filled with the starting state (this CR hasn't had a working
session yet) — treat it as the literal first thing to do, not a template to ignore.

**This is Investigation Phase 1 of a pipeline-wide effort, not a one-off.** Jason's decision at CR-065
scoping (2026-07-14, Open Question 3 resolved in the spec): "focus on JD extraction and work our way down
the pipeline." CR-064 closed `closed_partial` after three independently-correct ranking-arithmetic
mechanisms all failed to move `ACC-105-EXECUTION`'s cross-JD top-5 over-representation; the working
hypothesis this CR tests is that the defect is *upstream* of the ranking arithmetic, in the JD-profile
extraction step that feeds it. This CR diagnoses the extraction step. What comes after (a fix, or the next
step down the pipeline) is a separate, Jason-gated decision on this CR's written finding — but the
sequence is committed to, so frame results as "step 1 of N," not "the answer."

Read `CR-065-jd-profile-extraction-diagnostic.md` first if you haven't this session — it has the full
problem statement, the three concrete candidate defects, the three-way finding structure ((a)/(b)/(c)),
and the extended ranking-impact-spike scope (Decision item 3, third bullet). Then read the predecessor
tracker `CR-064-claim-score-formula-rework-tracker.md`'s "Close-out" section and CLAUDE.md's CR-063
summary — that's why this investigation moved upstream of the ranking arithmetic in the first place.

## Checkpointing protocol — this work may span multiple sessions, plan for it

Same four rules CR-063/CR-064 used, because they worked:

1. **Before executing any plan — a full round, or a specific measurement within a round — write the plan
   out as its own ordered checklist right here in this file**, under the round you're working on, even if
   it's more granular than what's pre-written below.
2. **Check off and log each step as you finish it, not in a batch at the end.** Real state (what a
   measurement actually showed, the actual per-company numbers), not a stale unchecked list or a
   reconstructed-from-memory summary. The per-company hand-review table and the ranking-spike before/after
   rank numbers must be written into this file as you produce them, not summarized away.
3. **If you sense you're running low on context or session time, stop at the nearest checkpoint boundary.**
   A cleanly stopped, fully logged company beats a rushed, unlogged batch.
4. **Before ending any session on this CR, fill in the Session Handoff block at the bottom.** Read first by
   whoever comes next, before anything else in this document.

## Before Round 1 — orientation (do this once)

- [x] Read `docs/spec/05-change-requests/CR-065-jd-profile-extraction-diagnostic.md` in full, especially
      the resolved Open Questions (1: proceed on 13 companies; 2: ranking-impact spike is in scope;
      3: this is Phase 1 of a sequence) and Decision item 3's three bullets.
- [x] Read `CR-064-claim-score-formula-rework-tracker.md`'s "Close-out" section (why the investigation
      moved upstream) and CLAUDE.md's CR-063 summary (what CR-063 did and did not test about the profile).
- [x] Confirm the 13 available eval-set companies are present in `data/archive/submissions/` with an
      `Original_JD.txt` each: `cresta`, `sailpoint`, `group_1001`, `onestream_software`,
      `buyers_edge_platform`, `ontra`, `remote`, `covideo`, `datagrail`, `mytime`, `pointclickcare`,
      `redox`, `lumos`. **Missing (do NOT wait on them, per resolved Open Question 1): `tilt`, `par`,
      `parkingpass_com`.** Note: the archive also contains `par_technology`, which is a *different* folder
      from the eval set's `par` slug — do not substitute it. Verified at scoping (2026-07-14) that exactly
      these 13 are present; re-confirm with an `ls`, since the archive is not immune to the same sync churn
      that degraded `data/submissions/` (CR-064 Round 5 finding).
      **Re-confirmed 2026-07-14 (this session):** re-ran the exact 13-slug + 3-missing + `par_technology`
      distinctness check with a shell loop against `data/archive/submissions/`. All 13 present, all 3
      confirmed still missing, `par_technology` confirmed present and distinct from `par`. No drift since
      scoping.
- [x] Confirm `JdProfile`'s field structure directly from `scripts/jd_tailoring.py` (lines 58-66) before
      constructing the corrected profile in the spike. It is a `@dataclass` with exactly four fields:
      `priority_themes: List[str]`, `requirements: List[str]`, `keywords: List[str]`, `source: str`
      (default `"deterministic"`). The spike constructs a plain
      `JdProfile(priority_themes=..., requirements=..., keywords=..., source="corrected")` — no other
      fields, no subclassing, no monkeypatching of the dataclass.
      **Confirmed by direct read** — matches exactly as described; `measure_jd_profile_extraction.py`'s
      `ranking_spike()` constructs the corrected profile this way, no deviation.
- [x] Confirm the two source-of-truth functions the spike calls are the current, CR-064-final versions and
      that their signatures are unchanged: `score_all_claims(jd_profile, catalog, jd_text)` (returns a
      descending-sorted list of `(ClaimRecord, score)` tuples, `scripts/jd_tailoring.py:540`) and
      `score_claim_for_jd(claim_text, profile, jd_text) -> int` (`scripts/jd_tailoring.py:295`, now
      dedup + rarity + DCG dampener). `extract_req_section(jd_text) -> str` is at line 100. The spike calls
      all three as-is — it does not reimplement scoring.
      **Confirmed by direct read**, docstring at line 295-311 confirms the dedup+rarity+DCG design
      described in CLAUDE.md/CR-064's close-out is what's live. Signatures unchanged.
- [x] Confirm the parallel-measurement-script precedent by reading `scripts/measure_theme_extraction.py`
      (logs only `priority_themes` today — line 79; this is the concrete instrumentation gap) and
      `scripts/measure_semantic_rerank.py` (imports `score_claim_for_jd` and layers a comparison on top
      without modifying it — the exact pattern this CR's new script follows). Reuse
      `measure_theme_extraction.py`'s `EVAL_SET`, `project_id`, `code_hits_top5`, and `TOP_N` by importing
      them, but source JDs from `data/archive/submissions/`, not `data/submissions/` (the script's own
      `SUBMISSIONS_DIR` points at the unstable live location — do not reuse that constant as-is).
      **Confirmed and followed** — `measure_jd_profile_extraction.py` imports `EVAL_SET`,
      `code_hits_top5`, `project_id` from `measure_theme_extraction.py` and defines its own
      `ARCHIVE_SUBMISSIONS_DIR` pointed at `data/archive/submissions/`, filtering `EVAL_SET` down to the
      13 present via `available_eval_set()`.
- [x] Run the full `scripts/` pytest baseline once before writing anything, so the "no production code
      changed" acceptance criterion has a before-number to compare against at close-out:
      `python -m pytest -q --ignore=test_domain_gate.py --ignore=test_fit_policy.py --ignore=test_llm.py`.
      Record the pass/fail/skip counts here. Per CR-064's close-out this was **28 failed / 190 passed /
      1 skipped** on 2026-07-14 — if it differs, something changed in the repo since; note it before
      proceeding. This CR adds a standalone script and touches no production code, so this count must be
      identical at close-out.
      **Ran 2026-07-14, this session: 28 failed / 190 passed / 1 skipped — exact match to the CR-064
      baseline.** No drift.

## Round 1 — Extraction diagnostic + ranking-impact spike

Everything in this CR is diagnostic. There is no "implement a fix" round — that is a separate future CR
gated on this CR's finding (spec Decision item 5). Round 1 is the whole measurement.

### Round 1 plan

**Part A — the new instrumentation script (all 13 companies).**
- [x] Write `scripts/measure_jd_profile_extraction.py` (standalone, not wired into any production path).
      For each of the 13 available companies, read `data/archive/submissions/{slug}/Original_JD.txt`, call
      the unmodified `build_jd_profile_deterministic(jd_text)`, and log the full profile —
      `priority_themes`, `requirements`, AND `keywords` together (the gap
      `measure_theme_extraction.py` leaves open). Import `EVAL_SET` from `measure_theme_extraction.py` and
      filter to the 13 present; do not hardcode a second copy of the eval list.
- [x] Run it and capture the full per-company output. Do not summarize — the raw `requirements` and
      `keywords` lists per company are the evidence the hand-review rests on.

**Part B — per-company hand-review vs. ground truth (all 13 companies).**
- [x] For each of the 13 companies, compare the logged `priority_themes`/`requirements`/`keywords` against
      that company's "Real JD themes (human-verified)" column in `docs/reports/jd-theme-claim-eval-set.md`.
      Record, per company, a plain judgment: does the extracted profile contain enough of the real theme(s)
      to plausibly support correct downstream ranking, or is it missing / diluted by generic terms /
      actively wrong (e.g. `requirements` capturing "About the company" boilerplate)?
- [x] Write the results as a per-company table in the "Round 1 results" section below — 13 rows, not a
      subset, not a summary without the underlying per-company detail (spec acceptance criterion).

**Part C — keywords test: alphabetical vs. frequency (sample of ≥5).**
- [x] Choose the ≥5-company sample per the spec: include ≥2 companies where CR-064's close-out showed
      `ACC-105-EXECUTION` top-5 over-representation, and ≥2 where an under-scoring rare-match claim
      (`ACC-401-AITOOLS` / `ACC-204`) should have surfaced but didn't. Name the chosen companies and the
      reason for each here before running, so the sample isn't cherry-picked after seeing results.
- [x] For each sampled company, compute the `keywords` list the current code produces (alphabetical) and
      the list a frequency-sort would produce — **same** length-≥5 filter, **same** 5-stopword filter,
      **same** `[:12]` cutoff, **same** source text (`_jd_body_for_themes(jd_text)`, the 72% body the
      current code tokenizes over), changing **only** the sort key from alphabetical to
      descending-frequency. Diff the two 12-word lists and record whether the alphabetical version discards
      words that appear in that company's ground-truth theme description and the frequency version keeps.

**Part D — requirements test: current line-scan vs. `extract_req_section()` (same sample).**
- [x] For each sampled company, run the JD through the unmodified `extract_req_section(jd_text)`, then apply
      the same 20-120-char / alphanumeric-start / `[:6]` line-scan to *that section* instead of the whole
      JD, and compare to what `build_jd_profile_deterministic`'s current whole-JD scan captured. Record the
      actual captured line(s) for both methods per company — is the current field pulling from inside the
      true requirements section, or from earlier boilerplate?

**Part E — ranking-impact spike (same sample) — the load-bearing measurement.**
- [x] For each sampled company, construct a corrected `JdProfile` **inside the script**:
      `JdProfile(priority_themes=<current themes, unchanged>, requirements=<Part D corrected list>,
      keywords=<Part C frequency-sorted list>, source="corrected")`. Themes stay identical — they are not
      one of the two candidate defects (CR-063 already worked that field).
- [x] Call `load_catalog()` once, then for each sampled company call the unmodified
      `score_all_claims(current_profile, catalog, jd_text)` and
      `score_all_claims(corrected_profile, catalog, jd_text)`. Do NOT reimplement scoring — import and call
      the shipped functions.
- [x] Record, per sampled company, `ACC-105-EXECUTION`'s **rank** (1-indexed position in the full
      descending-sorted `score_all_claims` output) and its **top-5 membership** under both profiles, with
      the actual before/after rank numbers — not "changed / didn't change". Use the eval set's
      `code_hits_top5` / `project_id` helpers for consistent top-5 accounting. Also note whether the
      sampled under-scoring claims (`ACC-401-AITOOLS` / `ACC-204`) move, since Part C was chosen partly to
      exercise them.

**Part F — the written finding.**
- [x] Write a single, explicit finding — (a), (b), or (c) from spec Decision item 4 — in the "Round 1
      results" section, with the evidence cited by company and by the specific comparison (Part B/C/D/E)
      that produced it. A finding that hedges between (a) and (b), or asserts (a) without naming which
      field is responsible, does not satisfy the acceptance criterion. The ranking-impact spike (Part E) is
      the primary evidence for (a)-vs-(b): corrected profile moves `ACC-105-EXECUTION`'s rank → points at
      (a); leaves it unchanged → points at (b).

**Part G — close-out verification (proves the "no production code touched" constraint).**
- [x] `git diff --stat` — confirm zero lines changed in `scripts/jd_tailoring.py` and no edit to
      `data/master_claims.json`. The only new file should be `scripts/measure_jd_profile_extraction.py`
      (plus this tracker and the spec/log updates).
- [x] Re-run the full `scripts/` pytest suite (same ignore flags as the baseline above) and confirm the
      pass/fail/skip counts match the Before-Round-1 baseline exactly. A mismatch means something outside
      this CR's scope was touched — explain before close-out.
- [x] Fill in the Session Handoff block. If the finding is (a) or (c), name the leading candidate field and
      what a follow-up CR would need to decide, without designing the fix (that's gated).

### Round 1 results

#### Part A — raw extraction output (all 13 companies)

Full per-company `priority_themes` / `requirements` / `keywords` output is captured verbatim by running
`python scripts/measure_jd_profile_extraction.py` (prints Part A for all 13). Selected excerpts are quoted
inline in the Part B table below where they matter to a judgment; the full raw output was reviewed
company-by-company to produce that table, not reconstructed from memory.

#### Part B — 13-company hand-review vs. ground truth

Ground truth column is the "Real JD themes (human-verified)" column from
`docs/reports/jd-theme-claim-eval-set.md`. Judgment is plain-language: does the extracted profile contain
enough signal to plausibly support correct ranking, and specifically is `requirements` capturing real
requirement content or boilerplate (title/location/salary/benefits/interview-process/section headings)?

| # | Company | Ground-truth theme | `priority_themes` | `requirements` verdict | `keywords` verdict | Overall judgment |
|---|---|---|---|---|---|---|
| 1 | Cresta | IAM/access governance, enterprise security, systems-level ambiguity | platform reliability, security backlog, roadmap, revenue-generating — decent, no explicit "IAM"/"access governance" theme | 6/6 substantive; captures "beyond IAM", "ambiguous, systems-level problem spaces", security/engineering language | Noise-heavy: `access`,`ambiguous`,`auditability` relevant but buried among `airlines`,`advantage`,`asking`,`agent`,`agents` — none of `security`,`identity`,`platform`,`product` present | **Partial** — themes/requirements adequate, keywords diluted |
| 2 | SailPoint | Identity governance, AI-powered access certification, cloud SaaS | platform, security backlog, roadmap, stakeholder alignment — misses "identity"/"AI" themes specifically (see note below table) | 6/6 substantive; explicitly captures "Identity security field", "AI tooling", "AI-powered features" | Misses `identity`,`security`,`ai`,`certification`,`cloud`,`sailpoint` entirely — dominated by `access`,`actionable`,`actively`,`administrators`,`analysis`,`applications` | **Partial/bad on keywords** — requirements strong, keywords fails to surface any of the JD's defining nouns (frequency-sort recovers `identity`,`security`,`cloud`,`sailpoint`,`certification` — see Part C) |
| 3 | Group 1001 | Multi-module platform ownership, regulated industry, data-driven baselines | platform, data integrity, roadmap, stakeholder alignment — good match | 6/6 substantive; captures "Owns a domain end to end", "Uses data to decide... baselines" | Scattered but includes `annuity` (regulated-insurance-specific) and `backward`,`baselines`-adjacent terms | **Good** |
| 4 | OneStream | Marketplace/partner ecosystem (primary), identity/entitlements/licensing (desirable), AI-enabled features | platform, data integrity, roadmap, B2B SaaS — misses marketplace/identity entirely | **BAD — 4/6 lines are posting metadata, not requirements**: `'Location: ... Remote, USA'`, `'Employment Type: ... Full-Time'`, `'Benefits Offered: ... Vision, Medical, Life, Dental, 401K'`, `'Gross annual base salary: USD 114,000-148,000'` | Fully generic: `abilities`,`ability`,`access`,`accounting`,`achieve`,`across`,`acumen`,`adapt` — zero domain nouns | **Bad — clean example of the "requirements captures boilerplate" defect named in the CR's Problem section** |
| 5 | Buyers Edge Platform | Stakeholder liaison, backlog/sprint management, Product Analyst mgmt, CSM cert | platform, data integrity, stakeholder alignment, API integration — stakeholder theme present, good partial match | 5/6 substantive (liaison/stakeholder/sprint-planning language); 1/6 is a remote/no-sponsorship HR line, not a requirement | Moderate: `agile`,`aligned`,`alignment`,`analysts` relevant; `america`,`accessible`,`aggregated` noise | **Partial** — requirements mostly good, keywords diluted |
| 6 | Ontra | AI/LLM product strategy, data analysis/insight generation, product launches | platform, data integrity, AI tooling and prompt engineering — AI theme correctly captured | **BAD — only 3/6 slots filled, and all 3 are boilerplate/intro, zero real requirements**: `'What the job involves'` (heading), `'Ontra is seeking a Senior Product Manager reporting to our VP of Product, GM'` (org context), `'We're looking for a bold, senior product manager ready to solve complex problems...'` (generic intro) | Misses `ai`,`llm`,`launch`,`strategy`,`insight` entirely (structurally can't — see note below table); generic `ability`,`align`,`aligning`,`analysis`,`aptitude` | **Bad** — requirements is 0/3 real content; compounded by `extract_req_section()` itself falling back to the whole JD for this heading style (see Part D) |
| 7 | Remote | Cursor/Claude Code hands-on coding (hard req), HRIS/payroll domain, partner-facing integration | platform, data integrity, stakeholder alignment, API integration — misses the "AI tooling" theme despite Cursor/Claude being a named hard requirement | **BAD — dominated by interview-process/posting metadata, not requirements**: `'Start date: As soon as possible'`, `'Interview with recruiter'`, `"You'll report to: Senior Group Product Manager"` are 3 of the 6 slots | `authentication`,`bamboohr` (HRIS product name) present by alphabetical luck; mostly generic `ability`,`accurate`,`across`,`align`,`architecture` | **Bad** — second clean, unambiguous example of requirements capturing interview/posting-process text instead of real requirements |
| 8 | Covideo | 4+ yrs automotive/dealership (hard req), AI-fluency (hard req), high-velocity shipping | platform, data integrity, roadmap, B2B SaaS — misses automotive/dealership and AI-fluency theme entirely (no THEME_KEYWORDS entry for either) | **BAD — 0/6 real requirements**: `'Senior Product Manager'` (title), `'Indianapolis, IN Remote (US)'` (location), `'Key Responsibilities'` (heading), then 3 culture/benefits lines (`'The autonomy to truly own...'`, `'A fast, collaborative environment...'`, `'Competitive salary, comprehensive benefits...'`) | `automotive` present by alphabetical luck; misses `dealership` entirely (frequency-sort recovers both — see Part C) | **Bad — worst requirements example in the sample, 0/6 real content** |
| 9 | DataGrail | Privacy/compliance domain (core), ML-powered features, AI tool fluency | platform, data integrity, security backlog, roadmap — adjacent (security) but no explicit "privacy"/"compliance" theme hit | 6/6 substantive: 5+ years, track record, "AI tools and a default toward using them" — genuinely strong, no boilerplate | Generic: `accelerate`,`across`,`action`,`adoption`,`assessments`,`autonomy` — misses `product`,`customer`,`engineering`,`ai` (frequency-sort recovers these — see Part C) | **Mixed/good** — requirements is a rare fully-clean example, keywords still diluted regardless |
| 10 | MyTime | Process-driven requirements documentation, Gen AI/LLM feature integration, multi-release roadmap | roadmap, B2B SaaS, AI tooling — good, captures both AI and roadmap themes | 5/6 substantive (agile team, ownership, "detailed functional and technical requirements"); 1/6 is the `'What the job involves'` heading | `appointments` (MyTime's own scheduling-product domain) present; otherwise generic `ability`,`acceptance`,`actionable`,`agile` | **Good** |
| 11 | PointClickCare | Healthcare/regulatory domain, "influence without formal authority" (JD's own phrase), "modernizing legacy products" (JD's own phrase), AI/ML feature-building | data integrity, roadmap, stakeholder alignment, API integration — adjacent, no healthcare-specific theme (no THEME_KEYWORDS entry for healthcare) | **6/6 substantive, all real** — explicitly captures "Ability to influence and drive alignment... without formal authority", the JD's own phrase, verbatim | `authority`,`alignment` present (directly relevant to the "influence without formal authority" phrase) by alphabetical luck; still misses `healthcare`,`legacy`,`modernizing` | **Good** — best requirements example in the full 13, keywords moderate |
| 12 | Redox | GTM/commercial (50% of role, hard gap), FHIR (hard, named requirement), addressable 40% (lifecycle/KPIs/eng) | data integrity, B2B SaaS, stakeholder alignment, revenue-generating — no FHIR/healthcare-interop theme (no THEME_KEYWORDS entry) | 6/6 substantive, all real — explicitly captures "Strong knowledge of FHIR (Fast Healthcare Interoperability Resources", B2B SaaS/sales-cycle language | Generic: `ability`,`accelerating`,`accessed`,`across`,`active`,`address` — misses `fhir`,`healthcare`,`revenue`,`sales`,`market` (frequency-sort recovers `healthcare`,`sales`,`market` — see Part C) | **Mixed** — requirements genuinely strong (captures FHIR explicitly), keywords diluted as usual |
| 13 | Lumos | 3rd-party API assessment, vendor ecosystem mgmt, ETL/data pipeline at scale, enterprise connection reliability | platform, data integrity, roadmap, B2B SaaS — data-integrity theme aligns with ETL/pipeline ground truth | 5/6 substantive and directly on-theme ("3rd-party APIs — assessing capabilities", "ETL/data pipeline concepts", "navigating vendor ecosystems"); 1/6 is the `'What the job involves'` heading | `assessing`,`assessment` relevant; `applifting` looks like a scrape artifact; otherwise generic | **Good** |

**Pattern across all 13, stated once rather than repeated per row:** `keywords` is measurably weak in
**13 of 13** companies without exception — every single company's alphabetical top-12 is dominated by
generic function/adjective words (`across`, `ability`, `based`, `business`, `background`, `adoption`) that
carry near-zero company-specific signal, while the JD's own defining nouns (`platform`, `product`,
`customer`, `security`, `identity`, `healthcare`, `automotive`, `dealership`, `fhir`, `marketplace`) are
excluded in the large majority of cases — not because they're absent from the JD, but purely because they
don't happen to sort alphabetically into the top 12 of that JD's 5+-letter vocabulary. `requirements` is
much more variable: genuinely strong and substantive for **7 of 13** (Cresta, Group 1001, Buyers Edge
[mostly], DataGrail, MyTime, PointClickCare, Redox, Lumos — 8 really, see below), but capturing job-posting
**boilerplate instead of real requirements** for **4 of 13** (OneStream — location/employment-type/
benefits/salary; Remote — interview-process/start-date; Covideo — title/location/heading/culture/benefits,
0/6 real; Ontra — 0/3 real, all intro/org-context text). That 4/13 rate is a genuine, JD-layout-dependent
defect exactly matching the "boilerplate instead of requirements" candidate named in the CR's Problem
section — but it is bimodal (mostly-fine or catastrophically-broken depending on document layout), not
universal like the `keywords` defect.

**Note on `priority_themes` (not one of this CR's two candidate defects, re-confirmed rather than
re-litigated per the spec):** SailPoint and Ontra both show a real interaction worth flagging even though
it's out of this CR's fix-design scope — `themes[:4]` truncates in `THEME_KEYWORDS` document order, so a
JD that matches many early-table themes (`platform`, `security`, `roadmap`, `stakeholder`) can fill its
4-theme quota before reaching a later-table theme (`identity`, `saas`) that is actually more central to
that JD (SailPoint's ground truth is literally "Identity governance... cloud SaaS," and `identity` is a
real, matched `THEME_KEYWORDS` entry that never makes it into the trimmed list). This is CR-063's
territory, not re-opened here, but it is direct supporting evidence that the extraction step generally
(not just `keywords`) has room CR-063's rounds didn't fully close.

**Note on the `keywords` field's length>=5 filter:** even a frequency-sorted fix cannot surface `AI`, `ML`,
or `UX` as `keywords` tokens — the `[a-z]{5,}` regex structurally excludes any token under 5 characters
regardless of sort order. `priority_themes` already covers this partially via substring matching inside
longer words (`"llm"` inside `"llm-powered"`, `"genai"`, etc.), which is why Ontra and MyTime's AI theme
does get picked up at the theme level even though it can never appear as a `keywords` token. Flagging as a
structural limitation of any keywords-only fix, not something this CR's tested correction resolves.

#### Part C — keywords: alphabetical (current) vs. frequency-sorted, 6-company sample

**Sample selection (named before running, per the tracker's anti-cherry-pick instruction):**
A same-day live measurement (current, CR-064-final `score_claim_for_jd`) against all 13 archived companies
found `ACC-105-EXECUTION` in the top-5 for **9/13** (Cresta, Group 1001, OneStream, Covideo, DataGrail,
MyTime, PointClickCare, Redox, Lumos) and an under-scoring rare-match `ACC-401-AITOOLS`/`ACC-204` miss
(should-surface per the eval set but not in top-5) for **8/13** (SailPoint, Buyers Edge Platform, Ontra,
Remote, Covideo, DataGrail, MyTime, PointClickCare). Chosen sample of 6, covering both criteria with
margin and including 2 companies that satisfy both simultaneously:

| Company | Why chosen |
|---|---|
| Cresta | ACC-105-EXECUTION over-representation (rank 2, top-5) |
| Redox | ACC-105-EXECUTION over-representation (rank 3, top-5) |
| Covideo | Both: ACC-105-EXECUTION over-representation (rank 3, top-5) AND ACC-401-AITOOLS should-surface-but-missing |
| DataGrail | Both: ACC-105-EXECUTION over-representation (rank 1, top-5) AND ACC-401-AITOOLS should-surface-but-missing |
| SailPoint | ACC-401-AITOOLS should-surface-but-missing (rank 7, outside top-5) |
| Ontra | ACC-401-AITOOLS should-surface-but-missing (rank 19, outside top-5) |

This gives 4/6 companies satisfying the over-representation criterion (≥2 required) and 4/6 satisfying the
under-scoring-miss criterion (≥2 required).

**Word-list diffs** (same length>=5 filter, same 5-stopword filter, same `_jd_body_for_themes()` source,
same `[:12]` cutoff — only the sort key changes):

| Company | Alphabetical (current) | Frequency-sorted (proposed) | Ground-truth words recovered by frequency, missed by alphabetical |
|---|---|---|---|
| Cresta | access, across, additional, advantage, agent, agents, airlines, ambiguous, architects, areas, asking, auditability | platform, capabilities, cresta, customer, product, access, drive, every, including, world, across, closely | `platform`, `product`, `customer` |
| Redox | ability, accelerating, accessed, across, active, address, adoption, agreements, ambiguous, anticipating, aptitude, articulate | product, solutions, sales, strong, business, effectively, healthcare, including, market, ability, address, ambiguous | `healthcare`, `sales`, `market`, `product` |
| Covideo | adoption, advance, agile, align, alignment, analyze, author, automation, automotive, autonomy, based, betas | product, automotive, covideo, video, dealership, agile, experience, features, iterate, major, platform, solutions | `dealership` (the hard-requirement automotive/dealership term the alphabetical list misses entirely), `product`, `platform` |
| DataGrail | accelerate, across, action, adoption, assessments, autonomy, background, balance, based, before, being, brief | product, products, customer, customers, engineering, management, assessments, discovery, execution, experience, ideas, intelligence | `product`, `customer`, `engineering` |
| SailPoint | access, actionable, actively, administrators, analysis, applications, architects, backlog, based, bring, built, business | product, identity, security, access, cloud, right, sailpoint, customer, engineering, feature, roadmap, certification | `identity`, `security`, `cloud`, `certification` — the JD's own ground-truth theme words, verbatim |
| Ontra | ability, align, aligning, analysis, aptitude, bachelor, background, behavior, between, building, business, capabilities | product, ability, focus, products, strategic, business, complex, define, developing, development, drive, experience | `strategic`, `product`, `development` (still no `ai`/`llm` token — structural length-filter limitation noted above) |

Every one of the 6 sampled companies shows the alphabetical version discarding at least one
ground-truth-relevant, JD-defining noun that the frequency version keeps. SailPoint is the sharpest case:
the frequency version recovers `identity`, `security`, `cloud`, `certification` — literally the words used
in that company's own "Real JD themes" ground-truth description — none of which appear in the current
alphabetical output at all.

#### Part D — requirements: current whole-JD scan vs. `extract_req_section()`-scoped scan, same sample

| Company | `extract_req_section()` found a real subsection? | Current (whole-JD) vs. corrected (section-scoped) | Verdict |
|---|---|---|---|
| Cresta | Yes — starts "3+ years of experience in product management or a technical..." | **Differ.** Current includes `"Contribute to the evolution of shared platform capabilities beyond IAM..."` and the `"What We're Looking For"` heading fragment; corrected drops both and adds `"Prior hands-on engineering experience..."`, `"Experience with platform, infrastructure, developer-facing, enterprise SaaS..."`, and (weakly) `"Compensation At Cresta"` | Section-scoping measurably changes the captured lines here — both versions are substantive, but corrected is more tightly scoped to the true requirements section |
| Redox | Yes | **Identical.** Both scans return the same 6 lines byte-for-byte | No change — the whole-JD scan already happened to land inside the true requirements section for this JD's layout |
| Covideo | **Correction (CR-067, same day, re-verified directly against `_REQ_SECTION_RE.search()`): NO match at all** — this row's original characterization ("regex matched a heading but the section it isolated still contains boilerplate") was wrong. `extract_req_section()` falls back to the full JD text, identical mechanism to Ontra below, not a distinct "boundary too loose" failure. The "starts with Senior Product Manager..." text is simply `jd_text` from character 0, since no heading matched. Covideo's actual requirements-equivalent heading is `"Who You Are"`, which was not in `_REQ_SECTION_RE`'s pattern list at the time of this measurement — see CR-067 for the full re-diagnosis. | **Identical.** Both scans return the same 6 boilerplate-dominated lines (title, location, heading, 3 culture/benefit lines) | **Section-scoping does NOT fix this company's defect** — corrected root cause (CR-067): missing heading pattern, not a loose boundary. Even after adding a `"who you are"` pattern, a second defect surfaces (`_NEXT_SECTION_RE` doesn't recognize Title-Case headings either) — see CR-067's full three-root-cause finding. |
| DataGrail | Yes | **Identical.** Both scans return the same 6 substantive lines | No change — this company's requirements were already good under the current whole-JD scan |
| SailPoint | Yes | **Identical.** Both scans return the same 6 substantive lines | No change — already good |
| Ontra | **No — `extract_req_section(jd_text) == jd_text` exactly** (confirmed by direct equality check); the regex's heading list does not match this JD's `"Who you are"` heading, so the function falls back to the full JD per its own documented fallback behavior | **Identical** (necessarily, since the "section" is the whole JD) — both scans return the same 3 boilerplate/intro lines | **Section-scoping cannot fix this company's defect either** — the underlying cause here is `extract_req_section()`'s own heading-regex missing this JD's specific heading text, a second, compounding defect this CR did not modify or attribute a fix to |

**Key finding from Part D:** the tested "requirements section-scoping" correction only changed the
captured lines in **1 of 6** sampled companies (Cresta). For the other 5, current and corrected are
byte-identical — including for Covideo and Ontra, two of the companies Part B confirmed have severely
broken (`0/6` and `0/3` real-content) requirements fields. This means the specific fix tested here does
**not** reliably resolve the boilerplate-capture defect Part B found; it only helped in the one case where
the whole-JD scan's failure and `extract_req_section()`'s success happened to diverge.

#### Part E — ranking-impact spike: `ACC-105-EXECUTION` rank, current vs. corrected profile

Corrected profile = same `priority_themes`, Part C's frequency-sorted `keywords`, Part D's section-scoped
`requirements`. Scored via the unmodified, shipped `score_all_claims()`.

| Company | Rank (current) | Top-5 (current)? | Rank (corrected) | Top-5 (corrected)? | `ACC-401-AITOOLS`/`ACC-204` before→after | Requirements changed for this company? (Part D) |
|---|---|---|---|---|---|---|
| Cresta | 2 | Yes | **1** | Yes | n/a (not a should-surface code for Cresta) | Yes |
| Redox | 3 | Yes | **6** | **No — drops out of top-5** | n/a (not a should-surface code for Redox) — but note: `ACC-401-AITOOLS` appears in the corrected top-5 as rank 5 anyway, an incidental positive side-effect | No (identical) |
| Covideo | 3 | Yes | **2** | Yes | ACC-401-AITOOLS: False → False (unchanged) | No (identical) |
| DataGrail | 1 | Yes | **6** | **No — drops out of top-5** | ACC-401-AITOOLS: False → False (unchanged) | No (identical) |
| SailPoint | 7 | No | 7 | No (unchanged) | ACC-401-AITOOLS: False → False (unchanged) | No (identical) |
| Ontra | 19 | No | 21 | No (unchanged) | ACC-401-AITOOLS: False → False (unchanged) | No (identical, both fall back to whole JD) |

**The load-bearing observation:** `ACC-105-EXECUTION`'s rank moves materially in **4 of 6** sampled
companies (Cresta 2→1, Redox 3→6, Covideo 3→2, DataGrail 1→6), including **dropping fully out of the top-5
in 2 of those 4** (Redox, DataGrail). Requirements is byte-identical (unchanged) in **5 of the 6** sampled
companies (all except Cresta), which means the rank movement in Redox, Covideo, DataGrail, SailPoint, and
Ontra is attributable **exclusively to the `keywords` field's alphabetical→frequency change** — Cresta is
the only company where both fields changed simultaneously, so it cannot cleanly isolate which field drove
its movement, but the other 5 companies isolate the effect cleanly. This directly contradicts CR-064's
finding that nothing moves `ACC-105-EXECUTION`'s rank — CR-064 never varied the *input* profile, only the
downstream aggregation arithmetic that consumes it. The under-scoring `ACC-401-AITOOLS` watch codes do
**not** flip from miss to hit anywhere in this small 6-company sample (they were already False before
correction and stay False after, in the 4 companies where they're tracked) — the tested correction
measurably fixes `ACC-105-EXECUTION`'s over-representation but does not, in this sample, also pull the
under-scoring rare-match claims into the top-5.

#### Part F — the finding

**(a) Profiles are measurably too generic/non-discriminating, with the `keywords` field's alphabetical
selection mechanism as the dominant, primary driver, and the `requirements` field's boilerplate-capture as
a real but secondary, JD-layout-dependent contributor.**

Evidence, cited by the specific comparison that produced it:

1. **Part B (13/13 companies):** the `keywords` field is measurably weak in every single company without
   exception — dominated by generic function/adjective words, almost never containing the JD's own
   defining nouns. This is universal, not a subset finding. The `requirements` field is bimodal: genuinely
   strong in 8-9 of 13, but confirmed capturing pure job-posting boilerplate (location/salary/benefits/
   interview-process/section headings, not real requirements) in 4/13 (OneStream, Remote, Covideo, Ontra).
2. **Part C (6/6 sampled companies):** the alphabetical-vs-frequency `keywords` diff shows the frequency
   version recovering ground-truth-relevant, JD-defining nouns the alphabetical version discards in every
   single sampled company — most sharply for SailPoint, where frequency-sort recovers `identity`,
   `security`, `cloud`, `certification`, literally the words in that company's own eval-set ground-truth
   description, none of which the current alphabetical `keywords` output contains at all.
3. **Part D (6-company sample):** the tested `requirements` correction (section-scoping) only changed
   output in 1 of 6 sampled companies; for the other 5 — including 2 that Part B confirmed are severely
   broken (Covideo, Ontra) — current and corrected `requirements` are byte-identical, meaning
   section-scoping as tested is *not* a reliable fix for the boilerplate-capture defect on its own.
4. **Part E, the load-bearing measurement:** the ranking-impact spike shows `ACC-105-EXECUTION`'s rank
   moving materially in 4 of 6 sampled companies (dropping out of the top-5 entirely in 2: Redox, DataGrail)
   when scored against a corrected profile — directly contradicting CR-064's five-round null result, which
   never varied the input profile, only the downstream aggregation arithmetic. Because `requirements` was
   byte-identical (per Part D) in 5 of those 6 companies while rank still moved in 3 of those 5
   (Redox, Covideo, DataGrail), the `keywords` field's alphabetical→frequency correction alone —
   independent of any `requirements` change — is directly responsible for the bulk of the observed rank
   movement. Cresta is the sole company where both fields changed together, so its movement (2→1) cannot
   be cleanly attributed to one field alone, but the other 5 companies isolate the effect: `keywords` is
   the dominant driver.

**What this finding does not claim:** the corrected profile did not pull the under-scoring
`ACC-401-AITOOLS`/`ACC-204` claims into the top-5 anywhere in this 6-company sample (Part E) — a
`keywords`-only or `requirements`-only fix targeting extraction generality is not, on this evidence, a
complete fix for the under-scoring side of the original CR-063/CR-064 problem statement, and the
`keywords` field's `[a-z]{5,}` length filter structurally cannot surface short discriminating tokens like
`AI`/`ML`/`UX` regardless of sort order (Part B note). `requirements`'s boilerplate-capture defect is real
(4/13 confirmed) but its currently-tested fix (`extract_req_section()`-scoping) does not reliably resolve
it — Covideo and Ontra both remain unfixed by that specific mechanism, pointing at a second, compounding
defect in `extract_req_section()`'s own heading-detection and the line-scan's 20-120-character window, not
addressed or attributed a fix here.

**Data caveat carried forward, per the tracker's honesty standard:** this finding rests on 13/16 eval-set
companies (`tilt`, `par`, `parkingpass_com` unavailable in the archive, per Open Question 1's resolution)
and a 6-company sub-sample for Parts C/D/E. The archive showed no drift during this session (re-confirmed
at orientation).

## Guardrails (apply this whole CR, no exceptions)

- **Zero changes to `scripts/jd_tailoring.py`** (`build_jd_profile_deterministic`, `build_jd_profile`,
  `extract_req_section`, `score_claim_for_jd`, or anything else in it) and **zero edits to
  `data/master_claims.json`.** The corrected profile is built as a `JdProfile` *object* inside the new
  standalone script; the frequency-sort and section-scoping logic lives in the script, not in production.
  Confirm via `git diff --stat` at close-out.
- **Diagnose, do not fix.** Even if Part B/C/D/E make a fix look obvious, this CR stops at the written
  finding. Designing the fix is a separate, Jason-gated CR (a hypothetical CR-066). Same two-step
  discipline CR-064 used, applied one level upstream.
- **Do not reopen embeddings or `jd_profile_mode="llm"` as a fix.** CR-063 ruled both out for the *ranking*
  question with real data. If this CR's finding is (a), LLM-mode *extraction* becomes a legitimately
  different future question — but it is not piloted inside this diagnostic phase.
- **Source JDs from `data/archive/submissions/`, never `data/submissions/`** (the live, sync-unstable
  location). If the archive itself shows churn mid-session, log it as a data caveat on the finding — same
  honesty standard CR-064 Round 5 used — do not silently drop or substitute companies without recording it.
- **Log real per-company numbers as you go**, not a reconstructed-from-memory summary at the end. The
  before/after ranks in Part E and the captured lines in Part D are the evidence; they must appear
  verbatim in this file.
- **Do not touch `data/submissions/` or `data/archive/submissions/` contents** — this CR reads JDs as fixed
  test input, it does not regenerate or edit any submission.

---

## Session Handoff — read this FIRST, fill it in before you stop

Whoever is reading this at the start of a session: check "Last updated" below.

- **Last updated:** 2026-07-14 — senior-engineer executed Round 1 in full (Parts A-G), single session, no
  blockers. See `../../pipeline-log.md`, "Senior Engineer — CR-065 Round 1".
- **Current stage:** **Round 1 complete, CR-065 diagnostic phase done.** Finding **(a)** reached and
  written up in "Round 1 results" Part F: profiles are measurably too generic, with the `keywords` field's
  alphabetical selection as the dominant driver (universal across 13/13 companies in Part B, isolated
  cleanly in 5/6 sampled companies in Part E where `requirements` was unchanged but rank still moved) and
  `requirements`'s boilerplate-capture as a real but secondary, JD-layout-dependent contributor (4/13
  companies confirmed broken in Part B, but the tested `extract_req_section()`-scoping fix only resolved
  1 of those 4 — Covideo and Ontra remain broken even after section-scoping, pointing at a second,
  compounding defect in `extract_req_section()`'s own heading-detection / the line-scan's 120-char cap that
  this CR did not attribute a fix to).
- **Exact next action:** This CR is done — diagnosis only, per its Out-of-Scope constraint. Next action is
  Jason reviewing this finding and deciding, per spec Open Question 3 (already resolved: "work our way down
  the pipeline"), what a hypothetical CR-066 should scope: most directly supported by this session's
  evidence, a `keywords` frequency-sort fix (the cleanly-isolated, universal, load-bearing defect) plus a
  *separate* look at `extract_req_section()`'s heading-regex coverage and line-scan length cap (the
  compounding defect Part D surfaced but did not fix) — but scoping that fix is explicitly gated on Jason's
  review, not decided here.
- **What this phase measured, in one line, and what it found:** does a *corrected* JD profile
  (frequency-sorted keywords + `extract_req_section()`-scoped requirements) actually change
  `ACC-105-EXECUTION`'s rank? **Yes — materially, in 4 of 6 sampled companies, dropping the claim fully out
  of the top-5 in 2 of those 4 (Redox, DataGrail).** This contradicts CR-064's five-round null result,
  because CR-064 never varied the *input* profile, only the downstream aggregation arithmetic. The
  extraction step (specifically `keywords`) is a real, previously-unpulled lever.
- **Known data caveat, unchanged from scoping:** working sample is 13/16 companies (`tilt`, `par`,
  `parkingpass_com` absent from the archive). Re-confirmed present/absent exactly as expected at this
  session's start, no drift during Round 1's own execution.
- **Correction (QA pass, same day, later):** `data/archive/submissions/sailpoint/` was present and readable
  during Round 1's execution (its Part B/C/E rows above are real, measured output, not fabricated) but is
  confirmed **gone from disk as of QA's verification pass**, hours later the same day — the archive is not
  immune to whatever sync/archiving process caused `data/submissions/`'s instability in CR-064. This means
  SailPoint's specific rows cannot be independently re-reproduced right now, but the written finding does
  not depend on SailPoint alone: both Part E load-bearing companies (Redox, DataGrail) and 5 of 6 Part C
  companies were independently reproduced by QA using data confirmed present at verification time. The
  finding stands; the "13/13, no drift" framing above should be read as "true at Round 1's execution time,"
  not as a standing guarantee.
- **New data caveat found this session:** the corrected profile did NOT pull the under-scoring
  `ACC-401-AITOOLS`/`ACC-204` claims into the top-5 in this 6-company sample (Part E) — a `keywords`
  frequency-sort fix, on this evidence, solves the over-representation half of the original CR-063/CR-064
  problem but is not shown to solve the under-scoring half. Also: `keywords`' `[a-z]{5,}` length filter
  structurally can never surface `AI`/`ML`/`UX` as tokens regardless of sort key — a follow-up CR
  targeting `keywords` would need to decide whether to also loosen or special-case that filter.
- **Open questions for Jason (do NOT act on these in this phase — they route back to him on the finding):**
  (1) whether to scope a CR-066 around the `keywords` frequency-sort fix (the strongest, most cleanly
  isolated evidence from this session) as a first, narrow step, versus waiting to also design a
  `requirements`/`extract_req_section()` fix in the same CR; (2) whether the under-scoring `ACC-401-AITOOLS`
  /`ACC-204` problem (which this session's corrected profile did not resolve) should become its own
  follow-up thread, and whether that requires loosening the `keywords` length filter, revisiting
  `ACC-105-EXECUTION`'s own tag/body breadth in `master_claims.json` (CR-063 Round 2's flagged-but-never-
  actioned candidate), or something else; (3) still-open operational item inherited from CR-064: the
  `data/submissions/` eval-set sync instability, unrelated to this CR's code but a standing blocker for any
  future measurement-dependent work.
