# CR-085: JD → Work-Experience Packet Dedup + Domination Cap (Phase 1)

## Metadata
- **Status**: Implemented (2026-08-10)
- **Date**: 2026-08-10
- **Source**: session-007 (harness-bridge, Claude Code ↔ Cursor cross-review), converged R1–R4
- **Related**: CR-063 (14/45 baseline; embeddings 14→11/45 — decisive prior art against
  primary-retrieval embeddings/LLM), CR-064 (rarity-weighted scoring, unchanged by this CR),
  CR-074 (authoring packet path this CR patches)
- **Requirement IDs**: None formally registered — implementation-level fix, not new scope

## Problem
Independent measurement by both harnesses (Claude Code: 3 real packets; Cursor: 15 real
packets) converged on the same finding: the authoring packet's problem is not the 8,000-token
fail-closed ceiling — real packets run 2,400–3,300 tokens, well under budget. It's duplication
and coverage collapse:

1. **Byte-identical duplicate excerpts.** 21 of 28 underlying projects have 2–5 claim lenses
   (e.g. `ACC-102-TECH`/`ACC-102-BUS`/`ACC-102-INT`), but `workExperience.md` has only one
   `[ACC-NNN]` bracket marker per project. Every lens resolves to the same 500-char slice,
   stored redundantly under different `excerpts` keys (measured: 2–4 duplicate-text groups per
   real packet).
2. **`jd_buckets.required/preferred/responsibilities` duplicates `evidence_map`.** These three
   arrays are always exactly reconstructable from `evidence_map` (same items, same order —
   `build_evidence_map` unconditionally emits one row per Stage-0 item), so the full JD item
   text is serialized twice into the actual prompt (`author_from_packet.py` dumps the whole
   packet as JSON). Measured: ~207 tokens / ~8% of a real packet.
3. **`hard_constraints` duplicates the rule digest**, which is loaded into every author session
   alongside the packet. Measured: ~245 tokens / ~9% of a real packet, ~80% redundant with
   content already in `authoring_rule_digest.md`.
4. **One claim can dominate unrelated requirements.** Per-requirement top-2 scoring has no
   global constraint. Confirmed in three independent real submissions: `ACC-104-CS` in 14 of 18
   evidence_map rows (Thermo Fisher), `ACC-113-ADOPTION` in 5 of 10 and 5 of 8 rows (Limble,
   Paylocity) — spanning genuinely unrelated requirements (remote collaboration, product
   lifecycle, CMMS experience, AI/ML features).
5. **The best-shaped evidence source in the repo goes unread.** `master_claims.json` (full
   catalog) already has a clean, lens-specific, single-paragraph `text` field per claim
   (all 67 claims, max 408 chars). `build_authoring_packet.py` only reads the tags-only file,
   which strips `text`, and instead regex-slices `workExperience.md` — a document written for a
   human reader, not extraction. This is *also* the root cause of (1): once wired in, each lens
   has genuinely distinct text, so the duplicate-byte problem resolves without any schema change.
6. Some JD lines carry no evidence-worthy signal ("excellent communication skills") and
   currently still consume a full 67-claim scoring pass and an `evidence_map` row.

## Decision
1. `load_claims()` merges each claim's `text` field from `master_claims.json` into the record
   it returns, keyed by the same lens claim_id (e.g. `ACC-101-TECH`'s own text, distinct from
   `ACC-101-PM`'s). Test fixtures that don't include `text` are unaffected (fall through to the
   existing path) — no test breakage.
2. Excerpt retrieval (`build_excerpts` and both floor-filling helpers) prefers
   `claims[cid]["text"]` when present, falling back to the existing
   `_extract_excerpt_for_project` WE/AI slicer only when a claim has no `text` (safety net for
   any future claim added without one; `_extract_excerpt_for_project` itself is unchanged).
3. `hard_constraints` trimmed from 8 items to 2: "don't copy excerpt sentences verbatim" (kept
   and strengthened — now load-bearing given (2), since `text` is grounding evidence, not
   draftable prose) and the geo-collaboration note (the only genuinely packet-specific,
   non-digest content). The other 6 were verified line-for-line redundant with
   `authoring_rule_digest.md` sections 2/3/8/9.
4. `_build_jd_buckets` returns empty `required`/`preferred`/`responsibilities` (schema keys
   kept, satisfies `authoring_packet_schema.json`) and populates only `culture` (the one bucket
   with no `evidence_map` counterpart — culture items are never scored/mapped).
   `author_from_packet.py`'s preamble gets one clarifying line so the cloud author isn't
   confused by the now-empty arrays.
5. A short, explicit, conservative boilerplate phrase list (`_is_boilerplate_item`) filters
   generic `preferred`/`responsibilities` lines before they consume a scoring pass or
   `evidence_map` row. **Never applied to `required`** — the fail-closed gate's Rule 2
   (unmapped required item) must stay authoritative. Filtered items are logged to stderr, never
   silently dropped from visibility.
6. `build_evidence_map` restructured into two passes: (1) score every non-filtered item against
   the full claim catalog as before, (2) a single global left-to-right assignment with a running
   `project_id` counter capped at `_MAX_SLOTS_PER_PROJECT = 3`. Each row still picks from its
   *own* ranked candidate list — a capped-out claim is replaced by that row's own next-best
   match, never an unrelated claim forced in to fill a slot. If a required item's own top
   candidates are all capped out with no fallback, the existing Rule 2 fail-closed check
   surfaces it as `incomplete` (no new mechanism needed — this is the correct, already-existing
   visibility path, not a silent drop).

## Explicitly deferred, not resolved by this CR
Raised in session-007 R2/R3 and intentionally left open rather than folded into this Phase 1
scope:
- **Cursor's 8-tier relevance-class taxonomy** (`direct / semantic_equivalent / capability /
  analogous / transferable / supporting / weak / unsupported`). Claude Code's position: Stage 0
  already has a working 3-tier version of this (required-with-evidence / soft-gap-with-bridge /
  hard-gap-skip). Before adopting the full 8-tier version, want one real case where the extra
  granularity changes what the author writes differently — otherwise it's bookkeeping the
  author can't act on. Cursor partial-accepted (keep 3-tier as default; add only
  `transferable` vs `unsupported` for soft-domain gaps) but this remains unimplemented and
  unmeasured — do not treat it as settled.
- **Token target discrepancy.** Cursor's proposed Phase 2+ target (~3.0–3.5k) is flat-to-higher
  than current real packet usage (2.4–3.3k) despite this CR's claimed duplication savings.
  Cursor clarified their number was a ceiling for *later* structured-card content, not a defense
  of current waste, and confirmed Phase 1 alone should lower tokens. Flagging here so a future
  reader doesn't read "similar token count post-Phase-2" as evidence Phase 1 didn't work — they
  are different phases with different token accounting.
- BM25 candidate generation, capability-ontology expansion, calibrated multi-weight scoring
  formula, embeddings/LLM in primary retrieval — all explicitly out of scope pending a
  re-measurement of CR-063's eval set after this CR lands (see AC5).

## Acceptance Criteria
| ID | Criterion |
|----|-----------|
| AC1 | Real packet excerpts source from `master_claims.json`'s per-lens `text` when present; existing `test_build_authoring_packet.py` suite passes unmodified against fixtures that lack `text` |
| AC2 | `hard_constraints` contains exactly the verbatim-copy rule + geo note; no content duplicated from `authoring_rule_digest.md` |
| AC3 | `jd_buckets.required/preferred/responsibilities` are empty in newly built packets; `culture` unaffected; all four keys still present (schema-valid) |
| AC4 | No single `project_id` occupies more than 3 `evidence_map` rows on re-generation of the Thermo Fisher, Limble, and Paylocity packets; required-item coverage on those three packets does not regress (no new Rule-2 `incomplete` vs. their current `ready` status) |
| AC5 | `docs/reports/jd-theme-claim-eval-set.md`'s CR-063 measurement re-run after this CR lands, confirming no regression below the 14/45 baseline |

## Out of Scope
- Relevance-class taxonomy (any tier count), BM25, capability-ontology expansion, calibrated
  scoring formula, embeddings/LLM in primary retrieval — see "Explicitly deferred" above.
- Evidence-card schema beyond what `master_claims.json` already provides (`problem`/`action`/
  `result`/`claim_boundaries` as separate structured fields) — real gap, not addressed here.
- Any change to `score_claim_for_jd` / CR-064's rarity-weighting formula.
