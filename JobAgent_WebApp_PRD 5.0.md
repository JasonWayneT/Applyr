# JobAgent — Web Application PRD
### Full-Stack Job Search Portal

| Field | Value |
|---|---|
| **Author** | Antigravity (Pair Programming with Jason Taylor) |
| **Status** | Draft / In Design |
| **Date** | April 12, 2026 |
| **Version** | 1.0 |
| **Target IDE** | Google Project IDX / Antigravity |

---

## 1. Product Overview

JobAgent is a personal job search portal that automates the grind of finding, evaluating, and applying to roles. It combines an AI-powered application asset generator (Resume, Cover Letter, Interview Cheat Sheet) with a clean pipeline tracker that shows exactly where every opportunity stands.

The web app is the public-facing, portfolio-grade version of a local automation system. It is designed for two audiences simultaneously: Jason as the daily user running his job search, and hiring managers viewing his portfolio who should be able to understand what was built within 30 seconds of landing on the page.

### Two modes, one codebase

| Mode | Audience | Data | Purpose |
|---|---|---|---|
| **Live (authenticated)** | Jason | Real job data, real assets | Daily job search tool |
| **Demo (unauthenticated)** | Portfolio visitors | Seeded demo data | Portfolio case study |

---

## 2. Core Design Philosophy

### Don't Make Me Think

Every label, button, and status must be self-explanatory without prior knowledge of the system. Internal pipeline vocabulary ("Scouted," "Drafted," "Gatekeeper") never surfaces in the UI. Every action button describes what happens when you click it.

### You set it once, it works forever

Resume and work experience are uploaded once and persist. The system references them on every run. Users should never be prompted to re-upload something they already provided.

### Today first

The default view is always "what needs my attention right now," not "show me the entire database." The full list is one click away but never the first thing you see.

---

## 3. Design System

This section is the source of truth for all UI implementation. Every component must match these specifications exactly. The design language is clean white cards on a light secondary background, with a purple primary accent and a two-tone sidebar. Inspired by the mockups built during the design exploration phase of this project.

### 3.1 Visual Reference

The overall aesthetic is:
- **Sidebar:** Light gray-white secondary surface (`#F7F8FA`), thin right border, purple active accent stripe
- **Main content:** Pure white cards on a slightly off-white page background
- **Accent color:** Purple (`#534AB7` family) for all primary actions, active states, new match badges, and the logo wordmark
- **Status colors:** Semantic and restrained — purple for new/action, amber for caution, green for active/positive, gray for neutral/closed
- **Typography:** Inter, two weights only (400 and 500), sentence case everywhere
- **Borders:** Consistently 0.5px, never heavy. Cards feel light, not boxy.
- **Logo:** `job` in primary text color + `agent` in purple (`#534AB7`), 15px, weight 500

### 3.2 Color Palette

```css
/* Primary brand — purple */
--color-primary:          #534AB7   /* Purple — buttons, active nav stripe, logo accent */
--color-primary-hover:    #4740A0   /* Hover state */
--color-primary-light:    #EEEDFE   /* Light purple tint — new match badge bg, accent fills */
--color-primary-border:   #AFA9EC   /* Purple border — badge borders, focus rings */
--color-primary-text:     #3C3489   /* Dark purple — text on light purple backgrounds */

/* Page & surface */
--color-bg:               #FFFFFF   /* Cards, main content area */
--color-bg-secondary:     #F7F8FA   /* Sidebar, section group headers, metric tiles */
--color-bg-tertiary:      #F3F4F6   /* Upload zones, input backgrounds */
--color-border:           #E5E7EB   /* Default — cards, rows, dividers (0.5px) */
--color-border-strong:    #D1D5DB   /* Hover borders */

/* Text */
--color-text-primary:     #111827   /* Company names, page titles, primary content */
--color-text-secondary:   #6B7280   /* Role names, sub-notes, nav items (inactive) */
--color-text-tertiary:    #9CA3AF   /* Timestamps, column headers, placeholders */

/* Status: New match */
--color-new-bg:           #EEEDFE   /* Light purple */
--color-new-text:         #3C3489   /* Dark purple */
--color-new-accent:       #534AB7   /* Left border stripe on cards/rows */

/* Status: Worth a look (borderline) */
--color-look-bg:          #FEF3C7   /* Amber tint */
--color-look-text:        #92400E   /* Dark amber */
--color-look-accent:      #F59E0B   /* Left border stripe */

/* Status: Ready to apply */
--color-ready-bg:         #EFF6FF   /* Light blue */
--color-ready-text:       #1E40AF   /* Dark blue */

/* Status: Waiting to hear back */
--color-waiting-bg:       #F3F4F6   /* Neutral gray */
--color-waiting-text:     #374151   /* Dark gray */

/* Status: In conversation */
--color-convo-bg:         #ECFDF5   /* Light green */
--color-convo-text:       #065F46   /* Dark green */
--color-convo-accent:     #10B981   /* Left border stripe on cards/rows */

/* Status: Closed / dimmed */
--color-closed-bg:        #F9FAFB
--color-closed-text:      #9CA3AF

/* Match score */
--color-score-hi-bg:      #ECFDF5   /* >= 80 */
--color-score-hi-text:    #065F46
--color-score-mid-bg:     #FEF3C7   /* 75–79 */
--color-score-mid-text:   #92400E
--color-score-lo-bg:      #F3F4F6   /* < 75 */
--color-score-lo-text:    #9CA3AF

/* Semantic utility */
--color-success:          #10B981
--color-warning:          #F59E0B
--color-danger:           #EF4444
--color-warn-text:        #92400E   /* Days-silent nudge text */
```

### 3.3 Typography

```css
/* Font */
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
/* Load from Google Fonts: https://fonts.google.com/specimen/Inter */
/* Weights needed: 400, 500 */

/* Scale */
--text-xs:    11px;  /* line-height: 1.5 — col headers, timestamps, badge labels */
--text-sm:    12px;  /* line-height: 1.5 — sub-notes, button text, secondary labels */
--text-base:  13px;  /* line-height: 1.6 — body text, card content, nav items */
--text-md:    15px;  /* line-height: 1.5 — page titles, company names in cards */
--text-lg:    16px;  /* line-height: 1.4 — section headings */
--text-xl:    20px;  /* line-height: 1.3 — modal titles, panel headings */

/* Weights — two only */
--weight-regular:  400;   /* All body text */
--weight-medium:   500;   /* Company names, nav active, page titles, stat numbers */

/* Never use 600, 700, or bold — too heavy for this aesthetic */

/* Letter spacing */
--tracking-tight:  -0.01em;   /* Page titles, company names */
--tracking-caps:    0.06em;   /* Uppercase section labels only */
```

### 3.4 Spacing & Layout

```css
/* Base unit: 4px */
--space-1:   4px
--space-2:   8px
--space-3:   12px
--space-4:   16px
--space-5:   20px
--space-6:   24px
--space-8:   32px
--space-10:  40px

/* Border radius */
--radius-sm:   4px    /* Badges, pills, tight elements */
--radius-md:   6px    /* Buttons, inputs, chips */
--radius-lg:   10px   /* Cards, panels */
--radius-xl:   14px   /* Modals, side panels */

/* Borders — always 0.5px */
--border-default:  0.5px solid var(--color-border)
--border-strong:   0.5px solid var(--color-border-strong)
--border-focus:    0 0 0 3px rgba(83, 74, 183, 0.12)   /* Purple glow on focus */

/* Layout shell */
--sidebar-width:   196px
--panel-width:     480px    /* Job detail side panel */

/* Shadows — use sparingly, keep subtle */
--shadow-card:   0 1px 2px rgba(0,0,0,0.05)
--shadow-modal:  0 8px 24px rgba(0,0,0,0.08)
```

### 3.5 Component Specs

#### Logo

```
Text: "job" + "agent" (no space)
"job"    → color: var(--color-text-primary),   weight: 500
"agent"  → color: var(--color-primary) #534AB7, weight: 500
font-size: 15px
No icon, no logomark — the wordmark is the brand
```

#### Buttons

```css
/* Primary — "Review & build", "Apply", "Run automation" */
background:     var(--color-primary)    /* #534AB7 */
color:          #FFFFFF
border:         none
border-radius:  var(--radius-md)
padding:        6px 14px
font-size:      var(--text-sm)
font-weight:    var(--weight-medium)
cursor:         pointer
transition:     background 120ms ease
hover:          background var(--color-primary-hover)  /* #4740A0 */
active:         transform scale(0.98)

/* Full-width variant (forms, CTAs) */
width: 100%
padding: 8px 14px

/* Primary with icon/arrow suffix — "Apply ↗", "Review & build ↗" */
/* Append " ↗" as text — no icon library needed */

/* Secondary — "Preview", "Cancel", "Dismiss" */
background:     var(--color-bg)
color:          var(--color-text-secondary)
border:         var(--border-default)
border-radius:  var(--radius-md)
padding:        5px 11px
font-size:      var(--text-sm)
hover:          background var(--color-bg-secondary), color var(--color-text-primary)

/* Accent purple ghost — "Review & build" alternative, badge-style actions */
background:     var(--color-primary-light)   /* #EEEDFE */
color:          var(--color-primary-text)    /* #3C3489 */
border:         0.5px solid var(--color-primary-border)  /* #AFA9EC */
border-radius:  var(--radius-md)
padding:        4px 10px
font-size:      var(--text-sm)

/* Accent green ghost — "Open cheat sheet", interview actions */
background:     var(--color-convo-bg)    /* #ECFDF5 */
color:          var(--color-convo-text)  /* #065F46 */
border:         0.5px solid #A7F3D0
border-radius:  var(--radius-md)
padding:        4px 10px
font-size:      var(--text-sm)
```

#### Navigation badges (count pills on nav items)

```css
/* Purple — "Today" attention count */
background:  var(--color-primary-light)  /* #EEEDFE */
color:       var(--color-primary-text)   /* #3C3489 */
font-size:   var(--text-xs)
padding:     1px 7px
border-radius: 10px

/* Green — "Find new jobs" unreviewed count */
background:  var(--color-convo-bg)    /* #ECFDF5 */
color:       var(--color-convo-text)  /* #065F46 */
font-size:   var(--text-xs)
padding:     1px 7px
border-radius: 10px
```

#### Status Pills

```css
/* All pills share base styles */
font-size:     var(--text-xs)     /* 11px */
font-weight:   var(--weight-medium)
padding:       3px 9px
border-radius: var(--radius-sm)   /* 4px — intentionally tight */
display:       inline-block
white-space:   nowrap

/* Per-status fill/text — reference Section 3.2 */
.pill-new       { background: #EEEDFE; color: #3C3489; }
.pill-look      { background: #FEF3C7; color: #92400E; }
.pill-ready     { background: #EFF6FF; color: #1E40AF; }
.pill-waiting   { background: #F3F4F6; color: #374151; }
.pill-convo     { background: #ECFDF5; color: #065F46; }
.pill-closed    { background: #F9FAFB; color: #9CA3AF; }
```

#### Match Score

```css
/* Number only — no progress bar, no ring */
font-size:     var(--text-sm)
font-weight:   var(--weight-medium)
padding:       2px 8px
border-radius: var(--radius-sm)

.score-hi   { background: #ECFDF5; color: #065F46; }  /* >= 80 */
.score-mid  { background: #FEF3C7; color: #92400E; }  /* 75–79 */
.score-lo   { background: #F3F4F6; color: #9CA3AF; }  /* < 75 or unscored */
```

#### Cards (Today view attention cards)

```css
background:      var(--color-bg)
border:          var(--border-default)
border-radius:   var(--radius-lg)
padding:         12px 14px
cursor:          pointer
transition:      border-color 150ms ease
hover:           border-color var(--color-border-strong)

/* New match / needs attention — purple left stripe */
.card-new  { border-left: 2px solid #534AB7; border-radius: 0 10px 10px 0; }

/* In conversation — green left stripe */
.card-live { border-left: 2px solid #10B981; border-radius: 0 10px 10px 0; }
```

#### List Rows (All Jobs view)

```css
/* Base row */
display:          grid
grid-template-columns: 1fr 130px 90px 120px
align-items:      center
gap:              12px
padding:          11px 20px
border-bottom:    var(--border-default)
cursor:           pointer
transition:       background 100ms ease
hover:            background var(--color-bg-secondary)

/* Company name */
font-size:   var(--text-base)   /* 13px */
font-weight: var(--weight-medium)
color:       var(--color-text-primary)

/* Role title */
font-size:   var(--text-sm)
color:       var(--color-text-secondary)
white-space: nowrap
overflow:    hidden
text-overflow: ellipsis

/* Sub-note (3rd line, contextual info) */
font-size:   var(--text-xs)
color:       var(--color-text-tertiary)
margin-top:  3px

/* Sub-note warning variant (days-silent) */
.sub-note-warn { color: var(--color-warn-text); }   /* #92400E */

/* Sub-note positive variant (interview date) */
.sub-note-good { color: var(--color-convo-text); font-weight: var(--weight-medium); }

/* Left accent stripes — same as cards */
.row-new  { border-left: 2px solid #534AB7; }
.row-live { border-left: 2px solid #10B981; }

/* Closed rows */
.row-closed { opacity: 0.45; }
```

#### Sidebar

```css
width:        196px
background:   var(--color-bg-secondary)   /* #F7F8FA */
border-right: var(--border-default)
padding:      16px 0
display:      flex
flex-direction: column

/* Logo area */
padding: 0 16px 16px
border-bottom: var(--border-default)
margin-bottom: 8px

/* Nav item — default */
padding:       5px 8px
margin:        1px 6px
border-radius: var(--radius-md)
font-size:     var(--text-base)    /* 13px */
color:         var(--color-text-secondary)
cursor:        pointer
display:       flex
align-items:   center
justify-content: space-between
transition:    background 100ms ease
hover:         background var(--color-bg-tertiary), color var(--color-text-primary)

/* Nav item — active */
background:    var(--color-bg)
color:         var(--color-text-primary)
font-weight:   var(--weight-medium)
border-right:  2px solid var(--color-primary)   /* purple accent stripe */
border-radius: 0                                 /* stripe needs flush edge */

/* Footer area (My Profile) */
margin-top: auto
padding: 12px 14px
border-top: var(--border-default)
font-size: var(--text-xs)
color: var(--color-text-tertiary)
```

#### Group / Section Labels (All Jobs view sticky headers)

```css
font-size:        var(--text-xs)    /* 11px */
font-weight:      var(--weight-medium)
color:            var(--color-text-tertiary)
text-transform:   uppercase
letter-spacing:   var(--tracking-caps)   /* 0.06em */
padding:          10px 20px 6px
background:       var(--color-bg-secondary)
border-bottom:    var(--border-default)
position:         sticky
top:              0
```

#### Metric Tiles (Today view bottom strip)

```css
background:    var(--color-bg-secondary)
border-radius: var(--radius-md)
padding:       10px 12px

/* Number */
font-size:   20px
font-weight: var(--weight-medium)
color:       var(--color-text-primary)

/* Label */
font-size:   var(--text-xs)
color:       var(--color-text-secondary)
margin-top:  2px

/* Response rate — colored when > 0 */
.metric-response-rate { color: var(--color-warn-text); }  /* amber */
```

#### Upload Zones

```css
background:    var(--color-bg-tertiary)   /* #F3F4F6 */
border:        1.5px dashed var(--color-primary-border)   /* #AFA9EC dashed */
border-radius: var(--radius-md)
padding:       28px 20px
text-align:    center
cursor:        pointer
transition:    background 150ms ease, border-color 150ms ease
hover:         background var(--color-primary-light), border-color var(--color-primary)
drag-active:   background var(--color-primary-light), border-color var(--color-primary)

/* Upload icon */
width:  22px
height: 22px
color:  var(--color-primary)
margin-bottom: 8px

/* Label text */
font-size:   var(--text-sm)
font-weight: var(--weight-medium)
color:       var(--color-text-secondary)

/* Uploaded state */
background:   var(--color-convo-bg)
border-color: #A7F3D0
border-style: solid
```

#### Inputs & Textareas

```css
background:    var(--color-bg)
border:        0.5px solid var(--color-border)
border-radius: var(--radius-md)
padding:       7px 11px
font-size:     var(--text-base)    /* 13px */
font-family:   inherit
color:         var(--color-text-primary)
width:         100%
transition:    border-color 120ms ease
placeholder:   color var(--color-text-tertiary)
focus:         border-color var(--color-primary), outline none, box-shadow var(--border-focus)
```

#### Search input (All Jobs topbar)

```css
/* Same as input above, plus: */
background:    var(--color-bg-secondary)
width:         180px
font-size:     var(--text-sm)
padding:       5px 10px
focus:         background var(--color-bg), border-color var(--color-primary)
```

#### Filter chips (All Jobs topbar)

```css
font-size:     var(--text-xs)
padding:       4px 10px
border:        0.5px solid var(--color-border)
border-radius: 10px
background:    transparent
color:         var(--color-text-secondary)
cursor:        pointer
transition:    all 120ms ease
hover:         border-color var(--color-border-strong), color var(--color-text-primary)

/* Active chip */
background:    var(--color-primary-light)
color:         var(--color-primary-text)
border-color:  var(--color-primary-border)
```

---

## 4. Application Structure

### 4.1 Navigation

Three primary views accessible from the sidebar:

| Nav item | Badge | Description |
|---|---|---|
| **Today** | Count of items needing attention | The default landing view. Shows new matches, upcoming interviews, and follow-up nudges. |
| **All jobs** | — | Full list view of every tracked opportunity, grouped by status. |
| **Find new jobs** | Count of unreviewed matches | The asset generation workflow — paste a JD or let the scout run. |

One secondary area, de-emphasized:

| Nav item | Placement | Description |
|---|---|---|
| **My profile** | Bottom of sidebar, above the footer | Resume and work experience uploads. Set once, referenced always. |

### 4.2 Page: Today (default landing)

**Purpose:** Answer "what do I do right now?" without clicking into anything.

**Layout:** Single column, vertically stacked sections. No Kanban board.

**Sections (in order):**

1. **New matches ready to review** — Cards for any job that scored ≥ 78 and hasn't been acted on yet. Each card shows: company, role, match score (colored pill), 1-line reason for the match, and a "Review & build" CTA.

2. **Worth a look** — Cards for jobs scoring 75–77. Different visual weight than new matches — same card but amber "Worth a look" badge instead of purple "New match." CTA is "Take a look" not "Review & build."

3. **Coming up** — Any role in "In conversation" status with an interview date within 7 days. Shows the interview date and a "Open cheat sheet" CTA. Green left accent border.

4. **Might be worth a follow-up** — Nudge rows (lighter weight than cards) for applications with no response after 7 days. Shows company, role, days elapsed. Dismissable. Amber left accent or sub-note.

5. **At a glance** — Four metric tiles at the bottom: Active, Waiting to hear back, In conversation, Response rate. These are informational only — no CTAs.

**Empty state:** If nothing needs attention, show a single centered message: "You're all caught up. Your next scout run is scheduled for tomorrow." with a secondary "Find new jobs" button.

### 4.3 Page: All Jobs

**Purpose:** A complete, scannable list of every tracked opportunity.

**Layout:** Full-width list view, grouped by status. No board/Kanban.

**Controls (top bar):**
- Page title: "All jobs"
- Search input: searches company name and role title in real time
- Filter chips: All · To do · Active · Closed

**List structure:**

Rows are grouped under sticky section headers. Groups in display order:

| Group header | Includes statuses | Left accent |
|---|---|---|
| Needs your attention | New match, Worth a look | Purple `#4F6BF4` |
| Ready to apply | Ready to apply | Blue `#4F6BF4` light |
| Waiting to hear back | Waiting | None |
| In conversation | In conversation | Green `#10B981` |
| Closed | Not a fit, They passed, I passed | None, 45% opacity |

**Row columns:** Company/role (flex, min-width 0, truncate role) · Status pill · Match score · Action button(s)

**Row sub-note:** One line of muted text below the role — shows contextual info: match reason for new items, days elapsed for waiting items, next interview date for active conversations, closure reason for closed.

**Actions per status:**

| Status | Primary action | Secondary action |
|---|---|---|
| New match | Review & build | — |
| Worth a look | Take a look | — |
| Ready to apply | Apply ↗ | Preview |
| Waiting | — | — |
| In conversation | Open cheat sheet | — |
| Closed | — | — |

**Row click behavior:** Clicking anywhere on a row (not just the button) opens the Job Detail side panel.

**Closed rows:** Rendered at 45% opacity. Grouped at the bottom. Collapsed by default with a "Show X closed jobs" expander.

### 4.4 Page: Find New Jobs

**Purpose:** The asset generation workflow. This is the core engine of the product — where you paste a JD and get a tailored resume, cover letter, and cheat sheet back.

**Layout:** Two-column split (matching existing portfolio design exactly).
- Left column: Input form (~38% width)
- Right column: Pipeline status / output panel (~58% width)

**Left column — Input form:**

```
Field 1: Company Name
  type: text input
  placeholder: "e.g. Acme Corp"
  label: "Company name"

Field 2: Job Description
  type: textarea
  placeholder: "Paste the full job description here..."
  label: "Job description"
  min-height: 180px
  resize: vertical

CTA: "Run automation"
  type: primary button, full width
  behavior: triggers the 5-stage pipeline
  disabled state: grayed out until Company Name and Job Description are filled

Optional: Manual job add link
  type: secondary text link below the button
  label: "Or add a job manually without generating assets →"
  behavior: opens a lightweight modal (see section 4.7)

Privacy note (below button):
  "Your data is never stored. All processing is stateless and ephemeral.
  Resume and JD text is transmitted to Google Gemini API for inference only."
  font-size: var(--text-xs)
  color: var(--color-text-tertiary)
  text-align: center
```

**Right column — Pipeline status:**

Before run starts:
```
Title: "Pipeline status"
Body: "Waiting to start..."
color: var(--color-text-tertiary)
```

During run — 5 animated stages, each with a status indicator:

```
Stage 1: Evaluating fit
Stage 2: Researching company
Stage 3: Building your resume
Stage 4: Writing cover letter
Stage 5: Preparing interview cheat sheet

Each stage shows:
  - Stage name
  - Status: pending (gray dot) → running (animated blue dot) → done (green checkmark) → error (red x)
  - On completion: a one-line summary of what was found/generated
```

After successful run:
```
Score badge: "Match score: 91" (colored per score tier)
Three download buttons:
  - Download resume (PDF)
  - Download cover letter (PDF)
  - Download cheat sheet (MD)
One CTA: "Add to my pipeline →" (saves the job to All Jobs with status "Ready to apply")
```

### 4.5 Page: My Profile

**Purpose:** One-time setup. Upload resume and work experience. Set it and forget it.

**Access:** Bottom of sidebar, below the main nav items. Visually de-emphasized — smaller font, no badge.

**Layout:** Single column, centered, max-width 560px. No sidebar content needed here — this is a settings-style page.

**Sections:**

```
Section 1: Your resume
  Label: "Resume"
  Sub-label: "Used as the base for every tailored resume we generate"
  Input: Upload zone (PDF, DOCX, TXT)
  Uploaded state: Shows filename + "Uploaded Apr 10" + "Replace" link
  Required: Yes — pipeline is disabled until this is uploaded

Section 2: Detailed work experience
  Label: "Detailed work experience"
  Sub-label: "An extended master document of all your wins, projects, and metrics.
              The more detail here, the better your tailored resumes will be."
  Input: Upload zone (PDF, DOCX, TXT)
  Uploaded state: Shows filename + "Uploaded Apr 10" + "Replace" link
  Required: No — marked "(optional, but recommended)"

Save button: "Save profile"
  Only visible/active when changes have been made
  On save: brief success toast — "Profile saved"
```

**First-time onboarding gate:**

If a user opens the app and has no resume uploaded yet, show a gentle prompt on the Today view:

```
Banner (top of Today view, dismissable after upload):
  "To get started, upload your resume →"
  Clicking navigates to My Profile
  Once a resume is uploaded, banner disappears permanently
```

### 4.6 Component: Job Detail Panel

**Trigger:** Click any row in All Jobs, or any card in Today view.

**Layout:** Slides in from the right as a side panel (~480px wide). The list behind it dims slightly but remains visible. Not a full modal.

**Contents:**

```
Header:
  Company name (--text-md, --weight-semibold)
  Role title (--text-base, --color-text-secondary)
  Status pill
  Match score pill
  Close button (×) top right

Body sections:

  "About this role"
    Source URL (linked)
    Date found
    Match reason (1-2 sentences from the Gatekeeper)

  "Your application" (only shown if assets exist)
    Resume — preview thumbnail or filename + Download button
    Cover letter — preview thumbnail or filename + Download button
    Cheat sheet — filename + Open button

  "Timeline"
    Date found
    Date assets generated (if applicable)
    Date applied (if applicable)
    Interview date (if applicable)

  "Notes"
    Free-text input, auto-saves on blur
    Placeholder: "Add notes about this role, recruiter contact, compensation details..."

  "Recruiter contact" (optional fields)
    Name input
    Email input

Footer actions:
  Primary: context-sensitive (matches row action — "Apply ↗", "Open cheat sheet", etc.)
  Destructive: "Remove from pipeline" — small, text-only, bottom of panel
```

### 4.7 Component: Manual Add Job Modal

**Trigger:** "Or add a job manually" link on Find New Jobs page, or a future "Add job" button in All Jobs.

**Purpose:** Add a job to the pipeline without running the full automation — useful for roles found outside the Scout, or jobs already applied to that you want to track.

**Layout:** Centered modal, max-width 480px.

```
Fields:
  Company name (required)
  Job title (required)
  Job URL (optional)
  Status (dropdown — defaults to "Waiting to hear back" since manual = likely already applied)
    Options: New match / Ready to apply / Waiting to hear back / In conversation
  Notes (optional, textarea)

Actions:
  "Add to pipeline" (primary)
  "Cancel" (secondary)
```

---

## 5. The Pipeline: Status Definitions

These are the only statuses that exist in the system. Internal names (for the database) are included for developer reference but never appear in the UI.

| UI label | DB value | Meaning | Left accent color |
|---|---|---|---|
| New match | `new_match` | Found by Scout, scored ≥ 78, assets not yet generated | Purple |
| Worth a look | `borderline` | Scored 75–77, held for manual review | Amber |
| Ready to apply | `ready` | Assets generated, not yet applied | Blue |
| Waiting to hear back | `applied` | Applied, no response yet | None |
| In conversation | `interviewing` | Active interview process | Green |
| Offer received | `offered` | Offer extended | Green |
| Not a fit | `rejected_auto` | Fast-gated or scored < 75 | None (dimmed) |
| They passed | `rejected_them` | Company rejected | None (dimmed) |
| I passed | `rejected_me` | User declined | None (dimmed) |

---

## 6. The Asset Generation Pipeline

This is the 5-stage AI pipeline that runs when the user clicks "Run automation." Each stage is visible in the right-hand panel of the Find New Jobs view.

| Stage | Name shown in UI | What happens | Output |
|---|---|---|---|
| 1 | Evaluating fit | Gatekeeper scores the JD against the user's profile | Match score (0–100) + match reason |
| 2 | Researching company | Dual-model research (Perplexity → Gemini fallback) | Company DNA, competitors, culture |
| 3 | Building your resume | Bridge Engine tailors resume to JD | Tailored resume (PDF) |
| 4 | Writing cover letter | Drafting layer generates cover letter | Cover letter (PDF) |
| 5 | Preparing cheat sheet | Coach generates interview prep | Cheat sheet (Markdown) |

**On score < 75 at Stage 1:** Pipeline halts. Right panel shows:
```
"This role isn't a strong match (score: 62)"
One-line reason
Two options:
  "Add to pipeline anyway" (secondary button)
  "Discard" (text link)
```

**On any stage error:** That stage shows a red × and an inline error message. Remaining stages are skipped. A "Retry" button appears.

---

## 7. Data Model

### Job record

```typescript
interface Job {
  id:                  string        // UUID
  company:             string
  title:               string
  url:                 string | null
  status:              JobStatus     // see Section 5 DB values
  score:               number | null // 0-100, null if not yet evaluated
  match_reason:        string | null // 1-2 sentence summary from Gatekeeper
  source:              'scout' | 'manual' | 'automation'
  date_found:          string        // ISO date
  date_assets_built:   string | null
  date_applied:        string | null
  date_interview:      string | null
  date_closed:         string | null
  closure_reason:      string | null // "title blocklist" | "they passed" | "I passed — comp" etc.
  notes:               string | null
  recruiter_name:      string | null
  recruiter_email:     string | null
  assets: {
    resume_url:        string | null
    cover_letter_url:  string | null
    cheat_sheet_url:   string | null
    ground_truth_version: string | null // hash of workExperience doc used
  }
  silent_days:         number        // computed: days since date_applied with no status change
}
```

### User profile

```typescript
interface UserProfile {
  id:                       string
  resume_url:               string | null
  resume_filename:          string | null
  resume_uploaded_at:       string | null
  work_experience_url:      string | null
  work_experience_filename: string | null
  work_experience_uploaded_at: string | null
}
```

---

## 8. Demo Mode (Portfolio Version)

When the app is accessed without authentication, it runs in Demo Mode automatically.

### Rules for Demo Mode

- All data is seeded from a static `demo_data.json` file — no real API calls
- All write operations (status updates, notes, pipeline runs) are in-memory only — nothing persists
- A non-intrusive banner sits at the top of every page:
  ```
  "You're viewing a live demo with sample data. Sign in to use JobAgent with your own search."
  [Sign in] button (right-aligned)
  ```
- The asset generation pipeline runs a simulated replay — each stage advances on a timer, and pre-generated sample assets are returned
- The "My Profile" tab is hidden in demo mode

### Demo data set

Seed data should tell a convincing story. Suggested set:

| Company | Role | Status | Score |
|---|---|---|---|
| Stripe | PM, Developer Platform | New match | 91 |
| Notion | PM, Platform | Ready to apply | 88 |
| Vercel | PM, Platform | In conversation | 89 |
| Rippling | PM, Platform Infrastructure | Waiting to hear back | 92 |
| Figma | PM, Developer Ecosystem | Waiting to hear back | 87 |
| Datadog | Senior PM | Not a fit | — |
| Mixpanel | PM, Growth | They passed | 73 |
| Amplitude | PM, Platform | I passed | 81 |

---

## 9. Tech Stack Recommendations

| Layer | Recommendation | Rationale |
|---|---|---|
| Frontend | React + Vite | Fast iteration, component model suits the panel/modal patterns |
| Styling | Tailwind CSS | Utility-first maps cleanly to the design tokens in Section 3 |
| Backend | Firebase (Firestore + Storage) | Zero-config auth, real-time updates for pipeline status, file storage for assets |
| Auth | Firebase Auth (Google sign-in) | One-click, no password friction |
| AI pipeline | Google Gemini 2.5 Flash | Consistent with local version, fast, multimodal for PDF parsing |
| Research layer | Perplexity sonar-pro → Gemini fallback | Consistent with local version spec |
| Hosting | Firebase Hosting or Vercel | Both integrate cleanly with the stack |
| PDF generation | `@react-pdf/renderer` or Puppeteer serverless | Render resume/cover letter templates to PDF |

---

## 10. Page-by-Page Acceptance Criteria

| Page / Component | Done when... |
|---|---|
| Today view | Loads within 1.5s. Sections only render if they have content. Empty state shows if nothing needs attention. |
| All Jobs list | Search filters in real-time with no perceptible lag. Closed group is collapsed by default. Clicking a row opens the detail panel without a page navigation. |
| Find New Jobs | Pipeline stages animate sequentially. A score < 75 halts the pipeline and shows the "not a strong match" state. Completed assets are downloadable. "Add to pipeline" correctly creates a job record with status `ready`. |
| My Profile | Upload zones accept PDF, DOCX, TXT. Uploaded state persists on page refresh. Replace flow asks for confirmation before overwriting. |
| Job Detail Panel | Opens and closes with a smooth slide transition (200ms). Notes auto-save within 1s of blur. Recruiter fields are optional and collapsible. |
| Manual Add Modal | Closes on Escape key and backdrop click. Form validates required fields before submit. |
| Demo Mode | All demo data is visible without sign-in. No real API calls are made. Pipeline simulation completes in ~8 seconds with realistic stage timings. |
| Responsive | Fully functional at 1280px+ desktop. Readable (not necessarily full-featured) at tablet (768px+). |

---

## 11. Out of Scope for v1.0

- Mobile native app
- Email/calendar integration (interview reminders)
- Automated Scout (LinkedIn scraping) — v1.0 uses manual JD paste only; Scout is a v2 feature
- Auto-submission to Greenhouse/Lever
- Analytics view (response rate trends, funnel analysis) — data is captured in v1.0, visualization is v2
- Team/shared accounts
- Export to CSV

---

*[PRD END] — JobAgent Web App v1.0*
