# Portfolio Site Audit — Implementation Plan & Handoff

```yaml
document_type: implementation_handoff
created: 2026-06-10
status: phases_1_through_5_complete
session_context: Phases 1-5 fully implemented and visually verified. Phase 6 (voice/copy audit + fact check) is next session.
```

---

## Project Overview

Full copy audit and rewrite of Jason's portfolio website (taylormade.me). Goal: convert a site that reads like an engineering pitch into one that converts recruiters into calls, with flexible copy that works for both B2B PM roles (current need) and consumer-adjacent roles (long-term goal).

**Portfolio site source code:**
`C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Portfolio Website\src\`

**Key pages to edit:**
- `pages/Home.jsx` — hero, metrics cards, project cards, CTA
- `pages/About.jsx` — opening, philosophy, sidebar
- `pages/Work.jsx` — page title, project cards, capability matrix
- `pages/WorkHistory.jsx` — career narrative, Sterkly entry, Zero To Sixty entry
- `pages/Contact.jsx` — headline and body
- `pages/Resume.jsx` — professional summary

---

## Essential Context Files (read these before starting)

**Voice profile:**
`C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\My Voice Writer\SKILL.md`
Full voice spec with examples. Key rules: conversational and direct, no em-dashes, no AI transitions ("Furthermore", "Additionally"), preserve "I think" / "I feel like", no formalization. The WorkHistory career narrative is the best existing example of his voice on the site.

**Source of truth for career facts/metrics:**
`C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Applyr\data\workExperience.md`
All approved accomplishments (ACC-*), verified metrics (MET-*), and vocabulary map (VOC-*). NEVER invent facts not in this file.

**Positioning notes (evolving):**
`C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Applyr\data\thinking\positioning_notes.md`

**Product philosophy:**
`C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Applyr\data\thinking\product_philosophy.md`

**Sterkly NDA context:**
`C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Applyr\data\thinking\project_sterkly_context.md` *(or see memory)*

---

## Core Positioning (do not drift from this)

**Identity:** "PM who makes sure customers are heard in technical rooms, then makes sure what gets built actually solves their problem."

**Three-act arc:**
1. Zero To Sixty Media (2017–2019) — internal tooling, ops automation
2. Sterkly Services (2019–2021) — B2C consumer software, macOS + Safari extensions
3. Cision (2021–2026) — B2B enterprise platform, $40M ARR, 3,500 accounts

**Targeting:** IC PM only. No Director/VP/leadership. B2C is the goal; B2B is the immediate need. Flexible copy — not one locked statement.

**Critical language rules:**
- NEVER say "platform leader", "product leadership role", or "leadership role" — implies Director+
- NEVER say "global scale" — Cision was $40M ARR / 3,500 accounts, not global scale
- NEVER say "deeply technical PM" — technically literate, not deeply technical
- NEVER use internal codenames (GPOD, UCP, Nexus/EDP) — use plain-language equivalents from VOC-* map

---

## What's Done

### Phase 1 — Critical fixes ✅
All four "leadership role" instances replaced with "PM role" or "product role":
- `Home.jsx` CTA: "Looking for your next PM?"
- `About.jsx` philosophy close: "product role"
- `Contact.jsx` headline: "Let's talk about a PM role."
- `Contact.jsx` body: rewritten without "leadership" language

`About.jsx` sidebar: "Senior Product Manager • Cision" → "Product Manager • Cision" ✅

`Resume.jsx`: Internal codenames replaced:
- "GPOD" → "source-of-truth database"
- "GPOD, UCP" → "upstream content monitoring and contact database systems"
- "Nexus/EDP" → "enterprise-wide data unification initiatives" ✅

`workExperience.md`: Sterkly NDA note corrected — Airo is safe to name ✅

### Phase 2 — Hero rewrite ✅
`Home.jsx` hero section updated:
- **Tagline:** "Product Manager — B2B Platform · Consumer Software · 8 Years"
- **H1:** "Keep customers successful. / Ship what actually matters."
- **Sub-headline:** Three-act arc in three sentences, customer-first framing, Sterkly named

### Phase 3 — About page full rewrite ✅
`About.jsx` fully rewritten:
- **H1:** "I keep the customer in the room. / Then I make sure it ships."
- **Intro:** Three-act arc (Zero To Sixty → Sterkly → Cision), 8 years framing
- **Philosophy:** Opportunity solution tree, build trap, technically literate but not deeply technical
- **Human detail:** LLM tools paragraph ("when you're both the PM and the user")
- **Looking for:** IC PM, consumer or consumer-adjacent, explicitly not Director/VP
- **Sidebar tags:** "Consumer" added alongside SaaS, B2B, Enterprise

### Phase 4 — Work page and Sterkly visibility ✅
`Work.jsx`:
- H1: "Selected Work" (removed "Systems & Platform Engineering")
- Description: rewritten to 8-year breadth framing
- Consumer Software section added with Sterkly card (Airo + Safari extensions, $1M–$3M / ~$100/cert / 3 countries metrics)
- KinBridge: corrected to voice messaging + LLM letter generation pipeline (ElevenLabs), tags updated to Voice AI / LLM Pipeline / Social Impact
- Capability matrix: SQL and ETL downgraded from "Expert" to "Working Knowledge"

`WorkHistory.jsx`:
- Sterkly role title: "Product Owner → Product Manager"
- Sterkly entry: full three-paragraph rewrite (consumer software context, certificate bottleneck fix, QA/distributed team)
- Career Narrative: third paragraph added acknowledging consumer chapter and forward intent
- Footer CTA: "Need the Technical Specifications?" → "Want the condensed version?"

### Phase 5 — Content accuracy and polish ✅
- `Contact.jsx` message placeholder: "How can I help you scale?" → "Tell me about the role."
- `Resume.jsx` section title: removed "(B2B SaaS)", now "Product Manager – Platform & Revenue Systems"
- `Resume.jsx` summary: "6+ years" → "8 years", opening acknowledges consumer + enterprise breadth
- `Resume.jsx` Sterkly role: "Product Manager" → "Product Owner / Product Manager", body replaced with real Sterkly story

---

## What Remains

### Phase 6 — Voice/copy audit + fact check (NEXT SESSION)

**What to do:**
Two passes over all rewritten copy across all six pages.

**Pass 1 — Voice audit (against `SKILL.md`):**
Check every new paragraph written in Phases 2–5 for:
- Em-dashes (strong AI tell — none should appear)
- AI transition words: "Furthermore", "Additionally", "Moreover", "In conclusion", "It is worth noting"
- Sycophantic openers or closers Jason wouldn't write
- Copy that sounds more formal than his voice (test: would Jason say this to a colleague?)
- Over-structured phrasing that sounds like a press release

Pages to audit: `Home.jsx`, `About.jsx`, `Work.jsx`, `WorkHistory.jsx`, `Contact.jsx`, `Resume.jsx`

**Pass 2 — Fact check (against `workExperience.md`):**
Every metric and claim in the new copy must trace to an ACC-* or MET-* ID.
Specific things to verify:
- "$40M ARR" — MET-01 ✓
- "3,500 accounts" — MET-02 ✓
- "8 years" — confirmed (June 2017–Jan 2026)
- "$1M–$3M revenue sustained" (Sterkly) — MET-13 (estimated, flag if stated as verified)
- "~$100 per certificate" — MET-14 ✓
- "3 countries" (Sterkly QA) — ACC-204 ✓ (Canada, US, offshore)
- "700 accounts" (migration) — MET-10 ✓
- "90% of 300-item security backlog" — MET-08 ✓
- "~$100 saved per certificate" in Work.jsx Sterkly card — MET-14 ✓
- KinBridge description (ElevenLabs + LLM pipeline) — no ACC-* for this, it's an independent project; confirm the description matches what was actually built
- Any claim not in workExperience.md that slipped through

**Key guardrails to re-check:**
- NEVER "global scale" — Cision was $40M ARR / 3,500 accounts
- NEVER "deeply technical PM" — removed in Phase 3, confirm it's gone everywhere
- NEVER internal codenames (GPOD, UCP, Nexus/EDP) — scan all files
- NEVER "leadership role" language — scan for "leader", "leadership"

**Files to read before starting:**
- `My Voice Writer/SKILL.md` — voice spec
- `Applyr/data/workExperience.md` — source of truth for all facts/metrics
- `Applyr/data/thinking/portfolio_site_audit_plan.md` — this file

---

*(Phases 3–5 detail sections removed — all completed. See "What's Done" above.)*

---

## Decisions Already Made (don't re-litigate)

| Decision | Rationale |
|---|---|
| One flexible positioning, not one locked statement | Jason confirmed — used contextually |
| Lead with customer voice, not B2C aspiration | Not enough consumer proof points to win those roles outright |
| "8 years" as experience framing | Includes Zero To Sixty (2017–2019 account manager/PO role) |
| Sterkly named by company, Airo named by product | Both fine; NDA covers data practices only |
| Safari extensions described as "ad tech" | Accurate, avoids NDA territory |
| Hero H1: "Keep customers successful. Ship what actually matters." | Jason approved |

---

## Style Rules for All New Copy

From `SKILL.md` voice profile:
- No em-dashes (—) — strong AI writing tell
- No "Furthermore", "Additionally", "In conclusion", "Moreover"
- Keep "I think" / "I feel like" — intentional opinion signals
- Keep directness: "I don't like this" not "this may warrant reconsideration"
- No sycophantic openers or AI-sounding closers
- Conversational but intelligent — explains a complex ETL pipeline the same way he'd explain picking a car
- Short punchy sentences alongside longer ones — mix is natural to him
