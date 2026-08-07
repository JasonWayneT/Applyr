# SESSION HANDOFF — 2026-08-04 — Cision first-bullet rule reversal, handed to Gemini

**Purpose of this doc:** cross-harness handoff. This came out of a Claude Code session that ran a
pressure-test of an external audit doc (`docs/reports/applyr_audit_final.md`) against the real codebase.
One of the audit's recommendations turned out to be reversing a decision Jason had made and dated on
purpose (2026-07-19) — not fixing an accidental bug. Jason read that context and made the call live in
chat: **reverse it.** Small, well-scoped, two-file text edit. No code changes, no script changes — this
rule lives entirely in prose instruction files that guide the LLM's authoring reasoning.

## The decision

**Before (current, both files):** the Cision role's resume bullet listing the $40M ARR platform-
stabilization story is hardcoded to always lead the Cision bullet list, regardless of the target JD's
actual relevance priorities.

**After (what to implement):** Cision's bullets follow the exact same JD-relevance-first ordering rule
that already governs every other role's bullets — no special-cased override for Cision. The $40M ARR
bullet may still often lead in practice (it's broad, strong evidence), but it's no longer forced. Same
hard-metric tiebreaker logic that already exists for other roles applies here too, nothing new to invent.

## Exact edits

### 1. `.claude/skills/generate-submission/SKILL.md`, Stage 1, point 4

Find this sentence (mid-paragraph, right after the Cision-bullet-cap sentence):

> The Cision role's first bullet is always the $40M ARR platform-stabilization framing ("Stabilized a $40M
> ARR legacy platform serving roughly 3,500 active accounts and 25,000 users...") — Jason's explicit
> standing preference (2026-07-19), not something to reprioritize per JD. Every other Cision bullet gets
> prioritized/ordered after it based on JD relevance.

Replace with something in this spirit (reword naturally, don't just paste — match the file's existing
voice/register):

> Cision's bullets are ordered by the same JD-relevance-first rule as every other role — no bullet is
> forced into a fixed position regardless of the target JD. (Reversed 2026-08-04 — the prior version
> hardcoded the $40M ARR platform-stabilization bullet first unconditionally; Jason reviewed that decision
> during an audit pressure-test and reversed it. See CLAUDE.md's "Ordering within a role's bullet list.")

### 2. `CLAUDE.md`, "Required Document Structure" section, the bullet titled **"Ordering within a role's
bullet list"**

Find:

> **Ordering within a role's bullet list**: JD-relevance is still the primary ordering signal (per the
> Cover Letter Proof-Point Selection section's same logic, applied here to bullets) — the Cision role's
> first bullet is always the $40M ARR line regardless. Among bullets of otherwise-comparable relevance to
> the JD, prefer the one carrying a hard metric. A bullet with no metric can still lead over a
> metric-bearing one if it is genuinely the single most JD-relevant bullet available (e.g. a
> compliance-heavy JD naming the compliance-workflow bullet ahead of a same-tier metric bullet) — this is
> a tiebreaker, not an override.

Replace with (drop the Cision carve-out clause, keep everything else — the general rule already covers
Cision correctly once the exception is removed):

> **Ordering within a role's bullet list**: JD-relevance is the primary ordering signal for every role,
> Cision included (per the Cover Letter Proof-Point Selection section's same logic, applied here to
> bullets) — **reversed 2026-08-04**; a prior version hardcoded the Cision role's $40M ARR line first
> regardless of JD, Jason's explicit 2026-07-19 standing preference at the time. Re-reviewed during an
> audit pressure-test and reversed — Cision no longer gets a special-cased position. Among bullets of
> otherwise-comparable relevance to the JD, prefer the one carrying a hard metric. A bullet with no metric
> can still lead over a metric-bearing one if it is genuinely the single most JD-relevant bullet available
> (e.g. a compliance-heavy JD naming the compliance-workflow bullet ahead of a same-tier metric bullet) —
> this is a tiebreaker, not an override.

### 3. Mirror into `AGENTS.md`

CLAUDE.md's own standing rule: **CLAUDE.md and AGENTS.md must stay byte-identical.** After editing
CLAUDE.md, copy the exact same change into AGENTS.md's matching section before calling this done — don't
let them drift.

## Explicitly out of scope — do not do this

- **Do not regenerate or edit any already-drafted resume in `data/submissions/`.** This changes the rule
  for *future* drafts only. Retroactively rewriting existing real submissions is a separate decision Jason
  hasn't made — don't scope-creep into it.
- **No code/script changes.** This rule is pure prose guidance consumed by the LLM during Stage 1
  authoring — there's no `if company == "Cision"` constant anywhere to touch.

## Verification before calling this done

1. Confirm the CLAUDE.md and AGENTS.md edits are byte-identical (diff the two files, or at minimum diff
   just the edited section).
2. Re-read both edited passages once written — confirm neither still contains the words "always" /
   "regardless" / "not something to reprioritize" in connection with the $40M ARR bullet; that language is
   exactly what's being reversed.
3. Report back: which two files changed, confirm the sync, and confirm nothing in `data/submissions/` was
   touched.
