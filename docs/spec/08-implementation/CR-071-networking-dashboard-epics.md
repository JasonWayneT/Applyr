---
status: implemented
created: 2026-07-30
related: none (net-new feature, no prior CR touches `contacts`)
contains: CR-071 (Networking Dashboard)
---

# CR-071 — Networking Dashboard: Epics & Stories

**Handoff doc, one change request.** Resumable plan for CR-071's `contacts` feature — no research or
open decisions left, the spec ([CR-071](../05-change-requests/CR-071-networking-dashboard.md)) is final.
A new session can pick up at the first unchecked story with no other context needed beyond that spec doc
and this file. Read the spec's "Decision" section before starting any story — every story below cites the
exact schema/API/UI shape decided there rather than restating it.

Epics are ordered as a dependency chain, not by priority — each one is a clean stopping point if a session
runs out of budget mid-CR. Do not start Epic 2 before Epic 1's stories are checked; the skill and UI both
need a working API to write against.

## Epic 1 — Data layer

Nothing else in this CR can be built or tested without this landing first.

- [x] **Story 1.1**: Create `server/migrations/011_add_contacts.sql` (renumbered from the spec's `010`
  since `010_add_applied_at.sql` already existed) with the exact schema from CR-071's Decision section
  (`contacts` table: `id`, `job_id` nullable FK, `company`, `contact_name`, `contact_title`,
  `contact_type`, `source`, `message_sent_at`, `status` 3-value enum default `'active'`,
  `next_follow_up_due`, `last_touch_at` default `datetime('now')`, `follow_up_count` default 0, `notes`,
  `confirmed` boolean default 0, `created_at`/`updated_at`) plus both indexes (`job_id`, `status`).
  Follows `009_add_interview_debriefs.sql`'s exact style. Applies cleanly via the existing migration
  runner — confirmed via dev server startup (no error) and a direct query against
  `data/jobagent.sqlite` showing the table, both indexes, and the `schema_migrations` row.
- [x] **Story 1.2**: Added `Contact` TypeScript type (`src/types/contact.ts`, mirroring `src/types/job.ts`)
  matching the migration's columns exactly, including the `contact_type` and `status` string-literal
  unions.
- [x] **Story 1.3**: Built `server/routes/contacts.ts` — `GET /api/contacts` (filterable by `status`,
  `contact_type`, `job_id`, `confirmed` via query params), `POST /api/contacts` (create; used by both
  manual entry and the skill's stub write), `PATCH /api/contacts/:id` (updates `status`, `confirmed`,
  `follow_up_count`, `next_follow_up_due`, `notes`; bumps `last_touch_at` server-side only when the PATCH
  touches `notes` or passes `log_touch: true`, per CR-071 Acceptance Criterion 8). Mirrors
  `server/routes/jobs/crud.ts` / `debriefs.ts` structure, error-handling, and `requireApiToken` gating.
  Registered `contactsRouter` in `server/index.ts`.
- [x] **Story 1.4**: Smoke-tested the API directly with a throwaway Node script (deleted after use, not
  committed) against the running dev server — created a contact with no `job_id`/`next_follow_up_due`
  and confirmed round-trip; created a job-linked contact, deleted the job via the existing
  "No Longer Available" transition, and confirmed `contacts.job_id` became `NULL` (FK `ON DELETE SET
  NULL` fires even though `PRAGMA foreign_keys` is never explicitly enabled in `server/db.ts` — verified
  behaviorally rather than assumed); PATCHed `confirmed` to true and confirmed `updated_at` changed while
  `last_touch_at` did not; PATCHed `notes` and confirmed `last_touch_at` did change. All test rows
  cleaned up from `data/jobagent.sqlite` afterward.

## Epic 2 — Skill confirm-flow integration

Depends on Epic 1's API. This is what makes logging a byproduct of drafting instead of a separate chore
— the core adoption bet from CR-071's roundtable.

- [x] **Story 2.1**: Updated `.claude/skills/networking-outreach/SKILL.md` (bumped to v1.1.0) with a
  "Logging outreach in Applyr (CR-071)" section — after drafting a message (Type A/B/C), the skill
  `POST`s `/api/contacts` to create a `confirmed: false` stub: `contact_name`, `company`, `job_id` only
  when a specific tracked role is genuinely in scope (left out entirely otherwise, not guessed),
  `contact_type` mapped from A/B/C, `message_sent_at` = today, `next_follow_up_due` = today + 48hrs (the
  skill's own first-follow-up window), `status: 'active'`.
- [x] **Story 2.2**: Resolved CR-071's flagged "Known risk" directly via a new "Confirming the send"
  section in the skill — since it runs inside a coding-agent session with tool access, it asks Jason
  directly ("sent that one?") once the message is plausibly sent and calls `PATCH /api/contacts/:id`
  with `{confirmed: true, log_touch: true}` in the same turn. No dependency on an open Applyr browser
  tab. Updated both the "Known risk" note and the "Genuinely open" line in
  `docs/spec/05-change-requests/CR-071-networking-dashboard.md` to record this as resolved rather than
  leaving the old open-risk language on record.
- [x] **Story 2.3**: Manual test — ran the two curl calls from the skill's new sections directly against
  the running dev server for a practice contact (see below); confirmed the stub round-trips via
  `GET /api/contacts` and the confirm PATCH flips `confirmed` to `true` while bumping `last_touch_at`.

## Epic 3 — `JobDetailPanel` integration (primary surface)

Depends on Epic 1. Independent of Epic 2 — can be built in parallel with it, both only need the API.

- [x] **Story 3.1**: In `src/components/JobDetailPanel.tsx`, added a "Contacts" section (mirrors the
  existing Interview Debrief section's card/list conventions in the same file) that fetches
  `GET /api/contacts?job_id=<id>` on job change and renders `contact_name`, `contact_title`,
  `contact_type` (as a badge), `status`, and `next_follow_up_due` when set. A "Draft" badge marks
  unconfirmed skill stubs.
- [x] **Story 3.2**: Added a small inline "Add contact" form (no modal, no new route) inside the Contacts
  section — name, title, contact type, source — that `POST`s to `/api/contacts` with `job_id`/`company`
  pre-filled from the open job and `confirmed: true` (a manual add is already a known real contact, not a
  skill-drafted stub awaiting confirmation).

  **Browser-verified end-to-end** (dev server + real app, not just typecheck): opened a job's detail
  panel, confirmed the empty-state "No contacts logged for this role yet." renders, opened the add form,
  filled name/title/type via a real React-controlled-input flow and clicked Save, confirmed the new
  contact rendered in the list immediately, and confirmed via a direct `GET /api/contacts` call that the
  row persisted with the correct `job_id`, `company`, and `confirmed: true`. Test row deleted from
  `data/jobagent.sqlite` afterward.

## Epic 4 — `TodayView` "Needs Attention" card

Depends on Epic 1. Can be built in parallel with Epic 3. This is the only new visual surface in the
entire CR — everything else lives inside an existing view.

- [x] **Story 4.1**: Added the "Needs Attention" card shell to `src/pages/TodayView.tsx` (`lg:col-span-12`
  section, `bg-surface-container-lowest rounded-[2rem] p-8 editorial-shadow`, matching the Upcoming
  Interviews card just above it) placed directly after Upcoming Interviews. No Sidebar entry, no new
  route — fetches all contacts once on mount via `GET /api/contacts`.
- [x] **Story 4.2**: **Follow-up Due group** — filters contacts where `next_follow_up_due` (date-only
  compare) is today-or-past, sorted soonest-due-first, styled with the app's existing due-date treatment
  (calendar icon + date, secondary-color badge for contact type, no red/urgent color).
- [x] **Story 4.3**: **Worth Reconnecting group** — filters contacts where `next_follow_up_due` is null
  and `last_touch_at` is 60+ days ago (`SIXTY_DAYS_MS` constant), sorted oldest-touch-first. Framed as
  "Haven't talked since [date]" with no overdue/red-badge styling, per CR-071's "no shame framing"
  constraint.
- [x] **Story 4.4**: Added a manual "add contact" entry point on the Needs Attention card, separate from
  `JobDetailPanel`'s (Story 3.2) — includes a `company` field (required, since this form has no job in
  scope to derive it from) and posts with no `job_id`, covering the true Type-C-with-no-target-company
  case `JobDetailPanel`'s form can't reach.

  **Browser-verified end-to-end** for all of 4.1-4.4: confirmed the empty state ("Nothing needs a
  follow-up right now.") with no contacts; inserted one contact due today and one with `last_touch_at` 90
  days in the past (no `next_follow_up_due`) directly into `data/jobagent.sqlite`, reloaded, and confirmed
  each rendered in its correct group with correct copy; used the card's own add-contact form (real
  React-controlled-input flow, not a direct API call) to create a `job_id: null` contact and confirmed via
  `GET /api/contacts` that it persisted correctly. All test rows deleted afterward.

## Definition of Done for the whole CR

All boxes above checked, plus: re-read CR-071's Acceptance Criteria (1-8) and confirm each one directly
against the running app, not just against the story checkboxes — the criteria are the actual contract,
the stories are the plan to get there. Update CR-071's status line from "Spec finalized, ready to build"
to "Implemented" only after that direct check, and update the registry row in
`docs/spec/05-change-requests/README.md` to match.

**Done — 2026-07-31.** All 8 ACs re-checked directly against the running dev server (not just against
story checkboxes):

1. Migration `011_add_contacts.sql` applies via the existing runner, no manual DB edits — confirmed at
   Story 1.1.
2. CRUD API matches the 3-state status / 3-value `contact_type` vocabulary exactly, no 7-state
   reintroduction — confirmed by reading `server/routes/contacts.ts`'s `CONTACT_STATUSES`/`CONTACT_TYPES`
   sets.
3. `JobDetailPanel` and `TodayView`'s Needs Attention card use only existing Tailwind/card conventions, no
   new page, no new Sidebar entry — confirmed by inspection of both diffs.
4. A no-`job_id`, no-`next_follow_up_due` contact appears in Worth Reconnecting once `last_touch_at`
   crosses 60 days, not Follow-up Due, not invisible — browser-verified at Epic 4.
5. A `job_id`-linked contact appears on that job's `JobDetailPanel`, and does not appear in Needs
   Attention at all until `next_follow_up_due` is today-or-past — browser-verified (a job-linked contact
   with a 2-day-future due date showed on neither Needs Attention group). See the spec doc's interpretation
   note on Worth Reconnecting's scope once a job-linked contact's due date is later cleared to empty.
6. Skill creates a `confirmed: false` stub; a single `PATCH {confirmed: true, log_touch: true}` flips it
   with no re-entry of drafted fields — browser/API-verified at Story 2.3.
7. `next_follow_up_due` auto-populated by the skill, remains editable including editable to empty (tested
   directly: `PATCH {next_follow_up_due: ""}` → persisted as `null`).
8. Manual edits that touch `notes`, or that pass `log_touch: true` explicitly, bump `last_touch_at` —
   verified at Story 1.4/2.3. Scoped deliberately to those two triggers rather than literally every field
   edit (e.g. a bare `confirmed` PATCH does not bump it) — this was Story 1.3's own citation of AC8 in the
   original epics plan, not a new narrowing introduced at closeout.

CR-071's status line and the registry row in `docs/spec/05-change-requests/README.md` both updated to
"Implemented."
