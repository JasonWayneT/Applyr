# Design System Document: The Mindful Pursuit

## 1. Overview & Creative North Star
**Creative North Star: "The Curated Sanctuary"**

Job hunting is inherently high-stress. This design system rejects the frantic, "hustle-culture" dashboard aesthetic in favor of a serene, editorial experience. We are not building a database; we are building a sanctuary. 

To achieve this, we move beyond the "template" look by embracing **Intentional Asymmetry** and **Soft Minimalism**. By utilizing generous whitespace and shifting away from rigid containers, we allow the user’s focus to breathe. The system leverages a "High-End Editorial" feel where typography carries the weight of the brand, and UI elements exist as soft, physical layers rather than flat digital boxes.

---

## 2. Colors & Surface Philosophy

The palette is rooted in nature—sage greens (`primary`), muted terracotta (`secondary`), and warm stone neutrals (`surface`). 

### The "No-Line" Rule
**Explicit Instruction:** Traditional 1px solid borders are prohibited for sectioning or defining layout boundaries. 
Structure is created through **Background Color Shifts**. For example, a `surface-container-low` sidebar should sit directly against a `surface` main content area. The eye perceives the edge through the shift in tone, creating a sophisticated, "borderless" interface.

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

---

## 6. Do's and Don'ts

### Do
- **Do** use asymmetrical layouts. For example, align your main heading to the left but place your "Quick Stats" in a floating container on the right with different vertical padding.
- **Do** use "Negative Space" as a functional tool. If a screen feels busy, increase the padding between sections rather than adding lines.
- **Do** use the `secondary` terracotta palette sparingly for "Life-affirming" actions (e.g., getting an offer, saving a dream job).

### Don't
- **Don't** use pure black (#000000). Use `on_surface` (#303330).
- **Don't** use standard 4px "Material" corners. Use the `md` (12px) or `lg` (16px) tokens to keep the experience feeling "soft" and approachable.
- **Don't** use hard dividers. If you feel the need to separate two pieces of content, use a 32px or 48px gap instead.
- **Don't** use "Alert Red" for errors unless critical. Use `error` (#a73b21) which is a muted, sophisticated clay-red that conveys urgency without causing panic.