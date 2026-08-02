# UI Redesign — Research Packet 01: Material Design 3 Prompting Approach

**Date:** 2026-08-01
**Status:** Reference only — not yet acted on
**Purpose:** First input toward an eventual final prompt for redesigning Applyr's UI around Material Design 3. Captures how to structure a redesign prompt (governing design language, required deliverables, token/component discipline, MUI as the React implementation layer) so later packets can build on it instead of re-deriving it.

---

## Source answer

Yes — the best way to direct your model is to give it a **design system brief plus hard constraints**, not just "make it look like Material." Material 3 is built around reusable design tokens, theme roles, and component behavior, so your prompt should explicitly force the model to use tokens, states, spacing, elevation, and accessibility rules instead of ad hoc styling. [m3.material](https://m3.material.io/foundations/design-tokens)

## Core approach

Tell the model to treat Google's Material Design 3 as the **governing design language** for your app redesign, and to map every UI decision to Material concepts like color roles, typography, shape, elevation, and component states. Material's guidance for web also emphasizes theming and accessible components, while its token system is meant to replace hardcoded values with named roles that can be reused across design and code. [m3.material](https://m3.material.io/)

A strong instruction is: "Do not invent visual patterns unless they align with Material 3 foundations and components." That matters because Material tokens are intended to be the single source of truth, with reference, system, and component token layers rather than one-off CSS values. [m3.material](https://m3.material.io/foundations/design-tokens)

## What to tell the model

Use a prompt structure like this:

```text
You are redesigning my job search application using Google Material Design 3 principles for web.

Goals:
- Redesign the app to feel modern, structured, and consistent.
- Follow Material 3 foundations for color, typography, shape, elevation, spacing, motion, and states.
- Use design tokens instead of hardcoded values whenever possible.
- Prefer reusable components and semantic styling.
- Optimize for accessibility, responsive layouts, and clear hierarchy.

Product context:
- App type: job search management app
- Primary workflows: track jobs, save postings, manage applications, resume tailoring, interview prep, follow-ups
- Users: job seekers who need high information density without clutter

Required output:
1. A design system definition
2. A screen-by-screen redesign proposal
3. Component specs
4. Design tokens
5. Implementation guidance for React/CSS/MUI
6. Rationale for every major design choice

Hard rules:
- No random gradients or decorative styles unless justified by Material 3
- Use Material 3 component patterns and interaction states
- Define color roles for light and dark mode
- Use consistent spacing and elevation
- Include empty, loading, error, success, and hover/focus/pressed states
- Prioritize accessibility and keyboard navigation
- If a pattern is not Material-aligned, explain why and propose the closest Material alternative
```

This works because Material 3 for web is explicitly framed as an adaptable system of guidelines, components, and theming, and Material's token model is meant to connect design and engineering through shared named values. [m3.material](https://m3.material.io/develop/web)

## Add app-specific constraints

For your job-search app, direct the model to redesign around the workflows that matter most, such as application tracking, status changes, saved jobs, reminders, documents, and interview prep. Material's component approach works best when the model knows which surfaces, list patterns, forms, and actions are most important, instead of trying to restyle everything generically. [mui](https://mui.com/material-ui/all-components/)

A useful constraint block would be:

- Dashboard should emphasize application pipeline, upcoming interviews, and follow-up tasks.
- Tables/lists should support scanning, filtering, sorting, and bulk actions.
- Forms should use clear validation, helper text, and step-by-step structure.
- Primary CTA should be obvious on each screen.
- Navigation should follow Material patterns for top app bar, navigation rail/drawer, tabs, and FAB only where appropriate.
- Dense data views should remain readable and not become overly spacious.

## Ask for the right deliverables

Don't just ask for "a redesign." Ask the model to return artifacts in this order:

| Deliverable | What to ask for |
|---|---|
| Audit | "Analyze my current app and identify where it violates Material 3 principles." [m3.material](https://m3.material.io/develop/web) |
| IA | "Propose a revised information architecture and navigation model using Material-style hierarchy." [m3.material](https://m3.material.io/develop/web) |
| Tokens | "Define reference, system, and component tokens for color, type, shape, and elevation." [m3.material](https://m3.material.io/foundations/design-tokens) |
| Components | "Map each feature to Material components or close equivalents." [mui](https://mui.com/material-ui/all-components/) |
| Screens | "Create annotated wireframes for dashboard, job detail, pipeline board, resume tracker, and interview prep views." [m3.material](https://m3.material.io/develop/web) |
| Build plan | "Generate implementation guidance using MUI or Material Web patterns." [m3.material](https://m3.material.io/) |

This makes the model produce something structured enough for design and engineering handoff, which is one of the main benefits of the Material token system. [m3.material](https://m3.material.io/foundations/design-tokens)

## Best implementation direction

If your app is in React, the most practical instruction is to use **MUI** as the implementation layer, because MUI explicitly provides React components based on Material Design guidelines. Google's own Material Web library for web is currently in maintenance mode, and the Material 3 expressive direction is not implemented on web there, so MUI is usually the safer path for an actively developed app. [mui](https://mui.com/material-ui/getting-started/)

You can tell the model:

```text
Implementation target:
- React app
- Use MUI as the primary component library
- Create a centralized theme object
- Map Material tokens into theme tokens
- Avoid direct hex values in component files
- Prefer sx/theme overrides or design-token-based styling
```

That aligns with Material's token guidance and MUI's role as a Material-based production component library. [mui](https://mui.com/material-ui/getting-started/)

## Example master prompt

```text
Act as a senior product designer and front-end architect.

I want to redesign my job search application using Google Material Design 3 for web. The app helps users save jobs, track application stages, manage resumes, prepare for interviews, and follow up on opportunities.

Your task:
- Redesign the app using Material 3 principles
- Use Material design tokens and semantic roles instead of hardcoded styles
- Keep the product clean, professional, and information-dense
- Optimize for accessibility, responsiveness, and clear workflow progression

Produce the output in these sections:
1. Current UX/UI issues likely to exist in a non-Material app
2. Material 3 design principles that should govern this redesign
3. Information architecture and navigation recommendations
4. Design tokens:
   - color roles
   - typography scale
   - spacing scale
   - shape/radius
   - elevation
   - motion/state behavior
5. Screen redesigns for:
   - dashboard
   - job listings
   - job detail
   - application tracker
   - resume manager
   - interview prep
   - settings
6. Component mapping:
   - app bar
   - navigation rail/drawer
   - cards
   - filters
   - data table
   - dialogs
   - snackbars
   - buttons
   - chips
   - tabs
   - text fields
7. Light and dark theme guidance
8. MUI implementation plan in React
9. Example theme object and component usage rules

Rules:
- Follow Material 3 closely
- Explain where each recommendation maps to Material foundations or components
- Use tokens, not arbitrary values
- Include hover, focus, pressed, disabled, error, loading, and empty states
- If a workflow needs deviation from standard Material patterns, explain why
```

---

## Open thread for next packet

Model offered to turn this into a Claude/GPT-ready redesign prompt tailored to Applyr's actual screens and features — not yet done. Next packet should pull in Applyr's real screen inventory (dashboard, job detail, pipeline board, resume manager, interview prep, settings) before drafting the final prompt, rather than working from the generic workflow list above.
