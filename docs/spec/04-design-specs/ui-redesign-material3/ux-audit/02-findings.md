# UX Audit — Findings

**Date:** 2026-08-01
**Scope:** UX only (information architecture, clarity, flow, copy, interaction cost) — not visual/Material 3 styling. Findings feed the later Material 3 redesign but do not replace it.
**Method:** Scored against `00-resources-and-heuristics.md` (Krug pass + NN/g 10-heuristics pass, weighted toward the complex-application variant). Base observations come from `01-screen-inventory.md`'s live walkthrough; each section below was then checked against the actual source component for grounding. Where source contradicts or extends the inventory, that's called out explicitly as a **correction** — this happened on 5 of 8 screens, several materially (Dashboard, Job Search, Job Detail Panel, Settings, Notification Panel all had meaningfully more content or different behavior than what the inventory captured). Nothing below invents content beyond what the inventory or source shows; anything genuinely unresolved is marked **unconfirmed**.

---

## 1. Dashboard (`TodayView`)

**What works:** The greeting + one-line status ("You have N submitted applications in progress") is a good trunk-test pass — lands you immediately in "what's my situation right now." The bar chart, stat tiles, and pipeline-stage labels are all clickable through to a filtered Opportunities view (`onNavigateToOpportunities`), which is a strong "where can I go" affordance the inventory didn't capture. Empty states throughout (no interviews, no active applications, no pipeline jobs) use consistent icon+heading+subtext framing.

**Correction to inventory — the page is far longer than what was captured.** The inventory stopped at the Application Progress chart + Ready to Apply list. Source shows four more full sections below that: an **Active Opportunities** list (near-duplicate row pattern to Ready to Apply), an **Upcoming Interviews** card grid, a **Needs Attention** networking-contacts panel (with its own inline "Add contact" form — company/name/title/type/source fields), and a 4-tile **Stats Grid** (Total Active, Screening, Interviewing, Response Rate). None of this appeared in the walkthrough, likely because the capture didn't scroll past the fold.
- **Krug: scanning, not reading.** A dashboard with 6 distinct sections (chart, ready-to-apply, active opportunities, upcoming interviews, needs-attention, stats) stacked vertically asks a lot of scrolling to scan the whole page. For a daily-use tool this is real friction — Jason likely doesn't want to scroll past 4 sections every morning to see if anything needs attention.
- **NN/g #8, Aesthetic and minimalist design (complex-app variant: information density).** Ready to Apply and Active Opportunities use near-identical row markup (avatar, company, title, score, status chip, download/link icons) with only the presence of a "Mark as Applied" button distinguishing them. Two lists that look alike but mean different things is a recognition cost every time.

**Correction (downgrade from inventory's implied severity):** The inventory described "No interviews yet" empty-state text as ambiguously "sharing a row with the chart, as if it should be a second stat card." Source shows this is actually its own well-formed card (icon, heading, subtext) in a legitimate 8-col/4-col grid split next to the chart — not a mislabeled or merged element. The real (milder) issue is just visual weight: an empty state sits at equal visual prominence to a data-bearing chart in the same row. Worth a note for the redesign, not a Krug/NN/g violation as originally implied.

**Confirmed, unaddressed:** the semantic search box ("Semantic search e.g. HealthTech") and "Rerank Backlog" button remain unlabeled in scope — source confirms they call `/api/jobs/rerank` with a free-text query but there's no copy anywhere explaining what corpus is searched or what "rerank" changes about the list order.
- **Krug: don't make me think.** Two controls with no visible explanation of what they act on.
- **NN/g #6, Recognition rather than recall.** Jason has to remember what "rerank" does each time he returns to this control, since nothing on-screen reminds him.
- **Why it matters here:** this is a control Jason presumably built to speed up his own daily triage — if he has to pause and recall its behavior every session, it's actively working against the reason it exists.

---

## 2. Opportunities (`AllJobsView`)

**What works:** Grouped-by-stage list (8 named buckets) with per-group counts is a clean scanning pattern, and the status-filter pills double as the same click-through target the Dashboard chart uses — good cross-screen consistency for that one mechanism.

**Correction to inventory.** The inventory described each row as ending in "two right-aligned icon buttons ('...' overflow and a 'Details' button)." Source shows no overflow ("...") menu at all — the actual row-end pattern is: a conditional download icon (only for statuses past Backlog), a conditional external-link icon (only if `job.url` exists), and one single CTA button whose label changes by status (`Apply Now` for ready Backlog jobs, `Cheat sheet` for Core Interviews, `Details` otherwise). This is worth correcting for the redesign — there's no overflow menu to preserve or redesign; what exists is a status-dependent single CTA.
- **NN/g #4, Consistency and standards.** A button whose label and implied action changes per row status, with no icon or color distinguishing "this is a navigation action" from "this is a state-changing action," asks the user to read every button rather than recognize a consistent shape.

**Cross-screen vocabulary drift (see also Job Search section — flagged together in the punch list as one issue).** This screen's 8 groups (`New from scout`, `Ready to Apply`, `Needs retry`, `Applied`, `Screening`, `Interviews`, `Offers`, `Terminal`) don't match the Dashboard chart's 5 stages (`Backlog`, `Applied`, `Screening`, `Interviews`, `Offers`) or the Job Search screen's own framing (`Scout queue` / `Evaluated`, with per-job actions `Draft Assets` / `Not a fit` / `Remove`). Same underlying job-status pipeline, three different vocabularies.
- **Krug: the trunk test.** Landing on any one of these three screens out of context, the labels for "where is this job in my pipeline" don't transfer between screens.
- **Why it matters here:** this is the core mental model of the whole app — "where does each job stand" — and it's the thing Jason checks most. Inconsistent labels for the same status across his 3 most-used screens is a real daily tax, not a cosmetic nit.

---

## 3. Job Detail Panel (`JobDetailPanel`)

**What works:** The vertical status timeline (Backlog → Applied → Recruiter Screen → Core Interviews → Offer) with done/active/pending states is a clear, standard pattern. The footer's dynamic progression button (see correction below) uses plain-language labels ("Got a Recruiter Call," "Offer Received!") instead of jargon status names, which is genuinely good "match between system and real world."

**Major correction to inventory — this panel is far larger than what was captured, and the fold problem is worse than described.** The inventory captured 4 sections (Details, Application Status, Interview Schedule, and a "Close & Archive" footer link) and flagged that content already reached the 900px fold by "Interview Schedule." Source confirms that concern and shows it's understated: below Interview Schedule there are **six more full sections** — Contacts (networking, with its own inline add-contact form), Interview Debrief (a required-field form: date/outcome/notes, plus a list of past debriefs), Match Summary, Scoring Transparency (7 weighted metric bars with a text rationale), Skill Gap Analysis (an on-demand analysis trigger), Application Assets & Links, and Pipeline Process Logs (a live terminal-style log feed scoped to that company). That's 10 sections total in one slide-out panel.
- **NN/g #8, Aesthetic and minimalist design / complex-app density.** Ten stacked sections in a fixed-width side panel is dense even by dashboard-app standards, with no in-panel navigation (no anchor jump-links, tabs, or collapse/expand) to move between them.
- **Krug: users scan, they don't read.** There's no way to jump straight to, say, "Assets & Links" without scrolling past 6 other sections every time.

**Correction — the primary action is buried, and the inventory missed it entirely.** The inventory only noted the "Close & Archive" text link at the bottom. Source shows the footer actually has two actions side by side: Close & Archive (destructive, red) **and** a dynamic progression button ("Mark as Applied," "Got a Recruiter Call," "Moving to Interviews," "Offer Received!") that is the single most likely action Jason takes on any given visit to this panel. Because it lives in a footer below 10 scrollable sections, it's invisible without either scrolling to the bottom or already knowing it's there.
- **NN/g #6, Recognition rather than recall / #7, Flexibility and efficiency of use.** The action Jason will take most often on this screen requires the most scrolling to reach.
- **Why it matters here:** this is arguably the single highest-frequency action in the entire app — advancing a job's status — and it's positioned as if it were a secondary, one-time action.

**Correction (minor):** panel width is a fixed `520px`, not "~35%" as the inventory estimated (close at 1440px viewport, but worth using the real value for redesign layout math).

**New finding — from live screenshots, not source (Jason captured the full scrolled panel for a real job, "Product Manager" at "Idc").** Two things visible only with real data, not from reading JSX:
1. **The header badge and the Scoring Transparency card directly contradict each other.** The header shows "Score: 80" next to the status pill — but scrolling down, the Scoring Transparency card reads "Unscored — Not yet scored or no breakdown details available." Same job, same panel, two different answers to "has this been scored." **NN/g #1, Visibility of system status** (the system is showing inconsistent state) and **#2, Match between system and real world** (a "Score: 80" badge implies a real, checkable number — the card two sections down says otherwise). **Why it matters here:** fit-score is core to how Jason triages what to apply to (per the app's own scoring-calibration work) — a visible contradiction about whether a job's score is real is the kind of thing that erodes trust in the number generally, not just for this one job.
2. **Pipeline Process Logs shows entries that don't obviously belong to the job being viewed.** Under "Idc" / "Product Manager," the log console's visible lines read `[REJECT] Lead Contract Manager, IDC Contracts at Meta - Title Blocklist` (repeated 3 times) plus one `Linked orphan submission folder "idc" as Backlog job` line. Whether this is a genuine per-company log correctly scoped to Idc, or a global rejection feed leaking into a single job's panel, is **unconfirmed** without reading the log-fetching code — but as displayed, raw log lines referencing a different company (Meta) inside a panel titled "Idc" reads as either a scoping bug or, at minimum, copy that needs a plain-language gloss. **Krug: don't make me think** — nothing on screen explains why a Meta-titled rejection appears under an Idc job.

---

## 4. Add Job (`FindNewJobsView`)

**What works:** The Single Paste / CSV Bulk Upload mode toggle is a clean, self-evident pattern, and both modes disable the toggle while a run is in progress — good error prevention against switching modes mid-run.

**Correction to inventory (copy).** The inventory recorded the empty-state copy as "No active request" / "Paste a JD and click 'Run Automation' to begin." Source shows the actual live copy is "No active session" / "Paste a JD and click 'Run' to begin." — worth using the real strings in the redesign rather than the inventory's approximation.

**Unconfirmed:** whether the actual submit button in `JDInputForm` (a separate component not read in this pass) is labeled "Run" or "Run Automation." If it says "Run Automation" while the helper text says "Run," that's a small but real copy inconsistency (**Krug: get rid of half the words, then get rid of half of what's left** — pick one term and use it everywhere) — worth confirming directly against the component before the redesign locks copy.

---

## 5. Job Search (`SyncActivityView`)

**Major correction to inventory — this is the screen with the largest gap between what was captured and what exists.** The inventory recorded two cards (Active Search Criteria, Gate Filters) and noted the page "clearly running long" with no anchors. Source shows three more full sections below the two config cards: a **Source Registries** grid (per-connector health status — Active/Warning/Error/Paused — with credit usage for at least one source), an **Automation Pipeline** 3-step process stepper (Scouting → Evaluating & Drafting → Ready for Action) with live status text, and a two-column bottom section pairing a **live terminal-style log console** with a **Pipeline Roles** list (Evaluated jobs and a Scout queue, each row carrying Draft Assets / Not a fit / Remove actions). This page is simultaneously a settings form and a live operations/monitoring dashboard.
- **NN/g #4, Consistency and standards / complex-app match between system and real world.** The sidebar labels this screen "Job Search" (implying configuration), but roughly half its actual content is live pipeline monitoring — logs, source health, in-flight job actions — which is a different task than "configure my search." The component is even named `SyncActivityView` internally, which is a more honest description of half of what it does than the user-facing "Job Search" label is.
- **Krug: get rid of half the words on the page, then get rid of half of what's left.** This is the densest screen in the app by a wide margin — 5 major sections, one of which (Gate Filters) is itself a dense multi-field form, plus a live log console and a duplicate job-status list that overlaps in purpose with Opportunities.
- **Why it matters here:** Jason likely visits this screen for two very different reasons — "adjust my search criteria" (infrequent) and "check if today's scout run is working" (frequent, especially right after clicking Run Job Search) — and both are forced through the same long scroll every time, regardless of which one he's actually there for.

**Confirmed:** no section anchors or jump-links, despite the page running to 5 major sections with a live-updating log console 450px tall.

---

## 6. Tuning Log (`TuningLogView`)

**What works:** Row layout is scannable — company avatar, self-rejected pill, quoted critique, engine score, in a consistent left-to-right order. The empty state explains what triggers the list to populate ("When you self-reject roles, they will appear here").

**Correction to inventory.** The inventory guessed at the callout banner's CTA button ("cut off in capture, appears to read 'Save_all' / similar"). Source shows there is **no CTA button in that callout at all** — it's a static text-only banner reading "Use these critiques to polish constraints inside `job_fit_engine.md`." This is worth flagging as its own issue, separate from the inventory's guess: the callout names an internal implementation file directly in user-facing copy.
- **Krug: don't make me think / NN/g #2, Match between system and the real world.** "`job_fit_engine.md`" is an implementation detail, not a concept Jason should need to hold in his head while triaging rejected roles. It also implies a manual step (go edit that file yourself) that the UI gives no path to actually do.

**Correction.** The inventory described each row ending in a "Triaged" status pill. Source shows no such pill — the row instead shows "Discovered Mismatch at: [stage]" as a secondary line under the job title, and ends in an "Inspect" button (not a status pill). Worth using the actual pattern for the redesign.

**Confirmed, and worse than a cosmetic nit:** "Engine Score," "Avg Mismatched Score," and "Target Mismatch Stage" all appear with zero inline definition anywhere on the page (unlike the Settings/Experience tab's collapsible glossary — see Section 7 — which shows the pattern exists elsewhere in the app and could be reused here).
- **Krug: don't make me think.** Four distinct jargon terms on one screen, no tooltip, no glossary, no link to one.
- **NN/g #10, Help users recognize/diagnose/recover (documentation).**
- **Why it matters here:** this screen exists specifically so Jason can review *why* the model and his own judgment disagreed — if the scoring vocabulary itself isn't legible without already knowing the system, the screen partially defeats its own purpose every time he uses it after a gap.

---

## 7. Profile (`SettingsView`, reached via account menu → Settings)

**What works:** The Experience tab's collapsible "How to edit this document without breaking codes" guide (Minor Edit / New Claim / Retire a Claim, each with a mini code example) is a genuinely good pattern — it's exactly the kind of inline documentation the Tuning Log screen (Section 6) is missing, and could be reused there. The debounced per-field autosave with a visible Saving/Saved/Local badge is good visibility of system status.

**Major correction to inventory — the inventory only saw a fraction of this screen.** The inventory captured "Current Profile," "Personal details" (confirmed: Full name, Email, Phone, Location), and noted "Online presence" was cut off in capture. Source confirms Online presence holds LinkedIn/Portfolio/GitHub link fields — but more importantly, **Profile is only 1 of 4 sub-tabs**, and the inventory captured none of the other three:
- **Experience** — a raw markdown editor for the entire "ground truth" career file, with an ACC-NNN/VOC-XX/MET-XX proof-code system, live counts of each code type, and the collapsible edit guide mentioned above.
- **Integrations** (internal tab id "API or Connections") — a dense table of 4 AI providers (Local LLM, Gemini, Claude, Perplexity) each with primary/status/masked-key-input columns, plus 2 job-board API connectors (Adzuna, TheirStack) with their own key fields and a numeric fetch-limit setting.
- **Analytics** — an outcomes dashboard (Ever applied, Still in play, Ghosted, Rejected counts, plus breakdowns by rejection stage and type).
- **NN/g #6, Recognition rather than recall / Krug: navigation orientation.** Four sub-screens' worth of genuinely different content (identity fields, a ground-truth document editor, credential management, and analytics) live behind one sidebar-adjacent entry point that's already one extra click removed from the trunk (see below). None of the 4 sub-tabs are individually discoverable from anywhere else in the app.

**Confirmed, and now more significant given the above:** Profile/Settings is reached only via the account-menu dropdown at the bottom of the sidebar, not as a direct sidebar item like the other 5 screens (Dashboard, Opportunities, Job Search, Add Job, Tuning Log).
- **Krug: navigation should answer "where can I go."** 5 of 6 real destinations are one click away in the sidebar; the 6th (which, per the correction above, actually holds 4 dense sub-screens including credential management) requires opening a menu first.
- **NN/g #4, Consistency and standards.**
- **Why it matters here:** the Experience tab specifically is presumably a screen Jason returns to whenever his ground-truth resume data changes — burying a frequently-edited, high-stakes document (it's literally the anti-hallucination source for every generated resume) two clicks deep is a real recurring cost, not a one-time onboarding friction.

**New finding from source, not in inventory — the account-menu dropdown itself (`Sidebar.tsx`), reached from the same entry point as Settings.** Three items worth flagging together as a set:
1. The user card shows a hardcoded name ("soylaertes") and a "Plus" plan badge. In a single-user local tool with no accounts or subscription tiers, a plan badge is either leftover placeholder content from a SaaS template or actively misleading about what the app is.
2. "Help" triggers a native browser `alert()` with hardcoded text ("Applyr v2.5 Multi-LLM Agent..."). This breaks out of the app's own visual language entirely — the one moment a native OS dialog appears in an otherwise fully custom UI.
3. "Log out" runs `localStorage.clear()` and reloads the page. There is no authentication in this app, so "Log out" doesn't log out of anything — it silently clears local browser storage, which is a different and non-obvious action hiding behind a familiar, low-stakes-sounding label.
- **NN/g #4, Consistency and standards (item 1, 2)** and **#5, Error prevention (item 3)** — a destructive-sounding-but-actually-not-that-destructive (or possibly more destructive than expected, depending what's in localStorage) action mislabeled as a routine one.
- **Why it matters here:** items 1–2 are cosmetic but visible every time Jason opens the account menu. Item 3 is the one with real stakes — a mislabeled action in a menu he'll open periodically is exactly the kind of thing that gets clicked on autopilot.

---

## 8. Notification Panel (bell icon dropdown)

**What works:** Notification rows are generated from live job-state conditions (new roles, backlog ready to apply, interviews in the next 3 days, active screening/interviews) rather than a stored notification log, which keeps the panel honest about current state rather than accumulating stale entries.

**Correction to inventory — the "unconfirmed" navigation question is resolved.** The inventory flagged "unconfirmed whether clicking navigates." Source confirms every notification row has a wired click action — new-role and backlog notifications navigate to Opportunities, interview notifications open that job's detail panel directly, all while closing the dropdown.

**Correction (minor, copy).** The inventory recorded a "14 restricted roles ready to apply" notification. Source shows the actual generated copy pattern is "N matched role(s) ready to apply" — no "restricted" language exists in the component.

**Confirmed, and worth its own flag beyond the inventory's note:** there is no "mark all read" or dismiss action — and source shows why: the panel has no read/unread concept at all. It recomputes the same 4 notification types from current job data on every open. A "24 new roles found" notification will keep reappearing, identically, every time the panel opens until those jobs' status actually changes.
- **NN/g #3, User control and freedom.** No way to acknowledge "yes, I've seen this" separately from "I've resolved the underlying condition."
- **Why it matters here:** for a tool Jason opens many times a day, a notification indicator that can never be cleared except by resolving the underlying task risks becoming background noise he stops registering — which defeats the point of a notification affordance.

---

## Prioritized Cross-Screen Punch List

### High

1. **Job Detail Panel — primary action buried below 10 scrollable sections.** *(Screen: Job Detail Panel.)* The dynamic status-progression button (the most frequent action on this panel — advancing a job's pipeline stage) sits in the footer below Details, Application Status, Interview Schedule, Contacts, Interview Debrief, Match Summary, Scoring Transparency, Skill Gap Analysis, Assets & Links, and Pipeline Process Logs. Violates NN/g #6 (Recognition over recall) and #7 (Flexibility and efficiency of use). **Fix:** pin the progression button (and Close & Archive) to a sticky footer that stays visible while the body scrolls, or duplicate it near the header next to the status chip, since it's the action taken most often per visit.

2. **Job Search screen conflates configuration with live operations monitoring.** *(Screen: Job Search / `SyncActivityView`.)* One screen holds search-criteria config, gate-filter config, a source-health grid, a 3-step pipeline stepper, a live terminal log, and a duplicate job-status list — under a sidebar label ("Job Search") that only describes half of it. Violates NN/g #4 (Consistency/match with real world) and Krug's "get rid of half the words." **Fix:** split into two views (Search Settings vs. Run Activity/Log), or collapse the monitoring section (source health, log console, pipeline roles) behind a single expandable "Activity" panel that's closed by default when there's no active run.

3. **Job status vocabulary is inconsistent across the 3 most-used screens.** *(Screens: Dashboard, Opportunities, Job Search.)* Dashboard's funnel uses 5 stage labels; Opportunities groups jobs into 8 differently-named buckets; Job Search frames the same jobs as "Scout queue" / "Evaluated" with its own action verbs (Draft Assets / Not a fit / Remove). Violates Krug's trunk test and NN/g #4 (Consistency and standards). **Fix:** define one canonical status vocabulary and use it verbatim in all three places — chart labels, group headers, and job-card badges — even where the screens serve different purposes.

4. **Tuning Log exposes an internal filename and undefined scoring jargon with zero inline help.** *(Screen: Tuning Log.)* The callout banner tells Jason to edit `job_fit_engine.md` directly, and "Engine Score" / "Avg Mismatched Score" / "Target Mismatch Stage" appear with no definition anywhere on the page. Violates Krug's "don't make me think" and NN/g #10 (Help and documentation). **Fix:** reuse the Settings/Experience tab's existing collapsible-glossary pattern here; drop the raw filename from user-facing copy (replace with plain description of what the flags do).

5. **Profile/Settings is 4 dense sub-screens hidden behind an indirect nav path.** *(Screen: Profile/Settings.)* Experience (ground-truth resume data editor), Integrations (credential management), and Analytics are not discoverable anywhere except inside a menu-triggered Settings screen that isn't a direct sidebar item like the other 5 screens. Violates Krug's navigation orientation and NN/g #4/#6. **Fix:** promote Settings (or at minimum, Experience — the highest-stakes, most-edited sub-tab) to a direct sidebar entry.

6. **Job Detail Panel's header score contradicts its own Scoring Transparency card.** *(Screen: Job Detail Panel.)* Observed live on a real job: header shows "Score: 80," but the Scoring Transparency card further down reads "Unscored — Not yet scored or no breakdown details available." Violates NN/g #1 (Visibility of system status) and #2 (Match between system and real world). **Fix:** trace why the top-level score and the transparency breakdown can disagree, and either backfill the breakdown whenever a score exists or don't render a numeric "Score: N" badge until the breakdown that explains it is also available.

7. **Account-menu "Log out" doesn't log out — it clears localStorage and reloads.** *(Screen: Sidebar account menu, reached from any screen.)* Mislabeled action on a local single-user tool with no authentication. Violates NN/g #5 (Error prevention) via a misleading label on a state-clearing action. **Fix:** rename to something accurate ("Reset local session" or similar) or remove entirely if it serves no real purpose in a local-first single-user app.

### Medium

8. **Dashboard's semantic search + "Rerank Backlog" controls have no explanation of scope or effect.** *(Screen: Dashboard.)* No copy anywhere indicates what's searched or what reranking changes. Violates NN/g #6 (Recognition over recall). **Fix:** add a one-line caption or placeholder text naming what's searched (e.g., "Search your backlog by company, role, or keyword").

9. **Job Detail Panel's Interview Debrief needed a defensive caption to avoid being confused with the cheat sheet.** *(Screen: Job Detail Panel.)* The component itself includes the line "This is separate from your prep cheat sheet" — a signal the distinction between these two similar-sounding features isn't self-evident from placement or naming alone. Violates Krug's "don't make me think." **Fix:** rename one of the two features so the difference is legible from the label itself, not from a footnote.

10. **Notification panel has no read/dismiss state — the same notification reappears every open until the underlying job changes status.** *(Screen: Notification Panel.)* Violates NN/g #3 (User control and freedom). **Fix:** add a lightweight dismiss/mark-as-seen affordance, even if it's session-only rather than persisted.

11. **Account-menu "Help" opens a native browser `alert()`, breaking out of the app's UI entirely.** *(Screen: Sidebar account menu.)* One jarring OS-native dialog in an otherwise fully custom interface. Violates NN/g #4 (Consistency and standards) and #8 (Aesthetic and minimalist design). **Fix:** replace with an in-app modal or remove if the version-string content isn't actually useful to surface.

12. **Opportunities row CTA button changes label and implied action per status with no visual distinction from the icon buttons next to it.** *(Screen: Opportunities.)* "Apply Now" / "Cheat sheet" / "Details" all render as the same button style regardless of whether they're navigational or state-changing. Violates NN/g #4 (Consistency and standards). **Fix:** visually distinguish state-changing actions (e.g., Apply Now) from navigational ones (Details, Cheat sheet) — different button treatment, not just different text.

13. **Account-menu user card shows a placeholder-looking name and a meaningless "Plus" plan badge.** *(Screen: Sidebar account menu.)* Reads as leftover SaaS-template content in a single-user local tool. Violates NN/g #4 (Consistency and standards). **Fix:** pull the real profile name (already fetched elsewhere in `Sidebar.tsx` via `/api/profile/identity`) and drop the plan badge entirely.

### Low

14. **Add Job screen's empty-state copy ("Paste a JD and click 'Run' to begin") may not match the actual submit button's label.** *(Screen: Add Job.)* Unconfirmed — `JDInputForm.tsx` wasn't read in this pass. **Fix:** verify the button label matches the helper text verbatim before the redesign locks copy.

15. **Job Detail Panel's fixed 520px width should be used as the real spec value, not the inventory's "~35%" estimate.** *(Screen: Job Detail Panel.)* Not a UX defect, just a data-accuracy note for whoever builds the Material 3 layout.

16. **Opportunities search box has no visible clear affordance once text is entered.** *(Screen: Opportunities.)* Minor click-cost increase (select-all + delete instead of one click) for a control used repeatedly. **Fix:** add a clear-icon inside the search field once it has a value.

17. **Job Detail Panel's Pipeline Process Logs shows entries that may not be scoped to the job being viewed.** *(Screen: Job Detail Panel.)* Observed live: log lines referencing a different company ("Meta") appeared under an "Idc" job's panel. Unconfirmed whether this is a genuine scoping bug or correctly-scoped data with confusing copy — verify against the log-fetching code before the redesign. **Fix:** either scope the query correctly or gloss the log lines in plain language so an unrelated-looking entry doesn't read as broken.

---

## Summary of Unconfirmed Items (carried from or added to the inventory's own list)

- Whether `JDInputForm`'s submit button reads "Run" or "Run Automation" (component not read in this pass).
- Whether an overflow ("...") menu exists anywhere in the Opportunities row pattern outside what `AllJobsView.tsx` renders directly (none found in the file read).
- General note: this pass read component source for grounding but did not execute the app or capture new screenshots, per the constraint already noted in `01-screen-inventory.md`. Any visual/layout claim here is inferred from JSX/class structure, not pixels.
