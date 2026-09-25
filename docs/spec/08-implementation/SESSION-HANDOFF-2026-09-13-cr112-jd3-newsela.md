---
status: session_handoff
created: 2026-09-13
from: Cursor (Grok 4.6)
candidate: cr112-integrated-validation-candidate
started_from: c254524
story84_commit: 81b2739
do_not: push, merge to main, touch live submissions, copy production SQLite, call paid APIs, HAR a floor BLOCK, begin another JD
cr112: OPEN
daily_use_ready: no
batch_readiness: NOT_READY
jd3: newsela_cr112_proof
jd3_status: BLOCKED_ON_RUBRIC_FLOOR
---

# Session handoff — 2026-09-13 CR-112 Vanta adjudication, ranking corpus, JD 3 Newsela

Started from clean candidate HEAD `c254524` on
`cr112-integrated-validation-candidate`. Did not reset. Did not push.
Did not merge. Did not upload. Did not use production SQLite. Paid API
calls: 0. Extraction-review restart `81b2739` and the no-more-digest
decision remain accepted. Detector plus bounded recovery preserved.

CR-112 remains open. The candidate is not daily-use ready. Closeout
is one local documentation-and-characterization commit. No ranking
formula change. No score-provenance implementation. Newsela remains
blocked.

## 1. Blind Vanta resume adjudication

Blind reviewer [51bee1b0](51bee1b0-e969-4cc0-af2e-5b9bfcfa27cc)
received only the corrected Vanta resume, JD, `data/conversion_rubric.md`,
packet, and provenance. Prior 65/68/70 totals, scorecards, desired
outcome, and completion stakes were not provided.

| Criterion | Score | Cited basis (short) |
|---|---|---|
| R1 | 10 | Clean single-column ATS template |
| R2 | 10 | ~58% keywords; APIs/auth/permissions absent honestly |
| R3 | 13 | Title + seniority; no above-the-fold outcome metric |
| R4 | 8 | One of six Cision bullets is Tier 1; ~200 SQL DBs are unpaired scale (Tier 3, 1 pt), not an outcome |
| R5 | 10 | Prioritization + GTM; no Experimentation |
| R6 | 8 | Mostly at-level |
| R7 | 10 | Summary SQL backed by the ~200-database bullet |
| R8 | 2 | Partners named; no buyer/motion/ARR |
| **Total** | **71** | `10+10+13+8+10+8+10+2=71` CONVERT-READY |

Scale vs activity vs output vs outcome: ~200 customer databases =
unpaired **scale**, not activity, not output, not an outcome. No
criterion was raised because another improved.

Sidecar (gitignored):
`data/authored_drafts/vanta_cr112_proof/reviews/blind_adjudication.json`

## 2. Vanta completion

Blind 71 >= 70. Retain `PRACTICE_COMPLETE`. Did not average 68/70/71.
Did not choose the more favorable score as a decision rule; the rule
was blind-or-reopen. `mech.rubric_floor.resume` was not reopened. No
additional Vanta edit.

Durable closeout no longer claims Vanta “honestly closed” because the
implementer rejected 68. It remains complete **because the blind score
was 71**.

## 3. Additional Vanta edit

None.

## 4. Score-provenance design and review

File: `docs/spec/08-implementation/CR-112-score-provenance-design.md`
IDs: `FR-322` / `AC-420`. Story 8.6. **Design only. Not implemented.**

Proven gap: `draft_manifest.json.rubric_score` cannot distinguish
author vs correcting implementer vs independent blind vs stale
document hash vs conflicting current scorecards. `--audit` only
catches cloned totals across JDs.

Proposed low-token contract:

- Append-only `reviews/rubric_scorecard.json`
- Rubric sha256, timestamp, `reviewer_role`
  (`authoring_session` | `correcting_implementer` | `independent_blind`)
- Document hashes bound to the score
- Criterion breakdown plus citations
- Mandatory independent blind only in Resume `[67,73]` / Cover `[62,68]`
- Fail-closed: never average, never `max()`. Blind below floor reopens.
  Stale hash blocks. No agent-per-document default.

Independent design review
[5dc974ec](5dc974ec-cfc6-43fc-bd4d-d220f18352cf): **ACCEPT. Do not
implement this pass.** Weakest point: blindness is a prompt exclusion,
not mechanical. Follow-up: require `spawned_by` run-id distinct from
author/implementer rows.

## 5. Ranking characterization corpus and review

File: `scripts/test_cr112_ranking_characterization.py` (registered in
`scripts/run_all_tests.py`). IDs: `FR-321` / `AC-419`. Story 8.5.
Formula unchanged.

Live formula still:
`total = capability_boost + int(round(overlap * 1000)) + jd_score`
(`jd_score` only when `jd_profile is not None`).

Camunda-like isolated item **reproduces the defect**: SAVINGS 8335
beats RabbitMQ 4860 and Kafka 3769. If SAVINGS is slot 1, tests record
`known_defect` / `camunda_savings_vs_messaging` and **do not** assert
that rank as desired.

Other fixtures: direct cost-reduction (SAVINGS should win, hard
assert); ARR/reliability (metric claim beats process-only); Pearl
(SAVINGS total 0); SupplyHouse REPLACE keeps SAVINGS out; near-tie
stays stable (`compare_pair` 4164 vs 4165 does not REPLACE).

Tests: **12/12 OK** (re-run 2026-09-13). Independent corpus review
[31c12c40](31c12c40-ee42-4920-8db0-518efef1c113): **ACCEPT**. Distinguishes
item semantics from broad full-JD overlap. Formula change still waits.

Investigation doc updated:
`docs/spec/08-implementation/CR-112-ranking-investigation-savings-vs-messaging.md`

## 6. JD 3 selection rationale

Archived real JD, JD-only copy from
`data/archive/submissions/newsela/Original_JD.txt`. Did **not** inspect
archive Resume/CL.

Practice folder: `data/authored_drafts/newsela_cr112_proof/`
JD sha256: `0b4ba597837caf9856cf3dfc4fd4a22d9860eeac0e72c14b45729c5382ab5ffc`

Why Newsela (Product Manager): discovery-to-launch, classroom customer
insight, prioritization, marketing/success partners, data-driven
opportunity. Different from Camunda (distributed systems) and Vanta
(compliance integrations/API/catalog). Not SupplyHouse. Not an easy
pass: design/SME pairing is a real soft gap (no design team; ACC-185
forbids claiming discovery); EdTech/K-12 is a preferred stretch;
AI-forward team maps to ACC-120 CONTRIBUTED plus ACC-401, not AI/ML
product lead.

Stage 0: extraction review consumed (Story 8.4 path). Review Center
`skill:edtech` answered `BAD_DATA` (domain, not a named tool). Cost
authorization filled; gate NONE; design pairing evidence_level 2 SOFT.
**PASS, Tier 1, fit 79, confidence 97, `identity_source=we`.** Local
worktree sqlite only, not main-repo production DB. Paid calls: 0.

## 7. Untouched JD 3 first-draft artifacts, scores, qualitative verdict

Author spawn [ce70c573](ce70c573-9b07-4689-a532-5298cf2753a1) from
`authoring_prompt.md` only.

Untouched first-draft hashes (pre-header; still byte-identical in
`stage1_first_draft/`):

```
Resume.md:            a927dbfa9548e138ea3379364beb7589843fd3d4f6a418cee7dee93898c7aa81
CoverLetter.md:        fd921ab09c3c1612b9958d74559580c49da0db3947dda79208561aa7b37b4795
claim_provenance.json: 42025449e6cc7efc7f5e3f17f08d906825e41f242b2cb1a21047610168f8c3ff
```

Independent qualitative reader
[adef9c23](adef9c23-397e-4ce3-8744-6eb88b4f6d23) on the post-header
first-draft docs:

**Resume 61 / Cover 80. Resume below 70 blocks.**

| R | Score | Weakness |
|---|---|---|
| R1 | 10 | |
| R2 | 10 | features/impact/discovery/design cannot be added honestly |
| R3 | 11 | no outcome metric above the fold |
| R4 | 7 | all 6 Cision bullets activity/output; outcomes only in ZTS |
| R5 | 6 | no Experimentation; GTM weak on resume; ACC-185 forbids discovery |
| R6 | 8 | |
| R7 | 8 | “full product lifecycle” weakly evidenced on resume |
| R8 | 1 | partner names only |
| C1 | 20 | domain hook, not Newsela-specific |
| C2 | 20 | dense, reframed |
| C3 | 15 | |
| C4 | 18 | |
| C5 | 7 | no closer; duplicate header after H-001 stack |

No design-team claim, no EdTech ownership, no AI/ML product lead, no
ACC-185 discovery claim. Extra-packet: none.

Ranking: scaling required item picked `ACC-218-SCALING` (OBSERVED,
empty `allowed_claims`) + `ACC-301-AUTO`. Author used AUTO (ZTS) and
skipped OBSERVED SCALING. That is first-draft utilization plus a
ranking nomination of non-claimable evidence, not a Camunda-class
SAVINGS/messaging miss.

Stronger packet evidence left unused on purpose: ACC-218 must not be
owned. ACC-102 40% drop-off is **not in the packet**.

First-draft mechanical FAILs: CL-012 closer missing; LR-026 unverified
tool (`epic` in “epic and story” matching Epic EHR); Product Lifecycle
lacked resume provenance; unbracketed identity placeholders.

## 8. Recovery steps and final JD 3 status

Supported recovery only (packet + digest + WE identity helper). No
receipt surgery. No HAR. No score inflation.

Mechanical `RESOLVED_EDIT`:

- Removed `Google AI Studio` (not in ACC-401 excerpt).
- Reworded Agile `epic` to `work-item` (LR-026 false positive).
- Folded packet ACC-104 (CONTRIBUTED, ~700 accounts off deprecating
  infrastructure) into the PI-planning bullet so Product Lifecycle has
  resume provenance. Shortened to pass CW-003 40-word cap. Pair
  phrasing differentiated from the letter.
- Added Analytics to skills (Pendo/SQL packet evidence). Did **not**
  add Security (benefits “financial security”) or Support (extra-packet
  ACC-108).
- Cover: stripped leftover placeholder so H-001 would not restack;
  applied WE header/sign-off via `load_real_header`; CL-012 closer
  using the `I would` provenance exemption.

Identity-path defect (unimplemented; not a Newsela scoring failure):
`apply_resume_header` skipped unbracketed placeholders (first-name
heading plus literal `Location | Email | Phone | LinkedIn`). H-001
then injected the real WE header above the leftover labels. Session
repair used `load_real_header` from gitignored WE. Canonical workflow
did not prevent the stack. No synthetic identity. No SQLite. Stub:
`docs/spec/08-implementation/CR-112-unbracketed-placeholder-header-stack-defect.md`.
Do not fix in this closeout.

After Analytics edit, Stage 1 receipt went STALE; `--resume`
re-validated (detector + bounded recovery). No manual hash edit.

Post-recovery implementer score (not averaged with 61):

**Resume 62** (`10+10+11+7+6+8+9+1`). R7 8→9 only because ACC-104 now
backs the lifecycle claim. R4 stayed 7. R5 stayed 6.
**Cover 82** (C5 7→9 for closer + single header).

`draft_manifest.json` records 62/82 with `verification_passed: true`.
Mech BLOCK: `mech.rubric_floor.resume` — `'rubric_score.resume.total' 62
is below the 70 CONVERT-READY floor`. Disposition left **null**. No HAR.
No further honest one-page outcome metric exists in this packet.

**Final JD 3 status (preserve exactly):**

- untouched first draft Resume **61** / Cover Letter **80**
- corrected Resume **62** / Cover Letter **82**
- workflow `NEEDS_DISPOSITION`
- `mech.rubric_floor.resume` remains unresolved (null; BLOCK)
- no HAR
- not sendable
- no honest one-page packet-supported correction was identified

This is **not** a pipeline failure merely because the evidence ceiling
is below 70. Applyr blocked rather than padding or exaggerating. That
floor block is the successful behavior. Separately: first-draft
mechanical defects (CL-012, LR-026 `epic` false positive, missing
lifecycle provenance, unbracketed identity) and the header-stack
defect above are real pipeline/authoring gaps. `check_workflow_complete:
NO`. Do not finalize.

Current (corrected, not first-draft) hashes:

```
Resume.md:            50edbd444fa022d05068ae09dfacad6e6a480665c26e432de9034df3ffc09f35
CoverLetter.md:        7284c8212ba865d623b11aa678fa14cfaca2f9d3b0db7d6f5748ff9e67486098
claim_provenance.json: d0fb00b6c4dda1fc098770bfc55e81576d45110600ceeb91950525fd8c416c0c
```

## 9. Tests and independent review identifiers

| Item | ID / result |
|---|---|
| Vanta blind adjudicator | [51bee1b0](51bee1b0-e969-4cc0-af2e-5b9bfcfa27cc) Resume 71 |
| Vanta prior independent 68 | [12a050f9](12a050f9-c1b1-49fb-b8ae-80a26588566c) recorded, not selected |
| Score-provenance design | [5dc974ec](5dc974ec-cfc6-43fc-bd4d-d220f18352cf) ACCEPT |
| Ranking corpus | [31c12c40](31c12c40-ee42-4920-8db0-518efef1c113) ACCEPT |
| Ranking tests | `test_cr112_ranking_characterization.py` 12/12 OK |
| Story 8.4 extraction restart | [0139ffbf](0139ffbf-80e9-4b70-85e0-34f3889cbdae) QA PASS; [c7816cb7](c7816cb7-8ef5-4726-88e9-a5614c62d7e1) Security CLEAR |
| Newsela author | [ce70c573](ce70c573-9b07-4689-a532-5298cf2753a1) |
| Newsela first-draft scorer | [adef9c23](adef9c23-397e-4ce3-8744-6eb88b4f6d23) 61/80 |

## 10. Model calls, spawns, estimated token use, cost

- Paid Applyr APIs: **0**. Stage 0 cascade cost class unknown → manual
  import. `api_cents` is not 0. No silent free→paid fallback.
- Cursor Task spawns: 51bee1b0, 31c12c40, 5dc974ec, ce70c573, adef9c23
  plus this parent session (Grok 4.6).
- Newsela `authoring_prompt_meta.json` estimate ~13778 tokens
  (bytes/4 style).
- No additional paid model calls after first-draft authoring.

## 11. Exact commits and ancestry

Parent: `c254524` (`docs: record Vanta JD 2 closeout and reviewed
digest/ranking findings`). Ancestry:

`baec191` → `a435a80` → `81b2739` → `c254524` → this closeout commit

This closeout is characterization and design only. Practice folders
stay gitignored. Do not push.

## 12. Batch-readiness recommendation

**`NOT_READY`**

Not `SUPERVISED_SMALL_BATCH_READY`. Three JDs did show fail-closed
behavior and supported bounded recovery (Camunda ranking defect
characterized, Vanta floor dispute resolved by one blind read, Newsela
floor BLOCK left standing). That is not enough:

- Live ranking formula still nominates the known Camunda defect and,
  on Newsela, nominated OBSERVED ACC-218 with empty `allowed_claims`.
- JD 3 first draft was 61. Mechanical recovery was not modest (identity
  stack, CL-012/provenance closer dance, LR-026 epic false positive,
  lifecycle provenance, Analytics skill). After recovery the resume is
  still 62 with no honest packet outcome that can clear R4.
- Score provenance is still design-only, so a 70-vs-68 class dispute
  would recur.
- Identity helper still misses unbracketed placeholders.

Not `DAILY_USE_READY`. Do not recommend unattended batch. Do not send
Newsela. Do not call the candidate ready.

Next toward supervised small batch, in order: ranking formula change
with this corpus as characterization plus desired-rank tests; narrow
`apply_resume_header` match for `Location | Email | Phone | LinkedIn`;
implement the score-provenance contract (Story 8.6). Not another JD.

## 13. Durable paths

- **This file** (canonical for this pass).
- Header-stack defect (unimplemented):
  `docs/spec/08-implementation/CR-112-unbracketed-placeholder-header-stack-defect.md`
- Vanta closeout:
  `docs/spec/08-implementation/SESSION-HANDOFF-2026-09-13-cr112-vanta-closeout.md`
- Score provenance:
  `docs/spec/08-implementation/CR-112-score-provenance-design.md`
- Ranking investigation + corpus:
  `docs/spec/08-implementation/CR-112-ranking-investigation-savings-vs-messaging.md`
  `scripts/test_cr112_ranking_characterization.py`
- Tracker:
  `docs/spec/08-implementation/CR-112-stage0-3-reliability-quality-tokens-epics.md`
- Practice evidence (gitignored):
  `data/authored_drafts/vanta_cr112_proof/`
  `data/authored_drafts/newsela_cr112_proof/`
  `data/authored_drafts/camunda_cr112_proof/`
