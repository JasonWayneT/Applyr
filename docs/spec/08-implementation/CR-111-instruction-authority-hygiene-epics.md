---
status: implemented
created: 2026-09-07
related: CR-098, CR-107
contains: CR-111 (Instruction-authority hygiene)
---

# CR-111 — Epics and stories

Source: `docs/instruction-authority-audit-2026-09-07.md`. Spec:
`docs/spec/05-change-requests/CR-111-instruction-authority-hygiene.md`.

Standing constraint for every story (NFR-013): no submission behavior, linter rule,
threshold, or pipeline code changes. Edits are doc/agent-file fixes plus the new drift
guard. When a story touches an instruction file, change only the lines the story names.

## Epic 1 — Contradiction and staleness fixes (FR-290, FR-291, FR-294)

- [x] 1.1 `.claude/agents/engineering-manager.md`: replace the "CLAUDE.md and AGENTS.md
      edited byte-identically" instruction with a pointer to the import-stub rule
      (`AC-379`)
- [x] 1.2 Cover-letter band reconciliation per Jason's CR-111 open-question decision:
      update the stale statement(s) so exactly one authoritative target band exists;
      comment in `submission_linter.py` LW-001 noting target band vs WARN tolerance
      (`AC-383`)
- [x] 1.3 Root `AGENTS.md` File Map: fix the `candidate_preferences.json` "min fit score
      72" row (floors live in `fit_rubric_calibration.json`, CR-093) and the "no automated
      page-count gate" claim (`verify_submission.py::_pdf_page_count` exists) (`AC-384`)
- [x] 1.4 `docs/AGENTS.md`: replace the absolute `file:///.../JobAgent/...` SDD_PROCESS
      link with a repo-relative link; add one header line subordinating this file to root
      `AGENTS.md` (`AC-391`)
- [x] 1.5 Registry hygiene pass: mark `AC-076` superseded by `FR-195`; annotate
      CR-079/080/081 `WAITING_FOR_HUMAN` rows as renamed by CR-107; flip CR-076–084 rows
      from `in_progress` to `implemented`; resolve duplicate IDs AC-095 (×2), AC-119 (×3),
      AC-175/AC-176 (×2), and NFR-004 (×2) (`AC-381`, `AC-385`)
- [x] 1.6 `.claude/agents/tech-lead.md`: replace the hardcoded "currently CR-053/054/055
      and CR-064" list with a pointer to `docs/spec/08-implementation/` (`AC-380`)
- [x] 1.7 `.claude/agents/product-manager.md`: verify whether the referenced `superpowers`
      skills are installed; if not, remove or reword the references (`AC-380`)
- [x] 1.8 `docs/spec/00-project-constitution.md`: refresh the LLM provider list
      (Claude/Local/Groq are first-class now) and the "batch pipeline" framing to
      post-CR-074 reality (`AC-382`)
- [x] 1.9 `docs/ACTIVE_WORKFLOW.md`: add the two-rubric disambiguation note (pipeline
      rubric `<60` advisory vs conversion rubric 70/65 floors are different instruments)
      (`AC-382`)
- [x] 1.10 Sweep: confirm all 12 audit "Contradictions And Drift" items are resolved or
      carry an in-place deferred-with-reason annotation (`AC-382`)

### Epic 1 verification record

- Confirmed `docs/SDD_PROCESS.md` exists at the repo-relative path used by
  `docs/AGENTS.md`.
- Confirmed no `.claude/agents/` file retains the old byte-identical edit instruction,
  hardcoded active-CR list, or uninstalled `superpowers` reference.
- Confirmed the requirements registry has no duplicate IDs in its row-ID column, no
  `in_progress` rows for CR-076–084, and no current-state row using
  `WAITING_FOR_HUMAN`. Historical CR text remains unchanged.
- Confirmed the cover-letter decision is explicit: 250–400 authoring target,
  220–450 linter warning tolerance, and 300–400 renderer constants deferred because
  changing them would alter submission behavior.
- Skill twin cleanup and the drift guard remain intentionally deferred to Epics 2 and 3.
  No implementation was started for either epic.

## Epic 2 — Skill canonicalization: one canonical, stubs elsewhere (FR-292)

- [x] 2.1 Add canonical-declaration headers (modeled on the no-ai-slop header) to
      `.codex/skills/generate-submission/SKILL.md`,
      `.codex/skills/conversion-ready-pass/SKILL.md`, and
      `.codex/skills/networking-outreach/SKILL.md` (`AC-386`)
- [x] 2.2 Replace the three `.claude/skills/` twins with pointer stubs of the same form as
      `.claude/skills/submission-no-ai-slop/SKILL.md` (`AC-386`, `AC-388`)
- [x] 2.3 Replace `.codex/skills/submission-no-ai-slop/SKILL.md` (full clone of the
      `.agents` canonical) with a pointer stub to `.agents/skills/submission-no-ai-slop/`
      (`AC-386`, `AC-388`)
- [x] 2.4 Harness verification: open a Claude Code session and a Codex session and confirm
      each of the four skills still loads and is followable through its stub; update root
      `AGENTS.md`'s File Map skill rows if any path wording changed (`AC-387`)

### Epic 2 verification record

- Confirmed the three `.codex/skills/` canonical files declare themselves as canonical.
- Confirmed the three `.claude/skills/` files and the `.codex` no-ai-slop file are
  pointer-only stubs, each 10 lines or fewer and naming its canonical target.
- Claude Code reported PASS in harness-bridge session 009 R52 after live skill discovery
  confirmed all four `.claude` stubs and their canonical targets.
- Codex reported PASS in session 009 R53 after its live available-skill inventory
  confirmed all four `.codex` skill surfaces and canonical declarations.

### Coordinator note - 2026-09-07

Jason has asked the agents to coordinate through shared files instead of chat-only
handoffs. Current owner split:

- Claude owns Story 2.4 / `AC-387`: verify from a live Claude Code session that
  `generate-submission`, `conversion-ready-pass`, `networking-outreach`, and
  `submission-no-ai-slop` load and remain followable through the current pointer
  stubs. Report PASS/FAIL/BLOCKED here or in `pipeline-log.md`, with exact file/path
  evidence for any failure.
- Codex has already verified the Codex-side file model by direct read: the three
  `.codex/skills/` canonical files declare themselves canonical; the three
  `.claude/skills/` files are pointer stubs; `.codex/skills/submission-no-ai-slop`
  points to the `.agents` canonical. Codex also observed
  `python scripts/check_instruction_drift.py` clean,
  `python scripts/test_check_instruction_drift.py` passing 7 tests, `npm test`
  passing, and `npm run build` passing.
- Factory completed the final CR-111 diff review after Claude R52 and Codex R53 both
  reported PASS. No stub/path issue was found.

Known readiness note outside CR-111 closure: `data/agent_context_pack.md` is stale
relative to current sources. Regenerate it before any agent relies on it for process
or optional ladder-2 review. Do not treat archived submission verification failures as
CR-111 failures; current `data/submissions/` is empty, and archived folders predate the
modern Stage 2 readiness expectations.

## Epic 3 — Instruction drift guard (FR-293)

- [x] 3.1 `scripts/check_instruction_drift.py`: fail when (a) a declared pointer-stub file
      exceeds ~20 lines, (b) a declared canonical target is missing, (c) a `file:///`
      absolute link appears in `AGENTS.md` / `CLAUDE.md` / `docs/**`, (d) a banned phrase
      reappears — seeded with: byte-identical `AGENTS.md`/`CLAUDE.md` edit instructions,
      `WAITING_FOR_HUMAN` outside historical CR docs, hardcoded "currently CR-"
      enumerations in `.claude/agents/` (`AC-389`)
- [x] 3.2 Tests + deliberately-broken fixtures proving each guard branch fails as designed
      (`AC-389`)
- [x] 3.3 Wire the guard into the same verification path as
      `check_context_pack_freshness.py` so doc-touching work runs it; passes clean on
      `main` after Epics 1–2 land (`AC-390`)

### Epic 3 verification record

- `python scripts/test_check_instruction_drift.py`: 7 tests passed.
- `python scripts/check_instruction_drift.py`: clean.
- `python scripts/check_context_pack_freshness.py`: drift portion clean; the existing
  context pack remains stale because several source files predate regeneration. The pack
  was not regenerated because that would add unrelated generated/private-data churn.

## Done criteria (CR level)

- [x] All `AC-379`–`AC-391` boxes in the spec check off
- [x] `verify_submission.py` passes on one real submission folder; `npm test` shows no
      regression (NFR-013 guard). Verified 2026-09-08 on the production
      `data/submissions/form_health_rerun` folder: `run_submission.py --resume`
      passed Stage 1 and mechanical verification end to end
      (`verification_receipt.json` records `mechanically_verified: true`, both
      PDFs one page), and the full `npm test` suite passed 47/47 with no
      regression.
- [x] `git diff` reviewed to confirm no substantive rule change — only contradiction
      fixes, staleness fixes, false-claim deletions, pointer conversions, and the new
      guard
- [x] CHANGELOG `[DRAFT]` entry appended per the GitHub & Release Notes Rule
- [x] Traceability matrix updated for `FR-290`–`FR-294` / `NFR-013` / `AC-379`–`AC-391`
