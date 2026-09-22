---
status: implemented
date: 2026-09-21
implementation_plan: ../08-implementation/CR-122-unknown-tools-nonblocking-review-epics.md
related: CR-108, CR-109, CR-119, CR-121
---

# CR-122: Unknown JD tools default to work experience, Review Center does not pause Stage 0

## Decision sought

Stop treating "this posting named a tool that is not in `workExperience.md`" as a Stage 0 human gate. Default to WE. Do not speak to that tool on this JD. Keep a Review Center row so a missed WE entry can be added later. Do not write `No` as a permanent career fact.

Approve this spec before implementation.

## Problem

CR-108 `AC-363` pauses an opportunity whenever Stage 0 finds a named tool absent from verified ground truth. The UI helper on `No` is "Do not ask again." That answer writes `skill_memory.NOT_PRESENT` on a primary key and suppresses every future ask.

Live 2026-09-22 CSV queue: `ss_c_technologies` paused on Google Cloud / IBM Cloud (an OR-list of cloud vendors). `employers` paused on Delta Lake, Quicksight, Tableau, plus a junk "And Experience" card. `businessolver` paused on the company name as a skill. Thirty JDs with thirty unknown tools would be thirty pauses. Jason already authored hundreds of resumes by the older rule: if it is not in WE, we do not claim it, and we keep moving.

A learnable tool is not a standing exclusion. People-management is. IBM Cloud is not.

CR-121 already withholds authoring when a **required** named tool has evidence 0 / `NOT_PRESENT` (`paused_reason=conversion_risk`). Preferred tools and OR-lists should never use that stop, and they should not use a Review Center quiz either.

## Product outcome

Stage 0 uses WE and the skills catalog as the closed world.

- Unknown named tool: not evidence for this JD. No `claim_ids`. Evidence level 0. Packet must not copy the JD tool name onto a transferable bridge (existing `AC-456` cap, applied automatically, no tap required).
- Stage 0 does **not** raise `WAITING_FOR_INPUT` / `Stage0NeedsInput` for `skill_presence` cards.
- The CSV worker does **not** leave the pack paused `review_center` because those cards are open.
- Review Center still lists each unknown tool, grouped by canonical `skill_key`, with affected opportunities. That inbox is how a missed WE fact gets added later.
- `Yes` / `CONFIRMED_USE` still cannot author a claim (`FR-284`). The correction is: write the tool into WE (and catalog when it is a verified tool), then later runs treat it as known.
- `BAD_DATA` stays durable and suppresses junk extraction (`FR-287`).
- Required unknown named tools still withhold via CR-121 `conversion_risk`. They do not Skip. They do not become a "have you used IBM Cloud" pause.

Unanswered is the same as not in WE. Tapping `No` is not required and must not mint a forever `skill_memory` row.

## Behavior by case

| Case | Stage 0 | Authoring | Review Center |
|---|---|---|---|
| Tool in WE or skills catalog | Known documented | May be evidence if cascade finds it | No new card |
| Unknown, preferred / OR-list / not required | Continue. Score as undocumented | Author without that tool | One grouped card, non-blocking |
| Unknown and required named tool | `conversion_feasibility=risk` | Withhold. Queue `conversion_risk` | Same non-blocking card. No extra quiz |
| Extraction junk (`And Experience`) | Continue if it is not a required named tool | Author | `BAD_DATA` still available |
| Hard-gate review (`hard_gate_review`) | Still pauses `WAITING_FOR_INPUT` | Does not author until resolved | Unchanged |
| Requirement extraction review | Unchanged (out of scope) | Unchanged | Unchanged |

## Skill memory

Keep `skill_memory` for:

- `CONFIRMED_USE` / `VERIFIED_EVIDENCE` (attestation, still not authorable until WE)
- `BAD_DATA` (never ask this surface form again)

Do not write new `NOT_PRESENT` or `UNSURE_NO_REASK` rows from this flow. Absence is "not in WE today," which WE already states.

WE and catalog win over a leftover `NOT_PRESENT` row. If IBM Cloud is later added to WE or `skills_catalog.json`, Stage 0 treats it as known documented even if an old `NOT_PRESENT` row exists. Do not mass-delete history in v1.

`AC-363` is superseded. `FR-283` is narrowed: grouped Review Center occurrences remain; the pause and the forever-No do not.

## Review Center UX

The card is a later correction, not a gate.

Copy direction:

- Question: this posting named {tool}. It is not in work experience, so this JD will not use it as evidence.
- Primary actions: **I have used this** (`CONFIRMED_USE`, still routes to strengthen / WE update) and **Not a real skill** (`BAD_DATA`).
- Do not label `No` as "Do not ask again." If `No` remains in the pad for compatibility, it is a no-op equivalent to unanswered and does not upsert `skill_memory`.
- Group by tool. Thirty JDs naming IBM Cloud are one card with thirty affected opportunities, not thirty pauses.

Queue labels may stay. `Needs your answer` for skill cards is optional work, not a pipeline blocker. Hard-gate items in that queue still block their own opportunity.

## Queue and resume

`pipeline_queue._review_center_open_count` / `_review_center_should_promote` / `requeue_paused` must ignore open `skill_presence` (and `evidence_enrichment`) rows. Open `hard_gate_review` still blocks that slug.

Live packs already paused `review_center` with only skill cards (`businessolver`, `employers`, `ss_c_technologies`, and any like them) must become promotable on the next worker claim or `requeue` without re-answering those cards. Do not auto-`apply_anyway` conversion_risk parks. Do not unpause amplify if it is a different pause kind.

## Out of scope

- CR-109 extraction precision (junk "And Experience" / company-as-skill). Related, not this CR.
- Requirement extraction review templates (eso timeout).
- Raising or lowering the fit skip floor.
- Domain gazetteer.
- Building a WE editor inside Review Center. `Yes` still cannot write `workExperience.md`.
- Agy rubric hook (CR-121 AC-464).
- Changing CR-121 `conversion_risk` rules.

## Requirements and acceptance

| Requirement | Acceptance |
| --- | --- |
| `FR-357` Unknown named tools do not pause Stage 0 | `AC-465` A JD with an unknown preferred named tool (IBM Cloud-shaped OR-list) creates a `skill_presence` row, finishes Stage 0 without `WAITING_FOR_INPUT`, and does not set queue `review_center`. Authoring may proceed unless CR-121 `risk` fires. Fixture covers the live ss_c / employers shape. |
| `FR-358` Absence is WE, not a forever No | `AC-466` Scoring/packet treat the unknown tool as evidence 0 with no `claim_ids` without any Review Center tap. No new `skill_memory` `NOT_PRESENT` / `UNSURE_NO_REASK` row is written. A later WE or catalog add of that tool is treated as known documented even if an old `NOT_PRESENT` row exists. |
| `FR-359` Review Center remains a grouped correction inbox | `AC-467` Two opportunities naming the same unknown tool share one Review Center item (`review_key` / `skill_key`) listing both. Answering `BAD_DATA` still suppresses re-queueing that surface. `CONFIRMED_USE` still cannot enter the authoring map (`FR-284`). |
| `UX-001` Skill cards are optional, not a gate | `AC-468` Skill-presence copy does not tell the user the pipeline is waiting. `No` is not "Do not ask again." Hard-gate copy and pause behavior stay as CR-108. |
| `FR-360` Open skill cards do not hold the CSV queue | `AC-469` Worker / `requeue_paused` promote a `review_center` pause that has zero open `hard_gate_review` rows even if `skill_presence` is open. Live-shaped fixture: employers/ss_c skill-only pause becomes queued. `conversion_risk` and extraction-review pauses are unchanged. |

## Release

Docs and tests first, then the Stage 0 raise + queue promote change, then Review Center copy.

Independent QA: IBM Cloud-shaped preferred fixture must not pause; Dynamics-required fixture must still `conversion_risk` (CR-121); hard-gate fixture must still pause.

After code lands, one size-1 worker on a skill-only paused slug must claim it (or the next queued slug) without Jason tapping IBM Cloud.
