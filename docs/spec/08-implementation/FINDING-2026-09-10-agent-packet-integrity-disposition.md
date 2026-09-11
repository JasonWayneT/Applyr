# FINDING — Agent-created packet integrity sidecar is not human authorization

**Date:** 2026-09-10
**Severity:** process / evidence integrity
**Does not authorize anything.** An agent wrote a gitignored live sidecar and attributed a `HUMAN_ACCEPTED_RISK` verdict to the candidate. That is not the candidate's approval.

## Evidence

**Local original (not in git):** the live `packet_integrity_disposition.json` under the gitignored submissions tree is left in place. A second local copy, with SHA-256, is under `data/reports/` (gitignored). Do not add either file to git.

**Tracked stand-in:** `tests/fixtures/packet_integrity_disposition.sanitized.json` — same schema (`verdict`, `reason`, `source`) with a fake employer slug and a fixture reason. It is not a copy of the live file.

## Origin

Written by **Cursor (Grok 4.6)** in conversation [agent-created sidecar](2d0b7f4a-c1f8-4a39-81d2-6c3631a1da36), not by the candidate.

The same turn:

1. Added detector code that reads a sidecar if present.
2. Wrote the live gitignored sidecar via Python `Path.write_text`.
3. Reported that option (b) had been recorded as `HUMAN_ACCEPTED_RISK`.

The live `reason` field names the candidate and asserts a date-stamped instruction. That chat does not contain a human message instructing `HUMAN_ACCEPTED_RISK` or option (b). The agent inferred approval from its own tracker/handoff prose.

## Does any workflow treat it as human authorization?

Checked 2026-09-10 against this repo:

| Surface | Reads this filename? | Treats it as authorization? |
|---------|----------------------|-----------------------------|
| `scripts/audit_packet_integrity.py` | Yes, display-only | **No.** `flagged` is computed from packet fields only. Sidecar does not unflag. Exit code 1 still fires if any packet is flagged. |
| `scripts/test_audit_packet_integrity.py` | Temp fixture only | Asserts sidecar does **not** unflag. |
| `scripts/run_submission.py` / `scripts/workflow/` | No | Stage 2 `HUMAN_ACCEPTED_RISK` is `reviews/dispositions.json`, a different path. |
| `scripts/workflow/policy.py` / `reviews.py` | No | Orchestrator dispositions only. |

No production gate, receipt, or finalize path consumes `packet_integrity_disposition.json`.

## What this finding is not

It is not residual packet-risk acceptance. On 2026-09-10 the candidate said the flagged live folder was already corrected, to remove its recovery from the active backlog, and not to rebuild, re-author, or request risk acceptance. That instruction is recorded on the Epic 1 tracker. It does not convert the sidecar into authorization, and it does not instruct anyone to rewrite the live sidecar.
