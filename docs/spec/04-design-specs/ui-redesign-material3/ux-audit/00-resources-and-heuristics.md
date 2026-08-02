# UX Audit — Resources & Heuristics (Locked In)

**Date:** 2026-08-01
**Purpose:** The fixed checklist this audit pass scores Applyr's screens against. Sits upstream of the Material 3 redesign (`01-research-packet.md`) — this is usability/UX, not visual design system work.

---

## Primary source: Steve Krug, *Don't Make Me Think, Revisited*

Core principles this audit applies:

1. **Don't make me think.** Every screen/element should be self-evident — a user shouldn't have to expend effort figuring out what something is or does.
2. **It doesn't matter how many times I have to click, as long as each click is a mindless, unambiguous choice.** Click cost isn't the enemy — ambiguity is.
3. **Get rid of half the words on each page, then get rid of half of what's left.** Ruthless clarity over completeness.
4. **Users don't read, they scan.** Design for scanning: clear visual hierarchy, conventional layout, obvious clickability.
5. **Users satisfice, they don't optimize.** People pick the first reasonable option, not the best one — so the "reasonable" option should be the right one.
6. **Navigation should answer, at every point: Where am I? Where can I go? How do I get back?**
7. **The "trunk test"** — could a user land on any single screen out of context and immediately tell what site/app this is, what page they're on, and what the major sections are?

## Krug's own primary-source materials (sensible.com)

- [Usability Testing Checklists](https://sensible.com/downloads/checklists.pdf) — Krug's actual prep/session checklists from *Rocket Surgery Made Easy*. The most direct "lock in" artifact if Jason ever wants to run real moderated tests on Applyr later.
- [Usability Test Script — Websites](https://sensible.com/downloads/test-script-web.pdf) — reusable script template for structuring a usability test session.
- [Downloads index](https://sensible.com/download-files/) — full list of Krug's public checklists/scripts.

## Complementary source: Nielsen Norman Group's 10 Usability Heuristics

Krug's rules are deliberately minimal and were written for marketing-style websites. Applyr is a working application (dashboard, filters, forms, panels), so this audit pairs Krug with NN/g's heuristics for a fuller evaluation lens:

- [10 Usability Heuristics for User Interface Design](https://www.nngroup.com/articles/ten-usability-heuristics/) — the canonical 10: visibility of system status, match between system and real world, user control and freedom, consistency and standards, error prevention, recognition rather than recall, flexibility and efficiency of use, aesthetic and minimalist design, help users recognize/diagnose/recover from errors, help and documentation.
- [10 Usability Heuristics Applied to Complex Applications](https://www.nngroup.com/articles/usability-heuristics-complex-applications/) — same heuristics, but calibrated for dense/dashboard-style apps rather than simple sites, which is the closer match to Applyr's actual screens (filters, status pipelines, data tables).

---

## How this audit scores each screen

For each of Applyr's screens (see `01-screen-inventory.md`), the audit stage will check:

- **Krug pass:** self-evident purpose, scannability, navigation orientation (where am I / where can I go / how do I get back), click-cost vs. ambiguity.
- **NN/g pass:** the 10 heuristics, weighted toward the complex-application variants (status visibility, error prevention/recovery, recognition over recall, minimalist density).

Findings land in `02-findings.md` as a per-screen punch list, not fixes — this stage is diagnosis only, per Jason's scoping (UX first, Material 3 redesign later).
