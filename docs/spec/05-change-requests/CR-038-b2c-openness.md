# CR-038: B2C Role Openness

## Metadata
- **Status**: Approved
- **Date**: 2026-06-02
- **Related Requirements**: `FR-191`

## Problem
Pipeline defaults and fit prompts assume B2B/enterprise SaaS only. Candidate is open to B2C PM roles but signal keywords, anchors (`b2b saas`), and scoring prompts bias toward rejecting consumer product fits.

## Decision
1. **`open_to_b2c` preference** — when true, inject fit-scoring note: do not penalize B2C/consumer business models; bridge from platform PM skills.
2. **Broader signal keywords** — add `b2c`, `consumer`, `mobile`, `app` alongside existing B2B terms (OR gate unchanged).
3. **Anchor broadening** — replace `b2b saas` with `saas` in default anchors so B2C SaaS JDs hit the Two-Anchor rule.
4. **Scoring prompt** — neutral B2B/B2C bridge language in scoring-only path.

## Acceptance criteria
| ID | Criterion |
|----|-----------|
| `AC-200` | `open_to_b2c: true` injects B2C openness note in fit scoring context |
| `AC-201` | JD with consumer/mobile signals passes keyword gate without requiring `b2b` |
| `AC-202` | Fit scoring prompt does not instruct B2B-only bridge rejection when `open_to_b2c` is set |
