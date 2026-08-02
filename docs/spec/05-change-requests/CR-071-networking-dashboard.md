# CR-071: Networking Dashboard

## Metadata
- **Status**: Implemented (2026-07-31). All 4 epics complete — see
  [CR-071-networking-dashboard-epics.md](../08-implementation/CR-071-networking-dashboard-epics.md) for the
  full build log and per-story browser verification. All 8 Acceptance Criteria below re-checked directly
  against the running app as part of closeout, not just against story checkboxes. One interpretation note
  worth recording: the Worth Reconnecting group's query (`next_follow_up_due IS NULL AND last_touch_at`
  60+ days stale) does **not** exclude job-linked contacts — a job-linked contact whose follow-up gets
  cleared to empty (the AC7 "active thread → maintained relationship" mechanism) can later surface in
  Worth Reconnecting once stale. AC5's phrasing ("only additionally appears... if next_follow_up_due is
  today-or-past") reads more strictly than that at first glance, but excluding job-linked contacts from
  Worth Reconnecting would break the AC7 mechanism for exactly that case, so the query was left matching
  the Decision section's literal definition rather than narrowed to satisfy AC5's stricter-sounding text.
  Flagging in case this wasn't the intended reading.
- **Date**: 2026-07-30
- **Source**: Direct request ("let's spec out a network dashboard in applyr"), following a same-day session that built `.claude/skills/networking-outreach/SKILL.md` (message-drafting playbook for hiring-manager and warm-connection outreach) and researched why cold applications underperform networking (Ashby: referrals ~1% of applications but 40% reach interview). Jason explicitly rejected a bigger standalone "networking coach" project earlier the same session in favor of a lightweight tracking addition to Applyr's existing DB — this CR is that addition.
- **Revision note (same day):** the original draft below (5-section standalone `NetworkView`, 7-state status enum) was rejected after a BMAD roundtable stress-tested it against real UX-abandonment research and Jason's explicit worry ("designed for use so we can dogfood it," not just functional completeness). Sally (UX) and Winston (Architect) independently converged on cutting the standalone page; John (PM) then caught two real gaps in that convergence — silent auto-logging removes the "ownership moment" that may matter for habit formation, and job-panel-only quietly drops Type C (informational-interview) contacts, which have no `job_id` by construction. Mary (Analyst) synthesized the final shape below. Full roundtable transcript available on request; this doc reflects the outcome, not the process.
- **Second revision note (same day, Jason-caught gap):** the synthesis above named Sally's "warm/cooling/cold, soft resurfacing" idea for long-term relationship maintenance but never actually built it — the Needs Attention card as first written only distinguished job-linked from not, not active-thread from maintained-relationship. Jason pushed directly: "building a network before you need it" (meeting people at a company with no role open yet, no active ask, just staying in each other's orbit) had nowhere to live that wouldn't either clutter Needs Attention forever or get marked `closed` just to silence it. Fixed below by adding `last_touch_at` and splitting Needs Attention into two groups instead of one.

## Problem

Applyr tracks the full job-application lifecycle (`jobs` table, `TodayView`/`AllJobsView`) but has zero visibility into networking activity — the higher-leverage channel per the same-day research. There is no record of who Jason has reached out to, what type of contact they are (hiring manager vs. warm/alum connection vs. informational-interview target — the three types the `networking-outreach` skill already distinguishes), whether a follow-up is due, or how outreach volume compares to a real cadence. "Blind applications isn't working" is a volume/consistency problem the app currently can't even measure, let alone surface.

## Decision

The guiding test the roundtable landed on for every piece of scope: **does this field or surface change what Jason does, or does it just describe what he already did?** Record-keeping lost to behavior-driving on every contested point below.

### Data model — new table `contacts`

Follows the existing `interview_debriefs` migration pattern (`server/migrations/009_add_interview_debriefs.sql`) — TEXT primary key, TEXT timestamps via `datetime('now')`, indexed FK. `job_id` is **nullable** — a Type C informational-interview contact often has no open role yet, only a company — and that nullability is load-bearing, not incidental: it's what the roundtable's Type C fix (below) depends on.

```sql
CREATE TABLE IF NOT EXISTS contacts (
  id TEXT PRIMARY KEY,
  job_id TEXT,                          -- nullable, no role open yet is a valid case (Type C)
  company TEXT NOT NULL,
  contact_name TEXT NOT NULL,
  contact_title TEXT,
  contact_type TEXT NOT NULL,           -- 'hiring_manager' | 'warm_connection' | 'informational'
  source TEXT,                          -- 'LinkedIn alum', 'mutual connection', 'cold search', etc.
  message_sent_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active', -- 'active' | 'responded' | 'closed' — collapsed from a 7-state draft; see Revision note
  next_follow_up_due TEXT,              -- set = active thread awaiting reply; NULL = maintained relationship, no pending ask
  last_touch_at TEXT NOT NULL DEFAULT (datetime('now')), -- bumped on any logged interaction, not just the first message; drives staleness for "Worth reconnecting"
  follow_up_count INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  confirmed BOOLEAN NOT NULL DEFAULT 0, -- 0 = drafted stub from the skill, awaiting Jason's one-tap confirm; 1 = confirmed sent
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_contacts_job_id ON contacts(job_id);
CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);
```

Cut from the original draft: the 7-value status enum (`sent`/`no_response`/`call_scheduled`/`call_completed`/`referred`/`closed_loop`) — Winston's read, unchallenged by the room: that's instrumentation for a pipeline Jason hasn't proven he'll run once. Three states is enough for a v1 whose job is to prove the habit, not model its full lifecycle. `follow_up_count` survives (John/Mary: it's the cheap side of "how many times have I followed up," no message-level text tracking needed).

`contact_type` deliberately matches the `networking-outreach` skill's Type A/B/C vocabulary, so the skill and the data model describe one lifecycle, not two parallel ones.

### API — `server/routes/contacts.ts`

- `GET /api/contacts` — list, filterable by `status`, `contact_type`, `job_id`, `confirmed`
- `POST /api/contacts` — create (used both for manual entry and the skill's auto-drafted stub, `confirmed: false` by default for the latter)
- `PATCH /api/contacts/:id` — update status, `confirmed` (the one-tap confirm action), `follow_up_count`, `next_follow_up_due`, `notes`
- Mirrors the existing `server/routes/jobs/crud.ts` structure and the `interview_debriefs` route pattern for consistency

### UI — no standalone page. Two surfaces only.

The roundtable killed the 5-section `NetworkView` outright ("designed for demo, not use" — Sally). Huntr attaches contacts to the job card as its primary model; Teal's bolted-on, separate contact tracking is the reviewed failure mode this is explicitly avoiding. A dedicated destination page is one more place a habit can quietly stop being opened.

1. **Job-linked contacts on `JobDetailPanel`** (Type A/B, `job_id` set) — contacts for that role shown inline, where the existing job-search behavior already happens. This is the primary surface.
2. **One small "Needs Attention" card**, placed wherever Jason already looks daily (e.g. `TodayView`, near the existing Ready to Apply / Upcoming Interviews cards — not a new nav destination), with **two distinct groups inside it, not one flat list:**
   - **Follow-up due** — `next_follow_up_due` is set and today-or-past, regardless of job link. Active threads awaiting a reply. This is the urgent group; styled like the rest of the app's due/overdue treatment.
   - **Worth reconnecting** — `next_follow_up_due` is null (no active ask pending) and `last_touch_at` is 60+ days ago. This is the long-term relationship-maintenance group: contacts met before a role opened, no pending thread, just gone quiet for a while. No overdue language, no red badge — sorted oldest-touch-first, framed as a gentle suggestion ("haven't talked to X in a while") not an obligation. This is where "building a network before you need it" actually lives — a contact with no job, no active ask, and no urgency gets a home here instead of cluttering the urgent group or getting marked `closed` just to go quiet.

This is the fix for two gaps, not one: job-panel-only has no home for Type C contacts at all (caught in the first roundtable pass), and a flat "not closed" rule has no way to distinguish an active thread from a maintained relationship (caught after — see Second revision note above). One card, two groups, still no new page.

Explicitly not built for v1: a stats row, a full sortable/grouped contact list, a standalone add-contact form, a Sidebar nav entry. See Out of Scope.

### The confirm flow (resolves the auto-logging question)

The `networking-outreach` skill drafts a stub `contacts` row (`confirmed: false`) at message-draft time — name, company, `job_id` if applicable, `message_sent_at`, `status: 'active'`. This is **not** a silent write: it surfaces as a single one-tap confirm action at the natural point Jason would close the loop (right after sending), not a form, not a modal with fields to fill in. The distinction matters — a silent insert removes both the re-entry friction *and* the moment of acknowledging he did the thing; implementation-intention research suggests that acknowledgment moment is sometimes part of what makes a habit stick, not overhead sitting on top of it. One tap keeps the friction near zero while keeping the moment.

**Resolved (2026-07-30, Epic 2):** the original draft flagged a risk that the confirm-tap would never fire if the real flow is draft → copy → paste into LinkedIn → send → close the tab, since the skill doesn't run inside an open Applyr browser tab. Fixed directly instead of waiting on usage data: since the skill already runs inside a coding-agent session with tool access, it asks Jason directly once the message is actually sent ("sent that one?") and calls `PATCH /api/contacts/:id` with `confirmed: true, log_touch: true` in the same turn — no dependency on an open browser tab at all. See `.claude/skills/networking-outreach/SKILL.md`'s "Confirming the send" section.

## Acceptance Criteria

1. Migration `010_add_contacts.sql` (or next available number) creates the table above, applied via the existing migration runner — no manual DB edits.
2. `contacts` CRUD API exists and matches the field/status vocabulary above exactly (3-state status, no reintroduction of the cut 7-state values at the route layer).
3. `JobDetailPanel` and the `TodayView` "Needs Attention" card both use existing Tailwind/component conventions (`bg-surface-container-lowest`, `editorial-shadow`, card classes already in `TodayView.tsx`/`AllJobsView.tsx`) — no new design system, no new page, no new Sidebar entry.
4. A contact can be created with no `job_id` and no `next_follow_up_due` (the "meeting someone before you need a job" case) and appears in the Needs Attention card's Worth Reconnecting group once `last_touch_at` crosses 60 days — not the Follow-up Due group, and not invisible.
5. A contact created with a `job_id` appears on that job's `JobDetailPanel`; it only additionally appears in Needs Attention if `next_follow_up_due` is today-or-past (Follow-up Due group).
6. The `networking-outreach` skill creates a `confirmed: false` stub row at draft time; a single tap (not a form) flips it to `confirmed: true` without requiring re-entry of any field already known at draft time.
7. `next_follow_up_due` is populated automatically from the skill's timing rules on creation and remains editable after — including editable to empty, which is how a contact moves from "active thread" to "maintained relationship" once Jason decides there's nothing left to chase.
8. Any manual edit or note added to a contact bumps `last_touch_at`, so a maintained relationship Jason actually reached out to (outside the skill, e.g. a LinkedIn comment or a coffee chat) resets its staleness clock instead of resurfacing as stale the next day.

## Out of Scope

- **Standalone `NetworkView` page and Sidebar nav entry.** Killed outright by the roundtable, not deferred — see Decision above for why a second destination page works against the adoption goal specifically.
- **Stats row / response-rate analytics.** A feature for once there's contact volume to analyze, not before any exists.
- **A weekly cadence/target tracker** (e.g., "3 of 5 messages sent this week"). Explicitly the scope Jason rejected earlier this session when a full "networking coach" was on the table — stays rejected.
- **Streaks, shame framing, or any gamified pressure mechanic** on follow-ups or cadence. Behavior-design research favors modeling consistency-over-time and recovery-from-lapses over punishing missed days; a red "3 days overdue" badge is the opposite of that.
- **Reminder notifications** (email/push for follow-ups due). The Needs Attention card is pull, not push, for v1.
- **Bulk import of existing/past contacts.** Starts empty; historical outreach isn't backfilled.
- **Message-level follow-up tracking** (the actual text of each nudge, not just a count). `follow_up_count` + `notes` is the decided v1 granularity.

## Decided (formerly Open Questions)

1. **Auto-logging from the skill: one-tap confirm, not silent insert, not fully manual.** See "The confirm flow" above. Resolves the tension between removing dual-entry friction (a named abandonment cause) and preserving the acknowledgment moment that may matter for habit formation.
2. **`next_follow_up_due`: auto-computed, editable.** Never actually contested once separated from the 7-state machine it got bundled with in the original draft.
3. **`follow_up_count` + `notes`: sufficient for v1.** No individual follow-up message tracking.

**Resolved 2026-07-30 (Epic 2):** the one-tap-confirm-never-fires risk (skill doesn't run inside the Applyr browser tab) is fixed by having the skill ask Jason directly and PATCH `confirmed: true` in the same session turn — no browser dependency. See the "Resolved" note under The confirm flow above.

## Traceability Mapping

| File | Action |
|---|---|
| `server/migrations/010_add_contacts.sql` | New |
| `server/routes/contacts.ts` | New |
| `server/index.ts` | Register `contactsRouter` |
| `src/components/JobDetailPanel.tsx` | Add job-linked contacts section (primary surface) |
| `src/pages/TodayView.tsx` | Add "Needs Attention" card (Type C + due follow-ups) |
| `.claude/skills/networking-outreach/SKILL.md` | Add the confirm-stub write step at draft time |
| `src/types/job.ts` (or new `src/types/contact.ts`) | New `Contact` type |
| `docs/spec/05-change-requests/README.md` | Update CR-071 registry row to reflect revised scope |
| No `NetworkView.tsx`, no `Sidebar.tsx` change | Explicitly cut — see Out of Scope |
