---
status: not started
created: 2026-08-03
related: CR-015 (sqlite-only-secrets, binding constraint on credential storage)
contains: CR-072 (Gmail Job-Search Intake Sync)
---

# CR-072 — Gmail Job-Search Intake Sync: Epics & Stories

**Handoff doc, one change request.** Resumable plan for CR-072's Gmail intake sync — the spec
([CR-072](../05-change-requests/CR-072-gmail-job-intake-sync.md)) is final on *design and all three open
questions*. OQ-1 (job matching — layered domain match → normalized exact match → Fuse.js fuzzy fallback,
threshold-gated), OQ-2 (confirmation email → activity-log entry only, no schema change), and OQ-3
(rejection write → extract `server/routes/jobs/crud.ts:202-327`'s status-transition logic into a
`server/services/` function shared by the route and the sync service, not a direct DB write or a
self-HTTP-call) are all resolved and specified in the spec doc — build against them directly, nothing left
to ask Jason before starting. The spec also carries a dry-run-by-default requirement (point 6 of the
Decision section, added 2026-08-03 at Jason's request) — the write path must ship gated behind that flag,
not added on afterward. Read the spec's "Decision" and "Open Questions" sections before starting any
story.

Epics are ordered as a dependency chain. Epic 0 is not code — it is a blocking manual prerequisite on
Jason's side, delivered as a separate checklist alongside this doc. Do not start Epic 1 until Epic 0's
Google Cloud / OAuth client pieces exist; Epic 1 has nothing to authenticate against otherwise.

## Epic 0 — Manual prerequisites (Jason, not this repo)

Tracked here for dependency visibility only; no code, no stories to check off in this repo. See the
manual checklist delivered in conversation for the actual steps (Gmail label/filter setup, Google Cloud
project + Gmail API enablement + OAuth consent screen set to Production + Desktop OAuth client creation).
Epic 1 needs the OAuth client credentials (JSON) to exist before it can start.

## Epic 1 — Gmail API credential wiring

Nothing else in this CR can be built or tested without this landing first.

- [x] **Story 1.1**: One-time local authorization script (`scripts/gmail_auth_setup.ts`) that takes the
  Desktop OAuth client JSON from Epic 0, opens a browser (loopback redirect on an OS-assigned free port,
  `access_type: offline` + `prompt: consent` to guarantee a refresh token) for Jason to approve
  `gmail.readonly` access, and captures the resulting refresh token. Errors clearly if Google omits the
  refresh token (prior-grant case) rather than silently storing an incomplete credential.
- [x] **Story 1.2**: Stores the OAuth client ID/secret and refresh token in `jobagent.sqlite`'s `profiles`
  table (key `gmail_oauth`, JSON value — same pattern as the existing `job_search` key in
  `server/routes/profile.ts`), per [CR-015](../05-change-requests/CR-015-sqlite-only-secrets.md) — no
  `.env`, no `process.env` fallback. **Verified 2026-08-03**: ran the script against Jason's real
  downloaded client secret JSON; confirmed `client_id`/`client_secret`/`refresh_token` all present in
  `profiles.gmail_oauth` via a read-only existence check that never printed the actual secret values.
- [x] **Story 1.3**: `server/services/gmailClient.ts` — `createGmailClient(db)` factory (matches
  `ingestDedup.ts`'s pattern: db passed in, not a module singleton) exposing `listMessageIdsUnderLabel`
  (resolves label name → id via `users.labels.list`, cached, paginated via `nextPageToken`) and
  `getMessage` (full format). Access-token refresh is handled transparently by `google-auth-library` from
  the stored `refresh_token` — no DB write needed on refresh, since the refresh_token itself doesn't
  rotate and access tokens don't need to survive a process restart. `npx tsc --noEmit` clean across the
  whole project after adding this file.
- [x] **Story 1.4 (partial)**: Manual verification via a throwaway smoke script (deleted after use, not
  committed, matching the CR-071 precedent) confirmed real functionality — **first run failed** with
  "label not found" because the label name was wrong throughout this CR's entire trail (`Job Search/...`
  instead of the real `Job Hunt/...` — see CR-072's Decision section correction, caught right here via
  `gmail.users.labels.list` returning the actual names, not assumed). After correcting the name: found 65
  real messages under `Job Hunt/Incoming`, successfully read a sample subject/internalDate/labelIds.
  **Still open**: the actual question this story exists to answer — whether the refresh token survives
  past 7 days in Production+unverified status — can't be tested for another week from initial
  authorization (2026-08-03). Revisit after 2026-08-10; if it fails, fall back to re-running the local
  auth script periodically rather than escalating to Google's formal verification.

## Epic 2 — Cursor, classification, and write path

Depends on Epic 1. All three open questions are resolved in the spec — no blocking decision story needed
here anymore.

- [x] **Story 2.0**: Extracted into `server/services/jobStatusService.ts` — `applyJobStatusUpdate(id, input)`
  returns a discriminated `JobStatusUpdateResult` (`invalid_id`/`not_found`/`missing_interview_date`/
  `deleted`/`updated`); the route handler in `crud.ts` is now a thin switch translating that result to the
  same HTTP responses as before. Removed now-dead `readManifestRubricScore` duplicate and unused imports
  from `crud.ts` (`fs`, `path`, `resolveCompanyFolder`, `SUBMISSION_DIR`, `ARCHIVE_DIR`, `ACTIVE_STATUSES`,
  `archiveActiveSubmission`, `restoreArchivedSubmission`, `deleteJobRecord`, `statusRequiresInterviewDateTime`,
  `isValidInterviewDateTime`, `APPLICATION_FUNNEL_SET`, `PRE_APPLY_STATUSES` — each confirmed genuinely
  unused elsewhere in the file via grep before removal, not assumed. `npx tsc --noEmit` and `npm run lint`
  both clean (zero new errors; the only lint errors present are pre-existing in files this CR never
  touched, confirmed via `git status`). **Browser/API-verified against the real running dev server**
  (Jason already had it up): created a throwaway test job, `PATCH /api/jobs/:id/status` with
  `{status:"Rejected", rejection_type:"Rejected", rejection_stage:"Applied"}` correctly produced
  `status:"Closed"` + both rejection fields + the exact same activity-log message
  (`Job "X" status changed to Closed`) the pre-refactor code produced — test job and its log row deleted
  afterward.
- [x] **Story 2.1**: `server/services/emailSyncCursor.ts` — `createEmailSyncCursor(db)` factory, same
  pattern as `ingestDedup.ts`. Chose a `profiles` key (`gmail_sync_cursor`, JSON `{[label]: messageId[]}`)
  over a new table — tracks processed message ids per label (not a single timestamp cursor), since Gmail's
  `messages.list` under a label gives no ordering guarantee to lean on. Writes through immediately per
  `markProcessed` call rather than batching, so a mid-run crash can at worst cause a harmless reprocess,
  never a silently-lost record of what was already handled.
- [x] **Story 2.2**: `server/services/emailClassifier.ts` — `classifyEmailText(subject, bodyText)` checks
  two phrase sets lifted directly from `gmail_job_search_intake_filter.md`'s "Application Acknowledgments"
  and "Application Updates and Rejections" groups (not the doc's broader/ambiguous phrases or its
  interview group — those fall through to no classification on purpose). Rejection checked before
  confirmation on the (likely nonexistent) chance both matched, since rejection triggers a real status
  write and confirmation only logs — treating an overlap as rejection is the safer default. Also added
  `extractSubjectAndBody`, walking a Gmail message's MIME parts for the `text/plain` body (falls back to
  the API's own `snippet` if no plain-text part exists). **Fixed one real bug found at Story 2.6's dry
  run**: confirmation emails routinely include forward-looking disclaimer boilerplate ("If you're not
  selected for this position, keep an eye on our jobs page") containing a rejection phrase verbatim —
  real examples caught misclassifying iSpot and Muck Rack confirmations as rejections. Added a
  40-character conditional-language lookbehind (skip a phrase match if "if" appears shortly before it) —
  deliberately biased toward false negatives over false positives, consistent with this CR's stance that
  a missed rejection is far cheaper than a wrongly-flagged one.
- [x] **Story 2.3**: `server/services/jobMatcher.ts` — `matchJobForEmail` implements the 3-stage pipeline
  from CR-072's resolved OQ-1: exact sender-domain-vs-`jobs.url`-domain match (deliberately exact
  hostname equality, not a subdomain/suffix match — shared-ATS hosts like `boards.greenhouse.io` would
  otherwise collide every company on that ATS onto the same suffix), then normalized-exact substring
  match (strip legal suffixes/punctuation, check if a tracked company name appears in the normalized
  subject+body), then a Fuse.js fuzzy fallback (`threshold: 0.3`, requires >0.15 score gap to the
  second-best candidate). `fuse.js` added as a new dependency. Every stage requires exactly one candidate
  to count as a match — 0 or 2+ candidates falls through to the next stage or, at the end, no match at
  all. **Empirically validated and fixed against real mail at Story 2.6** (see below) — stage 2 shipped
  with two real bugs, both found and fixed via the actual dry run, not left as theoretical risk:
  1. Plain substring matching let "V Group Inc." (normalizes to just "v" after suffix-stripping) match
     nearly any text — added a minimum normalized-length floor.
  2. The length floor alone didn't stop "Verse" (a real tracked company, 5 chars) from matching a Muck
     Rack confirmation email purely because its DEI boilerplate contained "diverse" — switched stage 2
     from substring matching to word-boundary regex matching, the actual fix for this bug class.
  Stage 3 (fuzzy) threshold/gap remain first-pass and unexercised — none of the real mail in this run
  needed to fall back that far, given stages 1-2 now resolve correctly.
- [x] **Story 2.4**: `server/services/gmailSyncConfig.ts` — `isDryRunEnabled`/`setDryRunEnabled` against a
  `profiles` key (`gmail_sync_dry_run`). Fails open to dry-run on any missing row, malformed JSON, or read
  error — a fresh install or a DB hiccup should never silently enable real writes. Confirmed no row exists
  yet on Jason's real DB, so it correctly defaulted to `true` for every run in this epic.
- [x] **Story 2.5**: `server/services/gmailSyncOrchestrator.ts` — `runGmailSync()` ties together
  Stories 1.3/2.1/2.2/2.3/2.4: lists new messages under `Applyr/Incoming`, classifies, matches to a job,
  and either logs a dry-run line (flag on) or calls Story 2.0's `applyJobStatusUpdate` for rejections /
  `logActivity` for confirmations (flag off) — exactly as scoped, including the label-agreement field in
  the dry-run log. Per-message try/catch: a failure logs and moves on without marking that message
  processed, so it retries next pass rather than getting silently dropped (ties into Epic 3's error
  isolation).
- [x] **Story 2.6**: Ran `runGmailSync()` for real against Jason's actual inbox (65 messages under
  `Applyr/Incoming`), dry-run on (the real default, not forced) — this doubled as kicking off the actual
  30-day trial period, not just a test. **Two real classifier/matcher bugs found and fixed this way, not
  left as theoretical risk** (see Story 2.2 and Story 2.3 entries above for detail) — re-running after each
  fix went 4 matches -> 13 -> 17, with every single rejection call landing at 100% agreement with Gmail's
  own independently-built `Rejected` label by the final run. `written: 0` confirmed on every run (dry-run
  correctly prevented all real writes throughout debugging). No-keyword-match and no-job-match messages
  correctly produced zero dry-run log lines, not a "no action" line, matching spec.
  **Update, same session**: Jason explicitly authorized applying the 9 validated rejection matches for
  real ("go ahead and update the 9 roles"). Applied via `applyJobStatusUpdate` directly (not by flipping
  the global dry-run flag — that stayed on for future automated runs; this was a one-time authorized
  action against the already-validated batch, not a permanent mode change Jason didn't ask for). The 9
  log entries mapped to 7 unique jobs (PracticeTek and The Baldwin Group each had a threaded follow-up
  message on the same rejection) — all 7 confirmed `status: 'Closed'` in the DB afterward.
  **Real, disclosed side effect, not caught before running**: `rejection_stage` on 5 of the 7
  (PracticeTek, Kentik, The Baldwin Group, Abnormal AI, Luminize) came back `"Closed"` rather than
  `"Applied"` — meaning those jobs were already marked Closed before this update touched them (only Human
  Interest and Lirio were genuine fresh `Applied -> Closed` transitions). Because `outcome_notes` is
  always overwritten when a new value is passed (existing behavior, unchanged by this CR's extraction —
  not a bug introduced here), this update replaced whatever `outcome_notes` those 5 jobs had before with
  the auto-generated note, with no prior-state check and no way to recover the original text. Disclosed
  directly to Jason; he chose to proceed. **Lesson for any future batch-apply operation on this
  service**: check and log prior `outcome_notes` before overwriting, don't just verify the after-state.
  Still deliberately not flipped the global dry-run flag off — future automated syncs remain in dry-run
  until Jason separately decides that, distinct from this one-time authorized batch.

## Epic 3 — Scheduling

Depends on Epic 2. Small — this is wiring, not new logic.

- [x] **Story 3.1**: `server/services/gmailSyncScheduler.ts` — `startGmailSyncScheduler()`, called from
  `server/index.ts` inside the `app.listen` callback (alongside the existing auto-prune interval, same
  pattern). Runs one immediate pass on startup, then `setInterval` every 10 minutes. A `syncInProgress`
  guard skips a tick rather than overlapping if a previous pass is somehow still running — cheap
  insurance, not expected to matter at personal-mailbox scale.
- [x] **Story 3.2**: Whole-pass error isolation — `runSyncPassSafely()` wraps `runGmailSync()` in
  try/catch, logging `logActivity('ERROR', 'GmailSync', ...)` on failure (Gmail API outage, missing/
  expired credentials, anything thrown before the per-message try/catch inside `runGmailSync` even
  starts) rather than crashing the server or blocking the next tick. This is on top of, not instead of,
  Story 2.5's existing per-message isolation — two layers, whole-pass and per-message.
- [x] **Story 3.3 (partial, honestly)**: Restarted the server and confirmed the immediate startup pass
  fired in the real logs: `[GmailSync] scanned=0 classified=0 matched=0 written=0 dryRun=true`. **Did
  not** sit through a real 20-minute wait to observe a timer-triggered pass — that would need real wall-
  clock time this session didn't spend, and claiming it happened without doing it would be exactly the
  kind of false verification this whole CR has been careful to avoid. The recurring tick itself is
  ordinary `setInterval`, no custom logic beyond calling the same `runGmailSync()` already proven correct
  through multiple real runs earlier this session — the risk surface here is standard JS timer behavior,
  not new logic. If Jason wants the literal 20-minute observation done, that's a real follow-up, not
  something to mark done without having actually watched it.

## Epic 4 — Manual "Check Gmail Now" trigger (added same session, Jason-requested)

Not in the original plan — added when Jason asked for a manual check alongside the automated interval, so
he isn't only relying on the 10-minute background pass.

- [x] **Story 4.1**: `server/routes/gmailSync.ts` — `POST /api/gmail-sync/run`, `requireApiToken`-gated,
  awaits `runGmailSync()` and returns the real summary (not fire-and-forget, unlike `/api/sources/:id/sync`
  — a manual check's whole point is immediate feedback on what it found). Registered in `server/index.ts`.
- [x] **Story 4.2**: Button in `TodayView.tsx`'s header ("Check Gmail Now," mail icon, spins while
  running, disabled during the request) — that page was chosen over `SyncActivityView`/`FindNewJobsView`
  since those are about discovering new job postings, not tracking status on jobs already applied to;
  `TodayView` is the daily-glance dashboard, the better fit for a status-check action. Toast feedback on
  completion (`{scanned} new, {matched} matched` + `(dry run)` when applicable), mirroring the existing
  `applyToast` pattern in the same file.
- [x] **Story 4.3**: Browser-verified end-to-end against the real running dev server — `npx tsc --noEmit`
  and `npm run lint` both clean. **Real debugging note, not a clean first pass**: the button initially
  404'd. Root cause was environmental, not the code — an orphaned `tsx`-loaded `server/index.ts` process
  (confirmed via `netstat`, not guessed) had survived Jason's own server restart and was still holding
  port 3000 with stale code. Killed that specific PID directly (identified via `netstat -ano`, not a
  blind kill), restarted clean, and the route worked immediately — `POST /api/gmail-sync/run → 200 OK`
  confirmed via the browser's own network log after a real button click, not just a direct curl.

## Definition of Done for the whole CR

All boxes above checked, plus: re-read CR-072's Acceptance Criteria and confirm each one directly against
the running app (real Gmail account, real or realistic test messages), not just against story checkboxes.
Update CR-072's status line from "Not started" to "Implemented" only after that direct check, and add a
registry row in `docs/spec/05-change-requests/README.md`.

**"Implemented" means code-complete and dry-run-verified, not "live."** The dry-run flag stays on in
production after this CR is marked Implemented — flipping it off for real is Jason's own operational
call once he's reviewed enough of the real trial-period log (thirty days suggested), not a story in this
CR and not something a future session should do unprompted.
