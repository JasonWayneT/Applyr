# Authoring packet fail-closed rules (CR-074 Epic 1.4)

**Implements:** `FR-253`, `AC-273`, `AC-274`  
**Schema:** [`authoring_packet_schema.json`](./authoring_packet_schema.json)

These rules are enforced by `build_authoring_packet` (Epic 3). Cloud authoring **must not run**
unless `packet_status === "ready"`.

## Fail → `packet_status: "incomplete"`

1. **Required item unmapped** — any `jd_buckets.required` entry has no `evidence_map` row, or that row has empty `claim_ids` **and** `bridge` is null/empty.
2. **Disabled claim selected** — any `claim_id` in `evidence_map` or `excerpts` is marked `"disabled": true` in `master_claims.json`.
3. **Missing excerpt** — a `claim_id` appears in `evidence_map` but has no non-empty string in `excerpts`.
4. **Skip tier** — `tier === "Skip"` (no drafting).
5. **Over budget** — `estimated_tokens` > **8000** (initial ceiling from Epic 1.2; tighten after calibration).

## Pass → `packet_status: "ready"`

- Every required item mapped with ≥1 claim_id **or** an explicit soft `bridge`.
- All selected claims active; all excerpts present.
- Estimated tokens ≤ 8000.
- Soft gaps may remain (Tier 2); they must appear in `soft_gaps` and be argued as fit in composition, never as confession.

## Cloud author closed world

When status is `ready`, the author may use **only**:
- this packet,
- the rule digest identified by `rule_digest_version`,
- the short authoring prompt contract (Epic 5).

It must not load `agent_context_pack.md`, full `CLAUDE.md`, or the full claims catalog as drafting inputs.
