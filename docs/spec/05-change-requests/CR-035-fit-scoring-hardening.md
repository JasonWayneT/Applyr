# CR-035: Fit Scoring Hardening (Location Lock + Anchor Floor)

## Metadata
- **Status**: Approved
- **Date**: 2026-06-02
- **Related Requirements**: `FR-188`, `FR-070`, `FR-172`

## Problem
Local fit LLM (`qwen2.5:7b`) re-runs Stage A rubric gates after deterministic pre-filters pass, causing false rejects:
- Location instant-kills despite `REMOTE_OK` (Brown & Brown class)
- Domain/seniority penalties despite optional domain language and anchor match (Ophelia class — score 68 vs threshold 72)

## Decision
1. **Location lock-in** — `resolve_location_verdict()` pre-verifies policy; strip §2.3 / Stage A from LLM rubric; scoring-only fallback when model cites location.
2. **Scoring-only primary path** — after deterministic gates pass, primary fit call scores Stage B only.
3. **Anchor floor (FR-188)** — when ≥2 `required_anchors` match and LLM score is 65–71, auto-promote to pass at `min_fit_score`.
4. **Optional domain note** — detect "nice plus" / "not required" JD language; inject `DOMAIN_REQUIREMENT: OPTIONAL`.
5. **Rubric clarifications** — triad co-lead ≠ people management; startup penalty only for solo traps.

## Out of scope
- Gemini/cloud fit provider switch (user declined).

## Acceptance criteria
| ID | Criterion |
|----|-----------|
| `AC-191` | Multi-city + Remote JD resolves `REMOTE_OK` and does not onsite-reject |
| `AC-192` | JD with ≥2 anchor hits and LLM score 68 promotes to pass at min_fit_score |
| `AC-193` | JD with "nice plus" healthcare language injects optional domain note |

## Implementation
- `scripts/zero_shot_classifier.py` — `resolve_location_verdict`, `location_lock_prompt_block`
- `scripts/fit_policy.py` — anchor floor, optional domain, gates-passed rubric strip
- `scripts/batch_pipeline.py` — scoring-only primary, post-process floor
- `.agent/rules/job_fit_engine.md` — location, co-lead, startup penalty updates
