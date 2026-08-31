---
trigger: manual
description: Six-module interview-prep research contract. Un-retired 2026-08-06, narrowly, for on-demand interview prep only -- not a general research-at-any-stage rule. See banner.
---

> **Live, narrow scope (un-retired 2026-08-06).** The standing "no web research, any stage" rule this file's retirement leaned on is no longer absolute, but this six-module packet stays scoped to its original purpose only: on-demand interview prep, invoked once a real interview is actually scheduled for a company, never at draft time. It is separate from the small cover-letter fact-finder `research-engine.py`'s `fetch_cover_letter_hook_fact()` provides during Stage 1 drafting for Tier 1 / `Reach Out` Tier 2 fits -- do not confuse the two. Run via `python scripts/research-engine.py "{company}" "{role}"` (Gemini-primary) to populate `Research_Packet.json` in the submission folder, then `generate_cheat_sheet.py` reads it to build a rich `Interview_Cheat_Sheet.md`. The pre-2026-08-06 "Retired, not active" banner (this file's state before the un-retirement) is recoverable from git history (`git log -- .agent/archive/rules/Research_Packet_Contract.md`, pre-2026-08-31 removal of `.agent/`) if ever needed for reference — not a live document any more.
>
> **Known stale line below (not reconciled by this reconstruction):** Section 2 still says the script outputs `Research_Packet.md` via Perplexity. Current live docs (`generate-submission/SKILL.md`, `research-engine.py`) describe Gemini-primary output to `Research_Packet.json` instead. This file was lost and rebuilt from `CHANGELOG.md`/`DEPRECATED.md`'s description of the banner-only change -- the six-module body below is reconstructed verbatim from the archived copy, not re-verified against the current script's actual behavior. Fix this line for real accuracy rather than trusting it as-is.

# Research Packet Contract (v2.0)

## 0) Purpose
To provide the "Strategic Fuel" for Jason Taylor's career assets. This contract defines the mandatory schema for research fetched via the Perplexity script.

## 1) Mandatory Research Modules

### Module A: The Company DNA
- **Core Mission/Values:** Stated vs. Observed.
- **Problem Space:** Plain-language explanation of the "Pain" they solve.
- **Business Model:** Revenue streams, growth stage, and current financial health.
- **Founding Story:** Key inflection points in their history.

### Module B: Market & Competitors
- **The "Big 3" Competitors:** Direct rivals and Clario/Company's differentiator.
- **Macro Trends:** Industry headwinds (e.g., regulatory shifts, AI disruption).

### Module C: Recent Intelligence (90-Day Window)
- **Financials/Funding:** Recent rounds or earnings results.
- **Organizational Shifts:** Layoffs, hiring surges, or leadership changes.
- **Product/Partnership News:** New launches or M&A activity.

### Module D: The Role & Org Chart
- **JD Analysis:** Keywords, "Hidden" success signals, and required vs. preferred.
- **Hierarchy:** Reporting lines and team structure (if findable).
- **Hiring Manager Profile:** Background, published content, and stated priorities.

### Module E: Culture & Reality Check
- **Sentiment Analysis:** Glassdoor/Reddit/Blind (Real-world vs. Advertised).
- **Operational Style:** Remote/Hybrid reality and employee tenure.

### Module F: The Intersection (The "Bridge")
- **Priority Mapping:** For every major priority found, identify a direct connection to Jason's experience (Platform, Data Integrity, Revenue Systems).

## 2) Script Output Requirements
The research script must output a structured Markdown file titled `Research_Packet.md` inside the specific `submissions/[Company]/` folder.
