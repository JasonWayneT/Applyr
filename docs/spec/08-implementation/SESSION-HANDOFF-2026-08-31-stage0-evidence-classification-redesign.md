# Session handoff — Stage 0 evidence-classification redesign: research + design needed, zero code written

**Date:** 2026-08-31
**Handing off from:** Claude Code (Sonnet 5), context-limited mid-session
**Handing off to:** Factory (or any fresh agent session capable of research + design)
**Status:** Problem is real and confirmed against live pipeline behavior. Two informal brainstorm rounds happened in chat (not in any file) with some external research already done. **Nothing has been scoped as a CR, nothing designed, zero code touched.** This is a request for a fresh, rigorous research + design pass — treat the prior brainstorm as a starting point to interrogate, not a plan to implement.

---

## Read first

- `AGENTS.md` (repo root) — canonical instruction set, read it in full before anything else.
- `docs/spec/05-change-requests/CR-093-*.md` (find via `ls docs/spec/05-change-requests/ | grep -i evidence` or similar) — the existing "evidence-scale engine" this work replaces. Its accuracy bar (a validated 21/21 golden-set result) is the bar to match or beat, not a historical footnote.
- `docs/spec/05-change-requests/CR-105-*.md` if present, else `scripts/build_stage0_fit_gate.py`'s own comments around `pipeline_env.stage0_section_mode()` — the sibling change (JD section extraction) that already moved from local-LLM-only to a deterministic-classifier-plus-cloud-fallback pattern. That migration is the closest in-repo precedent for what this work needs to do to a different, harder step.
- `scripts/evidence_scale.py` — the actual code in scope. `classify_requirement()` is the function being replaced/redesigned.
- Next available CR number as of this handoff: **CR-108**. Confirm it's still free before writing (another session may have claimed it).

---

## The problem, precisely

Applyr's Stage 0 job-fit triage has two LLM-touching steps inside `scripts/build_stage0_fit_gate.py`:

1. **JD section extraction/bucketing** (Step 3, CR-105, landed 2026-08-30) — NOT in scope here. Already migrated to a trained TF-IDF/LogisticRegression classifier with a batched Groq/Gemini cloud fallback for low-confidence lines only. Working as intended.

2. **Gap classification against the candidate's real work history** (Step 4, CR-093, `scripts/evidence_scale.py`) — **this is in scope.** For every required/preferred JD requirement line, `classify_requirement()` makes one LLM call (occasionally two, on a reasoning-mismatch retry), hardcoded to a local Ollama model (`qwen2.5:7b-instruct-q4_K_M`). It judges whether the candidate's real evidence (`workExperience.md`) actually supports that specific requirement, and returns a HARD/NONE gate plus a gap-source classification (tool / domain / degree / methodology). A HARD gate on a required item can cause the whole job to be auto-Skipped before a human ever sees it.

Measured live today: a 21-company Stage 0 batch made 12–48 local LLM calls per company in this one step alone (one per required+preferred line, sometimes more on retry). That's the actual bottleneck — not the CR-105 extraction step, which was already fixed.

### Why this needs a redesign, not just "move it to the cloud"

Two constraints from Jason, in his own words, that any design must satisfy simultaneously — accuracy first, cost second, both real:

> "we need to maximize accuracy as our north star and also try to reduce token cost as a secondary priority... I want other users to use this tool... but I want it to be free and depending on how many jobs they are looking at this can get expensive if everything goes to the cloud."

A naive "swap local for a cloud LLM call, same one-call-per-line pattern" fix would solve latency but make the cost problem worse at scale (linear in usage, across potentially many free users) — it does not satisfy the actual constraint. The design has to reduce how much of this work needs *any* model call (local or cloud) in the first place, while not regressing the accuracy CR-093 already validated. A wrong HARD verdict is a worse failure than a wrong NONE verdict — it silently discards a real opportunity before any human reviews it, whereas a wrong NONE is still caught later (a human reads the actual draft). Any confidence/escalation design should treat these asymmetrically.

### A second, separate failure mode found in the same conversation — must be a first-class requirement, not an afterthought

No retrieval method (deterministic keyword match, embeddings, NLI, or the current local LLM) can correctly judge a requirement the candidate's own data never captured. Example given: a JD asks for Trello; the candidate has real Trello experience but never wrote it into `workExperience.md`/`skills_catalog.json`. Every classification approach — including the current one — will incorrectly flag this as a real gap, because none of them are permitted to invent facts not in the user's own ground truth (this is deliberate, see `AGENTS.md`'s Hard Anti-Hallucination Rules and `evidence_scale.py`'s own constraint prompt). This is a ground-truth-completeness problem, not a classifier-quality problem, and it needs its own fix layered into the design: **when the system can't confirm a specific skill/tool one way or the other, it should ask the human instead of silently deciding "gap," and remember the answer permanently once given.**

That "ask instead of silently reject" mechanism has a further explicit requirement: it must be **durable and non-blocking**. If the system is unsure about one skill on one JD, it should write that open question somewhere permanent and move on immediately — to the rest of that JD's requirements, and to the rest of the batch — never pause or crash waiting on an answer that might come minutes or days later. This repo already has two working instances of exactly this pattern to use as precedent, not invent from scratch:

1. **`NEEDS_DISPOSITION`** (renamed from `WAITING_FOR_HUMAN` under CR-107 — read that rename's reasoning in `AGENTS.md`, it's directly relevant) — a Stage 2 WARN finding parks in `reviews/dispositions.json` without blocking other subphases or other submissions.
2. **CR-097's `data/authoring_defect_ledger.json`** — an occurrence gets flagged, surfaced for a human promote/decline call, and only then gets baked in permanently.

The new mechanism (something like a `pending_skill_confirmations` table, plausibly in `jobagent.sqlite` since that's the durable store this repo already trusts) should be recognizable as the third instance of this same shape, applied one level lower — at the individual skill/tool line-item level rather than the submission-subphase level — not a fourth, different pattern.

---

## What's already been informally explored (interrogate this, don't just implement it)

A chat brainstorm (not written to any file) proposed a layered/cascade approach and did some external research to support it:

1. **Free, deterministic layer** — named-tool/cert/domain hard-gap matching via the existing `scripts/blocked_tools.py` + `data/skills_catalog.json` machinery, reused rather than duplicated. Resolves unambiguous cases at zero marginal cost.
2. **Cheap local layer** — sentence-embedding cosine similarity against a cached `workExperience.md` index for a first-pass confidence signal, optionally an NLI cross-encoder for the mid-confidence band. Both would be *existing pretrained models used zero-shot* — research surfaced that pretrained NLI cross-encoders generalize reasonably well without task-specific fine-tuning for this class of problem, and that fine-tuning often does not reliably beat a good zero-shot baseline. **Do not assume "train a custom model" is required scope** — treat it as a possible future enhancement only if real testing shows the zero-shot layers are insufficient, not a starting assumption.
3. **Cloud LLM layer** (Groq/Gemini — same infra CR-105 already uses, PII redaction already wired into `scripts/utils.py`'s `call_llm`), reserved only for whatever remains genuinely ambiguous after layers 1–2, batched per company (one call covering every ambiguous line for that company, not one call per line — mirroring the pattern `_extract_sections_nlp`'s ambiguous-line fallback in `build_stage0_fit_gate.py` already uses successfully for the Step 3 extraction problem).
4. An asymmetric confidence bar — auto-resolving HARD without cloud/human confirmation should require materially higher confidence than auto-resolving NONE, given the asymmetric cost of being wrong described above.
5. The human-confirmation checkpoint (Trello case) sits logically between layers 1–2 and layer 3: a zero-anchor hard-gap tool/skill match should trigger a durable pending-question rather than an automatic Skip.

External sources cited during that informal research (verify currency, don't take at face value):
- Cascade/model-routing cost-quality tradeoffs: [arXiv 2606.27457](https://arxiv.org/html/2606.27457), [TianPan.co on LLM routing and cascades](https://tianpan.co/blog/2025-11-03-llm-routing-model-cascades)
- Pretrained NLI cross-encoders and zero-shot classification without fine-tuning: [HF NLI cross-encoders](https://huggingface.co/blog/dleemiller/nli-xenc-ways-to-use), [BTZSC benchmark, arXiv 2603.11991](https://arxiv.org/html/2603.11991)
- Hybrid retrieval architecture (embeddings + cross-encoder rerank + LLM as last stage): [Hybrid Search reference 2026](https://www.digitalapplied.com/blog/hybrid-search-bm25-vector-reranking-reference-2026)
- Groq free-tier rate limits by model (relevant if any per-line cloud fallback survives the redesign — `openai/gpt-oss-120b` is capped much lower than `llama-3.1-8b-instant`): [TokenMix, Groq free tier limits 2026](https://tokenmix.ai/blog/groq-free-tier-limits-2026)
- Durable execution / human-in-the-loop pause-resume patterns (for the pending-confirmation queue specifically): [Temporal human-in-the-loop](https://temporal.io/blog/human-in-the-loop-approvals), [SQLite-based durable workflows, Gunnar Morling](https://www.morling.dev/blog/building-durable-execution-engine-with-sqlite/), [DBOS](https://github.com/dbos-inc/dbos-transact-py)

None of this is authoritative. It's a starting point for a real research pass, not a design to rubber-stamp.

---

## What "done" looks like for this handoff

Not code. This handoff is asking for:

1. A bounded scope decision — what ships in a first version vs. explicitly deferred (e.g. the optional fine-tuned classifier, full multi-tenant account infrastructure, who pays for cloud calls across many users — that last one is a real open product question Jason has not answered, flag it, don't guess).
2. A concrete accuracy-validation plan — how the new approach gets fairly compared against CR-093's existing 21/21 golden-set result before it's allowed to replace the current local-LLM path in production. "It seems plausible" is not sufficient given a wrong HARD verdict silently costs a real opportunity.
3. A technical design for the durable, non-blocking human-confirmation queue as a first-class part of the design, not an add-on — including where it lives, how it's written to without blocking the rest of a batch, and how a person actually resolves a backlog of pending items.
4. A CR doc (`docs/spec/05-change-requests/CR-108-...md`, or renumber if 108 is taken by the time this is picked up) if the scope decision concludes this warrants one — my read is yes, given it's a multi-file, accuracy-critical pipeline change, but confirm rather than assume.
5. Explicit flags for anything genuinely undecided rather than resolved by best guess — Jason would rather answer a real open question than discover a guessed answer later.

---

## Repo state

Working tree on `main`, everything from today's separate submission batch is uncommitted and unrelated to this thread (see the same-day Antigravity handoff note if that context is needed — it's about 9 in-flight job application drafts, not this redesign). Nothing has been committed or written for this Stage 0 redesign thread. This file is the first artifact for it.
