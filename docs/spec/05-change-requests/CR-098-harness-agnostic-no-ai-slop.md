# CR-098 -- Harness-agnostic no-ai-slop (first draft + later check)

**Status:** Decisions locked and implemented same session (2026-08-21).
**Date:** 2026-08-21
**Author:** Cursor (Grok 4.6), from Jason's explicit "build the C3 and execute" on the prior research recommendation.
**Related:** CR-097 (retrieval bank / digest budget), CR-074 (authoring prompt), CR-070 Epic 8/9 (`submission_linter.py` as the word-list source of truth), generate-submission Stage 1/2.

**Registry note:** no new `FR-*`/`AC-*` IDs. Informal `VR-*` IDs below are scoped to this document.

---

## Overview

Cover-letter AI-tells (recap kickers, "lives or dies on", negative listing) were supposed to be
caught by a Claude Code skill at Stage 2. First drafts still emitted them, the Detect pass was
skippable, and Cursor/Antigravity do not reliably load `.claude/skills/`. This CR splits
enforcement into two harness-agnostic layers and keeps a skill only as the judgment checklist,
on a path every target harness actually loads.

## Decisions (locked)

1. **Skills are not the enforcement.** First draft = generated `authoring_prompt.md` (preamble + digest + packet + bank). Check = `submission_linter.py` via `run_submission.py`.
2. **Do not grow the digest** for this catalog. Short always-on voice constraint goes in `author_from_packet.py`'s USER preamble. Recap-kicker before/after examples go in `data/authoring_example_bank.json` (human-seeded, `few_shot_eligible: true`).
3. **Canonical skill path is `.agents/skills/submission-no-ai-slop/SKILL.md`** (tracked). Cursor and Antigravity load it natively. Claude Code gets a thin pointer under `.claude/skills/submission-no-ai-slop/` (force-add). Do not treat `.cursor/skills/` as canonical.
4. **Catchable tells become linter WARNs, not HARD_BLOCKs.** LW-033 / LW-034 / LW-035.
5. **Cover-letter reauthor of the six in-flight folders is in scope** after the mechanism lands. Resumes stay. Do not `--finalize`. Do not auto-disposition `hm.critical_read`.

## Requirements

| ID | Title | Description |
|----|-------|-------------|
| VR-01 | First-draft constraint in the generated prompt | Every `authoring_prompt.md` tells the author to stop after the last concrete fact. |
| VR-02 | Bank examples for the same failure shape | Recap-kicker and lives-or-dies entries, two source_slugs each, `few_shot_eligible: true`. |
| VR-03 | Mechanical check without a skill | LW-033/LW-034/LW-035 fire in `submission_linter.py`. |
| VR-04 | Portable skill | Tracked SKILL.md under `.agents/skills/`. AGENTS.md File Map names it. |
| VR-05 | Digest budget unchanged | No digest expansion for this catalog. |

## Scope boundary

- Does not raise digest hard/soft limits.
- Does not make slop WARNs into Stage 1 hard-fails.
- Does not replace CR-097's human `few_shot_eligible` gate for `--promote`.
- Does not auto-accept Stage 2 human gates.
- Does not re-run Stage 0 on the six in-flight folders.
