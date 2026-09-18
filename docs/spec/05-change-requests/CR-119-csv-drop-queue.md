# CR-119 — CSV Drop Queue, Harness Lease, and Pipeline Visibility

**Status:** Implemented
**Date:** 2026-09-18
**Author:** Product Manager (Cursor / Claude Sonnet 4.6)
**Approved:** 2026-09-18 (Jason), with OQ-1 resolved and Changes 1–4 below
**Related CRs:** CR-091 (pending_review + skip ledger), CR-076/077 (run_submission + --resume), CR-114/118 (Stage 0 internals — unchanged by this CR), ADR-001 (SQLite local-first)

---

## Overview

This CR introduces a durable, lease-protected ingest and queue layer for CSV-origin job opportunities. Jason drops `applyr_jobs*.csv` files (columns: Company, Position, Job Description, URL, Networking Contacts) into a known inbox folder (`data/inbox/csv/`). A normalizer validates rows and quarantines bad ones with a durable record. Good rows persist as queued opportunities in SQLite and their `pending_review/{slug}/Original_JD.txt` files are written using the same convention already established by `import_csv_to_submissions.py`. A claim API issues small, lease-protected packs of work to Python harnesses. The existing `run_submission.py` runner handles each job — unchanged. When a harness dies mid-pack, unclaimed jobs return to `queued` and the interrupted job resumes from its last stage receipt. Review Center gains a pipeline visibility panel showing queue depth, current leases, stuck items, and quarantine counts without any new app shell.

This CR does **not** change Stage 0/1/2/3 internals, does not replace or rewrite `run_submission.py`, and does not build a second workflow engine.

---

## Problem

Jason drops `applyr_jobs*.csv` files into a folder. Today `scripts/import_csv_to_submissions.py`:

- Hardcodes four specific paths under Jason's Downloads folder in `main()`, making it non-portable and blind to new drops.
- Prints empty and skipped rows to stdout then continues, with no durable quarantine record — the diagnostic information is gone when the terminal closes.
- Dumps all valid rows into `data/pending_review/` at once with no pack mechanism, regardless of how many rows the CSV contains.
- Has no lease table. If a harness dies mid-batch, an unknown number of folders sit in a partial state. No other harness can tell what is free, what is finished, and what was abandoned.

`server/services/exportPendingReview.ts` already exports scout-origin rows to the same `pending_review/` tree and enforces a 200-character minimum JD-text length (`LENGTH(TRIM(jd_text)) >= 200`). That export path has no queue state either, but fixing it for scout-origin rows is Phase B, not this CR.

Review Center can start, resume, and status a single slug but shows no queue depth, lease ownership, quarantine count, or stuck-item list. Jason cannot see pipeline state without grepping folders or reading SQLite directly.

---

## Decision (locked — do not reopen unless an existing CR or decision conflicts)

1. **Durable unit is one opportunity, not a pack.** A pack is claim size only (recommended 5–10, default 8). Packs are not atomic. Unfinished jobs in a dead pack return to `queued`.
2. **Do not replace Stage 0/1/2/3.** Canonical runner stays `python scripts/run_submission.py`. Resume stays `--resume`. Authority stays `workflow_state.json` + `stage_receipts/`. Incoming PASS folders still live under `data/pending_review/` (CR-091). Skip ledger still wins. Queue status only mirrors workflow authority for claim and visibility. Do not build a second source of truth for stage progress.
3. **Do not build Temporal, Camunda, or a second workflow engine.** Lease + heartbeat + checkpoint at stage boundaries is enough.
4. **In-flight Agy/LLM work may run again.** Resume is at-least-once from the last finished receipt. Handlers must be idempotent: no second skip-ledger row, no second folder for the same URL, no second folder for the same URL-less company+title.
5. **Throw-out is quarantine, not delete.** Keep the raw CSV. Keep the bad row with source file name, line number, raw payload, and error code. Jason can see it in the app.
6. **UI is in scope.** Queue depth, pack size, who claimed what, lease age, last stage, stuck list. Reuse Review Center / Opportunities patterns. Do not invent a second app shell.
7. **Three layers stay separate: Ingest / Claim / Resume.** Each layer has a single responsibility and a clear handoff to the next.
8. **Token exhaustion = drop the lease, leave the current job at last receipt.** Not compact 30 jobs in one chat.
9. **Local SQLite only, two harnesses on Jason's PC.** ADR-001 constrains this. No multi-machine distributed queue.
10. **No background file-watcher daemon.** Ingest is an explicit scan triggered by CLI command or API call. Watching `data/inbox/csv/` for new drops may be implemented as a poll on CLI invocation, not a daemon. Watching Jason's Downloads folder is out of scope.
11. **JD minimum length: 200 characters** (matching `exportPendingReview.ts`'s existing `LENGTH(TRIM(jd_text)) >= 200` gate). Rows below this threshold are quarantined, not silently skipped or printed and forgotten.
12. **Dedup order: URL match, then company+title when URL is absent, then skip ledger.** URL is preferred. When URL is absent, company+title is checked against existing `pending_review/` folders, `submissions/` folders, existing queue rows, and the skip ledger. A row with neither URL nor Position cannot be deduped; quarantine it with error code `NO_DEDUP_KEY` instead of queueing it.
13. **File dedup ledger keyed on sha256 only.** Filename is stored for display. The same content saved as `applyr_jobs (1).csv` must hit the ledger. Row dedup remains the real guarantee.
14. **Drop directory: `data/inbox/csv/`** (gitignored contents). Processing state is tracked by the file ledger; raw CSVs are archived, not deleted.
15. **Default pack size: 8, maximum 10.** Configurable pack size via Settings UI is Phase B — not in this CR.
16. **Keep the Networking Contacts cell as a raw string.** Store it verbatim on the queue row in nullable TEXT `networking_contacts_raw`. Do not create CR-071 `contacts` records. Do not parse the cell. Parsing and linkage are Phase B. The bookmarklet's `extractNetworkContacts()` scrapes LinkedIn's "in your network" section on purpose; filled on 6 of 61 real rows. The value is LinkedIn page state from the moment the job was saved, so retyping means revisiting every posting. Dropping it is the same silent loss decision 5 forbids. SEC-007 already covers these values.
17. **Per-slug lock file lives at `data/queue_locks/{slug}.lock`, not inside the job folder.** Jason required an exclusive per-slug lock that guards the folder. `stage0_placement.py` moves `pending_review/{slug}` on PASS and SKIP, and `move_folder_robust()` fails a Windows rename when a handle is held under the tree (CR-092). An open lock inside the job folder would force that path on every PASS. The lock still names the slug and still lives inside the repo data tree (SEC-007). Mechanism: OS byte-range lock (`msvcrt.locking` on Windows) held for the duration of that slug's runner invocation, not for the whole worker process lifetime. A worker running a pack of 8 does not hold all 8 locks until exit. Not exclusive-create plus clock-based stale delete (that fails AC-444 while harness-1 is still alive).
18. **Stuck-item staleness in Phase A is a named constant, not a Settings control.** `STUCK_STALE_MINUTES = 120`. Expired-lease rows are stuck regardless of this number. Receipt-age stuck uses 120 minutes. The Settings control joins pack size in Phase B.
19. **Phase A pipeline panel is read-only.** Counts, leases, stuck list, quarantine detail, links into the existing job view. No claim, release, or reclaim button. CLI remains the mutating surface.
20. **The runner child dies with the worker.** On Windows the worker launches `run_submission.py` inside a Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, so a hard kill of the worker (`TerminateProcess`, not Ctrl+C) kills the child before another worker can take the slug's lock. On POSIX the child is in a new process group and is killed on worker exit. This closes the orphan hole: the OS lock belongs to the worker, not the child, and Windows does not kill the child when the parent is hard-killed. Consistent with FR-344: SIGINT may kill the subprocess. Do not rewrite `run_submission.py`.
21. **Resume by bare slug, not path.** Stage 0 moves PASS folders to `data/submissions/`. `scripts/workflow/runner.py:_resolve_folder` already resolves a bare slug (`submissions/` first, then `pending_review/`). The worker invokes `python scripts/run_submission.py {slug} --resume`. Do not pass `data/pending_review/{slug}`.

---

## Queue status transitions

`workflow_state.json` + `stage_receipts/` stay the authority for stage progress. The queue `status` column only mirrors that authority for claim and visibility. Do not treat queue status as a second workflow engine.

| From | To | When |
|------|----|------|
| `queued` | `leased` | Claim transaction |
| `leased` | `in_progress` | Worker is about to invoke `run_submission.py` for that slug (fenced write: fencing token re-checked against the DB, exclusive per-slug lock acquired) |
| `in_progress` | `paused` | `run_submission.py` returns `WAITING_FOR_LLM` or `NEEDS_DISPOSITION`. The worker releases the lease (`locked_by` and `lease_expires_at` cleared). A paused job does not hold a pack slot. |
| `paused` | `queued` | `contracts.check_stage1_ready(folder)` returns True (packet `ready` plus `Resume.md`, `CoverLetter.md`, and `claim_provenance.json` all present), or the next claim sees that `workflow_state` has moved past `WAITING_FOR_LLM`. Do not requeue when only some of the three files are present. |
| `in_progress` | `done` | Workflow is `COMPLETE` / `COMPLETE_WITH_OVERRIDE` / `PRACTICE_COMPLETE`, or a Stage 0 skip is recorded (the folder goes to `archive/skipped`) |
| `leased` or `in_progress` | reclaimable | Lease has expired, subject to the per-slug OS lock at `data/queue_locks/{slug}.lock`. A worker that cannot get the lock does not run the slug. |

---

## Requirements

### Functional Requirements

| ID | Title | Priority | Description |
|----|-------|----------|-------------|
| `FR-340` | Drop-folder ingest and file ledger | P0 | An explicit CLI command and/or API call scans `data/inbox/csv/` for `*.csv` files. Before parsing, the system waits until each file reaches stable size (stable-size or drop-then-rename guard). Each scanned file is checked against a durable file ledger keyed on **sha256 only**; filename is stored for display and is not part of the uniqueness key. A file whose content hash is already in the ledger is not re-ingested. Successfully parsed files are moved to an archive state (file moved to `data/inbox/csv/archive/` or equivalent); structurally broken files (e.g., non-parseable CSV, wrong encoding) are moved to a quarantine path (`data/inbox/csv/quarantine/`) with a file-level record stating filename and reason. No background file-watcher daemon is introduced. |
| `FR-341` | Row validation and quarantine | P0 | For each CSV row, the normalizer checks: (a) company field is non-empty; (b) Job Description text, after trimming, is at least 200 characters; (c) the row has a URL or a Position so it can be deduped. Rows failing (a) or (b) are written to a durable quarantine record containing: source file name, 1-based line number, raw row payload, and a machine-readable error code. A row with neither URL nor Position is quarantined with error code `NO_DEDUP_KEY` and is not queued. Good rows in the same file proceed to the persist step. No row is silently dropped. No row that fails validation reaches `data/pending_review/` or the SQLite queue. |
| `FR-342` | Persist queued opportunities and write pending_review JD | P0 | Each validated row is upserted into SQLite as an opportunity with status `queued`. Nullable TEXT `networking_contacts_raw` stores the Networking Contacts cell verbatim (empty cell is NULL or empty string; do not invent contacts). Before any write, the skip-ledger lookup runs: a URL already in `stage0_skips` produces neither a SQLite opportunity row nor a `pending_review/` folder. For new opportunities, `data/pending_review/{slug}/Original_JD.txt` is written in the existing CSV-import format from `write_jd()`: optional `URL:` line, optional `Title:` line when Position is present, then JD text. A URL already present in an existing `pending_review/` or `submissions/` folder or existing queue row reuses that slug without a second file write. When URL is absent, company+title is checked against existing `pending_review/` folders, `submissions/` folders, existing queue rows, and the skip ledger; a match reuses or skips, never a second folder. All operations are idempotent: running ingest twice on the same file, or on two files that share the same URL-less company+title row, produces one queue row and one folder. Do not create CR-071 `contacts` records. Do not parse `networking_contacts_raw`. |
| `FR-343` | Pack claim, exclusive lease, heartbeat, expiry, fencing token, and folder lock | P0 | A claim operation accepts `--size` (default 8, maximum 10 per NFR-016) and `--worker <harness-id>`. It executes a short SQLite transaction that selects up to `size` rows with status `queued` (and `paused` rows that claim-time promotion has moved back to `queued`) and advances them to `leased` with `locked_by`, `lease_expires_at`, and a per-row incrementing fencing token. The DB lock is held only for the duration of this claim transaction and is released before any Stage 0 subprocess begins. A heartbeat call extends `lease_expires_at` for all rows held by the calling worker. A release call returns all leased-but-unstarted rows for a given worker back to `queued`. A lease whose `lease_expires_at` has passed without a heartbeat is reclaimable by any subsequent claim call without manual intervention, subject to the per-slug lock. A write from a worker holding an expired or mismatched fencing token is rejected without modifying SQLite state. **Fencing also guards the job folder.** `run_submission.py` has no file lock. Before the worker invokes `run_submission.py` for a slug, it re-checks its fencing token against the DB. It also acquires an exclusive per-slug OS lock at `data/queue_locks/{slug}.lock` (worker id and token in the payload). The lock is held for the duration of that slug's runner invocation and released when that invocation ends. A worker does not hold every pack slug's lock until process exit. A leftover file whose OS lock is unheld may be overwritten; a lock the OS still holds must not be taken, even if the SQLite lease has expired. A worker that cannot get the lock does not run the slug. Do not put the lock file inside the job folder: Stage 0 placement moves that folder and a held Windows handle under the tree breaks `move_folder_robust()` (CR-092). |
| `FR-344` | Worker abort/release, folder lock, and resume via run_submission --resume | P0 | When the worker process receives an abort signal or detects token exhaustion mid-pack, it releases all jobs in the current pack that have not yet had `run_submission.py` invoked for them, returning them to `queued`. The in-flight job stays at its last *finished* stage receipt. Mid-stage Agy/LLM work may be lost and may run again (at-least-once). SIGINT may kill the subprocess; that is allowed. The worker launches the runner inside a Windows Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (POSIX: new process group, killed on worker exit) so a hard-killed worker does not leave an orphaned child writing the folder. Queue status follows the transition table: `leased` → `in_progress` is a fenced write immediately before invoke; `WAITING_FOR_LLM` / `NEEDS_DISPOSITION` → `paused` with the lease released so the job does not hold a pack slot; `paused` → `queued` when `contracts.check_stage1_ready(folder)` is True or `workflow_state` has moved past `WAITING_FOR_LLM`; terminal COMPLETE* or Stage 0 skip → `done`. A subsequent call to `python scripts/run_submission.py {slug} --resume` (bare slug; `runner._resolve_folder` searches `submissions/` then `pending_review/`) advances that job from the last finished receipt without re-running completed stages. No second skip-ledger row is written for a URL already in `stage0_skips`. No second `pending_review/` folder is created for a URL already present or for a URL-less company+title already present. Two workers on an expired lease for the same slug: only one runner process executes. |
| `FR-345` | Pipeline visibility panel in Review Center | P0 | Review Center gains a pipeline section — not a new app shell — displaying: (a) live counts for `queued`, `leased`, `in_progress`, `paused`, `done`, and `quarantined` states as defined in the transition table; (b) current leases with worker ID and lease age; (c) a stuck list of items with an expired lease (no heartbeat received before `lease_expires_at`) or a stage receipt older than a configurable staleness threshold; (d) quarantine row count with navigation to a quarantine detail view showing source file, line number, and error code per row. Each leased or stuck item links to its existing job folder view in Review Center. The panel does not replace or hide the existing Review Center job list. Counts are derived from the queue mirror plus quarantine records; stage labels come from `workflow_state.json`, not a parallel progress store. |

### Data Requirements

| ID | Type | Priority | Status | Description | Source |
|----|------|----------|--------|-------------|--------|
| `DATA-006` | data | P0 | accepted | Queue state (status, locked_by, lease_expires_at, fencing_token, queued_at, claimed_at, nullable `networking_contacts_raw`), the file-ingest ledger (sha256 uniqueness key, filename for display, ingested_at, row_count, quarantine_count), and quarantine records (source_file, line_number, raw_payload, error_code, quarantine_reason) all live in the gitignored `jobagent.sqlite` (ADR-001). `data/inbox/csv/` and its subfolders (`archive/`, `quarantine/`) are gitignored. Per-slug lock files live at `data/queue_locks/{slug}.lock` inside the repo data tree, not inside the job folder. No queue state, lease data, quarantine detail, `networking_contacts_raw`, or JD/PII from CSV rows enters tracked files, git commits, test fixtures, or log files. | CR-119 |

### Security Requirements

| ID | Type | Priority | Status | Description | Source |
|----|------|----------|--------|-------------|--------|
| `SEC-007` | security | P0 | accepted | File writes during ingest are restricted to paths inside the repo data tree: `data/inbox/csv/` (inbox, archive, quarantine), `data/pending_review/`, and `jobagent.sqlite`. No write occurs outside these expected paths. JD text and Networking Contacts column values from CSV rows do not enter tracked fixtures, git commits, test reports, or log files. | CR-119 |

### Non-Functional Requirements

| ID | Type | Priority | Status | Description | Source |
|----|------|----------|--------|-------------|--------|
| `NFR-016` | performance / correctness | P0 | accepted | Claim size is bounded at runtime: default 8, maximum 10 (handoff recommended 5–10). The claim API rejects a size below 1 or above 10. The SQLite DB lock is held only for the duration of the claim transaction and released before any Stage 0 subprocess begins. A single ingest run over a 30-row CSV must not block the UI thread or hold an unbounded DB lock. | CR-119 |

---

## Acceptance Criteria

| ID | Criterion | FR |
|----|-----------|----|
| `AC-438` | A file dropped into `data/inbox/csv/` whose SHA-256 matches a previously ingested file produces zero new opportunity rows and zero new quarantine records when ingest is triggered, even if the filename differs (e.g. `applyr_jobs.csv` then `applyr_jobs (1).csv`). A structurally broken CSV (e.g., mismatched columns, non-UTF-8 encoding after BOM stripping) produces a file-level quarantine record with filename and reason, and does not prevent valid files in the same inbox scan from being processed. Ingest does not begin parsing a file that is still being written (stable-size or drop-then-rename guard fires first). | FR-340 |
| `AC-439` | A CSV row where the company field is empty, or where Job Description text after trimming is fewer than 200 characters, is written to a quarantine record that contains: source file name, 1-based line number, raw row payload, and a machine-readable error code. Good rows in the same file are not blocked. After ingest, no quarantined row appears as a `queued` opportunity in SQLite, and no `data/pending_review/` folder is created for it. | FR-341 |
| `AC-440` | After ingest of a valid CSV row: (a) SQLite contains an opportunity row with status `queued`; (b) `data/pending_review/{slug}/Original_JD.txt` exists in the CSV-import format (optional `URL:` line, optional `Title:` line, then JD text); (c) `networking_contacts_raw` equals the Networking Contacts cell verbatim (NULL or empty when the cell is empty); (d) no CR-071 `contacts` row is created; (e) running ingest again on the same file produces no additional rows or folders (idempotent). A row whose URL matches a `stage0_skips` ledger entry produces neither a SQLite row nor a folder. A row whose URL matches an existing `pending_review/` folder or queue row reuses that slug without a second file write. | FR-342 |
| `AC-441` | `claim --size 8 --worker harness-1` returns at most 8 rows in a single short SQLite transaction, sets their status to `leased`, populates `locked_by = 'harness-1'`, `lease_expires_at`, and increments each row's fencing token. `claim --size 11` is rejected. A heartbeat call from `harness-1` extends `lease_expires_at` on all its leased rows. A release call from `harness-1` returns all its still-`leased` rows to `queued`. After `lease_expires_at` passes without a heartbeat, a claim call from a second worker successfully leases those rows if it can take the per-slug lock. A write attempt from the first worker using the original fencing token is rejected without modifying SQLite state. The DB lock is not held during any Stage 0 subprocess invocation. | FR-343 |
| `AC-442` | When the worker receives SIGINT or detects token exhaustion mid-pack: (a) all jobs in the pack that have not yet had `run_submission.py` invoked are released to `queued`; (b) the in-flight job remains at its last finished stage receipt even if the subprocess was killed mid-stage; (c) `python scripts/run_submission.py {slug} --resume` (bare slug) on that job advances from that receipt without re-running completed stages; (d) no duplicate skip-ledger row is written for a URL already in `stage0_skips`; (e) no duplicate `data/pending_review/` folder is created for a URL already present. | FR-344 |
| `AC-443` | Review Center displays live counts for `queued`, `leased`, `in_progress`, `paused`, `done`, and `quarantined` states. Current leases show at minimum: worker ID and lease age in minutes. Stuck items (lease expired without heartbeat renewal, or last stage receipt older than `STUCK_STALE_MINUTES` which is 120 in Phase A) appear in a visually distinct list separate from active leases. Each leased or stuck row includes a link to the existing job detail view. A quarantine count is visible; navigating to it shows a detail view with source file, line number, and error code per quarantined row. The panel does not replace or hide the existing Review Center job list. The panel is read-only: no claim, release, or reclaim control. | FR-345 |
| `AC-444` | Two workers, expired lease, same slug: harness-1's lease expires while its `run_submission.py` subprocess is still running (or its OS lock is still held). Harness-2 claims the row. Only one runner process executes `run_submission.py` for that slug. The worker that cannot re-check a matching fencing token, or cannot acquire `data/queue_locks/{slug}.lock`, does not invoke the runner. After the holder exits, the OS lock is free so a later worker can take it. Harness-2 must not delete harness-1's lock file while harness-1's process is alive. Extended: harness-1 is hard-terminated with `TerminateProcess` (not Ctrl+C) mid-run. The runner child is gone before any other worker can take the slug's lock (Windows Job Object `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`; POSIX process group killed on worker exit). | FR-343, FR-344 |
| `AC-445` | Ingest two different files (different sha256) that contain the same URL-less row (same Company and Position, JD ≥ 200 chars). Result is one queue row and one `pending_review/` folder. | FR-342 |
| `AC-446` | A row with company and a usable JD, but neither URL nor Position, is quarantined with error code `NO_DEDUP_KEY`. It is not queued and no `pending_review/` folder is created for it. | FR-341 |
| `AC-447` | Queue status follows the transition table: claim sets `leased`; a fenced write immediately before `run_submission.py` sets `in_progress`; `WAITING_FOR_LLM` or `NEEDS_DISPOSITION` sets `paused` and clears `locked_by` / `lease_expires_at` (paused jobs do not occupy a pack slot on the next claim); `paused` → `queued` when `contracts.check_stage1_ready(folder)` is True or `workflow_state` has moved past `WAITING_FOR_LLM`; `COMPLETE` / `COMPLETE_WITH_OVERRIDE` / `PRACTICE_COMPLETE` or a recorded Stage 0 skip sets `done`. `workflow_state.json` remains the authority for stage progress; queue status is a mirror. | FR-343, FR-344, FR-345 |
| `AC-448` | A paused job whose folder has a ready packet and only 2 of the 3 Stage 1 files (`Resume.md`, `CoverLetter.md`, `claim_provenance.json`) stays `paused`. `contracts.check_stage1_ready(folder)` is False. The next claim does not promote it to `queued`. | FR-344 |

---

## Traceability Mapping

| Capability | Intended files | Notes |
|-----------|----------------|-------|
| Drop-folder ingest + file ledger | `scripts/import_csv_to_submissions.py` (replace hardcoded Downloads paths; add file-ledger logic) or new `scripts/ingest_csv_queue.py`; `data/inbox/csv/` (new gitignored directory tree); `jobagent.sqlite` schema migration | File ledger uniqueness keyed on sha256; filename stored for display |
| Row normalizer + quarantine | Same ingest script as above; `jobagent.sqlite` quarantine table | Quarantine replaces silent print-and-continue; 200-char gate matches `exportPendingReview.ts`; `NO_DEDUP_KEY` for URL-less Position-less rows |
| SQLite queue + pending_review write | `jobagent.sqlite` schema migration (pipeline_queue or equivalent table); ingest script; existing `write_jd()` convention | Status column: queued / leased / in_progress / paused / done; `networking_contacts_raw`; URL and URL-less company+title dedup against folders, queue, skip ledger |
| Claim / lease / heartbeat / expire / fencing / folder lock | New Python module or CLI (e.g., `scripts/queue_claim.py`); `jobagent.sqlite` lease columns (locked_by, lease_expires_at, fencing_token); per-slug OS lock at `data/queue_locks/{slug}.lock` | Short transaction; DB lock released before Stage 0 subprocess; re-check token then OS lock before invoke |
| Worker abort/release | Worker loop script or harness entrypoint; signal handler; lease release path; lock-file cleanup; Windows Job Object / POSIX process group around the runner child | Release unstarted; leave in-flight job at last receipt; pause releases pack slot; hard-kill of worker kills the child |
| Resume | Existing `python scripts/run_submission.py {slug} --resume` (bare slug; `scripts/workflow/runner.py:_resolve_folder` searches `data/submissions/` then `data/pending_review/`) | No changes to `run_submission.py` itself |
| Pipeline visibility | `server/routes/` (new or extended route for queue stats API); Review Center React component (new panel within existing shell); `jobagent.sqlite` read queries | Reuse Review Center nav; no new app shell; queue status is a mirror of workflow_state |

---

## Phase A vs. Phase B

### Phase A — ships in this CR (required to unblock PLAN Task 3)

- Known drop directory `data/inbox/csv/` (gitignored contents), explicit ingest scan via CLI and/or API.
- File dedup ledger on sha256; filename for display; file-level and row-level quarantine with durable records.
- Row normalizer: company required, JD text ≥ 200 chars (matching `exportPendingReview.ts`), URL optional, Position required when URL is absent (`NO_DEDUP_KEY` otherwise).
- SQLite queue table including `networking_contacts_raw`; `data/pending_review/` JD write; skip-ledger and folder/queue dedup for URL and URL-less company+title.
- Claim API/CLI with exclusive lease, heartbeat, release, expiry, fencing token, token re-check, and per-slug folder lock.
- Worker stop/release on abort; pause releases pack slot; resume via existing `python scripts/run_submission.py {slug} --resume`. Windows Job Object / POSIX process group so a hard-killed worker does not leave an orphaned runner. `paused` → `queued` only when `contracts.check_stage1_ready` is True (or workflow has moved past `WAITING_FOR_LLM`).
- Pipeline visibility panel in Review Center showing all six states, current leases, stuck list, and quarantine detail. Phase A panel is read-only. Stuck receipt-age uses `STUCK_STALE_MINUTES = 120`.

### Phase B — out of this CR (named follow-up, not accidentally omitted)

- **Configurable pack size in Settings UI** — default 8 is sufficient for Phase A. The setting must route through the Settings UI, never via direct edit of `candidate_preferences.json`.
- **Quarantine replay** — Jason fixes a bad row and re-enters it into the queue. Phase A parks the row visibly; replay is a follow-up.
- **Unified queue table for scout export and CSV drop** — `exportPendingReview.ts` and the new CSV ingest may write to the same SQLite queue table in Phase B so Today is not two separate lists. Phase A may queue CSV-origin rows without forcing scout rows onto the same table in this CR.
- **Parse `networking_contacts_raw` and link into CR-071 `contacts`** — Phase A stores the cell verbatim and creates no `contacts` records. Parsing names, `contact_type`, `job_id` linkage, and dashboard population are a follow-up.
- **Settings control for stuck-item staleness** — Phase A uses `STUCK_STALE_MINUTES = 120`. The Settings control joins pack size in Phase B.
- **Mutating queue actions in Review Center** (claim / release / reclaim buttons) — Phase A panel is read-only. CLI is the mutating surface.

---

## Out of Scope

The following are explicitly excluded from this CR. Do not implement, design, or raise them during the build phase.

| Excluded item | Reference |
|--------------|-----------|
| Promote `data/stage0_classifier.candidate.pkl` over the live pkl | `PLAN-2026-09-18-stage0-new-flow-ready.md`; live pkl hash `77b317...` stays unchanged |
| In-office / Aegon / ss_c skip-reason work | `docs/spec/08-implementation/stage0-backlog.md` |
| Stage 1 evidence-first authoring (CR-117 id collision / rename) | `docs/spec/05-change-requests/CR-117-stage1-evidence-first-authoring.md` |
| Changing Stage 0 Agy adapter behavior; `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER` stays off | `SESSION-HANDOFF-2026-09-18-csv-drop-queue.md` |
| PLAN Task 3 live Stage 0 batch | `docs/spec/08-implementation/PLAN-2026-09-18-stage0-new-flow-ready.md` Task 3 |
| Auto-running Stage 0 inside the Node scout process | Decision rule 10 above |
| Background file-watcher daemon on any directory | Decision rule 10 above |
| Multi-machine distributed queue | ADR-001 (SQLite local-first); two harnesses on Jason's PC only |
| Forcing 30-job batches because a CSV has 30 rows | Decision rules 1 and 15 above |
| Rewriting `scripts/run_submission.py` or calling CR-074 workers as an alternate sequencing path | `docs/ACTIVE_WORKFLOW.md`; decision rule 2 above |
| Editing `data/candidate_preferences.json` by hand | Root `AGENTS.md` |
| Harvesting the marked 5-PASS evidence CSV with `scripts/_harvest_pass5_evidence.py` | `SESSION-HANDOFF-2026-09-18-csv-drop-queue.md` |
| Importing the four Downloads `applyr_jobs*.csv` files via the old `import_csv_to_submissions.py` one-shot path | After this CR lands those four files are the first real files to drop into the new inbox; this CR does not run that import as the close-out of the spec phase |
| Reviving `scripts/archive/import_csv_*.py` as the product | One-off archive scripts; not the product path |
| Configurable pack size in Settings (Phase B) | Named Phase B above |
| Quarantine replay (Phase B) | Named Phase B above |
| Unifying scout export and CSV queue table (Phase B) | Named Phase B above |
| Parsing `networking_contacts_raw` or creating CR-071 `contacts` records (Phase B) | Named Phase B above; decision 16 |
| Settings control for stuck-item staleness (Phase B) | Named Phase B above; decision 18 |
| Claim / release / reclaim buttons on the Review Center panel | Named Phase B above; decision 19 |

---

## Open Questions

None remaining.

- OQ-1 resolved 2026-09-18: store `networking_contacts_raw` verbatim; do not parse; do not create CR-071 rows.
- OQ-TL-1 resolved 2026-09-18 (PM, after tech lead backflow): `STUCK_STALE_MINUTES = 120` constant in Phase A. Settings control is Phase B.
- OQ-TL-2 resolved 2026-09-18 (PM, after tech lead evidence from `stage0_placement.py` / CR-092): lock path is `data/queue_locks/{slug}.lock`. Intent of Change 1 (exclusive runner per slug) stands. Location moves so Stage 0 placement is not blocked by a held Windows handle.
- OQ-TL-3 resolved 2026-09-18 (PM, after tech lead backflow): Phase A panel is read-only.
- 2026-09-18 (Jason, before Story 4.1): Job Object / process group so a hard-killed worker does not orphan the runner (AC-444 extended). Lock held per slug invocation, not worker lifetime. Resume uses a bare slug. `paused` → `queued` uses `contracts.check_stage1_ready` (AC-448).
