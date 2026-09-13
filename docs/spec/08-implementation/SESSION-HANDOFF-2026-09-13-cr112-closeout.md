---
status: session_closeout
created: 2026-09-13
from: Cursor (Grok 4.6)
candidate: cr112-integrated-validation-candidate
head: after ac4384f
closeout_commit: this file
prior_brief: SESSION-HANDOFF-2026-09-13-cr112-next-session.md
code_baseline_story_81: 0aaab87
story_81_qa: 3cd059c0-ba53-42b7-b66a-a6677a310de5
story_82_code: ac4384f
story_82_security: 375d080a-7767-489f-97b1-73cd9d4f650a
story_82_qa: caa75e98-aade-4c21-93c7-4e2140e147de
result: HANDOFF_RECORDED
do_not: push, merge to main, touch live submissions, write production SQLite, call paid APIs
cr112: OPEN
daily_use_ready: no
---

# Session closeout — 2026-09-13 CR-112 Stories 8.1 QA + 8.2 identity

Started from clean `520fc17` on
`.claude/worktrees/cr112-integrated-validation-candidate`.
Did not reset to `b0e732e`. Left repo-root
`cr112-selection-closed-world-design` @ `b5616c8` (dirty) and
`cr112-story71-72` @ `7bf6829` untouched.

## Story 8.1

Unqualified follow-up QA PASS on `0aaab87` after the added negative
controls. Review [3cd059c0](3cd059c0-ba53-42b7-b66a-a6677a310de5).
Tracker commit `bf84afe`. Floors stay Resume 70 / Cover Letter 65.
`PRACTICE_COMPLETE` still means the practice workflow finished, not
apply-ready. No HAR, no `--force` floor bypass, no exception path.

Camunda `PRACTICE_COMPLETE` at Resume 68 remains gitignored regression
evidence. Do not rerun Camunda solely to replace that artifact. Do not
inflate scores.

## Story 8.2

Design review [c3000eab](c3000eab-fd55-4c1f-b99d-d1433b864ebb)
ACCEPT WITH CHANGES, then two brief-driven corrections before code:

1. Synthetic env short-circuits before any WE read (tests must not
   ingest live PII). Then WE. Then fail closed. No SQLite in the
   document identity chain.
2. Fail before authoring: `run_stage1_prompt` must not mint
   `WAITING_FOR_LLM` when identity is missing. `run_verify_only` FAIL
   stays defense in depth.

Implementation `ac4384f`. Security CLEAR
[375d080a](375d080a-7767-489f-97b1-73cd9d4f650a). QA PASS
[caa75e98](caa75e98-aade-4c21-93c7-4e2140e147de). `SEC-006` /
`AC-416` implemented.

Env: `APPLYR_SYNTHETIC_IDENTITY=1` only. No CLI flag on
`run_submission.py`. Logs `identity_source=we|synthetic|missing` with
no name/email/phone/LinkedIn.

## Quality comparison (do not implement yet)

Live `data/authoring_defect_ledger.json` in this worktree is empty
(`occurrences: []`). Frequency below uses the Camunda proof plus the
documented 2026-07-20 9-JD restatement batch, not a live CR-097 count.

### Candidate A — digest line for `LW-009-PAIR`

- **Camunda defect prevented:** 3 verbatim resume/letter restatements
  (Java platform, Critical Save, PTO capacity). Caught later by
  `check_cross_document_repetition`; the digest has no LW-009-PAIR line.
- **Cause class:** instruction (digest completeness). Detector already
  exists.
- **Frequency:** Camunda x3 in one draft. CHANGELOG records the same
  class across a 9-JD batch before the pair check existed. Live ledger
  has 0 rows here, so do not treat this as a CR-097 promote.
- **First-draft improvement:** author sees the split-of-labor rule
  before drafting. Camunda still reached a clean pair via fix rounds;
  this shrinks those rounds.
- **False-positive / overfit:** low. Restates an existing mechanical
  check. Does not invent a Camunda-only rule.
- **Token impact:** about one to two digest sentences.
- **Smallest regression:** `generate_authoring_rule_digest.py` output
  contains the pair-restatement instruction; existing
  `test_submission_linter.py` LW-009-PAIR cases stay the detector proof.
- **Generalizes:** yes. Restatement is not Camunda-specific.

### Candidate B — ranking so `ACC-101-SAVINGS` cannot beat RabbitMQ/Kafka
on a distributed-systems JD item

- **Camunda defect prevented:** SAVINGS won Top-2 at score 8330 over
  `ACC-215-RABBITMQ` (4860, `top2_cutoff`) and `ACC-189-KAFKA` (3766)
  for "Strong understanding of distributed systems…".
- **Cause class:** ranking / packet construction. Combined score is
  `capability_boost + overlap*1000 + jd_score`. Metric-heavy claim text
  can outrank distinctive distributed-systems overlap. Not a digest
  one-liner.
- **Frequency:** one proven Camunda selection. Pearl / SupplyHouse
  SAVINGS are **negative controls for auto-replace**, not for this
  initial Top-2 pick. Live ledger 0. Do not special-case SAVINGS vs
  this JD sentence.
- **First-draft improvement:** higher. Wrong Top-2 evidence never
  reaches the author. LW-009 cannot recover Kafka if it is not in the
  packet.
- **False-positive / overfit:** high if the story is "demote SAVINGS on
  Camunda." Lower if the story is general: distinctive item overlap
  must beat metric-sized `jd_score` / boost when the JD item is a
  domain/capability ask, not a savings ask. Pearl/SupplyHouse must
  still refuse automatic REPLACE on metric size.
- **Token impact:** none in the author prompt if this stays packet-side.
- **Smallest regression:** fixture JD item "distributed systems" where
  RabbitMQ/Kafka tags beat SAVINGS for Top-2; Pearl-shaped SAVINGS vs
  PM remains not-REPLACE.
- **Generalizes:** only as a formula constraint, not as a Camunda
  exception.

### Recommendation (exactly one)

**Next story: Candidate A, digest completeness for `LW-009-PAIR`.**

Broader evidence and lower overfit. The detector already grades the
pair; the author never sees the rule. Ranking is the more severe
conversion risk when it fires, but it needs a formula diagnosis and
Pearl/SupplyHouse SELECT-vs-REPLACE tests before it is safe. Do not
bundle both. Do not mechanize LW-011 from one Camunda paraphrase.

## JD 2 readiness

Gates from the incoming brief:

| Gate | Status |
|---|---|
| Story 8.1 unqualified QA PASS | yes (`bf84afe`) |
| Practice identity in a clean isolated worktree | yes (`ac4384f` + tests) |
| Relevant tests pass | yes (10 identity; 202 combined with workflow/author/contracts) |
| No paid provider configured or called | yes |
| Candidate clean and isolated | yes, local only |

**Do not begin JD 2 in a closeout.** Next product-proof session can
start JD 2. A clean Camunda rerun would uniquely exercise floors +
identity on the JD that exposed them, but it would not replace the
historical `PRACTICE_COMPLETE` folder and would not test
generalization. JD 2 is the stronger next product proof. Preserve
Camunda as regression evidence. Do not inflate 68 to clear 70.

## Ancestry (local, unpushed)

```
ac4384f fix: fail closed when practice identity is missing
bf84afe docs: record Story 8.1 unqualified follow-up QA PASS
520fc17 docs: hand off CR-112 next session from b0e732e
b0e732e docs: record Camunda follow-up handoff and practice-identity design
0aaab87 fix: fail closed when rubric totals sit below CONVERT-READY floors
```

Plus this closeout docs commit after these notes land.

## No-cost / spawn evidence

- No paid APIs. No `call_llm`. Stage 1 stayed author-paste.
- Spawns: one Story 8.1 QA reviewer, one Story 8.2 design reviewer,
  one security reviewer, one Story 8.2 QA reviewer. One at a time.
  No per-JD agents. No full WE / context pack / claims catalog loaded
  into those reviewers.
- Python `.venv` was absent in this worktree; tests used system
  Python 3.12. Identity tests 10/10. Combined 202/202. Earlier Story
  8.1 focused 140/140. `run_all_tests.py` previously timed out
  `test_cr112_stage0_extraction_review` (unrelated).

## Remaining blockers to daily-use readiness

- CR-112 remains open. Candidate is not daily-use ready.
- First-draft quality: digest LW-009-PAIR still missing; ranking still
  lets SAVINGS beat distributed-systems evidence on Camunda.
- ATS `evidence_map` can still attach empty `allowed_claims`
  (Camunda `ACC-185-CUSTOMER-DISCOVERY`).
- Camunda practice folder is historical, below-floor, not send-ready.
- No merge to main. No push.
