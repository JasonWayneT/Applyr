---
status: complete
created: 2026-08-21
related: CR-097, CR-074, CR-070
contains: CR-098 (Harness-agnostic no-ai-slop)
---

# CR-098 -- Epics and stories

Jason locked the design in chat (2026-08-21) and said build and execute. Stories below were implemented the same session.

## Epic 1 -- First draft (prevent)

- [x] 1.1 COVER LETTER VOICE block in `author_from_packet.py` preamble (outside digest budget)
- [x] 1.2 Seed `cover_voice_kicker` bank examples (recap kicker + lives or dies), few_shot_eligible true
- [x] 1.3 Register `cover_voice_kicker` in `authoring_defect_categories.py` (LW-033/034/035)

## Epic 2 -- Check (catch)

- [x] 2.1 LW-034 recap-kicker WARN
- [x] 2.2 LW-035 paragraph-start negative listing WARN
- [x] 2.3 Tests for the new rules and category map
- [x] 2.4 Lint every folder in `data/submissions/` after the new rules (self-repair protocol)

## Epic 3 -- Portable skill (not the source of truth)

- [x] 3.1 Canonical SKILL.md at `.agents/skills/submission-no-ai-slop/`
- [x] 3.2 Claude and Cursor pointers
- [x] 3.3 AGENTS.md File Map + generate-submission Stage 2 point 7 + conversion-ready-pass companion path

## Epic 4 -- Reauthor in-flight cover letters

- [x] 4.1 Rebuild packets for the six folders (no Stage 0 redo)
- [x] 4.2 Rewrite CoverLetter.md only from packet + digest + bank
- [x] 4.3 Stage 1 verify; do not finalize; do not disposition hm.critical_read
