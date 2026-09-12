---
status: in_progress
created: 2026-09-10
related: CR-074, CR-076–084, CR-097, CR-102, CR-108, CR-111
investigation: ./INVESTIGATION-2026-09-10-stage0-3-reliability-quality-tokens.md
contains: CR-112 (Stage 0–3 reliability, first-draft quality, token containment)
---

# CR-112 — Stage 0–3 reliability, first-draft quality, and token containment

**Handoff doc.** Investigation is complete; backlog corrected 2026-09-10 per Jason's review (see "Backlog corrections" below).

**Isolated verification (2026-09-10):** Epic 1 only, on branch `cr112-epic1` from `8bbc497`. Epics 2–6 remain planned and are not in this review. Checkboxes stay open. A landed-code summary does not establish that Stage 0–3 is ready. SupplyHouse is flagged and unresolved.

**Operating rule:** Applyr stays a composable *workflow*. One bounded author session after deterministic prep. Do not add agents, frameworks, or per-JD swarms. Do not weaken checks to get green tests. Do not treat valid JSON, known claim IDs, or exit 0 as semantic proof.

**Quality floor stays.** Token cuts come from removing duplicate context and unsafe fail-open patches, not from skipping truth review.

---

## Backlog corrections (2026-09-10, Jason's review)

Four corrections applied to the epics below, plus one gap closed. Recorded here so the reasoning isn't lost in the diff:

1. **Preserve meaningful review (Story 2.1).** The original draft said Stage 2 should default to `--resume` only — but this investigation's own F8 finding says `hm.critical_read` is a WARN placeholder, not a semantic review, and the drafting agent can auto-dispose it without ever actually reading the documents. Running mechanical checks (`--resume`) cannot substitute for assessing truth, relevance, and writing quality. Story 2.1 now scopes `--resume`-only to the mechanical subphases and keeps a real qualitative-read requirement in place.
2. **Audit the programmatic tests too, not just the fixture tier (new Story 4.3).** F4 gave the programmatic `CASES` tier a blanket KEEP because it calls production code. That's not sufficient on its own: `check_doc_003_forbidden_punctuation` and at least one sibling check catch *any* `runner.WorkflowError` as the expected outcome, so the test could pass because an unrelated upstream precondition failed first, without ever reaching punctuation validation. Calling production code establishes an exception path exists, not that the specific invariant fired.
3. **Describe token evidence accurately.** The investigation doc's token table labels several rows "measured" (e.g. `agent_context_pack.md` ≈ 64k, `workExperience.md` ≈ 34k) when the underlying method is bytes ÷ 4 — an estimate, not a measured token count. Separately, F1's harness-spawning path is confirmed to exist and be expensive; whether it actually fired during the specific session that burned Jason's five-hour allowance is unverified, not merely "observed risk." Both distinctions are corrected in the investigation doc.
4. **Keep selection explanations outside the author prompt by default (Stories 3.2/3.3).** A detailed per-candidate ranking audit trail is exactly the kind of content that caused F3's constraint-wipe bug in the first place (packet bloat under token pressure). The full diagnostic now lives in a separate file the Stage 1 author never loads; only a short reason-code enum is cheap enough to stay in the packet.
5. **Gap: fixing the generator doesn't repair what it already broke.** Story 1.2 explicitly excludes rebuilding SupplyHouse's already-wiped packet, but nothing else in the original backlog detected or recovered it either. New Story 1.4 adds a read-only audit across all live packets plus a human-reviewed (not automatic) recovery decision per affected folder.

---

```
Epic 1 (fail-open dirty patches)
  → Epic 2 (lean default / spawn containment)
  → Epic 3 (closed-world + evidence explainability)
  → Epic 4 (adversarial honesty)
  → Epic 5 (advisory composition texture)
  → Epic 6 (controlled evaluation)
  → Epic 7 (model-cost eligibility and telemetry)
```

**2026-09-11 design correction (Jason):** extra-packet is two defect classes, not WARN vs hard-stop. Design:
`CR-112-selection-and-closed-world-recovery-design.md`. Stories 3.0, 3.1, 3.5, and
3.6 each have independent QA PASS. Epic 3 integration PASS
(`d680faf4-4688-4ba6-8a64-0692f239b592`). Combined candidate starting at
`7bf6829` (local HEAD `165485f`): automated suite plus no-cost Stage 0→1
boundary passed. First-draft Stage 0–3 product proof remaining. Do not
mark CR-112 complete. Chain evidence:
`CR-112-reconciliation-2026-09-11.md` and
`SESSION-HANDOFF-2026-09-11-cr112-integrated-validation.md`.

CR-097 Epics 1–6 stay independent. CR-097 proposed Epic 7 is intake only and is superseded as a tracker by this file's Epic 3.

---

## Epic 1 — Close the two fail-open dirty patches, and repair what they already broke

**Depends on:** nothing. **Touches:** uncommitted Antigravity edits already in the tree.

**Definition of Done:** invented sequential IDs cannot attach a judgment to a requirement by list position; a packet that had to drop `claim_constraints` cannot be `ready`; already-shipped wiped packets are detectable by a read-only scan. SupplyHouse recovery is not on the active backlog (Jason, 2026-09-10: already corrected; do not rebuild, re-author, or request risk acceptance). Existing hash-suffix / unique-ordinal fallbacks remain.

### Story 1.1 — Reject invented sequential provider IDs

**Files:**
- Modify: `scripts/stage0_evidence_cascade.py` (`_resolve_item_id`, ~353–390)
- Modify: `scripts/test_stage0_evidence_cascade.py` (`test_invented_sequential_id_resolves_within_bucket`)
- Test: same file, plus a new case that shuffled content must not silently remap

**Acceptance:**
- `req-001` / `req-002` / `pref-1` against real `bucket:ordinal:hash` ids return `None` unless a unique hash or unique ordinal actually identifies one item.
- `validate_batch_response` then raises `unknown batch item_id` (or partial-missing) so the caller retries / falls back.
- Hash-tail (`len >= 8`) and unique suffix/ordinal fallbacks still pass their existing tests.
- A response whose `req-001` HARD reasoning names item two and whose `req-002` NONE names item one must not assign those gates by position.
- Isolated tests only. No live provider call.

**Dependencies:** none.
**Regression evidence:** existing cascade tests plus the new reject/shuffle cases. Archive replay harness (CR-108 Epic 7.3) is optional later, not this story.
**Status:** [ ] Documentation reconciliation only for location: implementation is on local `main` / this candidate (not only `cr112-epic1`). Cascade rejects invented `req-001` / shuffle remap; CHANGELOG names `FR-296`. Independent review ID not recorded; checkbox stays open.

### Story 1.2 — Do not ready a packet after dropping claim_constraints

**Files:**
- Modify: `scripts/build_authoring_packet.py` (~1522–1546)
- Test: `scripts/test_build_authoring_packet.py` (or nearest existing packet-assemble suite)

**Acceptance:**
- If excerpts are already at `_EXCERPT_MIN_CHARS` and estimated tokens still exceed `_TOKEN_BUDGET`, `packet_status` is `incomplete` with a recorded reason that names `claim_constraints` / budget, **or** a cheaper field is dropped first with a recorded reason (ATS-term padding, learned_examples already gone).
- `claim_constraints` is never silently replaced with `{}` while `packet_status=ready`.
- Isolated `assemble_packet` reproduction from the investigation (ready + empty constraints + tokens 2912) must fail after the fix.
- supplyhouse is **not** rebuilt in this story.

**Dependencies:** none. Can parallelize with 1.1.
**Regression evidence:** new unit test. Do not use a real employer folder as the fixture.
**Status:** [ ] Documentation reconciliation only for location: Rule 5 / no silent `claim_constraints` wipe is on local `main` / this candidate. Independent review ID not recorded; checkbox stays open. supplyhouse not rebuilt.

### Story 1.3 — Record the two patches in CHANGELOG + this tracker

**Files:** CHANGELOG.md (DRAFT), this file.

**Acceptance:** both behaviors named; no silent "resilience" language that hides fail-open.
**Status:** [ ] Documentation reconciliation only for location: CHANGELOG names Stories 1.1–1.3 (`FR-296`–`FR-298` / `AC-393`–`AC-395`) on local `main` / this candidate. Independent review ID not recorded; checkbox stays open.

### Story 1.4 — Detect already-wiped packets

Story 1.2 fixes the generator going forward. It does not rewrite packets already shipped with `packet_status=ready` and empty `claim_constraints`. This story is the read-only detector plus a one-time live scan. Per-folder recovery is not an automatic rebuild.

**Files:**
- New: `scripts/audit_packet_integrity.py` — read-only scan of `data/submissions/*/authoring_packet.json` for `packet_status=ready` with `claim_constraints` empty/missing while `evidence_map` or `soft_gaps` is non-empty.
- Modify: this file, to record the scan.
- Finding (not approval): [FINDING-2026-09-10-agent-packet-integrity-disposition.md](./FINDING-2026-09-10-agent-packet-integrity-disposition.md)

**Acceptance:**
- Detection is read-only: it reports affected folders and writes nothing.
- A `packet_integrity_disposition.json` sidecar is display-only. It does not unflag. It is not `run_submission` / Stage 2 authorization.
- Clean / flagged / unable-to-inspect are distinct. Unreadable packets (OSError, JSONDecodeError, UnicodeDecodeError), a missing root, and invalid field types are incomplete (exit 2), not a clean scan. One bad packet does not abort the others. An unreadable informational disposition sidecar does not abort scanning or clear a packet flag. An empty existing root may report zero inspected and must not imply safety.
- Run once against the then-current live folders; record the table below.
- Does not rebuild or finalize any submission as a side effect of running the detector.

**Dependencies:** Story 1.2 (fixed generator before any future rebuild someone explicitly requests).
**Status:** [x] isolated on `cr112-epic1`; Story 1.4 detector incomplete-inspection + R12 UnicodeDecode/split-field coverage accepted after independent review. SupplyHouse recovery remains off the active backlog. No rebuild. No re-author. No risk-acceptance request.

**Live scan (2026-09-10), `python scripts/audit_packet_integrity.py --root data/submissions`:** 7 packets scanned, **1 flagged**. Detector wrote nothing.

| slug | packet_status | constraint_count | estimated_tokens | evidence_map | soft_gaps | flagged |
|------|---------------|------------------|------------------|--------------|-----------|---------|
| arbiter | ready | 25 | 7705 | 22 | 5 | no |
| cdw | ready | 26 | 7473 | 21 | 2 | no |
| loot_labs | ready | 21 | 7624 | 18 | 5 | no |
| marlowe_companies_inc | ready | 26 | 7537 | 28 | 4 | no |
| pearl_com | ready | 25 | 7740 | 17 | 4 | no |
| supplyhouse | ready | 0 | 7227 | 20 | 9 | **yes** |
| trax_technologies | ready | 28 | 7923 | 23 | 6 | no |

**SupplyHouse (removed from active recovery backlog, 2026-09-10, Jason in chat):** "SupplyHouse was already corrected. Remove its recovery from the active backlog. Do not rebuild, re-author, or request risk acceptance. Keep the general regression tests and packet detector." That is not `HUMAN_ACCEPTED_RISK`. The detector may still flag the packet. Do not solicit option (b). Other six folders: no action.

**Separate finding:** an agent-written sidecar exists under the live flagged folder. Original stays local (gitignored). Git carries a sanitized fixture only. Not authorization. See the finding doc.

---

## Epic 2 — Make the lean path the only default spawn

**Depends on:** Epic 1 not required, but do not start if Jason wants reliability patches first.

**Definition of Done:** a default "process today's JDs" session cannot spawn a review agent or load WE/pack/AGENTS into Stage 1. Batch workflow remains opt-in and cannot load WE.

### Story 2.1 — Rewrite generate-submission Stage 0/2 prose to call the orchestrator

**Files:**
- Modify: `.codex/skills/generate-submission/SKILL.md` (canonical)
- Pointers already exist under `.claude/skills/`

**Acceptance:**
- Stage 0 section says: run `python scripts/run_submission.py data/pending_review/{slug}`. Do not re-derive fit from WE in the agent session.
- Stage 1 section says: paste `authoring_prompt.md` only. Forbidden loads listed: `agent_context_pack.md`, `workExperience.md`, `master_claims.json`, full `AGENTS.md`.
- **Stage 2 default is `--resume` for the mechanical subphases (truth/ats/mech/policy) only.** `--resume` alone does not satisfy `hm.critical_read` — running checks is not a substitute for actually assessing truth, relevance, and writing quality (this is F8: `hm.critical_read` is a WARN placeholder, not a semantic review, and the drafting agent must not silently self-dispose it as ACCEPTED_AS_CORRECT). The prose must require a real qualitative read (of the specific kind F8 describes — proof density, register, tailoring, no AI-tell shape) before `hm.critical_read` is disposed, whether that read is done by the drafting agent as a genuinely separate pass or deferred to Jason. Ladder-2 (multi-agent) review stays Jason-opt-in; this bullet is about not deleting the single-session qualitative read, not about restoring ladder-2 as default.
- `scripts/check_instruction_drift.py` still passes.

**Status:** [ ] Documentation reconciliation only: required Stage 0/1/2 language is present in `.codex/skills/generate-submission/SKILL.md` on this candidate (`test_cr112_lean_spawn.py`). Not planned. Independent review ID not recorded; checkbox stays open.

### Story 2.2 — Contain generate-submission-batch.js

**Files:** `.claude/workflows/generate-submission-batch.js` (`reviewPrompt`, header, `whenToUse`)

**Acceptance:**
- Review prompt does not read `workExperience.md`. Ground truth for review is packet excerpts + constraints + drafted docs + JD + rubric.
- Header/whenToUse state this is never the default for routine drafting.
- Existing 3-company cap and `allowLargeBatch` stay.

**Status:** [x] accepted locally on `cr112-story22` (2026-09-11). File is force-added despite `.claude/` gitignore. `reviewPrompt` forbids `workExperience.md`. `whenToUse` is never-default. Cap 3 + `allowLargeBatch` unchanged. Claude Workflow() primitives kept; portable rewrite deferred. Merged onto `cr112-integration`.

### Story 2.3 — AGENTS.md trigger phrase

**Files:** root `AGENTS.md` only (not CLAUDE.md copy).

**Acceptance:** "Processing job descriptions today" tells the agent to run `run_submission.py` per slug, one author paste per WAITING_FOR_LLM, and `--resume`. Explicit: do not Task/Agent-spawn per JD. Do not invoke conversion-ready-pass on generate-submission drafts.

**Status:** [ ] Documentation reconciliation only: `AGENTS.md` trigger requires `run_submission.py`, one `authoring_prompt.md` paste, `--resume`, no per-JD spawn, no `conversion-ready-pass` on generate-submission drafts. Not planned. Independent review ID not recorded; checkbox stays open.

---

## Epic 3 — Closed-world extra IDs and explainable ranking

**Depends on:** Epic 1.2 if packet shape changes. Uses investigation F5/F6.

**Definition of Done:** a high-relevance metric claim that loses Top-2 has a recorded reason; an omitted fact that clearly dominates the weakest selected fact is swapped before authoring; citing a claim the packet never offered blocks Stage 1 completion until remove / rewrite / explicit widen / human-compare. Detection and comparative selection stay separate.

**Integration status (2026-09-11):** Stories 3.1, 3.5, and 3.6 have independent QA PASS. Epic 3 integration PASS (`d680faf4-4688-4ba6-8a64-0692f239b592`) on `706504a`. Combined candidate `7bf6829` / `165485f`: automated + no-cost Stage 0→1 passed; first-draft product proof remaining. WARN-era Story 3.1 (FR-302 / AC-399) is superseded; detection is FAIL-closed.

### Story 3.0 — Pre-implementation design review (no code)

**Files:** `docs/spec/08-implementation/CR-112-selection-and-closed-world-recovery-design.md`

**Acceptance:**
- Independent reviewer (not the design author) issues ACCEPT / REVISE / REJECT against the seven-folder 2026-09-10 evidence and FR-254.
- Pearl and SupplyHouse `ACC-101-SAVINGS` must not `REPLACE`.
- Detection must stay separable from comparison.
- No live folder rewrite. No implementation of 3.1/3.5/3.6/7.x before ACCEPT.

**Status:** [x] QA PASS (`2d3549f0-39f6-41f9-8386-fc2d74fb76ff`) 2026-09-11
against the design, Story 3.1 diff, seven-folder evidence, and FR-254.
Independent design ACCEPT was `21fd8c64-6c03-4c55-9fc3-4a7a2a974dbb`.
Independent Epic 3 integration PASS (`d680faf4`). Combined candidate: automated + no-cost Stage 0→1 passed; first-draft product proof remaining.

### Story 3.1 — Detect extra-packet provenance IDs as a recoverable completion block

**Files:** `scripts/author_from_packet.py` (`run_verify_only`), `scripts/packet_closed_world.py`, tests.

**Acceptance:**
- Any provenance `claim_id` not in packet excerpts ∪ evidence_map ∪ soft_gaps is a finding with stable id `truth.provenance.extra.<id>`.
- Detection does not rank, recommend, or widen.
- Unresolved extra IDs FAIL Stage 1 verify. Finalize cannot complete. Agents must not dispose these as `ACCEPTED_AS_CORRECT` / `FALSE_POSITIVE` / `NOT_APPLICABLE` / `HUMAN_ACCEPTED_RISK`. This is not `NEEDS_DISPOSITION`.
- Project-prefix match (`ACC-101-SAVINGS` citing as PM) does **not** clear the extra-ID check.
- WARN-and-continue (FR-302 / AC-399) is superseded.
- Recovery actions live in Story 3.6, not in this detector.

**Status:** [x] QA PASS (`2d3549f0-39f6-41f9-8386-fc2d74fb76ff`) 2026-09-11
on the detection slice (12/12 focused tests; nearby 56/56). Detection
is FAIL-closed. Recovery stays Story 3.6. Independent Epic 3
integration PASS (`d680faf4`). Combined candidate: automated + no-cost Stage 0→1 passed; first-draft product proof remaining.
Live scan below is frozen evidence, not a rewrite
list.

**Live extra-packet scan (2026-09-10),** `python scripts/packet_closed_world.py --root data/submissions`:

| slug | extra_ids |
|------|-----------|
| arbiter | (none) |
| cdw | (none) |
| loot_labs | ACC-108-SUPPORT |
| marlowe_companies_inc | ACC-103-SEC |
| pearl_com | ACC-101-SAVINGS |
| supplyhouse | ACC-101-SAVINGS |
| trax_technologies | (none) |

4 of 7 extra. Do not treat those extras as automatically stronger. SupplyHouse was not re-authored.

### Story 3.2 — Record why a scored claim lost the slot

**Files:** `scripts/build_authoring_packet.py` (`build_evidence_map`, `_write_selection_trace`), `scripts/test_cr112_story32.py`.

**Acceptance:**
- Packet `evidence_map` rows store cheap `omitted_reasons` `{claim_id, reason}` where reason is `top2_cutoff` or `project_slot_cap` only. `displaced_by_dominance` is Story 3.5 / FR-314, not this story.
- Full ranking (every scored candidate, score, reason, attribution) lives in sibling `evidence_selection_trace.json`. Stage 1 never loads that file.
- `score_zero` catalog noise and `boilerplate_filtered` preferred/responsibility lines are TRACE-only. Boilerplate items still get no evidence_map row.
- No `disabled` pick-loop skip and no `disabled` omitted reason. Production scoring already skips disabled claims.
- Sanitized Pearl-like fixture: SAVINGS ranks 3rd emits `top2_cutoff`, is **not** auto-inserted, and rank-1 SAVINGS is picked. Story 3.5 must not `REPLACE` this fixture.
- Author prompt may contain the cheap reason code. It must not contain candidate scores, comparator axes, or `evidence_selection_trace.json`.
- Production `build_packet` writes the sibling trace. A hand-call of `_write_selection_trace` is not coverage.

**Status:** [x] accepted locally on `cr112-story32` (2026-09-11). Independent review ACCEPT. Packet enum is `top2_cutoff` | `project_slot_cap` until Story 3.5 adds `displaced_by_dominance`. TRACE holds scores, `score_zero`, and `boilerplate_filtered`. Merged onto `cr112-integration` / local main. Do not weaken Pearl KEEP.

### Story 3.3 — Advisory swap report (read-only)

**Files:** `scripts/report_evidence_swaps.py`, `scripts/test_cr112_story33.py`.

**Acceptance:**
- Labels: `SWAP_CANDIDATE` (`top2_cutoff`) | `INTENTIONAL_TRADEOFF` (`project_slot_cap` or TRACE `filter=boilerplate_filtered`) | `INSUFFICIENT_PROOF` (`score_zero`) | `PACKET_MISSING` (empty item, no filter).
- Never rewrites a document. Never blocks finalize. Not wired into Stage 1/2/3.
- Includes packet version, claim id, attribution, rank/reason/score/label/jd_item. Rank is 1-based in the full TRACE candidate list.
- Fixtures use claim IDs and JD descriptors, not private resume text.
- **This report reads `evidence_selection_trace.json` (Story 3.2) and writes `evidence_swap_report.json` — never a field merged into `authoring_packet.json` or surfaced to the Stage 1 author prompt.**

**Status:** [x] accepted locally on `cr112-story33` (2026-09-11). Independent review ACCEPT. Synthetic traces only. Merged onto `cr112-integration`.

### Story 3.4 — Background-check / admin-line assignment

**Files:** `scripts/build_stage0_fit_gate.py` (`_ADMIN_BACKGROUND_RE`, `_ADMIN_SCHEDULE_RE`, `_is_administratively_satisfied`), `scripts/build_authoring_packet.py` (`_enqueue` skip-scoring), `scripts/test_cr112_story34.py`.

**Acceptance:**
- Eligibility-framed fingerprint / background-check and nights-and-weekends required lines skip `_score_claims_for_item` and do not receive ACC-103-ROADMAP.
- Product lines that name background check or release schedule as the work still score.
- Years lines still may receive claims. Bachelor's stays admin via the existing force-empty path.
- Fixture cloned from marlowe's Level II fingerprint line, with overlapping ROADMAP tags so the 8bbc497 path would have assigned the claim.

**Status:** [x] accepted locally on `cr112-story34` (2026-09-11). Independent review ACCEPT. Eligibility-framed skip only. Merged onto `cr112-integration`.

### Story 3.5 — Pre-authoring comparative replace

**Depends on:** Story 3.0 ACCEPT, Story 3.2 TRACE.

**Files:** `scripts/build_authoring_packet.py` (post Top-2 pass), `scripts/evidence_dominance.py`, `scripts/test_cr112_story35.py`.

**Acceptance:**
- After Top-2, omitted eligible candidates are compared to the weakest selected fact on that item using the six axes in the design doc.
- `REPLACE` only on clear dominance. Swap before excerpts/prompt. TRACE records the decision. Packet omitted reason for the displaced ID is `displaced_by_dominance`.
- `AMBIGUOUS` preserves current picks and sets `selection_review: true` on TRACE. No author-prompt scores.
- Pearl-like SAVINGS fixture does not `REPLACE`. A separate synthetic fixture (not a larger-metric trick) does `REPLACE`.
- Comparator uses no `call_llm`.
- Story 3.3 report remains read-only.

**Status:** [x] QA PASS (`e5d85297-faa2-4002-8452-74517e3547cf`) 2026-09-11
on the Class 1 comparator (16/16 then 18/18 after eligibility-shadow and
INFLUENCED/OBSERVED fixtures). Pearl/SupplyHouse SAVINGS never REPLACE.
Independent Epic 3 integration PASS (`d680faf4`). Combined candidate: automated + no-cost Stage 0→1 passed; first-draft product proof remaining.

### Story 3.6 — Closed-world recovery after extra-packet detection

**Depends on:** Story 3.0 ACCEPT, Story 3.1 FAIL-closed detection, Story 3.5 comparator.

**Files:** `scripts/closed_world_recovery.py`, `scripts/workflow/runner.py` (`run_stage1_validate` recovery step), `scripts/test_cr112_story36.py`.

**Acceptance:**
- Detector still does not recover. Recovery is a separate step. Helpers do not write `workflow_state.json` or `stage_receipts/`.
- `INELIGIBLE` / prohibited / no WE span → `REWRITE_UNSUPPORTED` (do not widen).
- Comparator `KEEP` or sibling-lens extras → `REMOVE_EXTRA` (do not widen).
- True `AMBIGUOUS` extra → `QUALITATIVE_REVIEW` pause with both candidates and axes. Not auto-remove. Not `NEEDS_DISPOSITION`.
- Extra IDs not in TRACE omitted/candidates → `REMOVE_EXTRA` or `REWRITE_UNSUPPORTED`. Never `WIDEN_PACKET`.
- Comparator `REPLACE` only if A is a same-item TRACE omitted candidate → `WIDEN_PACKET`, invalidate leaked draft, require a new author pass, do not provenance-stamp leaked sentences. Orchestrator writes `WAITING_FOR_LLM`.
- `HUMAN_COMPARE` only for unreadable packet, missing catalog, or WE/constraint conflict.
- Cross-item REPLACE is forbidden.
- Unresolved extras keep Stage 1 FAIL. Finalize blocked. `--resume` is the correction path.
- Fixtures: pearl/supplyhouse SAVINGS, loot_labs SUPPORT, marlowe SEC → `REMOVE_EXTRA`; synthetic same-item TRACE omitted REPLACE → `WIDEN_PACKET` + new author pass; disabled extra → `REWRITE_UNSUPPORTED`.
- Do not rewrite live seven folders.

**Status:** [x] QA PASS (`d5a8861b-f6bd-4997-a3c8-9916fe5a40f6`) 2026-09-11
on Class 2 recovery (8/8 then fixtures added for SupplyHouse and
constraint conflict). Helper does not mint receipts. Independent Epic 3
integration PASS (`d680faf4`). Combined candidate: automated + no-cost Stage 0→1 passed; first-draft product proof remaining.
Not a 7.x gate.

---

## Epic 4 — Adversarial harness honesty

**Depends on:** none.

**Definition of Done:** unknown fixtures cannot PASS. Catalog IDs that the runner claims to enforce have a programmatic case or an explicit "not enforced here" row.

### Story 4.1 — Fail closed on unhandled fixture names

**Files:** `scripts/run_adversarial_pressure_test.py` `run_fixture_case`.

**Acceptance:**
- Missing `name` handler returns FAIL/ERROR, never PASS.
- `case_stale_hash` fixture either calls the programmatic stale check or is removed from the fixture walk.
- Unknown directory → not counted as pass.

**Status:** [x] accepted locally on `cr112-epic4` (2026-09-11). Unhandled name FAIL closed.
`case_stale_hash` fixture SKIPPED (programmatic STATE-003 covers it). Runner
13/13 passed, SKIPPED excluded from pass count. Merged onto `cr112-integration`.

### Story 4.2 — Positive control + catalog alignment

**Files:** runner + `docs/spec/INVARIANTS_CATALOG.md`.

**Acceptance:**
- One healthy temp folder must pass STATE-004 inverse (complete check is False until complete, True only with real receipts) without mocks that skip the invariant.
- Catalog rows FIT-*/DOC-002/004/TRUTH-002/003/FINAL-* are either given a programmatic case or marked `enforced_by: not this runner`.
- `payload_*.txt` either wired or moved to `docs/` / archive with a note.

**Status:** [x] accepted locally on `cr112-epic4` (2026-09-11). STATE-004 incomplete
False / chained receipts True without mocking the oracle. Catalog column
`Adversarial runner` marks FIT-*/DOC-002/004/TRUTH-002/003/FINAL-* as
`not this runner`. Payloads archived under `docs/spec/archive/adversarial-payloads/`.
Merged onto `cr112-integration`.

### Story 4.3 — Audit the programmatic `CASES` tier's own assertions, not just the fixture tier

F4's original "KEEP" verdict on programmatic `CASES` assumed calling production code is sufficient. It is not: several checks in `scripts/run_adversarial_pressure_test.py` (`check_state_001_downstream_no_receipt` ~L25-33, `check_doc_003_forbidden_punctuation` ~L70-78, at minimum) follow the pattern `try: runner.run_stage1_validate(...); assert False except runner.WorkflowError: pass` — catching *any* `WorkflowError`, not one whose message/type is specific to the invariant under test. `check_doc_003_forbidden_punctuation` in particular could pass because an earlier, unrelated precondition in `run_stage1_validate` raised first — never actually reaching punctuation validation — and the test would still report the invariant as enforced. Calling production code establishes that *some* exception path exists, not that the specific invariant fired.

**Files:** `scripts/run_adversarial_pressure_test.py` (`check_state_001_downstream_no_receipt`, `check_doc_003_forbidden_punctuation`, and any other `except runner.WorkflowError: pass` check in the programmatic tier).

**Acceptance:**
- Each programmatic check asserts on the raised error's specific reason (message substring, error code, or a typed subclass/attribute identifying the invariant), not the bare `WorkflowError` class.
- Add a negative-control case per audited check: same folder setup minus the specific defect (e.g. valid punctuation, valid Stage 0 receipt) must NOT raise that specific error — proving the check can distinguish "this invariant" from "some other reason validate failed."
- Document which programmatic checks were audited and which (if any) are left broad with a stated reason.

**Status:** [x] accepted locally on `cr112-epic4` (2026-09-11). STATE-001 named
substring + negative control; DOC-003 linter-direct + negative control.
STATE-002 still asserts skip lock via status (not a bare WorkflowError
success). Audit list is in `run_adversarial_pressure_test.py`.
Merged onto `cr112-integration`.

---

## Epic 5 — Composition texture (advisory only)

**Depends on:** Epic 3 optional. Do not block 1–4.

### Story 5.1 — Measure trailing-gerund rate

**Acceptance:** report-only metric on Resume.md bullets. Validated against a human-reviewed sample of the 7 folders before any LW rule. No auto-rewrite.

**Status:** [x] accepted locally on `cr112-story51` (2026-09-11). Independent review ACCEPT. F7 metric is comma / `by` / `while` + `-ing`. Live scan (advisory only): `arbiter` 11/11 (1.00), `cdw` 9/10 (0.90), `loot_labs` 7/9 (0.78), `marlowe_companies_inc` 10/10 (1.00), `pearl_com` 6/11 (0.55), `supplyhouse` 7/10 (0.70), `trax_technologies` 9/10 (0.90). No LW rule. Merged onto `cr112-integration`. Do not use dirty-main end-of-bullet `ing` rates (0.09–0.11).

---

## Epic 6 — Controlled evaluation

**Depends on:** Epic 1 at minimum before claiming reliability improved.

### Story 6.1 — Frozen 5-JD eval set

**Acceptance:**
- Isolated copies of five JDs (sanitized or practice). Redirected SQLite.
- Metrics table from the investigation §5 filled once as baseline (no code change required beyond logging).
- Paid model calls listed with a budget line. Default: zero.

**Status:** [x] accepted locally on `cr112-story61` (2026-09-11). Independent review ACCEPT. Frozen sanitized set in `tests/fixtures/cr112_eval/` (5 fictional JDs). Runtime copy `data/eval/cr112/` (gitignored). Default assemble remains off. Paid calls = 0. Production sqlite refused. Offline CLI baseline: `prompt_meta_estimated_tokens=742`. Merged onto `cr112-integration`.

### Story 6.2 — Instrument harness vs API separately

**Acceptance:**
- Prompt-meta tokens (already on disk) + spawn count (0/1/3) + `call_llm` invocations if a log exists.
- `run_events.jsonl` present on the eval folders.
- Report never adds subscription minutes to API cents.

**Status:** [x] accepted locally on `cr112-story61` (2026-09-11). Independent review ACCEPT. Columns kept separate: `prompt_meta_estimated_tokens`, `call_llm_invocations`, `harness_spawn_count`, `api_cents`, and `subscription_minutes`. Baseline: paid=0, spawn=0, api_cents=0, subscription_minutes=0, prompt-meta estimate 742 (`bytes_div_4_estimate`). `--paid-llm` still does not call `call_llm`. Merged onto `cr112-integration`.

---

## Epic 7 — Model-cost eligibility and telemetry

**Depends on:** none for the registry. Touches CR-108 cascade and `call_llm`. Blocked on Story 3.0 ACCEPT because Jason specified this policy in the same 2026-09-11 design pass.

**Definition of Done:** no model call proceeds with unknown cost eligibility; free providers cannot silently fall back to paid; unknown cost is never reported as zero dollars; missing authorized API pauses onto manual paste.

### Story 7.1 — Cost eligibility, no free→paid fallback, pause to paste

**Files:** new cost-policy module, `scripts/utils.py` `call_llm` / provider cascade, Stage 0 cascade, tests.

**Acceptance:**
- Runtime classes are `offline` | `manual_paste` | `free_only` | `paid_with_budget`. Missing class is `unknown`.
- Groq and Gemini stay `unknown` until an adapter can assert the configured call cannot incur a charge. Advertised free tier is not enough. Provider name does not imply free.
- `unknown` is not callable (fail closed).
- `free_only` requires that zero-charge assertion. User declaration alone does not make a billed project free.
- Paid requires user-configured provider allowlist, remaining run/batch budget, and a known estimate. Unset/0 budget or unknown estimate → paid ineligible.
- Fallback may not move `free_only` → `paid_with_budget`. Provider errors cannot silently change cost mode.
- No eligible provider: do not call; pause at `WAITING_FOR_INPUT` with
  `pause_kind=cost_authorization`. Never `WAITING_FOR_LLM`. Stage 1 paste
  does not complete Stage 0.
- Does not wire eval `--paid-llm` to `call_llm`.

**Status:** [x] QA PASS (`18868b0f-a352-4cf6-8a76-b86249672614`) 2026-09-11
on cost eligibility. Follow-up `7bf6829` independent review PASS
(`97887893-381a-47fa-b521-e5c1d5d2af78`) for canonical
`WAITING_FOR_INPUT` / `cost_authorization` receipt, bound Stage 0 import,
and consumed-import rename. Combined candidate: automated + no-cost Stage 0→1 passed; first-draft product proof remaining.
Do not push. Do not merge onto `cr112-selection-closed-world-design` yet.

### Story 7.2 — Cost telemetry: unknown is not zero

**Files:** call sites + eval/metrics writers, tests.

**Acceptance:**
- Per call / totals record: invocations, provider, estimated tokens, `cost_class`, `cost_known`, `api_cents` only when `cost_known` is true, `subscription_minutes` separately.
- When `cost_known=false`, `api_cents` is omitted or null, never `0`.
- Never sum subscription minutes with API cents.
- Eval 6.1/6.2 baseline remains zero-call with explicit `cost_class` labels, not implied free spend.

**Status:** [x] QA PASS (`18868b0f-a352-4cf6-8a76-b86249672614`) 2026-09-11
on unknown ≠ zero telemetry. Eval zero-call stays `offline` with
`cost_known=true`. Follow-up `7bf6829` review PASS (`97887893`). Combined
candidate: automated + no-cost Stage 0→1 passed; first-draft product
proof remaining. Do not push.

## Out of scope

- Rewriting the seven live submissions **as a blanket action.** Story 1.4's per-folder recovery decision is the sole, narrow exception — any re-authoring it triggers is explicit, human-reviewed, and limited to folders the audit actually flags, not a general rewrite pass.
- Auto-inserting larger metrics (Story 3.5 replace is dominance, not metric size)
- Automatic style/gerund hard blocks
- Migrating Stage 1 compose to a cheaper API model without Epic 7 eligibility
- Multi-tenant billing
- Deleting Antigravity's runner, catalog, or fixtures
- Accepting CR-097 Epic 7 as CR-097 scope
- Implementing Stories 3.1-revise / 3.5 / 3.6 / 7.x before Story 3.0 ACCEPT

---

## Review checkpoint (Epic 1 isolated)

Epic 1 is on branch `cr112-epic1` for independent review. Epics 2–6 stay planned and are not in this commit. Checkboxes stay open. Do not self-mark done.

SupplyHouse recovery is off the active backlog (Jason, 2026-09-10 chat: already corrected; do not rebuild, re-author, or request risk acceptance). Keep the detector and regression tests. The agent-created sidecar is a separate finding and is not authorization.

