# JobAgent: The Educational Architecture & PRD

Welcome to the JobAgent codebase! This document is both a Product Requirements Document (PRD) and an educational guide. If you are reading this to learn how full-stack applications are built, this guide explains not just *what* we built, but *why* we chose the specific tools we did, explained in simple terms.

---

## 1. The Core Philosophy: Solving the "Job Hunt Grind"

Job hunting usually involves looking at hundreds of jobs, figuring out if they fit your specific experience, and then writing a unique resume and cover letter for each one. This is exhausting. 

**The Goal of JobAgent:** Create an automated, local "robot" that runs on your personal computer. It talks to job boards to find new roles, instantly filters out the garbage using strict math/text rules (so we don't waste time or money on AI), and only passes the "perfect fit" jobs to a localized AI to write your application materials.

We use two key analogies in this platform:
1.  **The Firehose:** The raw, unfiltered data of thousands of job postings coming from the internet.
2.  **The Source of Truth:** Your actual, grounded work experience (saved in a local file) that the AI is strictly forced to use, so it doesn't "hallucinate" or lie about your skills.

---

## 2. The Big Picture Architecture

JobAgent is a **Full-Stack Web Application**. This means it is divided into two main hemispheres that talk to each other:

### Hemisphere A: The Frontend (The Face)
This is what you see and click on. It lives in your web browser. 
- It shows you the jobs.
- It provides a dashboard to watch the background robot work.
- It provides a "My Profile" page for you to update your settings.

### Hemisphere B: The Backend (The Brain)
This is the invisible engine running behind the scenes on your computer.
- It connects to databases.
- It runs the scheduled "scout" script that actually looks at thousands of jobs.
- It hosts the "API" (Application Programming Interface), which is basically a set of mailboxes the Frontend can send requests to (e.g., "Hey Backend, give me the latest logs!").

---

## 3. The Technology Stack: What We Chose & Why

Here is every technology used in JobAgent, and exactly why it was chosen over the alternatives.

### 3.1 The Frontend Tech
*   **React:** React is a JavaScript library for building user interfaces. Instead of building one giant webpage, React lets us build "Components" (like Lego blocks) — a sidebar, a job card, a terminal log screen — and assemble them. It is unmatched for complex, state-heavy interfaces.
*   **Vite:** In modern web development, you need a tool to bundle all your code together and serve it to your browser fast during development. Vite is the fastest bundler available today. It makes our local development lightning fast.
*   **Tailwind CSS:** Normally, styling a website involves writing hundreds of lines of complex CSS code in separate files. Tailwind lets us style elements directly inside our React code using short utilities (like `bg-blue-500` for a blue background). It is chosen for rapid iteration.
*   **TypeScript:** Standard JavaScript lets you pass any data anywhere, which causes hidden bugs. TypeScript forces us to define the "shape" of our data (e.g., "A Job always has a title and a URL"). If we write code that breaks that shape, it warns us before we even run the app.

### 3.2 The Backend Tech
*   **Node.js & Express:** Node lets us run JavaScript on our computer (outside the browser). Express is a tiny framework that lets us set up our Backend server in just 10 lines of code. It listens for requests from the Frontend and sends back data.
*   **SQLite (via better-sqlite3):** 
    *   *What is it?* Most databases (like Postgres or MySQL) require you to install heavy background services on your computer, or host them in the cloud. SQLite is entirely different. The entire database is just a single local file (`jobagent.sqlite`) living right next to our code.
    *   *Why we chose it:* It is lightning fast, requires zero setup, and perfectly matches our "Local Privacy First" philosophy. Your data never leaves your hard drive. It also allows us to cleanly read from other local databases (like the separate scraper database).

---

## 4. Feature Deep Dive: How the Core Works

### 4.1 The Background Scout Engine (`server/scout.ts`)
This is the heart of automation. When you click "Sync", this script wakes up.
1.  **Reading the Firehose:** It connects to a massive, raw database of scraped job postings.
2.  **The Deterministic Gate:** Before we ever use expensive AI, we use simple math/text checks. The scout pulls a list of "Blocked Words" (like "Senior", "Director", "Crypto"). If a job title has those words, it is instantly thrown in the trash. This saves massive amounts of time and AI API costs.
3.  **Logging:** Every time it throws a job away or keeps one, it writes a line to an `activity_log` table in our SQLite database.

### 4.2 The "My Profile" Hub (`src/pages/ProfileView.tsx`)
This is where the user controls the platform.
*   **Settings Persistence:** Through the UI, users type their blocklists. React detects the keystrokes, waits 1 second to make sure they are done typing (called "debouncing"), and sends the new list to the Express Backend to save in SQLite.
*   **The Markdown Editor:** The platform needs your history to write resumes. We built a direct text editor that lets the user edit `workExperience.md` from the UI. When they click "Save", the Express backend overwrites the physical file on the hard drive. 

### 4.3 The Visibility Dashboard (`src/pages/SyncActivityView.tsx`)
If the scout runs in the background, the user needs to know what it is doing.
*   **Real-Time Polling:** Every 3 seconds, the Frontend asks the Backend: "Do you have any new logs?"
*   If new logs exist, React adds them to a fake "Terminal" window, and automatically scrolls to the bottom so the user can watch the robot work in real-time.

---

## 5. The Journey of a Job Posting (Step-by-Step Data Flow)

To understand how it all ties together, follow a single job as it moves through the system:

1.  **Ingestion:** A python script (outside this platform) scrapes a company website and stores a job for "Senior Product Manager" in `jobs.db`.
2.  **The Wake-Up:** The user clicks "Trigger Manual Sync" in the React `.tsx` frontend.
3.  **The API Call:** React makes an HTTP POST request to `http://localhost:3000/api/sync`.
4.  **The Hand-off:** Our Express backend `index.ts` receives the request and starts the `scout.ts` function in the background. It immediately replies to React saying "Okay, I started."
5.  **The Rules Check:** `scout.ts` looks at the database, grabs the "Senior Product Manager" job, and checks our `TITLE_BLOCKLIST` configuration.
6.  **The Execution:** It sees the word "Senior". It halts. It writes an `ERROR` log to the SQLite `activity_log` table saying "Auto-rejected: Seniority mismatch".
7.  **The Display:** 3 seconds later, the React `SyncActivityView.tsx` dashboard asks for logs. It sees the new rejection log, and paints it red on the user's screen.

---

## 6. Security and Privacy Philosophy

**Zero-Knowledge Architecture:** 
You are placing your personal phone number, home address, and entire career history into this system. If this were a traditional web startup, that data would sit on an Amazon AWS server under an account you don't control.

Because JobAgent uses a Node server running on `localhost` and a SQLite file saved in your personal file directory, **your data physically cannot leave your machine** unless you explicitly program a feature to send it to an LLM for processing. It is completely isolated.

## 7. Next Steps for Development
*   **Cron Jobs:** Right now, the user clicks "Sync". Eventually, we will add a timer in Node.js (a cron job) to wake up every morning at 4:00 AM automatically.
*   **LLM Connection:** The "Pipeline" state tracker currently just simulates fetching research and writing cover letters. The next major phase is to wire those steps up to OpenAI/Gemini API calls.
