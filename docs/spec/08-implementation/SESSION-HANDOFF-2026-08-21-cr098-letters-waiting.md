# Session handoff — CR-098 landed, six letters waiting on a human read

**Date:** 2026-08-21 (evening)
**Handing off from:** Cursor (Grok 4.6)
**Handing off to:** any harness (Cursor, Claude Code, Antigravity)
**Status:** Engineering for this thread is done. Next work is a pressure-test of six cover letters, not a new CR.

**Ignore** `SESSION-HANDOFF-2026-08-21-cr096-097-cursor-handoff.md`. It is stale. CR-097 is already built. Rhino Jetty is `COMPLETE`. The fit-rubric HTML is tracked.

---

## Read first

1. `AGENTS.md` (repo root). Do not load `data/agent_context_pack.md` into a Stage 1 author session.
2. This file.
3. `.agents/skills/submission-no-ai-slop/SKILL.md` only if you are doing a judgment Detect pass.

Canonical authoring entry point remains `python scripts/run_submission.py data/submissions/{slug}`.

---

## Git (tracked)

- Branch: `main`, **ahead of `origin/main` by 2**, not pushed.
- `c3a86a8` CR-098: harness-agnostic no-ai-slop + `LW-033`–`LW-037`.
- `55a0d67` tracks `data/fit_rubric_spec.html`; gitignores `data/*.docx` and `scripts/_bakeoff*.py`.

Do not commit `data/submissions/` (PII). Do not push unless Jason asks.

---

## What is next (do this, in this order)

**1. Pressure-test the six in-flight cover letters.** Jason said the letters looked fine and to pressure-test later. That is now the job.

Folders, all `workflow status=WAITING_FOR_HUMAN`, Stage 2 stuck on `hm` because `hm.critical_read` is still `null`:

- `amn_healthcare`
- `point_c`
- `meeboss`
- `tm2_group_llc`
- `alfa_laval`
- `nuaxis_innovations`

Read `CoverLetter.md` (and the matching `Resume.md` if the letter depends on it). **PDFs are stale.** Markdown is the source of truth until Jason asks to compile.

**Do not** auto-disposition `hm.critical_read`. That is Jason's read.
**Do not** `--resume` Stage 2 just to clear the queue.
**Do not** `--finalize`.
**Do not** invent rubric scores. `rubric_score` and `verification_passed` in `draft_manifest.json` stay empty until a real score happens.

When Jason says a letter is send-ready: compile PDFs, enter the rubric + `verification_passed: true`, then `--resume`. `--finalize` only when he says to write the jobs DB.

**2. Engineering is not next.** CR-098's epics tracker is fully checked. CR-097 has only wait-gated leftovers:

- Story 5.5 — seed `wrong_job_bleed` bank examples **after** 2 real ledger hits. Do not hand-write them now.
- Story 6.2 — run `scan_authoring_defects.py --report --last 10` after 10 post-launch submissions.

**3. Optional hygiene, not a starter task.** `data/submissions/lightcast/CoverLetter.md` still says `closed-lost` (`LW-036`). Leave it unless Jason wants archive cleanup.

---

## Standing letter rules from this thread (still bind)

- ACC-104 + ACC-115 are **one** story: CX, Upgrades, **and** Engineering. He owned requirements + export tooling for ~700 at-risk accounts. Do not split two "I moved 700" bullets.
- ACC-102: **prioritized**, not conceived. An engineer suggested going around failing ETL.
- Docker is `HARD_BLOCKED`. Never print it.
- Do not claim close/direct customer work. Discovery = lost subscriptions / Pendo / CX.
- Never print `closed-lost`. Say lost subscriptions / lost subscription opportunities (VOC-17, `LW-036`).
- Never claim a design team (`LW-037`). "I designed a formula" is fine.
- Cover letters: no workforce-reduction argument, even via euphemism.
- AMN/TM2 AI: Applyr tooling **OWNED** + Cision joint prompt research **CONTRIBUTED**. Not AI/ML product ownership.
- Nuaxis: do not claim PMP.
- Meeboss: Product Manager on the resume; letter may name the Associate seat. Do not downlevel the resume.
- No recap kickers, "lives or dies," negative listing, em dashes, semicolons, colon-as-elaboration (`LW-033`–`LW-035`, `LR-014`, `LR-015`).

---

## If Jason instead asks to build

There is no unchecked CR-098 story. Do not invent CR-099. Ask what he wants. The only open CR-097 boxes are the two wait-gates above.
