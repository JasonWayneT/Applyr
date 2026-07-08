---
status: not_started
created: 2026-07-07
related: CR-058 (generation-defect-fixes, same session, immediate predecessor)
contains: CR-059 (Local LLM Tuning Loop)
---

# CR-059 — Local LLM Tuning Loop: Handoff & Round Tracker

**Handoff doc, one change request, self-paced experimental loop.** This is the resumable plan for
tuning how Applyr's drafting pipeline uses its local LLMs (via Ollama) so the small models it actually
runs on do their best possible work. A new session can pick up at the first unchecked round with no
other context needed beyond this file + the files it references. Read top-to-bottom before doing
anything.

**Do not re-litigate the plan below without new evidence.** It was reviewed and approved by Jason on
2026-07-07 before any round started. If a round's findings genuinely contradict an assumption here,
update this doc and say why — don't silently drift from it.

## Why this exists (do not re-derive without re-reading this)

CR-058 (same session, immediately prior — see
[CR-058-generation-defect-fixes.md](../05-change-requests/CR-058-generation-defect-fixes.md)) fixed 7
confirmed bugs in the deterministic layer of the drafting pipeline: fabricated metrics, JD-text
leakage, punctuation corruption from a buggy em-dash cleanup, JD-context misclassification, and an
audit-vs-generator grounding mismatch that silently discarded the adaptive summary far more often than
necessary. Those were regex/logic bugs — fixable without touching any LLM prompt.

This CR is different. It's about the **3 small local LLMs** the pipeline actually calls, and whether
the prompts/task-decomposition/model-routing handed to them are matched to what an 8B/3.8B/7B quantized
model can reliably do. Several of CR-058's bugs had exactly the failure shape you'd expect from an
under-scoped prompt asking a small model to do too much at once (fabricated numbers, reflexive generic
framing) — but that's a **hypothesis**, not yet confirmed to be an LLM-prompting problem rather than
pure deterministic-code problem. Round 1 below exists to test that hypothesis before any prompt changes
are made.

### Environment, confirmed 2026-07-07 (re-verify if this doc is stale)

- LLM settings (`data/llm_settings.json` equivalent, loaded via `utils.load_llm_settings()`):
  `primaryProvider: local`, `localModel: llama3.1:8b-instruct-q5_K_M`,
  `localFallbackModel: phi3.5:3.8b-mini-instruct-q8_0`, `localModelFit: qwen2.5:7b-instruct-q4_K_M`,
  Ollama at `http://localhost:11434`.
- All 3 configured models are actually installed (`curl localhost:11434/api/tags`) — no
  configured-vs-installed mismatch.
- **Model selection is VRAM-only, not task-aware.** `scripts/model_manager.py::select_model()` picks
  `localModel` if free VRAM ≥ 7.5GB, else `localFallbackModel` — zero logic tied to what the task
  actually is. A task prone to hallucination and a trivial extraction task get routed identically.
- **Larger local models exist but are wired into nothing**: `phi4:14b`, `qwen3:14b`,
  `qwen2.5-coder:14b-instruct-q4_K_M`, `ministral-3-14b` are installed and idle. Worth asking in Round 1
  whether any high-stakes, low-frequency call (e.g. final grounding/hallucination check) should route to
  one of these instead of accepting VRAM-driven fallback to the *smaller* model under memory pressure.
- **Two parallel bullet-generation code paths exist and it's not yet confirmed which one is live**:
  - `bullet_generation.py`'s `legacy_llm` mode (only runs if `DRAFT_MODE=legacy_llm`): one well-scoped
    LLM call per claim, JSON-schema-constrained output, few-shot examples, `temperature=0.0`, explicit
    "NEVER include the metrics or numbers in your JSON — we will append them automatically" instruction,
    logit-bias penalty on vibe words. This is a genuinely good example of small-model-appropriate
    prompting.
  - `claim_composer.py`'s `compose` mode — **the actual default** (`DRAFT_MODE` defaults to
    `"compose"`). Unknown as of this writing how much of this path is LLM-driven vs. deterministic
    string assembly (`local_draft_stages.py`'s own docstring claims "Tier 0–2 and 4–6 are deterministic,
    Tier 3 uses one LLM call per claim" — need to confirm which tier `compose` mode actually exercises
    and whether it shares `bullet_generation.py`'s well-scoped prompt or has its own).
  - **Round 1, Story 1 below is entirely about resolving this before touching any prompt.**
- Round 1 CR-058 regeneration logs showed the actual LLM call target as
  `phi3.5:3.8b-mini-instruct-q8_0` (the *fallback*, smaller model) — meaning the dev machine was under
  VRAM pressure during that session. Don't assume the primary `llama3.1:8b` model was exercised; check
  `logs/model_manager.log` for what actually ran in each test round.

## Test bed

`data/submissions/` is live and was rewritten under us multiple times during the CR-058 session by
whatever process/pipeline is running in the background — unsuitable for a controlled before/after
comparison. Use `data/archive/submissions/` instead, which is stable:

1. Copy 5 JDs' `Original_JD.txt` from `data/archive/submissions/` into a scratchpad location outside
   the repo's live folders, so nothing external can move or rewrite them mid-loop. Suggested picks
   (adjust if a folder no longer exists — `data/archive/submissions/` contents can shift):
   - **Avetta** — security/compliance-relevant control (does the security-framing gate fire correctly
     when it should? CR-058 left this as an open question — `has_security_jd_signal`'s regex didn't
     match Avetta's "compliance"/"risk" language).
   - **Donorbox** — previously misclassified as "consumer" JD context (CR-058 fixed the classifier;
     confirm it holds).
   - One JD with a dense, bulleted "Responsibilities" section, to stress-test JD-leak filtering (CR-058
     fixed one leak shape; confirm no new ones surface).
   - One generic B2B SaaS JD as a control (no known prior defects).
   - One JD from a distinctly different domain (e.g. Everbridge, Splash Financial) to check
     generalization, not just regression on known cases.
2. Regenerate all 5 into isolated scratch folders each round (`draft_compiler.run(..., company_folder=<scratch>)`
   with `SKIP_PDF_EXPORT=1`, `LOCAL_ONLY_MODE=1`, `RESEARCH_MODE=skip`, `JD_PROFILE_MODE=deterministic`,
   `DRAFT_MODE` set explicitly per what Round 1 Story 1 determines is worth testing — try both
   `compose` and `legacy_llm` if Story 1 finds they diverge meaningfully). Never touch
   `data/submissions/` or `data/archive/submissions/` during this loop.

## What "the test" measures, every round

For each of the 5 benchmark JDs after regeneration:

1. **Hard gate, must be 0 across all 5, every round:** lint blocks (`submission_linter.py`),
   `quality_checker.check_resume`/`check_and_repair_cover_letter` failures, 1-page violations, any of
   CR-058's 7 defect classes recurring (fabricated/ungrounded number, JD-leak fragment, stray-space
   punctuation, banned phrase, malformed/truncated sentence).
2. **Primary score:** the pipeline's own internal rubric critique, already logged by
   `draft_compiler.py` (`Rubric score: X/100 (summary Y / exp Z)`) — fast, consistent, already the
   project's chosen conversion-readiness proxy.
3. **Secondary score:** score each resume/cover letter by hand against
   `data/conversion_rubric.md` (R1–R8 resume, C1–C5 cover letter) — catches things the pipeline's
   self-critique might miss, especially C4 Authenticity (does it read as genuinely shaped by *this* JD,
   or as fluent-but-generic small-model paraphrase?).
4. **Attribution:** for anything that scores low or trips a defect, identify which model actually
   generated it (`logs/model_manager.log`) and which code path (`compose` vs `legacy_llm`, which
   function). Add lightweight prompt/response capture for the duration of this loop if nothing already
   logs it — remove or gate behind a debug flag before this CR closes out, don't leave it as permanent
   log noise.

**Rubric score is a proxy for conversion, not the real thing** — there's no interview-outcome data to
optimize against directly. Use it as the project's best available stand-in, but don't chase the number
past what the actual prose quality supports. If a change raises the rubric score but the letter reads
worse, that's a red flag, not a win — say so.

## Guardrails (carried over from CR-058, don't relearn these the hard way)

- **One or two changes per round, never a batch.** CR-058 briefly over-broadened a shared validity
  filter and had to walk it back after noticing it silently dropped legitimate content — a batch of
  changes would have hidden that regression behind other, unrelated improvements.
- Every code change gets unit-tested before the regeneration test.
- If a change breaks the deterministic guard layer (lint / `quality_checker` / `style_compliance_guard`),
  that's stop-and-fix immediately, not "note it and continue" — never trade a working guard for an LLM
  experiment.
- Prompt/model-routing changes stay scoped to the drafting pipeline (`scripts/*` files touched by
  `draft_compiler.py`'s call graph). Do not touch the job-scouting/fit-scoring side (`fit_policy.py`,
  gates, connectors, `server/`) unless a round's findings show it shares one of the same LLM call sites.
- Before any command that could discard uncommitted work (this repo has substantial pre-existing
  uncommitted changes from other in-flight work — confirmed via `git status` during the CR-058 session),
  never run `git stash`/`git reset --hard`/`git checkout --` without first confirming what's at risk.
  CR-058's session did this once by accident and had to `git stash pop` immediately to recover; no data
  was lost, but don't repeat it.

## Success criteria

- **Floor, every round, non-negotiable:** 0 hard-defect instances across all 5 benchmarks (see "What
  the test measures," item 1).
- **Target by Round 4:** average rubric score 85+ across the 5-JD batch for both resume and cover
  letter. 90 is the aspiration, not a forced target.
- **Qualitative, every round:** do letters read as genuinely shaped by *this* JD? Flag even if the
  rubric score looks fine — rubric and authenticity can diverge, especially with small models prone to
  fluent genericness.

## Round tracker

### Round 1 — Baseline + diagnosis (NOT STARTED)

- [ ] Story 1.1: Resolve which code path actually produces bullet content by default. Trace
      `DRAFT_MODE=compose` → `claim_composer.py` → confirm how much is LLM-driven vs. deterministic, and
      whether it reuses `bullet_generation.py`'s well-scoped prompt or has a separate, less-scoped one.
      This determines where the rest of Round 1's analysis should focus.
- [ ] Story 1.2: Regenerate all 5 benchmark JDs with zero code changes. Score each per the methodology
      above. Record `logs/model_manager.log` output for each run (which model actually served each
      call).
- [ ] Story 1.3: For every prompt actually sent to a local model in this batch, capture it. Research
      (WebSearch) each implicated model's documented reliability for that specific task shape —
      instruction-following under long/multi-instruction context, JSON-mode adherence, negative-
      constraint reliability at that parameter count and quantization level. Not generic "best LLM"
      research — task-specific, model-specific.
- [ ] Story 1.4: Produce a ranked list of concrete, small, attributable prompt/routing changes for
      Round 2, each with a stated hypothesis for why it should help and which specific observed failure
      it targets.
- [ ] Story 1.5: Present Round 1 findings to Jason before starting Round 2's code changes — this is a
      diagnostic round, not a fix round; don't skip the checkpoint.

### Round 2 — First changes (NOT STARTED)

- [ ] Implement the top 1–2 changes from Round 1, Story 1.4.
- [ ] Unit test.
- [ ] Regenerate the same 5 benchmarks, rescore, compare against Round 1 baseline.
- [ ] Record what moved, what didn't, and update the ranked list for Round 3.

### Round 3 — Second changes (NOT STARTED)

- [ ] Same pattern as Round 2, next highest-leverage change(s) from the updated list.

### Round 4 — Consolidation (NOT STARTED)

- [ ] Final round of changes if Round 3 was still net-positive.
- [ ] Retest.
- [ ] Write the wrap-up: Round 1 baseline → Round 4 final score/defect-rate trend across every
      benchmark JD, which specific changes helped/hurt/were neutral, and a recommendation for what to
      keep. This becomes the closing update to this doc (flip `status: not_started` → `status: complete`
      in the frontmatter) and, if the changes are substantial, its own short CR spec entry following the
      CR-057/CR-058 format.

## Starting prompt (use this to kick off Round 1 in a fresh session)

> Investigate how well Applyr's local LLM stack (`llama3.1:8b-instruct-q5_K_M`,
> `phi3.5:3.8b-mini-instruct-q8_0`, `qwen2.5:7b-instruct-q4_K_M` via Ollama, selected purely by VRAM
> availability in `model_manager.py` with no task-awareness) is actually being used across the
> resume/cover-letter drafting pipeline, and whether the prompts, task decomposition, and model routing
> are matched to what these specific small models can reliably do. Full context, test methodology, and
> round tracker: `docs/spec/08-implementation/CR-059-local-llm-tuning-loop.md`. Start at the first
> unchecked story.
