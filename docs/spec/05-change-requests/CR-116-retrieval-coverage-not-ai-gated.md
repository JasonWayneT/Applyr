---
status: in_progress
date: 2026-09-17
related: CR-093, CR-114, CR-115, FEAT-002
---

# CR-116: Retrieval coverage is not AI-token-gated

## Decision

Stage 0 evidence retrieval must put corpus-backed distinctive requirement tokens into the excerpt the scorer sees. `window_ok` only fires on AI/LLM/agentic/MCP tokens, so a healthy instrumentation pair can hide a starved Jira or executive-briefing excerpt. Add a coverage check that is not AI-token-gated, and force-include the smallest WE chunk that holds each missing corpus-backed token, before any 30-JD replay.

No model answer is a gold label. This CR does not manufacture adjudication marks.

## Problem

Sitting 1 false gaps at Acquia:

- `acquia:req:3` Jira/Confluence/Aha scored 0. ACC-119 names Confluence and Jira. ACC-108 is a weighted Jira priority-score. Both `window_ok` and `prefix_ok` were True.
- `acquia:req:0` executive briefing scored 0. WE line 254 and ACC-109 document presenting the quarterly roadmap to 200-300 including CEOs. Agy reasoned from "not part of leadership's decision-making," a different claim. Both flags True.

`window_ok` is True by definition on non-AI lines. Jaccard on the ~77k-char Approved Accomplishments Inventory chunk loses to small generic anti-claim / executive-turnover chunks. The scorer never received the evidence.

A replay that passes while those lines score 0 is measuring the wrong thing.

## Stories

1. [ ] Force-include corpus-backed distinctive query tokens (and window huge inventory chunks around those tokens) so Acquia Jira/Confluence and executive-briefing evidence reach the excerpt. Independent QA remains. Production switch off.
2. [ ] Expose `coverage_ok`: distinctive requirement tokens that exist in `workExperience.md` must appear in the excerpt. Not AI-token-gated. Independent QA remains.
3. [ ] Do not run the adjudicated 30-JD replay as a CR-114 promotion gate while `coverage_ok` can be False on sitting-1 Acquia Jira/exec lines. Independent QA remains.

## Out of scope

- Manufacturing gold labels or enabling `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER`.
- Changing skip rules or leftover bucket vocabulary.
- Expanding `_ZERO_TO_ONE_RE` to "ship MVPs" / "build an OS".

## Implementation gate

CR-115 heading/fragment drop and this coverage check both land before the 30-JD replay.
