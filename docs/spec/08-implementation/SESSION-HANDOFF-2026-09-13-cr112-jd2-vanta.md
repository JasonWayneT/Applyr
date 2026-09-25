---
status: session_handoff
created: 2026-09-13
from: Cursor (Grok 4.6)
candidate: cr112-integrated-validation-candidate
head: baec191
prior_head: 257b003
do_not: push, merge to main, touch live submissions, copy production SQLite, call paid APIs
cr112: OPEN
daily_use_ready: no
---

# Session handoff — 2026-09-13 CR-112 digest Story 8.3 + Vanta JD 2

Started from clean local HEAD `257b003` on
`cr112-integrated-validation-candidate`. Did not reset earlier.
Left repo-root `cr112-selection-closed-world-design` and
`cr112-story71-72` untouched.

## 1. Confirmed ancestry

`git merge-base --is-ancestor` of HEAD at session start:

| SHA | Role | Ancestor of `257b003` |
|---|---|---|
| `520fc17` | next-session brief from `b0e732e` | yes |
| `ac4384f` | Story 8.2 identity fail-closed | yes |
| `257b003` | closeout stamp | yes (was HEAD) |

Local chain (newest first) through this session:

```
baec191 fix: tell Stage 1 authors not to restate resume bullets in the letter
257b003 docs: stamp closeout HEAD on the CR-112 session brief
f808bb5 docs: record CR-112 session closeout after Stories 8.1 and 8.2
ac4384f fix: fail closed when practice identity is missing
bf84afe docs: record Story 8.1 unqualified follow-up QA PASS
520fc17 docs: hand off CR-112 next session from b0e732e
```

Do not reset to `b0e732e`.

## 2. Digest story (8.3)

**Design:** DR-001 ACCEPT WITH CHANGES
[Review](ffcef2c9-5020-4992-9558-c6feb91f7997). Locked one bullet in
digest §5 (250 chars). Detector unchanged. Not a CR-097 promote.

**Commit:** `baec191` (`FR-319` / `AC-417`)

**Tests:** generate_digest + build_authoring_prompt SYSTEM BLOCK
contain both locked clauses. Negative control: incidental "resume" /
"cover letter" wording fails `contains_pair_restatement_instruction`.
149 tests in QA pass (digest, author_from_packet, linter, identity).
Digest 9805 / 10000, version `9634969118ac5d3d`.

**QA:** PASS [Review](de184edd-f4e3-4249-88ce-193500cb8161).
`submission_linter.py` zero diff vs `257b003`.

**JD 2 product finding:** first-draft Vanta still restated 13 shared
6+ word sequences. Digest instruction did not prevent the Camunda-class
defect on the next JD. Detector still caught it. Authoring prevention
is incomplete.

## 3. JD 2 selected and why

**Vanta** — Senior Product Manager, Integrations Delivery.
Practice folder (gitignored):
`data/authored_drafts/vanta_cr112_proof/`
Copied `Original_JD.txt` only from main-repo
`data/archive/submissions/vanta/`. Did not read archive Resume/CL.

Why this JD, not a likely pass:

- Materially different from Camunda (compliance integrations catalog,
  APIs/auth/permissions, partner activation vs BPM/Java/distributed
  messaging).
- Not SupplyHouse.
- Soft stretches: catalog ownership (evidence_level 2), API/auth
  fluency (evidence_level 2), design pairing in responsibilities,
  security-domain product vs InfoSec-partner history.
- Tests a different mix than Camunda's technical ranking miss.

Stage 0: Tier 2, fit_score 77, confidence 94, `identity_source=we`.
Isolated review DB:
`%TEMP%\cr112_vanta_jd2_review.sqlite`.
No production SQLite. No synthetic identity.

## 4. Untouched first-draft scores and qualitative verdict

Baseline (pre-header, pre-correction) hashes:

```
Resume.md:            063bdd465195e028b511135738142c62becfa24f1fa6c7dfeb94b79a9f4ff2aa
CoverLetter.md:        06b9f7747ef67e3e72c8b5402a43048029288fe217a7ad92e971f7c9c91a8d2c
claim_provenance.json: cd6ca2f3a0ad4e19cd4d0504684619cd6a1a1751c97cd5d6cba9734d7f1dbbcc
```

Copies: `%TEMP%\vanta_jd2_baseline\`

Independent HM read [Review](53157efb-d61b-4b24-ab44-83686a2c56af):

| Doc | Score | Floor | Verdict |
|---|---|---|---|
| Resume | 65 | 70 | below floor |
| Cover letter | 75 | 65 | above floor; CL-012 still a structural miss |

**FIRST_DRAFT_ADEQUATE.** Hook is strong. Attribution clean. Extra-packet
none. Heavy resume↔letter restatement (13 `LW-009-PAIR` sequences).
Packet AI bridges `ACC-179-ROADMAP` / `ACC-120-AIRESEARCH` unused.
SQL fluency in summary not backed by a resume bullet. Corrections
were judged targeted, not a rewrite.

## 5. Recovery and whether the workflow handled it

Supported paths used:

1. Stage 0 `requirement_extraction_review` pause (18 items). Filled
   buckets. After consume, a later resume re-asked extraction; restoring
   the consumed file onto the live import unblocked it. **Loop is a
   real ops finding:** consumed review is not reused automatically.
2. Stage 0 `cost_authorization` (unknown providers). Manual
   `stage0_cascade_import.json`. Zero paid calls.
3. Stage 1 verify FAIL: `CL-012` + `LW-009-PAIR`. Error text:
   `author_from_packet.run_verify_only FAILED — fix docs using packet+digest only`.
   Identity header applied via Story 8.2 (`identity_source=we`).
4. Targeted letter rewrite (pair + closer only). Resume body not
   rewritten to chase 70. Stage 1 then PASS.
5. Truth/HM WARNs disposed with real reasoning (extra-catalog unused
   claims `NOT_APPLICABLE`; LW-021 `FALSE_POSITIVE`; qualitative
   `hm.critical_read` accepted).
6. Honest first-draft scores written to `draft_manifest.json` (65 / 75).
7. Mech BLOCK `mech.rubric_floor.resume`:
   `'rubric_score.resume.total' 65 is below the 70 CONVERT-READY floor`.

**The system identified the correct cause** (resume below 70) and
parked Stage 2 at `NEEDS_DISPOSITION` with a BLOCK. Policy/Stage 3
locked. Did **not** HAR. Did **not** inflate to 70. Workflow did
**not** reconstruct receipts by hand.

PDFs compiled in practice anyway: Resume 1 page, Cover letter 1 page,
`page_counts_ok=true`. Archive-practice skill says md-only; compile
still ran and passed.

Parked state: `NEEDS_DISPOSITION` / mech / `mech.rubric_floor.resume`.
Leaving it blocked is the Story 8.1 proof on JD 2.

## 6. Evidence-selection findings (Vanta)

Used: ACC-102-INT, ACC-113-REBUILD, ACC-103-ROADMAP,
ACC-184-INCIDENT-TRIAGE, ACC-109-SYNTHESIS, ACC-112-COMPLIANCE,
ACC-107-COMPLIANCE, ACC-202-DELIVERY, ACC-302-SALESFORCE,
ACC-301-AUTO, ACC-121-SQLFOOTPRINT (letter).

Unused stronger packet evidence: ACC-179-ROADMAP and
ACC-120-AIRESEARCH for the JD's "open to using AI" preferred item.
That is a first-draft quality miss, not extra-packet.

Coverage heuristic flagged ACC-103-SEC, ACC-117-PENDO, ACC-401-AITOOLS
with `in_packet: false`. Correctly not forced in.

No extra-packet provenance IDs. Optimization bar / utilization / ATS
contract passed after draft.

## 7. Ranking investigation (no implementation)

Doc:
`docs/spec/08-implementation/CR-112-ranking-investigation-savings-vs-messaging.md`

Camunda distributed-systems item: SAVINGS 8330 picked vs RabbitMQ 4860
and Kafka 3766 cutoff. Cause class: full-JD `jd_score` plus weak
`systems`/`optimization` overlap, not an explicit metric-size term.
Capability boost did not fire.

Pearl/SupplyHouse SAVINGS remain negative REPLACE controls.
Two metric-should-win cases: cost-reduction items; ARR/reliability
items. Rule is not "technical always beats metrics."

Do not change the formula until this recommendation is independently
reviewed.

## 8. Model calls, spawns, tokens, cost

| Item | Count / note |
|---|---|
| Paid API calls | 0 |
| Cost applicability | none incurred; unknown is not recorded as $0 |
| Stage 0 providers | none configured; local NLP + failed LLM fallback; cascade import |
| Spawns this session | 4: design `ffcef2c9`, QA `de184edd`, Stage 1 author `650653c2`, qualitative `53157efb` |
| Digest size | 9805 chars, ~2451 tokens |
| Packet | practice Vanta `authoring_packet.json` (gitignored) |

## 9. Remaining blockers before JD 3 and supervised batch

- CR-112 still open. Not daily-use ready. Do not upload.
- Vanta JD 2 parked on `mech.rubric_floor.resume` BLOCK at Resume 65.
  Next recovery is a real resume edit (`RESOLVED_EDIT`), not HAR and
  not a 65→70 bump.
- Lean-digest pair line did not stop first-draft restatement. Decide
  whether JD 3 waits on a stronger authoring control or accepts
  detector-after-draft as the backstop.
- Ranking formula unchanged. Camunda SAVINGS-vs-messaging defect
  still in packet builder.
- Stage 0 extraction-review consume loop: live import must be restored
  after consume if Stage 0 restarts. Not fixed.
- No supervised batch. No push. No merge to main.

## 10. Durable paths

- This file.
- Story 8.3 design:
  `docs/spec/08-implementation/CR-112-lean-digest-pair-restatement-design.md`
- Ranking investigation:
  `docs/spec/08-implementation/CR-112-ranking-investigation-savings-vs-messaging.md`
- Tracker:
  `docs/spec/08-implementation/CR-112-stage0-3-reliability-quality-tokens-epics.md`
- Practice evidence (gitignored):
  `data/authored_drafts/vanta_cr112_proof/`
  `data/authored_drafts/camunda_cr112_proof/` (do not rerun solely to
  replace Resume 68)

Next reader: either independently review the ranking recommendation,
or resume Vanta only via a genuine resume-quality `RESOLVED_EDIT` that
can honestly clear 70, or start JD 3 on a third archived JD with the
same isolation rules. Do not call the candidate ready.
