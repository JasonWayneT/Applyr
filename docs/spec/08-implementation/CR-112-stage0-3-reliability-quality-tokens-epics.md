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
```

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
**Status:** [ ] isolated on `cr112-epic1`; pending review. Reject/shuffle/partial-unknown tests plus simulated Groq→Gemini fallback. Hash-tail `len >= 8` on committed main already rejected `req-001`; this story locks that reject and the fallback path.

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
**Status:** [ ] isolated on `cr112-epic1`; pending review. Comment + budget regression test. Committed main already omitted the wipe; this story locks Rule 5. supplyhouse not rebuilt.

### Story 1.3 — Record the two patches in CHANGELOG + this tracker

**Files:** CHANGELOG.md (DRAFT), this file.

**Acceptance:** both behaviors named; no silent "resilience" language that hides fail-open.
**Status:** [ ] CHANGELOG [DRAFT] 2026-09-10 Epic 1 only; pending review. Registry `FR-296`–`FR-298` / `AC-393`–`AC-395`. No Epics 2–6 in that entry.

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

**Status:** [ ] planned; not in the Epic 1 commit. Stage 0 default is `run_submission.py data/pending_review/{slug}`; no WE rescore. Stage 1 paste is `authoring_prompt.md` only. Stage 2 `--resume` is mechanical; qualitative read required before `hm.critical_read`.

### Story 2.2 — Contain generate-submission-batch.js

**Files:** `.claude/workflows/generate-submission-batch.js` (`reviewPrompt`, header, `whenToUse`)

**Acceptance:**
- Review prompt does not read `workExperience.md`. Ground truth for review is packet excerpts + constraints + drafted docs + JD + rubric.
- Header/whenToUse state this is never the default for routine drafting.
- Existing 3-company cap and `allowLargeBatch` stay.

**Status:** [ ] planned; not in the Epic 1 commit. `reviewPrompt` uses packet excerpts + `claim_constraints`; does not load WE. Header/whenToUse say never-default. Cap 3 unchanged.

### Story 2.3 — AGENTS.md trigger phrase

**Files:** root `AGENTS.md` only (not CLAUDE.md copy).

**Acceptance:** "Processing job descriptions today" tells the agent to run `run_submission.py` per slug, one author paste per WAITING_FOR_LLM, and `--resume`. Explicit: do not Task/Agent-spawn per JD. Do not invoke conversion-ready-pass on generate-submission drafts.

**Status:** [ ] planned; not in the Epic 1 commit. Root `AGENTS.md` only.

---

## Epic 3 — Closed-world extra IDs and explainable ranking

**Depends on:** Epic 1.2 if packet shape changes. Uses investigation F5/F6.

**Definition of Done:** a high-relevance metric claim that loses Top-2 has a recorded reason; citing a claim the packet never offered is visible to Stage 1 verify.

### Story 3.1 — Fail or WARN extra-packet provenance IDs

**Files:** `scripts/author_from_packet.py` (`run_verify_only`), tests.

**Acceptance:**
- Any provenance `claim_id` not in packet excerpts ∪ evidence_map ∪ soft_gaps is a finding.
- First implementation: WARN with a stable id (`truth.provenance.extra.<id>`). Do not hard-block until Jason sees false-positive rate on the 7-folder set (run read-only).
- Project-prefix match (`ACC-101-SAVINGS` citing as PM) does **not** clear the extra-ID check.

**Status:** [ ] planned; not in the Epic 1 commit. WARN only
(`truth.provenance.extra.<id>`). Prefix does not clear. Tests in
`scripts/test_cr112_epic3.py`. Live scan recorded below. No live rewrites.

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

4 of 7 WARN. Hard-block still deferred. SupplyHouse was not re-authored.

### Story 3.2 — Record why a scored claim lost the slot

**Files:** `scripts/build_authoring_packet.py` (`build_evidence_map`, `_write_selection_trace`), `scripts/test_cr112_story32.py`.

**Acceptance:**
- Packet `evidence_map` rows store cheap `omitted_reasons` `{claim_id, reason}` where reason is `top2_cutoff` or `project_slot_cap` only.
- Full ranking (every scored candidate, score, reason, attribution) lives in sibling `evidence_selection_trace.json`. Stage 1 never loads that file.
- `score_zero` catalog noise and `boilerplate_filtered` preferred/responsibility lines are TRACE-only. Boilerplate items still get no evidence_map row.
- No `disabled` pick-loop skip and no `disabled` omitted reason. Production scoring already skips disabled claims.
- Sanitized Pearl-like fixture: SAVINGS ranks 3rd emits `top2_cutoff`, is not auto-inserted, and rank-1 SAVINGS is picked.
- Author prompt may contain the cheap reason code. It must not contain candidate scores or `evidence_selection_trace.json`.
- Production `build_packet` writes the sibling trace. A hand-call of `_write_selection_trace` is not coverage.

**Status:** [x] accepted locally on `cr112-story32` (2026-09-11). Independent review ACCEPT. Packet enum is `top2_cutoff` | `project_slot_cap`. TRACE holds scores, `score_zero`, and `boilerplate_filtered`. Merged onto `cr112-integration`.

### Story 3.3 — Advisory swap report (read-only)

**Files:** new script under `scripts/` or extension of `check_ground_truth_coverage.py`.

**Acceptance:**
- Labels: `SWAP_CANDIDATE` | `INTENTIONAL_TRADEOFF` | `PACKET_MISSING` | `INSUFFICIENT_PROOF`.
- Never rewrites a document. Never blocks finalize.
- Includes packet version, claim id, attribution, rank/reason.
- Fixtures use claim IDs and JD descriptors, not private resume text.
- **This report reads `evidence_selection_trace.json` (Story 3.2) and writes its own output file — it is a standalone diagnostic tool, never a field merged into `authoring_packet.json` or surfaced to the Stage 1 author prompt.** A human (Jason, or a review pass) reads this report; the author only ever sees what Story 3.2 already scopes into the packet (the reason code, not the full trace).

**Status:** [ ] planned; not in the Epic 1 commit. `scripts/report_evidence_swaps.py`. Label mapping covered in `test_cr112_epic3.py`.

### Story 3.4 — Background-check / admin-line assignment

**Files:** `build_authoring_packet.py` scoring / `_is_administratively_satisfied`.

**Acceptance:**
- A required line that is a background check, schedule, or degree does not receive ACC-103-ROADMAP (or any product-roadmap claim) as its Top-2.
- Fixture cloned from marlowe's Level II fingerprint line.

**Status:** [ ] planned; not in the Epic 1 commit. Fingerprint and
nights-and-weekends fixtures have empty `claim_ids` and no ACC-103-ROADMAP.

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

**Status:** [ ] planned; not in the Epic 1 commit. Unhandled name FAIL.
`case_stale_hash` fixture SKIPPED (programmatic STATE-003 covers it). Runner
13/13 passed, SKIPPED excluded from pass count.

### Story 4.2 — Positive control + catalog alignment

**Files:** runner + `docs/spec/INVARIANTS_CATALOG.md`.

**Acceptance:**
- One healthy temp folder must pass STATE-004 inverse (complete check is False until complete, True only with real receipts) without mocks that skip the invariant.
- Catalog rows FIT-*/DOC-002/004/TRUTH-002/003/FINAL-* are either given a programmatic case or marked `enforced_by: not this runner`.
- `payload_*.txt` either wired or moved to `docs/` / archive with a note.

**Status:** [ ] planned; not in the Epic 1 commit. STATE-004 incomplete
False / chained receipts True without mocking the oracle. Catalog column
`Adversarial runner` marks FIT-*/DOC-002/004/TRUTH-002/003/FINAL-* as
`not this runner`. Payloads archived under `docs/spec/archive/adversarial-payloads/`.

### Story 4.3 — Audit the programmatic `CASES` tier's own assertions, not just the fixture tier

F4's original "KEEP" verdict on programmatic `CASES` assumed calling production code is sufficient. It is not: several checks in `scripts/run_adversarial_pressure_test.py` (`check_state_001_downstream_no_receipt` ~L25-33, `check_doc_003_forbidden_punctuation` ~L70-78, at minimum) follow the pattern `try: runner.run_stage1_validate(...); assert False except runner.WorkflowError: pass` — catching *any* `WorkflowError`, not one whose message/type is specific to the invariant under test. `check_doc_003_forbidden_punctuation` in particular could pass because an earlier, unrelated precondition in `run_stage1_validate` raised first — never actually reaching punctuation validation — and the test would still report the invariant as enforced. Calling production code establishes that *some* exception path exists, not that the specific invariant fired.

**Files:** `scripts/run_adversarial_pressure_test.py` (`check_state_001_downstream_no_receipt`, `check_doc_003_forbidden_punctuation`, and any other `except runner.WorkflowError: pass` check in the programmatic tier).

**Acceptance:**
- Each programmatic check asserts on the raised error's specific reason (message substring, error code, or a typed subclass/attribute identifying the invariant), not the bare `WorkflowError` class.
- Add a negative-control case per audited check: same folder setup minus the specific defect (e.g. valid punctuation, valid Stage 0 receipt) must NOT raise that specific error — proving the check can distinguish "this invariant" from "some other reason validate failed."
- Document which programmatic checks were audited and which (if any) are left broad with a stated reason.

**Status:** [ ] planned; not in the Epic 1 commit. STATE-001 named
substring + negative control; DOC-003 linter-direct + negative control.
STATE-002 still asserts skip lock via status (not a bare WorkflowError
success). Audit list is in `run_adversarial_pressure_test.py`.

---

## Epic 5 — Composition texture (advisory only)

**Depends on:** Epic 3 optional. Do not block 1–4.

### Story 5.1 — Measure trailing-gerund rate

**Acceptance:** report-only metric on Resume.md bullets. Validated against a human-reviewed sample of the 7 folders before any LW rule. No auto-rewrite.

**Status:** [ ] planned; not in the Epic 1 commit. Synthetic tests green.
Live scan (advisory only): arbiter 0/11, cdw 1/10 (0.10), loot_labs 1/9 (0.11),
marlowe 0/10, pearl_com 1/11 (0.09), supplyhouse 0/10, trax 0/10. No LW rule.

---

## Epic 6 — Controlled evaluation

**Depends on:** Epic 1 at minimum before claiming reliability improved.

### Story 6.1 — Frozen 5-JD eval set

**Acceptance:**
- Isolated copies of five JDs (sanitized or practice). Redirected SQLite.
- Metrics table from the investigation §5 filled once as baseline (no code change required beyond logging).
- Paid model calls listed with a budget line. Default: zero.

**Status:** [ ] planned; not in the Epic 1 commit. Frozen sanitized set
in `tests/fixtures/cr112_eval/` (5 fictional JDs). Runtime copy
`data/eval/cr112/` (gitignored). Paid calls = 0. Production sqlite refused.
Investigation §5 baseline filled.

### Story 6.2 — Instrument harness vs API separately

**Acceptance:**
- Prompt-meta tokens (already on disk) + spawn count (0/1/3) + `call_llm` invocations if a log exists.
- `run_events.jsonl` present on the eval folders.
- Report never adds subscription minutes to API cents.

**Status:** [ ] planned; not in the Epic 1 commit. `run_events.jsonl` on
eval folders. Columns kept separate: `prompt_meta_estimated_tokens`,
`call_llm_invocations`, `harness_spawn_count`. Baseline: all three paid/spawn
counters 0; prompt-meta estimate 742 (bytes÷4, not a tokenizer count).

---

## Out of scope

- Rewriting the seven live submissions **as a blanket action.** Story 1.4's per-folder recovery decision is the sole, narrow exception — any re-authoring it triggers is explicit, human-reviewed, and limited to folders the audit actually flags, not a general rewrite pass.
- Auto-inserting larger metrics
- Automatic style/gerund hard blocks
- Migrating Stage 1 compose to a cheaper API model
- Multi-tenant billing
- Deleting Antigravity's runner, catalog, or fixtures
- Accepting CR-097 Epic 7 as CR-097 scope

---

## Review checkpoint (Epic 1 isolated)

Epic 1 is on branch `cr112-epic1` for independent review. Epics 2–6 stay planned and are not in this commit. Checkboxes stay open. Do not self-mark done.

SupplyHouse recovery is off the active backlog (Jason, 2026-09-10 chat: already corrected; do not rebuild, re-author, or request risk acceptance). Keep the detector and regression tests. The agent-created sidecar is a separate finding and is not authorization.

