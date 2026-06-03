# CR-039: Transferable Skills Over Domain Gating

## Metadata
- **Status**: Approved
- **Supersedes**: CR-037 (required domain zero-token gate)
- **Date**: 2026-06-02
- **Related Requirements**: `FR-192`, `FR-191`

## Problem
CR-037 hard-rejected JDs when vertical industry years did not match `domain_experience`. User policy: **do not gate on customer base (B2C/B2B) or industry vertical** — evaluate transferable PM skills instead.

## Decision
1. **Remove** zero-token `check_domain_gate` reject and `enforce_required_domain_cap` post-process.
2. **Inject** `TRANSFERABLE SKILLS POLICY` in fit scoring — score on platform, roadmap, cross-functional, agile, data complexity; domain gaps → RiskFlags only, not sole reject.
3. **Keep** `domain_gate.py` extraction for informational `domain_gaps` and scoring context only.
4. **Keep** `blocked_industries` moral blocklist (Gambling, Crypto) — user-specified exclusions, not transferable-skills evaluation.

## Acceptance criteria
| ID | Criterion |
|----|-----------|
| `AC-203` | Cotiviti-class JD (required healthcare years) passes zero-token gates |
| `AC-204` | Fit scoring injects transferable skills policy by default |
| `AC-205` | Domain vertical gap does not force NO via deterministic cap |

## Implementation
- `scripts/domain_gate.py` — `get_domain_gaps`, `transferable_skills_prompt_block`; gate reject removed
- `scripts/fit_policy.py` — transferable note, remove domain cap and anchor-floor domain skip
- `scripts/batch_pipeline.py` — remove domain zero-token gate
