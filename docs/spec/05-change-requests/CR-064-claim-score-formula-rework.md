# CR-064: Claim-Score Formula Rework (`score_claim_for_jd`)

## Metadata
- **Epic**: Local-LLM Drafting Pipeline (see `docs/reports/local-llm-builder-architecture-options.md`)
- **Status**: Not started — this CR is the handoff brief for the session that starts it
- **Date**: 2026-07-13
- **Source**: Direct follow-up to CR-063 (`docs/spec/08-implementation/CR-063-jd-theme-claim-selection-loop-tracker.md`),
  which ran a 16-JD human-verified eval loop against the deterministic claim-selection path and tested
  both of its own proposed fallbacks (semantic re-ranking via cached embeddings, `jd_profile_mode="llm"`)
  with real local infra. Both fallbacks failed cleanly, and the tracker's go/no-go recommendation pinned
  the actual defect to one function: `score_claim_for_jd` in `scripts/jd_tailoring.py:226-241`. This CR
  is that recommendation, formalized. Read the CR-063 tracker's "Round 4", "Final round", and "Go/no-go
  recommendation" sections before starting — they contain the full diagnostic trail, not just the
  conclusion.

## Problem
`score_claim_for_jd(claim_text, profile, jd_text)` computes a claim's rank via four independent,
additive loops with no cross-loop or cross-line deduplication:

```python
score = sum(1 for w in profile.keywords if w in text_l and w in jd_l)          # loop 1
for req in profile.requirements:                                               # loop 2
    for token in re.findall(r"[a-z]{5,}", req.lower()):
        if token in text_l:
            score += 2                          # uncapped per requirement line
for theme in profile.priority_themes:                                          # loop 3
    for token in re.findall(r"[a-z]{5,}", theme.lower()):
        if token in text_l:
            score += 1
for kw, _phrase in THEME_KEYWORDS:                                             # loop 4
    if kw in jd_l and kw in text_l:
        score += 3
```

Measured, not hypothesized, via CR-063's eval harness (`scripts/measure_theme_extraction.py`, 16-JD set):

1. **Generic-vocabulary claims win almost every JD regardless of fit.** `ACC-105-EXECUTION` ("enforced
   strict prioritization... across engineering teams... platform stability, compliance mandates...
   roadmap delivery") appeared in the top-5 for **11 of 16 JDs** tested. Its short body happens to share
   common PM words (engineering, platform, teams, roadmap, across) with nearly every requirements
   section, and because those words can independently trip loop 1, loop 2 (potentially multiple times,
   once per requirement line that restates the word), and loop 4, its score compounds where a more
   relevant claim's doesn't.
2. **A single precise, rare match can't compete.** For Remote's JD ("Proficiency in Cursor and/or
   Claude Code (Required)"), `ACC-401-AITOOLS`'s body literally contains "Claude" — a real, exact,
   JD-critical match. It earns the flat `+3` from loop 4 once. Final score: **3**. Remote's actual
   top-5 cutoff that round: **12**. The same pattern held for `ACC-204` (Sterkly dev-coordination,
   never surfaces for Buyers Edge/PAR despite literal "backlog" overlap) and for `ACC-401-AITOOLS`
   against Ontra/Covideo.
3. **Neither of CR-063's own proposed fallbacks fixes this, because neither touches this function.**
   Semantic re-ranking (cosine similarity via cached embeddings) made the aggregate hit rate
   monotonically *worse* (14/45 → 11/45 across 6 tested scale values) — a separate, now-closed line of
   investigation, not a substitute for fixing the formula. `jd_profile_mode="llm"` produced
   byte-identical top-5 rankings to the deterministic path on the 3 worst JDs even when the LLM
   correctly extracted a theme (`"AI"` for Ontra) the keyword table had missed — proving the bottleneck
   is downstream of JD-profile quality, in this exact ranking arithmetic.
4. **This function is on the real drafting path, not just the CR-063 eval harness** — it has 6
   production call sites: `local_draft_stages.py:438`, `claim_composer.py:154,216`,
   `draft_compiler.py:406,496`, `cover_claim_picker.py:134`, plus the eval-only
   `scripts/measure_theme_extraction.py`/`measure_semantic_rerank.py`. Every one calls it with the same
   3-positional-argument signature `(claim_text, profile, jd_text)`. This is genuinely a resume-bullet-
   ordering and cover-letter-claim-selection defect for every real submission, not only a measurement
   artifact.

## Decision
Rework `score_claim_for_jd`'s internal scoring so that:

1. **A given matched token contributes at most once per claim-JD pair**, not once per loop and not once
   per requirement line it happens to appear in. (Exact dedup mechanism — e.g. a `matched: set[str]`
   threaded through all four loops, take-the-max-bonus-tier per token — is an implementation decision
   for whoever picks this up, not mandated here; the requirement is the *outcome*, verified against the
   eval set, not a specific data structure.)
2. **Match weight scales inversely with how common the matched token is across the active claim
   catalog** (a TF-IDF-style rarity weight, or equivalent), so an exact match on a distinctive term
   (a named tool, a specific compliance regime, a rare domain word) outweighs an incidental match on
   ordinary PM vocabulary shared by dozens of claims. This requires a one-time per-catalog-load
   computation of token document-frequency across `catalog.claims` — cache it at module level inside
   `jd_tailoring.py` (same pattern `local_embeddings.py` uses for `_TAG_ANCHORS`), so `score_claim_for_jd`
   does **not** need a new parameter and all 6 production call sites are untouched.
3. **Keep the existing 3-argument signature** `score_claim_for_jd(claim_text, profile, jd_text)`. This is
   a hard constraint, not a nice-to-have — changing it means auditing and updating 6 call sites plus
   whatever tests reference them, which is unnecessary risk for a change whose actual fix lives entirely
   inside the function body.
4. **Validate against the same fixed instrument CR-063 built**, don't invent a new one:
   `docs/reports/jd-theme-claim-eval-set.md` (16 human-verified JDs) via
   `scripts/measure_theme_extraction.py` (already exists, unmodified, calls the real
   `build_jd_profile_deterministic` → `score_all_claims` path). Re-run the full 16-JD measurement after
   every change, not just the JD that motivated it — this is the same discipline CR-063 used and it
   caught a real regression (Round 2) that a narrower test would have missed.
5. **Follow the exact checkpointing/round protocol CR-063 used** (write a plan as checkboxes before
   executing, check off as you go, log real before/after numbers, stop at clean boundaries, fill in a
   Session Handoff block). See the tracker for this CR:
   `docs/spec/08-implementation/CR-064-claim-score-formula-rework-tracker.md`.

## Acceptance Criteria
- Re-running `scripts/measure_theme_extraction.py` after the fix shows a **higher** aggregate
  should-surface hit rate than CR-063's final baseline (**14/45 codes, 0/16 companies** — adjusted to
  **11/37 codes, 0/14 companies** per the tracker's working-tree data-availability note; see tracker for
  why) — the CR-063 bar is the long-term target, but any round of this CR should show measurable, logged
  improvement over the prior round, same discipline as CR-063.
- **Cover-letter-side proof selection is explicitly checked, not assumed.** `scripts/measure_theme_extraction.py`
  only exercises `build_jd_profile_deterministic` → `score_all_claims` (the resume-ranking path). It never
  calls `pick_cover_bullets` (`jd_tailoring.py:260-340`) or `cover_claim_picker.py`'s `_proof_score`
  (`cover_claim_picker.py:134`), even though `cover_claim_picker.py:134` is one of this CR's own named
  production call sites. Hand-verify `pick_cover_bullets`/`_proof_score` output (which claims get selected
  as cover-letter proof points, and their relative order) for 2-3 eval-set JDs before and after each round's
  change, logged the same way as the resume-side numbers. A round that only shows resume-side improvement
  is incomplete for this criterion.
- `ACC-105-EXECUTION`'s over-representation (11/16 top-5 lists at CR-063's baseline) measurably drops,
  and `ACC-401-AITOOLS` / `ACC-204` measurably rise, in the same re-run — a fix that only moves one side
  of this (fixes the over-triggering without helping the under-scoring rare matches, or vice versa) is
  incomplete; both are documented symptoms of the same dedup/rarity defect.
- Full `scripts/` pytest suite (`python -m pytest -q --ignore=test_domain_gate.py --ignore=test_fit_policy.py --ignore=test_llm.py`
  — those three are pre-existing non-pytest collection issues, unrelated) shows no *new* failures beyond
  the 27 pre-existing ones documented in the CR-063 tracker's "Regression check between rounds" section.
  Confirm this with a path-limited `git stash` of just the changed file(s), the same technique CR-063
  used, before and after — don't assume, measure.
- `score_claim_for_jd`'s signature is unchanged: `score_claim_for_jd(claim_text: str, profile: JdProfile, jd_text: str) -> int`.
  All 6 production call sites (`local_draft_stages.py`, `claim_composer.py` ×2, `draft_compiler.py` ×2,
  `cover_claim_picker.py`) require zero changes.
- Zero new fabricated claims or tag rewrites to `master_claims.json` as part of this CR — this is a
  ranking-arithmetic fix, not a claim-content change. (If the work surfaces a real tag-quality issue,
  e.g. the `ACC-107`/`ACC-112` tag overlap CR-063's Round 2 found, flag it to Jason as a separate,
  explicit follow-up rather than silently editing the catalog mid-CR.)
- New unit tests added directly against `score_claim_for_jd`'s dedup/rarity behavior (none currently
  exist — `test_claim_preselection.py` only covers `score_all_claims`/`select_cl_claims` with MagicMock
  profiles, and doesn't pin down the internal arithmetic this CR changes).

## Out of Scope
- Wiring in semantic/embedding-based re-ranking — CR-063's Final round already tested this with real
  data (cached `nomic-embed-text` embeddings) and found it makes the aggregate hit rate *worse*, not
  better (14/45 → 11/45 as re-ranking weight increased). Do not revisit without new evidence that
  specifically explains why CR-063's negative result doesn't apply anymore (e.g. a different embedding
  model, or a rewritten claim catalog with more textually distinctive claims).
- Broadening the `jd_profile_mode="llm"` pilot — CR-063 confirmed it produces identical selection
  accuracy to the deterministic path because the defect is downstream of JD-profile quality. Revisit
  only after this CR's formula fix ships and is re-measured; if a formula fix alone doesn't close enough
  of the gap, an LLM-mode pilot becomes relevant again, but only as a next step after this one, not a
  parallel one.
- Building Hybrid Anchor + Polish (CR-062 phase 2) — the defect found in CR-063 lives entirely inside the
  existing deterministic `score_claim_for_jd` function; it is a bug in that function's arithmetic, not
  evidence the deterministic architecture itself needs replacing. Fix the formula and re-run the eval set
  before concluding a bigger architecture change is warranted.
- Adding new `THEME_KEYWORDS` entries — three rounds of this in CR-063 (Rounds 2-4) showed diminishing
  and even net-negative returns (Round 2 fixed one JD and regressed another via a tag collision). The
  keyword table itself is not the remaining problem; more entries feed the same flawed formula.
- Editing `master_claims.json` claim tags (e.g. tightening `ACC-107`/`ACC-112`'s overlapping tags) —
  noted as a real, separate finding in CR-063 Round 2, but requires Jason's sign-off since it touches the
  source-of-truth catalog. Flag it; don't fold it into this CR's diff.
