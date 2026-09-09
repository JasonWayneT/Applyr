# Stage 0 Improvement Spec — Handoff Document

**Created:** 2026-09-01
**Status:** Ready for implementation
**Context:** Deep monitoring session identified 10 improvement opportunities after all Stage 0 bugs were fixed and verified. Stage 1 improvements already implemented and verified (80 tests pass).

---

## Summary

All 9 Stage 0 bugs/issues are fixed and verified (see CHANGELOG). This spec covers **improvements**, not bug fixes — ways to make Stage 0 faster, more accurate, and better at matching candidate experience to JD needs.

## Improvement #1 — Add few-shot examples to the evidence cascade batch prompt (HIGH IMPACT)

**File:** `scripts/stage0_evidence_cascade.py`
**Function:** `_build_batch_prompt()` (line ~210) and `_SYSTEM_PROMPT` (line ~228)

**Problem:** The batch prompt is terse (6-line system prompt, no few-shot examples). The single-item path (`evidence_scale.classify_requirement`) gets k=4 few-shot examples and a detailed 50-line system prompt with evidence-scale definitions, OR-alternative handling, and forbidden-evidence rules. The batch path lacks all of this, likely degrading classification accuracy.

**Fix:**
1. Expand `_SYSTEM_PROMPT` to include the evidence scale 0-4 definitions, OR-alternative line handling, forbidden evidence types, and HARD gate categories — align with `evidence_scale._SYSTEM_PROMPT`.
2. Retrieve k=2 few-shot examples from `data/fit_rubric_golden_set.json` (via `fit_rubric_examples.retrieve_examples`) and include them before the items in `_build_batch_prompt`.
3. Extract shared rules into a common constant so both paths stay aligned.

**Risk:** Increases token count per batch call. With k=2 examples (~600 chars), total prompt grows by ~150 tokens. Should still fit within Groq's 8000 TPM limit with the 3000-char evidence context reduction already in place.

## Improvement #2 — Batch the responsibilities exclusion zone scanner (HIGH IMPACT)

**File:** `scripts/build_stage0_fit_gate.py`
**Function:** `screen_responsibilities_for_exclusion()` (line ~1935)

**Problem:** Makes one `classify_requirement` LLM call per responsibility line (sequentially). A JD with 8+ responsibilities adds 8+ sequential LLM calls, each going through Groq → Gemini cascade. This is the primary reason the Bazaarvoice JD takes 100+ seconds.

**Fix:**
1. Collect all responsibility lines not caught by `_DETERMINISTIC_0TO1_BUILD_RE` into `BatchItem` objects.
2. Call `stage0_evidence_cascade.classify_requirements_batch()` in one shot.
3. Iterate over batch results to collect HARD hits.
4. This mirrors exactly how the caller already batches required/preferred items.

**Risk:** The batch classifier was designed for required/preferred items. Responsibility lines have different classification needs (exclusion zone detection, not evidence-level scoring). May need a separate batch prompt or a `classification_mode` parameter. Test with Bazaarvoice JD (8 responsibilities) and Kintsugi JD (3 responsibilities).

## Improvement #3 — Track recent 429 failures and skip rate-limited providers (MEDIUM IMPACT)

**File:** `scripts/utils.py`
**Function:** `check_rate_limits()` (line ~206) and `_call_groq`/`_call_gemini`

**Problem:** `check_rate_limits` only counts self-initiated "API request initiated" log entries. If a provider returned an actual HTTP 429, `check_rate_limits` has no knowledge — it will attempt the provider again, wasting a round-trip before cascading. This adds 2-5 seconds per call for Groq when it's rate-limited.

**Fix:**
1. When `_call_groq`/`_call_gemini` receives a 429, log it to `activity_log` with message `[groq] RATE_LIMITED` (or `[gemini] RATE_LIMITED`).
2. In `check_rate_limits`, count recent RATE_LIMITED entries — if a provider has > 3 RATE_LIMITED entries in the last 5 minutes, return `False` (skip this provider).
3. Replace the blocking `time.sleep(60)` with `return False` — let the caller cascade to the next provider instead of blocking.

**Risk:** May skip Groq too aggressively if rate limits are transient. Set a cooldown window (e.g., 5 minutes) after which the provider is retried.

## Improvement #4 — Implement automatic chunking for batches > 24 items (MEDIUM IMPACT)

**File:** `scripts/stage0_evidence_cascade.py`
**Function:** `classify_requirements_batch()` (line ~70)

**Problem:** If a batch exceeds `MAX_BATCH_ITEMS = 24`, it raises `CascadeValidationError`. No chunking or splitting. Also, if validation fails on 1 of 24 items, all 23 valid results are discarded.

**Fix:**
1. If `len(items) > MAX_BATCH_ITEMS`, split into chunks of <= 24, call `classify_requirements_batch` for each chunk, merge results.
2. Implement partial acceptance — validate each result independently, accept valid ones, only re-classify invalid/missing items via the next provider.

**Risk:** Partial acceptance adds complexity. Test thoroughly with the checkpoint database to ensure partial results are correctly persisted.

## Improvement #5 — Expand deterministic exclusion zone regex (MEDIUM IMPACT)

**File:** `scripts/build_stage0_fit_gate.py`
**Constant:** `_DETERMINISTIC_0TO1_BUILD_RE` (line ~1820)

**Problem:** Only catches "own/lead/drive/responsible for zero-to-one/0-to-1 build/launch/creation". Misses common exclusion-zone phrasing like "founding PM", "build from scratch", "greenfield", "where none previously existed".

**Fix:** Add alternative patterns:
```python
r"(?:founding|first)\s+(?:pm|product\s+manager)\b|"
r"(?:build|create|launch)\s+(?:from\s+scratch|from\s+the\s+ground\s+up|from\s+nothing)\b|"
r"\bgreenfield\s+(?:product|build|launch)\b|"
r"(?:shaping|maturing)\s+an?\s+early.stage\s+product\s+area\b|"
r"(?:where|when)\s+none\s+(?:previously\s+)?existed\b"
```

**Risk:** False positives — "first product manager" could be a legitimate non-founding role. Test against archived JDs to calibrate.

## Improvement #6 — Improve evidence context retrieval with TF-IDF weighting (MEDIUM IMPACT)

**File:** `scripts/evidence_scale.py`
**Function:** `build_evidence_context()` (line ~100)

**Problem:** Uses raw Jaccard similarity (unweighted token overlap). A chunk mentioning "roadmap" and "cooking" ranks the same for a requirement about "roadmap prioritization" as one mentioning "roadmap" and "Jira". No TF-IDF weighting, no semantic similarity.

**Fix:**
1. Apply `_rarity_weight()` from `jd_tailoring.py` to each overlapping token before computing similarity (same fix as Stage 1 improvement #1).
2. Increase k from 6 to 8 for larger WE documents.
3. Consider boosting tokens that match the anchor vocabulary.

**Risk:** Changes to evidence retrieval may shift which evidence the classifier sees, changing classification results. Test against the golden set.

## Improvement #7 — Implement deferred fit-score modifiers (MEDIUM IMPACT)

**File:** `scripts/evidence_scale.py`
**Function:** `compute_fit_score()` (line ~380)

**Problem:** Two modifiers are explicitly noted as not implemented:
- Repetition modifier (+1, capped) — spec Sec. 10
- Hedge-language modifier (-1) — spec Sec. 10

Also, weights (`_REQUIRED_WEIGHT = 3.0`, `_PREFERRED_WEIGHT = 1.0`) and confidence multipliers (`_CONFIDENCE_MULTIPLIER = {"high": 1.00, "medium": 0.85, "low": 0.65}`) are hardcoded, not calibration-file-driven.

**Fix:**
1. Implement the repetition modifier: if the same evidence_level appears 3+ times across required items, +1 to each (capped at 4).
2. Implement the hedge modifier: if reasoning contains hedge language ("contributed to", "partnered on"), -1 to evidence_level (floored at 0).
3. Move weights and confidence multipliers to `data/fit_rubric_calibration.json`.
4. Consider lowering "low" confidence multiplier from 0.65 to 0.5.

**Risk:** Changing the fit score formula will change tier assignments. Test against archived JDs to ensure no regressions (Kintsugi should still SKIP, Bazaarvoice should still PASS).

## Improvement #8 — Incorporate anchor-vocabulary matching into requirement specificity scoring (LOW IMPACT)

**File:** `scripts/build_stage0_fit_gate.py`
**Function:** `_requirement_specificity_score()` (line ~480)

**Problem:** Specificity scoring only checks for digits (+2.0) and generic soft-skill patterns (-2.0). A requirement like "Experience with Salesforce Health Cloud" (no digit, not a generic soft skill) scores the same as "Experience working in a collaborative environment".

**Fix:** Add +1.0 for items containing terms from `_load_anchor_vocab()` (anchor vocabulary from claims + skills catalog). This would prioritize specific, decision-bearing requirements over generic ones when capping.

**Risk:** Low — only affects which items survive the 12-item cap for very large JDs.

## Improvement #9 — Add more stage signal patterns (LOW IMPACT)

**File:** `scripts/build_stage0_fit_gate.py`
**Function:** `_detect_stage_signal()` (line ~1360)

**Problem:** Only 7 regex patterns, first-match only. Misses "bootstrapped", "profitable", "hypergrowth", "scale-up", "post-Series-B", employee count ranges.

**Fix:** Add more patterns and a priority ordering (enterprise > public > PE-backed > VC-backed > startup > unknown).

**Risk:** Low — only affects the `stage_signal` display field, not the tier decision.

## Improvement #10 — Make rate limit thresholds configurable (LOW IMPACT)

**File:** `scripts/utils.py`
**Constant:** `_RATE_LIMIT_THRESHOLDS` (line ~165)

**Problem:** Hardcoded RPM/daily limits for Gemini and Groq. No tracking for Claude or Perplexity. Limits can't be adjusted without code changes.

**Fix:** Move to `candidate_preferences.json` or a new `llm_rate_limits.json` config file. Add entries for Claude and Perplexity.

**Risk:** Low — configuration change only.

---

## Verification Plan

After implementing any of these improvements:
1. Run `python -m pytest scripts/test_build_authoring_packet.py -x -q` — all 80 tests must pass
2. Run Kintsugi JD through Stage 0 — must still SKIP (fit_score < 40)
3. Run Bazaarvoice JD through Stage 0 — must still PASS (fit_score >= 40)
4. Check that no local LLM calls are made (all calls go to Groq/Gemini)
5. Check that the evidence cascade produces valid results (no validation errors)
6. Compare timing before/after — improvements #2 and #3 should reduce Stage 0 time by 30-50% for large JDs
