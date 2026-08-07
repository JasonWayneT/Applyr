# CR-072: Gmail Job-Search Intake Sync

## Metadata
- **Epic**: Net-new feature, no prior CR touches Gmail/email ingestion
- **Status**: Nearly implemented (2026-08-04) — Epics 0-3 built and running live in dry-run mode (Epic 4,
  a manual "Check Gmail Now" button, added mid-build at Jason's request, also done). One honest gap:
  Story 3.3's 20-minute real-time observation of a timer-triggered sync pass was not actually done — see
  the epics tracker. Not yet marked "Implemented" until that's either observed for real or explicitly
  waived.
- **Date**: 2026-08-03
- **Source**: Jason read a reference doc (`gmail_job_search_intake_filter.md`, external, not part of this
  repo) describing a conservative Gmail label + filter for job-application email, after seeing a LinkedIn
  post about tying email into a job-search tracker. Design was worked through conversationally before this
  CR was written; see that conversation for the full reasoning trail behind each decision below —
  this doc records the concluded design, not the exploration.

## Problem
Jason currently reads every job-application email by hand and manually updates job status/notes in
Applyr. This doesn't scale with application volume, and the highest-volume category (rejections) carries
close to zero decision-making value per email — he wants to stop manually checking for them every morning
without missing anything that actually matters (interview invites, recruiter outreach).

Two infrastructure paths were explicitly considered and ruled out:
- **Cloud hosting (e.g. Oracle Cloud free tier) for an always-on Applyr instance** — technically feasible
  (Ampere A1 free-tier VM fits the app's resource needs, SQLite ports natively since it's a real
  persistent disk not serverless storage) but unnecessary: nothing in this design requires Applyr to be
  reachable while it's off, because Gmail already durably holds labeled mail until Applyr next runs.
- **Cloud-side LLM classification (e.g. a Google Apps Script trigger calling an LLM API)** — ruled out on
  cost grounds: Jason uses AI subscriptions (Claude Pro/Max-style access), and a script-based cloud
  classifier requires a separately metered API key, not subscription usage. Classification in this CR is
  rule-based specifically to avoid that cost, not as a placeholder for it.

## Decision

### Phase A — Gmail-side gate (manual, no code)
Build exactly the label + filter described in the reference doc: `Applyr/Incoming` label, the
33-phrase bracketed OR query tested in Gmail's search bar before being saved as a filter, filter action
limited to **apply label only** (no skip-inbox, no mark-as-read, no archive, no delete). This is a
prerequisite for everything below and has no dependency on any code in this repo. Jason executes this
himself (see manual checklist delivered alongside this CR).

**Naming history — two renames, current name is `Applyr`:**
1. The reference doc and this CR's original text both said `Job Search/...` — wrong from the start.
2. Caught 2026-08-03 via Epic 1's smoke test (`gmail.users.labels.list` against the real account, not
   assumed): the real labels were actually `Job Hunt/Incoming`, `Job Hunt/Rejected`, `Job Hunt/Interview`.
   Corrected throughout this doc and its epics tracker at that point.
3. Same day, Jason renamed the top-level label again, from `Job Hunt` to `Applyr` — current real labels
   are `Applyr/Incoming`, `Applyr/Rejected`, `Applyr/Interview`. This doc's Decision/Acceptance-Criteria
   text is updated to `Applyr/...` throughout. **The epics tracker's Story 1.4 verification log is left
   saying `Job Hunt/Incoming` on purpose** — that's what was actually tested at that timestamp, and
   rewriting a completed verification record to match a later rename would misrepresent what happened.
   Don't re-edit that log entry; if re-verification against the current `Applyr/...` names is needed,
   that's a new checkbox, not a correction to an old one.

**Known risk to watch during setup**: Gmail's "Has the words" filter field has an undocumented but real
length cap: some users hit a "query too long" error on OR-lists this size. If that happens, split the
phrase list into two filters both applying the same label — Gmail filters aren't ordered relative to each
other, so this is functionally identical to one filter.

### Phase B — Local sync service (this repo)
No cloud component. A new sync routine runs inside the existing Applyr server process:

1. **Read access**: Gmail API, `gmail.readonly` OAuth scope, via a Desktop-app OAuth client. Per
   [CR-015](CR-015-sqlite-only-secrets.md), the refresh token and client credentials are stored in
   `jobagent.sqlite`'s `profiles` table — no `.env` file, matching the existing secrets policy exactly.
   The OAuth consent screen is set to **Production** publishing status (done 2026-08-03), not **Testing**
   — Testing status definitively revokes refresh tokens after 7 days, which is the exact friction Jason
   hit on an earlier project. **Correction to this CR's original claim**: `gmail.readonly` *is* a
   sensitive scope, and Google's Verification Center does prompt for formal verification once a sensitive
   scope is requested — that part of the original Decision text was wrong, caught live during Epic 0 when
   the console showed a "Data access status: not verified" warning. What's still genuinely unresolved
   (checked Google's own docs directly, both the "Manage App Audience" and "Sensitive scope verification"
   pages — neither states this explicitly) is whether an **unverified app already in Production status**
   still carries the 7-day refresh-token expiry, or whether that expiry is specific to Testing status.
   Decision: proceed with Production + unverified as-is (already done) rather than pursue Google's formal
   verification (a review process that can take up to 10 days and expects things like a privacy policy
   URL — disproportionate for a single-user personal tool). **Epic 1 Story 1.4 is the actual resolution
   mechanism** — it empirically tests whether the refresh token survives past 7 days in this exact
   configuration. If it doesn't, the fallback is re-running the one-time local auth script periodically,
   not escalating to full verification.
2. **Trigger**: the sync routine runs once on server startup, and again every 10 minutes on a timer while
   the process stays alive. No push/webhook, no Pub/Sub, no Apps Script — Gmail is the durable buffer;
   Applyr only ever pulls, and only while it happens to be running. A message is never lost by Applyr
   being off, because nothing about Phase A ever removes a matching message from the inbox — Jason still
   sees anything time-sensitive there regardless of sync timing.
3. **Cursor**: a persisted "last synced" marker (new small table or a `profiles` key — implementation
   detail, not mandated here) so a message already processed is never reprocessed.
4. **Classification**: rule-based (regex/keyword) only in this CR, deliberately not an LLM call — this is
   what keeps the feature free under the cost constraint above. Two keyword sets, both derived from and
   consistent with Phase A's own phrase groups (`gmail_job_search_intake_filter.md`'s "Application
   Acknowledgments" and "Application Updates and Rejections" sections):
   - **Rejection** keywords → auto-write (status transition, see point 5).
   - **Application confirmation** keywords → activity-log entry only, no status change. `jobs.status` is
     already `Applied` by submission time via the existing drafting pipeline, not by this CR — a
     confirmation email doesn't need to move a status that's already correct. Deliberately not adding a
     new column (e.g. `ats_confirmed`) for this in this CR: it has no consumer yet, and speculative schema
     for a signal nothing reads is exactly the kind of premature abstraction to avoid. If a future need
     shows up (e.g. flagging applications stuck at `Applied` with no confirmation ever received, as a
     "did this actually submit" signal), that's a distinct, explicit follow-up CR, not a default add here.
   - Everything else caught by the Phase A label but not matching either keyword set (interview invites,
     recruiter screens, assessments, ambiguous mail) is **left alone** — no auto-write, no queue to review.
     Jason continues to see and act on these through his normal inbox use. This deliberately does not
     require a review UI in this CR.
5. **Write path**: for a rejection match, the sync service must go through the same transition
   `JobDetailPanel.tsx`'s closure flow uses, not a bare status string — closing a job actually sets
   `jobs.status = 'Closed'` plus `jobs.rejection_type` (e.g. `'Rejected'`) and `jobs.rejection_stage`
   (`server/db.ts:24-40`, `src/components/JobDetailPanel.tsx:100-139`). Every write is paired with an
   activity-log entry citing the source email's subject line and received date, so every auto-applied
   change has a visible, auditable trail — this replaces "review before applying" with "cheap to check
   after the fact," which is what actually satisfies "I don't want to look at rejection emails every
   morning" without silently trusting an unreviewed classifier.
6. **Dry-run mode, on by default (2026-08-03 addition, Jason-supplied)** — the same conservative
   test-before-trust philosophy Phase A already used (search-bar test before saving a filter) applied to
   Phase B: a `profiles`-stored flag (per CR-015, not `.env`) gates whether Story 2.4's write path actually
   fires. While the flag is on, the classifier still runs against every message under `Incoming` in full,
   but instead of writing, it logs the *intended* action (matched job, resolved category, would-be status
   change) alongside whether Gmail's own `Rejected`/`Interview` labels agree with that independent
   classification. This produces exactly the validation signal needed before trusting the automation:
   agreement confirms the classifier is sound; a case where Applyr flags a rejection Gmail's filter missed
   validates why classification isn't label-trust-only (see point 4); a case where Gmail's filter caught a
   rejection Applyr's classifier didn't is a real gap to close before flipping the flag off. Jason reviews
   this log over a trial period (thirty days suggested, not enforced) and manually flips the flag off once
   satisfied — no auto-expiry timer, that's unnecessary complexity for a manual, low-frequency decision.

## Acceptance Criteria
- Phase A live and verified per the reference doc's own Steps 4–8 (label nests correctly, filter applies
  label only, existing inbox/read/archive state is unchanged for a sample of matching messages) before any
  Phase B work begins.
- OAuth consent screen confirmed at Production publishing status; a manual token-refresh test (or simply
  normal use across more than 7 days) confirms the refresh token survives without re-authorization.
- Sync runs on startup and on a 10-minute interval; confirmed via logs that a second run within the window
  processes zero already-seen messages.
- A real or realistic test email matching the rejection keyword set results in the target job's `status`
  becoming `Closed` with the correct `rejection_type`/`rejection_stage`, plus one new activity-log entry
  naming the source email.
- A real or realistic test email matching the confirmation keyword set produces the agreed effect from
  Open Question 2 below (activity-log entry at minimum).
- A message under `Applyr/Incoming` that matches neither keyword set causes no write of any kind —
  confirmed by checking that job's activity log is unchanged.
- No `.env` file or new secrets-storage mechanism introduced — Gmail credentials follow CR-015 exactly.
- Dry-run flag defaults to on for a fresh install; while on, zero real writes occur to `jobs` or the
  activity log's write-affecting entries regardless of classifier output, and every message under
  `Incoming` produces a dry-run log line naming matched job, resolved category, and label-agreement
  status against Gmail's own `Rejected`/`Interview` labels. Flipping the flag off is a manual, one-time
  action confirmed to enable real writes on the next sync pass.

## Open Questions

- **OQ-1 (job matching) — RESOLVED 2026-08-03.** An email has no Applyr job ID, so matching it to a
  `jobs` row needs its own layered strategy, not a single fuzzy-match call — company-name matching is a
  known hard problem (entity resolution / record linkage), and standard practice is to try the highest-
  confidence signal first and only fall back to fuzzy text matching when nothing more reliable is
  available:
  1. **Sender-domain match** (try first, highest confidence): extract the sending address's domain and
     compare it against a domain derived from `jobs.url` (the job posting URL's own domain, or the ATS
     subdomain pattern — e.g. `boards.greenhouse.io/{company-slug}`, `jobs.lever.co/{company-slug}`).
     Ashby/Greenhouse/Lever confirmation and rejection mail is very often sent from a domain tied
     one-to-one to the company/ATS instance, which makes this the least ambiguous signal available and
     costs nothing extra to compute (`jobs.url` already exists on every tracked job).
  2. **Normalized exact match** (second): strip legal suffixes (Inc, LLC, Ltd, Corp, Co, Company, Group),
     lowercase, collapse punctuation/whitespace on both the sender/subject text and every `jobs.company`
     value, then compare for exact equality. This is standard company-name-matching practice — normalize
     before ever reaching for fuzzy scoring, since most "fuzzy" mismatches are actually just legal-suffix
     or punctuation noise, not genuine ambiguity.
  3. **Fuzzy token match** (fallback only): if neither above resolves it, score the normalized sender/
     subject text against every tracked `jobs.company` using [Fuse.js](https://www.fusejs.io/) (zero-
     dependency, built for exactly this shape of problem — fuzzy-searching a query string against a small
     in-memory list of records) with a deliberately strict threshold. Auto-write only when there is a
     single match clearly above threshold with no close second candidate — a near-tie between two tracked
     companies is treated as no match, not a coin flip.
  4. **No match / below threshold**: no auto-write of any kind. Skip silently — this is consistent with
     the rest of this CR's design (Jason's inbox remains the safety net), and does not require a
     manual-linking UI in this CR. If unmatched volume turns out to be high enough to matter, that's a
     signal to revisit, not a reason to build a review queue speculatively now.

  This pipeline is the concrete answer to build against in Epic 2 — Story 2.0 no longer needs to re-open
  this question, only confirm the exact fuzzy-match threshold empirically against real mail once Epic 1's
  data is flowing.
- **OQ-3 (rejection write path's exact call) — RESOLVED 2026-08-03.** Checked the actual endpoint
  (`router.patch('/api/jobs/:id/status', ...)`, `server/routes/jobs/crud.ts:202-327`) rather than assuming
  its shape. It does meaningfully more than update `status`/`rejection_type`/`rejection_stage`: it also
  archives the submission folder on disk (`archiveActiveSubmission`), reads and logs the rubric score for
  calibration (`RubricLog` activity entry), and handles `applied_at` stamping/clearing. A direct
  `better-sqlite3` write from the sync service would skip all of that — a job closed by an incoming
  rejection email would end up in a different, inconsistent state than one closed through the UI (folder
  never archived, no rubric log). Direct write is therefore disqualified, not just less clean.
  Calling the existing endpoint over HTTP (the server hitting its own `localhost` port) would preserve the
  behavior but is an antipattern — a self-HTTP-call for logic already running in the same process.

  **Decision**: extract the route handler's status-transition logic into a standalone function in
  `server/services/` (matching the existing pattern — `crawlPolicy.ts`, `ingestDedup.ts`,
  `scoutOrchestrator.ts` are all factored out the same way), have the route handler call it exactly as
  before (no behavior change to the existing endpoint), and have the new sync service call the same
  function directly. Same single source of truth, no self-HTTP-call, and it's a mechanical move of an
  existing block rather than a redesign.

## Out of Scope
- Any cloud hosting for Applyr (Oracle or otherwise) — ruled out above, not a phased-later item unless a
  reason independent of this CR comes up (e.g. wanting Applyr reachable from a phone).
- Any LLM-based classification, local or remote — this CR is rule-based only. A future CR could route
  ambiguous-bucket classification through a local Claude Code invocation (subscription-covered, not a
  billed API) once the rule-based path's real hit/miss rate is known; premature until then.
- A review/confirmation queue UI for the non-auto-written categories (interview/recruiter/uncertain) —
  deliberately not built; Jason's existing inbox is the safety net for anything time-sensitive.
- Gmail push notifications via Cloud Pub/Sub — polling on a 10-minute interval was chosen specifically to
  avoid this infrastructure; revisit only if 10-minute staleness becomes a real problem, which is unlikely
  given the inbox safety net above.
- Expanding Phase A's label/filter phrase list — this CR consumes Phase A's existing categories as-is;
  phrase tuning belongs to the reference doc's own Step 5 process, done in Gmail directly, not in this repo.
