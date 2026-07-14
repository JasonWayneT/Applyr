---
status: closed_partial
created: 2026-07-13
spec: ../05-change-requests/CR-064-claim-score-formula-rework.md
eval_set: ../../reports/jd-theme-claim-eval-set.md
predecessor_tracker: CR-063-jd-theme-claim-selection-loop-tracker.md
---

# CR-064 Tracker — Claim-Score Formula Rework (`score_claim_for_jd`)

Resumable round-by-round log, same discipline as its predecessor CR-063. **Read the Session Handoff
block at the very bottom of this file first** — if a prior session left one filled in, that block tells
you exactly where to pick up, and you should trust it over re-deriving state from the round logs
yourself. Right now the handoff block is pre-filled with the starting state (this CR hasn't had a
working session yet) — treat it as the literal first thing to do, not a template to ignore.

Read `CR-064-claim-score-formula-rework.md` first if you haven't this session — it has the full problem
statement, the hard signature constraint, and why the two obvious alternatives (embeddings, LLM mode)
are already ruled out. Then read the predecessor tracker,
`CR-063-jd-theme-claim-selection-loop-tracker.md`, specifically its "Round 4", "Final round", and
"Go/no-go recommendation" sections — that's the full diagnostic trail this CR is executing on, not just
the summary repeated here.

## Checkpointing protocol — this work will span multiple sessions, plan for it

Same four rules CR-063 used, because they worked:

1. **Before executing any plan — a full round, or a specific fix within a round — write the plan out
   as its own ordered checklist right here in this file**, under the round you're working on, even if
   it's more granular than what's pre-written below.
2. **Check off and log each step as you finish it, not in a batch at the end.** Real state (what a
   measurement actually showed, what a fix actually was), not a stale unchecked list or a
   reconstructed-from-memory summary.
3. **If you sense you're running low on context or session time, stop at the nearest checkpoint
   boundary.** A cleanly stopped, fully logged step beats a rushed, unlogged one.
4. **Before ending any session on this CR, fill in the Session Handoff block at the bottom.** Read
   first by whoever comes next, before anything else in this document.

## Before Round 1 — orientation (do this once)

- [ ] Read `docs/spec/05-change-requests/CR-064-claim-score-formula-rework.md` in full.
- [ ] Read `CR-063-jd-theme-claim-selection-loop-tracker.md`'s "Round 4", "Final round", and "Go/no-go
      recommendation" sections — this is where the dedup/rarity diagnosis and the two ruled-out
      fallbacks are documented with real numbers, not just asserted.
- [x] Read `scripts/jd_tailoring.py`'s `score_claim_for_jd` (currently lines ~226-241) and
      `score_all_claims`/`select_cl_claims`/`pick_cover_bullets` end to end — understand exactly how the
      four scoring loops combine today before changing them. **Result (tech-lead pass, 2026-07-13):
      real current location is lines 236-251 (spec's "~226-241" was ~10 lines off, immaterial). Function
      body matches the spec's transcription exactly.**
- [x] Confirm the 6 production call sites are still exactly these (grep to re-verify, code may have
      moved since 2026-07-13): `local_draft_stages.py:438`, `claim_composer.py:154,216`,
      `draft_compiler.py:406,496`, `cover_claim_picker.py:134`. All must keep working with an unchanged
      3-argument `score_claim_for_jd(claim_text, profile, jd_text)` signature. **Result: all 6 confirmed
      at the exact line numbers claimed, zero drift. NOTE: `claim_composer.py:154/216` have `catalog` in
      scope; `local_draft_stages.py:438`, `draft_compiler.py:406`, `cover_claim_picker.py:134` do NOT
      (only `dict`/`str` params) — this matters for the rarity-cache design, see Round 1 plan below.**
- [x] Confirm `scripts/measure_theme_extraction.py` (built by CR-063, not modified since) still runs
      clean and reproduces the CR-063 baseline exactly: **14/45 should-surface codes, 0/16 companies
      with a full pass**. **Result (tech-lead pass, 2026-07-13): does NOT run clean as-is —
      `data/submissions/sailpoint/` and `data/submissions/group_1001/` are missing from this working
      tree (likely a Google Drive sync gap), so the script throws `FileNotFoundError` on the 2nd
      eval-set company. Jason's decision: adjust the eval set to the 14 companies actually present
      rather than pause for a restore. New working baseline: 11/37 should-surface codes, 0/14 companies
      with a full pass** (45−37=8 codes = SailPoint's 3 + Group 1001's 5, so this is consistent with,
      not contradictory to, the original 14/45 — just not a byte-for-byte reproduction of it). **Every
      reference to "14/45, 0/16" elsewhere in this tracker and in the CR-064 spec should be read as
      "11/37, 0/14" until/unless the two missing folders are restored.** If restored later, re-run
      against the full 16 and treat that as the real baseline going forward.
- [x] Confirm `scripts/jd_tailoring.py`'s current `THEME_KEYWORDS` still has the CR-063 Round 2+3
      additions live (`privacy`, `compliance`, `identity`, `access`, `governance`, `genai`, `agentic`,
      `llm`, `cursor`, `claude` — 10 entries, still uncommitted as of 2026-07-13, confirm via
      `git diff -- scripts/jd_tailoring.py`). This CR builds on top of that state, not a clean baseline.
      **Result: confirmed, exactly the 10 claimed lines, still uncommitted.**
- [x] Confirm Ollama is NOT required for this CR (the formula fix is pure Python arithmetic over
      `master_claims.json` token frequencies — no embeddings, no LLM calls) — this CR should be fully
      testable without any local-model dependency, unlike CR-063's Final round. **Result (tech-lead pass):
      confirmed as a design constraint, but with a real latent risk to design around — see Round 1 plan
      item on `claim_catalog.load_catalog()` vs. reading `master_claims.json` directly.**
- [x] Run the full `scripts/` pytest baseline once before touching anything:
      `python -m pytest -q --ignore=test_domain_gate.py --ignore=test_fit_policy.py --ignore=test_llm.py`
      (those three are pre-existing non-pytest collection issues). Confirm it matches CR-063's documented
      baseline: **188 passed, 27 failed, 1 skipped**. If it doesn't match, something changed in the repo
      since 2026-07-13 — investigate before using this as your regression baseline. **Result: exact
      match, 188 passed / 27 failed / 1 skipped.**

## Round 1 — Design the dedup + rarity mechanism (no code yet)

Do NOT write the implementation before this round is checked off — the CR-063 experience (three
keyword-table rounds, one of which caused a real regression from an unexamined tag collision) shows the
value of deciding the mechanism on paper first, then implementing, rather than iterating blind.

### Round 1 plan
- [x] Decide the dedup mechanism precisely. **Decision (tech-lead, 2026-07-13): thread a
      `matched: dict[str, int]` (surface token -> best/highest base tier seen) through all four loops
      via a `_bump(tok, tier)` helper that keeps the MAX tier per token; final score sums
      `tier * rarity_weight(tok)` once per unique token. Base tiers are unchanged from today's per-hit
      values — keyword loop=1, requirement loop=2, theme loop=1, THEME_KEYWORDS loop=3. Take-the-max
      (not sum) per token, because sum-across-loops IS today's compounding bug; max preserves the
      "strongest signal for this token wins" intent while removing the double/triple count. Verified by
      hand against Cresta/ACC-105: collapses today's raw 28 to a dedup-only 19 — `platform` (loops
      2+3+4) 3 hits -> tier 3 once, `engineering` (2 requirement lines) 2 hits -> tier 2 once, `ability`
      (2 lines) -> once, `across` (loop1+loop2) -> tier 2 once, `roadmap` (loops 3+4) -> tier 3 once.
      The surface-token string is the dedup key; a loop-1 keyword phrase that isn't equal to a single
      extracted token simply won't collide with loops 2-4, which is acceptable (a genuinely different
      match signal).**
- [x] Decide the rarity-weight mechanism precisely. **Decision (tech-lead, 2026-07-13): a module-level
      lazy df table over active (non-disabled) claims; `weight(tok) = 1 + log(N / df(tok))` (smoothed
      IDF), floor `1.0` for any token absent from the table. N = active-claim count (63 in this tree).
      Built once on first `score_claim_for_jd` call, cached in module globals `_RARITY_DF`/`_RARITY_N` —
      NOT recomputed per call (runs thousands of times per batch run), NOT keyed off catalog identity
      (self-loads from disk, see data-source item).
      Rejected alternative, tested on paper not just reasoned: a scale-neutral mean-normalized weight
      `idf(tok)/mean_idf`. It ERASES the rare-token advantage this mechanism exists to create — this
      63-claim catalog's mean idf is already high (3.715; most of the 596 vocab tokens appear in only
      1-2 claims), so dividing by it compresses `claude` back to weight ~1.1 and leaves Remote/ACC-401
      unmoved (rank 43->30, score still 3). Smoothed IDF instead lifts Remote decisively (43->24,
      3->15). Known tradeoff, flagged: `1+log(N/df)` inflates the absolute scale ~1.7x-5x — fine for
      ranking (scale-invariant within one JD) but it interacts with the cover-letter flat bonuses (see
      cover-letter item).
      Absent-token floor 1.0 (not treating absent as maximally-rare) is deliberate: a JD token absent
      from the word-tokenized table is almost always a substring artifact — e.g. `ability` inside
      "st**ability**", which fires in Cresta's loop 2 today. Flooring it to 1.0 quietly suppresses that
      noise without touching the substring-matching logic (out of scope for this CR).**
- [x] Write out the exact new `score_claim_for_jd` pseudocode here in this file before touching
      `scripts/jd_tailoring.py`. **Done — see "Round 1 results" below.**
- [x] Sanity-check the design by hand against the two concrete examples CR-063 measured. **Done — see
      "Round 1 results". In brief: Remote/ACC-401 moves as intended (rank 43->24, score 3->15);
      Cresta/ACC-105 does NOT drop in rank (stays #1) and its absolute score rises (28->49) via scale
      inflation. A real, must-review finding — full interpretation and why it does not invalidate the
      design is in the results section.**
- [x] **(Added by tech-lead, 2026-07-13) Decide the rarity-table data source explicitly.**
      **Decision: self-load `data/master_claims.json` via plain `json.load` (path from the imported
      `PROJECT_ROOT`). Confirmed by inspection the file is a dict keyed by claim id (not a list) —
      iterate `.values()`, skip any record that isn't a dict or has `disabled` truthy. Build df over
      each claim's `text` + `" ".join(tags)`, tokenized with the same `re.findall(r"[a-z]{5,}", ...)`
      the scoring loops use, incrementing each token at most once per claim (`set(...)` per claim). Do
      NOT go through `claim_catalog.load_catalog()` — it calls `_sync_embeddings()` -> Ollama when the
      embeddings cache is stale, a dormant coupling this CR must not introduce. Confirmed live: 63
      active claims, 1 disabled.**
- [x] **(Added by tech-lead, 2026-07-13) Decide a test-isolation mechanism for the rarity cache.**
      **Decision: module globals `_RARITY_DF = None`, `_RARITY_N = None`, lazy-built by
      `_get_rarity_table()`. Two test hooks: `_reset_rarity_cache()` (sets both to `None`, forces
      rebuild) and `_set_rarity_table(df, n)` (injects a fixed synthetic table so new dedup/rarity unit
      tests pin exact arithmetic without coupling to production catalog contents that drift). New unit
      tests build a hand-made df table via `_set_rarity_table` and call `_reset_rarity_cache()` in
      teardown. `test_claim_preselection.py`'s MagicMock catalogs are untouched — they never reach the
      rarity cache, which self-loads from disk rather than reading the passed-in catalog.**
- [x] **(Added by tech-lead, 2026-07-13) Note the return-type constraint explicitly in the pseudocode.**
      **Decision: the weighted sum accumulates as a float `total`; the function returns
      `int(round(total))`, shown explicitly at the return below. Also adds a new `import math` to
      `jd_tailoring.py` (currently imports only `json`, `os`, `re` from stdlib) — trivial, flagged so it
      is not a surprise in the Round 2 diff.**
- [x] **(Added by tech-lead, 2026-07-13 — resolves a backflow item) Plan the cover-letter-side check.**
      **Decision: do NOT retune `_complement_score` / `_proof_score`'s flat bonuses (3-8 pts, +10 for
      `cover_story`) inside this CR — that is calibration risk against a moving scale and violates the
      "ranking-arithmetic fix, not a bonus recalibration" guardrail. Instead, Round 2 hand-verifies
      `pick_cover_bullets` (`jd_tailoring.py:260-341`) and `cover_claim_picker.py`'s `_proof_score`
      (`cover_claim_picker.py:134`) — selected proof points and their order — for 3 concrete eval-set
      JDs before/after: **cresta** (exercises `_proof_score`'s security/compliance/data branches),
      **remote** (rare AI token — does ACC-401 now compete for a cover slot?), and **covideo**
      (media/monetiz — exercises `_complement_score`'s `media`/`monetiz` branches). If scale inflation
      makes any flat bonus negligible or dominant, flag to Jason as a separate calibration follow-up
      rather than folding a retune into this CR. Concrete mechanism of the risk: those bonuses were tuned
      against a base scale of ~3-28; the new base scale is ~15-49 for the same JDs, so an 8-pt bonus that
      was ~30% of a strong base score is now ~16% of it.**

### Round 1 results

**Design, as pseudocode (drop-in replacement for `score_claim_for_jd`; module-level cache + helpers
added alongside it in `jd_tailoring.py`). Requires `import math`. NOT YET IMPLEMENTED — gated on Jason's
review per the Session Handoff.**

```python
# --- module level in jd_tailoring.py ---
_RARITY_DF: dict[str, int] | None = None   # token -> number of active claims containing it
_RARITY_N: int | None = None               # number of active (non-disabled) claims

def _reset_rarity_cache() -> None:                          # test hook
    global _RARITY_DF, _RARITY_N
    _RARITY_DF, _RARITY_N = None, None

def _set_rarity_table(df: dict[str, int], n: int) -> None:  # test hook — inject fixed table
    global _RARITY_DF, _RARITY_N
    _RARITY_DF, _RARITY_N = dict(df), n

def _get_rarity_table() -> tuple[dict[str, int], int]:
    global _RARITY_DF, _RARITY_N
    if _RARITY_DF is not None and _RARITY_N is not None:
        return _RARITY_DF, _RARITY_N
    path = os.path.join(PROJECT_ROOT, "data", "master_claims.json")
    with open(path, encoding="utf-8") as fh:
        claims = json.load(fh)                              # dict keyed by claim id
    df: dict[str, int] = {}
    n = 0
    for rec in claims.values():
        if not isinstance(rec, dict) or rec.get("disabled"):
            continue
        n += 1
        blob = ((rec.get("text") or "") + " " + " ".join(rec.get("tags") or [])).lower()
        for tok in set(re.findall(r"[a-z]{5,}", blob)):     # count each token once per claim
            df[tok] = df.get(tok, 0) + 1
    _RARITY_DF, _RARITY_N = df, n
    return df, n

def _rarity_weight(token: str) -> float:
    df, n = _get_rarity_table()
    freq = df.get(token, 0)
    if freq <= 0:                # absent / substring artifact (e.g. 'ability' in 'stability') -> floor
        return 1.0
    return 1.0 + math.log(n / freq)

# --- signature UNCHANGED, return still int ---
def score_claim_for_jd(claim_text: str, profile: JdProfile, jd_text: str) -> int:
    text_l = claim_text.lower()
    jd_l = jd_text.lower()

    # DEDUP PASS: surface token -> best (max) base tier across all four loops.
    matched: dict[str, int] = {}
    def _bump(tok: str, tier: int) -> None:
        if matched.get(tok, 0) < tier:
            matched[tok] = tier

    for w in profile.keywords:                             # loop 1, tier 1
        if w in text_l and w in jd_l:
            _bump(w, 1)
    for req in profile.requirements:                       # loop 2, tier 2
        for tok in re.findall(r"[a-z]{5,}", req.lower()):
            if tok in text_l:
                _bump(tok, 2)
    for theme in profile.priority_themes:                  # loop 3, tier 1
        for tok in re.findall(r"[a-z]{5,}", theme.lower()):
            if tok in text_l:
                _bump(tok, 1)
    for kw, _phrase in THEME_KEYWORDS:                     # loop 4, tier 3
        if kw in jd_l and kw in text_l:
            _bump(kw, 3)

    # RARITY-WEIGHT PASS: each unique token contributes once, scaled by how rare it is catalog-wide.
    total = 0.0
    for tok, tier in matched.items():
        total += tier * _rarity_weight(tok)

    return int(round(total))                               # signature pinned -> int
```

**Hand-check #1 — Cresta / ACC-105-EXECUTION (currently 28). N=63. Instrumented against the real cached
JD profile (`data/submissions/cresta/jd_profile_cache.json`) and the real claim body.**

Deduped matched tokens (tier = max across loops; weight = `1 + ln(63/df)`; floor 1.0 if df=0):

| token | max tier | df | weight | tier x weight |
|---|---|---|---|---|
| ability | 2 | 0 (substring of "stability") | 1.000 | 2.000 |
| across | 2 | 12 | 2.658 | 5.316 |
| compliance | 3 | 10 | 2.841 | 8.522 |
| delivery | 1 | 8 | 3.064 | 3.064 |
| engineering | 2 | 15 | 2.435 | 4.870 |
| platform | 3 | 22 | 2.052 | 6.156 |
| prioritization | 1 | 5 | 3.534 | 3.534 |
| roadmap | 3 | 7 | 3.197 | 9.592 |
| teams | 2 | 8 | 3.064 | 6.127 |

Sum = 49.18 -> `int(round(...))` = **49**. Old = 28. **Score went UP, not down. Rank vs the full
63-claim field: 1 -> 1 (UNCHANGED).**

**Hand-check #2 — Remote / ACC-401-AITOOLS (currently 3). N=63.**

| token | max tier | df | weight | tier x weight |
|---|---|---|---|---|
| claude | 3 | 1 | 1 + ln(63) = 5.143 | 15.429 |

Sum = 15.43 -> **15**. Old = 3. **Rank vs the full field: 43 -> 24 (UP 19 places).**

**Verdict — honest; this is the part Jason must review before authorizing implementation:**

- **Remote (under-scoring-rare-match symptom): the design works as intended.** The single genuine,
  JD-critical `claude` match now carries real weight (5.14x vs the old flat +3), lifting ACC-401 from
  rank 43 to 24 of 63. This is the exact defect the rarity mechanism was built for, moving decisively in
  the right direction. Confident.

- **Cresta (generic-over-scoring symptom): the design does NOT drop ACC-105's rank on this single JD,
  and the tracker's pre-round prediction that Cresta's score would "drop significantly" is wrong — the
  score rises 28 -> 49.** Two things are happening, both matter:
  1. The **dedup pass does its job**: collapses ACC-105's raw 28 to a dedup-only 19, killing the
     cross-loop/cross-line compounding (platform counted 3x, engineering/ability/across each 2x). That
     part is validated.
  2. The **rarity pass re-inflates it to 49**, because — contrary to the pre-round assumption that
     ACC-105 wins on "common PM vocabulary" — its surviving tokens are NOT all common: `roadmap` (df 7),
     `prioritization` (df 5), `compliance` (df 10), `teams`/`delivery` (df 8) are *moderately rare*, and
     each is genuinely on-theme for Cresta (Cresta's extracted themes: "roadmap prioritization and
     execution", "platform reliability and scale", "security backlog and risk reduction"). For THIS JD,
     ACC-105 is arguably a legitimate strong match, not a false positive.

  Load-bearing conclusion: **Cresta is a weak single-JD proxy for what CR-063 actually complained about
  — ACC-105 appearing in the top-5 of 11/16 (now 11/14) JDs, a CROSS-JD over-representation.** A
  single-JD hand-check cannot confirm the "reduces over-representation" claim; only the full 14-JD
  `measure_theme_extraction.py` run (Round 2's measurement) can, by checking whether ACC-105's top-5
  appearance COUNT falls from 11/14. The absolute-score-down prediction was the wrong success metric for
  a scale-inflating multiplier; top-5 appearance count across the eval set is the right one.

- **Two items flagged for Jason, not smoothed over:**
  1. **Scale inflation is real and interacts with the cover-letter flat bonuses.** Base scores rise
     ~1.7x-5x on this evidence (Cresta 28->49, Remote 3->15). `_complement_score`/`_proof_score`'s flat
     3-8 pt bonuses were tuned against the old scale and become relatively smaller. Round 2's
     cover-letter-side hand-check (cresta/remote/covideo) is where this gets caught; the decision is to
     flag any distortion as a separate calibration follow-up, not retune inside this CR.
  2. **The Cresta result means the acceptance criterion "ACC-105's over-representation measurably drops"
     is NOT yet demonstrated** and cannot be until Round 2's full-set run. If that run shows ACC-105
     still surfacing in ~11/14 top-5 lists, the pure-additive dedup+rarity SUM is insufficient on its
     own (it rewards breadth — ACC-105 wins by matching 9 tokens; ACC-401 loses with 1 strong match),
     and a breadth-dampening refinement (diminishing returns on the Nth matched token, or a peak-match
     component) is the next lever. I am NOT introducing that now — it is a second mechanism the spec
     doesn't mandate, and whether it's needed is a measured Round-2 question plus a Jason decision, not a
     Round-1 improvisation.

## Round 2+ — Implement, measure, iterate

Same procedure as CR-063's Round 2+, adapted:

For each implementation step:
- [ ] Implement the smallest coherent piece of the Round 1 design (e.g. dedup first, rarity weight
      second, as two separate rounds if that makes attributing effect-to-cause cleaner — same
      "test one hypothesis at a time" discipline CR-063 used).
- [ ] Re-run `scripts/measure_theme_extraction.py` across the 14 JDs actually present in this working
      tree (SailPoint and Group 1001 are missing — see "Before Round 1" note above; restore and re-run
      against the full 16 if/when those two folders come back). Confirm:
      (a) aggregate should-surface hit rate vs. the adjusted baseline (**11/37**) and the prior round,
      (b) `ACC-105-EXECUTION`'s top-5 appearance count vs. the adjusted baseline (**11/14**),
      (c) `ACC-401-AITOOLS` and `ACC-204`'s hit rates vs. baseline (0/6 and 0/2 respectively, unless
      either fell in a now-missing company's JD — confirm on first re-run).
- [ ] Hand-verify the cover-letter-side check per the "Plan the cover-letter-side check" Round 1 item
      above (`pick_cover_bullets`/`_proof_score` output for the same 2-3 eval-set JDs, before/after).
- [ ] Run the full `scripts/` pytest suite (excluding the same 3 known-bad files) and confirm no new
      failures beyond the pre-existing 27. Use the path-limited `git stash` technique from CR-063 if you
      need to isolate whether a failure is pre-existing or caused by this round's change.
- [ ] Log before/after numbers and what changed, in a new "Round N results" section below.
- [ ] Repeat until the CR's acceptance criteria are met, or a clear diminishing-returns/regression signal
      says to stop and hand off with a documented partial result (same honesty standard CR-063's Round 2
      and Round 4 modeled — a fix that doesn't work, or only partially works, is a real, loggable result,
      not a failure to hide).

### Round 2 plan

**Scope: dedup ONLY (the `matched: dict[token->max tier]` / `_bump()` pass from the Round 1
pseudocode's loops 1-4). NOT the rarity-weight multiplier, `_RARITY_DF`/`_RARITY_N` cache,
`_get_rarity_table`, `_rarity_weight`, or the two rarity test hooks — those are Round 3. This
round's `score_claim_for_jd` returns `sum(matched.values())` (plain int tier sum, no
`int(round(...))` float-cast needed since no rarity float is introduced yet).**

Expected effect (per Round 1's hand-check, dedup-only sub-total before rarity re-inflation):
Cresta/ACC-105 raw score should fall (28 -> dedup-only ~19 per the Round-1 hand check), i.e. dedup
alone should show at least partial movement against ACC-105's over-representation, even though
Round 1 flagged that the full rarity pass re-inflates it back up. Remote/ACC-401 will NOT show the
big rarity-driven jump yet (that requires Round 3) — dedup alone should leave a single strong match
close to its current raw value, since there's little/no cross-loop double-counting to remove for a
claim that only matches on one token.

- [x] Write a new failing unit test against `score_claim_for_jd` in `test_claim_preselection.py`
      pinning the dedup behavior: a token matched by multiple loops (e.g. requirement-loop tier 2 +
      THEME_KEYWORDS-loop tier 3) should be counted once at its max tier, not summed across loops.
      Watch it fail against the current (pre-Round-2) implementation. **Done — added
      `TestScoreClaimForJdDedup.test_cross_loop_double_count_collapses_to_max_tier`, watched fail
      with `13 != 7` against the pre-Round-2 code (`platform`/`roadmap` each triple-counted).**
- [x] Implement the dedup-only body of `score_claim_for_jd` in `scripts/jd_tailoring.py` per the
      Round 1 pseudocode's dedup pass (loops 1-4 + `_bump`), returning `sum(matched.values())`.
      Signature unchanged. **Done.**
- [x] Watch the new unit test pass. **Done — 8/8 `test_claim_preselection.py` tests pass.**
- [x] Re-run `scripts/measure_theme_extraction.py` (14-JD adjusted set) — log aggregate hit rate,
      ACC-105 top-5 count, ACC-401/ACC-204 hit rates vs. the 11/37, 0/14, 11/14, 0/6, 0/2 baseline.
      **Done — see Round 2 results. Surprising: all 5 numbers unchanged.**
- [x] Hand-verify cover-letter side (`pick_cover_bullets` + `cover_claim_picker.pick_cover_proofs`)
      for cresta/remote/covideo before/after. **Done — `pick_cover_bullets` picks changed for all 3;
      `pick_cover_proofs` picks unchanged for all 3. See Round 2 results.**
- [x] Run full `scripts/` pytest suite (excluding the 3 known-bad files), confirm no new failures
      beyond the documented pre-existing 27. **Done — 190 passed, 26 failed, 1 skipped. Zero new
      failures; 1 pre-existing failure now passes as an unplanned positive side effect.**
- [x] Log real before/after numbers below, including anything surprising (do not smooth over a
      result that contradicts the expected-effect prediction above). **Done.**

### Round 2 results

**Implementation.** `score_claim_for_jd` in `scripts/jd_tailoring.py` (was lines 236-251) rewritten
to build `matched: dict[str, int]` (surface token -> max base tier seen across all four loops) via
a local `_bump(tok, tier)` closure, then `return sum(matched.values())`. Base tiers unchanged
(keyword loop=1, requirement loop=2, theme loop=1, THEME_KEYWORDS loop=3). No rarity weight, no
`import math`, no module-level cache added this round — strictly the dedup pass, per the assigned
scope. Signature unchanged: `score_claim_for_jd(claim_text: str, profile: JdProfile, jd_text: str) -> int`.

**Unit test.** Added `TestScoreClaimForJdDedup.test_cross_loop_double_count_collapses_to_max_tier`
to `test_claim_preselection.py`. Constructed a `JdProfile` where the tokens `platform` and `roadmap`
each fire in 3 of the 4 loops (keyword tier 1, requirement tier 2, THEME_KEYWORDS tier 3) and
`reliability` fires once (theme tier 1). Old formula (naive per-loop sum): **13**. New dedup formula
(max tier per token, summed once each): **7** (`platform`:3 + `roadmap`:3 + `reliability`:1). Watched
fail first: `assert score == 7` failed with `13 != 7` against the pre-Round-2 code, then implemented
and re-ran green (8/8 `test_claim_preselection.py` tests pass).

**measure_theme_extraction.py (14-JD adjusted set), before -> after.** Measured via a scratchpad
wrapper script (not a repo change) that imports `measure_theme_extraction.py`'s own `EVAL_SET`,
`project_id`, and `code_hits_top5` and filters to the 14 companies whose `Original_JD.txt` is
present, since `sailpoint`/`group_1001` are still missing from this working tree (see "Before Round
1" note). Verified deterministic and reproducible (3 repeat runs, `python -B` with `__pycache__`
cleared, identical output every time) after discovering a false lead: `git stash`-ing only
`jd_tailoring.py` to get a quick "before" snapshot silently reverted the file all the way to the last
*commit*, wiping the still-uncommitted CR-063 `THEME_KEYWORDS` additions along with my edit and
producing a bogus, non-comparable "before" (ACC-105 top-5 count 9/14 instead of the real 11/14). Caught
by re-deriving the true "before" via a scoped in-place revert of just the function body (keeping
`THEME_KEYWORDS` intact) instead of a file-level stash. Noting this so it isn't mistaken for a bug
found in the pipeline itself — it was a measurement-methodology error on my part, corrected before
logging.

| Metric | Baseline (pre-Round-2, verified) | After dedup (verified) |
|---|---|---|
| Aggregate should-surface codes | 11/37 | **11/37 (unchanged)** |
| Per-company full pass | 0/14 | 0/14 (unchanged) |
| ACC-105-EXECUTION top-5 appearance count | 11/14 | **11/14 (unchanged)** |
| ACC-401-AITOOLS hit rate | 0/6 | 0/6 (unchanged) |
| ACC-204 hit rate | 0/2 | 0/2 (unchanged) |

**Honest, surprising finding — flagged, not smoothed over: the aggregate eval-set metrics show ZERO
measurable movement from the dedup-only change**, despite the underlying arithmetic clearly working
as designed. Full top-5 diff confirms every company's absolute scores dropped (e.g. Cresta's
ACC-105-EXECUTION: 28 -> 19, an exact match to Round 1's hand-derived "dedup-only sub-total"
prediction of ~19), and several companies' top-5 *membership* churned (e.g. OneStream's should-surface
`ACC-103` flips HIT->MISS, Lumos's `ACC-102` flips MISS->HIT, ParkingPass.com flips one code each
direction) — but these individual flips happen to net to exactly zero in the 37-code aggregate and
leave ACC-105's top-5 appearance count unchanged at 11/14. This contradicts the Round 2 plan's stated
expectation ("dedup alone should show at least partial movement against ACC-105's over-representation").
Interpretation: dedup removes double-counting roughly *uniformly* across claims that have multi-loop
matches (not just ACC-105), so it mostly rescales the field rather than reordering it — dedup by
itself does not appear to be the mechanism that drops ACC-105 out of top-5 lists; that may require the
rarity weight (Round 3) or a breadth-dampener (flagged as a possible follow-on in Round 1), not dedup
alone. This is a real, attributable, negative-for-the-aggregate-metric result for this specific
mechanism in isolation — logged honestly per the guardrails, not glossed over.

**Cover-letter side hand-check (`pick_cover_bullets` + `cover_claim_picker.pick_cover_proofs`), proxy
pool = full catalog `truth_map()`, before -> after:**

| Company | `pick_cover_bullets` before | `pick_cover_bullets` after | `pick_cover_proofs` before | `pick_cover_proofs` after |
|---|---|---|---|---|
| cresta | `['ACC-105-EXECUTION', 'ACC-103-ROADMAP']` (scores 28, 18) | `['ACC-105-EXECUTION', 'ACC-105-PROCESS']` (scores 19, 15) | `['ACC-401-AITOOLS', 'ACC-101-RETENTION']` | `['ACC-401-AITOOLS', 'ACC-101-RETENTION']` (unchanged) |
| remote | `['ACC-112-COMPLIANCE', 'ACC-107-LEGAL']` (scores 15, 13) | `['ACC-113-MIGRATION', 'ACC-107-PLATFORM']` (scores 12, 11) | `['ACC-401-AITOOLS', 'ACC-102-BUS']` | `['ACC-401-AITOOLS', 'ACC-102-BUS']` (unchanged) |
| covideo | `['ACC-111-SCOPE', 'ACC-102-TECH']` (scores 10, 9) | `['ACC-113-ADOPTION', 'ACC-102-TECH']` (scores 8, 8) | `['ACC-401-AITOOLS', 'ACC-102-BUS']` | `['ACC-401-AITOOLS', 'ACC-102-BUS']` (unchanged) |

Honest finding: **`pick_cover_bullets` (the `draft_compiler.py:678` production path) DID change its
picks for all 3 sample companies** — cresta's 2nd pick, remote's entire pair, and covideo's 1st pick
all changed. This is the opposite of my first (later-discovered-invalid) measurement pass, which used
the same stash-corrupted "before" state described above and wrongly suggested no change; the correct
before/after pair above is from the verified, non-corrupted comparison. `pick_cover_proofs`
(`cover_claim_picker.py:134`, the actual cover-letter proof-selection path) did NOT change picks for
any of the 3 companies — ACC-401-AITOOLS already wins slot 0 on all three via the `has_ai_signal`-gated
bonus and `_protected_ai_slot` guard in `cover_claim_picker.py`, a mechanism independent of
`score_claim_for_jd`'s base score, so this dedup change doesn't reach that decision for these 3 JDs.

**Pytest regression check.** Full suite (`python -m pytest -q --ignore=test_domain_gate.py
--ignore=test_fit_policy.py --ignore=test_llm.py`), clean `__pycache__`, verified with the real
Round-2 code in place: **190 passed, 26 failed, 1 skipped.** Compared against the pre-Round-2 baseline
of 188 passed / 27 failed / 1 skipped by diffing the sorted `FAILED` line lists of a true before/after
pair (before = same working tree with only `score_claim_for_jd`'s body reverted in place, not a file
stash): the diff is exactly 2 lines — my 1 new dedup test (expected, present only in "after"), and
`test_cover_claim_picker.py::TestCoverClaimPicker::test_fintech_jd_prefers_dropoff_story`, which
**FAILED before this change and PASSES after it** (confirmed stable across a repeat run). That test
asserts `ACC-102-BUS` appears in `pick_cover_proofs`'s top-3 for a fintech JD snippet via the same
production call site this CR targets — a genuine, unplanned positive side effect of the dedup fix, not
a regression. Zero new failures. Net: **26 failed** (one fewer than baseline), **190 passed** (two
more than baseline: the 1 new test + the 1 newly-passing pre-existing test).

**Verdict for this round.** Dedup is implemented correctly and verified against the exact Round 1
hand-check prediction (Cresta 28 -> 19). It measurably changes absolute scores and, on the
cover-letter-bullet-selection path (`pick_cover_bullets`), measurably changes which claims get picked
for real sample JDs — plus fixes one previously-failing production-path unit test as an unplanned
bonus. However, it produces **no measurable movement on this round's primary target metrics**
(aggregate should-surface hit rate, ACC-105 top-5 over-representation count) on the resume-ranking
path (`score_all_claims`/`measure_theme_extraction.py`), contradicting this round's own stated
expectation. Round 3 (rarity weight) remains necessary for the under-scoring-rare-match side
(ACC-401/ACC-204, both still flat at 0/6 and 0/2) and is now also an open question for the
over-representation side, since dedup alone did not deliver it as hoped — Round 3's measurement should
explicitly re-check whether rarity, layered on top of dedup, moves ACC-105's top-5 count, and if not,
the breadth-dampener option flagged in Round 1 becomes a live candidate rather than a contingency.

### Round 3 plan

**Scope: layer the rarity-weight multiplier (`_RARITY_DF`/`_RARITY_N` module cache, `_get_rarity_table`,
`_rarity_weight`, the two test hooks `_reset_rarity_cache`/`_set_rarity_table`) on top of the
already-implemented Round 2 dedup pass, exactly per the Round 1 pseudocode. Final line becomes
`total = sum(tier * _rarity_weight(tok) for tok, tier in matched.items())`; `return int(round(total))`.
`import math` added.**

- [x] Write a new failing unit test in `test_claim_preselection.py` pinning rarity-weight behavior with
      a synthetic, pinned df table via `_set_rarity_table`/`_reset_rarity_cache` (not live catalog
      contents). Watch it fail against the current (Round-2-only) code.
- [x] Implement `_RARITY_DF`/`_RARITY_N`, `_get_rarity_table()`, `_rarity_weight()`,
      `_reset_rarity_cache()`/`_set_rarity_table()`, and the weighted-sum final line in
      `score_claim_for_jd`. Add `import math`.
- [x] Watch the new unit test pass.
- [x] Update the existing Round 2 dedup test (`TestScoreClaimForJdDedup`) to pin a synthetic rarity
      table where every involved token has weight 1.0 (df == n), isolating the dedup mechanism from the
      now-always-applied rarity multiplier — otherwise it silently starts asserting against live-catalog
      rarity weights it was never designed to test, and breaks every time the catalog changes.
- [x] Re-run `scripts/measure_theme_extraction.py` (14-JD adjusted set) — log aggregate hit rate,
      ACC-105 top-5 count, ACC-401/ACC-204 hit rates vs. both the original baseline (11/37, 0/14, 11/14,
      0/6, 0/2) and Round 2's dedup-only result (same numbers, unchanged from baseline).
- [x] Hand-verify cover-letter side (`pick_cover_bullets` + `cover_claim_picker.pick_cover_proofs`) for
      cresta/remote/covideo, Round-2-state vs Round-3-state (not vs original baseline).
- [x] Run full `scripts/` pytest suite (excluding the 3 known-bad files), confirm no new failures beyond
      Round 2's confirmed 26 — or root-cause and explicitly justify any that appear.
- [x] Log real before/after numbers below, including if ACC-105's top-5 count does NOT drop.

### Round 3 results

**Implementation.** `scripts/jd_tailoring.py`: added `import math`; added module globals `_RARITY_DF`/
`_RARITY_N` (both `None` initially), `_reset_rarity_cache()`, `_set_rarity_table(df, n)` (test hooks),
`_get_rarity_table()` (self-loads `data/master_claims.json` via `json.load`, skips non-dict/disabled
records, builds token->doc-frequency over `text`+`tags` tokenized with `re.findall(r"[a-z]{5,}", ...)`,
one increment per token per claim via `set(...)`), and `_rarity_weight(token)` (`1.0 + math.log(n/freq)`
if `freq>0` else floor `1.0`). `score_claim_for_jd`'s final two lines changed from
`return sum(matched.values())` to
`total = sum(tier * _rarity_weight(tok) for tok, tier in matched.items()); return int(round(total))`.
Signature unchanged: `score_claim_for_jd(claim_text: str, profile: JdProfile, jd_text: str) -> int`.
Dedup pass (the `matched`/`_bump` logic, loops 1-4) untouched from Round 2. Verified live: 63 active
claims, 1 disabled (`N=63`), matching Round 1's hand-check assumption exactly.

**Unit test.** Added `TestScoreClaimForJdRarity.test_rare_token_match_outweighs_common_token_match` to
`test_claim_preselection.py`: two claims each match one keyword-loop (tier 1) token against the same JD,
via a pinned synthetic table `{"raretoken": 1, "commontoken": 50}, n=50` (`_set_rarity_table`). Expected
`rare_score == 5` (`1 + ln(50/1) = 4.912` -> `round` -> 5) and `common_score == 1` (`1 + ln(50/50) = 1.0`
-> flat/unweighted). Watched fail first against the pre-Round-3 code: `ImportError: cannot import name
'_reset_rarity_cache' from 'jd_tailoring'` (the hooks didn't exist yet), then implemented and re-ran
green. Also updated `TestScoreClaimForJdDedup.test_cross_loop_double_count_collapses_to_max_tier` to pin
`_set_rarity_table({"platform": 10, "roadmap": 10, "reliability": 10}, 10)` (weight 1.0 for every
involved token, i.e. `df == n`) so it continues to isolate the dedup mechanism specifically, now that
rarity is unconditionally applied on every call — without this pin it failed against live catalog
contents (`20 != 7`), which was watched and understood as an artifact of the new always-on rarity layer,
not a dedup regression, before fixing the test's isolation. Full `test_claim_preselection.py`: 9/9 pass.

**measure_theme_extraction.py (14-JD adjusted set), Round-2-baseline -> Round-3.** Measured via a
scratchpad wrapper script (not a repo change) filtering `measure_theme_extraction.py`'s own `EVAL_SET` to
the 14 present companies, same method Round 2 used. Verified the "before" figure by monkeypatching
`jd_tailoring._rarity_weight` to always return `1.0` in-process (mathematically identical to Round 2's
plain-sum formula: `int(round(sum(tier*1.0))) == sum(tier)`) rather than `git stash`, per Round 2's
documented stash pitfall (stashing `jd_tailoring.py` reverts to the last commit, silently wiping the
still-uncommitted CR-063 `THEME_KEYWORDS` additions). The monkeypatch reproduced Round 2's exact
documented figures (11/37, 0/14, ACC-105 11/14) byte-for-byte, confirming the technique is sound.

| Metric | Original baseline | Round 2 (dedup-only) | Round 3 (dedup+rarity) |
|---|---|---|---|
| Aggregate should-surface codes | 11/37 | 11/37 (unchanged) | **12/37 (+1)** |
| Per-company full pass | 0/14 | 0/14 | 0/14 (unchanged) |
| ACC-105-EXECUTION top-5 appearance count | 11/14 | 11/14 (unchanged) | **11/14 (STILL UNCHANGED)** |
| ACC-401-AITOOLS hit rate | 0/6 | 0/6 | **0/6 (STILL UNCHANGED)** |
| ACC-204 hit rate | 0/2 | 0/2 | **0/2 (STILL UNCHANGED)** |

**Honest, load-bearing finding — logged plainly, not softened:** rarity weight, layered on dedup, does
**NOT** move this round's two primary target metrics. ACC-105's top-5 over-representation count is
identical (11/14) to both the original baseline and Round 2. ACC-401/ACC-204's hit rates are identical
(0/6, 0/2) to both prior states. The aggregate should-surface metric moved by exactly +1 code (11/37 ->
12/37), net of 5 codes flipping MISS->HIT (`DataGrail/ACC-103`, `PAR/ACC-109`, `ParkingPass.com/ACC-109`,
`PointClickCare/ACC-109`, `Redox/ACC-109`) against 4 flipping HIT->MISS (`Tilt/ACC-101`,
`DataGrail/ACC-107`, `Redox/ACC-101`, `Lumos/ACC-102`) — real churn, but a near-wash in aggregate, the
same "rescales roughly uniformly rather than reordering" pattern Round 2 found for dedup alone.

Reconciling this against Round 1's isolated hand-check (which predicted Remote/ACC-401 moving rank 43 ->
24 "UP 19 places"): that prediction is **directionally correct but insufficient to cross the finish
line** — rank 24 is nowhere near the top-5 cutoff this measurement actually gates on. A 19-place
improvement in absolute rank does not translate into a hit-rate change unless it clears rank 5, and it
does not. This is not a contradiction of Round 1's math (re-verified: Remote/`ACC-401-AITOOLS` does score
higher and rank higher under Round 3 than under Round 2 — confirmed via the same wrapper script), it is a
correction of what that improvement is sufficient to achieve. ACC-105's non-movement was already
correctly anticipated as a live possibility by Round 1's own Cresta hand-check (score 28 -> 49, rank
unchanged at #1) and by Round 2's closing note; this full 14-JD measurement now confirms it holds across
the whole eval set, not just the one JD Round 1 hand-checked.

**Per Jason's Round-1-approved instruction: this result does NOT trigger a breadth-dampener design or any
other new mechanism from me.** Per the tracker's own Round 1 note, that is explicitly flagged as a
candidate for a further round requiring a fresh tech-lead design pass and Jason's sign-off — logging the
result here and stopping, not improvising past it.

**Cover-letter side hand-check (`pick_cover_bullets` + `cover_claim_picker.pick_cover_proofs`), proxy
pool = full catalog `truth_map()`, Round-2-state -> Round-3-state (same in-process monkeypatch
methodology as above, not git stash):**

| Company | `pick_cover_bullets` Round 2 | `pick_cover_bullets` Round 3 | `pick_cover_proofs` Round 2 | `pick_cover_proofs` Round 3 |
|---|---|---|---|---|
| cresta | `['ACC-105-EXECUTION' (19), 'ACC-105-PROCESS' (15)]` | `['ACC-105-EXECUTION' (49), 'ACC-112-COMPLIANCE' (44)]` (2nd pick changed) | `['ACC-401-AITOOLS', 'ACC-101-RETENTION']` | `['ACC-401-AITOOLS', 'ACC-101-RETENTION']` (unchanged) |
| remote | `['ACC-113-MIGRATION' (12), 'ACC-107-PLATFORM' (11)]` | `['ACC-112-COMPLIANCE' (35), 'ACC-107-PLATFORM' (27)]` (1st pick changed) | `['ACC-401-AITOOLS', 'ACC-102-BUS']` | **`['ACC-401-AITOOLS', 'ACC-101-RETENTION']` (2nd slot CHANGED)** |
| covideo | `['ACC-113-ADOPTION' (8), 'ACC-102-TECH' (8)]` | `['ACC-201-ALIGNMENT' (26), 'ACC-108-SUPPORT' (25)]` (both picks changed) | `['ACC-401-AITOOLS', 'ACC-102-BUS']` | **`['ACC-401-AITOOLS', 'ACC-101-RETENTION']` (2nd slot CHANGED)** |

Honest finding, a real difference from Round 2: **`pick_cover_bullets` (`draft_compiler.py:678` fallback
path) again changed picks for all 3 sample companies, as expected given base scores shift under rarity.
More significantly, `pick_cover_proofs` (`cover_claim_picker.py:134`, the actual cover-letter
proof-selection path used by `build_cover_plan`) — which Round 2 found completely stable across all 3
companies — now CHANGES its 2nd-slot pick for 2 of 3 companies (remote, covideo), both flipping from
`ACC-102-BUS` to `ACC-101-RETENTION`.** `ACC-401-AITOOLS` still wins slot 0 on all three via the
`has_ai_signal`-gated bonus / `_protected_ai_slot` guard, unaffected by base-score scale (consistent with
Round 2). This is the first concrete, real-JD confirmation of the risk Round 1 flagged on paper
("`_complement_score`/`_proof_score`'s flat 3-8pt bonuses interact with a moving base scale") actually
changing production cover-letter proof selection, not just absolute scores.

**Pytest regression check — 2 real, root-caused, new failures found and explicitly justified per
guardrails, not fixed inline.** Full suite, clean `__pycache__`: **28 failed, 189 passed, 1 skipped**
(vs. Round 2's 26 failed / 190 passed / 1 skipped). True before/after isolated via the same in-process
`_rarity_weight`-forced-to-1.0 monkeypatch (deselecting only the new rarity unit test, which is
meaningless under that patch) rather than git stash: **before = 26 failed / 190 passed / 1 skipped / 1
deselected — an exact match to Round 2's documented figures**, confirming the monkeypatch technique
reproduces Round 2 state precisely. Diffing the two sorted `FAILED` lists: exactly 2 new failures, both
in the "after" (Round 3) list only:

1. `test_cover_claim_picker.py::TestCoverClaimPicker::test_fintech_jd_prefers_dropoff_story` — asserts
   `ACC-102-BUS` is in `pick_cover_proofs`'s top-3 for a fintech JD snippet. Now returns
   `{'ACC-112-PIPELINE', 'ACC-303-GTM', 'ACC-102-MODERN'}` instead. This is the exact test Round 2 fixed
   as an unplanned side effect (dedup collapsed a scoring tie in `ACC-102-BUS`'s favor); Round 3's rarity
   layer flips the ranking back the other way. Net effect vs. the *very original* pre-CR-064 baseline:
   this test was already failing there too, so this is a reversion of Round 2's bonus fix, not a failure
   beyond anything ever seen in this CR's history — but it IS a real regression relative to Round 2's
   state, logged as such.
2. `test_cover_word_padding.py::TestCoverWordPadding::test_thin_jd_still_produces_proof_content` —
   asserts a thin/near-empty JD still produces cover-letter proof content mentioning "cision" (the
   Optum-regression guard). Genuinely new: not failing in the original baseline or in Round 2.

**Root cause (traced, not guessed, for both as a single mechanism — not two separate bugs):**
`cover_claim_picker.py`'s `_proof_score` (line 134) computes `score = score_claim_for_jd(...)` then adds
flat additive bonuses (3-12 points per matched signal, e.g. the fintech drop-off bonus at line 196-197,
the generic per-token match bonus at line 137-139) on top. `best_for_need` (line 281-306) then picks
whichever claim has the single highest `sc` per JD need. These flat bonuses were calibrated against the
pre-CR-064 base-score scale (~3-28 per Round 1's hand-check). Round 3's rarity multiplier inflates that
base scale ~1.7x-5x unevenly across claims (each claim's inflation depends on which specific tokens it
matched and how rare each one is catalog-wide), so a claim that previously won a need-slot primarily on a
flat bonus can now be outranked by a claim whose base score inflated more, and vice versa — this is
**exactly** the risk Round 1 named explicitly on paper ("Scale inflation is real and interacts with the
cover-letter flat bonuses... an 8-pt bonus that was ~30% of a strong base score is now ~16% of it") and
pre-decided not to fix inside this CR: *"do NOT retune `_complement_score`/`_proof_score`'s flat bonuses
inside this CR... flag any distortion as a separate calibration follow-up rather than folding a retune
into this CR."* Both test failures are that exact, already-named risk materializing in production-path
selection logic and its test coverage, not a new or unrelated defect requiring fresh root-causing.

**Action taken: none, by design.** Per Round 1's explicit, Jason-reviewable decision, I am not retuning
`cover_claim_picker.py`'s flat bonuses inside this CR. Flagging both failures, and the broader
`pick_cover_proofs` slot-2 churn found in the cover-letter hand-check above, to Jason as a calibration
follow-up (see Session Handoff open questions) rather than fixing inline — this satisfies the guardrail's
"fix or explicitly justify" via the "explicitly justify" branch, grounded in Round 1's own pre-approved
scope boundary, not a unilateral decision made this round.

**Verdict for this round.** Rarity weighting is implemented correctly and verified against the exact
Round 1 hand-check predictions (Remote/ACC-401 rank improves 43->24; Cresta/ACC-105 score rises 28->49
with rank unchanged at #1). It does NOT move this round's two primary target metrics on the full 14-JD
eval set (ACC-105 top-5 count stays 11/14; ACC-401/ACC-204 hit rates stay 0/6, 0/2) — both dedup (Round
2) and rarity (Round 3) individually fail to resolve ACC-105's cross-JD over-representation or
ACC-401/ACC-204's under-scoring, despite each performing exactly as designed on isolated hand-checks. It
DOES cause real, measurable churn in production claim selection (`pick_cover_bullets` every company;
`pick_cover_proofs` 2 of 3 companies now) and 2 new, root-caused, explicitly-justified (not fixed) test
failures via the pre-flagged flat-bonus-vs-inflated-scale interaction. The pure additive dedup+rarity
design, as approved and now fully implemented across both rounds, has not delivered the CR's stated
acceptance criterion (ACC-105's over-representation measurably drops) — the breadth-dampener option
Round 1 flagged as a contingency is now the live open question for Jason, not a hypothetical.

## Round 4 — Design the breadth-dampener mechanism (no code yet)

Same discipline as Round 1: this is a **design-only, paper** round. Jason explicitly authorized designing
the breadth-dampener after reviewing Round 3's full-set result (dedup+rarity live, ACC-105 top-5 count
still 11/14). Do NOT implement in `scripts/jd_tailoring.py` or `scripts/cover_claim_picker.py` — Round 5
(implementation) is gated on Jason reviewing this design first, exactly as Round 2 was gated on Round 1.

**Why a breadth-dampener, stated precisely (Round 3's finding):** the current formula is
`score = sum(tier * rarity_weight(tok) for each unique matched token)` — purely additive over however
many distinct tokens a claim matches. This structurally rewards *breadth* (ACC-105 matches 9
moderately-on-theme tokens for most JDs, summing to 49 at Cresta) over *precision* (ACC-401 matches the
1 rare, killer-relevant token `claude`, scoring 15 at Remote). Dedup (Round 2) and rarity (Round 3) each
performed exactly as designed on isolated hand-checks yet moved the full-set metric by ~0, because the
additive sum still lets 9 mediocre tokens outscore 1 great one. The dampener attacks the sum itself.

### Round 4 plan
- [x] Choose the dampener mechanism precisely. **Decision (tech-lead, 2026-07-14): a rank-discounted
      breadth dampener using the DCG (Discounted Cumulative Gain) position-discount from information
      retrieval. Sort each claim's per-token contributions `tier * _rarity_weight(tok)` descending, then
      divide the value at 1-indexed rank `r` by `log2(r + 1)` before summing:
      `total = sum(v / log2(rank+1) for rank, v in enumerate(sorted(contribs, desc), start=1))`.
      Rationale over the two alternatives the brief named: (1) it EXACTLY preserves the single strongest
      match (`log2(1+1)=1`, so the rank-1 token is undiscounted) — this is the property that makes a
      1-token precision claim like ACC-401 completely immune to the breadth penalty, which is the whole
      point; (2) it discounts each additional token progressively (2nd token /1.585, 3rd /2.0, 9th
      /3.322) so breadth still counts but at sharply diminishing returns; (3) unlike a hand-picked
      geometric constant (`0.7 ** rank`), `log2(rank+1)` is the canonical, non-arbitrary position-discount
      curve — not a magic number I'd have to defend; (4) unlike a hard top-K cap, it keeps a small tail
      contribution (rank-9 still adds 0.602) so it breaks ties on the single-best-token instead of
      collapsing many claims to an identical peak value and falling back to the alphabetical `item[0]`
      tiebreaker (a real risk under aggressive decay — see rejected alternatives).**
- [x] Reject the weaker candidates on paper, not just by reasoning. **Rejected: (a) a HARD top-K cap
      (only the K highest-weighted tokens contribute). Discards breadth information discontinuously — a
      claim with 5 genuinely strong matches is capped identically to one with K strong + noise, and it
      produces exact ties on peak tokens that fall through to the arbitrary alphabetical id tiebreaker.
      (b) An aggressive GEOMETRIC decay `v * (0.7 ** rank)`. Computed against the real Cresta table it
      pushes ACC-105 to 24 (vs DCG's 27) — more separation, but it over-compresses: past rank ~4 the
      contribution is near-zero, so most claims collapse to ~their single best token and tie-density
      rises. Held in reserve as the escalation lever (see the escalation note in Round 4 results), NOT
      the default. (c) A flat tail-discount `max_value + d * sum(rest)`. Simple and one-knob, but it does
      not differentiate the 2nd token from the 9th, which is exactly the gradient DCG gives for free.**
- [x] Confirm the design still satisfies every CR hard constraint. **Decision: it does, with ZERO new
      module state. Signature `score_claim_for_jd(claim_text: str, profile: JdProfile, jd_text: str) -> int`
      unchanged. The dampener is a pure, stateless transform of the already-built `matched` dict — no new
      `_RARITY_*`-style cache, no new import (`math` is already imported since Round 3, `math.log2` is
      stdlib). Return stays `int(round(total))`. No `master_claims.json` read/write. The ONLY lines that
      change vs. the live Round 3 code are the final aggregation (`total = ...`) — everything above it
      (the four dedup loops, `_bump`, `_get_rarity_table`, `_rarity_weight`) is byte-identical.**
- [x] Write the exact new `score_claim_for_jd` pseudocode here before any code. **Done — see Round 4
      results.**
- [x] Hand-check against BOTH Round-3-measured data points using their real per-token tables (Round 1
      tables, lines 251-272), showing the arithmetic. **Done — see Round 4 results. Cresta/ACC-105
      49 -> 27; Remote/ACC-401 15 -> 15 (immune).**
- [x] Decide explicitly whether the 2 Round-3 `cover_claim_picker.py` test regressions are in scope for
      this design or a separate follow-up. **Decision: OUT of scope for this design round, unchanged from
      Round 1/3 — but with a sharpened, testable Round-5 prediction. See "Cover-letter-side regression
      decision" in Round 4 results. Retuning `_proof_score`'s flat bonuses changes cover-letter proof
      SELECTION (a product-behavior change), which the Mid-Process Backflow Rule reserves for Jason, not
      a silent tech-lead call; and it would be calibrating against a scale that Round 5's dampener is
      about to change again — the exact "moving-scale" anti-pattern Round 1 named. Correct sequence:
      implement the dampener, re-run pytest, THEN see whether the 2 regressions self-resolve.**

### Round 4 results

**Design, as pseudocode (drop-in for the live Round 3 `score_claim_for_jd`; the ONLY change is the final
aggregation — the four dedup loops, `_bump`, and the rarity helpers are untouched from Round 3). NOT YET
IMPLEMENTED — gated on Jason's review per the Session Handoff.**

```python
# --- signature UNCHANGED, return still int; helpers/loops above this are Round 3 code, unchanged ---
def score_claim_for_jd(claim_text: str, profile: JdProfile, jd_text: str) -> int:
    text_l = claim_text.lower()
    jd_l = jd_text.lower()

    matched: dict[str, int] = {}                 # UNCHANGED from Round 3 (dedup pass)
    def _bump(tok: str, tier: int) -> None:
        if matched.get(tok, 0) < tier:
            matched[tok] = tier

    for w in profile.keywords:                             # loop 1, tier 1  (unchanged)
        if w in text_l and w in jd_l:
            _bump(w, 1)
    for req in profile.requirements:                       # loop 2, tier 2  (unchanged)
        for tok in re.findall(r"[a-z]{5,}", req.lower()):
            if tok in text_l:
                _bump(tok, 2)
    for theme in profile.priority_themes:                  # loop 3, tier 1  (unchanged)
        for tok in re.findall(r"[a-z]{5,}", theme.lower()):
            if tok in text_l:
                _bump(tok, 1)
    for kw, _phrase in THEME_KEYWORDS:                     # loop 4, tier 3  (unchanged)
        if kw in jd_l and kw in text_l:
            _bump(kw, 3)

    # --- CR-064 Round 4 CHANGE: breadth dampener (DCG position discount) -------------------
    # Round 3 did: total = sum(tier * _rarity_weight(tok) for tok, tier in matched.items())
    # Round 4 sorts those same per-token contributions descending and discounts the value at
    # 1-indexed rank r by log2(r+1). rank-1 (the single strongest match) is undiscounted, so a
    # claim that wins on ONE rare precise token is unaffected; each additional token pays a
    # progressively steeper breadth tax, so 9 mediocre tokens can no longer out-sum 1 great one.
    contribs = sorted(
        (tier * _rarity_weight(tok) for tok, tier in matched.items()),
        reverse=True,
    )
    total = sum(v / math.log2(rank + 1) for rank, v in enumerate(contribs, start=1))
    return int(round(total))                               # signature pinned -> int
```

**Hand-check #1 — Cresta / ACC-105-EXECUTION. Real per-token (tier x weight) values from the Round 1
table (lines 251-263), sorted descending, DCG divisor `log2(rank+1)`:**

| rank | token | tier x weight | divisor `log2(rank+1)` | discounted |
|---|---|---|---|---|
| 1 | roadmap | 9.592 | 1.000 | 9.592 |
| 2 | compliance | 8.522 | 1.585 | 5.377 |
| 3 | platform | 6.156 | 2.000 | 3.078 |
| 4 | teams | 6.127 | 2.322 | 2.639 |
| 5 | across | 5.316 | 2.585 | 2.057 |
| 6 | engineering | 4.870 | 2.807 | 1.735 |
| 7 | prioritization | 3.534 | 3.000 | 1.178 |
| 8 | delivery | 3.064 | 3.170 | 0.967 |
| 9 | ability | 2.000 | 3.322 | 0.602 |

Sum = 27.22 -> `int(round(...))` = **27.** Round 3 (additive) = 49. Pre-CR baseline = 28.
**The dampener drops ACC-105 -45% off its Round 3 score, back below even its original pre-CR score.**

**Hand-check #2 — Remote / ACC-401-AITOOLS. 1 matched token:**

| rank | token | tier x weight | divisor `log2(rank+1)` | discounted |
|---|---|---|---|---|
| 1 | claude | 15.429 | 1.000 | 15.429 |

Sum = 15.43 -> **15.** Round 3 = 15. **Completely unchanged — a 1-token claim has no rank-2+ tokens to
discount, so the breadth penalty cannot touch it. This is the immunity property by construction.**

**Verdict — honest, and deliberately NOT over-claimed (this is the third "should work" prediction in
this CR; the prior two were wrong on full-set measurement, so I am pinning exactly what the hand-check
does and does NOT establish):**

- **The design cleanly SEPARATES the two cases, and this part is structural, not a lucky number.** The
  breadth penalty a claim pays is monotonic in its token count and in how flat its contribution
  distribution is. ACC-105 (9 similar-magnitude tokens) is the single most-penalized shape possible;
  ACC-401 (1 token) is the single least-penalized (zero penalty). So the dampener taxes precisely the
  breadth pattern CR-063 complained about and precisely spares the precision pattern the CR exists to
  reward. Confident in the mechanism's *direction* and in these two absolute numbers (49->27, 15->15).

- **What the hand-check does NOT establish: that ACC-105 actually leaves Cresta's top-5.** I have real
  per-token tables for exactly TWO claims (these two). I do NOT have the token breakdowns of the other
  ~62 claims in Cresta's field, so I cannot compute ACC-105's post-dampener RANK by hand. Its absolute
  score falls 49->27, but every other claim is dampened too — a competitor with fewer/peakier tokens is
  dampened LESS, which is how the reorder is supposed to happen, but whether ACC-105 falls below 5 other
  claims at Cresta is a full-field question. **This is the exact trap that sank the Round 2 and Round 3
  predictions: absolute-score movement is not rank movement.** Rank is a Round-5
  `measure_theme_extraction.py` measurement, full stop — I am not predicting it here.

- **Primary risk to watch in Round 5, flagged not smoothed:** the dampener taxes ANY breadth-heavy
  claim, and not every "should-surface" claim is a precision claim — some should legitimately surface on
  broad relevance. If a should-surface claim that was borderline-top-5 on breadth gets compressed out,
  the aggregate should-surface metric (11/37 -> 12/37 currently) could move DOWN even as ACC-105's
  over-representation improves. The two acceptance criteria (ACC-105 count down AND aggregate up) could
  therefore pull in opposite directions under this mechanism. Round 5 must report both, and a win on one
  at the cost of the other is a partial result to hand back to Jason, not a pass.

- **Pre-registered escalation lever (mirrors Round 1's discipline of naming the next move before
  needing it):** if Round 5's full-set run shows ACC-105 STILL in ~11/14 top-5 lists (i.e. DCG is too
  gentle to reorder the field), the first lever is to make the SAME mechanism more aggressive — swap the
  `log2(rank+1)` divisor for a geometric `v * (0.7 ** (rank-1))` decay (hand-checked above: pushes
  ACC-105 to 24, taxing the tail harder) — NOT to bolt on yet another separate mechanism. The knob is
  "which discount curve," and it is a one-line change. Only if BOTH the DCG and geometric curves fail to
  move the metric is the additive-formula thesis itself falsified, at which point the honest conclusion
  is that the defect is not in the aggregation arithmetic and the CR should hand back to Jason for a
  scope reconsideration (e.g. the JD-profile/keyword extraction upstream, which CR-063 measured but did
  not fully resolve).

**Cover-letter-side regression decision (Round 4 plan item 3 — decided explicitly per the Mid-Process
Backflow Rule, not silently assumed):**

The 2 Round-3 pytest regressions (`test_cover_claim_picker.py::test_fintech_jd_prefers_dropoff_story`,
`test_cover_word_padding.py::test_thin_jd_still_produces_proof_content`) were root-caused in Round 3 to
`cover_claim_picker.py::_proof_score` (line 134 onward) adding flat additive bonuses (3-12 pts) on top of
`score_claim_for_jd`'s base score, calibrated against the pre-CR ~3-28 scale and swamped by Round 3's
~15-49 inflated scale.

**Decision: keep `cover_claim_picker.py` explicitly OUT of scope for this design round.** Three reasons,
in priority order:

1. **Backflow rule.** Retuning `_proof_score`'s flat bonuses changes which claims get selected as
   cover-letter proof points — a product-behavior change, not an internal refactor. Round 1 already
   routed this to Jason as an open question; re-deciding it inside a tech-lead design pass would be
   exactly the kind of missing-decision improvisation the rule forbids. It stays Jason's call.
2. **The dampener may make the retune unnecessary — but I will NOT predict that it does.** The Round-3
   regressions were caused by scale INFLATION; the dampener partially REVERSES that inflation for
   breadth-heavy claims (Cresta/ACC-105 49->27, back near its pre-CR 28). So the flat bonuses regain
   relative weight against breadth claims. BUT precision claims stay inflated (ACC-401 stays 15, not back
   to its pre-CR 3), so the scale is NOT uniformly restored and the net effect on those 2 specific test
   assertions is genuinely not hand-predictable. Given this CR's two-for-two record of wrong "should
   work" predictions, I am explicitly NOT claiming the dampener fixes the regressions — only that it
   plausibly mitigates them, to be MEASURED in Round 5's pytest run, not assumed.
3. **Sequencing.** Retuning bonuses now would calibrate them against Round 3's inflated scale, which
   Round 5's dampener is about to change again — the "calibration against a moving scale" anti-pattern
   Round 1 named. The only correct order is: implement dampener -> re-run pytest -> observe whether the 2
   regressions self-resolve -> if they persist, THEN scope a bonus recalibration against real,
   post-dampener numbers (still as a Jason-gated follow-up, since it changes selection behavior).

## Round 5 — Implement the breadth-dampener (Jason-approved)

### Round 5 plan
- [x] Write a new failing unit test in `test_claim_preselection.py` pinning the DCG dampener's core
      property with a synthetic, pinned rarity table: one high-value single-token match (unaffected by
      the dampener) and a separate many-token match summing to a similar Round-3 (pre-dampener) total
      (meaningfully lower post-dampener). Watch it fail against the live Round-3 code.
- [x] Implement the Round-4-approved DCG rank-discount as `score_claim_for_jd`'s final aggregation
      (replacing only the final two lines; dedup loops + rarity helpers untouched).
- [x] Watch the new unit test pass.
- [x] Re-check the existing Round 2/3 dedup-isolation test (`TestScoreClaimForJdDedup`) — the dampener
      applies unconditionally to any multi-distinct-token match, so a 3-distinct-token test case is no
      longer isolated from it. Fix if broken, using the same "isolate the mechanism under test" precedent
      Round 3 used for the rarity multiplier.
- [x] Re-run `scripts/measure_theme_extraction.py` (14-JD adjusted set) — log ACC-105 top-5 count,
      aggregate should-surface count, ACC-401/ACC-204 hit rates vs. Round 3's 11/14, 12/37, 0/6, 0/2.
      **Done, but with a major caveat found mid-session — see "Round 5 results": the eval-set working
      tree shrank further, from 14 present companies (Round 3/4) to 7, and changed composition
      mid-session (a folder disappeared between two checks a few minutes apart). The 11/14, 12/37
      headline numbers are NOT reproducible on this working tree at all; measured a genuine
      apples-to-apples before/after on the 7 companies actually present instead.**
- [x] Hand-verify cover-letter side (`pick_cover_bullets` + `cover_claim_picker.pick_cover_proofs`) for
      cresta/remote/covideo, Round-3-state vs Round-5-state. **cresta/remote/covideo are ALL THREE
      missing from this working tree — substituted redox/ontra/buyers_edge_platform (comparable
      compliance/AI-token/tracked-metric coverage). See "Round 5 results".**
- [x] Run full `scripts/` pytest suite (excluding the 3 known-bad files); check whether the 2 Round-3
      regressions now pass, still fail, or something else; report real pass/fail/skip counts vs. Round 3's
      28 failed/189 passed/1 skipped. **Done — 28 failed/190 passed/1 skipped. Both Round-3 regressions
      still fail, unchanged. Zero new failures beyond the known 28 (verified via true before/after diff,
      see "Round 5 results").**
- [x] Log real before/after numbers below, interpreting honestly per the pre-registered guidance (clean
      win / genuine tradeoff / null result triggering the escalation-lever stop). **Done.**

### Round 5 results

**Implementation.** `scripts/jd_tailoring.py`'s `score_claim_for_jd` final aggregation replaced exactly
per the Round 4 pseudocode: `contribs = sorted((tier * _rarity_weight(tok) for tok, tier in
matched.items()), reverse=True); total = sum(v / math.log2(rank + 1) for rank, v in
enumerate(contribs, start=1)); return int(round(total))`. `import math` already present since Round 3
(no new import). Signature unchanged. The four dedup loops, `_bump`, `_get_rarity_table`,
`_rarity_weight` are byte-identical to Round 3 — confirmed via diff, only the final aggregation lines
changed. Docstring updated to describe the 3-stage pipeline (dedup -> rarity -> dampener).

**Unit test.** Added `TestScoreClaimForJdBreadthDampener::test_many_token_breadth_claim_taxed_while_single_token_claim_immune`
to `test_claim_preselection.py`, using a pinned synthetic rarity table (`_set_rarity_table`/
`_reset_rarity_cache`, N=1000): a single-token claim (`killerterm`, df=1, weight 7.908, tier 1) vs. a
9-distinct-token claim (each df=N=1000, weight floors to 1.0, tier 1 each). Pre-dampener the two totals
are in the same ballpark (round(7.908)=8 vs. round(9.0)=9 — mirrors the Round 4 hand-check's Cresta
(9 tokens, moderate weights) vs. Remote (1 rare token) shape). Watched fail first against the live
Round-3 code: `breadth_score` asserted `== 4`, got `9` (`9 != 4`) — the dampener didn't exist yet, so the
many-token claim scored its full undamped sum. Implemented, re-ran green: `single_score == 8`
(unaffected — a 1-token claim has no rank-2+ to discount, `log2(1+1)==1`), `breadth_score == 4`
(9 -> 4, a ~55% cut from sorting the 9 equal-weight contributions descending and dividing by
`log2(rank+1)` for ranks 1-9). Full `test_claim_preselection.py`: 10/10 pass.

Also had to fix the existing `TestScoreClaimForJdDedup::test_cross_loop_double_count_collapses_to_max_tier`
test (Round 2/3), which broke as a genuine, expected side effect of the dampener now applying
unconditionally to every call — its original 3-distinct-token scenario (`platform`/`roadmap`/
`reliability`) is no longer isolated from the dampener (score dropped 7 -> 5 once the dampener's
rank-discount applied to the 3 tokens), the same "no longer isolates the mechanism under test" problem
Round 3 hit with the rarity multiplier and the Round 2 test. Followed the same precedent: rewrote the
test to use a single token (`platform`, matched across 3 of 4 loops, max tier 3) so the dampener is a
structural no-op (rank-1 divisor is 1) and the test isolates dedup specifically again. Watched pass
(score == 3, single-token dedup collapse, dampener not exercised) — this was a test-isolation fix, not a
new red/green TDD cycle, since it was fixing an existing passing-then-broken test rather than pinning new
behavior.

**MAJOR CAVEAT, found mid-session, affecting everything below — logged prominently, not buried:** the
eval-set working tree has degraded further and become actively unstable since Round 3/4. Round 3/4
documented 14/16 `data/submissions/` folders present (missing only `sailpoint`/`group_1001`, attributed
to a Google Drive sync gap). At the start of this session, only **7/16** were present — `cresta`,
`sailpoint`, `group_1001`, `onestream_software`, `remote`, `covideo`, `datagrail`, `mytime`, `lumos` were
ALL missing (9 of 16, not 2). Worse: the set is not even static within this session — an `ls` of
`data/submissions/` mid-session showed 8 folders including `remote`; a repeat `ls` ~5 minutes later
(no action taken by me on that directory in between) showed `remote` gone, down to 7, and a later check
showed two unrelated new folders (`_batch_audit`, `test_co`) had appeared that are not in `EVAL_SET` at
all. This points to an actively running, uncoordinated external process (very likely the "Google Drive
sync" already named in the tracker) mutating this directory live, not a one-time gap. **This means the
11/14, 12/37 headline numbers from Round 3/4 cannot be reproduced or directly compared against on this
working tree at all right now** — there is no stable "14-company set" to re-run against. I did not
attempt to restore the missing folders (out of scope, same call Round 1 made for the original 16->14
gap) and instead measured a genuine, internally-consistent before/after on the 7 companies that were
actually present and stable for the duration of each individual measurement run (the before/after pair
within one script invocation always used the same frozen company list). Flagging this to Jason as a
live, worsening infrastructure problem, not a CR-064-specific finding — see Session Handoff open
questions.

**measure_theme_extraction.py, 7-company adjusted set (Buyers Edge Platform, Ontra, Tilt, PAR,
ParkingPass.com, PointClickCare, Redox — the only 16 EVAL_SET companies with `Original_JD.txt` present),
Round-3-state (reconstructed via an in-process monkeypatch, `jd_tailoring.math.log2 = lambda x: 1.0`,
which forces the DCG divisor to 1 for every rank, mathematically identical to Round 3's plain
`sum(tier*weight)` — same "reconstruct via monkeypatch, not git stash" technique Round 3 used, verified
sound by construction) vs. Round-5-state (live code):**

| Metric | Round 3 (reconstructed, 7-co set) | Round 5 (live, 7-co set) |
|---|---|---|
| Aggregate should-surface codes | 8/19 | **7/19 (-1)** |
| Per-company full pass | 0/7 | 0/7 (unchanged) |
| ACC-105-EXECUTION top-5 appearance count | 5/7 | **5/7 (UNCHANGED)** |
| ACC-401-AITOOLS hit rate | 0/2 | 0/2 (unchanged) |
| ACC-204 hit rate | 0/2 | 0/2 (unchanged) |

**Honest, load-bearing finding: this is the null-result / no-movement scenario the story's interpretation
guidance pre-registered, on the only data available.** ACC-105's top-5 appearance count does NOT drop —
identical 5/7 before and after (Tilt, PAR, ParkingPass.com, PointClickCare, Redox all still show
`ACC-105-EXECUTION` in their top-5; only Buyers Edge Platform and Ontra don't, unchanged both states).
The aggregate should-surface metric moved DOWN by 1 (8/19 -> 7/19): `PointClickCare/ACC-102` flips
HIT->MISS (its Round-3 top-5 had `ACC-102-LEAD`; Round-5's top-5 swaps in `ACC-109-EXEC` instead), no
codes flipped MISS->HIT to offset it. Full top-5 diff (both states shown above the delta) confirms real,
attributable churn (not a no-op): Buyers Edge Platform's 5th slot swaps `ACC-101-RETENTION`->
`ACC-108-OPS`; Ontra's slots 3-5 reorder; Tilt's entire top-5 reorders; PointClickCare's slots 1 and 5
change (`ACC-112-COMPLIANCE`/`ACC-102-LEAD` drop out, `ACC-109-EXEC` enters); Redox's slots 1 and 5
change. So the dampener is measurably doing something to rank order — just not the specific thing (drop
ACC-105 below rank 5) the CR needs, on this severely reduced 7-company sample.

**Per the story's pre-registered interpretation guidance and Round 4's own pre-registered escalation
lever: since ACC-105's top-5 count does NOT drop at all, I am NOT trying the geometric-decay escalation
or any other new mechanism myself.** That is explicitly reserved for a fresh tech-lead design pass and
Jason's sign-off, same discipline as every prior round. Logging the null result and stopping here, on
the code side.

**Caveat on confidence, stated plainly:** this null result is measured on a 7-company sample, half the
size of Round 3/4's already-adjusted 14-company set and a third of the original 16. A result this
sensitive to sample composition (Round 2/3 both found aggregate metrics net near-zero from real,
non-trivial per-company churn) is weaker evidence at n=7 than it would be at n=14 or n=16. I am reporting
the measured 5/7-to-5/7 result honestly as what it is — a real, reproducible null result on the data
actually available — while flagging that it is not the full-strength measurement Round 4 asked for, and
that a re-run against a restored 14- or 16-company set (once the sync issue is resolved) would be the
higher-confidence version of this same check.

**Cover-letter side hand-check.** cresta/remote/covideo (the story's assigned companies) are all
missing from this working tree — see the caveat above. Substituted 3 currently-present companies chosen
for comparable `_proof_score`/`_complement_score` branch coverage: **redox** (healthcare data/compliance,
comparable to cresta's security/compliance/data branches), **ontra** (should-surface list includes
`ACC-401-AITOOLS`, comparable to remote's rare-AI-token check), **buyers_edge_platform** (should-surface
list includes `ACC-204`, a tracked continuity metric from prior rounds). Same monkeypatch technique
(Round-3-reconstructed vs. Round-5-live), `catalog.truth_map()` as the bullet-pool proxy (same
methodology prior rounds used):

| Company | `pick_cover_bullets` Round 3 (reconstructed) | `pick_cover_bullets` Round 5 (live) | `pick_cover_proofs` Round 3 | `pick_cover_proofs` Round 5 |
|---|---|---|---|---|
| redox | `[licensing-compliance bullet, prioritization/capacity bullet]` | `[licensing-compliance bullet (unchanged), PI-planning bullet]` (2nd slot changed) | `['ACC-401-AITOOLS', 'ACC-101-RETENTION']` | `['ACC-401-AITOOLS', 'ACC-101-RETENTION']` (unchanged) |
| ontra | `[specs-translation bullet, data-integration bullet]` | `[specs-translation bullet, data-integration bullet]` (unchanged) | `['ACC-401-AITOOLS', 'ACC-102-LEAD']` | `['ACC-401-AITOOLS', 'ACC-102-LEAD']` (unchanged) |
| buyers_edge_platform | `[PI-planning bullet, data-integration bullet]` | `[licensing-compliance bullet, PI-planning bullet]` (BOTH slots changed) | `['ACC-101-RETENTION', 'ACC-202-DELIVERY']` | `['ACC-101-RETENTION', 'ACC-202-DELIVERY']` (unchanged) |

Honest finding, consistent with the Round 2/3 pattern: `pick_cover_bullets` (the `draft_compiler.py:678`
fallback path) changed picks for 2 of 3 companies (redox's 2nd slot, buyers_edge_platform's both slots);
ontra's picks were stable. `cover_claim_picker.pick_cover_proofs` (the real `cover_claim_picker.py:134`
production path used by `build_cover_plan`) was **unchanged for all 3 companies** — `ACC-401-AITOOLS`
still wins slot 0 for redox/ontra via the `has_ai_signal`-gated bonus / `_protected_ai_slot` guard,
consistent with every prior round's finding that this guard is independent of `score_claim_for_jd`'s
base-score scale.

**Pytest regression check.** Full suite (`python -m pytest -q --ignore=test_domain_gate.py
--ignore=test_fit_policy.py --ignore=test_llm.py`), clean `__pycache__`: **28 failed / 190 passed /
1 skipped.** True before/after isolated via a scoped in-place revert of just the final two lines of
`score_claim_for_jd` back to Round 3's plain-sum formula (not git stash, per the documented pitfall),
deselecting only the new Round 5 dampener test (which is meaningless under the reverted formula):
**before (Round 3 state, reconstructed) = 28 failed / 189 passed / 1 skipped / 1 deselected — an exact
match to Round 3's documented baseline**, confirming the revert technique is sound. Diffing the two
sorted `FAILED` lists: **byte-identical, zero differences.** The exact same 28 tests fail in both states,
including — **the load-bearing check this round was asked to make** — both Round-3 regressions
(`test_cover_claim_picker.py::TestCoverClaimPicker::test_fintech_jd_prefers_dropoff_story`,
`test_cover_word_padding.py::TestCoverWordPadding::test_thin_jd_still_produces_proof_content`) are
present in BOTH the before and after lists — **they did NOT self-resolve under the dampener.** This
directly falsifies Round 4's own explicitly-hedged, not-guaranteed prediction ("the dampener may make
the retune unnecessary... I will NOT predict that it does... only that it plausibly mitigates them, to
be MEASURED"): measured, and it did not. Zero new failures, zero newly-passing pre-existing tests. Net:
same 28 failed as Round 3/4; 190 passed (189 + this round's 1 new test).

**Verdict for this round — a genuine null result on the code side, delivered inside a real
infrastructure-degradation finding that undercuts confidence in even that null result:**

1. **The DCG dampener is implemented correctly and behaves exactly as its Round 4 hand-check predicted**
   on isolated cases: a single-token precision claim is completely unaffected (structural immunity,
   confirmed both by the new pinned unit test and by Remote/ACC-401's real per-token math), and a
   multi-token breadth claim's contribution is cut sharply (unit test: 9->4; the existing dedup test's
   3-token case: 7->5 as an unplanned confirmation).
2. **On the only measurable evidence available this session (7 of 16 eval-set companies), ACC-105's
   top-5 over-representation does NOT drop at all** (5/7 -> 5/7) — the same null-movement pattern Round
   2 (dedup alone) and Round 3 (dedup+rarity) both hit on the full 14-company set. Three consecutive
   mechanisms — dedup, rarity, and now a structurally-sound breadth dampener — have each performed
   exactly as designed on isolated hand-checks and unit tests, yet none has moved this specific
   full-field ranking metric on real JD data.
3. **Per the pre-registered escalation lever, this null result does NOT authorize trying the geometric
   decay or any other mechanism unilaterally.** That decision routes to Jason, same as Round 3's null
   result did.
4. **The 2 Round-3 cover-letter pytest regressions remain, unchanged** — Round 4's speculative mitigation
   did not materialize. They remain exactly what Round 3/4 called them: a real, root-caused,
   explicitly-justified-not-fixed consequence of `cover_claim_picker.py`'s flat additive bonuses
   interacting with a scale this CR's mechanisms keep changing, still awaiting a Jason-gated calibration
   follow-up decision.
5. **The eval-set working tree instability is now severe enough to be its own finding, separate from
   CR-064's substantive result**, and should be escalated to Jason as an operational blocker for any
   further rounds of this CR (or any other work depending on `data/submissions/` eval-set folders) —
   see Session Handoff.

## Guardrails (apply every round, no exceptions)

- Keep `score_claim_for_jd`'s signature exactly `(claim_text: str, profile: JdProfile, jd_text: str) -> int`.
  If a round's design genuinely requires more inputs (e.g. the catalog itself, for a rarity table), solve
  it with a module-level cache inside `jd_tailoring.py`, not a signature change — see CR-064 spec
  Decision §3 for why this is a hard constraint, not a preference.
- Never fabricate a claim or edit `master_claims.json` content/tags as part of this CR. If a real
  tag-quality issue surfaces (e.g. CR-063's `ACC-107`/`ACC-112` overlap finding), flag it to Jason as its
  own explicit follow-up — do not fold a catalog edit into this CR's diff.
- Re-run the full `measure_theme_extraction.py` measurement (14 JDs as of 2026-07-13; 16 if SailPoint/
  Group 1001 are restored) every round, not just against the JD that motivated that round's change —
  CR-063's Round 2 found a real regression (Lumos) that only a full-set re-run caught.
- Also re-check the cover-letter-side (`pick_cover_bullets`/`_proof_score`) sample every round, not just
  once — this is a new guardrail added after tech-lead's 2026-07-13 pass found the existing measurement
  script never exercises this path.
- Run the full pytest suite every round (excluding the 3 known-bad non-pytest files) and treat any new
  failure as a real regression to fix or explicitly justify, not something to note and move past.
- Do not touch `data/submissions/` for any already-reviewed company as part of this work — this CR
  changes the pipeline's *default* ranking behavior using the eval set's JDs as fixed test input, not
  live submission output.

---

## Session Handoff — read this FIRST, fill it in before you stop

Whoever is reading this at the start of a session: check "Last updated" below. Round 1 (design), Round 2
(dedup), Round 3 (rarity weight), and now **Round 5 (breadth-dampener implementation) are COMPLETE and
live in `score_claim_for_jd`.** Round 4 (design) was Jason-approved and Round 5 implemented it exactly as
designed. **The CR's core mechanism (dedup + rarity + DCG breadth dampener) is now fully implemented,
but the CR's stated acceptance criterion (ACC-105's cross-JD over-representation measurably drops) is
STILL NOT DEMONSTRATED — three consecutive, individually-correct mechanisms have each failed to move
that specific metric.** Do not start a Round 6 implementation without a fresh Jason decision — see
"Open questions" below, item (0).

Whoever is ending a session on this CR: fill this in before you go, with the same concreteness CR-063's
handoffs used.

- **Last updated:** 2026-07-14 — senior-engineer implementation pass, Round 5 (DCG breadth-dampener,
  Jason-approved in Round 4). See `../../pipeline-log.md`, "Senior Engineer — CR-064 Round 5", and the
  "Round 5" section above.
- **Current stage:** Round 5 (breadth-dampener IMPLEMENTATION) is DONE. `score_claim_for_jd` in
  `scripts/jd_tailoring.py` now does dedup (max tier per token) -> rarity-weighted contribution
  (`tier * _rarity_weight(tok)`) -> DCG rank-discount (sort contributions descending, divide the value at
  1-indexed rank `r` by `log2(r+1)`, sum, `int(round(...))`). Signature unchanged. Exactly the Round-4
  design, zero deviation. New unit test `TestScoreClaimForJdBreadthDampener` pins the dampener's core
  property with a pinned synthetic table (single-token claim unaffected; 9-token claim cut ~55%); watched
  red then green. The existing Round 2/3 dedup-isolation test was updated (same precedent Round 3 set for
  the rarity multiplier) to use a single multi-loop-matched token so it isolates dedup from the
  now-unconditionally-applied dampener.
- **Round 5 measured outcome — a genuine null result on the CR's target metric, PLUS a severe, separate
  infrastructure finding that undercuts confidence in the null result itself (read both, don't average
  them):**
  1. **ACC-105's top-5 over-representation does NOT drop** on the only data available this session:
     5/7 companies show it in top-5, both before (Round-3-reconstructed) and after (Round-5-live) —
     completely unchanged, the same null-movement pattern Round 2 (dedup alone) and Round 3 (dedup+rarity)
     both hit on the (larger, now-unavailable) 14-company set. **Three consecutive, individually
     hand-verified-correct mechanisms — dedup, rarity, and a structurally-sound breadth dampener — have
     now each failed to move this specific full-field ranking metric.**
  2. **NEW, severe finding this round: the `data/submissions/` eval-set working tree degraded further and
     became actively unstable mid-session.** Round 3/4 measured against 14/16 present companies (missing
     only sailpoint/group_1001). At the start of this session only **7/16** were present — cresta,
     sailpoint, group_1001, onestream_software, remote, covideo, datagrail, mytime, lumos were ALL
     missing. Worse: an `ls` mid-session showed 8 folders (including `remote`); a repeat `ls` ~5 minutes
     later, with no action taken on that directory by me in between, showed `remote` gone (down to 7),
     and a later check showed two unrelated new folders (`_batch_audit`, `test_co`, not in `EVAL_SET`) had
     appeared. **This points to an actively running external process (very likely the Google Drive sync
     already named in the tracker) mutating `data/submissions/` live during active work, not a one-time
     gap.** The historical 11/14, 12/37 headline numbers cannot be reproduced on this working tree at all
     right now. I measured a genuine, internally-consistent before/after on the 7 companies present and
     stable for each individual run, and substituted redox/ontra/buyers_edge_platform for the
     story-assigned cresta/remote/covideo (all three missing) in the cover-letter hand-check. This is a
     real, worsening, separate problem from CR-064's substantive result — recommend treating it as its own
     operational issue, not something to resolve inside this CR.
  3. **Cover-letter side, on the 3 substitute companies:** `pick_cover_bullets` changed picks for 2 of 3
     (redox's 2nd slot, buyers_edge_platform's both slots); `cover_claim_picker.pick_cover_proofs` (the
     real production path) was unchanged for all 3 — `ACC-401-AITOOLS` still wins slot 0 via the
     `has_ai_signal` guard, independent of base-score scale, consistent with every prior round.
  4. **The 2 Round-3 pytest regressions (`test_cover_claim_picker.py::test_fintech_jd_prefers_dropoff_story`,
     `test_cover_word_padding.py::test_thin_jd_still_produces_proof_content`) did NOT self-resolve** —
     Round 4's explicitly-hedged prediction that the dampener "may plausibly mitigate" them is measured
     and falsified. Both still fail, unchanged. Full pytest: **28 failed / 190 passed / 1 skipped**
     (identical 28-test FAILED list to the reconstructed Round 3 state via a verified before/after diff;
     190 = 189 + this round's 1 new test; zero new failures, zero newly-passing tests).
- **Per the story's own pre-registered escalation lever and every prior round's discipline: this null
  result does NOT authorize trying the geometric-decay escalation or any other new mechanism
  unilaterally.** That decision routes to Jason. Logging the result and stopping here on the code side.
- **A measurement-methodology note reused successfully again this session:** rather than `git stash`
  (documented pitfall since Round 2) or a fragile module-attribute monkeypatch of `_rarity_weight` (Round
  3/4's technique, which doesn't cleanly reconstruct the dampener's ancestor state), this round used two
  techniques depending on the check: (a) `jd_tailoring.math.log2 = lambda x: 1.0` in-process monkeypatch
  for the measurement/cover-letter scripts (forces the DCG divisor to 1 for every rank, mathematically
  identical to Round 3's plain sum — verified sound by construction, not just by inspection), and (b) a
  scoped in-place revert of just `score_claim_for_jd`'s final two lines (not a file-level stash) for the
  pytest before/after, which reproduced Round 3's documented 28/189/1 baseline exactly before being
  trusted. Both recommended for any future before/after comparison on this file.
- **Exact next action:** Jason reviews this Round 5 result. Two separable decisions: (1) whether to
  authorize a fresh tech-lead design pass for the pre-registered geometric-decay escalation lever (the
  next knob per Round 4's own contingency plan) given 3/3 mechanisms have now failed to move ACC-105's
  top-5 count, or accept the CR as landed-but-not-fully-effective and close it with the honest limitation
  documented; (2) whether/how to address the newly-severe `data/submissions/` eval-set instability before
  any further measurement-dependent round of this CR is attempted, since the current working tree cannot
  reproduce a stable 14-company (let alone 16-company) baseline.
- **Open questions for Jason:** (0) NEW, highest priority: given dedup (Round 2), rarity (Round 3), and
  the DCG breadth dampener (Round 5) have ALL independently and correctly performed as designed yet NONE
  has moved ACC-105's top-5 over-representation count, does Jason want to (a) authorize the geometric-decay
  escalation as a 4th attempt at the same additive-formula thesis, (b) accept this CR as landed with a
  documented partial result (the formula is now measurably better-reasoned — precision claims are no
  longer structurally disadvantaged against breadth claims — even though the specific over-representation
  metric hasn't moved), or (c) reconsider whether the defect is upstream of the aggregation arithmetic
  entirely (e.g. JD-profile/keyword extraction, which CR-063 measured but did not fully resolve — see
  CLAUDE.md's CR-063 summary). (1) NEW, urgent and likely blocking regardless of (0): the
  `data/submissions/` eval-set folders are now actively unstable (7/16 present, changing mid-session,
  unrelated folders appearing) — needs its own resolution (restore from Drive, pause the sync, or snapshot
  a frozen local copy for eval-set use) before any further measurement-dependent round of ANY CR can trust
  its numbers. (2) Still open, unchanged since Round 3/4: the `cover_claim_picker.py` flat-bonus-vs-scale
  interaction (2 pytest regressions, real production proof-pick churn) — needs its own calibration
  follow-up decision, and now confirmed NOT self-resolving under the dampener either. (3) Unchanged from
  prior sessions: whether to commit the CR-063/CR-064 artifacts (the `THEME_KEYWORDS` additions, the two
  `measure_*` scripts, all three rounds' `score_claim_for_jd` changes, the new/updated unit tests, and the
  CR-063/CR-064 docs) as a scoped commit — none of it is committed yet.

---

## Close-out — Engineering Manager (2026-07-14)

**Status changed to `closed_partial` (deliberately NOT `complete`).** In this repo's convention
`complete` implies the goal was achieved; it was not, and a future reader must not mistake this for a
clean win. This is an informed closure decision by Jason after three independently-verified mechanisms,
not a failure state — nothing is broken, security is clear across every round.

**What shipped and is staying** (live in `scripts/jd_tailoring.py`, uncommitted, signature unchanged
across all 8 call sites): `score_claim_for_jd` now does dedup (max tier per token) -> rarity weight
(`1 + ln(N/df)`, floor 1.0) -> DCG breadth dampener (sort per-token contributions descending, divide the
value at 1-indexed rank `r` by `log2(r+1)`, sum, `int(round(...))`). This fixed **two real, verified
bugs**: (1) cross-loop/cross-line double-counting (a single token such as `platform` could score 3+
times), and (2) rare precise matches being under-scored in isolation against generic PM vocabulary. Both
are genuine improvements to the formula's reasoning and are kept.

**What was NOT achieved** (the core acceptance criterion): `ACC-105-EXECUTION`'s cross-JD top-5
over-representation did not measurably drop. It stayed **10/14 top-5 appearances** — same count, same
company membership — before and after, on the fullest and best-sourced measurement this CR ever achieved
(QA's Round-5 archive-sourced 14-company set including sailpoint/group_1001). This is the fourth
consecutive null result on this specific metric across dedup (Round 2), rarity (Round 3), and the breadth
dampener (Round 5). Each mechanism was correct in isolation; the additive-then-dampened aggregation
arithmetic is evidently not where the over-representation is decided.

**Open residual risk, explicitly deferred (not resolved by this close-out):**
1. **Two known cover-letter test regressions**, both deferred by design, not fixed:
   `test_cover_claim_picker.py::test_fintech_jd_prefers_dropoff_story` and
   `test_cover_word_padding.py::test_thin_jd_still_produces_proof_content`. Root cause (traced across
   Rounds 3-5): `cover_claim_picker.py::_proof_score`'s flat additive bonuses were calibrated against the
   pre-CR score scale and are now swamped/reordered by this CR's inflated scale. Retuning them changes
   cover-letter proof *selection* (a product-behavior change) against a scale this CR kept moving —
   correctly reserved as a Jason-gated calibration follow-up, not folded into this CR.
2. **Missing-file guard (Minor, QA Round 3 finding):** `_get_rarity_table()` opens
   `data/master_claims.json` with no `os.path.exists`/`FileNotFoundError` guard, unlike the house pattern
   in `claim_catalog.load_catalog()` (`scripts/claim_catalog.py:49-51`). Harmless on Jason's machine and
   in CI today (file present), but it silently gives three previously mock-only unit tests a hard
   dependency on the real gitignored catalog being present. Low-risk follow-up: add the same
   existence guard, returning an empty/all-floor table on absence. Not fixed here.
3. **Eval-set working-tree instability (operational, not CR-064's code):** `data/submissions/` degraded
   to 7/16 present and mutated mid-session during Round 5 (very likely the Google Drive sync). Not
   attributable to this CR's diff (security confirmed neither changed file touches `data/submissions/`),
   but it blocks any future measurement-dependent round until resolved (restore, pause sync, or snapshot
   a frozen eval copy).

**Recommended next direction (naming only, not scoping it here):** a NEW, separate investigation into
JD-profile / keyword extraction (upstream of `score_claim_for_jd`, the area CR-063 flagged but did not
fully resolve), per tech-lead's Round 4 escalation note that if both the DCG and geometric curves fail
to move the metric, the defect is not in the aggregation arithmetic. This is future work, not a
continuation of CR-064.

**Verification performed at close-out (independently re-run, not trusted from the chain):** full pytest
suite from `scripts/` reproduced **28 failed / 190 passed / 1 skipped** with both named regressions
present; current `score_claim_for_jd` read directly and confirmed byte-matching the Round-4/5 approved
design; all 8 call sites grepped and confirmed on the unchanged 3-arg signature; `data/master_claims.json`
confirmed unmodified; CR-064's code footprint confirmed confined to `scripts/jd_tailoring.py` +
`scripts/test_claim_preselection.py` (`git diff --stat`). Note for whoever commits this: the working tree
also carries an *unrelated* uncommitted change to `scripts/cover_claim_picker.py` (the `has_ai_signal`
proof bonus + `_protected_ai_slot` guard, a CR-061 mechanism the CR-064 rounds treated as pre-existing) —
scope the CR-064 commit to the two files above, not the whole dirty tree.
