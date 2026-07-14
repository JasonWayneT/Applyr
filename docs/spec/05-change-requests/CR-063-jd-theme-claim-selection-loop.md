# CR-063: JD Theme-Extraction & Claim-Selection Test-and-Iterate Loop

## Metadata
- **Epic**: Local-LLM Drafting Pipeline (see `docs/reports/local-llm-builder-architecture-options.md`)
- **Status**: Not started — this CR is the handoff brief for the session that starts it
- **Date**: 2026-07-13
- **Source**: Jason manually reviewed 16 submissions across two batches in one session (see
  `data/jd_gap_analysis_log.md` and `docs/spec/08-implementation/CR-053-fit-rubric-overhaul-epics.md`
  finding 6). The recurring defect — the same closing paragraph reused verbatim in 6 of 16 letters
  regardless of JD fit — pointed at claim/theme selection, not prose quality, as the dominant problem.
  Jason then asked to build a prompt and resources for a dedicated session to run an explicit
  test-and-iterate loop on this specifically, rather than continue fixing submissions by hand one at a
  time.

## Problem
Root-caused during the same session, in code, not by inference:

1. **`jd_tailoring.py: THEME_KEYWORDS`** — the only mechanism that flags a JD's "priority themes" is a
   hardcoded 27-entry keyword→phrase lookup table. It contains no entry for `privacy`, `compliance`,
   `identity`, `access`, `governance`, `healthcare`, `regulatory`, `notification`, `workflow`, or
   `commercial` — but does contain oddly specific one-offs (`lender`, `borrower`, `franchise`,
   `underwriting`) that look like they were bolted on reactively after one JD each. Its vocabulary is
   shaped by Jason's own resume terms (`platform`, `data`, `migration`, `security`, `roadmap`, `saas`,
   `stakeholder`, `integration`, `api`, `analytics`), so almost any B2B SaaS JD trips the same 3-4
   themes regardless of what it's actually distinctively about.
2. **`jd_tailoring.py: score_claim_for_jd`** — claim ranking is literal keyword/token overlap between
   claim text and JD text (plus the same narrow theme list). No semantic matching at all.
3. **Already built, never wired in**: `local_embeddings.py` (`get_embedding` via Ollama's
   `nomic-embed-text`, `cosine_similarity`) and `claim_catalog.py`'s `_sync_embeddings` generate and
   cache an embedding for every claim in `master_claims.json` — but nothing in the selection path
   calls `cosine_similarity`. The infrastructure for semantic matching exists and is unused.
4. **Already designed, never built**: the architecture judge workflow in
   `docs/reports/local-llm-builder-architecture-options.md` ranked "Hybrid Anchor + Polish" (#3, 79.8
   overall / 64 quality-ceiling, best of the top four) as the design that actually touches claim tiering
   and cover-hook generation — explicitly named as "the piece that addresses those [structural]
   defects, not just phrasing." CR-062 shipped its safe, narrower predecessor ("Deterministic-Minimal-LLM",
   prose rewriting only, claim selection untouched by design) and named Hybrid Anchor + Polish as
   phase 2, not started.

This CR does **not** propose a new architecture. It proposes the calibration loop CR-062 itself said
should happen before phase 2 is built: measure the actual selection-accuracy gap against real JDs,
using ground truth a human already verified, before writing any new selection code.

## Decision
Run an explicit, repeatable loop, using `docs/reports/jd-theme-claim-eval-set.md` (16 JDs, human-verified
themes and the specific grounded claim each should surface, built the same session as this CR) as the
fixed ground truth:

1. **What happened** — run the current pipeline's JD-profiling + claim-selection step
   (`build_jd_profile_deterministic` → `score_claim_for_jd` → `pick_cover_bullets`) against each JD in
   the eval set's `Original_JD.txt`. Record the actual priority_themes, keywords, and top-ranked claims
   per JD.
2. **What should have happened** — the eval set's "Claims that should surface" column, already verified
   against `workExperience.md` this session. Do not re-derive this; it is the fixed baseline.
3. **Diagnose and fix the smallest thing that closes the gap** — for each mismatch, identify which layer
   actually failed (missing `THEME_KEYWORDS` entry vs. a claim with weak/missing tags vs. a scoring
   formula that over-weights generic tokens vs. something only semantic matching or an LLM judge could
   catch) and apply the narrowest fix for that specific layer. Do not jump straight to building Hybrid
   Anchor + Polish's full architecture on the first mismatch found.
4. **Re-test the full eval set, not just the JD that motivated the fix** — a fix aimed at one JD's gap
   can change ranking behavior for all 16. Re-run step 1 across every row every round.
5. **Repeat** until the eval set shows reliable coverage — see Acceptance Criteria for the bar — or
   until cheap fixes (expanded keyword table, better claim tags) are clearly exhausted and the gap
   remaining can only close via semantic matching (wire in the existing cached embeddings) or an LLM
   judge (flip `jd_profile_mode`/`cover_hook_mode` to `"llm"`, which already prefers local models first
   per `llm_stages.call_llm_stage`'s `STAGE_PROVIDERS` ordering — this is not a cloud-only path).

**Hard constraint carried over from every other CR in this project:** this loop is about *selection*
accuracy — which existing, grounded claims surface for a given JD — never about inventing new claims
or wording that isn't in `workExperience.md`. If a JD needs something no claim covers, the eval set
already marks that as an unfixable gap; the loop should confirm the pipeline discloses it honestly
(as the manually-rewritten Covideo/Redox/PAR letters now do) rather than fabricate coverage.

## Acceptance Criteria
- A dated round-log (append to this file or a new `CR-063-tracker.md` under `08-implementation/`,
  matching the CR-053-epics.md pattern) showing, per round: which JDs were re-tested, what changed,
  and the before/after theme-match rate.
- Quantitative bar: reliable means the deterministic extractor (or whatever replaces it) correctly
  surfaces the eval set's "should surface" claims for at least 14 of 16 JDs, with the 2 remaining
  failures documented as requiring semantic/LLM-based matching rather than a keyword-table patch.
- Zero new fabricated claims introduced anywhere in the process — every fix either expands
  `THEME_KEYWORDS` with real JD vocabulary, improves tags on an existing `master_claims.json` entry, or
  changes ranking math. Nothing gets invented.
- If the loop concludes cheap fixes are exhausted, a clear go/no-go recommendation on wiring in the
  existing embedding infrastructure and/or piloting `jd_profile_mode="llm"` on a small batch, informed
  by real round-by-round evidence rather than the architectural reasoning alone.

## Out of Scope
- Building Hybrid Anchor + Polish's full architecture (schema-enum claim IDs, self-consistency cover-hook
  ensemble, resident 14B "anchor" model) — that is the follow-up CR if this loop concludes it's needed,
  not this one.
- Re-litigating the architecture ranking itself — `local-llm-builder-architecture-options.md`'s judge
  workflow already ran; resume it (`Workflow({scriptPath, resumeFromRunId: "wf_6ba6f622-72e"})`) only if
  new evidence from this loop genuinely contradicts its ranking, not by default.
- Re-scoring already-fixed submissions from this session's two review batches — they're done; this CR
  is about the pipeline's default behavior for the *next* batch.
