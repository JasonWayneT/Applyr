# Requirements Registry

This is the canonical list of project requirements. Feature specs, tasks, tests, and code changes must trace back here.

## ID naming convention

| Prefix | Category | Example |
|---|---|---|
| `FR` | Functional requirement | `FR-001` |
| `NFR` | Non-functional requirement | `NFR-001` |
| `SEC` | Security/privacy requirement | `SEC-001` |
| `DES` | Visual design requirement | `DES-001` |
| `DATA` | Data requirement | `DATA-001` |
| `INT` | Integration requirement | `INT-001` |
| `AC` | Acceptance criterion | `AC-001` |

## Status values

- `draft`: proposed but not accepted
- `accepted`: approved source of truth
- `implemented`: implemented in code
- `verified`: implemented and validated

## Requirement records

### Scouting & Ingestion (FR-001 to FR-005)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-001` | functional | P0 | implemented | Multi-source job discovery via Playwright | `AC-001`, `AC-002` | `BMAD-SRC-001` |
| `FR-002` | functional | P0 | implemented | OpenPostings SQLite database scraper | `AC-003` | `BMAD-SRC-001` |
| `FR-003` | functional | P1 | implemented | Job deduplication via URL and Title/Company hash | `AC-004` | `BMAD-SRC-001` |

### Evaluation & Gating (FR-006 to FR-010)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-006` | functional | P0 | implemented | Deterministic Keyword Pre-Filter (Zero Token Gate) | `AC-006` | `BMAD-SRC-005` |
| `FR-007` | functional | P0 | implemented | LLM-based 100-point Job Fit Scoring | `AC-007` | `BMAD-SRC-005` |
| `FR-008` | functional | P0 | implemented | "Two-Anchor Room" validation for YES decisions | `AC-008` | `BMAD-SRC-005` |
| `FR-009` | functional | P1 | implemented | Context Firewall (Memory isolation between jobs) | `AC-009` | `BMAD-SRC-004` |

### Research & Intelligence (FR-011 to FR-013)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-011` | functional | P1 | implemented | Perplexity AI company intelligence fetch | `AC-011` | `BMAD-SRC-007` |
| `FR-012` | functional | P2 | implemented | Research Packet Contract compliance validation | `AC-012` | `BMAD-SRC-007` |

### Drafting & Generation (FR-014 to FR-018)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-014` | functional | P0 | implemented | Bridge Logic: Translate Platform wins to Growth needs | `AC-014` | `BMAD-SRC-004` |
| `FR-015` | functional | P0 | implemented | Resume generation from verified `workExperience.md` | `AC-015` | `BMAD-SRC-006` |
| `FR-016` | functional | P1 | implemented | ATS-optimized, single-column PDF export | `AC-016` | `BMAD-SRC-004` |

### Audit & Quality (FR-019 to FR-022)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-019` | functional | P0 | implemented | Hard Fact Validation (Metric check against source) | `AC-019` | `BMAD-SRC-006` |
| `FR-020` | functional | P0 | implemented | Hallucination Guard: Automatic replacement of lies | `AC-020` | `BMAD-SRC-006` |

### Web Application & API (FR-023 to FR-034)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-023` | functional | P0 | implemented | Express API for pipeline control and log streaming | `AC-023` | `BMAD-SRC-003` |
| `FR-024` | functional | P0 | implemented | Real-time Sync Activity Terminal (polling-based) | `AC-024` | `BMAD-SRC-003` |
| `FR-025` | functional | P1 | implemented | "My Profile" hub with Markdown editor | `AC-025` | `BMAD-SRC-003` |
| `FR-026` | functional | P1 | implemented | Interactive WYSIWYG asset editing via Toast UI | `AC-026` | `BMAD-SRC-003` |
| `FR-027` | functional | P1 | implemented | Single-file background compilation via Python | `AC-027` | `BMAD-SRC-001` |
| `FR-028` | functional | P1 | implemented | Dual-pane Side-by-Side review and editor space | `AC-028` | `BMAD-SRC-003` |
| `FR-029` | functional | P2 | implemented | LLM-assisted document editing with setting-stored key | `AC-029` | `BMAD-SRC-004` |
| `FR-030` | functional | P1 | implemented | Closure & Archival Workflow |  | `BMAD-SRC-003` |
| `FR-031` | functional | P1 | implemented | Job Status Progression Actions |  | `BMAD-SRC-003` |
| `FR-032` | functional | P2 | implemented | Interview Scheduling |  | `BMAD-SRC-003` |
| `FR-033` | functional | P1 | implemented | Bulk Asset ZIP Download |  | `BMAD-SRC-003` |
| `FR-034` | functional | P0 | implemented | Pipeline Paradigm Split |  | `BMAD-SRC-003` |
| `FR-035` | functional | P0 | implemented | End-to-End Automated Background Sync, Evaluation, and Drafting Pipeline | `AC-035` | `BMAD-SRC-005` |
| `FR-036` | functional | P0 | implemented | Triple Redundancy Style Compliance Guard | `AC-036` | User Request |
| `FR-037` | functional | P0 | implemented | SDD Auto-Codification Engine for Work Experience | `AC-037` | User Request |
| `FR-038` | functional | P0 | implemented | Cover Letter Best Practices Enforcement | `AC-038` | User Request |
| `FR-039` | functional | P0 | implemented | Dynamic Candidate Preference Integration | `AC-040` | User Request |
| `FR-040` | functional | P1 | implemented | Multi-LLM Selection & Provider Configuration Support | `AC-041` | User Request |
| `FR-041` | functional | P1 | implemented | Full-Panel Claude-Style Settings View | `AC-042` | User Request |
| `FR-042` | functional | P1 | implemented | Hybrid Active Scouting Filters Control Panel | `AC-043` | User Request |
| `FR-043` | functional | P1 | implemented | Separated Portfolio and GitHub Fields Isolation | `AC-044` | User Request |
| `FR-044` | functional | P1 | implemented | Experience Level Multi-Select Filter Dropdown | `AC-045` | User Request |
| `FR-045` | functional | P1 | implemented | Dashboard Opportunity Visibility & Refactored Notifications | `AC-046` | User Request |
| `FR-046` | functional | P0 | implemented | Unified Job Search Settings Panel — single `profiles/job_search` key replaces `scouter_preferences` + `preferences` | `AC-050`, `AC-051` | `CR-003` |
| `FR-047` | functional | P0 | implemented | Preference Materialization — server writes `candidate_preferences.json` on every job_search save | `AC-047` | `CR-003` |
| `FR-048` | functional | P0 | implemented | Dynamic Scout URL Construction — all source URLs built at runtime from `candidate_preferences.json` | `AC-048` | `CR-003` |
| `FR-049` | functional | P1 | implemented | Generic ACC-ID Codification — any number of employer sections supported with dynamic range assignment | `AC-049` | `CR-003` |
| `FR-050` | functional | P1 | implemented | Context-Aware Experience Onboarding Flow — empty-state onboarding with VOC/MET/ACC explanation; active-state codification status bar with live code counts | `AC-052` | User Request |
| `FR-051` | functional | P1 | implemented | Claim Update Protocol — collapsible three-panel edit guide enforcing retire-don't-delete convention for coded experience claims | `AC-053` | User Request |
| `FR-052` | functional | P0 | implemented | Funnel Expansion — Himalayas, The Muse, and Adzuna added as Phase 1 parallel API sources | `AC-054` | `CR-004` |
| `FR-053` | functional | P1 | implemented | Role-generic search term expansion — `materializeJobSearchPrefs()` generates role-specific variants from targetRole | `AC-055` | `CR-004` |
| `FR-054` | functional | P1 | implemented | Optional Adzuna connection — UI field in Settings > Connections; key stored in SQLite `profiles/api_connections`; injected at spawn time | `AC-056` | `CR-004` |
| `FR-055` | functional | P1 | implemented | Adzuna free-tier rate guard — max 10 calls per scout run, 3s delay between calls | `AC-057` | `CR-004` |
| `FR-056` | functional | P1 | implemented | Role-aware source routing — The Muse category derived from TARGET_ROLE; hardcoded `Product Owner` fallback removed | `AC-058` | `CR-004` |
| `FR-057` | functional | P0 | superseded | Perplexity API key UI entry point — superseded by FR-061/FR-062; key moved to `llm_settings` | `AC-059` | `CR-005` |
| `FR-058` | functional | P0 | implemented | Unified Python env injection — `buildPythonEnv()` injects all DB-stored keys into every Python spawn so `.env` is never required | `AC-060` | `CR-005` |
| `FR-059` | functional | P0 | implemented | Provider configuration guard — `call_llm()` calls `_is_configured()` before invoking any provider; returns `""` with actionable warning if no providers configured | `AC-061` | `CR-006` |
| `FR-060` | functional | P0 | implemented | Multi-provider fallback chain — `call_llm()` iterates providers: primary first, then `[gemini, claude, local, perplexity]`; non-rate-limit error falls through to next provider | `AC-062` | `CR-006` |
| `FR-061` | functional | P1 | implemented | Perplexity as LLM provider — `sonar-pro` added as `call_llm()` provider branch; key stored in `llm_settings.perplexityApiKey`; research engine tries Perplexity first if configured | `AC-063` | `CR-006` |
| `FR-062` | functional | P0 | implemented | Four-card LLM provider UI — Gemini, Claude, Local, Perplexity cards each show key field, Connected badge, and Primary selection button | `AC-064` | `CR-006` |
| `FR-063` | functional | P0 | implemented | `primaryProvider` field — `LlmSettings.provider` renamed to `primaryProvider` with backward-compat read in Python and TypeScript | `AC-065` | `CR-006` |


### Data Traceability (DATA-001 to DATA-001)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `DATA-001` | data | P0 | implemented | Fact ID Traceability System | `AC-039` | User Request |

## Acceptance criteria

| ID | Parent | Scenario | Given | When | Then | Status |
|---|---|---|---|---|---|---|
| `AC-001` | `FR-001` | Scout start | Valid cookie session | Scout command is triggered | Browser navigates to LinkedIn/BuiltIn | verified |
| `AC-006` | `FR-006` | Keyword hit | Job title contains "Senior" | Pre-filter runs | Job is rejected with score 0 without calling LLM | verified |
| `AC-007` | `FR-007` | Scoring | Valid JD and workExperience | Scoring engine runs | A JSON object with Score, Decision, and Reasoning is returned | verified |
| `AC-015` | `FR-015` | Generation | Claim verifier pass | Resume generator runs | Output only contains metrics found in `data/` folder | verified |
| `AC-019` | `FR-019` | Metric audit | Resume claims "15% increase" | Audit script runs | Claim is flagged if `workExperience.md` says "12%" | verified |
| `AC-024` | `FR-024` | Log streaming | Scout is running | Dashboard is open | New lines appear in the terminal UI within 3 seconds | verified |
| `AC-026` | `FR-026` | Visual Edit | User opens an asset | Clicks the "Edit" action | Text loads inside the Toast UI WYSIWYG editor | accepted |
| `AC-027` | `FR-027` | Compile | User edits document | Clicks "Compile & Save" | Backend saves Markdown and recompiles the PDF using Python | accepted |
| `AC-028` | `FR-028` | Dual Pane | User is editing | Editor workspace opens | Left pane renders PDF iframe and right pane renders editor | accepted |
| `AC-029` | `FR-029` | AI Assistance | User triggers instruction | AI key is saved and text is submitted | The LLM processes the prompt and applies changes to Markdown | accepted |
| `AC-035` | `FR-035` | Background Sync | Jobs added as New | Background pipeline triggers | Descriptions are scraped, fit is evaluated, assets are drafted, and SQLite status is updated to Backlog | verified |
| `AC-036` | `FR-036` | Conformity Check | Resume draft edited/saved | Compliance guard runs | Standardizes HTML wrapper, converts markdown headers, and strips backslashes | verified |
| `AC-037` | `FR-037` | Auto-Codification | User saves work experience | POST /api/experience is called | Sequential VOC/MET/ACC IDs are automatically prepended to lines | verified |
| `AC-038` | `FR-038` | CL Enforcement | Cover letter generated/saved | Compliance guard runs | Applies Cover Letter Best Practices layout margins and line heights | verified |
| `AC-039` | `DATA-001` | Fact Traceability | LLM generates resume | Hard fact validation runs | Every claim must map back to a codified source metric or vocabulary term without printing the raw ID | verified |
| `AC-040` | `FR-039` | Dynamic Routing | User changes candidate preferences | Evaluation run | System dynamically adjusts title blocklists and scoring anchors | accepted |
| `AC-041` | `FR-040` | LLM Custom Routing | Settings configured to a custom provider (e.g., Claude or Ollama) | Pipeline triggers an LLM call | The LLM call is routed to the configured provider endpoint with its API key | verified |
| `AC-042` | `FR-041` | Full-Panel Claude-Style Settings View | Settings triggered | Clicks Settings in sidebar menu | Opens full-panel workspace with responsive tabs, auto-saving status tracking, and light sage theme elements | verified |
| `AC-043` | `FR-042` | Hybrid Scouting Control | User modifies target title or job type | Scouting Dashboard is open | Filter selections auto-save immediately to SQLite and update active crawlers | verified |
| `AC-044` | `FR-043` | Separate Portfolio/GitHub | User updates portfolio or GitHub field | Settings Profile tab is open | Auto-saves separate portfolio and github fields to local SQLite identity record | verified |
| `AC-045` | `FR-044` | Experience Dropdown Selection | User selects experience levels or clicks Clear | Scouting Dashboard is open | Filter selections auto-save immediately to SQLite and update Active Scouting search criteria | verified |
| `AC-046` | `FR-045` | Dashboard Opportunity Visibility | New opportunities ready in backlog | TodayView is open | Backlog jobs show up instantly on dashboard as "Ready to Apply" once PDF assets generate, and notifications utilize friendly "Ready to Apply" wording | verified |
| `AC-047` | `FR-047` | Preference Materialization | User sets targetRole to "Technical Program Manager" and saves | Server receives POST /api/profile/job_search | `data/candidate_preferences.json` is rewritten with matching `target_role` within 1 second | accepted |
| `AC-048` | `FR-048` | Dynamic Scout URLs | `experience_levels` contains "Mid Level (2-5 Years)" | Scout runs | LinkedIn URL includes `f_E=4`; BuiltIn URL includes `experience%5B%5D=mid-level` | accepted |
| `AC-049` | `FR-049` | Generic Codification | `workExperience.md` contains `### 5.1` through `### 5.4` | User saves experience | Each section receives IDs in its own 100-number range with no collisions | accepted |
| `AC-050` | `FR-046` | Settings Load | No `job_search` profile record exists in SQLite | Job Search tab loads | Default values matching `candidate_preferences.json` are displayed | accepted |
| `AC-051` | `FR-046` | Blocklist Enforcement | Title Blocklist set to "Senior, VP" and saved | Next scout run triggers | `blocked_titles` in JSON is `["Senior", "VP"]`; those titles appear as `[REJECT]` in pipeline log | accepted |
| `AC-052` | `FR-050` | Onboarding Trigger | `data/workExperience.md` is empty or under 100 chars | User opens Experience tab | Empty-state card is shown with VOC/MET/ACC three-card layout and paste CTA; once content exceeds 100 chars the codification status bar appears instead | accepted |
| `AC-053` | `FR-051` | Retire a Claim | User removes `[ACC-NNN]` tag from a bold header and saves | Server calls `codifyExperienceAndAssignIDs()` | The plain-text line is preserved in `workExperience.md` but no ACC code is generated for it, so future AI drafts cannot cite it | accepted |
| `AC-054` | `FR-052` | New sources active | Scout run triggers | Phase 1 completes | Activity log shows Himalayas, The Muse, and Adzuna in source health summary | accepted |
| `AC-055` | `FR-053` | PM search expansion | User sets targetRole to "Product Manager" and saves | Scout runs | `search_terms` in JSON contains at least "Product Manager", "Product Owner", "Technical Product Manager" | accepted |
| `AC-056` | `FR-054` | Adzuna key stored | User enters Adzuna App ID and Key in Settings | Saves | Keys stored in SQLite `profiles/api_connections`; next scout run uses them without `.env` | accepted |
| `AC-057` | `FR-055` | Adzuna rate guard | SEARCH_TERMS has 12 entries | scoutAdzuna runs | API calls stop at 10; log shows "Adzuna rate cap reached" | accepted |
| `AC-058` | `FR-056` | Role-aware Muse | User sets targetRole to "Software Engineer" | Scout runs | The Muse fetches `category=Engineering+%26+Tech` not `category=Product` | accepted |
| `AC-059` | `FR-057` | Perplexity UI (superseded) | — | — | Superseded by AC-063; key now in `llm_settings` | superseded |
| `AC-060` | `FR-058` | No .env required | User clears `.env` and sets all keys in UI | Runs full pipeline | Evaluation, drafting, and research all succeed using only SQLite-stored keys | accepted |
| `AC-061` | `FR-059` | Provider guard | No LLM keys configured | Pipeline calls `call_llm()` | Returns `""` and logs actionable warning; no API call attempted | accepted |
| `AC-062` | `FR-060` | Fallback chain | Gemini is primary but key is invalid | `call_llm()` invoked | Gemini fails → falls through to next configured provider; result returned from working provider | accepted |
| `AC-063` | `FR-061` | Perplexity provider | User sets Perplexity key in Settings > LLM Providers | Research engine runs | Key read from `llm_settings.perplexityApiKey`; Perplexity tried first for research; falls back to primary LLM on failure | accepted |
| `AC-064` | `FR-062` | Four-card UI | User opens Settings > API or Connections | Page renders | Four provider cards visible (Gemini, Claude, Local, Perplexity) each with key field, Connected badge, and Primary button | accepted |
| `AC-065` | `FR-063` | primaryProvider migration | Existing DB record has `"provider": "gemini"` | Python reads settings | `_get_configured_providers()` returns `["gemini"]` via backward-compat read | accepted |

## Non-Functional Requirements

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `NFR-001` | performance | P0 | implemented | Batch pipeline must wait 15s between jobs to avoid rate limits |
| `NFR-002` | cost | P1 | implemented | JD characters capped at 1500 for scoring to save tokens |
| `NFR-003` | security | P0 | implemented | Local-only execution; no career data leaves localhost |
| `NFR-004` | performance | P1 | implemented | Adzuna API calls capped at 10 per scout run with 3s inter-call delay to respect 25 req/min free-tier limit |
| `NFR-005` | cost | P0 | implemented | No LLM provider is called unless `_is_configured()` returns True — zero silent token waste from misconfigured providers |

## Security Requirements

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `SEC-001` | security | P0 | implemented | `.env` excluded from git via `.gitignore` |
| `SEC-002` | security | P0 | implemented | Third-party data source API keys (Adzuna) stored only in SQLite `profiles/api_connections` table (gitignored); never written to tracked files |
| `SEC-003` | security | P0 | implemented | `.env` is an optional fallback only — all API keys have a UI entry point and DB-first read path; application must function without `.env` |
| `SEC-004` | security | P0 | implemented | All LLM provider keys (Gemini, Claude, Perplexity) stored in `profiles/llm_settings`; injected at spawn time via env vars and never logged or written to disk |
| `NFR-004` | maintainability | P0 | implemented | All pipeline behavior variables (search terms, blocklists, score threshold, freshness window) must trace to `candidate_preferences.json`; no hardcoded overrides permitted in scout or pipeline scripts |
