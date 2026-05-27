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
| `FR-058` | functional | P0 | superseded | Unified Python env injection — superseded by `FR-095`; keys no longer passed via env | `AC-060` | `CR-005` |
| `FR-095` | functional | P0 | implemented | SQLite-only secrets — all scripts read `profiles` from `jobagent.sqlite`; no `.env`, dotenv, or `os.getenv` key fallbacks; `buildPythonEnv()` sets `PYTHONUNBUFFERED` only | `AC-095` | `CR-015` |
| `FR-059` | functional | P0 | implemented | Provider configuration guard — `call_llm()` calls `_is_configured()` before invoking any provider; returns `""` with actionable warning if no providers configured | `AC-061` | `CR-006` |
| `FR-060` | functional | P0 | implemented | Multi-provider fallback chain — `call_llm()` iterates providers: primary first, then `[gemini, claude, local, perplexity]`; non-rate-limit error falls through to next provider | `AC-062` | `CR-006` |
| `FR-061` | functional | P1 | implemented | Perplexity as LLM provider — `sonar-pro` added as `call_llm()` provider branch; key stored in `llm_settings.perplexityApiKey`; research engine tries Perplexity first if configured | `AC-063` | `CR-006` |
| `FR-062` | functional | P0 | implemented | Four-card LLM provider UI — Gemini, Claude, Local, Perplexity cards each show key field, Connected badge, and Primary selection button | `AC-064` | `CR-006` |
| `FR-063` | functional | P0 | implemented | `primaryProvider` field — `LlmSettings.provider` renamed to `primaryProvider` with backward-compat read in Python and TypeScript | `AC-065` | `CR-006` |
| `FR-064` | functional | P0 | implemented | Auto-generate `workExperience_summary.md` — spawned as background process after every `POST /api/experience` save; `batch_pipeline.py` falls back to full `workExperience.md` if summary not yet generated | `AC-066` | internal |
| `FR-065` | functional | P1 | implemented | Intra-Local Model Failover — system detects 500/load failure from primary local model and immediately invokes configured `localFallbackModel` without interrupting the caller | `AC-067` | User Request |
| `FR-066` | functional | P1 | implemented | Automatic VRAM Reclamation (Eco-Hook) — `batch_pipeline.py` utilizes explicit unload signals upon script exit to purge models from GPU and release resources immediately | `AC-068` | User Request |
| `FR-067` | functional | P0 | implemented | Hybrid Intelligence Switching — `call_llm()` supports explicit `provider_override` flag allowing Drafting and Auditing stages to lock to Cloud while Evaluation stage runs locally | `AC-069` | User Request |
| `FR-068` | functional | P0 | accepted | Stateful Pipeline Orchestration — decodes callback hell into a checkpointed state machine supporting resumes | `AC-070` | User Request |
| `FR-069` | functional | P0 | accepted | Fact-Bound Numerical Verification & Refinement — auditing prevents metric inflation via automated 2-strike refinement loops | `AC-071` | User Request |
| `FR-070` | functional | P0 | accepted | Early Scouting Geographic Gating — filters crawler opportunities at scraping phase based on candidate location bounds | `AC-072` | User Request |
| `FR-071` | functional | P0 | implemented | Local Model Deterministic Sampling Override — `_call_local()` forces `temperature=0.0`, `top_k=40`, `top_p=0.9`, `num_predict≤1000` regardless of caller input; few-shot WRONG/CORRECT bullet examples added to `LOCAL_CONSTRAINT_PREFIX` | `AC-073` | `CR-007` |
| `FR-072` | functional | P0 | implemented | Two-Phase Local Resume Generation — when local provider is active, `_generate_resume_local_twophase()` splits generation into JSON ACC-ID selection (Phase 1) and per-bullet generation (Phase 2) instead of a single monolithic prompt | `AC-074` | `CR-007` |
| `FR-073` | functional | P0 | implemented | Deterministic Numeric Fact Preservation — `preserves_core_facts()` extracts all numeric tokens from source and bullet, flags any number in the bullet with no equivalent in source as invented; zero LLM cost | `AC-075` | `CR-007` |
| `FR-074` | functional | P0 | implemented | Style Guard Forbidden Section & Header Normalization — `strip_forbidden_sections()` removes 12+ prohibited section types; name header normalized from any `##`/bold variant to canonical `# JASON TAYLOR`; duplicate contact lines, placeholder tokens, and education sections in cover letters are automatically stripped | `AC-076` | `CR-007` |
| `FR-075` | functional | P0 | implemented | `validate_hard_facts()` Document-Type Awareness — education presence check suppressed for cover letters; Cision job title auto-corrected from "Product Owner" to "Product Manager"; unfilled template tokens (`[JD]`, `[Position Overview]`, etc.) stripped before output | `AC-077` | `CR-007` |
| `FR-076` | functional | P1 | accepted | Interactive Accordion-Style Connections UI — consolidates LLM providers and Data Sources under single scrollable view with micro-animations | `AC-078` | `CR-008` |
| `FR-077` | functional | P1 | accepted | Integrated Search & Filter Interface — live search field allowing instant filtering across LLM names/descriptions | `AC-079` | `CR-008` |
| `FR-078` | functional | P0 | accepted | Resilient Dual-Layout Built In Parsing — extracts metadata using combined selectors representing both `.job-item` and `div[data-id="job-card"]` patterns | `AC-080` | `CR-009` |
| `FR-079` | functional | P0 | accepted | Multi-Term Built In Search Gating — generates specific `/jobs?search={term}` target endpoints for each candidate search variant | `AC-081` | `CR-009` |
| `FR-080` | functional | P0 | accepted | Decommissioned LinkedIn Channel — removes all automated scraping, navigation, and auth operations targeting `linkedin.com` to eliminate session risk | `AC-082` | `CR-010` |
| `FR-081` | functional | P0 | implemented | Gemini-Primary Drafting — cloud monolithic resume/cover use `provider_override=['gemini']` only; no silent monolithic local fallback | `AC-083` | `CR-012` |
| `FR-082` | functional | P0 | implemented | Structured Local Fallback Pipeline — superseded by `draft_compiler.run()` (CR-014); bite-sized select → bullets → summary → assemble | `AC-084` | `CR-012` |
| `FR-083` | functional | P0 | implemented | Deterministic Resume QA Repair — `repair_resume_markdown()` injects missing R-005 sections before hard QA | `AC-085` | `CR-012` |
| `FR-084` | functional | P0 | implemented | Non-Fatal Drafting Errors — `DraftingPipelineError` replaces QA `ValueError`; batch marks `Needs Retry` and continues | `AC-086` | `CR-012` |
| `FR-085` | functional | P0 | implemented | Employer-Scoped Claim Routing — `ACC-1xx/2xx/3xx` prefix maps to Cision/Sterkly/ZTS buckets deterministically | `AC-087` | `CR-013` |
| `FR-086` | functional | P0 | implemented | Per-Employer Claim Selection — Tier 2 runs ≤3 small JSON selections (one per employer) with keyword fallback | `AC-088` | `CR-013` |
| `FR-087` | functional | P0 | implemented | Expanded Bullet Gates — local bullets reject blocked tools, seniority inflation, and >25 words before fallback | `AC-089` | `CR-013` |
| `FR-088` | functional | P0 | implemented | Deterministic Summary & Cover Assembly — summary and cover letter built without monolithic LLM; corpus numeric audit on final text | `AC-090` | `CR-013` |
| `FR-089` | functional | P0 | implemented | Unified Draft Compiler — single `draft_compiler.run()` stage graph; no cloud/local fork in `run_drafting_engine` | `AC-091` | `CR-014` |
| `FR-090` | functional | P0 | implemented | Draft Manifest — `draft_manifest.json` records claim IDs, jd_profile, pipeline_version, fallback counts | `AC-092` | `CR-014` |
| `FR-091` | functional | P0 | implemented | Validated JdProfile — themes/requirements must substring-match JD; fit summary boosts scoring | `AC-093` | `CR-014` |
| `FR-092` | functional | P0 | implemented | Compiler-stage gates — `verify_content` with internal claim IDs before strip; `DraftingPipelineError` on QA fail | `AC-094` | `CR-014` |
| `FR-093` | functional | P0 | implemented | `call_llm_stage(stage_id)` — per-stage provider preference list; same prompts for gemini and local | `AC-095` | `CR-014` |
| `FR-094` | functional | P0 | implemented | Fit-aware tailoring — `evaluation_result` feeds JdProfile and claim ranking | `AC-096` | `CR-014` |
| `FR-100` | functional | P0 | implemented | Claim catalog — parse `workExperience.md` ACC/VOC into `claim_catalog.py` | `AC-100` | `CR-017` |
| `FR-101` | functional | P0 | implemented | Compose-mode bullets — `claim_composer.py` default; `DRAFT_MODE=legacy_llm` escape hatch | `AC-101` | `CR-017` |
| `FR-102` | functional | P0 | implemented | Fail-closed verification chain — `verification_chain.py` blocks on verify/QA failures | `AC-102` | `CR-017` |
| `FR-103` | functional | P0 | implemented | Display company name — DB `jobs.company` passed to cover letter templates | `AC-103` | `CR-017` |
| `FR-104` | functional | P0 | implemented | Recruiter QA gate — `recruiter_qa.py` before Backlog PDF promotion | `AC-104` | `CR-017` |
| `FR-105` | functional | P1 | implemented | Sentence-aware bullet fitting — `bullet_fit.fit_bullet_to_budget()` | `AC-106` | `CR-018` |
| `FR-106` | functional | P1 | implemented | One bridge bullet per job; `strip_bridge_prefix` on cover proofs | `AC-107`, `AC-108` | `CR-018` |
| `FR-107` | functional | P1 | implemented | Fresh backlog summary on successful draft — `_draft_success_summary()` | `AC-109` | `CR-018` |
| `FR-108` | functional | P1 | implemented | Template-first cheat sheet — `CHEAT_SHEET_MODE` default template | `AC-110` | `CR-018` |


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
| `AC-095` | `FR-095` | SQLite-only secrets | No `.env` file on disk; keys in Settings | Scout + `batch_pipeline.py` + research | All providers read keys from `jobagent.sqlite` only | implemented |
| `AC-061` | `FR-059` | Provider guard | No LLM keys configured | Pipeline calls `call_llm()` | Returns `""` and logs actionable warning; no API call attempted | accepted |
| `AC-062` | `FR-060` | Fallback chain | Gemini is primary but key is invalid | `call_llm()` invoked | Gemini fails → falls through to next configured provider; result returned from working provider | accepted |
| `AC-063` | `FR-061` | Perplexity provider | User sets Perplexity key in Settings > LLM Providers | Research engine runs | Key read from `llm_settings.perplexityApiKey`; Perplexity tried first for research; falls back to primary LLM on failure | accepted |
| `AC-064` | `FR-062` | Four-card UI | User opens Settings > API or Connections | Page renders | Four provider cards visible (Gemini, Claude, Local, Perplexity) each with key field, Connected badge, and Primary button | accepted |
| `AC-065` | `FR-063` | primaryProvider migration | Existing DB record has `"provider": "gemini"` | Python reads settings | `_get_configured_providers()` returns `["gemini"]` via backward-compat read | accepted |
| `AC-066` | `FR-064` | Summary auto-generation | User saves experience via Settings > Experience | Server codifies file and returns immediately | `workExperience_summary.md` is regenerated in background; `batch_pipeline.py` uses full file as fallback if summary not yet ready | accepted |
| `AC-067` | `FR-065` | Local Failover | Primary local model errors with 500/Empty | `_call_local()` invoked | The function catches standard error/empty response and immediately attempts configured secondary local model | verified |
| `AC-068` | `FR-066` | VRAM Reclaim | `batch_pipeline.py` completes all jobs | Process finishes or interrupts | `unload_local_models()` sends synchronous `keep_alive: 0` to local API purging loaded weights | verified |
| `AC-069` | `FR-067` | Hybrid Overrides | High-fidelity function like drafting calls `call_llm` | `provider_override='gemini'` passed | System completely bypasses the configured local primary provider and forces cloud execution for that call | verified |
| `AC-070` | `FR-068` | Orchestration Checkpoints | A stage crashes or server restarts | Re-triggers pipeline run | System queries `pipeline_runs` to resume exactly from the last non-completed execution stage | accepted |
| `AC-071` | `FR-069` | Fact-Bound Audit Fail | Draft inflates number to '20%' vs ground truth '10%' | Verifier runs | Catches mismatch and sends corrective prompt loop back to drafting engine up to 2 times | accepted |
| `AC-072` | `FR-070` | Early Ingestion Filtering | Scraped job location is 'Texas' (Out-of-bounds) | Aggregation routine runs | Scraped listing is rejected at the boundary and never persisted to the database | accepted |
| `AC-073` | `FR-071` | Sampling Override | Local model is primary provider | `_call_local()` is invoked | Ollama payload contains `temperature: 0.0`, `top_k: 40`, `num_predict: 1000`; log line confirms override | verified |
| `AC-074` | `FR-072` | Two-Phase Generation | Local model is primary and resume draft is requested | `run_drafting_engine()` is called | Log shows Phase 1 JSON selection followed by per-bullet Phase 2 calls; `llm_verify_claims()` is skipped; `preserves_core_facts()` runs on each bullet | verified |
| `AC-075` | `FR-073` | Numeric Preservation | Source text contains "3,500 accounts"; bullet contains "5,000 accounts" | `preserves_core_facts()` runs | Returns `(False, ["5,000"])` — invented number flagged; bullet discarded and replaced by `_fallback_bullet()` | verified |
| `AC-076` | `FR-074` | Forbidden Section Strip | Resume contains `## Core Competencies` section with bullets | `style_compliance_guard.py` runs | Section and all its content removed; `## PROFESSIONAL EXPERIENCE` boundary preserved; name header normalized to `# JASON TAYLOR` | verified |
| `AC-077` | `FR-075` | CL Education Skip | Cover letter is passed to `validate_hard_facts()` | `doc_type='cover_letter'` | Education check does not run; no "MISSING FACT: Education" warning produced; placeholder tokens stripped | verified |
| `AC-078` | `FR-076` | Accordion Expansion | User clicks on a connection card header | Accordion tab is clicked | Toggles current card to expanded mode and automatically closes previously expanded element | accepted |
| `AC-079` | `FR-077` | Connection Filter | User types search criteria | Text entered into 'Search connections' | Instantly hides non-matching LLM provider or data source elements from active view | accepted |
| `AC-080` | `FR-078` | Dual Selector Match | Page loads in search mode or taxonomy mode | `scoutBuiltIn` runs | Standardizes selector to `.job-item, div[data-id="job-card"]` ensuring all listing cards are captured | accepted |
| `AC-081` | `FR-079` | Search Loop Execution | Multiple search terms configured in json preferences | Built In scout phase triggered | Crawler cycles through distinct URLs for each term, scraping up to 30 positions per term | accepted |
| `AC-082` | `FR-080` | Browser Request Bypassing | Main orchestration loop triggered | `scout_local` script executed | Browser initializes and executes BuiltIn + Levels.fyi pipelines while logging that LinkedIn is skipped, dispatching zero network packets to linkedin.com | accepted |
| `AC-083` | `FR-081` | Gemini-only cloud draft | Gemini configured and quota available | `run_drafting_engine()` drafts resume | `call_llm` uses `provider_override=['gemini']` for monolithic resume/cover; no monolithic local in cloud path | implemented |
| `AC-084` | `FR-082` | Structured local fallback | Gemini returns 429 or QA fails on a stage | `call_llm_stage` falls back to local | `draft_compiler.run()` completes bite-sized stages; log shows Compiler Stage 1–3 | implemented |
| `AC-085` | `FR-083` | QA repair | Local resume missing `## PROFESSIONAL SUMMARY` | `repair_resume_markdown()` runs before `check_resume` | Required sections and employer anchors injected deterministically | implemented |
| `AC-086` | `FR-084` | Batch continues on draft fail | Drafting raises `DraftingPipelineError` | `batch_pipeline` processes job | Job marked `Needs Retry`; batch exit code 0; no uncaught `ValueError` | implemented |
| `AC-087` | `FR-085` | Employer routing | Claim `ACC-203` selected | `employer_for_claim_id()` runs | Returns `sterkly`, not `cision` | implemented |
| `AC-088` | `FR-086` | Per-employer select | JD mentions onboarding | Tier 2 selection runs | At least one `ACC-3xx` ID included when ZTS pool non-empty | implemented |
| `AC-089` | `FR-087` | Bullet tool block | Local bullet mentions `Kubernetes` | `validate_bullet_for_local()` runs | Returns invalid; `_fallback_bullet` used | implemented |
| `AC-090` | `FR-088` | Deterministic CL | 4+ validated bullets exist | `assemble_cover_letter_deterministic()` runs | Cover letter has no LLM call; paragraphs use bullet corpus only | implemented |
| `AC-091` | `FR-089` | Unified compiler | Drafting runs with gemini or local configured | `draft_compiler.run()` completes | Same stage order; no `_run_gemini_monolithic_draft` invoked | implemented |
| `AC-092` | `FR-090` | Manifest | Draft completes | Read `draft_manifest.json` | Contains `selected_claim_ids`, `jd_profile`, `pipeline_version` | implemented |
| `AC-093` | `FR-091` | JdProfile validation | LLM returns invented requirement | `build_jd_profile()` validates | Invented strings dropped; deterministic fallback fills gaps | implemented |
| `AC-094` | `FR-092` | verify_content | Resume assembled with `[ACC-*]` on bullets | `verify_content()` runs pre-strip | Invalid IDs fail closed or trigger fallback bullets | implemented |
| `AC-095` | `FR-093` | Stage providers | Stage `bullet` runs | `call_llm_stage('bullet')` | Uses `['gemini','local']` preference, not hardcoded local-only | implemented |
| `AC-096` | `FR-094` | Fit boost | Job passed fit with Summary | Stage 2 selection runs | Claims matching fit summary themes rank higher | implemented |
| `AC-100` | `FR-100` | No ID tokens in PDFs | Compose draft completes | Read `Resume.md` and `CoverLetter.md` | No `ACC-`, `MET-`, `VOC-`, or pipe-wrapped ID tokens in final text | implemented |
| `AC-101` | `FR-101` | Manifest compose mode | Draft completes | Read `draft_manifest.json` | Contains `draft_mode`, `selected_claim_ids`, `pipeline_version` CR-017-* | implemented |
| `AC-102` | `FR-102` | verify_content blocks | Invalid metric on tagged resume body | `draft_compiler.run()` | Raises `DraftingPipelineError`; job not promoted to Backlog | implemented |
| `AC-103` | `FR-103` | Display company | Job row has `company` in SQLite | Cover letter generated | Salutation uses DB `company`, not `submissions/` folder slug | implemented |
| `AC-104` | `FR-104` | Summary length | Compose draft completes | Read `## PROFESSIONAL SUMMARY` | ≤380 characters; not concatenation of full bullets | implemented |
| `AC-105` | `FR-102`, `FR-104` | Verification passed flag | Full chain succeeds | Read `draft_manifest.json` | `verification_passed: true` before Backlog-eligible PDFs | implemented |
| `AC-106` | `FR-105` | Complete bullets | Compose draft completes | recruiter_qa on resume | No incomplete-clause bullet endings | implemented |
| `AC-107` | `FR-106` | One bridge | Resume with JD roadmap theme | Count bridge-prefixed bullets | At most one bullet starts with bridge phrase | implemented |
| `AC-108` | `FR-106` | Cover strip | Cover generated | Read CoverLetter.md | No bridge_phrases.json values in proof paragraphs | implemented |
| `AC-109` | `FR-107` | Fresh summary | Draft succeeds | Query jobs.summary | No `Asset drafting failed` or `numeric audit` in summary | implemented |
| `AC-110` | `FR-108` | Cheat sheet | Research packet exists | Read Interview_Cheat_Sheet.md | Non-empty template cheat sheet | implemented |
| `AC-111` | `SEC-005` | Doppler Hybrid Config | User boots with `npm run dev:doppler` | App loads | UI detects injected variables and hides input fields displaying "Managed via Doppler" lock badge | verified |
| `AC-112` | `NFR-006` | Overlay Network Access | App running on Desktop | Laptop on Tailscale accesses IP | Server accepts connection and renders JobAgent UI | verified |

## Non-Functional Requirements

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `NFR-001` | performance | P0 | implemented | Batch pipeline must wait 15s between jobs to avoid rate limits |
| `NFR-002` | cost | P1 | implemented | JD characters capped at 1500 for scoring to save tokens |
| `NFR-003` | security | P0 | implemented | Local-only execution; no career data leaves localhost |
| `NFR-004` | performance | P1 | implemented | Adzuna API calls capped at 10 per scout run with 3s inter-call delay to respect 25 req/min free-tier limit |
| `NFR-005` | cost | P0 | implemented | No LLM provider is called unless `_is_configured()` returns True — zero silent token waste from misconfigured providers |
| `NFR-006` | infrastructure | P1 | implemented | Zero-Trust Remote Binding — Vite client and Express server bind to `0.0.0.0` to permit authorized access across overlay networks (Tailscale) |

## Security Requirements

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `SEC-001` | security | P0 | implemented | `.env` excluded from git via `.gitignore` |
| `SEC-002` | security | P0 | implemented | Third-party data source API keys (Adzuna) stored only in SQLite `profiles/api_connections` table (gitignored); never written to tracked files |
| `SEC-003` | security | P0 | implemented | No `.env` for secrets — all API keys configured via Settings UI and read from SQLite at runtime (`CR-015`) |
| `SEC-004` | security | P0 | implemented | LLM and data-source keys stored in `profiles` (`llm_settings`, `api_connections`); read in-process from `jobagent.sqlite`; never logged or written to tracked files |
| `SEC-005` | security | P0 | implemented | Secret Portable Management — Supports injecting API keys directly from environment variables (Doppler) decoupling sensitive strings from local database |
| `NFR-004` | maintainability | P0 | implemented | All pipeline behavior variables (search terms, blocklists, score threshold, freshness window) must trace to `candidate_preferences.json`; no hardcoded overrides permitted in scout or pipeline scripts |
