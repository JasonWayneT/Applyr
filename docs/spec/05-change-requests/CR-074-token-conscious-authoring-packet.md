# CR-074: Token-Conscious Authoring Packet (Approach A)

## Metadata
- **Status**: Implemented (2026-08-06) — Epics 1–7 done; Epic 8 optional local assists deferred
- **Date**: 2026-08-06
- **Related**: Supersedes the multi-agent Stage 0–3 *orchestration* pattern in `generate-submission` for cloud-token cost; does **not** retire grounding rules, linters, or `verify_submission.py`. Related history: CR-062 (local rewrite), CR-070 (native generation), context-pack work (2026-07-27).
- **Requirements**: `FR-252`–`FR-255`, `NFR-007`, `AC-272`–`AC-277`
- **Tracker**: [epics](../08-implementation/CR-074-token-conscious-authoring-packet-epics.md)
- **Gate record**: [methodology gates](../08-implementation/CR-074-methodology-gate-record.md)
- **Research basis**: Stanford/TACL “Lost in the Middle” (Liu et al. 2024); Anthropic context engineering (2025); Wang et al. EMNLP 2024 RAG best practices; agent-scaling overhead study (2025); Enhancv 2025 recruiter ATS interviews; Fowler test pyramid / fail-fast gates.

## Problem
Stage 0–3 quality rules are largely sound, but the *operating model* burns cloud tokens before finishing small batches:
- Fixed overhead per agent is huge (`data/agent_context_pack.md` ~157KB plus a long skill).
- Stage 2’s “fresh session independent review” reloads that pack for every company.
- Batch fan-out into many agents multiplies the same load (observed as ~13-agent workflows hitting session token limits).
- Long packs also hurt quality: models under-attend the middle of long contexts (“Lost in the Middle”; Anthropic “context rot”).

Multi-agent independence was added to catch real failures (fake rubric scores, unused ground truth). Those failures are now largely caught by **mechanical receipts** (`verify_submission.py`, coverage, jd terms, `--audit`). Paying a second full cloud context load for that is no longer the right default.

## Decision
Adopt **Approach A — Authoring Packet + one cloud draft**:

1. **Stage 0** becomes primarily **deterministic scripts** (DB cooldown, blocklists, years/travel, hard-gap string/tag checks, JD bucket extraction into `stage0_fit_gate.json`). Soft gaps stay rule-classified in v1 (named tool/cert = hard; transferable domain = soft). No local soft-gap LLM in v1.
2. **Packet builder** (new): retrieve → rank → repack into `authoring_packet.json` (~2–6k tokens): JD buckets, evidence map (required/preferred/responsibilities → ACC/MET IDs), **excerpts only** from `workExperience.md`, soft-gap tags, compact rule digest. Block cloud draft if any required item lacks evidence or a soft-bridge tag.
3. **Stage 1**: **one cloud authoring pass** that receives the packet + short rule digest only — not the full context pack / skill self-repair history. Writes Resume.md + CoverLetter.md. Closed world: may not invent claims outside packet IDs.
4. **Stage 2 default**: verification **pyramid** — scripts first (`verify_submission`, coverage, jd terms, `--audit`); optional local judge later; Jason skim before send. Fresh-cloud independent review is **opt-in / send-batch only**, not default per company.
5. **Stage 3**: unchanged finalize scripts (compile, page count, `finalize_submission_job.py`). No draft-time cheat sheet / full research packet.

Do **not** revive full deterministic `draft_compiler` prose as the author. Retrieval stays deterministic; **composition** stays cloud.

## Acceptance Criteria
| ID | Criterion |
|----|-----------|
| AC1 | `build_stage0_fit_gate` (or equivalent) produces valid `stage0_fit_gate.json` for ≥3 real JDs without a cloud LLM call |
| AC2 | `build_authoring_packet` emits `authoring_packet.json` under a documented token/size budget, with excerpts only for selected ACC/MET IDs, and fails closed on incomplete evidence maps |
| AC3 | A single cloud authoring invocation can draft Resume + Cover Letter from packet + rule digest alone (no `agent_context_pack.md` in that call’s required inputs) |
| AC4 | Default Stage 2 path is scripts-only; `verification_receipt.json` remains the mechanical done gate; `--audit` still required when rubric scores are written |
| AC5 | Calibration: ≥3 real submissions through the new path clear mechanical verify; Jason judges quality acceptable vs a same-JD baseline drafted the old way (or explicitly accepts deltas) |
| AC6 | `generate-submission/SKILL.md` documents the new default path; multi-agent Stage 2 is demoted to optional |

## Out of Scope
- Making Ollama the primary author (optional polish only; CR-062 remains opt-in)
- Local soft-gap classifier / local rubric judge (deferred epic after v1 calibration)
- Replacing `conversion_rubric.md` criteria or lowering anti-hallucination rules
- Auto-send without Jason skim
- Changing scout/ingest gates (separate from authoring)

## Open decisions (resolve during epics, not before start)
- Exact packet token budget number (start with “must be ≤8k tokens estimated”; tighten after Epic 1 measurement).
- Whether Stage 0 bucket extraction is 100% regex/heuristic or allows a tiny local structured-extract for messy JDs after rules fail (default: rules only in Epic 2).
