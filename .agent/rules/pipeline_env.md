---
trigger: always_on
---

# Pipeline Environment & Local-First Defaults (CR-021)

Agents editing `scripts/batch_pipeline.py`, `scripts/draft_compiler.py`, scouting, or fit evaluation **must** respect these environment defaults. Do not weaken anti-hallucination guards without a new `CR-*` and registry updates.

**Requirement IDs:** `FR-131`–`FR-150` · **Spec:** `docs/spec/05-change-requests/CR-021-local-funnel-compose-hardening.md`

---

## 1) Required defaults (compose + local)

| Variable | Default | Purpose |
|----------|---------|---------|
| `DRAFT_MODE` | `compose` | Catalog-grounded bullets; no per-claim LLM rewrite |
| `LOCAL_ONLY_MODE` | `1` | Ollama only — **no** Gemini/Perplexity fallback on fit/draft |
| `JD_PROFILE_MODE` | `deterministic` | JD themes from keywords only in compose path |
| `COVER_HOOK_MODE` | `template` | Legacy path only when `COVER_ENGINE` ≠ `v1` |
| `COVER_ENGINE` | `v1` | CR-024 Match Brief (`cover_letter_compiler.py`); independent of resume |
| `COVER_ONLY` | `0` | `1` = regenerate `CoverLetter.md` / PDF only |
| `APPLYR_API_TOKEN` | *(unset)* | When set, require `X-Applyr-Token` header on API routes (CR-025) |
| `RESEARCH_MODE` | `local` | SearXNG + local summarizer; use `skip` if offline |
| `CHEAT_SHEET_MODE` | `template` | Template cheat sheet when cloud research unavailable |

Set via `scripts/pipeline_env.py`, `batch_pipeline.py` `setdefault`, and `server/shared.ts` `buildPythonEnv()`.

---

## 2) Forbidden combinations

| Setting | Result |
|---------|--------|
| `LOCAL_ONLY_MODE=1` + `DRAFT_MODE=legacy_llm` | **Blocked** — raises at compose entry (`FR-141`) |
| `COVER_HOOK_MODE=llm` without audit | LLM hook must pass numeric audit against JD snippet |
| `JD_PROFILE_MODE=llm` in compose | Only when explicitly needed; LLM themes must be substring-valid in JD |

---

## 3) Optional tuning

| Variable | When to use |
|----------|-------------|
| `FIT_EVAL_TOP_N` | Cap fit LLM calls per batch (e.g. `30`) after pre-score sort |
| `BATCH_PARALLEL_WORKERS` | Default `1` — sequential evaluate/draft (honest UI progress, one GPU fit) |
| `FIT_LLM_TIMEOUT_SEC` | Default `180` — HTTP timeout for local fit calls (prevents hung batch) |
### Resume compose quotas (default)

| Variable | Default | Purpose |
|----------|---------|---------|
| `RESUME_BULLET_QUOTAS` | `cision:5,sterkly:3,zero_to_sixty:3` | Bullets per employer on composed resumes |
| `RESUME_ONLY` | `0` | `1` = regenerate resume/PDF only (leave cover letter files) |

### Quality batch (default for `LOCAL_ONLY_MODE=1`)

Applied automatically via `apply_quality_batch_defaults()` — **no action needed**:

| Setting | Value | Why |
|---------|-------|-----|
| Fit model | **qwen2.5:7b** (unchanged) | Full rubric quality |
| `FIT_NUM_PREDICT` | `768` | Fit JSON is small; saves ~10–15% on fit latency |
| `BATCH_UNLOAD_MODELS` | `0` | Keep model in VRAM between jobs |
| `BATCH_INTER_JOB_SLEEP_SEC` | `2` | Was 8s; no quality impact |
| Tag embeddings | **cached** | Same tags, one-time embed per run |

### Fast batch (opt-in only — trades fit quality)

| `BATCH_FAST_MODE` | `1` — phi3.5 fit, 512 tokens, skip tagger + duplicate embed, no sleep |
| `FIT_MODEL` | Override fit model (e.g. force `qwen2.5:7b` while fast mode is on) |
| `SKIP_METADATA_TAGGER` | `1` — skip optional metadata tags (also skipped in fast mode) |
| `SKIP_DUPLICATE_VECTOR` | `1` — skip JD dedup embedding (also skipped in fast mode) |
| `LOCAL_LINT` | `0` to skip phi3.5 JSON lint in `draft_linter.py` |
| `localModelFit` (SQLite) | Override fit model; default `qwen2.5:7b-instruct-q4_K_M` |

---

## 4) Drafting invariants (do not break)

1. **Resume/cover bullets** come from `workExperience.md` ACC catalog in compose mode — never invent metrics or tools.
2. **Cover letters** (`COVER_ENGINE=v1`, `FR-157`–`FR-163`): JD + claim catalog only — **never** read `Resume.md` for cover claim selection (`FR-158`). Legacy: bullet-paste when `COVER_ENGINE` unset.
3. **Resume summary themes** use `format_themes_for_prose` — no chained “and” from compound JD theme strings (`FR-161`).
4. **`draft_manifest.json`** must record `verification_passed: true` before UI PDF compile (`FR-139`); may include `cover_letter_plan` when `COVER_ENGINE=v1`.
5. **WebGPU grammar** lists issues only — never auto-rewrite resume/cover text (`FR-140`).
6. **Scout** applies title + max-years gate when job description is present (`FR-135`).

---

## 5) Verification commands

```bash
python scripts/smoke_draft_compiler.py
python scripts/build_claim_embeddings.py
python scripts/test_smoke_regression.py
```

---

## 6) SDD traceability

Any change to defaults or guards requires: `CR-*` → `02-requirements-registry.md` → feature spec → `traceability-matrix.md` → `IMP-*` → `PRODUCT_CAPABILITIES_AND_RELEASE_NOTES.md`.
