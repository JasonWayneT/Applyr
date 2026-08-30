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
| **Last updated** | August 2026 (CR-093 fit engine, CR-094 truth architecture, CR-097 authoring feedback loop) |

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

> **Groq (separate, optional, not a pipeline primary):** the same Settings → API or Connections table also has a **Groq** row with no "Set Primary" option. It is the default for Gmail sync classification and interview date extraction, because Groq's free tier doesn't train on submitted data and those calls see real email. Gemini can be turned on as a secondary fallback for those two tasks from **Settings → AI Usage** — opt-in, and even then Groq is always tried first. The same card also lets you pin a first-choice provider for the work-experience scoring summary and the document-editor AI rewrite (company research stays Gemini-only; it needs live search grounding).

### 2. Set your profile

Go to **Settings → Profile**. Fill in your name, email, phone, LinkedIn, and portfolio links. These populate the headers of every generated document.

### 3. Add your work experience

Go to **Settings → Experience**. Paste your raw work history in any format — job titles, bullet points, accomplishments, metrics, anything. Click **Save & Sync AI**.

The system structures it into five sections and assigns stable proof codes (`ACC-NNN`, `VOC-XX`, `MET-XX`) to every claim. These codes are the anti-hallucination contract: the AI cannot claim anything in a generated document that doesn't trace back to a code in this file.

After saving, the system automatically generates a condensed scoring brief (`data/workExperience_summary.md`) in the background. Default provider is Gemini; pin a different first-choice from **Settings → AI Usage** if you want. This brief is used during fit scoring to keep token usage low — the full experience document is only loaded for roles that pass the score threshold. You never need to touch the summary file directly.

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
| We Work Remotely | **Removed** (2026-08-30, Jason-directed — not a source he uses) |
| Himalayas | Public API |
| The Muse | Public API (role-aware category routing) |
| Jobicy | Public API |
| Working Nomads | Public API (title-matched; not category-filtered — see CR-056) |
| JobsCollider | **Removed** (2026-08-30, Jason-directed — sourced from remotefirstjobs.com, not a source he uses) |
| Adzuna | Aggregator API (optional, key required) |
| OpenPostings | Local ATS aggregator across 7,700+ companies (Greenhouse, Lever, Ashby, Workday, iCIMS, and more) — see setup below |
| TheirStack | Lane 2 API (optional, key required, 200 credit guard) |

The pipeline runs in four sequential stages automatically:
1. **Scout** — discover new job URLs across all sources
2. **Backfill** — fill in any missing job detail URLs
3. **Scrape** — fetch full job description text for new listings
4. **Review export** — gate-passed JDs with real text export to `data/pending_review/` for later Stage 0 evaluation via `scripts/run_submission.py`; no scoring or drafting happens during Sync itself (silent auto-draft removed 2026-08-04)

Live progress and source metrics (fetched, filtered, and passed counts), along with source health badges, stream to the Scout log console in real time via Server-Sent Events (SSE).

### Fit scoring

**CR-093 (2026-08-19): the entire fit-scoring engine was rebuilt and every older mechanism removed** — `scripts/structured_fit.py`, `scripts/fit_policy.py`, `scripts/batch_pipeline.py`'s `evaluate_job_fit()`, and `candidate_preferences.json`'s `min_fit_score` field are all gone. There is exactly one fit-scoring path now, and it only runs via `scripts/run_submission.py`'s Stage 0 (`scripts/build_stage0_fit_gate.py`):

1. **Deterministic gates first (zero LLM):** DB cooldown/reapply history, prefs exclusion zones (people management, 0-to-1, revenue/billing, AI/ML ownership), title/location/years gates.
2. **Per-requirement evidence judgment (`scripts/evidence_scale.py`):** one LLM call per required/preferred JD line, rating a 0–4 behaviorally-anchored evidence scale (no evidence → strong direct evidence) against retrieval-scoped excerpts of `workExperience.md`. A line only hard-gates (disqualifies outright) for an unbridgeable degree, a named regulated-domain requirement with its own years threshold, or a role-category exclusion — named tools/skills never gate on their own (spec-grounded fix for a real miss: a JD was previously rejected sight-unseen over one tool mention).
   For multi-role local runs, set `STAGE0_BATCH_KEEP_ALIVE=1` to avoid the
   redundant post-role model purge. The next role still purges before loading
   Qwen, so the VRAM-safe Qwen/Gemma handoff is unchanged.
3. **Deterministic weighted formula:** `compute_fit_score()` turns those per-item judgments into a single 0–100 score — no second LLM call.
4. **Score bands from `data/fit_rubric_calibration.json`** (tracked in git, deliberately not `candidate_preferences.json` — a scoring-algorithm calibration constant isn't a personal job-search preference): `skip_floor` 40 and `tier1_floor` 65 decide Skip / Tier 2 / Tier 1. Jason locked those numbers 2026-08-20 (CR-093 Story 3.3). They are research-grounded, not yet calibrated against Applyr interview outcomes — see that file and `docs/spec/05-change-requests/CR-093-evidence-scale-fit-engine.md`.

Full spec: `data/fit_rubric_spec.html` (the research this implements) and `docs/spec/05-change-requests/CR-093-evidence-scale-fit-engine.md` (the implementation + calibration record). `docs/spec/05-change-requests/CR-053-fit-rubric-overhaul.md` is superseded — read CR-093 instead.

### Drafting assets

Sync never auto-drafts — after scrape it exports new gate-passed JDs to `data/pending_review/` for later `generate-submission` via `scripts/run_submission.py`. Day-to-day authoring is Claude + ground truth via `.claude/skills/generate-submission/SKILL.md` → `run_submission.py`; there is no other live drafting path (the old "Find New Jobs" page and its `POST /api/evaluate` route were removed 2026-08-19 along with the rest of the old fit-scoring system).

Roles that pass Sync gates are exported for review (not drafted automatically). Authoring still produces:

1. A tailored 1-page resume — every claim grounded in your `workExperience.md` proof codes
2. A tailored cover letter
3. PDFs compiled via `compile_single.py` after verification

Output for finished applications lands in `data/submissions/[company-name]/`.

### Editing documents

Click any asset in the detail panel to open the visual editor:

- **Left pane:** Live PDF preview that reloads on save
- **Right pane:** Rich-text WYSIWYG editor (Toast UI)

Saving auto-runs the style compliance guard and recompiles the PDF. Use the **AI Rewrite** field to issue natural-language instructions for targeted document edits — it follows your primary provider unless you pin a different first-choice from **Settings → AI Usage**.

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

**Last verified against the actual file tree 2026-08-07** — this section had drifted stale before (see the note at the end of it); if you find it wrong again, fix it in place rather than letting it rot, since it's the map both engineers and coding agents are meant to check before grepping the codebase to relocate something.

```
server/
  index.ts          — Entry point: middleware, router mounts, app.listen
  shared.ts         — Shared path constants, buildPythonEnv (PYTHONUNBUFFERED only), resolveCompanyFolder
  db.ts             — SQLite init, logActivity helper
  scout.ts          — Scout run orchestrator: checkpoints, stderr routing, delegates connector-level work to services/scoutOrchestrator.ts
  middleware.ts     — requireApiToken, isValidJobId, and other cross-route guards
  pipelineLock.ts / migrationRunner.ts / assetProgress.ts / submissionFolders.ts — pipeline concurrency lock, DB migrations, asset-generation progress tracking, submission-folder helpers

  domain/
    jobSearchPrefs.ts — materializeJobSearchPrefs + gate-key preservation (FR-248)
    jobStatus.ts       — canonical job-status rules for submission-folder placement (CR-ARCH-002 / FR-030)
    paths.ts           — PROJECT_ROOT and other path constants
    pythonBin.ts       — resolves the Python interpreter to spawn

  middleware/
    crawlPolicy.ts    — per-host scrape allow/pause/block status, backed by the DB

  pipeline/
    processRunner.ts  — unified subprocess spawning (CR-ARCH-004), transport only, no line parsing

  repository/
    jobRepository.ts             — single write boundary for the jobs table (keeps FTS sync + stale-job bookkeeping from ever being skipped)
    interviewDebriefRepository.ts — interview-debrief CRUD

  routes/
    system.ts / pipeline.ts / profile.ts — /api/system-status·/api/logs, /api/sync (SSE)·/api/sync/stream, /api/profile·/api/experience
    contacts.ts / sources.ts     — networking-contact CRUD, connector source management
    gmailSync.ts / llmUsage.ts   — manual "check inbox now" trigger for the CR-072 Gmail intake sync; GET /api/llm-usage/notifications for provider-cascade events (CR-106)
    jobs/                        — split out from one jobs.ts: index.ts (router mount), crud.ts (CRUD + status transitions), files.ts (ZIP download, PDF assets), debriefs.ts, shared.ts (jobBaseDir helper)

  services/
    scoutOrchestrator.ts   — connector wiring; buildDefaultConnectors() is the single source of truth for which connectors run
    jobMatcher.ts           — CR-072 layered job-matching for inbound Gmail signals (highest-confidence signal first, ambiguous ⇒ skip rather than guess)
    jobStaging.ts / jobStatusService.ts — staging-dir helpers; shared status-transition path used by both the UI route and Gmail sync (CR-072)
    emailClassifier.ts / emailSyncCursor.ts / gmailSyncConfig.ts / gmailClient.ts / gmailSyncOrchestrator.ts / gmailSyncScheduler.ts / interviewDateExtractor.ts / groqClient.ts / geminiClient.ts / llmSettings.ts — CR-072/CR-105/CR-106 Gmail intake sync: free pattern-match classifier first, low-confidence emails fall through to a Groq call (Gemini opt-in as a secondary fallback — see Groq note under "Add your LLM provider"), interview date/time extraction with auto-status-write when eligible, per-label processed-message cursor, dry-run-by-default config, client, orchestrator, background scheduler
    clusterDedup.ts / ingestDedup.ts — job de-duplication on ingest
    exportPendingReview.ts  — exports scraped, gate-passed jobs to data/pending_review/ for Stage 0 (skips ledger hits)
    theirstackCreditLedger.ts / ollamaLifecycle.ts — TheirStack API credit tracking; local Ollama process lifecycle
    stage0SkipLedger.ts     — URL-normalized Stage 0 skip lookup (CR-091; keep in sync with scripts/stage0_skip_ledger.py)

scripts/
  Scout/scrape (TypeScript):
    scout_local.ts        — 7-source parallel job scraper (reads candidate_preferences.json)
    scrape_new_jobs.ts    — fetches full JD text for newly discovered jobs
    archive/backfill_urls.ts — URL backfill crawler (spawned automatically after scout)

  Workflow authority (CR-076–084 — canonical entry point):
    run_submission.py              — sole writer of workflow_state.json + stage_receipts/; Stage 0→1→2→3
    workflow/                      — state, receipts, transitions, policy, runner, reviews, invalidate, entry_warning

  Stage 0 / fit gates (Python) — workers under run_submission, not the default CLI entry:
    build_stage0_fit_gate.py — deterministic Stage 0 fit gate (orchestrator calls this)
    stage0_skip_ledger.py / stage0_placement.py — skip memory (URL then company+title) + pending_review/submissions/skipped folder moves (CR-091)
    import_csv_to_submissions.py — CSV → data/pending_review/ (does not write submissions/)
    stage0_db_gate.py / stage0_prefs_gate.py — DB application-history and preferences sub-gates
    domain_gate.py / industry_gate.py / seniority_gate.py / solo_pm_gate.py / anchor_gate.py — individual hard gates
    evidence_scale.py — CR-093 evidence-scale fit engine (per-requirement 0-4 judgment, weighted formula, score bands from data/fit_rubric_calibration.json)
    zero_shot_classifier.py — location zero-token gate

  CR-074 authoring packet (Stage 1 workers under run_submission):
    build_authoring_packet.py         — builds the lean authoring_packet.json (JD evidence map + workExperience excerpts + claim constraints + packet-supported ATS term contract)
    generate_authoring_rule_digest.py — builds authoring_rule_digest.md (~1.6k-token rule digest)
    author_from_packet.py             — prompt emit + Stage 1 exit gate (--verify-only), including evidence/ATS utilization, pair repetition, JD specificity, document quality, and rebuilt-packet sentence provenance
    packet_evidence_utilization.py    — deterministic ranking of packet-selected evidence to prevent high-priority retrieved claims being omitted
    authoring_defect_categories.py    — CR-097 rule_id → category map
    authoring_examples.py             — CR-097 retrieval-scoped example selection for Stage 1 packets
    scan_authoring_defects.py         — CR-097 cross-submission ledger, 2-occurrence reviews, --status/--promote/--report
    import_historical_defects.py      — CR-099 structured historical baseline, isolated from live metrics

  Full-pack path (optional, non-default — see CLAUDE.md):
    generate_context_pack.py / check_context_pack_freshness.py — agent_context_pack.md generation + freshness check

  Verification / QA (Mech 2D under run_submission — see "Required Verification Before You're Done" in CLAUDE.md):
    verify_submission.py           — lint + structure/QA + unapproved-metrics + page-count check in one pass, writes verification_receipt.json; --audit flags byte-identical rubric scores across submissions (worker; prefer --resume)
    submission_linter.py           — LR/LW rule engine (forbidden language, structural hard blocks)
    check_ground_truth_coverage.py — unused-claim sweep against master_claims_tags_only.json, writes ground_truth_coverage.json
    jd_term_extractor.py           — this JD's own hard-skill/tool term-gap sweep (CR-073), writes jd_term_gaps.json
    quality_checker.py             — structure auto-repair (cover-letter header/sign-off, resume section headings)

  Cover letter subsystem:
    cover_letter_plan.py / cover_plan_builder.py — plan construction
    cover_claim_picker.py / cover_jd_needs.py     — proof-point selection, JD-requirement extraction
    cover_letter_compiler.py / cover_letter_renderer.py — compile/render the final letter
    cover_letter_slots.py / cover_letter_structure.py / cover_narrative_templates.py / cover_phrasing.py / cover_prose.py — structural template + phrasing helpers
    cover_letter_audit.py — audit pass

  Claims / vocabulary:
    claim_catalog.py / claim_composer.py / claim_provenance.py — master_claims.json access layer, claim assembly, attribution tracking (owned/contributed/influenced — see LW-028)
    generate_master_claims.py — regenerates master_claims.json + the tags-only sidecar
    voc_map.py — codename → plain-language translation (VOC codes)

  Style/tone guards:
    tone_guard.py             — R-011 layoff-language guard
    style_compliance_guard.py — resume/cover-letter format validation
    pii_guard.py               — PII-leak guard

  Compilation:
    compile_single.py  — Markdown → PDF via Playwright
    draft_compiler.py  — unified resume/cover compiler (CR-014)
    drafting_engine.py — entry + research + hard-fact guards, delegates to draft_compiler

  Batch orchestration / maintenance:
    batch_pipeline.py       — DB/JD helper library only (CR-093, 2026-08-19: evaluate_job_fit()/process_single()/process_batch() and the whole old fit-scoring + --mode single|batch CLI removed; no longer directly executable)
    local_draft_stages.py   — stage-based local drafting, builds the Core Competencies section (FR-195)
    finalize_submission_job.py / reconcile_submissions.py — job finalization; archive/remove stale submission folders (FR-030)
    audit_all_submissions.py / audit_and_improve.py / audit_improve_native.py — audit/improvement passes
    regenerate_all_resumes.py / regenerate_all_cover_letters.py / regenerate_all_submissions.py — bulk regeneration utilities
    prefs_rollout.py / apply_gate_rollout.py — one-time gate-prefs migration (see Manual utilities below)
    research-engine.py / generate_experience_summary.py / ai_rewrite.py / utils.py / llm_stages.py — company intelligence lookups (Gemini-search, not on taskProviderOverrides), auto-generated scoring brief (overridable via Settings → AI Usage), LLM-powered manual editing (same), shared LLM-call/path/file-I/O helpers, legacy UI Draft per-stage provider map

  test_*.py (~55 files) — one test module per script above; run the full suite via `npm test` / `run_all_tests.py`

  archive/ — one-off historical/diagnostic scripts (batch imports, calibration harnesses, dry-run diagnostics). Not part of the live pipeline — don't treat anything in here as current behavior, and don't grep here first when tracing how something works today.

src/
  App.tsx           — Root: 5s job poll, status handler, routing
  pages/            — TodayView, AllJobsView, SyncActivityView, TuningLogView
  components/       — JobDetailPanel, DocumentEditor, SettingsView, Sidebar, ...

data/
  ats-pipeline.md               — Optional manual ATS queue for GET /api/ats-pipeline
  candidate_preferences.json    — Materialized search/scoring config (auto-written by server)
  workExperience.md             — Full codified work history (edited via Settings > Experience)
  workExperience_summary.md     — Condensed scoring brief (auto-generated on every experience save)
  candidate_preferences.example.json — Template for gate rollout keys (blocked_role_titles, etc.)
  (Authoring/verification content files — master_claims.json, conversion_rubric.md, Resume.md, Cover_Letter_Reference.md, etc. — are catalogued in CLAUDE.md's own File Map table, not duplicated here; this list is infra files the server itself reads/writes.)

.agent/
  rules/claim_verifier.md — the one rule file still live (reference-only, trigger: manual)
  DEPRECATED.md — everything else that used to live under .agent/ (job_fit_engine.md, the old workflows/skills files) is archived here with a "use instead" pointer; read it before assuming any other .agent/ path is current. job_fit_engine.md's Stage-0 role was superseded by .claude/skills/generate-submission/SKILL.md; the master Resume.md and Cover_Letter_Reference.md templates now live at data/Resume.md and data/Cover_Letter_Reference.md, not under .agent/.
```

This section previously listed `.agent/rules/job_fit_engine.md`, `Resume.md`, and `Cover_Letter_Reference.md` as live, and `server/` with only 5 top-level files — both wrong by the time this was caught (2026-08-07): the rule files had been archived and the master templates moved to `data/`, and `server/` had grown `domain/`, `middleware/`, `pipeline/`, `repository/`, and a 14-file `services/` directory (CR-072 Gmail sync) with nothing here describing any of it. Caught only because a token-efficiency question prompted a from-scratch grep against the real tree instead of trusting this section — don't let that be the only trigger next time.

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
| `python scripts/archive/calibration_harness.py` | Compare structured vs legacy fit scores on stored JDs (archived — compares against the pre-CR-074 legacy scorer, not the current default path) |
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
| [docs/ACTIVE_WORKFLOW.md](./docs/ACTIVE_WORKFLOW.md) | Runtime workflow for operators — scout, triage, author, verify, finalize |
| [docs/system-invariants.md](./docs/system-invariants.md) | Non-negotiable truth, workflow, privacy, and derived-artifact rules |
| [docs/interview-prep-ux-discovery.md](./docs/interview-prep-ux-discovery.md) | Discovery brief for the future interview-prep module |
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
