---
status: not started
created: 2026-08-28
related: docs/ROADMAP_BEST_PRACTICES.md (research/rationale for every epic below — read it first)
contains: CR-104 (frontend & API hardening pass)
---

# CR-104 — Frontend & API Best-Practices Hardening: Epics & Stories

**Handoff doc, no separate CR spec.** This tracker skips the usual `05-change-requests/CR-104-*.md`
step — the research and rationale already live in
[`docs/ROADMAP_BEST_PRACTICES.md`](../ROADMAP_BEST_PRACTICES.md), written after reading the actual
current code and cross-checking it against external best-practice guidance. Read that doc's relevant
section before starting any epic below — every story here assumes you already know *why*, and only
spells out *what*. A new session can pick up at the first unchecked story with just those two files.

**Ordering:** originally ranked by priority alone (auth/security first, structural cleanup last).
Reordered at Jason's request to put **Epic 1 (decomposing `JobDetailPanel.tsx`) first**, ahead of
priority order — it's genuinely a prerequisite that makes several later epics cheaper and cleaner
(Epic 4's error boundaries wrap individual sections instead of one 1200-line monolith; Epic 6's tests
target an already-isolated `StatusSection.tsx` instead of logic tangled inside JSX). Everything after
Epic 1 is still in its original priority order. Each epic is a clean stopping point — check its
stories, verify, stop, hand off.

**Public-repo note:** this repo is being shared publicly. Two epics reflect that directly:
- **Epic 2** was redesigned around it (originally "always require an auth token," changed to "default
  to localhost-only, require the token only if a user opts into wider network access" — a friendlier
  default for a stranger cloning this repo than forcing extra setup on everyone).
- **Epic 12** (OS-keychain secret storage) is marked **optional / skip by default** at Jason's request
  — it's the one item here that adds a platform-specific dependency, and not everyone running a public
  clone of this repo will want that tradeoff. Do not start Epic 12 unless explicitly asked to.

**General verification expectation for every epic:** don't mark a story's checkbox done on a typecheck
alone. Run the dev server (`npm run dev`) and actually exercise the change in the browser, or run the
relevant test/lint command, and say what you observed — same standard the rest of this project's
implementation trackers hold to.

---

## Epic 1 — Decompose `JobDetailPanel.tsx` into per-section subcomponents [moved first]

**Why:** largest component in the frontend (1219 lines, 10 sections, no internal subdivision) — any
local change re-renders the whole panel, and it's the hardest file in the app to test or
error-isolate. Doing this first means Epic 4 (error boundaries) and Epic 6 (tests) below build on
already-separated pieces instead of a monolith. See `ROADMAP_BEST_PRACTICES.md` §2 (Job Detail Panel
row).

This is the biggest epic here — treat each story as its own stopping point if a session runs out of
budget mid-epic.

- [ ] **Story 1.1**: Create `src/components/job-detail/` and extract the "Application Status" section
  into `StatusSection.tsx`, taking exactly the props it needs (not the whole job object by default —
  check what the section actually reads first).
- [ ] **Story 1.2**: Extract "Interview Schedule" into `InterviewScheduleSection.tsx`.
- [ ] **Story 1.3**: Extract "Contacts" into `ContactsSection.tsx`.
- [ ] **Story 1.4**: Extract "Interview Debrief" into `DebriefSection.tsx`.
- [ ] **Story 1.5**: Extract "Match Summary" into `MatchSummarySection.tsx`.
- [ ] **Story 1.6**: Extract "Skill Gap Analysis" into `SkillGapSection.tsx`.
- [ ] **Story 1.7**: Extract "Your Assets & Links" (including the `DocumentEditor` mount point) into
  `AssetsSection.tsx`.
- [ ] **Story 1.8**: Extract "Pipeline Process Logs" into `LogsSection.tsx`.
- [ ] **Story 1.9**: Extract the closure modal (Self-Reject / No Longer Available / Confirm Deletion)
  into `ClosureModal.tsx`.
- [ ] **Story 1.10**: Reassemble `JobDetailPanel.tsx` as a thin shell that composes the sections above
  in the original order. Don't add error-boundary wrapping yet — the reusable `ErrorBoundary`
  component doesn't exist until Epic 4; that epic comes back and wraps each of these sections
  individually once it does.
- [ ] **Story 1.11 — verify**: Full manual pass in the browser — open a job, exercise every section
  (change status, schedule an interview, add a contact, log a debrief, view match summary, run skill
  gap, edit/download an asset, check logs, run the closure flow) and confirm nothing regressed
  visually or functionally compared to before the extraction.

---

## Epic 2 — Close the token / API-key exposure gap [P0]

**Why (short version):** the server binds to all network interfaces by default, the optional auth
token is off by default, and Settings' API-key fields are never masked when read back. See
`ROADMAP_BEST_PRACTICES.md` §1.3 for the full reasoning.

**Redesigned default for the public repo:** instead of forcing every user to set up a token, flip the
*bind address* default to localhost-only — safe out of the box for a stranger cloning the repo — and
only require the token when a user deliberately opts into wider access (e.g. for their own
Tailscale/phone use).

- [ ] **Story 2.1**: In `server/index.ts`, replace the hardcoded `app.listen(PORT, '0.0.0.0', ...)`
  with a bind address controlled by a new env var, e.g. `APPLYR_BIND_ALL` (unset/false → bind
  `127.0.0.1`; `true` → bind `0.0.0.0`, preserving today's behavior for anyone already relying on it).
  Log which mode it started in.
- [ ] **Story 2.2**: In `server/middleware.ts`'s `requireApiToken`, when `APPLYR_BIND_ALL` is true and
  `APPLYR_API_TOKEN` is unset, fail startup with a clear error message explaining why (don't silently
  run unprotected on a wide bind) rather than just falling through to `next()` as it does today.
- [ ] **Story 2.3**: Update `README.md` (and `.env.example` / equivalent, if one exists — check first)
  to document both env vars and this default.
- [ ] **Story 2.4**: Find every GET route that returns stored API key values (start with
  `server/routes/profile.ts`'s `api_connections`/`llm_settings` handlers) and mask them before they
  leave the server — return something like `sk-...ab12` (last 4 chars only) instead of the full value.
  Confirm the Settings UI (`src/components/SettingsView.tsx`) still renders sensibly with a masked
  value (it should already treat the field as opaque display text, not something it parses).
- [ ] **Story 2.5 — verify**: Start the server fresh with no env vars set — confirm it binds to
  localhost only (`netstat`/`curl` from a non-localhost angle should fail, or just confirm the log
  line). Set `APPLYR_BIND_ALL=true` with no token — confirm it now refuses to start with a clear
  message. Set both `APPLYR_BIND_ALL=true` and `APPLYR_API_TOKEN=<value>` — confirm it starts and a
  mutating request without the header gets a 401. Load Settings in the browser with a real key saved
  and confirm only the masked form is ever visible in the Network tab's response body.

---

## Epic 3 — Add baseline Express hardening (Helmet + rate limiting) [P1]

**Why:** `cors()` is already correctly scoped to localhost origins; `helmet` and rate limiting are
the other two-thirds of the usual baseline trio and are currently missing entirely. See
`ROADMAP_BEST_PRACTICES.md` §1.4.

- [ ] **Story 3.1**: `npm install helmet express-rate-limit`.
- [ ] **Story 3.2**: In `server/index.ts`, add `app.use(helmet())` early in the middleware stack
  (before the route mounts, alongside `cors()`).
- [ ] **Story 3.3**: Add a rate limiter applied to mutating routes (or all `/api/*` routes — your
  call, but keep GET-heavy polling routes like `/api/jobs` and `/api/gmail-sync/notifications` in
  mind). Size the window/limit generously — this app already polls itself every 5-10 seconds from
  multiple components (see `ROADMAP_BEST_PRACTICES.md` §1.1), so a naive default limit will trip on
  normal use. Something like 300 requests/minute per IP is a safe starting point; tune from there.
- [ ] **Story 3.4 — verify**: `curl -I` a route and confirm Helmet's headers are present. Write a
  throwaway loop hitting an endpoint past the configured limit and confirm a 429 comes back, then
  confirm normal app usage (leave the dev server + browser open for a couple of minutes with the app's
  existing polling running) never trips the limiter on its own.

---

## Epic 4 — Add crash containment (React error boundaries) [P1]

**Why:** zero error boundaries exist anywhere in the frontend today — one bad render anywhere
white-screens the entire app. See `ROADMAP_BEST_PRACTICES.md` §1.2.

- [ ] **Story 4.1**: Create `src/components/ErrorBoundary.tsx` — a reusable class component (error
  boundaries still require a class component in React) taking a `fallback` render prop or a simple
  default "Something went wrong here" message, and logging the caught error via `componentDidCatch`
  (`console.error` at minimum — don't swallow it silently).
- [ ] **Story 4.2**: Wrap `renderPage()`'s output in `src/App.tsx` in one root `ErrorBoundary` with a
  fallback that includes a reload button.
- [ ] **Story 4.3**: Wrap the `<JobDetailPanel />` render in `src/App.tsx` in its own `ErrorBoundary`,
  separate from the root one — a crash in the slide-out panel shouldn't take out the rest of the app
  behind it.
- [ ] **Story 4.4**: Now that Epic 1 split the panel into `src/components/job-detail/*`, wrap each of
  those sections (`StatusSection`, `InterviewScheduleSection`, `ContactsSection`, `DebriefSection`,
  `MatchSummarySection`, `SkillGapSection`, `AssetsSection`, `LogsSection`) individually in its own
  `ErrorBoundary` inside `JobDetailPanel.tsx`'s composing shell — this is the granular placement the
  research called for, and it's cheap now that the sections are already separate components.
- [ ] **Story 4.5**: Wrap `DocumentEditor`'s render specifically (it mounts inside `AssetsSection.tsx`
  after Epic 1) in its own `ErrorBoundary` too — this is the component most likely to render
  unpredictable AI-generated content, worth isolating even within `AssetsSection`.
- [ ] **Story 4.6 — verify**: Temporarily throw an error inside one wrapped section (e.g. a fake
  `throw new Error('test')` in `SkillGapSection.tsx`'s render), confirm only that section shows the
  fallback UI while the rest of the panel and app keep working, then remove the test throw before
  committing.

---

## Epic 5 — Replace ad hoc polling with a shared data-fetching layer, starting with jobs [P1]

**Why:** five independent, uncoordinated polling loops, no shared cache, no tab-visibility awareness.
`useJobs` is the biggest one and every screen depends on it. See `ROADMAP_BEST_PRACTICES.md` §1.1.

- [ ] **Story 5.1**: `npm install @tanstack/react-query`. Add a `QueryClientProvider` at the root in
  `src/App.tsx` (or a new `src/main.tsx` wrapper if that's the cleaner spot — check how the app is
  currently bootstrapped first).
- [ ] **Story 5.2**: Convert `src/hooks/useJobs.ts` to use `useQuery` with `refetchInterval: 5000`
  (matching today's `POLL_INTERVAL_MS`), keeping the hook's existing return shape (`jobs`, `isLoaded`,
  `selectedJob`, `setSelectedJob`, `handleStatusChange`) unchanged so nothing consuming it needs to be
  touched in this story.
- [ ] **Story 5.3 — verify**: Dashboard, Opportunities, and Tuning Log all still show live data;
  confirm via the browser's Network tab that requests are still deduped (no duplicate simultaneous
  `/api/jobs` calls from different components) and that navigating between tabs no longer triggers a
  fresh loading spinner for data already in cache.
- [ ] **Story 5.4 (stretch, optional within this epic)**: Migrate `NotificationPanel.tsx`'s Gmail poll
  to the same `QueryClient` for consistency. Not required to close this epic — note explicitly if
  skipped, so it's clear this was a deliberate scope cut, not an oversight.

---

## Epic 6 — Add automated test coverage for the highest-risk logic [P1]

**Why:** almost no frontend test coverage exists despite Vitest already being configured. Start with
the logic that has the widest blast radius if it silently breaks. See `ROADMAP_BEST_PRACTICES.md`
§1.6.

- [ ] **Story 6.1**: Add unit tests for `shared/domain/jobPipeline.ts` — cover every status-transition
  rule and `statusRequiresInterviewDateTime()`.
- [ ] **Story 6.2**: Add unit tests for `shared/domain/interviewDebrief.ts`.
- [ ] **Story 6.3**: Add tests for `src/components/job-detail/StatusSection.tsx`'s status-stepper
  logic (already isolated in its own file since Epic 1 — if the decision logic is still tangled
  inside JSX event handlers within that file, pull it out into a small testable function first, don't
  write a test that requires full component rendering just to exercise a status-transition rule).
- [ ] **Story 6.4 — verify**: `npm run test:vitest` passes clean, and confirm the new tests actually
  fail if you temporarily break the logic they cover (a quick sanity check that they're testing the
  real thing, not a tautology).

---

## Epic 7 — Accessibility pass [P2]

**Why:** 4 total `aria-label`/`role` occurrences across the entire frontend; no automated check for
new instances. See `ROADMAP_BEST_PRACTICES.md` §1.5.

- [ ] **Story 7.1**: `npm install -D eslint-plugin-jsx-a11y`, add it to `eslint.config.*` alongside
  the existing `eslint-plugin-react-hooks`.
- [ ] **Story 7.2**: Run `npm run lint` and collect the full list of newly-flagged issues.
- [ ] **Story 7.3**: Sweep and fix — add `aria-label` to icon-only buttons across the flagged files
  (expect at least the notification bell and account-menu avatar in `Sidebar.tsx`, the dismiss `×` in
  `NotificationPanel.tsx`, and the edit/download icons in `src/components/job-detail/*` — Epic 1's
  extracted sections, primarily `AssetsSection.tsx`).
- [ ] **Story 7.4 — verify**: `npm run lint` clean of `jsx-a11y` errors.

---

## Epic 8 — Add schema validation to the highest-risk write routes [P2]

**Why:** no general request-body validation exists server-side beyond two narrow hand-written guards.
See `ROADMAP_BEST_PRACTICES.md` §1.8.

- [ ] **Story 8.1**: `npm install zod` (it's currently present only as another package's transitive
  dependency — add it as a direct one).
- [ ] **Story 8.2**: Define Zod schemas for the POST/PATCH bodies in `server/routes/profile.ts`
  (identity, `job_search` prefs, `api_connections`, `llm_settings`, `theirstack_settings`) and
  validate before acting on them, returning a clean 400 with the validation error on failure.
- [ ] **Story 8.3**: Define schemas for the job-creation/update bodies in `server/routes/jobs/crud.ts`.
- [ ] **Story 8.4 — verify**: Send a deliberately malformed payload to two or three of the newly
  validated routes (missing field, wrong type) and confirm a clean 400 with a useful message comes
  back, instead of the request silently propagating further into the app.

---

## Epic 9 — Skip redundant Dashboard recalculation [P2]

**Why:** `TodayView.tsx` derives 4+ filtered/sorted lists from the same `jobs` array on every 5-second
poll tick with no memoization. See `ROADMAP_BEST_PRACTICES.md` §2 (Dashboard row).

- [ ] **Story 9.1**: Wrap the derived lists (Ready to Apply, Active Opportunities, Upcoming
  Interviews, stat-tile counts) in `useMemo`, keyed on `jobs` (and any other actual inputs, like the
  search box's filter text).
- [ ] **Story 9.2 — verify**: Confirm the Dashboard still updates correctly when jobs change (add a
  quick `console.log` inside one memoized calculation temporarily, confirm it does *not* re-run on an
  unrelated re-render, then remove the log).

---

## Epic 10 — Verify (and if needed, fix) SSE reconnect behavior [P2]

**Why:** `src/lib/sse.ts` is a hand-rolled SSE parser (needed to send the auth header, which the
native `EventSource` API can't do) — meaning the free auto-reconnect-with-backoff that native
`EventSource` provides isn't automatic here. This was flagged as "go verify," not a confirmed bug.
See `ROADMAP_BEST_PRACTICES.md` §2 (Job Search row).

- [ ] **Story 10.1**: Read the full `connectSSE()` implementation (wherever it's defined — search for
  it, likely in `src/pages/SyncActivityView.tsx` or a lib file it imports) and determine whether it
  currently reconnects after a dropped connection, and if so, whether it backs off (waits
  progressively longer between attempts) rather than hammering the server immediately.
- [ ] **Story 10.2**: If reconnect-with-backoff is missing, add it — on connection drop, retry with a
  short delay (e.g. 3s) that increases on repeated failures, capped at some reasonable ceiling (e.g.
  30s), resetting back to the short delay once a connection succeeds.
- [ ] **Story 10.3 — verify**: With the dev server running and the Job Search screen open and actively
  streaming, kill and restart the backend process, and confirm the frontend automatically reconnects
  and resumes live updates without a manual page refresh.

---

## Epic 11 — URL-synced routing [P2, optional]

**Why:** no client-side router — refreshing always returns to Dashboard, no deep links, no back-button
support for tab/filter/job-panel state. Low urgency for a single-user tool. See
`ROADMAP_BEST_PRACTICES.md` §1.7.

- [ ] **Story 11.1**: Evaluate `react-router` vs. a lighter URL-search-param sync (no full router
  needed for a 5-tab app) — pick the smaller footprint unless there's a concrete reason not to.
- [ ] **Story 11.2**: Implement — sync `activeTab`, the Opportunities filter, and the selected job ID
  to the URL.
- [ ] **Story 11.3 — verify**: Refresh the browser mid-session and confirm you land back on the same
  tab/filter/job instead of Dashboard; confirm the browser back button undoes navigation sensibly.

---

## Epic 12 — OS-keychain secret storage [P2, **OPTIONAL — SKIP BY DEFAULT**]

**Do not start this epic unless explicitly asked to.** Jason's instruction: this repo is being shared
publicly, and moving API-key storage to an OS-specific credential vault (Windows Credential Manager /
macOS Keychain / Linux libsecret) adds a platform-specific dependency that not everyone running a
public clone of this repo will want. Leaving it documented here as an option, not a default task, so
it isn't lost — but it should stay unchecked unless someone deliberately opts in.

- [ ] **Story 12.1 (optional)**: Evaluate a cross-platform OS-keychain library (e.g. `keytar`'s
  actively-maintained successors, since `keytar` itself is deprecated — check current options at
  implementation time) against the tradeoff of adding a native dependency to the project.
- [ ] **Story 12.2 (optional)**: If pursued, migrate the 5 provider API keys (Gemini, Claude,
  Perplexity, Adzuna, TheirStack) from the SQLite `api_connections`/`llm_settings` columns to the
  chosen keychain store, with a one-time migration path for existing users' already-saved keys.
- [ ] **Story 12.3 (optional) — verify**: Confirm keys round-trip correctly through the OS vault on
  the maintainer's own platform, and confirm the app degrades gracefully (clear error, not a crash) on
  a platform/environment where the OS vault isn't available (e.g. some headless Linux setups).
