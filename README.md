# JobAgent (v6.0)

A locally-hosted, privacy-first, automated job scouting and application generation platform. JobAgent connects to job boards automatically, filters out noisy roles using deterministic rules, and lines up high-fit opportunities for automated matching based on your strictly verified career history.

---

## 🚀 Quick Start Guide

### 1. Installation
Ensure you have Node.js installed on your machine.
Open your terminal in the JobAgent folder and install dependencies:

```bash
npm install
```

### 2. Starting the Platform
We use a single command to spin up the entire Full-Stack system (both the React Frontend and the Express/Node Backend concurrently):

```bash
npm run dev
```

Once running, open your web browser and go to: **[http://localhost:5173](http://localhost:5173)**

---

## 🛠️ How to Use JobAgent (The Workflow)

### Step 1: Configure Your "Source of Truth"
Before scouting for jobs, you need to tell the AI who you are. Open the app and navigate to the **"My profile"** tab on the bottom left.
1. **Identity:** Fill out your name, contact info, and portfolio links. This maps directly to your future resume headers. (Auto-saves as you type).
2. **Experience:** Paste your raw career history in markdown format here. This directly edits your `data/workExperience.md` file. The AI is strictly forced to use this context so it cannot "hallucinate" fake metrics. **You must click the "Save & Sync AI" button here to persist changes.**
3. **Preferences (The Gatekeeper):** Configure your salary targets and, most importantly, your **Title and Industry Blocklists**. By default, add terms like `senior`, `director`, or `web3`. The backend scout will automatically throw away jobs containing these words, saving you time and API costs.

### Step 2: Run the Scout Automation
Navigate to the **"Sync Activity"** tab in the sidebar.
1. Click the **"Trigger Manual Sync"** button.
2. JobAgent's backend Node.js server will wake up, connect to the external job scraper database, and begin iterating through listed roles.
3. Watch the Live Terminal: The frontend polls the backend every 3 seconds. You will see colored logs appearing as the scout automatically rejects Senior roles (Yellow `WARN`) and passes mid-level "High-Fit" roles (Blue `INFO`).

### Step 3: Review the Catch
Once the background sync completes, navigate to the **"Today"** or **"All jobs"** views.
Here, you will see the interactive dashboard of every job that successfully passed your deterministic gate checks. You can select them to open the slide-out detail panel and prepare them for tracking.

---

## 📂 Where Does My Data Live?
JobAgent is a **Zero-Knowledge, Local-Only Architecture**. Your data never leaves your computer invisibly.

- **Your Settings & Logs:** Are stored purely locally in the `jobagent.sqlite` file located in the root directory.
- **Your Resume Data:** Is stored physically in `data/workExperience.md`.
- **The Raw Job Market:** Arrives via the `openpostings` database schema attached directly to our local SQLite instance.

*Note: If the application ever shows a red banner saying "Cannot connect to server", ensure your terminal hasn't crashed and `npm run dev` is still actively running!*