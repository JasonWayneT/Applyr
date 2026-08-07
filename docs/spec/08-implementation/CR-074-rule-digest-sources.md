# CR-074 Epic 4 — Rule Digest Source Decisions

**Date:** 2026-08-06  
**Status:** Decided  
**Related:** [CR-074 epics](./CR-074-token-conscious-authoring-packet-epics.md)

The digest (`data/authoring_rule_digest.md`) is the lean authoring-rule reference a cloud author loads
instead of the full `agent_context_pack.md`. Target: ≤ 2k tokens (~8k chars). Hard ceiling: 10k chars.

---

## INCLUDED

| Topic | What to include |
|---|---|
| Resume structure | Exact section header order; `## PROFESSIONAL SUMMARY` literal heading; exactly 3 summary sentences; 1-page hard rule; all 3 canonical roles present (Cision, Sterkly, Zero To Sixty) |
| Resume bullet rules | JD-relevance is the primary ordering signal; ~2–3 lines per bullet; lead with the number when a hard metric is present; 5–6 bullets on most-recent role, 2–3 on earlier roles |
| Cover letter structure | Name/contact header → `Dear Hiring Manager,` → body paragraphs → `Best regards,` → Name; 250–400 words; no bullet points |
| Cover letter argument | Argue fit only; no gap-confession language; no workforce-reduction framing anywhere in the letter |
| Forbidden formatting | Em dash (—), semicolon (`;`), colon-as-elaboration (`word: word` prose pattern); double-hyphen (`--`) |
| Forbidden words (core) | leverage, passionate, driven, dynamic, innovative, seamless, transformative, synergy, proven track record, layoffs — see `LR-009`/`LW-006`/`LW-007` for the full linter list |
| Forbidden openers | No transition fluff sentence openers; no "I am writing to express my interest" |
| Attribution tiers | OWNED = Jason built/designed/led it; CONTRIBUTED = joint or adjacent; INFLUENCED = informed without ownership — use only what workExperience.md actually supports |
| Exclusion zones | No people-management claims; no 0-to-1 or greenfield PM framing; no revenue/billing/payments ownership; no AI/ML model training or engineering ownership |
| Closed-world rule | Use only claim_ids + excerpts from the authoring packet; write fresh prose from those facts; never invent a metric, tool, company, or date not present in the packet |

---

## EXCLUDED

These are available in full context files but add no authoring value and would expand the digest past
its token budget. An Epic 7 calibration pass may revisit any of these exclusions.

| Topic | Reason excluded |
|---|---|
| Full MET code table (MET-01–MET-16) | Already present verbatim in packet excerpts; repeating them in the digest double-counts tokens |
| Full conversion rubric text (R1–R8, C1–C5) | Rubric is for scoring, not for authoring; Stage 2 handles verification |
| Full submission-linter rule list | Digest points to rule codes conceptually; linter runs independently post-draft |
| Scout/connector architecture | Engineering-only; cloud author never needs it |
| CR archaeology (CR-053 through CR-073) | Historical rationale, not authoring instructions |
| Skill self-repair history and failure postmortems | Embedded in CLAUDE.md prose; not needed for a single compose pass |
| Full ACC code descriptions | Delivered via packet excerpts on a per-JD basis |
| Networking-outreach patterns | Different workflow; not in scope for resume/cover letter authoring |
