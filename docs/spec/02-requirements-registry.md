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
| `FR-001` | functional | P0 | implemented | Multi-source job discovery via Playwright + API/RSS (12 active sources) | `AC-001`, `AC-002` | `BMAD-SRC-001` |
| `FR-002` | functional | P0 | implemented | OpenPostings SQLite database scraper | `AC-003` | `BMAD-SRC-001` |
| `FR-003` | functional | P1 | implemented | Job deduplication via URL and Title/Company hash | `AC-004` | `BMAD-SRC-001` |
| `FR-184` | functional | P1 | implemented | Jobicy official free JSON API source (`geo=usa`, per-term tag search, `passesTitleBlocklist`) | — | User Request |
| `FR-185` | functional | P1 | implemented | Working Nomads public JSON API source (client-side PM category + `passesBroadPmTitleScope` filter) | — | User Request |
| `FR-186` | functional | P1 | implemented | JobsCollider/RemoteFirstJobs hourly RSS source (PM category feed, `passesBroadPmTitleScope`, "Title at Company" parse) | — | User Request |
| `FR-187` | functional | P1 | implemented | `passesBroadPmTitleScope()` — blocks product marketing, design, analytics from broad-category feeds; used by Working Nomads + JobsCollider | — | User Request |
| `FR-240` | functional | P1 | implemented | Broad PM title scope gate applied to WWR + Himalayas; WWR management-finance feed removed; adjacent-role deny patterns | `AC-209`–`AC-214` | CR-045 |

### Evaluation & Gating (FR-006 to FR-010)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-006` | functional | P0 | implemented | Deterministic Keyword Pre-Filter (Zero Token Gate) | `AC-006` | `BMAD-SRC-005` |
| `FR-007` | functional | P0 | implemented | LLM-based 100-point Job Fit Scoring | `AC-007` | `BMAD-SRC-005` |
| `FR-008` | functional | P0 | implemented | "Two-Anchor Room" validation for YES decisions | `AC-008` | `BMAD-SRC-005` |
| `FR-188` | functional | P1 | implemented | Anchor floor + scoring-only fit path after deterministic gates (CR-035). **Score promotion retired** — anchor hits are risk flags only (`FR-242` / CR-053). | `AC-191`, `AC-192`, `AC-193` | CR-035 |
| `FR-189` | functional | P1 | implemented | Solo PM trap zero-token gate + years policy lock for fit LLM (CR-036) | `AC-119`, `AC-119b`, `AC-194`, `AC-195`, `AC-196` | CR-036 |
| `FR-190` | functional | P1 | implemented | Required vertical domain zero-token gate + fit cap when JD mandates industry years candidate lacks (CR-037) | `AC-197`, `AC-198`, `AC-199` | CR-037 |
| `FR-191` | functional | P2 | implemented | B2C role openness via preferences, keywords, anchors, and fit prompt (CR-038) | `AC-200`, `AC-201`, `AC-202` | CR-038 |
| `FR-192` | functional | P1 | implemented | Transferable skills scoring over industry/customer-base gating (CR-039 supersedes CR-037 gate) | `AC-203`, `AC-204`, `AC-205` | CR-039 |
| `FR-193` | functional | P1 | implemented | Theme primary claims — force theme-matched ACC IDs on resume; align cover numeric audit corpus with resume bullets + catalog (CR-040) | `AC-206`, `AC-207` | CR-040 |
| `FR-194` | functional | P1 | implemented | ATS watchlist must not load `ats_watchlist.example.json` at runtime (CR-041) | `AC-208` | CR-041 |
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
| `FR-096` | functional | P0 | implemented | No layoff or workforce-reduction tone on resumes/cover letters — `tone_guard.py` rewrites to constraints framing; bullets rejected at compose; R-011 / CL-010 QA fail if present | `AC-097` | `CR-023` |

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
| `FR-036` | functional | P0 | implemented | Triple Redundancy Style Compliance Guard | `AC-036` | CR-020 |
| `FR-037` | functional | P0 | implemented | SDD Auto-Codification Engine for Work Experience | `AC-037` | CR-020 |
| `FR-038` | functional | P0 | implemented | Cover Letter Best Practices Enforcement | `AC-038` | CR-020 |
| `FR-039` | functional | P0 | implemented | Dynamic Candidate Preference Integration | `AC-040` | CR-020 |
| `FR-040` | functional | P1 | implemented | Multi-LLM Selection & Provider Configuration Support | `AC-041` | CR-020 |
| `FR-041` | functional | P1 | implemented | Full-Panel Claude-Style Settings View | `AC-042` | CR-020 |
| `FR-042` | functional | P1 | implemented | Hybrid Active Scouting Filters Control Panel | `AC-043` | CR-020 |
| `FR-043` | functional | P1 | implemented | Separated Portfolio and GitHub Fields Isolation | `AC-044` | CR-020 |
| `FR-044` | functional | P1 | implemented | Experience Level Multi-Select Filter Dropdown | `AC-045` | CR-020 |
| `FR-045` | functional | P1 | implemented | Dashboard Opportunity Visibility & Refactored Notifications | `AC-046` | CR-020 |
| `FR-046` | functional | P0 | implemented | Unified Job Search Settings Panel — single `profiles/job_search` key replaces `scouter_preferences` + `preferences` | `AC-050`, `AC-051` | `CR-003` |
| `FR-047` | functional | P0 | implemented | Preference Materialization — server writes `candidate_preferences.json` on every job_search save | `AC-047` | `CR-003` |
| `FR-048` | functional | P0 | implemented | Dynamic Scout URL Construction — all source URLs built at runtime from `candidate_preferences.json` | `AC-048` | `CR-003` |
| `FR-049` | functional | P1 | implemented | Generic ACC-ID Codification — any number of employer sections supported with dynamic range assignment | `AC-049` | `CR-003` |
| `FR-050` | functional | P1 | implemented | Context-Aware Experience Onboarding Flow — empty-state onboarding with VOC/MET/ACC explanation; active-state codification status bar with live code counts | `AC-052` | CR-020 |
| `FR-051` | functional | P1 | implemented | Claim Update Protocol — collapsible three-panel edit guide enforcing retire-don't-delete convention for coded experience claims | `AC-053` | CR-020 |
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
| `FR-065` | functional | P1 | implemented | Intra-Local Model Failover — system detects 500/load failure from primary local model and immediately invokes configured `localFallbackModel` without interrupting the caller | `AC-067` | CR-020 |
| `FR-066` | functional | P1 | implemented | Automatic VRAM Reclamation (Eco-Hook) — `batch_pipeline.py` utilizes explicit unload signals upon script exit to purge models from GPU and release resources immediately | `AC-068` | CR-020 |
| `FR-067` | functional | P0 | implemented | Hybrid Intelligence Switching — `call_llm()` supports explicit `provider_override` flag allowing Drafting and Auditing stages to lock to Cloud while Evaluation stage runs locally | `AC-069` | CR-020 |
| `FR-068` | functional | P0 | accepted | Stateful Pipeline Orchestration — decodes callback hell into a checkpointed state machine supporting resumes | `AC-070` | CR-020 |
| `FR-069` | functional | P0 | accepted | Fact-Bound Numerical Verification & Refinement — auditing prevents metric inflation via automated 2-strike refinement loops | `AC-071` | CR-020 |
| `FR-070` | functional | P0 | accepted | Early Scouting Geographic Gating — filters crawler opportunities at scraping phase based on candidate location bounds | `AC-072` | CR-020 |
| `FR-071` | functional | P0 | implemented | Local Model Deterministic Sampling Override — `_call_local()` forces `temperature=0.0`, `top_k=40`, `top_p=0.9`, `num_predict≤1000` regardless of caller input; few-shot WRONG/CORRECT bullet examples added to `LOCAL_CONSTRAINT_PREFIX` | `AC-073` | `CR-007` |
| `FR-072` | functional | P0 | implemented | Two-Phase Local Resume Generation — when local provider is active, `_generate_resume_local_twophase()` splits generation into JSON ACC-ID selection (Phase 1) and per-bullet generation (Phase 2) instead of a single monolithic prompt | `AC-074` | `CR-007` |
| `FR-073` | functional | P0 | implemented | Deterministic Numeric Fact Preservation — `preserves_core_facts()` extracts all numeric tokens from source and bullet, flags any number in the bullet with no equivalent in source as invented; zero LLM cost | `AC-075` | `CR-007` |
| `FR-074` | functional | P0 | implemented | Style Guard Forbidden Section & Header Normalization — `strip_forbidden_sections()` removes 12+ prohibited section types; name header normalized from any `##`/bold variant to canonical `# CANDIDATE NAME`; duplicate contact lines, placeholder tokens, and education sections in cover letters are automatically stripped | `AC-076` | `CR-007` |
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
| `FR-088` | functional | P0 | superseded (cover) | Deterministic Summary & Cover Assembly — summary deterministic; **cover bullet-paste superseded by `FR-157` when `COVER_ENGINE=v1`** | `AC-090` | `CR-013` |
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
| `FR-109` | functional | P1 | implemented | Years-first seniority gate — `seniority_gate.py` title + years pre-LLM | `AC-115`, `AC-116`, `AC-117` | `CR-019` |
| `FR-110` | functional | P1 | implemented | AI-tools vs AI-PM rubric - LLM fit must not reject tool mentions alone | `AC-118` | `CR-019` |
| `FR-111` | functional | P1 | implemented | JD Deduplication via Vector Similarity | `AC-119` | CR-020 |
| `FR-112` | functional | P1 | implemented | I/O vs GPU Concurrency Splitting | `AC-120` | CR-020 |
| `FR-113` | functional | P1 | implemented | Local Salary Extraction | `AC-121` | CR-020 |
| `FR-114` | functional | P1 | implemented | Vector-Based ATS Backlog Re-ranking | `AC-122` | CR-020 |
| `FR-115` | functional | P1 | implemented | Rapid Metadata Tagging using Cosine Similarity | `AC-123` | CR-020 |
| `FR-116` | functional | P1 | implemented | SQLite FTS5 Search Integration | `AC-124` | CR-020 |
| `FR-117` | functional | P1 | implemented | DOM Cleanup Pre-Processor for JDs | `AC-125` | CR-020 |
| `FR-118` | functional | P1 | implemented | Prompt Context Truncation Guard | `AC-126` | CR-020 |
| `FR-119` | functional | P1 | implemented | Fast-Fail Context Fallbacks | `AC-127` | CR-020 |
| `FR-120` | functional | P1 | implemented | Local Skill-Gap Analysis & UI integration | `AC-128` | CR-020 |
| `FR-121` | functional | P1 | implemented | Cover Letter Intro Customization via local model | `AC-129` | CR-020 |
| `FR-122` | functional | P1 | implemented | Local Offline Web Research (SearXNG + Playwright) | `AC-130` | CR-020 |
| `FR-123` | functional | P1 | implemented | Competitor Matrix via Pre-computed Local Vectors | `AC-131` | CR-020 |
| `FR-124` | functional | P1 | implemented | Zero-Shot On-Site Classifier | `AC-132` | CR-020 |
| `FR-125` | functional | P1 | implemented | Auto-Pruning Stale DB Blobs script/cron | `AC-133` | CR-020 |
| `FR-126` | functional | P1 | implemented | Local Model Text Streaming (SSE) | `AC-134` | CR-020 |
| `FR-127` | functional | P1 | implemented | WebGPU Browser-Side Inference for Grammar checks | `AC-135` | CR-020 |
| `FR-128` | functional | P1 | implemented | Responsive PDF Layout Feedback dynamically | `AC-136` | CR-020 |
| `FR-129` | functional | P1 | implemented | Notification Webhooks (Tailscale Native / NTFY) | `AC-137` | CR-020 |
| `FR-130` | functional | P1 | implemented | Local PII Redaction Guard via SpaCy/Regex | `AC-138` | CR-020 |


### Data Traceability (DATA-001 to DATA-001)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `DATA-001` | data | P0 | implemented | Fact ID Traceability System, including complete story-class claim indexing | `AC-039` | CR-020, CR-095 |

## Acceptance criteria

| ID | Parent | Scenario | Given | When | Then | Status |
|---|---|---|---|---|---|---|
| `AC-001` | `FR-001` | Scout start | Valid cookie session | Scout command is triggered | Browser navigates to LinkedIn/BuiltIn | verified |
| `AC-006` | `FR-006` | Keyword hit | Job title contains blocked Lead/Director term | Pre-filter runs | Job is rejected with score 0 without calling LLM | implemented |
| `AC-006b` | `FR-109` | Senior allowed | Job title Senior PM, years within range | Pre-filter runs | Job is not rejected by title gate alone | implemented |
| `AC-007` | `FR-007` | Scoring | Valid JD and workExperience | Scoring engine runs | A JSON object with Score, Decision, and Reasoning is returned | verified |
| `AC-015` | `FR-015` | Generation | Claim verifier pass | Resume generator runs | Output only contains metrics found in `data/` folder | verified |
| `AC-019` | `FR-019` | Metric audit | Resume claims "15% increase" | Audit script runs | Claim is flagged if `workExperience.md` says "12%" | verified |
| `AC-024` | `FR-024` | Log streaming | Scout is running | Dashboard is open | New lines appear in the terminal UI within 3 seconds | verified |
| `AC-026` | `FR-026` | Visual Edit | User opens an asset | Clicks the "Edit" action | Text loads inside the Toast UI WYSIWYG editor | accepted |
| `AC-027` | `FR-027` | Compile | User edits document | Clicks "Compile & Save" | Backend saves Markdown and recompiles the PDF using Python | accepted |
| `AC-028` | `FR-028` | Dual Pane | User is editing | Editor workspace opens | Left pane renders PDF iframe and right pane renders editor | accepted |
| `AC-029` | `FR-029` | AI Assistance | User triggers instruction | AI key is saved and text is submitted | The LLM processes the prompt and applies changes to Markdown | accepted |
| `AC-035` | `FR-035` | Background Sync | Jobs added as New | Background pipeline triggers | Descriptions are scraped, fit is evaluated, assets are drafted, and SQLite status is updated to Backlog | verified |
| `AC-175` | `FR-035` | Evaluate visibility | Full sync in Stage 4 | Job Search shows Step 2 active, batch progress N/M, and current job line | verified |
| `AC-176` | `FR-035` | Gate log level | JD fails zero-token gate | Activity log records `[ZERO-TOKEN REJECT]` as INFO, not ERROR | verified |
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
| `AC-076` | `FR-074` | Forbidden Section Strip | Resume contains `## Core Competencies` section with bullets | `style_compliance_guard.py` runs | Section and all its content removed; `## PROFESSIONAL EXPERIENCE` boundary preserved; name header normalized to `# CANDIDATE NAME` | verified |
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
| `AC-115` | `FR-109` | Senior title allowed | Title Senior PM, JD 3-6 years | Title gate | Passes zero-token gate | implemented |
| `AC-116` | `FR-109` | Lead blocked | Title Lead Product Manager | Title gate | Rejected title_blocked | implemented |
| `AC-117` | `FR-109` | Years cap | JD requires 10+ years, max=7 | Years gate | Rejected before LLM | implemented |
| `AC-119` | `FR-109`, `FR-189` | Years boundary pass | JD requires 7 years, max=7 | Years gate | Passes zero-token gate | implemented |
| `AC-119b` | `FR-109`, `FR-189` | Years boundary fail | JD requires 8 years, max=7 | Years gate | Rejected before LLM | implemented |
| `AC-194` | `FR-189` | Solo trap reject | JD "only product manager", no org signals | Solo PM gate | Rejected zero-token | implemented |
| `AC-195` | `FR-189` | Squad PM pass | Squad + product org + mentorship | Solo PM gate | Passes zero-token gate | implemented |
| `AC-196` | `FR-189` | Years lock fit | 4–7 years JD after gates pass | Fit scoring | No years-over-max penalty | implemented |
| `AC-118` | `FR-110` | AI tools OK | JD mentions ChatGPT as plus | LLM fit | Not sole reject reason | implemented |
| `AC-119` | `FR-111` | JD Deduplication via Vector Similarity | New JD arrives | Compare vector to existing | JD is deduplicated correctly | implemented |
| `AC-120` | `FR-112` | I/O vs GPU Concurrency Splitting | Batch process starts | I/O and GPU tasks | Process concurrency is split safely | implemented |
| `AC-121` | `FR-113` | Local Salary Extraction | Salary string is passed | Extract salary locally | Correct salary integer extracted | implemented |
| `AC-122` | `FR-114` | Vector-Based ATS Backlog Re-ranking | Backlog is re-ranked | Compare vectors | Correct order and updated ranks | implemented |
| `AC-123` | `FR-115` | Rapid Metadata Tagging using Cosine Similarity | Tags generated | Compute cosine similarity | Tags assigned efficiently | implemented |
| `AC-124` | `FR-116` | SQLite FTS5 Search Integration | Queries are sent | FTS5 enabled tables | Text searches match semantics | implemented |
| `AC-125` | `FR-117` | DOM Cleanup Pre-Processor for JDs | HTML loaded | Pre-process | Clean text returned | implemented |
| `AC-126` | `FR-118` | Prompt Context Truncation Guard | Long context passed | Enforce limits | Text is truncated safely | implemented |
| `AC-127` | `FR-119` | Fast-Fail Context Fallbacks | System encounters an error | Try fallback | Recovers from context error | implemented |
| `AC-128` | `FR-120` | Local Skill-Gap Analysis & UI integration | Skills analyzed | Render UI | Shows gap correctly | implemented |
| `AC-129` | `FR-121` | Cover Letter Intro Customization via local model | Prompt sent | Local model processes | Custom intro generated | implemented |
| `AC-130` | `FR-122` | Local Offline Web Research (SearXNG + Playwright) | Queries triggered | SearXNG runs locally | Retrieves valid results offline | implemented |
| `AC-131` | `FR-123` | Competitor Matrix via Pre-computed Local Vectors | Compare vectors | Run model | Valid matrix is generated | implemented |
| `AC-132` | `FR-124` | Zero-Shot On-Site Classifier | JD indicates on-site | Run local model | Correctly classifies role type | implemented |
| `AC-133` | `FR-125` | Auto-Pruning Stale DB Blobs script/cron | Run pruning script | DB is checked | Stale blobs are deleted | implemented |
| `AC-134` | `FR-126` | Local Model Text Streaming (SSE) | Generate text | SSE enabled | Text is streamed line by line | implemented |
| `AC-135` | `FR-127` | WebGPU Browser-Side Inference for Grammar checks | Input text | Check with WebGPU | Errors highlighted client-side | implemented |
| `AC-136` | `FR-128` | Responsive PDF Layout Feedback dynamically | Layout updated | PDF scaled | Fits one page cleanly | implemented |
| `AC-137` | `FR-129` | Notification Webhooks (Tailscale Native / NTFY) | System event occurs | Send webhook | Push notification received | implemented |
| `AC-138` | `FR-130` | Local PII Redaction Guard via SpaCy/Regex | Input containing PII | Run guard | PII replaced with redaction | implemented |
| `AC-139` | `FR-131` | Compose pipeline env defaults | Batch starts | Env vars | `DRAFT_MODE=compose`, `JD_PROFILE_MODE=deterministic`, `COVER_HOOK_MODE=template` | implemented |
| `AC-140` | `FR-132` | Pre-score job ordering | Batch queue | Sort by pre_score | Higher-signal jobs evaluated first | implemented |
| `AC-141` | `FR-133` | Strict local-only LLM | `LOCAL_ONLY_MODE=1` | Fit/draft calls | No Gemini fallback in logs | implemented |
| `AC-142` | `FR-134` | Stage-specific local models | `call_llm_stage('fit')` | Model pin | Uses `localModelFit` or qwen2.5 default | implemented |
| `AC-143` | `FR-135` | Scout seniority gate | Scout ingest | Years/title reject | Logged before DB insert | implemented |
| `AC-144` | `FR-136` | Template cover hook | Compose cover | Read para 1 | No ungrounded LLM hook by default | implemented |
| `AC-145` | `FR-137` | Summary grounding | Compose summary | Audit | Fails back to theme-only if metrics invented | implemented |
| `AC-146` | `FR-138` | Manifest claim_sources | Draft completes | `draft_manifest.json` | Maps ACC IDs to source snippets | implemented |
| `AC-147` | `FR-139` | PDF export verification gate | Save Resume.md | PUT without verify | 400 if manifest not passed | implemented |
| `AC-148` | `FR-140` | Grammar highlight-only | Editor lint | Lint click | Text unchanged; issues listed | implemented |

### CR-021 Funnel & compose (FR-131–FR-150)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-131` | functional | P0 | implemented | Pipeline env defaults for compose + local | `AC-139` | CR-021 |
| `FR-132` | functional | P1 | implemented | BM25+embedding pre-score before fit LLM | `AC-140` | CR-021 |
| `FR-133` | functional | P0 | implemented | Strict local-only provider chain | `AC-141` | CR-021 |
| `FR-134` | functional | P1 | implemented | Per-stage Ollama model selection | `AC-142` | CR-021 |
| `FR-135` | functional | P1 | implemented | Scout-time seniority/years gate | `AC-143` | CR-021 |
| `FR-136` | functional | P0 | implemented | Template-only cover letter hook in compose | `AC-144` | CR-021 |
| `FR-137` | functional | P0 | implemented | Summary numeric grounding | `AC-145` | CR-021 |
| `FR-138` | functional | P1 | implemented | Draft manifest claim source trace | `AC-146` | CR-021 |
| `FR-139` | functional | P1 | implemented | PDF compile blocked without verification | `AC-147` | CR-021 |
| `FR-140` | functional | P2 | implemented | WebGPU grammar issues without rewrite | `AC-148` | CR-021 |
| `FR-141` | functional | P0 | implemented | Block legacy_llm when LOCAL_ONLY_MODE | `AC-149` | CR-021 |
| `FR-142` | functional | P1 | implemented | JdProfile disk cache per submission | `AC-150` | CR-021 |
| `FR-143` | functional | P1 | implemented | Claim embeddings build script + cache refresh | `AC-151` | CR-021 |
| `FR-144` | functional | P2 | implemented | Draft linter JSON-only (no rewrite) | `AC-152` | CR-021 |
| `FR-145` | functional | P1 | implemented | Anti-claim phrase verification | `AC-153` | CR-021 |
| `FR-146` | functional | P0 | implemented | Verb + numeric grounding on compose bullets | `AC-154` | CR-021 |
| `FR-147` | functional | P2 | implemented | ATS watchlist scout channel | `AC-155` | CR-021 |
| `FR-148` | functional | P1 | implemented | GitHub Actions pipeline smoke | `AC-156` | CR-021 |
| `FR-149` | functional | P1 | implemented | BM25-pruned fit + JSON schema fit eval | `AC-157` | CR-021 |
| `FR-150` | functional | P1 | implemented | RESEARCH_MODE local/skip/cloud routing | `AC-158` | CR-021 |

| `AC-149` | `FR-141` | legacy_llm blocked | LOCAL_ONLY + legacy_llm | compose entry | RuntimeError with clear message | implemented |
| `AC-150` | `FR-142` | JdProfile cache | Same JD re-draft | Read cache file | `jd_profile_cache.json` hash matches | implemented |
| `AC-151` | `FR-143` | Embeddings build | Run build script | claim_embeddings.json | All ACC IDs have vectors | implemented |
| `AC-152` | `FR-144` | Linter no rewrite | lint_draft_text | Output | issues list only; text unchanged | implemented |
| `AC-153` | `FR-145` | Anti-claim | DO NOT phrase in output | verify chain | ValueError | implemented |
| `AC-154` | `FR-146` | Verb gate | Invented verb bullet | validate_bullet_for_local | Rejected | implemented |
| `AC-155` | `FR-147` | ATS watchlist | config file present | Scout run | ATS source in health log | implemented |
| `AC-156` | `FR-148` | CI smoke | Push to main | workflow | smoke_draft_compiler passes | implemented |
| `AC-157` | `FR-149` | Fit BM25+schema | Batch fit call | Logs | Uses pruned context + JSON schema | implemented |
| `AC-158` | `FR-150` | Research mode | LOCAL_ONLY research | fetch | SearXNG/local path, no Perplexity required | implemented |

### CR-024 Cover conversion engine (FR-157–FR-163)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-157` | functional | P0 | implemented | Cover conversion engine v1 — `cover_letter_compiler.py` Match Brief (JD + catalog, micro-narrative slots, audit loop) when `COVER_ENGINE=v1` | `AC-164`, `AC-166` | `CR-024` |
| `FR-158` | functional | P0 | implemented | Independent cover pipeline — cover claim selection SHALL NOT read `Resume.md` or resume-stage bullet dict | `AC-165` | `CR-024` |
| `FR-159` | functional | P1 | implemented | `cover_letter_plan.json` — traceability for claim IDs, ranked needs, themes per submission | `AC-165` | `CR-024` |
| `FR-160` | functional | P0 | implemented | Application-first cover opener — “I am applying for…”; audit bans “{Company} is hiring” | `AC-164` | `CR-024` |
| `FR-161` | functional | P0 | implemented | Theme prose formatting — `format_themes_for_prose()` prevents chained “and” in resume summary and cover theme lines | `AC-167` | `CR-024` |
| `FR-162` | functional | P1 | implemented | Cover letter conversion audit — weighted rubric in `cover_letter_audit.py` (word band, metrics, buzzwords) | `AC-164` | `CR-024` |
| `FR-163` | functional | P1 | implemented | JD `ranked_needs` extraction — responsibilities/requirements clauses for cover proof mapping; excludes salary lines | `AC-169` | `CR-024` |

| `AC-164` | `FR-157`, `FR-160`, `FR-162` | Cover engine v1 | `COVER_ENGINE=v1` regen | Letter opens with application; audit Pass | implemented |
| `AC-165` | `FR-158`, `FR-159` | Cover plan | Read `cover_letter_plan.json` | claim_ids + needs; no resume input | implemented |
| `AC-166` | `FR-157` | Batch covers | `regenerate_all_cover_letters.py` | 11 folders PDF+md | implemented |
| `AC-167` | `FR-161` | Summary themes | Themes with internal “and” | `build_summary_deterministic` | No triple-and chain | implemented |
| `AC-168` | `FR-157` | Cover numeric audit | Cover-only verify | Uses claim catalog corpus | Metrics from claims pass | implemented |
| `AC-169` | `FR-163` | Forbes pilot | Forbes JD | Cover letter | JD-specific match narrative | implemented |

### CR-025 Audit remediation (FR-164–FR-169)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-164` | functional | P0 | implemented | Subprocess hardening — server routes use `spawn` with array args, never shell-interpolated user input | `AC-170` | `CR-025` |
| `FR-165` | functional | P0 | implemented | Evaluate SSE `done` event includes score, company, title, url, summary from pipeline stdout | `AC-171` | `CR-025` |
| `FR-166` | functional | P0 | implemented | PDF export fail-closed — `generate_pdf` raises; manifest only after PDF exists | `AC-172` | `CR-025` |
| `FR-167` | functional | P1 | implemented | Pipeline mutex — concurrent sync/evaluate/draft returns 409 when busy | `AC-173` | `CR-025` |
| `FR-168` | functional | P1 | implemented | FTS sync on job write — `syncJobFts` after INSERT/PATCH | `AC-174` | `CR-025` |
| `FR-169` | functional | P1 | implemented | Company slug sanitization — shared `company_slug.py` / `sanitizeCompanySlug()` blocks traversal | `AC-170` | `CR-025` |

| `AC-170` | `FR-164`, `FR-169` | No shell injection | POST rerank, GET skill-gap | spawn args only | implemented |
| `AC-171` | `FR-165` | Evaluate done payload | POST /api/evaluate SSE | done event has score | implemented |
| `AC-172` | `FR-166` | PDF gate | draft_compiler | Missing PDF raises | implemented |
| `AC-173` | `FR-167` | Pipeline lock | POST /api/sync while busy | 409 response | implemented |
| `AC-174` | `FR-168` | FTS sync | POST /api/jobs | jobs_fts row updated | implemented |

### CR-027 / CR-028 Collection quality gates (FR-170–FR-173)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-170` | functional | P1 | implemented | Deterministic `blocked_industries` gate at scout + batch zero-token | `AC-175`–`AC-178` | `CR-027` |
| `FR-171` | functional | P1 | implemented | `must_have_keywords` (AND) + `signal_keywords` (OR) in zero-token gate | `AC-179` | `CR-028` |
| `FR-172` | functional | P2 | implemented | `required_anchors` preserved in prefs; optional `ANCHOR_GATE_ENABLED` two-anchor gate | `AC-180` | `CR-028` |
| `FR-173` | functional | P1 | implemented | Levels.fyi skip without title; Remote-only geo bypass tightened | `AC-181`, `AC-182` | `CR-028` |

| `AC-175` | `FR-170` | Industry blocklist | Company Crypto.com, block Crypto | Scout ingest | Rejected `industry_blocked:Crypto` | implemented |
| `AC-176` | `FR-170` | Industry batch header | DraftKings header, block Sports Betting | Zero-token gate | Rejected before LLM | implemented |
| `AC-177` | `FR-170` | Empty blocklist | No blocked industries | Gates run | No-op | implemented |
| `AC-178` | `FR-170` | B2B pass | Salesforce, no blocked term | Gates run | Passes | implemented |
| `AC-179` | `FR-171` | Must-have AND | must_have saas+b2b, JD agile only | Keyword gate | Reject `missing_must_have` | implemented |
| `AC-180` | `FR-172` | Anchor gate | ANCHOR_GATE_ENABLED=1, 1 hit | Batch gate | Reject `anchor_hits_1` | implemented |
| `AC-181` | `FR-173` | Levels parse | Empty title from card | Scout | Skip row | implemented |
| `AC-182` | `FR-173` | Remote geo | Remote work_setting, BuiltIn stub | Scout geo | Reject not bypass | implemented |

### CR-033 Built In detail-page JD (FR-180)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-180` | functional | P0 | implemented | Built In scout opens each new job URL and extracts full JD before industry/geo/seniority gates | `AC-183` | `CR-033` |

| `AC-183` | `FR-180` | Built In JD | New card passes dedup | Scout detail fetch | Description ≥ 200 chars required; gates use full text; `jd_text` + staging file written | implemented |

### CR-034 Built In strict geo-signal hardening (FR-181)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-181` | functional | P1 | implemented | Built In scout preserves explicit card-level remote/SD location cues in description input so strict geo gate evaluates real evidence without source bypass | `AC-184`, `AC-185` | `CR-034` |
| `FR-182` | functional | P1 | implemented | Built In scout starts from strict seed URL constrained to Remote + Mid-level + Product Manager + USA + freshness window | `AC-186` | `CR-034` |
| `FR-183` | functional | P1 | implemented | Built In card pre-filter for PM title scope and strict remote listing before detail fetch | `AC-187`, `AC-188` | `CR-034` |

| `AC-184` | `FR-181` | Built In remote card signal | Built In card text contains explicit `remote` cue | Scout detail fetch + gates | Description is prefixed with normalized listing location signal and geo gate may pass on explicit remote text | implemented |
| `AC-185` | `FR-181` | Strict policy retained | Built In card lacks remote and SD cues | Scout geo | Job remains rejected out-of-bound | implemented |
| `AC-186` | `FR-182` | Strict seed target | Built In scout starts | URL builder runs | Crawler uses strict single target URL (`/jobs/remote/mid-level?...search=Product Manager&country=USA`) without taxonomy fallback | implemented |
| `AC-187` | `FR-183` | PM title scope | Built In card title is Product Marketing or Product Owner-only | Scout card loop | Reject before detail fetch | implemented |
| `AC-188` | `FR-183` | Strict remote card | Built In card shows Remote or Hybrid / In-Office or Remote | Scout card loop (Remote prefs) | Reject before detail fetch | implemented |

### CR-035 Fit scoring hardening (FR-188)
| `AC-191` | `FR-188` | Location lock | JD lists US cities and Remote | Fit evaluate | `REMOTE_OK`; model must not reject on location | implemented |
| `AC-192` | `FR-188` | Anchor floor | ≥2 anchors match; LLM score 65–71 | Fit post-process | ~~Promote to YES~~ **Retired (CR-053):** `anchor_hits_*` RiskFlags only; no score promotion | implemented |
| `AC-193` | `FR-188` | Optional domain | JD says "nice plus" for vertical | Fit prompt | Injects DOMAIN_REQUIREMENT: OPTIONAL | implemented |

### CR-037 Required domain experience gate (FR-190)
| `AC-197` | `FR-190` | Required domain | JD requires 3–5 years US healthcare; candidate lacks healthcare in domain_experience | Zero-token gate | Rejects with required_domain_missing:healthcare | implemented |
| `AC-198` | `FR-190` | Optional domain preserved | JD says healthcare is nice plus / may not have experience | Zero-token + fit | Domain gate passes; optional note injected | implemented |
| `AC-199` | `FR-190` | Fit cap | Cotiviti-class JD; LLM returns score 98 | Fit post-process | Forces NO when required domain gap | implemented |

### CR-038 B2C role openness (FR-191)
| `AC-200` | `FR-191` | B2C preference | open_to_b2c true | Fit prompt | Injects B2C openness note | implemented |
| `AC-201` | `FR-191` | Consumer keywords | JD mentions consumer/mobile app | Keyword gate | Passes without b2b token | implemented |
| `AC-202` | `FR-191` | Scoring neutrality | open_to_b2c true | Fit scoring-only | No B2B-only bridge reject instruction | implemented |

### CR-039 Transferable skills over domain gate (FR-192)
| `AC-203` | `FR-192` | No domain zero-token gate | Cotiviti-class required healthcare years | Zero-token pipeline | Passes gates; domain_gaps informational only | implemented |
| `AC-204` | `FR-192` | Transferable skills prompt | Any JD through fit | Fit scoring context | Injects TRANSFERABLE SKILLS POLICY | implemented |
| `AC-205` | `FR-192` | No domain cap | LLM score 98 on vertical gap | Fit post-process | No enforce_required_domain_cap | implemented |

### CR-040 Theme primary claims (FR-193)
| `AC-206` | `FR-193` | Security theme inject | JD mentions security backlog | Stage 2 selection | `ACC-103-ROADMAP` (or SEC/PM fallback) in selected claims | implemented |
| `AC-207` | `FR-193` | Cover corpus union | Cover cites 90%/300; claim on resume or catalog | `verify_document_bundle` | Numeric audit passes | implemented |

### CR-041 ATS watchlist no example (FR-194)
| `AC-208` | `FR-194` | No example watchlist | No `data/ats_watchlist.json` | Scout run | Zero jobs from Example Corp / demo Greenhouse | implemented |

### Phase 1 Resume Quality — Core Competencies & JD Parsing (FR-195 to FR-196)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-195` | functional | P1 | implemented | Core Competencies section assembly: two-row section injected between summary and experience; Row 1 sourced from tags of selected claims only (evidence-backed); Row 2 sourced from `data/skills_catalog.json` (static verified tools); both rows JD-sorted via `extract_req_section` boost; section omitted if no claims selected | `AC-209`: compiled resume contains `## CORE COMPETENCIES` heading; `AC-210`: every Row 1 skill maps to at least one selected claim tag; `AC-211`: section absent when `bullets_with_ids` is empty | `resume_decision_report_2026` |
| `FR-196` | functional | P1 | implemented | JD requirements section extraction: `extract_req_section(jd_text)` returns the subsection under requirements/qualifications headings for targeted skill scoring; falls back to full JD text when no heading is detected | `AC-212`: function returns sub-string when JD contains "Requirements", "What You'll Bring", or equivalent heading; `AC-213`: function returns full JD text when no heading detected | `resume_decision_report_2026` |
| `FR-197` | functional | P1 | implemented | Conversion signal detection: `check_conversion_signals()` scans compiled resume for duty-heavy bullets (no action verb + no metric), unquantified Cision bullets, word-count violations, and em-dash presence; returns non-empty warning list for any detected signals | `AC-214`: function returns CW-001 warning for a bullet with no action verb and no digit; `AC-215`: function returns CW-002 when all Cision bullets lack digits | `resume_decision_report_2026` |
| `FR-198` | functional | P1 | implemented | Manifest warning log: `draft_manifest.json["conversion_warnings"]` contains the output of `check_conversion_signals()`; field is always present (empty list when no warnings) | `AC-216`: manifest written after every pipeline run contains `conversion_warnings` key | `resume_decision_report_2026` |
| `FR-199` | functional | P1 | implemented | Summary opener accuracy: base summary opener uses accurate career-breadth framing without B2B narrowing or seniority inflation; JD-specific theme phrase replaces generic domain when themes are available | `AC-217`: compiled summary does not contain "B2B SaaS Product Manager"; `AC-218`: summary opener contains "Product Manager with 6+ years" | `resume_decision_report_2026` |
| `FR-200` | functional | P1 | implemented | Rubric scoring: `score_resume()` in `resume_rubric.py` scores every compiled resume against a weighted rubric (summary 40%, experience 60%) using deterministic regex and token-matching proxies; no LLM calls | `AC-219`: `score_resume()` returns a dict with `overall`, `summary`, and `experience` keys; `AC-220`: overall score is between 0 and 100 | `FEAT-015`, `resume_decision_report_2026` |
| `FR-201` | functional | P1 | implemented | Rubric threshold flag: `threshold_flag=True` when overall score < 60; printed to console with review recommendation; does not block pipeline unless `STRICT_RUBRIC=1` | `AC-221`: manifest contains `threshold_flag: true` when overall < 60 | `FEAT-015` |
| `FR-202` | functional | P1 | implemented | Rubric score manifest logging: `draft_manifest.json["rubric_score"]` contains full rubric result after every non-cover-only pipeline run; field is `null` in cover-only mode | `AC-222`: manifest written after pipeline run contains `rubric_score` key with `overall` sub-key | `FEAT-015` |
| `FR-208` | functional | P1 | implemented | Projects section injection: `build_projects_section()` reads `data/projects_catalog.json` and returns a formatted `## PROJECTS` block containing only `ai_relevant=true` entries; injected between experience and education when `has_ai_signal()` is true | `AC-223`: compiled resume contains `## PROJECTS` when JD text includes "AI", "LLM", "agentic", or similar terms; `AC-224`: section absent when JD contains no AI signal | `resume_decision_report_2026` |
| `FR-209` | functional | P1 | implemented | AI-role signal detection: `has_ai_signal(jd_text)` returns True when the JD body (first 80% of text) contains any AI/LLM indicator keyword; used to gate PROJECTS section injection and avoid job-board footer tag false positives | `AC-225`: `has_ai_signal()` returns True for JD containing "LLM", "agentic", "generative AI"; `AC-226`: returns False for a standard PM JD with no AI terms; `AC-226b`: returns False when AI terms appear only in trailing metadata/footer tags | `resume_decision_report_2026` |
| `FR-214` | functional | P1 | implemented | Metric bullet floor: `enforce_metric_bullet_floor()` swaps lowest-relevance non-metric bullets for metric-bearing alternatives until at least 4 experience bullets contain digits | `AC-235`: compiled resume contains ≥4 metric bullets when catalog has enough metric claims; `AC-236`: swaps only occur within the same employer bucket | `resume_decision_report_2026` |
| `FR-215` | functional | P1 | implemented | PDF page-count guard: after resume PDF export, `get_pdf_page_count()` checks page count; if >1, prune lowest-JD-relevance bullets and re-render until one page or employer floor quota is reached | `AC-237`: Everbridge-style overflow resumes are pruned to 1 page when possible; `AC-238`: guard logs prune count and final page count | `resume_decision_report_2026` |
| `FR-216` | functional | P1 | implemented | Conversion framing module: `conversion_framing.py` classifies outcome vs activity bullets, defensive summary phrases, and outcome metrics | `AC-239`: Sterkly activity bullets from critique are flagged `is_activity_bullet()==True`; `AC-240`: defensive summary phrases detected when security JD signal absent | `resume_decision_report_2026` |
| `FR-217` | functional | P1 | implemented | Sterkly metric anchor: `enforce_sterkly_metric_anchor()` ensures ≥1 outcome-metric Sterkly bullet when catalog provides one | `AC-241`: CVS-style resumes include `$1M-$3M` Sterkly bullet | `resume_decision_report_2026` |
| `FR-218` | functional | P1 | implemented | Activity cap per employer: max 1 activity-only bullet per employer; 0 for Sterkly when metric anchor present | `AC-242`: CVS Sterkly section does not lead with Partnered/Translated bullets | `resume_decision_report_2026` |
| `FR-219` | functional | P1 | implemented | Impact pyramid enforcer: swaps senior-role non-metric bullets for metric claims when junior role has more outcome metrics | `AC-243`: Cision metric count ≥ Zero to Sixty after enforcement | `resume_decision_report_2026` |
| `FR-220` | functional | P1 | implemented | Human-mirror conversion critique: `evaluate_resume_conversion()` detects incomplete summary, PDF header inversion, and Sterkly narrative gaps; logged to `draft_manifest.json["conversion_critique"]` | `AC-247`: manifest contains `conversion_critique.pass`; `AC-244`–`AC-246` | `CR-027` |
| `FR-221` | functional | P1 | implemented | PDF experience header layout: `compile_single.py` parses `Title \| Company \| Dates` with flex layout; no `float:right` on print | `AC-244`: company appears before location in PDF text extraction | `CR-027` |
| `FR-222` | functional | P1 | implemented | Sterkly context bridge: `enforce_sterkly_context()` swaps domain-jargon bullet for context claim when jargon ≥2 | `AC-246`: Sterkly includes developer/partnership context bullet | `CR-027` |
| `FR-223` | functional | P1 | implemented | One-proof summary: max one grounded proof sentence in `build_summary_deterministic()`; CW-013 detects stacked participle fragments | `AC-248`: CVS summary has one outcome-led proof, not multiple bullet clauses | `CR-027` |
| `FR-224` | functional | P1 | implemented | Experience-backed summary themes: summary opener uses only JD themes substantiated by selected bullets; JD-only themes move to cover-letter transferable bridge; CW-014 flags ungrounded focus phrases | `AC-249`: CVS summary does not claim analytics product delivery; cover letter may name analytics as transferable | `CR-027` |
| `FR-225` | functional | P1 | implemented | Summary attribution payoff + Sterkly weak-claim swap: full grounded adoption clause in summary; ACC-204-QA replaced by ACC-203-OPS/ACC-204-GLOBAL when available; CW-015 | `AC-250`: attribution summary includes 'sought to adopt it'; Sterkly drops task-only QA bullet | `CR-027` |

### CR-042 Resume quality enforcement — two-phase (FR-226–FR-232)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-226` | functional | P1 | implemented | Strict conversion critique: `STRICT_CONVERSION_CRITIQUE=1` raises `DraftingPipelineError` when `conversion_critique.pass` is false after PDF export | `AC-251`, `AC-252` | `CR-042` |
| `FR-227` | functional | P1 | implemented | `SUBMISSION_MODE=1` setdefault enables `STRICT_CONVERSION_CRITIQUE=1` alongside existing strict bundle | `AC-260` | `CR-042` |
| `FR-228` | functional | P1 | implemented | Auto-retry loop: up to `CONVERSION_RETRY_MAX` (default 2) deterministic fix attempts before strict gate | `AC-253`, `AC-254` | `CR-042` |
| `FR-229` | functional | P1 | implemented | `critique_retry.py` maps fixable CW-009/011/012/013/014/015 codes to summary/framing/PDF actions | `AC-253` | `CR-042` |
| `FR-230` | functional | P2 | implemented | Retry telemetry: manifest `attempts` + `retry_log`; console remediation hints on final fail | `AC-255` | `CR-042` |
| `FR-231` | functional | P1 | implemented | Golden JD archetype smoke: analytics / platform / generic PM fixtures assert critique PASS | `AC-256`, `AC-257` | `CR-042` |
| `FR-232` | functional | P2 | implemented | Fleet conversion report: scan `submissions/*/draft_manifest.json` for pass rate and top failing codes | `AC-258`, `AC-259` | `CR-042` |

### CR-043 Deterministic cover voice (FR-233–FR-236)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-233` | functional | P1 | implemented | Cover voice phrasing module: banned robot/casual phrases; `apply_voice_polish()`; no LLM rewrite | `AC-261` | `CR-043` |
| `FR-234` | functional | P1 | implemented | Cover word band 300–400 in renderer and audit | `AC-262` | `CR-043` |
| `FR-235` | functional | P1 | implemented | Proof paragraphs render `cover_story` only without template JD bridge | `AC-261` | `CR-043` |
| `FR-236` | functional | P2 | implemented | Opener `jd_presence_clause` for audit JD fragment; cover_story uses constraints language not layoffs | `AC-263` | `CR-043` |
| `FR-210` | functional | P1 | implemented | Outcome-rubric correlation logging: on status change to Closed/Screener/Interview/Offer, reads `draft_manifest.json["rubric_score"]` and appends a `RubricLog` activity_log entry with outcome, rubric_overall, summary_score, experience_score, and threshold_flag in the meta JSON column | `AC-227`: activity_log contains a row with source="RubricLog" and meta.event="outcome_rubric_log" after a job is moved to Closed; `AC-228`: field is absent when no draft_manifest.json exists for the company | `FEAT-015` |
| `FR-211` | functional | P1 | implemented | JD pain-point extraction: `extract_jd_pain_points(jd_text)` returns up to 5 short hiring-signal phrases (e.g., "reduce churn", "scale the platform") grounded as substrings of the JD role description; stored in `CoverLetterPlan.pain_points` | `AC-229`: function returns a list of strings for a JD containing "help us scale"; `AC-230`: all returned phrases are literal substrings of the input JD | `cover_letters_llm_report_2026` |
| `FR-212` | functional | P1 | implemented | CSI cover story catalog: high-value `master_claims.json` entries carry a `cover_story` field containing a 2-3 sentence Challenge-Decision-Impact narrative sourced from `workExperience.md`; `ClaimRecord.cover_story` loaded at catalog parse time; claims with `cover_story` receive a +10 score bonus in `pick_cover_proofs()` and are preferred for cover letter body paragraphs | `AC-231`: `ClaimRecord` for ACC-105-PROCESS has non-null `cover_story`; `AC-232`: story-bearing claim outscores an equal story-free claim by at least 10 points | `cover_letters_llm_report_2026` |
| `FR-213` | functional | P1 | implemented | Cover letter conversion signal detection: `check_cl_conversion_signals(cl_text, jd_text)` returns non-blocking warnings for CLW-002 (opener has fewer than 2 JD-specific terms) and CLW-004 (enthusiasm word in paragraph with no evidence); warnings logged to `draft_manifest.json["cl_conversion_warnings"]` | `AC-233`: CLW-004 fires when letter contains "excited" in a paragraph with no metric or action verb; `AC-234`: CLW-002 fires when opener contains only company name and role title with no JD content tokens | `cover_letters_llm_report_2026` |

### CR-031 Draft quality gates (FR-174–FR-179)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-174` | functional | P1 | implemented | Unified approved metrics module | `approved_metrics.py` imported by guards | `CR-031` |
| `FR-175` | functional | P1 | implemented | Catalog validation + anti-claim hints | `catalog_validator.py`, `claim_catalog.py` | `CR-031` |
| `FR-176` | functional | P1 | implemented | Optional strict fail-closed flags | `pipeline_env.py` STRICT_* | `CR-031` |
| `FR-177` | functional | P1 | implemented | Document Editor light verify | `verify_editor_save.py`, jobs route | `CR-031` |
| `FR-178` | functional | P2 | implemented | Claim strength in draft manifest | `draft_compiler.py` | `CR-031` |
| `FR-179` | functional | P2 | implemented | Baseline quality gate report | `baseline_quality_gates.py` | `CR-031` |

### CR-046 Unified test runner (FR-241)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-241` | functional | P1 | accepted | Unified test runner that executes both Python unit tests and Vitest TypeScript tests with UTF-8 encoding support | `AC-215`, `AC-216`, `AC-217`, `AC-218`, `AC-219` | `CR-046` |

### CR-053 / CR-054 / CR-055 Fit, pipeline & collection gates (FR-242–FR-248)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-242` | functional | P1 | implemented | Structured evidence-tiered fit scoring: must-have extraction, LLM equivalence judgments (no holistic score), deterministic weighted score + confidence review routing (`STRUCTURED_FIT=1` default) | `AC-264`, `AC-266` | CR-053 |
| `FR-243` | functional | P1 | implemented | Extended deterministic location gate: non-SD onsite/hybrid cities, Canada in-person, EST/CST-only remote | `AC-265` | CR-053 |
| `FR-244` | functional | P1 | implemented | Requirements-anchored years parsing; ignore incidental year figures in JD prose | `AC-267` | CR-055 |
| `FR-245` | functional | P1 | implemented | Contextual title blocklist: `blocked_role_titles` vs `blocked_focus_area_words` | `AC-268` | CR-055 |
| `FR-246` | functional | P0 | implemented | Post-draft audit convergence failure must surface as `passed: false`; restore pre-audit submission files on failure | `AC-269` | CR-054 |
| `FR-247` | functional | P1 | implemented | `blocked_companies` zero-token gate before fit scoring | `AC-270` | CR-054 |
| `FR-248` | functional | P1 | implemented | `materializeJobSearchPrefs()` preserves pipeline gate keys across UI save (ADR-005) | `AC-271` | CR-053, CR-055, FEAT-009 |

| `AC-264` | acceptance | P1 | implemented | Structured fit path computes score in code; LLM returns judgments only | `FR-242` | CR-053 |
| `AC-265` | acceptance | P1 | implemented | Location fixtures for hybrid NYC, onsite Chicago, Canada in-person reject | `FR-243` | CR-053 |
| `AC-266` | acceptance | P1 | implemented | Required-domain JD scores lower than strong PM JD without domain hard-require | `FR-242` | CR-053 |
| `AC-267` | acceptance | P1 | implemented | Jackson Lab / Civica years fixtures ignore prose-year false positives | `FR-244` | CR-055 |
| `AC-268` | acceptance | P1 | implemented | `Product Manager, Growth` passes title gate; `Head of Growth` blocks | `FR-245` | CR-055 |
| `AC-269` | acceptance | P0 | implemented | Audit non-convergence → pipeline `passed: false` + file restore | `FR-246` | CR-054 |
| `AC-270` | acceptance | P1 | implemented | Blocklisted company rejected at zero-token gate | `FR-247` | CR-054 |
| `AC-271` | acceptance | P1 | implemented | UI re-save preserves `blocked_role_titles`, `blocked_focus_area_words`, `blocked_companies` | `FR-248` | FEAT-009 |

### CR-051 Interview datetime gate (FR-251)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-251` | functional | P1 | implemented | Status transitions to Recruiter Screen or Core Interviews require a valid `interview_date` (UI block + API 400) | CR-051 acceptance criteria | `CR-051` |

### CR-074 Token-conscious authoring packet (FR-252–FR-255)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-252` | functional | P0 | implemented | Deterministic Stage 0 builder produces `stage0_fit_gate.json` (DB cooldown, prefs/exclusion gates, JD buckets, hard/soft gaps) without a cloud LLM call on the common path | `AC-272` | CR-074 |
| `FR-253` | functional | P0 | implemented | Authoring packet builder emits fail-closed `authoring_packet.json` (evidence map + workExperience excerpts only for selected ACC/MET IDs + soft gaps + rule digest version) under the documented size budget | `AC-273`, `AC-274` | CR-074 |
| `FR-254` | functional | P0 | implemented | Single cloud authoring pass drafts Resume.md + CoverLetter.md from packet + lean rule digest only (closed world: no inventing claims outside packet IDs) | `AC-275` | CR-074 |
| `FR-255` | functional | P0 | implemented | Default Stage 2 verification is scripts-first (`verify_submission`, coverage, jd terms, `--audit`); fresh-cloud independent review is optional / send-batch only | `AC-276`, `AC-277` | CR-074 |
| `AC-272` | acceptance | P0 | implemented | Stage 0 script succeeds for ≥3 real JDs with no cloud LLM | `FR-252` | CR-074 |
| `AC-273` | acceptance | P0 | implemented | Packet build fails if any required item lacks claim_ids and bridge, or selected claim is disabled, or excerpt missing | `FR-253` | CR-074 |
| `AC-274` | acceptance | P0 | implemented | Estimated packet tokens ≤ budget locked in Epic 1 metrics (initial ceiling 8k est. tokens) | `FR-253` | CR-074 |
| `AC-275` | acceptance | P0 | implemented | Author path does not require `agent_context_pack.md` as an input | `FR-254` | CR-074 |
| `AC-276` | acceptance | P0 | implemented | SKILL.md Stage 2 default is scripts-only; multi-agent Stage 2 demoted | `FR-255` | CR-074 |
| `AC-277` | acceptance | P0 | implemented | Calibration ≥3 real submissions clear mechanical verify; Jason send-ready judgment recorded | `FR-254`, `FR-255` | CR-074 |

### CR-075 Stage 0-2 completion gates & verification lineage (FR-256)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-256` | functional | P0 | implemented | Stage 0-2 completion is machine-enforced via `contracts.check_stage{0,1,2}_ready` / `check_finalize_ready` predicates plus `stage_gate.py` enforcement at producing scripts; verification receipts carry content hashes; Stage 2 records rubric-audit + claim_provenance WARN fields; batch Author path uses CR-074 packet context | `AC-278`–`AC-288` | CR-075 |
| `AC-278` | acceptance | P0 | implemented | `check_stage1_ready()` and `check_stage2_ready()` exist in `contracts.py`, return `(bool, list[str])`, with unit tests (CR-075 AC1) | `FR-256` | CR-075 |
| `AC-279` | acceptance | P0 | implemented | `build_authoring_packet.py` refuses invalid/missing `stage0_fit_gate.json` unless `--force`; override logged (CR-075 AC2) | `FR-256` | CR-075 |
| `AC-280` | acceptance | P0 | implemented | `author_from_packet.py` / `--verify-only` refuse `packet_status != ready` with **no** `--force` override for that condition (CR-075 AC3) | `FR-256` | CR-075 |
| `AC-281` | acceptance | P0 | implemented | Stage 2 complete requires fresh hash-verified receipt + populated `rubric_score` + claim_provenance field present in receipt (WARN content non-blocking) (CR-075 AC4) | `FR-256` | CR-075 |
| `AC-282` | acceptance | P0 | implemented | Known-stale folders (camunda/ncontracts/paylocity) fail freshness under hash-aware `check_freshness` (CR-075 AC5) | `FR-256` | CR-075 |
| `AC-283` | acceptance | P0 | implemented | Rubric `--audit` runs inline whenever `rubric_score` is present and gates `verification_passed` (CR-075 AC6) | `FR-256` | CR-075 |
| `AC-284` | acceptance | P0 | implemented | Batch `authorPrompt()` uses packet+digest; company-count guard ≤3 without opt-in (CR-075 AC7) | `FR-256` | CR-075 |
| `AC-285` | acceptance | P0 | implemented | `check_submission_status.py` report shape unchanged (CR-075 AC8) | `FR-256` | CR-075 |
| `AC-286` | acceptance | P0 | implemented | `claim_provenance` WARN never blocks `check_stage2_ready`; script listed in Required Verification (CR-075 AC9) | `FR-256` | CR-075 |
| `AC-287` | acceptance | P0 | implemented | Stage 2 bare `--force` rejected; requires `--force-reason`; Stages 0/3 bare `--force` unchanged (CR-075 AC10) | `FR-256` | CR-075 |
| `AC-288` | acceptance | P0 | implemented | Post-CR-075 compose emits valid `claim_provenance.json` from packet evidence_map (CR-075 AC11) | `FR-256` | CR-075 |

### CR-076 Workflow authority foundation (FR-257)

| ID | Type | Priority | Status | Statement | Acceptance | Source |
|----|------|----------|--------|-----------|------------|--------|
| `FR-257` | functional | P0 | in_progress | Authoritative `run_submission` CLI + `scripts/workflow/` owns workflow_state/stage_receipts; workers never write those files; Stage 0→packet/prompt→WAITING_FOR_LLM vertical slice; `check_workflow_complete` is the DONE oracle (full COMPLETE in later CRs) | `AC-289`–`AC-293` | CR-076 |
| `AC-289` | acceptance | P0 | in_progress | Stage 0 via existing builder + receipt; Skip → workflow SKIPPED | `FR-257` | CR-076 |
| `AC-290` | acceptance | P0 | in_progress | Pass builds packet+prompt and stops at WAITING_FOR_LLM | `FR-257` | CR-076 |
| `AC-291` | acceptance | P0 | in_progress | Only workflow.receipts writes stage_receipts | `FR-257` | CR-076 |
| `AC-292` | acceptance | P0 | in_progress | check_workflow_complete False for mid-states; reports WAITING_FOR_LLM/SKIPPED | `FR-257` | CR-076 |
| `AC-293` | acceptance | P0 | in_progress | Adopt existing valid Stage 0/packet/prompt artifacts into receipts | `FR-257` | CR-076 |

### CR-077 Receipt chaining + hash invalidation (FR-258)

| ID | Type | Priority | Status | Statement | Acceptance | Source |
|----|------|----------|--------|-----------|------------|--------|
| `FR-258` | functional | P0 | in_progress | After WAITING_FOR_LLM, docs → verify-only → Stage 1 COMPLETE receipt with prior chain; Stage 2 READY only; hash reconcile marks STALE + locks downstream; `--resume` | `AC-294`–`AC-298` | CR-077 |
| `AC-294` | acceptance | P0 | in_progress | Docs present after WAITING_FOR_LLM → verify-only + Stage 1 COMPLETE with prior_receipt_id | `FR-258` | CR-077 |
| `AC-295` | acceptance | P0 | in_progress | Stage 2 READY only when Stage 1 COMPLETE and hashes fresh | `FR-258` | CR-077 |
| `AC-296` | acceptance | P0 | in_progress | Edit Resume/CL after Stage 1 COMPLETE → Stage 1 STALE, Stage 2 LOCKED | `FR-258` | CR-077 |
| `AC-297` | acceptance | P0 | in_progress | `--resume` continues WAITING→validate or rebuilds from STALE without inventing COMPLETE | `FR-258` | CR-077 |
| `AC-298` | acceptance | P0 | in_progress | CR-075 `check_stage1_ready` still enforced (no force for packet_status) | `FR-258` | CR-077 |

### CR-079 Truth / Evidence review (FR-260)

| ID | Type | Priority | Status | Statement | Acceptance | Source |
|----|------|----------|--------|-----------|------------|--------|
| `FR-260` | functional | P0 | in_progress | Stage 2A Truth: mechanical collectors → reviews/truth_findings.json; dispositions; WAITING_FOR_HUMAN or truth COMPLETE + ats READY; no stage2 receipt | `AC-307`–`AC-311` | CR-079 |
| `AC-307` | acceptance | P0 | in_progress | Stage1 COMPLETE → Truth collectors + truth_findings.json | `FR-260` | CR-079 |
| `AC-308` | acceptance | P0 | in_progress | Open findings → WAITING_FOR_HUMAN + dispositions stub; no Stage 2 COMPLETE receipt | `FR-260` | CR-079 |
| `AC-309` | acceptance | P0 | in_progress | CLEAN dispositions → truth COMPLETE + ats READY | `FR-260` | CR-079 |
| `AC-310` | acceptance | P0 | in_progress | HUMAN_ACCEPTED_RISK → PASS with OVERRIDDEN integrity | `FR-260` | CR-079 |
| `AC-311` | acceptance | P0 | in_progress | BLOCK+FALSE_POSITIVE fails; Stage1 STALE resets truth subphase | `FR-260` | CR-079 |

### CR-080 ATS / AI review (FR-261)

| ID | Type | Priority | Status | Statement | Acceptance | Source |
|----|------|----------|--------|-----------|------------|--------|
| `FR-261` | functional | P0 | in_progress | Stage 2B ATS: jd_term_extractor → reviews/ats_findings.json; dispositions; WAITING_FOR_HUMAN or ats COMPLETE + hm READY | `AC-312`–`AC-315` | CR-080 |
| `AC-312` | acceptance | P0 | in_progress | Truth COMPLETE → ATS collectors + ats_findings.json | `FR-261` | CR-080 |
| `AC-313` | acceptance | P0 | in_progress | Open ATS findings → WAITING_FOR_HUMAN; no Stage 2 receipt | `FR-261` | CR-080 |
| `AC-314` | acceptance | P0 | in_progress | CLEAN dispositions → ats COMPLETE + hm READY | `FR-261` | CR-080 |
| `AC-315` | acceptance | P0 | in_progress | ATS blocked until Truth COMPLETE | `FR-261` | CR-080 |

### CR-081 HM + mech + Stage 2 receipt (FR-262)

| ID | Type | Priority | Status | Statement | Acceptance | Source |
|----|------|----------|--------|-----------|------------|--------|
| `FR-262` | functional | P0 | in_progress | Stage 2C–2E: HM findings, mech compile+verify_one, check_stage2_ready → stage2 COMPLETE receipt + stage3 READY | `AC-316`–`AC-320` | CR-081 |
| `AC-316` | acceptance | P0 | in_progress | HM critical_read + lint findings; WAITING_FOR_HUMAN until disposed | `FR-262` | CR-081 |
| `AC-317` | acceptance | P0 | in_progress | Mech wraps compile_single + verify_one | `FR-262` | CR-081 |
| `AC-318` | acceptance | P0 | in_progress | Policy PASS writes stage2 COMPLETE + stage3 READY | `FR-262` | CR-081 |
| `AC-319` | acceptance | P0 | in_progress | check_stage2_ready FAIL → policy WAITING_FOR_HUMAN | `FR-262` | CR-081 |
| `AC-320` | acceptance | P0 | in_progress | Sole receipt writer + OVERRIDDEN integrity carry-forward | `FR-262` | CR-081 |

### CR-084 Stage 3 finalize under orchestrator (FR-263)

| ID | Type | Priority | Status | Statement | Acceptance | Source |
|----|------|----------|--------|-----------|------------|--------|
| `FR-263` | functional | P0 | in_progress | Stage 3: `--finalize` wraps finalize_submission_job; stage3 COMPLETE receipt; terminal COMPLETE / COMPLETE_WITH_OVERRIDE / PRACTICE_COMPLETE | `AC-321`–`AC-325` | CR-084 |
| `AC-321` | acceptance | P0 | in_progress | Stage2 COMPLETE + `--finalize` wraps finalize worker | `FR-263` | CR-084 |
| `AC-322` | acceptance | P0 | in_progress | Production → stage3 receipt + workflow COMPLETE | `FR-263` | CR-084 |
| `AC-323` | acceptance | P0 | in_progress | Practice → PRACTICE_COMPLETE, no DB | `FR-263` | CR-084 |
| `AC-324` | acceptance | P0 | in_progress | OVERRIDDEN → COMPLETE_WITH_OVERRIDE; check_workflow_complete True | `FR-263` | CR-084 |
| `AC-325` | acceptance | P0 | in_progress | Without `--finalize`, stop at Stage 3 READY | `FR-263` | CR-084 |

### CR-091 Stage 0 skip ledger (FR-264)

| ID | Type | Priority | Status | Statement | Acceptance | Source |
|----|------|----------|--------|-----------|------------|--------|
| `FR-264` | functional | P0 | implemented | Stage 0 Skip is remembered by URL (then company+title) in `stage0_skips`; incoming JDs stay in pending_review until PASS; Skips move to archive/skipped | `AC-326`–`AC-331` | CR-091 |
| `AC-326` | acceptance | P0 | implemented | Normalized URL hit returns the prior Skip without re-extraction | `FR-264` | CR-091 |
| `AC-327` | acceptance | P0 | implemented | Same company, different title does not hit the ledger | `FR-264` | CR-091 |
| `AC-328` | acceptance | P0 | implemented | CSV import writes to pending_review and skips ledger URLs | `FR-264` | CR-091 |
| `AC-329` | acceptance | P0 | implemented | Production Skip → archive/skipped + ledger; PASS from pending_review → submissions | `FR-264` | CR-091 |
| `AC-330` | acceptance | P0 | implemented | `--force` PASS deletes the ledger row | `FR-264` | CR-091 |
| `AC-331` | acceptance | P0 | implemented | Reconcile sweeps SKIP fit-gate folders out of submissions | `FR-264` | CR-091 |

### CR-102 Stage 1 first-draft quality contract (FR-265)

| ID | Type | Priority | Status | Statement | Acceptance | Source |
|----|------|----------|--------|-----------|------------|--------|
| `FR-265` | functional | P0 | implemented | Stage 1 fails closed on deterministic first-draft quality defects, requires exact unit-level provenance for rebuilt packets, and retains Stage 2 as an independent audit | `AC-332`–`AC-338` | CR-102 |
| `AC-332` | acceptance | P0 | implemented | Substantive `LW-009-PAIR` findings block Stage 1 | `FR-265` | CR-102 |
| `AC-333` | acceptance | P0 | implemented | `LW-026` JD-specificity findings block Stage 1 | `FR-265` | CR-102 |
| `AC-334` | acceptance | P0 | implemented | Provenance-contract v2 packets require every resume bullet and factual cover-letter sentence to cite packet claim IDs | `FR-265` | CR-102 |
| `AC-335` | acceptance | P0 | implemented | Stage 1 runs resume and cover quality checks, including bullet length and professional close | `FR-265` | CR-102 |
| `AC-336` | acceptance | P0 | implemented | Narrow defensive ownership disclaimers hard-block under `LR-032` | `FR-265` | CR-102 |
| `AC-337` | acceptance | P0 | implemented | Corrected Sony/Solace examples can enter the packet example budget by global relevance | `FR-265` | CR-102 |
| `AC-338` | acceptance | P0 | implemented | Confirmed `LW-021`, `LW-028`, and `LW-032` false-positive classes are regression-tested | `FR-265` | CR-102 |

### CR-103 ATS retrieval evidence & PDF parser QA (FR-266–FR-267)
| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source |
|---|---|---|---|---|---|---|
| `FR-266` | functional | P1 | implemented | Verification reports packet-supported ATS term coverage separately from global vocabulary gaps | `AC-339` | CR-103 |
| `FR-267` | functional | P1 | implemented | Verification reports whether required resume and cover-letter fields survive PDF text extraction | `AC-340`–`AC-341` | CR-103 |
| `AC-339` | acceptance | P1 | implemented | Receipt records each packet ATS term, claim IDs/JD items, and resume presence | `FR-266` | CR-103 |
| `AC-340` | acceptance | P1 | implemented | Missing extracted identity, contact, role, employer, date, section, greeting, or sign-off fields are reported | `FR-267` | CR-103 |
| `AC-341` | acceptance | P1 | implemented | Clean fixture reports all checked fields present | `FR-267` | CR-103 |
| `AC-342` | acceptance | P1 | implemented | ATS and parser reports remain WARN-only and do not alter mechanical verification | `NFR-008` | CR-103 |

## Non-Functional Requirements

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `NFR-001` | performance | P0 | implemented | Batch pipeline must wait 15s between jobs to avoid rate limits |
| `NFR-002` | cost | P1 | implemented | JD characters capped at 1500 for scoring to save tokens |
| `NFR-003` | security | P0 | implemented | Local-only execution; no career data leaves localhost |
| `NFR-004` | performance | P1 | implemented | Adzuna API calls capped at 10 per scout run with 3s inter-call delay to respect 25 req/min free-tier limit |
| `NFR-005` | cost | P0 | implemented | No LLM provider is called unless `_is_configured()` returns True — zero silent token waste from misconfigured providers |
| `NFR-006` | infrastructure | P1 | implemented | Zero-Trust Remote Binding — Vite client and Express server bind to `0.0.0.0` to permit authorized access across overlay networks (Tailscale) |
| `NFR-007` | cost | P0 | implemented | Cloud authoring input context per company must use a lean packet + rule digest; default path must not reload full `agent_context_pack.md` + full skill into a second independent cloud review agent per company (CR-074) |
| `NFR-008` | reliability | P1 | implemented | ATS retrieval and PDF parser checks are local, deterministic, and WARN-only |

## Security Requirements

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `SEC-001` | security | P0 | implemented | `.env` excluded from git via `.gitignore` |
| `SEC-002` | security | P0 | implemented | Third-party data source API keys (Adzuna) stored only in SQLite `profiles/api_connections` table (gitignored); never written to tracked files |
| `SEC-003` | security | P0 | implemented | No `.env` for secrets — all API keys configured via Settings UI and read from SQLite at runtime (`CR-015`) |
| `SEC-004` | security | P0 | implemented | LLM and data-source keys stored in `profiles` (`llm_settings`, `api_connections`); read in-process from `jobagent.sqlite`; never logged or written to tracked files |
| `SEC-005` | security | P0 | implemented | Secret Portable Management — Supports injecting API keys directly from environment variables (Doppler) decoupling sensitive strings from local database |
| `NFR-004` | maintainability | P0 | implemented | All pipeline behavior variables (search terms, blocklists, score threshold, freshness window) must trace to `candidate_preferences.json`; no hardcoded overrides permitted in scout or pipeline scripts |
