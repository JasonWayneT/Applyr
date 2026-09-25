# Instruction-Authority Audit — 2026-09-07

Audit of Applyr's agent instruction system. No files were edited. Method: full read of root
`AGENTS.md` / `CLAUDE.md`, `docs/AGENTS.md`, `docs/ACTIVE_WORKFLOW.md`,
`docs/spec/00-project-constitution.md`, `docs/spec/02-requirements-registry.md`, all
`SKILL.md` copies under `.claude/` / `.codex/` / `.agents/`, all `.claude/agents/*.md`,
plus a mechanical-enforcement map of `scripts/submission_linter.py`, `quality_checker.py`,
`verify_submission.py`, `claim_provenance.py`, `check_ground_truth_coverage.py`,
`resume_conversion_eval.py`, `tone_guard.py`. External grounding: ETH Zurich / LogicStar
"Evaluating AGENTS.md" (arXiv 2602.11988, Feb 2026), HumanLayer "Writing a good CLAUDE.md"
(Nov 2025), and 2026 AGENTS.md practice surveys.

## Executive Summary

Applyr's instruction system is not failing because its rules are wrong. It is failing
structurally: the always-on layer has become an append-only incident log, and the
repository now has **nine files that claim some form of canonical authority**, several of
which contradict each other in specific, findable places.

Three facts frame everything else:

1. **Most high-risk authoring rules are already mechanical.** The anti-hallucination core
   (forbidden titles, people management, revenue ownership, unverified tools, codenames,
   em-dashes, gap confessions, workforce-reduction framing, the 1-page rule) is enforced by
   `submission_linter.py` / `quality_checker.py` / `verify_submission.py` as HARD_BLOCKs.
   The prose in `AGENTS.md` is largely a *second copy* of rules that code already enforces.
   This is what makes cleanup safe: shrinking prose does not shrink protection.
2. **The prose layer is past the size where models follow it reliably.** Published research
   (ETH Zurich, Feb 2026) found context files make agents follow instructions *more
   uniformly worse* as instruction count grows, and add 20%+ inference cost; instruction-
   following quality decays across the whole file, not just at the bottom. Root `AGENTS.md`
   is 220 dense lines containing dozens of dated incident narratives. Every stale or
   narrative line actively taxes compliance with the rules that matter.
3. **The contradictions are real, not hypothetical.** This audit found a live rule conflict
   in `.claude/agents/engineering-manager.md` (orders byte-identical `CLAUDE.md`/`AGENTS.md`
   edits, directly forbidden since 2026-08-14), a numeric conflict on cover-letter length
   (250–400 vs 300–400), an unsuperseded registry row that mandates stripping a section the
   root file mandates including, four byte-identical twin skill files with no declared
   canonical, and at least three stale factual claims in root `AGENTS.md` itself.

The smallest safe first step is a hygiene CR that **fixes contradictions, converts skill
twins to pointer stubs, and adds a drift guard — without deleting or rewriting a single
rule**. Content restructuring of root `AGENTS.md` is a second CR, done only after the
authority skeleton is unambiguous.

## Current Authority Map

| File | Authority claim | Actual role | Health |
|---|---|---|---|
| `AGENTS.md` (root, 220 lines) | "the canonical always-on instruction set for Applyr" | Always-on authoring rules + engineering pointers + incident log | Dense; carries stale rows and heavy incident scar tissue |
| `CLAUDE.md` (6 lines) | Import stub (`@AGENTS.md`) + Claude-only notes | Healthy pattern; the model other files should copy | Good |
| `docs/AGENTS.md` (124 lines) | "All AI agents must follow this file and SDD_PROCESS.md before making changes" | SDD engineering process + standards | **Competing root claim; stale `file:///` link to old `JobAgent` folder; never defers to root AGENTS.md** |
| `docs/ACTIVE_WORKFLOW.md` | "Active Workflow (Source of Truth)" | Operator + pipeline-developer workflow | Mostly fresh; two fixable drifts (see below) |
| `docs/spec/00-project-constitution.md` | "preserve project intent across agents" | Goals, non-goals, tech defaults | Right home, right content; two stale lines (provider list, "batch pipeline") |
| `docs/spec/02-requirements-registry.md` (787 lines) | "the canonical list of project requirements" | Append-only requirement ledger | Status columns stale (CR-076–084 `in_progress` though landed; WAITING_FOR_HUMAN rows not renamed per CR-107; AC-076 not superseded; duplicate IDs) |
| `docs/spec/08-implementation/` | "current source of truth for status" (per root AGENTS.md) | Per-CR handoff docs | Correct pattern; root AGENTS.md already defers here |
| `scripts/submission_linter.py` | "single source of truth" for forbidden language | 33 HARD_BLOCK + ~30 WARN + 3 INFO rules | Healthy; the architecture's best asset |
| `data/workExperience.md` | "Ground truth" | Evidence corpus | Healthy (untouched by this audit) |
| `.agents/skills/submission-no-ai-slop/SKILL.md` | Declared canonical for that skill | Canonical + `.claude` pointer | **The proven target pattern** |
| 4 other skills × 2 harness dirs | No declared canonical | Byte-identical twins | Drift-in-progress (frontmatter already diverging) |
| `.claude/agents/*.md` (7 files) | Per-role gates in SDD pipeline | Engineering pipeline roles | One rule conflict (EM), one stale CR list (tech-lead), one dangling external ref (PM) |

## Contradictions And Drift

Ranked by blast radius:

1. **`.claude/agents/engineering-manager.md` orders "CLAUDE.md and AGENTS.md edited
   byte-identically if either changed."** This is the exact twin-drift failure the repo
   burned itself on and explicitly banned in both files. It is inside the final quality
   gate, so it fires at the worst possible moment. Highest-priority fix.
2. **Cover-letter word band conflict:** root `AGENTS.md` says 250–400;
   `docs/ACTIVE_WORKFLOW.md` (CR-043 row / FR-234) says 300–400. One is stale.
3. **Registry `AC-076` mandates stripping `## Core Competencies`; root `AGENTS.md` and the
   same registry's `FR-195` mandate injecting it.** AC-076 was never marked superseded. An
   agent tracing requirements can "verify" either behavior.
4. **Root `AGENTS.md` File Map is stale on fit threshold:** says `candidate_preferences.json`
   holds "min fit score 72"; `ACTIVE_WORKFLOW.md` says that floor "no longer exists —
   do not resurrect" (CR-093 moved floors to `fit_rubric_calibration.json`, 40/65).
5. **Root `AGENTS.md` claims "There is no automated page-count gate in this pipeline yet."**
   False since `verify_submission.py::_pdf_page_count`. Stale prose that invites redundant
   manual behavior it elsewhere demands.
6. **Two competing "canonical agent instruction" claims:** root `AGENTS.md` vs
   `docs/AGENTS.md` ("All AI agents must follow this file"). Neither declares precedence.
7. **`docs/AGENTS.md` links `SDD_PROCESS.md` via an absolute `file:///c:/.../JobAgent/...`
   path** — the pre-rename folder name. Evidence the file is unmaintained.
8. **Registry status rot:** CR-079/080/081 AC rows still say findings go to
   `WAITING_FOR_HUMAN` (renamed by CR-107 precisely because the name caused a real
   behavioral bug); CR-076–084 block still `in_progress`; duplicate IDs (AC-095 ×2,
   AC-119 ×3, NFR-004 ×2) violate the repo's own ID-uniqueness rule.
9. **`.claude/agents/tech-lead.md` hardcodes "currently CR-053/054/055 and CR-064"** —
   missing CR-094/CR-070; the same staleness pattern root `AGENTS.md` already corrected
   in itself.
10. **`.claude/agents/product-manager.md` references `superpowers` skills** that exist only
    as an unwired copy under `scratch/superpowers/` — a dangling external dependency.
11. **Semantic drift, minor:** registry FR-199/AC-217 states the "B2B SaaS" subtitle ban as
    absolute; LR-031 (and root prose) are JD-conditional. And two different rubrics use
    similar numbers (`<60` pipeline advisory vs 70/65 conversion floors) with no
    reconciliation note — a confusion hazard, found in both `ACTIVE_WORKFLOW.md` and the
    registry.
12. **Skill twin drift has started:** every `.claude` twin differs from its `.codex` twin by
    exactly the frontmatter lines `version:` / `author:`. Today it's metadata; the repo's
    own AGENTS.md/CLAUDE.md history shows where this ends. Worst case:
    `.codex/skills/submission-no-ai-slop/SKILL.md` is a byte-identical clone of the
    `.agents` canonical *whose own text names a different file as canonical*.

## Keep

Durable product rules. These are correct, load-bearing, and should survive any cleanup
(possibly relocated, never weakened):

- **The ground-truth contract:** `workExperience.md` is source of truth; claims are an
  index, not a biography; WE wins disagreements (CR-094).
- **Hard anti-hallucination rules:** no people management, no titles above Senior IC PM,
  no AI/ML ownership, no revenue ownership, no unverified tools, verified-partner list,
  VOC codename table, Exclusion Zones. (Note: nearly all already HARD_BLOCKed in code —
  the prose is the safety briefing, the code is the guardrail.)
- **`run_submission.py` as sole sequencing authority** and writer of workflow receipts;
  workers are debug-only.
- **NEEDS_DISPOSITION = retry-inline semantics** (CR-107). Keep the rule; the *story* of
  the rename is what should move out.
- **"Done is strongest available evidence, not cleared threshold"** and the 70/65 floors.
- **Trigger-phrase bindings** ("conversion ready" → three-pass workflow; JDs →
  `generate-submission`). Genuinely universally applicable; this is what always-on files
  are for.
- **`submission_linter.py` as single source of truth for forbidden language**, with prose
  reduced to the always-hard-blocked core. Already the declared pattern; extend it.
- **The `.agents`-canonical + pointer-stub skill pattern** demonstrated by
  `submission-no-ai-slop`.
- **`docs/spec/00-project-constitution.md`** as the durable identity doc (after a two-line
  refresh), and `08-implementation/` as status authority.
- **What must never become mechanical:** rubric scoring and compelling-ness judgment.
  `verify_submission.py`'s own docstring already says this. Keep it prose.

## Move Out Of Always-On Instructions

Old incident history. The *rule* stays; the *story of how we learned it* moves to the CR
doc or a new `docs/postmortems/` file. Root `AGENTS.md` and `generate-submission/SKILL.md`
are the densest offenders:

- Every dated anecdote: "found 2026-07-21 … 5 of 11 real letters," "6 of 9 real submissions
  in the 2026-07-20/21 batch," "the Bazaarvoice 73/100 dry run," "confirmed real 2026-08-05
  on a 9-company batch," the Humana compound-requirement finding, the 2026-08-30 batch that
  left 2 of 15 stuck, the pop_up_talent 69-vs-92 anecdote.
- Self-correcting meta-commentary: "This section previously said '3+ sentences,' which is
  wrong," "reversed 2026-08-04; a prior version hardcoded…," "renamed from WAITING_FOR_HUMAN
  under CR-107 — that name read as an instruction to stop," "promoted from WARN on
  2026-08-11." The current rule is all an agent needs; the archaeology belongs in CHANGELOG
  / CR docs.
- Session/corpus references that mean nothing to a fresh agent: "harness-bridge
  shared-sessions/session-006/009," "R25-R32, Phase 2."
- The "Active Engineering Work" status enumeration in root `AGENTS.md` — shrink to the one
  line that already exists ("status lives in `docs/spec/08-implementation/`").
- `generate-submission/SKILL.md`'s incident narrative — its own self-repair note admits a
  prior version "reached 19 accreted rules." The bulk of the move-out work lives here.

A test for what moves: if a sentence's truth depends on a date, a batch, or a specific past
failure, it is history. If it is true on its own, it is a rule.

## Delete Or Rewrite

- **Delete** the byte-identical-edit instruction in `engineering-manager.md` (replaced by a
  pointer to the import-stub rule).
- **Rewrite (slim), don't delete, `docs/AGENTS.md`:** it is the only home of the
  requirement-ID namespace, coding/testing standards, and CHANGELOG template. Fix the
  `file:///` link, delete the competing-root header, add one line subordinating it to root
  `AGENTS.md`. Keep it as the engineering-standards module.
- **Fix stale rows in root `AGENTS.md` File Map:** the "min fit score 72" line and the
  "no automated page-count gate" claim.
- **Reconcile the cover-letter band** (pick one; the linter's LW-001 band is 220–450, so
  three numbers currently exist — decide which is authoritative and align).
- **Mark registry staleness:** supersede AC-076, rename WAITING_FOR_HUMAN rows per CR-107,
  flip CR-076–084 statuses, dedupe the duplicated IDs. One mechanical pass, no rewriting.
- **Refresh two lines in `00-project-constitution.md`** (LLM provider list; "batch
  pipeline" framing).
- **Verify or remove** the `superpowers` references in `product-manager.md`.

## Convert To Mechanical Checks

Verification beats instruction (ETH Zurich's central finding; also HumanLayer's "never send
an LLM to do a linter's job"). Candidates, in priority order:

1. **Instruction-drift guard (new, highest value):** a script that fails CI/pre-push if
   (a) any pointer-stub skill file regrows past ~20 lines, (b) any two canonical-declared
   files disagree, (c) any `file:///` absolute link appears in docs, (d) the
   `engineering-manager.md`-class banned phrases reappear. This converts the findings of
   *this audit* into a permanent check so the system self-maintains.
2. **Codename coverage gap:** LR-011 blocks 6 codenames but the VOC table lists 11. CPRE,
   Visible, PIC, Datagroups, C3 are unblocked (Closed-lost is WARN-only via LW-036).
   Either add them to LR-011 or document the intentional omission in the linter. Right now
   the prose table implies protection the code doesn't provide.
3. **`Original_JD.txt` first-line `URL:` convention** — currently enforced only by prose and
   a silent downstream `null` fallback. Cheap structural check in `verify_submission.py`.
4. **Domain-qualifier subtitle check** — LR-031 covers "B2B SaaS" only; the "never adopt the
   JD's domain qualifier" rule (e.g. "Product Manager, Insurance") is prose-only and
   mechanizable as a WARN (subtitle shares a JD domain token absent from WE).
5. **Registry status consistency** — a lint that flags `in_progress` rows for CRs whose
   08-implementation tracker says complete. Lower priority; registry hygiene may be
   adequately served by a one-time pass.

Explicitly **not** to mechanize: rubric scoring, hook insight vs paraphrase, compellingness,
cross-letter distinctiveness judgment. Prose + skill is the right tool there.

## Recommended Future Architecture

Four layers, each with exactly one job. Aligned with the AGENTS.md convention (single
universal root file, pointers not copies, under ~150 lines) and progressive disclosure:

```
Layer 0  AGENTS.md (root, ≤ ~120 lines)          ALWAYS LOADED
         Identity, ground-truth pointers, orchestrator entry point,
         precedence declaration, "rules live in X, history lives in Y."
         No dated sentences. No status enumerations. No second copies of
         mechanical rules — one line naming the linter as authority.

Layer 1  Task modules, loaded on trigger          PROGRESSIVE DISCLOSURE
         - generate-submission SKILL (authoring rules, incident-free)
         - conversion-ready-pass SKILL
         - networking-outreach SKILL
         - submission-no-ai-slop SKILL (.agents canonical — keep)
         - docs/AGENTS.md → slimmed engineering-standards module,
           explicitly subordinate to root
         One canonical copy each; every other harness dir holds a
         ~10-line pointer stub (the proven no-ai-slop pattern).

Layer 2  Mechanical authority                     CODE, NOT PROSE
         submission_linter.py / quality_checker.py / verify_submission.py
         remain the single source of truth for everything regex-able,
         plus the new drift guard. Prose elsewhere points here.

Layer 3  History                                  COLD STORAGE
         Incident narratives, rename rationales, reversal stories →
         the owning CR doc or docs/postmortems/. Registry stays
         append-only ledger, status columns kept honest.
```

Precedence, declared once in root `AGENTS.md`: mechanical checks > root `AGENTS.md` >
triggered skill/module > CR docs. When a check and prose disagree, the check is a bug or
the prose is stale — file a CR, never carry both.

Do **not** attempt the Layer-0 shrink first. It is only safe once authority is unambiguous
and the drift guard exists.

## Proposed First CR: Instruction-Authority Hygiene

**Scope:** Fix every identified contradiction, convert skill twins to pointer stubs, and add
the mechanical drift guard. **No rule is deleted, reworded, or relocated. No always-on file
is restructured.** That is CR+1, proposed separately after this lands.

**Acceptance criteria:**

1. Zero known cross-file rule contradictions remain (the 12 items in "Contradictions And
   Drift" each resolved or explicitly deferred with a note).
2. Every skill has exactly one declared canonical copy; every other copy is a pointer stub
   of the same form as `.claude/skills/submission-no-ai-slop/SKILL.md`. Canonical homes:
   keep `.agents` for `submission-no-ai-slop` (already declared); use `.codex` as canonical
   for `generate-submission`, `conversion-ready-pass`, `networking-outreach` (only tree
   with the full inventory) with `.claude` stubs; convert the `.codex` no-ai-slop clone to
   a stub. Verify each harness still loads its skill through the stub before merging.
3. `python scripts/check_instruction_drift.py` (new) runs clean, and fails when fed a
   regrown stub or a reintroduced banned phrase.
4. `git diff` shows no substantive rule change: every edit is a contradiction fix, a
   staleness fix, a deletion of a false claim, or a pointer conversion.
5. Full Required Verification suite (`verify_submission.py` on one real submission folder)
   still passes, proving the mechanical layer is untouched.

**Story 1 — Contradiction fixes (no behavior change).**
- `engineering-manager.md`: replace the byte-identical-edit instruction with a pointer to
  the import-stub rule.
- Reconcile cover-letter band across root `AGENTS.md` / `ACTIVE_WORKFLOW.md` / LW-001 to
  one authoritative number.
- Root `AGENTS.md` File Map: fix "min fit score 72" and "no automated page-count gate."
- `docs/AGENTS.md`: fix the `file:///` link; add the one-line subordination to root.
- Registry: supersede AC-076, apply the CR-107 rename to stale rows, flip CR-076–084
  statuses, dedupe duplicate IDs.
- `tech-lead.md`: replace the hardcoded CR list with "read `docs/spec/08-implementation/`."
- `product-manager.md`: verify or remove `superpowers` references.
- `00-project-constitution.md`: refresh provider list and pipeline framing.

**Story 2 — Pointer-ize the four skill twins.**
- Add a canonical-declaration header to each chosen canonical file (mirroring the
  no-ai-slop header).
- Replace the three `.claude` twins and the `.codex` no-ai-slop clone with pointer stubs.
- Manually verify with each harness (Claude Code session, Codex session) that the skill
  still resolves and executes through the stub.

**Story 3 — Drift guard.**
- `scripts/check_instruction_drift.py`: stub-size cap on declared pointer files;
  canonical-file existence; ban `file:///` links in `docs/` and root instruction files;
  banned-phrase list seeded with this audit's findings (byte-identical-edit instruction,
  WAITING_FOR_HUMAN outside history docs, hardcoded "currently CR-" enumerations in agent
  files).
- Wire into the existing verification chain so it runs where `check_context_pack_freshness.py`
  runs today.

**Explicitly out of scope (next CR):** shrinking root `AGENTS.md` to Layer-0 form, moving
incident narratives to `docs/postmortems/`, slimming `generate-submission/SKILL.md`, the
codename-coverage and URL-first-line linter additions. Each is safe only after the authority
skeleton above exists.
