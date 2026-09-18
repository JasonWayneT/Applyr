---
status: backlog_provisional_id
date: 2026-09-18
implementation_plan: ../08-implementation/CR-117-stage1-evidence-first-authoring-epics.md
research: ../08-implementation/RESEARCH-2026-09-18-stage1-authoring-shape.md
related: CR-074, CR-094, CR-097, CR-102, CR-112, FEAT-004
---

# CR-117: Evidence-first Stage 1 authoring

**ID collision:** This draft used CR-117 before the 2026-09-18 CSV-drop handoff identified CR-117 as the years-range change. Its `FR-332` to `FR-336` and `AC-430` to `AC-434` labels are also provisional; at least `FR-332` and `AC-430/431` belong to years-range in the live registry. Treat this Stage 1 document as backlog, not an approved CR. Assign free IDs during product review; do not use these numbers for implementation tracking.

## Decision sought

Build the evidence-first Stage 1 path behind a switch, then test its quality before changing the default. The path selects and checks evidence in a compact plan, writes the resume and cover letter together, performs a dedicated editorial read, validates, and repairs defects. The current single-pass author is the comparison control. This CR authorizes the candidate implementation; a production switch requires the release gate below.

## Problem and evidence

Stage 1 currently asks one author to allocate packet evidence, compose two documents, and record unit-level provenance in one response. The Camunda root-cause report found zero identified fabrication or employer misattribution but weak evidence utilization, repeated phrasing, a JD-adjacent opening, and incomplete provenance. That is one case, not a measured first-draft failure rate. The existing CR-112 fixture runner records offline cost and input data; it does not author or grade drafts. The linked research memo distinguishes external findings from Applyr-specific inference.

## Product outcome

Produce stronger initial application pairs that Jason would send or fix in one pass. Truthful attribution, the one-page resume, a distinct cover-letter argument, and Jason's voice are the quality bar. Additional subscription turns are acceptable when they improve the draft. Measure first-draft and post-repair outcomes separately so extra repair does not masquerade as stronger initial authoring. Time and subscription usage are operational signals, not the quality target.

## Current authoring size

Eight local prompt/document pairs have a mean `authoring_prompt_meta.json` input estimate of 12,346 tokens (range 11,972-12,762) and a mean current resume-plus-letter size of 1,474 tokens by bytes/4 (range 1,310-1,649). Seven provenance files average another 1,373 tokens by the same approximation (range 1,100-1,619). A typical visible input plus artifacts is therefore roughly 15.2k estimated tokens before planning, editorial review, repair turns, conversation carryover, or hidden model reasoning. The document files may have been revised after the initial draft. These are not provider-reported token counts or a subscription charge. The existing subscription has no per-draft API invoice, but authoring consumes context and allowance; total session consumption is not measured yet.

## Agy model and transport choice

`agy models` on 2026-09-18 lists Gemini 3.8, 3.7, and 3.6 Flash at low/medium/high thinking levels, Gemini 3.1 Pro, and Claude models. Jason chose `gemini-3.8-flash-medium` for the Stage 1 authoring pilot after deciding not to spend the limited Claude-model allowance on routine drafts. Test it on frozen pilot cases before changing any production default. High thinking or Pro requires evidence of better Applyr writing, not a generic benchmark or an automatic fallback. This is a model choice to test, not an Applyr writing benchmark result.

A synthetic headless Agy smoke showed that Opus rejects `--effort high`. The same smoke without `--effort` returned an empty answer after a headless `read_file` permission denial, with reported usage of 22,828 input tokens and 3 output tokens. That usage includes Agy's harness context and cannot be treated as Stage 1 prompt cost or added directly to the bytes/4 estimate. Later isolated no-tools calls succeeded, but a real Stage 1 output-contract probe and transport tests remain necessary; manual Agy authoring remains usable until they pass. `agy models` does not report remaining allowance or context capacity, so availability must come from a verified signal or a real limit response, not guessed from the model list.

Follow-up isolated probes with an explicit no-tools prompt did produce clean Opus answers. A fresh sandboxed turn reported 22,838 input and 32 output tokens. A second turn in the same `--input-format stream-json` process raised cumulative input to 23,423 (a 585-token delta), cumulative output to 64, and `cache_read_tokens` to 22,362. A separate fresh call without `--sandbox` reported 21,964 input tokens, only 874 fewer than the sandboxed cold turn. These are synthetic calls, not Stage 1 quality or context-capacity tests. Agy's documented stream mode reuses one conversation process and reports cumulative usage, so per-turn deltas must be computed from successive results. Cache-read tokens still occupy context and must not be treated as zero usage.

The first overhead design is one fresh, sandboxed Agy session **per application**, kept open for plan, paired draft, and editorial/repair turns. Pass the packet once and reuse checked artifacts within that session. Never reuse a conversation for another JD. Explicitly forbid file/tools in the closed-world author prompt; a tool request or permission denial produces no valid draft. The current prompt averages 50,511 bytes; its pretty packet averages 35,015 bytes and a compact JSON rendering averages 29,145 bytes across nine local folders. Compacting the packet could save about 1.5k input tokens by bytes/4, but must be tested for readability and first-draft quality. Keep digest and evidence intact unless a controlled comparison proves a safe reduction.

The overhead budget has three separate lines: cold session/harness input, packet and instruction input, and subsequent turn deltas (including cache reads and output). Record them separately from context occupancy and allowance outcomes. Reusing one session avoids another cold start but does not make its prior context free or expand the context window. An Agy `SUCCESS` status is insufficient: require a nonempty, parseable response matching the requested artifact contract, with no denied actions or tool requests. If a session must restart, persist the checked plan and drafts first, then resend only the bounded artifacts needed by the next qualified model. Do not trim evidence or skip editorial review solely to meet a token target.

## Requirements and acceptance criteria

| Requirement | Acceptance criterion |
| --- | --- |
| `FR-332`: Comparable Stage 1 evaluation | `AC-430`: Frozen, privacy-safe JD/packet cases and a blind scorecard compare the current path with evidence-first authoring under the same packet, model capability tier, shared rules, and repair limit. First-draft and final outcomes, truth errors, review effort, elapsed time, and subscription usage are recorded separately. The runner does not write production submissions, receipts, or SQLite. |
| `FR-333`: Evidence-plan contract | `AC-431`: A small plan names source-backed resume slots and a distinct cover-letter argument, with exact packet claim IDs, source-span references, JD need, metric/attribution constraints, and explicit omissions. A deterministic gate rejects unknown IDs, source text absent from the cited excerpt, employer mismatch, prohibited/disabled evidence, unaddressed required items without an honest bridge, and over-budget role slots. Semantic support that cannot be proved mechanically is flagged for qualitative review. The plan never widens the packet. |
| `FR-334`: Paired authoring and provenance | `AC-432`: A subscription author composes both documents from the same checked plan and packet, then performs a separate editorial read of the pair. The output contract covers factual Core Competencies and other factual resume units as well as factual cover-letter sentences; no cited unit can rely only on an unrelated valid ID. Existing Stage 1 checks and Stage 2 qualitative review still run. |
| `FR-335`: Targeted repair | `AC-433`: Stage 1 returns ranked, actionable defects and permits at most the existing bounded fix rounds. A repair uses only the same packet and checked plan, preserves unaffected valid content, and re-verifies both documents and provenance. Unresolved objective blocks remain blocks. |
| `FR-336`: Subscription cascade and controlled promotion | `AC-434`: Agy pilots `gemini-3.8-flash-medium` first and uses one sandboxed stream session per application when context permits. Each result's cumulative usage is converted to per-turn deltas; packet and harness context are not resent through a new process between plan, draft, and review. On a real context or allowance limit, it pauses or resumes from checked artifacts on a separately quality-qualified subscription model; it never silently moves to paid API or purchased credits. A failed headless permission check is a transport failure, not a draft. The production default changes only after blind paired quality review, no truth/attribution regression, and independent QA of `run_submission.py`. The old path remains available for rollback. |

## Scope and boundaries

- Stage 0 supplies the packet. Its active CR-114/115/116 changes may alter packet quality; freeze the packet version for each comparison case and re-run the evaluation if the input contract changes materially.
- Reuse the current digest, claim constraints, packet closed world, verification checks, first-draft history, and Stage 2 review wherever possible. Do not make the plan a second biography or copy full Work Experience into the author context.
- Keep candidate documents, plans, and human judgments in a gitignored evaluation location. Tracked fixtures must be fictional or sanitized and contain no candidate PII. Use subscription authoring by default; do not make paid API a fallback. A separately requested paid API experiment would follow existing cost authorization.
- No new per-JD agent swarm, autonomous web research, unreviewed packet widening, direct edits to real applications, or replacement of the hiring-manager read.

## Evaluation protocol

1. Freeze at least the five existing fictional JD fixtures plus a small sanitized holdout spanning narrow fit, broad fit, and honest soft-gap cases. Build packets once per case and record packet/digest hashes. A fixture without a valid packet is a Stage 0 fixture problem, not a Stage 1 loss.
2. Before candidate runs, publish the scorecard and record Agy's pinned model, tested fallback order, CLI/manual transport, and how each route reports context and allowance limits. Use the same model for matched control and candidate cases when available; randomize and blind document-pair labels. Keep tuning cases separate from the frozen holdout.
3. Run the current control and the evidence-first candidate under the same shared contract. The untouched current-path baseline is a diagnostic; after any common provenance change, rerun the control for the matched comparison. Record the initial pair before editorial or mechanical repair, then record the pair after the same allowed repair process. Reviewers mark send / one-pass / rework and pairwise preference with concrete reasons; mechanical checks record truth, provenance, coverage, repetition, specificity, and page count. Resolve reviewer disagreements explicitly.
4. Review whether the candidate improves human judgment without truth regression. Examine subscription turns, context growth, pauses, and wall time to make the workflow operable, but do not select a weaker draft to save time or tokens. If quality is mixed, refine the candidate and extend the holdout before promotion.

## Release gate

The comparison is a decision artifact, not automatic promotion. Product review discusses the quality evidence with Jason; security reviews PII and artifact boundaries; independent QA runs isolated tests and an end-to-end practice submission through `run_submission.py`; the engineering manager checks scope, docs, subscription cascade, and rollback. Only then may the default change. Record the result and verification in the implementation tracker.

## Open product decision

After candidate drafts are reviewed, discuss how much additional subscription usage the quality gain warrants and whether the editorial pass consistently improves the pair. This discussion informs tuning and promotion; it does not block building the candidate path.
