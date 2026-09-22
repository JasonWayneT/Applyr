---
status: proposed
date: 2026-09-21
related: CR-091, CR-092, CR-119, CR-121, CR-122
---

# CR-123: Already-applied and archived postings close the CSV queue

## Decision sought

Stop treating a posting Jason already Applied (or later funnel) as new CSV pipeline work. Close the three ledgers that today do not close each other: `jobs.status`, `pipeline_queue`, and `stage0_skips`. Approve this spec before implementation.

## Overview

CSV ingest and the unsupervised worker can re-open a posting that is already an application outcome. CR-119 `resolve_opportunity` checks the skip ledger, live `pending_review/`, live `submissions/`, and existing queue rows. It does not check `jobs.status`. It does not check `data/archive/submissions/` or `data/archive/skipped/`. Stage 0 then PASSes a same-posting Applied row as a human flag (`active_application`, CR-092 / Kroll-style Tier 2). That flag is correct for an attended batch. CR-119 Stage 0 is unattended, so the worker authors anyway. `applyJobStatusUpdate` archives folders and never touches `pipeline_queue`. CR-119 already maps a recorded Stage 0 Skip to queue `done`; SKIPPED archive folders still sitting `paused` were never reconciled.

Identity stays the posting, not the company. URL first; company+title when URL is absent (CR-091 `AC-327`, CR-119 Decision 12). Do not reopen company-versus-posting.

This CR does **not** change skip-ledger semantics, company cooldown, different-role Applied flags, CR-121, CR-122, or scout Phase B. No new UI screens.

## Motivation

Live 2026-09-19 CSV ingest queued Certara, PeopleFinders, Velosio, Clarion Events, and Velera. Those postings were already `Applied` in `jobs` (some from May–August 2026). Folders already lived in `data/archive/submissions/`. Stage 0 PASSed Certara with `active_application: Applied` and a note to verify it is not a duplicate. The unsupervised worker kept authoring. Queue rows remain `paused`.

Cousin: GoodRx and Omnissa are SKIPPED under `data/archive/skipped/` while `pipeline_queue` is still `paused`. CR-119's transition table already says a recorded Stage 0 skip sets `done`. Those rows were never closed.

The miss is design, not a one-off ingest bug. Three ledgers never close each other. On reuse with no queue row, ingest creates one and re-queues an archived Applied pack.

## Locked decisions (do not reopen)

1. **Posting identity.** URL first (tracking-query stripped, same as CR-091 `AC-326`). When URL is absent, exact company+title. A different role at the same company is a different posting (`AC-327`).
2. **Already-applied funnel.** `jobs.status` in `APPLICATION_FUNNEL_STATUSES`: `Applied`, `Recruiter Screen`, `Core Interviews`, `Offer and Negotiation` (`shared/domain/jobPipeline.ts`). Same posting in that set is already handled.
3. **Not already-applied.** `Backlog`, `Drafted`, `Needs Retry` (and `New`) reuse the existing slug. They are not already-applied.
4. **Skip ledger is not the Applied memory.** Do not write `stage0_skips` for an Applied+ hit. `stage0_skips` remains Skip memory only (CR-091).
5. **Cooldown / Self-Rejected unchanged.** Closed, Rejected, Self-Rejected, and company cooldown stay the existing Stage 0 DB-gate path. They are not this CR's already-applied rule.
6. **Different-role Applied flag unchanged.** `is_different_role` at the same company still raises the existing `active_application` flag. That is not a same-posting Applied+ hit.
7. **No re-apply override in v1.** A live Applied+ posting is not re-queued. Jason did not ask for a force-reapply control (OQ-1 default: no).
8. **CR-119 Decision 12 is extended, not replaced.** Existing skip-ledger / live-folder / existing-queue checks stay. This CR adds `jobs` Applied+ and archive trees to the same posting lookup.
9. **No new UI.** Pipeline panel counts already include `done`. Closing rows is enough.

## Expected behavior

1. **Ingest, jobs Applied+.** Same posting already in `jobs` with funnel status Applied / Recruiter Screen / Core Interviews / Offer and Negotiation: no new pipeline work, no `pending_review/` folder, no skip-ledger write. Ingest treats the row like a skip-ledger hit (no queued row).
2. **Ingest, archive trees.** Same posting already under `data/archive/submissions/` or `data/archive/skipped/`: do not recreate `pending_review/`. Do not create a new `queued` row (a queue row with no live folder is the same ghost this CR closes).
3. **Existing queue + Applied+.** Existing `pipeline_queue` row for that posting whose `jobs` row is Applied+: mark the queue row `done`. Do not lease. Do not invoke `run_submission.py`.
4. **Status update closes the queue.** Mark as Applied (and later funnel statuses) via `applyJobStatusUpdate` closes matching queue row(s) to `done`. Matching is posting identity (URL, then company+title). Pre-apply statuses do not close the queue.
5. **Stage 0, same-posting Applied+.** Terminal already-handled, not PASS-with-flag. Do not author. Do not write the skip ledger. Queue `done`. This applies on the unsupervised CR-119 worker and on a hand `run_submission.py` for the same posting, so the flag cannot be ignored by changing who launched Stage 0. Different role at the same company stays the existing flag. Cooldown / Self-Rejected unchanged.
6. **Reconcile ghosts.** Existing non-`done` queue rows that match (1)–(3) become `done`, including SKIPPED archive folders with stale queue mirrors (GoodRx / Omnissa shape) and Applied archive packs still `paused` (Certara / PeopleFinders / Velosio / Clarion Events / Velera shape). Reconcile must run as part of this CR so the live panel is clean after ship, not only when a new CSV row happens to match.
7. **Pre-apply reuse.** Same posting in `Backlog` / `Drafted` / `Needs Retry` (or live `pending_review/` / `submissions/`): reuse the slug. Not already-applied.

## Behavior by case

| Case | Ingest | Queue | Stage 0 | Skip ledger |
|---|---|---|---|---|
| Same posting, `jobs` Applied / Recruiter Screen / Core Interviews / Offer and Negotiation | No folder, no new queue row | Existing row → `done`; never lease | Already-handled terminal. No author | Not written |
| Same posting under `archive/submissions/` or `archive/skipped/` | No new `pending_review/` | No new queued row; existing row → `done` | No new Stage 0 | Not written for this hit |
| Same posting, `jobs` Backlog / Drafted / Needs Retry | Reuse slug | Existing live row stays claimable | Existing Stage 0 | Unchanged |
| Same company, `is_different_role` true, other posting Applied | New work (new posting) | New or reused row for *this* posting | Existing `active_application` flag | Unchanged |
| Same company, cooldown / Self-Rejected | Existing ingest | Existing queue rules | Existing DB-gate Skip / reject | Written only on a real Skip, as today |
| Skip-ledger URL or company+title hit | Existing CR-119 / CR-091: no folder, no row | Unchanged | Unchanged | Unchanged |
| Recorded Stage 0 Skip (folder → `archive/skipped/`) | Unchanged | `done` (CR-119 table; this CR reconciles stale mirrors) | Unchanged | Unchanged |

## Requirements

| ID | Title | Priority | Description |
|----|-------|----------|-------------|
| `FR-361` | Ingest treats jobs Applied+ as already-handled | P0 | Before any `pending_review/` write or `pipeline_queue` insert, CSV ingest resolves the posting (URL, then company+title when URL is absent) against `jobs`. A match whose `status` is `Applied`, `Recruiter Screen`, `Core Interviews`, or `Offer and Negotiation` produces no new queue row, no `pending_review/` folder, and no `stage0_skips` write. The ingest result counts as already-handled the same way a skip-ledger hit counts as skipped (no queued row). `jobs.url` is part of the URL match. |
| `FR-362` | Ingest does not recreate archived packs | P0 | A CSV row whose posting already exists under `data/archive/submissions/` or `data/archive/skipped/` does not create a new `pending_review/` folder and does not insert a new `queued` row. Live `pending_review/` and live `submissions/` reuse stays CR-119. |
| `FR-363` | Applied+ queue rows are `done` and not leased | P0 | A `pipeline_queue` row whose posting matches a `jobs` Applied+ row is `done`. Claim must not lease it. The worker must not invoke `run_submission.py` for it. Rows in `queued`, `paused`, `leased`, or `in_progress` are all closable. A later write with a stale fencing token is already rejected (CR-119). This CR does not add a runner-kill. |
| `FR-364` | Funnel status update closes matching queue rows | P0 | `applyJobStatusUpdate` that sets `Applied`, `Recruiter Screen`, `Core Interviews`, or `Offer and Negotiation` closes matching `pipeline_queue` row(s) to `done`. Match is posting identity: `jobs.url` then company+title. Setting `Backlog`, `Drafted`, `Needs Retry`, or `New` does not close the queue. Folder archive behavior stays as today. |
| `FR-365` | Stage 0 same-posting Applied+ is already-handled | P0 | When Stage 0 identifies the same posting as `jobs` Applied+, the outcome is terminal already-handled: not PASS, not PASS-with-`active_application` flag, not a Skip. Do not author. Do not write `stage0_skips`. Set matching queue row `done`. A different role at the same company (`is_different_role`) keeps the existing flag. Company cooldown and Self-Rejected stay the existing DB-gate path. CR-121 `conversion_risk` is unchanged and does not apply to this terminal. |
| `FR-366` | Reconcile stale queue mirrors | P0 | Delivery includes a reconcile that marks `done` every existing non-`done` `pipeline_queue` row that matches FR-361, FR-362, or a recorded Stage 0 Skip whose folder is already in `data/archive/skipped/`. It must run without requiring Jason to re-drop the 2026-09-19 CSV. Ingest of a matching row also closes the existing row. After reconcile, the pipeline panel `paused` count no longer includes those ghosts. |

## Acceptance Criteria

| ID | Criterion | FR |
|----|-----------|----|
| `AC-470` | Ingest a valid CSV row whose URL (tracking-query stripped) matches a `jobs` row with status `Applied` (and separately each of Recruiter Screen, Core Interviews, Offer and Negotiation). Result: zero new `pipeline_queue` rows, zero new `pending_review/` folders, zero new `stage0_skips` rows. A URL-less row whose company+title matches the same Applied+ job behaves the same. A second ingest of the same file stays idempotent. | FR-361 |
| `AC-471` | Ingest a valid CSV row whose posting matches a folder already under `data/archive/submissions/` or `data/archive/skipped/` (URL, then company+title). No new `pending_review/` folder. No new `queued` row. Live `pending_review/` or live `submissions/` for the same posting still reuse the slug (CR-119). | FR-362 |
| `AC-472` | A `paused` (and separately `queued`) `pipeline_queue` row whose posting is `jobs.status=Applied` is set `done`. The next `claim` does not return it. The worker does not invoke `run_submission.py` for that slug. | FR-363 |
| `AC-473` | `applyJobStatusUpdate` to `Applied` on a job that has a matching non-`done` queue row leaves that row `done`. The same for Recruiter Screen, Core Interviews, and Offer and Negotiation. `applyJobStatusUpdate` to `Backlog` or `Drafted` does not mark the matching row `done`. | FR-364 |
| `AC-474` | Stage 0 on a same-posting Applied fixture (unsupervised-shaped: queue worker or `run_submission.py`) does not PASS, does not author, does not write `stage0_skips`, and sets the queue row `done`. A same-company different-role fixture still emits the existing `active_application` flag and is not this terminal. A Self-Rejected / in-window cooldown fixture still follows the existing DB gate, not this terminal. | FR-365 |
| `AC-475` | Reconcile (no new CSV required) marks `done`: (a) a paused queue row whose `jobs` posting is Applied+; (b) a paused queue row whose folder is already `data/archive/skipped/` (CR-119 skip→`done` never applied); (c) a paused queue row whose posting folder is already `data/archive/submissions/`. After reconcile those rows are not claimable. Live ghosts in this shape are Certara / PeopleFinders / Velosio / Clarion Events / Velera (Applied + archive/submissions) and GoodRx / Omnissa (SKIPPED + stale paused). Tests use synthetic fixtures, not those gitignored folders. | FR-366 |
| `AC-476` | Ingest a valid CSV row whose URL or company+title matches a `jobs` row in `Backlog`, `Drafted`, or `Needs Retry`. The existing slug is reused. A queue row is not treated as already-applied. No `stage0_skips` write from this rule. | FR-361 |

## Traceability Mapping

| Capability | Intended files | Notes |
|-----------|----------------|-------|
| Ingest Applied+ and archive dedup | `scripts/csv_ingest.py` (`resolve_opportunity`), `scripts/ingest_csv_queue.py`, `scripts/test_csv_ingest.py` | Extends CR-119 Decision 12 lookup; consult `jobs.url` / status; consult archive trees |
| Queue close + no lease | `scripts/pipeline_queue.py`, `scripts/run_queue_worker.py`, `scripts/test_pipeline_queue.py`, `scripts/test_run_queue_worker.py` | `done` is the existing terminal; do not add a seventh status |
| Status update closes queue | `server/services/jobStatusService.ts` (`applyJobStatusUpdate`), existing jobs status tests | Folder archive unchanged; queue write is additive |
| Stage 0 already-handled | `scripts/stage0_db_gate.py`, `scripts/build_stage0_fit_gate.py`, `scripts/workflow/runner.py` or queue worker mapping, `scripts/test_stage0_db_gate.py`, `scripts/test_build_stage0_fit_gate.py` | Not a Skip. Not CR-121 `conversion_risk`. Different-role flag stays |
| Ghost reconcile | Same queue/ingest modules; one path that does not require a new CSV | Clears live paused mirrors after ship |
| Panel counts | Existing Review Center pipeline panel (`FR-345`) | No new screens; `done` already counted |

`FR-342` / `AC-440` remain in force. Their lookup set is incomplete without FR-361 / FR-362. Do not rewrite FR-342; implement the extension here.

## Out of scope

| Excluded item | Why |
|---------------|-----|
| Skip-ledger semantics, `--force` PASS clearing a skip, practice-mode ledger rules | CR-091 stands |
| Company cooldown and Self-Rejected DB-gate behavior | CR-091 / CR-074 `AC-457`; unchanged |
| Different-role `active_application` flag (`is_different_role`) | CR-092 Kroll / Tier 2; still a flag, not this terminal |
| Re-apply override for a live Applied+ posting | OQ-1 default no |
| CR-121 conversion feasibility / `conversion_risk` / Agy rubric | Separate withhold |
| CR-122 unknown-tools / Review Center pause | Separate |
| Scout Phase B (scout rows on the CSV queue) | CR-119 Phase B |
| New UI screens, claim/release/reclaim buttons, Settings controls | Panel already shows `done` |
| Changing posting identity to company-level | Locked; do not reopen |
| Treating Closed / Rejected / Ghosted as already-applied at ingest | Those stay cooldown / outcome paths |
| Rewriting `run_submission.py` or a second workflow engine | CR-119 Decision 2 |
| Mass-deleting archive folders or `jobs` rows | Reconcile queue status only |
| Writing real JD/PII into tracked fixtures | `SEC-007` / `DATA-006` |

## Open Questions

None remaining that block this spec.

- **OQ-1 (resolved 2026-09-21, Jason):** Re-apply override for a live Applied+ posting. Default **no**. Do not build a force-requeue control in this CR.

## Release

Docs first. Then ingest + claim refuse + `applyJobStatusUpdate` close + Stage 0 already-handled + reconcile of existing ghosts. Independent QA on synthetic Applied+, archive, different-role, Backlog-reuse, and skip-ledger fixtures. After code lands, one reconcile (or ingest) must clear the live paused Applied/SKIPPED mirrors without Jason re-dropping the 2026-09-19 CSV.

Approve this spec before implementation.
