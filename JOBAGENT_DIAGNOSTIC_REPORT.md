# JobAgent Diagnostic Report

**Audit date:** 2026-07-04  
**Scope:** Diagnosis only — no fix proposals  
**Database snapshot:** `data/jobagent.sqlite` (1,011 job rows)  
**Codebase:** Applyr repo (`server/`, `packages/connectors/`, `scripts/`)

---

## System Summary

JobAgent is the discovery-and-evaluation front half of Applyr: a TypeScript/Playwright/SQLite application that pulls job postings from 17 configurable connectors, stores them in `data/jobagent.sqlite`, optionally scrapes missing descriptions with Playwright, and runs a Python fit-scoring + asset-drafting pipeline (`scripts/batch_pipeline.py`) against local Ollama/GPU models. The UI triggers a full sync via `POST /api/sync`, which runs scout orchestration → URL backfill → JD scrape → batch evaluate/draft. Manual evaluation bypasses connectors entirely: the user pastes a full job description into `JDInputForm`, which streams `batch_pipeline.py --mode single` with the JD on stdin. The automated path and manual path share the same scoring engine but differ sharply in what text reaches that engine.

---

## Pipeline Map

End-to-end stages, inputs each stage assumes, and where data lives:

| # | Stage | Trigger | Input assumed | Output / side effects |
|---|--------|---------|---------------|------------------------|
| 1 | **SCOUT (connector fetch + ingest gates)** | `runConnectorOrchestration()` in `server/services/scoutOrchestrator.ts` | Each connector returns `{ title, company, url, description? }`. Title gates assume PM-family titles match `passesTargetRoleTitleScope`. Description may be empty, truncated (1500 chars), or RSS snippet. | Rows inserted into `jobs` with `status='Drafted'` if `description.length >= 200`, else `status='New'` and `jd_text=NULL`. Staging file written only when `hasJd`. Activity log: `{source}: N fetched, M saved`. |
| 2 | **BACKFILL** | `scripts/backfill_urls.ts` | Jobs missing usable URLs | URL reconciliation (details in backfill script; not primary relevance driver). |
| 3 | **SCRAPE** | `scripts/scrape_new_jobs.ts` | Jobs with `status='New'` and a non-blocked URL | Playwright extraction via `extract_job_page.ts`. On success: `jd_text` populated, `status='Drafted'`, `jobs/{company}_{id8}.txt` written. On failure: job stays `New` with null `jd_text` — **no hard failure**. ATS redirect → empty text, no throw. |
| 4 | **EXPORT STAGING** | `scripts/export_staging_from_db.ts` | `status='Drafted'` AND `jd_text >= 200 chars` AND title passes target-role scope | Writes missing `jobs/*.txt` from DB for batch consumption. |
| 5 | **EVALUATE + DRAFT** | `batch_pipeline.py --mode batch` | Staging files in `jobs/` (or DB `jd_text` fallback). JD must include parseable content; title line extracted from staging header for zero-token gates. | Fit score, summary, status updates (`Backlog` / `Rejected` / `Needs Retry`). **`jd_text` is not written back** on evaluate — only score/summary/status. Scoring uses first **1500 chars** (`SCORING_JD_MAX_CHARS`). |
| — | **Manual evaluate (parallel path)** | `POST /api/evaluate` → `batch_pipeline.py --mode single` | Full pasted JD on stdin (typically 4k–7k+ chars from user clipboard). Company name required; URL optional. | Same gates + fit + draft. Full JD used for drafting; fit LLM still sees truncated 1500 chars. Does not require prior DB row or connector ingest. |

**Workday note:** There is **no Workday connector**. Workday appears only as a blocked ATS redirect target in `scripts/extract_job_page.ts` (`myworkday.com`, `workday.com`). When Built In or another listing links straight to a Workday tenant, the scraper returns `{ text: '' }` and the job never gets a description in DB.

---

## Funnel Numbers

### Lifetime (all rows in `jobagent.sqlite`)

| Stage | Count | Notes |
|-------|------:|-------|
| Total jobs in DB | **1,011** | Includes legacy imports, CSV, manual, and automated |
| Missing or short JD (`jd_text` NULL or &lt;200 chars) | **658** (65%) | Cannot be reliably fit-scored from DB alone |
| Usable JD in DB (≥200 chars) | **353** (35%) | Avg length **3,323 chars** where present |
| Any fit score ≥72 (min threshold) | **207** | Inflated vs quality — see below |
| Score ≥72 **and** usable JD | **42** | **4.2%** of all jobs; **20%** of threshold-passers |
| Score ≥72 but **no** usable JD | **165** | Legacy/title-only evaluation artifacts |
| Status = Rejected | **587** | |
| Status = Closed | **347** | |
| Status = Backlog (apply-ready queue) | **2** | Nearly empty at audit time |

### Most recent full scout run (from `activity_log`, summed across 17 connectors)

| Metric | Count |
|--------|------:|
| Raw postings fetched | **250** |
| Saved to DB after ingest gates | **1** |
| Filter rate at ingest | **99.6%** |

Per-connector lines from that run (newest first):

```
remotive: 31 fetched, 0 saved
remoteok: 0 fetched, 0 saved
weworkremotely: 29 fetched, 0 saved
himalayas: 0 fetched, 0 saved
themuse: 1 fetched, 0 saved
jobicy: 24 fetched, 0 saved
workingnomads: 0 fetched, 0 saved
jobscollider: 100 fetched, 1 saved
adzuna: 0 fetched, 0 saved
openpostings: 0 fetched, 0 saved
builtin: 37 fetched, 0 saved
levelsfyi: 0 fetched, 0 saved
greenhouse: 28 fetched, 0 saved
lever: 0 fetched, 0 saved
ashby: 0 fetched, 0 saved
workable: 0 fetched, 0 saved
theirstack: 0 fetched, 0 saved
```

**Interpretation:** The largest signal loss in *recent* runs is **ingest filtering** (duplicate URL, title scope, geographic gate, blocklist) — not fit scoring. Historical DB volume predates current gate strictness and includes off-role titles from loose API sources.

### Source × JD coverage × pass rate (lifetime DB)

| source_site | Jobs | With JD ≥200 | Score ≥72 |
|-------------|-----:|-------------:|----------:|
| *(null)* — legacy/LinkedIn/local | 367 | 12 | 132 |
| Himalayas | 171 | 77 | 2 |
| Built In | 165 | 54 | 7 |
| jobscollider | 119 | 119 | 4 |
| Adzuna | 58 | 3 | 18 |
| builtin (lowercase, newer) | 23 | 23 | 12 |
| greenhouse | 21 | 21 | 3 |
| OpenPostings | 9 | 0 | 8 |
| CSV Import | 7 | 0 | 7 |

---

## Findings Per Source

Connectors are registered in `buildDefaultConnectors()` (`server/services/scoutOrchestrator.ts` lines 92–118). Each implements `fetchJobs()` + `normalize()`. **None use a unified Workday API** — ATS integrations are per-vendor, per-company slug.

---

### 1. Built In (`packages/connectors/builtin/index.ts`)

**Architecture:** Playwright scraper against `builtin.com/jobs/remote/mid-level?search=…`. Per-site HTML selectors, not an API. Uses **first search term only** from prefs (`searchTerms[0]`), not all four configured terms.

**Query parameters sent:** `search=Product Manager` (from prefs), `daysSinceUpdated=7`, `country=USA`, up to 2 pages.

**Critical evidence — listing cards store empty descriptions:**

```122:127:packages/connectors/builtin/index.ts
                results.push({
                  external_job_id: url,
                  url,
                  source_id: 'builtin',
                  raw_data: { title, company, url, description: '' },
                });
```

Every Built In job enters DB as `status='New'`, `jd_text=NULL`. Relevance depends entirely on **Stage 3 scrape**.

**Title gate:** Stricter than other sources — requires literal `"product manager"` in title (`passesBuiltInPmTitleScope`), excludes Product Owner-only titles and product marketing/devops patterns.

**Scrape failure modes:**
- `extract_job_page.ts` detects ATS redirect (including Workday) and returns **empty text without error**:

```220:225:scripts/extract_job_page.ts
        if (ATS_DOMAINS.some(d => finalUrl.includes(d))) {
            console.log(`[LOG] extract_job_page: ATS redirect ${url} → ${finalUrl}`);
            return { text: '', source: 'body', confidence: 'low', flags: ['external_ats_redirect'] };
        }
```

- Selector staleness risk: card loop uses `.job-item, div[data-id="job-card"]` with silent `catch { break }` on page errors and `catch { /* skip */ }` on malformed cards.

**DB evidence:** 165 rows (`Built In`) + 23 (`builtin` casing split). Only 54+23 have JD. 7+12 pass score ≥72 when JD exists, scores often ~85 (suggesting full scrape helps).

**Selector verification:** No automated freshness check or last-verified timestamp in repo. Empty-card break on `cards.length === 0` exits pagination silently.

---

### 2. Himalayas (`packages/connectors/himalayas/index.ts`)

**Architecture:** JSON API — `https://himalayas.app/jobs/api?roles={slug}&limit=50` per search term slug.

**Query:** `roles=product-manager`, `product-owner`, etc. (slugified from `searchTerms`).

**No client-side title filter** in connector — relies on orchestrator `passesBroadPmTitleScope`.

**Description handling:** API description HTML-stripped and **truncated to 1500 chars** at normalize.

**DB evidence — API returns off-role jobs that polluted historical DB:**

| company | title | score | jd_len |
|---------|-------|------:|-------:|
| INFUSE | Middle Project Manager (Remote, Contract) | 87 | NULL |
| QHR | Manager, Follow Up | 85 | 1500 |
| agile six | Production Support Specialist | 38 | 1500 |
| Johnson & Johnson | Sales Training Manager, Sports Medicine | 38 | 1500 |

171 Himalayas jobs; only **2** score ≥72 despite 77 having JD. High volume, very low relevance yield.

**Recent run:** `himalayas: 0 fetched, 0 saved` — either API returned nothing or all filtered at ingest (likely duplicates after historical saturation).

---

### 3. JobsCollider + We Work Remotely (RSS feeds)

**Architecture:** RSS XML parsers. **No search-term filter at fetch** — entire category feeds:
- JobsCollider: `https://remotefirstjobs.com/remote-product-jobs.rss`
- WWR: `https://weworkremotely.com/categories/remote-product-jobs.rss`

**Query/filter:** Title parsing only (`"Title at Company"` / `"Company: Title"`). All items returned; PM relevance deferred to orchestrator title gate.

**Description:** RSS `<description>` HTML-stripped, capped at 1500 chars. Often enough to pass 200-char ingest threshold → `Drafted` without scrape.

**DB evidence:** jobscollider 119 jobs, **all 119** have JD; only **4** pass ≥72. Feed is high-volume "remote product" category, not PM-specific.

**Recent run:** jobscollider 100 fetched → 1 saved (99% ingest filter).

---

### 4. Adzuna (`packages/connectors/adzuna/index.ts`)

**Architecture:** Aggregator REST API per search term.

**Query parameters:**

```39:45:packages/connectors/adzuna/index.ts
        const params = new URLSearchParams({
          app_id: appId,
          app_key: appKey,
          results_per_page: '50',
          what: term,
          'content-type': 'application/json',
        });
```

`what` = each of `searchTerms` (Product Manager, Product Owner, Technical Product Manager, Platform Product Manager). Broad by design.

**Description:** API `description` field, truncated 1500. Often **under 200 chars** (aggregator snippet) → `New` without `jd_text`.

**Credentials gate:** Returns `[]` if `ADZUNA_APP_ID` / key missing — **silent empty source**, no error surfaced to UI beyond 0 fetched.

**DB anomaly:** 58 jobs, **only 3** with JD, but **18** score ≥72; **15** of those pass without JD. Suggests historical evaluation from staging/title-only before JD persistence rules, or evaluate path that scored without backfilling `jd_text`.

**Recent run:** `adzuna: 0 fetched` — credentials empty or quota exhausted.

---

### 5. Greenhouse / Lever / Ashby / Workable (per-company ATS APIs)

**Architecture:** **Not unified.** Each vendor exposes a **per-company board endpoint**:

| Connector | Example endpoint | Default company slugs |
|-----------|------------------|------------------------|
| Greenhouse | `boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | stripe, shopify, figma, notion, linear |
| Lever | `api.lever.co/v0/postings/{slug}?mode=json` | netflix, dropbox, twilio, zendesk |
| Ashby | per-company GraphQL/board | (configured slugs) |
| Workable | per-company REST | linear, flight-control |

**Title filter at fetch:** `searchTerms.some(t => titleLower.includes(t))` — substring match, allows "Associate Product Manager" unless blocklist catches it.

**Description:** Full HTML content from API, stripped, **truncated to 1500** at normalize. Usually ≥200 → immediate `Drafted`.

**Silent failure:** Company fetch errors use `catch { continue }` — failed board = skipped with no log line.

**Workday:** These boards are **not** Workday. Jobs hosted on Workday never flow through these connectors unless listed on a Greenhouse/Lever board.

**Recent run:** greenhouse 28 fetched, 0 saved (all duplicates or filtered).

---

### 6. Remotive / RemoteOK / Jobicy / Working Nomads / The Muse

**Architecture:** Public JSON/RSS APIs.

**Query:** Remotive/Jobicy pass `searchTerms` to API query params. RemoteOK/others vary.

**Normalize:** Universal **1500-char description cap**.

**Geographic gate bug (evidence):** `REMOTE_ONLY_SOURCES` uses display names (`'Remotive'`, `'Himalayas'`) but orchestrator passes lowercase `sourceId` (`'remotive'`, `'himalayas'`):

```31:39:shared/domain/gates.ts
const REMOTE_ONLY_SOURCES = new Set([
  'Remotive',
  'RemoteOK',
  ...
]);
```

```171:171:server/services/scoutOrchestrator.ts
            source,
```

When `work_setting=Remote` and description &lt;50 chars, jobs from `remotive` may be **incorrectly rejected** at geographic gate (`remote_only_no_location_signal`) because `REMOTE_ONLY_SOURCES.has('remotive')` is false. DB shows split casing: `Remotive` (5) vs `remotive` (4).

---

### 7. OpenPostings (`packages/connectors/openpostings/index.ts`)

**Architecture:** Spawns local Node server from `OpenPostings-extracted/OpenPostings-main` (default path). Queries `GET /postings?search={term}&remote=remote`.

**Description:** Passes through `d['description']` if present in API payload — **no truncation in normalize**, but ingest often gets **no description field** in listing response.

**DB evidence:** 9 jobs, **0** with JD, **8** score ≥72 — title/metadata-only evaluation legacy.

**Failure modes:** Missing directory → returns `[]` silently. Server start/sync errors caught with `catch { /* return empty */ }`.

**Recent run:** 0 fetched (directory/server likely unavailable).

---

### 8. Levels.fyi (`packages/connectors/levelsfyi/index.ts`)

**Architecture:** Playwright on `levels.fyi/jobs?jobId=1`. Scrapes anchor tags; title filter applied **in connector** via `passesTargetRoleTitleScope`.

**Description:** **Never fetched** — normalize omits description entirely:

```112:121:packages/connectors/levelsfyi/index.ts
    normalize(raw: RawJobPayload): NormalizedJob {
      ...
        source_site: 'levelsfyi',
      };
    },
```

All Levels.fyi jobs → `New` → require scrape. **Recent run:** 0 fetched (policy block or empty page).

---

### 9. TheirStack (`packages/connectors/theirstack/index.ts`)

**Architecture:** Paid API `POST https://api.theirstack.com/v1/jobs/search` with `job_title_or: searchTerms`, `job_country_code_or: ['US']`, `posted_at_max_age_days: 14`.

**Requires API key** — returns 0 if missing.

**Recent run:** 0 fetched, 0 saved.

---

### 10. CSV Import / Manual Eval (non-scraper paths)

**CSV import** (`scripts/import_csv_jobs.py`):
- Writes **full** JD to `jobs/{company}_{id}.txt` with `Title:` header.
- Inserts DB row **without** `jd_text`: `INSERT INTO jobs (id, company, title, url, status) VALUES (..., 'New')`.
- Batch evaluate reads staging file → full JD available to pipeline; DB `jd_text` stays NULL unless manually backfilled.

**Manual evaluate** (`server/routes/pipeline.ts` + `JDInputForm.tsx`):
- User pastes full JD (placeholder: "Paste the full job description here…").
- JD sent on **stdin** to `batch_pipeline.py --mode single` — no 1500-char cap at ingest.
- Bypasses connector title noise, scrape failures, and ATS redirects.

**This is the primary explainable quality gap** between Jason's CSV/manual runs (7–17 jobs, most with full JD in staging) and automated scout rows sitting at `jd_text=NULL`.

---

## Silent Failures and Degraded Responses

| Location | Behavior | Impact |
|----------|----------|--------|
| `scoutOrchestrator.ts:222-227` | Empty `catch` on `insertJob` / normalize failure → `filtered++`, **no log** | Lost jobs with no audit trail |
| `scoutOrchestrator.ts:225-227` | Outer per-job `catch { filtered++ }` | Swallows connector normalize exceptions |
| Built In card loop `catch { /* skip */ }` | Malformed cards dropped silently | Under-counted fetch yield |
| Built In page loop `catch { break }` | Pagination stops on any error | Partial fetch looks like complete fetch |
| Greenhouse/Lever/etc. `catch { continue }` | Whole company board skipped | Missing companies with no activity log |
| `extract_job_page.ts` ATS redirect | Returns empty text, exit 0 | Jobs stuck `New` forever |
| `extract_job_page.ts` extraction fail | Returns `{ text: '', flags: ['extraction_failed'] }` | Log line only; no DB status change |
| `scrape_new_jobs.ts:52` | "too short" → log, continue | No retry queue marker |
| Adzuna/Theirstack/OpenPostings | Missing creds/dir → `return []` | Source appears "healthy" with 0 jobs |
| OpenPostings sync | `fetch(.../sync/ats).catch(() => {})` | Sync may not complete; still queries postings |
| `batch_pipeline.py _set_backlog` | Updates score/summary, **not** `jd_text` | Scored jobs can show pass with NULL JD in UI |
| Geographic gate source ID mismatch | Wrong casing → remote sources not exempt | False geographic rejects for short descriptions |

**Bot-detection / rate-limit evidence:** Playwright stealth plugin used (`puppeteer-extra-plugin-stealth`). No captcha detection logic — a challenge page could be parsed as body text or fail length check silently. Adzuna enforces 3s gap between calls (`callGapMs: 3000`). Built In uses `humanWait(2000, 4000)` between pages. No metrics on HTTP 429 or repeated identical payloads in DB.

---

## Manual vs Automated Evaluation — Input Path Diff

| Dimension | Automated pipeline | Manual paste / CSV import |
|-----------|-------------------|---------------------------|
| JD source | Connector API/RSS (≤1500 chars) or Playwright scrape (≤15000, often fails) | User clipboard / CSV column (full text, often 4k–7k+) |
| Title noise | Broad APIs (Himalayas role slug), RSS category feeds, `Product Owner` in search terms | User-selected rows; explicit PM listings |
| Ingest gate | `passesBroadPmTitleScope` allows Product Owner, `(platform\|data\|…) product` | Same gates if run through batch |
| JD in SQLite | Often NULL (65% of DB) even after scoring | NULL in DB but **present in staging file** |
| Fit LLM input | First 1500 chars only (`SCORING_JD_MAX_CHARS`) | Same 1500-char truncation for **scoring** |
| Drafting input | Truncated if from connector; fuller if scrape succeeded | Full pasted JD for asset generation |
| Zero-token gates | `passes_title_gate` extracts title from **JD text** (`Title:` line in staging) | CSV staging includes `Title:` line → gates work correctly |
| Persistence | Score written; JD often not backfilled to DB | Same — but user never relies on DB JD column |

**Example — title-only false pass (Himalayas legacy):** "Middle Project Manager" scored **87** with **NULL** `jd_text`. Broad title gate at ingest (historical) or evaluate without body text produced a high score disconnected from PM relevance.

**Example — CSV batch (Jul 2026):** 17 imported jobs with full descriptions in staging; 10 passed fit (88) when evaluated with complete JD text. Same engine, richer input.

---

## Title Filter Breadth (contributes to volume)

Configured `search_terms` in `data/candidate_preferences.json`:

```json
["Product Manager", "Product Owner", "Technical Product Manager", "Platform Product Manager"]
```

`passesBroadPmTitleScope` (`shared/domain/gates.ts`) **allows**:
- `product manager`, `product owner`
- `(technical|platform|data|ai|api|integration|enterprise|infrastructure) product`

**Blocks** (among others): product marketing, program manager, project manager, solutions engineer.

**DB title counts:** Product Owner **56**, Product Marketing **11** (some slip through on non-BuiltIn sources if title phrasing avoids regex), APM **5**.

Built In uses **stricter** `passesBuiltInPmTitleScope` (PM literal required); other sources use broad scope — explains why Built In + builtin sources show better precision but lower volume.

---

## Root Cause Hypotheses (ranked by confidence)

### H1 — Missing or truncated JD body (HIGH)

**Evidence:**
- 65% of DB rows lack usable `jd_text`.
- Built In stores `description: ''` on ingest; Levels.fyi omits description; OpenPostings/Adzuna often have no/short body.
- All API normalizers cap at 1500 chars; fit scoring caps again at 1500.
- Only 42/207 threshold-passers have usable JD.
- Manual/CSV path supplies full JD via stdin/staging.

**Would confirm:** Compare fit scores for same URL with full pasted JD vs connector-ingested JD. Measure scrape success rate for `status='New'` Built In rows.

**Would disconfirm:** If scrape succeeds >90% and scores still cluster low with full JD in DB.

---

### H2 — High-volume sources return off-role titles despite PM-ish queries (HIGH)

**Evidence:**
- Himalayas API `roles=product-manager` returned "Production Support Specialist", "Sales Training Manager", etc.
- JobsCollider/WWR ingest entire "remote product jobs" RSS without PM title filter at source.
- 171 Himalayas rows → 2 pass ≥72.
- Historical INFUSE "Project Manager" scored 87 without JD.

**Would confirm:** Log raw titles from Himalayas API on next fetch; count % passing `passesBroadPmTitleScope` before vs after ingest.

**Would disconfirm:** If API results are PM-pure and losses happen only at fit scoring.

---

### H3 — Two-hop Built In + ATS redirect scrape failure (HIGH for Built In slice)

**Evidence:**
- Empty description at listing ingest.
- `extract_job_page` returns empty on Workday/Greenhouse/Lever redirect without error.
- 165 Built In jobs, 54 with JD (~33% scrape success implied).

**Would confirm:** Run scrape stage on Built In `New` rows; count `external_ats_redirect` vs `extraction_failed` log flags.

**Would disconfirm:** If failures are DOM selector staleness rather than redirects.

---

### H4 — Score persistence without JD creates misleading "passed" inventory (MEDIUM)

**Evidence:**
- 165 jobs score ≥72 with no JD; Adzuna 15/18, null source 126/132.
- `_set_backlog` updates score/summary only.
- UI/metrics counting passers overstate apply-ready pool (actual Backlog = 2).

**Would confirm:** Audit whether any evaluate path ran with &lt;200 char staging files. Check `summary` field for title-only LLM prompts.

**Would disconfirm:** If all 165 have staging files on disk that were deleted post-evaluate.

---

### H5 — Geographic gate source ID casing mismatch (MEDIUM)

**Evidence:**
- `REMOTE_ONLY_SOURCES` uses `'Remotive'`; orchestrator passes `'remotive'`.
- Short-description remote jobs may fail geographic gate incorrectly.

**Would confirm:** Unit test with `source='remotive'`, empty description, `workSetting='Remote'` → reject. Fix casing → pass.

**Would disconfirm:** If rejected remotive jobs all fail on other gates first.

---

### H6 — Recent ingest gates are extremely strict → "high volume" is historical, not current (MEDIUM)

**Evidence:**
- Last run: 250 fetched → 1 saved (99.6% filtered).
- Duplicates (`isUrlKnown`, `isCompanyTitleNew`) dominate after initial DB fill.
- User-perceived "high volume" may be UI listing all historical rows including Closed/Rejected.

**Would confirm:** Compare jobs `created_at` histogram vs scout saved counts.

**Would disconfirm:** If new runs still insert dozens of off-role jobs per sync.

---

### H7 — Selector/HTML staleness on Playwright sources (LOW–MEDIUM)

**Evidence:**
- Built In waits for `.job-item, div[data-id="job-card"]` with empty catch → break.
- Recent builtin: 37 fetched, 0 saved (could be duplicates OR empty card list).
- No last-verified date for selectors in repo.

**Would confirm:** Live fetch showing `cards.length === 0` on valid search page.

**Would disconfirm:** If 37 jobs parsed but all rejected by duplicate/title gates.

---

### H8 — Rate limiting / bot detection (LOW, insufficient data)

**Evidence:**
- Stealth plugin present; human-like waits on Built In/Levels.fyi.
- No captcha detection; no 429 metrics.
- Some sources returned 0 without error detail (credentials, policy).

**Would confirm:** HTTP 429/403 in connector logs; captcha HTML in scrape debug body length dumps.

**Would disconfirm:** Clean 200 responses with valid JSON/RSS on all sources.

---

## Open Questions

1. **What percentage of current `status='New'` rows are Built In vs other sources?** At audit time `New=0`, so scrape backlog is empty — routine sync may not be exercising scrape at all.

2. **When were the 165 score≥72 / no-JD rows evaluated?** Pre-CR-053 legacy pipeline may have used different prompts or title-only inputs.

3. **Is `OpenPostings-extracted/OpenPostings-main` present on Jason's machine?** Recent 0 fetched suggests path or server failure; health check only verifies directory exists.

4. **Are Adzuna/Theirstack API keys configured in production?** Both returned 0 fetched in last run.

5. **Does Himalayas `roles=` slug actually filter server-side, or is it a taxonomy hint that returns loosely related jobs?** Sample data strongly suggests loose matching.

6. **What is the scrape success rate by domain** (builtin.com vs levels.fyi vs generic ATS redirect targets)? No aggregated metric exists today.

7. **Why do null `source_site` rows (367) dominate high scores without JD?** Likely early LinkedIn/manual imports — provenance not tracked.

8. **Is the UI "job list" sorted/filtered in a way that surfaces low-quality historical rows** rather than recent scout saves?

9. **Workday tenant pages:** Should redirect detection fetch the external ATS page instead of giving up? Currently by design returns empty — no connector handles Workday natively.

10. **For fit scoring, how much score variance exists on the same job at 1500 vs 5000 chars?** Not measured in this audit; manual advantage may be partly in drafting (full JD) not just fit score.

---

## Key Code References (quick index)

| Concern | File |
|---------|------|
| Connector registry | `server/services/scoutOrchestrator.ts` |
| Ingest MIN_JD_CHARS=200 | `server/services/scoutOrchestrator.ts:35,204-216` |
| Title scope gates | `shared/domain/gates.ts` |
| Scout pipeline stages | `server/scout.ts` |
| Playwright JD extract | `scripts/extract_job_page.ts` |
| Scrape stage | `scripts/scrape_new_jobs.ts` |
| Fit scoring truncation | `scripts/utils.py` (`SCORING_JD_MAX_CHARS = 1500`), `batch_pipeline.py:739-740` |
| Manual evaluate stdin | `server/routes/pipeline.ts:38-60`, `batch_pipeline.py:1439-1448` |
| CSV import (staging only) | `scripts/import_csv_jobs.py` |
| 1500-char normalize pattern | `packages/connectors/*/index.ts` (most connectors) |

---

*End of diagnostic report. No remediation recommendations included by scope.*
