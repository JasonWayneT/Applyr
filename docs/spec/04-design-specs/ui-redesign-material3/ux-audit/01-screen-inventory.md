# UX Audit — Screen Inventory

**Date:** 2026-08-01
**Captured from:** live `applyr-dev` server (localhost:5173), desktop viewport (1440x900)
**Method:** manual walkthrough via in-app browser, pixel screenshots viewed live but **not saved to disk** — see note at bottom.

Applyr's shell: a fixed left sidebar (logo, 5 nav items: Dashboard, Opportunities, Job Search, Add Job, Tuning Log, plus an account menu pinned to the bottom) and a top-right header (notification bell, avatar). No breadcrumb/page-title pattern in the header itself — the page title is repeated inside the main content area instead.

---

## 1. Dashboard (`TodayView`, sidebar label "Dashboard")

- Greeting header: "Good evening, Jason." + one line of state ("You have 157 submitted applications in progress. Let's keep the momentum going.")
- **Application Progress** card: a bar chart across 5 pipeline stages (Backlog / Applied / Screening / Interviews / Offers) with counts under each bar. At capture time, "No interviews yet" empty-state text appeared inside what looks like it should be a second stat card, sharing the row with the bar chart.
- **Ready to Apply** list below: job rows with company name/initial avatar, role title, a fit-score badge ("FIT SCORE"), a status pill ("Ready to Apply"), and 3 icon-only action buttons per row (no visible labels/tooltips confirmed in this pass).
- A semantic search box ("Semantic search (e.g. HealthTech)") and a "Rerank Backlog" button sit above the list, right-aligned, disconnected from any visible label explaining what they rerank or search across.

## 2. Opportunities (`AllJobsView`, sidebar label "Opportunities")

- Header: "Opportunities" + subtext "Track your career journey with clarity."
- Search box + a "Date Added (Newest)" sort dropdown + a filter pill row: All / Backlog / Applied / Screening / Interviews / Offers / Closed (these double as the Dashboard's pipeline-stage click-throughs — `onNavigateToOpportunities`).
- A "NEW FROM SCOUT" badge/count sits directly above the list.
- Each row: company avatar-letter, company name, status pill (color-coded: e.g. amber "Pending Assets", blue "Ready to Apply"), role title beneath, and two right-aligned icon buttons ("..." overflow and a "Details" button) per row.
- List is dense — 6 rows visible before scroll at 900px height.

## 3. Job Detail Panel (`JobDetailPanel`, slide-out from any job row)

- Slides in from the right as an overlay (~35% width), dims the rest of the screen.
- Header: role title, company name, a "Back" link (top-left of panel) and a circular company-initial avatar (top-right).
- **Details** card: Discovered / Applied / Interview dates in a 3-column mini-grid.
- **Application Status** card: a vertical radio-style stepper (Backlog → Applied → Recruiter Screen → Core Interviews → Offer), current stage highlighted.
- **Interview Schedule** card: a date/time picker, empty at capture time.
- A red "Close & Archive" text link at the bottom.
- **At 900px viewport height, the panel's content already reaches the visible fold by "Interview Schedule"** — anything below (there's more card content per the component) requires scrolling inside the panel, with no visible scroll affordance in the screenshot.

## 4. Add Job (`FindNewJobsView`, sidebar label "Add Job")

- Header: "Add Job" + subtext "Evaluate a role and generate tailored assets."
- Two entry-mode tabs, top-right: "Single Paste" / "CSV Bulk Upload".
- Left column form: Company Name, Job URL (optional), Job Description (large paste textarea) — a single linear form, no multi-step structure.
- Right column: a "Pipeline Tracking" card, empty state ("No active request", "Paste a JD and click 'Run Automation' to begin").
- Primary CTA: "Run Automation" button, disabled/greyed out until required fields are filled (grey in the captured state since the form was empty).
- Small print under the button: a one-line disclaimer about the pipeline reading the JD to generate tailored assets.

## 5. Job Search (`SyncActivityView`, sidebar label "Job Search")

- Header: "Job Search" + subtext "Configure your search criteria, then run the scout to find and evaluate matching roles."
- Primary CTA top-right: "Run Job Search" (green, high-contrast — the clearest CTA of any screen in this audit).
- **Active Search Criteria** card: Target Role, Additional Search Titles, Work Setting (Remote/Hybrid/On-site chips), Location, Date Posted, Experience Level.
- **Gate Filters** card below: Title Blocklist, Max Years Required, Industry Blocklist, Minimum Salary — dense multi-field form, several fields showing placeholder/helper microcopy beneath them.
- This is the densest form screen in the app; no visible section anchors/jump-links despite the page clearly running long (confirmed by scrollbar).

## 6. Tuning Log (`TuningLogView`, sidebar label "Tuning Log")

- Header: "Tuning Log" + subtext "Review discrepancies between automated fit scoring and your manual self-rejections."
- A callout banner top-right: "Use these X flags to auto-tune the scoring model" + a CTA button (cut off in capture, appears to read "Save_all" / similar).
- 3 stat tiles: Total Critiques (226), Avg Mistmatch Score (32), Target Mismatch Stage (Drafted).
- **Feedback Records** list: each row shows company, role, a "Self-Rejected" pill, a quoted critique snippet in quotes, an "Engine Score" number, and a "Triaged" status pill.
- This screen is the most jargon-dense of the six tabs (mismatch score, engine score, triaged, target mismatch stage) with no visible inline explanation of what these terms mean to a first-time viewer.

## 7. Profile (`SettingsView`, reached via account menu → Settings, not a direct sidebar item)

- Breadcrumb: "Settings > Profile" (the only screen in the app with a breadcrumb).
- Sub-navigation: 4 pills — Profile / Experience / Integrations / Analytics.
- **Current Profile** card: name + contact line.
- **Personal details** card: Full name, Email, Phone, Location fields, pre-filled.
- **Online presence** card below (cut off in capture).
- Note: this screen surfaces real contact PII (name/email/phone) in a plain editable form — flagged for the audit stage to check password/contact-field exposure conventions, not reproduced here.

## 8. Notification Panel (bell icon, top-right, available from any screen)

- Dropdown overlay, anchored under the bell icon.
- Header: "Notifications" + a count ("X active").
- 2 notification rows observed: "24 new roles found" (with a relative timestamp) and "14 restricted roles ready to apply" (with a "Ready to Apply" sub-badge).
- No visible "mark all read" / clear action, and no visible link from a notification row to the thing it's about (unconfirmed whether clicking navigates — not tested in this pass).

---

## Note on saved screenshots

Jason asked to save the screens captured in this pass for reuse in the later Material 3 redesign. **The in-app browser tool used for this walkthrough can display live screenshots but has no mechanism to persist them as image files to disk** — there's no export/save-to-path action available. What's preserved instead is this written inventory (structure, content, states, copy) for every screen. If pixel references are wanted for the redesign pass, they'll need to be captured separately (e.g. OS screenshot tool) when that work starts.
