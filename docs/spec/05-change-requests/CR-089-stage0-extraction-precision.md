# CR-089: Stage 0 Extraction Precision (False Tier 1 / Body Industry / People-Mgmt / Benefits-as-Reqs)

## Metadata
- **Status**: Proposed (do not implement in the 2026-08-14 send batch)
- **Date**: 2026-08-14
- **Source**: Human Stage 0 review of the 2026-08-14 CSV batch; same defect class on the prior Claude batch
- **Related**: CR-086 (header/boilerplate noise), CR-068 (requirements section extraction), CR-027 (industry blocklist, header-only), `scripts/stage0_prefs_gate.py` people-mgmt regex
- **Requirement IDs**: none yet

## Problem
Mechanical Stage 0 still over-promotes JDs that a human Skip/Tier-2's. Header-alias and boilerplate filters (CR-086 / 2026-08-10 remediations) did not stop it. Recurring classes:

1. **False Tier 1** — thin or loosely anchored JDs score as clean (Penguin OriginAI, PineQ, QuinStreet this round).
2. **Blocked industry in the JD body** — Ad Tech / similar terms below the 600-char header scan (`industry_gate.batch_industry_blocked` is company + title + header by design).
3. **People-mgmt phrasing missed** — e.g. "managing multidisciplinary teams" / "team of project managers" does not match `_PEOPLE_MGT_REQUIRED_RE` (direct reports / manage a team of N engineers).
4. **Benefits / EEO / salary-tool lists scraped as requirements** — Oracle/Microsoft-style benefits blocks land in `required`.
5. **Empty extraction** — Expel / Orion / Grey Parrot-class empty buckets. Packet Rule 6 fail-closes later; Stage 0 can still emit a misleading Tier.

Human review caught this round. The harm is an agent drafting from a false mechanical Keep before Jason sees the table.

## Decision (recommended; not landed)

Do **not** start another header-alias round. That is the 08-10 approach and the same classes came back.

Land these as separate, measured slices:

1. **Benefits/comp/EEO section exclusion** before itemizing required (expand ignore-headers + item denylist with this-batch fixtures).
2. **People-mgmt phrase widening** with negative-context tests so "manage stakeholders/roadmaps" still passes.
3. **Industry block: full JD body for high-precision terms only** (e.g. `Ad Tech`), keeping header-only scan for terms that false-positive on client industries.
4. **Empty extraction cannot be Tier 1** (already extraction_empty → Tier 2). Consider Skip or a forced human-review flag when all buckets are empty on a non-thin JD.
5. **Tighten tag anchors** — `tags: modernization` / generic `data, infrastructure, security` must not mark `gap: false` without a distinctive claim id (CR-087 scoring is downstream; Stage 0 anchors are the leak).
6. Keep the human `--batch-table` as authority. Mechanical Stage 0 is a draft triage, not a send gate.

## Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC1 | Fixtures from this batch: benefits-block JDs do not put Oracle/Microsoft-tool benefits in `required` |
| AC2 | "managing multidisciplinary teams" (and 2–3 sibling phrases from the live miss) trip people-mgmt Skip; "manage stakeholders" does not |
| AC3 | Ad Tech in JD body (below header) Skip/block; a client-industry mention of a weaker term does not regress |
| AC4 | Empty required+preferred+responsibilities on a non-thin JD cannot be Tier 1 |
| AC5 | Existing `test_build_stage0_fit_gate.py` still passes; packet eval should-surface does not regress below the CR-086 bar (~30/35) |

## Out of Scope
- Tonight's send / already-authored folders
- LLM-primary JD extraction
- Replacing human Stage 0 review
- Packet scoring overhaul (CR-087)

## Next
Pick one slice (benefits exclusion or people-mgmt phrases) and land it with fixtures from the 08-14 Skips before the next authoring batch.
