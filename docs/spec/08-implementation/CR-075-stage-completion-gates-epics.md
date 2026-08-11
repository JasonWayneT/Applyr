---
status: done
created: 2026-08-07
related: CR-074 (token-conscious authoring packet — the path this CR wraps enforcement around, not modified), CR-070 (native generation pipeline — unaffected), CR-073 (jd_term_extractor/reading-order WARN fields already in the receipt this CR extends)
contains: CR-075 (Stage 0-2 Completion Gates & Verification Lineage Hardening)
---

# CR-075 — Stage 0-2 Completion Gates & Verification Lineage Hardening: Epics & Stories

**Handoff doc.** Resumable plan for [CR-075](../05-change-requests/CR-075-stage-completion-gates.md)
(scope locked, approved by Jason 2026-08-07, all five Open Questions — the original three plus two
more found during this epics pass — resolved in the CR itself — do not re-litigate them here). A new
session picks up at the **first unchecked story**.
Stories are sized for one senior-engineer pass each: read the story, make the change, run the tests
named in it, check the box, stop.

**Operating rule:** every gate this CR adds must be enforceable by code that reads files on disk.
A gate that depends on an agent having remembered to run something is not a gate — that is the exact
failure this CR exists to close.

```
Epic 1 (token burn) → Epic 2 (hash lineage) → Epic 3 (contract fns) → Epic 4 (enforcement + Stage 0/1)
                                                                              → Epic 5 (Stage 2) → Epic 6 (docs/closeout)
```

Epics are ordered by ROI/risk, not by the order the CR lists them: Epic 1 is the cheapest change with
the largest real-world payoff (it prevents the incident that produced this CR), Epic 2 fixes a defect
that is live on disk right now, and the architecture work (Epics 3-5) lands after both.

---

## Why this exists (read this before touching anything)

Three facts, all verified against live code during this planning pass, not recalled:

1. **Only Stage 3 has an enforced gate.** `scripts/contracts.py` has five check functions, but
   `check_finalize_ready()` is the only one ever used as a blocking precondition — in
   `finalize_submission_job.py:60 _require_ready`. `check_stage0_fit_gate` / `check_draft_manifest` /
   `check_verification_receipt` / `check_freshness` are imported only by
   `scripts/check_submission_status.py`, for read-only reporting. Stages 0, 1 and 2 can be skipped or
   re-read stale and nothing stops it unless Stage 3 is actually attempted.
2. **Verification lineage is mtime-only, and it is failing right now.** `check_freshness()`
   (`contracts.py:174`) compares `os.path.getmtime`. Confirmed by running it during this pass:
   `camunda`, `ncontracts` and `paylocity` under `data/submissions/` all return
   `(False, ['Resume.md was edited after verification_receipt.json was generated', ...])`. mtime is
   also fragile to clock skew, `touch`, and checkout — it is the only lineage signal that exists.
   Of 41 submission folders, 22 have a `verification_receipt.json` and **2** have a
   `draft_manifest.json` at all.
3. **The Author agent in the batch workflow never migrated to CR-074.**
   `.claude/workflows/generate-submission-batch.js:131 authorPrompt()` still tells every Author agent
   to read `data/agent_context_pack.md` or `CLAUDE.md` + `data/workExperience.md`. That is the
   pre-CR-074 context path at ~100-150k tokens per agent. CR-074's own calibration measured the packet
   path at ~3.8-4.3k. Twelve companies x 3 agents on the old path is what burned a five-hour
   allocation in about five minutes with zero completions.

Everything below is either closing one of those three, or is test/docs work required to make the
closure hold.

---

## Architecture decisions locked in this pass (do not re-derive them per story)

These are tech-lead calls made against the real code. If one of them turns out to be wrong once you
are in the file, say so and stop — do not quietly pick a different design.

- **`contracts.py` stays a pure predicate library. Enforcement lives in a new `scripts/stage_gate.py`.**
  `contracts.py` is imported by `check_submission_status.py`, which is deliberately the *read-only*
  status oracle. Putting argparse handling, `sys.exit`, subprocess calls or durable-log writes into
  `contracts.py` would make merely *reporting* status have side effects (including mutating
  `data/.rubric_score_history.json`, which `audit_rubric_scores` writes). New module, one concern:
  gate enforcement + `--force` policy + override logging. This is the one new pattern this CR
  introduces, and that separation is why.
- **`check_stage2_ready()` never shells out.** It reads what `verify_submission.py` already recorded
  in `verification_receipt.json`. The audit and the provenance check are *run by the producing script
  and written into the receipt*; the contract function reads those recorded results. Same reason as
  above, plus it keeps the functions unit-testable from fixtures with no subprocess.
- **`check_stage2_ready()` does not chain `check_stage1_ready()`.** It contains exactly what the CR's
  Decision item 2 lists for Stage 2. Chaining would make the 28 packet-less legacy folders permanently
  un-verifiable, which is blast radius this CR did not ask for. `check_stage1_ready()` is enforced at
  `author_from_packet.py --verify-only` (its real position in the flow: Stage 1 exit / Stage 2 entry).
- **`check_stage2_ready()` requires `rubric_score` populated but NOT `verification_passed`.**
  AC6 makes the audit gate `verification_passed`, so requiring it would be circular. That check stays
  where it already is, in `check_finalize_ready()` (`contracts.py:214`).
- **"Refuse to report Stage 2 complete" is a verdict change, not an exit-code change on the normal
  run.** `verify_submission.py` writes the receipt first, then evaluates the gate. When `rubric_score`
  is absent — the normal mid-flow state, since scoring is a later hand pass — it prints
  `STAGE 2: INCOMPLETE` with the itemized reason and keeps today's exit semantics. When a
  `rubric_score` **is** present, the full gate applies and failure exits non-zero. This is exactly
  AC6's own "whenever a rubric score is present" qualifier, and it is what keeps the batch script's
  Finalize phase (which stops on any non-zero exit, `generate-submission-batch.js:217`) from breaking
  on every first-pass verify.
- **Legacy receipts (no `content_hashes`) keep mtime semantics.** Hash comparison applies when hashes
  are present; absent, `check_freshness()` behaves exactly as today. Treating a missing hash field as
  stale would invalidate 19 receipts belonging to already-sent submissions for no acceptance-criteria
  benefit. AC5's three folders are caught either way (verified above), and the hash path is strictly
  stronger for everything verified after this lands.
- **The `--force` override log lives at `data/.force_override_log.json`.** Same convention and same
  directory as `data/.rubric_score_history.json`, and covered by `.gitignore`'s `data/*.json`
  (line 96) — an operational log carrying company slugs must not become a tracked file. Do not name it
  `.jsonl`; that extension is not matched by the ignore rule.
- **`--force` / `--force-reason` policy lives in one function.** `stage_gate.validate_force(stage,
  force, force_reason)` owns the asymmetry (Stage 2 requires a non-empty reason; Stages 0/1/3 do not).
  Scripts get their flags from `stage_gate.add_force_args(parser, stage)`; `verify_submission.py`,
  which parses `sys.argv` by hand (`verify_submission.py:293`), gets `stage_gate.parse_force_flags(argv)`
  instead of an argparse migration. No per-script duplication of the policy itself.

---

## Open questions from the epics pass — RESOLVED 2026-08-07

Both surfaced only after reading the real code, both routed to Jason the same day, both now decided.
Kept here for audit trail. See CR-075's own "Second Revision" section for the full record.

- **OQ-1 — AC3 vs. CR-074's fail-closed packet rule — RESOLVED: no override, full stop.** AC3
  originally modeled Stage 1's `--force` on the same bare-flag pattern as Stages 0/3. `packet_status:
  incomplete` means one of CR-074's five fail-closed conditions fired
  (`scripts/contracts/authoring_packet_RULES.md`): unmapped required item, disabled claim, missing
  excerpt, Skip tier, or over token budget — a content-safety condition, not a staleness one. Decision:
  `check_stage1_ready()`'s `packet_status` requirement has **no `--force` override at all**, matching
  the existing `scripts/test_author_from_packet.py:151 test_non_ready_overrides_force` behavior
  ("force does not bypass packet_status check — only the version check") rather than loosening it.
  Story 4.3 below implements this as final, not interim.
- **OQ-2 — nothing emits `claim_provenance.json` — RESOLVED: widen the CR, make Stage 1 emit it.**
  `scripts/claim_provenance.py` validates the file, but nothing wrote one, so the WARN wired in Story
  5.2 would have surfaced the identical `claim_provenance.json not found` forever — the exact "WARN
  nobody reads" failure the CR names. Fixing it means editing `author_from_packet.py`'s compose-pass
  output contract (CR-074's surface), which the CR's Metadata originally said this work wouldn't touch.
  Jason chose to widen CR-075 rather than open a follow-on CR. New **Story 5.0** below adds the
  emission requirement; Story 5.2's framing is updated accordingly.

---

## Epic 1 — Stop the token burn in the batch workflow

**Goal:** the batch script can no longer spend six figures of tokens per company, and can no longer be
pointed at twelve companies unattended by accident.

Highest ROI in the CR and the only epic with no Python coupling — two edits to one file, both before
any agent spawns. Scoped tightly per the CR's Out of Scope line: the Author/Review/Finalize phase
structure, the Cross-Batch Sweep, the `JSON.parse` defensive fallback (line 169) and the
`check_finalize_ready`-gated Finalize phase are **not touched**.

- [x] **Story 1.1 — Migrate `authorPrompt()` to the CR-074 packet path.**
  `.claude/workflows/generate-submission-batch.js:130-140`. Replace the first paragraph's context
  instruction (`check_context_pack_freshness.py` → `agent_context_pack.md`, else `CLAUDE.md` +
  `workExperience.md`) with the CR-074 sequence: run
  `python scripts/build_authoring_packet.py data/submissions/${item.slug}` if
  `authoring_packet.json` is absent, then `python scripts/author_from_packet.py
  data/submissions/${item.slug}`, and author **closed-world from
  `data/submissions/${item.slug}/authoring_packet.json` + `data/authoring_rule_digest.md` only** — no
  `agent_context_pack.md`, no full `CLAUDE.md`, no `workExperience.md`, no `master_claims.json`.
  Keep, verbatim in intent: the PDF compile + `verify_submission.py` /
  `check_ground_truth_coverage.py` / `jd_term_extractor.py` instruction, and the "Do NOT write
  draft_manifest.json's rubric_score — that is the independent reviewer's job" sentence (that sentence
  is the Author/Review split; deleting it silently re-creates the self-graded-review bug). Add
  `python scripts/author_from_packet.py data/submissions/${item.slug} --verify-only` as the Stage 1
  exit step before the PDF compile. Do not touch `reviewPrompt()` — AC7 names `authorPrompt()` only,
  and the reviewer reading `workExperience.md` is deliberate (independent attribution check).
- [x] **Story 1.2 — Add the company-count guard.**
  Same file, immediately after the `const jobs = ...` parse at line 169 and **before**
  `phase('Author')` at line 171 — the guard is worthless if it fires after agents have spawned. Add
  `const MAX_COMPANIES_PER_RUN = 3` and refuse (`throw`) when `jobs.length > MAX_COMPANIES_PER_RUN`
  unless an explicit opt-in is present on the payload (`jobs.some(j => j.allowLargeBatch === true)`).
  The error message must name the real reason: the file's own header already says the first real run
  should be treated as a dry run, and the incident was a 12-company unattended first invocation. Do
  not change the separate `if (jobs.length >= 3)` Cross-Batch Sweep guard at line 195 — different
  threshold, different purpose, leaving both is correct.

---

## Epic 2 — Content-hash verification lineage

**Goal:** a verification receipt proves *which bytes* it verified, so an edit after verification can
never read as passing.

- [x] **Story 2.1 — Create `scripts/test_contracts.py` with baseline coverage.**
  There is no existing test file for `contracts.py` — AC1's "matching the existing
  `check_finalize_ready` test pattern" refers to a file that does not exist (verified: no
  `test_contracts.py`, and no other `scripts/test_*.py` imports `contracts`). Create it now, before
  changing `check_freshness`, so the rest of this CR has a regression net. `unittest` style with
  `tempfile.TemporaryDirectory` fixtures, matching `scripts/test_author_from_packet.py` and
  `scripts/test_build_authoring_packet.py` (the two most recent and most similar test files). Cover
  the current behavior of all five existing functions, `check_finalize_ready` and `check_freshness`
  included. Register the file in `scripts/run_all_tests.py`'s `PYTHON_TEST_SCRIPTS` list — these are
  the gates the whole process depends on, they belong in the standard run.
- [x] **Story 2.2 — `verify_submission.py` records `content_hashes`.**
  In `verify_one()` (`scripts/verify_submission.py:132`), add a `content_hashes` key to the receipt:
  sha256 of the raw bytes of `Resume.md` and `CoverLetter.md` as they were read for verification, plus
  the algorithm name so a future change is detectable. Additive only — every existing key keeps its
  name, type and position, because `check_submission_status.py`, `check_verification_receipt()` and
  `check_finalize_ready()` all read this file today.
- [x] **Story 2.3 — Make `check_freshness()` hash-aware, with a legacy fallback.**
  `contracts.py:174`. When the receipt carries `content_hashes`, compare the current file hashes
  against the stored ones and report per-document mismatches; keep the mtime comparison as the cheap
  pre-check ahead of it. When the receipt has no `content_hashes` (every receipt written before Story
  2.2), behave exactly as today. Signature stays `(bool, list[str])` — `finalize_submission_job.py`
  and `check_submission_status.py:68` both depend on it. Extend `test_contracts.py` with both
  directions the hash path exists to catch: identical content with a newer mtime (a `touch`) must
  read fresh, and changed content with an unchanged mtime must read stale.
- [x] **Story 2.4 — AC5 evidence pass on the three known-stale folders.**
  Ran `python scripts/contracts.py data/submissions/{camunda,ncontracts,paylocity}` (post Story 2.3)
  without re-running `verify_submission.py` on any of them. All three still `[FAIL] freshness`, both
  `Resume.md`/`CoverLetter.md` flagged as edited after their `verification_receipt.json`. **Honest
  note on mechanism**: all three receipts predate Story 2.2 (no `content_hashes` field), so they're
  caught via the unchanged mtime-fallback path, not a live hash comparison — re-running
  `verify_submission.py` on them to get a hash-bearing receipt is exactly the action this story
  forbids, since it would clear the current staleness signal. The hash-comparison capability itself
  (AC5's "not just mtime" clause) is proven directly by Story 2.3's dedicated unit tests
  (`test_hash_mismatch_with_unchanged_mtime_reads_stale` et al.), not by these three specific legacy
  folders. Deciding whether/when to re-verify these three for real is Jason's call, not made here.

---

## Epic 3 — The two new contract functions

**Goal:** `contracts.py` can answer "is Stage 1 done?" and "is Stage 2 done?" from files on disk, in
the same shape as the Stage 3 gate that already works.

Nothing calls these until Epics 4-5. Landing this epic alone is a safe intermediate state.

- [x] **Story 3.1 — `check_stage1_ready(folder)`.**
  New function in `contracts.py`, returning `(bool, list[str])`, built on `load_json`. Requires
  `authoring_packet.json` present with `packet_status == "ready"` (echoing `incomplete_reasons` into
  the error list when not), and both `Resume.md` and `CoverLetter.md` present in the folder. This is
  the Stage 1 **exit** condition, per the CR's Decision item 2. Add it to the module docstring's
  "Also importable" list (`contracts.py:36-40`) and to `main()`'s per-folder report loop.
- [x] **Story 3.2 — `check_stage2_ready(folder)`.**
  New function in `contracts.py`, `(bool, list[str])`, composed from existing primitives plus receipt
  fields: `check_verification_receipt()` passing, `check_freshness()` passing, `draft_manifest.json`
  present with a populated `rubric_score` (reuse `_check_rubric_score_shape`, `contracts.py:102`),
  zero linter `HARD_BLOCK`s (the receipt's `lint_all_clean` plus an explicit per-document `blocks`
  empty assertion), the receipt's recorded rubric-audit result clean, and the receipt's
  `claim_provenance` field **present** (presence only — its content never affects the result, AC9).
  Does not require `verification_passed` and does not call `check_stage1_ready` — see the locked
  decisions above. Reads the audit/provenance fields defensively: a receipt written before Epic 5
  lacks them, and the resulting error must say *why* ("re-run scripts/verify_submission.py"), not
  crash.
- [x] **Story 3.3 — Unit tests for both, including the AC9 non-blocking case.**
  Extend `scripts/test_contracts.py`. Must include the AC9 test explicitly: a fixture where
  `claim_provenance` reports findings and every other Stage 2 requirement is clean returns
  `check_stage2_ready() == True`. Also cover each individual failure mode returning a specific,
  actionable error string — the itemized error list is what AC2/AC4 mean by "itemized", and a generic
  "not ready" is a failed story.

---

## Epic 4 — Enforcement layer and the Stage 0 / Stage 1 gates

**Goal:** the scripts that produce each stage's artifacts refuse to run on bad upstream state, and
every override is durably recorded.

- [x] **Story 4.1 — New `scripts/stage_gate.py`.** (Cursor, 2026-08-07 — parallel with Claude Code on Epic 3; new files only, no contracts.py edits)
  Owns: `StageGateNotReadyError`; `validate_force(stage, force, force_reason)` implementing the
  asymmetry (Stage 2 rejects a bare `--force` with no non-empty `--force-reason`; Stages 0/1/3 accept
  the bare flag, unchanged); `require_stage_ready(stage, folder, force, force_reason)` which runs the
  matching `contracts` check, raises with an itemized message when it fails and no override is given,
  and calls the logger when an override *is* given; `log_force_override(...)` appending
  `{timestamp, stage, folder, reason, argv}` to `data/.force_override_log.json`;
  `add_force_args(parser, stage)` for the argparse-based callers; `parse_force_flags(argv)` for
  `verify_submission.py`'s hand-rolled parsing. Ship with its own tests in
  `scripts/test_stage_gate.py` (registered in `run_all_tests.py`) — the log must be written to a temp
  path in tests, never to the real `data/` file.
- [x] **Story 4.2 — Stage 0 gate in `build_authoring_packet.py` (AC2).** (Cursor, 2026-08-07)
  In `_main()` (`scripts/build_authoring_packet.py:~920`), after the existing `--with-stage0`
  auto-run block and before `build_packet()`, call the Stage 0 gate on
  `contracts.check_stage0_fit_gate`. **This changes the script's documented "Exit: always 0"
  contract** (docstring line ~19, a deliberate CR-074 Story 3.5 decision) — change it only for this
  gate path: a missing or structurally invalid `stage0_fit_gate.json` now exits non-zero with the
  itemized error list, `--force` (via `add_force_args`) overrides and logs. Leave the other
  `sys.exit(0)` error paths (not-a-directory, packet build exception) alone; unrelated behavior drift
  is not in scope. Check `scripts/test_build_authoring_packet.py` for any test asserting exit 0 on the
  missing-stage0 path and update it deliberately, with the reason in the test docstring.
- [x] **Story 4.3 — Stage 1 gate in `author_from_packet.py` (AC3, OQ-1 resolved).** (Cursor, 2026-08-07)
  `--verify-only` (`author_from_packet.py:384`) calls `check_stage1_ready()` before running its
  checks, so a `--verify-only` against a folder with no packet or a missing document fails with the
  itemized reason instead of a bare `FAIL: Resume.md not found`. `check_stage1_ready()` has **no
  `--force` parameter at all** — this is final, not interim (OQ-1 resolved: a content-safety gate,
  not a staleness gate, gets no override). Do **not** widen the existing `--force` in
  `_check_packet_ready()` (`author_from_packet.py:114`, which covers the *version* check only) to
  also cover `packet_status`, and do not modify `test_author_from_packet.py:151` — both stay exactly
  as they are, which is what OQ-1 resolved to keep.
- [x] **Story 4.4 — Retrofit Stage 3's override logging.** (Cursor, 2026-08-07)
  `finalize_submission_job.py:60 _require_ready`. Stage 3 semantics stay exactly as they are (bare
  `--force`, `NotReadyToFinalizeError`, same message) — the only change is calling
  `stage_gate.log_force_override("stage3", ...)` when `force` is used to bypass a real failure, so the
  CR's "every `--force` override, at every stage gate, gets appended to a persistent log" holds for
  all four stages. Do not route Stage 3 through `require_stage_ready`; there is no benefit and it
  risks changing a gate that currently works.

---

## Epic 5 — The Stage 2 gate

**Goal:** nothing can report Stage 2 complete on a stale receipt, an unscored manifest, a duplicated
rubric score, or without the provenance check having run.

- [x] **Story 5.0 — Stage 1 compose output emits `claim_provenance.json` (AC11, OQ-2 resolved).**
  `scripts/author_from_packet.py`'s `_PREAMBLE` (~line 54-69) currently instructs the compose agent to
  output exactly two fenced blocks, `Resume.md` and `CoverLetter.md`. Add a third required block,
  `claim_provenance.json`, in the exact schema `scripts/claim_provenance.py`'s own docstring documents:
  `{"company": ..., "resume_claims": [{"bullet": ..., "claim_ids": [...]}], "cover_letter_claims":
  [{"proof_point": ..., "claim_ids": [...]}]}`. The agent already selects which packet `claim_ids`
  back each bullet via the packet's `evidence_map` — this instruction asks it to record that choice,
  not do new work. Write the third block to `data/submissions/{slug}/claim_provenance.json` the same
  way the other two are written today. This is the one story in this CR that edits CR-074's
  authoring-prompt output contract — deliberate, per Jason's decision, not an oversight. Must land
  before Story 5.2, which surfaces the check this story gives real data to check.
- [x] **Story 5.1 — Run the rubric audit inline and record it in the receipt (AC6).**
  `scripts/verify_submission.py`. In `verify_one()`, when the folder's `draft_manifest.json` carries a
  populated `rubric_score`, call `audit_rubric_scores([folder])` (`verify_submission.py:252`) and write
  the outcome into the receipt as `rubric_audit: {ran, clean, findings}`. When no score is present yet,
  write `{ran: false, reason: "rubric_score not yet entered"}` — the normal mid-flow state, not a
  failure. The standalone `--audit` CLI mode stays exactly as it is for manual use. Be explicit in the
  code comment that this call mutates `data/.rubric_score_history.json`, and that re-running verify for
  the same company is idempotent (`history[key] = company`).
- [x] **Story 5.2 — Run `claim_provenance.py` and surface it as a WARN-tier field (AC4/AC9).**
  Same function. Import `claim_provenance` directly (it is importable:
  `check_claim_provenance(folder) -> (ok, errors)`) rather than shelling out, matching how
  `verify_submission.py` already imports `submission_linter` / `quality_checker` /
  `approved_metrics` / `jd_term_extractor` at lines 49-52. Write
  `claim_provenance: {ran: true, ok: bool, findings: [...]}` as a new top-level receipt key,
  positioned next to the other WARN-tier fields (`reading_order`, `jd_literal_term_gaps`). It must
  **not** be added to `mechanically_verified`'s conjunction (`verify_submission.py:225`) — that is the
  AC9 line. With Story 5.0 landed, submissions authored after this CR will have a real
  `claim_provenance.json` to check; the 41 legacy folders authored before it won't, and will correctly
  report `claim_provenance.json not found` — record it as-is, do not special-case legacy folders into
  silence.
- [x] **Story 5.3 — Wire `check_stage2_ready()` into both entry points (AC4, AC10).** (Cursor, 2026-08-07)
  `verify_submission.py`: after writing the receipt, evaluate `check_stage2_ready()` and print an
  explicit `STAGE 2: COMPLETE` / `STAGE 2: INCOMPLETE — <itemized>` verdict. Exit non-zero on a failed
  gate **only when a `rubric_score` is present** (see the locked decisions — this is what keeps the
  batch Finalize phase from breaking on every first-pass verify). Override requires `--force` **and**
  a non-empty `--force-reason`, enforced through `stage_gate.validate_force("stage2", ...)`, both
  written to the override log together; a bare `--force` at Stage 2 is rejected. Use
  `parse_force_flags` rather than migrating `main()` (`verify_submission.py:293`) to argparse — the
  hand-rolled parsing supports multi-folder invocation and `--audit` today and must keep doing so.
  `author_from_packet.py --verify-only` gets the same verdict line and the same Stage 2 force policy.
  Implementation: `stage_gate.apply_stage2_verdict()` shared by both entry points.
- [x] **Story 5.4 — AC8 regression check on the status oracle.** (Cursor, 2026-08-07)
  Confirm `scripts/check_submission_status.py` still produces the same report shape (same check names,
  same PASS/FAIL/WARN lines, same `STATUS: DONE|INCOMPLETE`, same exit codes) against a folder that
  passes and one that fails, before and after this CR. It calls `check_freshness` at line 68, so
  Epic 2 reaches it; results may legitimately change, the *shape* must not. No new gate is added to
  this script and its DONE/INCOMPLETE computation is not touched — both are explicit Out of Scope
  lines in the CR. Locked by `scripts/test_check_submission_status.py` (registered in `run_all_tests.py`).

---

## Epic 6 — Documentation and closeout

**Goal:** the new WARN check is in the list humans actually run, and the spec record matches the code.

- [x] **Story 6.1 — Add `claim_provenance.py` to Required Verification (AC9).** (Cursor, 2026-08-07 — parallel with Claude Code on Epic 5)
  `CLAUDE.md`'s "Required Verification Before You're Done" section, step 2, alongside
  `check_ground_truth_coverage.py` and `jd_term_extractor.py` — same tier, same framing (mechanical
  check whose output must be read, not a blocking gate). Add the one line of ordering the new Stage 2
  gate requires: after the rubric score is hand-entered, `verify_submission.py` must be re-run (it now
  performs the audit and refreshes the content hashes), then `--audit` as today. Minimal edit — do not
  restructure the section. **Copy the identical edit into `AGENTS.md`; those two files must stay
  byte-identical**, per the rule at the top of both. (Verified byte-identical via matching SHA-256 after copy.)
- [x] **Story 6.2 — Registry, changelog, and CR closeout.** (Cursor, 2026-08-07 — completed after Stories 5.3/5.4 landed)
  Reserved `FR-256` / `AC-278`–`AC-288` in `docs/spec/02-requirements-registry.md`, added the
  traceability rows in `docs/spec/06-traceability/traceability-matrix.md`, flipped CR-075 + README
  to **Implemented**, wrote `CHANGELOG.md` `[Unreleased]` entries, set this file's frontmatter
  `status: done`. OQ-1 / OQ-2 already recorded in this file and the CR's Second Revision section.

---

## Rollout priority

If only part of this ships, ship it in this order:

1. **Epic 1** — two edits in one JavaScript file, no Python coupling, and it is the only work here
   that directly prevents a repeat of the incident that produced the CR. Land it first even if
   everything else slips.
2. **Epic 2** — fixes a defect confirmed live on three folders, and every later gate reads the
   lineage it establishes. Story 2.1 (the missing `test_contracts.py`) is a prerequisite for touching
   `contracts.py` safely at all, so it comes before 2.3 rather than after.
3. **Epic 3** — inert on its own; landing it early is free and makes Epics 4 and 5 small.
4. **Epic 4 then Epic 5** — in that order. Epic 5's gate reads receipt fields Epic 5 itself writes,
   so its stories are internally ordered 5.0 (Stage 1 emits the file) then 5.1/5.2 (produce the
   receipt fields) before 5.3 (enforce on them); do not invert that or the gate will fail on every
   folder the moment it is wired, and Story 5.2 will have nothing real to surface if 5.0 hasn't landed.
5. **Epic 6** — last, but it is not optional. The CR's own argument for WARN-tier `claim_provenance`
   rests entirely on Story 6.1 existing; without it, Epic 5 Story 5.2 ships a JSON field nobody reads.

**OQ-1 and OQ-2 are resolved** (see "Open questions from the epics pass — RESOLVED" above and CR-075's
own "Second Revision" section) — Story 4.3 and Story 5.0 implement final decisions, not interim ones.
Nothing in this tracker is blocked on an outstanding answer.

---

## Follow-ups from 2026-08-07 CSV test run (post CR-075)

CR-075 itself stays **Implemented / done**. These are adjacent Stage 0 / suite / smoke gaps found
while running `applyr_jobs (1).csv` through the gated path. Do **not** treat them as unfinished
CR-075 stories — track and land them as post-work (likely a small Stage 0 hardening CR or a
CR-074 packet fail-closed patch).

### Must-fix (fail-open still live)

- [x] **Empty-bucket Stage 0 → false Tier 1.** (landed with Round 4 optimization-bar pass, 2026-08-07)
  Non-thin JD with empty required+preferred+responsibilities appends `extraction_empty` soft gap → Tier 2.
- [x] **Empty-bucket packet → not `packet_status: ready`.** (same pass)
- [x] **Register stage0/packet/author tests in `run_all_tests.py`.** (same pass)
- [x] **Round 4 draft optimization bar fail-closed.** Digest §1b; Stage 0 domain soft-flag;
  packet `soft_gaps[].claim_ids` + compliance claim scoring; `--verify-only` fails on unused
  soft_gap/required claim_ids; rubric “Stop improving” removed; SKILL/CLAUDE/AGENTS synced.
  Central Bank rebuilt: Tier 2, ACC-107 bridge in docs, Stage 2 COMPLETE, verify-only PASS.

### Already patched in the CSV session (keep; do not regress)

- [x] **Curly/smart apostrophe normalization** in `build_stage0_fit_gate._extract_sections` via
  `_normalize_jd_punctuation` (U+2018/U+2019/etc. → ASCII `'`), plus
  `TestSectionExtraction.test_curly_apostrophe_headers_extract`. This fixed Pinterest
  `What you'll do` / `What we're looking for` extracting empty. It is **not** a substitute for
  the empty-bucket fail-closes above.
- [x] **ATS boilerplate bleed out of quals buckets (2026-08-07):** ignore-headers (end-anchored)
  + item denylist in `_extract_sections`; Pinterest unit fixture; corpus eval
  `scripts/eval_stage0_boilerplate.py` on 408 archive/live JDs (`confidence_gate` PASS).

### CSV smoke still incomplete (process coverage, not product bugs)

- [x] Pinterest Tier 2 Stage 1–3 authored (AI/ML soft gap → ACC-120 CONTRIBUTED bridge;
  Stage 2 COMPLETE; finalized to Backlog).
- [x] Central Bank hand rubric → `draft_manifest.json` → re-verify → `--audit` so
  `STAGE 2: COMPLETE` fires once for real. (2026-08-07: resume 78 / cover 89 with SecureU hook;
  audit clean. Rebuilt with ACC-107 compliance bridge under optimization bar.)
- [x] Tier 1 cover-letter hook research (`research-engine.py --hook-fact`) run on
  Central Bank (SecureU fraud-awareness).
- [x] Thermo Fisher Stage 0 DB Skip overridden per Jason; Digital PM drafted + Stage 2/3 done.
  Also fixed `finalize_submission_job` company-only UPDATE clobbering Closed Gas Analyzers row.
- [x] Stage 3 `finalize_submission_job` exercised on Central Bank / Pinterest / Thermo.
