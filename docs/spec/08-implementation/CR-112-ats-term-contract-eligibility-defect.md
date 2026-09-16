---
status: design_v1_pending_review
created: 2026-09-13
from: Claude (product-proof run, Camunda correction cycle)
candidate: cr112-integrated-validation-candidate @ 470abdf (worktree, local commit)
related: CR-112, docs/spec/08-implementation/CR-112-stage0-extraction-fallback-defect.md
budget_note: written under an explicit Claude usage-conservation directive (2026-09-12) —
  kept intentionally tight, not the exhaustive style of the sibling CR-112 doc.
---

# ATS-term-contract claim-eligibility defect

Bounded defect story, discovered while correcting the Camunda first-draft submission
(separate from, and downstream of, CR-112's Stage 0 extraction fix — that fix is
proven working; this is a different module).

## Root cause (confirmed by direct code trace, not assumed)

`scripts/jd_term_extractor.py::build_packet_ats_term_contract` has **two** term-discovery
paths:

1. **Main loop** (lines 224-242): a term enters the contract only if it appears in a
   JD's raw text AND in a specific `evidence_map` row's `jd_item` text, in which case
   **every** `claim_ids` on that row is added — this path is fine, it already keeps all
   siblings.
2. **Fallback loop** (lines 246-260, comment: "Stage 0 may omit a JD line even though the
   packet builder pulled a verified skill-anchor excerpt for it"): iterates every claim
   already loaded into the packet (`excerpt_claim_ids = set(excerpts)`, i.e. **every**
   claim in the packet, not just evidence_map-mapped ones) and adds `claim_id` to the
   term's `claim_ids` whenever the term string matches one of that **claim's own tags**
   (`master_claims_tags_only.json`). This path has **no relationship to `evidence_map`
   at all** — it never checks `jd_items`, never checks sibling claims for the same JD
   item, and critically **never checks eligibility** (`allowed_claims`, `prohibited_claims`,
   `disabled`, attribution). The function's signature doesn't even receive `disabled` or
   `claim_constraints`, so it structurally cannot check eligibility today.

**Confirmed exact mechanism for the Camunda case:** `ACC-185-CUSTOMER-DISCOVERY` carries
tag `"Support Signals"` in `master_claims_tags_only.json`. The word "Support" appears in
the raw Camunda JD only inside benefits boilerplate ("perks that support you...",
"co-working space support") — not in any requirement/preferred/responsibility line. The
fallback loop matched "Support" (term) against "Support Signals" (tag) and added
`ACC-185-CUSTOMER-DISCOVERY` to the contract. That claim's `claim_constraints` entry has
`"allowed_claims": []` and three `prohibited_claims` blocking any real customer-discovery
narrative — there is no honest sentence that satisfies it. `ACC-113-ADOPTION` (real,
usable, already cited elsewhere in the draft) was **never a candidate** for this specific
term — its own tags (`Cross-Platform, Google Analytics, Internal Adoption, Stakeholder
Alignment`) don't contain "support." My first hypothesis (two claims map to the same
`evidence_map` row, only the first survived) was **wrong** — investigated and ruled out
by direct trace; recording that here so the next reader doesn't re-walk the same wrong
path.

**Corpus scan** (`data/submissions`, `data/archive/submissions`, `data/pending_review`,
`data/authored_drafts` — only one packet exists in this worktree, the Camunda practice
one; the worktree does not carry the full production corpus): 4 of 11 `ats_term_contract`
entries in the Camunda packet have **zero** eligible claim (`allowed_claims` empty on
every listed claim_id) — Epics, Product Strategy, Reliability, Support. Product Strategy
happened to still pass Stage 1 verify because its *second* listed claim
(`ACC-181-PRODUCT-FIT`) has attribution `OBSERVED`, not `""`/empty, and got cited
elsewhere — worth noting as a near-miss, not a fix target itself. This scan is **not**
representative of the full corpus; the invariant fix should hold universally, not just
for these four terms.

## Required invariant (Jason's language)

> An ATS-term contract cannot require evidence through a claim that the author is
> prohibited from using. When an item has multiple mapped claims, contract construction
> must retain or select eligible evidence deterministically. If no eligible claim exists,
> the system must represent a genuine unsupported term or gap rather than demand an
> impossible citation.

## Answers to the 10 investigation questions

1. **Where ATS terms are selected:** `_load_true_vocabulary()` — skills_catalog.json's
   flat tool list + master_claims_tags_only.json's tags, minus a small hand-maintained
   generic-soft-skill exclusion set.
2. **Where each term is associated with JD items:** only in the main loop (path 1 above),
   via literal-text match against `evidence_map[i]["jd_item"]`.
3. **Where JD items are associated with claim IDs:** `evidence_map` itself (built earlier
   in `build_authoring_packet.py` by `build_evidence_map`) — already carries every mapped
   `claim_ids` per JD item; the main loop already preserves all of them correctly.
4. **Why only the first mapped claim survives:** it doesn't, for the main loop — that
   loop already keeps every sibling. The actual defect is in the *fallback* loop, which
   was never claim-sibling-aware to begin with because it isn't keyed by JD item at all,
   only by individual claim tag.
5. **How allowed_claims/prohibited/disabled/attribution/WE spans/sibling lenses affect
   eligibility:** today, **not at all**, in either loop. The main loop takes `claim_ids`
   verbatim off the evidence_map row (which Stage 0/`build_evidence_map` already vetted
   for prohibition/attribution *when selecting which claims map to that JD item* — so
   the main loop's claims are usually eligible by construction, inherited eligibility,
   not enforced here). The fallback loop has no such inheritance — it's tag-string
   matching against every packet claim regardless of usability.
6. **What the contract intends to store:** per its own field name `claim_ids` (plural)
   and the main loop's behavior, the design intent is clearly "a set of acceptable
   alternative claims," not one required claim and not a pre-selected best claim. The
   fallback loop breaks this intent by effectively contributing a single, unvetted claim.
7. **How `run_verify_only` interprets the contract:** `author_from_packet.py
   ::_check_packet_ats_term_contract` (unchanged by this story) requires the resume's
   *literal term* present, AND at least one *cited* resume claim_id to match/prefix-match
   *some* `claim_ids` entry for that term. It has no visibility into eligibility — it
   trusts the packet's `claim_ids` list is already all-eligible. That trust is what this
   story restores.
8. **Whether similar impossible contracts exist elsewhere:** see corpus scan above — 4/11
   in the one packet available in this worktree; not a full-corpus claim.
9. **Whether "Support" should have entered the contract at all:** **No, not as a bare
   token in this instance** — its only literal JD occurrence is generic benefits
   boilerplate, unrelated to the "Support Signals" tag's actual meaning (customer support
   signal-gathering). This is a second, independent problem from the eligibility gap:
   even a fully-eligible claim shouldn't have been forced to answer for a JD occurrence
   that isn't a real requirement signal. See "Generic-term handling" below — the fix
   for this piece is narrower than eligibility filtering and must not special-case the
   word "Support" itself.
10. **Term presence vs. factual support vs. both:** both, and they are two separate
    checks in `_check_packet_ats_term_contract` today (`missing` vs. `unsupported`) —
    already the right shape. This story only touches how eligible `claim_ids` are
    computed at packet-build time, not that downstream two-part check.

## Design: explicit alternatives + eligibility, not silent first-claim selection

Per Jason's schema, extend each `ats_term_contract` entry (packet-facing, kept small) to:

```json
{
  "term": "Support",
  "jd_item": "<source evidence_map jd_item text, or null for a tag-only fallback match>",
  "item_id": "<stable hash of jd_item text + bucket, or null>",
  "eligible_claim_ids": ["ACC-113-ADOPTION"],
  "ineligible_claim_ids": [
    {"claim_id": "ACC-185-CUSTOMER-DISCOVERY", "reason": "no_allowed_claims"}
  ],
  "status": "SUPPORTED",
  "selection_reason": "eligible_claim_present"
}
```

`status` ∈ `SUPPORTED` (≥1 eligible claim) / `UNSUPPORTED` (≥1 mapped claim, none
eligible) / `AMBIGUOUS` (reserved — not producible by today's deterministic filter, kept
for a future path that needs human/LLM disambiguation) / `NOT_ACTIONABLE` (term entered
via a fallback tag match with no real JD-item anchor — see generic-term section).

**Eligibility filter** (applied to every candidate claim_id in both loops, before it is
added to `claim_ids`/`eligible_claim_ids`):
- present in `excerpts` (packet evidence) — already implicit, keep it explicit
- not in `disabled`
- `claim_constraints[claim_id]` exists and has a **non-empty `allowed_claims` list**, OR
  (if `allowed_claims` is empty) the claim has **no `prohibited_claims` either** — an
  empty `allowed_claims` alongside a non-empty `prohibited_claims` is the exact signature
  of "flagged but unusable," and is the disqualifying condition. An empty/empty card
  (no allowed, no prohibited — i.e. attribution `""`, unconstrained) stays eligible.
- attribution present and not itself a disallowed tier for the calling context (out of
  scope to fully design here — no case in this packet needs it; note as a follow-up, not
  a blocker)
- claim_id must be the **exact** claim, never a sibling/prefix match standing in for it
  (test 9 below exists specifically to pin this)

`run_verify_only`'s `_check_packet_ats_term_contract` changes minimally: read
`eligible_claim_ids` (falling back to legacy `claim_ids` if a packet predates this
schema, so old frozen packets don't break) instead of `claim_ids` directly, and treat a
`status: "UNSUPPORTED"` or `"NOT_ACTIONABLE"` term as **not a hard block** — it is
recorded (WARN-tier, same posture `check_ground_truth_coverage.py` already uses) rather
than demanding a citation that cannot exist. A `SUPPORTED` term with zero actual citation
still fails exactly as it does today (negative control, test 20).

## Generic-term handling (independent finding, do not special-case "Support")

The fallback loop's real defect is broader than eligibility: it manufactures a
requirement from a claim *tag* string match with **no verification that the term's
actual JD occurrence has anything to do with that tag's meaning** — "Support" matched
because it is a substring of "Support Signals," not because the JD used the word to
describe a requirement. Recommended, minimal, non-special-cased fix: the fallback loop
should require the matched vocabulary term to appear in the JD **near** (same sentence,
or within N tokens of) requirement/responsibility-signal context — reuse the existing
`_looks_like_qualification`/section-header signal the codebase already has elsewhere,
**not** a new heuristic invented for this story — or, more simply and more in the spirit
of "smallest change consistent with current architecture": require the fallback match to
land inside a JD line that Stage 0 actually bucketed as required/preferred/responsibility
(i.e. cross-reference against `stage0_fit_gate.json`'s buckets, which this packet-build
step already has access to via `stage0`), not just "appears anywhere in the raw JD text."
A term whose only JD occurrence is in culture/benefits/compensation text should not enter
`ats_term_contract` via the fallback path at all — mark it `NOT_ACTIONABLE` and drop it
from the author-facing contract entirely (it was never actionable, not merely
under-evidenced). This is the design reviewer's call to confirm or refine, not implement
without review — flagging both directions (filter at the term-vocabulary level via
generic-soft-skill-style exclusion vs. filter at the JD-occurrence-context level) for the
reviewer to pick between, since only one avoids being Camunda/"Support"-specific.

## Scope / do-not-fix-by

Do not touch: `_check_packet_ats_term_contract`'s core two-part logic (present-in-resume
+ cited-claim-matches), `_load_true_vocabulary`, `_term_present`/`_term_present_stemmed`,
CR-112's own Stage 0 gate (separate module, already proven fixed and committed), the
practice-identity/John Doe finding (tracked separately, does not block this story),
Camunda's already-corrected Resume.md/CoverLetter.md content (this story only changes
packet construction + verify's eligibility read, not the authored documents).

## Test plan (trimmed to the required-tests list; each maps 1:1 to Jason's numbered list)

1. First mapped claim prohibited (empty allowed_claims + nonempty prohibited), second
   eligible → contract carries only the second as eligible, first as ineligible with
   reason `no_allowed_claims`.
2. First disabled, second eligible → same shape, reason `disabled`.
3. First has no excerpt in packet, second eligible → reason `no_excerpt`.
4. First has unusable constraints (present but empty allowed + nonempty prohibited),
   second eligible → reason `no_allowed_claims`.
5. Multiple eligible claims remain — `eligible_claim_ids` keeps all of them, not just one.
6. All mapped claims prohibited → `status: UNSUPPORTED`, `eligible_claim_ids: []`.
7. All mapped claims disabled → same, reason `disabled` for all.
8. No mapped claims at all → term never enters the contract (unchanged existing
   behavior — confirm, don't regress).
9. A sibling/prefix-matching claim_id (e.g. `ACC-185-X` vs `ACC-185-CUSTOMER-DISCOVERY`)
   cannot satisfy eligibility for a term mapped to the other — exact claim_id only.
10. A claim mapped to a *different* JD item cannot satisfy a term tied to this one.
11. An attribution-incompatible claim cannot satisfy it (design reviewer defines the
    concrete fixture — no such case exists in the Camunda packet itself).
12. Deterministic ordering: same inputs twice → identical `eligible_claim_ids` order.
13. Reordering `evidence_map` rows doesn't change which claims are eligible.
14. An eligible alternative can be cited in `claim_provenance.json` and
    `_check_packet_ats_term_contract` passes.
15. An ineligible claim cited alone does not pass merely because it's listed first.
16. `status: UNSUPPORTED` does not become a hard FAIL in `run_verify_only` (WARN-tier,
    same posture as `check_ground_truth_coverage.py`).
17. An existing genuinely-supported term (e.g. "Agile" in the real Camunda packet, which
    has real eligible claims already used) keeps passing — no regression.
18. A small sanitized synthetic fixture (not the real Camunda JD/candidate text)
    reproduces the exact original failure shape: one claim tag-matched via the fallback
    path, empty allowed_claims, nonempty prohibited_claims, term present only in
    non-requirement JD text.
19. Corpus scan (this worktree's available packets only, documented as such — not a
    full-production-corpus claim) — count of impossible contracts before vs. after.
20. Negative control: a genuinely `SUPPORTED` term with an eligible claim that is
    deliberately **not** cited anywhere still fails `_check_packet_ats_term_contract`
    (proves the fix didn't accidentally loosen the citation requirement itself).

## Next step

Send to one fresh design reviewer for: (a) confirm the root cause trace above is correct
by independently re-reading `jd_term_extractor.py` and the Camunda packet, (b) pick a
direction on the generic-term-handling open question, (c) sanity-check the
`eligible_claim_ids`/`status` schema against `run_verify_only`'s real call sites. One
implementation pass, one fresh QA pass, then resume the parked Camunda workflow via the
canonical runner (packet rebuild triggers the natural hash-invalidation path — no
hand-editing of `authoring_packet.json`, `workflow_state.json`, or any receipt).
