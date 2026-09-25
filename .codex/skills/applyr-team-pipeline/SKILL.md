---
name: applyr-team-pipeline
description: Run Applyr's gated product, engineering, security, QA, and final-verification workflow for a material change or change request.
metadata:
  short-description: Applyr's role-based delivery pipeline
---

# Applyr Team Pipeline

Use for a material Applyr change, a change request, or when Jason asks for the team pipeline. This replaces Claude-specific agent definitions with the same responsibilities and independent verification gates.

## Shared constraints

Read the relevant project specifications, `AGENTS.md`, and `CLAUDE.md` before work. For resume or cover-letter changes, treat the ground-truth, verification, exclusion-zone, and forbidden-language rules as binding. Use `pipeline-log.md` as a durable record when the pipeline is used.

## Order and responsibilities

1. **Product manager:** define the problem, smallest acceptance criteria, explicit out-of-scope work, open questions, and CR-worthiness. Do not make implementation or design decisions. For a CR, create or update the relevant record and requirement IDs.
2. **Product designer:** only when user-facing behavior or UI changes. Specify flow, states, existing components to reuse, edge cases, and important copy. Return unresolved scope questions to product management.
3. **Tech lead:** read the actual code, confirm an existing pattern or justify a new one, identify architectural risks, and create a resumable epics-and-stories tracker for CR-worthy work. If a product decision is missing, route backward instead of deciding it during implementation.
4. **Senior engineer:** implement one unchecked story at a time. Read surrounding code, write and observe a failing test when a relevant harness exists, implement the smallest change, and report what was and was not verified. Never self-mark a story complete.
5. **Security reviewer:** required for PII, database, submission data, secrets, file-path, SQL, connector, or dependency changes. Inspect the real diff for exposure, secret handling, trust boundaries, dependency risk, and zero-knowledge/local-only architecture drift. Return CLEAR or BLOCKED with evidence.
6. **QA reviewer:** independently run the actual test, build, and lint commands. Verify the story's own acceptance criteria, nearby regressions, and meaningful test coverage. Only QA may mark a story complete after PASS.
7. **Engineering manager:** after all stories pass, independently rerun verification, compare the full diff to scope and out-of-scope boundaries, check regressions and documentation duties, and issue the final APPROVED or BLOCKED verdict. Do not rely on earlier self-reports.

## Non-negotiable gates

- A BLOCKED security result blocks completion until fixed and cleared.
- An unchecked story blocks final approval.
- "Tests should pass" is not evidence. The reviewer must run them.
- Do not expand scope because a related improvement looks useful.
- Keep each agent or review handoff self-contained and pass only the context it needs.
- For real submissions, use the authoritative `scripts/run_submission.py` workflow and its receipts. Do not call work complete while the workflow remains incomplete or an objective block is unresolved.

## When not to use it

For a genuinely trivial, bounded change, use the project spec directly. Do not simulate seven roles just to make a one-file correction feel formal.
