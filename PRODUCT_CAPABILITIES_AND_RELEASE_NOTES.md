# Applyr — Product Capabilities & Release Notes

Welcome to the definitive product capabilities registry and release ledger for **Applyr (The Curated Job Hunt Agent)**. This document serves as the single source of truth for the system's operational architecture and product milestones.

---

## Part 1: Core System Capabilities (Today)

Applyr is a highly specialized, local-first intelligence platform designed to automate the job search lifecycle—from automated discovery and deterministic fit filtering to bespoke resume drafting, WYSIWYG visual asset editing, and application lifecycle tracking.

### 1. Automated Job Scouting & Crawling Pipeline
*   **Multi-Platform Scraping Engine:** Orchestrates automated web crawls across major networks (LinkedIn, Built In, and direct company career portals) using localized selenium/playwright tasks.
*   **Intelligent URL Backfilling:** Allows manual URL injection that automatically scrapes raw job descriptions on the fly, feeding them straight into the evaluation pipeline.
*   **Company DNA Perplexity Intelligence:** Executes targeted real-time Perplexity queries to extract company missions, problem spaces, financial status, and competitor matrices into a `Research_Packet.md` file.

### 2. Deterministic Job-Fit Scoring Engine (Stage A & Stage B)
*   **The Fast Gate (Instant Kill):** A deterministic filter that instantly rejects roles with mismatched seniority levels, solo-PM traps ("0-to-1 PM", "Founding PM"), low compensations (<$70k), or non-US based locations.
*   **Multi-Dimensional Scoring:** Evaluates JDs across four distinct vectors (Direct Leadership/Mentorship availability, Seniority Fit, Technical Execution Depth, and Transition potential) to produce a weighted score from `0` to `100`.
*   **Anchor Safeguard Room:** Validates that a role contains at least two core overlaps (Platform stability, complex migrations, security compliance, or enterprise B2B workflows) before allowing a greenlight.

### 3. Bespoke Asset Generation (The Bridge)
*   **The "Hallucination" Guard:** A cynical auditor that strictly verifies that every metric, tool, or team responsibility claimed in generated documents is 100% grounded in `data/workExperience.md` to prevent AI seniority inflation.
*   **Custom Asset Pack Compilation:** Synthesizes professional resumes, cover letters, and interview cheat sheets tailored precisely to the job description keywords using the Company DNA research.

### 4. Live Visual Document Workspace
*   **Inline Action Triggers:** Consolidates all file-level actions. Standard PDF download and visual editing triggers reside inline as side-by-side controls within each asset row.
*   **Live Side-by-Side Viewport:** Launches a dual-pane overlay when editing:
    *   **Left Pane:** Browser-native PDF preview iframe that reloads dynamically on file compile.
    *   **Right Pane:** A rich-text visual WYSIWYG editor powered by Toast UI.
*   **Background Single-File PDF Compiler:** Initiates sub-second compilation processes to write edited Markdown directly to the file system and instantly regenerate high-quality PDF binaries.
*   **Setting-Gated AI Copywriter:** Displays an LLM instruction input panel in the editor workspace if a Gemini API key is linked in Settings, enabling direct, prompt-based document rewrites.

---

## Part 2: Release Ledger

### 5.20
Applyr Release
May 11, 2026

Version 5.20, deployed on May 11, 2026

Previous
Applyr 5.19

Next
Applyr 6.0 (Planned)

New
- **Dual-Tier Local Intelligence Failover:** Redesigned `utils.py` to dynamically monitor local inference health. If the large primary model throws an Out-Of-Memory (500) exception, the engine automatically locks onto a user-defined lightweight fallback model (`gemma2:9b`) and resumes with zero pipeline lag.
- **Automatic VRAM Reclamation (Eco-Hook):** Authored `unload_local_models()` protocol and hooked it to the `finally` block of `batch_pipeline.py`. As soon as processing finishes, Python sends explicit `keep_alive: 0` signals to Ollama, immediately cleaning local GPU memory for system/gaming performance.
- **Hybrid Local-Cloud Switching:** Introduced explicit `provider_override` logic enabling tiered operations. Rejection triage runs instantly locally while delicate Drafting and Auditing functions dynamically lock to Gemini Pro, eliminating local model hallucinations.

---

### 5.19
Applyr Release
May 11, 2026

Version 5.19, hotfix deployed to local users on May 11, 2026

Previous
Applyr 5.18

Next
Applyr 6.0 (Planned)

Fixed
- **Critical Scraper Context Leak (BUG-008):** Resolved a core execution defect where sequential loops shared a single Playwright `Page` instance. Pending redirects from previous hops would asynchronously interrupt subsequent job loadings, which the system misclassified as "dead links." 
- **Redirection Chain Isolation:** The engine now allocates a fresh, isolated browser context per URL load and enforces strict destruction (`page.close()`) to end lingering network threads, ensuring high-fidelity navigation capture for multi-hop aggregators like Adzuna.

Developer
- **Data Recovery Protocol:** Authored `restore_stale_jobs.ts` to successfully pull 93 false-positively archived records from `stale_jobs` back into `jobs` table.
- **SDD compliance:** Logged `BUG-008` in known-issues registry.

---

### 5.18
Applyr Release
May 11, 2026

Version 5.18, first offered to local users on May 11, 2026

Previous
Applyr 5.17

Next
Applyr 6.0 (Planned)

Fixed
- **Scraper Navigation Interruption Loop (BUG-007):** Resolved an issue where automated client/server redirects (common with expired Adzuna links) interrupted the Playwright navigation cycle, trapping jobs in an infinite `New` processing loop. Dead links are now caught, automatically archived in `stale_jobs`, and removed from the primary queue.

Developer
- **SDD compliance:** Registered `BUG-007` in `traceability-matrix.md` and finalized resolution state in known-issues log.

---

### 5.17
Applyr Release
May 9, 2026

Version 5.17, first offered to local users on May 9, 2026

Previous
Applyr 5.16

Next
Applyr 6.0 (Planned)

New
- **Job Funnel Expansion — 7 Active Sources (CR-004, FR-052):** Added three new job sources to the scout pipeline: Himalayas (remote-focused), The Muse (culture-forward listings), and Adzuna (aggregates thousands of boards). Phase 1 now runs 7 parallel API sources simultaneously, significantly expanding the top of the funnel without additional token spend.
- **Adzuna Optional Connection (FR-054, FR-055, NFR-004):** Adzuna is configured entirely from the UI. If no key is provided the source is silently skipped. A built-in rate guard caps usage at 10 calls per scout run with a 3-second inter-call delay, keeping usage comfortably inside the free tier (25 req/min, 250 req/day).
- **LLM Provider Fallback Chain (CR-006, FR-059, FR-060):** The pipeline now supports automatic multi-provider fallback. The primary provider is tried first; on a non-rate-limit error it falls through to the next configured provider in order (Gemini → Claude → Local → Perplexity). Rate limit errors retry within the same provider. If no providers are configured, an actionable warning is logged and no API call is attempted.
- **Perplexity as Full LLM Provider (FR-061):** Perplexity `sonar-pro` is now a first-class pipeline provider alongside Gemini, Claude, and Local. When a Perplexity key is configured, the research engine uses it first for company intelligence (native web retrieval), then falls back to the primary LLM on failure. No Perplexity key = no Perplexity calls, ever.
- **Four-Card LLM Provider UI (FR-062):** The "API or Connections" settings tab is redesigned into four independent provider cards — Gemini, Claude, Local LLM, and Perplexity. Each card has an always-visible key/URL field, a Connected badge when credentials are present, and a "Set Primary / Primary ✓" toggle. Configure any combination; the pipeline uses whatever is connected.

Fixed
- **RemoteOK Tag Format Bug:** RemoteOK slugs require hyphens (`product-manager`), not URL-encoded spaces (`product+manager`). Fixed tag generation to use the correct format.
- **Remotive Category Lock:** Remotive was locked to a single category search. Fixed to iterate all `SEARCH_TERMS` with per-term dedup via a shared `seenUrls` Set.
- **WWR Single Feed:** We Work Remotely was fetching only one RSS feed. Fixed to pull both the product and management/finance feeds with shared extraction logic.
- **Import-Time Gemini Crash:** `utils.py` instantiated a global `genai.Client` at module import time, causing an immediate crash if `GEMINI_API_KEY` was unset. Removed — clients are now created lazily inside `_call_gemini()` only when that provider is actually invoked.

Changed
- **Role-Aware Muse Routing (FR-056):** The Muse source now derives its category from `TARGET_ROLE` via `getTheMuseCategory()` rather than a hardcoded `"Product"` category. Users targeting Engineering, Design, or Data roles get correct category routing automatically.
- **PM Search Term Expansion (FR-053):** `materializeJobSearchPrefs()` now automatically appends Product Owner, Technical Product Manager, Platform Product Manager, and Digital Product Manager to the search terms when the target role includes "Product Manager" — without hardcoding these anywhere in scout scripts.
- **Perplexity Moved from Data Sources to LLM Providers (SEC-004):** The Perplexity API key is now stored in `llm_settings` alongside Gemini and Claude, not in `api_connections`. Existing keys are transparently migrated on first Settings load.
- **`provider` → `primaryProvider` (FR-063):** The LLM settings field renamed from `provider` to `primaryProvider` in both the frontend and Python. Backward compatibility is maintained — old DB records with `"provider"` continue to work automatically.

Developer
- **`_is_configured()` + `_get_configured_providers()` in `utils.py` (FR-059):** Provider guard functions ensure no LLM API is ever called without a valid key. Configured providers are returned in call order: primary first, then the fixed fallback sequence.
- **`buildPythonEnv()` updated (FR-058, SEC-004):** Reads `perplexityApiKey` from `llm_settings`; reads Adzuna keys from `api_connections`. All LLM keys injected at Python spawn time via environment variables — never written to disk.
- **SDD compliance:** CR-004, CR-005, and CR-006 documents created. Requirements registry updated with FR-052 through FR-063, NFR-005, and SEC-004.

---

### 5.16
Applyr Release
May 8, 2026

Version 5.16, first offered to local users on May 8, 2026

Previous
Applyr 5.15

Next
Applyr 6.0 (Planned)

New
- **Unified Job Search Settings Panel (CR-003, FR-046, FR-047):** Collapsed four disconnected preference islands into a single canonical control surface under a renamed "Job Search" sidebar tab. A primary card covers Target Role, Work Setting, Location, Date Posted, and Experience Level. A secondary card covers Title Blocklist, Industry Blocklist, and Minimum Salary. Every field saved here now actually governs every scout run.
- **Live Settings Materialization Pipeline (FR-048, ADR-005):** Saving Job Search settings writes to `profiles/job_search` in SQLite and immediately materializes `data/candidate_preferences.json` server-side. Python pipeline scripts read only the JSON file — the entire preference chain is now end-to-end live with zero manual file editing required.
- **Dynamic Scout URL Generation (FR-049):** `scout_local.ts` now builds all search URLs at runtime from `candidate_preferences.json` — LinkedIn geo IDs, BuiltIn city/state slugs, RemoteOK tag arrays, search terms, and the freshness window are all derived from user settings. No hardcoded URLs remain.
- **Generic ACC-ID Codification Engine:** Rewrote `codifyExperienceAndAssignIDs()` to use a dynamic employer Map rather than hardcoded per-company seed values. Any number of `### 5.N` experience sections are supported; each section gets IDs in the range `N×100+1` to `(N+1)×100` automatically.
- **Experience Tab Onboarding Flow (FR-050, FR-051):** The Experience tab now branches on file state. An empty or uninitialized file shows a structured onboarding card explaining the VOC/MET/ACC proof-code system before the user pastes anything. A populated file shows a live codification status bar with real-time ACC/VOC/MET count pills and a collapsible edit guide covering the three safe edit patterns: Minor Edit, New Claim, and Retire.
- **Premium Settings Modal (FR-041):** Migrated all app configuration from a static Profile sub-tab into a full-screen backdrop-blur overlay with Claude-style dual-pane navigation. Left pane: vertically stacked tabs (General, Account, Privacy, Billing, Usage, Capabilities, Connectors, LLM Engine). Right pane: dynamic scrolling workspace. LLM provider selection and API key management now live here.

Changed
- **Sidebar Label:** "Scout" renamed to "Job Search" to reflect that the tab now controls all search criteria, not just crawl scheduling.
- **Profile Tab Cleanup:** Removed the "Preferences" sub-tab from the Profile page entirely; those settings now live in the unified Job Search panel.
- **Pipeline Score Threshold:** Hardcoded `score < 72` filter in `batch_pipeline.py` replaced with `MIN_FIT_SCORE` read from `candidate_preferences.json`, making the pass threshold user-configurable.

---

### 5.15
Applyr Release
May 8, 2026

Version 5.15, first offered to local users on May 8, 2026

Previous
Applyr 5.14

Next
Applyr 6.0 (Planned)

New
- **Direct Manual Asset Drafting Triggers (FR-045, AC-046):** Integrated an inline, premium "Draft Assets" manual trigger button directly onto matched role cards that are in "Pending Assets" state. This gives users absolute, granular control to initiate localized single-role background evaluations and resume/cover letter compilations instantly on demand.
- **Background Single-Job Drafting Pipeline (FR-045, AC-046):** Built a dedicated POST `/api/jobs/:id/draft` server endpoint that triggers single-mode batch execution, feeds real-time stdout and stderr logs straight to the Scout page terminal, and dynamically updates system status.

---

### 5.14
Applyr Release
May 8, 2026

Version 5.14, first offered to local users on May 8, 2026

Previous
Applyr 5.13

Next
Applyr 6.0 (Planned)

New
- **Pulsing Active Process Log Console:** Appended a real-time pulsing `ACTIVE` terminal line to the bottom of the Scout page's Log Console. When the background system is crawling feeds or synthesizing assets, the active item is shown natively at the bottom of the log stream, providing continuous visibility.
- **Drawer Active Task Indicators:** Embedded a glowing active indicator at the top of the details panel's log drawer. If the background scouter is actively processing assets for the selected company, a glowing green `ACTIVE` log line is shown to make current pipeline executions instantly transparent.

---

### 5.13
Applyr Release
May 8, 2026

Version 5.13, first offered to local users on May 8, 2026

Previous
Applyr 5.12

Next
Applyr 6.0 (Planned)

New
- **Interactive Pipeline Process Logs (FR-045, AC-046):** Built an inline, monospace background log console inside the `JobDetailPanel` drawer. It dynamically queries the database for any crawling, gate evaluation, and asset synthesis logs matching the selected opportunity's company name. This provides complete visibility and background transparency for roles currently in the "Pending Assets" queue (such as *Vitestro*).

Changed
- **Standardized Pipeline Labels & Badges:** Extended the dynamic *"Pending Assets"* fallback to the Scout page (`SyncActivityView.tsx`) to guarantee label consistency across the app. Jobs in backlog missing assets are now cleanly labeled as *"Pending Assets"* with a neutral amber look instead of being labeled as *"Ready to Apply"*.

---

### 5.12
Applyr Release
May 8, 2026

Version 5.12, first offered to local users on May 8, 2026

Previous
Applyr 5.11

Next
Applyr 6.0 (Planned)

Fixed
- **Strict Backlog Asset Readiness Verification (FR-045, AC-046):** Fixed a logical bug where backlog jobs with missing PDF assets were incorrectly marked as *"Ready to Apply"* with green buttons on the Opportunities board. Now, they dynamically render with a neutral grey **"Pending Assets"** status badge and a standard **"Details"** button, switching to the green **"Apply Now"** button only after their compiled assets become available.
- **Accurate Dashboard & Sidebar Pipeline Metrics:** Hardened Sidebar badge counts and Dashboard progress charts to only include backlog opportunities that have completed asset generation, keeping pending-asset roles cleanly segregated in the background.

---

### 5.11
Applyr Release
May 8, 2026

Version 5.11, first offered to local users on May 8, 2026

Previous
Applyr 5.10

Next
Applyr 6.0 (Planned)

Changed
- **Unified "Opportunities" Branding Refactor (FR-045, AC-046):** Fully re-labeled the central application-tracking vertical to "Opportunities" across the entire user experience. This includes renaming sidebar navigation tags, main page headings, notifications routing callbacks, and active lists inside `TodayView.tsx`, establishing a far more professional, premium, and lifelike terminology.

---

### 5.10
Applyr Release
May 8, 2026

Version 5.10, first offered to local users on May 8, 2026

Previous
Applyr 5.9

Next
Applyr 6.0 (Planned)

New
- **First-Class Settings Panel Tab (FR-041, AC-042):** Transformed Settings from a pop-up modal to a first-class page/tab rendered directly inside the main workspace's right panel. It features a full-panel 2-column layout with vertical tab navigation, fully integrating all 5 subsections (Profile, Job Preferences, Experience, API or Connections, Analytics).
- **Sage-and-Cream Premium Light Styling:** Completely replaced legacy dark mode grays and blacks (`#121212` and `#181818`) with the premium Applyr light theme color tokens (`bg-surface-container-lowest` pure white cards, `bg-surface-container-low` cream text inputs, and charcoal text), creating a beautifully unified first impression.

Changed
- **Direct Sidebar Navigation Routing (FR-041):** Added "Settings" directly into the main sidebar's icon navigation, allowing instant single-click access. Clicking "Settings" inside the lower-left profile menu also automatically redirects the active tab to the main Settings page.

---

### 5.9
Applyr Release
May 8, 2026

Version 5.9, first offered to local users on May 8, 2026

Previous
Applyr 5.8

Next
Applyr 6.0 (Planned)

Fixed
- **Robust Company Folder Resolution (FR-045, AC-046):** Integrated a dynamic `resolveCompanyFolder()` path-compatibility helper in `server/index.ts` to solve file/folder slug mismatches caused by trailing underscores or different spacing (e.g., `'Cisco_Systems_Inc_'`), instantly restoring the visibility of compiled PDF assets on the Dashboard and All Jobs review panes.
- **Background URL Backfill Execution (FR-042):** Updated the background scouter orchestrator (`server/scout.ts`) to target the correct path `scripts/archive/backfill_urls.ts` for missing URL crawls, eliminating module-not-found background execution logs.

Changed
- **Dashboard Ready to Apply Filter Integrity (FR-045, AC-046):** Hardened TodayView and Sidebar indicators to count and display only `'Backlog'` status jobs (which have fully ready compiled assets) under "Ready to Apply", keeping jobs with `'New'` or `'Drafted'` pending states in the background.
- **Friendly "Ready to Apply" Notification Labels (FR-045, AC-046):** Re-mapped the notification panel backlog text to read friendly `"matched roles ready to apply"` instead of `"backlog"`.
- **Scout Matched Roles Layout Correction (FR-045, AC-046):** Fixed inverted status badge labels in the active matches list on the Scout page, mapping `'Backlog'` status to a green **Ready to Apply** badge and `'Drafted'` to an amber **Pending Assets** badge.
- **Action Button Copy Streamlining:** Re-labeled the button for backlog items from `"Review"` to `"Apply Now"` inside the All Jobs grid, removing work-like chore implications and inviting immediate submission.

---

### 5.8
Applyr Release
May 8, 2026

Version 5.8, first offered to local users on May 8, 2026

Previous
Applyr 5.7

Next
Applyr 6.0 (Planned)

New
- **Hybrid Scouting Active Filters Panel (FR-042, AC-043):** Deployed a premium, high-impact scouter parameters control card at the very top of the Scouting dashboard, containing live editable inputs for Target Job Title, option chips for Job Type (Remote, Hybrid, On-site), and a locked location indicator. All parameters auto-save to SQLite with beautiful debounced status indicators.
- **Experience Level Multi-Select Dropdown Filter (FR-044, AC-045):** Implemented a high-fidelity dropdown component containing multi-select experience options (Internship, Entry Level, Junior, Mid Level, Senior, Expert) with an immediate clear action. The selected filter values seamlessly persist in real-time to SQLite scouter preferences.
- **Isolated Portfolio and GitHub Fields (FR-043, AC-044):** Fully separated Portfolio and GitHub link text inputs inside the Profile settings sub-tab, enabling structured, isolated data collection instead of combined values.
- **Master Experience Rich Text Context Editor:** Embedded a direct master markdown textarea context editor inside the settings modal's new Experience tab, complete with a "Save & Sync AI" action button to write to `workExperience.md`.

Changed
- **Dashboard Opportunity Visibility (FR-045, AC-046):** Made all newly matched and backlog jobs show up instantly on the TodayView dashboard as "Pending" while their PDF assets are being drafted, preventing them from appearing lost before compilation finishes.
- **Friendly Backlog Notifications (FR-045, AC-046):** Replaced the confusing "need review" backlog alerts with friendly "matched roles in backlog ready to apply" notifications, fully eliminating chore-like wording.
- **Streamlined Sidebar Layout:** Completely eliminated redundant links (Personalization, Profile) from the lower-left sidebar menu, routing settings workflow entirely through the unified Claude-style Settings Modal.
- **Vertical 5-Tab Modal Restructuring:** Restructured Settings Modal sidebar navigation into five streamlined categories: Profile, Job Preferences, Experience, API or Connections, and Analytics.

---

### 5.7

Next
Applyr 6.0 (Planned)

New
- **Premium Claude-Style Overlay Settings Modal (FR-041, AC-042):** Designed and deployed a stunning, high-fidelity settings room overlay mimicking Anthropic Claude's layout. It includes a responsive 2-column sidebar navigation with 8 fully custom settings sub-tabs (General, Account, Privacy, Billing, Usage, Capabilities, Connectors, LLM Engine).
- **Interactive Usage Limit Indicators (FR-041):** Integrated dynamic session and weekly model progress bars (e.g. 4% session usage, 25% weekly limits, daily Selenium routine runs tracker), alongside a functional "Extra Usage" toggle control.
- **Centralized LLM Engine Configuration Tab:** Migrated the dynamic Multi-LLM card selector and cloud/local API keys settings directly into the modal for seamless, unified setup.

Changed
- **Uncluttered Profile View Tab:** Centralized LLM configuration under the dynamic SettingsModal overlay triggered directly from the lower-left sidebar profile menu.

---

### 5.6
Applyr Release
May 8, 2026

Version 5.6, first offered to local users on May 8, 2026

Previous
Applyr 5.5

Next
Applyr 6.0 (Planned)

New
- **Multi-LLM Provider Support (FR-040, AC-041):** Added fully dynamic Multi-LLM provider selection directly inside the Settings tab of My Profile. Users can select between Google Gemini (Cloud), Anthropic Claude (Cloud), and Local LLM (Ollama / LM Studio) with custom API keys and base URL configurations.
- **Dynamic LLM Routing Engine:** Updated the python backend calling utility (`scripts/utils.py:call_llm()`) to dynamically retrieve LLM configurations from the local SQLite database and route requests in real-time. It supports standard OpenAI-compatible endpoints as well as Ollama's direct `/api/chat` native API for maximum local resiliency.
- **ChatGPT-Style Lower-Left Profile Menu:** Designed and implemented a sleek, stateful user profile card at the bottom of the sidebar displaying name/avatar initials, user plan, and a chevron toggle. Clicking the card opens an interactive popup menu with direct links to Preferences, Identity, and Settings tabs, aligning perfectly with modern ChatGPT UI aesthetics.

Changed
- **Header Cleanup:** Streamlined the main layout by completely removing the legacy top-right settings cog button, unifying settings navigation under the new lower-left sidebar menu.

---

### 5.5
Applyr Release
May 7, 2026

Version 5.5, first offered to local users on May 7, 2026

Previous
Applyr 5.4

Next
Applyr 6.0 (Planned)

New
- **Auto-Merging & Duplicate Resolution Utility:** Implemented a background duplicate audit and resolution strategy across active and archived submission directories. It resolved five major directory collisions (Allstate, Expel, GE Healthcare, PeopleGrove, and Ryan) by analyzing SQLite database status, merging files to preserve the largest and most complete copies, and storing safe pre-deletion backups in `scratch/folder_backups/`.
- **Peach Asset Customization & Tailoring:** Generated and compiled high-fidelity, compliant PDF assets (Resume and Cover Letter) tailored for Peach's modern API-first loan management system-of-record, perfectly aligning technical ingestion experience with corporate compliance.

Fixed
- **Multi-Folder OS Collisions:** Resolved duplicate active and archived submission folder states that previously threw Windows `fs.renameSync` EEXIST errors when users updated job statuses in the UI, fully unblocking the status update workflow.

Changed
- **Bulk Application Clearing:** Automatically cleared and archived all remaining folders in the active `submissions/` directory (Carefull, SpotOn, and Bellese) while updating their database statuses to `Applied`.

---

### 5.4
Applyr Release
May 7, 2026

Version 5.4, first offered to local users on May 7, 2026

Previous
Applyr 5.3

Next
Applyr 6.0 (Planned)

New
- **Job Name & Company on Editor Workspace:** Renders the active job title and target company inline inside the WYSIWYG PDF editor's top bar (e.g. `Editing Resume.md for Secureframe (Product Manager – Platform Trust & Security)`), providing clear candidate context during edits.
- **Line-by-Line Section Stripper & Contact Normalizer:** Refactored the Style Compliance Guard (`style_compliance_guard.py`) to process documents line-by-line rather than using complex multiline regexes. This completely prevents vertical whitespace deletion, line merging, and format corruption while aggressively stripping skills/expertise blocks and formatting contact lines.

Fixed
- **Tagline Hyphenation & Corrupted Characters:** Fixed an empty string replacement bug that caused hyphens to be inserted between every character in the tagline block during compilation. Unescaped backslash parentheses `\( \)` are now successfully converted to professional round brackets.

---

### 5.3
Applyr Release
May 7, 2026

Version 5.3, first offered to local users on May 7, 2026

Previous
Applyr 5.2

Next
Applyr 5.4

New
- **Triple Redundancy Style Compliance Guard (FR-036):** Introduced a state-of-the-art formatting auditor and auto-correction script (`style_compliance_guard.py`). It guarantees perfect HTML single-page resume structures across three distinct checkpoints: immediate post-generation cleanup, pre-compilation text capacity compaction (automatic company bullet trimming and dynamic inline font-size scaling), and save-time interception.

Fixed
- **AI Rewrite Log Pollution & Escaped Characters:** Completely eliminated the `[LLM] Calling...` prefix from ruining saved documents by redirecting all Python utility and LLM logging to `sys.stderr`. Updated the system prompt in `ai_rewrite.py` to prevent Gemini from converting HTML style elements to raw Markdown headings or injecting backslash-escaped characters.

Developer
- **Visual Compliance Enforcement on Save:** Connected the compliance guard directly to the Express server's file PUT route and Python's drafting engine, ensuring that all manual edits, AI rewrites, or background pipeline compilations are automatically verified and polished for single-page style compliance.

### 5.2
Applyr Release
May 6, 2026

Version 5.2, first offered to local users on May 6, 2026

Previous
Applyr 5.1

Next
Applyr 6.0 (Planned)

New
- **End-to-End Background Sync (FR-035):** Fully automated the background sync pipeline. After scouting completes, the system now automatically scrapes full descriptions (`scrape_new_jobs.ts`), evaluates fit via the Gemini fit engine (`batch_pipeline.py`), and drafts tailored resumes/cover letters directly in the background. Passed jobs instantly appear on the dashboard under "Ready to Apply"!

Fixed
- **Gatekeeper Queue Cleanup:** Prevented "New" status clutter and stat inflation by registering non-matching or low-scoring scouted jobs in the `stale_jobs` table (to prevent re-crawling) and then completely deleting them from the primary `jobs` table.

Developer
- **Integrated Database Control in Batch Pipeline:** Modified `batch_pipeline.py` to connect directly to `jobagent.sqlite` using standard python `sqlite3` to dynamically fetch job status for idempotent skips, and write back evaluation results (Backlog/Closed status, score, fit summary) automatically.

### 5.1
Applyr Release
May 6, 2026

Version 5.1, first offered to local users on May 6, 2026

Previous
Applyr 5.0

Next
Applyr 6.0 (Planned)

New
- **Job Pipeline Paradigm:** Introduced the Job Pipeline Paradigm Split! Pipeline jobs (unreviewed and reviewed ready-to-apply jobs) are now completely segmented from submitted active applications.
- **Dynamic Gating:** Added a dynamic status flow where `New` (unseen) jobs feature a prominent green badge to differentiate them from `Backlog` (seen) jobs.

Fixed
- **BUG-003 (Asset Dynamic Gate):** Prevented "Ready to Apply" from showing when no PDF assets exist by checking folder contents dynamically on the Express server (`has_assets` check).
- **BUG-006 (Inflated Stat Card):** Fixed the inflated "Total Active" stat card count on the dashboard. It now accurately reflects submitted applications under "Submitted" instead of backlog/pipeline.

Changed
- **Dashboard Separation:** The dashboard layout is redesigned into two clear list groupings: "Ready to Apply" (pre-submission) and "Active Applications" (waiting for contact).
- **Drafting Muting:** Muted `Drafted` status labels to "Drafting..." and hid them from primary dashboard sections to prevent clutter.
- **Jobs Tab Filters:** Re-aligned AllJobsView tab filters to: Backlog, Active, Interviewing, Closed.

Developer
- **100% SDD Compliance:** Achieved 100% SDD (Spec Driven Development) compliance by backfilling 14 missing matrix rows in `traceability-matrix.md` and adding `docs/spec/` requirements `FR-030` to `FR-034`.
- **Systematic Governance:** Added a formal agent rule in `AGENTS.md` enforcing future SDD compliance and GitHub Release Notes.

---
Applyr Release
May 6, 2026

Version 5.0, first offered to local users on May 6, 2026

Previous
Applyr 4.0

Next
Applyr 6.0 (Planned)

New
We have integrated a stunning side-by-side **Visual Document Workspace**! You can now view generated PDFs natively in an inline iframe and edit their Markdown sources directly in-browser using a Toast UI WYSIWYG editor. No more switching back and forth between Applyr and your IDE to polish your application assets.

We've added a **Setting-Gated AI Prompt Panel**! When a Gemini API key is linked in Settings, you can now issue direct, prompt-based instruction to the GenAI client to automatically rewrite sections or documents.

![Applyr v5.0 Inline Actions Layout](file:///C:/Users/Jason/.gemini/antigravity/brain/e6816052-1f6c-47f9-aae1-f3b2f3b7886a/.system_generated/click_feedback/click_feedback_1778100680612.png)

Fixed
Resolved Windows-specific parameter escaping issues on CLI calls. The Express server now processes AI rewrites using secure temporary files under the `scratch/` directory to fully eliminate CLI length limits and character escaping bugs.

Changed
The application detail panel now features a completely streamlined **Inline Actions Layout**. The separate "Edit CoverLetter" and "Edit Resume" buttons have been replaced with beautiful, side-by-side **Edit (pencil icon)** and **Download** buttons directly inline on each PDF asset card.

Developer
Targeted single-file background compiler is now live. Rather than executing heavy batch generation scripts, the system now runs `scripts/compile_single.py` to regenerate PDFs in under 500ms when a save is completed.

---

### 4.0
Applyr Release
April 15, 2026

Version 4.0, first offered to local users on April 15, 2026

Previous
Applyr 3.0

Next
Applyr 5.0

New
Introduced the local web portal containing backlog metrics, active pipelines, and individual job detail panels. Added a dedicated view to adjust API keys, base career models, and work experience parameters in SQLite.

Changed
Migrated from CLI automation execution to a full local single-page web dashboard using an Express backend server and a Vite React frontend SPA client.

---

### 3.0
Applyr Release
March 12, 2026

Version 3.0, first offered to local users on March 12, 2026

Previous
Applyr 2.0

Next
Applyr 4.0

New
Deployed a cynical verification auditing "Hallucination Guard" to strictly check that every claim made in generated documents is anchored in the baseline `workExperience.md` file to prevent AI seniority inflation.

Built initial Markdown-to-PDF conversion pipelines utilizing standard system packages to package draft files.

---

### 2.0
Applyr Release
February 18, 2026

Version 2.0, first offered to local users on February 18, 2026

Previous
Applyr 1.0

Next
Applyr 3.0

New
Implemented the full multi-dimensional Job-Fit Decision Engine evaluating jobs against Jason's B2B Platform experience. Scripted quick-rejection Stage A filter blocklists to eliminate solo-PM, founding PM, low salary, or international roles.

---

### 1.0
Applyr Release
January 10, 2026

Version 1.0, first offered to local users on January 10, 2026

Next
Applyr 2.0

New
Initial system release establishing automated job discovery and parsing crawls of LinkedIn and Built In. Structured extraction of raw text payloads from JDs.

---

## Part 3: Templates & Guidelines
To maintain consistency in future product updates, refer to the **[Release Notes Template](file:///c:/Users/Jason/Desktop/Jason/Resource/Code%20Projects/JobAgent/docs/RELEASE_NOTES_TEMPLATE.md)** inside your `docs/` folder. Copy and paste its structure when adding new release logs.
