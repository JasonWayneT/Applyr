---
status: design_v3_pending_review
created: 2026-09-12
updated: 2026-09-12
from: Claude (product-proof run, JD 1/3 = Camunda)
candidate: cr112-integrated-validation-candidate @ a900b3e (worktree)
related: CR-112, docs/spec/08-implementation/CR-112-stage0-3-evaluation-plan.md
review_v1: tech-lead subagent a010c09641f1a661d — ACCEPT WITH CHANGES (folded into v2)
review_v2: same subagent, resumed — ACCEPT WITH CHANGES (folded in below; v2's
  correction mechanism was schema-invalid, replaced)
---

# CR-112 Stage 0 extraction-fallback defect — v3 (post second design-review)

Bounded defect story, not a new CR. v1 → ACCEPT WITH CHANGES (Jason then
revised the gate himself after seeing "6/6 JDs pause"). v2 → ACCEPT WITH
CHANGES again: the reviewer independently re-derived all 52 line-level
classifications (safety direction holds — nothing qualification-shaped
ever landed in `NON_QUALIFICATION`, including both `jd_05` trap lines) but
found 4 transcript errors and, more importantly, that v2's manual-judgment-
correction design **violates the real `stage0_judgments` schema**
(`UNIQUE (run_key, item_key, request_hash)` — a second row for the same
unchanged requirement set cannot be inserted, full stop). v3 replaces that
mechanism with the house's own existing append-only-history pattern
(`020_add_review_answer_history.sql`) instead of inventing a new one.
Nothing below has been implemented yet.

## Reproduction (unchanged from v1, re-confirmed by the reviewer independently)

`data/authored_drafts/camunda_cr112_proof/` (gitignored practice folder) in
the `cr112-integrated-validation-candidate` worktree, JD =
`data/archive/submissions/camunda/Original_JD.txt`, no LLM provider
credentials present, `--mode practice`. Result: `tier: Skip, fit_score: 0`,
`required` has 1 item, `preferred` is empty, despite the JD having 6 real
required bullets and 3 real preferred bullets and Jason having real,
usable evidence for several of them. Historical (LLM-based) run of the
same JD: `Tier 2 / PASS`.

## Root cause — corrected per v1 review

Default extractor is `_extract_sections_nlp()`
(`scripts/build_stage0_fit_gate.py:1093`): a local TF-IDF+LogReg classifier
per bullet; anything under `conf < 0.65` goes to `fallback_queue` for one
batched `call_llm(...)` disambiguation call.

**Two dump sites, not one** (v1 review Correction A):
- `build_stage0_fit_gate.py:1229-1231` — `call_llm` returns falsy (no
  provider). `model_call_occurred=false`.
- `build_stage0_fit_gate.py:1226-1228` — provider answered but the JSON
  body failed to parse (`except Exception`). `model_call_occurred=true`,
  **cost may already have been incurred**. Any fix that keys off
  `model_call_occurred: false` misses this branch entirely.

**A third, worse silent-loss path** (v1 review Correction B):
`build_stage0_fit_gate.py:1211-1216` — even on a *successful* parse, the
loop only applies the indices the model actually returned and `continue`s
past anything else. A partial mapping (3 of 5 indices answered, or an
answer naming a bucket string not in `buckets`) silently drops the
unmapped items — not even into `responsibilities`. No `partial`/`missing`
handling exists here, unlike `stage0_evidence_cascade.validate_batch_response`.

**`compute_fit_score` is a normalized weighted average, not additive**
(v1 review Correction C — v1 got this wrong). One required item at
`evidence_level: 3`/high confidence scores ~75 → clean **Tier 1 PASS**,
not just a possible false Skip. `build_stage0_fit_gate.py:3018` only
downgrades when `qual_required_n == 0`; at `qual_required_n == 1` (our
case, and the general single-survivor case) there is no guard. **This can
produce a false clean PASS just as easily as a false SKIP** — any fix
must not be scoped to the Skip path only.

`_recover_mixed_responsibilities` (line 1386) no-ops here because
`required` already has 1 item from the classifier's own confident guess
(guard: `if buckets.get("required"): return`, line 1394) — it was built
for "required completely empty," not "required present but thin."

The `flagged_gaps` "only N qualification-shaped required items" tripwire
(line 2943-2960, "a tripwire, not a fix") fires correctly but nothing
reads it before `compute_fit_score()`/`_determine_tier()` finalize a
terminal decision.

**Measured, not assumed** (v1 review Correction D): every one of the 6 JDs
available in this worktree (5 frozen eval fixtures + Camunda) produces a
nonempty `fallback_queue` with no provider — this is the normal case for
the no-cost path, not a Camunda-only edge case.

Header-detection gap (investigation item 2, confirmed): `classify_jd_header`
does not recognize hyphenated `"Nice-to-haves"` as a preferred-section
header (`"Nice to have"` works, the hyphenated compound does not). This
contributes to Camunda's `preferred: []` but is independent of the
fallback-dump defect and is **out of scope for this story** (see Scope
below) — it changes bucket assignment on every extractor path across all
JDs and deserves its own story and its own test corpus, not a rider on a
reliability fix.

## The two defects (unchanged framing, both confirmed)

**Defect A** — a self-flagged/structurally-unreliable extraction can still
produce a terminal PASS *or* SKIP.

**Defect B** — the manual Stage 0 classifier's request artifact does not
bind `item_id` to exact requirement text, and (new, from Jason's revision)
there is no supported way to correct a wrong classification once cached,
short of an unsupported direct `DELETE` against `jobagent.sqlite` (which is
what I did, once, to unblock this evaluation, and which is explicitly not
an acceptable recovery path going forward).

## Revised invariant (Jason's language, final)

> Stage 0 cannot produce a terminal PASS or SKIP while any unresolved
> source bullet is qualification-likely or ambiguous. Only bullets
> positively classified as non-qualification may bypass review, and every
> bypassed bullet and reason must be recorded.

The burden of proof is on `NON_QUALIFICATION`. Uncertainty pauses.

## The three-way gate

Every bullet that lands in `fallback_queue` (from *either* dump site above,
and every index dropped by the partial-mapping loss path) gets exactly one
of:

- `QUALIFICATION_LIKELY` — pauses.
- `AMBIGUOUS` — pauses.
- `NON_QUALIFICATION` — may continue without review, **but is recorded in
  the Stage 0 receipt with its reason code**, never silently.

### Independence from the failed parser

This gate must not reuse `_looks_like_qualification`/`_looks_like_duty` or
the LogReg model's own (sub-0.65-confidence, by definition unreliable for
this exact bullet) prediction as its basis — Jason's explicit requirement.
Signals used instead:

**Positive `NON_QUALIFICATION` categories** (narrow allowlist; a bullet
must affirmatively match one, absence of a qualification signal is not
enough):
1. Compensation range / pay structure text.
2. Benefits / perks text.
3. EEO / accommodation / non-discrimination boilerplate.
4. Recruiting or application-process instructions (how to apply, agency
   notices, hiring-partner logistics like "you'll be hired via Remote.com").
5. Company/role marketing description with no candidate-addressed
   expectation ("Northwind Labs is a fictional B2B workflow company...").
6. Location/travel logistics stated as *information*, not eligibility.
7. Internal posting instructions ("Talent Ops to delete as necessary").

8. **The posting's own title line**, matched against the title Stage 0
   already extracted into its own `role` field (an affirmative match
   against a known field, not a heuristic guess) — added in v3. 5 of the
   8 `AMBIGUOUS` calls in the v2 measurement were nothing but the
   posting's own title line ("Product Manager", "Technical Product
   Manager", etc.), which is structurally never a requirement and does
   not need a human review pass just because it happened to be
   low-confidence to the LogReg model.

**Signals that push toward `QUALIFICATION_LIKELY`** (independent of
bucket): explicit requirement/capability vocabulary regardless of which
section header it sits under — "experience (with/of/in)", "knowledge of",
"familiarity with", "understanding of", "ability to", "comfort with",
"skills", "must [pass/have/be]", "required", "ownership", "partner/work
with [team]", a verb phrase describing a capability the candidate must
demonstrate even when phrased as an action ("sequence...", "prioritize...",
"translate...", "keep [team] in the loop...", "use metrics to decide...").
**Responsibility-header text is NOT auto-exempted** — per Jason's explicit
examples, "Communicate complex technical concepts" and "Partner with
engineering on distributed systems" must stay qualification-likely/ambiguous
even under a Responsibilities header, because JDs routinely express hiring
criteria as duty language. **A required-section-header line may enter
`NON_QUALIFICATION` only on an affirmative category match** — sitting under
`required`/`"What You Bring"` is not itself protective; the only bullet in
the whole 52-line measurement that does this is Camunda #10 ("Talent Ops to
delete as necessary...", header `What You Bring`), and it earns
`NON_QUALIFICATION` on category 7 (internal posting instruction), not on
its header.

**Default to `AMBIGUOUS`** for anything that doesn't cleanly match a
`NON_QUALIFICATION` category and isn't unambiguous capability language —
e.g. a vague responsibility line whose capability implication is real but
soft ("Keep the platform honest about what is owned versus transferable").

### Behavior is binary; the three labels are receipt annotation only (v3 change)

v2 had `QUALIFICATION_LIKELY` and `AMBIGUOUS` behave identically (both
pause) while asking for line-level agreement on which of the two applies
to soft cases like "Keep the self-managed team equipped..." — the reviewer
correctly flagged this as unfalsifiable (no implementer can reproduce a
split that has no behavioral consequence, and disagreement on the label
should never gate approval). v3: the gate itself is binary —
**NON_QUALIFICATION (bypass, disclosed) vs. everything else (pause)**. The
three-way vocabulary stays in the recorded reason code for a human
reviewer's ordering/triage, but no test may assert `QUALIFICATION_LIKELY`
vs. `AMBIGUOUS` as a pass/fail distinction — only `NON_QUALIFICATION` vs.
not.

### Independence, made testable (v3 — replaces the honor-system clause)

"Don't reuse the failed parser's own heuristics" is not verifiable as
prose. Three concrete, checkable properties instead:

1. The detector decides **review-vs-bypass only** — it must never also be
   consulted for required-vs-responsibilities bucket assignment (no shared
   code path with `_extract_sections`/`_extract_sections_nlp`'s own
   bucketing).
2. It matches evidence **anywhere in the line**, not only at a leading
   phrase. `_looks_like_qualification`'s `_QUAL_LEADIN_RE` is applied with
   `.match()` (anchored at the start) and empirically returns `False` on
   `"Must pass a Level II fingerprint background check"`, `"Nights and
   weekends availability required"`, and Camunda #9 `"Technical knowledge
   of configuring, deploying, managing the life cycle of platform
   products."` — i.e. reusing that helper (v1's own original suggestion)
   would have swept both `jd_05` trap lines and a real Camunda requirement
   straight into a silent bypass. This is not a hypothetical risk; it is
   the exact failure mode confirmed against the existing code.
3. It defaults to **pause on no confident match**, the inverse of
   `_looks_like_qualification`'s default-`False`/non-qualifying default.

An implementation review must show these three properties hold, not just
that the doc says "independent."

### The trap this gate must not fall into

`jd_05_wideworld`'s "Must pass a Level II fingerprint background check" and
"Nights and weekends availability required" look, on the surface, like they
could hide behind "privacy/background-check boilerplate" or "location/
schedule logistics" — **they must not**. Both are explicit, `Requirements:`
-headed, "must"/"required"-worded eligibility statements (this fixture
exists specifically to test the eligibility-vs-boilerplate distinction —
Story 3.4). Category 3/6 above only covers *informational* disclosure
("we may conduct a background check as part of our process"), never an
explicit pass/fail eligibility condition. Both lines are classified
`QUALIFICATION_LIKELY` below.

## Measurement across all 6 JDs (actual lines, not just counts)

Captured by patching `utils.call_llm` to return `None` (or, for the
prompt-capture pass, a side effect that records the prompt and still
returns `None`) and calling `_extract_sections_nlp` directly against each
JD's real preprocessed text — zero network calls, confirmed by inspecting
every mock call.

### Camunda (15 queued)

| # | Text (truncated) | Header | Classification | Why |
|---|---|---|---|---|
| 0 | "Curious about the kind of challenges..." | (duplicated in source; `current_header` == the bullet itself) | NON_QUALIFICATION | culture marketing, no candidate expectation |
| 1 | "Keep the self-managed team equipped to work on the appropriate epics." | What You'll Be Doing | AMBIGUOUS | duty-shaped but no clear capability verb; conservative default |
| 2 | "Ability and/or willingness to use our product" | What You Bring | QUALIFICATION_LIKELY | "willingness" — candidate-addressed capability |
| 3 | "Experience working with platform products used by IT departments..." | What You Bring | QUALIFICATION_LIKELY | "Experience working with" |
| 4 | "Experience of OKRs, customer research techniques..." | What You Bring | QUALIFICATION_LIKELY | "Experience of" |
| 5 | "Strong communication skills..." | What You Bring | QUALIFICATION_LIKELY | "skills" |
| 6 | "Strong understanding of distributed systems concepts..." | What You Bring | QUALIFICATION_LIKELY | "understanding of" |
| 7 | "Familiarity with technologies such as Kubernetes, Docker..." | What You Bring | QUALIFICATION_LIKELY | "Familiarity with" |
| 8 | "Experience working with IT platforms in banking..." | What You Bring | QUALIFICATION_LIKELY | "Experience working with" |
| 9 | "Technical knowledge of configuring, deploying..." | What You Bring | QUALIFICATION_LIKELY | "knowledge of" |
| 10 | "Talent Ops to delete as necessary -> ..." | What You Bring | NON_QUALIFICATION | internal posting instruction (category 7) — the one bypass sitting under a required-section header; earns it on affirmative match, not on header |
| 11 | "If you're based elsewhere, you'll be hired via Remote.com..." | Compensation | NON_QUALIFICATION | recruiting/hiring-logistics disclosure |
| 12 | "We invest in your wellbeing, growth..." | Benefits & Perks | NON_QUALIFICATION | benefits |
| 13 | "Financial Security: Retirement and pension plans..." | Benefits & Perks | NON_QUALIFICATION | benefits |
| 14 | "Professional Growth: Up to $/€/£1,000/yr..." | Benefits & Perks | NON_QUALIFICATION | benefits |

**8 QUALIFICATION_LIKELY, 1 AMBIGUOUS, 6 NON_QUALIFICATION. Pauses.**
Correction (v2 review Error E4): only **5 of the 6** "What You Bring" real
requireds are in this queue (items 2-9, i.e. 8 lines once you count
correctly across What-You-Bring + Nice-to-haves) — the sixth, "5+ years of
product management experience, ideally in distributed systems...", was
confidently classified straight into `required` by the LogReg model and
never entered the queue at all; it is the single survivor this whole
defect is about. So review set = 8 qualification-likely + 1 ambiguous = 9
items (all 3 real "Nice-to-haves" preferreds are among the 8
qualification-likely). Nothing qualification-shaped is in the
non-qualification bucket.

### jd_01_northwind (7 queued)

| # | Text | Header | Classification | Why |
|---|---|---|---|---|
| 0 | "Product Manager, Platform" | (title) | AMBIGUOUS | bare title, no allowlist match |
| 1 | "Northwind Labs is a fictional B2B workflow company..." | (intro) | NON_QUALIFICATION | company description, no candidate expectation |
| 2 | "Roadmap ownership with engineering, CX, and sales partners" | Requirements: | QUALIFICATION_LIKELY | "ownership", Requirements header |
| 3 | "Comfort with data quality, release sequencing..." | Requirements: | QUALIFICATION_LIKELY | "Comfort with" |
| 4 | "SQL for investigation, not warehouse ownership" | Preferred: | QUALIFICATION_LIKELY | explicit tool/skill |
| 5 | "Sequence platform work against customer risk" | Responsibilities: | QUALIFICATION_LIKELY | implies required prioritization capability — not auto-exempted for sitting under Responsibilities |
| 6 | "Write clear requirements and keep partners aligned" | Responsibilities: | QUALIFICATION_LIKELY | implies required communication capability |

**5 QUALIFICATION_LIKELY, 1 AMBIGUOUS, 1 NON_QUALIFICATION. Pauses.**

### jd_02_contoso (7 queued) — same shape

0 title → AMBIGUOUS. 1 company description → NON_QUALIFICATION. 2
"Product management for data remediation..." (Requirements:) →
QUALIFICATION_LIKELY. 3 "Translate messy operational problems into a
backlog" (Requirements:) → QUALIFICATION_LIKELY. 4 "Experience with
customer-facing reporting quality" (Preferred:) → QUALIFICATION_LIKELY.
5 "Prioritize data defects against customer impact" (Responsibilities:) →
QUALIFICATION_LIKELY. 6 "Keep legal and CX in the loop on high-risk
changes" (Responsibilities:) → QUALIFICATION_LIKELY.
**5 QUALIFICATION_LIKELY (items 2,3,4,5,6), 1 AMBIGUOUS, 1 NON_QUALIFICATION.
Pauses.** (Correction, v2 review Error E1: v2 mis-totaled this as "4"; the
row must sum to 7.)

### jd_03_fabrikam (7 queued)

0 title → AMBIGUOUS. 1 company description → NON_QUALIFICATION. 2
"Experience with privacy or compliance workflow product work"
(Requirements:) → QUALIFICATION_LIKELY. 3 "Cross-functional alignment with
legal, CX, and engineering" (Requirements:) → QUALIFICATION_LIKELY. 4
"GDPR or CCPA program experience" (Preferred:) → QUALIFICATION_LIKELY. 5
"Turn audit findings into a sequenced backlog" (Responsibilities:) →
QUALIFICATION_LIKELY. 6 "Keep the platform honest about what is owned
versus transferable" (Responsibilities:) → AMBIGUOUS (vaguer capability
implication — conservative default).
**4 QUALIFICATION_LIKELY, 2 AMBIGUOUS, 1 NON_QUALIFICATION. Pauses.**

### jd_04_adventure (8 queued)

0 title → AMBIGUOUS. 1 "Adventure Works Ops is a fictional logistics
software company. This is an IC product role..." → NON_QUALIFICATION
(company/role description — note: this line does carry a real
IC-vs-manager signal relevant elsewhere in Stage 0, but is not itself a
required/preferred bullet). 2 "Own roadmap for an existing B2B operations
platform" (Requirements:) → QUALIFICATION_LIKELY. 3 "Work with engineering,
support, and account management" (Requirements:) → QUALIFICATION_LIKELY. 4
"Use metrics to decide what ships next" (Requirements:) →
QUALIFICATION_LIKELY. 5 "Experience in fulfillment or onboarding
automation" (Preferred:) → QUALIFICATION_LIKELY. 6 "Cut operational waste
without claiming revenue ownership" (Responsibilities:) →
QUALIFICATION_LIKELY. 7 "Keep the backlog honest under resource
constraints" (Responsibilities:) → AMBIGUOUS.
**5 QUALIFICATION_LIKELY, 2 AMBIGUOUS, 1 NON_QUALIFICATION. Pauses.**

### jd_05_wideworld (8 queued) — the trap case

0 title → AMBIGUOUS. 1 company description ("...mixes real product work
with administrative hiring lines...") → NON_QUALIFICATION. 2 **"Must pass
a Level II fingerprint background check"** (Requirements:) →
**QUALIFICATION_LIKELY — deliberately not swept into the background-check
boilerplate category; explicit "must pass" + Requirements header is an
eligibility condition, not disclosure.** 3 **"Nights and weekends
availability required"** (Requirements:) → **QUALIFICATION_LIKELY** — same
reasoning. 4 "Roadmap ownership with engineering partners" (Requirements:)
→ QUALIFICATION_LIKELY. 5 "SQL for investigation" (Preferred:) →
QUALIFICATION_LIKELY. 6 "Sequence platform reliability work"
(Responsibilities:) → QUALIFICATION_LIKELY. 7 "Partner cross-functionally
without direct reports" (Responsibilities:) → QUALIFICATION_LIKELY.
**6 QUALIFICATION_LIKELY, 1 AMBIGUOUS, 1 NON_QUALIFICATION. Pauses.**

### Summary

| JD | Queued | QUAL | AMBIG | NON_QUAL | Pauses? |
|---|---|---|---|---|---|
| Camunda | 15 | 8 | 1 | 6 | yes |
| jd_01_northwind | 7 | 5 | 1 | 1 | yes |
| jd_02_contoso | 7 | 5 | 1 | 1 | yes |
| jd_03_fabrikam | 7 | 4 | 2 | 1 | yes |
| jd_04_adventure | 8 | 5 | 2 | 1 | yes |
| jd_05_wideworld | 8 | 6 | 1 | 1 | yes |
| **Total** | **52** | **33** | **8** | **11** | |

**All 6 still pause under this conservative gate** — this design does not
reduce pause *frequency* relative to the literal invariant, only review
*size* (NON_QUALIFICATION items — company-description prose, comp/benefits
text, internal posting notes — are excluded from the human/harness review
burden but disclosed in the receipt). Per Jason: this is fine; frequency
reduction was never the target, correctness was. Zero known
qualification-shaped bullets (including the two `jd_05` trap lines) landed
in `NON_QUALIFICATION` in this measurement — independently re-derived and
confirmed by the second design review, which also confirmed the safety
direction holds (11 NON_QUALIFICATION calls checked against the real
queued text, all clean) and flagged 5 of the 8 AMBIGUOUS calls as nothing
but the posting's own title line (folded into category 8 above in v3).

**This classification was produced by Claude (the orchestrator), not by an
automated regex yet** — it is the specification the implementer's actual
detector must match. The second design review independently re-derived all
52 queues from the fixture files (not from this transcript) and checked
every classification against them.

## Manual judgment correction (Defect B, v3 — replaces v2's schema-invalid design)

v2 proposed writing a new `stage0_judgments` row and marking the old one
`SUPERSEDED`. **The second design review found this is forbidden by the
real schema**: the incident (my `required:0:bjiplgnonojgoadn`
mis-classification) is against an *unchanged* requirement set, so
`run_key`, `item_key`, and `request_hash` are all identical to the bad
row's — and `stage0_judgments` has `UNIQUE (run_key, item_key,
request_hash)` plus `judgment_key = f"{run_key}:{item_key}"` as its literal
primary key. A second row cannot be inserted; this is not a style
objection, it is a constraint violation. Making the new-row idea work would
require rebuilding the table (drop the UNIQUE, widen the CHECK, change
`judgment_key`'s derivation) and touch `get_completed_judgment`'s read
path with multi-row resolution logic — real risk on the exact durability
layer the rest of CR-112 depends on, and `stage0_checkpoint._connect()`
re-runs every migration file on every connection, so a rebuild-style
migration means a full table copy on every Stage 0 DB open (the precedent,
`022_add_bad_data_answer.sql`, does exactly that and says so in its own
header).

**v3 mechanism — the house's own existing pattern, additive only**
(`020_add_review_answer_history.sql`'s own header: *"Append-only audit
history... current state remains on the live table, each answer preserved
separately"*):

- New migration, `CREATE TABLE IF NOT EXISTS stage0_judgment_corrections`
  (judgment_key, run_key, opportunity_key, item_key, item_text,
  request_hash, previous_judgment_json, corrected_judgment_json,
  correction_source, reason, corrected_at). Pure additive `CREATE TABLE IF
  NOT EXISTS` — safe under `_connect()`'s re-run-every-migration-on-every-
  connect behavior, no rebuild, no per-connect table copy. Registered in
  `stage0_checkpoint._MIGRATIONS`.
- New `correct_judgment(...)` in `stage0_checkpoint.py`: read the live row;
  reject on missing row, or a mismatched `request_hash`/`content_hash`/
  `evidence_index_hash`, or a different `opportunity_key`, or an unknown
  `item_key` (**not** `jd_hash` — `stage0_judgments` has no `jd_hash`
  column; that lives on `stage0_runs`. Key the correction on what is
  actually on the row: `request_hash`, `content_hash`,
  `evidence_index_hash`, `opportunity_key`); then, in one transaction,
  append the history row and update the live row's `judgment_json` +
  `updated_at` in place.
- **`get_completed_judgment` needs zero changes.** It keeps returning the
  single live row, which is now the corrected one. No resolution logic
  means no way for the read path to pick the wrong row — this is the main
  reason to prefer append-only-history-plus-in-place-update over a
  superseded-row scheme.
- A correction cannot itself set `fit_score`/`tier`/`decision`/workflow
  status/receipts — it only changes what `classify_gaps` sees for that
  item on the next `--resume`; scoring happens through the normal path
  afterward.
- Rejects a correction against a stale `request_hash`/`content_hash`/
  `evidence_index_hash`, an unknown `item_key`, or a different
  `opportunity_key`.
- **Defect B recurs one layer down if not addressed here too**: the whole
  point is "no SQL, ever," but `make_item_key` letter-encodes a SHA prefix
  on purpose (to survive provider safety filters) — it is not
  human-derivable. If the correction *request* artifact carries only the
  bare `item_key`, whoever is answering it is right back to inspecting
  `stage0_judgments` to figure out what it means, reproducing Defect B
  inside its own fix. **The generated correction-request artifact must
  carry `item_key` + `bucket` + exact `item_text` + the current (wrong)
  judgment** — same binding discipline as the exact-text import template
  in the next section.
- **Regression test, explicit**: replay this exact incident — a wrong
  manual classification for `required:0:bjiplgnonojgoadn` on an unchanged
  requirement set — correct it through this mechanism, confirm zero direct
  SQLite access is needed (in contrast to what I actually had to do today),
  and confirm every *other* cached judgment under the same `run_key` is
  left untouched (the obvious blast-radius regression for an in-place
  update).

### Why no purge/invalidation mechanism is needed when the requirement set *does* change (restored from v1, dropped from v2 in error)

`get_completed_judgment` (`stage0_checkpoint.py:296-327`) requires all five
of `run_key`, `item_key`, `request_hash`, `content_hash`, and
`evidence_index_hash` to match before returning a cached judgment.
`request_hash` is the spool digest computed over `{run_key, required,
preferred}` (`build_stage0_fit_gate.py:2509-2519`) — so any change to the
requirement/preferred content changes `request_hash` and the old judgment
simply misses the cache lookup on its own; nothing needs to explicitly
purge it. (`run_key` itself is *not* content-sensitive — `make_run_key`
covers only `opportunity_key`, `jd_hash`, `prompt_version`,
`provider_policy_hash`, `evidence_index_hash` — so do not key any
invalidation logic off `run_key` changing; it won't.) This is exactly why
the correction mechanism above is only needed for the *unchanged*-requirement-
set case: that's the one case the natural cache-miss doesn't cover.

Separately (v1 review, still valid): `try_load_cascade_import` should
verify a submitted import's echoed `requirement`/`bucket` text (once item
3 below adds it to the template) actually equals the real item text, not
just that `item_id` is a known key — otherwise a classifier could answer
about text it rewrote and nothing would catch it.

## Mechanics for the new pause (v1 review PINs 1-4, unchanged, still required)

**PIN 1.** This pause fires during extraction, *before* `run_key`/
`request_hash`/`start_run` exist (those are built at
`build_stage0_fit_gate.py:2502-2543`; extraction is at `~2435`). It is a
**receipt-only pause** — no `stage0_runs` row, no `mark_run_status` call.
Do not hoist `start_run` above extraction to work around this.

**PIN 2.** Two copy sites must branch on the new `pause_kind`, not one:
`contracts.waiting_for_input_message` (what `--status` prints) and
`run_submission.py`'s own console print (~line 337). Both currently fall
through to Review Center copy for any unrecognized `pause_kind`.

**PIN 3.** Do not raise an exception from inside `_extract_sections_nlp`
itself — `test_build_stage0_fit_gate.py` and `test_stage0_confirmations.py`
call it directly and/or patch it at five sites expecting a plain 4-key
dict back. Return the unresolved queue (now three-way-classified) as an
extra key on the same returned dict; have the caller
(`build_stage0_fit_gate`) decide whether to pause.

**PIN 4.** Splice in right after `sections = ...` (~2435-2443), before
`_count_qualification_required`/`_detect_thin_jd`/`_cap_requirement_bucket`
all read `required_raw`.

## Do NOT fix this by (full list, v1 + Jason's additions)

Forcing Camunda to PASS; restoring its historical result; lowering the fit
threshold; treating all `responsibilities` as `required`; suppressing the
tripwire warning; giving the one recognized item disproportionate weight;
adding Camunda-specific phrasing/company-name special-casing; using an LLM
despite the no-cost policy; auto-promoting every bullet to required;
letting a tripwire warning coexist with a terminal decision; rubber-
stamping the pause (an "accept all" response key, or leaving an unresolved
item's bucket silently defaulted rather than requiring it be explicitly
set); relaxing `_recover_mixed_responsibilities`'s guard as a substitute
fix (it has no idea the classifier was unconfident and cannot see this
class of bug); converting the failure into `Stage0ExtractError`/`FAILED`
(a crash is not a resumable pause and kills batch/practice flow); gating
the pause on `model_call_occurred == false` only (misses the
parse-failure branch); reusing the extraction parser's own bucket/duty
heuristics as the qualification-risk signal (must be independent); tuning
the three-way gate's thresholds merely to reduce pause count on the 6
measured JDs (accuracy is the target, not a quota).

## Scope

In scope: the fallback-dump defect (both sites + partial-mapping loss),
the new pause, the three-way gate, the manual-judgment correction
mechanism, exact-text binding on the existing Stage 0 manual-import
template. Out of scope, log separately: `_extract_sections_llm` (already
fails closed via `Stage0ExtractError`, no fallback queue, untouched);
Stage 1's closed-world cascade (Epic 3, a different module); the
hyphenated `"Nice-to-haves"` header-detection gap (changes bucket
assignment on every extractor path and JD, deserves its own story/tests).

## Test plan (supersedes v1's list)

1. Camunda-shaped fixture, `call_llm` mocked to return `None` → pauses
   `WAITING_FOR_INPUT`/`pause_kind=requirement_extraction_review`, not
   `SKIPPED`; no `stage0_runs` row created; no `mark_run_status` call
   (PIN 1).
2. Same fixture, one confidently-classified required item at
   `evidence_level: 3`/high confidence + a nonempty QUALIFICATION_LIKELY
   queue → must pause, not finalize a clean `Tier 1 PASS` (the false-PASS
   direction — this is the case that would let a Skip-only fix through).
3. `call_llm` mocked to return an unparseable body (`except` branch,
   `model_call_occurred: true`) → pauses the same way.
4. `call_llm` mocked to return a partial/invalid index mapping → the
   unmapped items are not silently lost; they enter the three-way gate
   like any other unresolved item.
5. `contracts.waiting_for_input_message` and `run_submission.py`'s console
   print both branch correctly for `pause_kind=requirement_extraction_review`
   (PIN 2) — do not just test `_print_status`, which prints nothing of
   its own.
6. Fully-confident extraction (empty `fallback_queue`) → unchanged
   behavior, no new pause (synthetic case; no natural corpus example
   exists in this repo).
7. Genuinely-thin JD (classifier confident, one real required item, empty
   queue) → still reaches `Tier 2`/`Skip` normally (synthetic; proves the
   gate keys off unresolved-and-risky, not off small `required[]`).
8. Each `NON_QUALIFICATION` category gets its own fixture/assertion —
   compensation, benefits, EEO, recruiting-instructions, company-marketing,
   location-logistics-as-information, internal-posting-instructions, and
   the posting's-own-title-line match — all bypass with a recorded reason.
   A required-section-header line ("What You Bring: Talent Ops to delete
   as necessary...") must still classify `NON_QUALIFICATION` (affirmative
   category match, not header-protected) — name this exact line. An
   explicit Requirements-headed capability line, and a Responsibilities-
   headed line implying a real capability, both **pause** (assert only the
   binary bypass-vs-pause outcome, never `QUALIFICATION_LIKELY` vs.
   `AMBIGUOUS` as pass/fail — that split is receipt annotation only, per
   the binary-behavior change above). A mixed queue (one non-qual + one
   anything-else) pauses; an all-non-qualification queue proceeds. The two
   `jd_05` trap lines pause (test 9 below).
9. Regression, `jd_05`-shaped: "must pass a background check" /
   "nights and weekends availability required" must classify
   `QUALIFICATION_LIKELY`, never `NON_QUALIFICATION`, even though both sit
   near privacy/schedule vocabulary.
10. NON_QUALIFICATION bypasses are visible in the Stage 0 receipt/
    diagnostic artifact with their reason code, per item.
11. Manual-judgment-correction regression: replay the actual
    `required:0:bjiplgnonojgoadn` mis-classification incident from today
    against `stage0_judgment_corrections` + `correct_judgment(...)`,
    confirm zero direct SQLite access is needed, confirm the wrong
    judgment is preserved in the corrections table as history, and confirm
    `get_completed_judgment` now returns the corrected value with no
    changes to that function itself.
11a. The same correction leaves every *other* cached judgment under the
    same `run_key` untouched (blast-radius regression for the in-place
    update).
12. A correction against a stale `request_hash`/`content_hash`/
    `evidence_index_hash`, an unknown `item_key`, or a different
    `opportunity_key` is rejected.
13. A correction cannot itself set `fit_score`/`tier`/`decision`/workflow
    status (validation test, mirrors the existing "response can't set
    workflow fields" contract already proven for Epic 3's closed-world
    import).
13a. The generated correction-request artifact carries `item_key` +
    `bucket` + exact `item_text` + the current (wrong) judgment — a
    correction answered without inspecting any table.
14. `stage0_cascade_import.template.json` carries exact requirement text
    (+ bucket) per `item_id`; an import whose echoed text doesn't match
    the real item text is rejected, not silently accepted.
15. Repeated `--resume` before the extraction-review or the
    manual-correction is answered makes zero provider calls and does not
    fork receipts (same contract already proven for `cost_authorization`).

## Isolation for the rerun

Continue on `cr112-integrated-validation-candidate`, local commit only (not
pushed, not merged to `main`). Use `APPLYR_STAGE0_REVIEW_DB` (already an
existing override point, `build_stage0_fit_gate.py:2462-2468`) explicitly
set to a fresh temp path for the Camunda rerun, rather than relying on the
worktree's incidental separate `jobagent.sqlite`. Copied real evidence
stays gitignored/local, out of the diff and out of any commit. No paid API
call, no production DB write, no live-submission edit, no push/merge.

## Review history

- **v1 → ACCEPT WITH CHANGES.** Found both dump sites, the partial-mapping
  loss path, the `compute_fit_score` additive-vs-weighted-average error,
  PINs 1-4, and that the literal invariant pauses 6/6 measured JDs (which
  Jason then used to revise the gate himself, in front of implementation).
- **v2 → ACCEPT WITH CHANGES.** Independently re-derived all 52 queued
  bullets from the real fixture files (not from my transcript) and
  confirmed the safety direction: zero qualification-shaped bullets in
  `NON_QUALIFICATION`, including both deliberate `jd_05` traps. Found 4
  transcript errors (fixed above) and — the blocking finding — that v2's
  correction mechanism violated `stage0_judgments`'s real `UNIQUE`
  constraint (fixed above by adopting the existing
  `020_add_review_answer_history.sql` append-only pattern instead).
  Recommended (adopted): make the gate binary in behavior, and add a
  title-line bypass category.

All required and recommended changes from both reviews are folded into
this v3. Next: hand to an implementation agent, then a fresh QA reviewer
(not either design reviewer), then Claude re-verifies before the Camunda
practice folder is rerun clean.
