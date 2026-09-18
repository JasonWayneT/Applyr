---
status: done
created: 2026-09-18
related: CR-091 (pending_review + stage0_skips skip ledger — reused, not modified), CR-076/077/079 (run_submission.py + workflow_state.json/stage_receipts authority — read-only here), CR-092 (move_folder_robust, the Windows rename failure mode this tracker's lock design has to avoid), CR-109/FR-285 (Review Center shell the new panel mounts into), FR-316/AC-413 (run-submission operator route + WorkflowOperator component), ADR-001 (SQLite local-first), CR-071 (contacts — deliberately NOT written by this CR)
contains: CR-119 (CSV Drop Queue, Harness Lease, and Pipeline Visibility)
---

# CR-119 — CSV Drop Queue, Harness Lease, and Pipeline Visibility: Epics & Stories

**Handoff doc.** Resumable plan for
[CR-119](../05-change-requests/CR-119-csv-drop-queue.md) (Approved 2026-09-18 by Jason, with
Changes 1-4 already folded into the CR; OQ-1 resolved there). A new session picks up at the
**first unchecked story**. Stories are sized for one senior-engineer pass each: read the story,
make the change, run the tests named in it, check the box, stop.

Scope is locked. Do not re-litigate the CR's Decision list, do not pull Phase B forward, and do
not widen a story because the adjacent code looks improvable.

```
Epic 1 (inbox + schema)  →  Epic 2 (ingest/normalize/quarantine)  →  Epic 3 (claim/lease/fencing)
                                                                  →  Epic 4 (folder lock + worker)
                                                                  →  Epic 5 (Review Center panel)
                                                                  →  Epic 6 (docs closeout)
```

Ordered cheapest-and-highest-confidence first. Epic 1 is additive DDL plus two directories and
touches no behavior. Epic 5 (UI) lands last because it reads tables Epics 1-4 populate, and
because it carries no remaining open questions (OQ-TL-1/2/3 resolved 2026-09-18).

---

## Why this exists (read this before touching anything)

Five facts, all verified against the live repo during this planning pass, not recalled.

1. **`scripts/import_csv_to_submissions.py` is a one-shot, not a product path.** `main()`
   (lines 164-196) hardcodes four `c:\Users\Jason\Downloads\applyr_jobs*.csv` literals as its
   default argv. `import_csv()` prints `skip empty:` and `skip ledger:` to stdout and continues
   (lines 104-128), so every rejection is lost when the terminal closes. There is no length gate
   at all: a 12-character JD is imported as happily as a 4,000-character one. There is no lease,
   no status, no file-level dedup. Its `write_jd()` (line 84) and `sanitize()` (line 36) are the
   only pieces worth keeping, and the CR's AC-440 pins the output format to `write_jd()`'s exact
   shape.

2. **`server/services/exportPendingReview.ts` already enforces the 200-character gate** at
   `selectPendingRows()` (`LENGTH(TRIM(jd_text)) >= 200`, line 57) and writes the same
   `pending_review/{slug}/Original_JD.txt` convention via `formatOriginalJd()` (line 41). Its
   folder naming is `{slug}_{id8}` (`pendingReviewFolderName`, line 34) because it has a jobs-row
   UUID to disambiguate with. CSV rows have no such id, so this CR keeps the CSV-side
   `sanitize(company)` plus disambiguation convention rather than adopting `{slug}_{id8}`.
   Unifying the two export paths onto one table is explicitly Phase B.

3. **Stage 0 moves the job folder out from under you, mid-run.**
   `scripts/stage0_placement.py:apply_stage0_placement()` moves
   `data/pending_review/{slug}` to `data/submissions/{slug}` on PASS (line 106-112) and to
   `data/archive/skipped/{slug}` on SKIP (line 89-104), via
   `scripts/utils.py:move_folder_robust()`. `_unique_dest()` (line 40) appends a UTC timestamp to
   the folder name when the destination already exists, so **the slug itself can change during a
   run**. This single fact drives two design decisions below (lock-file location, and the queue
   row keyed on slug plus a re-resolve after the subprocess exits). `server/services/
   runSubmissionRunner.ts:findFolderAfterRun()` (line 289) already solves the same problem on the
   Node side and is the precedent to copy.

4. **`move_folder_robust()` cannot rename a directory that contains an open file handle.** Its
   own docstring (`scripts/utils.py:1210-1232`) records a real CR-092 incident: a transient
   Windows handle somewhere under the tree made `shutil.move()` raise `PermissionError`, and the
   recovery is 8 retries then `copytree` + `rmtree`. If the source `rmtree` also fails, the folder
   exists in **both** `pending_review/` and `submissions/`. A lock file held open inside the job
   folder for the life of the subprocess would trigger that path on every single PASS. This is
   why the per-slug lock lives beside the data tree rather than inside the folder (see the locked
   decisions below, and open question OQ-TL-2).

5. **There is an established dual-DDL pattern for a Python-plus-Node table, and CR-119 needs it.**
   `server/migrations/016_add_stage0_skips.sql` and
   `scripts/stage0_skip_ledger.py:_SCHEMA_SQL` carry byte-equivalent DDL on purpose; the SQL file's
   own header says so ("Python `scripts/stage0_skip_ledger.py.ensure_schema()` uses the same DDL
   so Stage 0 still works if a script runs before the server has migrated"). Migrations run
   Node-side only, at server boot (`server/db.ts:156` calls
   `server/migrationRunner.ts:runMigrations`). The CSV ingest CLI must work with the server
   stopped, so it needs the same mirrored DDL, and a test that proves the mirror has not drifted.

Everything below is either building one of the three layers the CR names (Ingest / Claim /
Resume), the read-only panel over them, or the test and doc work that makes them hold.

---

## Architecture decisions locked in this pass (do not re-derive them per story)

Tech-lead calls made against the real code. If one turns out to be wrong once you are in the file,
say so and stop. Do not quietly pick a different design.

### Three new tables in `jobagent.sqlite`, no second workflow store

`pipeline_queue`, `csv_ingest_ledger`, `csv_quarantine`. Additive only. Nothing existing is
altered, and in particular `jobs`, `stage0_skips`, and `contacts` are untouched. Per ADR-001 this
all stays in the one local SQLite file.

- **`pipeline_queue`** is the durable opportunity. One row per opportunity, keyed on `slug`
  (UNIQUE). Carries `company`, `title`, `url`, `url_key`, `posting_key`,
  `networking_contacts_raw` (TEXT NULL, verbatim), `source_sha256` + `source_line` for provenance
  back to the ledger, `folder_root` (`pending_review` / `submissions` / `archive/skipped`),
  `status` with a CHECK constraint over exactly the five transition-table values
  (`queued`, `leased`, `in_progress`, `paused`, `done`), the lease triple
  (`locked_by`, `lease_expires_at`, `fencing_token INTEGER NOT NULL DEFAULT 0`), timestamps
  (`queued_at`, `claimed_at`, `started_at`, `updated_at`), and two **mirror-only** columns
  `last_workflow_status` / `last_stage`. Mirror-only means: written from `workflow_state.json`
  after a run, never read as an input to a stage decision. `workflow_state.json` +
  `stage_receipts/` stay the authority (CR-119 Decision 2, AC-447).
- **`url_key` uses `stage0_skip_ledger.normalize_url()` and `posting_key` uses
  `stage0_skip_ledger.posting_key()`.** Import them; do not write a second normalizer. Dedup that
  disagrees with the skip ledger's own key derivation is a dedup bug waiting to happen.
- **Two partial unique indexes, deliberately asymmetric.**
  `UNIQUE(url_key) WHERE url_key IS NOT NULL AND url_key != ''` mirrors
  `idx_stage0_skips_url_key`. `UNIQUE(posting_key) WHERE url_key IS NULL OR url_key = ''` is the
  URL-less guarantee behind AC-445, and it is deliberately **not** unconditional: two genuinely
  different postings for the same company+title with different URLs must both be allowed
  (CR-119 Decision 12 makes URL the preferred key, company+title the fallback *when URL is
  absent*). A blanket `UNIQUE(posting_key)` would silently drop the second one.
- **`csv_ingest_ledger`** is keyed `sha256 TEXT PRIMARY KEY`. `filename` is a display column and
  is **not** part of any uniqueness constraint (CR-119 Decision 13, AC-438). Also holds
  `ingested_at`, `row_count`, `quarantine_count`, `archive_path`, `status`
  (`ingested` / `file_quarantined`).
- **`csv_quarantine`** holds both tiers with one `scope` column (`file` | `row`). Row records
  carry `source_file`, `line_number` (1-based), `raw_payload`, `error_code`, `quarantine_reason`;
  file records carry `source_file`, `error_code`, `quarantine_reason` with `line_number` NULL.
  One table, not two, because AC-443's quarantine detail view renders one list and the two record
  shapes differ by one nullable column.
- **Error codes are a closed set**, defined once in the shared module:
  `EMPTY_COMPANY`, `JD_TOO_SHORT`, `NO_DEDUP_KEY`, `FILE_UNPARSEABLE`, `FILE_ENCODING`.
  `NO_DEDUP_KEY` is named in the CR (AC-446) and must be spelled exactly that way.

### DDL lives in two mirrored places, and a test proves they match

`server/migrations/025_add_pipeline_queue.sql` (Node path, applied at server boot) and
`_SCHEMA_SQL` in `scripts/pipeline_queue.py` with an `ensure_schema(conn)` (Python path, so the
ingest CLI works with the server stopped). This is the `016_add_stage0_skips.sql` pattern exactly,
including the explanatory header comment. Story 1.3 adds the anti-drift test; without it the two
copies will diverge and the divergence will surface as a confusing runtime error months later.

### Lease and fencing: short `BEGIN IMMEDIATE`, filesystem reads outside the transaction

- The claim is one `BEGIN IMMEDIATE` transaction that (a) applies the paused-to-queued promotions
  computed *before* the transaction opened, (b) selects up to `size` `queued` rows, (c) sets
  `status='leased'`, `locked_by`, `lease_expires_at`, and `fencing_token = fencing_token + 1` per
  row. Nothing else happens inside it. No filesystem walk, no subprocess, no
  `workflow_state.json` read (NFR-016, AC-441).
- **The paused-to-queued promotion scan happens before the transaction.** Reading
  `workflow_state.json` for every paused row is a filesystem walk; doing it inside
  `BEGIN IMMEDIATE` would hold the write lock for its duration. Compute the promotable slug list
  first, then promote and select in the one short transaction.
- **Every mutating statement is fenced.** Each UPDATE carries
  `WHERE slug = ? AND fencing_token = ? AND locked_by = ?` and the caller asserts
  `cursor.rowcount == 1`. A zero rowcount is a rejected stale-token write and must raise, not warn
  (AC-441's "rejected without modifying SQLite state").
- **Defaults: lease TTL 20 minutes, heartbeat every 5 minutes**, both overridable by CLI flag.
  Chosen because a single slug's Stage 0 through Stage 2 run routinely exceeds 20 minutes, so the
  lease is renewed by heartbeat rather than sized to the longest plausible job. `--size` is
  validated `1 <= size <= 10`, default 8 (NFR-016).
- `PRAGMA busy_timeout` is set per connection in the queue module. Do **not** change any global
  pragma (journal mode, synchronous) on the shared database; `server/db.ts` owns those.

### The per-slug runner lock is an OS lock held open by the worker, not an exclusive-create marker

This is the AC-444 decision and it is the one most likely to be re-derived wrongly.

**Mechanism: a lock file opened for the duration of that slug's runner invocation, with a real OS byte-range
lock taken on the open handle.** `msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)` on Windows,
`fcntl.flock(fd, LOCK_EX | LOCK_NB)` on POSIX, behind one small `scripts/queue_lock.py`
context manager. The handle stays open for that slug's `run_submission.py` subprocess and is closed
in a `finally` when that invocation ends. A worker processing a pack of 8 acquires and releases
one slug lock at a time. It does not hold all 8 until process exit.

**Why not exclusive-create (`os.open(..., O_CREAT | O_EXCL)`) plus lease-expiry staleness.** That
mechanism fails AC-444 outright. AC-444's scenario is precisely: harness-1's lease has expired
*while its subprocess is still alive*. Under exclusive-create-plus-stale-on-expiry, harness-2 sees
an expired lease, concludes the marker is stale, deletes it, creates its own, and starts a second
`run_submission.py` against the same folder. Two runners, two Stage 0 writes, two possible skip
ledger rows. The staleness signal has to come from process liveness, not from a clock.

**Why an OS lock satisfies AC-444 on Windows.** The Windows kernel releases a byte-range lock when
the owning handle closes, and it closes the handle when the process exits for any reason:
clean exit, unhandled exception, SIGINT, Task Manager kill, or crash. So "is the holder alive?" is
answered by the operating system, not by a timestamp the holder failed to refresh. Harness-2
attempting `LK_NBLCK` against a live holder gets `OSError`/`PermissionError` immediately and, per
FR-343, does not run the slug. When the holder really is gone, the lock is already free and
harness-2 takes it on the first try. No reaper, no heuristic, no clock.

**Reconciling with the CR's "treated as stale once its lease has expired."** The lease-expiry
staleness rule still applies, but only to the *file contents*: a leftover lock file whose OS lock
is unheld can be reopened and overwritten by the next claimant. It never authorizes taking a lock
the OS says is held. The CR's intent (a leftover file must not block forever) is preserved; the
mechanism that would have broken AC-444 is not used.

**Lock payload and Job Object (the orphan hole is closed, not papered over).** The lock file holds JSON:
`{worker_id, fencing_token, runner_pid, slug, acquired_at}`. `runner_pid` is the
`run_submission.py` subprocess PID. The OS lock belongs to the worker, but the runner is a child.
On Windows, hard-killing the parent does not kill the child, so the lock would release while the
child is still writing. **Required (Jason 2026-09-18, AC-444 extended):** launch the runner inside a
Windows Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (stdlib `ctypes`; no new dependency).
POSIX: new process group, killed on worker exit. A `TerminateProcess` of the worker must leave the
child gone before any other worker can take the slug's lock. The old `runner_pid` liveness check
is not a substitute for the Job Object / process group.

**Lock file location: `data/queue_locks/{slug}.lock`, not inside the job folder.** Fact 4 above is
the reason: an open handle inside `data/pending_review/{slug}/` forces
`move_folder_robust()` down its 8-retry-then-copytree path on every Stage 0 PASS, and a failed
source `rmtree` leaves the same submission in two places. `data/queue_locks/` is inside the repo
data tree and therefore satisfies SEC-007; the file name is the slug and the payload carries no JD
text, no company description, and no `networking_contacts_raw`. PM resolved OQ-TL-2 on 2026-09-18:
FR-343 and DATA-006 now name this path.

### Ingest: one shared module, one new CLI, the old script reduced rather than forked

- **`scripts/csv_ingest.py`** (new) is the shared, importable, side-effect-free-where-possible
  module: `sanitize()`, `write_jd()`, row validation, error codes, sha256 hashing, the stable-size
  guard, and the dedup resolver. Moved from `import_csv_to_submissions.py`, not copied.
- **`scripts/ingest_csv_queue.py`** (new) is the FR-340/341/342 CLI over the inbox: scan, ledger,
  quarantine, persist `queued` rows, write `Original_JD.txt`, archive the file.
- **`scripts/import_csv_to_submissions.py`** stays, but as a thin wrapper over `csv_ingest.py`
  with its four hardcoded Downloads paths deleted (explicit paths only). It is not deleted in this
  CR, and it does not gain queue writes; it is the pre-CR-119 escape hatch and is documented as
  legacy. Three importers is the outcome this CR exists to avoid, so do not create a fourth, and
  do **not** revive anything under `scripts/archive/import_csv_*.py`.
- **Dedup order, single implementation, used by both callers:** normalized URL against
  `pending_review/` folders, `submissions/` folders, `pipeline_queue` rows, then `stage0_skips`.
  When URL is absent: `posting_key` against the same four. Neither URL nor Position:
  quarantine `NO_DEDUP_KEY`, no row, no folder (AC-446).
- **Stable-size guard:** stat the file, wait a short interval, stat again, require equality before
  opening it (AC-438). Explicit scan only; no watcher, no daemon, no Downloads polling
  (CR-119 Decision 10).

### Worker loop: mirror status from `workflow_state.json`, never from the exit code alone

`run_submission.py`'s exit codes are not a status enum. Verified in `scripts/run_submission.py`
`main()`: `WAITING_FOR_LLM` exits **0** (line 300), `WAITING_FOR_INPUT` exits 0 (line 369),
`SKIPPED` exits 2 (line 294), `STALE` exits 3, `NEEDS_DISPOSITION` exits 4 (line 377),
`FAILED` and `WorkflowError` exit 1. The worker therefore re-resolves the folder after the
subprocess exits (Fact 3: it may have moved to `submissions/` or `archive/skipped/`), reads
`workflow_state.json`, and maps `status` to the queue mirror per AC-447. The exit code is logged
as context, not used as the mapping key.

`--resume` is the only resume mechanism. The worker invokes
`python scripts/run_submission.py {slug} --resume` with a **bare slug** (Decision 21).
`runner._resolve_folder` searches `data/submissions/` then `data/pending_review/`. Do not pass
`data/pending_review/{slug}`. The child is launched in a Windows Job Object with
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (POSIX: new process group). `run_submission.py` is an
unmodified subprocess. The worker never imports `scripts/workflow/`, never calls a CR-074 worker
directly, and never writes `workflow_state.json` or anything under `stage_receipts/`.

### Review Center: a panel inside the existing page, read-only

Mounted in `src/pages/ReviewCenterView.tsx` immediately after the existing `<WorkflowOperator />`
(line 644), inside the same `ReviewCenterView` returned by `src/App.tsx`'s `'Review Center'` tab
case (line 111-113). No route, no nav entry, no new shell (FR-345). Data comes from a new
read-only Express route pair mounted the same way `reviewCenterRouter` and `runSubmissionRouter`
already are in `server/index.ts` (lines 87, 89), behind the same `requireApiToken` middleware. The
panel reads; it does not claim, release, or reclaim. OQ-TL-3 resolved 2026-09-18: Phase A is read-only.

### Privacy constraints that apply to every story

- No `networking_contacts_raw` value, no JD text, and no `raw_payload` content is ever written to
  a log line, an `activity_log` message, a test fixture, a test report, or a tracked file
  (SEC-007, DATA-006). The API responses that back the panel return counts, slugs, worker ids,
  timestamps, file names, line numbers, and error codes. Quarantine `raw_payload` stays in SQLite
  and is rendered from an authenticated request; it is never logged server-side.
- Every Python test fixture is **synthetic**. Do not copy a row, a JD, a company, or a contact
  string out of any real `applyr_jobs*.csv`, out of `data/pending_review/`, or out of
  `data/submissions/`.
- `data/inbox/csv/` and `data/queue_locks/` contents are gitignored (Story 1.1).

---

## Epic 1 — Inbox tree, gitignore, and the three tables

**Goal:** the drop folder exists and the three tables exist, in both the Node and Python paths,
with no behavior change anywhere.

Additive DDL and two directories. Nothing in this epic can break an existing flow, which is why it
goes first.

- [x] **Story 1.1 — Create the inbox tree and gitignore it.** (FR-340, DATA-006, SEC-007)
  `data/inbox/csv/`, `data/inbox/csv/archive/`, `data/inbox/csv/quarantine/`, and
  `data/queue_locks/`, each with a `.gitkeep`. Add explicit `data/inbox/` and `data/queue_locks/`
  entries to `.gitignore` with `!` exceptions for the `.gitkeep` files. Note in the comment that
  the existing `*.csv` rule (line 108) already covers the dropped files, and that the explicit
  entries exist so a future narrowing of that rule cannot silently expose real JD content. Do not
  narrow or reorder any existing ignore rule.

- [x] **Story 1.2 — `server/migrations/025_add_pipeline_queue.sql`.** (DATA-006, FR-342, FR-343)
  The three tables and their indexes exactly as specified in the locked decisions above:
  `pipeline_queue` (slug UNIQUE, status CHECK over the five values, lease triple with
  `fencing_token INTEGER NOT NULL DEFAULT 0`, `networking_contacts_raw TEXT` nullable, the two
  partial unique indexes), `csv_ingest_ledger` (sha256 PRIMARY KEY, filename display-only),
  `csv_quarantine` (scope column, nullable line_number). `CREATE TABLE IF NOT EXISTS` throughout,
  additive only, no ALTER and no DROP of anything existing. Header comment in the same style as
  `016_add_stage0_skips.sql`, including the sentence pointing at the mirrored Python DDL. Verify
  with `tests/unit/migrationRunner.test.ts` still green.

- [x] **Story 1.3 — `scripts/pipeline_queue.py` schema half plus the anti-drift test.**
  (DATA-006, ADR-001)
  New module shaped exactly like `scripts/stage0_skip_ledger.py`: `_SCHEMA_SQL`, `ensure_schema
  (conn)`, `connect(db_path=None)` with `row_factory = sqlite3.Row` and a `busy_timeout` pragma,
  `DEFAULT_DB` resolved from `Path(__file__).parent.parent / "data" / "jobagent.sqlite"`. The
  DDL must be semantically identical to Story 1.2's file. New `scripts/test_pipeline_queue.py`
  opens two in-memory databases, applies the `.sql` file to one and `ensure_schema()` to the
  other, and asserts the normalized `sqlite_master` dumps match; this is the test that stops the
  two copies drifting. Register `scripts/test_pipeline_queue.py` in
  `scripts/run_all_tests.py`'s `PYTHON_TEST_SCRIPTS`.

---

## Epic 2 — Ingest, normalization, quarantine, and the pending_review write

**Goal:** a CSV dropped in the inbox becomes `queued` rows plus `Original_JD.txt` folders, with
every rejected row durably recorded and every re-run a no-op.

- [x] **Story 2.1 — Extract the shared module `scripts/csv_ingest.py`.** (FR-340, FR-341, FR-342)
  Move `sanitize()`, `write_jd()`, `unique_slug()`, `url_to_slug()`, `_scan_jd_urls()` and
  `existing_urls()` out of `scripts/import_csv_to_submissions.py` into the new module, unchanged
  in behavior. `write_jd()`'s output format is pinned by AC-440 (optional `URL:` line, blank line,
  optional `Title:` line, blank line, then trimmed JD) and must not be "improved". Add the closed
  error-code set as module constants. Reduce `import_csv_to_submissions.py` to a wrapper that
  imports from the new module, and **delete the four hardcoded `c:\Users\Jason\Downloads\...`
  default paths from `main()`** so it requires explicit argv. Add a docstring line marking it
  legacy and pointing at `ingest_csv_queue.py`. New `scripts/test_csv_ingest.py` locks
  `write_jd()`'s exact byte output against a synthetic row (this is the AC-440 format contract);
  register it in `run_all_tests.py`.

- [x] **Story 2.2 — Row validator and quarantine writer.** (FR-341, AC-439, AC-446)
  In `csv_ingest.py`: `validate_row(row) -> (ok, error_code | None)` checking, in order, non-empty
  company (`EMPTY_COMPANY`), `len(jd.strip()) >= 200` (`JD_TOO_SHORT`, the same threshold
  `exportPendingReview.ts:57` already enforces for scout rows), and presence of a URL or a
  Position (`NO_DEDUP_KEY`). In `pipeline_queue.py`: `record_quarantine(...)` writing scope,
  source file, 1-based line number, raw payload, error code, and reason. A quarantined row must
  produce no `pipeline_queue` row and no `pending_review/` folder, and must not stop the rest of
  the file. Tests in `scripts/test_ingest_csv_queue.py` (new, registered in `run_all_tests.py`)
  with synthetic rows only: one empty-company, one 150-character JD, one company+JD with neither
  URL nor Position asserting `NO_DEDUP_KEY`, and one good row in the same file proving it still
  lands.

- [x] **Story 2.3 — Dedup resolver over folders, queue, and the skip ledger.**
  (FR-342, AC-440, AC-445)
  `resolve_opportunity(company, title, url, conn) -> (action, slug)` in `csv_ingest.py`, where
  action is `create` / `reuse` / `skip_ledger`. Import `normalize_url` and `posting_key` from
  `stage0_skip_ledger` rather than reimplementing them, and call `lookup_skip()` for the ledger
  leg. URL leg checks `pending_review/` folders, `submissions/` folders, and `pipeline_queue`
  rows. URL-less leg does the same on `posting_key`. Tests: AC-445's exact scenario (two files
  with different sha256 carrying the same URL-less company+title yields one row and one folder),
  a URL already in `stage0_skips` yielding neither row nor folder, and a URL matching an existing
  `pending_review/` folder reusing the slug with no second file write.

- [x] **Story 2.4 — File ledger, stable-size guard, and file-level quarantine.**
  (FR-340, AC-438)
  In `pipeline_queue.py`: `lookup_file(sha256)` / `record_file(...)`. In `csv_ingest.py`: a
  stable-size guard (stat, short sleep, stat, require equality) and sha256 of the file bytes. A
  content hash already in the ledger is skipped entirely regardless of filename, which is the
  `applyr_jobs.csv` then `applyr_jobs (1).csv` case in AC-438. A structurally broken file
  (unparseable CSV, undecodable after BOM strip) is moved to `data/inbox/csv/quarantine/` with a
  `scope='file'` record and does not abort the scan of the other files. Successfully parsed files
  move to `data/inbox/csv/archive/`. Tests in `test_ingest_csv_queue.py`: same content under two
  names produces zero new rows on the second pass, and a broken file does not block a valid file
  in the same scan.

- [x] **Story 2.5 — `scripts/ingest_csv_queue.py` CLI wiring it together.**
  (FR-340, FR-341, FR-342, AC-440, SEC-007)
  Arguments: `--inbox` (default `data/inbox/csv`), `--db`, `--dry-run`. Per file: stable-size
  guard, hash, ledger check, parse, per-row validate, dedup resolve, `write_jd()`, insert
  `pipeline_queue` row with `status='queued'` and `networking_contacts_raw` set verbatim from the
  Networking Contacts cell (NULL when the cell is empty), then archive the file and write the
  ledger row with counts. Prints a summary of counts only. **No JD text, no
  `networking_contacts_raw`, and no raw payload in any printed line.** Explicitly assert in a test
  that no CR-071 `contacts` row is created (AC-440d). Add the full-run idempotency test: ingest
  the same synthetic file twice, assert zero additional rows and zero additional folders.

---

## Epic 3 — Claim, lease, heartbeat, expiry, and fencing

**Goal:** two harnesses can take disjoint packs from one SQLite file, and a dead harness's work
comes back on its own.

Pure SQLite, no filesystem lock and no subprocess yet. That lands in Epic 4, which keeps this epic
testable in isolation.

- [x] **Story 3.1 — Queue row lifecycle helpers and the status transition guard.**
  (FR-343, AC-447)
  In `pipeline_queue.py`: `upsert_queued(...)`, `get_row(slug)`, `list_rows(status=None)`, and a
  single `transition(slug, to_status, *, worker, token, conn)` that is the **only** function
  allowed to write the `status` column. It validates the move against the CR's transition table
  and raises on an illegal pair, so no caller can invent `queued` to `done`. Every status write is
  fenced (`WHERE slug = ? AND fencing_token = ? AND locked_by = ?` where a lease is held) and
  asserts `rowcount == 1`. Tests in `test_pipeline_queue.py` cover each legal transition once and
  at least three illegal ones raising.

- [x] **Story 3.2 — `claim_pack()` with fencing tokens and the pre-transaction pause promotion.**
  (FR-343, AC-441, AC-447, AC-448, NFR-016)
  `claim_pack(worker, size=8, lease_minutes=20, conn)`. Rejects `size < 1` or `size > 10` before
  touching the database (AC-441's `--size 11` case). Before opening the transaction, scan `paused`
  rows and, for each, resolve the folder then call `contracts.check_stage1_ready(folder)` (packet
  `ready` plus `Resume.md`, `CoverLetter.md`, and `claim_provenance.json` all present) and/or read
  `workflow_state.json` to see if status has moved past `WAITING_FOR_LLM`. Do not promote when only
  2 of the 3 files exist (AC-448). Then one `BEGIN IMMEDIATE`: apply promotions, select up to
  `size` `queued` rows, set `leased` / `locked_by` / `lease_expires_at` /
  `fencing_token = fencing_token + 1`, commit. Nothing else inside the transaction. Tests: at most
  `size` rows returned, tokens incremented, size bounds rejected, a `paused` row does not occupy a
  pack slot until promoted, AC-448 (2 of 3 files stays paused).

- [x] **Story 3.3 — Heartbeat, release, and expiry reclaim.** (FR-343, AC-441)
  `heartbeat(worker, lease_minutes, conn)` extends `lease_expires_at` on all rows held by that
  worker. `release(worker, conn)` returns that worker's still-`leased` (not yet `in_progress`)
  rows to `queued`, clearing `locked_by` / `lease_expires_at`. Claim treats a row whose
  `lease_expires_at` has passed as claimable regardless of `locked_by`. Tests: heartbeat extends;
  release returns rows to `queued`; after simulated expiry a second worker claims the row; and a
  write from the first worker carrying its now-stale `fencing_token` raises and leaves the row
  byte-identical (AC-441's final clause).

- [x] **Story 3.4 — `scripts/queue_claim.py` CLI.** (FR-343, NFR-016)
  Subcommands `claim --size --worker --lease-minutes`, `heartbeat --worker`,
  `release --worker`, `status`. Thin argparse over Story 3.1-3.3; no logic of its own. Output is
  slugs, statuses, worker ids, and timestamps. Never prints JD text or
  `networking_contacts_raw` (SEC-007). Covered by `test_pipeline_queue.py` via subprocess or
  direct `main(argv)` calls against a temp database.

---

## Epic 4 — Per-slug runner lock, the worker loop, and status mirroring

**Goal:** exactly one `run_submission.py` per slug, ever, and a killed harness leaves the job
resumable from its last receipt.

- [x] **Story 4.1 — `scripts/queue_lock.py`: the OS-lock context manager.** (FR-343, AC-444)
  `acquire_slug_lock(slug, worker_id, fencing_token, lock_dir=data/queue_locks)` as a context
  manager yielding a handle, raising `SlugLockUnavailable` when the lock is held. Windows path
  uses `msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)`, POSIX path uses
  `fcntl.flock(fd, LOCK_EX | LOCK_NB)`; select at import time, not per call. Writes the JSON
  payload (`worker_id`, `fencing_token`, `runner_pid` filled in later by Story 4.2, `slug`,
  `acquired_at`) after acquiring, truncating any leftover contents. Releases and closes in a
  `finally`. Do **not** implement a lease-expiry-based stale-file deletion path; read the locked
  decision above for why that mechanism fails AC-444. New `scripts/test_queue_lock.py` (registered
  in `run_all_tests.py`) proves: a second in-process acquire of the same slug raises; a second
  acquire from a **live child process** raises; and after that child exits the lock is
  immediately acquirable with no cleanup step.

- [x] **Story 4.2 — `scripts/run_queue_worker.py`: claim, fence, lock, invoke.**
  (FR-343, FR-344, AC-442, AC-444, AC-447)
  Loop: `claim_pack()`, then per slug in order: re-read the row and re-check the fencing token
  against the database, acquire the slug lock (on `SlugLockUnavailable`, skip the slug and leave
  it for the lock holder, per FR-343's "a worker that cannot get the lock does not run the slug"),
  fenced `transition(..., 'in_progress')` immediately before invoke, then launch
  `python scripts/run_submission.py {slug} --resume` (bare slug, never a `pending_review/` path;
  omit `--resume` only on a first run with no `workflow_state.json`). On Windows, assign the child
  to a Job Object created with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (stdlib `ctypes`). On POSIX,
  start the child in a new process group and kill the group on worker exit. Write the child PID
  into the lock payload. While the child runs, poll `proc.wait(timeout=...)` in a loop and call
  `heartbeat()` each iteration; no background thread. Release that slug's lock when the invocation
  ends, before starting the next slug. `run_submission.py` is invoked as an unmodified subprocess
  and is not edited by any story in this CR.

- [x] **Story 4.3 — Map `workflow_state.json` back onto the queue mirror.** (FR-344, AC-447)
  After the child exits: re-resolve the folder across `data/pending_review/`, `data/submissions/`,
  and `data/archive/skipped/` (Fact 3; copy the approach in
  `server/services/runSubmissionRunner.ts:findFolderAfterRun`), update `folder_root` and `slug`
  if placement moved or renamed it, read `workflow_state.json`, and map: `WAITING_FOR_LLM` or
  `NEEDS_DISPOSITION` to `paused` **with the lease released** (`locked_by` and `lease_expires_at`
  cleared, so it does not hold a pack slot); `COMPLETE` / `COMPLETE_WITH_OVERRIDE` /
  `PRACTICE_COMPLETE` / `SKIPPED` to `done`; anything else stays `in_progress` for the next pass.
  Mirror `last_workflow_status` and `last_stage` at the same time. The exit code is recorded for
  context only, never used as the mapping key. Tests drive the mapping from synthetic
  `workflow_state.json` fixtures with a stubbed subprocess, in
  `scripts/test_run_queue_worker.py` (new, registered in `run_all_tests.py`).

- [x] **Story 4.4 — Abort, token exhaustion, and release-on-signal.** (FR-344, AC-442)
  SIGINT / SIGTERM handler and an explicit token-exhaustion path: release every pack row that has
  not yet reached `in_progress` back to `queued`, leave the in-flight row where it is, remove the
  slug lock, exit. The in-flight job stays at its last finished stage receipt even when the child
  was killed mid-stage (at-least-once, per CR-119 Decision 4). Tests assert: unstarted rows return
  to `queued`; the in-flight row's `workflow_state.json` is untouched by the worker; a subsequent
  `run_submission.py {slug} --resume` is the documented next step (assert the command the worker
  would emit, do not execute a real Stage 0 in a test).

- [x] **Story 4.5 — The AC-444 two-worker regression test.** (AC-444, FR-343, FR-344)
  The acceptance criterion gets its own story because it is the one this design was chosen for.
  In `scripts/test_run_queue_worker.py`: worker-1 holds the slug lock with a **live** stub child
  process and an **already-expired** `lease_expires_at`. Worker-2 claims the row (which it is
  entitled to do, the lease is expired) and attempts to run it. Assert: worker-2 fails to acquire
  the lock, does not spawn a second runner, and the test observes exactly one runner process for
  that slug. Then let the stub child and worker-1 exit, and assert worker-2 acquires the lock on a
  later pass with no manual cleanup. Also assert the negative case explicitly: worker-2 never
  deletes worker-1's lock file while worker-1's process is alive.
  **Hard-kill extension (Jason 2026-09-18):** worker-1 is `TerminateProcess`'d (not Ctrl+C) while
  the stub child is still running. Assert the child is gone before a second worker can acquire
  that slug's lock. On Windows this is the Job Object `KILL_ON_JOB_CLOSE` proof. On POSIX this is
  the process-group kill proof. Do not skip this case on Windows; this is Jason's OS.

---

## Epic 5 — Pipeline visibility panel in Review Center

**Goal:** Jason can see queue depth, leases, stuck items, and quarantine without opening SQLite.

OQ-TL-1 resolved 2026-09-18: `STUCK_STALE_MINUTES = 120` as a named constant. Stories 5.1–5.4 can proceed.

- [x] **Story 5.1 — `server/repository/pipelineQueueRepository.ts` read queries.**
  (FR-345, AC-443, SEC-007)
  Named exports, functional style, no `any`: `queueCounts()` returning the six counts
  (`queued`, `leased`, `in_progress`, `paused`, `done`, plus `quarantined` from `csv_quarantine`),
  `activeLeases()` returning slug, company, `locked_by`, `lease_expires_at` and a derived lease
  age in minutes, `stuckItems(staleMinutes)` returning expired-lease rows and rows whose last
  stage receipt is older than the threshold, and `quarantineRows()` returning source file, line
  number, error code, reason, and id. **`raw_payload` is not selected by any of these queries**
  and `networking_contacts_raw` is not selected by any of them. Mirror the shape of
  `server/repository/reviewCenterRepository.ts`, including the injectable
  `database: Database.Database = db` parameter that its tests rely on. New
  `tests/unit/pipelineQueueRepository.test.ts` against an in-memory database seeded with synthetic
  rows.

- [x] **Story 5.2 — `server/routes/pipelineQueue.ts` read-only API.** (FR-345, AC-443, SEC-007)
  `GET /api/pipeline-queue/stats` (counts + leases + stuck) and
  `GET /api/pipeline-queue/quarantine` (detail list). `createPipelineQueueRouter(database = db)`
  factory plus a default export, `router.use(requireApiToken)` as the first line, matching
  `server/routes/reviewCenter.ts` exactly. Mount with `app.use('/', pipelineQueueRouter)` in
  `server/index.ts` alongside the existing routers (lines 87-89). No POST, no PATCH, no DELETE in
  this CR. New `tests/unit/pipelineQueueRoute.test.ts` modeled on
  `tests/unit/reviewCenterRoute.test.ts`, including the `tests/unit/routerAuth.test.ts` style
  unauthenticated-request assertion.

- [x] **Story 5.3 — `src/components/PipelineQueuePanel.tsx` and its client plumbing.**
  (FR-345, AC-443)
  New `src/types/pipelineQueue.ts`, `src/lib/pipelineQueue.ts` (fetch + defensive normalize, in
  the style of `src/lib/workflowOperator.ts`'s `normalizeWorkflowResult`), and
  `src/hooks/usePipelineQueue.ts` (in the style of `src/hooks/useReviewCenter.ts`: `items`,
  `isLoading`, `error`, `refresh`). The panel renders: the six live counts, an active-leases list
  showing worker id and lease age in minutes, a visually distinct stuck list, and the quarantine
  count. Each leased or stuck row links to the existing job detail view through the same
  `onOpenJob` path `ReviewCenterView` already uses. Reuse the existing Material tokens and the
  `outlined-surface` / `bg-surface-container-lowest` classes already in `ReviewCenterView.tsx`;
  **do not introduce new visual language** (Jason skipped the product-designer stop; inventing a
  new card treatment here would be designing without a designer). Mount it in
  `src/pages/ReviewCenterView.tsx` directly after `<WorkflowOperator />` (line 644). The existing
  review queue list is not replaced, hidden, or reordered. Client test
  `src/lib/pipelineQueue.test.ts` alongside `src/lib/workflowOperator.test.ts`.
  Stuck receipt-age uses `STUCK_STALE_MINUTES = 120` (OQ-TL-1 resolved). Do not add a Settings
  control. Do not add claim/release/reclaim buttons.

- [x] **Story 5.4 — Quarantine detail view inside the panel.** (FR-345d, AC-443)
  An in-place expandable section of `PipelineQueuePanel` (not a new tab, not a new route, not a
  modal shell) listing source file, 1-based line number, and error code per quarantined row.
  `raw_payload` is not rendered in this CR: the count, the file, the line, and the code are what
  AC-443 requires, and the payload is the one field carrying real JD text. Replay of a fixed row
  is Phase B; the row is parked visibly and that is the whole Phase A promise.

---

## Epic 6 — Registry, traceability, and closeout

**Goal:** the spec record matches what landed, and the next person finds the new commands.

- [x] **Story 6.1 — Requirements registry and traceability.** (FR-340 through FR-345, AC-438
  through AC-448, DATA-006, SEC-007, NFR-016)
  Flip the CR-119 rows in `docs/spec/02-requirements-registry.md` from `draft` to `accepted` and
  add AC-444 through AC-448 there if the PM pass left them CR-only. Add the traceability rows in
  `docs/spec/06-traceability/traceability-matrix.md` mapping each FR to the real files that landed.

- [x] **Story 6.2 — Operator docs and changelog.** (FR-340, FR-343, FR-344)
  Add the three new commands (`ingest_csv_queue.py`, `queue_claim.py`, `run_queue_worker.py`) to
  `docs/ACTIVE_WORKFLOW.md` in the ingest position, stating plainly that `run_submission.py` and
  `--resume` are unchanged and remain the canonical runner. Append a `CHANGELOG.md`
  `[Unreleased]` entry per `docs/AGENTS.md`'s template, marked `[DRAFT]`. Set this file's
  frontmatter `status: done` and flip CR-119 plus the
  `docs/spec/05-change-requests/README.md` row to Implemented. Do not push.

---

## Rollout priority

If only part of this ships, ship it in this order.

1. **Epic 1.** Additive DDL and two gitignored directories. Cannot break anything, and every later
   epic reads the tables it creates. Story 1.3's anti-drift test comes with the schema, not after
   it, for the same reason CR-075 put `test_contracts.py` before the `contracts.py` edits.
2. **Epic 2.** This alone replaces today's print-and-continue with a durable quarantine record and
   kills the hardcoded Downloads paths. It is independently useful even if no worker is ever run:
   Jason drops a CSV, gets folders and a quarantine list, and drives `run_submission.py` by hand
   exactly as he does now.
3. **Epic 3.** Pure SQLite, no filesystem and no subprocess, so it is the last epic that is fully
   testable without a real run. Landing it before Epic 4 keeps the lock work small.
4. **Epic 4.** The riskiest epic. Story 4.1 (the lock primitive) must land and be green before 4.2
   invokes anything, and Story 4.5 is the acceptance gate for the whole epic; treat a red 4.5 as a
   design failure to escalate, not a test to loosen.
5. **Epic 5.** Last among features. Story 5.3 uses `STUCK_STALE_MINUTES = 120`. Panel is read-only.
6. **Epic 6.** Not optional. The three new commands are invisible to the next session unless 6.2
   lands.

**PLAN Task 3 stays blocked** until Epic 4 is green. The four Downloads `applyr_jobs*.csv` files
are the first real drop into the new inbox *after* this CR lands; ingesting them is not a
close-out action for any story here.

---

## Do not touch

- `scripts/run_submission.py` and anything under `scripts/workflow/`. Invoked as a subprocess,
  never edited, never imported. `--resume` is the resume mechanism.
- `workflow_state.json` and `stage_receipts/*.json`. Read-only for every file in this CR. The
  queue `status` column is a mirror (AC-447).
- `data/candidate_preferences.json` (Settings UI is the only writer), `data/stage0_classifier*.pkl`
  (the leftover candidate pkl stays unpromoted), and `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER`
  (stays off).
- `scripts/archive/import_csv_*.py`. Not the product path, not revived.
- The `contacts` table and anything in CR-071. `networking_contacts_raw` is stored verbatim and
  never parsed in this CR.
- `server/services/exportPendingReview.ts`. Unifying it onto this queue is Phase B.
- Any existing `.gitignore` rule. Add entries, do not narrow or reorder.
- Any global SQLite pragma on the shared database. `server/db.ts` owns those.

---

## Open questions routed back to PM

All three resolved 2026-09-18 by PM after this tech-lead pass. Spec text in
`docs/spec/05-change-requests/CR-119-csv-drop-queue.md` Decisions 17–19.

- **OQ-TL-1** — `STUCK_STALE_MINUTES = 120` named constant in Phase A. Settings control is Phase B.
- **OQ-TL-2** — Lock path amended to `data/queue_locks/{slug}.lock`.
- **OQ-TL-3** — Phase A panel is read-only. No Release action.
