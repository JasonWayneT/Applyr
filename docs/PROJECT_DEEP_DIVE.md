# Project Deep Dive: Applyr — Curated Job Hunt Agent

> **Purpose**: Learning-focused technical analysis of the Applyr codebase. Every claim is anchored to a specific file, function, or line number. This document is honest about anti-patterns, accidental decisions, and technical debt.

---

## PART 0: PROJECT COMPLEXITY SNAPSHOT

- **Total Files**: ~60 project files (excluding node_modules, archive, OpenPostings-extracted)
- **Major Components**: 5 — React frontend, Express API server, Python pipeline engine, TypeScript scout engine, SQLite database
- **External Dependencies**: 4 critical — Gemini API, Claude API, Perplexity API (all optional with fallback), Adzuna Job API (optional)
- **Backend Presence**: Yes — Express server on localhost:3000, synchronous SQLite via better-sqlite3
- **LLM Usage**: Batch processing after scout runs (scoring + drafting), background on experience save (summary generation), on-demand for document AI rewrite. Never in the hot path of UI interactions.
- **Development Timeline**: Ongoing multi-month build, versioned from v1 through v5.17 at time of writing
- **Builder's Skill Level**: Intermediate-advanced full stack; strong on backend orchestration and Python pipeline; frontend competent but not expert
- **Primary Tech Stack**: React 19, TypeScript, Vite, Express, better-sqlite3, Python 3.10+, Playwright, TailwindCSS

---

## PART 1: EXECUTIVE OVERVIEW

### 1.1 What This Actually Does (User Perspective)

**Core User Flow**:
1. User configures target role, blocklists, salary floor, and LLM API keys via a settings UI
2. User pastes their full work history into an experience editor; system auto-assigns ACC/VOC/MET proof codes
3. User triggers a scout run — headless browser + 7 API sources scrape new job postings matching their criteria
4. Each job is scored against the user's profile by an LLM (zero-token pre-filter runs first)
5. Roles scoring above threshold get a company research packet, then a tailored resume, cover letter, and interview cheat sheet auto-drafted and compiled to PDF
6. User reviews assets in a WYSIWYG editor, edits with AI assistance, then tracks the role through 6 lifecycle stages to Applied/Closed

**Primary Value Delivered**: Eliminates the 80% of job search effort that is wasted on poor-fit roles and generic documents. A user with a configured profile can go from "scout triggered" to "PDF-ready tailored application" with zero manual effort per job.

**Usage Pattern**: Solo, local-only, triggered manually. One user. Scout runs on-demand, not scheduled. The typical session is: trigger scout → review dashboard for new matches → edit one or two assets → mark as applied.

### 1.2 What Problem This Solves

**The Pain Point**: Job searching at scale requires applying to many roles with tailored documents. Both parts are painful in isolation — sourcing (finding relevant roles across many sites) and tailoring (customizing resumes without hallucinating credentials). Together they make high-volume quality search impractical by hand.

**Why Existing Solutions Weren't Used**:
- LinkedIn Easy Apply produces generic applications, no document tailoring
- Resume builders (Resumake, Canva) require manual per-role editing
- Job aggregators (Indeed, Glassdoor) have no fit scoring or document generation
- Commercial AI resume tools (Teal, Rezi) are subscription SaaS, send your career data to their servers, and don't integrate scouting with drafting into one pipeline

**Target User**: A mid-career technical individual contributor actively job searching who: (a) has a strong but nuanced work history that doesn't translate well to generic templates, (b) is comfortable running a local dev environment, (c) applies to 10-30 roles per month and wants each one properly tailored.

### 1.3 Project Origin Story

**Initial Idea**: A LinkedIn scraper that would collect job posts matching a specific role. Simple Playwright automation.

**Scope Evolution**: Expanded significantly through versioned CRs. The scouting layer grew from 1 source (LinkedIn) to 8. The scoring layer was added when raw scraping produced too much noise. The drafting layer was added when scoring identified good roles but manual tailoring was still the bottleneck. The UI was added when managing everything via CLI/files became unwieldy.

**Key Pivots**:
- CR-001: Moved from Playwright-only scraping to a hybrid pipeline (APIs + Playwright)
- CR-003: Collapsed four disconnected preference UIs into one materialized JSON pipeline (ADR-005)
- CR-005: Moved all API key management from `.env` to SQLite + UI (triggered by security concern about accidental git commits of keys)
- CR-006: Replaced single-provider LLM with a fallback chain after recognizing that any provider outage would silently kill the pipeline

---

## PART 2: ARCHITECTURAL OVERVIEW

### 2.1 System Architecture

```
User Browser (React App — localhost:5173)
    ↓ HTTP / SSE (Server-Sent Events for streaming)
Express API Server (localhost:3000 — server/index.ts + server/routes/)
    ↓ better-sqlite3 (synchronous, no async/await)
SQLite Database (jobagent.sqlite — 5 tables)
    ↓ spawn() child_process
    ├── TypeScript Scout Engine (scripts/scout_local.ts via npx tsx)
    │       ↓ HTTP APIs
    │       └── 7 Job Sources (LinkedIn Playwright, BuiltIn Playwright, RemoteOK,
    │                          Remotive, WWR RSS, Himalayas, The Muse, Adzuna)
    ├── TypeScript Backfill (scripts/archive/backfill_urls.ts)
    ├── TypeScript Scraper (scripts/scrape_new_jobs.ts)
    └── Python Pipeline (scripts/batch_pipeline.py via python)
            ↓ import
            ├── scripts/drafting_engine.py
            │       ↓ subprocess
            │       └── scripts/research-engine.py
            ├── scripts/generate_cheat_sheet.py
            ├── scripts/compile_single.py (Playwright headless PDF)
            └── scripts/utils.py → LLM API calls (Gemini / Claude / Local / Perplexity)
                                   with fallback chain
```

The server never awaits Python processes — they run as detached child processes writing progress to stdout, which the server captures and inserts into the `activity_log` table. The frontend polls `GET /api/logs` and `GET /api/system-status` to surface progress.

### 2.2 Technology Stack

| Technology | Why This | What Was Rejected | Trade-off Accepted |
|---|---|---|---|
| **React 19** | Familiar, mature component model; Vite gives instant HMR | Next.js (overkill for localhost SPA), Vue (familiarity) | Client-side only — no SSR, no SEO |
| **SQLite + better-sqlite3** | Single-user local app, synchronous API matches Express request handlers cleanly, zero ops overhead | PostgreSQL (multi-user ops overhead, requires running service), MongoDB (no joins for stats queries) | No concurrent write safety, file-level locking, not portable to multi-user |
| **Express** | Minimal boilerplate, spawn() integration straightforward | FastAPI (Python, would mean mixing runtime boundaries further), Next.js API routes (tied to Vercel deployment model) | Manual route management, no type safety on endpoints |
| **Python (pipeline)** | `google-generativeai`, `anthropic`, `playwright` all have mature Python SDKs; PDF generation via Playwright Python is more battle-tested | Node.js pipeline (would need to rewrite all LLM integrations, PDF compilation is harder) | Cross-language boundary adds spawn() overhead and stdout parsing complexity |
| **Playwright (scout + PDF)** | Headless Chrome gives pixel-perfect PDFs from styled HTML/Markdown; also used for authenticated LinkedIn scraping | Puppeteer (less maintained), wkhtmltopdf (poor CSS support), pdfkit (programmatic, loses styling) | Heavy install (~300MB Chromium), slow cold start |
| **TailwindCSS** | Rapid UI prototyping, no context-switching to CSS files | CSS Modules, styled-components | Utility class sprawl in JSX, harder to read components |
| **Vite** | Fast HMR, handles TS/React out of the box | CRA (deprecated), Webpack (config overhead) | Non-standard for some legacy patterns |

### 2.3 File/Folder Structure

```
server/           — Express server lives here, NOT in src/
  index.ts        — 33 lines: middleware setup, router mounts, app.listen()
  shared.ts       — Path constants (PROJECT_ROOT, SCRIPTS_DIR, SUBMISSION_DIR, etc.),
                    buildPythonEnv(), resolveCompanyFolder(), materializeJobSearchPrefs()
  scout.ts        — Scout orchestrator: chains scout → backfill → scrape → evaluate
  db.ts           — SQLite init + logActivity. Schema-on-boot, idempotent.
  routes/
    system.ts     — /api/system-status, /api/ats-pipeline, /api/logs
    jobs.ts       — All /api/jobs/* (CRUD, file serve, AI rewrite, ZIP download, manual draft)
    profile.ts    — /api/profile/*, /api/experience (includes codifyExperienceAndAssignIDs)
    pipeline.ts   — /api/evaluate (SSE streaming), /api/sync

scripts/          — Python and TypeScript pipeline scripts
  *.py            — Python pipeline: batch_pipeline, drafting_engine, research-engine, utils
  *.ts            — TypeScript scouts: scout_local.ts, scrape_new_jobs.ts, backfill_urls.ts
  archive/        — Old scripts preserved but not in main flow (backfill_urls.ts is exception)
  scratch/        — One-off debug scripts (gitignored via scratch/ rule)

src/              — React frontend
  App.tsx         — Root router, 5-second job poll, status change handler
  pages/          — Full-page views (TodayView, AllJobsView, etc.)
  components/     — Reusable components (JobDetailPanel, DocumentEditor, SettingsView, etc.)
  lib/api.ts      — Single helper: constructs API base URL from env
  types/job.ts    — Shared Job interface
  hooks/          — usePipeline.ts

data/             — User data files (gitignored or carefully managed)
  candidate_preferences.json   — Materialized output from server; never edited directly
  workExperience.md            — Source of truth for all LLM claims
  workExperience_summary.md    — Auto-generated condensed scoring brief
  job_fit_engine.md            — Scoring rules and anchor criteria (manually maintained)
  Resume.md, Cover_Letter_Reference.md — Master templates (manually maintained)
```

**Key organizational decision**: `server/` is separate from `src/` to make the TypeScript compilation boundary clear. Vite compiles `src/` for the browser; `server/` is run directly with `tsx` (no compilation step). This means the server can use Node APIs freely without worrying about browser compatibility.

---

## PART 3: CONSTRAINT PROFILE

### 3.1 Time Constraints
- **Timeline**: Ongoing over multiple months, built in iterative releases (v1 through v5.17)
- **Speed vs Quality Trade-offs**: Prompt engineering was done empirically (try → observe → adjust) rather than systematically benchmarked. The codification engine (`codifyExperienceAndAssignIDs` in `server/routes/profile.ts`) was written for correctness, not performance — it re-scans the entire file on every save.
- **Shortcuts Taken Knowingly**: The Python pipeline uses `print()` to stdout for inter-process communication rather than a proper IPC mechanism. (The `server/index.ts` monolith was also a known shortcut — resolved May 2026 via router split.)

### 3.2 Skill Constraints
- **Technologies Known Well**: Python, Express, React, SQLite, Playwright
- **Technologies Learned On-The-Fly**: SSE (Server-Sent Events for streaming pipeline progress), better-sqlite3 synchronous API patterns, Playwright PDF generation quirks
- **Knowledge Gaps That Shaped Design**: No background in job queuing systems (BullMQ, Celery) — explains why all pipeline stages are chained via sequential `on('close')` callbacks in `server/scout.ts` rather than a proper queue. No background in stream processing — explains why stdout from Python processes is parsed line-by-line with prefix conventions (`[LOG]`, `[FOUND]`, `[DONE]`) rather than structured JSON streaming.

### 3.3 Tooling & Infrastructure Constraints
- **Available Tools**: Local machine only (Windows 11), existing Python environment, Node 18+
- **Cost Constraints**: Free tiers for all APIs where possible. Gemini Flash chosen specifically for its generous free tier. Adzuna capped at 10 calls/run (250/day free tier limit). Token budgeting built into pipeline (`SCORING_JD_MAX_CHARS = 1500` in `utils.py:41`, two-stage scoring with summary-first).
- **Deployment Constraints**: Local-only by design. No cloud hosting, no CI/CD. Career data privacy is an explicit constraint — data must not leave the local machine except for API calls the user explicitly configures.

### 3.4 Scale Assumptions
- **Expected Users**: 1 (the builder)
- **Data Volume**: Hundreds of jobs per month, ~1-2GB of submissions/PDFs over a long job search
- **Performance Requirements**: Sub-10-second UI responses (everything except scout runs). Scout runs are expected to take 5-20 minutes — acceptable because they run in the background.

**How These Constraints Shaped the Architecture**:
- Single user + local-only → SQLite instead of PostgreSQL (zero ops overhead)
- Privacy constraint + single user → no auth, no sessions, no multi-tenancy
- Free tier cost constraint → two-stage scoring (deterministic keyword gate first, LLM only if signals present), JD character truncation, summary-based scoring instead of full-file
- No queue system knowledge → sequential chained spawns in `scout.ts` (simpler but no parallelism or retry isolation)

---

## PART 4: DECISION LEDGER

#### Decision #1: Local-First Architecture

**Context**: The app stores a user's full work history, target companies, and job search strategy. This is sensitive career intelligence. A cloud architecture would require hosting this on external servers.

**Options Considered**:
1. **Cloud SaaS** (Vercel + Supabase): Standard modern stack
   - Pros: Accessible anywhere, shareable, deployable
   - Cons: Career data stored on third-party servers, recurring cost, auth complexity, vendor lock-in
2. **Electron App**: Packaged local desktop app
   - Pros: True desktop app with file system access, no browser security restrictions
   - Cons: Heavy bundle (~150MB), Electron expertise needed, platform-specific builds
3. **Local Dev Server (Chosen)**: Express + React served locally, user runs `npm run dev`
   - Pros: Zero packaging complexity, full file system access, simple to develop, privacy guaranteed
   - Cons: Requires Node/Python installed, no "just download and run" UX, port conflicts possible

**Why This Won**: Privacy constraint was non-negotiable. Developer skill set aligned with web stack. Single user means zero multi-tenancy complexity. The target user (technical job seeker who can clone a repo) is comfortable with `npm run dev`.

**Trade-offs Accepted**: Non-technical users cannot use this. No mobile. No sharing. No access from multiple machines.

**Revisit Conditions**: If the project ever targets non-technical users or if a multi-device use case emerges.

---

#### Decision #2: SQLite Over PostgreSQL

**Context**: Need persistent storage for jobs, activity logs, user settings, and pipeline state.

**Options Considered**:
1. **PostgreSQL**: Production-grade relational DB
   - Pros: Concurrent writes, full SQL, mature tooling
   - Cons: Requires a running service, connection pooling setup, overkill for 1 user
2. **JSON Files**: Plain files for each data type
   - Pros: Zero dependencies, human-readable
   - Cons: No querying, no atomic writes, race conditions with concurrent pipeline processes
3. **SQLite via better-sqlite3 (Chosen)**
   - Pros: Zero ops overhead, synchronous API eliminates async/await boilerplate in Express handlers, single file, full SQL for stats queries
   - Cons: Single writer, file-level locking (not a problem at this scale), no native JSON column type

**Why This Won**: `better-sqlite3`'s synchronous API was the tipping point. Express route handlers that do `db.prepare(...).run()` are cleaner and easier to reason about than async `await pool.query(...)` chains. The single-user constraint meant write contention was never a concern.

**Trade-offs Accepted**: If two processes try to write simultaneously (e.g., scout + manual status update), SQLite serializes them via locking. At this scale this is fine; at scale it would be a problem.

**Revisit Conditions**: If multiple users, if write throughput > ~100/second, if data volume > ~50GB.

---

#### Decision #3: Python Pipeline as Separate Process

**Context**: LLM orchestration, PDF compilation, and document drafting need to happen without blocking the Express server.

**Options Considered**:
1. **Inline Node.js LLM calls**: Use `@google/generative-ai` npm package directly in Express
   - Pros: Single runtime, no spawn overhead, proper async/await
   - Cons: Python has better-maintained LLM SDKs; Playwright PDF in Python is more stable; would require rewriting all existing Python scripts
2. **Separate Python microservice**: FastAPI server that Express calls via HTTP
   - Pros: Proper inter-process communication, restartable independently
   - Cons: Port management, service discovery, startup ordering complexity
3. **Spawn child processes (Chosen)**: `spawn('python', ['scripts/batch_pipeline.py'])` from Express
   - Pros: Simple, no additional services, stdout capture gives real-time log streaming, no shared memory concerns
   - Cons: Stdout parsing is fragile (relies on `[LOG]`, `[FOUND]` prefix conventions), no proper error propagation, can't easily cancel mid-run

**Why This Won**: All the LLM and PDF logic already existed in Python. Rewriting in Node would have been a net regression. The spawn pattern gave "good enough" IPC for a single-user app.

**Trade-offs Accepted**: Stdout parsing fragility. No mid-run cancellation. Process exit code is the only reliable error signal.

**Revisit Conditions**: If structured streaming output is needed, or if the pipeline needs cancellation support.

---

#### Decision #4: Materialized JSON for Pipeline Config (ADR-005)

**Context**: The Python pipeline needs to know the user's search terms, blocklists, score threshold, and other preferences. These are set via the UI and stored in SQLite. But Python can't easily read SQLite without a connection.

**Options Considered**:
1. **Pass everything as CLI args**: `python batch_pipeline.py --role "PM" --blocklist "Senior,VP" ...`
   - Pros: No file dependency
   - Cons: Args get unwieldy with 10+ settings; shell escaping nightmares on Windows
2. **Python reads SQLite directly**: `sqlite3.connect('jobagent.sqlite')` in Python
   - Pros: Single source of truth
   - Cons: Two concurrent connections to same SQLite file, Python needs DB schema knowledge
3. **Materialized JSON file (Chosen)**: Server writes `data/candidate_preferences.json` whenever settings change. Python reads this file.
   - Pros: Decoupled (Python doesn't know about SQLite), human-readable, diffable, easy to debug
   - Cons: Two sources of truth (SQLite profiles + JSON file), possible drift if server crashes mid-write

**Why This Won**: Clean separation of concerns. The JSON file is a cache/projection of the SQLite state. The server owns the write path; Python owns the read path. No cross-language DB connection needed.

**Trade-offs Accepted**: Drift risk if the server writes preferences to SQLite but fails before materializing JSON. In practice this hasn't been an issue because the materialization is synchronous and immediately follows the SQLite write.

**Revisit Conditions**: Never — this pattern is correct for this architecture.

---

#### Decision #5: LLM Provider Fallback Chain (CR-006)

**Context**: Original design had a single provider field in `llm_settings`. If Gemini was set and the API was down or quota-exhausted, every LLM call would silently return `""` and jobs would be skipped without explanation.

**Options Considered**:
1. **Single provider, hard fail**: Error loudly if provider fails
   - Pros: Clear failure signal
   - Cons: A rate limit at 2am kills the entire overnight scout run
2. **User manually switches provider**: Settings UI for active provider
   - Pros: User in control
   - Cons: Requires user to notice the failure and intervene
3. **Automatic fallback chain (Chosen)**: `_get_configured_providers()` in `utils.py` returns providers in order (primary first, then fixed order). `call_llm()` iterates them, falling through on non-rate-limit errors.
   - Pros: Pipeline survives single provider outages. Rate limits retry within provider. Zero user intervention.
   - Cons: Harder to debug (which provider actually ran?). Inconsistent model behavior across providers.

**Why This Won**: The pipeline runs unattended, often during hours when the user isn't watching. Silent recovery is more valuable than explicit failure in an unattended context.

**Trade-offs Accepted**: A job might be scored by Gemini and a second job by Claude in the same batch run, producing inconsistent scoring behavior. Logged to activity_log as `[LLM] Falling back from gemini to claude...` but easy to miss.

**Revisit Conditions**: If audit trails of which provider scored which job become important.

---

#### Decision #6: Proof Code Anti-Hallucination System

**Context**: LLMs hallucinate credentials. A naive "write me a resume" prompt will invent metrics, tools, and accomplishments. For a job application, this is a career risk.

**Options Considered**:
1. **Post-generation verification**: Generate resume, then check claims against source
   - Pros: Separates concerns
   - Cons: Requires a second LLM call; catching hallucinations after generation is harder than preventing them
2. **Strict prompt constraints**: Tell the LLM "only use facts from this document"
   - Pros: Simple
   - Cons: LLMs reliably ignore this instruction under token pressure
3. **Proof code system (Chosen)**: Every claim in `workExperience.md` gets a stable code (`ACC-101`, `VOC-01`, `MET-03`). The drafting prompt requires every claim in the output to cite a code. The claim verifier validates this post-generation.
   - Pros: Structurally prevents hallucination — if no code exists, the claim cannot be made
   - Cons: High setup cost for the user (must codify their experience), brittle to badly-formatted input

**Why This Won**: The structural constraint is more reliable than a prompt constraint. This was the founding design decision that differentiated Applyr from "just call ChatGPT with my resume."

**Trade-offs Accepted**: User must invest time in writing a well-formatted, codified work experience document before the pipeline produces useful output. There is no shortcut. The `workExperience_summary.md` auto-generation (FR-064) reduces ongoing maintenance but the initial setup remains manual.

---

#### Decision #7: Two-Stage Scoring (Zero-Token Gate + LLM)

**Context**: In a batch run, the pipeline might process 50-100 job descriptions. Each LLM scoring call costs tokens and time. Many jobs will be obvious rejects (wrong title, wrong seniority, wrong location).

**Options Considered**:
1. **LLM for everything**: Pass every JD to the LLM
   - Pros: Most accurate
   - Cons: 50 LLM calls per batch run, token cost, 5-10 minutes of API time
2. **Zero-token gate only**: Deterministic keyword filter, no LLM
   - Pros: Free, instant
   - Cons: Misses nuance — a JD titled "Product Manager" for a growth/consumer role would pass the keyword gate
3. **Two-stage (Chosen)**: Zero-token keyword gate (`passes_jd_keyword_gate()` in `batch_pipeline.py:17`) eliminates obvious mismatches. LLM scoring (`evaluate_job_fit()` at line 33) runs only on jobs that pass the gate. Full workExperience.md loaded only on LLM YES decision.
   - Pros: Token cost roughly proportional to signal quality. Real-world: ~70% of jobs are gated out before any LLM call.
   - Cons: Gate might reject a relevant job whose title is unusual

**Why This Won**: Cost constraint. Gemini Flash free tier has limits. Burning them on obvious rejects was wasteful.

**Trade-offs Accepted**: False negative risk at the gate layer. Mitigated by keeping the gate broad (keyword presence, not keyword match score) and truncating JDs at 1500 chars rather than rejecting on length.

---

#### Decision #8: Modular Express Router Architecture (May 2026)

**Context**: `server/index.ts` had grown to 844 lines containing all 24 routes, helper functions (`buildPythonEnv`, `resolveCompanyFolder`, `materializeJobSearchPrefs`, `codifyExperienceAndAssignIDs`), and business logic. A duplicate copy of the API key-reading logic also existed in `server/scout.ts`. Navigation, AI-assisted editing, and domain isolation were all suffering.

**Options Considered**:
1. **Keep the monolith**: No change — it works, refactor is churn
   - Pros: Zero risk, zero effort
   - Cons: Grows unboundedly; AI editing context window fills with irrelevant routes; duplicate logic compounds
2. **Controllers pattern** (`server/controllers/*.ts`): One controller per resource
   - Pros: Standard MVC naming
   - Cons: Controller files are just thin pass-throughs without a service layer — adds a layer without real separation
3. **Express Router split (Chosen)**: Four router files grouped by domain, one shared module for utilities
   - Pros: Each file is independently navigable and editable; shared utilities live in exactly one place; `index.ts` is now the entry point only (33 lines)
   - Cons: More files to import; circular import risk if shared module imports from a router (avoided by keeping shared.ts free of route logic)

**Why This Won**: Modularity preference (explicit project goal). The domain boundaries were already obvious (system health, job CRUD, profile/experience, pipeline triggers) — this just enforced them in the file system. The `shared.ts` extraction also eliminated a latent bug: `/api/jobs/:id/draft` was missing `buildPythonEnv()`, so manual draft triggers never had API keys injected.

**What's in each file**:
- `server/shared.ts` — `buildPythonEnv()`, `resolveCompanyFolder()`, `materializeJobSearchPrefs()`, all path constants. Imported by all route files and `scout.ts`.
- `server/routes/system.ts` — `/api/system-status` (GET/POST), `/api/ats-pipeline`, `/api/logs`
- `server/routes/jobs.ts` — All `/api/jobs/*` routes: list, create, stats, status transitions, file CRUD, AI rewrite, ZIP download, manual draft
- `server/routes/profile.ts` — `/api/profile/job_search`, `/api/profile/:key`, `/api/experience` (includes `codifyExperienceAndAssignIDs`)
- `server/routes/pipeline.ts` — `/api/evaluate` (SSE stream), `/api/sync`

**Trade-offs Accepted**: Five files to open instead of one when debugging an unfamiliar route. Mitigated by naming that makes the domain obvious.

**Revisit Conditions**: If a service layer is needed (business logic that's shared between multiple routes), extract `server/services/*.ts` at that point.

---

## PART 5: DATA MODELING & SCHEMA DESIGN

### 5.1 Core Data Entities

#### Entity: `jobs` (SQLite table — `server/db.ts:12`)

**Purpose**: The canonical record of every discovered or manually added job opportunity.

**Schema**:
```sql
id TEXT PRIMARY KEY          -- UUID (randomUUID() in server/routes/jobs.ts)
company TEXT NOT NULL        -- Denormalized company name (scout writes this directly)
title TEXT NOT NULL          -- Job title as scraped
url TEXT UNIQUE              -- Source URL; UNIQUE constraint deduplicates scout runs
score INTEGER                -- 0-100 fit score from LLM; NULL before evaluation
status TEXT DEFAULT 'Drafted' -- Lifecycle stage (see lifecycle section)
summary TEXT                 -- One-line LLM summary of the role
salary_range TEXT            -- Freeform (scraped or manually entered)
recruiter_name TEXT          -- Optional; manually entered after contact
recruiter_url TEXT           -- Optional; LinkedIn URL of recruiter
source_site TEXT             -- Which scout source found this (LinkedIn, Himalayas, etc.)
rejection_stage TEXT         -- At what stage was this closed
rejection_type TEXT          -- Rejected / Ghosted / Withdrew
outcome_notes TEXT           -- Freeform notes on outcome
interview_date DATETIME      -- Tracked for calendar awareness
created_at DATETIME          -- Auto-set on insert
```

**Design Decisions**:
- **Denormalized company name**: No separate `companies` table. Company is a string on the job record. Simpler queries, no joins for the job list. Cost: if company name is scraped inconsistently across runs, the same company may appear as "Acme Corp" and "Acme Corporation".
- **`url TEXT UNIQUE`**: The deduplication mechanism for the entire scout pipeline. `INSERT OR IGNORE` on URL means the same posting scraped twice doesn't create a duplicate job record. The UNIQUE constraint does the work that would otherwise require application-level dedup logic.
- **Freeform salary_range**: Not a structured `{ min, max, currency }`. Scraped salary strings vary wildly ("$120k-$150k", "Competitive", "DOE"). Storing as-is avoids a parsing problem that doesn't need to be solved for the UI use case.

---

#### Entity: `profiles` (SQLite table — `server/db.ts:40`)

**Purpose**: Key-value store for all user configuration. Functions as a document store within SQLite.

**Schema**:
```sql
key TEXT PRIMARY KEY   -- e.g., 'identity', 'llm_settings', 'job_search', 'api_connections'
value TEXT             -- JSON-serialized blob
```

**Design Decisions**:
- **KV over structured columns**: Configuration grows and changes frequently. A KV store means adding a new settings category doesn't require a schema migration — just a new key. The downside is no SQL-level validation of the JSON structure; validation happens at the application layer.
- **JSON values as TEXT**: SQLite has a JSON1 extension but better-sqlite3 doesn't expose it cleanly. Storing as TEXT and parsing in application code (`JSON.parse(row.value)`) is simpler.
- **Separation from `jobs` table**: Configuration and job data are conceptually distinct, even though they share a database. This makes `profiles` backups/exports independent of job history.

---

#### Entity: `activity_log` (SQLite table — `server/db.ts:31`)

**Purpose**: Append-only event log. The UI's "Terminal" view reads from this table. Pipeline progress is communicated via inserts to this table, not via WebSockets or SSE.

**Schema**:
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
level TEXT NOT NULL    -- INFO / WARN / ERROR
source TEXT NOT NULL   -- Scout / Pipeline / Scraper / System
message TEXT NOT NULL
meta TEXT              -- Optional JSON blob for structured data
```

**Design Decisions**:
- **Pull model, not push**: The frontend polls `GET /api/logs` on a 5-second interval (`App.tsx`). This is simpler than WebSockets but means log visibility has up to a 5-second lag. For a background process running over minutes, this is acceptable.
- **level + source as free-text strings**: No enum enforcement at the DB level. `logActivity()` in `server/db.ts:66` accepts any string. Consistency depends on callers using `'INFO' | 'WARN' | 'ERROR'` and known source strings (`'Scout'`, `'Pipeline'`, `'System'`).

---

### 5.2 Data Evolution & Migration

**Strategy**: None formally. The schema uses `CREATE TABLE IF NOT EXISTS` which is idempotent but doesn't handle column additions. If a new column is added to the `jobs` table, existing databases won't have it until manually migrated or the database is deleted and rebuilt.

**In practice**: New columns have been added by altering the `CREATE TABLE IF NOT EXISTS` statement in `server/db.ts`. Users with existing databases must either run `ALTER TABLE jobs ADD COLUMN ...` manually or delete `jobagent.sqlite` and let it rebuild (losing job history).

**Technical debt**: No migration system (e.g., no numbered migration files). This is acceptable for a solo-user app where the developer is the user, but would be a hard blocker for any public distribution.

### 5.3 Data Flow

```
User (Settings UI)
  → POST /api/profile/job_search
  → SQLite profiles table (key='job_search', value=JSON)
  → materializeJobSearchPrefs() in server/shared.ts
  → data/candidate_preferences.json (written to disk)
  → [Scout triggered] → scout_local.ts reads this file
  → New jobs written to SQLite jobs table
  → [Pipeline triggered] → batch_pipeline.py reads this file + workExperience.md
  → Score returned → SQLite jobs.score updated
  → Assets written to submissions/{company}/
  → PDFs compiled → submissions/{company}/*.pdf
  → [User opens detail panel] → GET /api/jobs/:id/files returns asset list
  → [User edits] → PUT /api/jobs/:id/files/:filename
  → style_compliance_guard.py → compile_single.py → PDF updated
```

---

## PART 6: FEATURE-BY-FEATURE DEEP DIVE

### Feature: Scout Pipeline (End-to-End)

#### 6.1 What It Does
User clicks "Run Scout" in the Job Search tab. Over the next 5-20 minutes, the system discovers new job postings from 7 sources, fetches their full descriptions, scores them against the user's profile, and generates PDF application assets for roles that pass. User sees live log output in a terminal-style view.

#### 6.2 Why It Exists
The core bottleneck in job searching is the discovery + filtering + tailoring loop. Scout automates the first two stages completely.

#### 6.3 Technical Implementation

```
POST /api/sync (server/routes/pipeline.ts)
  → server/scout.ts: runScoutSync()
    → buildExtraEnv() reads SQLite for all API keys
    → spawn('npx tsx scripts/scout_local.ts')
      → reads data/candidate_preferences.json
      → 7 parallel Promise.all() API calls
      → INSERT OR IGNORE into jobs table (URL dedup)
      → EXIT 0 on success
    → on('close', code 0):
      → spawn('npx tsx scripts/archive/backfill_urls.ts')
        → fills missing job URLs in jobs table
      → on('close'):
        → spawn('npx tsx scripts/scrape_new_jobs.ts')
          → fetches full JD text, writes to jobs/{company_uuid}.txt
        → on('close'):
          → spawn('python scripts/batch_pipeline.py --mode batch')
            → for each .txt in jobs/: score → draft if YES
          → on('close'):
            → UPDATE system_status SET status='completed'
```

**Key Functions**:
- **`runScoutSync()` in `server/scout.ts:9`**: Entry point. Reads all API keys from SQLite, builds environment vars, chains all four sub-processes.
- **`passes_jd_keyword_gate()` in `batch_pipeline.py:17`**: Zero-token filter. Checks first 200 chars for blocked titles, then checks full JD for at least one required keyword.
- **`evaluate_job_fit()` in `batch_pipeline.py:33`**: LLM scoring call. Truncates JD to `SCORING_JD_MAX_CHARS=1500`, sends summary + fit rules + preferences. Returns JSON with Score, Decision, TopFitReasons, RiskFlags.

#### 6.4 Implementation Decisions
- **Sequential chaining via `on('close')` callbacks**: Each stage must complete before the next starts. Scout must finish before scraping can begin (need URLs). Scraping must finish before pipeline (need JD text files). This is correct semantically but creates deeply nested callbacks in `scout.ts` (callback pyramid).
- **Environment injection at spawn time**: API keys read from SQLite → injected as env vars at spawn. Python's `load_dotenv()` doesn't override existing env vars, so injected values always win over any `.env` file.

#### 6.5 Failure Modes
- **Scout exits non-zero**: Logged as error, remaining stages skipped, `system_status` set to `idle`. No retry.
- **Playwright LinkedIn ban**: LinkedIn blocks automated access. The Playwright stealth plugin mitigates this but doesn't guarantee it. Failure is silent — the LinkedIn source returns 0 results rather than an error.
- **LLM rate limit during batch**: `call_llm()` retries within the same provider with escalating waits (60s, 120s, 180s...). This can make a batch run take hours if quota is exhausted. No per-job timeout means a single slow LLM call blocks the entire batch.
- **`candidate_preferences.json` missing**: `scout_local.ts` will use hardcoded defaults. **Fragile assumption**: both `scout_local.ts` and `batch_pipeline.py` assume this file exists and is valid JSON.

---

### Feature: Proof Code Anti-Hallucination System

#### 6.1 What It Does
User pastes raw work history in the Experience tab. The system auto-assigns stable proof codes (`[ACC-101]`, `**VOC-01**`, `**MET-01**`) to every claim. Generated resumes and cover letters must cite these codes. The LLM is structurally forbidden from inventing uncoded claims.

#### 6.2 Why It Exists
LLMs hallucinate metrics, tools, and accomplishments. In a job application context, fabricated credentials are a career risk. The proof code system creates an auditable chain from claim → source.

#### 6.3 Technical Implementation

**Code flow for save**:
1. User edits `workExperience.md` in the WYSIWYG textarea in `SettingsView.tsx`
2. `POST /api/experience` called with raw markdown
3. `codifyExperienceAndAssignIDs()` in `server/routes/profile.ts` scans the file, assigns IDs to untagged bold bullets in `### 5.N` sections, assigns VOC/MET IDs to table rows in Sections 3 and 4
4. Codified content written to `data/workExperience.md`
5. `generate_experience_summary.py` spawned as detached background process

**Key function**: `codifyExperienceAndAssignIDs()` in `server/routes/profile.ts`
- Scans existing IDs to seed counters above existing maxima (prevents collisions on re-save)
- Section 5.N maps to ID range `N×100+1` through `(N+1)×100` (employer-partitioned ID space)
- Lines containing `[RETIRED-ACC-NNN]` are preserved but not re-assigned

#### 6.5 Failure Modes
- **Badly formatted experience file**: If the user writes experience that doesn't follow the 5-section structure, codification produces no codes. The pipeline then runs with an empty proof code set, and the LLM has nothing to cite — resulting in either empty output or rule violations.
- **Retiring vs deleting**: If a user deletes a coded line instead of retiring it (`[RETIRED-ACC-101]`), future codification may re-assign that number to a different claim. This corrupts any existing document that cited the old code.

---

### Feature: LLM Provider Fallback Chain

#### 6.1 What It Does
When `call_llm()` is called in any Python script, it checks which providers are configured (have valid keys), orders them with the user's primary choice first, and iterates through them. Non-rate-limit errors skip to the next provider. Rate limits retry within the same provider.

#### 6.2 Technical Implementation

**Core functions in `scripts/utils.py`**:
- `_is_configured(provider, settings)` — checks for key presence in settings or env vars
- `_get_configured_providers(settings)` — returns ordered list, primary first; backward compat via `settings.get('primaryProvider') or settings.get('provider', 'gemini')`
- `_call_gemini()`, `_call_claude()`, `_call_local()`, `_call_perplexity()` — provider-specific callers returning `None` (try-next) or `str` (success)
- `call_llm()` — iterates providers, logs fallback transitions

**Key design**: Return value semantics. `None` means "this provider failed non-fatally, try next." `str` (even `""`) means "this provider responded, use this result." An empty string from a provider is treated as success (the prompt may have legitimately returned nothing).

#### 6.5 Failure Modes
- **All providers fail**: `call_llm()` returns `""`. Callers must handle empty string explicitly. In `batch_pipeline.py`, an empty scoring result causes the job to be skipped with an error log entry. But this is silent to the user — they see "0 jobs passed" with no explanation of why.
- **tools param on non-Gemini provider**: The `tools=[{"google_search": {}}]` parameter used by `research-engine.py` is only valid for Gemini. When falling back to Claude or Local, the tools param is intentionally dropped in `_call_claude()` and `_call_local()`. This means company research quality degrades on fallback (no web grounding).

---

### Feature: WYSIWYG Document Editor

#### 6.1 What It Does
User opens a PDF asset (resume, cover letter, cheat sheet) from the job detail panel. A full-screen overlay opens with the PDF preview on the left and a rich-text editor on the right. User edits, saves — the PDF regenerates automatically. An AI rewrite field accepts natural language instructions.

#### 6.2 Technical Implementation

```
DocumentEditor.tsx
  → GET /api/jobs/:id/files/:filename (loads Markdown source)
  → Toast UI WYSIWYG editor (toastui-editor)
  → PUT /api/jobs/:id/files/:filename
      → server/routes/jobs.ts
      → fs.writeFileSync(mdPath) — writes Markdown
      → exec('python scripts/style_compliance_guard.py ' + mdPath)
      → exec('python scripts/compile_single.py ' + mdPath + ' ' + pdfPath)
      → res.json({ success: true })
  → Client reloads PDF iframe src with cache-busting timestamp
```

**AI Rewrite** (`POST /api/jobs/:id/ai-rewrite` → `scripts/ai_rewrite.py`):
- Server writes instruction to `scratch/instr_{id}.tmp` and text to `scratch/text_{id}.tmp`
- `ai_rewrite.py` reads both, calls `call_llm()`, returns rewritten text to stdout
- Server captures stdout, returns to client

#### 6.5 Failure Modes
- **style_compliance_guard.py fails**: Server logs the error but still attempts compilation. The guard is advisory, not blocking.
- **Playwright PDF compilation fails**: Common on Windows if Chromium can't find the correct executable. The error surfaces as a 500 from the PUT endpoint. The Markdown is saved but no PDF is generated — the user sees their edit saved but the PDF preview doesn't update.
- **Large documents**: Playwright has a default timeout for PDF generation. Very long documents can timeout. No retry logic.

---

## PART 7: LLM INTEGRATION

### 7.1 Where LLMs Are Used

**Use Case #1: Job Fit Scoring** (`evaluate_job_fit()` in `batch_pipeline.py:33`)
- Model: User's primary provider (default: `gemini-2.5-flash`)
- Input: Candidate preferences JSON + workExperience_summary.md + truncated JD (1500 chars) + job_fit_engine.md rules
- Output: JSON `{ Decision, Score, Confidence, Summary, TopFitReasons, RiskFlags }`
- Cost estimate: ~3,000-4,000 input tokens, ~200 output tokens per call. At Gemini Flash pricing (~$0.075/1M input): ~$0.0003/call. 50-job batch ≈ $0.015.
- `response_mime_type="application/json"` is passed to constrain output format (Gemini-specific)

**Use Case #2: Asset Drafting** (`drafting_engine.py`)
- Model: User's primary provider
- Input: workExperience.md (full) + JD + company research + resume template + cover letter reference + style guides + claim verifier rules
- Output: Tailored resume Markdown + cover letter Markdown
- Cost estimate: ~8,000-15,000 input tokens per draft. ~$0.001-0.002/job at Gemini Flash rates. 10 qualified jobs/batch ≈ $0.02.

**Use Case #3: Company Research** (`research-engine.py`)
- Model: Perplexity `sonar-pro` if configured, else `call_llm()` with `tools=[{"google_search": {}}]` (Gemini-specific grounding)
- Input: Research Packet Contract + company + role
- Output: JSON matching contract modules A-F (mission, financials, competitors, etc.)

**Use Case #4: Experience Summary Generation** (`generate_experience_summary.py`)
- Model: User's primary provider
- Input: Full `workExperience.md` + structured prompt requesting specific 7-section output
- Output: Condensed `workExperience_summary.md` (~400-600 words)
- Triggered: Background spawn after every experience save

**Use Case #5: AI Document Rewrite** (`ai_rewrite.py`)
- Model: User's primary provider
- Input: User instruction + current document text
- Output: Rewritten document text
- On-demand, user-triggered

### 7.2 Prompt Engineering Decisions

**Scoring prompt** (in `batch_pipeline.py:40`):
```
You are the JobAgent Job-Fit Decision Engine.

CANDIDATE PREFERENCES:
{prefs_json}

GROUND TRUTH (Candidate Profile):
{work_exp_summary}

JOB DESCRIPTION (first 1500 chars):
{truncated_jd}

RULES & SCORING PROTOCOL:
{job_fit_rules}

Process the JOB DESCRIPTION using RULES & SCORING PROTOCOL.
First, check Fast Gate (Hard Disqualifiers). If disqualified, score < 30, Decision: NO.
Apply 100-point scoring criteria. Apply Two-Anchor rule.

Return ONLY valid JSON:
{ "Decision": "YES"/"NO", "Score": 0-100, "Confidence": "High"/"Medium"/"Low",
  "Summary": "...", "TopFitReasons": [...], "RiskFlags": [...] }
```

**Why this structure**: The rules file (`job_fit_engine.md`) is injected verbatim rather than summarized. This was an intentional choice — the rules are nuanced and any compression risks losing important scoring criteria. The prompt explicitly calls out sections ("GROUND TRUTH", "CANDIDATE PREFERENCES") to help the LLM navigate a long context.

**What was tried and failed**: An earlier prompt that asked the LLM to "evaluate fit holistically" produced inconsistent score distributions. Adding the explicit `job_fit_engine.md` rules file and specifying the JSON schema improved consistency dramatically.

### 7.3 LLM Output Handling

**Parsing**: `batch_pipeline.py:82-90`. The response is parsed as JSON. `response_mime_type="application/json"` is set for Gemini to force JSON output — but this parameter is Gemini-specific and is silently ignored by `_call_claude()` and `_call_perplexity()`. Those providers may still return markdown-wrapped JSON.

**Fallback parsing**: Lines 84-88 strip `\`\`\`json` and `\`\`\`` wrappers before parsing. This is a defensive measure for non-Gemini providers that ignore the JSON MIME type.

**Failure handling**: If `json.loads()` fails, the job is skipped with an error log entry. No retry on parse failure — the assumption is that a malformed JSON response is a prompt issue, not a transient error.

### 7.4 Prompt-to-Architecture Mapping

**Vibe Coding Artifacts**:
- The `job_fit_engine.md` rules file is a Markdown document injected directly into the scoring prompt. It's a prompt artifact masquerading as a configuration file. Changes to the rules file immediately change scoring behavior with no code change — this is intentional but means the rules are "code" that isn't version-controlled with the same rigor as actual code.
- The experience summary generator prompt (in `generate_experience_summary.py`) uses "exactly these headers" instruction — if the LLM doesn't comply, the resulting summary may not match what `batch_pipeline.py` expects. There's no structural validation of the generated summary.

### 7.5 Abstraction Drift

- **Thought**: "The scoring engine evaluates job fit"
- **Reality**: It evaluates fit against rules in a Markdown file that must be manually maintained to reflect the user's actual preferences
- **Gap**: The rules file is not connected to the settings UI. Changes to the user's blocklist in Settings update `candidate_preferences.json` and are used in the gate, but the LLM scoring rules in `job_fit_engine.md` remain static.

---

## PART 8: STATE MANAGEMENT

### 8.1 State Architecture

- **Frontend state**: React `useState` in each component. No global state manager (no Redux, no Zustand). `App.tsx` owns the jobs array and passes it as props. This works because the app has no complex shared state beyond the job list.
- **Backend state**: SQLite is the authoritative state. No in-memory caching layer. `system_status` table tracks pipeline state; `activity_log` tracks events.
- **Persistent state**: SQLite for all structured data; Markdown files for experience, resume, and cover letter templates; JSON file for materialized preferences.

### 8.2 State Flow

**Job status change**:
1. User clicks status badge in `JobDetailPanel.tsx`
2. `PATCH /api/jobs/:id/status` called
3. SQLite `jobs.status` updated
4. Server moves submission folder if status is `Applied` (`archive/submissions/`)
5. 5-second polling in `App.tsx` picks up the change on next tick
6. `JobDetailPanel` re-renders with new status

### 8.3 State Persistence

**What gets saved**: All job records, all settings, all activity logs.
**What is ephemeral**: Pipeline running status (reset to `idle` on server restart), draft SSE stream connections.

**Data Loss Scenarios**:
- Server restart during scout: `system_status` resets to `idle`. The pipeline process may still be running as a detached child. The UI loses visibility into it, but the process continues and jobs are still written to SQLite. The user would see new jobs appear but with no log output.
- Crash during PDF compilation: Markdown is written first (`fs.writeFileSync`), then PDF is compiled. If the server crashes between these, the edit is saved but the PDF is stale.

---

## PART 9: API DESIGN

### 9.1 Notable Endpoint Decisions

**`POST /api/evaluate` — SSE Streaming**

The single-job evaluation endpoint uses Server-Sent Events to stream pipeline progress. The client receives a series of JSON progress objects:
```json
{"id": "gate", "status": "running", "summary": "Checking keyword signals..."}
{"id": "fit", "status": "done", "summary": "Passed (Score: 82)"}
{"id": "resume", "status": "done", "summary": "ATS-Optimized PDF Generated"}
{"score": 82, "passed": true, "company": "Acme", "title": "PM"}
```

The SSE choice over WebSockets was purely pragmatic — SSE is built into `express` with no additional library, is one-directional (server to client), and maps cleanly to a "watch this process run" use case.

**`GET /api/profile/:key` + `POST /api/profile/:key` — Generic KV**

Rather than typed endpoints for each settings category, the profile API accepts any key. `GET /api/profile/llm_settings`, `POST /api/profile/identity`, etc. are all the same route handler. This means the frontend can add new settings categories without any server changes — just use a new key string.

Risk: No server-side schema validation. A malformed settings object will be stored and parsed at read time, with errors only visible when the setting is actually used (e.g., when a scout run reads `api_connections`).

**PATCH `/api/jobs/:id` — Allowlist**

Generic field update uses an explicit allowlist (`ALLOWED_JOB_FIELDS` in `server/shared.ts`). This prevents blind pass-through of arbitrary fields to the UPDATE statement, which would otherwise be an SQL injection risk through field name injection.

### 9.2 Error Handling

Most routes follow a try/catch pattern returning `{ error: 'message' }` on failure. No standardized error code system. Frontend components check for `response.ok` but rarely inspect the error body for user-facing messages.

---

## PART 10: PERFORMANCE & COST ANALYSIS

### 10.1 Performance Characteristics

**Latency Hotspots**:
- **Scout run**: 5-20 minutes total. Bottleneck is Playwright (LinkedIn/BuiltIn) — headless browser startup and navigation takes 10-30 seconds per site. API sources (RemoteOK, Himalayas, etc.) each take ~1-3 seconds.
- **LLM scoring per job**: 3-8 seconds per call (Gemini Flash). A 50-job batch with 30% passing the keyword gate = ~15 LLM scoring calls = ~60-120 seconds just for scoring.
- **PDF compilation**: 2-4 seconds per PDF (Playwright headless Chromium). Three documents per job = ~10 seconds per qualified role.

**What Was Optimized**:
- `SCORING_JD_MAX_CHARS = 1500` (`utils.py:41`) — truncating JDs reduces input tokens ~60-70% with minimal signal loss (job requirements are front-loaded)
- `workExperience_summary.md` for scoring, full file only on YES — reduces input tokens for rejected jobs
- Zero-token keyword gate — eliminates LLM calls for obvious rejects

**What Was Ignored**:
- No caching of LLM responses (same company could be re-evaluated on every scout run)
- No parallel LLM calls (jobs are processed sequentially in `batch_pipeline.py`)
- No Playwright browser reuse across scout stages (each spawn starts a fresh Chromium)

### 10.2 Cost Drivers

**At current usage (1 user, ~2 scout runs/week, ~50 jobs/run)**:
- Gemini Flash scoring: ~15 calls/run × $0.0003/call × 2 runs/week × 4 weeks = ~$0.036/month
- Gemini Flash drafting: ~5 qualified jobs/run × $0.002/job × 2 runs/week × 4 weeks = ~$0.08/month
- Total estimated: **< $0.15/month** on Gemini Flash free tier (likely $0)

**Cost Optimization Decisions**:
- Gemini Flash chosen over GPT-4 specifically because of free tier generosity and lower cost per token
- Two-stage scoring exists primarily to minimize LLM calls
- JD truncation at 1500 chars was tuned empirically — longer truncation improved recall by < 5% while increasing cost ~40%

### 10.3 Scalability Limits

- **SQLite single-writer limit**: At current scale (< 100 writes/minute), never a bottleneck
- **Sequential batch processing**: A 200-job batch run would take ~2-4 hours. No parallelism in `process_batch()`. Acceptable for a single user who runs the pipeline unattended overnight.
- **Playwright stability**: Playwright sessions occasionally crash on Windows under memory pressure. No watchdog or restart mechanism.

---

## PART 11: SECURITY & RISK SURFACE

### 11.1 Security Considerations

**Authentication & Authorization**: None. The app is localhost-only. Any process that can reach `localhost:3000` can call any API. This is an intentional and acceptable trade-off for a local-only single-user app. The risk is negligible: an attacker with local machine access has far worse attack surfaces available.

**API Keys & Secrets**:
- Keys are stored in SQLite `profiles` table. The SQLite file is at `jobagent.sqlite` in the project root.
- `.gitignore` excludes `jobagent.sqlite`.
- Keys are injected at spawn time as environment variables (`buildPythonEnv()` in `server/shared.ts`). They are never written to log files or returned in API responses.
- `.env` is excluded from git and documented as optional fallback only.

**Data Security**: All career data stays on local disk. The only data sent to external services is: JD text + experience summary to LLM APIs for scoring, experience to LLM for summary generation, company name/role to research APIs.

### 11.2 Known Vulnerabilities

**Path Traversal — FIXED**: An earlier version of the file download route (`GET /api/jobs/:id/files/:filename`) used `path.join(folder, filename)` without validation. A malicious `filename` containing `../../server/db.ts` would serve arbitrary files. Fixed by sanitizing filename to basename only (see QA fix in project memory from 2026-05-05).

**SQL Injection Prevention**: All SQLite queries use parameterized statements (`db.prepare('... WHERE id = ?').run(id)`). The PATCH allowlist (`ALLOWED_JOB_FIELDS`) prevents field name injection in the dynamic UPDATE query.

**LLM Prompt Injection Risk**: Job descriptions scraped from the web are injected directly into LLM prompts. A malicious JD could contain prompt injection text ("Ignore previous instructions and..."). Mitigated partially by: structured JSON output enforcement, low temperature (0.1), explicit schema in the prompt. Not fully mitigated — a sophisticated injection could manipulate scoring output.

**What Was Intentionally Skipped**:
- CORS is enabled broadly (`cors()` with no origin restriction). Acceptable for localhost-only.
- No rate limiting on API endpoints. Acceptable for single-user.
- No HTTPS. Acceptable for localhost.

### 11.3 Data Privacy

**What's stored locally**: Full work history, target companies, job search strategy, all scraped JDs, generated resumes and cover letters.

**What's sent externally** (only with user-configured APIs):
- LLM APIs: Receive JD text, work experience summary, prompts. Do not receive recruiter names, salary expectations, or outcome data.
- Adzuna: Receives only search query strings (e.g., "product manager remote").
- Perplexity: Receives company name and role title for research queries.

---

## PART 12: OBSERVABILITY & DEBUGGING

### 12.1 Logging Strategy

**What gets logged**: All pipeline events via `logActivity()` in `server/db.ts:66`. The frontend's "Terminal" view is a direct read of the `activity_log` table.

**Log format**:
```
level: INFO | WARN | ERROR
source: Scout | Pipeline | Scraper | Crawler | System | Drafting
message: human-readable string
```

Pipeline scripts use prefix conventions on stdout that the server parses:
```
[LOG] General progress message
[FOUND] Matched job title — url
[REJECT] Skipped: reason
[ACTION] User action required
[DONE] Process completed
```

**What's not logged**: Individual API call latencies, token counts per LLM call, PDF compilation times. These are visible in the raw stdout but not persisted.

### 12.2 Error Handling Philosophy

**Approach**: Fail forward in the pipeline (one failed job doesn't stop the batch), fail loud in the server (500 responses with error details in the body). Python scripts try to continue after per-job errors rather than aborting the batch.

**Recovery**: No automatic retry on scout failure. No automatic retry on compilation failure. Rate limits are the one case with automatic retry (escalating waits in `call_llm()`).

### 12.4 Debug Workflow

**Common Issues & Solutions**:

1. **"No jobs appearing after scout"**
   - Diagnosis: Check `activity_log` for `[REJECT]` entries. Check `candidate_preferences.json` for overly restrictive blocklists. Check SQLite `jobs` table directly with `sqlite3 jobagent.sqlite "SELECT * FROM jobs ORDER BY created_at DESC LIMIT 10"`.
   - Fix: Broaden blocklist, confirm search terms match source query format.

2. **"PDF not updating after edit"**
   - Diagnosis: Check server stdout for `compile_single.py` errors. Common cause: Playwright can't find Chromium executable on Windows.
   - Fix: `npx playwright install chromium` + `playwright install chromium` (both Node and Python Playwright).

3. **"LLM returning empty results"**
   - Diagnosis: Check `activity_log` for `[LLM Error]` entries. Check if API key is saved in Settings.
   - Fix: Re-enter API key in Settings > API or Connections. Key may have expired or quota exhausted.

4. **"Scout fails immediately"**
   - Diagnosis: Look for `Engine Error:` in activity log. Common cause: `candidate_preferences.json` is malformed or missing.
   - Fix: Go to Job Search tab, save settings — this regenerates the file.

---

## PART 13: TESTING STRATEGY

### 13.1 Test Coverage

**What's tested**: `scripts/test_smoke_regression.py` and `scripts/test_llm.py` exist as manual test utilities. They're not automated and not run in CI.

**What's not tested**: Essentially everything. No unit tests, no integration tests, no CI pipeline. The codebase is tested by the developer running it and observing behavior.

### 13.2 Testing Philosophy

**Approach**: Empirical validation — run the scout, check the output, adjust. Given the LLM-heavy nature of the pipeline, automated tests would require mocking LLM responses, which would test the harness but not the actual prompt quality. The developer treats real scout runs as integration tests.

**Known risk**: A change to the scoring prompt or rules file could silently degrade scoring quality. There's no regression test that catches this.

---

## PART 14: DEPLOYMENT & OPERATIONS

### 14.1 Deployment Process

Local only. `npm run dev` starts Vite dev server + tsx server concurrently. No production build process is used in practice (though `npm run build` + `npm run preview` exist).

**Startup sequence**:
1. `npm run dev` starts `server/index.ts` via tsx (port 3000) and Vite (port 5173)
2. `server/db.ts` runs `CREATE TABLE IF NOT EXISTS` on boot — database initialized idempotently
3. No other services required

**Maintenance Tasks**:
- `submissions/` directory grows unboundedly. No automatic cleanup. Long job searches could accumulate hundreds of PDFs.
- `activity_log` table grows unboundedly. No rotation. After months of use, queries against it will slow.
- `jobs/` directory (JD text files) is not cleaned up after processing. Should be pruned periodically.

---

## PART 15: VIBE-TO-CODE ANALYSIS

### 15.1 Accidental vs Intentional Decisions

**Accidental Decisions**:

- **`server/index.ts` as a monolith (844 lines) → resolved**: Started as a small Express server, grew feature by feature without extracting a router layer. Refactored May 2026 into `server/routes/` (system, jobs, profile, pipeline) + `server/shared.ts`. Entry point is now 33 lines. The boundary was always clear — it just took the pain of a 844-line file to enforce it.

- **stdout parsing with prefix strings**: `[LOG]`, `[FOUND]`, `[DONE]` in Python → parsed in `server/scout.ts:47-61`. This emerged from "let's just print progress to stdout" and then needed to be parsed. A structured JSON stream (one JSON object per line) would be cleaner. The prefix convention worked and was never replaced.

- **`jobs/` directory as IPC mechanism**: The scout writes JD text to `jobs/{company}.txt`. The pipeline reads from this directory. This is a file-system message queue. It emerged naturally but has no cleanup, no ordering guarantee, and no atomic writes.

**Intentional Decisions**:

- **Proof code system**: Deliberately designed as the founding anti-hallucination mechanism. Not vibe-coded.
- **Materialized JSON for preferences**: Explicitly designed in ADR-005 after the chaos of four disconnected preference systems.
- **LLM fallback chain**: Explicitly designed in CR-006 after observing silent failures from single-provider outages.

### 15.2 Abstraction Gaps

- **Thought**: "The settings UI manages all configuration"
- **Reality**: `data/job_fit_engine.md` is a manually maintained prompt artifact that governs scoring. Changes to scoring criteria must be made directly in this file — there's no UI for it. It's "configuration" but it's really a prompt component.

- **Thought**: "The pipeline processes new jobs"
- **Reality**: The `jobs/` directory accumulates `.txt` files from every scout run. Old files are never cleaned up. If a company changes its job listing (same URL, updated JD), the old text file persists and the pipeline will re-score using stale text.

### 15.3 Hidden Complexity

- **LinkedIn scraping**: "Just use Playwright to search LinkedIn" turned out to require: stealth plugin to avoid bot detection, authenticated session management via `browser_context/` directory, careful timing to avoid rate limits, and still produces unreliable results because LinkedIn actively changes its DOM structure.

- **PDF compilation**: "Generate a PDF from the resume Markdown" turned out to require: a full Playwright headless Chromium instance, a custom HTML wrapper that injects the styled Markdown, a `style_compliance_guard.py` that normalizes the Markdown before compilation, and careful handling of page break logic.

---

## PART 16: ALTERNATIVE ARCHITECTURE SNAPSHOT

### 16.1 "If Built Properly" (Enterprise Version)

| Current | Enterprise Version | Why the Difference |
|---|---|---|
| `spawn()` chain in `scout.ts` with `on('close')` callbacks | Job queue (BullMQ/Celery) with separate workers per stage | Retry isolation, cancellation, visibility, backpressure |
| stdout prefix parsing for IPC | Structured JSON streaming over named pipes or Redis pub/sub | Type safety, structured error propagation |
| Sequential batch processing | Parallel job evaluation with worker pool | 10x throughput on large batches |
| No migration system | Numbered migration files (e.g., Flyway, Alembic) | Safe schema evolution, rollback capability |
| SQLite | PostgreSQL | Multi-user, concurrent writes, proper tooling ecosystem |
| No test suite | Unit tests for codification engine, integration tests for pipeline stages | Regression safety |
| `job_fit_engine.md` as prompt config | UI-editable scoring criteria with version history | Non-technical users, auditability |
| `jobs/` directory as file queue | S3/blob storage with metadata DB | Ordering, dedup, cleanup |

### 16.2 Refactoring Roadmap

**Phase 1 (Critical for robustness)**:
- Add `ALTER TABLE` migration system before any DB schema changes
- Clean up `jobs/` directory after each pipeline run
- Add `LIMIT` to `activity_log` queries (table will grow indefinitely)
- Replace stdout prefix parsing with newline-delimited JSON from Python

**Phase 2 (Important for reliability)**:
- Introduce a lightweight job queue for the pipeline stages (even a simple SQLite-backed queue)
- Add per-job LLM call timeout to prevent a single slow call from blocking the batch
- Add structured logging of token counts and provider used per LLM call

**Phase 3 (Nice to have)**:
- Extract `server/index.ts` into route modules
- UI for `job_fit_engine.md` editing (scoring rules are currently invisible to users)
- Playwright browser pool/reuse across scout stages

---

## PART 17: LEARNING EXTRACTION

### 17.1 Key Learnings

**Technical Skills Developed**:
- End-to-end Python LLM orchestration with provider abstraction and fallback chains
- Playwright for both web scraping and PDF generation from styled HTML
- SQLite patterns for a single-user local-first app (synchronous better-sqlite3, idempotent schema init)
- SSE (Server-Sent Events) for streaming pipeline progress to a React frontend

**Patterns Recognized**:
- **Materialized view pattern**: Write to SQLite, then project to a JSON file that downstream consumers can read without DB knowledge. Clean separation of concerns.
- **Proof code anti-hallucination**: Structural constraints (cite a code or don't make the claim) are more reliable than prompt constraints ("only use facts from this document").
- **Two-stage evaluation**: Zero-cost gate first, expensive gate second. Applicable to any pipeline with a large input set and expensive evaluation.

**Mistakes & Lessons**:
- **Building `server/index.ts` as a monolith**: Should have extracted route handlers into separate files from the start. The boundary was clear (routes, middleware, background jobs) but never enforced. Fixed May 2026 — see `server/routes/`.
- **Not designing IPC from the start**: The `[LOG]`/`[FOUND]` stdout prefix convention was a hack that became load-bearing. Defining a JSON streaming protocol from the start would have been worth the upfront cost.
- **Not adding migrations early**: Schema changes have been painful. SQLite `ALTER TABLE` is limited; dropping and recreating tables loses data.

### 17.2 Reusable Components/Patterns

**Worth extracting**:
- `call_llm()` with fallback chain and provider guard — this is a general-purpose pattern for any multi-provider LLM app
- `codifyExperienceAndAssignIDs()` — the ID assignment logic is generic and could apply to any domain requiring stable, auditable IDs on claim items
- The materialized JSON projection pattern — write to DB, project to file for downstream consumers

### 17.3 Future Improvements

**What would change on a rebuild**:
- Start with a job queue (even a simple one) for the pipeline stages
- Define a structured JSON streaming protocol for Python → Node communication from day 1
- Extract route handlers into modules from the start
- Add a migration system before writing the first schema

**What would be kept**:
- SQLite for this use case — it's the right tool
- The two-stage scoring architecture
- The proof code anti-hallucination system
- The materialized JSON projection for pipeline config

---

## PART 18: DEPENDENCIES & ECOSYSTEM

### 18.1 Key Dependencies

| Package | Purpose | Alternative Considered | Breaking Change Risk |
|---|---|---|---|
| `better-sqlite3` | Synchronous SQLite for Express | `sqlite3` (async, more complex) | Low — very stable |
| `playwright` (Node) | Scout automation + PDF compilation | Puppeteer (less maintained), Selenium (slower) | Medium — DOM APIs change |
| `playwright` (Python) | PDF compilation in Python scripts | Puppeteer-python, wkhtmltopdf | Medium |
| `google-generativeai` | Gemini API in Python | `openai` (different API surface) | Medium — Google changes SDK frequently |
| `anthropic` | Claude API in Python | Direct HTTP requests | Low |
| `toastui-editor` | WYSIWYG Markdown editor | Tiptap, Quill, CodeMirror | Medium — depends on React version |
| `adm-zip` | ZIP all assets for download | `archiver`, `jszip` | Low |
| `vite` | Frontend build tooling | Webpack, CRA | Low — stable |

### 18.2 Dependency Hell Scenarios

- **`google-generativeai` API change**: Google has changed the SDK interface twice during development. The `genai.Client(api_key=...)` pattern replaced an older `google.generativeai.configure()` pattern. Any future SDK change would break all Gemini calls simultaneously.
- **LinkedIn DOM change**: LinkedIn actively changes its DOM structure. A scout run that worked last week may return 0 results after a LinkedIn frontend deploy. No way to detect this except observing 0 results.
- **`toastui-editor` + React 19 compatibility**: Toast UI editor was not officially tested against React 19 at integration time. It works, but upgrade paths may be blocked.

---

## PART 19: ANTI-PATTERNS & TECHNICAL DEBT

### 19.1 Known Anti-Patterns

**Anti-Pattern #1: 844-Line God File → RESOLVED (May 2026)**
- **What (was)**: `server/index.ts` contained all route handlers, helper functions, and business logic in one file
- **Where (was)**: `server/index.ts` — 23 routes, `codifyExperienceAndAssignIDs()`, `materializeJobSearchPrefs()`, `buildPythonEnv()`, all mixed together
- **Why It Existed**: Grew incrementally. Each feature was "just one more route."
- **Cost (was)**: Hard to navigate, no separation between HTTP transport and business logic
- **Resolution**: Extracted to `server/routes/` (system, jobs, profile, pipeline) + `server/shared.ts` for path constants and shared utilities. `index.ts` is now 33 lines — middleware setup and router mounts only. `scout.ts` also updated to import `buildPythonEnv` from `shared.ts`, eliminating 15 lines of duplicated key-reading logic.

**Anti-Pattern #2: Callback Pyramid for Pipeline Chaining**
- **What**: `server/scout.ts` chains 4 process spawns via nested `on('close')` callbacks, 4 levels deep
- **Where**: `server/scout.ts:71-157`
- **Why It Exists**: Each stage needs the previous to complete. No queue library. Sequential callback was the obvious solution.
- **Cost**: Hard to read, hard to add error recovery, impossible to add retry logic for individual stages
- **Fix**: A simple SQLite-backed job queue, or convert to async generator pattern

**Anti-Pattern #3: File System as Message Queue**
- **What**: `jobs/` directory stores JD text files. Scout writes them; pipeline reads them. Files are never cleaned up.
- **Where**: `scripts/scout_local.ts` (writes), `scripts/batch_pipeline.py:177` (reads via `glob.glob`)
- **Why It Exists**: Simplest possible IPC — no shared state needed, both processes can access the filesystem
- **Cost**: Grows unboundedly, stale files from old runs can be re-processed, no ordering guarantee
- **Fix**: Clean up processed files, or use SQLite to store JD text directly

**Anti-Pattern #4: No Schema Migrations**
- **What**: Schema is defined as `CREATE TABLE IF NOT EXISTS` in `server/db.ts`. Column additions require manual `ALTER TABLE` by the user.
- **Where**: `server/db.ts:11-64`
- **Why It Exists**: Schema was simple initially. Migrations weren't needed for the first few months.
- **Cost**: Every schema change is a manual operation. Forgetting to migrate breaks features silently.
- **Fix**: Add a migration table (`schema_version`) and run numbered migration scripts on boot.

### 19.2 Technical Debt Log

| Item | Impact | Priority | Effort |
|---|---|---|---|
| No schema migration system | Schema changes break existing installs silently | Critical | Medium (2-3 days) |
| `jobs/` directory never cleaned | Grows unboundedly; stale files re-processed | High | Low (1-2 hours) |
| `activity_log` table never pruned | Query performance degrades over time | Medium | Low (add LIMIT to queries + periodic DELETE) |
| ~~`server/index.ts` monolith~~ | ~~Developer experience, merge conflicts~~ | **RESOLVED** | Refactored May 2026 → `server/routes/` |
| Pipeline chaining via callbacks | No retry, no cancellation, hard to modify | Medium | High (requires queue system) |
| `scripts/scratch/` not gitignored | Debug scripts committed accidentally | Low | Trivial (add to .gitignore) |
| `re_scrape_backlogs.ts` orphan | Dead code, confusing | Low | Trivial (delete or document) |
| No automated tests | Regressions invisible | High | High (ongoing investment) |

---

## PART 20: APPENDIX — KEY CODE EXAMPLES

### Example 1: Provider Fallback Chain

```python
# scripts/utils.py — _get_configured_providers() + call_llm()
# This pattern is the core of the LLM reliability architecture.

def _is_configured(provider: str, settings: dict) -> bool:
    # Only calls providers that have a valid key.
    # This is why configuring no providers gives an actionable warning
    # rather than a silent empty string return.
    if provider == 'gemini':
        return bool(settings.get('geminiApiKey') or os.getenv('GEMINI_API_KEY'))
    # ... other providers

def _get_configured_providers(settings: dict) -> list:
    # primaryProvider field with backward compat for old 'provider' field.
    primary = settings.get('primaryProvider') or settings.get('provider', 'gemini')
    fixed_order = ['gemini', 'claude', 'local', 'perplexity']
    ordered = [primary] + [p for p in fixed_order if p != primary]
    return [p for p in ordered if _is_configured(p, settings)]

def call_llm(...):
    providers = _get_configured_providers(settings)
    for i, provider in enumerate(providers):
        result = None
        if provider == 'gemini':
            result = _call_gemini(...)   # Returns None on error, str on success
        elif provider == 'claude':
            result = _call_claude(...)   # tools param intentionally omitted
        # ...
        if result is not None:
            return result                # str result terminates the loop
        if i + 1 < len(providers):
            print(f"    [LLM] Falling back from {provider} to {providers[i+1]}...")
    return ""                            # All providers failed
```

### Example 2: Materialized JSON Projection Pattern

```typescript
// server/index.ts — materializeJobSearchPrefs()
// The canonical example of the ADR-005 pattern.
// SQLite is the source of truth. JSON file is a projection for Python consumers.

function materializeJobSearchPrefs(jobSearch: any): void {
  // Read existing file to preserve fields Python may have added
  let existing: any = {};
  try {
    if (fs.existsSync(CANDIDATE_PREFS_PATH)) {
      existing = JSON.parse(fs.readFileSync(CANDIDATE_PREFS_PATH, 'utf-8'));
    }
  } catch { /* use defaults */ }

  const targetRole = jobSearch.targetRole || 'Product Manager';
  const searchTerms = [targetRole];

  // Role-specific search term expansion — keeps logic server-side,
  // not hardcoded in scout scripts
  if (targetRole.toLowerCase().includes('product manager')) {
    searchTerms.push('Product Owner', 'Technical Product Manager', ...);
  }

  const updated = {
    ...existing,
    target_role: targetRole,
    search_terms: searchTerms,
    blocked_titles: ...,
    min_fit_score: ...,
    // etc.
  };

  fs.writeFileSync(CANDIDATE_PREFS_PATH, JSON.stringify(updated, null, 2));
}
// Called immediately after: db.prepare("INSERT OR REPLACE INTO profiles...").run()
```

### Example 3: Zero-Token Keyword Gate

```python
# scripts/batch_pipeline.py:17
# This runs BEFORE any LLM call. At 50 jobs/batch, it eliminates ~35 LLM calls.

def passes_jd_keyword_gate(jd_text: str, prefs: dict = None) -> bool:
    lower = jd_text.lower()

    # Blocked titles check on first 200 chars only (title/header is always first)
    # This avoids blocking a job because a blocked term appears in requirements
    if prefs and "blocked_titles" in prefs:
        title_chunk = lower[:200]
        for blocked in prefs["blocked_titles"]:
            if blocked.lower() in title_chunk:
                return False

    # Required keyword: at least one must appear anywhere in the JD.
    # JD_REQUIRED_KEYWORDS loaded from candidate_preferences.json at import time.
    return any(kw in lower for kw in JD_REQUIRED_KEYWORDS)
```

### Example 4: Proof Code Assignment

```typescript
// server/routes/profile.ts — codifyExperienceAndAssignIDs()
// Key insight: scan existing IDs first to seed counters above current maxima.
// This prevents collisions when a user saves an already-codified document.

// Section 5.N maps to range N*100+1 through (N+1)*100
// Section 5.1 → 101-199, Section 5.2 → 201-299, etc.
// This partitioning allows multiple employer sections without ID conflicts.

// Lines containing [RETIRED-ACC-NNN] are preserved but never re-assigned —
// the ID is permanently retired from the pool.
```

---

*Generated 2026-05-09 | Covers Applyr v5.17 | 20 of 20 parts complete*
