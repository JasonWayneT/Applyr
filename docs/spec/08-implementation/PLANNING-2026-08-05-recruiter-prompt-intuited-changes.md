# Planning Doc: Intuiting Process Changes from a Director of Recruiting's ChatGPT Prompt List

**Status:** Exploratory — not yet implemented. This is a working doc for Jason + Claude to keep adding
options to before anything gets built. Nothing below has been written into `conversion_rubric.md`,
`conversion-ready-pass/SKILL.md`, or any other pipeline file yet.

**Source:** Jason supplied a 16-prompt list a Director of Recruiting shared as "more specific ways to
let AI improve your resume" (vs. just asking ChatGPT to write it outright). Task: figure out whether any
of these represent gaps in Applyr's own resume/cover-letter authoring and audit process.

---

## Round 1 — Mapping the 16 prompts against the existing pipeline

Cross-referenced against `data/conversion_rubric.md` (R1–R8 / C1–C5), `.claude/skills/conversion-ready-pass/SKILL.md`
(Pass 1/2/3), and the Hard Anti-Hallucination Rules / Exclusion Zones in `CLAUDE.md`.

### Already covered — no new process needed
| # | Prompt | Where it's already handled |
|---|---|---|
| 4 | Translate skills/keywords to a new industry | R4 Metric Quality + claims-based authoring in `generate-submission` |
| 12 | Responsibilities → measurable achievements | Same — this is the core mechanism of the pipeline |
| 7 | Tailor to a specific job title | R2 JD Keyword Alignment, R6 Seniority Altitude |
| 2, 10 | Concision / action verbs | R2, R6 implicitly enforce outcome-forward, non-padded bullets |
| 8 | Make impressive without exaggerating | Hard Anti-Hallucination Rules + `LW-012` (assertion-of-fit overclaim) — governed *more* strictly than the prompt implies |
| 14 | Showcase a transferable skill | Same `LW-012` guard, plus the honest-transferable-bridge rule (see Relativity/"Data Enrichment" example in `CLAUDE.md`) |
| 9 | Appeal to a specific company's recruiter | C1 Opening Hook / C3 Role Fit Logic (cover letter side) |

### Not applicable / actively risky for Jason specifically
| # | Prompt | Why it's a bad fit, not just a non-gap |
|---|---|---|
| 6 | Reorganize to emphasize leadership experience | Jason is explicitly **not a people manager** (Exclusion Zones). This framing pressure is exactly what produces an overclaim — building tooling around it would work against the anti-hallucination rules, not for them. |
| 13 | Adapt resume for a leadership role, keep technical detail | Same issue — targets management titles Jason isn't targeting. |
| 11 | Reflect a recent promotion | No promotion event exists in his history per current source docs. Nothing to build for yet. |

### Genuine gaps — process moves the current pipeline doesn't make
| # | Prompt | Gap identified |
|---|---|---|
| 1, 15 | "Tell me why you'd reject this" / "identify red flags" | Pass 3 today is a **quality** read (proof density, authenticity, tailoring) — not an adversarial **kill-reason** hunt. Nothing currently asks "what's the single reason a hiring manager tosses this in the first pass." |
| 5, 3 | "Readable in 6 seconds" / "a recruiter who's never done this job" | R3 (Top-Third Signal) checks whether the *right content* is up top — it does not test visual scan speed (bullet length, density, whether the eye actually lands on the metric). Different failure mode than anything R1–R8 currently scores. |
| 15, 16 | Red flags / employment-gap phrasing | Distinct from Pass 2 (truth-grounding/fabrication) and from the no-ai-slop pass (voice). Career-narrative concerns — gaps, tenure length, title trajectory — are currently unowned by any step. |

**Working recommendation from Round 1** (not yet actioned): these three gaps are judgment reads, not
point-scorable dimensions — they'd fit as an addition inside Pass 3 of `conversion-ready-pass`, not as
new R/C rubric criteria. Rubric stays as-is; Pass 3 gets sharper.

---

## Round 2 — External research (ATS/recruiting best-practices doc Jason sourced)

Jason supplied a 4-stage research summary (job-fit filtering, ATS resume tailoring, cover letter
drafting, AI-authenticity/detection) with citations. Verified claims via WebSearch before trusting them,
then cross-referenced against the actual pipeline (`generate-submission/SKILL.md`, `conversion_rubric.md`,
`scripts/submission_linter.py`).

### Source-doc claims that don't hold up — don't cite these even if we adopt the underlying idea
- **"75% of resumes rejected by ATS" is fabricated.** Traces to an unpublished 2012 vendor sales pitch
  (Preptel, defunct since 2013). A 2025 Enhancv survey of real recruiters found 92% said their systems
  don't auto-reject on content at all. No study behind the number, ever.
- **"~30% ATS score drop from keyword stuffing"** — untraceable citation chain (LinkedIn data → Resume
  Genius → everyone else), same SEO-content-mill genre that produced the 75% stat. Directionally plausible
  (context > density is real), specific number is not trustworthy.
- **83% of hiring managers read cover letters / 81% reject based on them alone — this one is real**
  (Resume Genius 625-hiring-manager survey 2023; Zety Recruiting Preferences Report, 753 recruiters).

### Already matched or exceeded by the existing pipeline — no new work
- R2's 60–80% keyword coverage ≈ the doc's (legitimately-sourced) 70–80% match recommendation.
- R4 metric hierarchy / "Action + Context + Result" ≈ the doc's PM-scan criteria.
- Attribution Discipline (OWNED/CONTRIBUTED/INFLUENCED) is stricter than the doc's binary
  ownership-verb suggestion.
- The doc's "convergent AI phrasing across applicants" concern is exactly what the 2026-07-30 cross-batch
  sweep already found and mechanized as `LW-021`/`LW-022`.

### Genuinely new candidates (none implemented yet)
1. **Posting-quality red-flag score** — Stage 0 today only checks fit-for-Jason, never "is this posting
   itself a bad-actor signal" (urgent-hire + tiny team, unrealistic skill-stacking, repeated reposting).
   Different axis, currently unchecked. **Open question:** does `jobagent.sqlite`/the scout connectors
   record first-seen dates, so "reposted 3x in 90 days" is even mechanically detectable? Needs a look
   before this goes further.
2. **Vocabulary list gap in `submission_linter.py`** — confirmed via grep, not guessed. Already banned:
   `delve`, `pivotal`, `cutting-edge`, `spearheaded`, `harness`, `unwavering` (line ~394-395). **Missing:**
   `paramount`, `showcasing`/`showcase`, `foster`/`fostered` — all current (2026) recruiter-detection tells
   per research, not in the list anywhere. Small, low-risk addition.
3. **Bug found while checking #2, unrelated to the source doc:** `spearheaded` is simultaneously banned
   as an AI-slop tell (`submission_linter.py:394-395`) and used as a trusted high-confidence ownership-verb
   signal for the attribution-fidelity check (`submission_linter.py:1278-1280`). Contradictory treatment of
   the same word by two different rules — worth fixing regardless of anything else in this doc.
4. **PDF-only submission format — a question, not a task.** Pipeline only ever produces PDF
   (`compile_single.py`, the 1-page rule). Doc flags `.docx` as the safer ATS-parsing default. Not
   proposing a docx export path — just flagging nobody's confirmed whether PDF-only has ever actually cost
   a real application.

### Real tension — flagged, not resolved
The doc's cover-letter advice ("reference a product launch/blog post that only research would surface")
directly conflicts with `generate-submission/SKILL.md`'s explicit, deliberately-argued rule: no web
research at any stage, for any purpose — the file's own reasoning is that if search isn't safe for the
higher-stakes REJECT/PASS call, it isn't available for the lower-stakes cover-letter-hook call either.
Not recommending reversal. Sitting here as the one place this research pushes directly against a decision
Jason already made on purpose.

---

## Infrastructure — offloading research to Gemini (2026-08-05)

Goal: stop spending Claude's token budget on research-type side-tasks (this doc's Round 2/3) so it
doesn't compete with actual drafting throughput for the day.

- **`gemini` CLI is a dead end for this.** Installed (v0.42.0), but its existing OAuth login is for
  "Gemini Code Assist for individuals," which Google has sunset for headless/API-key use — hard
  `IneligibleTierError`, redirects to Antigravity. Tried forcing API-key auth via a scoped
  `.gemini/settings.json` override too; same failure. This looks like a property of the agentic CLI
  product's tier-check layer, not fixable from our side.
- **Working path: call the Gemini API directly**, reusing Applyr's own existing pattern
  (`scripts/utils.py`'s `call_llm()`, same helper `scripts/research-engine.py` already uses for
  company intel) — `provider_override='gemini'`, `tools=[{"google_search": {}}]` for live grounding.
  Confirmed working with the key saved via the Settings UI (`profiles.llm_settings.geminiApiKey` in
  `data/jobagent.sqlite`).
- **Model note:** `gemini-2.5-flash-lite` is deprecated for new callers (404). Current cheap model is
  `gemini-3.5-flash-lite` — matches what the pricing research flagged as the cost-efficient option.
- Antigravity/shared-log path (Option A from the original discussion) not needed for now given B works
  headlessly — still available if a task genuinely needs Antigravity's own tool access rather than a
  plain research call.
- API key never touched the chat transcript at any point — pulled from the SQLite DB in-process, never
  printed.

## Round 3 — Stretch-role / transferable-skill fit under 2025-2026 market conditions

Prompted by Jason's recruiter-video observation (7-second scans look "damning" on stretch-fit resumes
that don't meet stated requirements) — correctly flagged as one data point. Two-part check before acting
on it: (1) Applyr's own historical outcome data, (2) external corroboration via the new Gemini research
path, both independently verified rather than taken at face value.

### Internal data check — inconclusive, not negative
Only 14 submissions have a `stage0_fit_gate.json` at all (Stage 0 fit-gating is recent; most of the 1,276
historical `jobs` rows predate it). None of those 14 have progressed past `Backlog`/`Closed` — no
interview/offer signal either way yet. The `jobs.status` schema also doesn't distinguish "silently
rejected" from "got an interview," so this won't be answerable from status alone even with more volume
later. **No real internal data exists yet to validate or refute the stricter-gate hypothesis.**

### External research — verified, holds up better than the original video
Ran a grounded Gemini query (search-tool-enabled) on requirement-strictness in the current market, then
independently WebSearch-verified its two load-bearing claims before trusting them:
- **Real & corroborated:** HBS/Accenture "Hidden Workers" study — 88% of 2,250 surveyed executives admit
  qualified candidates get vetted out by rigid, literal criteria; ~27M Americans affected. ([JobCannon](https://jobcannon.io/research/stats/hbs-accenture-hidden-workers-2021))
- **Real & corroborated:** Jobscan 2024 — exact job-title match produces a 10.6x higher interview rate.
- **Unverified, don't rely on it:** the "94% exclusion rate for middle-skills tiers" figure — no
  independent corroboration found.

### Synthesis — a refinement of "get stricter," not a blanket tightening
The mechanism is what matters, not fit-tightness in general: ATS/keyword filters are described as binary
and literal (can't infer transferable-skill equivalence), so a narrative genuinely cannot rescue a cold
application from that filter — it never reaches a human. But transferable-skill narratives are reported
to work well specifically in **warm channels** (referral, direct outreach) where a human sees the case
before any keyword filter runs.

**Proposed distinction for Stage 0's Tier 2 policy** (not yet implemented):
1. **Hard, literally-keyworded gap** (named tool/platform/certification/license) — honest-bridge-and-
   submit-cold is close to wasted effort per this research. Lean Skip, or only draft if paired with direct
   outreach rather than a blind submission.
2. **Softer domain/industry-experience gap** — the existing honest-bridge Tier 2 approach still has a real
   path, since a human is the one weighing it, not just a keyword filter.

**New lever surfaced, not yet implemented:** `Reach Out` tagging (Stage 3) currently only fires for clean
Tier 1 fits. Given warm channels are specifically where transferable narratives work, strong-bridge Tier 2
stretch fits may be where outreach matters *most* — worth extending the tagging logic, not just tightening
the reject bar.

**Concrete low-risk lever surfaced:** given the 10.6x title-match effect size, worth confirming whether
Applyr's resume headline/subtitle mechanism actually mirrors the JD's literal target title whenever that's
a true, honest match (it already has a mechanism for this — CLAUDE.md's positioning-subtitle rule — just
worth checking it's landing this consistently in practice, not assuming it does).

---

## Round 4 — Narrowing pass: decided, implemented, and still open

Full narrow-down conversation (2026-08-05). Status of every item, so this doc stays the single
source of truth instead of scattered chat history.

### Implemented this session
- **Vocab gap**: `paramount`/`foster(ed)`/`showcas(e/es/ing)` added to `LW-006` in `submission_linter.py`.
- **`spearheaded` contradiction**: removed from the banned-buzzword pattern, kept as a trusted
  ownership-verb signal, cross-referenced with comments in both places.
- **Resume name ALL CAPS bug**: `compile_single.py`'s `h1` no longer gets `text-transform: uppercase`
  (was forcing every PDF-extracted name to read "JASON TAYLOR" regardless of source casing — a known
  ATS name-parsing gotcha). `h2` section headers keep it, that's fine/expected there.
- **`jobs.status_changed_at`** (migration 015) + wiring in `jobStatusService.ts` — only stamped when
  status actually changes. Enables real elapsed-time-since-rejection math that `created_at` alone
  couldn't provide.
- **Stage 0 DB-reject rule refined**: rejection_type-classified + time-gated (30d for
  Ghosted/No-Longer-Available/unset, 120d for genuine evaluated-no, conservative block for unknown/NULL
  timing). Past-cooldown rows route to Tier 2 flagged as a re-apply, not silent auto-reject forever.
  `Self-Rejected` is permanently blocked, no cooldown clears it — corrected 2026-08-05 same day after
  the first draft had this backwards (treated it as most lenient instead of strictest; Jason: "if I
  rejected it myself, I had a reason to"). `generate-submission/SKILL.md` Stage 0 step 0.
- **Stage 0 hard/soft gap split implemented** (2026-08-05, same session, approved after the FHIR-vs-
  compliance example): zero-anchor hard gaps (named tool/platform/cert) now REJECT by default, same
  tier as a clear mismatch, flagged distinctly so Jason can override toward outreach-only pursuit for a
  standout fit. Soft gaps (domain/industry descriptors) keep the existing Tier 2/honest-bridge path.
  `generate-submission/SKILL.md` Stage 0 step 2/3.
- **Title-mirroring rule**: mirror the JD's base role title when honest; never adopt its domain/industry
  qualifier unless genuinely backed by real experience (same overclaim class as the existing "Data
  Enrichment" rule). `CLAUDE.md`/`AGENTS.md`, synced.
- **`Reach Out` extended to strong-bridge Tier 2 fits**, not just clean Tier 1 — warm outreach is where a
  transferable-skill argument actually works, per the Round 3 research. `generate-submission/SKILL.md`
  Stage 0 + Stage 3.
- **Pass 3 reject-trigger checklist**: sourced, concrete (typos/grammar 77% CareerBuilder, structural
  breaks, unexplained gaps, missing must-haves). `conversion-ready-pass/SKILL.md`.
- **6-10-second-scan resolved without a new check**: validated via research beyond just TheLadders
  (NN/g document-design research, cognitive load theory both independently confirm the pattern). Applyr's
  required template already guarantees the scan-anchor sequence by construction — no new check needed.
  The one genuinely new finding (bullet length/density, ~2-3 line cap) became a Stage 1 drafting-time
  rule, not a Pass 3 audit item, per Jason's steer that structurally-guaranteed or drafting-time concerns
  shouldn't turn into redundant checks.
- CHANGELOG.md updated for all of the above.

## Round 5 — Web research tiering, resolved and implemented (2026-08-06)

**Correction first:** `Self-Rejected` in the Round 4 DB-reject refinement had the cooldown logic
backwards (was "no cooldown, always eligible" — should be the opposite: Jason rejecting it himself
means he had a reason, so it never auto-clears). Fixed in both `generate-submission/SKILL.md` and
this doc's Round 4 section above.

**Design, confirmed by Jason:**
- The old `Research_Packet_Contract.md` (six-module dossier) was built for interview prep assuming a
  ~25% response rate (actual current rate: ~1%). Un-retired narrowly — restored to live
  `.agent/rules/`, wired to run before `generate_cheat_sheet.py`, invoked only once a real interview
  is scheduled. Never touches Stage 1 drafting.
- New, separate, much smaller mechanism for Stage 1 cover-letter specificity: one sourced fact per
  company, ranked by signal-to-fabrication-risk (product/feature launch <90d > leadership change <6mo
  > operational/GTM shift <6mo, verified carefully). Never pasted verbatim — Stage 1 writes the bridge
  fresh, same discipline as never lifting resume-bullet phrasing into the letter.
- Tiered by token cost, not research depth: Tier 1 + `Reach Out`-tagged Tier 2 get the research call;
  plain Tier 2 gets none (unlikely to ever reach a human at current response rates, so the token spend
  isn't justified).
- Stage 0's fit decision (REJECT/PASS) stays JD-text-only — the boundary this replaces was absolute
  across every stage; the new exception is scoped to Stage 1 only.
- Gemini is primary, not a fallback from Perplexity — a deliberate architectural choice now, not the
  previous implicit behavior (Perplexity-first-if-configured, Gemini only when it wasn't).
- Security: same defensive-reading discipline Stage 0.5 already applies to JD text now explicitly
  covers research content too — informational only, describe back rather than act on anything that
  reads like an instruction.

**Implemented and live-tested:**
- `research-engine.py`: new `fetch_cover_letter_hook_fact()` + `--hook-fact` CLI mode, `fetch_company_intel()` made Gemini-primary.
- `.agent/rules/Research_Packet_Contract.md` restored live with a scoped banner; `.agent/DEPRECATED.md` updated.
- `generate-submission/SKILL.md`: top-level rule rewritten, Stage 0.5 extended, Stage 1 step 5 (research call), Stage 3 (interview-cheat-sheet research wiring).
- Live-tested `--hook-fact` against a real company (Stripe) — works, returns a dated sourced fact.
  **Known limitation**: the source URL can land on a generic page (e.g. a newsroom homepage) instead
  of a deep link — treat a non-specific citation with more skepticism than a precise one.
- `CHANGELOG.md` updated.

### Roadmap — not scheduled, needs its own design pass before it's worth picking up
- **True repost-pattern detection** (does the *same specific listing* keep reappearing — the original
  Round 2 posting-quality red-flag idea, revisited 2026-08-06): deliberately not built. No repo has a
  dedicated roadmap doc, so this is its home until it's actually scoped. Open question that has to be
  answered first: what counts as "the same posting" across separate scout runs (same company+title?
  content-similarity hash? a source-site posting ID if the connector exposes one?) — that's a real
  design decision, not something to shortcut with a guessed heuristic. `status_changed_at` (built,
  Round 4) already solves the *reapply-timing* need this was originally bundled with; this item is
  specifically the separate, harder "is this listing itself being reposted" signal from Round 2.

---

## Open — Round 6 and beyond

Space for further options as we explore. Nothing here yet.

## Implementation checklist (fill in once we've converged on scope)

- [ ] Decide exact wording/placement of the Pass 3 addition(s)
- [ ] Decide whether this needs a CR doc per `CLAUDE.md`'s Documentation Update Checklist, or is small
      enough to land as a direct `SKILL.md` edit
- [ ] Update `conversion-ready-pass/SKILL.md`
- [ ] Update `CHANGELOG.md` under `[Unreleased]` if it's a process/behavior change worth recording
- [ ] Copy any `CLAUDE.md` edits into `AGENTS.md` byte-identical (per the sync rule at the top of both files)
