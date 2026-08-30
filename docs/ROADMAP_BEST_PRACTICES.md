# Best-Practices Roadmap — Frontend & API Layer

**Purpose:** a research-only pass over every feature in [`docs/FEATURE_MAP.md`](FEATURE_MAP.md),
checked against current (2025/2026) industry best practice, with concrete gaps and a prioritized
fix list. No code was changed to produce this — it's a plan to work from, not a diff.

**Method:** read the actual current source for the app shell, data layer, and a representative
cross-section of screens (App.tsx, api.ts, useJobs.ts, Sidebar.tsx, NotificationPanel.tsx,
SettingsView.tsx, server/index.ts, server/middleware.ts, sse.ts), grepped the rest of `src/` and
`server/` for the patterns that matter (data fetching, accessibility, tests, secrets, security
middleware), and cross-checked each finding against current external guidance (sources at the
bottom). Findings below are only the ones with a real gap — several areas checked out fine and are
noted as such rather than padded with manufactured issues.

**Scope note:** this is a personal, single-user, locally-run tool, not a multi-tenant SaaS product.
Priorities below are weighted for that — a few "best practice" items that would be non-negotiable
in a hosted product (e.g. Redis-backed rate limiting) are marked low priority here because the
threat model and scale don't justify them yet.

---

## How to read this

- **P0** — cheap, closes a real exposure or crash risk, do next.
- **P1** — real architectural gap, worth a dedicated pass soon.
- **P2** — genuine improvement, but lower urgency for a single-user local tool.

Effort is rough (S = under a day, M = a few days, L = multi-week).

---

## 1. Cross-cutting findings (affect nearly every screen)

These aren't per-feature issues — they're patterns in the shared app shell and data layer that
every screen in §2 inherits, so they're worth fixing once at the root rather than per-screen.

### 1.1 — Data fetching is polling-only, with no shared cache [P1, effort M]

**Current state:** every screen's data ultimately comes from independent, uncoordinated
`setInterval` + `fetch` loops:
- [`useJobs.ts`](../src/hooks/useJobs.ts) polls the *entire* `/api/jobs` table every 5s, unconditionally, for every screen (Dashboard, Opportunities, Tuning Log all depend on it).
- [`NotificationPanel.tsx`](../src/components/NotificationPanel.tsx) separately polls `/api/gmail-sync/notifications` every 10s.
- `Sidebar.tsx` fetches `/api/profile/identity` once, `useFitThresholds.ts` fetches thresholds once — different lifecycle from the two pollers above.
- None of these check `document.visibilityState`, so polling continues at full rate even when the browser tab is backgrounded.

**Best practice:** for React apps with any meaningful amount of server state, the current standard
is a dedicated data-fetching library (TanStack Query is the dominant one — ~42M weekly downloads)
rather than hand-rolled `useEffect` + `setInterval`. It gives you cache deduplication (two
components asking for the same data share one request), stale-while-revalidate (no spinner flash
on remount), built-in `refetchInterval` polling that respects component lifecycle, and it stops
each screen from reinventing its own loading/error state.

**Gap:** none of that exists here — five independent polling loops, no cache, no visibility
awareness, and loading/error handling duplicated ad hoc in each hook/component (`useJobs`'s own
try/catch fallback vs. `NotificationPanel`'s silent-swallow are already two different styles for
the same problem).

**Recommendation:** adopt TanStack Query incrementally, starting with `useJobs` (it's the one
every screen depends on, so fixing it once has the widest payoff). Don't do a big-bang migration —
convert one hook at a time.

### 1.2 — No React error boundaries anywhere [P1, effort S]

**Current state:** grepped all of `src/` for `ErrorBoundary` / `componentDidCatch` — zero hits.
`App.tsx`'s `renderPage()` switch has no fallback for a thrown render error.

**Best practice (2025 guidance):** don't rely on one root boundary for the whole app — a crash
still takes down the whole screen. The current recommendation is layered: one root boundary (last
resort), one per route/page, and one around any widget that renders external or LLM-produced
content, since that's the highest-risk render input.

**Gap:** a render error anywhere — including inside the 1219-line `JobDetailPanel` or the
AI-rewritten content in `DocumentEditor` — currently white-screens the entire app, not just that
panel.

**Recommendation:** add a boundary in `App.tsx` around `renderPage()`, plus dedicated boundaries
around `JobDetailPanel` and `DocumentEditor` specifically, since both render content that
originated outside your own code (server data, AI output).

### 1.3 — Secrets: plaintext storage + auth gaps on a Tailscale-reachable server [P0 for the two cheap items, P2 for keychain migration]

**Current state:**
- `server/index.ts` binds Express to `0.0.0.0:3000` explicitly, on purpose, for Tailscale/LAN reach — not just `localhost`.
- `server/middleware.ts`'s `requireApiToken` only enforces `X-Applyr-Token` when `APPLYR_API_TOKEN` is set in the environment, and it's **off by default**. Even when set, it only gates mutating verbs — every GET route (including `/api/env_status`, and whatever `/api/profile/api_connections` returns) is unauthenticated.
- Settings' "API or Connections" tab writes Gemini/Claude/Perplexity/Adzuna/TheirStack keys via `POST /api/profile/api_connections`. Grepped `server/` for `encrypt` — zero hits. These keys almost certainly land in `jobagent.sqlite` as plaintext columns.

**Best practice:** for any app storing API keys locally, current guidance is clear that a plaintext
file or DB column is one step above hardcoding — readable by any process running as your user, no
extra authentication required. OS-level secure storage (Keychain / Windows Credential Manager /
libsecret) is the recommended target; if that's not practical short-term, at minimum encrypt the
DB column with a machine-local key.

**Gap:** two different things stacked — (a) the server is reachable beyond localhost with
authentication effectively optional, and (b) the secrets it protects are stored in plaintext.
Given this is a personal tool, the realistic risk is lower than a hosted product, but it's not
zero — anything else on the same tailnet/LAN can currently read `/api/env_status` and any
key-echoing GET route with no credential at all.

**Recommendation, split by cost:**
- **P0 (cheap, do next):** require `APPLYR_API_TOKEN` to be set when the server binds `0.0.0.0`
  (fail loudly at startup if it isn't), and confirm no GET route ever echoes a full key value back
  to the frontend — mask it (e.g. `sk-...ab12`) the way most SaaS settings pages do.
- **P2 (bigger lift):** evaluate OS-keychain-backed storage for the 5 provider keys instead of the
  SQLite column, now that the app already has a Doppler integration for *some* secrets — this
  would extend the same instinct to the Settings-UI-entered ones.

### 1.4 — No Express hardening middleware [P1, effort S]

**Current state:** `server/index.ts` has `cors()` scoped correctly to localhost-pattern origins
(this part is fine, no change needed) but no `helmet()` and no rate limiter of any kind.

**Best practice:** `helmet`, `cors`, and `express-rate-limit` are described as the de facto
baseline trio for an Express API today — helmet for secure response headers, rate limiting so no
single client can hammer the process.

**Gap:** missing two of the three, on a server that's intentionally reachable beyond localhost
(see 1.3).

**Recommendation:** add `helmet()` and a light per-IP rate limiter on mutating routes. This is a
same-day change, no Redis needed at this scale (that's only a multi-instance concern, which
doesn't apply here).

### 1.5 — Accessibility investment is close to zero [P2, effort S]

**Current state:** grepped `src/` for `aria-label|role=|alt=` — 4 total hits across the entire
frontend (`TodayView.tsx` x1, `NotificationPanel.tsx` x1, `Sidebar.tsx` x2). No
`eslint-plugin-jsx-a11y` in the lint config (only `eslint-plugin-react-hooks` is installed). Most
icon-only buttons — the notification bell, avatar menu trigger, per-notification dismiss ×,
edit/download icons in the Job Detail Panel — have no accessible name.

**Gap:** this isn't a compliance requirement for a single-user tool, but it's also a genuinely
cheap fix that pays off the moment you use the app with a screen reader, voice control, or just
unfamiliar hardware — and it's the kind of thing that's ten times more expensive to retrofit once
every icon button ships without one.

**Recommendation:** add `eslint-plugin-jsx-a11y` to the lint config (catches new instances going
forward for free) and do one sweep adding `aria-label` to existing icon-only buttons.

### 1.6 — Frontend test coverage is thin [P1, effort M]

**Current state:** outside `node_modules`, the entire frontend has exactly one test file —
`src/lib/sse.test.ts` — plus one Python-adjacent unit test (`tests/unit/jdQuality.test.ts`).
Vitest is already configured (`npm run test:vitest`) but essentially unused for components. None
of the 8 screens/components — including the status-transition stepper in `JobDetailPanel` that
feeds real application data — have any test coverage.

**Recommendation:** don't try to backfill everything at once. Start with the highest-blast-radius
logic: `shared/domain/jobPipeline.ts` and `shared/domain/interviewDebrief.ts` (used by both
frontend and backend, so a bug there is a double bug), then the status-stepper logic in
`JobDetailPanel`.

### 1.7 — No client-side routing / URL state [P2, effort M]

**Current state:** `activeTab` lives in `App.tsx`'s bare `useState`, no `react-router` (or any
router) in `package.json`. Refreshing the browser always returns to Dashboard; there's no way to
deep-link to "Opportunities filtered to Interviews" or a specific job.

**Recommendation:** low urgency for a single-user local tool where you're never sharing a link —
but if you ever want the URL to reflect state (e.g. bookmarking a filtered Opportunities view,
or the browser back button undoing a job-panel open), a lightweight router or URL-search-param
sync is the standard fix. Not worth doing proactively; worth doing the next time the lack of it
actually causes friction.

### 1.8 — No request-body schema validation on the server [P2, effort M]

**Current state:** `server/middleware.ts` has hand-rolled, narrow guards (`isValidJobId`,
`isSafeHttpUrl`) but no general schema validation layer for POST/PATCH bodies. `zod` exists in
`node_modules` only as someone else's transitive dependency — it's not used anywhere in `server/`.

**Recommendation:** add `zod` schemas on the highest-risk write routes first (`/api/profile/*`,
job creation) rather than a blanket rewrite — this is the standard modern pattern (parse at the
boundary, trust the typed result everywhere downstream) and pairs naturally with the existing
TypeScript-strict setup.

---

## 2. Per-screen findings

Most per-screen issues are just instances of §1 above (every screen inherits the polling and
error-boundary gaps). This section only lists things specific to that one screen.

| Screen | Finding | Priority |
|---|---|---|
| **Dashboard** ([`TodayView.tsx`](../src/pages/TodayView.tsx)) | Derives 4+ filtered/sorted lists (Ready to Apply, Active Opportunities, Upcoming Interviews, stat tiles) from the same `jobs` array on every 5s poll tick, with no `useMemo` — recomputes even when `jobs` hasn't meaningfully changed. Cheap to fix once §1.1 lands. | P2 |
| **Opportunities** ([`AllJobsView.tsx`](../src/pages/AllJobsView.tsx)) | No list virtualization. Fine at current job volume; flag only as a scaling watch-item if the kanban ever holds hundreds of cards per column. The dismissible "New from scout" banner being session-only (no localStorage) reads as a deliberate choice per the doc, not a defect — no action. | Watch-item, not actionable now |
| **Job Search** ([`SyncActivityView.tsx`](../src/pages/SyncActivityView.tsx)) | Uses a hand-rolled SSE buffer parser ([`sse.ts`](../src/lib/sse.ts)) instead of native `EventSource` — almost certainly because `EventSource` can't send the custom `X-Applyr-Token` header, which is a legitimate reason, not a smell. Native `EventSource` gets free auto-reconnect-with-backoff; a hand-rolled client has to implement that itself. Worth a quick verification pass (not read in full here) that `connectSSE()` actually reconnects with backoff on a dropped connection, since that's easy to silently miss when building SSE by hand. | P2 (verify only) |
| **Tuning Log** ([`TuningLogView.tsx`](../src/pages/TuningLogView.tsx)) | Read-only screen, no write paths, nothing found. | — |
| **Settings** ([`SettingsView.tsx`](../src/components/SettingsView.tsx)) | Covered by §1.3 (secrets). No client-side field validation before POSTing connector settings (e.g., a malformed Adzuna App ID isn't caught until the connector fails later) — minor. | P2 |
| **Job Detail Panel** ([`JobDetailPanel.tsx`](../src/components/JobDetailPanel.tsx)) | Largest component in the frontend (1219 lines), 10 sections, no internal decomposition — a local state change anywhere re-renders the whole panel, and it's the single hardest file to unit-test as-is. Natural candidate to split into one subcomponent per section (Status, Interview, Contacts, Debrief, Match Summary, Skill Gap, Assets, Logs), which would also make the error-boundary and test recommendations in §1.2/§1.6 much cheaper to apply. | P1 |
| **Document Editor** ([`DocumentEditor.tsx`](../src/components/DocumentEditor.tsx)) | No `dangerouslySetInnerHTML` anywhere in `src/` (checked repo-wide) — reassuring, no obvious client-side XSS vector from the AI Rewrite path. The PDF-compile step lives in Python (`compile_single.py`), outside this frontend-focused review's grounding — worth a separate look if you want that path checked too, not flagged as a finding here. | — |
| **Status Chip** ([`StatusChip.tsx`](../src/components/StatusChip.tsx)) | Single-source-of-truth mapping (`STATUS_CONFIG`) is exactly the pattern best practice recommends for this kind of enum-to-label translation. No change needed. | — |
| **API route table** (§4 of the feature map) | Route files are already grouped by domain (system/jobs/profile/pipeline/sources/contacts/gmailSync), which matches REST best practice — no restructuring recommended. | — |

---

## 3. Prioritized roadmap

| # | Item | Priority | Effort |
|---|---|---|---|
| 1 | Require `APPLYR_API_TOKEN` when bound to `0.0.0.0`; mask API keys in any GET response | P0 | S |
| 2 | Add `helmet()` + a per-IP rate limiter to the Express app | P1 | S |
| 3 | Add root + widget-level React error boundaries (App shell, JobDetailPanel, DocumentEditor) | P1 | S |
| 4 | Migrate `useJobs` (then other hooks) to TanStack Query | P1 | M |
| 5 | Add component tests for `shared/domain/*` and JobDetailPanel's status stepper | P1 | M |
| 6 | Decompose `JobDetailPanel.tsx` into per-section subcomponents | P1 | M |
| 7 | Add `eslint-plugin-jsx-a11y` + sweep icon-only buttons for `aria-label` | P2 | S |
| 8 | Add `zod` schema validation on highest-risk POST/PATCH routes | P2 | M |
| 9 | `useMemo` the Dashboard's derived lists | P2 | S |
| 10 | Evaluate OS-keychain storage for the 5 provider API keys | P2 | L |
| 11 | Verify SSE client reconnect/backoff behavior in `sse.ts` / `connectSSE()` | P2 | S (verification) |
| 12 | URL-synced routing / deep-linkable tab-filter-job state | P2 | M |

---

## Sources

- [React Query vs useEffect: 2026 Data Fetching Best Practices](https://weblogtrips.com/programming-languages/web-development/react-query-vs-useeffect-best-practices-2026/)
- [Stop Using useEffect for Data Fetching: Why TanStack Query is a Game Changer in React](https://medium.com/@benjaminalladi10/stop-using-useeffect-for-data-fetching-why-tanstack-query-is-a-game-changer-in-react-00cec36d6336)
- [The Pitfalls of Manual Data Fetching with useEffect — Leapcell](https://leapcell.io/blog/the-pitfalls-of-manual-data-fetching-with-useeffect-and-why-tanstack-query-is-your-best-bet)
- [The secure way to store secrets on iOS devices — Securing](https://www.securing.pl/en/the-secure-way-to-store-secrets-on-ios-devices/)
- [macOS Keychain Tutorial for Developers — Store API Keys the Right Way](https://noboxdev.com/blog/macos-keychain-tutorial-for-developers)
- [helmet vs cors vs express-rate-limit for Express Security (2026) — PkgPulse Guides](https://www.pkgpulse.com/guides/helmet-vs-cors-vs-express-rate-limit-express-security-2026)
- [Node.js Security Basics: Rate Limiting, Sanitization & Helmet — Prateeksha Web Design](https://prateeksha.com/blog/nodejs-security-basics-rate-limiting-input-sanitization-helmet-setup)
- [Using server-sent events — MDN](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)
- [Server-Sent Events: A Practical Guide for the Real World](https://tigerabrodi.blog/server-sent-events-a-practical-guide-for-the-real-world)
- [How to Implement Error Boundaries for Graceful Error Handling in React](https://oneuptime.com/blog/post/2026-01-15-react-error-boundaries/view)
- [Robust React Applications: Preventing Crashes with Error Boundaries — Leapcell](https://leapcell.io/blog/robust-react-applications-preventing-crashes-with-error-boundaries)
