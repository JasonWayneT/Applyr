# Stage 0 Architecture Research Report

**Status:** Research deliverable. No production code was changed for this report.
**Scope:** The Stage 0 fit gate (JD → Tier 1 / Tier 2 / Skip, or an explicit review pause) at ~30-JD batch scale.
**Prepared:** 2026-09-16. Section 17 records the first revision and its research pressure test. Jason's 2026-09-17 clarification in Section 18 is the current direction wherever it conflicts with Sections 7-17: improve Stage 0 NLP and matching, while using subscription-harness calls for uncertain runtime cases instead of Groq/Gemini free-tier calls.
**Method:** Direct read of `scripts/build_stage0_fit_gate.py` (3,651 lines) and `scripts/evidence_scale.py` (983 lines); three exhaustive sub-investigations (gate workers, orchestration, data/specs/calibration) each citing file:line as source of record; external literature review with citations. Nothing here is speculative about the codebase: every claim about current behavior traces to a file and line.

**Evidence tags used throughout:**
- `[M]` measured from repo code or data
- `[U]` user-supplied operational constraint
- `[P]` published external figure
- `[E]` estimate (reasoning given, needs a spike to confirm)

---

## Contents

1. Intent and Problem Statement
2. Current Stage 0 Architecture (measured)
3. Current Weaknesses
4. Subproblem Decomposition
5. External Research Review
6. Subproblem-to-Technology Matrix
7. Candidate Architectures
8. Benchmarks and Spikes
9. Recommendation
10. LLM Burden-of-Proof Verdict
11. Confidence and Abstention Design
12. Evaluation Framework
13. Observability and Versioning
14. Migration Plan (Shadow Mode)
15. Risks
16. Implementation Plan
17. Addendum: Revised Learning Architecture (2026-09-16)
18. Runtime Harness Fallback and NLP Improvement (2026-09-17)

Appendix A: Source Inventory
Appendix B: Bibliography
Appendix C: Open Questions

---

## 1. Intent and Problem Statement

### 1.1 What Stage 0 is for

For each incoming job description, Stage 0 must produce one of four outcomes:

- **Tier 1**: strong fit, prioritize for Stage 1 authoring.
- **Tier 2**: moderate fit, author when Tier 1 work is done.
- **Skip**: not a fit; record why, archive the folder, and remember the skip.
- **Review pause**: a human (Jason) must resolve a specific ambiguity before the decision can be made. A pause is not a failure; it is a first-class outcome.

The decision must be **reliable** (few false skips, few wasted pursuits), **explainable** (every decision cites its reasons), **cheap** (near-zero marginal cost per JD), **deterministic and reproducible** (same inputs → same outputs), and **operable by one person** at ~30 JDs per session `[U]`.

### 1.2 Constraints

| Constraint | Source |
|---|---|
| Groq and Gemini hosted fallbacks are unreliable at batch scale: the free tiers cannot get through a ~30-JD batch | `[U]` (corroborated by published limits, Section 5.9) |
| Local machine has 16 GB VRAM with Ollama already in use (`qwen2.5:7b-instruct-q4_K_M` is already pinned for the opt-in `llm` extraction mode, `scripts/build_stage0_fit_gate.py:57`) | `[M]` |
| Single operator; review time is the scarcest resource | `[U]`/`[M]` (all review surfaces are single-user) |
| Data corpus is small: 9 active submissions, 35 pending review, 453 archived submissions, 162 archived skips, 159 skip-ledger rows, 21-entry human-confirmed golden set | `[M]` |
| Score floors are locked by Jason: skip floor 40, Tier 1 floor 65 (`data/fit_rubric_calibration.json`, locked 2026-08-20) | `[M]` |
| No production changes as part of this investigation; the deliverable is this report | `[U]` |
| Strong preference for non-LLM solutions where sufficient; LLM usage must meet a burden of proof per subproblem | `[U]` |

### 1.3 Method rules applied

- Research before architecture: all claims about current behavior come from reading the code, not from memory or docs alone.
- Baseline first: any proposed architecture must be compared against the current system's measured behavior, not against a strawman.
- Least complex technology that reliably solves each subproblem; LLMs only where a simpler alternative demonstrably cannot.
- Every external claim is cited (Appendix B); every internal claim has a file:line.
- Measured vs estimated is always distinguished.

---

## 2. Current Stage 0 Architecture (measured)

### 2.1 Entry path and ownership

- CLI: `python scripts/run_submission.py data/pending_review/{slug}` (or `data/submissions/{slug}`). `main()` at `run_submission.py:103`; the default path is `run_until_truth_settled` (`run_submission.py:238`).
- Orchestration: `scripts/workflow/runner.py` `run_stage0` (`runner.py:242-489`) is the only caller of the single Stage 0 worker, `build_stage0_fit_gate()` (`scripts/build_stage0_fit_gate.py:2309-3349`).
- The worker refuses to write into a folder already owned by `run_submission.py` receipts (`build_stage0_fit_gate.py:3493-3503`), so there is exactly one fit path `[M]`.
- The server (Node) contains **no fit scoring or tier decisioning**. `server/services/stage0Policy.ts:39-62` only normalizes provider/model settings; `server/services/exportPendingReview.ts:48-110` gates what lands in `data/pending_review/` using dedup + skip-ledger + status/length checks (JD ≥ 200 chars) with zero LLM calls. All tiering happens in Python `[M]`.

### 2.2 The exact gate order (source of record)

Sequence inside `build_stage0_fit_gate()`, with the runner's handling around it:

| # | Step | Where | Deterministic? |
|---|---|---|---|
| 0 | Parse JD (URL line, company from folder name, role title via `seniority_gate.extract_job_title_line`), load prefs | `build_stage0_fit_gate.py:2355-2391` | Yes |
| 0.4 | **Skip ledger**: `lookup_skip` by URL then company+title; prior Skip → early SKIP (`skip_ledger`) | `:2394-2427`; `scripts/stage0_skip_ledger.py:88-131` | Yes (SQLite) |
| 1 | **DB gate**: cooldowns (120 d for hard rejections, 30 d for no-signal types; self-reject permanent), checks JD self-identified employer under both names; reject → early SKIP | `:2429-2461`; `scripts/stage0_db_gate.py:37-38,108-137,289-449` | Yes (SQLite + regex) |
| 2 | **Prefs/exclusion gate**: people-mgmt, 0-to-1, revenue/billing, AI/ML, solo-PM trap, travel > 15%, title blocklist, years ceiling (max 7), blocked industries, location; plus an **industry-semantic LLM supplement (fail-open)** and a bracket-placeholder content validator | `:2463-2491`; `scripts/stage0_prefs_gate.py:265-353`; `scripts/industry_gate.py`, `seniority_gate.py`, `solo_pm_gate.py`, `zero_shot_classifier.py` | Mostly yes; one fail-open hosted LLM supplement |
| 3 | **Section extraction**, default `nlp` (TF-IDF/LogReg, 0.65 confidence cutoff); sub-0.65 lines → one batched Groq→Gemini fallback call; still-unresolved → `unresolved_for_review`. Modes `llm` (local Ollama, raises on failure) and `deterministic` (regex) also exist | `:2494-2511`; nlp `:1116-1306` (cutoff `:1195-1202`, fallback call `:1222-1230`, unresolved `:1263-1305`); regex `:789-890`; llm `:1308-1455` | Classifier yes; fallback is hosted LLM |
| 3.5 | **CR-112 qualification-risk gate**: pure-regex three-way classification of unresolved bullets (NON_QUALIFICATION bypasses; LIKELY/AMBIGUOUS → pause with a per-item review template; no default accepted) | `:2513-2601`; `scripts/stage0_qualification_risk_gate.py:176-273` | Yes (regex) |
| 3.7 | **Skill confirmations**: unknown named tools (via `blocked_tools.looks_like_named_tool` + catalog/blocked lists) become durable Review Center items | `:2629-2636`; `scripts/stage0_confirmations.py:98-145,169-235` | Yes |
| 3.8 | **Checkpoint setup**: run_key = sha256(opportunity, jd_hash, prompt_version, provider_policy_hash, evidence_index_hash); `stage0_runs` row + request spool | `:2639-2700`; `scripts/stage0_checkpoint.py:65-100` | Yes |
| — | **Pause (review_center)** if pending skill confirmations | `:2702-2705` | — |
| 4 | **Evidence cascade** for uncached required/preferred lines: checkpoint reuse first (all of run_key + item_key + request_hash + content_hash + evidence_index_hash must match), then TF-IDF evidence context (max 3,000 chars, kept under the Groq free-tier TPM limit, comment `:2798-2801`), then one batched hosted call (batch cap 24, split > ~6,000 output tokens), with validation, unsafe-HARD demotion, partial-result retry; **cost authorization is fail-closed** (unknown ≠ zero; free → paid forbidden) and pauses with a manual cascade-import template | `:2707-2984`; `scripts/stage0_evidence_cascade.py` (cap `:14`, split `:330-368`, validate `:613-657`, demote `:723-727`); `scripts/cost_eligibility.py:291-456` | Cache yes; classification is hosted LLM (local only when configured) |
| — | **Pause (cost_authorization)** when no provider is eligible | `:2861-2888`; `cost_eligibility.py:560-608` | — |
| 4.5 | **classify_gaps**: consumes only cached/cascade results; a missing item raises `Stage0ExtractError` (fails closed, no silent defaults) | `:2986-2990`, raise `:2011-2031` | Yes |
| 4.6 | **Responsibilities exclusion screen**: deterministic 0-to-1 regex fast path, then batched classifier for the rest, **fail-open** | `:2995-3009`, fast path `:2164-2177`, batched `:2194-2215` | Fast path yes; rest is hosted LLM |
| — | **Hard-gate reviews + model-flagged skills**: any LLM-proposed HARD or unknown skill → Review Center pause before any terminal decision | `:3011-3062` | — |
| — | **Failsafe flags**: thin/incomplete extraction → HARD gap; empty extract → SOFT; required-empty and required-thin tripwires; PO-solo-backlog signal | `:3064-3120` | Yes |
| 5 | **`_determine_tier` fallback tier** (no-score path): DB/prefs reject, thin_incomplete, or HARD gap with source degree/domain/certification → Skip; reapply or any SOFT/HARD gap or required_empty → Tier 2; else Tier 1. Tool-only HARD gaps deliberately do not auto-Skip | `:3122-3129`, fn `:2227-2286` | Yes |
| 5.5 | **Score-driven final tier** (overrides Step 5): `compute_fit_score` over classified lines vs floors (65/40). Disqualified → Skip; ≥ 65 → Tier 1; ≥ 40 → Tier 2; else Skip; required-empty can never be Tier 1 | `:3131-3175` | Yes (formula) over LLM judgments |
| 6 | **skip_reason / skip_reason_code** assembly | `:3177-3201` | Yes |
| — | **Output assembly**: full gate JSON (tier, decision, fit_score, confidence_score, stage_signal, extraction_source, flagged_gaps, exclusion checks, notes, review metadata); run marked COMPLETE; VRAM release | `:3203-3349` | Yes |
| — | **Placement (runner)**: SKIP → skip-ledger write + move to `data/archive/skipped/`; PASS → `clear_skip` + move to `data/submissions/`; practice mode no-ops | `scripts/workflow/runner.py:428-489`; `scripts/stage0_placement.py:56-104` | Yes |

Diagram:

```
JD folder
  → skip ledger (SQLite) ──────────────── hit → SKIP (skip_ledger)
  → DB cooldown gate (SQLite) ─────────── reject → SKIP (db_reject/cooldown)
  → prefs/exclusion gate (regex [+1 fail-open LLM])
                                        reject → SKIP (exclusion zone)
  → section extraction (LogReg @0.65 default)
       └─ low-conf lines → hosted fallback → still unresolved → CR-112 regex gate
                                                             └─ likely/ambiguous → PAUSE (review)
  → skill confirmations ───────────────── any → PAUSE (review_center)
  → checkpoint (stage0_runs, run_key)
  → evidence cascade (cache → hosted batch [cost-gated])
       └─ no eligible provider → PAUSE (cost_authorization, manual import resume)
       └─ LLM-proposed HARD / new skill → PAUSE (review_center)
  → classify_gaps (fails closed) → responsibilities screen (fail-open)
  → failsafe flags → _determine_tier (fallback)
  → compute_fit_score → floors 65/40 → FINAL TIER
  → placement (ledger + folder move)
```

### 2.3 The score formula (measured, `scripts/evidence_scale.py:769-970`)

- Per required/preferred line, the cascade LLM returns: evidence level 0-4, gate ∈ {HARD, NONE} with a `gap_source` ∈ {degree, domain, role_exclusion, certification, tool}, confidence ∈ {high, medium, low}, reasoning, optional canonical skill.
- `compute_fit_score`: any required HARD → disqualified (fit_score 0). Otherwise:
  - `RawFit = 100 × Σ(weight_i × (level_i/4) × conf_i) / Σ(weight_i)`
  - weights: required 3.0, preferred 1.0 (`:775-776`)
  - confidence multipliers: high 1.00, medium 0.85, low 0.50 (`:769`)
  - repetition modifier: ≥ 3 repeated items → +1 each, cap +4 (`:781`); hedge modifier: -1 per hedge ("contributed to", "partnered on", "assisted with", "supported", "helped with"), floor 0 (`:782-787`)
- `confidence_score` (output field) = the same weighted average of the self-reported confidence multipliers. It is **not** a calibrated probability `[M]`.
- Bands loaded at runtime from `data/fit_rubric_calibration.json`: skip_floor 40, tier1_floor 65, locked by Jason 2026-08-20 `[M]`. The rubric spec (`data/fit_rubric_spec.html`) describes different bands (75/50/35) and acknowledges the gap `[M]`.
- Defensive post-processing on LLM output: ungrounded HARD reasoning is demoted to NONE and held for review (`evidence_scale.py:559-590`; cascade `stage0_evidence_cascade.py:723-727`); non-required buckets force gate=NONE; `needs_user_confirmation` without a `canonical_skill` fails the whole batch (fail-closed).

### 2.4 LLM touch points in the default path (complete list)

1. Extraction low-confidence fallback: one batched hosted call (Groq→Gemini, task-scoped, `build_stage0_fit_gate.py:1222-1230`). Successful mappings are appended to `training_data_feedback.csv` for retraining (`:1237-1262`).
2. Prefs-gate industry-semantic supplement: hosted, fail-open (`scripts/stage0_prefs_gate.py` via `industry_semantic`, `scripts/llm_stages.py:24-52`).
3. Evidence cascade (the core judgment): hosted Groq→Gemini by default; `local` only when explicitly configured (`stage0_evidence_cascade.py:82-113`).
4. Responsibilities exclusion screen fallback: hosted, fail-open (`build_stage0_fit_gate.py:2194-2215`).
5. Opt-in `llm` extraction mode: local Ollama only (`:1308-1455`).

Two are load-bearing (1 feeds the CR-112 queue, 3 is mandatory for gap classification), two degrade gracefully. None of the four load-bearing/fail-open distinctions changes the conclusion in Section 3: the default path cannot complete a 30-JD batch offline today.

### 2.5 Pause kinds, checkpointing, and receipts (already strong)

- Three pause kinds, all `WAITING_FOR_INPUT`: `review_center` (confirmations, hard-gate reviews), `requirement_extraction_review` (CR-112, pre-checkpoint, receipt-only), `cost_authorization` (CR-112 cost gate, manual cascade-import resume) `[M]` (`runner.py:262-383`).
- Durable state: `stage0_runs` / `stage0_judgments` (+ `stage0_judgment_corrections`), hash-addressed spools, sha256 receipt IDs, atomic writes, STALE reconciliation (`server/migrations/019_add_stage0_checkpoints.sql`; `scripts/stage0_checkpoint.py`; `scripts/workflow/receipts.py:59-157`; `scripts/workflow/invalidate.py:50-175`) `[M]`.
- Judgment reuse is strictly keyed: changed JD, prompt version, provider policy, evidence index (workExperience.md), or item text invalidates the cache `[M]`.
- Manual cascade import is a real offline escape hatch with exact-text echo binding per item and jd/batch sha256 validation (`stage0_evidence_cascade.py:129-136,172-233`) `[M]`.

### 2.6 Training data for the section classifier (measured)

- `data/stage0_classifier.pkl` = TF-IDF (1-3 grams) + LogisticRegression, trained by `scripts/retrain_stage0.py` from `training_data_clean.csv` + ~1,500 synthetic rows + double-weighted `training_data_feedback.csv` (the feedback file is fed by successful hosted-LLM fallback mappings, Section 2.4) `[M]`.
- Labels are machine-generated (past pipeline outputs + LLM feedback loop + templates). The only human-confirmed set is the 21-entry fit golden set (`data/fit_rubric_golden_set.json`), which validates the **evidence classifier**, not the section classifier `[M]`.

---

## 3. Current Weaknesses

Ordered by severity for the stated goal (reliable 30-JD batches).

**W1. The default path cannot complete a batch offline.** Two load-bearing steps (extraction fallback, evidence cascade) depend on hosted Groq/Gemini free tiers that the operator has measured as unable to get through a ~30-JD batch `[U]`. Published limits corroborate: Groq free tier is on the order of 30 RPM and single-digit-thousands TPM (the code itself encodes "Groq's 8000 TPM free-tier limit", `build_stage0_fit_gate.py:2798-2801`); Gemini free tier is on the order of 15 RPM / 1,500 requests per day `[P]`. A 30-JD batch implies roughly 30-60 cascade calls (one to a few chunks per JD, ≤ 24 items per batch) plus per-JD extraction fallbacks `[E]`. The result under load is either mid-batch 429 throttling or a fail-closed `cost_authorization` pause per JD. Reliability at batch scale is the primary requirement, and the current default path fails it.

**W2. Confidence is uncalibrated and semantically conflated.** `confidence_score` is a weighted average of LLM self-reported high/medium/low labels (×1.0/0.85/0.5), and the same multipliers are multiplied into `RawFit` (`evidence_scale.py:769,894-970`) `[M]`. Two harms: (a) a number presented like a probability is actually a model self-report; (b) multiplying confidence into the score hides low-confidence judgments in the aggregate instead of surfacing them for review. Example: ten required lines all judged level 4 but "low" confidence yield RawFit 50 → silent Tier 2, no review `[E, arithmetic from measured formula]`. The literature is unambiguous that raw model confidence needs post-hoc calibration before it can drive decisions (Guo et al. 2017; Platt 1999; see Section 5.2).

**W3. Machine-labeled training data with a feedback loop.** The section classifier is trained on its own pipeline's past outputs plus mappings produced by the hosted fallback it later depends on (Section 2.6) `[M]`. There is no human-labeled section data and no drift measurement between rounds. This is distillation of an unvalidated teacher, not supervision; retraining can entrench the teacher's errors.

**W4. Multiple hand-set numeric thresholds, none validated.** The 0.65 extraction cutoff, the 1.0/0.85/0.5 confidence multipliers, the 65/40 floors, the 24-item batch cap, the 3/4 repetition rule, and the spec-vs-production band discrepancy (75/50/35 in `fit_rubric_spec.html` vs 65/40 live) are all hand-set constants with no empirical risk/coverage justification on labeled outcomes `[M]`. The spec and code also disagree on confidence threshold details (spec language around 0.65 vs the 0.5/0.85 multipliers in code) `[M]`.

**W5. Dead and stale code paths raise maintenance cost.** Measured inventory: the module docstring still describes the 2026-08-17 "LLM-default" world (`build_stage0_fit_gate.py:22-40` vs the truth at `:2495-2511`); `_classify_one_item` (`:1778-1815`) is dead; `evidence_scale.classify_requirement` (`evidence_scale.py:629-761`) is out of the live flow (tests/`__main__` only); `zero_shot_classifier.classify_location` (`:221-262`) has zero production callers; `domain_gate.check_domain_gate` (`:217-218`) is a deprecated always-pass stub; `anchor_gate` is disabled by default and not wired into the folder Stage 0 path; `server/services/ollamaLifecycle.ts` has no importer; several docs/specs describe the evidence cascade as opt-in while `pipeline_env.stage0_evidence_cascade_enabled()` always returns True (`pipeline_env.py:41-50`) `[M]`.

**W6. Contract drift server-side.** `server/services/runSubmissionRunner.ts:48` `PAUSE_KINDS` omits `requirement_extraction_review`, so `enumOrNull` (`:159-160`) surfaces `kind: null` to the UI for CR-112 pauses `[M]`.

**W7. Operational surface is heavy for one operator.** Three pause kinds, a manual cascade-import JSON with exact-text echoes, a cost-authorization ceremony (free-tier certification expires every 30 days, `cost_eligibility.py:58`), and per-JD folder moves. Each mechanism is individually well-designed (fail-closed, tamper-evident), but the composite is a lot of ceremony for a solo job search `[M]`.

**W8. The extraction stack has three implementations with drift risk.** Regex, LogReg, and local-LLM extractors coexist; the docstring describes one of them as primary when another is (`W5`); tests pin different modes per file. No cross-mode agreement measurement exists on any corpus `[M]`.

**W9. No end-to-end offline regression benchmark.** The 21/21 golden-set gate validates per-line evidence classification only `[M]`. There is no harness that replays a batch of archived JDs end-to-end and compares tier outcomes across versions, which is the metric that actually matters for a tier classifier. (Archive is rich: 453 submissions, 162 skips, 159 ledger rows, 35 pending `[M]`.)

**W10. Semantic matching beyond the curated tables has no offline story.** Evidence retrieval is TF-IDF rarity-weighted token overlap over heading-chunked `workExperience.md` (`evidence_scale.py:133-207`) `[M]`. With the curated VOC/DOMAIN/skills tables this covers a lot, but paraphrase ("customer success tooling" vs a named catalog tool, or a domain alias not yet listed) falls to the hosted LLM today. Offline semantic matching is simply absent, not impossible.

---

## 4. Subproblem Decomposition

Stage 0 decomposes into eight subproblems with sharply different properties. This decomposition is the backbone of the candidate architectures.

| ID | Subproblem | Current solution | Deterministic today? | Error cost |
|---|---|---|---|---|
| S1 | **Identity and memory**: has this posting/company already been decided or cooled down? | Skip ledger + DB gate (SQLite) | Yes | Low (reversible via `--force`) |
| S2 | **Hard exclusion screening**: structural no-gos (title ceiling, years > 7, solo PM, blocked industries, foreign location, travel > 15%, 0-to-1, people mgmt, revenue/billing, AI/ML ownership, blocked tools) | Regex/keyword blocklists + prefs | Yes | **High: false skip loses an opportunity silently**; false pursue wastes Stage 1 hours |
| S3 | **Section extraction**: JD line → required/preferred/responsibilities/culture/exclude | LogReg @ 0.65 + hosted fallback + unresolved queue | Classifier yes; fallback no | Medium (misrouted required line distorts the score) |
| S4 | **Per-requirement evidence judgment**: level 0-4 + HARD gate detection (+ confidence) | Hosted LLM cascade with deterministic evidence context | No | High both ways (false HARD → false skip; missed HARD → false pursue) |
| S4a | — gate detection subset (degree, certification, role exclusion, domain) | LLM category + regex post-checks (e.g. `_degree_hard_gate_allowed`) | Partially | Highest (drives disqualified) |
| S4b | — evidence-level subset (semantic match to Jason's evidence) | LLM with TF-IDF context | No | Medium-high |
| S5 | **Aggregation**: weighted sum, modifiers, floors | Deterministic formula | Yes | N/A (exact) |
| S6 | **Tier decision + skip reasons**: map score+gates → Tier 1/2/Skip with reason codes | Deterministic policy | Yes | N/A (exact given inputs) |
| S7 | **Abstention/review routing**: which items need human eyes | Ad hoc: three pause kinds, unresolved queue, CR-112 gate, hard-gate reviews, tripwires | Mixed | Review load too high → operator bypasses; too low → silent errors |
| S8 | **Data and labels**: golden set, judgment cache, corrections, feedback | 21-item golden set; machine-labeled cache; Review Center corrections (the only human labels) | N/A | Labels gate everything |

Key structural observation: **S1, S2, S5, S6 are already solved deterministically and well** (receipts, ledger, and policy layers are strong, Section 2.5). The open questions are concentrated in S3 (fallback), S4 (the whole judgment), S7 (unified abstention), and S8 (labels).

---

## 5. External Research Review

Each finding is mapped to the subproblem it constrains. Bibliography in Appendix B.

### 5.1 The reject option / selective classification (→ S7)

Chow (1970) formalized the accuracy/reject tradeoff: a classifier that may abstain buys accuracy with coverage, and the optimal policy thresholds the posterior at a cost ratio. Geifman and El-Yaniv (2017) formalized selective classification for deep nets (risk-coverage curves), and Hendrickx et al. (2021) survey the modern design space (reject-option classifiers, conformal-style set predictions, cascades). Implications for Stage 0:

- Abstention is a legitimate, first-class outcome, not a defect. Stage 0 already has three abstention mechanisms; the literature says to unify them, put them on a measured risk-coverage curve, and pick thresholds for an explicit review budget (cost ratio between false skip and false pursue).
- Cascades (cheap-first, escalate on uncertainty) are the standard architecture: deterministic gates first, human review last. This is precisely the shape recommended in Section 7.

### 5.2 Calibration (→ S4b, S7)

Platt (1999) scaling and Guo et al. (2017) (temperature scaling, expected calibration error) establish that raw model confidence must be post-hoc calibrated on held-out labeled data before it can be used as a decision threshold. Brier (1950) scoring is the standard summary. Implications:

- The current 1.0/0.85/0.5 multipliers are not calibrated and should not gate anything until measured (W2).
- Whatever matcher or model produces the per-line score, its confidence needs a reliability diagram on labeled outcomes, and thresholds should be expressed on that calibrated scale.
- For the LLM verbalized confidence specifically: treat it as an unvalidated feature. Measure it (Sp3 in Section 8); do not assume it.

### 5.3 Lexical retrieval: BM25 (→ S4b)

Robertson and Zaragoza (2009) define BM25 and its document length normalization. Thakur et al. (2021) (BeIR) show BM25 remains a strong zero-shot baseline that outperforms many dense retrievers on out-of-domain short text. Implications:

- Stage 0's evidence corpus is small (one candidate's claims and ~7 years of experience chunks) and its queries are short requirement lines: exactly the regime where lexical scoring with a fixed corpus is robust and inspectable.
- A BM25 (or the existing TF-IDF rarity-weighted) matcher over `workExperience.md` + `skills_catalog.json` + curated alias tables is the right deterministic backbone for S4b. The repo already contains a pure-Python BM25 (`scripts/local_embeddings.py:54-127`) `[M]`.

### 5.4 Sentence embeddings on CPU (→ S4b, optional)

Reimers and Gurevych (2019) established SBERT-style bi-encoders for semantic similarity; MiniLM/BGE-small class models run in milliseconds per pair on CPU `[P]`. Implications:

- An embeddings layer is affordable offline, but it adds a model artifact and a calibration surface, and BeIR (5.3) shows lexical often wins on short out-of-domain text. Under the burden-of-proof rule it is a spike-gated upgrade (only if BM25 coverage is insufficient), not a default.

### 5.5 Weak supervision (→ S8)

Ratner et al. (2016) ("data programming") and the Snorkel line of work formalize generating training labels from many noisy programmatic labeling functions with learned weights, using a small labeled set to estimate accuracies. Implications:

- Stage 0's deterministic gates are already labeling functions in all but name (title, years, solo, industry, exclusion zones, tool blocklists). The path from "hand-set regexes with unknown precision" to "measured, versioned labeling functions with estimated accuracies on a labeled set" is exactly what this literature prescribes, and it fits the small-corpus reality.

### 5.6 Classical short-text classification (→ S3)

Wang and Manning (2012) showed simple NBSVM/linear baselines rival far more complex models on short-text classification. The existing TF-IDF/LogReg extraction classifier is the right complexity class for line-level bucketing at this data scale; no deep model is warranted.

### 5.7 Skill and occupation taxonomies (→ S3, S4a)

ESCO (European Commission) and O*NET (US DOL) provide standardized occupation/skill vocabularies with relationships (ESCO v1.2+, O*NET content model) `[P]`. Nesta's open-source Skills Extractor Library (2023) is a deterministic, spaCy-based ESCO-aligned skill extractor for job postings; Skill-LLM (Li et al., 2024) represents the LLM-based alternative. Implications:

- Requirement-line normalization against a standard taxonomy is achievable without an LLM. A curated alias table (the repo already maintains VOC codes, `DOMAIN_ALIASES`, `skills_catalog.json`, `blocked_tools.py`) is the pragmatic domestic equivalent; ESCO/O*NET can be consulted to extend coverage rather than imported wholesale `[E]`.

### 5.8 Simple-baseline discipline (→ all)

The consistent external finding across 5.3, 5.5, 5.6: on small corpora and short text, well-tuned simple methods (lexical scoring, linear classifiers, explicit rules) are competitive with or better than complex models, especially when measured honestly. This aligns with the stated LLM burden-of-proof rule.

### 5.9 Hosted free-tier limits (→ constraint)

Groq's published free-tier limits are on the order of 30 requests/min and 6,000-8,000 tokens/min depending on model (the repo's own comment encodes the ~8K TPM figure, `build_stage0_fit_gate.py:2798-2801`); Gemini's free tier is on the order of 15 requests/min and 1,500 requests/day `[P]`. These figures vary over time and by model; the operative constraint is the operator's measured experience that a ~30-JD batch cannot get through `[U]`. Any architecture whose default path requires hosted calls at batch scale fails this constraint by construction.

---

## 6. Subproblem-to-Technology Matrix

"Least complex technology that reliably solves it." The Verdict column anticipates Section 10.

| Subproblem | Current | Recommended least-complex technology | LLM justified? |
|---|---|---|---|
| S1 identity/memory | SQLite ledger + cooldowns | Keep as-is | No |
| S2 hard exclusions | Regex blocklists + prefs | Keep; add per-rule hit-rate telemetry and a false-positive review of historical Skips (Sp2c) | No |
| S3 section extraction | LogReg + hosted fallback | Keep LogReg; **replace hosted fallback with abstention → CR-112 gate** (already built); optionally spike local-LLM fallback later | No for hosted; local only as spike |
| S4a gate detection (degree/cert/role/domain) | LLM category + regex checks | **Deterministic detection**: degree regex vs Jason's education (the `_degree_hard_gate_allowed` logic is already the right shape), certification/blocklist vs catalog, exclusion zones (S2 overlap), domain via alias tables + years | No |
| S4b evidence level 0-4 | Hosted LLM + TF-IDF context | **Deterministic matcher**: BM25/TF-IDF over WE chunks + skills catalog + curated aliases → level with explicit score; abstain band → local LLM adjudication (offline) → human review | Hosted: no. Local: conditionally, abstain band only, gated on Sp1/Sp2 |
| S5 aggregation | Deterministic formula | Keep formula; **remove confidence multiplication from the score** (confidence routes to review instead; Section 11) | No |
| S6 tier decision | Deterministic policy + floors | Keep; add near-floor abstention (score within ±ε of a floor → review) and keep locked floors stable until recalibration is measured | No |
| S7 abstention routing | Three ad hoc mechanisms | **Unified calibrated abstention layer** with a risk-coverage operating point tied to a review budget | No |
| S8 data/labels | Machine-labeled cache + 21 golden | Expanded human-confirmed gold set (tier-level), versioned labeling functions, corrections table as error labels | No |

---

## 7. Candidate Architectures

All candidates share the preserved core: skip ledger, DB gate, prefs gate, receipts/checkpointing, Review Center, placement, and the hard-gate principle that no model may silently finalize a HARD (review-first is already enforced and stays).

### Candidate A: Status Quo Hardened

Keep the NLP default + hosted cascade. Add: paid-tier budget, smarter 429 backoff, the Phase-0 hygiene fixes (Section 14).

- Pros: zero behavior change; fixes W5/W6 cheaply.
- Cons: fails the reliability constraint (paid cost or throttled batches), keeps uncalibrated confidence at the core, keeps the training feedback loop. Paying for hosted calls converts a reliability problem into a recurring cost + external dependency.
- Verdict: **rejected as target** (fails W1). Its hygiene items are absorbed into every other candidate's Phase 0.

### Candidate B: Deterministic-First with Calibrated Abstention (zero-LLM default)

- S3: LogReg @ 0.65; low-confidence lines go **straight to the CR-112 qualification-risk gate** (no hosted fallback). NON_QUALIFICATION bypasses; the rest queue for review, exactly as CR-112 already does.
- S4: deterministic matcher: curated alias tables (VOC, DOMAIN_ALIASES, skills catalog, blocked tools) + degree/cert regexes (S4a) + BM25/TF-IDF evidence scoring with an explicit abstain band [τ_low, τ_high] (S4b).
- S7: abstain band → batch-level human review (a review file per batch, not per line). Near-floor score → review.
- Everything else unchanged.
- Pros: fully offline, zero tokens, fully deterministic and reproducible, maximally explainable (every decision cites a rule or a score with visible evidence), cheapest to test (no model in the loop).
- Cons: abstain band size is unknown until measured; genuinely novel paraphrase may reach review where an LLM would have resolved it. Review load is the bet: if the median JD adds 1-2 review lines, a 30-JD batch adds 30-60 lines, too much for a solo operator to adjudicate by hand every session.
- Verdict: **the baseline and the bar**. Every other candidate must beat it on measured evidence.

### Candidate C: B plus Local-LLM Adjudication of the Abstain Band

Same as B, but the abstain band is first adjudicated by the **local** Ollama model (`qwen2.5:7b-instruct-q4_K_M` q4, fits 16 GB VRAM `[M]`), batched exactly like today's cascade (≤ 24 items). Only what the local model still cannot resolve confidently goes to human review. HARD proposals from the local model route to Review Center (existing hard-gate review principle).

- Critical practical fact: **this is largely configuration today**. `stage0_evidence_classification.provider_order` accepts `["local"]`, `local_only` exists, and `LOCAL_ONLY_MODE` is already implemented (`stage0_evidence_cascade.py:82-113`; `utils.py:1025-1028`) `[M]`. What is missing is (a) local-model quality evidence on the golden set (Sp1), (b) the deterministic matcher + abstain band in front of it (so the local model sees only the hard minority), and (c) calibration.
- Pros: offline and self-sufficient at batch scale; bounds local inference to the abstain band (minutes per batch `[E]`); keeps LLM strengths where they plausibly matter (paraphrase) while removing them everywhere else; review load shrinks to the residue.
- Cons: local 7B judgment quality is unmeasured (Sp1 is mandatory before it decides anything); local LLM is still non-deterministic across hardware/model versions (mitigated: judgments are checkpointed with model identity in the run key, and temperature 0 + validation layers exist today).
- Verdict: **the likely landing spot**, gated on spikes. B remains the fallback if the local model fails the golden-set gate.
- **Revision 2026-09-16: superseded.** User testing found the local small model unreliable for rubric judgment (it remains measured-good only for extraction bucketing, Section 2). The abstain band now escalates to a subscription-backed offline tutor rather than a local runtime judge; see Section 17. The "config-reachable today" observation survives only as an emergency escape hatch (`LOCAL_ONLY_MODE`).

### Candidate D: End-to-End Classical Tier Classifier

Train a supervised classifier (LogReg/GBM over features: gate outputs, matcher scores, JD n-grams, seniority/title signals) to predict Tier 1/2/Skip directly from ~600 historical decisions.

- Pros: simple, fast, deterministic at inference, a cheap shadow-agreement baseline.
- Cons: the historical labels were produced by the incumbent system (machine-labeled, W3), so the classifier learns to imitate the current system, errors included (circularity); per-line explainability is lost exactly where false skips originate; no path to "better than today", only "cheaper than today".
- Verdict: **not a decision system**; useful only as a shadow baseline for agreement measurement (its disagreement with the rule stack is itself a tripwire).

### Candidate E: Embeddings-First Matcher

Replace BM25 in S4b with CPU sentence embeddings (MiniLM/BGE-small) + cosine thresholds against claim/WE-chunk vectors, calibrated on the gold set; deterministic gates unchanged.

- Pros: handles paraphrase without any LLM; millisecond latency on CPU `[P]`; thresholds calibratable like any score.
- Cons: adds a model artifact + vector-index maintenance; less inspectable than BM25 (though similarity scores are still explainable); BeIR evidence says lexical is often stronger on short out-of-domain text (5.3); Jason's corpus already has curated alias tables that cover much of the paraphrase space deliberately.
- Verdict: **spike-gated variant of B**, only if Sp2 shows BM25 coverage insufficient. Burden of proof not currently met.

### Comparison

| Goal | A (status quo) | B (deterministic) | C (B + local adjudication) | D (end-to-end ML) | E (embeddings) |
|---|---|---|---|---|---|
| Reliability at 30-JD batch scale | Fails (W1) | Pass | Pass | Pass | Pass |
| Determinism/reproducibility | No (hosted LLM core) | Yes | Mostly (local LLM band, checkpointed) | Yes | Yes |
| Explainability | Good (verdicts cite lines) | Best | Good | Worst (aggregate) | Good |
| Marginal cost per batch | Free-tier stalls or paid $ | Zero | Zero (local compute) | Zero | Zero |
| Testability | Hard (mocks/network) | Trivial (pure functions) | Easy (band only) | Easy | Easy |
| Maintainability | 3 extract paths + cascade + drift | Most rules already exist | Adds matcher + local band | New model + features | New artifact + index |
| Review load per batch | Lowest when hosted works | Highest (unknown) | Low-medium `[E]` | Low | Medium |
| Migration effort | Low | Medium | Medium (config-reachable core) | Low (shadow only) | Medium |

---

## 8. Benchmarks and Spikes

All spikes run offline against archived data and the gold set. None touch production paths. Sizes are estimates `[E]`.

| ID | Spike | Protocol | Success criterion | Effort |
|---|---|---|---|---|
| Sp1 | **Local-model golden-set replay** | Configure the existing cascade with `provider_order: ["local"]`; replay the 21-item golden set + the per-line judgments of ~50 archived JDs from `stage0_judgments`; compare gate + gap_source + level (±1) agreement and latency per chunk | ≥ 19/21 exact gate agreement; 100% of local HARD proposals routed to review (never silent); latency supports a 30-JD batch in < 60 min | 0.5-1 day (config + compare script) |
| Sp2 | **Deterministic matcher prototype** | Build the BM25 + alias-table + catalog matcher as a standalone module; run against (a) 21 golden items, (b) cached judgments (machine labels: distillation agreement only), (c) a Jason-adjudicated sample of ~200 lines drawn from pending + archive | Level agreement within ±1 on ≥ 80% of lines; HARD precision ≥ 95% with recall measured (false skip is the asymmetric cost); abstain band ≤ ~15% of lines on the pending corpus | 2-3 days |
| Sp3 | **Calibration audit** | For the existing cache: verbalized confidence (high/med/low) vs outcomes, using `stage0_judgment_corrections` + hard-gate review answers as error labels; reliability diagram + ECE; separately validate the 0.65 extraction cutoff against CR-112 gate outcomes on 35 pending JDs | ECE reported; decision on whether verbalized confidence carries any signal; cutoff justified or moved | 1 day |
| Sp4 | **Batch throughput, offline** | End-to-end 30-JD replay under B and under C (shadow configs): wall clock, abstain counts, review items, VRAM, hosted calls (must be 0) | C completes a 30-JD batch offline in < 60 min with ≤ ~5 JDs flagged for review `[E, budget for Jason to tune]` | 0.5 day |
| Sp5 | **Extraction-fallback removal impact** | Replay 35 pending_review JDs with the hosted extraction fallback disabled (low-confidence → CR-112 gate only): count review items per batch vs today | Marginal review load per 30-JD batch ≤ ~5 JDs; if higher, keep a local fallback spike on the list | 0.5 day |
| Sp6 | **Threshold sweep (risk-coverage)** | Sweep matcher abstain thresholds and near-floor ε on gold + archive; produce risk-coverage curves at review budgets (e.g., 3/5/10 JDs per batch) | Jason picks an operating point with measured tradeoff, replacing hand-set constants (W4) | 0.5 day |

Sequencing: Sp1, Sp3, Sp5 can run immediately (config/measurement only). Sp2 gates the rest. Sp4/Sp6 consume Sp2's matcher.

---

## 9. Recommendation

**Adopt Candidate C (deterministic-first, with local-LLM adjudication of the abstain band), built as Candidate B first, with the choice of keeping or dropping the local band made on spike evidence.**

Rationale:

1. **The deterministic skeleton already exists and is good.** S1, S2, S5, S6 plus receipts, checkpointing, ledger, and placement (Section 2.5) are zero-token, deterministic, well-tested machinery. The recommendation is surgical: change the two hosted dependency points and the confidence semantics; do not rewrite the system.
2. **The hosted dependency is the one hard constraint failure** (W1, `[U]`). Both load-bearing hosted uses (extraction fallback, evidence cascade) have offline replacements already half-built: the CR-112 gate was designed for exactly the "low-confidence → route it" case, and the cascade's `local` provider is already implemented and selectable by settings.
3. **Burden of proof lands where it belongs.** Deterministic matching is the default everywhere; the LLM (local only) is confined to the abstain band, where the deterministic matcher has measured uncertainty. That is the cascade shape the reject-option literature prescribes (Section 5.1), and it inverts the current design where the LLM is the primary judge and regexes are the backstop.
4. **Confidence stops being cargo-culted into the score.** Calibration gets measured (Sp3), and low confidence routes to review instead of silently discounting the score (Section 11, fixing W2).
5. **The gold set becomes the arbiter.** The 21-entry golden gate extends to tier-level replay on the archive (W9), so every subsequent change is measured against an offline benchmark instead of vibes.

Decision rule between B and C, from spikes:
- If Sp2 shows abstain band ≤ ~5% of lines and Sp5 shows ≤ ~3 extra review JDs per batch → **stay at B** (drop the local band entirely).
- If the band is wider, or HARD recall in S4a is short of the golden set, → **enable C** (local adjudication of the band), provided Sp1 passes. If Sp1 fails (local model below threshold), return to B with a larger review budget and reassess; hosted paid tiers are the fallback of last resort, not the plan.

Explicitly rejected: paying for hosted calls to keep the status quo (converts W1 into recurring cost and keeps W2/W3); end-to-end ML tiering (D) as the decider (circular labels); embeddings (E) without spike evidence of need.

**Revision 2026-09-16:** the recommendation now reads: Candidate B as the runtime, with the abstain band resolved by an offline subscription-backed tutor instead of a local runtime band (Section 17). The decision rule also changes shape: because the tutor sits off the critical path behind a budget dial, band width is no longer a go/no-go for the runtime flip. The flip is gated on matcher coverage (Sp2) and raw review load (Sp5); the tutor then converts raw review into draft-grading once unblocked.

**Revision 2026-09-17:** Jason clarified that the subscription harness must also be available to resolve uncertain Stage 0 cases during a batch. Section 18 supersedes the runtime-only-deterministic assumption above and in Section 17; the matcher still minimizes calls.

---

## 10. LLM Burden-of-Proof Verdict

Per-subproblem, applying the rule: an LLM is justified only when a simpler alternative demonstrably cannot do the job, and only at the least powerful tier that suffices (hosted > local > none, on cost/reliability grounds here).

| Use | Verdict | Reasoning |
|---|---|---|
| S1 identity/memory | **Not justified** | SQLite lookups; already solved |
| S2 hard exclusions | **Not justified** | Regex blocklists are more auditable than any model; the industry-semantic supplement is fail-open today and its marginal value is unmeasured (fold into Sp2 or into the abstain band) |
| S3 extraction fallback (hosted) | **Not justified** | Creates the batch-scale failure (W1) and a training feedback loop (W3); the CR-112 gate already provides the abstain path. Local-LLM fallback is a spike-gated option (Sp5) |
| S4a HARD gate detection | **Not justified** | Degree/certification/role-exclusion/domain are pattern problems with a fixed, small target ontology; regex + alias tables + catalog cover them deterministically, and LLM HARD proposals are already demoted unless grounded and reviewed |
| S4b evidence level | **Hosted: not justified** (reliability, cost, determinism). **Local: conditionally justified** | Offline reliability is a hard constraint; a deterministic matcher handles the bulk; for the residual paraphrase band, a local 7B is the least powerful sufficient tier, admitted only after Sp1 (quality) and Sp2 (band size) |
| S5 aggregation, S6 tiering | **Not justified** | Pure arithmetic/policy |
| S7 abstention | **Not justified** | Thresholds + calibration, no model needed to decide *when to ask* |
| Verbalized confidence as a decision input | **Not justified until calibrated** (Sp3) | Raw self-report (W2); the literature (5.2) requires post-hoc calibration before use |

Net: the current system uses the LLM as the primary judge for the one subproblem where a deterministic-plus-abstention design is viable, and as a fallback for a subproblem that already has a deterministic abstention path. Both usages fail the burden of proof at the hosted tier. The local tier passes only for the abstain band, pending Sp1.

**Revision 2026-09-16:** the "local tier passes, pending Sp1" clause is withdrawn. Testing found the local small model unreliable for rubric judgment, and the subscription tutor replaces it in an offline teaching role (Section 17). After the revision, no LLM holds runtime decision authority at any tier. The only admitted LLM role is teacher: off the critical path, spending already-paid subscription budget at a controlled rate, with every label validated before use.

---

## 11. Confidence and Abstention Design

### 11.1 What exists today (measured)

- Per-line confidence is LLM self-report (high/medium/low) multiplied into the score (`evidence_scale.py:769`).
- Extraction confidence is a LogReg predict_proba with a hand-set 0.65 cutoff (`build_stage0_fit_gate.py:1195-1202`).
- Abstention exists in four disconnected forms: the unresolved-lines queue, the CR-112 three-way gate, hard-gate reviews, and the cost pause. No shared vocabulary, no shared thresholds, no coverage measurement.

### 11.2 Proposed design

**Principle 1: two channels, never mixed.**
- **Rule channel**: deterministic gates emit booleans + cited rule IDs. No confidence value exists or is needed; explainability is the rule citation.
- **Score channel**: the matcher emits a level/score plus a *calibrated* confidence plus an explicit abstain band. Confidence never multiplies into the score (removes W2's conflation; a level-4-low-confidence line raises review, it does not silently drag RawFit to 50).

**Principle 2: abstention is a state machine, not an exception.** Unify the existing pauses into three named abstentions:

| State | Level | Trigger | Resolution path |
|---|---|---|---|
| `EXTRACT_ABSTAIN` | line | LogReg p < cutoff | CR-112 three-way gate → bypass or review (already built) |
| `MATCH_ABSTAIN` | line | matcher score in [τ_low, τ_high] | local-LLM adjudication (C) → still-uncertain → batch review file |
| `POLICY_ABSTAIN` | JD | final score within ε of a floor (e.g. 62-68 vs the 65 floor), or `required_empty`, or thin JD | batch review with both rule-channel and score-channel evidence attached |

This generalizes what CR-112 already proved: deterministic routing of uncertain items to named review buckets works and the operator can answer a structured template.

**Revision 2026-09-16:** the MATCH_ABSTAIN resolution path becomes "subscription tutor drafts an answer offline; the batch review file arrives pre-answered; you grade." The state machine is unchanged; what changes is who drafts the answer (Section 17).

**Principle 3: thresholds are data, chosen on a risk-coverage curve.** Sp6 produces the curves; the operating point is a review budget Jason picks (e.g. "≤ 5 JDs flagged per 30-JD batch"), replacing hand-set constants (W4). The false-skip / false-pursue cost asymmetry is explicit in the choice (Chow's cost ratio, 5.1).

**Principle 4: HARD gates are never model-silent.** Keep and strengthen the existing invariant: any model-proposed HARD (local or otherwise) requires grounding and routes to Review Center; only deterministic gate detection can finalize a Skip directly. This is already close to true (unsafe-HARD demotion, hard-gate reviews); make it absolute in the new matcher (S4a is deterministic anyway).

**Principle 5: confidence is calibrated and reported.** Temperature/Platt scaling on the gold set for the matcher score; ECE/Brier reported in the shadow harness; verbalized confidence is measured (Sp3) and used only if it survives calibration.

**Batch ergonomics (new):** abstentions roll up per batch into one review file (per-JD sections with the specific lines, evidence snippets, and proposed resolutions), so a 30-JD session produces at most one review event, not N pauses. This directly addresses W7.

---

## 12. Evaluation Framework

### 12.1 Gold dataset

- **Tier-level labels (new, the critical asset):** sample ~100 JDs stratified across the corpus (453 archived submissions, 162 archived skips, 159 ledger rows, 35 pending `[M]`), preserving the real tier mix; Jason labels each with Tier 1 / Tier 2 / Skip from the JD alone. This is the only label set that measures what Stage 0 actually outputs. Estimated effort: ~100 labels × 1-2 min `[E]`.
- **Line-level labels:** keep the 21-entry golden set as the hard regression gate; extend opportunistically with lines adjudicated during batch reviews (each MATCH_ABSTAIN resolution is a human label; `stage0_judgment_corrections` already stores corrections `[M]`).
- **Distillation set (not ground truth):** the cached `stage0_judgments` corpus (~thousands of machine labels) is used for agreement measurement only, never as ground truth (W3 discipline).

### 12.2 Metrics

| Metric | What it catches | Target `[E]` |
|---|---|---|
| False-skip rate on gold set (Tier 1/2 labeled, system says Skip) | the asymmetric worst error | ≤ 2% |
| False-pursue rate (Skip labeled, system says Tier 1/2) | wasted Stage 1 hours | ≤ 5% |
| Review rate per 30-JD batch | operator burden | ≤ 5 JDs (budget chosen in Sp6) |
| HARD-gate precision/recall on golden set | disqualified decisions | precision ≥ 95%, recall reported (21-item set is small; grow it) |
| Matcher level agreement (±1) on golden + adjudicated lines | S4b quality | ≥ 80% before flip |
| Calibration: ECE/Brier on score channel | W2 fix | ECE < 0.05 on labeled set, cross-validated |
| Shadow agreement vs current system (Cohen's κ on tier) | drift between old/new | measured before flip; disagreements adjudicated |
| Determinism property tests | reproducibility | same input hash → byte-identical output, no network |

### 12.3 Testing strategy

- Existing per-gate unit pins continue (they are good) `[M]`.
- Add: golden-set replay as an offline, CI-able script (extend the existing `check_fit_rubric_golden_set.py` pattern to the matcher); determinism property tests (freeze network, hash outputs); calibration regression tests (thresholds are versioned data files; changing one requires a curve re-run).
- Shadow harness (Section 14) doubles as the batch-level regression: every code change that touches scoring re-runs the 100-JD gold replay and reports metric deltas.

---

## 13. Observability and Versioning

**Keep (already strong `[M]`):** sha256 receipts with input/output hash maps; `stage0_runs`/`stage0_judgments` with run_key over (opportunity, jd_hash, prompt_version, provider_policy_hash, evidence_index_hash); hash-addressed spools; `run_events.jsonl`; STALE reconciliation; the llmUsage surface reading run status.

**Extend:**
1. **Version every decision input into the run key inputs**: matcher version, calibration version, abstain-threshold version, alias-table version. The cache-invalidation machinery already handles multi-input hashing; these become additional hashed inputs so stale judgments never leak across versions `[E, low risk since the pattern exists]`.
2. **Per-batch shadow diff report**: for every JD run in shadow, record both old and new tier + the top contributing rules/scores; a per-batch summary lists disagreements. This is the acceptance artifact for the flip (Section 14).
3. **Abstention telemetry**: counts by state (EXTRACT_ABSTAIN bypassed vs reviewed; MATCH_ABSTAIN local-resolved vs human-resolved; POLICY_ABSTAIN rate), review-latency, and per-rule hit rates (which regexes fire how often; a rule that never fires or always fires is a maintenance signal).
4. **Hosted-call counter**: after the flip, Stage 0's hosted call count must be zero; the meter makes regressions visible immediately.

**Data versioning:** `fit_rubric_calibration.json` gains matcher/calibration/threshold version fields; gold set is content-hashed and the hash recorded in every replay report.

---

## 14. Migration Plan (Shadow Mode)

Nothing below executes before a CR is written (per the repo's SDD rules); this is the plan for that CR. Every phase is independently revertible; decisions only flip at Phase 3+ and only on measured agreement.

| Phase | Content | Behavior change | Rollback |
|---|---|---|---|
| **P0 Hygiene** | Fix `PAUSE_KINDS` to include `requirement_extraction_review` (`runSubmissionRunner.ts:48`); update the stale module docstring; delete dead code (`_classify_one_item`, `classify_location`, `check_domain_gate` stub, orphaned local score-model machinery) with tests; reconcile spec-vs-production band docs | None | Trivial |
| **P1 Data + harness** | 100-JD gold set labels; archive replay harness (offline); corrections/corpus extraction for Sp3 | None (read-only tooling) | n/a |
| **P2 Matcher + abstention, shadow only** | Deterministic matcher module; calibrated abstention layer; shadow scorer runs alongside every live Stage 0 and writes per-JD diffs; **no decision authority** | None (shadow writes only) | Delete shadow output |
| **P3 Decision flip** (gated: Sp2 + Sp3 + shadow agreement + Jason sign-off) | Default path: extraction fallback → CR-112 abstention; evidence judgment → matcher (+ local adjudication band if Sp1 passed); confidence removed from RawFit; near-floor POLICY_ABSTAIN live; floors unchanged until P3 metrics justify recalibration | Yes: default becomes offline-first | Settings flag restores hosted cascade (`provider_order`); matcher bypass flag |
| **P4 Conditional local band** (only if Sp1 passed and Sp2 band > budget) | Enable local provider for MATCH_ABSTAIN; Review Center routing for local HARDs | Bounded | Remove `local` from provider order |
| **P5 Retirement** | Remove hosted calls from Stage 0 code paths (manual cascade import stays as escape hatch; Gmail/interview features untouched); docs + CHANGELOG + traceability updates; archive the old cascade docs | Cleanup | n/a |

Acceptance gates: P3 requires ≥ 1 month or ≥ 60 JDs of shadow runs, false-skip rate on gold ≤ 2%, review budget met, and zero unexplained disagreements. P4 requires the Sp1 golden-set gate.

**Revision 2026-09-16:** P4 is replaced by the offline learner worker (Section 17.8): a subscription-backed tutor queue with a budget dial and no runtime provider change. Its acceptance gate is the claudexor version pin (≥3.12.1; the daemon crash was fixed upstream in 3.12.1, so no external fix is pending) plus harness smokes and a timed agreement replay, not Sp1. P3 is unaffected.

**Revision 2026-09-17:** the staged order and runtime behavior above are superseded by Section 18. Harness fallback is an early Stage 0 workstream, not a P4-only learner feature. The production switch requires the harness path and the NLP/matcher path to pass separate batch-scale gates.

---

## 15. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Deterministic matcher under-covers: abstain band too wide for solo-operator review | Medium | High (batches bog down in review) | Sp2/Sp5 measure before any flip; Candidate C absorbs the band; review budget chosen explicitly (Sp6) |
| R2 | Local 7B judgment quality (was: Sp1 fails) | Resolved 2026-09-16 | — | User testing found the local model unreliable for judgment; it is removed from the decision and tutor paths (Section 17). Sp1 survives only as a recorded benchmark; `LOCAL_ONLY_MODE` stays as an emergency escape hatch |
| R3 | Gold set inherits incumbent bias (Jason labels from memory of past decisions) | Medium | Medium (metrics flatter the new system) | Label blind to the system's past verdict (label from JD text only); stratified sampling; report disagreement adjudication |
| R4 | Calibration overfits a small labeled set | Medium | Medium (mis-set thresholds) | Cross-validate; version calibrations; re-estimate as adjudicated labels grow; report ECE with intervals |
| R5 | Score-band semantics shift when confidence leaves RawFit (floors 65/40 were locked against the old formula) | **Certain if P3 lands as designed** | High if unmanaged | Recalibrate floors on the gold set during shadow (P2 produces both old- and new-formula distributions); Jason re-locks; document in the CR |
| R6 | Regex rules overfit the historical corpus (garden of forking paths for blocklists) | Medium | Medium (false skips drift in) | Per-rule hit-rate telemetry + periodic false-skip review (Sp2c); version alias tables |
| R7 | Dual system during shadow raises ops complexity | Medium | Low-Medium | Timeboxed; shadow is read-only; diff report is one file per batch |
| R8 | Removing the hosted extraction fallback degrades classifier retraining data volume | Low | Low | Feedback loop was part of the problem (W3); retraining continues from adjudicated reviews, which are human-confirmed |
| R9 | Local model VRAM contention with other pipeline stages | Low | Low | `_release_stage0_vram` and keep-alive flags already manage this `[M]`; batch band inference is small |
| R10 | Server/UI surfaces lag new abstention states (repeat of W6) | Medium | Low | P0 pattern: contract-first; add abstention kinds to `PAUSE_KINDS`/UI enums in the same change, with tests |
| R11 | Subscription tutor drafts contaminate the label corpus (confidently wrong answers get auto-accepted) | Medium | High (poisons future matcher training; hard to distinguish from good labels afterward) | Precision-first policy (Section 17.3): grounding check + adaptive self-consistency (double-ask only near-threshold or HARD-proposing items; disagreement escalates, per 17.10) + engine-validated schema; auto-accept threshold derived from the measured blind-audit error rate; consequence-ranked items always human-graded |
| R12 | Subscription caps or harness instability throttle learning | Medium | Low (learning slows; runtime unaffected by design) | Budget dial on the learner queue; tutor is off the critical path; raw review and manual cascade import remain the floor |
| R13 | Case bank and alias tables drift from an updated `workExperience.md` | Low | Medium (stale aliases mis-score) | Alias/case-table versions join the run_key hashed inputs (the pattern already exists, Section 13), so stale judgments invalidate instead of silently reusing |
| R14 | Automation bias: pre-answered drafts get rubber-stamped, so wrong tutor labels slip through review | Medium | Medium-High (silently undermines the precision-first policy) | Evidence-first display + blind-audit sample (17.5); blind-vs-seen delta tracked on the dashboard (17.7); auto-accept threshold tied to the measured delta. External evidence says this risk is real, not hypothetical (Appendix B: jagged-frontier field experiment; persuasion-bombing study) |

---

## 16. Implementation Plan

Story-level plan for the future CR (not executed now). Sizes are `[E]`.

**P0 Hygiene (0.5-1 day total)**
1. Add `requirement_extraction_review` to server `PAUSE_KINDS` + UI handling + tests. (BUG-class)
2. Rewrite `build_stage0_fit_gate.py` module docstring to the NLP-default reality; delete dead paths (`_classify_one_item`, `classify_location`, `check_domain_gate`, orphaned score-model prep) with test updates. (CR-story)
3. Reconcile spec band values (75/50/35) vs production (65/40) in docs with an explicit "production wins; recalibration planned" note.

**P1 Data + harness (2-3 days, plus subscription replay time)**
4. Gold-set sampling + labeling tool (stratified sample, JD-only labeling UI or markdown worksheet) + import script.
5. Archive replay harness: offline re-run of Stage 0 over a JD list with network frozen; outputs per-JD diffs vs the archived verdicts.
6. Calibration corpus extractor: dump judgments + corrections into the Sp3 table.
6a. Subscription wire validation (mandatory): pin `claudexor@3.12.1`, smoke the real evidence-cascade schema through `claude`, `codex`, and `agy`, inspect warnings, then time and score 5-10 archived JDs against the gold set. Record harness version, latency, failures, and agreement. Do not set auto-accept thresholds until these measurements exist (Section 17.8).

**P2 Matcher + abstention, shadow (4-6 days)**
7. `stage0_matcher.py`: alias tables + BM25 scoring + degree/cert regexes + abstain band; pure functions; unit pins per rule; versioned data files.
8. Calibrator: temperature/Platt on gold lines; ECE/Brier report; threshold sweep tool (Sp6).
9. Shadow scorer: runs in every live Stage 0, writes `stage0_shadow_diff.json` per JD + per-batch summary; zero decision authority.
10. Batch review-file rollup (one file per batch for MATCH_ABSTAIN/POLICY_ABSTAIN).

**P3 Flip (2-3 days + soak)**
11. Wire matcher as default S4 path; extraction fallback → CR-112 abstention (config-gated during soak); remove confidence multiplication from RawFit (recalibrated floors from P2 data, Jason re-locked); POLICY_ABSTAIN near-floor rule; update contract tests, receipts, and `stage0_runs` metadata with new version inputs.
12. Settings flag + rollback path documented; hosted-call counter at zero asserted in telemetry.

**P4 Offline learner worker (revised 2026-09-16; 3-5 days, after P1 wire validation)**
13. Learner queue: abstain-band items plus archive replay jobs, throttled by a subscription budget dial; dispatches to claudexor with `--access readonly` + `--output-schema`; populates `subscription_minutes` as its own cost class (never `api_cents`); validation gate before any auto-accept (grounding + self-consistency + schema conformance).
14. Draft-to-review pipeline: tutor drafts flow into the batch review file pre-answered; Review Center and `stage0_judgment_corrections` capture every resolution as a permanent artifact (alias, rule, label, or correction), with the failing line pinned as a regression test.
15. Retraining on adjudicated labels only (replaces the `training_data_feedback.csv` loop, fixing W3); case-bank dedup so a taught phrase is never re-taught; the "relies less" dashboard (Section 17.7) goes live with the first learner run.

**P5 Retirement (1-2 days)**
16. Remove hosted Stage 0 call sites (keep manual cascade import + other features' clients); full docs pass: CHANGELOG, README structure section, spec CR, traceability matrix.

**Out of scope:** Stage 1+ behavior, scout ingest gates, Gmail/interview LLM features, any change to the locked floors without the recalibration evidence from P2.

**Revision 2026-09-17:** Section 18 replaces this phase order. Stage 0 harness fallback must be implemented and tested before depending on it for a batch; offline tutor work may follow later. Stage 1-3 improvements are a future sequence, not part of this Stage 0 change.

---

## 17. Addendum: Revised Learning Architecture (2026-09-16)

This section records the design that emerged from follow-up discussion plus the claudexor spike (`docs/spec/08-implementation/INVESTIGATION-2026-09-16-claudexor-stage0-fallback-spike.md`). It supersedes specific earlier text, itemized in 17.9.

### 17.1 New evidence since the original report

1. **Local small model, rubric judgment: unreliable** `[U]`. Testing found the small local model (the qwen 7B class pinned for the opt-in `llm` extraction mode) unreliable for the per-requirement 0-4 judgment and labeling role. It remains measured-good only for extraction bucketing (the PracticeTek measurement cited in Section 2); that opt-in extraction mode is untouched by this revision. Consequence: no local LLM in the Stage 0 decision path or the tutor path, and Stage 0 stops competing for VRAM entirely. Rules, BM25, LogReg, and any future embedding-based matcher all run on CPU in milliseconds `[M]`, so the 16 GB VRAM budget becomes irrelevant to Stage 0 and the model keep-alive/VRAM-release machinery goes vestigial.

2. **Subscription-backed calls are viable; real-schema validation remains** `[M]` (spike doc):
   - Auth verified through the claudexor CLI for three profiles: `claude` (Claude Pro), `codex` (ChatGPT Plus), and `agy` (Antigravity, bound to `gemini-3.8-flash-high`). `cursor` is not reliably verifiable and is deferred.
   - The same subscription-routing pattern (subscription login instead of metered API token) is in production use by Metis on this machine, so the path is proven end-to-end for engineering dispatch.
   - The CLI already exposes the exact call shape Stage 0 needs, distinct from Metis's methodology-gated dispatch: `--access readonly`, `--output-schema` (engine-validated JSON conformance), `--max-seconds`, no git/workspace requirements.
   - The cost machinery anticipated this: `cost_eligibility.py` tracks `subscription_minutes` as a class distinct from `api_cents`, currently hardcoded to 0, waiting to be populated. Subscription time is never summed with metered API cost, and the free→paid prohibition stays intact.
   - Blocker (resolved 2026-09-16): the readonly + directory + output-schema dispatch combination crashed on claudexor 3.12.0 (`daemon connection closed`, three spike attempts with a freshly started daemon; per-invocation daemon death in the logs). Follow-up found claudexor **3.12.1 had shipped on 2026-09-15**, the day before the spike ran against the npx-cached 3.12.0. A same-day A/B smoke test reproduced the exact crashing flag combination (`agent ... --access readonly --workspace-kind directory --no-review --json --output-schema`, harness `claude`) **against 3.12.1 and it succeeded**: run completed, exit 0, engine-validated structured output at `final/output.json`, verified schema-conformant (attempt status `success_with_warnings`; warnings to be enumerated in the learner smoke suite) `[M]`. The subscription wire to the only LLM tier in this architecture is real and available today; what remains is a version pin plus validation, not a bug fix (17.8).

### 17.2 The structural change: runtime and learning are separated

```
RUNTIME (every batch; deterministic + ML only; no LLM; no subscription)
  rules → matcher → confident lines resolve
                 → uncertain lines → batch review file (raw until the offline tutor has processed them)

LEARNER (offline worker; throttled; never on the batch critical path)
  abstain backlog + archive replay → subscription tutor → validated draft labels
  → human spot-check (stratified sample) → labels retrain the ML
  + aliases/rules grow the case bank → abstain band shrinks
  → tutor call count per batch falls toward zero
```

What this buys:

- **A batch can never be blocked by the subscription.** Caps, outages, and daemon bugs are inconveniences for learning, not broken pipelines. The reliability constraint that killed the hosted-cascade design (W1) is satisfied structurally rather than hoped for.
- **The budget is a dial, not a gamble.** The learner is a queue; more budget means faster learning, and a large batch never touches subscription quota at runtime. The "large batches obliterate the budget" failure mode is designed out.
- **"Every run relies on it less" becomes measurable** (17.7) instead of aspirational. Runtime reliance is zero by construction; the tutor's effect shows up as a shrinking band and falling tutor call counts. If those numbers do not fall, the loop is broken and the dashboard says so.

### 17.3 The tutor ladder (revised)

| Tier | Who | What it handles | Cost |
|---|---|---|---|
| 1 | Deterministic matcher (rules, alias tables, BM25, LogReg) | the confident ~85-90% of lines `[E]` | zero; CPU; milliseconds |
| 2 | Subscription tutor (claude/codex/agy via claudexor, readonly + schema) | the abstain band; drafts labels offline | already paid; capped; budget dial |
| 3 | Human (Jason) | grades drafts; corrects; every correction becomes a permanent artifact | minutes per batch, falling |

Why the local model is out, stated precisely: classical methods fail loudly (unmatched line abstains and surfaces), reproducibly (same input, same output, unit-testable), and permanently fixably (add the alias, pin the test, that failure class is dead). The small model fails silently (confident wrong answers), stochastically (same line can judge differently across runs), and unfixably (re-prompting does not kill the error class). For a teaching loop this asymmetry is decisive: **label precision beats label coverage.** A wrong label is worse than a slow label, because it poisons the ML corpus and cannot be distinguished from a good label afterward, whereas an abstention merely waits. A tutor that is wrong 30% of the time but sounds sure is worse than no tutor, since it forces a spot-check rate that eats the human time it was meant to save.

### 17.4 Budget economics (why a 30-JD batch does not obliterate the quota)

- **Only the band is taught, never the JD.** At a 10-15% band, a 30-JD batch produces roughly 30-60 teachable lines `[E]`, not 300-400.
- **Phrases repeat, so teaching dedups.** "Stakeholder management" appears across many JDs; teach it once, it enters the case bank, every future occurrence resolves free. Dedup applies within a batch and across batches.
- **The requirement space is finite-ish.** PM JD requirement lines cluster into a few canonical shapes (a tool, a domain, a years threshold, a degree, a certification, a deliverable, a soft skill). The endgame is a curated ontology plus a case bank; the tutor is the curator that builds it and then mostly retires.
- **The first few batches are the expensive ones**; marginal tutor cost per batch decays `[E]`. The dashboard verifies this instead of assuming it.

### 17.5 Review ergonomics: grade, don't solve (amended after pressure test, 17.10)

- Once the offline learner processes an item, its review entry gains the tutor's proposed label, cited evidence line from Jason's history, and reason. Before that, the raw item remains reviewable. Correcting a draft yields a labeled example of exactly where the system was wrong.
- **Evidence-first display (17.10 amendment):** each item shows the JD line and the matched evidence from Jason's history first; the tutor's verdict and reasoning stay collapsed until requested. External evidence (Appendix B: Amplified Oversight) shows AI labels and explanations presented up front cause over-reliance, while evidence-first presentation fosters appropriate trust. The draft speeds review without doing the persuading.
- **Blind-audit sample (17.10 amendment):** a fixed fraction of band items (plus every tier-flipping or HARD-proposing item not otherwise graded blind) is presented with no draft at all. The delta between blind and seen-draft agreement rates measures automation bias directly (Appendix B: jagged-frontier field experiment; persuasion-bombing study); a widening delta tightens the auto-accept threshold.
- Review is consequence-ranked: items that would flip a tier decision or propose a HARD always get eyes; mid-band routine lines can wait for tutor consensus. Framing amended per 17.10: this is a safety property that guarantees the most-consequential items are always human-graded; it is not claimed as a labeling-budget optimizer.
- **No review closes without a permanent artifact**: an alias added, a rule edited, a judgment corrected, or a labeled line, plus the failing line pinned as a regression test. The capture points already exist (`stage0_confirmations` Review Center, `stage0_judgment_corrections`, versioned data files); the new work is wiring resolution to artifact, not inventing the store.
- Retraining moves to adjudicated labels only, which replaces the machine-labeled `training_data_feedback.csv` loop and fixes W3 at the same time.

### 17.6 Free signals

Application outcomes the system already records (applied, interviewed, rejected, ghosted, cooldown data the DB gate consumes) are weak but zero-cost calibration telemetry about where the 65/40 floors actually sit. Use as directional signals only; outcomes are confounded by market conditions and Stage 1 quality, so they are never labels.

### 17.7 The "relies less" dashboard

Review load, abstention, tutor calls, correction rate, and the blind-versus-seen delta should fall over comparable batches. Tutor-human agreement should rise; metered API calls must remain zero. Investigate adverse movement across two consecutive batches rather than treating every rising metric as a failure:

| Metric | Initial target `[E]` |
|---|---|
| Abstain band as % of lines | ≤ 10-15% at start, then falling |
| Tutor calls per 30-JD batch (after dedup) | ≤ ~5 |
| Human review items per batch | ≤ ~5 JDs' worth, then falling |
| Tutor-human agreement on stratified spot-checks | measured continuously; auto-accept only above the measured bar |
| Blind vs seen-draft agreement delta (automation bias) | near zero; a widening delta tightens the auto-accept threshold |
| Correction rate | falling |
| Metered API calls | zero, always |

### 17.8 The claudexor wire: proven; what remains to build it (updated 2026-09-16, superseded by Section 18)

The spike's daemon crash occurred on claudexor 3.12.0; the exact crashing combination (`agent ... --access readonly --workspace-kind directory --no-review --json --output-schema`, harness `claude`) succeeded on 3.12.1 with schema-conformant structured output `[M]`. That verifies one harness and a toy schema, not the complete learner wire. With metered APIs excluded and local models tested unreliable, this is the **only LLM access path in the proposed architecture**, so real-schema and cross-harness validation is a mandatory P1 workstream, not an optional fallback.

Remaining steps, in order:

1. **Pin the version.** The learner invokes `npx -y claudexor@3.12.1` (or a newer tested pinned version) explicitly. Two traps exist on this machine: the npx cache holds 3.12.0 (the crashing version), and Metis's own default pin is 3.11.0. An unpinned or Metis-inherited pin could resurrect the crash. The version belongs in learner config and in every run's telemetry.
2. **Real-schema smoke suite.** Run the actual evidence-cascade JSON schema (not the toy smoke schema) through each harness: `claude` (proven above), `codex` (one smoke), `agy` (one smoke via `--profile agy-default`; per Metis's CR-002 investigation, agy is reachable only through a named profile, not as a native harness). Cursor stays deferred. Enumerate and triage the `success_with_warnings` detail seen in the claude smoke.
3. **Timed agreement replay:** 5-10 archived JDs through the real schema, measuring agreement with the golden set and latency per call. An agentic harness call is much heavier than a raw completion; the learner tolerates that because it is off the critical path, but real numbers are required before auto-accept thresholds are set and the budget dial is calibrated.
4. **Wire the learner, not the runtime:** shell out to claudexor readonly+schema from an offline worker; populate `subscription_minutes` as its own cost class (never `api_cents`); leave `call_llm()`'s provider chain untouched. Teacher first, judge never; runtime stays deterministic. The learner builds the claudexor command directly, bypassing Metis's methodology gate (write-scope checks, approval markers) entirely, exactly as the spike recommended; Metis's own project boundary rules require that separation in both directions.
5. **Scope:** claude/codex/agy only; cursor deferred; free→paid fallback remains forbidden; the manual cascade import stays as the final escape hatch.

### 17.9 Supersession list (exact)

| Original text | Superseded by |
|---|---|
| §7 Candidate C (local-LLM adjudication band) | Withdrawn; the band escalates to the offline subscription tutor |
| §9 recommendation (C as likely landing spot) | B as runtime + offline tutor (17.2); band width becomes a budget question, not a flip gate |
| §10 S4b "Local: conditionally justified" | Withdrawn per user testing; no LLM holds runtime decision authority |
| §11 MATCH_ABSTAIN resolution (local adjudication) | Tutor drafts offline; the human grades (17.5) |
| §14 P4 (conditional local band) | Offline learner worker (17.8) |
| §15 R2 | Resolved; replaced by R11 (label contamination) and R12 (caps/harness) |
| §16 P4 stories | Learner worker stories |
| Sp1 (local golden-set replay) | Formality: run once to record the unreliability benchmark for the CR |
| Spike doc step 3 (claudexor as a provider backend in `call_llm()`) | Learner worker first; runtime provider integration explicitly not pursued |
| Spike doc step 1 (root-cause the claudexor daemon crash) | Resolved 2026-09-16: claudexor 3.12.1 (published 2026-09-15) fixes the readonly/directory/schema crash; A/B smoke test succeeded with clean structured output. Remaining work is the version pin plus real-schema validation (17.8) |

### 17.10 Pressure test against external research (2026-09-16)

Before committing, the architecture's eight load-bearing claims were checked against the external literature (citations in Appendix B, items 18-40).

| # | Claim tested | Key external evidence | Verdict |
|---|---|---|---|
| 1 | A strong LLM can label the band well enough to teach the matcher | Gilardi et al. 2023 (PNAS): LLM annotators beat crowd workers on accuracy and intercoder agreement at near-zero marginal cost; Pangakis, Wolken, and Fasching 2023: automated annotation without validation against trusted gold is unsafe; Törnberg 2023: LLM text analysis needs structured validation pipelines | **Survives, conditionally.** Validation is load-bearing, not garnish: the 17.8 timed agreement replay and the blind-audit spot-check decide auto-accept, and their measured error rate sets the threshold |
| 2 | A small student converges toward the teacher on this narrow domain | Hsieh et al. 2023 (Distilling Step-by-Step): 350M-770M parameter students outperform few-shot LLMs on narrow tasks with less data; NAACL 2025 (Learning with Less): LLM pseudo-labels beat LLM prompting for small classifiers; Active Knowledge Distillation 2025: combines active learning and LLM distillation for budget-efficient text classification | **Survives, strongly.** The core specialization bet has direct precedent; the last paper is nearly this exact architecture |
| 3 | Double-asking plus grounding filters junk labels | Wang et al. 2022 (self-consistency improves accuracy); Farquhar et al. 2024 (Nature: semantic entropy over multiple samples detects confabulations); 2025 work quantifying that LLMs are inconsistent even on simple tasks (inconsistency is a usable escalation signal) | **Survives, amended.** Self-consistency is a signal, not a guarantee (models can be consistently wrong), so blind audits remain necessary; double-ask adaptively (near-threshold and HARD-proposing items only) rather than uniformly, per difficulty-adaptive sampling results |
| 4 | Consequence-ranked review reduces the labeling burden | Mussmann and Ermon 2018: uncertainty-sampling efficiency depends on calibration; but the critique line (Parting with Illusions 2019; JMLR 2024 regimes of no gain; 2025 LLM-era survey) finds active-learning gains often marginal or absent | **Amended.** No claim that ranked review saves budget. Keep it as a safety property (most-consequential items always human-graded) and keep the calibration work, since ranking quality depends on it |
| 5 | The cheap-first cascade with defer-to-human is sound | FrugalGPT 2023: LLM cascades cut cost dramatically while improving accuracy; Cascade-Aware Training 2024; Mozannar and Sontag 2020 (learning to defer); Hemmer et al. 2023 (deferral under limited expert predictions: exactly our scarce-human setting) | **Survives, strongly.** The ladder is a named, validated pattern, including under limited human predictions |
| 6 | Label precision beats coverage (wrong labels poison) | Frénay and Verleysen 2014 (label noise survey: many negative consequences); Natarajan et al. 2013 (noisy labels cost disproportionate data) | **Survives, strengthened.** Small corpora amplify noise cost, and ours is small (21-line golden set plus a growing adjudicated set), so the precision-first policy and its blind-audit threshold are required by theory, not preference |
| 7 | The requirement space is finite-ish; dedup economics hold | O*NET Hot Technologies (skills frequently included across postings: a canonical vocabulary exists); ESCO/O*NET crosswalk 2022; JobBERT 2021; occupational models from 42M postings 2023 (postings cluster into the standardized occupation structure) | **Partially survives.** Taxonomy-level canonicalization is well supported, which strengthens the alias-table approach. Phrase-level dedup economics stay `[E]`, verified by the 17.7 dashboard (open question 7) |
| 8 | Pre-answered drafts make review faster and better | Dell'Acqua et al. (758-consultant field experiment): outside the AI's capability frontier, AI-assigned consultants performed 19 points worse than the unassisted; Randazzo and Lakhani 2025 (persuasion bombing: professionals validating LLM output get argued into wrong approvals); Amplified Oversight 2025 (labels and explanations shown up front cause over-reliance; evidence-first presentation fosters appropriate trust) | **Contradicted in part.** Drafts speed review but invite rubber-stamping. Amendments: evidence-first display, a blind-audit fraction, blind-or-evidence-first treatment for tier-flipping and HARD items, and a dashboard metric for the blind-vs-seen delta |

One additional minor finding: LLM-as-judge biases (position, verbosity, self-preference; Zheng et al. 2023; and "No Free Labels" 2025, which also found judge grounding matters more than judge strength) recommend two things: randomize ordinal assignment of items inside tutor batch prompts (the exact-text echo binding already protects item identity; order randomization protects against position-driven category skew), and keep the evidence context (grounding) attached to every tutor call, since grounding quality affects tutor accuracy more than model choice.

**Net verdict: the architecture survives in shape; five amendments are folded in before commit.** (1) Validation is load-bearing and threshold-setting, not decorative. (2) Adaptive self-consistency, not uniform double-asking. (3) Consequence-ranked review is a safety property, not a budget optimizer. (4) Evidence-first review display plus blind audits, with the delta on the dashboard and the auto-accept threshold tied to it. (5) Randomized item order in tutor batch prompts. Claims 1, 2, 5, and 6 came out stronger than assumed (direct precedent exists for the whole design); claim 8 was the real finding of the pressure test and produced the amendments most worth building.

---

## 18. Runtime Harness Fallback and NLP Improvement (2026-09-17)

Jason clarified the operating goal: keep Stage 0 accurate through a meaningful batch without exhausting Groq/Gemini free-tier limits or consuming a large share of subscription capacity. Improve the NLP and deterministic matching so the harness handles progressively fewer uncertain cases. Stage 1, then Stage 2, then Stage 3 are later improvement efforts; this plan changes Stage 0 only. This section supersedes Section 17's zero-harness runtime, offline-tutor-only ladder and phase order.

### 18.1 Two existing calls need separate replacements

1. **Extraction:** the default TF-IDF/LogReg classifier buckets JD lines. Lines below its current 0.65 confidence cutoff go to Groq/Gemini (`build_stage0_fit_gate.py`, Section 2.4). Preserve high-confidence NLP decisions; route the uncertain batch through a subscription harness once its schema, latency, and error handling are validated. If it cannot answer, preserve the CR-112 unresolved/review path. Never silently drop a line or guess a bucket.
2. **Evidence judgment:** the current Groq/Gemini cascade classifies requirement gaps even when extraction succeeds (`stage0_evidence_cascade.py`, Section 2.4). Improve this path with rules, aliases, a case bank, and a calibrated matcher. Only its uncertain remainder goes to the subscription harness. A missing, invalid, or exhausted harness result becomes explicit review, never a terminal PASS or Skip inferred from missing evidence.

The two paths have different prompts, schemas, and quality gates. A successful toy-schema `claude` call in 17.8 proves neither path at production scale. Other Stage 0 hosted calls listed in 2.4 must be inventoried and removed or given a measured deterministic/review path before claiming zero Groq/Gemini calls for Stage 0.

### 18.2 Target batch behavior

```
JD -> existing hard gates -> NLP extraction
                     confident -> extracted requirements
                     uncertain -> cached/deduplicated harness batch -> validated buckets
                               -> unresolved review if unavailable/invalid
requirements -> rules + matcher
                     confident -> grounded levels and gates
                     uncertain -> cached/deduplicated harness batch -> validated judgments
                               -> explicit review if unavailable/invalid
aggregator -> tier or review pause; existing hard-gate safeguards still apply
```

The harness is a bounded runtime fallback, not a license to send every JD through an agent. Use a pinned, tested `claudexor` version; batch uncertain items; cache by JD, item, evidence, policy, and model versions; set a per-batch call/time budget; and record calls, elapsed `subscription_minutes`, failures, and review deferrals separately from `api_cents`. A cap or outage must yield a resumable review state so the batch does not silently consume an unbounded quota or make an unsupported decision. No metered API fallback is part of this design.

Only human-adjudicated corrections enter classifier or matcher training. Harness labels are proposals until the validation and audit policy is proven; do not feed unreviewed fallback answers into `training_data_feedback.csv` as the current extraction path does (W3). Track extraction abstentions, matcher abstentions, harness calls per 30 JDs, reviewed items, false skips, and errors over comparable batches. Falling harness use is an outcome to measure, not an assumption.

### 18.3 Implementation order and gates

1. **Specify and measure the baseline:** create the change request, label a representative JD and line-level gold set, record current extraction misses, cascade calls, false skips, review load, and 30-JD throughput. Preserve existing floors until replay supports a change.
2. **Prove the runtime wire:** pin `claudexor@3.12.1` or a later tested version. Smoke the actual extraction and evidence schemas through the intended profiles, inspect warnings, and replay 5-10 archived JDs for latency, agreement, and call count. Then run a timed 30-JD replay with a finite budget. One toy-schema success is not an acceptance gate.
3. **Replace the free-tier extraction fallback:** use the validated harness for low-confidence NLP lines, with the CR-112 review path on failure. Remove automatic training on unadjudicated fallback mappings. Verify no Groq/Gemini calls from this extraction path and no lost lines.
4. **Improve the evidence matcher in shadow:** build the rules/alias/case-bank matcher and calibrated abstention; compare with adjudicated gold and current decisions. Measure its raw uncertainty and false skips before giving it authority. Reuse confirmed corrections to improve both extraction and matching.
5. **Switch evidence judgment with a bounded fallback:** confident matcher outputs resolve locally; uncertain outputs go through the harness; unavailable or invalid outputs go to review. Gate the switch on gold-set error, review load, harness capacity, and a representative shadow run. Retain a rollback that uses explicit review rather than assuming the free-tier cascade can carry a batch.
6. **Tune and retire:** measure calls and errors across real batches, tighten thresholds only with evidence, then remove the remaining Groq/Gemini Stage 0 call sites. The offline tutor, blind-audit UI, and learning dashboard from Section 17 may be added after the runtime path works; they do not block the first reliable Stage 0 batch.

**Release test:** a representative 30-JD batch must finish or reach explicit, resumable review states within the chosen time and harness budget, with no unreviewed false skips on the adjudicated sample, no silent extraction loss, and no Groq/Gemini Stage 0 calls. Set numeric budget and error thresholds from the baseline and replay; current percentages in Sections 8 and 12 are estimates, not yet release evidence.

---

## Appendix A: Source Inventory (primary evidence)

Directly read: `scripts/build_stage0_fit_gate.py` (full 3,651 lines across the session), `scripts/evidence_scale.py` (scoring/prompt/retrieval sections).

Covered by the three sub-investigations with file:line citations (each report is the source of record for its files):

- **Gates/workers:** `stage0_db_gate.py`, `stage0_prefs_gate.py`, `domain_gate.py`, `industry_gate.py`, `seniority_gate.py`, `solo_pm_gate.py`, `anchor_gate.py`, `zero_shot_classifier.py`, `stage0_skip_ledger.py`, `stage0_placement.py`, `stage0_confirmations.py`, `stage0_checkpoint.py`, `stage0_evidence_cascade.py`, `stage0_qualification_risk_gate.py`, `evidence_scale.py`, `cost_eligibility.py`, `blocked_tools.py`, `utils.py`, `llm_stages.py`, `model_manager.py`, `local_embeddings.py`, `pipeline_env.py`, `stage0_extract.py`, `fit_rubric_examples.py`.
- **Orchestration:** `run_submission.py`, `workflow/runner.py`, `workflow/transitions.py`, `workflow/policy.py`, `workflow/receipts.py`, `workflow/invalidate.py`, `workflow/observability.py`, `import_csv_to_submissions.py`, `retrain_stage0.py`.
- **Server:** `services/stage0Policy.ts`, `services/exportPendingReview.ts`, `services/runSubmissionRunner.ts`, `services/scoutOrchestrator.ts`, `services/groqClient.ts`, `services/geminiClient.ts`, `services/llmSettings.ts`, `services/emailClassifier.ts`, `services/interviewDateExtractor.ts`, `services/ollamaLifecycle.ts`, `routes/llmUsage.ts`, `migrations/019_add_stage0_checkpoints.sql`.
- **Data/specs:** `fit_rubric_calibration.json`, `candidate_preferences.json`, `fit_rubric_spec.html`, `fit_rubric_golden_set.json`, `stage0_classifier.pkl`, `training_data_raw/clean/feedback.csv`, `skills_catalog.json`, `master_claims_tags_only.json`, `workExperience.md` (structure only), `jobagent.sqlite` (stage0_skips/runs/judgments/corrections), CR-093/CR-108/CR-112 spec docs, implementation docs under `docs/spec/08-implementation/`.

## Appendix B: Bibliography

1. Chow, C. K. (1970). "On Optimum Recognition Error and Reject Tradeoff." *IEEE Transactions on Information Theory* 16(1).
2. Geifman, Y., and El-Yaniv, R. (2017). "Selective Classification for Deep Neural Networks." *NeurIPS 2017*.
3. Hendrickx, K. et al. (2021). "Machine Learning with a Reject Option: A Survey." arXiv:2107.11277.
4. Platt, J. (1999). "Probabilistic Outputs for Support Vector Machines and Comparisons to Regularized Likelihood Methods." In *Advances in Large Margin Classifiers*. (Platt scaling)
5. Guo, C., Pleiss, G., Sun, F., and Weinberger, K. Q. (2017). "On Calibration of Modern Neural Networks." *ICML 2017*. (temperature scaling, ECE)
6. Brier, G. W. (1950). "Verification of Forecasts Expressed in Terms of Probability." *Monthly Weather Review* 78(1).
7. Robertson, S., and Zaragoza, H. (2009). "The Probabilistic Relevance Framework: BM25 and Beyond." *Foundations and Trends in Information Retrieval* 3(4).
8. Thakur, N. et al. (2021). "BeIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models." *NeurIPS 2021 Datasets and Benchmarks*.
9. Reimers, N., and Gurevych, I. (2019). "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks." *EMNLP 2019*.
10. Wang, S., and Manning, C. D. (2012). "Baselines and Bigrams: Simple, Good Sentiment and Topic Classification." *ACL 2012*.
11. Ratner, A. et al. (2016). "Data Programming: Creating Large Training Sets, Quickly." *NeurIPS 2016*. (weak supervision; Snorkel line)
12. European Commission. *ESCO: Classification of European Skills, Competences, Qualifications and Occupations* (framework v1.2+).
13. U.S. Department of Labor. *O*NET Occupational Database* (content model; job zones; skills taxonomy).
14. Nesta (2023). *Skills Extractor Library* (open-source ESCO-aligned skill extraction, spaCy-based).
15. Li, M. et al. (2024). "Skill-LLM: Task-Adaptive Fine-Tuning of Large Language Models for Skill Extraction." (LLM-based alternative)
16. Groq. *Rate Limits* documentation (free-tier figures, model-dependent, current as of research date).
17. Google. *Gemini API Rate Limits* documentation (free-tier figures, current as of research date).

Pressure-test additions (Section 17.10):

18. Gilardi, F., Alizadeh, M., and Kubli, M. (2023). "ChatGPT Outperforms Crowd-Workers for Text-Annotation Tasks." *PNAS* 120(30), e2305016120.
19. Pangakis, N., Wolken, S., and Fasching, N. (2023). "Automated Annotation with Generative AI Requires Validation." arXiv:2306.00176.
20. Törnberg, P. (2023). "How to Use Large Language Models for Text Analysis." arXiv:2307.13106.
21. Hsieh, C. et al. (2023). "Distilling Step-by-Step! Outperforming Larger Language Models with Less Training Data and Smaller Model Sizes." *Findings of ACL 2023*.
22. Wang, X. et al. (2022). "Self-Consistency Improves Chain of Thought Reasoning in Language Models." arXiv:2203.11171.
23. Farquhar, S. et al. (2024). "Detecting Hallucinations in Large Language Models Using Semantic Entropy." *Nature* 630.
24. Chen, L., Zaharia, M., and Zou, J. (2023). "FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance." arXiv:2305.05176.
25. Mozannar, H., and Sontag, D. (2020). "Consistent Estimators for Learning to Defer to an Expert." *ICML 2020*.
26. Hemmer, P. et al. (2023). "Learning to Defer with Limited Expert Predictions." *AAAI 2023*.
27. Natarajan, N. et al. (2013). "Learning with Noisy Labels." *NeurIPS 2013*.
28. Frénay, B., and Verleysen, M. (2014). "Classification in the Presence of Label Noise: A Survey." *IEEE Transactions on Neural Networks and Learning Systems* 25(5).
29. Dell'Acqua, F. et al. "Navigating the Jagged Technological Frontier: Field Experimental Evidence of the Effects of Artificial Intelligence on Knowledge Worker Productivity and Quality." SSRN 4573321 (2023); *Organization Science* (2026).
30. Randazzo, S., and Lakhani, K. (2025). "GenAI as a Power Persuader: How Professionals Get Persuasion Bombed When They Attempt to Validate LLMs." Harvard Business School working paper.
31. Zheng, L. et al. (2023). "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." *NeurIPS 2023 Datasets and Benchmarks*.
32. "Parting with Illusions about Deep Active Learning." (2019). arXiv:1912.05361.
33. "Regimes of No Gain in Multi-class Active Learning." (2024). *Journal of Machine Learning Research* 25.
34. "Have LLMs Made Active Learning Obsolete? Surveying the NLP Community." (2025). arXiv:2503.09701.
35. Mussmann, S., and Ermon, S. (2018). "On the Relationship between Data Efficiency and Error for Uncertainty Sampling." *ICML 2018*.
36. "LLM on a Budget: Active Knowledge Distillation for Efficient Classification of Large Text Corpora." (2025). arXiv:2511.11574.
37. "No Free Labels: Limitations of LLM-as-a-Judge Without Human Grounding." (2025). arXiv:2503.05061.
38. "Human-AI Complementarity: A Goal for Amplified Oversight." (2025). arXiv:2510.26518.
39. "Occupational Models from 42 Million Unstructured Job Postings." (2023). *Patterns* 4(7).
40. European Commission. (2022). *The Crosswalk between ESCO and O*NET: Technical Report.*

## Appendix C: Open Questions

1. **Local-model golden-set parity (Sp1)** was the biggest unknown in the original C path; resolved 2026-09-16 by user testing (unreliable for judgment) and superseded by the subscription tutor (Section 17). Sp1 survives as a recorded benchmark for the CR.
2. **Abstain-band width (Sp2)** still decides matcher coverage and raw review load; no estimate replaces the measurement.
3. **Verbalized confidence signal (Sp3):** if high/med/low correlates with correctness, a calibrated version could survive inside the tutor's validation stack; if not, it is dropped entirely.
4. **Floor recalibration (R5):** when confidence leaves RawFit, the 65/40 distribution shifts; the new operating bands must be re-locked by Jason against the gold set rather than inherited.
5. **Industry-semantic supplement fate**: currently fail-open hosted; either fold its function into the matcher's alias tables (preferred) or delete it after measuring its historical hit rate.
6. **Tutor latency and agreement (17.8 step 2):** an agentic claudexor call is a heavier unit than a raw completion; the timed replay sets the auto-accept bar and the budget dial's realistic throughput.
7. **Case-bank decay curve (17.4):** how fast does the band actually shrink? The first month of learner runs answers this; if marginal tutor cost per batch does not fall, the dedup/ontology assumption needs revision.
