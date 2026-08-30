# Design System Document: Applyr

> **Staleness notice (2026-08-28):** Section 2's palette description ("sage greens,
> muted terracotta, warm stone neutrals") and its hex values, and the matching hex
> values quoted in Sections 4 and 5, describe a palette that was replaced on
> 2026-08-02 (see `src/index.css`'s own dated comments — light mode moved to an
> indigo/cyan system, dark mode to coral/teal). `src/index.css` is the real source
> of truth for every color/radius/spacing token; treat any hex value in this
> document as illustrative of the *philosophy*, not a literal current value,
> until those sections get a full pass. Section 7 (added the same day) is
> already written against the real tokens.

## 1. Overview & Creative North Star
**Creative North Star: "Applyr — The Strategic Pipeline"**

Job hunting is inherently high-stress. This design system rejects the frantic, "hustle-culture" dashboard aesthetic in favor of a serene, editorial experience. We are not building a database; we are building a high-impact mission control for your career. 

To achieve this, we move beyond the "template" look by embracing **Intentional Asymmetry** and **Soft Minimalism**. By utilizing generous whitespace and shifting away from rigid containers, we allow the user’s focus to breathe. The system leverages a "High-End Editorial" feel where typography carries the weight of the brand, and UI elements exist as soft, physical layers rather than flat digital boxes.

---

## 2. Colors & Surface Philosophy

The palette is rooted in nature—sage greens (`primary`), muted terracotta (`secondary`), and warm stone neutrals (`surface`). 

### The "No-Line" Rule — superseded 2026-08-28, see §7.2
**Original instruction (kept for history, no longer the live rule):** traditional 1px solid
borders were prohibited for sectioning or defining layout boundaries; structure was meant to
come from background-color shifts alone. That was never fully true in practice — the shared
`.editorial-shadow` class (`src/index.css`) carried a border from 2026-08-02 until this pass,
because a shadow alone at the time measured ~1.05:1 contrast against the page background
(effectively invisible). §7.2 below is the live rule now: Material Design 3's Elevated/Outlined
split (shadow OR border, never both on the same element) — implemented app-wide as of this
pass, with a real two-layer elevation shadow replacing the old single faint one so Elevated
surfaces no longer need a border to read.

Background-color shifts are still the *preferred* way to imply structure where a shadow isn't
otherwise needed (e.g. a `surface-container-low` sidebar sitting against a `surface` main
content area) — that part of the original instruction stands.

### Surface Hierarchy & Nesting
Treat the UI as a series of stacked sheets of fine paper. 
- **Base Layer:** `surface` (#faf9f6) or `surface-container-lowest` (#ffffff).
- **Secondary Grouping:** `surface-container-low` (#f4f4f0).
- **High-Focus Elements:** `surface-container-high` (#e8e9e4).

### The "Glass & Gradient" Rule
To add soul to the interface, avoid flat-fill primary buttons. 
- **Signature Gradients:** Use a subtle linear gradient from `primary` (#526452) to `primary_dim` (#465746) for main CTAs to create a soft, tactile depth.
- **Glassmorphism:** For floating navigation or modal overlays, use a semi-transparent `surface_container_lowest` with a `24px` backdrop blur. This allows the warm neutrals of the background to bleed through, softening the visual impact.

---

## 3. Typography

The system uses a pairing of **Manrope** for expressive, high-contrast headings and **Inter** for functional, high-legibility data.

*   **Display (Manrope):** `display-lg` (3.5rem) through `display-sm` (2.25rem). Use these for welcome headers or major milestones (e.g., "3 Applications Pending"). These should feel authoritative yet approachable.
*   **Headline (Manrope):** `headline-lg` (2rem) to `headline-sm` (1.5rem). Use these for section titles.
*   **Title (Inter):** `title-lg` (1.375rem) to `title-sm` (1rem). Used for card titles and sub-headings.
*   **Body (Inter):** `body-lg` (1rem) for general reading; `body-md` (0.875rem) for metadata.
*   **Label (Inter):** `label-md` (0.75rem). Used for tags and tiny button text. Always set with a slight letter-spacing (0.02em) to ensure clarity.

**Editorial Logic:** Use `on_surface_variant` (#5d605c) for body text to reduce the harsh contrast of pure black, further easing eye strain.

---

## 4. Elevation & Depth

### Tonal Layering
Depth is achieved by "stacking" surface tiers. Place a `surface-container-lowest` card on a `surface-container-low` section to create a natural, soft lift.

### Ambient Shadows
Shadows must be "ghostly" and organic.
- **Value:** `0px 12px 32px rgba(48, 51, 48, 0.06)`.
- **Logic:** The shadow is a tinted version of the `on-surface` color (#303330) at very low opacity, mimicking natural light hitting textured paper.

### The "Ghost Border" Fallback
If a border is required for accessibility (e.g., in a high-density table), use the `outline_variant` (#b0b3ae) at **15% opacity**. Never use a 100% opaque border.

---

## 5. Components

### Buttons
- **Primary:** Rounded `md` (0.75rem). Gradient fill (`primary` to `primary_dim`). White text (`on_primary`).
- **Secondary:** Surface-colored with a `surface-tint` (#526452) text. No border; use a `surface-container-highest` background on hover.
- **Floating Action Button (FAB):** Use `secondary` (#8b4f3a) for high-contrast actions like "Add New Job."

### Cards (The "Application" Card)
- **Styling:** No borders. `md` (0.75rem) or `lg` (1rem) corner radius. 
- **Separation:** Forbid the use of divider lines. Separate the "Company Name" from the "Salary" using vertical whitespace (24px) or a soft tonal background shift in the footer of the card using `surface-container-highest`.

### Input Fields
- **Background:** `surface-container-low`.
- **Active State:** Change background to `surface-container-lowest` and apply a "Ghost Border" of `primary` at 20% opacity. This creates a "glow" effect rather than a harsh outline.

### Status Chips
- **Applied:** Background `primary_container`; Text `on_primary_container`.
- **Interviewing:** Background `secondary_container`; Text `on_secondary_container`.
- **Rejected/Closed:** Background `surface_variant`; Text `on_surface_variant`.

### Document Editor Workspace
- **Layout:** A balanced dual-pane split-screen. The left side houses the compiled PDF preview using the browser's native engine inside an iframe. The right side contains the rich text editor.
- **Visuals:** Follows the "No-Line" Rule. Pane separation is done with a subtle shift from `surface-container-lowest` on the left to `surface-container-low` on the right.
- **The AI Panel:** A soft, high-focus container using `surface-container-high` with a semi-transparent background to isolate AI prompts from manual word processing.

### Dashboard Pipeline Paradigm
The dashboard enforces a strict separation between pipeline jobs and active applications:
- **Ready to Apply:** The pre-submission pipeline. Displays `New` (unseen, with a primary badge) and `Backlog` (seen) jobs that have PDF assets ready. Prompts actionable next steps. `Drafted` jobs (assets generating) remain hidden to avoid clutter.
- **Active Applications:** The engagement tracker. Displays `Applied`, `Recruiter Screen`, `Core Interviews`, and `Offer and Negotiation` statuses. Focuses on jobs waiting for external response.

---

## 6. Do's and Don'ts

### Do
- **Do** use asymmetrical layouts. For example, align your main heading to the left but place your "Quick Stats" in a floating container on the right with different vertical padding.
- **Do** use "Negative Space" as a functional tool. If a screen feels busy, increase the padding between sections rather than adding lines.
- **Do** use the `secondary` terracotta palette sparingly for "Life-affirming" actions (e.g., getting an offer, saving a dream job).

### Don't
- **Don't** use pure black (#000000). Use `on_surface`.
- **Don't** use standard 4px "Material" corners. Use the `md` (12px) or `lg` (16px) tokens to keep the experience feeling "soft" and approachable.
- **Don't** use hard dividers. If you feel the need to separate two pieces of content, use a 32px or 48px gap instead.
- **Don't** use "Alert Red" for errors unless critical. Use `error` which is a muted, sophisticated red that conveys urgency without causing panic.

---

## 7. Material Design 3 Consistency Rules (added 2026-08-28)

Applyr's tokens (`src/index.css`) were already named after Material Design 3's real role
system (`surface-container-lowest/low/high/highest`, `on-primary-container`, `outline-variant`
— these are MD3's actual token names, not a loose analogy). Sections 1-6 above then diverged
from MD3's own structural conventions in specific, sometimes undocumented ways. As we build
out a wider suite of screens/components, this section is the enforced standard for keeping
new work consistent with itself and with the Material Design 3 system these tokens came from.
**Where this section conflicts with Sections 2-6 above, this section wins.**

### 7.1 Elevation — five real surface tiers, not three

Applyr already implements MD3's actual 5-tier elevation model (most apps that borrow MD3
naming simplify to 2-3 tiers; this one didn't). Keep using it as-is — this is the strongest
existing point of MD3 alignment in the codebase, not something to "fix":

| Tier | Token | Used for |
|---|---|---|
| Canvas | `surface` | Page background only |
| 1 | `surface-container-lowest` | Resting cards, the sidebar's brand row |
| 2 | `surface-container-low` | Secondary grouping (inputs, nested sections) |
| 3 | `surface-container` | Default component fill |
| 4 | `surface-container-high` | High-focus / hover states |
| 5 | `surface-container-highest` | Rare — reserved for the most emphasized nested element on a screen |
| Inverse | `inverse-surface` | Tooltips, the Job Search pipeline log console (dark-on-light UI, deliberately inverted) |

**Rule:** two persistent elements at the same conceptual level share the same tier token. Don't
hand-pick an adjacent shade because it "looks right" — if the sidebar and a docked bar are both
top-level chrome, they use the same tier.

### 7.2 Borders vs. shadows — Elevated or Outlined, never both

**Rule going forward:** an **Elevated** surface uses shadow only, zero border. An **Outlined**
surface uses border only, zero shadow. This is Material Design 3's actual Card taxonomy
(Elevated Card vs. Outlined Card), not a stricter house invention.

- **Elevated** — floating/liftable content: the Dashboard's bento cards, the Next Interview
  card, modals (`DocumentEditor`), dropdowns.
- **Outlined** — dense/structural containers that sit flush with their surroundings: table
  rows, list rows (Opportunities groups), Settings cards, the sidebar's border.

**Implemented 2026-08-28.** `.editorial-shadow` and `.card-applyr` (`src/index.css`) combined
both from 2026-08-02 through this pass — not an oversight, the original CSS comment documented
why: the shadow alone measured ~1.05:1 contrast against the canvas (i.e. imperceptible), so a
border was added to actually create separation. The fix was the shadow itself, not a
compromise: `.editorial-shadow`/`.card-applyr` now use a real two-layer MD3-style elevation
shadow (a tight "contact" layer + a soft "ambient" layer, both meaningfully higher-alpha than
the original single 6%-opacity shadow) that reads on its own with zero border. Every call site
across the app was individually reclassified as Elevated (`.editorial-shadow`) or Outlined
(new `.outlined-surface` class, border only) per the table above — see the code for the
per-component call:

- **Elevated** (shadow, no border): Dashboard bento cards, the Next Interview / Needs
  Attention / Stats Grid tiles, `JobDetailPanel`'s slide-out panel, `NotificationPanel`'s
  dropdown, the Job Search pipeline log console.
- **Outlined** (border, no shadow): the top header bar (`border-b` only, not a full
  `.outlined-surface` border — a docked bar only needs the one edge), Opportunities'
  job-row list and filter pills, Tuning Log's feedback-record rows, Job Search's form/settings
  panels, the Dashboard's own "Ready to Apply" / "Active Opportunities" / "Upcoming Interviews"
  repeated list items (kept consistent with Opportunities' list-row treatment rather than the
  bento cards on the same page, since they're the same repeated-item pattern).

Verified live against the running dev server (computed `box-shadow`/`border-width`, both
themes) — Elevated elements show `border-width: 0px` with the new two-layer shadow, Outlined
elements show `box-shadow: none` with a real 1px border. Don't copy the border+shadow combo
into new components — pick Elevated or Outlined per §7.2's table above.

### 7.3 8pt spatial grid

Tailwind's spacing scale is 4px-stepped; treat 4/8 as Applyr's real grid (stricter than a
multiples-of-8-only rule). Half-steps (2px via `-0.5`, 6px via `-1.5`, 10px via `-2.5`, 14px
via `-3.5`) already appear throughout — badge dots, compact icon buttons, tight chip padding —
and are fine for small decorative elements. New **layout-level** padding/margin/gap (section
spacing, card padding, gaps between siblings) should land on 4/8/12/16/24/32/48/64, matching
what's already standard: `space-y-8`, `gap-8`, `p-8`, `rounded-[2rem]` bento cards.

### 7.4 Touch targets — 40px interactive, 36px icon-only floor

Matches MD3's own accessibility guidance. Applyr's real icon buttons mostly clear this:
`w-10 h-10` (40px) is the standard for primary actions (download, mark-applied, external
link — see `TodayView.tsx`). `w-9 h-9` (36px) is used for the avatar and notification bell —
right at the floor, don't shrink further.

**Known violation:** [`JobDetailPanel.tsx:476`](../src/components/JobDetailPanel.tsx#L476) —
the "Edit applied date" icon button is `w-8 h-8` (32px), below the 36px icon-only floor. It's
a real click target (opens a date picker), not decorative, so it doesn't qualify for the
decorative-icon exemption below. Small fix, flagged for the cleanup backlog rather than done
here.

**Exemption:** purely decorative icon containers with no `onClick` (toast icons, section
badge circles) may go below 36px — the floor only applies to actual interactive elements.

### 7.5 Typography zones — two typefaces, already correctly split

Manrope (`--font-headline`, applied via `.font-headline` and bare `h1`/`h2`/`h3`) for section
titles, page headers, and card headlines. Inter (`--font-body`) for everything else — body
copy, labels, buttons, inputs, badges, chips. This already matches MD3/editorial practice
(a distinct display face reserved for headings, a workhorse UI face for everything else).
**Rule:** new components' headings get `.font-headline`; don't introduce a third typeface, and
don't apply Manrope to interactive/control text (buttons, inputs, nav) even if it "looks nice"
on a specific screen — that zone is reserved for Inter across the whole app.

### 7.6 Color-role budget — one accent, three uses

Primary (`#3B5FE0` indigo / `#D97757` coral in dark mode) is the one true accent. Its three
sanctioned uses:
1. Primary CTA fill (`.btn-primary`'s gradient)
2. Active nav state (`Sidebar.tsx`'s `bg-sidebar-active`, which resolves to `--color-primary`)
3. One emphasized metric per screen (e.g. a fit score above threshold, `TodayView.tsx`'s
   `job.score >= tier1Floor` check)

Secondary (cyan/teal) is reserved for a small number of genuinely secondary actions — today
that's the "Check Gmail Now" button and count badges. Keep it that scarce. A new screen
reaching for secondary as a second general-purpose brand color, rather than for one of these
specific roles, is a violation even if it "matches" — grep the primary/secondary hex counts
before adding a new use.

**Reviewed, not retrofitted (2026-08-28):** the shipped app already uses primary well beyond
these three roles (download/link icon buttons, score highlights, hover states throughout).
This rule is guidance for new work going forward, not a cleanup target — re-coloring every
existing icon button to hit a strict 3-use budget would touch dozens of already-fine
components for a largely aspirational rule. Don't treat existing primary-colored icon buttons
as violations; do hold new components to the budget above.

### 7.7 Semantic colors are status, not style

Success (green) / warning (amber) / error (red) map to a real system state the user needs to
notice, never to decoration. Applyr already gets this mostly right, with one rule worth
calling out explicitly because it's easy to get backwards: **job-pipeline outcomes are not
system errors.** `Rejected`/`Closed` jobs deliberately render in the same neutral slate as
`Backlog` (see `--color-status-closed-*` in `src/index.css` and `StatusChip.tsx`) — a closed
application is a status, not a failure, so it never gets error-red. Error red is reserved for
actual system/API failures (a failed sync, a broken connector). If a new feature needs to show
"this didn't work out," reach for the neutral/warning slate the job pipeline already uses, not
red — red is a scarcer signal here than the generic MD3 default would suggest.

### 7.8 Audit checklist

Before merging a new component, or when reviewing an existing screen for consistency:

1. **Elevation** — does every persistent-chrome element at the same conceptual level share
   one surface tier? (§7.1)
2. **Border vs. shadow** — is this Elevated (shadow only) or Outlined (border only)? If it's
   neither and combines both, is it `.editorial-shadow`/`.card-applyr` (the one approved
   exception) or a new violation? (§7.2)
3. **Grid** — do new layout-level spacing values land on 4/8/12/16/24/32/48/64? (§7.3)
4. **Touch targets** — is every real interactive element ≥40px (≥36px if icon-only)? (§7.4)
5. **Typography** — is Manrope reserved for headings only, Inter for everything else? (§7.5)
6. **Accent budget** — does primary appear only as CTA fill / active nav / one emphasized
   metric? Is secondary still scarce? (§7.6)
7. **Semantic color** — does every success/warning/error use map to a real system state, and
   does a job-pipeline outcome correctly avoid error-red? (§7.7)

### 7.9 Known violations (cleanup backlog)

- ~~`.editorial-shadow` / `.card-applyr` combine border + shadow~~ — **fixed 2026-08-28**,
  see §7.2.
- ~~`JobDetailPanel.tsx:476` — "Edit applied date" icon button below the 36px touch-target
  floor~~ — **fixed 2026-08-28**, along with every other icon-only control below 36px found
  in the same sweep (§7.4).

Nothing currently outstanding from this pass. §7.6 (accent color budget) was reviewed but
deliberately not retrofitted — see §7.6's own note; it's guidance for new work, not a backlog
item, since enforcing it retroactively would mean re-coloring dozens of already-fine icon
buttons across the app for a largely aspirational rule.