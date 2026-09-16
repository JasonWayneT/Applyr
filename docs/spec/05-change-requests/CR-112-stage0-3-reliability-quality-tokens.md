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

Epics 2–6 remain planned in the tracker. They are not allocated in the registry by this commit. **2026-09-16:** Allocation since progressed — `FR-299`/`AC-396` (Story 2.1) and `FR-301`/`AC-398` (Story 2.3) allocated; `FR-300`/`AC-397` (Story 2.2) and Epics 3–7 previously allocated. See `docs/spec/02-requirements-registry.md` for current FR/AC rows.

2026-09-11 design: `FR-312`–`FR-317`, `AC-409`–`AC-414`, `NFR-015`. `FR-302`/`AC-399` superseded. Story 3.0 second review `PASS` (`2d3549f0`). `FR-316`/`FR-317` (Stories 7.1/7.2) implemented and independently re-reviewed `PASS` (`97887893`) 2026-09-11; see 2026-09-14 status correction below and Story 7.1/7.2 status lines in the epics doc.

## Minimal workflow operator slices (2026-09-16)

Implements `FR-316` / `AC-413` and preserves the existing backend controls
from `FR-164` / `AC-170`, `FR-167` / `AC-173`, `CR-ARCH-004`, and CR-104's
localhost/token-auth hardening.

### Backend

- Authenticated POST routes start, resume, inspect, or finalize the canonical
  `scripts/run_submission.py` workflow. There is no alternate workflow writer.
- Commands pass the selected folder as an argument array through
  `server/pipeline/processRunner.ts`. `shell:false` and the centralized
  sanitized child environment remain mandatory.
- A per-submission in-memory lock rejects overlapping mutating commands with
  HTTP 409. Status is read-only but authenticated in this operator surface.
- Responses project only workflow status, mode, active stage, stage
  status/integrity, and allowlisted pause metadata from `workflow_state.json`
  and `stage_receipts/*.json`. Hashes, checks, candidate content, paths,
  provider reasons, and subprocess output are not returned.
- Folder scope is closed to `data/pending_review/{slug}` and
  `data/submissions/{slug}`. Traversal and missing folders fail closed.

### Compact Review Center UI

- The Review Center includes an operator panel for one selected folder scope
  and slug. It shows Stage 0, Stage 1, and Stage 2 status from the authenticated
  status route and exposes explicit Start, Resume, and Finalize actions.
- Client actions call only
  `/api/run-submission/:scope/:slug/{start,resume,status,finalize}`. The client
  does not invoke Python, read workflow files, or write workflow authority.
- A Stage 0 `cost_authorization` pause states that no model API call occurred,
  no API cost was incurred, and Stage 0 is incomplete. It directs the operator
  to import cascade JSON, certify a zero-charge provider, or authorize paid use
  before resuming, and it prohibits pasting `authoring_prompt.md`.
- This packet does not add provider configuration or cascade-import UI.

## Implementation status (2026-09-16 working-tree wave)

On `cr112-selection-closed-world-design`: Stories 2.1, 2.3, cost-pause status
copy, and 7.3 are committed and pending independent review. Story 7.4 is
implemented in the local working tree and pending independent review. The
cascade-import `created_at` should-fix is still open. The Metis wave for this
work is operator-closed and the implementation approval marker was removed.
Stories are **not** self-marked done.

## Implementation status (2026-09-10)

Epic 1 is isolated on branch `cr112-epic1` for review. Stories are **not** self-marked done. SupplyHouse recovery is off the active backlog (Jason, 2026-09-10: already corrected; do not rebuild, re-author, or request risk acceptance). Keep the detector and tests. The agent-created sidecar is a separate finding and is not authorization.
