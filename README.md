# Applyr — Curated Job Hunt Agent

A locally-hosted, privacy-first platform that automates the full job search lifecycle: stealth scouting across 7 job sources → deterministic fit scoring → bespoke resume, cover letter, and interview cheat sheet drafting grounded in your verified work history.

Everything runs on your machine. No career data leaves your desktop except the API calls you explicitly configure.

---

## Prerequisites

- **Node.js 18+** — [nodejs.org](https://nodejs.org)
- **Python 3.10+** — [python.org](https://www.python.org)
- **Git** — [git-scm.com](https://git-scm.com)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/JasonWayneT/JobHuntAgent.git
cd JobHuntAgent
```

### 2. Install Node dependencies

```bash
npm install
```

### 3. Install Playwright browsers (for the scout engine)

```bash
npx playwright install chromium
playwright install chromium
```

### 4. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 5. Start the app

```bash
npm run dev
```

This starts both the React frontend (port `5173`) and the Express backend (port `3000`) together.

Open **[http://localhost:5173](http://localhost:5173)** in your browser.

> **No `.env` file required.** All API keys are configured through the UI under **Settings → API or Connections**. Keys are stored only in the local SQLite database and never written to any tracked file.

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

### 5. (Optional) Connect Adzuna

Go to **Settings → API or Connections → Data Sources**. Enter your Adzuna App ID and App Key. Get a free key at [developer.adzuna.com](https://developer.adzuna.com). If no key is provided, Adzuna is silently skipped. Usage is capped at 10 calls per run (well inside the 250/day free tier).

---

## Core workflows

### Scouting

Go to **Job Search** and click **Run Scout**. The backend launches a parallel scrape across 7 sources using your saved criteria:

| Source | Type |
|---|---|
| LinkedIn | Playwright-based authenticated crawl |
| BuiltIn | Playwright-based crawl |
| RemoteOK | Public API |
| Remotive | Public API |
| We Work Remotely | RSS feeds (product + management) |
| Himalayas | Public API |
| The Muse | Public API (role-aware category routing) |
| Adzuna | Aggregator API (optional, key required) |

The pipeline runs in four sequential stages automatically:
1. **Scout** — discover new job URLs across all sources
2. **Backfill** — fill in any missing job detail URLs
3. **Scrape** — fetch full job description text for new listings
4. **Evaluate & Draft** — score every new job and generate assets for those that pass

Live progress streams to the Scout log console in real time.

### Fit scoring

Each job is evaluated in two stages:

1. **Fast gate (deterministic):** Instantly rejects roles that match your title blocklist, industry blocklist, or fall below your minimum salary. No LLM token spent.
2. **LLM scoring:** Evaluates the JD across four vectors (leadership fit, seniority fit, technical depth, transition potential) against your summarized experience. Roles scoring at or above your threshold proceed to drafting.

### Drafting assets

Roles that pass scoring automatically get a full asset pack drafted:

1. Company research via Perplexity (if configured) or your primary LLM with web grounding
2. A tailored 1-page resume — every claim grounded in your `workExperience.md` proof codes
3. A tailored cover letter
4. An interview cheat sheet

Output lands in `submissions/[company-name]/`. PDFs are compiled automatically.

You can also trigger a manual draft on any Backlog role from the **Opportunities** view.

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

---

## Project structure

```
server/
  index.ts          — Entry point: middleware, router mounts, app.listen (33 lines)
  shared.ts         — Shared path constants, buildPythonEnv, resolveCompanyFolder, materializeJobSearchPrefs
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
  drafting_engine.py             — Resume/CL drafting (imported by batch_pipeline)
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
  candidate_preferences.json    — Materialized search/scoring config (auto-written by server)
  workExperience.md             — Full codified work history (edited via Settings > Experience)
  workExperience_summary.md     — Condensed scoring brief (auto-generated on every experience save)
  job_fit_engine.md             — Scoring rules and anchor criteria
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

| Script | Purpose |
|---|---|
| `scripts/audit_all_submissions.py` | Audit quality of all generated assets |
| `scripts/regenerate_all_submissions.py` | Bulk regenerate all resumes and cover letters |
| `scripts/login_linkedin.ts` | Re-authenticate the LinkedIn Playwright session |
| `scripts/test_llm.py` | Test LLM provider connectivity and response quality |
| `scripts/test_smoke_regression.py` | Run smoke tests against the live pipeline |

Run these directly with `python scripts/<name>.py` or `npx tsx scripts/<name>.ts`.
