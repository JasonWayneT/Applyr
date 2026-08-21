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

## CR-085 (2026-08-10): jd_buckets and hard_constraints trimmed

`jd_buckets.required`/`preferred`/`responsibilities` are always empty in the assembled
packet. `build_evidence_map` emits exactly one row per Stage-0 item in each of those three
buckets (same order, unconditionally), so the text is always fully reconstructable from
`evidence_map` — populating both duplicated the same JD requirement text a second time in
the serialized prompt. Only `culture` (which has no `evidence_map` counterpart) is still
populated. All four keys remain present so the schema's required-keys check still passes.

`hard_constraints` is trimmed to two items (verbatim-copy rule + geo-collaboration note).
The other six are redundant with `authoring_rule_digest.md`, which is loaded into every
author session alongside this packet.

Excerpts prefer each claim's own `text` field (merged in from `master_claims.json` by
`load_claims`) over regex-slicing `workExperience.md` by `project_id`. This is also what
resolves the historical duplicate-excerpt problem across a project's lenses (e.g.
`ACC-102-TECH` vs `ACC-102-BUS`) — each lens now has genuinely distinct text instead of
falling back to the same single `[ACC-NNN]` bracket-marker slice.

**Superseded for excerpt source by CR-094:** excerpts now come from WE spans; lens
distinctiveness is a pointer + lens instruction, not catalog `text`.

`evidence_map` claim selection is capped at `_MAX_SLOTS_PER_PROJECT` (3) rows per
underlying project, applied globally across the whole map — a capped-out claim is replaced
by that requirement's own next-best-scoring match, never dropped silently (a required item
with no viable fallback still trips Rule 1 above, same as before this CR).

## CR-094 (2026-08-20): WE-primary excerpts

Excerpts are retrieved `workExperience.md` spans (or `aiProjects.md` for ACC-401), never
catalog `text`. `claim_constraints` carries attribution and prohibited fields per claim_id.
A later lens of the same `project_id` is a pointer plus lens instruction, not a second
biography. Attribution / DO NOT CLAIM ACC ids in WE are metadata on the preceding story,
not accomplishments.

## Intentionally omitted fields (Cluster C item 11, 2026-08-08)

The packet schema does **not** include name, contact, location, education line, or
historical job titles/dates. That is deliberate: those values are static PII /
ground-truth identity fields with zero JD-specific reasoning value, and sending them
into a cloud author call is unnecessary risk.

Closed-world compose may leave digest-template placeholders (`# [Name]`, `[Location]`,
`[Degree]`, `### [Title] | …`). The canonical fix is **not** expanding the packet —
it is `scripts/apply_resume_header.py`, which `author_from_packet.py --verify-only`
runs before lint. Do not invent header content in the cloud author session.
