# CR-087: Item-Overlap Precision (Generic-Token Denylist + No JD-Score-Only Top-2)

## Metadata
- **Status**: Implemented (2026-08-10)
- **Date**: 2026-08-10
- **Source**: session-007 (Camunda ACC-120 false positive); Jason green-lit Cursor build
- **Related**: CR-085 (packaging), CR-086 (Stage0 extraction noise), CR-064 (full-JD scorer —
  unchanged; this CR only changes *item-level* pairing in `build_authoring_packet.py`)
- **Requirement IDs**: None formally registered — retrieval precision

## Problem
After CR-085/086, Camunda still mapped:

> Keep the self-managed team equipped to work on the appropriate epics.

→ `ACC-120-AIRESEARCH` (joint prompt-engineering research — unrelated).

Measured cause (`_score_claims_for_item`):

```
total = capability_boost + overlap*1000 + jd_score
```

ACC-120 scored **1015** with item overlap = **`{team}` only** (from tag "Cross-Team Learning").
One generic 4-letter word is worth 1000 points. Real Agile/prioritization claims
(ACC-105) had **zero** item overlap and scored ~9–11, so they lost.

Second place (`ACC-107-PLATFORM`, score 23) had **zero item overlap** — pure full-JD
`jd_score` filling Top-2. So even after killing the `team` hit, garbage can still occupy
slots via the secondary scorer alone.

This is a **precision** bug, not a missing ontology / synonym problem.

## Decision
1. **Generic-token denylist** for item↔claim overlap. Tokens like `team`, `work`, `product`,
   `experience`, `years`, `ability`, `skills`, … do not count toward `overlap`. Distinctive
   tokens (`epics`, `agile`, `migration`, `privacy`, …) still do.
2. **No JD-score-only nomination.** If distinctive overlap is 0 **and** `capability_boost` is 0
   (AI/compliance soft-gap boosts unchanged), force `total = 0` so the claim cannot enter
   Top-2. `jd_score` remains a tiebreaker among claims that already have item signal or a
   capability boost.
3. Empty `claim_ids` for a line with no distinctive match is acceptable (better empty than
   ACC-120). Soft gaps / Rule 2 unchanged for real requireds that need bridges.

## Acceptance Criteria
| ID | Criterion |
|----|-----------|
| AC1 | Camunda epics-staffing line does **not** map to `ACC-120*` (unit + live packet rebuild) |
| AC2 | AI/ML JD items still boost ACC-120 / ACC-401 via existing capability_boost path |
| AC3 | Existing `test_build_authoring_packet.py` suite passes; new regression tests cover AC1–AC2 |
| AC4 | Camunda ACC-120 FP eliminated on live rebuild; packet-level should-surface may dip slightly vs CR-086's 30/35 because jd_score-only stuffing is disabled — floor **≥ 28/35**, with the dip accepted as precision > fake recall |

## Out of Scope
- Capability ontology / BM25 / embeddings / LLM primary retrieval
- Changes to `score_claim_for_jd` / CR-064 formula
- Deleting or rewriting ACC-120 claim content
- Stage0 extraction (CR-086)
