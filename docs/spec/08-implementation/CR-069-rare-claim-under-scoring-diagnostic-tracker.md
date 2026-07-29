---
status: round1_complete
created: 2026-07-15
spec: ../05-change-requests/CR-069-rare-claim-under-scoring-diagnostic.md
eval_set: ../../reports/jd-theme-claim-eval-set.md
related: [CR-063, CR-064, CR-065, CR-066, CR-068]
contains: CR-069
---

# CR-069 Tracker — `ACC-401-AITOOLS` / `ACC-204` Under-Scoring Diagnostic (Phase 1, measurement + root cause, NO fix)

Resumable round-by-round log. **Read the Session Handoff block at the very bottom of this file first** —
if a prior session left one filled in, it tells you exactly where to pick up, and you should trust it over
re-deriving state from the round logs. Only if the handoff block is still the empty template should you
start at "Before Round 1" below. Read the spec (`CR-069-rare-claim-under-scoring-diagnostic.md`) in full
this session if you haven't — it has the Problem statement, the three pre-scoping evidence items, the
6-item Decision, 8 Acceptance Criteria, 3 Open Questions already routed to Jason, and the hard Out-of-Scope
list (no production edits, no `master_claims.json` edits, no reopening CR-066/068/064-final mechanisms).

**This is a diagnostic-only phase. You write measurements and one named root cause per claim. You do NOT
ship a fix, and you do NOT edit `master_claims.json`, `jd_tailoring.py`, `cover_claim_picker.py`,
`draft_compiler.py`, `claim_composer.py`, or `local_draft_stages.py`.** Acceptance Criteria 7 and 8 gate on
those files being untouched by your work.

## Checkpointing protocol — this work will span sessions, plan for it

Same four rules the whole CR-063→068 arc has held:

1. **Before executing any plan — a whole round or a specific measurement — write it as an ordered checklist
   right here in this file**, even more granular than what is pre-written below. A plan that lives only in
   your reasoning is invisible to whoever resumes.
2. **Check off and log each step as you finish it, not in a batch at the end.** Interrupted between steps 2
   and 3? The next session must see 2 checked with real state written in place, 3-5 unchecked.
3. **If you sense you're low on context/time, stop at the nearest checkpoint boundary.** Do not cram in "one
   more trace" you won't have room to log properly.
4. **Before ending any session, fill in the Session Handoff block at the bottom.** It is read first by
   whoever comes next.

---

## Before Round 1 — orientation (do this once; several things have changed since CR-063)

The setup below was verified against live code/data on 2026-07-15 during CR-069 tech-lead scoping. It is
recorded here as **confirmed state so you do not re-derive it** — but re-confirm the archive presence and
the git baseline yourself at the start of your session, since the archive has churned continuously across
this arc and the working tree is already dirty.

### Code-location confirmations (verified 2026-07-15 — spot-check, don't re-audit)

- [x] Confirm `data/master_claims.json` `ACC-401-AITOOLS`: body contains "Claude" but **not** "Cursor"
      (line ~889); `employer: ""` (line ~878); tags `AI Tools / Prompt Engineering / Agentic Workflows /
      Automation / Python`. **Verified present as the spec states.**
- [x] Confirm `scripts/jd_tailoring.py`:
      - `THEME_KEYWORDS` (lines 18-56): re-counted directly this session via `len(THEME_KEYWORDS)` — **37
        entries, not 36** as this doc's prior note said (off-by-one; the file's actual last entry index is
        56, first is 19, inclusive count is 37). No functional impact, just correcting the count for the
        record. First 8 are `platform, data, ingest, migration, security, roadmap, saas, stakeholder`
        (generic). The 5 AI-tooling entries (`genai, agentic, llm, cursor, claude`) are the **last 5** (lines
        51-55). The privacy/compliance/identity/access/governance block (CR-063 Round 2) sits at 46-50, just
        before the AI block. **There is no `scrum`/`agile`/`sprint`/`backlog` entry anywhere** — confirmed
        directly by `scripts/trace_priority_themes.py`'s scan of the full table this session — confirming the
        spec's claim that the `priority_themes` truncation mechanism is moot for `ACC-204` (loop 3 and loop 4
        have nothing to match). **Verified.**
      - `build_jd_profile_deterministic` (starts line 126): appends every `THEME_KEYWORDS` match to `themes`
        in table order (loop at 130-132), then returns `priority_themes=themes[:4]` at **line 153** — the
        4-item cap the spec's evidence item 2 is about. The spec cited "126-157"; the truncation is at 153,
        inside that range. **Verified.**
      - `score_claim_for_jd` (starts line 299): 4 scoring loops with cross-loop dedup via `_bump` (keeps the
        max tier per token), then rarity weight (`_rarity_weight`), then DCG rank discount
        (`v / log2(rank+1)`). **Loop 1** = `profile.keywords` (tier 1, line 325). **Loop 2** =
        `profile.requirements` tokens (tier 2, line 328). **Loop 3** = `profile.priority_themes` tokens
        (tier 1, line 332) — this is the loop that reads only the truncated 4-item theme list. **Loop 4** =
        full `THEME_KEYWORDS` table against `jd_l`+`text_l` (tier 3, line 336) — this one bypasses the 4-item
        cap and is the only path that can still credit `claude` for `ACC-401-AITOOLS`. Matches the CR-064-final
        formula and the spec's evidence item 2 exactly. **Verified.**
      - `has_ai_signal` at **line 449** (`_AI_SIGNAL_RE` compiled at 438). NOTE: the spec's Traceability
        table row says "lines 210, 347" for `has_ai_signal`/`_protected_ai_slot` — the 210 is a spec typo;
        `has_ai_signal` is at 449 (the spec's own evidence item 3 cites 449 correctly). Minor, no impact.
- [x] Confirm `scripts/cover_claim_picker.py`:
      - `pick_cover_proofs` at **line 264** (spec evidence item 3 says "134" — line drift, the function
        exists and is the real production cover-letter proof path).
      - `_protected_ai_slot` at **line 347** — the `ACC-401-AITOOLS`-specific guard: fires when
        `has_ai_signal(jd_text)` is true and the claim in slot 0 is `ACC-401-AITOOLS`, exempting it from the
        metric-density replacement that would otherwise discard it (lines 354-355 use it as the gate).
        **Verified.** No equivalent guard exists for `ACC-204` — confirmed by grepping the file for `ACC-204`
        this session: zero hits.

### Data-state confirmations (RE-CONFIRM THESE — archive churns, do not trust stale)

- [x] **`data/submissions/` is now EMPTY.** All submission folders moved to
      `data/archive/submissions/{company}/`. CR-063's `scripts/measure_theme_extraction.py` and any script
      you reuse point at `data/submissions/` — **you must repoint every JD path to
      `data/archive/submissions/`** or the scripts will read nothing. Re-confirmed 2026-07-15 this session.
- [x] **Confirm the 8 should-surface JDs this CR measures are present with a non-empty `Original_JD.txt`**
      in `data/archive/submissions/`. Re-confirmed present this session (byte sizes match prior note exactly):
      - `ACC-401-AITOOLS` (6 present): `ontra` (2272), `remote` (4247), `covideo` (3760), `datagrail`
        (3971), `mytime` (2885), `pointclickcare` (2819). `sailpoint` confirmed MISSING (no folder).
      - `ACC-204` (2 present): `buyers_edge_platform` (6064), `par_technology` (5666).
- [x] **READ THIS — two count/slug facts the spec does not capture:**
      1. **`SailPoint` is GONE from the archive.** The eval set (`jd-theme-claim-eval-set.md`) names
         `ACC-401-AITOOLS` as should-surface on **7** companies — SailPoint, Ontra, Remote, Covideo,
         DataGrail, MyTime, PointClickCare — **not 6** as the spec's Problem table and Acceptance Criteria
         2/3 state (the spec's "0/6" inherited a CR-063 undercount; CR-063 Round 1 actually listed 7 AITOOLS
         rows, all MISS). SailPoint no longer has a folder in `data/archive/submissions/`, so it is not
         measurable right now. Net effect: **exactly 6 AITOOLS pairs are measurable**, which happens to match
         the spec's stated "6" — but for the wrong reason (spec undercount + SailPoint's independent absence,
         not a correct count of 6). Log SailPoint explicitly as "excluded — not in archive," do not silently
         treat 6 as the full eval-set truth. If SailPoint gets re-scraped later this becomes 7. This does not
         block the diagnostic; measure the 6 present. If Jason wants the 7th, that is a re-scrape ask, not a
         scope change here.
      2. **PAR's folder slug changed: `par` → `par_technology`.** CR-063 used `par`. Use `par_technology`.
      - Net measurable should-surface set: **6 AITOOLS + 2 ACC-204 = 8 pairs** — aligns numerically with the
        spec's "8 total," so Acceptance Criteria 2/4 (8 pairs) and 3 (6 AITOOLS) are reachable as written.
- [x] **Capture the git baseline BEFORE you touch anything** — Acceptance Criteria 7 and 8 depend on it.
      `scripts/jd_tailoring.py` and `data/master_claims.json` confirmed **clean** in the working tree.
      Baseline `git diff --stat` on the 4 pre-dirty files, captured at session start:
      ```
      scripts/claim_composer.py     | 14 ++++++++++++--
      scripts/cover_claim_picker.py | 39 ++++++++++++++++++++++++++++++++++++---
      scripts/draft_compiler.py     | 17 ++++++++++++-----
      scripts/local_draft_stages.py | 22 +++++++++++++++++++++-
      4 files changed, 81 insertions(+), 11 deletions(-)
      ```
      (Note: the rest of the working tree, unrelated to these 6 target files, is also extremely dirty —
      dozens of pre-existing modified/untracked files across `scripts/`, `server/`, `docs/`, root config
      files — from prior sessions' work, confirmed pre-existing and out of scope for this CR's AC7 gate,
      which only cares about the 6 named target files.)
- [x] **Run the pytest baseline once, working tree as-is:** `python -m pytest -q
      --ignore=test_domain_gate.py --ignore=test_fit_policy.py --ignore=test_llm.py`. **Baseline result this
      session: 200 passed, 28 failed, 1 skipped** (differs from CR-063's 188/27/1 — working tree has moved
      since then, as expected; this session's own baseline is the one AC 8 gates against).
- [x] Confirm no `DRAFT_MODE` / `JD_PROFILE_MODE` / `COVER_HOOK_MODE` env vars are set in your shell — this
      diagnostic measures the default deterministic path (`jd_profile_mode()="deterministic"`). Confirmed
      none set this session.

---

## Instrumentation scripts — build THREE standalone tools, keep them separate

Per the spec's "parallel measurement tool" discipline (CR-063/065 pattern): **no production edits.** All
instrumentation lives in new standalone scripts under `scripts/` that import the production functions and
observe them, never modifying them. **Decision (tech lead): keep these as three separate scripts, not one
combined driver.** Rationale — each maps 1:1 to a distinct Acceptance Criterion, produces a differently
shaped output artifact, and can be run and resumed independently, which is the resumability unit the
checkpointing protocol is built around. A single combined script would couple three unrelated instrumentation
surfaces and make a clean mid-session stop harder to log. This mirrors CR-063, which kept
`measure_theme_extraction.py` and `measure_semantic_rerank.py` as separate tools.

1. **`scripts/trace_priority_themes.py`** (Decision item 3 → AC 3). Re-runs
   `build_jd_profile_deterministic`'s theme-collection loop (or wraps it) to capture and print the **full,
   untruncated `themes` list** before the `themes[:4]` cap, for each of the 6 AITOOLS should-surface JDs.
   Directly confirms or refutes whether the AI-tooling theme phrase is present-but-displaced. Because the
   truncation is a single line (153), the cleanest approach is to reproduce the loop at lines 130-132 in the
   script against the imported `THEME_KEYWORDS` and print the whole list plus which entries `[:4]` would keep
   — no monkeypatching of the production function required.
2. **`scripts/trace_score_loops.py`** (Decision item 4 → AC 4). For each of the 8 pairs, reports which of
   `score_claim_for_jd`'s 4 loops fired, the token(s) each contributed, each token's tier / rarity-weight
   (`_rarity_weight`) / DCG rank-discount, the final rounded score, AND that JD's actual top-5 cutoff score
   (compute the JD's full `score_all_claims` ranking to get the 5th-place score). This will require
   re-implementing the loop bookkeeping in the wrapper (the production `score_claim_for_jd` only returns an
   int), importing `THEME_KEYWORDS`, `_rarity_weight`, `_bump` semantics, and the DCG sum from
   `jd_tailoring.py` — mirror the exact arithmetic at lines 316-345 so the traced total matches the
   production total. Sanity-check: your traced final score must equal `jd_tailoring.score_claim_for_jd(...)`
   for the same inputs.
3. **`scripts/check_guard_mitigation.py`** (Decision item 5 → AC 5). **Reuses existing production functions
   directly, no new instrumentation of internals.** Calls `cover_claim_picker.pick_cover_proofs` (line 264,
   the real cover-letter proof path) for all 8 JDs and reports which get `ACC-401-AITOOLS` / `ACC-204` in a
   proof slot and whether `_protected_ai_slot` was the reason. Then calls `jd_tailoring.score_all_claims`
   (the resume-side / `pick_cover_bullets` fallback ranking, no guard) for the same 8 pairs and reports each
   claim's rank — showing the guard-mitigation asymmetry (mitigated for `ACC-401-AITOOLS` on the cover path,
   unmitigated everywhere else and for `ACC-204` everywhere) with real output, not inference.

The **fresh baseline (Decision item 1)** and the **vocabulary-gap table (Decision item 2)** do NOT need new
instrumentation: item 1 can adapt CR-063's `scripts/measure_theme_extraction.py` (repointed to
`data/archive/submissions/`, PAR→`par_technology`), and item 2 is a pure substring read of each
`Original_JD.txt` against the relevant claim body/tags in `master_claims.json` — a short read-only script or
even a manual grep table is enough.

---

## Round 1 — full diagnostic pass (Decision items 1-6)

Run these in order. Each maps to a spec Decision item and Acceptance Criterion. Log real numbers under each
as you go, per the checkpointing protocol — do not batch.

### Round 1 plan

- [x] **Step 1 — Fresh baseline (Decision 1 → AC 1).**
- [x] **Step 2 — Vocabulary-gap table (Decision 2 → AC 2).**
- [x] **Step 3 — Pre-truncation `priority_themes` trace (Decision 3 → AC 3).**
- [x] **Step 4 — Loop-by-loop `score_claim_for_jd` trace (Decision 4 → AC 4).**
- [x] **Step 5 — Guard-mitigation confirmation (Decision 5 → AC 5).**
- [x] **Step 6 — Named root cause per claim (Decision 6 → AC 6).**
- [x] **Step 7 — Close-out checks (AC 7, AC 8).**
- [x] **Step 8 — Answer the cheap Open Question 1 if it's cheap (spec Open Questions).**

### Round 1 results

New standalone scripts built this round (all in `scripts/`, all read-only against production code/data,
zero production edits):
- `measure_aitools_acc204_baseline.py` — Step 1
- `check_vocab_gap.py` — Step 2
- `trace_priority_themes.py` — Step 3
- `trace_score_loops.py` — Step 4
- `check_guard_mitigation.py` — Step 5

Raw JSON output from Step 1 also written to `docs/reports/cr069-round1-baseline-raw-output.json`.

#### Step 1 — Fresh baseline hit-rate (differs from history — do not assume 0/6 still holds)

Ran `python measure_aitools_acc204_baseline.py`. Full console output logged; headline numbers:

| Claim | Fresh baseline (this session, current shipped code) | Last-known historical figure | Changed? |
|---|---|---|---|
| `ACC-401-AITOOLS` (6 measurable) | **1/6** (Remote HIT, rank 3, score 27 vs cutoff 24) | 0/6 (CR-066 Round 1) | **YES — improved by 1.** Remote now clears top-5, everything else still MISS. |
| `ACC-204` (2 companies) | **0/2** (unchanged) | 0/2 | No change. |

Per-company detail (rank/score of the should-surface claim vs. that JD's actual top-5 cutoff score):

| Company | Claim | Rank | Score | Top-5 cutoff | Hit? |
|---|---|---|---|---|---|
| Ontra | ACC-401-AITOOLS | 23 | 10 | 17 | MISS |
| Remote | ACC-401-AITOOLS | **3** | **27** | 24 | **HIT** |
| Covideo | ACC-401-AITOOLS | 17 | 18 | 20 | MISS |
| DataGrail | ACC-401-AITOOLS | 58 | 2 | 22 | MISS |
| MyTime | ACC-401-AITOOLS | 24 | 10 | 15 | MISS |
| PointClickCare | ACC-401-AITOOLS | 23 | 12 | 19 | MISS |
| Buyers Edge Platform | ACC-204 (best of QA/GLOBAL) | 25 | 12 | 22 | MISS |
| PAR | ACC-204 (best of QA/GLOBAL) | 38 | 10 | 18 | MISS |

SailPoint explicitly excluded (folder absent from `data/archive/submissions/`); not counted toward the
6/8 denominators above, per the Before-Round-1 orientation note.

#### Step 2 — Vocabulary-gap table

Ran `python check_vocab_gap.py`. JD-stated terms (identified by targeted grep of each `Original_JD.txt`
for AI/LLM and scrum/agile/sprint/backlog vocabulary) checked against the relevant claim's body+tags blob
from `master_claims.json`, at both whole-phrase and individual-word (`[a-z]{5,}`, the actual granularity
`score_claim_for_jd`'s loops match at) level.

**`ACC-401-AITOOLS`** (claim blob contains: `claude`, `gemini`, `prompt`, `engineering`, `agentic`,
`tooling`, `automation`, `pipeline`, `python`, `applyr`, `catalog`, etc. — but **never** `cursor`, `ai`
as a 2-char token doesn't even qualify for `[a-z]{5,}` matching):

| Company | JD-stated terms with ZERO phrase match | Individual words that DO match at token level |
|---|---|---|
| Ontra | "AI development", "LLMs", "AI capabilities", "cutting edge of AI" | (none) |
| Remote | "Cursor", "Claude Code", "autonomously build", "debug", "ship functional code" | `claude` (from "Claude Code"), `build` |
| Covideo | "AI-driven video content creation", "leverage AI", "AI-Fluent", "workflow automation" | `workflow`, `automation` |
| DataGrail | "ML practitioners", "ML-powered", "AI-first", "AI throughout the product", "Vera AI", "AI direction" | (none) |
| MyTime | "Gen AI", "LLM technologies", "AI-powered features" | (none) |
| PointClickCare | "AI/ML-powered product features", "leveraging AI", "intelligent logic", "AI, automation" | `automation` |

Confirms the spec's headline finding directly: Remote's "Cursor" (as a distinct product name, not just
the generic word) never appears in `ACC-401-AITOOLS`'s body — only "Claude" survives, and only as a bare
word, not the 2-word phrase "Claude Code" the JD uses. DataGrail, Ontra, and MyTime have **zero** overlap
at all, phrase or word level — their JDs use generic "AI"/"ML"/"LLM" vocabulary that the claim's specific
tool-name-based body never echoes.

**`ACC-204`** (claim blob = `ACC-204-QA` body+tags union `ACC-204-GLOBAL` body+tags — contains
`backlog management`, `qa`, `sdlc`, `distributed`, `teams`, `global`, `coordination`, `release
management` — but never `scrum`, `agile`, or `sprint`):

| Company | JD-stated terms with ZERO phrase match | Individual words that DO match at token level |
|---|---|---|
| Buyers Edge Platform | "sprint planning", "sprint ceremonies", "Agile methodologies", "Agile/Scrum teams", "Certified Scrum Master" | `teams` |
| PAR | "agile environment", "scrum teams", "sprint objectives", "Agile development processes, especially SCRUM", "Agile Leadership", "Scrum related events" | `teams`, `processes` |

Confirms the spec's headline finding: `ACC-204-QA`'s "backlog" is a real (if generic) match, but neither
variant contains any form of scrum/agile/sprint — the JDs' own core vocabulary for this theme.

#### Step 3 — Pre-truncation `priority_themes` trace

Ran `python trace_priority_themes.py`. Every traced truncated-list matched the real production
`build_jd_profile_deterministic()` output exactly (sanity-check assertion passed for all 6 JDs).

| Company | AI-tooling theme phrase status | Untruncated index | Displaced by truncation? |
|---|---|---|---|
| Ontra | Matched (`llm` keyword), **survived** truncation | 2 of 3 | No — kept in `priority_themes[:4]` |
| Remote | Matched (`cursor` keyword), **displaced** | 5 of 6 | **Yes** — 5 earlier generic themes (platform/data/stakeholder/integration/compliance) pushed it out |
| Covideo | **Never matched at all** — no genai/agentic/llm/cursor/claude keyword found anywhere in JD body | n/a | Not a truncation issue — the keyword itself never fires |
| DataGrail | **Never matched at all** | n/a | Not a truncation issue |
| MyTime | Matched (`llm` keyword), **survived** truncation | 2 of 3 | No — kept in `priority_themes[:4]` |
| PointClickCare | **Never matched at all** | n/a | Not a truncation issue |

Key finding: the truncation-order hypothesis (evidence item 2) is **directly confirmed for exactly 1 of 6**
(Remote) — it is real, but not the dominant mechanism across the set. In 3 of 6 (Covideo, DataGrail,
PointClickCare) there is nothing to truncate — `THEME_KEYWORDS`' 5-entry AI vocabulary (`genai`, `agentic`,
`llm`, `cursor`, `claude`) never fires against these JDs' generic "AI"/"ML"/"AI-powered" phrasing at all,
a table-coverage gap distinct from truncation order. In 2 of 6 (Ontra, MyTime) the theme survives fully
intact and still isn't enough (see Step 4).

Also re-confirmed (not re-derived): `THEME_KEYWORDS` has **zero** entries containing `scrum`/`agile`/
`sprint`/`backlog` anywhere in its (directly counted) 37-entry table, and neither `ACC-204` JD's untruncated
theme list contains any Scrum/coordination-flavored phrase (Buyers Edge: 5 generic themes, all platform/
data/stakeholder/integration/access; PAR: 5 generic themes, all platform/data/roadmap/saas/stakeholder).
Confirms the spec's claim that this mechanism is moot for `ACC-204` — there is no keyword to displace.

#### Step 4 — Loop-by-loop `score_claim_for_jd` trace

Ran `python trace_score_loops.py`. All 10 traces (6 AITOOLS + 4 ACC-204 variant×company combinations)
passed the sanity-check assertion (traced total == real production `score_claim_for_jd()` output) exactly.

Score vs. top-5 cutoff, all 8 should-surface pairs (ACC-204 shown as best-of-2-variants per company):

| Pair | Score | Cutoff | Gap | Dominant contributing token(s) |
|---|---|---|---|---|
| ACC-401-AITOOLS / Ontra | 10 | 17 | -7 | `prompt`(t1), `engineering`(t2, dual-loop), `tooling`(t1) — only 3 AI-flavored tokens total |
| ACC-401-AITOOLS / Remote | 27 | 24 | **+3 (HIT)** | `claude`(t3, loop4 full-table bypass of truncation) — single highest-value token wins it |
| ACC-401-AITOOLS / Covideo | 18 | 20 | -2 | `hands`, `automation`, `engineering`, `design` — all generic requirements-loop tokens, none AI-specific |
| ACC-401-AITOOLS / DataGrail | 2 | 22 | **-20 (worst)** | `engineering`(t1) only — single generic token, nothing else matched at all |
| ACC-401-AITOOLS / MyTime | 10 | 15 | -5 | `prompt`(t1), `engineering`(t2), `tooling`(t1), `design`(t1) |
| ACC-401-AITOOLS / PointClickCare | 12 | 19 | -7 | `including`, `engineering`, `design` — all generic, no AI tokens matched |
| ACC-204 (best variant) / Buyers Edge | 12 | 22 | -10 | `consistent`, `cross`, `across` — GLOBAL variant, no Scrum/coordination-specific token |
| ACC-204 (best variant) / PAR | 10 | 18 | -8 | `distributed` — GLOBAL variant, single generic token |

Notable: for Remote, `claude` matched via **loop 4 only** (the profile-independent full-`THEME_KEYWORDS`
scan that bypasses the 4-item `priority_themes` cap), at tier 3 (highest), confirming the spec's evidence
item 2 exactly ("only the separate, profile-independent full-table loop... can still fire, and only for
whichever literal keyword IS present... `claude`, not `cursor`"). This single high-tier, high-rarity token
(rarity weight 5.14, undiscounted at DCG rank 1) is what clears Remote's cutoff — not `priority_themes`
survival, and not truncation order once loop 4 is accounted for.

DataGrail is the extreme case: **zero** AI-relevant tokens match anywhere (confirmed consistent with Step 2's
zero-overlap finding and Step 3's "never matched" finding) — the single `engineering` token that does
match is a coincidental generic overlap, not evidence of AI-tooling relevance at all.

#### Step 5 — Guard-mitigation confirmation

Ran `python check_guard_mitigation.py`, driving the real unmodified `pick_cover_proofs` (exactly as
`cover_plan_builder.build_plan` calls it in production) and `score_all_claims` for all 8 pairs.

**Cover-letter proof path (`pick_cover_proofs`, guarded):**

| Company | `has_ai_signal` | `ACC-401-AITOOLS` proof slot? | Guard conditions met? |
|---|---|---|---|
| Ontra | True | **Yes, slot 0** | Yes — no metric, slot ≤1, AI signal true |
| Remote | True | **Yes, slot 0** | Yes |
| Covideo | True | **Yes, slot 0** | Yes |
| DataGrail | True | **Yes, slot 0** | Yes |
| MyTime | True | **Yes, slot 0** | Yes |
| PointClickCare | True | **Yes, slot 0** | Yes |

**6/6 — full mitigation on the cover-letter path**, regardless of each company's underlying base score
(including DataGrail, whose base score is only 2). `ACC-204`:

| Company | `has_ai_signal` | `ACC-204-QA`/`ACC-204-GLOBAL` proof slot? |
|---|---|---|
| Buyers Edge Platform | False | No / No |
| PAR | False | No / No (though `ACC-401-AITOOLS` incidentally won slot 2 here on pure merit, no guard involved, since `has_ai_signal` is False for PAR) |

**0/2 — no mitigation for `ACC-204`, confirmed** (zero `ACC-204` references in `cover_claim_picker.py`).

**Resume-side / fallback path (`score_all_claims`, unguarded — same ranking `pick_cover_bullets` sorts by):**

| Company | Claim | Rank | Score |
|---|---|---|---|
| Ontra | ACC-401-AITOOLS | 23 | 10 |
| Remote | ACC-401-AITOOLS | 3 | 27 |
| Covideo | ACC-401-AITOOLS | 17 | 18 |
| DataGrail | ACC-401-AITOOLS | 58 | 2 |
| MyTime | ACC-401-AITOOLS | 24 | 10 |
| PointClickCare | ACC-401-AITOOLS | 23 | 12 |
| Buyers Edge Platform | ACC-204-QA / ACC-204-GLOBAL | 33 / 25 | 10 / 12 |
| PAR | ACC-204-QA / ACC-204-GLOBAL | 45 / 38 | 8 / 10 |

**Confirms the guard-mitigation asymmetry from spec evidence item 3 with real output, not inference**: the
under-scoring problem is **fully invisible on the cover-letter path** for `ACC-401-AITOOLS` (6/6 slot-0 wins)
but **fully exposed on the resume-side/fallback path** (same ~1/6 hit rate as the raw formula, since neither
`score_all_claims` nor `pick_cover_bullets` has any guard). `ACC-204` has no mitigation anywhere.

#### Step 6 — Named root cause per claim

**`ACC-401-AITOOLS` — ranked, multi-factor (do not collapse to one cause; Steps 3+4 show 3 distinct
sub-populations within the 6 should-surface companies):**

1. **Dominant (3/6 — Covideo, DataGrail, PointClickCare; Step 3 + Step 2 evidence).** `THEME_KEYWORDS`' 5
   AI-specific entries (`genai`/`agentic`/`llm`/`cursor`/`claude`) are too narrow — they never fire at all
   when a JD uses generic "AI"/"ML"/"AI-powered"/"AI-first" phrasing instead of one of those 5 specific
   words. Step 3 shows the AI-tooling theme phrase is **never matched at all** for these 3 JDs, independent
   of the 4-item truncation cap — there is nothing to truncate because loop 3 (themes) and loop 4
   (full-table) both have zero keyword to scan for. This is a **table-coverage gap**, not the
   truncation-order mechanism evidence item 2 hypothesized. DataGrail is the extreme case (score 2 vs.
   cutoff 22, a 20-point gap) because it has zero matching tokens of any kind related to AI.
2. **Confirmed but narrow (1/6 — Remote; Step 3 + Step 4 evidence).** The truncation-order effect from
   evidence item 2 is real and directly confirmed here — the AI theme survives the keyword-match step but
   is displaced from `priority_themes[:4]` by 5 earlier generic table-order entries. However, Step 4 shows
   this does **not** actually block Remote's success: loop 4's profile-independent full-table scan
   (bypassing the 4-item cap entirely) already recovers `claude` at tier 3 with a high rarity weight, and
   that single token alone clears the top-5 cutoff (27 vs 24). Truncation order is real but not
   consequential for this claim in practice, because loop 4 is a safety net for exactly this failure mode.
3. **Secondary (2/6 — Ontra, MyTime; Step 4 evidence).** Even where the AI theme survives truncation fully
   intact, the claim's own body only contains 3 short AI-specific tokens (`prompt`, `engineering`,
   `tooling`) with a low combined ceiling once DCG rank-discounting is applied to the 2nd/3rd contributions.
   Gap sizes here (-7, -5) are the smallest among the MISS companies — this factor alone, without help from
   #1 or #2, is a real but non-catastrophic formula-breadth property (a claim with few relevant tokens has
   a structurally low score ceiling, independent of vocabulary gaps or truncation).

**Separate, orthogonal finding (Step 5):** the cover-letter-proof consumer (`pick_cover_proofs`, gated by
`has_ai_signal`/`_protected_ai_slot`) is **fully mitigated** — 6/6 AITOOLS JDs land the claim in cover-letter
slot 0 regardless of the above. The resume-side/fallback consumer (`score_all_claims`, no guard) is **not**
mitigated and shows the same low hit rate as the raw formula. **The real-world severity of this claim's
under-scoring is asymmetric by consumer**: already solved for cover letters, still live for resume-bullet
selection.

**`ACC-204` — single dominant cause, both companies (Step 2 + Step 3 evidence, directly confirmed):**

A genuine, uncontested **vocabulary/catalog-content gap**, not a scoring-formula defect. Neither
`ACC-204-QA` nor `ACC-204-GLOBAL`'s body contains "scrum", "agile", or "sprint" in any form — only
`ACC-204-QA`'s "backlog management" partially overlaps, and `THEME_KEYWORDS` has **zero** entries for any
of this vocabulary family (directly re-confirmed, 37-entry table, zero matches), so loop 3 (themes) can
never contribute a token and loop 4 (full-table) has nothing to scan for either — this mechanism is moot for
`ACC-204` exactly as the spec anticipated. Step 4's traces show only generic filler tokens contributing
(`process`, `product`, `consistent`, `cross`, `across`, `distributed`, `management`) — not one domain-specific
Scrum/coordination-flavored token — confirming the formula is scoring correctly given what's actually in the
claim text; there is simply not enough real overlap to score on. A secondary, compounding structural factor
(visible across Steps 1/4/5): `ACC-204` is **split across 2 claim variants** (QA vs. GLOBAL) that never both
score well for the same JD's needs, diluting whichever one would otherwise be strongest — exactly the
mechanism spec Open Question 3 speculated about. No guard exists for either variant on any consumer (Step 5):
0/2 on the cover-letter path, 0/4 (both variants × both companies) on the resume-side path.

#### Step 7 — Close-out checks (AC 7, AC 8)

- **AC 7 (zero production changes):** `git diff --stat` on the 6 target files at close-out is **byte-identical**
  to the Before-Round-1 baseline captured above — `scripts/jd_tailoring.py` and `data/master_claims.json`
  remain clean (zero diff); `scripts/claim_composer.py` (14/2), `scripts/cover_claim_picker.py` (39/3),
  `scripts/draft_compiler.py` (17/5), `scripts/local_draft_stages.py` (22/1) all show the exact same
  pre-existing insertion/deletion counts as the session-start baseline. **Confirmed unchanged — nothing in
  this round touched any of the 6 target files.** (The rest of the working tree remains separately, and
  pre-existingly, dirty — unrelated to this CR, not gated by AC 7.)
- **AC 8 (identical test counts):** pytest re-run at close-out: **200 passed, 28 failed, 1 skipped** —
  identical to the session-start baseline. **Confirmed.**

#### Step 8 — Open Question 1 cheap check

`ACC-401-AITOOLS`'s empty `employer` field: confirmed clean for the **scoring** question specifically
(`score_claim_for_jd`'s signature takes only `claim_text`, `profile`, `jd_text` — no `employer` parameter,
so it structurally cannot affect this diagnostic's under-scoring finding). Went one step further than the
spec flagged as optional: traced `candidate_context.employer_for_claim_id`'s fallback chain (used by
`local_draft_stages.py`'s `bucket_claim_ids`/`select_claims_deterministic`/`ensure_employer_quotas` for
**resume employer-bucket quota assignment**, a completely separate consumer from scoring). Because
`rec.employer` is falsy (`""`) and the claim ID `ACC-401-AITOOLS` doesn't start with `ACC-1`/`ACC-2`/`ACC-3`,
it falls through to `ordered[0]` — silently routing this claim into whichever employer is first in
`load_employers_ordered()` (the candidate's primary/most-recent employer) for quota-bucketing purposes only.
This is a real, minor, **separate** finding — not inert overall, but **not the under-scoring root cause**
and out of this diagnostic's scope to fix (it affects which employer-quota bucket a resume-selected
`ACC-401-AITOOLS` bullet gets grouped under, not whether it gets selected in the first place). Flagging for
Jason's awareness, not opening a dedicated thread.

Open Questions 2 (bespoke `ACC-204` guard vs. general-formula fix) and 3 (is a claim-content fix the
load-bearing lever) are answered with evidence, not resolved, per the spec's Out-of-Scope constraint — see
Step 6 above: both claims' dominant causes are vocabulary/catalog-content gaps rather than formula defects,
which is direct evidence in favor of Open Question 3's hypothesis (claim-content fix as the load-bearing
lever) for both claims, and directly relevant to Open Question 2 (a guard mirrors what already works for
`ACC-401-AITOOLS` on the cover-letter path, but Step 6 shows `ACC-204`'s gap is vocabulary-level, so a guard
would mask the symptom on the cover-letter path only — it would do nothing for the equally-unmitigated
resume-side path, unlike a catalog-content fix which would help both consumers). Both remain Jason's calls.

---

## Session Handoff — read this FIRST, fill it in before you stop

If "Last updated" below is still the template placeholder, no session has run this CR yet — start at
"Before Round 1." Otherwise trust this block over re-deriving state from the round logs.

- **Last updated:** 2026-07-15, Round 1 executed and completed in full (Senior Engineer session).
- **Current stage:** **Round 1 complete — all 8 Acceptance Criteria satisfied.** Fresh baseline measured
  (Step 1: 1/6 AITOOLS, 0/2 ACC-204 — AITOOLS improved by 1 since last-known 0/6, likely from CR-064-final/
  CR-066/CR-068 fixes landing since that figure was taken). Vocabulary-gap table built (Step 2). Pre-truncation
  theme trace built and run (Step 3). Loop-by-loop score trace built and run, all sanity-checks passed (Step
  4). Guard-mitigation confirmed with real output (Step 5). Named, ranked root causes written for both claims
  (Step 6). Close-out checks confirm zero production changes and identical pytest counts (Step 7). Open
  Question 1 cheap-checked and answered (Step 8). **This is diagnostic-only — no fix has been implemented.**
  Full real numbers, tables, and root-cause writeups are in the "Round 1 results" section above; do not
  re-derive them, read them directly.
- **State of the world right now:** 5 new standalone scripts added to `scripts/` (all read-only against
  production code/data, zero production edits): `measure_aitools_acc204_baseline.py`, `check_vocab_gap.py`,
  `trace_priority_themes.py`, `trace_score_loops.py`, `check_guard_mitigation.py`. One new JSON artifact at
  `docs/reports/cr069-round1-baseline-raw-output.json`. The 6 target production files
  (`jd_tailoring.py`/`cover_claim_picker.py`/`draft_compiler.py`/`claim_composer.py`/`local_draft_stages.py`/
  `master_claims.json`) are confirmed byte-identical to the session-start baseline — 2 clean, 4 pre-dirty
  with unchanged diffs. Pytest: 200 passed / 28 failed / 1 skipped, identical before and after.
- **Exact next action:** This CR's Phase 1 (measurement + root cause) is done. There is no Round 2 planned
  in this tracker — any further work (a fix) requires a **new, separate CR** per the spec's Out-of-Scope
  section ("Any fix... this phase is measurement and a written finding only"). Do not implement a fix inside
  this tracker. If Jason wants to proceed, next step is Jason deciding on Open Questions 2 (bespoke `ACC-204`
  guard vs. general-formula fix) and 3 (claim-content fix as the load-bearing lever) and someone scoping a
  follow-up CR from those decisions plus this round's root-cause findings.
- **Anything discovered that changes the plan:** `THEME_KEYWORDS` is actually 37 entries, not 36 as
  originally noted (off-by-one in the prior orientation note, no functional impact, corrected in the
  Before-Round-1 section above). The eval set names `ACC-401-AITOOLS` should-surface on 7 companies, not 6
  (spec undercount); SailPoint's absence from the archive independently leaves 6 measurable, so the numbers
  align with the spec's "6/8" but for a different reason — logged as excluded per the orientation note, not
  treated as the eval-set truth. Two minor spec line-drift typos (has_ai_signal "210"→449, pick_cover_proofs
  "134"→264) — functions exist, no impact. Biggest substantive discovery: the truncation-order hypothesis
  (spec evidence item 2) is real but only explains 1 of 6 AITOOLS companies (Remote) — the dominant cause
  for AITOOLS is a `THEME_KEYWORDS` table-coverage gap (3/6 companies never match any AI keyword at all,
  independent of truncation), not truncation order. See Step 6 for the full ranked writeup.
- **Open questions for Jason:** None new. The spec's 3 Open Questions are all answered with evidence (not
  resolved) in Step 6/Step 8 above: (1) empty `employer` field is clean for scoring, but does silently affect
  which employer-quota bucket a selected `ACC-401-AITOOLS` resume bullet lands in — minor, separate, not the
  root cause; (2) a bespoke `ACC-204` guard would only fix the cover-letter-path symptom, not the equally-
  unmitigated resume-side path, since `ACC-204`'s gap is vocabulary-level not consumer-level — evidence leans
  toward this being a narrower fix than the underlying gap; (3) both claims' dominant root causes are
  vocabulary/catalog-content gaps, not formula defects — direct evidence in favor of a claim-content fix
  being the load-bearing lever over further formula tuning. All three remain Jason's decisions to make.
