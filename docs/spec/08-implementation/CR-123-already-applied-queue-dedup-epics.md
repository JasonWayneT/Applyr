---
status: complete
created: 2026-09-21
related: CR-091 (skip ledger stays Skip memory only), CR-092 (different-role active_application flag stays), CR-119 (Decision 12 + queue transitions + fencing; extended not replaced), CR-121 (conversion_risk untouched), CR-122 (skill-presence pause untouched), ADR-001 (SQLite local-first), FR-342 / AC-440 (lookup set was incomplete)
contains: CR-123 (Already-applied and archived postings close the CSV queue)
---

# CR-123 — Already-applied queue dedup: Epics & Stories

**Handoff doc.** Resumable plan for
[CR-123](../05-change-requests/CR-123-already-applied-queue-dedup.md)
(PM locked 2026-09-21; Jason: design miss, proceed; OQ-1 no re-apply override).
A new session picks up at the **first unchecked story**. One senior-engineer
pass completes one story and stops. QA marks the box, not the engineer.

Product decisions are closed. Do not reopen posting identity, Applied+ membership,
skip-ledger reuse, different-role flags, cooldown / Self-Rejected, or a force-requeue
control. If a product call is actually missing, stop and log an OQ in
`pipeline-log.md` under Product Manager. Do not invent it here.

```
Epic 1 (ingest refuse)  →  Epic 2 (claim / fence close)
                        →  Epic 3 (status update)
                        →  Epic 4 (Stage 0 already-handled)
                        →  Epic 5 (reconcile ghosts + docs)
```

Cheapest, highest-confidence first: a resolver action plus tests cannot
lease, author, or write the skip ledger. Architecture that can clobber a
live worker stays later, behind the existing fence.

---

## Why this exists (read this before touching anything)

Five facts, verified against the live repo this pass, not recalled.

1. **`resolve_opportunity()` never looks at `jobs.status` or archive trees.**
   `scripts/csv_ingest.py:311-353` returns `create` / `reuse` / `skip_ledger`.
   Order today: skip ledger, then live `pending_review/` + live `submissions/`
   + `pipeline_queue` (`_slug_for_url` / `_slug_for_posting`).
   `url_to_slug()` already reads `jobs.url` for a slug map, but
   `_slug_for_url()` does not use that map. Archive roots are not scanned.

2. **Reuse with no queue row inserts a new `queued` row.**
   `scripts/ingest_csv_queue.py:159-177`: `action == "reuse"` and
   `get_row(conn, slug) is None` calls `upsert_queued()`. That is the ghost
   factory. An archive hit must not be `reuse`.

3. **`LEGAL_TRANSITIONS` cannot close `queued` or `leased`.**
   `scripts/pipeline_queue.py:272-284` allows `paused→done` and
   `in_progress→done` only. `mark_done()` (`:297-318`) returns the row
   unchanged unless status is `paused` or `in_progress`. CR-119 Story 3.1
   even forbade inventing `queued→done`. CR-123 requires those two pairs.
   That is an extension of the CR-119 table, not a seventh status.

4. **Every status write is already fenced.**
   `transition()` (`:384-398`): if `locked_by` is set, the UPDATE is
   `slug + fencing_token + locked_by`; if not, `slug + fencing_token +
   locked_by IS NULL`. A stale token is `FenceRejected` and leaves SQLite
   unchanged. There is no runner-kill API. CR-119 Decision 20 kills the
   child only when the *worker process* dies.

5. **Same-posting Applied+ today PASSes with a human flag.**
   `_find_active_applications()` (`scripts/stage0_db_gate.py:488-539`) is
   company-level, role-filtered by `is_different_role()`, and does not
   SELECT `url`. `build_stage0_fit_gate.py:3805-3808` attaches
   `active_application` and keeps `decision=PASS`. Placement on `SKIP`
   writes `stage0_skips` and moves the folder to `archive/skipped/`
   (`stage0_placement.py:89-104`). Placement on any other decision already
   no-ops (`:114`). `policy.evaluate_stage0()` only knows PASS / SKIP /
   FAIL. The runner treats non-PASS-non-SKIP as FAILED
   (`workflow/runner.py:518-528`).

Live ghosts this CR must close after ship (tests stay synthetic): Certara,
PeopleFinders, Velosio, Clarion Events, Velera (Applied +
`archive/submissions/`, queue `paused`); GoodRx, Omnissa (SKIPPED archive,
queue still `paused`).

---

## Architecture decisions locked in this pass (do not re-derive them per story)

Tech-lead calls against the real code. If one is wrong once you are in the
file, say so and stop. Do not quietly pick a different design.

### Pattern reuse: extend Decision 12 and the existing fence. Nothing new.

| Need | Existing pattern | Not this |
|------|------------------|----------|
| Ingest refuse | New resolver action `already_handled`, counted like `skip_ledger` (no folder, no insert, no ledger write) | Do not reuse `reuse` (that upserts). Do not write `stage0_skips` |
| Close `queued` / `paused` | `transition(..., "done")` with the unlocked fence (`locked_by IS NULL`) | No seventh queue status |
| Close `leased` / `in_progress` | Holder's own token, or claim-time expiry reclaim that already knows `locked_by` + `fencing_token` | No runner-kill. No unfenced UPDATE. Ingest and `applyJobStatusUpdate` do not clobber a live lease |
| Stage 0 terminal | New gate `decision=ALREADY_HANDLED`. Placement already no-ops unknown decisions. Policy + runner grow one verdict so it is not FAIL and not SKIP | Do not call the SKIP placement / `record_skip` path. Do not use CR-121 `conversion_risk` |
| Status update | Same posting identity as ingest (`normalizeSkipUrl` / `postingKey` already in `server/stage0SkipLedger.ts`) | Do not archive extra folders. Do not spawn Python from the HTTP path |
| Ghosts | One `reconcile_already_handled()` used by CLI and ingest | Do not mass-delete `pending_review/` or archive trees |

### Resolver order (Decision 12 extended, not replaced)

`resolve_opportunity()` stays the single implementation. New action string:
`already_handled`. Order:

1. Skip ledger (unchanged) → `skip_ledger`
2. `jobs` Applied+ (URL via `normalize_url`, else exact company+title) → `already_handled`
3. Live `pending_review/` / live `submissions/` / existing queue row → `reuse`
4. `data/archive/submissions/` or `data/archive/skipped/` (same identity) → `already_handled`
5. else → `create`

URL present: URL match only. Do not also company+title-match a different URL
at the same company. URL absent: `posting_key(company, title)` / exact
lowered company+title. Import `normalize_url` and `posting_key` from
`stage0_skip_ledger`. Compare `jobs.url` by normalizing both sides.

Applied+ membership is exactly
`shared/domain/jobPipeline.ts` `APPLICATION_FUNNEL_STATUSES`:
`Applied`, `Recruiter Screen`, `Core Interviews`, `Offer and Negotiation`.
Python gets a frozenset with those four strings and a comment pointing at
that file. Do not treat Closed / Rejected / Ghosted / Self-Rejected as
this rule.

### Queue close fencing (FR-363 residue)

- **`queued` and `paused`:** close immediately from ingest, claim, status
  update, Stage 0, and reconcile. Fence: current `fencing_token` +
  `locked_by IS NULL`.
- **`leased` and `in_progress` with a live lease:** leave the row.
  `process_slug()` already re-checks token then lock; after that check and
  *before* invoke, if the posting is already-handled, `transition` to
  `done` with the worker's own token and return. Do not acquire a second
  kill. Do not call `run_submission.py`.
- **`leased` and `in_progress` with `lease_expires_at` due:** `claim_pack`
  already reclaims those by transitioning to `queued` then `leased` with
  the stored `locked_by` + token (`pipeline_queue.py:976-994`). Intercept
  *before* re-lease: `transition` to `done` instead, using that same
  stored fence. The next claim does not return the slug.

Add to `LEGAL_TRANSITIONS`: `("queued", "done")` and `("leased", "done")`.
Widen `mark_done()` to those four closable statuses. Still no seventh
status. CHECK constraint stays
`queued | leased | in_progress | paused | done`.

CR-119 Story 3.1's "no caller can invent queued→done" is superseded for
this CR only.

### Stage 0 already-handled (not Skip, not PASS-with-flag)

- Add `find_same_posting_applied_plus(url, company, title, ...)` next to
  `_find_active_applications`. It SELECTs `url` and uses posting identity.
  Do not change `is_different_role()` or the existing flag list.
- `evaluate_db_gate()` grows an `already_handled` result (action plus the
  matched job). Cooldown `reject` / `reapply_flag` stay first when they
  apply to *this* company for those reasons. Same-posting Applied+ is a
  separate terminal and must win over the Kroll-style PASS-with-flag for
  that same posting. Different role at the same company still only sets
  `active_application`.
- `build_stage0_fit_gate()` short-circuits like `db_action == "reject"`
  (`:2891-2911`) but writes `decision: "ALREADY_HANDLED"`, not `SKIP`.
  No `skip_reason_code` that placement could treat as a Skip. Empty lists
  are fine (same shape as the reject stub) so `contracts.check_stage0_fit_gate`
  still passes (it does not constrain `decision`).
- `apply_stage0_placement()` already returns the folder unchanged when
  decision is neither PASS nor SKIP. Do not add a move. Do not call
  `record_skip`.
- `policy.evaluate_stage0()` returns `verdict: "ALREADY_HANDLED"`.
- `run_stage0()` in `workflow/runner.py` must handle that verdict
  *before* the `!= PASS → FAILED` branch: commit a terminal workflow
  status `ALREADY_HANDLED`, `active_stage=None`, do not start Stage 1.
  Then attempt `pipeline_queue.mark_done` for the folder slug (no-op if
  no row; `FenceRejected` if another worker holds a live lease).
- Add `ALREADY_HANDLED` to `DONE_WORKFLOW` in `run_queue_worker.py` so a
  worker map also closes when it holds the token.

This is why a hand `run_submission.py` and the unsupervised worker hit
the same terminal. Do not rewrite `run_submission.py`. Do not apply
CR-121 `conversion_risk` to this path.

### Node status update is a second fenced writer, on purpose

`transition()` is the Python sole writer. `applyJobStatusUpdate` runs in
the server process with no worker token. Port the *unlocked* close only
(`queued` / `paused`, `locked_by IS NULL`) into
`pipelineQueueRepository.ts` using `normalizeSkipUrl` + `postingKey`
from `server/stage0SkipLedger.ts` (already lockstep with Python). Match
`jobs.url` then company+title. Pre-apply statuses do not close.
Live `leased` / `in_progress` are left for claim / worker. Folder
archive / restore stays as today.

### Privacy

Synthetic fixtures only. No real company names, JDs, URLs, or contacts
from the 2026-09-19 CSV or from `data/archive/**`. SEC-007 / DATA-006
stand. Do not copy Certara / GoodRx folders into tests.

### Out of scope (repeat so a later session does not "help")

Skip-ledger semantics. `--force` PASS clearing a skip. Company cooldown.
Self-Rejected. `is_different_role` flag behavior. Re-apply override.
CR-121 / CR-122. Scout Phase B. New UI. Company-level identity. Closed /
Rejected / Ghosted as ingest already-applied. Rewriting
`run_submission.py`. Mass-deleting folders or `jobs` rows. A seventh
queue status. A runner-kill.

---

## Epic 1 — Ingest refuses Applied+ and archive packs

**Goal:** a CSV row for an already-handled posting produces no
`pending_review/` folder, no new `queued` row, and no `stage0_skips`
write. Pre-apply still reuses a live slug.

- [x] **Story 1.1 — Ingest Applied+ refuse.** (FR-361, AC-470)
      First story. Spelled in full at the bottom of this file under
      "First story for the engineer". `resolve_opportunity()` returns
      `already_handled` when `jobs.status` is Applied+.
      `ingest_csv_queue.py` treats that action like `skip_ledger`
      (continue; no `write_jd`; no `upsert_queued`; do not increment
      `skipped_ledger`). Failing tests first in
      `scripts/test_csv_ingest.py`.

- [x] **Story 1.2 — Pre-apply is not already-applied.** (FR-361, AC-476)
      Same files. A `jobs` row in `Backlog`, `Drafted`, `Needs Retry`,
      or `New` must not return `already_handled`. Live folder / queue
      reuse stays CR-119 `reuse`. Tests in `test_csv_ingest.py`: Backlog
      URL match is `reuse` or `create` per live-folder rules, never
      `already_handled`; no skip-ledger write from this rule.

- [x] **Story 1.3 — Archive trees are already-handled, not reuse.**
      (FR-362, AC-471)
      Extend `_slug_for_url` / `_slug_for_posting` (or a sibling scan)
      over `data/archive/submissions/` and `data/archive/skipped/` using
      existing `_scan_jd_urls` + title-header match. A hit returns
      `already_handled`, **not** `reuse`. Live `pending_review/` or live
      `submissions/` still win as `reuse` because they are checked
      first. Tests in `test_csv_ingest.py` with temp archive roots:
      archive URL / URL-less company+title → `already_handled`; live
      pending folder for the same posting still `reuse`. Do not close
      queue rows in this story (Epic 2 owns `done`).

---

## Epic 2 — Queue rows go `done` and are not leased

**Goal:** an Applied+ (or archive / skip-already-placed) queue row is
`done`, claim does not return it, and the worker does not invoke
`run_submission.py` for it. Live leases are closed only through the
existing fence.

- [x] **Story 2.1 — Legal `queued→done` and `leased→done`; widen `mark_done`.**
      (FR-363)
      `LEGAL_TRANSITIONS` in `scripts/pipeline_queue.py` gains
      `("queued", "done")` and `("leased", "done")`. `mark_done()`
      accepts `queued`, `paused`, `leased`, and `in_progress`. It still
      calls `transition()` with the row's `locked_by` + `fencing_token`
      (empty worker + unlocked fence when `locked_by` is NULL). Tests in
      `scripts/test_pipeline_queue.py`: each new pair once; a
      mismatched token on a `leased` row raises `FenceRejected` and
      leaves status `leased`; `done→done` stays a no-op.

- [x] **Story 2.2 — Claim refuses already-handled rows.** (FR-363, AC-472)
      Before `BEGIN IMMEDIATE` (same slot as `_promotable_paused_slugs`),
      compute slugs that are already-handled: `jobs` Applied+, or folder
      already under `archive/submissions/` / `archive/skipped/`. Inside
      the transaction: for those slugs, if `queued` or `paused`,
      `transition` to `done` with the unlocked fence; if `leased` /
      `in_progress` and `lease_expires_at <= now`, `transition` to
      `done` with the stored `locked_by` + token (do not re-lease); if
      the lease is still live, skip (do not claim). Select / promote
      only remaining work. Tests in `test_pipeline_queue.py`: paused
      Applied+ becomes `done` and is not in the claim result; queued
      Applied+ same; expired leased Applied+ becomes `done` not
      re-leased; live leased Applied+ is not returned and stays
      `leased`.

- [x] **Story 2.3 — Worker pre-invoke refuse.** (FR-363, AC-472)
      In `scripts/run_queue_worker.py` `process_slug()`, after the
      existing token / `locked_by` re-check (`:496-499`) and **before**
      `run_submission.py` is built, if the slug is already-handled,
      `transition` to `done` with this worker's token and return a
      distinct result string (e.g. `already_handled`). Do not take the
      slug lock only to no-op if you can avoid it; if the lock is
      already the next line, holding it for a fenced `done` write is
      fine. Tests in `scripts/test_run_queue_worker.py`: Applied+ leased
      row is marked `done` and the spawn callable is never invoked.

---

## Epic 3 — Funnel status update closes matching queue rows

**Goal:** marking a job Applied+ closes matching `queued` / `paused`
queue rows. Pre-apply statuses do not. Live leases stay fenced.

- [x] **Story 3.1 — `applyJobStatusUpdate` closes unlocked matches.**
      (FR-364, AC-473)
      After the existing `jobs` UPDATE in
      `server/services/jobStatusService.ts`, if the new status is in
      `APPLICATION_FUNNEL_SET`, SELECT `url, company, title` for that
      id and call a new
      `closeMatchingQueuedOrPaused(db, { url, company, title })` on
      `server/repository/pipelineQueueRepository.ts`. Match
      `pipeline_queue.url_key` via `normalizeSkipUrl(jobs.url)` first;
      if the job has no URL, match URL-less `posting_key`. UPDATE only
      `status IN ('queued', 'paused') AND locked_by IS NULL`. Set
      `status='done'`, clear `paused_reason`, stamp `updated_at`.
      `Backlog` / `Drafted` / `Needs Retry` / `New` must not call the
      closer (or the closer no-ops). Folder archive / restore
      unchanged. There is no existing `applyJobStatusUpdate` unit test;
      add `tests/unit/jobStatusService.test.ts` (in-memory DB + queue
      migrations, same harness style as
      `tests/unit/pipelineQueueRepository.test.ts`). Cases: Applied,
      Recruiter Screen, Core Interviews, Offer and Negotiation each
      close a paused match; Backlog / Drafted leave the row; a
      `leased` match is left `leased`.

---

## Epic 4 — Stage 0 same-posting Applied+ is already-handled

**Goal:** Stage 0 on a same-posting Applied+ fixture does not PASS, does
not author, does not write `stage0_skips`, and sets the queue `done`
when the fence allows. Different-role flag and cooldown / Self-Rejected
stay.

- [x] **Story 4.1 — Posting-identity Applied+ lookup on the DB gate.**
      (FR-365, AC-474)
      Add `url` to the `jobs` SELECT (test DDL in
      `scripts/test_stage0_db_gate.py` currently has no `url` column;
      add it). New helper `find_same_posting_applied_plus`.
      `evaluate_db_gate()` accepts optional `url` and exposes
      `already_handled` when that helper hits Applied+. Do not change
      `is_different_role()`. Tests: URL (tracking-query stripped) +
      Applied → already-handled; each other funnel status; URL-less
      company+title; same company + `is_different_role` true is **not**
      already-handled (existing `active_application` path still
      available); same posting in Backlog is **not** already-handled;
      Self-Rejected / in-window cooldown still `reject` /
      existing codes, not this terminal.

- [x] **Story 4.2 — Fit gate short-circuit writes `ALREADY_HANDLED`.**
      (FR-365, AC-474)
      `build_stage0_fit_gate.py` Step 1: if the gate result is
      already-handled, return a stub like the `db_action == "reject"`
      block but `decision="ALREADY_HANDLED"` and **no** Skip reason
      codes. Pass `url` into `evaluate_db_gate`. Do not attach
      `active_application` on this terminal. Tests in
      `scripts/test_build_stage0_fit_gate.py`: same-posting Applied
      fixture is `ALREADY_HANDLED` and is not `PASS`; different-role
      same-company still PASSes with `active_application`; a cooldown
      reject fixture is still `SKIP`. Do not run placement in this
      story beyond asserting the JSON.

- [x] **Story 4.3 — Policy, runner, worker map, and unlocked queue close.**
      (FR-365, AC-474)
      `policy.evaluate_stage0`: `ALREADY_HANDLED` → that verdict.
      `workflow/runner.py` `run_stage0`: handle it before FAILED;
      workflow status `ALREADY_HANDLED`; no Stage 1. Placement is
      already a no-op (add a test in `scripts/test_stage0_skip_ledger.py`
      or placement tests: folder stays, `stage0_skips` row count
      unchanged). After commit, `mark_done` the slug if a queue row
      exists and is unlocked / held by this path. Add
      `ALREADY_HANDLED` to `DONE_WORKFLOW`. Tests:
      `scripts/test_workflow_authority.py` (verdict + no SKIPPED
      lock-as-skip); `scripts/test_run_queue_worker.py` (map to
      `done`); confirm `record_skip` is not called. Do not edit
      `run_submission.py`.

---

## Epic 5 — Reconcile live ghosts without a new CSV

**Goal:** one function marks existing non-`done` mirrors `done` so the
pipeline panel `paused` count drops without Jason re-dropping the
2026-09-19 CSV. Ingest of a matching row uses the same function.

- [x] **Story 5.1 — `reconcile_already_handled()` + ingest / CLI hook.**
      (FR-366, AC-475)
      In `scripts/pipeline_queue.py`: walk non-`done` rows; a row is a
      ghost if (a) `jobs` posting is Applied+, (b) its folder (or slug)
      is already under `data/archive/skipped/`, or (c) already under
      `data/archive/submissions/`. Close `queued` / `paused`
      immediately; close expired `leased` / `in_progress` with the
      stored fence; leave a live lease. `ingest_csv_queue.py`: on
      `already_handled`, call the same closer for any existing row;
      also expose `--reconcile-already-handled` so a reconcile runs
      with no inbox files (do not add a fourth ingest script). Tests
      in `test_pipeline_queue.py` / `test_ingest_csv_queue.py` with
      synthetic slugs only: the three AC-475 shapes; claim does not
      return them afterward. Do not delete folders.

- [x] **Story 5.2 — Operator docs.**
      AGENTS.md (CSV queue / Applied+ one-liner), `docs/ACTIVE_WORKFLOW.md`
      step 4b, `CHANGELOG.md` `[DRAFT]` Changed/Developer line for
      CR-123. No new UI copy. Do not rewrite FR-342; this CR extends
      it.

---

## First story for the engineer (Story 1.1)

**IDs:** FR-361, AC-470.

**What becomes true:** `resolve_opportunity()` can return
`already_handled`. Ingest of an Applied+ posting creates zero queue
rows, zero `pending_review/` folders, and zero `stage0_skips` rows.
A second ingest of the same synthetic file stays idempotent.

**Files you may touch**

- `scripts/csv_ingest.py` (`resolve_opportunity`, plus a small
  `lookup_applied_plus_job(conn, url, company, title)` that SELECTs
  `url, company, title, status` from `jobs`. Guard
  `sqlite3.OperationalError` the same way `url_to_slug()` already does
  if `jobs` is missing.)
- `scripts/ingest_csv_queue.py` (branch `already_handled` next to
  `skip_ledger`; increment a new `already_handled` count, not
  `skipped_ledger`)
- `scripts/test_csv_ingest.py` (failing tests first)
- `scripts/test_ingest_csv_queue.py` only if you need one end-to-end
  ingest assertion for AC-470's "zero folders / zero queue / zero
  skip" clause. Prefer keeping the resolver tests in `test_csv_ingest.py`
  as Jason asked.

**Failing test first** (add to `test_csv_ingest.py`, then implement)

Use a temp SQLite with a minimal `jobs(id, company, title, url, status)`
table plus `pipeline_queue` / `stage0_skips` schema via the existing
`ensure_schema` helpers. Synthetic company `Synth Applied Co`, URL
`https://example.test/jobs/applied-1?utm_source=board`. Cases:

1. `jobs.status='Applied'` and CSV URL with a tracking query →
   `already_handled`. Normalize both sides.
2. Repeat for `Recruiter Screen`, `Core Interviews`, `Offer and Negotiation`.
3. URL-less row: empty URL, company+title equals the Applied job →
   `already_handled`.
4. After resolve, `SELECT COUNT(*) FROM stage0_skips` is 0. After a
   matching `ingest_inbox` (or a direct assert on the ingest branch),
   no `pending_review/{slug}` and no new `pipeline_queue` row.
5. Second ingest / second resolve stays `already_handled` (idempotent).

Write the tests. Run
`.venv\Scripts\python.exe -m unittest scripts.test_csv_ingest -v`
and watch the new cases fail. Then implement the smallest resolver +
ingest branch. Re-run until green.

**What not to touch in Story 1.1**

- Archive roots (Story 1.3)
- `LEGAL_TRANSITIONS`, `mark_done`, `claim_pack`, `run_queue_worker.py`
- `applyJobStatusUpdate` / any `server/` file
- `stage0_db_gate.py`, `build_stage0_fit_gate.py`, `workflow/runner.py`,
  `stage0_placement.py`, `stage0_skip_ledger.record_skip`
- `run_submission.py`
- CR-121 `conversion_risk` and CR-122 skill-presence
- Real `data/archive/**` or the 2026-09-19 CSV
- Closing an existing paused row (Epic 2). Refuse new work only.

**Do not** return `reuse` for Applied+ (ingest would `upsert_queued`).
**Do not** return `skip_ledger` for Applied+ (that is a different
counter and a different memory).

---

## Rollout priority

1. **Epic 1.** Stops the leak on the next CSV drop. Independently useful
   even if claim still picks an old paused ghost.
2. **Epic 2.** Stops the worker from authoring those ghosts. Fencing
   lands here; do not skip 2.1.
3. **Epic 3.** Closes the UI / Gmail path so a later Applied click does
   not leave a paused mirror.
4. **Epic 4.** Closes the Stage 0 PASS-with-flag hole for both the
   worker and a hand `run_submission.py`.
5. **Epic 5.** Required for ship. The live panel stays dirty until
   reconcile runs once. After 5.1 is green, run
   `python scripts/ingest_csv_queue.py --reconcile-already-handled`
   against the real DB in a later operator step (not inside a unit
   test).

---

## Do not touch

- `scripts/run_submission.py` as a rewrite target. Invoked as a
  subprocess. Story 4.3 may observe it; it must not edit it.
- `is_different_role()`, cooldown, Self-Rejected, skip-ledger `--force`
- CR-121 / CR-122 files except to avoid breaking their tests
- `server/services/exportPendingReview.ts` (Phase B)
- Review Center panel components (counts already include `done`)
- Global SQLite pragmas
- Real gitignored submission / archive / inbox files

---

## Open questions routed back to PM

None. OQ-1 is resolved (no re-apply override). The leased / in_progress
"closable but no runner-kill" residue is a fencing choice, not a product
gap: close `queued`/`paused` now; close live leases only with the
holder's token or after expiry on the next claim.
