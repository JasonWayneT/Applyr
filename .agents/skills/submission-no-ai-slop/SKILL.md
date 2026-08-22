---
name: submission-no-ai-slop
description: >-
  Detect (default) or edit AI-slop patterns in Applyr Resume.md and CoverLetter.md
  using the no-ai-slop pattern catalog, scoped to hiring-manager voice for Jason's
  PM applications. Use when reviewing, checking, polishing, or verifying a
  submission in data/submissions/; when running generate-submission Stage 2 or
  conversion-ready-pass Pass 3; when Jason asks if a resume/letter "reads as AI,"
  "sounds like AI," "has slop," or wants a no-ai-slop pass; or after drafting any
  new Resume.md / CoverLetter.md pair.
---

# Submission no-ai-slop (Detect / Edit)

Canonical copy for Cursor, Antigravity, and any harness that loads `.agents/skills/`.
Claude Code loads a pointer at `.claude/skills/submission-no-ai-slop/SKILL.md`.
Do not treat `.cursor/skills/` as source of truth (that tree is gitignored).

Applyr-scoped wrapper around [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop). Local reference copy: `Resource/CodeProjects/.Github Projects of Interest/no-ai-slop-main/SKILL.md` (also installed at `~/.claude/skills/no-ai-slop`).

**This skill is the later check, not the first-draft mechanism.** First drafts are constrained by `authoring_prompt.md` (preamble + digest + packet + `authoring_example_bank.json`) and caught by `scripts/submission_linter.py` via `python scripts/run_submission.py`. Run this skill for judgment-only patterns the linter cannot regex. Do not skip the linter because you ran Detect, and do not skip Detect because the linter was clean.

**Default job: Detect.** Name each pattern, quote the line, give a short fix. Do not rewrite until Jason confirms (same checkpoint rule as conversion-ready-pass Pass 3). Do not score. Do not guess whether AI wrote it.

**Edit job:** only when Jason says to apply / fix / rewrite the findings.

## When this runs (required, not optional)

1. After Stage 1 authoring in `generate-submission` (before or as part of Stage 2's human read).
2. As part of `conversion-ready-pass` Pass 3 (alongside the hiring-manager read).
3. Anytime Jason asks for a voice / AI / slop check on submission docs.

Audience is always: a hiring manager reading **one** company's resume + letter. Jason's voice: plain, concrete, blunt, no corporate fluff. Preserve grounded facts from `workExperience.md`. Never invent claims to sound more human.

## Already covered by `submission_linter.py` (still flag if present, but prefer the mechanical receipt)

Do not re-litigate these as novel findings if `verify_submission.py` already passed clean. Only raise them if the linter missed them:

| Pattern | Linter |
|---|---|
| Em dashes / `--` | LR-006 |
| Semicolons | LR-014 |
| Colon-as-elaboration | LR-015 |
| Gap confession | LR-016 |
| Banned core words (leverage, passionate, etc.) | LR-009 / LW-006 |
| Throat-clearing / faux-insight / puffery / weasel / hub-verb / binary contrast | LW-015-LW-020 |
| "Lives or dies on" cliche | LW-033 |
| Recap-kicker labels ("That's genuine...", "That's how I treated...") | LW-034 |
| Paragraph-start negative listing ("Not a ...") | LW-035 |
| Contrast-frame density | LW-008 / LW-008-PAIR |
| Cross-doc 6+ word restatement | LW-009-PAIR |
| Ownership-verb vs. claim's own `attribution` tag | LW-028 |

## Judgment-only patterns (this skill's real job)

These do not regex reliably. Read for them every time:

1. **Robotic rhythm** -- stacked resume bullets with the same shape (especially trailing `-ing` / participial clauses). Vary shape: some lead with obstacle, some with number, some with who was involved, some end clean with no trailing clause.
2. **Synonym cycling** -- rotating "agent/assistant/tool" or "platform/system/solution" for style when one clear word is right.
3. **Dramatic fragmentation** -- "X. And Y. And Z." / "That's it."
4. **Negative listing the linter missed** -- "Not X. Not Y. A Z." when it is not a paragraph-starting "Not a ...".
5. **Fake-profound kickers the linter missed** -- closing line that turns the point into a cute metaphor or mic-drop, in wording LW-033/LW-034 did not catch.
6. **Summary-recap endings** -- "Ultimately," / "Overall," / a final paragraph that only restates (LW-007 catches the comma-gated openers).
7. **Formula letter architecture** -- flag per letter if that letter itself is formulaic; do not flag solely because another company's letter shares a closer.
8. **Banned / empty words the linter may not catch** -- `streamline(d)`, `robust`, `utilize`, `facilitate`, `empower`, plus empty "really"/"actually"/"genuinely" when they add nothing. `cutting-edge` / `delve` / `harness` / `elevate` / `paramount` / `multifaceted` are already LW-006.
9. **Superficial analysis** -- trailing "highlighting/underscoring/reflecting/showcasing..." clauses.
10. **Fake-strong verbs** -- "serves as a centralized hub," "plays a vital role," etc. (LW-017/LW-019 catch some of these).

## Detect output format

Per company / document:

```
### {Company} -- Resume | Cover letter
- **{Pattern}** -- "{quoted line}" -- fix: {few words}
```

If clean: `none` for that document. End the batch with the 1-3 loudest cross-document process tells so Jason can fix the drafting habit, not only the instance.

## Edit rules (when approved)

- Minimum effective edit. Keep Jason's grounded metrics and ACC stories intact.
- After edits: recompile PDFs, run `python scripts/run_submission.py data/submissions/{company} --resume`, then re-Detect the changed docs.
- Never "humanize" by inventing voicey claims that aren't in `workExperience.md`.

## Out of scope

- Story-fit / best-ACC selection (that's generate-submission Stage 1 + required-item fidelity).
- Rubric scoring (conversion_rubric.md).
- Cross-company distinctiveness as a goal (invisible to real readers).
- First-draft composition (that's `authoring_prompt.md`, not this file).
