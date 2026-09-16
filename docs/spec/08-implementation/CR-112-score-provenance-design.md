---
status: implemented
created: 2026-09-13
from: Cursor (Grok 4.6)
candidate: codex/cr112-consolidation
originating_candidate: cr112-integrated-validation-candidate
related: CR-112, FR-322, AC-420
implement_this_pass: yes
do_not: majority-vote scores, spawn a reviewer per document, lower 70/65
---

# CR-112 score provenance — low-token contract

Implemented as CR-112 Story 8.6 on `codex/cr112-consolidation`
2026-09-15. The Vanta 70-vs-68-vs-71 disagreement is the proven defect.

## Question

Can the canonical workflow distinguish:

1. a rubric score entered by the document author
2. a score entered by the correcting implementer
3. an independent blind review
4. a stale score from an earlier document hash
5. conflicting current scorecards

## Pre-implementation behavior (proven defect)

Canonical object: `draft_manifest.json.rubric_score`. Shape check
requires `resume.total` and `cover_letter.total` as finite numbers.
Floor check (`FR-318`) reads those totals only.

There is no required:

- document sha256 bound to the score
- reviewer role
- timestamp
- rubric-file version
- criterion citations
- second scorecard slot

`--audit` compares byte-identical totals across *different* JDs via
`data/.rubric_score_history.json`. That catches cloned scorecards. It
does not catch two honest scores of the *same* document, and it does
not stale-out a total after `Resume.md` changes.

Vanta JD 2:

| Source | Resume total | R4 | Bound to hash? | Role recorded? |
|---|---|---|---|---|
| First-draft qualitative read | 65 | 10 | no | no (session prose) |
| Correcting implementer after `RESOLVED_EDIT` | 70 | 10 | no | no (overwrote manifest) |
| Independent qualitative reader | 68 | 8 | no | no (session only) |
| Blind adjudicator [51bee1b0](51bee1b0-e969-4cc0-af2e-5b9bfcfa27cc) | 71 | 8 | no | no until this design |

The workflow completed because the manifest said 70. The independent
68 never had a machine-readable place to live, so it could not reopen
`mech.rubric_floor.resume`. That is fail-open on disagreement.

Stale-hash is a sibling hole: an edit that does not rewrite
`rubric_score` keeps the previous total.

## Non-goals

- Majority vote.
- Agent-per-document default.
- Extra reviewers for scores with clear margin (example: 78 vs 70).
- Changing 70/65.
- Averaging two scorecards.
- Picking the higher of two current scores.

Normal completions stay one real qualitative read plus mechanical
gates.

## Implemented contract

Add one optional-then-required sidecar, not a new agent:

`reviews/rubric_scorecard.json` (append-only array). Each row:

```
{
  "schema_version": 1,
  "rubric_sha256": "<sha256 of data/conversion_rubric.md>",
  "scored_at": "<ISO-8601>",
  "reviewer_role": "authoring_session" | "correcting_implementer"
                   | "independent_blind",
  "document_sha256": {
    "resume": "<sha256 Resume.md>",
    "cover_letter": "<sha256 CoverLetter.md>"
  },
  "resume": {
    "total": 71,
    "breakdown": {"R1": 10, "R2": 10, "R3": 13, "R4": 8,
                  "R5": 10, "R6": 8, "R7": 10, "R8": 2},
    "citations": {"R1": "<quote>", "...": "..."}
  },
  "cover_letter": { "total": 80, "breakdown": {}, "citations": {} }
}
```

`draft_manifest.json.rubric_score` remains the completion input. It
must copy the *binding* scorecard row, including hashes. Mech rejects
the floor check when current file hashes ≠ scorecard hashes (stale).

Criterion citations are required only inside the boundary band below.
Outside the band, totals plus breakdown are enough.

### Reviewer roles

| Role | Who | When |
|---|---|---|
| `authoring_session` | Stage 1/2 qualitative reader who first scores the untouched draft | always |
| `correcting_implementer` | Same or later agent after `RESOLVED_EDIT` | only after docs change |
| `independent_blind` | Fresh agent given docs + JD + rubric + packet/provenance only | only in the boundary band |

Do not spawn `independent_blind` for every submission.

### Boundary band (mandatory independent read)

Resume band: `total` in `[67, 73]` (floor 70 ± 3).
Cover letter band: `total` in `[62, 68]` (floor 65 ± 3).

Trigger on the *current-hash* score, usually the implementer row after
a correction. If that total sits in the band, Stage 2 cannot complete
until an `independent_blind` row exists for the same hashes.

Clear margin (resume ≥ 74, or resume ≤ 66 with no claim that it
passes) does not pay for a second reader. Below-floor scores already
block via `mech.rubric_floor.*`.

### Disagreement routing (fail closed)

Compare only rows whose `document_sha256` matches the files on disk.
Ignore stale rows.

Let `S_impl` be the latest `correcting_implementer` or, if none, the
`authoring_session` total. Let `S_blind` be the `independent_blind`
total when the band required one.

1. Any current-hash total below floor → BLOCK. Do not average. Do not
   keep COMPLETE because a different row is higher.
2. If `S_blind` exists and `S_blind < floor` → reopen
   `mech.rubric_floor.resume` (or cover). Same rule as this session.
3. If `S_blind >= floor` and `S_impl >= floor` → COMPLETE. Record both
   rows. Manifest may keep `S_impl`; the sidecar is the audit trail.
4. Never `max(S_impl, S_blind)`. Never `(S_impl + S_blind) / 2`.
5. Conflicting current rows with no blind row, inside the band →
   incomplete, not "use the 70".

A later honest `RESOLVED_EDIT` may add a new hash-bound row. Old rows
become stale automatically. HAR is still forbidden for the floor.

### Token budget

Blind adjudication prompt: rubric + JD + one document + packet +
provenance. No handoff, no prior scorecards, no "completion depends
on this." One spawn only, and only in the band. That is the Vanta
adjudicator load, made mechanical.

## Independent design review (historical, 2026-09-13)

**Reviewer:** [Review](5dc974ec-cfc6-43fc-bd4d-d220f18352cf)
**Verdict at that checkpoint: ACCEPT. Do not implement in the JD 3 proof
pass.** The bounded implementation landed later on 2026-09-15.

Weakest point recorded: blindness is a prompt exclusion, not a
mechanical guarantee. Next story should require `spawned_by` run-id
distinct from author/implementer rows for the same hashes.

Band [67, 73] / [62, 68] accepted. Disagreement routing matches the
Vanta floor rule.

The defect is real, but the fix is a new completion contract plus
Mech findings. Shipping it before JD 3 would delay the product proof
this session is for. Record Vanta's blind 71 in prose/sidecar by hand.
Do not pretend the workflow already distinguishes roles.

## Story shape (bounded)

Story 8.6 / `FR-322` / `AC-420`:

- Scorecard schema + hash stale-out in `check_rubric_floors` or Mech.
- Band-gated requirement for `independent_blind`.
- Fail-closed disagreement: any current-hash below-floor total blocks.
- Tests: stale hash blocks; two current totals 70 and 68 block; 71
  blind with 70 implementer on the same hash completes; resume 78
  needs no blind row; no LLM in the helper.

Do not add reviewers to generate-submission-batch. Do not vote.

## Implementation record (2026-09-15)

Implemented as pure local completion checks:

- `scripts/contracts.py::check_rubric_score_provenance` validates current Resume/Cover Letter hashes, `draft_manifest.json.rubric_score.document_sha256`, and append-only `reviews/rubric_scorecard.json` rows.
- `scripts/workflow/runner.py` emits Mech BLOCK findings for stale, missing, below-floor, or disputed current-hash scorecards after rubric shape/floor checks.
- Boundary-band scores require a same-hash `independent_blind` row; clear-margin scores do not.
- Any current-hash score below the applicable floor blocks. No averaging, voting, or higher-score selection is allowed.

Verification:

- `python -m unittest scripts.test_contracts scripts.test_workflow_authority scripts.test_cr112_story71 scripts.test_stage0_evidence_cascade` => 208 tests OK.
- `python -m unittest scripts.test_cr112_story31 scripts.test_cr112_story35 scripts.test_cr112_story36 scripts.test_hm_critical_read_contract scripts.test_practice_identity scripts.test_cr112_ranking_characterization` => 123 tests OK.

No LLM, provider, or paid API call is made by the helper or tests.
