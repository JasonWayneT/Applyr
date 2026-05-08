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
