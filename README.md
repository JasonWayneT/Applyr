# JobAgent (v7.0)

A locally-hosted, privacy-first, automated job scouting and application generation platform. JobAgent uses stealth headless browsing to scout opportunities across the web, applies deterministic filters grounded in your exact preferences, and automatically drafts bespoke, un-hallucinated application assets (Resumes & Cover Letters) ready for submission.

---

## 🛠️ Technical Stack & Architecture

JobAgent is built entirely locally to ensure maximum data privacy and zero API payload risks while browsing external job sites.

*   **Frontend:** React (TypeScript) + Vite, heavily styled with TailwindCSS (using an internal glassmorphism design system).
*   **Backend API:** Node.js (Express) server bridging the gap between the UI and local file operations.
*   **Database:** `better-sqlite3` acting as the lightning-fast, local-first source of truth (`jobagent.sqlite`).
*   **Scouting Engine:** Playwright embedded via Node (`scripts/scout_local.ts`) offering highly stealthy, randomized-DOM-interaction browser automation for platforms like LinkedIn and Built In.
*   **AI Drafting Engine:** Python (`scripts/batch_pipeline.py` & `scripts/drafting_engine.py`) hooked into the LLM of choice to generate deterministic PDFs using `markdown-pdf`. Real-time progress is streamed backwards to the UI using **Server-Sent Events (SSE)**.
*   **Physical Inbox File System:** JobAgent ties its software state directly to your OS file tree. The `submissions/` directory acts as an Inbox Zero queue.

---

## 🚀 Quick Start Guide

### 1. Installation
Ensure you have **Node.js** and **Python 3.10+** installed on your machine.
Open your terminal in the JobAgent folder and install dependencies:

```bash
# Install Node dependencies
npm install

# Install Playwright browsers (for the Scout engine)
npx playwright install chromium
```

### 2. Starting the Platform
You can spin up the entire Full-Stack system (both the React Frontend on port `5173` and the Express Backend on port `3000`) using one command:

```bash
npm run dev
```

Once running, open your web browser and go to: **[http://localhost:5173](http://localhost:5173)**

---

## 🧭 The Core Workflows

### 1. Define Your Persona ("The Source of Truth")
JobAgent doesn't just guess what job you want. You dictate the rules using standard configuration files:
*   **Profile Interface (The UI):** Navigate to the **"My Profile"** tab. Update your basic identity placeholders, salary preferences, and blocklists (e.g. `Senior`, `Web3`).
*   **`data/workExperience.md`:** This is the sacred text. Paste your raw career history here. The AI is structurally forbidden to claim any software, metric, or experience not explicitly listed in this file. 
*   **`data/candidate_preferences.json`:** The JSON routing engine. If you want to switch from hunting for "Product Manager" roles to "Account Executive" roles, you change the boolean strings in this file. JobAgent's crawler and fit engine will dynamically swap to evaluating for the new persona.

### 2. Live Stealth Scouting
1. Go to the **"Find new jobs"** tab.
2. Select **"Live Scout"** and hit Start.
3. The backend will trigger a headless Playwright instance that will execute human-mimicking search queries across LinkedIn. The scout will match the fetched job descriptions against your `candidate_preferences.json`, instantly dropping roles that violate your blocklists or experience requirements.
4. Accepted roles are pushed into the local SQLite database as `Backlog` candidates.

### 3. Pipeline Generation (The AI Engine)
1. In the **"Find new jobs"**, or right from the Dashboard, you can paste in a specific URL or JD, or run against your newly scouted Backlog.
2. The UI streams Server-Sent Events (SSE) live from the Python drafting engine as it:
   *   Passes the job through the final `job_fit_engine.md` deterministic gate.
   *   Researches the company (via Perplexity or similar scripts).
   *   Drafts a 1-page Resume tailored *only* using your `workExperience.md` data.
   *   Drafts a Cover Letter and an Interview Cheat Sheet.
3. Upon completion, these markdown files are finalized into PDFs securely within your IDE.

### 4. The "Physical Inbox" Submission Strategy
JobAgent is designed to prevent "Desktop Clutter Anxiety".
*   **The Active State:** All jobs currently in your `Backlog` have their assets located in `submissions/[Company Name]`. When you apply for a job, you just open that one folder.
*   **The Archive Shift:** When you click the massive **"🚀 Open Application URL"** button in the dashboard, you submit your documents online. Afterwards, you click **"Mark as Applied"** in the app.
*   **OS-Level Cleanup:** The backend server intercepts the `Applied` status flag and physically triggers an OS-level `fs.renameSync()`, instantly migrating the company's folder from `submissions/` to `archive/submissions/`. Your active workspace immediately reaches Inbox Zero. 

---

## 🚦 Application State Diagram

The pipeline tracks a clean 6-stage lifecycle, synced directly to the dashboard's Analytics widgets:
1. **Backlog** (Active physical workspace)
2. **Applied** (Archived physical workspace)
3. **Recruiter Screen**
4. **Core Interviews**
5. **Offer and Negotiation**
6. **Closed** 

Any changes executed through the Web UI drop-up menus will instantly push to the internal SQLite store and mirror locally correctly on disk.