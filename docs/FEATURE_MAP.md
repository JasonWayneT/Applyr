# Feature Map — UI Screen ↔ Code Lookup

**Purpose:** fast lookup from "what the user sees" to "what file that is," and from "what
API call fired" to "what route/service handled it." Built for an agent that gets handed a
screenshot, a bug report ("the thing on the Dashboard is wrong"), or a feature request, and
needs to find the right file in seconds without grepping for UI text first.

**This is not another narrative walkthrough.** [`docs/PROJECT_DEEP_DIVE.md`](PROJECT_DEEP_DIVE.md)
already covers the "why was this built this way" story (partially stale per its own banner —
its job-fit-scoring sections describe a deleted system). [`README.md`](../README.md)'s
"Project structure" section is the canonical map for `server/` and `scripts/` internals. This
doc's job is the piece neither of those covers well: the **frontend screen-by-screen map**,
plus a **flat API route table** connecting UI actions to backend handlers.

**Verified against the file tree 2026-08-28.** If a section here goes stale, fix it in place —
same rule README's structure section states for itself.

---

## 1. App shell (present on every screen)

| What you see | File | Notes |
|---|---|---|
| Left sidebar — logo, 5 nav items, dark/light toggle, account menu | [`src/components/Sidebar.tsx`](../src/components/Sidebar.tsx) | Nav list is the `mainNav` array (line ~33). Account popup (Settings / Help / theme toggle / "Reset local session") is the `isMenuOpen` block. |
| Top header bar — bell icon, avatar circle ("JT") | [`src/App.tsx`](../src/App.tsx) | Owns `activeTab` state and routes to the 5 pages via `renderPage()`'s switch statement. |
| Notification bell dropdown | [`src/components/NotificationPanel.tsx`](../src/components/NotificationPanel.tsx) | Polls `/api/gmail-sync/notifications` every 10s (`GMAIL_POLL_MS`) independent of the Job Search page's own log console. |
| Slide-out job detail panel (opens from any job card, any screen) | [`src/components/JobDetailPanel.tsx`](../src/components/JobDetailPanel.tsx) | See §3 — this is the single richest file in the frontend (1219 lines). |

**Nav → screen → page component:**

| Sidebar label | `activeTab` value | Page component |
|---|---|---|
| Dashboard | `'Dashboard'` | [`src/pages/TodayView.tsx`](../src/pages/TodayView.tsx) |
| Opportunities | `'Opportunities'` | [`src/pages/AllJobsView.tsx`](../src/pages/AllJobsView.tsx) |
| Job Search | `'Job Search'` | [`src/pages/SyncActivityView.tsx`](../src/pages/SyncActivityView.tsx) |
| Tuning Log | `'Tuning Log'` | [`src/pages/TuningLogView.tsx`](../src/pages/TuningLogView.tsx) |
| Settings | `'Settings'` | [`src/components/SettingsView.tsx`](../src/components/SettingsView.tsx) *(lives in `components/`, not `pages/` — historical, not a typo)* |

A 6th case, "Find New Jobs" / single-JD Add Job page, was **removed** (CR-093, 2026-08-19) —
if you see a reference to it in an old screenshot or doc, it no longer exists. See §6.

---

## 2. Screen-by-screen map

### 2.1 Dashboard — `src/pages/TodayView.tsx` (814 lines)

Landing screen after login. Distinctive on-screen text → section:

| On-screen text | Section | What it does |
|---|---|---|
| "Good morning/afternoon/evening, {name}." + "Check Gmail Now" button | Welcome header | `getGreeting()`; button hits `POST /api/gmail-sync/run` |
| "Application Progress" bar chart | Bento grid, left | 5-bar funnel (Ready to Apply → Applied → Screening → Interviews → Offers), click-through to Opportunities via `onNavigateToOpportunities` |
| "Next Interview" card (or "No interviews yet") | Bento grid, right | Soonest `interview_date` across all jobs |
| "Ready to Apply" list | Below bento | `status === 'Backlog' && has_assets`, sortable, has "Mark as Applied" (`PATCH /api/jobs/:id/status`) and ZIP download (`GET /api/jobs/:id/download-all`) actions inline |
| "Active Opportunities" list + search box | Mid-page | Applied/Screen/Interview/Offer jobs, searchable by company/title |
| "Upcoming Interviews" card grid | Mid-page | Future-dated interviews only |
| "Needs Attention" — networking contacts | Bottom, CR-071 | Follow-up-due and 60-day-quiet contacts; "Add contact" form posts to `POST /api/contacts` |
| Bottom stat tiles (Total Active / Screening / Interviewing / Response Rate) | Footer | Click-through to Opportunities except Response Rate |

Uses [`src/hooks/useFitThresholds.ts`](../src/hooks/useFitThresholds.ts) for the `tier1_floor`
score-color cutoff (fetched from `GET /api/fit-thresholds`, backed by
`data/fit_rubric_calibration.json` — CR-093 evidence-scale engine, not a hardcoded constant).

### 2.2 Opportunities — `src/pages/AllJobsView.tsx` (246 lines)

Kanban-style grouped list, one job-status pipeline. Groups (in render order) come from the
`groups` array: **New from scout → Ready to Apply → Needs retry → Applied → Screening →
Interviews → Offers → Terminal (Closed)**. Each group's chip color/icon is set right there.

Filter pills at top-right map to `OPPORTUNITIES_FILTERS` / `FILTER_STATUS_MAP` in
[`src/types/opportunities.ts`](../src/types/opportunities.ts) — this is also what the
Dashboard's chart/stat-tile click-throughs target (`onNavigateToOpportunities`).

"New from scout" banner (dismissible, per-session only — no localStorage) shows when any job
has `status === 'New'`.

### 2.3 Job Search — `src/pages/SyncActivityView.tsx` (1154 lines — largest page)

This is the scout configuration + live pipeline monitor screen. Top to bottom:

| On-screen text | What it is |
|---|---|
| "Job Search" header + "Run Job Search" button | Triggers `POST /api/sync`; button label cycles Scouting/Exporting/Drafting per `runButtonLabel()` |
| "Active Search Criteria" card (Target Role, Additional Search Titles, Work Setting, Location, Date Posted, Experience Level) | Auto-saves (1s debounce) to `POST /api/profile/job_search`, materialized server-side by `server/domain/jobSearchPrefs.ts` |
| "Blocklists & Minimum Salary" card | Title/Industry blocklist textareas, max-years-required, min-salary — same auto-save path |
| "Activity" (collapsible) — Source Registries grid | Per-connector health chips (Active/Warning/Error/Paused), polls `GET /api/sources` |
| "Automation Pipeline" 3-step tracker | Scout → Export for Review → Ready for Action; live status via `GET /api/system-status` + SSE `stage_handoff` events |
| Asset-creation stepper (`PipelineTracker`) | Only shown mid-draft; 5 stages (`gate → fit → research → resume → cover`) driven by SSE `asset_progress` events |
| "Pipeline Log Console" (terminal-styled) | Tails `GET /api/logs`, live-appends on SSE events |
| "Pipeline Roles" panel | Evaluated + scout-queue job cards, "Not a fit"/"Remove" dismiss buttons → `PATCH /api/jobs/:id/status` |

SSE connection is `GET /api/sync/stream`, listened to via `connectSSE()`; event types:
`stage_handoff`, `source_progress`, `source_health`, `connector_error`, `asset_progress`,
`run_complete`. If you're chasing a "the UI didn't update live" bug, start here, then trace
into `server/routes/pipeline.ts` and `server/scout.ts` server-side.

Curated location list (`CITY_LOCATIONS`) must stay in sync with `CITY_COUNTRY` in
`server/domain/jobSearchPrefs.ts` — noted inline in the file, worth checking both sides on
a location bug.

### 2.4 Tuning Log — `src/pages/TuningLogView.tsx` (243 lines)

Shows only self-rejected jobs (`status === 'Closed' && rejection_type === 'Self-Rejected'`).
"What do these terms mean?" collapsible glossary defines Engine Score / Avg Mismatched Score
/ Target Mismatch Stage / Discovered Mismatch at — same labels used in the stat tiles and per-
card metadata below it. Read-only diagnostic screen; no write actions besides `onJobClick`
into the detail panel.

### 2.5 Settings — `src/components/SettingsView.tsx` (984 lines)

Four sub-tabs (local `activeTab` state inside this one component, not the app-level tab):

| Sub-tab | Content |
|---|---|
| **Profile** | Name/email/phone/location card → `POST /api/profile/identity` |
| **Experience** | Master career-experience textarea (`data/workExperience.md` source of truth) — the big free-text editor with "Document structure (5 sections)" helper text; auto-generates `workExperience_summary.md` on save via `POST /api/experience` |
| **API or Connections** | FR-059–063. Provider table (Local LLM / Gemini / Claude / Perplexity) with "Set primary" + key inputs, each falls back to a "Doppler / env" locked badge when `envStatus.<provider>` is true (`GET /api/env_status`). Below it: Job board API connectors (Adzuna App ID/Key, TheirStack API key + jobs-per-run) |
| **Analytics** | Application-outcome stats (`stats?.outcomes`) — where applications landed, rejection breakdown |

Reusable local helpers: `SettingsCard` (card chrome) and `SettingsField` (labeled input wrapper)
are defined at the top of this same file, not extracted — if you're hunting for a shared
Settings UI primitive, it's inline here, not in `components/`.

### 2.6 Job Detail Panel — `src/components/JobDetailPanel.tsx` (1219 lines — largest component)

Slide-out panel, not a route — opens from a job card click on any screen (`onJobClick`).
Single scrolling panel, no internal tabs. Section order top to bottom:

| Section heading | What's there |
|---|---|
| Job title + company (h2) | Header |
| "Details" | Location, salary, source, posted date, `has_assets` |
| "Application Status" | Status stepper (Backlog → Applied → Recruiter Screen → Core Interviews → Offer), status-change control |
| "Interview Schedule" | Date/time picker, gated by `statusRequiresInterviewDateTime()` from `shared/domain/jobPipeline` |
| "Contacts" | Per-job networking contacts (distinct from Dashboard's "Needs Attention" global list) — `hiring_manager` / `warm_connection` / `informational` types |
| "Interview Debrief" | Post-interview notes/outcome form — `server/repository/interviewDebriefRepository.ts` + `routes/jobs/debriefs.ts` |
| "Match Summary" | Fit-score breakdown text |
| "Skill Gap Analysis" | On-demand `GET /api/jobs/:id/skill-gap` call ("Analyze Now" button) |
| "Your Assets & Links" | Original JD link, PDF file list with inline Edit (opens `DocumentEditor`) and Download actions |
| "Pipeline Process Logs" | Per-job log tail |
| Closure modal (Self-Reject / No Longer Available / Confirm Deletion) | Bottom — `closureData.type` switch, feeds the Tuning Log (§2.4) when type is `Self-Rejected` |

Imports shared domain logic from `shared/domain/jobPipeline` and `shared/domain/interviewDebrief`
rather than duplicating status/date rules — check `shared/domain/` first if a rule here looks
wrong, it may be defined there and just consumed here.

### 2.7 Document Editor — `src/components/DocumentEditor.tsx` (360 lines)

Modal opened from JobDetailPanel's "Your Assets & Links" (Edit icon on any `.md`-backed PDF).
WYSIWYG via `@toast-ui/react-editor`. Three actions in the toolbar:

- **"Lint"** — local WebGPU grammar check (`src/lib/grammarCheck.ts` / `src/lib/grammar-worker.ts`), never modifies text, just flags issues
- **"Apply AI Rewrite"** — free-text instruction box + `handleAiRewrite()`, calls `POST /api/jobs/:id/ai-rewrite`
- **"Compile & Save"** — `PUT /api/jobs/:id/files/:filename`, recompiles the PDF server-side

### 2.8 Status chip label lookup — `src/components/StatusChip.tsx`

If you're matching a screenshot's colored pill text back to a `job.status` DB value, this file
is the entire mapping (`STATUS_CONFIG`). Notable non-obvious ones: DB status `'New'` and
`'Backlog'` both render as **"Ready to Apply"**; `'Recruiter Screen'` renders as
**"Screening"**; `'Rejected'` renders as **"Not a fit"** (short) or **"Archived"** (long mode,
`StatusChip`'s `long` prop) — never the raw word "Rejected."

---

## 3. Orphaned components — not wired into the app

Confirmed via `grep` (not imported by `App.tsx` or any page/component as of 2026-08-28):

- [`src/components/BulkUploadForm.tsx`](../src/components/BulkUploadForm.tsx) — CSV drag-drop upload
- [`src/components/JDInputForm.tsx`](../src/components/JDInputForm.tsx) — single-JD paste form

Both are leftovers of the single-JD "Add Job" / "Find New Jobs" page removed in CR-093
(2026-08-19, see `Sidebar.tsx`'s own comment at line ~28). They still compile and have no
current importer — don't treat a screenshot or design reference showing that old page as
current, and don't spend time debugging these files unless you're deliberately reviving that
flow.

---

## 4. API route table

Every `router.<verb>('/api/...')` registration, grouped by file. Frontend call sites use the
`api()` helper (`src/lib/api.ts`) to prefix the dev-server origin.

| Method | Route | File |
|---|---|---|
| GET | `/api/system-status` | `server/routes/system.ts` |
| POST | `/api/system-status` | `server/routes/system.ts` |
| GET | `/api/fit-thresholds` | `server/routes/system.ts` |
| GET | `/api/ats-pipeline` | `server/routes/system.ts` |
| GET | `/api/logs` | `server/routes/system.ts` |
| POST | `/api/stream/local-model` | `server/routes/system.ts` |
| GET | `/api/sync/stream` (SSE) | `server/routes/pipeline.ts` |
| POST | `/api/sync` | `server/routes/pipeline.ts` |
| GET | `/api/profile/job_search` | `server/routes/profile.ts` |
| POST | `/api/profile/job_search` | `server/routes/profile.ts` |
| GET | `/api/profile/:key` (identity, llm_settings, api_connections, theirstack_settings, …) | `server/routes/profile.ts` |
| POST | `/api/profile/:key` | `server/routes/profile.ts` |
| GET | `/api/env_status` | `server/routes/profile.ts` |
| GET | `/api/experience` | `server/routes/profile.ts` |
| POST | `/api/experience` | `server/routes/profile.ts` |
| GET | `/api/contacts` | `server/routes/contacts.ts` |
| POST | `/api/contacts` | `server/routes/contacts.ts` |
| PATCH | `/api/contacts/:id` | `server/routes/contacts.ts` |
| POST | `/api/gmail-sync/run` | `server/routes/gmailSync.ts` |
| GET | `/api/gmail-sync/notifications` | `server/routes/gmailSync.ts` |
| GET | `/api/sources` | `server/routes/sources.ts` |
| POST | `/api/sources/:id/sync` | `server/routes/sources.ts` |
| GET | `/api/jobs` | `server/routes/jobs/crud.ts` |
| POST | `/api/jobs` | `server/routes/jobs/crud.ts` |
| POST | `/api/jobs/reconcile-submissions` | `server/routes/jobs/crud.ts` |
| GET | `/api/jobs/stats` | `server/routes/jobs/crud.ts` |
| PATCH | `/api/jobs/:id/status` | `server/routes/jobs/crud.ts` |
| PATCH | `/api/jobs/:id` | `server/routes/jobs/crud.ts` |
| GET | `/api/jobs/:id/debriefs` | `server/routes/jobs/debriefs.ts` |
| POST | `/api/jobs/:id/debriefs` | `server/routes/jobs/debriefs.ts` |
| PATCH | `/api/jobs/:id/debriefs/:debriefId` | `server/routes/jobs/debriefs.ts` |
| DELETE | `/api/jobs/:id/debriefs/:debriefId` | `server/routes/jobs/debriefs.ts` |
| GET | `/api/jobs/:id/files` | `server/routes/jobs/files.ts` |
| GET | `/api/jobs/:id/files/:filename` | `server/routes/jobs/files.ts` |
| PUT | `/api/jobs/:id/files/:filename` | `server/routes/jobs/files.ts` |
| GET | `/api/jobs/:id/skill-gap` | `server/routes/jobs/files.ts` |
| POST | `/api/jobs/:id/ai-rewrite` | `server/routes/jobs/files.ts` |
| GET | `/api/jobs/:id/download-all` | `server/routes/jobs/files.ts` |

`server/routes/jobs/index.ts` is just the mount point for the 4 `jobs/*` sub-files;
`server/routes/jobs/shared.ts` holds the `jobBaseDir` helper they share.

---

## 5. Backend & pipeline (pointer, not a duplicate)

`server/` (Express) and `scripts/` (Python authoring pipeline + TS scout) are already mapped
in full in [README.md → "Project structure"](../README.md#project-structure) — that section
is the maintained source of truth for those two trees (domain/middleware/pipeline/repository/
services layout, the full `scripts/` breakdown by subsystem: Stage 0 gates, CR-074 authoring
packet, cover-letter subsystem, style guards, compilation, batch orchestration). Don't
duplicate it here; go there for anything under `server/` or `scripts/`.

One addition not in that section: **`shared/`** — code imported by both `server/` and
`src/` (e.g. `shared/domain/jobPipeline.ts`, `shared/domain/interviewDebrief.ts`, both used
by `JobDetailPanel.tsx`, §2.6 above). If a status/date rule looks duplicated between frontend
and backend, check here first — it's meant to be the single copy.

---

## 6. Common lookup patterns

**"I have a screenshot of screen X, where's the code?"** → §2, match the distinctive heading
text in the left column, or the nav label in §1's table.

**"A button/action did Y, what fired?"** → search this file for the route in §4, or grep the
route string directly in `src/` for the `fetch(api('/api/...'))` call site.

**"What does status chip color/text Z mean?"** → §2.8, `StatusChip.tsx`.

**"I see a page/component in a screenshot or old doc that isn't in App.tsx's switch statement or
this map."** → check §3 (orphaned components) before assuming it's missing — it may have been
deliberately removed (e.g. CR-093's "Find New Jobs" page).

**"Something in `server/` or `scripts/` I can't find here."** → README's "Project structure"
(§5 above), not this file.
