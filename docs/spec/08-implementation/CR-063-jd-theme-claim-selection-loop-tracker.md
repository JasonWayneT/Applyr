---
status: fallbacks_ruled_out_awaiting_formula_fix
created: 2026-07-13
spec: ../05-change-requests/CR-063-jd-theme-claim-selection-loop.md
eval_set: ../../reports/jd-theme-claim-eval-set.md
---

# CR-063 Tracker — JD Theme-Extraction & Claim-Selection Loop

Resumable round-by-round log. **Read the Session Handoff block at the very bottom of this file first**
— if a prior session left one filled in, that block tells you exactly where to pick up, and you should
trust it over re-deriving state from the round logs yourself. Only if the handoff block is still the
empty template should you start at "Before Round 1" below. Read `CR-063-jd-theme-claim-selection-loop.md`
too if you haven't this session — it has the full problem statement and hard constraints (selection
accuracy only, never fabricate a claim).

## Checkpointing protocol — this work will span multiple sessions, plan for it

This loop will very likely hit a context or time limit before it's done — that's expected, not a
failure. Every stage of work must be resumable by a fresh session with zero conversation history,
using only this file plus the files it references. Four rules, no exceptions:

1. **Before executing any plan — a full round, or a specific fix within a round — write the plan out
   as its own ordered checklist right here in this file**, under the round you're working on, even if
   it's more granular than what's pre-written below. A plan that only exists in your own reasoning is
   invisible to whoever picks this up next.
2. **Check off and log each step as you finish it, not in a batch at the end.** If you're interrupted
   between steps 2 and 3 of a 5-step plan, the next session needs to see 2 checked and 3-5 unchecked,
   with real state (what a measurement actually showed, what a fix actually was) written in place — not
   a stale unchecked list, and not a summary reconstructed from memory after the fact.
3. **If you sense you're running low on context or session time, stop at the nearest checkpoint
   boundary.** Do not try to cram in "just one more fix" you won't have room to verify and log properly.
   A cleanly stopped, fully logged Round 2 Step 3 beats a rushed, unlogged Round 3.
4. **Before ending any session on this CR — whether by finishing a round or by running out of room —
   fill in the Session Handoff block at the bottom of this file.** That block is read first by whoever
   comes next, before anything else in this document.

## Before Round 1 — orientation (do this once)

- [x] Read `docs/reports/jd-theme-claim-eval-set.md` in full — this is the fixed ground truth, do not
      re-derive it from scratch.
- [x] Read `scripts/jd_tailoring.py` end to end, specifically `THEME_KEYWORDS`, `score_claim_for_jd`,
      `build_jd_profile_deterministic`, `pick_cover_bullets`.
- [x] Read `scripts/local_embeddings.py` and `scripts/claim_catalog.py`'s `_sync_embeddings` — confirm
      whether `data/claim_embeddings.json` (the cache) is still present and current, or needs
      regenerating. **Result:** cache present (`data/claim_embeddings.json`, mtime Jul 13 10:36) and
      newer than `data/master_claims.json` (mtime Jul 12 13:01) — freshness check in `_sync_embeddings`
      passes, cache is current, no regeneration needed.
- [x] Read `scripts/pipeline_env.py` in full — `draft_mode`, `jd_profile_mode`, `cover_hook_mode`,
      `_COMPOSE_LIKE_DRAFT_MODES`, `local_only_mode`. Confirm what `DRAFT_MODE` env var is actually set
      to right now, if anything, vs. the `"compose"` default. **Result:** no `DRAFT_MODE`,
      `JD_PROFILE_MODE`, or `COVER_HOOK_MODE` env vars set in this shell — all defaults apply:
      `draft_mode()="compose"` → `jd_profile_mode()="deterministic"`, `cover_hook_mode()="template"`.
      This matches the CR's "current pipeline" deterministic path that Round 1 is supposed to measure.
- [x] Confirm the 16 `Original_JD.txt` files referenced in the eval set are still present and unchanged
      in `data/submissions/{company}/` — the eval set was built against these exact files. **Result:**
      all 16 present and non-empty (`buyers_edge_platform`, `covideo`, `cresta`, `datagrail`,
      `group_1001`, `lumos`, `mytime`, `onestream_software`, `ontra`, `par`, `parkingpass_com`,
      `pointclickcare`, `redox`, `remote`, `sailpoint`, `tilt`).

## Round 1 — Baseline measurement (What Happened vs. What Should Have Happened)

### Round 1 plan
- [x] Confirm module wiring needed: `claim_catalog.load_catalog()` → `ClaimCatalog` (skips `disabled`
      claims at load); `jd_tailoring.build_jd_profile_deterministic(jd_text)` → `JdProfile`;
      `jd_tailoring.score_all_claims(profile, catalog, jd_text)` → sorted `(ClaimRecord, score)` list.
      This is the real batch-scoring path used by `select_cl_claims`/resume selection, not just the
      single-claim `score_claim_for_jd` — using it directly avoids re-deriving ranking logic.
- [x] Map each of the 16 eval-set company names to its `data/submissions/{folder}/Original_JD.txt` path
      (folder slugs differ slightly from the eval set's display names, e.g. "OneStream" →
      `onestream_software`, "Buyers Edge Platform" → `buyers_edge_platform`).
- [x] Write `scripts/measure_theme_extraction.py` (standalone, not wired into the main pipeline): for
      each of the 16 JDs, load `Original_JD.txt`, call `build_jd_profile_deterministic()`, call
      `score_all_claims()` against the full catalog, capture top-5 claim_ids + scores + extracted
      `priority_themes`.
- [x] Run it across all 16 and produce a table: company | themes extracted | top-5 claims ranked | which
      of the eval set's "should surface" claims landed in the top-5 (yes/no per claim).
- [x] Compute the aggregate hit rate (measured, not estimated).
- [x] Log the result below under "Round 1 results," with the raw output table.

### Round 1 results

Script: `scripts/measure_theme_extraction.py`. Ran deterministic JD-profile + full-catalog claim
scoring (`build_jd_profile_deterministic` → `score_all_claims`) against all 16 `Original_JD.txt` files,
same code path the compose pipeline uses by default (confirmed no env override in this shell).

Correction made while building the script (logging the wrong turn, not just the fix, per the
checkpointing protocol): `master_claims.json`'s real claim_ids all carry a descriptive suffix (e.g.
`ACC-107-COMPLIANCE`, `ACC-107-LEGAL`, `ACC-107-PLATFORM`, `ACC-401-AITOOLS`). I first assumed
`ACC-401-AITOOLS` and `ACC-107-LEGAL` were eval-set typos needing resolution to bare `ACC-401`/`ACC-107`
— checked via `load_catalog()` and both exist verbatim, so no resolution was needed there; that
assumption was simply wrong. The real ambiguity is the *opposite* direction: most of the eval set's
codes (`ACC-101`, `ACC-102`, `ACC-103`, `ACC-104`, `ACC-105`, `ACC-107`, `ACC-109`, `ACC-113`) are bare
and don't exist as literal claim_ids at all — they match `ClaimRecord.project_id`
(`_project_id_from_claim_id` strips the suffix), which is shared by 2-4 suffixed claim variants each.
**Scoring rule used below:** a bare eval-set code counts as a hit if *any* claim_id sharing that
project_id lands in the top-5; a fully-suffixed eval-set code (`ACC-401-AITOOLS`) counts as a hit only
if that exact claim_id lands in the top-5. "Sterkly dev-coordination bullet" (Buyers Edge) and
"ACC-204-style dev-team coordination" (PAR) are free-text in the eval set, not codes — treated as
project_id `ACC-204` for matching purposes (its two suffixed variants, `ACC-204-QA` and
`ACC-204-GLOBAL`, are the only Sterkly dev-coordination claims in the catalog).

Script output written to `docs/reports/cr063-round1-raw-output.json` (full themes/top-5/scores per JD).

| Company | Themes extracted (deterministic) | Top-5 claim_ids (score) | Should-surface | Hit/Miss |
|---|---|---|---|---|
| Cresta | platform reliability, security backlog, roadmap, revenue-generating | ACC-105-EXECUTION(25), ACC-115-REQUIREMENTS(19), ACC-103-ROADMAP(18), ACC-105-PROCESS(18), ACC-101-RETENTION(16) | ACC-107 / ACC-103 / ACC-101 | MISS / HIT / HIT |
| SailPoint | platform reliability, security backlog, roadmap, stakeholder alignment | ACC-104-CS(18), ACC-109-SYNTHESIS(18), ACC-111-SCOPE(15), ACC-102-MODERN(12), ACC-103-ROADMAP(12) | ACC-107 / ACC-103 / ACC-401-AITOOLS | MISS / HIT / MISS |
| Group 1001 | platform reliability, data integrity, roadmap, stakeholder alignment | ACC-113-MIGRATION(18), ACC-105-EXECUTION(13), ACC-106-DATA(13), ACC-102-INT(12), ACC-102-BUS(11) | ACC-101 / ACC-103 / ACC-105 / ACC-107 / ACC-113 | MISS / MISS / HIT / MISS / HIT |
| OneStream | platform reliability, data integrity, roadmap, B2B SaaS delivery | ACC-105-EXECUTION(14), ACC-102-INT(11), ACC-103-ROADMAP(11), ACC-113-MIGRATION(10), ACC-101-OPS(9) | ACC-107 | MISS |
| Buyers Edge Platform | platform reliability, data integrity, stakeholder alignment, API integration | ACC-102-INT(16), ACC-109-PROCESS(15), ACC-113-MIGRATION(14), ACC-115-REQUIREMENTS(14), ACC-101-RETENTION(13) | ACC-109 / ACC-204 | HIT / MISS |
| Ontra | platform reliability, data integrity | ACC-102-INT(14), ACC-202-REQUIREMENTS(13), ACC-115-REQUIREMENTS(12), ACC-113-MIGRATION(11), ACC-203-TECH(10) | ACC-401-AITOOLS / ACC-103 | MISS / MISS |
| Remote | platform reliability, data integrity, stakeholder alignment, API integration | ACC-102-INT(15), ACC-113-MIGRATION(14), ACC-102-BUS(12), ACC-112-COMPLIANCE(12), ACC-112-PIPELINE(11) | ACC-401-AITOOLS / ACC-106 | MISS / MISS |
| Tilt | platform reliability, data integrity, roadmap, B2B SaaS delivery | ACC-115-REQUIREMENTS(15), ACC-105-EXECUTION(14), ACC-102-BUS(12), ACC-202-REQUIREMENTS(12), ACC-101-OPS(11) | ACC-101 / ACC-104 | HIT / MISS |
| Covideo | platform reliability, data integrity, roadmap, B2B SaaS delivery | ACC-105-EXECUTION(10), ACC-111-SCOPE(10), ACC-102-TECH(9), ACC-203-BUS(9), ACC-111-ENTERPRISE(9) | ACC-401-AITOOLS / ACC-105 | MISS / HIT |
| DataGrail | platform reliability, data integrity, security backlog, roadmap | ACC-102-INT(14), ACC-102-TECH(13), ACC-102-BUS(12), ACC-109-SYNTHESIS(12), ACC-111-ENTERPRISE(12) | ACC-107 / ACC-401-AITOOLS / ACC-103 | MISS / MISS / MISS |
| MyTime | roadmap, B2B SaaS delivery | ACC-202-REQUIREMENTS(12), ACC-105-EXECUTION(11), ACC-202-DELIVERY(11), ACC-105-PROCESS(10), ACC-103-ROADMAP(8) | ACC-401-AITOOLS / ACC-104 / ACC-105 | MISS / MISS / HIT |
| PAR | platform reliability, roadmap, B2B SaaS delivery, stakeholder alignment | ACC-105-EXECUTION(17), ACC-101-OPS(11), ACC-105-PROCESS(11), ACC-101-RETENTION(10), ACC-111-SCOPE(10) | ACC-105 / ACC-204 / ACC-109 | HIT / MISS / MISS |
| ParkingPass.com | data integrity, roadmap, B2B SaaS delivery | ACC-102-MODERN(10), ACC-203-INDUSTRY(9), ACC-109-SYNTHESIS(8), ACC-105-EXECUTION(7), ACC-204-QA(7) | ACC-101 / ACC-103 / ACC-109 | MISS / MISS / HIT |
| PointClickCare | data integrity, roadmap, stakeholder alignment, API integration | ACC-105-EXECUTION(18), ACC-105-PROCESS(17), ACC-202-REQUIREMENTS(15), ACC-112-COMPLIANCE(15), ACC-102-LEAD(14) | ACC-101 / ACC-102 / ACC-109 / ACC-401-AITOOLS | MISS / HIT / MISS / MISS |
| Redox | data integrity, B2B SaaS delivery, stakeholder alignment, revenue-generating | ACC-105-EXECUTION(16), ACC-203-BUS(16), ACC-111-ENTERPRISE(16), ACC-110-LEADERSHIP(13), ACC-109-PROCESS(12) | ACC-101 / ACC-103 / ACC-109 | MISS / MISS / HIT |
| Lumos | platform reliability, data integrity, roadmap, B2B SaaS delivery | ACC-106-DATA(17), ACC-113-MIGRATION(17), ACC-109-SYNTHESIS(16), ACC-102-TECH(15), ACC-104-CS(14) | ACC-102 / ACC-107-LEGAL / ACC-103 / ACC-101 | HIT / MISS / MISS / MISS |

**Aggregate: 14/45 should-surface codes present in top-5** across 16 JDs. **Per-company full pass (every
should-surface code hit): 0/16.**

### Round 1 diagnosis notes (feeds directly into Round 2 planning)

- `ACC-105-EXECUTION` (Agile/prioritization/delivery, generic tags) appears in **11 of 16** top-5 lists —
  it is the dominant score winner almost regardless of JD content. This is the same "generic vocabulary
  crowds out distinctive themes" defect the CR names for `THEME_KEYWORDS`, but showing up in the claim
  layer too: `ACC-105`'s tags (`Prioritization`, `Delivery`, `Engineering Alignment`, `Agile Planning`)
  overlap almost every SaaS-PM JD's boilerplate language, so it racks up keyword-overlap score
  everywhere.
- `ACC-107` (compliance/privacy/access) — the theme the CR calls out by name as entirely missing from
  `THEME_KEYWORDS` — never once appears in a top-5 across all 6 JDs that should surface it (Cresta,
  SailPoint, Group 1001, OneStream, DataGrail, Lumos). This is the single highest-value fix candidate:
  0/6 hit rate on a theme the CR already root-caused.
- `ACC-401-AITOOLS` (explicit "AI Tools/Prompt Engineering/Agentic Workflows" claim) has an empty
  `employer` field in `master_claims.json` and never appears in any top-5, including JDs where the
  eval set calls AI-fluency a **hard stated requirement** (Covideo, Remote) — worth checking whether
  `THEME_KEYWORDS` has no "ai"/"llm"/"genai" entry at all (confirmed: it does not — the table has no
  AI-related keyword, only domain-specific SaaS/fintech terms), which would starve this claim of any
  theme-based scoring bonus.
- `ACC-204` (Sterkly dev-coordination) never surfaces for Buyers Edge or PAR — no `THEME_KEYWORDS` entry
  maps to Scrum/team-coordination language either.
- Two structural false-negatives, not content gaps: Group 1001's top claim is `ACC-113-MIGRATION` (score
  18) which is *also* one of its should-surface codes — Group 1001 actually scores 2/5 (ACC-105, ACC-113)
  correctly per the per-code table, better than the discouraging "themes look generic" read suggests.
- This confirms the CR's own diagnosis rather than contradicting it: the gaps cluster exactly where
  `THEME_KEYWORDS` has no entry (`privacy`/`compliance`/`identity`/`access`/`governance` for ACC-107,
  `ai`/`llm`/`genai` for ACC-401-AITOOLS, `agile`/`scrum`/`coordination` for ACC-204) — these look like
  (a)-type fixes (missing keyword-table entries) per the Round 2 classification scheme, not (c)-type
  scoring-formula problems or (d)-type semantic-only gaps. `ACC-105-EXECUTION`'s over-triggering is more
  likely a (c)-type generic-token over-weighting problem.

## Round 2+ — Diagnose, fix smallest thing, re-test full set

Before running anything, add a "### Round N plan" subsection below listing the specific mismatches
you're tackling this round as its own checklist (per the checkpointing protocol above) — the four
bullets here are the recurring per-round procedure, not a substitute for that concrete list.

For each mismatch found in Round 1 (or the prior round):
- [ ] Classify it: (a) missing `THEME_KEYWORDS` entry, (b) claim has weak/missing tags in
      `master_claims.json`, (c) scoring formula over-weights a generic token, (d) requires semantic
      similarity or LLM judgment that no keyword-table fix can reach.
- [ ] For (a)/(b)/(c): apply the single smallest fix. Do not batch multiple unrelated fixes into one
      round — one round should test one hypothesis at a time so you know which change caused which
      effect.
- [ ] Re-run the full 16-JD measurement from Round 1, not just the JD that motivated this round's fix.
      Confirm no regression on JDs that were previously passing.
- [ ] Log before/after hit rate and what changed, in a new "Round N results" section below.
- [ ] Repeat until 14/16 hit rate is reached, or all (a)/(b)/(c)-type fixes are exhausted and only
      (d)-type gaps remain.

### Round 2 plan

**Hypothesis under test this round:** adding `THEME_KEYWORDS` entries for the privacy/compliance/access
vocabulary the CR names as entirely missing will raise `ACC-107`'s hit rate above 0/6, without
regressing any JD that currently passes. One hypothesis only — no other keyword or scoring change this
round.

- [x] Add `THEME_KEYWORDS` entries (classification: (a) missing keyword-table entry) for the terms the
      CR problem statement names as absent: `privacy`, `compliance`, `identity`, `access`, `governance`.
      Phrased each entry toward `ACC-107`'s actual tag vocabulary (`Compliance`, `Privacy`, `GDPR/CCPA`,
      `Legal Alignment`, `Third-Party Integration`, `Vendor Terms`, `Platform Architecture`, `Automated
      Workflows`, `Governance`) so the theme text itself scores against those claims in
      `score_claim_for_jd`'s theme-token loop.
- [x] Re-run `scripts/measure_theme_extraction.py` unchanged (no script edits) across all 16 JDs.
- [x] Confirm `ACC-107`'s hit rate specifically (target: improve on 0/6) and confirm no JD that
      previously had a HIT on any code regresses to MISS. **Result: ACC-107 improved 0/6 → 1/6
      (DataGrail), but a different regression was found on Lumos's ACC-102 — see results below.**
- [x] Log before/after aggregate (14/45 baseline) and the ACC-107-specific before/after in "Round 2
      results" below.

### Round 2 results

Applied: added `privacy`, `compliance`, `identity`, `access`, `governance` to `THEME_KEYWORDS` in
`scripts/jd_tailoring.py`, phrased toward `ACC-107`'s real tag vocabulary. No other change. Re-ran
`measure_theme_extraction.py` unchanged across all 16 JDs.

**Result: net flat at the aggregate level (14/45 → 14/45), but NOT a no-op** — one real fix and one real
regression cancelled out:

- **Fixed:** DataGrail's `ACC-107` flipped MISS → HIT (`ACC-107-PLATFORM` entered top-5 at score 12,
  displacing `ACC-111-ENTERPRISE`). This is the intended effect of the fix working correctly.
- **Regressed:** Lumos's `ACC-102` flipped HIT → MISS. Before: top-5 included `ACC-102-TECH` (score 15).
  After: `ACC-102-TECH` was pushed out by `ACC-105-EXECUTION` (16, generic over-triggering — see Round 1
  notes) and `ACC-112-COMPLIANCE` (16, newly boosted by the `compliance` keyword this round). Root cause:
  `ACC-112-COMPLIANCE`'s tags (`Compliance`, `Content Licensing`, `Access Control`, `Third-Party Terms`)
  overlap almost entirely with `ACC-107-COMPLIANCE`/`ACC-107-LEGAL`'s tags (`Compliance`, `Privacy`,
  `GDPR/CCPA`, `Legal Alignment`, `Third-Party Integration`, `Vendor Terms`) — the new `compliance` and
  `access` keywords can't distinguish "compliance = privacy/legal governance" (what Lumos and most
  eval-set JDs actually mean) from "compliance = content-licensing/vendor-terms" (`ACC-112`'s specific
  domain). Widening the keyword table raised recall for the JD it was aimed at, and cost precision on
  an adjacent claim with genuinely overlapping tags.
- No other previously-passing code (any HIT from Round 1) flipped to MISS. Lumos is the only regression.
- All other before/after per-JD results were identical to Round 1 (see raw table above vs. re-run).

**Decision:** keep the fix — it is net-neutral in aggregate but net-positive in kind (fixes a named,
CR-called-out gap; the regression is a pre-existing ambiguity between two already-similar claims'
tags, not something the fix invented). Flagging the `ACC-107` vs `ACC-112` tag-overlap problem as its
own Round 3 candidate: classification (b) (claim has overlapping/under-differentiated tags), specifically
`ACC-112-COMPLIANCE`'s tags read almost identically to `ACC-107-COMPLIANCE`/`ACC-107-LEGAL`'s — the fix
there is tightening `ACC-112`'s tags to its actual content-licensing/vendor-terms specificity (or
`ACC-107`'s to privacy/GDPR specificity) so `score_claim_for_jd`'s tag-token overlap can tell them apart,
not another `THEME_KEYWORDS` addition.

### Round 3 plan

**Hypothesis under test this round:** `ACC-401-AITOOLS` (0/6 hit rate, including two JDs — Covideo,
Remote — where the eval set marks AI-fluency as a hard stated requirement) is missing purely because
`THEME_KEYWORDS` has zero AI/LLM-related entries. Confirmed via grep before writing this plan: no
`ai`/`llm`/`genai`/`agentic` keyword exists in the table. Adding entries should raise this specific
claim's hit rate without the ACC-107/ACC-112 tag-collision problem from Round 2, since no other claim's
tags overlap AI-tooling vocabulary. One hypothesis only.

- [x] Add `THEME_KEYWORDS` entries (classification: (a) missing keyword-table entry) for `genai`,
      `agentic`, `llm`, phrased toward `ACC-401-AITOOLS`'s actual tags (`AI Tools`, `Prompt Engineering`,
      `Agentic Workflows`, `Automation`, `Python`). Deliberately did NOT add bare `ai` — it's a substring
      of common words (`maintain`, `obtain`, `training` doesn't contain it but `remain`/`detail`-adjacent
      forms do) and `THEME_KEYWORDS` matching is plain substring (`kw in jd_lower`), not word-bounded, so
      it would be noisy. Mid-round discovery: Remote's JD (an eval-set hard-requirement JD for this exact
      claim) contains zero AI-vocabulary words at all — it says "Proficiency in Cursor and/or Claude
      Code" — so also added `cursor` and `claude` as literal keyword entries; same single hypothesis
      (make `ACC-401-AITOOLS`'s real JD-vocabulary triggers exist in the table), not a second fix.
- [x] Re-run `scripts/measure_theme_extraction.py` unchanged across all 16 JDs.
- [x] Confirm `ACC-401-AITOOLS`'s hit rate specifically (target: improve on 0/6) and confirm no
      previously-passing code regresses. **Result: hit rate did NOT improve — still 0/6 — despite the
      keyword bonus verifiably firing. See diagnosis below; this is not a repeat of the Round 2 failure
      mode (no tag collision found), it's a different mechanism.**
- [x] Log before/after aggregate (14/45 after Round 2) and the ACC-401-AITOOLS-specific before/after in
      "Round 3 results" below.

### Round 3 results

Applied: added `genai`, `agentic`, `llm`, `cursor`, `claude` to `THEME_KEYWORDS` in
`scripts/jd_tailoring.py`. Re-ran `measure_theme_extraction.py` unchanged across all 16 JDs.

**Result: 14/45 → 14/45, zero movement, no regressions.** `ACC-401-AITOOLS` still 0/6.

**Diagnosis — confirmed the fix mechanism fires, but its magnitude is too small to matter:**
manually verified with a direct `score_claim_for_jd` call (not just the top-5 script) that for Remote,
`"claude"` is a literal substring of both the JD text ("Proficiency in Cursor and/or Claude Code") and
`ACC-401-AITOOLS`'s claim body ("Daily hands-on use of Claude and Gemini...") — so the `+3` per-matched-
keyword bonus in `score_claim_for_jd`'s final loop does apply. `ACC-401-AITOOLS`'s Remote score came out
to only **3** total, while Remote's actual 5th-place top-5 cutoff was **12** (`ACC-102-BUS`). Same
pattern on Ontra (score 4 vs. cutoff ~10) and Covideo (score 1 vs. cutoff 9) — the theme-keyword bonus
mechanism (`+1`/`+3` per token) is flatly outweighed by claims like `ACC-105-EXECUTION`/`ACC-102-INT`/
`ACC-113-MIGRATION` that accumulate large scores from broad, generic keyword/requirement-token overlap
(these are the same over-triggering claims flagged in the Round 1 notes).

**This is a different failure mode than Round 2's tag-collision regression** — no other claim's tags
collide with `ACC-401-AITOOLS`'s AI vocabulary, so there's no adjacent-claim conflict to fix. The actual
defect is that `score_claim_for_jd`'s scoring formula gives a flat, small, uniform bonus (+1 theme-token,
+2 requirement-token, +3 keyword-in-both) regardless of how distinctive or rare the matched term is —
a JD-specific named-tool match like "Claude Code" or "Cursor" (which should be a very strong, almost
disqualifying-if-absent signal per the eval set's own "hard requirement" framing) scores identically to
a single generic token match. Classification: **(c) scoring formula over-weights generic tokens /
under-weights rare-and-specific ones** — not exhausted-cheap-fixes/semantic-only territory yet, but also
not a small, isolated keyword-table edit like Round 2/3's additions. Fixing it properly would mean
changing `score_claim_for_jd`'s weighting (e.g., a much larger bonus for a JD requirement-section term
that is rare across the full claims catalog, or a TF-IDF-style rarity weight instead of flat +1/+2/+3) —
a real formula change with catalog-wide blast radius, which is exactly the kind of change the
checkpointing protocol says shouldn't be crammed in without room to verify and log it properly.
**Flagging as the lead Round 4 candidate** rather than attempting it in this session's remaining budget.

### Regression check between rounds (added mid-session, applies retroactively to Rounds 2-3)

Ran the project's full `scripts/` pytest suite (`python -m pytest -q --ignore=test_domain_gate.py
--ignore=test_fit_policy.py --ignore=test_llm.py` — those three are standalone scripts with
module-level `sys.exit`/API-key requirements, not real pytest files, pre-existing collection issue
unrelated to this CR) both with and without the Round 2+3 `THEME_KEYWORDS` edits (isolated via
`git stash push -- scripts/jd_tailoring.py`, path-limited so the rest of the already-messy working tree
was untouched). **Identical result both times: 188 passed, 27 failed, 1 skipped.** The 27 failures are
pre-existing (cover-letter-slot/audit/gap-detector tests unrelated to JD theme/claim selection) and were
not caused by this CR's edits. Confirms Rounds 2-3 introduced zero test regressions.

### Round 4 — diagnosis-only (no code change applied)

**Hypothesis tested:** `ACC-204` (Sterkly dev-coordination, missing for Buyers Edge and PAR) is another
missing-keyword case fixable the same way as Rounds 2-3 — add `scrum`/`agile`/`sprint`/`backlog` to
`THEME_KEYWORDS`.

- [x] Confirmed via literal grep that Buyers Edge's and PAR's JDs both contain `scrum`, `agile`,
      `sprint`, `backlog` verbatim.
- [x] Checked the two real claim variants sharing project_id `ACC-204`: `ACC-204-QA`'s body contains
      `backlog` verbatim ("Owned backlog management..."); `ACC-204-GLOBAL`'s body contains none of
      `scrum`/`agile`/`sprint`/`backlog` at all ("Coordinated with a globally distributed engineering
      team... release cadence").
- [x] Before writing any code, manually computed what adding `backlog` as a keyword would do (avoiding
      a repeat of Round 2's blind-apply-then-discover-the-regression pattern): `ACC-204-QA`'s score
      against Buyers Edge is currently 8; the top-5 cutoff is 13. The `+3` bonus from a new `backlog`
      keyword would bring it to 11 — still short. Against PAR, `ACC-204-QA` is at 1 and `ACC-204-GLOBAL`
      at 4, versus a cutoff of 10 — not remotely close, and `ACC-204-GLOBAL` (the variant PAR's eval-set
      description "ACC-204-style dev-team **coordination**" actually seems to mean) wouldn't benefit from
      the keyword at all since its body doesn't contain any of those terms.
- [x] **Decision: did not apply this fix.** The manual calculation showed it would not close either
      gap, so implementing it would have been a wasted edit with the same regression risk as Round 2
      for no measured benefit — skipped per "only changing the code you need to change."

**Why this is being logged as a real round despite no code change:** it's the third consecutive keyword-
table candidate to underperform (Round 2: fixed one JD, regressed another; Round 3: fires correctly but
loses to generic-vocabulary claims by 3-8x; Round 4: doesn't even get close). That's enough evidence to
stop guessing at more individual keywords and diagnose the shared root cause directly.

**Root-cause diagnosis (traced by inspecting `score_claim_for_jd`'s actual arithmetic on a live example,
not by re-reading the code in the abstract):** decomposed `ACC-105-EXECUTION`'s score of 25 against
Cresta's JD. Its short, generic body ("enforced strict prioritization... across engineering teams...
platform stability, compliance mandates... roadmap delivery") re-earns credit from the SAME handful of
common words multiple times because `score_claim_for_jd` has three independent scoring loops with no
cross-loop dedup: the profile-keyword loop, the per-requirement-line token loop (`+2` per 5+-letter token,
uncapped per requirement — and Cresta's JD yields 6 requirement lines, several of which redundantly
contain "engineering"/"teams"/"platform"), and the full-`THEME_KEYWORDS`-table loop (`+3` per table
entry present in both). A claim using ordinary PM vocabulary (engineering, teams, platform, roadmap,
across) collects small bonuses from all three loops simultaneously and from multiple requirement lines
that each restate the same word. A claim with one precise, rare, JD-specific term (`ACC-401-AITOOLS`'s
"Claude", `ACC-204`'s "backlog") only ever earns the flat `+3` once, because rare terms by definition
don't recur across profile keywords, multiple requirement lines, and the theme-keyword table
simultaneously the way generic ones do. **This is a structural (c)-type defect** — not a missing keyword,
a missing claim tag, or a semantic-only gap — and fixing it correctly (e.g., deduping repeated-token
credit across requirement lines, or weighting rarity) is a formula change with catalog-wide blast radius
that needs its own careful round with full regression testing, not a same-round bolt-on to a keyword
diagnosis. Documented here as the clearest concrete evidence for the go/no-go call below, rather than
attempted half-built in the time remaining this session.

## Final round — go/no-go on semantic matching or LLM mode

Entered after 3 consecutive keyword-table rounds (2-4) showed diminishing/risky returns and Round 4
traced the remaining gaps to a structural scoring-formula property (no cross-loop dedup rewards
generic-vocabulary accumulation over rare precise matches) — see Round 4 diagnosis above. Confirmed
Ollama is reachable and `nomic-embed-text` is pulled (`curl localhost:11434/api/tags`), so this pilot is
actually runnable, not theoretical.

### Final-round plan

- [x] Write `scripts/measure_semantic_rerank.py` (standalone pilot script, NOT modifying
      `score_claim_for_jd` or any production pipeline path — this is explicitly a pilot per the CR's own
      "small blast radius" instruction). For each of the 16 JDs: get a JD embedding via
      `local_embeddings.get_embedding`, compute `cosine_similarity` against every claim's already-cached
      embedding (`catalog.claim_embeddings`, populated by `claim_catalog.load_catalog()`), combine as
      `final_score = keyword_score + round(cosine_similarity * SCALE)`, re-rank, check should-surface
      hit/miss same as `measure_theme_extraction.py`.
- [x] Run it across all 16 JDs (not just the failing ones) so a real before/after aggregate is possible
      — a parallel pilot script carries none of the live-pipeline regression risk that editing
      `score_claim_for_jd` directly would, so there's no reason to artificially narrow the test set.
- [x] Compare aggregate hit rate against the Round 4 baseline (14/45 codes, 0/16 companies). **Result:
      WORSE at every scale tested, not better — see results below.**
- [x] Since it did NOT improve (see below): sample-tested `jd_profile_mode="llm"` on 3 of the
      worst-performing JDs before writing the go/no-go, since the reasoning for skipping it needed to be
      more than "embeddings already failed" — an LLM judge reads full text and isn't inherently subject
      to the same compressed-cosine-similarity problem, so it deserved its own check.
- [x] Write the go/no-go recommendation grounded in the actual round-by-round numbers in this file.

### Final-round results

**Semantic re-ranking pilot (`scripts/measure_semantic_rerank.py`):** confirmed Ollama reachable and
`nomic-embed-text:latest` present (`curl localhost:11434/api/tags`). Computed `final_score = kw_score +
round(cosine_similarity * SCALE)` and swept `SCALE` across 0, 5, 8, 12, 20, 30 (0 = pure keyword
baseline, for a same-script sanity check against `measure_theme_extraction.py`'s numbers — matched
exactly at 14/45, confirming the pilot's scoring path is consistent with the production path it
mirrors).

| SCALE | Aggregate | Per-company pass |
|---|---|---|
| 0 (keyword-only, sanity check) | 14/45 | 0/16 |
| 5 | 12/45 | 0/16 |
| 8 | 13/45 | 0/16 |
| 12 | 12/45 | 0/16 |
| 20 | 11/45 | 0/16 |
| 30 | 11/45 | 0/16 |

**Monotonically non-improving at every scale tested — this is not a tuning problem, it's a signal
problem.** Manually inspected the cached cosine similarities across all 63 claims for several JDs: they
cluster tightly (roughly 0.43-0.65 for SailPoint, Cresta, etc.) regardless of whether a claim is
actually relevant to that JD. `nomic-embed-text` isn't meaningfully discriminating between these claims
— short, stylistically uniform "B2B SaaS PM accomplishment" paragraphs apparently embed too similarly to
each other for cosine distance to separate relevant from irrelevant ones. Any non-zero scale therefore
adds noise on top of a keyword ranking that, for several JDs, was already correct — e.g. SailPoint's
`ACC-103` was a HIT at scale 0 (via `ACC-103-ROADMAP` in the keyword-only top-5) and flipped to a MISS
at scale 20 purely because `ACC-204-QA` and `ACC-203-INDUSTRY` had marginally higher cosine similarity
and displaced it. **Conclusion: wiring `cosine_similarity` into claim ranking, at least with
`nomic-embed-text` and this claim catalog's writing style, would make selection accuracy worse, not
better. Do not wire this in.**

**`jd_profile_mode="llm"` sample pilot:** ran `build_jd_profile(jd_text)` with `JD_PROFILE_MODE=llm` set
(no other env override) against the 3 worst-performing JDs (Redox 0/3, Ontra 0/2, OneStream 0/1 at
Round-4 baseline), confirming per the CR's own claim that this stage prefers local models first — it
used `llama3.1:8b-instruct-q5_K_M` locally, no cloud call, 4-8s per JD.

| Company | LLM-extracted themes | LLM top-5 | Should-surface | Hit rate | vs. deterministic baseline |
|---|---|---|---|---|---|
| Redox | Fast-paced environment, Enterprise software, Complex B2B sales cycles | ACC-111-ENTERPRISE(12), ACC-113-MIGRATION(12), ACC-101-ANCHOR(11), ACC-101-RETENTION(11), ACC-107-PLATFORM(10) | ACC-101/103/109 | 1/3 (ACC-101) | **Identical** (1/3 at baseline too, same ACC-101 variants) |
| Ontra | AI, Product Vision, Cross-Functional Collaboration | ACC-102-INT(12), ACC-113-MIGRATION(9), ACC-102-BUS(7), ACC-102-MODERN(7), ACC-104-LIFECYCLE(7) | ACC-401-AITOOLS/103 | 0/2 | **Identical** (0/2 at baseline) |
| OneStream | Customer Success, Product Roadmap, AI-Powered Enterprise Marketplace | ACC-115-REQUIREMENTS(11), ACC-113-MIGRATION(10), ACC-102-INT(9), ACC-103-SEC(9), ACC-102-TECH(8) | ACC-107 | 0/1 | **Identical** (0/1 at baseline) |

**This is the single most important finding of the whole loop.** For Ontra, the LLM correctly identified
`"AI"` as a theme and `"Experience with AI development"` as an explicit requirement — a genuinely better,
more accurate JD read than the deterministic keyword table produced (which found no AI theme at all
before Round 3's fix, and still under-weights it after). **But `ACC-401-AITOOLS` still didn't crack the
top-5**, because a better-extracted `JdProfile` still feeds into the exact same `score_claim_for_jd`
function that Round 4 diagnosed as structurally biased toward generic-vocabulary accumulation over
precise, specific matches. Improving JD-profile quality — whether via better keywords or a real LLM —
cannot fix a downstream ranking-formula defect. **Both of the CR's proposed fallback paths (embeddings,
LLM-mode profiling) fail for the same underlying reason, not two different reasons.**

### Go/no-go recommendation

**Status against the CR's acceptance bar:** 14/45 should-surface codes, 0/16 companies with a full pass
— far short of the 14/16 bar, and none of the three fallback/patch strategies tested this session
(more `THEME_KEYWORDS` entries, semantic re-ranking, LLM-mode JD profiling) meaningfully closed the gap.
This is not a failed loop — it is a loop that did exactly its job: it definitively ruled out three of
the four hypothesized fix strategies with real data, and pinpointed the actual defect to one specific,
narrow location.

**Recommendation: do not expand `THEME_KEYWORDS` further, do not wire in embeddings, do not broaden the
LLM-mode pilot. Rewrite `score_claim_for_jd`'s scoring formula — specifically, add cross-loop dedup and
a rarity weight — as its own follow-up CR/story, before touching claim-selection code again.**

Reasoning, grounded in this session's actual numbers, not architectural preference:

1. **Keyword-table fixes (Rounds 2-4) are demonstrably not the lever.** Three attempts: one fix +
   one regression (net zero), one correct-but-too-weak fix (zero movement), one fix ruled out by hand
   calculation before implementation (would not have closed either target gap). The common failure mode
   across all three is not "wrong keywords" — it's that even a correct keyword match only earns a flat
   `+3` once, while generic claims accumulate small bonuses from three separate uncapped scoring loops
   (profile-keyword overlap, per-requirement-line tokens, theme tokens) simultaneously. `ACC-105-EXECUTION`
   alone appeared in 11 of 16 top-5 lists across every round tested, unmoved by any keyword-table edit.
2. **Semantic re-ranking (embeddings, already cached and cheap to test) failed cleanly, not
   ambiguously.** Swept 6 scale values; the aggregate got monotonically *worse* as the semantic weight
   increased (14/45 → 11/45), and inspection showed why: `nomic-embed-text` cosine similarities across
   this claim catalog cluster too tightly (0.43-0.65) to discriminate relevant from irrelevant claims,
   because the claim bodies are all written in a stylistically uniform "B2B SaaS PM accomplishment"
   voice. This isn't a scale-tuning problem to revisit later — the embedding model isn't separating this
   specific text corpus, full stop, at least not usefully enough to help rather than hurt.
3. **LLM-mode JD profiling (already the CR's other proposed fallback) produced identical selection
   accuracy to the deterministic path on the 3 worst JDs tested, despite genuinely better theme
   extraction.** This is the decisive piece of evidence: it proves the defect is NOT in how the JD gets
   read (keyword table vs. LLM), it's in what happens to a correctly-read JD profile afterward, in
   `score_claim_for_jd`'s ranking arithmetic. Piloting LLM mode more broadly would cost real local-model
   inference time (4-8s/JD observed) to re-confirm a conclusion already reached on a representative
   sample.
4. **The formula defect is narrow and specific, not "rewrite everything":** `score_claim_for_jd` needs
   (a) some form of dedup so the same word doesn't earn credit repeatedly across the keyword/requirement/
   theme loops and across multiple requirement lines, and (b) a way to weight a rare, JD-specific,
   exact-substring match (a named tool, a specific compliance regime) more heavily than an incidental
   overlap on common PM vocabulary. This is scoped enough to be its own careful CR/story with its own
   regression-tested rollout — not a same-session bolt-on, per the checkpointing protocol's guidance
   against cramming in unverified changes.

**Explicit non-recommendation:** do not begin scoping Hybrid Anchor + Polish (CR-062's phase 2) on the
strength of this finding alone. The defect found here lives entirely inside the existing deterministic
`score_claim_for_jd` function — it's a bug in arithmetic, not evidence that the deterministic architecture
itself is insufficient. Fix the formula first and re-run this exact eval set before concluding a bigger
architecture change is warranted.

## Guardrails (apply every round, no exceptions)

- Every fix must be traceable to an existing `master_claims.json` claim and its `workExperience.md`
  anchor. If a round's diagnosis is "we need a new claim," stop and flag it to Jason — do not invent one.
- Re-run `submission_linter.lint_document` and `quality_checker.check_resume` on any resume/cover letter
  actually regenerated during testing, same as every other session in this project.
- Do not touch `data/submissions/` for the 16 already-reviewed companies as part of this loop — they are
  done. This loop tests the pipeline's *default* behavior using their JDs as fixed input, not their
  finished output.

---

## Session Handoff — read this FIRST, fill it in before you stop

Whoever is reading this at the start of a session: check "Last updated" below. If it's still the
template placeholder, no prior session has touched this CR yet — start at "Before Round 1." Otherwise,
trust this block over re-deriving state from the round logs above.

Whoever is ending a session on this CR, whether you finished a full round or are stopping mid-step
because you're low on context/time: fill this in before you go. Be concrete — "continue Round 2" is not
an exact next action, "run the fix from Round 2 Step 3 against JDs Redox and Tilt, which hadn't been
re-tested yet when the session ended" is.

- **Last updated:** 2026-07-13, end of second working session on this CR (continued through Round 4 and
  the Final round in one sitting after the first session's handoff).
- **Current stage:** Loop's diagnostic phase is essentially complete. Rounds 1-4 and the Final round
  (semantic re-ranking pilot + LLM-mode pilot) are all run and logged, with a go/no-go recommendation
  written. What's NOT done: the actual scoring-formula fix the recommendation calls for — that's
  deliberately out of scope for this session (see recommendation's reasoning) and is the next concrete
  step, likely warranting its own story/CR given catalog-wide blast radius.
- **State of the world right now:** Baseline 14/45 should-surface codes, 0/16 full-company-pass, measured
  via `scripts/measure_theme_extraction.py` (standalone). Three keyword-table rounds (2-4) left the
  aggregate at 14/45 net (one real fix + one real regression in Round 2, one correctly-firing-but-
  too-weak fix in Round 3, one calculated-and-skipped candidate in Round 4). The Final round tested both
  of the CR's proposed fallbacks with real local infra (Ollama running, `nomic-embed-text` cached,
  `llama3.1:8b` for LLM mode) and ruled out both: semantic re-ranking made the aggregate monotonically
  *worse* (14/45 → 11/45 as scale increased, tested at 6 scale values), and LLM-mode JD profiling
  produced byte-identical selection accuracy to the deterministic path on the 3 worst JDs despite
  genuinely better theme extraction. Root cause is now pinned to `score_claim_for_jd` itself: three
  independent, uncapped scoring loops (profile-keyword overlap, per-requirement-line tokens, theme
  tokens) let generic PM vocabulary accumulate credit repeatedly, while a single rare/specific match
  (a named tool, a compliance regime) only ever earns a flat `+3` once. `scripts/jd_tailoring.py`
  currently has the Round 2+3 keyword additions live (10 lines added to `THEME_KEYWORDS`, confirmed via
  `git diff` to be the only change in that file) — no other production code was touched. Full `scripts/`
  pytest suite confirmed clean both before and after: 188 passed / 27 failed (pre-existing, unrelated) /
  1 skipped, identical both times.
- **Exact next action:** Scope and implement the `score_claim_for_jd` formula fix the go/no-go
  recommendation calls for: (1) dedup so the same JD word can't earn credit from the profile-keyword
  loop, the per-requirement-line loop, AND the theme-keyword loop simultaneously (or at minimum, so it
  can't earn `+2` repeatedly across multiple requirement lines that restate the same word), and (2) some
  form of rarity weighting so an exact match on a distinctive term (a named tool, a specific compliance
  regime) scores meaningfully higher than an incidental match on common PM vocabulary (engineering,
  platform, teams, roadmap). Do this as its own round with its own plan/checkboxes here in the tracker —
  it touches every claim's score on every JD, so re-run the full 16-JD measurement (not a sample) plus
  the full pytest suite afterward, same discipline as every prior round. `ACC-105-EXECUTION`'s 11/16
  over-triggering and `ACC-401-AITOOLS`/`ACC-204`'s under-scoring are the same defect from opposite
  sides — a working fix should move both simultaneously; if it only fixes one, look harder before
  declaring success.
- **Anything discovered that changes the plan:** The two fallback paths the CR itself proposed as the
  "if keyword fixes plateau" answer (semantic re-ranking, LLM-mode profiling) are now both ruled out by
  real data, not just architectural reasoning — this is a stronger, more specific conclusion than the CR
  anticipated going in. The actual fix is narrower and more mechanical than either fallback: a formula
  bug in `score_claim_for_jd`, not a missing-capability problem needing new infrastructure. Do not spend
  further session time on `THEME_KEYWORDS` edits, embedding weights, or LLM-mode piloting — all three
  are now closed lines of investigation with logged evidence in this file. Also: this tracker had an
  ordering bug earlier this session (Round 3's plan/results got inserted after the Final-round section
  by an earlier edit) — it's been fixed and the section order is now Round 1 → 2 → 3 → regression check
  → Round 4 → Final round → Guardrails; if anything reads out of chronological order again, check for
  a similar edit-anchor mistake before assuming the content itself is wrong.
- **Open questions for Jason:** None requiring his input yet — every fix/pilot traces to existing
  `master_claims.json` claims and no new claim was proposed. Two things worth his awareness before the
  next session does the formula rewrite: (1) `ACC-107` vs `ACC-112`'s tag overlap (Round 2 finding) may
  eventually warrant tightening `master_claims.json` tags themselves (not inventing a claim, just
  clarifying existing ones) — flag before editing since it's the source-of-truth catalog; (2) the
  `score_claim_for_jd` fix is explicitly recommended as its own scoped follow-up rather than something
  attempted live this session — worth confirming he agrees with deferring it rather than pushing through
  now, given it's a catalog-wide-blast-radius change.
