---
status: in_progress
created: 2026-09-10
implementation_plan: ../08-implementation/CR-112-stage0-3-reliability-quality-tokens-epics.md
investigation: ../08-implementation/INVESTIGATION-2026-09-10-stage0-3-reliability-quality-tokens.md
related: CR-074, CR-076–084, CR-097, CR-102, CR-108, CR-111
---

# CR-112 — Stage 0–3 reliability, first-draft quality, and token containment

## Decision summary

Keep Applyr a composable workflow: deterministic Stage 0/packet/Stage 2, one bounded Stage 1 author session, explicit Stage 3 finalize.

Do not add agents or frameworks. Close two fail-open dirty patches (sequential ID remap, `claim_constraints` wipe). Make the lean authoring path the only default spawn. Explain evidence-ranking omissions. Do not auto-insert larger metrics or add stylistic hard gates.

Jason 2026-09-11: extra-packet is not WARN-versus-hard-stop. Split pre-authoring selection defects from closed-world authoring defects. Comparative replace is allowed only when an omitted eligible fact clearly dominates the weakest selected fact. Extra cites are a recoverable completion block. Detection and comparison stay separate. Model cost: offline default, free-tier only under a hard zero-dollar declaration, paid opt-in, no silent free→paid fallback, unknown cost is not zero. Design:
`docs/spec/08-implementation/CR-112-selection-and-closed-world-recovery-design.md`.
No implementation until independent pre-implementation review ACCEPT.

## Problem

Stage 0–3 is reliable on paper (`run_submission.py`) and leaky in practice: harness-level per-JD agents still reload fat context and can exhaust a five-hour subscription in minutes; two uncommitted patches fail open under provider/token pressure; first-draft quality still depends on authors reaching outside the packet.

## Out of scope

Live submission rewrites, paid model experiments without a budget, local/cheaper author models without eval, deleting Antigravity's adversarial work, treating extra-packet cites as automatically stronger, wiring `--paid-llm` to `call_llm`.

## Requirements allocated

Epic 1 (this commit):

| ID | Statement |
|----|-----------|
| `FR-296` / `AC-393` | Reject invented sequential Stage 0 batch IDs |
| `FR-297` / `AC-394` | Do not ready a packet after dropping `claim_constraints` |
| `FR-298` / `AC-395` | Read-only detector for already-wiped packets |

Epics 2–6 remain planned in the tracker. They are not allocated in the registry by this commit.

2026-09-11 design (not implemented): `FR-312`–`FR-317`, `AC-409`–`AC-414`, `NFR-015`. `FR-302`/`AC-399` superseded. Story 3.0 review 1 REVISE; design revised; second review required before code.

## Implementation status (2026-09-10)

Epic 1 is isolated on branch `cr112-epic1` for review. Stories are **not** self-marked done. SupplyHouse recovery is off the active backlog (Jason, 2026-09-10: already corrected; do not rebuild, re-author, or request risk acceptance). Keep the detector and tests. The agent-created sidecar is a separate finding and is not authorization.
