# Applyr — Curated Job Hunt Agent

A locally-hosted, privacy-first platform that automates the full job search lifecycle: stealth scouting across LinkedIn, BuiltIn, and company career pages → deterministic fit scoring → bespoke resume and cover letter drafting grounded in your verified work history.

Everything runs on your machine. No data leaves your desktop except the API calls you explicitly configure.

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

### 3. Install Playwright browser (for the scout engine)

```bash
npx playwright install chromium
```

### 4. Install Python dependencies

```bash
pip install -r requirements.txt
```

Then install Playwright's Python bindings:

```bash
playwright install chromium
```

### 5. Configure API keys

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

Open `.env` and add:

- **`PERPLEXITY_API_KEY`** — Used for company research. Get one at [perplexity.ai/settings/api](https://www.perplexity.ai/settings/api)
- **`GEMINI_API_KEY`** — Used for AI drafting (default provider). Get one at [aistudio.google.com](https://aistudio.google.com/app/apikey)

You can also use Claude or a local Ollama model instead — switch the provider in the app under **Profile → API or Connections**.

---

## Running the app

```bash
npm run dev
```

This starts both the React frontend (port `5173`) and the Express backend (port `3000`) together.

Open **[http://localhost:5173](http://localhost:5173)** in your browser.

---

## First-time configuration

### Set your job search criteria

Go to the **Job Search** tab. Configure:

- Target role and search terms
- Work setting (Remote / Hybrid / On-site)
- Location
- Date posted window
- Experience level filters
- Title and industry blocklists
- Minimum salary

Hit **Save**. This writes your preferences to the local database and immediately updates what the scout and pipeline will search for.

### Add your work experience

Go to **Profile → Experience**. Paste your raw work history in any format — job titles, bullet points, numbers, anything. Click **Save & Sync AI**.

The system will automatically structure it into five sections and assign stable proof codes (`ACC-NNN`, `VOC-XX`, `MET-XX`) to every claim. These codes are the anti-hallucination contract: the AI is structurally forbidden from claiming anything in a generated document that doesn't trace back to a code in this file.

### Set your identity

Go to **Profile → Profile**. Fill in your name, email, phone, LinkedIn, and portfolio links. These populate the headers of generated documents.

---

## Core workflows

### Scouting

Go to **Job Search** and trigger a scout run. The backend launches a headless Playwright browser that searches LinkedIn, BuiltIn, and other configured sources using your saved criteria. Matching roles land in **Opportunities** as `Backlog` candidates.

### Drafting assets

From the **Dashboard** or **Opportunities** view, click **Draft Assets** on any Backlog role. The pipeline:

1. Runs a final deterministic fit gate against your preferences
2. Researches the company via Perplexity
3. Drafts a tailored 1-page resume, cover letter, and interview cheat sheet — sourced only from your coded work experience
4. Streams live progress to the Scout log console

Output lands in `submissions/[company-name]/`.

### Application lifecycle

Track every role through six stages via the detail panel: `Backlog → Applied → Recruiter Screen → Core Interviews → Offer and Negotiation → Closed`. When you mark a role as Applied, the submission folder is automatically archived to `archive/submissions/`.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, TailwindCSS |
| Backend | Node.js, Express, tsx |
| Database | SQLite via better-sqlite3 |
| Scout engine | Playwright + playwright-extra stealth |
| AI drafting | Python — Gemini / Claude / Ollama (configurable) |
| Research | Perplexity API |
