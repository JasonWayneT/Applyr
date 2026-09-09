---
name: conversion-ready-pass
description: Run the full multi-pass conversion-readiness workflow on one or more submissions in data/submissions/ — rubric scoring, a mechanical truth-grounding sweep (auto-fixed), and a qualitative hiring-manager read (surfaced for approval) — repeated up to 3 rounds so Jason doesn't have to ask for each pass separately. Use when Jason asks to make a submission "conversion ready," "apply ready," or "ready to send," asks to "review" or "check" resumes/cover letters in data/submissions/, or says he's "about to start an application cycle." This supersedes running eval_submission.py alone — that script is Pass 1 of this workflow, not the whole thing.
license: private
---

Canonical copy for Codex and harnesses that load `.codex/skills/`.
Claude Code loads a pointer at `.claude/skills/conversion-ready-pass/SKILL.md`.
Do not keep a second full copy under another harness directory.

# Conversion-Ready Pass

Three passes, run in order, on every submission in scope. Don't stop after Pass 1 and call it done — that's the mistake this skill exists to prevent. Don't wait to be asked for Pass 2 or Pass 3 separately.

**Read `CLAUDE.md` at the project root first if you haven't this session.** It owns the ground-truth files, the verified-partner list, the forbidden-language list, and Required Verification. For submissions already on the CR-076–084 path (`workflow_state.json` present, or authored via `generate-submission`), prefer `python scripts/run_submission.py <folder> --resume` / `--finalize` over hand-assembling Pass 2 worker scripts — Mech already wraps compile + `verify_submission`. This skill is for checking a document *not* produced by that flow (or when Jason asks for conversion-ready on an older folder); for generate-submission-authored docs, Stage 2 of that skill already covers the conversion-ready trigger.

## Scope

Applies to whichever submissions Jason names, or every folder in `data/submissions/` if he says "these" / "the new batch" without naming specific companies. Confirm scope before starting if it's ambiguous (e.g., "the new batch" when there are both untouched and already-reviewed folders present).

---

## Pass 1 — Rubric

**Do not shell out to `python scripts/eval_submission.py` as the default path.** CR-070 Epic 5 Story 5.1 (2026-07-17, `docs/spec/08-implementation/CR-070-claude-native-generation-pipeline-epics.md`) deliberately retired that call to opt-in-only: it calls a local LLM (`call_llm`, Ollama with a Gemini cloud fallback), and reusing it by default would silently reintroduce the exact subprocess call this CR's own acceptance criterion eliminated. The script stays in the repo unmodified for opt-in use only — this line in this skill previously still pointed at it as the default, which is a doc-staleness bug, not a green light to use it (found and corrected 2026-08-17, after it returned a materially wrong score — see below).

Instead, score directly against `data/conversion_rubric.md` (R1-R8 resume / C1-C5 cover letter) yourself, inline, using the same schema and thresholds `eval_submission.py`'s prompt already encodes.

**Check for an existing score first.** Any submission authored via `generate-submission`'s CR-076-084 flow (`workflow_state.json` present, status COMPLETE) already has an authoritative `rubric_score` in `draft_manifest.json`, written the correct way (inline, at authoring time). Read it before re-scoring from scratch — only re-score if the document changed since, or no manifest exists. Trust the manifest's number over anything `eval_submission.py` would return: on a real 2026-08-17 batch, the manifest had pop_up_talent's cover letter at 69/100 (barely above the 65 floor, correctly flagging a fleet-domain proof-point stretch) while `eval_submission.py` reported 92/100 for the identical unedited text — the subprocess path isn't just off-default, it can materially mask a real weakness.

Thresholds: Resume 70+, Cover Letter 65+ = CONVERT-READY floor (per `CLAUDE.md`). Below threshold or within ~5 points of it: treat the specific rubric criteria that came in low as the signal, and fix based on those, using real claims from `master_claims.json` — never invented ones. Re-score after any fix to confirm it moved.

## Pass 2 — Truth-Grounding Sweep (mechanical — auto-fix, don't ask first)

This pass exists because the rubric grader doesn't check this and the deterministic linter (`submission_linter.py`) only catches partner mentions in cover letters, not resumes, and only certain phrase patterns. Two real, ground-truth violations have slipped through both those tools in this project's history: a resume claiming an unverified "regulatory stakeholders" partnership, and a resume bullet claiming Cision (a PR/media-monitoring company) served "educator-style customer education needs" — a JD-keyword injection with zero basis in `workExperience.md`.

Run this sweep across every resume and cover letter in scope:

```bash
grep -inE "director of|head of|vp of|vice president|principal product|group product manager|direct reports?|managed a team of|hired|fired|snowflake|tableau|\bfhir\b|docker|regulatory" */Resume.md */CoverLetter.md
```

Then a second pass for domain-leakage — JD-specific vocabulary that doesn't belong in a Cision/Sterkly/Zero To Sixty bullet (extend this list per the target company's industry each time — this is the pattern, not a fixed list):

```bash
grep -inE "classroom|K-12|patient|diabetes|restaurant|OEM|automotive|pharma|dealership|instructional|district" */Resume.md
```

For every hit:
1. Check it against `workExperience.md` and `master_claims.json`. If it's there, it's fine — move on (don't flag verified claims just because the regex matched).
2. If it's not grounded, fix it immediately. Don't ask first — this is a factual defect, not a judgment call, and leaving a false claim in a document that's about to be submitted is worse than a wrong fix would be. Swap in the nearest verified equivalent (e.g., "regulatory stakeholders" → "legal stakeholders"; a fabricated domain tie-in → remove it or replace with what actually happened).
3. Note what you changed and why in your final summary, so Jason sees it even though you didn't stop to ask.

This list of grep patterns will go stale as new JDs introduce new industries — add terms for whatever domain the current batch spans (medical device, automotive, restaurant tech, etc. so far) rather than treating the patterns above as exhaustive.

## Pass 3 — Hiring-Manager Read (judgment — surface, then confirm)

Read each cover letter and resume the way an actual hiring manager for that specific JD would, not against the rubric. Look for:
- **Proof density and specificity** — is the strongest available accomplishment actually in the letter, stated plainly, or is it hedged/vague where a concrete detail was available? (Example from this project: "a personal product pipeline I designed and shipped end to end" vs. naming it as the job-search automation pipeline — same fact, one reads as real.)
- **Whether reused proof points are genuinely the best fit for *this* JD**, not just reused because they're the strongest material overall. Per `CLAUDE.md`'s cover-letter-proof-point-selection policy, reuse across companies is fine and expected — the question is only whether it's the right proof for the JD in front of you.
- **Register mismatches** — does the tone fit who's actually reading this? (Example: a clever one-line rhetorical flourish that reads fine for a scrappy SaaS audience might read as too cute for a compliance-heavy regulated-industry buyer.)
- **Whether the hook is actually tailored** or could be swapped into a different company's letter unchanged.

**Structural AI tells (CR-070 Epic 8 research)** — these can't be regex-caught by Pass 2 or the linter; they're a shape, not a word, so they need an actual read:
- **Predictable per-bullet formula with no narrative variation.** Every resume bullet following the identical verb-metric-outcome template back to back reads as generated, even when every individual fact is true. Real work has some bullets that lead with the obstacle, some with the number, some with who was involved — vary the shape, not just the words.
- **Vague outcome language with no named specific.** "Significant growth," "enhanced efficiency," "improved processes" without naming the tool, project, or obstacle that made it real. If a bullet or sentence could describe literally any PM's work at any company, it's failing this check regardless of whether the underlying claim is grounded.
- **A summary or skills section that mirrors the JD's exact keywords while adding zero information about how the work was actually done.** Echoing the JD's language back at it without a specific mechanism behind it reads as keyword-stuffing, not fit.

**Adversarial reject-trigger checklist (2026-08-05, sourced — planning doc Round 1/4)**: read each document once specifically hunting for the single reason a picky hiring manager would reject it, not for what's good about it. Check against real, sourced triggers rather than a vibe:
- **Typos/grammar** — the single most common dealbreaker (77% of hiring managers, CareerBuilder survey, consistent across independent sources). Required Verification should already have caught this; read for it here anyway since a Pass 3 rewrite can reintroduce one.
- **Structural/formatting breaks** — multi-column layout, text boxes, tables, sub-10pt font, cramped whitespace. R1 (ATS Integrity) should already prevent this; flag if it slipped through.
- **Unexplained gaps or a job-hopping pattern in the dates** — read the timeline the way a hiring manager scanning for flight risk would, not just the bullet content.
- **Missing must-have keywords** — cross-check against `jd_term_gaps.json` if the folder has one; this is the human-judgment layer on top of that mechanical scan, not a duplicate of it.

Note: "does the eye find title/company/dates fast enough" (the 6-10-second scan) is deliberately *not* a Pass 3 check. Applyr's required resume template (bolded title/company/date line, reverse-chronological) already guarantees the scan-anchor sequence by construction, and bullet-density discipline is a Stage 1 drafting-time rule (`generate-submission/SKILL.md`), not something to catch after the fact — don't re-add it here as a redundant check.

**Required companion pass (2026-07-28):** run Detect mode from `.agents/skills/submission-no-ai-slop/SKILL.md` on every Resume.md / CoverLetter.md in scope before presenting Pass 3 findings. That skill owns the full no-ai-slop pattern catalog (robotic rhythm, synonym cycling, fake-profound kickers, banned words the linter may miss, etc.). Merge its findings into the Pass 3 list Jason confirms before any rewrite.

No ATS in production use detects AI authorship (2026 research, see CR-070 spec) — this isn't about evading a detector, there isn't one. It's about whether a human reader believes a real person with real experience wrote this.

**Do not auto-apply Pass 3 fixes.** Present findings as a short list — what you'd change and why — and apply only what Jason confirms. This is the one place in the workflow that stays a checkpoint: Pass 3 findings are taste and persuasion calls on documents about to go out under Jason's name, and he should see them before they change. (Contrast with Pass 2, which auto-fixes, because Pass 2 findings are true/false, not better/worse.)

---

## Convergence — the "2-3 rounds" part

After Pass 3 fixes are confirmed and applied, re-run Pass 2's grep sweep and do a fresh Pass 3 read on whatever changed. Stop when either:
- A full round (2 + 3) turns up nothing new, or
- You've completed 3 total rounds,

whichever comes first. This is what replaces Jason having to re-prompt for "one more pass" — loop it yourself before reporting back.

## Required Verification (every edit, no exceptions)

After any change in any pass, before moving to the next document or reporting anything as done:

```bash
# Lint
python -c "
from submission_linter import lint_document
with open(f'../data/submissions/{COMPANY}/{DOC}', encoding='utf-8') as fh:
    text = fh.read()
r = lint_document(text, filename='{DOC}')
print('blocks:', [b.rule_id for b in r.blocks], 'warns:', [w.rule_id for w in r.warns])
"

# Recompile
python compile_single.py ../data/submissions/{COMPANY}/{DOC} ../data/submissions/{COMPANY}/{DOC_PDF}

# Page count — must be 1
python -c "
from pypdf import PdfReader
print(len(PdfReader('../data/submissions/{COMPANY}/{DOC_PDF}').pages))
"
```

A `LW-005` (unverified cross-functional partner) warning is worth a manual read before dismissing it — the regex sometimes truncates mid-word (e.g. "engineers across three countries on back[log]") and false-positives on plural forms ("engineers" vs. the verified "engineering"). Confirm it's actually a false positive rather than skipping it by default.

## Final report format

End with what changed, grouped by pass (Pass 2 auto-fixes, Pass 3 confirmed fixes), the before/after eval scores for anything touched, and confirmation that lint + page-count checks passed — the same structure used in this project's conversion-ready sessions to date. Don't report a document "done" without having actually run the verification commands, not just eyeballed the text.
