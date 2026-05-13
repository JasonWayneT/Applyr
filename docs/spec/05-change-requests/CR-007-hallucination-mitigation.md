# CR-007: Local Model Hallucination Mitigation & Style Guard Hardening

## Metadata

| Field | Value |
|---|---|
| **CR ID** | `CR-007` |
| **Date** | 2026-05-13 |
| **Status** | Implemented |
| **Priority** | P0 |
| **Author** | Jason Taylor |
| **Implements** | `FR-071`, `FR-072`, `FR-073`, `FR-074`, `FR-075` |

## Problem Statement

The pipeline produced structurally and factually corrupt output when a local small model (GEMMA 4 E4B, 4B parameters via Ollama) was set as the primary provider. Root causes identified:

1. **Sampling drift** — `temperature: 0.2` and uncapped `num_predict: 4096` let the model invent facts and run far past the required length.
2. **Monolithic prompt overload** — one massive prompt containing master resume + style guide + best practices + work experience + JD overwhelmed the 4B model's effective context window, causing confabulation.
3. **No few-shot grounding** — the `LOCAL_CONSTRAINT_PREFIX` only listed prohibitions; small models respond better to concrete before/after examples.
4. **Self-referential verification** — `llm_verify_claims()` was calling the same local model that produced the hallucination to verify it — a model that invents a claim will not reliably catch it.
5. **`validate_hard_facts()` lacked document-type awareness** — education presence checks ran on cover letters (which don't contain education sections), producing spurious warnings and occasionally triggering incorrect auto-injection.
6. **Unfilled template placeholders leaked into output** — tokens like `[JD]`, `[Position Overview]`, `[Your City, State]` were not caught by any guard and reached final PDFs.
7. **Style guard did not strip forbidden sections** — sections like "Core Competencies", "Technical Skills & Tools", "Key Projects & Achievements" appeared in final resumes despite being prohibited by R-005.
8. **Name header normalization was incomplete** — the guard only caught `# JASON TAYLOR`; variants like `## JASON TAYLOR` and `**Jason Taylor**` passed through uncorrected.

## Solution Overview

### Layer 1: Local Model Sampling Hardening (`scripts/utils.py`)
- Override `temperature` to `0.0` for all Ollama calls regardless of caller input.
- Cap `num_predict` at `1000` (down from `4096`).
- Add `top_k: 40`, `top_p: 0.9` to constrain the token distribution.
- Add two concrete WRONG/CORRECT bullet examples to `LOCAL_CONSTRAINT_PREFIX` (few-shot grounding).
- Add helper `is_local_provider_active() -> bool` — reads settings, returns True if `providers[0] == 'local'`.
- Add helper `call_local_json(system, user, num_predict=200) -> dict | None` — direct Ollama call with `format: "json"`, returns parsed dict or None; used for structured selection tasks.

### Layer 2: Two-Phase Local Resume Generation (`scripts/drafting_engine.py`)
When local is the active primary provider, route through `_generate_resume_local_twophase()` instead of the single monolithic drafting call:
- **Phase 1 (Selection):** Send only the ACC ID menu + JD to `call_local_json` with `format: "json"` and `num_predict: 200`. Model returns `{"selected_ids": [...]}`. Small task, tiny output, near-impossible to hallucinate.
- **Phase 2 (Bullet Generation):** For each selected ACC ID, send one focused call: original claim text + target JD requirement. Model writes 2 bullets per call. Each call is ≤ 150 tokens output.
- Per-bullet validation: `preserves_core_facts()` runs deterministically (no LLM cost) first; if clean, `_verify_bullet_local()` runs an LLM VALID/INVALID self-check; on any failure, `_fallback_bullet()` reformats the source text directly without LLM creativity.
- `llm_verify_claims()` is skipped for local output — same-model verification is not reliable.

### Layer 3: Deterministic Numeric Fact Preservation (`scripts/verify_claims.py`)
`preserves_core_facts(source_text, generated_bullet) -> tuple[bool, list]`:
- Extracts all numeric tokens from source and bullet using a pattern covering `$NNN`, `NN%`, and standalone numbers ≥ 2 digits.
- Any number in the bullet that has no equivalent (substring match) in the source is flagged as invented.
- Returns `(is_clean, invented_list)`. Zero LLM cost.

### Layer 4: `validate_hard_facts()` Document-Type Awareness (`scripts/drafting_engine.py`)
- Added `doc_type='resume'` parameter; CL call now passes `doc_type='cover_letter'`.
- Education presence check gated: `if doc_type == 'resume'`.
- Cision job title guard: if any line contains both "cision" and "product owner" → replace with "Product Manager" and log.
- Placeholder catch-all: strip `[Caps Token]` patterns from all output before the remaining guards run.

### Layer 5: Style Guard Hardening (`scripts/style_compliance_guard.py`)
- `strip_forbidden_sections()` — removes 12 prohibited section types and all their content up to the next `##` boundary. Regex covers all capitalization and bold variants.
- `strip_placeholders()` — strips `[CAPS TOKEN]` patterns (unfilled template tokens) from all doc types.
- `normalize_resume_headers()` — name match regex expanded from `^#\s*` to `^(?:#{1,3}\s*)?(?:\*\*)?` to catch `## JASON TAYLOR` and `**Jason Taylor**` variants.
- Duplicate contact line guard — `re.sub` removes any orphaned `[REDACTED_PHONE] | ... | linkedin.com` line after the canonical header is re-injected.
- Education section stripped from cover letters via `re.sub` on the `## EDUCATION` boundary.
- Artifact-only line removal — lines containing only `[\s,\-\*|•]+` are deleted.

## Requirements Introduced

| ID | Summary |
|---|---|
| `FR-071` | Local Model Deterministic Sampling Override |
| `FR-072` | Two-Phase Local Resume Generation |
| `FR-073` | Deterministic Numeric Fact Preservation |
| `FR-074` | Style Guard Forbidden Section & Header Normalization |
| `FR-075` | `validate_hard_facts()` Document-Type Awareness |

## Files Changed

| File | Change |
|---|---|
| `scripts/utils.py` | Sampling override, few-shot prefix, `is_local_provider_active`, `call_local_json` |
| `scripts/drafting_engine.py` | Two-phase generation, `validate_hard_facts` doc_type, Cision guard, placeholder catch-all |
| `scripts/verify_claims.py` | `preserves_core_facts()` |
| `scripts/style_compliance_guard.py` | Forbidden sections, placeholder stripping, header normalization, education-in-CL guard |

## Verification

1. Trigger a drafting run with local provider as primary; confirm logs show `[LLM] Two-Phase Local Generation`.
2. Inspect `[HARD FACT AUDIT]` output — target: 0 invented-number warnings (was 5+ before this CR).
3. Run `style_compliance_guard.py` on a resume containing a "Core Competencies" section — verify it is stripped.
4. Run guard on a resume with `## JASON TAYLOR` header — verify normalized to `# JASON TAYLOR`.
5. Run guard on a cover letter with `## EDUCATION & CERTIFICATIONS` at bottom — verify stripped.
6. Confirm all 29 submissions pass `quality_checker.py` with no R-005, R-007, R-008, R-009 violations.
