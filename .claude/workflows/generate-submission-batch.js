// CR-082 note (2026-08-09): scripts/run_submission.py + scripts/workflow/* is now the
// canonical, machine-enforced Stage 0-3 progression path (CR-076/077/079-084) -- receipts,
// hash-based STALE cascades, and a Truth/ATS/HM mechanical-findings-plus-human-disposition
// review model that no agent can self-report past. It is NOT a replacement for this file's
// Author/Review LLM split -- that split stays the legitimate mechanism for an opt-in SECOND,
// independent multi-agent read on top of the mechanical Stage 2 checks (per CR-075's own
// decision to patch, not deprecate, this file). Default to `python scripts/run_submission.py
// {slug}` for normal single-company progression and completion truth; reach for this batch
// script deliberately, when an extra independent-review pass is actually wanted, not out of
// habit for routine single-company drafting.
//
// CR-112 Story 2.2 (2026-09-11): force-added despite the `.claude/` gitignore, same pattern
// as generate-submission/SKILL.md. This runner still uses Claude Code Workflow/agent/phase
// primitives. A harness-agnostic rewrite is deferred. Every harness's default remains
// `python scripts/run_submission.py`.
//
// Written 2026-08-05, revised 2026-08-06 (Jason-supplied design question, addressed below) --
// still not run against a real JD yet. First real run should be treated as a dry run: watch it,
// read what it actually produces, before trusting it unattended.
//
// Why this exists: a single long session authoring 16 submissions back to back produced two
// real, confirmed failures a genuinely isolated pipeline would have caught structurally:
//   1. Self-anchoring across companies -- all 9 cover letters drafted in one sitting closed
//      with the literal phrase "I'd welcome the chance to talk through how" (confirmed via
//      LW-029, the new cross-batch linter check this same incident produced).
//   2. Self-graded review -- every rubric score and every "is this linter warning a false
//      positive" call was made by the same agent, in the same context, that wrote the draft
//      being judged. Research on self-review bias (cited to Jason directly) shows this
//      structurally under-catches problems even when the agent is trying to be honest.
//
// These are TWO DIFFERENT BUGS with two different fixes, and it matters to keep them separate:
//   Bug 1 (cross-company bleed) is caused by drafting multiple companies in one shared context.
//   Bug 2 (self-review collapse) is caused by one company's author and reviewer sharing a
//   context -- it happens even when only ONE company is being drafted.
// Jason's 2026-08-06 question was: if I'm not in a rush, why not just do one company at a time
// and let the context clear naturally between them, instead of batching? That fully solves Bug 1
// by construction (a fresh context per company has nothing to anchor on) -- but it does NOT
// solve Bug 2 on its own. Doing one company per fresh conversation still self-reviews within
// that one conversation unless Author and Review are still two separate agent() calls. So: this
// script now treats "one company at a time" as the normal, fully-supported case -- Author/Review
// isolation runs identically whether args has 1 entry or 9 -- and only spends the Cross-Batch
// Sweep phase (which exists purely for Bug 1) when there's actually more than one company in the
// same run to compare. Below 3 companies, the sweep has nothing meaningful to check against and
// is skipped -- see the `if (args.length >= 3)` guard in the Cross-Batch Sweep phase below.
//
// One caveat worth naming honestly: a fresh context prevents IN-CONTEXT memory bleed (the model
// literally copying a phrase it just wrote for a different company), but it doesn't rule out the
// model converging on similar phrasing independently each time from its own stylistic defaults,
// with no shared memory involved at all. That's a slower, subtler version of the same tell, and
// it's why SKILL.md's own standing rule (separate from this script) still calls for a periodic
// retrospective sweep across data/submissions/ before any real send-batch, or every 3+ new real
// submissions accumulated -- regardless of whether they were drafted together or one at a time.
//
// COST NOTE: roughly 3 agents per company (author, review, finalize), plus 1 more only when the
// Cross-Batch Sweep actually runs (3+ companies in one invocation). A single company costs ~3
// agents total -- not the "3N+1 for a big batch" concern this file used to lead with.
//
// USAGE:
//   Workflow({
//     name: 'generate-submission-batch',
//     args: [
//       { slug: 'asurion', company: 'Asurion', title: 'Sr Product Manager', reachOut: false },
//       // a single-entry array is the normal case, not a lesser-supported one -- run one
//       // company at a time whenever there's no reason to rush; add more entries only when you
//       // actually want several companies moving through Author/Review concurrently.
//     ],
//   })
//
// WHAT THIS DOES NOT DO: if Independent Review or the Cross-Batch Sweep surface a real
// problem, this script does not loop back and re-author automatically -- it reports findings
// and stops. Deciding whether a finding needs a fix, and re-running this workflow (or editing
// by hand) after fixing it, stays a human-in-the-loop decision. A "Fix" phase that
// auto-applies review findings was deliberately left out of this first version -- it would
// need its own correctness guarantees (does the fix agent actually address the finding? does
// it introduce a new one?) that are worth designing deliberately, not bolting on by default.

export const meta = {
  name: 'generate-submission-batch',
  description: 'OPT-IN second review only (CR-112): never the default for routine drafting. Default path is scripts/run_submission.py. Author/Review isolation for when Jason explicitly wants a multi-agent pass. Review ground truth is packet excerpts + claim_constraints + drafts + JD + rubric, not workExperience.md. Cross-batch sweep only when 3+ companies run together. Cap 3 companies unless allowLargeBatch.',
  whenToUse: 'Never the default for routine single-company drafting or completion truth. Use only when Jason explicitly asks for an independent multi-agent Author/Review pass on top of scripts/run_submission.py. Do not spawn this workflow because a JD arrived. Prefer one company at a time unless concurrency is intentional; Cross-Batch Sweep skips below 3 companies.',
  phases: [
    { title: 'Author', detail: 'One agent per company drafts Resume.md/CoverLetter.md from ground truth + stage0_fit_gate.json (or packet/digest). Prefer starting from run_submission WAITING_FOR_LLM / authoring_prompt.md when available.' },
    { title: 'Independent Review', detail: 'A separate, isolated agent per company scores the draft against the JD -- never sees the authoring reasoning' },
    { title: 'Cross-Batch Sweep', detail: 'Only runs with 3+ companies in this invocation -- LW-029 + no-ai-slop Detect across the whole batch. Skipped for 1-2, which have nothing to cross-check.' },
    { title: 'Finalize', detail: 'Per company: python scripts/run_submission.py {slug} --resume (Truth/ATS/HM/Mech/Policy), then --finalize. Do not treat standalone verify_submission.py / finalize_submission_job.py as completion without orchestrator receipts.' },
  ],
}

const AUTHOR_SCHEMA = {
  type: 'object',
  properties: {
    company: { type: 'string' },
    resume_written: { type: 'boolean' },
    cover_letter_written: { type: 'boolean' },
    gaps_bridged: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
  required: ['company', 'resume_written', 'cover_letter_written'],
}

// 2026-08-06: rubric scores and required-item fidelity used to be bare numbers/prose arrays --
// exactly the shape that let 8 companies get byte-identical, unread scores in a real incident.
// Both are now structured so a plausible-but-ungrounded answer can't come back at all: every
// rubric criterion needs its own evidence citation, and every required item from
// stage0_fit_gate.json needs an explicit engaged true/false, not just a prose complaint when
// something's missing. See scripts/contracts.py for the same idea applied to file handoffs.
// 2026-08-08 Cluster C item 13: align with contracts.py._check_rubric_score_shape /
// real draft_manifest.json (amplify et al). Flat resume_rubric_score fields were a
// doc/workflow drift; the enforced shape is nested under rubric_score.
const RUBRIC_CRITERION_ENTRY_SCHEMA = {
  type: 'object',
  properties: {
    score: { type: 'number' },
    max: { type: 'number' },
    evidence: { type: 'string' },
  },
  required: ['score', 'evidence'],
}

const RUBRIC_SIDE_SCHEMA = {
  type: 'object',
  properties: {
    total: { type: 'number' },
    breakdown: {
      type: 'object',
      additionalProperties: RUBRIC_CRITERION_ENTRY_SCHEMA,
      description: 'Keyed by criterion id (R1_ats_integrity, C1_opening_hook, ...)',
    },
  },
  required: ['total', 'breakdown'],
}

const REQUIRED_ITEM_SCHEMA = {
  type: 'object',
  properties: {
    item: { type: 'string' },
    engaged: { type: 'boolean' },
    evidence_or_bridge: { type: 'string' },
  },
  required: ['item', 'engaged', 'evidence_or_bridge'],
}

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    company: { type: 'string' },
    rubric_score: {
      type: 'object',
      properties: {
        resume: RUBRIC_SIDE_SCHEMA,
        cover_letter: RUBRIC_SIDE_SCHEMA,
      },
      required: ['resume', 'cover_letter'],
    },
    required_items: { type: 'array', items: REQUIRED_ITEM_SCHEMA },
    authenticity_concerns: { type: 'array', items: { type: 'string' } },
    verdict: { type: 'string', enum: ['CONVERT_READY', 'NEEDS_ONE_PASS', 'NEEDS_REWORK'] },
  },
  required: [
    'company', 'rubric_score',
    'required_items', 'verdict',
  ],
}

function authorPrompt(item) {
  return `You are authoring a resume and cover letter for a real job application, following Applyr's generate-submission skill Stage 1 exactly (the CR-074 packet path). Read .claude/skills/generate-submission/SKILL.md's Stage 1 section first. If data/submissions/${item.slug}/authoring_packet.json is absent, run python scripts/build_authoring_packet.py data/submissions/${item.slug} to build it. Then run python scripts/author_from_packet.py data/submissions/${item.slug} to assemble the authoring prompt. Author closed-world from data/submissions/${item.slug}/authoring_packet.json + data/authoring_rule_digest.md only -- do not read data/agent_context_pack.md, the full CLAUDE.md, data/workExperience.md, or data/master_claims.json.

Company: ${item.company}
Title: ${item.title}
Folder: data/submissions/${item.slug}/ (already has Original_JD.txt and stage0_fit_gate.json from Stage 0 -- read stage0_fit_gate.json, do not re-derive the fit reasoning).

Write data/submissions/${item.slug}/Resume.md and CoverLetter.md directly. Follow CLAUDE.md's Required Document Structure, forbidden-language list, and Attribution Discipline table exactly. Resolve every flagged gap in stage0_fit_gate.json as an honest transferable-skill bridge argued as fit -- never a gap confession (hard-blocked as LR-016).

Run python scripts/author_from_packet.py data/submissions/${item.slug} --verify-only as the Stage 1 exit gate -- fix anything it flags before moving on. Then compile PDFs with scripts/compile_single.py and run scripts/verify_submission.py, scripts/check_ground_truth_coverage.py, scripts/jd_term_extractor.py against this one folder -- fix everything they flag before you finish. Do NOT write draft_manifest.json's rubric_score -- that is the independent reviewer's job in the next stage, not yours, and writing it yourself would defeat the point of a separate review. Return the required JSON.`
}

function reviewPrompt(item) {
  return `You are the INDEPENDENT Stage 2 reviewer for one job application, per Applyr's generate-submission skill. You have NOT seen how this was drafted and must not try to reconstruct that reasoning. Read only:
- data/submissions/${item.slug}/Original_JD.txt
- data/submissions/${item.slug}/stage0_fit_gate.json
- data/submissions/${item.slug}/Resume.md
- data/submissions/${item.slug}/CoverLetter.md
- data/submissions/${item.slug}/authoring_packet.json (excerpts + claim_constraints for attribution; do not treat catalog text as authoring input)
- data/conversion_rubric.md (the scoring rubric)

Do not read data/workExperience.md, data/agent_context_pack.md, data/master_claims.json, this workflow script, any other company's files, or anything under docs/spec/08-implementation. Attribution fidelity uses packet claim_constraints (OWNED/CONTRIBUTED/INFLUENCED), not a full WE reload. Score the resume (R1-R8) and cover letter (C1-C5) by hand against conversion_rubric.md -- write rubric_score.resume and rubric_score.cover_letter each with total plus a breakdown object keyed by criterion id (e.g. R1_ats_integrity, C1_opening_hook), each entry {score, max, evidence} with a real evidence citation (a specific sentence or bullet, not a vibe). A criterion with no genuine citation is not a scored criterion.

Before scoring required-item fidelity, independently re-run these two (do not assume Stage 1 already handled it correctly -- that's the point of this being a separate pass):
    python scripts/check_ground_truth_coverage.py data/submissions/${item.slug}
    python scripts/jd_term_extractor.py data/submissions/${item.slug}
Then pull stage0_fit_gate.json's full required list and fill in required_items with one entry per item: engaged=true only if it's actually addressed via real evidence or an honest bridge, with the specific evidence_or_bridge text quoted. engaged=false for anything silently dropped -- do not summarize into prose instead of filling in every item.

Flag authenticity/AI-slop concerns (robotic bullet rhythm, synonym cycling, gap-confession language, generic AI phrases) -- run the no-ai-slop Detect pass per .claude/skills/submission-no-ai-slop/SKILL.md if available, otherwise apply the same judgment directly.

Write rubric_score (shape: {resume: {total, breakdown}, cover_letter: {total, breakdown}} — matches scripts/contracts.py) and required_items into data/submissions/${item.slug}/draft_manifest.json (create the file if it doesn't exist -- company="${item.company}", title="${item.title}", verification_passed=true only if every required_items entry is engaged=true and both rubric_score.*.total values clear their conversion_rubric.md threshold). Do not write flat resume_rubric_score / cover_letter_rubric_score fields — those are status-report flattenings from check_submission_status.py, not the draft_manifest schema. Return the required JSON.`
}

// 2026-08-06: defensive fix for a real, reproduced bug -- `args` reached this script as a JSON
// STRING on two consecutive live invocations, both passing a genuine JSON array through the
// Workflow tool call (confirmed via `pipeline() expects an array` failing at 0 agents/16ms both
// times, before any agent logic ran). Root cause not confirmed (looks like a harness-level
// serialization quirk on this parameter), but the fix is safe either way: parse if it arrived
// as a string, use as-is if it's already an array. `jobs` replaces every direct `args` use below.
const jobs = typeof args === 'string' ? JSON.parse(args) : args

// 2026-08-07 (CR-075 Story 1.2): this file's own header says the first real run should be
// treated as a dry run, and the incident that produced CR-075 was a 12-company unattended
// first invocation -- three agents per company on the old context path burned a five-hour
// token allocation in about five minutes with zero completions. Refuse an unattended large
// batch by default; require an explicit opt-in on the payload to run more than 3 at once.
const MAX_COMPANIES_PER_RUN = 3
if (jobs.length > MAX_COMPANIES_PER_RUN && !jobs.some((j) => j.allowLargeBatch === true)) {
  throw new Error(
    `Refusing to run ${jobs.length} companies unattended (max ${MAX_COMPANIES_PER_RUN} without opt-in). ` +
    `This file's own header says the first real run should be treated as a dry run -- the incident ` +
    `that produced CR-075 was a 12-company unattended first invocation that burned a five-hour token ` +
    `allocation in about five minutes with zero completions. Set allowLargeBatch: true on at least one ` +
    `job entry to opt in explicitly.`
  )
}

phase('Author')
const authored = await pipeline(
  jobs,
  (item) => agent(authorPrompt(item), { label: `author:${item.company}`, phase: 'Author', schema: AUTHOR_SCHEMA }),
)

phase('Independent Review')
const reviewed = await pipeline(
  jobs,
  (item, _origItem, idx) => agent(reviewPrompt(item), {
    label: `review:${item.company}`,
    phase: 'Independent Review',
    schema: REVIEW_SCHEMA,
  }),
)

phase('Cross-Batch Sweep')
// 2026-08-06: only meaningful with something to cross-check. For 1-2 companies there's no
// cross-company habit to detect (see the header comment's Bug 1 vs Bug 2 explanation) -- running
// it anyway would just be spending an agent to report "nothing to compare." SKILL.md's own
// standing rule still covers the slower, memory-independent version of this risk (periodic
// sweeps before a real send-batch / every 3+ accumulated submissions) -- that's a separate,
// occasional maintenance action, not something this per-run phase needs to substitute for.
let sweepReport = null
if (jobs.length >= 3) {
  const slugPaths = jobs.map((a) => `data/submissions/${a.slug}`).join(' ')
  sweepReport = await agent(
    `Run this exact command from the repo root and report its full output verbatim, including every LW-029 finding: python scripts/submission_linter.py ${slugPaths}

Then run the no-ai-slop Detect pass (per .claude/skills/submission-no-ai-slop/SKILL.md) across every company's Resume.md + CoverLetter.md in this batch, looking specifically for a stylistic HABIT recurring across different companies -- not proof-point reuse, which is fine per CLAUDE.md's own policy (no hiring manager reads two of Jason's letters side by side), only a repeated rhetorical device, opening-hook shape, or closing-line construction. Report every finding with the specific companies and phrases involved. This is a reporting task -- do not edit any files.`,
    { label: 'cross-batch-sweep', phase: 'Cross-Batch Sweep' },
  )
  log(`Cross-batch sweep complete -- review before finalize.`)
} else {
  log(`Skipping Cross-Batch Sweep -- only ${jobs.length} compan${jobs.length === 1 ? 'y' : 'ies'} in this run, nothing to cross-check for cross-company repetition.`)
}

phase('Finalize')
// 2026-08-09: completion truth is scripts/run_submission.py (CR-076-084), not
// check_submission_status.py alone. Mech still runs verify_submission underneath --resume;
// --finalize wraps finalize_submission_job and mints stage3. Opt-in batch review still ends here.
const finalized = await pipeline(
  jobs,
  (item) => agent(
    `Run these exact commands from the repo root for data/submissions/${item.slug}, in order, and report the exact output of each. Stop and report the failure -- do not proceed to the next command or invent a passing result -- if any of them exits non-zero:
1. python scripts/run_submission.py data/submissions/${item.slug} --resume
2. python scripts/run_submission.py data/submissions/${item.slug} --status
3. Only if Stage 2 is COMPLETE (or COMPLETE_WITH_OVERRIDE) and content is send-ready: python scripts/run_submission.py data/submissions/${item.slug} --finalize
Do not treat standalone verify_submission.py / check_submission_status.py / finalize_submission_job.py as done without orchestrator workflow_state + stage_receipts. If --resume stops at NEEDS_DISPOSITION, settle reviews/dispositions.json and re-run --resume before finalize.`,
    { label: `finalize:${item.company}`, phase: 'Finalize' },
  ),
)

return { authored, reviewed, sweepReport, finalized }
