---
title: "Applyr"
description: "A locally-hosted job search platform that automates discovery, scoring, and application drafting — with every generated claim grounded in verified work history."
author: "Jason Taylor"
role: "Product Manager"
status: "in-progress"
ai_role: "code generation within spec, document drafting from user templates and grounded work history, pipeline execution under operator direction"
tech_stack: ["React", "TypeScript", "Node.js", "Express", "SQLite", "Python", "Playwright", "Vite", "TailwindCSS"]
pm_skills: ["spec-driven development", "requirements management", "anti-hallucination architecture", "iterative development", "traceability design"]
keywords: ["job search automation", "resume generation", "cover letter", "AI pipeline", "local-first", "career tools", "BMAD"]
date_completed: "2026-06"
---

# Applyr — Job Search Platform

> A locally-hosted job search platform I built during my own job search. Every generated document traces back to verified work history. The AI can't invent claims. Got to screener stage.

Everything runs on your machine. No career data leaves your desktop except the API calls you explicitly configure.

---

## What This Is

Applyr has three layers: a background scout that surfaces qualified roles, a tailoring engine that generates targeted resumes and cover letters, and a tracker for the full application pipeline.

The decision everything else builds on: the AI works from your complete work history, not your current resume. A resume is a lossy snapshot. Experience directly relevant to this role might never have made it in. Applyr pulls from the full picture. Nothing it generates can be fabricated.

This works for anyone with real experience to draw from: corporate roles, freelance and volunteer work, or non-traditional backgrounds where transferable skills get buried by standard resume formats. If it happened and it's relevant to the role, the system finds it.

**My role:** Problem definition, product requirements (BMAD methodology), requirements registry with traceable IDs, anti-hallucination architecture, evaluation of every generated output.
**AI's role:** Code generation within my spec, document drafting from my templates and grounded work history, pipeline execution under my direction.

**What this is not:**
- A job board or listing aggregator you browse manually
- A resume builder without a job in mind — all drafts are generated against a specific posting
- A hosted SaaS product — nothing is stored outside your machine except the API calls you configure
- A system for mass-applying without review — every asset is reviewed and edited before submission

---

## Status

| Field | Value |
|---|---|
| **Phase** | Dogfood |
| **Stability** | Active development — breaking changes possible between versions |
| **Last updated** | June 2026 (CR-053/054/055 fit & gate overhaul) |

---

## Results & Impact

- **Real-world use:** Daily operational tool throughout a 6-month active job search — not a demo project.
- **Application outcomes:** Got to screener stage on roles Applyr identified and drafted.
- **Development pace:** Six major versions over 5 months, from CLI scraper to full local web platform.
- **What I learned:** The anti-hallucination architecture matters more than AI generation quality. A structured, codified source of truth is the product — the prompts are secondary.

---

## Prerequisites

- **Node.js 18+** — [nodejs.org](https://nodejs.org)
- **Python 3.10+** — [python.org](https://www.python.org)
- **Git** — [git-scm.com](https://git-scm.com)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/JasonWayneT/Applyr.git
cd Applyr
```

### 2. Install Node dependencies

```bash
npm install
```

> CI and clean installs use `npm ci`. The repo `.npmrc` sets `legacy-peer-deps` because `@toast-ui/react-editor` declares React 17 peers while this app uses React 19 (install still works at runtime).

### 4. Create Applyr's Python environment (isolated from Hermes / global PATH)

```bash
npm run setup:python
```

This creates `.venv/` in the project root, installs `requirements.txt`, and downloads Playwright Chromium for PDF export. The server and pipeline **only** use this interpreter — never whatever `python` is on your PATH.

Optional override: set `APPLYR_PYTHON` to an absolute path if you keep the venv elsewhere.

### 5. Start the app

```bash
npm run dev
```

This starts both the React frontend (Vite, usually port `5173` or `5174` if busy) and the Express backend (port `3000`).

Open the **Local** URL printed by Vite (e.g. **[http://localhost:5173](http://localhost:5173)**). The UI proxies `/api` to the backend in dev.

### Troubleshooting empty UI or startup errors

| Symptom | Fix |
|---------|-----|
| Dashboard looks empty but you had jobs before | Your jobs are likely **Applied** / **Closed** — open **Opportunities** (all jobs). Dashboard highlights **Backlog** with PDFs. |
| `jobs.filter is not a function` in browser console | Restart dev after pulling latest; API returned an error object instead of a list (fixed in `fetchJobs()`). |
| `npm ci` / install fails on React peer deps | Repo `.npmrc` sets `legacy-peer-deps=true`. |
| Missing `data/workExperience.md` after clone | Run `npm run setup:python` then `node scripts/invoke_applyr_python.mjs scripts/bootstrap_local_data.py` and configure Settings. |
| Pipeline uses Hermes Python / PDF compile fails | Run `npm run setup:python` and restart `npm run dev`. Applyr requires project `.venv`, not PATH `python`. |
| Missing gate keys after upgrading (`blocked_role_titles`, etc.) | Run `npm run gate-rollout` **once** — merges from `candidate_preferences.example.json`. Not needed on every pull. |
| Wrong Vite port | Use the port Vite prints (not an old tab on 5173 if Vite moved to 5174). |
| `APPLYR_API_TOKEN` set without `VITE_APPLYR_API_TOKEN` | POST requests need both, or unset the server token for local-only dev. GET routes work without a token. |

> **No `.env` file required.** All API keys are configured through the UI under **Settings → API or Connections**. Keys are stored only in the local SQLite database and never written to any tracked file.

---

## Moving between devices

All private data lives in a single folder: **`data/`**. To move Applyr to another machine, sync `data/` — everything else (code, deps) comes from git.

**Recommended: Google Drive**

Add `data/` to Google Drive sync (Backup & Sync mode). Exclude `data/browser_context/`, `data/jobs/`, and `data/__pycache__/` — these are large, device-specific, and regenerated at runtime.

On the new device:

```bash
git clone https://github.com/JasonWayneT/Applyr.git
cd Applyr
npm install
pip install -r requirements.txt
npx playwright install chromium
```

Wait for Google Drive to finish syncing `data/`, then `npm run dev`. The app reads all credentials, work history, submissions, and archive directly from `data/`.

**Upgrading to CR-053+ on a synced machine:** If your `data/candidate_preferences.json` predates the gate overhaul (missing `blocked_role_titles`, `blocked_focus_area_words`, or `blocked_companies`), run the one-time migration below — not required on every pull.

**What lives where**

| Location | Contents | How to sync |
|---|---|---|
| `data/` | Database, submissions, archive, personal files | Google Drive |
| Git (public) | All code, specs, examples | `git push jobhunt main` |
| Nothing | API keys, credentials | Stored in `data/jobagent.sqlite` — synced via Drive |

> `data/` is fully gitignored (except public example files). Nothing personal ever reaches GitHub.

---

## First-time configuration

Complete these steps in order before running your first scout.

### 1. Add your LLM provider

Go to **Settings → API or Connections**. Under **LLM Providers**, enter a key for at least one provider:

| Provider | Where to get a key | Notes |
|---|---|---|
| **Google Gemini** | [aistudio.google.com](https://aistudio.google.com/app/apikey) | Recommended. Free tier is generous. Has Google Search grounding for research. |
| **Anthropic Claude** | [console.anthropic.com](https://console.anthropic.com) | Premium reasoning. Used as automatic fallback if Gemini fails. |
| **Local LLM** | Ollama / LM Studio | 100% private, no API key required. Set the endpoint URL and model name. |
| **Perplexity** | [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api) | Optional. If configured, used automatically for company research. Falls back to primary LLM if not set. |

Click **Set Primary** on your preferred provider. If you configure multiple providers, the pipeline automatically falls back to the next one on error — you never lose a run to a single provider outage.

### 2. Set your profile

Go to **Settings → Profile**. Fill in your name, email, phone, LinkedIn, and portfolio links. These populate the headers of every generated document.

### 3. Add your work experience

Go to **Settings → Experience**. Paste your raw work history in any format — job titles, bullet points, accomplishments, metrics, anything. Click **Save & Sync AI**.

The system structures it into five sections and assigns stable proof codes (`ACC-NNN`, `VOC-XX`, `MET-XX`) to every claim. These codes are the anti-hallucination contract: the AI cannot claim anything in a generated document that doesn't trace back to a code in this file.

After saving, the system automatically generates a condensed scoring brief (`data/workExperience_summary.md`) in the background using your configured LLM. This is used during fit scoring to keep token usage low — the full experience document is only loaded for roles that pass the score threshold. You never need to touch the summary file directly.

### 4. Set your job search criteria

Go to the **Job Search** tab. Configure:

- Target role and search terms
- Work setting (Remote / Hybrid / On-site)
- Location and date posted window
- Experience level filters
- Title and industry blocklists
- Minimum salary threshold

Click **Save**. This immediately materializes `data/candidate_preferences.json` which governs every scout run and pipeline evaluation.

**Gate keys preserved on save:** UI edits update search targeting and the legacy `blocked_titles` list from the Title Blocklist field. Pipeline-only keys (`blocked_role_titles`, `blocked_focus_area_words`, `blocked_companies`, `min_confidence_score`) are **not** wiped when you save from the Job Search tab — they are merged from the existing JSON file.

### 5. (Optional) Connect Adzuna

Go to **Settings → API or Connections → Data Sources**. Enter your Adzuna App ID and App Key. Get a free key at [developer.adzuna.com](https://developer.adzuna.com). If no key is provided, Adzuna is silently skipped. Usage is capped at 10 calls per run (well inside the 250/day free tier).

---

## Core workflows

### Scouting

Go to **Job Search** and click **Run Scout**. The backend launches a parallel scrape across active sources using your saved criteria:

| Source | Type |
|---|---|
| LinkedIn | **Decommissioned** (CR-010 — security risk; skipped in `scout_local.ts`) |
| BuiltIn | **Removed** (CR-056 — Playwright stealth-browser crawl against a live site; ban-risk pattern retired in favor of API-only sourcing) |
| Levels.fyi | **Removed** (CR-056 — same reason as BuiltIn) |
| Greenhouse / Lever / Ashby / Workable (per-company) | **Removed** (CR-056 — required hand-curating a company watchlist; superseded by OpenPostings, which covers these same ATS platforms plus Workday, iCIMS, and others across 7,700+ companies with no watchlist) |
| RemoteOK | Public API |
| Remotive | Public API |
| We Work Remotely | Public API |
| Himalayas | Public API |
| The Muse | Public API (role-aware category routing) |
| Jobicy | Public API |
| Working Nomads | Public API (title-matched; not category-filtered — see CR-056) |
| JobsCollider | Public API |
| Adzuna | Aggregator API (optional, key required) |
| OpenPostings | Local ATS aggregator across 7,700+ companies (Greenhouse, Lever, Ashby, Workday, iCIMS, and more) — see setup below |
| TheirStack | Lane 2 API (optional, key required, 200 credit guard) |

The pipeline runs in four sequential stages automatically:
1. **Scout** — discover new job URLs across all sources
2. **Backfill** — fill in any missing job detail URLs
3. **Scrape** — fetch full job description text for new listings
4. **Evaluate & Draft** — score every new job and generate assets for those that pass

Live progress and source metrics (fetched, filtered, and passed counts), along with source health badges, stream to the Scout log console in real time via Server-Sent Events (SSE).

### Fit scoring

Each job is evaluated in stages before any drafting tokens are spent:

1. **Fast gate (deterministic, zero LLM):** Rejects roles that match title tier blocklists, focus-area blocklists, blocked companies, industry blocklist, solo-PM trap, years-over-max, location (non–San Diego onsite/hybrid, Canada in-person, EST/CST-only remote), keyword gates, or minimum salary.
2. **Structured fit (default):** Extracts must-have criteria from the JD, asks the LLM for per-criterion equivalence judgments only (`yes` / `partial` / `no` — no holistic score), then computes the 0–100 score in Python (`scripts/structured_fit.py`). Required-domain gaps apply a bounded penalty (max −10), not an instant kill. Set `STRUCTURED_FIT=0` to use the legacy holistic LLM rubric instead.
3. **Threshold:** Roles at or above **`min_fit_score`** in `candidate_preferences.json` (default **72**) proceed to drafting. Optional **`min_confidence_score`** can route low-confidence structured results to manual review.

Anchor keyword hits are recorded as risk flags only — scores are no longer force-promoted at the threshold.

Rubric reference: `.agent/rules/job_fit_engine.md` (v5.0). Formal spec: `docs/spec/05-change-requests/CR-053-fit-rubric-overhaul.md`.

### Drafting assets

**Note (2026-08-04):** Sync no longer auto-drafts. After scrape it exports new gate-passed JDs to `data/pending_review/` for later `generate-submission` Stage 0–3 in a chat session — no Ollama, no `batch_pipeline` on Sync. The Sync "Draft Assets" button and `POST /api/jobs/:id/draft` were removed. **Still live (flagged):** Find New Jobs (`POST /api/evaluate` via `usePipeline`) still spawns `batch_pipeline.py --mode single` — not yet retired. Day-to-day authoring remains Claude + ground truth via `.claude/skills/generate-submission/SKILL.md`.

Roles that pass Sync gates are exported for review (not drafted automatically). Authoring still produces:

1. A tailored 1-page resume — every claim grounded in your `workExperience.md` proof codes
2. A tailored cover letter
3. PDFs compiled via `compile_single.py` after verification

Output for finished applications lands in `data/submissions/[company-name]/`.

### Editing documents

Click any asset in the detail panel to open the visual editor:

- **Left pane:** Live PDF preview that reloads on save
- **Right pane:** Rich-text WYSIWYG editor (Toast UI)

Saving auto-runs the style compliance guard and recompiles the PDF. Use the **AI Rewrite** field to issue natural-language instructions to your configured LLM for targeted document edits.

### Application lifecycle

Track every role through six stages via the detail panel:

```
Backlog → Applied → Recruiter Screen → Core Interviews → Offer & Negotiation → Closed
```

When you mark a role as **Applied**, the submission folder is automatically moved to `archive/submissions/`. Closed roles record rejection stage and type for analytics.

### OpenPostings (optional scout source)

OpenPostings runs as a local Express server the connector spawns on demand. The project lives at `data/archive/OpenPostings-extracted/OpenPostings-main/` (gitignored). To enable it:

1. Extract the OpenPostings project into that path if it isn't already there.
2. Install its 4 real server dependencies only (skip its full `package.json`, which pulls in an unrelated Expo/React Native app tree): `cd data/archive/OpenPostings-extracted/OpenPostings-main && npm install cors express sqlite sqlite3 --no-save`.

Scouts read/write `data/archive/OpenPostings-extracted/OpenPostings-main/jobs.db`. A full sync across all ~7,700 tracked companies takes longer than the connector's 2-minute per-run timeout, so coverage builds up incrementally across multiple scout runs rather than completing in one pass.

---

## Project structure

```
server/
  index.ts          — Entry point: middleware, router mounts, app.listen (33 lines)
  shared.ts         — Shared path constants, buildPythonEnv (PYTHONUNBUFFERED only), resolveCompanyFolder
  domain/jobSearchPrefs.ts — materializeJobSearchPrefs + gate-key preservation (FR-248)
  scout.ts          — Scout orchestrator: spawns scout → backfill → scrape → evaluate
  db.ts             — SQLite init, logActivity helper
  routes/
    system.ts       — /api/system-status, /api/ats-pipeline, /api/logs
    jobs.ts         — All /api/jobs/* routes (CRUD, files, AI rewrite, ZIP download, manual draft)
    profile.ts      — /api/profile/*, /api/experience (includes proof-code codification)
    pipeline.ts     — /api/evaluate (SSE stream), /api/sync

scripts/
  scout_local.ts    — 7-source parallel job scraper (reads candidate_preferences.json)
  scrape_new_jobs.ts — Fetches full JD text for newly discovered jobs
  batch_pipeline.py — Fit scoring + asset generation engine (--mode batch | single)
  structured_fit.py — Evidence-tiered fit scoring (default when STRUCTURED_FIT=1)
  seniority_gate.py — Years + contextual title blocklist gates
  zero_shot_classifier.py — Location zero-token gate
  prefs_rollout.py / apply_gate_rollout.py — One-time gate-prefs migration (see Manual utilities)
  drafting_engine.py             — Entry + research + hard-fact guards (delegates to draft_compiler)
  draft_compiler.py              — Unified resume/cover compiler (CR-014)
  bullet_generation.py           — Per-claim bullets (Stage 3)
  jd_tailoring.py / llm_stages.py — JD profile + per-stage LLM routing
  generate_experience_summary.py — Auto-generates scoring brief from workExperience.md (background)
  research-engine.py             — Company intelligence via Perplexity or primary LLM
  compile_single.py              — Markdown → PDF via Playwright
  style_compliance_guard.py — Resume/CL format validation
  ai_rewrite.py      — LLM-powered document editing
  utils.py           — Shared: LLM call with fallback chain, path constants, file I/O
  archive/
    backfill_urls.ts — URL backfill crawler (spawned automatically after scout)

src/
  App.tsx           — Root: 5s job poll, status handler, routing
  pages/            — TodayView, AllJobsView, FindNewJobsView, SyncActivityView, TuningLogView
  components/       — JobDetailPanel, DocumentEditor, SettingsView, Sidebar, ...

data/
  ats-pipeline.md               — Optional manual ATS queue for GET /api/ats-pipeline
  candidate_preferences.json    — Materialized search/scoring config (auto-written by server)
  workExperience.md             — Full codified work history (edited via Settings > Experience)
  workExperience_summary.md     — Condensed scoring brief (auto-generated on every experience save)
  candidate_preferences.example.json — Template for gate rollout keys (blocked_role_titles, etc.)

.agent/rules/
  job_fit_engine.md             — Scoring rubric loaded by Python fit path
  Resume.md                     — Master resume template
  Cover_Letter_Reference.md     — Master cover letter template
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, TailwindCSS |
| Backend | Node.js, Express, tsx |
| Database | SQLite via better-sqlite3 |
| Scout engine | Playwright + playwright-extra stealth, public APIs |
| AI pipeline | Python — Gemini / Claude / Ollama / Perplexity (configurable, auto-fallback) |
| PDF compilation | Playwright (headless Chromium) |

---

## Manual utilities

These scripts are not part of the automated pipeline but are useful for maintenance:

| Script / command | Purpose |
|---|---|
| `npm run gate-rollout` | **One-time** (not per `git pull`): merge missing gate keys from `candidate_preferences.example.json` into live prefs; dry-run location rescore on Backlog/New jobs |
| `npm run gate-rollout:apply` | Same as above, but apply location rejects to the database |
| `python scripts/calibration_harness.py` | Compare structured vs legacy fit scores on stored JDs |
| `python scripts/rescore_location_gates.py` | Location-gate-only rescore utility |
| `scripts/reconcile_submissions.py` | Archive or remove stale folders in `submissions/` (FR-030) |
| `scripts/audit_all_submissions.py` | Audit quality of all generated assets |
| `scripts/regenerate_all_submissions.py` | Bulk regenerate all resumes and cover letters |
| `scripts/login_linkedin.ts` | Re-authenticate the LinkedIn Playwright session |
| `scripts/test_llm.py` | Test LLM provider connectivity and response quality |
| `scripts/test_smoke_regression.py` | Run smoke tests against the live pipeline |
| `npm test` | Unified runner: all Python unit tests + Vitest |

Run Python/TS scripts directly with `python scripts/<name>.py` or `npx tsx scripts/<name>.ts`.

---

## Documentation

| Document | Purpose |
|---|---|
| [CHANGELOG.md](./CHANGELOG.md) | Release history — major milestones and what changed |
| [docs/AGENTS.md](./docs/AGENTS.md) | Agent operating rules — methodology, coding standards, testing |
| [docs/SDD_PROCESS.md](./docs/SDD_PROCESS.md) | Three-layer change enforcement — the process every code change must follow |
| [docs/spec/00-project-constitution.md](./docs/spec/00-project-constitution.md) | Project scope, operating mode, technical defaults, constraints |
| [docs/spec/02-requirements-registry.md](./docs/spec/02-requirements-registry.md) | Canonical requirement IDs — source of truth for all FR/NFR/SEC/DATA/INT requirements |
| [docs/spec/06-traceability/traceability-matrix.md](./docs/spec/06-traceability/traceability-matrix.md) | Requirement → spec → code → status mapping |
| [docs/ACTIVE_WORKFLOW.md](./docs/ACTIVE_WORKFLOW.md) | Runtime workflow for operators — scout, evaluate, draft, verify |
| [docs/spec/08-implementation/IMP-CR-053-055-fit-gate-overhaul.md](./docs/spec/08-implementation/IMP-CR-053-055-fit-gate-overhaul.md) | CR-053/054/055 implementation tracker — structured fit, gates, rollout |
| [docs/spec/05-change-requests/CR-053-fit-rubric-overhaul.md](./docs/spec/05-change-requests/CR-053-fit-rubric-overhaul.md) | Structured evidence-tiered fit scoring spec |
---

## Challenges & Decisions

### Full work history as source of truth, not the current resume
**Problem:** AI resume tools hallucinate experience or generate generic claims that don't fit the role. The root cause is the resume as source of truth — it's already a lossy, role-specific snapshot.
**Decision:** Work from a complete, codified work history with stable proof codes (`ACC-NNN`, `VOC-XX`, `MET-XX`). Every claim in every generated document must trace back to a code in that file.
**Tradeoff:** Higher setup friction. Users have to invest time structuring their work history before getting any value out of the system.
**Outcome:** Zero hallucination in generated documents. The AI cannot claim experience that isn't in the source file.

### Local-first, no hosted service
**Problem:** Job search data is sensitive — target companies, salary expectations, interview notes. Sending it to a third-party service creates a real privacy problem.
**Decision:** Everything runs on the user's machine. No data leaves the desktop except the API calls they explicitly configure.
**Tradeoff:** Higher setup barrier. Requires Node.js, Python, and a local database. Not consumer-grade onboarding.
**Outcome:** Complete privacy ownership. The product delivers something a hosted SaaS can't credibly promise.

### Spec-first under active development pressure
**Problem:** During an active job search, the temptation is to ship fast and skip the process. Every day without a working scout is a missed opportunity.
**Decision:** Held the spec-first process regardless — BMAD brief, PRD, requirement IDs assigned before any code. Every change request goes through the same gate.
**Tradeoff:** Slower initial velocity. Writing specs when you're urgently job hunting is discipline, not preference.
**Outcome:** A codebase that stayed coherent across 6 major versions. Every breaking change was traceable to a requirement. Bugs were diagnosed against specs, not guesses.

---

## How This Was Built

I started this as a CLI scraper in January 2026, the month I was laid off. Six major versions later it's a full local web platform. The problem is personal: I needed a structured, repeatable job search process that wouldn't hallucinate my credentials or waste time on roles I'd never get.

I wrote product requirements before any code. Brief, PRD, architecture decisions first. Every code change cites a traceable requirement ID (`FR-*`, `CR-*`, etc.) from the requirements registry. Nothing ships without a spec entry. Release milestones are in [`CHANGELOG.md`](./CHANGELOG.md); full spec traceability is in [`docs/spec/`](./docs/spec/).

`docs/spec/` is the source of truth. If the code and the spec disagree, the spec wins.
