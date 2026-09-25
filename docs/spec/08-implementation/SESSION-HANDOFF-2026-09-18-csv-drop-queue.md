# Next session — CSV drop folder, queued packs, harness resume, pipeline UI

> Incoming brief. Start here. Do not reopen CR-114 close-out. Do not run the tiny live Stage 0 batch until this work is done.

```
status: next_session_brief
created: 2026-09-18
from: Cursor (Grok 4.6)
result: HANDOFF_TO_NEW_SESSION
prior_session: CR-114/118 close-out + Stage 0 new-flow ready Tasks 1–2
do_not: push; edit candidate_preferences.json by hand; promote leftover pkl;
        set APPLYR_STAGE0_SUBSCRIPTION_ADAPTER for production; harvest the
        marked 5-PASS evidence CSV; start PLAN Task 3; rewrite run_submission
```

**Jason's call (2026-09-18):** Build this. When it is done, run the small Stage 0 live batch from `PLAN-2026-09-18-stage0-new-flow-ready.md` Task 3. This session stays on CR-114/new-flow. The new session owns ingest + queue + resume + app visibility.

**Suggested CR number:** `CR-119`. Confirm against `docs/spec/05-change-requests/` before minting. Do not reuse `CR-117` (already owned by years-range; Stage 1 evidence-first draft collided on that id and is backlog). Next free FR/AC after CR-118 is `FR-340` / `AC-438` in the registry. Product manager assigns IDs. Do not invent them in chat.

**Delivery path:** Applyr team pipeline (`.codex/skills/applyr-team-pipeline/SKILL.md`). Product manager first. Product designer because UI visibility is in scope. Then tech lead + epics. Do not start senior-engineer until Jason has approved the CR.

---

## Problem in plain language

Jason drops `applyr_jobs*.csv` files (Company, Position, Job Description, URL, Networking Contacts) into a folder. Today a harness or a one-shot script (`scripts/import_csv_to_submissions.py`) tries to swallow the whole pile and then run Stage 0 on too many jobs at once. If the harness runs out of tokens, 30 folders sit in a weird mid-state and another harness does not know what is free.

He wants:

1. Drop CSVs into a known folder.
2. Normalize rows. Bad lines leave the good ones and get parked, not silently printed and forgotten.
3. Save work as small queued packs so nothing forces ~30 at a time.
4. If a harness dies mid-pack, jobs not in process stay queued. Another harness claims a pack that is not leased.
5. If a harness dies mid-opportunity, a new harness resumes that one job from the last finished stage.
6. The Applyr app shows pipeline state so he is not grepping folders.

## Locked design rules (do not reopen unless Jason says so)

1. **The durable unit is one opportunity, not a pack.** A pack is only a claim size (recommended 5–10, default 8). Packs are not atomic transactions. Unfinished jobs in a dead pack go back to `queued`.
2. **Do not replace Stage 0/1/2/3.** Canonical runner stays `python scripts/run_submission.py`. Resume stays `--resume`. Authority stays `workflow_state.json` + `stage_receipts/`. Incoming PASS folders still live under `data/pending_review/` (CR-091). Skip ledger still wins.
3. **Do not build Temporal / Camunda / a second workflow engine.** Lease + heartbeat + checkpoint at stage boundaries is enough.
4. **In-flight Agy/LLM work may run again.** Resume is at-least-once from the last *finished* receipt. Handlers must be idempotent (no second skip-ledger row, no second folder for the same URL).
5. **Throw-out is quarantine, not delete.** Keep the raw CSV. Keep the bad row with file name, line number, reason. Jason can see it in the app.
6. **UI is in scope.** Queue depth, pack size, who claimed what, lease age, last stage, stuck list. Reuse Review Center / Opportunities patterns. Do not invent a second shell.

## Three layers (keep them separate in the CR)

| Layer | Job | Existing code to extend, not fork |
|---|---|---|
| Ingest | Drop folder → parse → validate → quarantine bad rows → archive file → upsert opportunities | `scripts/import_csv_to_submissions.py`, `server/services/exportPendingReview.ts`, CR-091 skip ledger |
| Claim | Small packs, exclusive lease, heartbeat, expired lease is free | SQLite `jobagent.sqlite` (same DB as jobs). Postgres world's `SKIP LOCKED` idea, local SQLite shape |
| Resume | Per-folder `run_submission.py --resume` from last receipt | `scripts/run_submission.py`, `scripts/workflow/`, Review Center start/resume/status routes |

Token exhaustion is "drop the lease, leave the current job at last receipt." It is not "compact 30 jobs in one chat."

## What already exists (do not re-investigate)

- CSV import already writes `data/pending_review/{slug}/Original_JD.txt` and does URL / skip-ledger / existing-folder reuse. It **hardcodes** four Downloads paths, **prints** empty rows then continues, dumps **all** good rows into pending_review at once, and has **no** pack/lease. Archive copies under `scripts/archive/import_csv_*.py` are one-off. Do not revive them as the product.
- Scout already exports gate-passed DB rows to the same `pending_review/` tree (`exportPendingReview.ts`). Drop-folder ingest must not fight that path. Same destination, same skip ledger, extra source.
- Per-job resume already works. The hole is claiming and ingest, not Stage 0 internals.
- Review Center already shows paused Stage 0 items and can call `/api/run-submission/:scope/:slug/{start,resume,status,finalize}`. Pipeline visibility should sit next to that, not replace it.
- Stage 0 new-flow Tasks 1–2 are done. Evidence pipe on locked 30: 29 `ok`, 1 `skipped` (`unity`, no items). Jason marked `data/stage0_adjudication_5pass_evidence.csv`. Live leftover pkl hash stays `77b317467a6018a17e47b28fe3bda59a6901015945fc75d0f770dd04bc775913`. Adapter switch stays **off** until Task 3 after this CR.
- First real files to ingest after the CR lands (do not import them in this old one-shot way as the product):
  - `C:\Users\Jason\Downloads\applyr_jobs.csv`
  - `C:\Users\Jason\Downloads\applyr_jobs (1).csv`
  - `C:\Users\Jason\Downloads\applyr_jobs (2).csv`
  - `C:\Users\Jason\Downloads\applyr_jobs (3).csv`
  Header: `Company,Position,Job Description,URL,Networking Contacts`.

## External research (already done; cite, do not redo from scratch)

**Drop / quarantine**

- Inbox → raw land (immutable, content hash) → valid rows load, invalid rows quarantine with source file, line, raw payload, error code, replay status. File-level quarantine if the CSV is structurally broken; row-level if only some rows fail. Do not silently drop. [Elysiate quarantine tables](https://www.elysiate.com/blog/quarantine-tables-isolating-bad-csv-rows-without-losing-audits), [file landing / schema drift](https://dev.to/gowthampotureddi/sftp-edi-flat-file-ingestion-file-landing-schema-drift-late-partial-files-3fl), [ingest pipeline](https://narcismiclaus.com/programming/python/38-ingestion-pipeline/).
- Wait until the file is fully written (stable size, or drop-then-rename). Ledger on `(filename, sha256)` so the same Downloads file is not ingested twice.

**Claim / multi-worker**

- Short transaction to claim. Do not hold a DB lock while Stage 0 runs. Status `queued` → `leased` with `locked_by`, `lease_expires_at`, incrementing fencing token. Heartbeat. Expired lease is reclaimable. Stale owner writes must fail. [SKIP LOCKED queues](https://codenotes.tech/blog/postgresql-job-queues-with-skip-locked), [worklease checkpointed lease](https://github.com/aetomala/worklease/blob/main/docs/ARCHITECTURE.md).
- Bounded claim size is the production rule, not a nice-to-have.

**Resume / token death**

- Durable state lives outside the harness. Checkpoint at super-step / stage boundaries. Mid-step work rewinds. [Agent runtime sessions](https://slavadubrov.github.io/blog/2026/05/26/ai-agent-runtime/), [MS Agent Framework checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints), [LlamaIndex durable workflows](https://developers.llamaindex.ai/python/llamaagents/workflows/durable_workflows/). Applyr already has the stage-boundary store. Do not add a parallel checkpoint file format unless tech lead proves `workflow_state.json` cannot carry lease metadata.

## Recommended build shape (PM may tighten; do not expand)

**Phase A (must ship before Task 3)**

- Drop directory, e.g. `data/inbox/csv/` (gitignored contents). Subfolders `processing/`, `archive/`, `quarantine/` or equivalent table + moved files.
- Normalizer for the applyr_jobs schema. Required: company + JD text of usable length (exportPendingReview uses 200 chars; reuse or justify). URL optional but preferred. Dedup: URL, then company+title, then skip ledger.
- Persist opportunities + `queued` state in SQLite. Write `pending_review/{slug}/Original_JD.txt` the same way import already does.
- Claim API / CLI: `claim --size 8 --worker <harness-id>`. Heartbeat. Release. Expire.
- Worker loop: claim pack → for each job run existing `run_submission.py` (or start/resume API) → on token/abort, stop, release unstarted jobs, leave current job at last receipt.
- App page or Review Center section: counts by `queued / leased / in_progress / paused / done / quarantined`, current leases, stuck (lease expired or receipt stale), link into the existing job folder.

**Phase B (same CR if cheap, else follow-up)**

- Configurable pack size in Settings (never via hand-edit of prefs JSON).
- Quarantine replay: Jason fixes a row, it re-enters the queue.
- Scout export and CSV drop share one queue table so Today is not two lists.

**Out of scope**

- Leftover pkl promote.
- In-office / Aegon / ss_c skip-reason work (`stage0-backlog.md`).
- Stage 1 evidence-first CR-117 collision.
- Changing Stage 0 Agy adapter behavior.
- Auto-running Stage 0 inside the Node scout process.
- Multi-machine distributed queue. This is local SQLite, two harnesses on Jason's PC.
- Forcing 30-job batches "because the CSV has 30 rows."

## New session first moves (in order)

1. Read this file, `PLAN-2026-09-18-stage0-new-flow-ready.md` (Task 3 is blocked), `docs/ACTIVE_WORKFLOW.md`, `scripts/import_csv_to_submissions.py`, `server/services/exportPendingReview.ts`, Review Center run-submission routes.
2. Team pipeline: **product manager** locks problem, AC, out of scope, CR-worthiness (yes). Write `docs/spec/05-change-requests/CR-119-…`. Stop for Jason to approve the CR.
3. **Product designer** for the pipeline visibility surface (states, copy, reuse Review Center vs new nav item).
4. **Tech lead** reads real SQLite schema and workflow receipts, then writes epics/stories. Prefer one `pipeline_queue` (or similar) table over a pile of lock files. Justify if lock files win.
5. Implement story by story. Security reviewer on anything that writes `jobagent.sqlite`, inbox paths, or PII from JDs. QA marks stories. EM closes.
6. Prove with the four Downloads CSVs: drop them, see quarantine vs queued, claim one pack of 8, kill the worker, confirm another worker can claim the rest and `--resume` the half-finished job.
7. Only then return to PLAN Task 3 (tiny live batch, adapter on for that process only, leftover pkl unchanged).

## Hard limits (same as the frozen close-out)

- Do not push.
- Do not edit `data/candidate_preferences.json` directly.
- Do not manufacture gold.
- Do not run `scripts/_harvest_pass5_evidence.py` against the marked 5-PASS CSV (it wipes `your_mark`).
- Do not copy `data/stage0_classifier.candidate.pkl` over the live pkl.
- Do not set `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER` except inside PLAN Task 3 after this CR is done.
- Do not call CR-074 workers as an alternate sequencing path.
- Preserve unrelated dirty work in this repo.

## Success

Jason can drop CSVs, see bad rows parked, see a short queued pack, walk away when a harness dies, open another harness, pick up a job that is not leased, and see that state in the app without asking an agent to grep. Then, and only then, the 5–10 job Stage 0 live batch runs.
