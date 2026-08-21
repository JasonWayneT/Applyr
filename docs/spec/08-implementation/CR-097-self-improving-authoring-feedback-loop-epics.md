---
status: in_progress
created: 2026-08-21
related: CR-096 (stage1-3-audit-remediation — names this as "Piece A"), CR-093 (evidence-scale fit engine — `fit_rubric_examples.py` precedent, unmodified), CR-074 (token-conscious authoring packet — owns the digest budget and the packet contract this injects into), CR-076–084 (workflow authority — owns `run_submission.py` / `scripts/workflow/`), CR-094 (WE-primary packet)
contains: CR-097 (Self-Improving Stage 1 Authoring Feedback Loop)
---

# CR-097 — Self-Improving Stage 1 Authoring Feedback Loop: Epics & Stories

**Handoff doc, one change request.** This is the resumable plan for making confirmed authoring
corrections durably reduce how often the same mistake needs correcting again. Read top-to-bottom
before doing anything; check off stories as completed; a new session can pick up at the first
unchecked story with no other context beyond this file, `docs/spec/05-change-requests/CR-097-self-improving-authoring-feedback-loop.md`,
and the files referenced below.

**The CR's four product decisions are locked (2026-08-21) and are not reopened here.** Storage is
split by failure type (digest keeps binary structural rules, a new retrieval bank takes contextual
examples); the trigger is automatic-on-repeat at 2+ independent submissions; the bank targets "the
rule exists but was not applied to a case shaped like X" while "the rule does not exist yet" stays a
digest hand-edit; the promotion bar is the same 2 by construction. This tracker designs the
mechanics only.

---

## Why this exists (do not re-litigate without re-reading this)

Jason's ask, verbatim from CR-096: *"I am particularly interested in getting the first draft to have
as little corrections needed as possible and I wonder if the checker can inform the first draft
process over time some kind of mechanic to self improve."*

Today nothing carries a confirmed correction from one submission into the next. The only time it ever
happened was CR-096's Fix 6, where a human noticed three repeat mistakes during an unrelated audit and
hand-edited `data/authoring_rule_digest.md`. That edit also consumed the last of the digest's budget:
it now sits at **7,989 chars against a coded 8,000-char soft target and a 10,000-char hard limit**
(`scripts/generate_authoring_rule_digest.py:31-33`). There is no room to keep answering "the model
made this mistake again" with more digest text, which is why the locked decision routes contextual
examples to a separate, retrieval-scoped bank.

### What the real code says (verified by direct read this pass, not inferred)

1. **There is no cross-submission read anywhere in the pipeline.** `scripts/workflow/reviews.py` and
   `scripts/workflow/runner.py` only ever read `reviews/*_findings.json` and `reviews/dispositions.json`
   inside the folder currently being processed. The one existing cross-submission accumulator in the
   whole repo is `data/.rubric_score_history.json`, written by `verify_submission.py`'s
   `audit_rubric_scores()`. That file is the shape precedent for this CR's ledger: a repo-level JSON
   under `data/` (covered by `.gitignore`'s `data/*.json`, so real company slugs never become tracked).

2. **The three SR-06 target categories cannot be observed where the CR assumed they would be, and this
   is the single most important finding in this pass.** All three are `HARD_BLOCK` rules in
   `scripts/submission_linter.py`:
   - wrong-job content bleed → **no rule exists at all** (see Epic 5)
   - gap-confession → `LR-016`
   - forbidden punctuation → `LR-006` (em dash / `--`), `LR-014` (semicolon), `LR-015` (colon-as-elaboration)

   Hard blocks are caught and fixed at **Stage 1**, not Stage 2: `runner.run_stage1_validate()` calls
   `author_from_packet.run_verify_only()`, which lints both documents and raises `WorkflowError` on any
   hard block, so a first draft carrying `LR-016` never reaches Stage 2 at all. Measured across all 30
   real folders in `data/submissions/`: **9 folders have a `dispositions.json`, 6 `RESOLVED_EDIT`
   dispositions exist in total, and every one of them is a `LW-*` warn** (`LW-009-PAIR` x3,
   `LW-008-PAIR`, `LW-011`, `LW-001`). Zero `LR-006/014/015/016` findings exist anywhere in any
   `reviews/*_findings.json`. Counting `RESOLVED_EDIT` dispositions for the SR-06 categories would
   return identically zero forever, and the 2-occurrence trigger would never fire.

   **Design consequence (not a spec change):** the primary observation point is the Stage 1 verify gate,
   which is strictly closer to Jason's actual ask ("first draft needs fewer corrections") than Stage 2
   dispositions are. Stage 2 dispositions stay wired as a secondary source, because SR-09's wording names
   them and future non-hard-block categories will surface there. Nothing about SR-05's intent changes:
   the count is still "how often did a targeted category need correcting," just read at the point where
   those categories actually appear.

3. **The Stage 1 verify result is not persisted anywhere.** `run_verify_only()`
   (`scripts/author_from_packet.py:302-397`) prints a summary and returns a bool; on failure
   `run_stage1_validate` raises before writing any receipt. So the first draft's defects are visible for
   exactly one console scroll and then gone. Nothing in this repo can currently answer "did this draft
   trip LR-016 before the agent fixed it." Epic 1 fixes that, and Epic 1 has standalone value even if the
   rest of this CR is never built.

4. **Dispositions record that an edit happened, never what the edit was.** `dispositions.json` maps a
   finding id to one of five enum values (`reviews.py:23-32`). A bank entry needs a corrected
   before/after pair, so the "after" text has to come from a first-draft snapshot diffed against the
   final document. Nothing snapshots the first draft today.

5. **The packet is dumped whole into the Stage 1 prompt.** `author_from_packet.build_authoring_prompt()`
   writes `SYSTEM = digest text`, `USER = preamble + json.dumps(packet)`. Anything added to the packet
   dict reaches the authoring model with no other plumbing. `assemble_packet()`
   (`build_authoring_packet.py:1347-1412`) already stamps `rule_digest_version` from
   `data/authoring_rule_digest.version`, and `_check_packet_ready()` refuses to author on a version
   mismatch — that is the versioning precedent the bank reuses.

### Success signal (SR-05), made actually countable

Every ledger occurrence is stamped with the `rule_digest_version` and `example_bank_version` the packet
was built against. That means the before/after comparison is computable from one continuous stream and
needs no separate quiet baseline phase: `scan_authoring_defects.py --report --last 10` splits occurrence
counts per category by whether the authoring packet had bank examples in it or not.

---

## Architecture decisions (made in this pass; rationale so they are not silently reversed)

- **New bank file, not an extension of `fit_rubric_golden_set.json`.** Locked by SR-08, and correct:
  different prompt (Stage 1 document authoring vs Stage 0 line classification), different vocabulary
  (`expected_gate`/`expected_evidence_level` vs `before`/`after`), different lifecycle. CR-093's files
  are read as precedent and never modified.
- **Real deviation from the precedent's retrieval, deliberately.** `fit_rubric_examples.retrieve_examples()`
  ranks the whole bank by Jaccard against **one JD line**. Stage 1's query is a whole packet, so Jaccard's
  union term makes every score collapse toward zero and effectively ranks by entry length instead of
  relevance. Two changes: (a) score with **containment** (`|query ∩ entry| / |entry|`), not Jaccard;
  (b) demote similarity to an **intra-category tiebreak** and make the primary selector
  condition-gating plus per-category slot caps — because the v1 categories are mostly JD-independent
  ("never use a semicolon" does not get more or less relevant with the JD). This still satisfies SR-03:
  selection is per-session and capped, never a growing block appended to every prompt.
- **Three new scripts, each with a stated reason to be separate.** `scripts/authoring_examples.py` is
  imported by the packet builder and must stay import-light and side-effect-free (same discipline
  CR-075 applied to `contracts.py` vs `stage_gate.py`). `scripts/scan_authoring_defects.py` is a batch
  CLI that writes the ledger — side effects are its whole job, so it must not be importable-by-accident
  from the authoring path. `scripts/authoring_defect_categories.py` holds the `rule_id → category` map
  used by both, so the map cannot drift into two copies.
- **The detection scan never blocks a submission.** SR-09 requires a mandatory human *review*, not a
  mandatory *gate*. Blocking a real job application on a process chore is the wrong tradeoff during an
  active job search, and the orchestrator's receipt chain stays out of it entirely. The scan is called
  in advisory mode after the Stage 2 receipt is already minted, and prints an explicit
  `[defect_scan, status: warning]` line on failure rather than failing silently (the pattern CR-054
  Epic 2 blessed for genuinely best-effort work).
- **Stale-bank posture is WARN, not hard fail.** `rule_digest_version` hard-fails because the digest is
  a rules contract. The bank is advisory few-shot content: a packet built one bank version ago is still
  correct, so a mismatch prints a warning and does not force a rebuild. Do not copy the digest's
  hard-fail here.
- **Cross-folder reads never touch another submission's documents.** SKILL.md's standing rule ("Every
  company's application is judged, authored, and verified entirely on its own") is about not comparing
  documents. The ledger scanner reads defect metadata (rule ids, categories, slugs); Epic 5's bleed
  check reads a **company-name index only**. Neither ever reads another folder's `Resume.md` /
  `CoverLetter.md`.
- **Per-folder artifacts live in a subdirectory, not the folder root.** `stage1_first_draft/` holds the
  snapshot plus `verify_history.json`. Verified safe: `submission_linter.lint_folder()` uses a
  non-recursive `os.listdir` and only accepts exactly `Resume.md`/`CoverLetter.md` at top level, and
  `server/routes/jobs/files.ts:18` uses a non-recursive `readdirSync` with an extension filter, so a
  snapshot copy can never be linted as a second resume (the `Interview_Cheat_Sheet.md` bug class) or
  surface in the app's file list.

---

## Epic 0 — Diagnosis (COMPLETE, 2026-08-21 tech-lead pass)

- [x] Read `scripts/fit_rubric_examples.py` + `data/fit_rubric_golden_set.json` in full; confirm the
      retrieval shape, the `few_shot_eligible` curation gate, and the stated "no embeddings until
      ~10-15 entries per category" threshold.
- [x] Read the exact read/write contract in `scripts/workflow/reviews.py` + `scripts/workflow/runner.py`;
      confirm no cross-submission read exists anywhere.
- [x] Map each SR-06 category to a real mechanical signal: `LR-016`; `LR-006`/`LR-014`/`LR-015`; and
      **nothing at all** for wrong-job content bleed.
- [x] Measure the real disposition corpus (30 folders, 9 with dispositions, 6 `RESOLVED_EDIT`, all
      `LW-*`) and conclude that Stage 2 dispositions cannot carry the SR-06 categories.
- [x] Confirm the packet → prompt injection path (`assemble_packet` → `build_authoring_prompt`) and the
      `rule_digest_version` stamping precedent.

Re-derive the disposition corpus with:
```bash
python -c "import json,glob;from pathlib import Path;[print(Path(p).parts[2],[(k,v) for k,v in (json.load(open(p,encoding='utf-8')).get('by_finding_id') or {}).items() if v=='RESOLVED_EDIT']) for p in sorted(glob.glob('data/submissions/*/reviews/dispositions.json'))]"
```

---

## Epic 1 — Make first-draft defects observable (do this first; cheapest, standalone value)

**Goal:** every Stage 1 verify attempt leaves a durable, structured record of which rules the draft
tripped, and the first draft's text is preserved so a corrected before/after can be recovered later.

- [x] **Story 1.1 — Category map module.** New `scripts/authoring_defect_categories.py`: a frozen
      `RULE_CATEGORY: dict[str, str]` mapping `LR-016 → "gap_confession"`, `LR-006`/`LR-014`/`LR-015`
      → `"forbidden_punctuation"`, plus `CATEGORIES` tuple including `"wrong_job_bleed"` (populated by
      Epic 5). Pure constants and two lookup helpers (`category_for_rule`, `rule_ids_for_category`), no
      I/O, no imports beyond stdlib. This is the single source of truth both the scanner and the bank
      validator use.
- [x] **Story 1.2 — Persist structured verify results.** Extend `author_from_packet.run_verify_only()`
      with a keyword-only `record_to: Path | None = None`. When set, it appends one entry to
      `{folder}/stage1_first_draft/verify_history.json`: `{attempt, observed_at, passed,
      resume_sha256, cover_sha256, rule_digest_version, example_bank_version, violations: [{rule_id,
      severity, doc, line, category}]}`. Append is idempotent on the `(resume_sha256, cover_sha256)`
      pair, so re-running `--resume` on unchanged documents does not mint a phantom attempt. Existing
      callers keep today's signature and behavior; the bool return is unchanged.
- [x] **Story 1.3 — Wire the recorder into the orchestrator.** In `runner.run_stage1_validate()`
      (`scripts/workflow/runner.py:413`), pass `record_to=Path(folder)`. Recording must happen inside
      `run_verify_only` because the runner raises `WorkflowError` on failure before it could write
      anything itself — the failing attempt is exactly the one worth recording.
- [x] **Story 1.4 — First-draft snapshot.** On the first recorded attempt only, copy `Resume.md` and
      `CoverLetter.md` into `{folder}/stage1_first_draft/`. Write-once: never overwrite an existing
      snapshot, so later fix rounds cannot destroy the "before" text. Reuse the snapshot-before-mutation
      pattern from CR-054 Story 1.4 (`scripts/audit_and_improve.py`).
- [x] **Story 1.5 — Tests.** Extend `scripts/test_author_from_packet.py`: a draft with a seeded
      semicolon records one `forbidden_punctuation` violation and a snapshot; a re-run on identical
      bytes adds no second attempt; a re-run after an edit adds attempt 2 and leaves the snapshot
      untouched; `record_to=None` writes nothing. Register anything new in `scripts/run_all_tests.py`.

---

## Epic 2 — Cross-submission ledger and the 2-occurrence trigger (SR-01, SR-09, SR-11)

**Goal:** the second time a targeted category shows up on a different submission, a named review item
opens by itself and stays visible until a human promotes or declines it.

- [x] **Story 2.1 — Ledger schema and scanner core.** New `scripts/scan_authoring_defects.py` writing
      `data/authoring_defect_ledger.json`: `{schema_version, generated_at, occurrences[], reviews[]}`.
      Each occurrence is `{key, slug, category, rule_id, stage, doc, line, observed_at,
      rule_digest_version, example_bank_version, evidence_ref}` with
      `key = f"{slug}|{stage}|{attempt}|{rule_id}|{doc}|{line}"` so repeated scans are idempotent.
      Primary source: every `data/submissions/*/stage1_first_draft/verify_history.json`. Missing files
      are skipped, never raise (same posture as `fit_rubric_examples.load_few_shot_examples`).
- [x] **Story 2.2 — Secondary source: Stage 2 dispositions.** Also walk
      `data/submissions/*/reviews/{truth,ats,hm,mech}_findings.json` + `dispositions.json`, and record an
      occurrence for any finding disposed `RESOLVED_EDIT` whose rule id maps to a target category.
      **Parse the rule id with a regex (`L[RW]-\d+[A-Z-]*`) against the finding id or its `message`, not
      by splitting the id on dots** — real finding ids contain dots and spaces inside the doc segment
      (`hm.lint.warn.resume+cover_letter (pair).LW-009-PAIR.0`, `hm.lint.warn.cover_letter hook vs
      JD.LW-011.0`). Expect this source to be empty for the SR-06 categories today; it is wired for
      SR-09 fidelity and future categories.
- [x] **Story 2.3 — Repeat detection and the review queue.** Group occurrences by category and count
      **distinct slugs**. At 2+ distinct slugs not already covered by a `promoted` or `declined` review,
      append `{id, category, distinct_slugs, opened_at, status: "pending_review", bank_entry_id: null,
      resolution_note: null}` to `reviews[]`. A promoted or declined review re-opens when 2 further
      distinct slugs accumulate after it — that is how a promoted example that is not working comes back
      for another look.
- [x] **Story 2.4 — CLI surfaces.** `--status` prints each pending review with its category, its slugs,
      and the exact `evidence_ref` paths to read, exiting 3 when anything is pending (0 when clean).
      Default (no flags) scans, updates the ledger, and prints a one-line summary plus the pending count.
      Both must run standalone from the repo root with no orchestrator involvement.
- [x] **Story 2.5 — Advisory call from the workflow.** At the end of `runner.run_stage2_policy()`, after
      the Stage 2 COMPLETE receipt is committed, call the scanner in-process inside a `try/except` that
      can only print. Success prints `[defect_scan, status: ok] N pending review(s)`; any exception
      prints `[defect_scan, status: warning] <reason>`. It must not write to `workflow_state.json`, any
      receipt, or any subphase status, and must never change the command's exit code.
- [x] **Story 2.6 — Standing trigger in the skill.** Add the scan to the **existing** cross-batch sweep
      paragraph in `.claude/skills/generate-submission/SKILL.md` (Required Verification, the "every 3 new
      submissions / before any send-batch" trigger). Do not add a new numbered rule anywhere — the
      Self-Repair Protocol's own item 4 forbids growing the prose list, and this belongs to a trigger
      that already exists.
- [x] **Story 2.7 — Tests.** New `scripts/test_scan_authoring_defects.py` on tempdir fixtures: one slug
      with one occurrence opens no review; two slugs same category opens exactly one; a re-scan opens no
      duplicate and adds no duplicate occurrences; a declined review plus two new slugs re-opens; a
      malformed `verify_history.json` is skipped without raising. Register in `run_all_tests.py`.

---

## Epic 3 — The retrieval bank and its Stage 1 injection (SR-08, SR-03, SR-10)

**Goal:** a curated example reaches the authoring model on the jobs where it applies, capped, and
without costing the packet its evidence budget.

- [x] **Story 3.1 — Bank file and schema.** New `data/authoring_example_bank.json`:
      `{schema_version, description, categories, entries[]}`. Each entry:
      `{id, category, rule_ids[], added_date, source_slugs[] (>=2, SR-11), confirmed_by, status:
      active|superseded, few_shot_eligible: bool, applies_when: {mode: "always"|"packet_condition",
      condition}, match_text, before, after, why}`. The `description` field carries the append-only
      curation discipline in the file itself, exactly as `fit_rubric_golden_set.json` does (never edit a
      shipped entry in place; supersede and add). Ship the file with `entries: []` — Epic 4 seeds it.
- [x] **Story 3.2 — Selection module.** New `scripts/authoring_examples.py`, modeled on
      `fit_rubric_examples.py` but not copied: `load_bank()` (returns `[]` when the file is missing,
      never raises), `bank_version()` (first 16 hex of sha256 of file bytes, mirroring
      `generate_authoring_rule_digest._version_from_content`), and
      `select_examples(context, k=3, max_chars=1200)`. Selection order: filter to `status == "active"`
      and `few_shot_eligible`; drop entries whose `applies_when` condition is unmet (`soft_gaps_present`
      is the only v1 condition); take at most **1 entry per category**; break intra-category ties by
      containment score against `match_text` then by `added_date` descending; stop at `k` entries or
      `max_chars`, whichever comes first. Docstring must state why containment replaces the precedent's
      Jaccard and why embeddings stay out of v1 (bank starts at zero entries).
- [x] **Story 3.3 — Packet injection.** In `build_authoring_packet.assemble_packet()`, add
      `learned_examples: []` and `example_bank_version` to the draft dict, positioned **after**
      `thin_jd` so they render last in the dumped JSON (recency, the same reason Fix 6 put the
      self-check last in the digest). Build the context from `jd_buckets` + `soft_gaps`.
- [x] **Story 3.4 — Budget ordering rule (do not get this backwards).** `learned_examples` is counted
      inside `estimated_tokens` before the `_TOKEN_BUDGET` check. If the packet is over budget,
      **drop examples first**, one at a time, and only call `_shrink_excerpts_to_budget()` if it is
      still over after the examples are gone. Evidence never gets truncated to make room for a teaching
      example. Add this as an explicit comment at the call site.
- [x] **Story 3.5 — Prompt rendering.** In `author_from_packet.build_authoring_prompt()`, render a
      compact block after the packet JSON (last thing in the USER block) when `learned_examples` is
      non-empty, one `BEFORE:` / `AFTER:` / `why` line group per entry under a heading that states these
      are real corrected drafts, not new rules. Mirrors `fit_rubric_examples.format_examples_for_prompt()`
      returning `""` for the empty case so the caller splices unconditionally. Add `example_bank_version`
      to the returned `meta` dict.
- [x] **Story 3.6 — Stale-bank posture.** In `author_from_packet._check_packet_ready()`, compare the
      packet's `example_bank_version` against the current bank and print a **warning only** on mismatch.
      Do not raise, and do not extend the existing `rule_digest_version` hard failure to cover it (see
      Architecture decisions).
- [x] **Story 3.7 — Contract doc + tests.** Add `learned_examples` and `example_bank_version` to
      `scripts/contracts/authoring_packet_schema.json` (top level is `additionalProperties: false`;
      the file is a documentation contract, not runtime-validated, but it must not go stale). Extend
      `scripts/test_build_authoring_packet.py` and `scripts/test_author_from_packet.py`: empty bank
      yields `learned_examples: []` and an unchanged prompt; a fixture bank yields at most one entry per
      category; an over-budget packet drops examples before shrinking excerpts; a version mismatch warns
      instead of raising.

---

## Epic 4 — Seed the bank and make curation a real gate (SR-02, SR-06)

**Goal:** the first real entries exist, and no path can put an entry in front of the authoring model
without a human explicitly marking it eligible.

- [x] **Story 4.1 — `--promote` scaffold.** `scan_authoring_defects.py --promote {review_id}` appends a
      skeleton entry to the bank with `before`/`after`/`why` set to `"TODO"` and
      **`few_shot_eligible: false`**, fills `category`/`rule_ids`/`source_slugs` from the review, sets
      `bank_entry_id` on the review, and prints the file plus the evidence paths to read. Flipping
      `few_shot_eligible` to `true` is a human edit and nothing in the codebase may do it. Also support
      `--decline {review_id} --note "..."`.
- [x] **Story 4.2 — Seed `gap_confession`.** Using the CR-096 Fix 6 evidence and `LR-016`'s own real
      history (the five 2026-07-21 letters: "is new territory for me," "I have not yet applied that
      thinking," "are new to me"), write one entry with a real before line and the corrected bridge
      sentence that replaced it. `applies_when.mode = "packet_condition"`, `condition =
      "soft_gaps_present"` — the failure only exists when there is a gap to confess.
- [x] **Story 4.3 — Seed `forbidden_punctuation`.** One entry, `applies_when.mode = "always"`, capped at
      a single slot by Story 3.2's per-category rule so an always-on entry is a rotation and not
      accretion. Prefer a colon-as-elaboration (`LR-015`) case over a bare semicolon: it is the variant
      the model reaches for while trying to obey the em-dash rule, which is exactly the "rule exists but
      is not applied to a case shaped like X" target SR-10 names.
- [x] **Story 4.4 — Curation checklist.** Three or four lines inside the bank's own `description` field
      (not a separate doc): entry needs 2+ distinct `source_slugs`, a real before/after from real
      drafted text, a `why` naming which digest rule already covered it, and a `confirmed_by`. Same
      self-documenting posture as `fit_rubric_golden_set.json`.

---

## Epic 5 — Wrong-job content bleed detection (the one category with no signal today)

**Goal:** the third SR-06 category becomes observable at all, so it can be counted and eventually
promoted. Deliberately last: it is the only story group that needs a brand-new heuristic, and it
carries the highest false-positive risk. Epics 1-4 deliver the full loop for the other two categories
without it.

- [x] **Story 5.1 — Company-name index.** A helper that returns the set of company names Applyr knows
      about, read from `data/jobagent.sqlite`'s `jobs.company` column (plus `stage0_fit_gate.json`'s
      `company` where a folder has no row). Names only. It must never open another submission's
      `Resume.md` or `CoverLetter.md` — see the cross-folder rule in Architecture decisions.
- [x] **Story 5.2 — Folder-level lint rule.** Add a `WARN`-tier check to `submission_linter.lint_folder()`
      alongside the existing JD-aware checks (`LW-011` reads `Original_JD.txt` the same way): flag any
      company name from the index that appears in this folder's documents and is neither this
      submission's own company nor present in `Original_JD.txt`. WARN, not `HARD_BLOCK` — a first
      version of a new heuristic must not be able to stop a real application. Precision first: match on
      known company names only, not general capitalized-proper-noun guessing.
- [x] **Story 5.3 — Register the category.** Add the new rule id to
      `authoring_defect_categories.RULE_CATEGORY` under `"wrong_job_bleed"`. No other change is needed:
      Epic 1's recorder already writes every violation, and Epic 2's scanner already groups by category.
- [x] **Story 5.4 — Tests.** Extend `scripts/test_submission_linter.py`: a letter naming a different
      known company warns; the same letter naming its own company does not; a company named in
      `Original_JD.txt` (a real partner or competitor mention) does not warn; a missing DB is skipped
      without raising.
- [ ] **Story 5.5 — Seed the category once it has evidence.** Only after two real occurrences appear in
      the ledger. Do not hand-write a bleed entry ahead of the trigger — that is exactly the
      single-occurrence overfitting SR-11 exists to prevent.

---

## Epic 6 — Measurement and documentation (SR-05, plus the repo's own doc checklist)

**Goal:** someone can actually run the number that decides whether this worked.

- [x] **Story 6.1 — `--report`.** `scan_authoring_defects.py --report --last 10` prints per-category
      occurrence counts across the 10 most recent submissions by first-draft date, split by whether the
      packet carried bank examples (`example_bank_version` present and non-empty vs not). Print the slug
      list for each side so the number is auditable rather than asserted.
- [ ] **Story 6.2 — Read the number at 10 real submissions post-launch** and record the result in
      `pipeline-log.md`. If the targeted categories have not fallen, say so plainly and treat it as a
      finding about the mechanism, not a reason to add more entries.
- [x] **Story 6.3 — Documentation closeout.** `CHANGELOG.md` entry; `PRODUCT_CAPABILITIES.md` if the
      capability surface changed; `README.md`'s Project structure section for the three new scripts;
      `AGENTS.md`'s File Map rows for `data/authoring_example_bank.json` and
      `data/authoring_defect_ledger.json`. Per AGENTS.md's Documentation Update Checklist, this is not
      optional cleanup.

---

## Rollout priority

**Epic 1 first, regardless of what else is in flight.** It is small, it touches one function plus one
call site, and it is the only thing standing between this project and having any first-draft quality
data at all. It also has value on its own: even if Epics 2-6 never ship, `stage1_first_draft/` gives a
real answer to "is the first draft getting better," which is the question CR-096 could only answer by
one person's recollection.

Then **Epic 2**, which turns that data into the SR-09 trigger and is the last piece needed before the
bank has anything trustworthy to be seeded from. Epics 1-2 together are shippable and useful with an
empty bank.

**Epic 3 before Epic 4**, and do not seed the bank until Story 3.4's budget ordering is in place — an
example that silently truncates a WE excerpt would cost more accuracy than it buys, and the failure
would be invisible in the output.

**Epic 5 last.** It is the only new heuristic in the CR, it is the one most likely to need tuning
against real false positives, and holding it back keeps the first live version of this loop to
mechanisms that are already proven in this codebase. If it turns out noisy, the right move is to
narrow the match, not to promote it to `HARD_BLOCK`.

No separate quiet baseline window is needed before Epic 3 lands: every occurrence carries the bank
version it was authored against, so Epic 6's before/after split is computable from one continuous
stream. The SR-05 window is the 10 real submissions following Epic 3.
