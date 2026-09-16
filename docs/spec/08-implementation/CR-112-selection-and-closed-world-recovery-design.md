---
status: design_accepted_story31_qa_pass
created: 2026-09-11
revised: 2026-09-11 after Story 3.0 REVISE
accepted: 2026-09-11 independent review 2 ACCEPT
from: Cursor (Grok 4.6)
related: CR-112 Epic 3 Stories 3.1/3.2/3.3, FR-254, FR-302 (superseded), FR-312–FR-317, NFR-015
investigation: ./INVESTIGATION-2026-09-10-stage0-3-reliability-quality-tokens.md
evidence_date: 2026-09-10 seven-folder closed-world scan
implementation: Story 3.0 QA PASS. Story 3.1 detection QA PASS. Story 3.5 QA PASS. Story 3.6 QA PASS. Epic 3 integration PASS. Stories 7.1/7.2 QA PASS. No live-folder rewrite.
---

# CR-112 design — selection defects vs closed-world authoring defects

This is a behavior design. It is not an implementation plan and it is not
authorization to edit live submissions or call paid models.

**Done for this document means:** two defect classes are separated, a
deterministic comparator is specified, recovery actions are specified, the
seven-folder 2026-09-10 evidence has expected outcomes, and the model-cost
policy is stated as requirements. Code does not start until an independent
reviewer issues ACCEPT against this file.

**Review log:** 2026-09-11 first independent review
(`21fd8c64-6c03-4c55-9fc3-4a7a2a974dbb`) **REVISE**. Same reviewer
second pass **ACCEPT**. Sibling-lens distinctiveness lock and duplicate
decision-rule paragraph corrected after ACCEPT notes. Checkbox for
Story 3.0 QA PASS after ACCEPT. Stories 3.1, 3.5, and 3.6 have independent
QA PASS. 7.x waits on the Epic 3 integration review. Do not rewrite the
seven live folders.

**Not done means:** extra-packet still silently WARNs, a larger metric is
treated as a better fact, or unknown cost is recorded as zero.

## Problem

Story 3.1 currently detects a provenance ID that is not in the packet and
emits WARN. Stage 1 can still pass. Finalize is not blocked. That collapses
two different failures into one signal:

1. The packet omitted a grounded fact that should have been selected.
2. The author cited a fact the packet never authorized.

The 2026-09-10 scan found extra IDs in 4 of 7 live folders. Investigation
F6 showed those extras are not automatically the better bullet. Pearl's
`ACC-101-SAVINGS` lost Top-2 by one score point and is CONTRIBUTED. Citing
it anyway is an authoring leak, not proof the packet ranked wrong.

## Product decisions already made (Jason, 2026-09-11)

- Separate the two defect classes. Do not treat extra-packet as a binary
  WARN-versus-hard-stop.
- Pre-authoring: if an omitted eligible fact clearly dominates the weakest
  selected fact, replace before authoring and record the decision in
  `evidence_selection_trace.json`. Do not put the full ranking trace in the
  author prompt. If dominance is ambiguous, keep the current selection and
  surface a review decision.
- After authoring: do not silently WARN and finalize. Treat extra-packet as
  a recoverable completion block with remove / rewrite / explicit packet
  widen / human-only-when-unsafe.
- An extra-packet fact is not automatically a better fact. Detection and
  comparative selection are separate operations. Do not infer strength
  because the author used it.
- Deterministic/offline is the default. Free-tier APIs require a hard
  zero-dollar policy. Paid APIs are opt-in with a user-configured provider
  and budget. Never silently fall back from free to paid. Unknown cost
  eligibility fails closed. No authorized API pauses cleanly onto the
  existing manual-paste path. Unknown cost is not recorded as zero.

## Non-claims

- This design does not claim Applyr is product-ready.
- This design does not authorize rewriting the seven live folders.
- This design does not change Story 3.4 admin-line skip, Story 5.1 advisory
  gerund, or Story 2.2 batch.js never-default.
- This design does not auto-insert a larger metric.
- `APPLYR_CR112_PAID_BUDGET` still does not buy a paid eval run on accepted
  6.1.

## Closed-world contract that must survive

Stage 1 authors from packet WE spans plus `claim_constraints`. Allowed
claim IDs are the exact set in excerpts ∪ evidence_map.claim_ids ∪
soft_gaps.claim_ids. Project-prefix match (`ACC-101-SAVINGS` vs
`ACC-101-PM`) does not authorize a lens. When Stage 0 and Stage 1 disagree,
WE wins. Disabled and prohibited claims stay ineligible.

FR-254 remains: the author may not invent claims outside packet IDs. This
design enforces that after the draft exists. The packet may change before
a *new* authoring pass when comparative selection proves a stronger
eligible fact was omitted. Widening never stamps provenance onto the
leaked draft. The leaked draft is invalid until a new author pass from
the new packet.

---

## 1. Two operations, two times

| Operation | When | Input | Output | May change packet? | May change draft? |
|---|---|---|---|---|---|
| Detection | After provenance exists | packet + `claim_provenance.json` | extra ID list | No | No |
| Comparative selection | Packet build, and again during extra-ID recovery | omitted/extra candidate vs weakest selected | `REPLACE` / `KEEP` / `AMBIGUOUS` / `INELIGIBLE` | Only on `REPLACE` | No. Recovery may require a later rewrite |
| Recovery | After detection, before Stage 1 can complete | extra ID + comparator result + WE/constraints | `REMOVE_EXTRA` / `REWRITE_UNSUPPORTED` / `WIDEN_PACKET` / `HUMAN_COMPARE` | Only `WIDEN_PACKET`, and only same-item TRACE omitted + REPLACE | Yes: remove/rewrite in place, or invalidate draft and require a new author pass. Detector never edits |

`packet_closed_world.extra_packet_findings` stays a detector. It must not
score, rank, or recommend. Severity becomes a completion block, not WARN.

---

## 2. Comparative selection (shared)

Used by Story 3.5 (pre-authoring) and Story 3.6 (post-author extra IDs).
Deterministic. No `call_llm`.

### Eligible candidate

A claim ID may enter comparison only if all of the following are true:

- Present in the live claims catalog and not `disabled`.
- Not prohibited / DO NOT CLAIM.
- Has a WE (or ACC-401) span the packet builder can excerpt.
- Score on the comparison item is `> 0`.
- The JD item is not an admin-skip line (Story 3.4 fingerprint /
  nights-and-weekends). Those items keep empty `claim_ids`.
- Not boilerplate-filtered preferred/responsibility noise.

An extra-packet cite that fails eligibility is `INELIGIBLE`, never
`REPLACE`.

### Comparison pair

- **Candidate A:** omitted scored claim (Class 1) or extra cited claim
  (Class 2).
- **Anchor B:** the weakest currently selected fact on the **same JD
  item**. Weakest means lowest packet score among that item's
  `claim_ids`. If the item has one pick, that pick is B.

Same-item only. Cross-item `REPLACE` is forbidden.

How A binds to an item:

- Class 1: the evidence_map / TRACE row under comparison.
- Class 2: the TRACE `omitted_reasons` / candidates row that lists A.
  If A appears on more than one item, compare per item and `REPLACE`
  only if every bound item would REPLACE. If A is **not** in TRACE
  omitted/candidates for any item, Class 2 cannot `REPLACE`. Recovery
  is `REMOVE_EXTRA` or `REWRITE_UNSUPPORTED`.

Do not fall through to "the globally weakest selected claim on a
required item." That path is how Pearl SAVINGS could beat a weak
unrelated required pick.

### Six axes

Each axis returns `A_better` / `tie` / `B_better` / `veto_A`.

1. **JD-priority relevance.** Use the existing item score from
   `_score_claims_for_item` (already in TRACE). `A_better` only if A's
   score exceeds B's by a **clear margin**: `A - B >= max(1, ceil(0.10 *
   max(B, 1)))`. Required-bucket A vs preferred/responsibility B may
   count as `A_better` inside the numeric margin **only in Class 1,
   same item**. It does not apply to Class 2. Same-item near-ties
   (Pearl SAVINGS 4164 vs PM 4165) are `tie`.
2. **Evidence strength.** Metric size alone cannot make `A_better`. A
   CONTRIBUTED rollup does not beat an OWNED scoped fact on this axis.
   `A_better` only when A is at least as specific as B and not a weaker
   attribution of the same story. Larger dollar figures are recorded,
   not treated as dominance.
3. **Attribution safety.** Case-fold catalog values. Rank when both
   sides are known: `OWNED` > `CONTRIBUTED` > `INFLUENCED` >
   `OBSERVED`. Missing / unknown on **either** side is `tie`, not a
   rank. Missing is not weaker than CONTRIBUTED. CONTRIBUTED cannot
   beat missing. Weaker known attribution is `veto_A`. Equal known is
   `tie`. Strictly stronger known is `A_better`.
4. **Distinctiveness.** Evaluate against the **packet** picked set and
   packet excerpts, never against the leaking draft. A sibling lens of
   an already-picked ID on the same `project_id` is `B_better` (cannot
   dominate). That sibling lock is not overridden if A also has a
   distinctive tag the JD names. Author use of A is not evidence A is
   distinctive. If A is **not** a sibling lens, supplies a distinctive
   tag the picked packet set lacks, and the JD names that tag,
   `A_better`.
5. **Domain-truth risk.** Gap-domain, exclusion-zone, title-overclaim,
   or assigning a product-roadmap claim to an eligibility line is
   `veto_A`. Transferable-bridge claims cannot dominate an honest owned
   match.
6. **Document capacity.** Same-item swap of one ID for another is
   capacity-ok. Adding a bullet, exceeding 5–6 Cision / 2–3 earlier-role
   caps, or forcing page 2 is `veto_A`. Class 1 is replace, not add.

### Decision rule

- Any `veto_A` → `KEEP` (Class 1) or not-stronger (Class 2).
- `REPLACE` only when there is no veto, JD-priority is `A_better`,
  evidence strength is not `B_better`, attribution is not `B_better`,
  distinctiveness is not `B_better`, and domain-truth is not `B_better`.
- Otherwise → `AMBIGUOUS`.

This is fail-closed on dominance. The packet's current Top-2 remains the
default. Clear dominance is a high bar on purpose.

### Recording

Write the decision on the TRACE row, not in `authoring_prompt.md`:

```
decision: REPLACE | KEEP | AMBIGUOUS | INELIGIBLE
candidate_id
anchor_id
axes: { jd_priority, evidence_strength, attribution_safety,
        distinctiveness, domain_truth_risk, document_capacity }
```

On Class 1 `REPLACE`, packet `omitted_reasons` for the displaced ID uses
`displaced_by_dominance` (FR-314). Story 3.2 ranking losers stay
`top2_cutoff` | `project_slot_cap` only (FR-303). Author prompt may
include that cheap code. It must not include scores, axes, or TRACE.

Story 3.3 stays read-only. Remaining `KEEP`/`AMBIGUOUS` omitted IDs can
still appear as `SWAP_CANDIDATE`. The swap report still must not rewrite
drafts or packets.

---

## 3. Class 1 — pre-authoring selection defect

**When:** inside `build_evidence_map` after the current Top-2 pass, before
excerpts and prompt are written.

**What:** for each evidence_map row, consider omitted eligible candidates
(`top2_cutoff` or `project_slot_cap` with score > 0). Compare the best
omitted eligible candidate to anchor B. On `REPLACE`, swap A in and B out,
adjust project slot counts, record TRACE. On `AMBIGUOUS` or `KEEP`, leave
picks unchanged and leave a TRACE review flag (`selection_review: true`
on AMBIGUOUS only).

`project_slot_cap` candidates may `REPLACE` only if swapping B frees a
slot for A's project or A is already under cap. Do not break the cap to
force a larger metric in.

**What this is not:** scanning the whole catalog for unused tags
(coverage ATTENTION). Only TRACE-scored omitted candidates.

**Positive control:** Pearl-like fixture. SAVINGS ranks third, score
within margin of PM, CONTRIBUTED vs stronger/equal PM/SCOPE. Result:
`KEEP` or `AMBIGUOUS`, never `REPLACE`. Packet still omits SAVINGS with
`top2_cutoff`. Prompt has no scores.

---

## 4. Class 2 — closed-world authoring defect

**When:** Stage 1 verify-only / `run_verify_only` after drafts and
provenance exist.

**Detection (Story 3.1 revised):** extra IDs are a recoverable completion
block. `run_verify_only` returns FAIL while any extra ID is unresolved.
`--resume` / finalize cannot complete. Agents must not dispose these as
`ACCEPTED_AS_CORRECT`, `FALSE_POSITIVE`, `NOT_APPLICABLE`, or
`HUMAN_ACCEPTED_RISK`. Prefix match still does not clear. This is not
`NEEDS_DISPOSITION`. Unresolved extras are Stage 1 FAIL until a named
recovery action completes.

**Recovery (Story 3.6), after detection, using the same comparator:**

| Case | Test | Action |
|---|---|---|
| Unsupported or prohibited | `INELIGIBLE`, disabled, no WE span, DNC | `REWRITE_UNSUPPORTED`: remove or rewrite the sentence. Rebuild provenance. Re-verify. Do not widen. |
| Grounded, not REPLACE | eligible and comparator is `KEEP`, including sibling-lens extras | `REMOVE_EXTRA`: drop the extra cite. Keep authorized evidence. If the sentence is only the extra fact, rewrite using authorized IDs. Rebuild provenance. Re-verify. Do not widen. |
| Grounded, ambiguous | eligible and comparator is `AMBIGUOUS` (not sibling/redundant `B_better`) | `QUALITATIVE_REVIEW`: pause with both candidates and comparison axes. Do not auto `REMOVE_EXTRA`. Not `NEEDS_DISPOSITION`. `--resume` after `human_decision` on `closed_world_recovery.json`. |
| Grounded and clearly stronger | comparator `REPLACE` **and** A is a TRACE omitted candidate on the same item | `WIDEN_PACKET`: rebuild the packet with A in and B displaced, record TRACE. **Invalidate the leaked draft.** Do not rebuild provenance onto the leaked sentences. Require a **new author pass** from the new packet (`WAITING_FOR_LLM` / paste). Then verify the new draft. |
| Extra not in TRACE omitted | eligible or not, no same-item TRACE row | `REMOVE_EXTRA` or `REWRITE_UNSUPPORTED`. Never `REPLACE` / `WIDEN_PACKET`. Author use is not a ranking signal. |
| Unsafe to resolve | unreadable packet, missing catalog, or WE/constraint conflict | `HUMAN_COMPARE` only. Not for `AMBIGUOUS`. Not for the seven-folder extras. |

Detection does not widen. `WIDEN_PACKET` does not launder FR-254: the
leaked draft is not the output.

Do not silently keep the extra cite because rubric floors already cleared.
The 2026-09-10 folders all had `verification_passed: true`. That is the
failure mode being closed.

---

## 5. Seven-folder expected outcomes (frozen 2026-09-10 evidence)

Use the investigation F5/F6 table and the Story 3.1 scan. Do not reopen,
rewrite, or re-scan live folders to "confirm" this design. Sanitized
fixtures in tests will clone the shapes.

| Slug | Extra ID | Class | Expected recovery | Why |
|---|---|---|---|---|
| arbiter | none | none | no block | Closed world held |
| cdw | none | none | no extra-packet block | CLOUDERAEXIT was in packet and used. Mapping smell is not Class 2. Class 1 must not auto-replace a 700-account retention bullet with $100K just because the metric is larger |
| loot_labs | ACC-108-SUPPORT | Class 2 | `REMOVE_EXTRA`. Never `WIDEN_PACKET`. Never `HUMAN_COMPARE` | Packet offered ACC-108-OPS. SUPPORT is a sibling lens (`B_better` distinctiveness). Author use of SUPPORT is not dominance. Remaining unused catalog miss was RETENTION |
| marlowe_companies_inc | ACC-103-SEC | Class 2 | `REMOVE_EXTRA`. Never `WIDEN_PACKET`. Never `HUMAN_COMPARE` | Fingerprint line stays empty after 3.4. SEC is not licensed by ROADMAP. ACC-103-PM never selected is a possible later Class 1 same-item question, not a Class 2 widen from author use of SEC |
| pearl_com | ACC-101-SAVINGS | Class 2 (also Class 1 omitted) | Class 1 `KEEP` or `AMBIGUOUS`, never `REPLACE`. Class 2 `REMOVE_EXTRA`, never widen | Same-item scores 4164 vs 4165 are `tie`. CONTRIBUTED cannot beat missing or OWNED. Packet stays `top2_cutoff`. Author citing it is the leak |
| supplyhouse | ACC-101-SAVINGS | Class 2 (also Class 1 omitted) | Class 1 never `REPLACE`. Class 2 `REMOVE_EXTRA`, never widen | Never Top-2 on infra items. Two ACC-101 slots used does not license REPLACE. Distinctiveness is packet-side, not the leaking $2M sentence |
| trax_technologies | none | none | no block | Closed world held |

SupplyHouse packet-integrity recovery stays closed. This design does not
rebuild that folder.

These outcomes are the acceptance oracle for the pre-implementation
reviewer. If the comparator would `REPLACE` Pearl or SupplyHouse SAVINGS,
the design is wrong.

---

## 6. Model-cost policy

Applies to every `call_llm` site and to the CR-108 Stage 0 cascade, not
only `run_cr112_eval.py`.

### Eligibility

Each provider name in config must have an explicit `cost_class`:

- `offline` — local / no billed network model call
- `manual_paste` — do not call; keep `authoring_prompt.md` paste
- `free_only` — adapter asserts the configured call cannot incur a charge.
  Provider name and advertised free tier are not enough. Groq/Gemini
  projects can bill.
- `paid_with_budget` — allowed only when the user has configured that
  provider, a remaining run/batch budget, and a known cost estimate
- `unknown` — default when class is missing or cannot be proven

`unknown` is not callable. Fail closed. Do not treat unknown as free.
Do not record unknown as `api_cents: 0`. When `cost_known` is false,
omit `api_cents` or store `null`. Groq and Gemini stay `unknown` until
an adapter can assert no charge under the current account configuration.
A user declaration without that assertion still classifies as unknown.

### Runtime rules

1. Deterministic/offline behavior is the default path (packet build,
   comparator, verify, lint).
2. Free-tier API may run only when `cost_class=free_only` and the adapter
   assertion holds.
3. Paid API requires opt-in provider allowlist plus budget plus a known
   estimate. Budget 0, unset, or unknown estimate → paid providers are
   not eligible. Stop before a call that could exceed remaining budget.
4. Provider fallback may move `free_only` → `free_only` or `offline`.
   It must not move `free_only` → `paid_with_budget`. Provider errors
   cannot silently change cost mode.
5. If no eligible provider remains, do not call. Pause. Leave
   `WAITING_FOR_LLM` / manual paste of `authoring_prompt.md` as the
   supported author path. Do not spawn review agents to bypass this.
6. Track per call: count, provider, estimated tokens, `cost_class`,
   `cost_known`, `api_cents` only when `cost_known` is true (known free
   may be 0), subscription minutes separately. Never sum those columns.
   Never report unknown as zero dollars.

Eval Story 6.1/6.2 stays zero-call. This policy does not wire `--paid-llm`
to `call_llm`. That remains a later story after budget + provider are
real.

CR-108's groq→gemini fallback is allowed only after both are `free_only`
with a zero-charge assertion. Until that exists, unknown fails closed
and Stage 0 extract pauses rather than guessing. Declaring a name "free"
still does not prove a billed Google/Groq project will not invoice.

---

## 7. Story and requirement mapping

Implementation is blocked until Story 3.0 ACCEPT.

| Story | Change | FR / AC |
|---|---|---|
| 3.0 | Pre-implementation review. First pass 2026-09-11: REVISE. Second pass required after this revision | gate, no code |
| 3.1 | REVISE: detection is a completion block; still detection-only; prefix does not clear | FR-312 / AC-409. FR-302 / AC-399 (WARN) superseded |
| 3.2 | KEEP enum `top2_cutoff` \| `project_slot_cap` only. TRACE holds scores. Prompt still has no scores | FR-303 / AC-400 Pearl KEEP |
| 3.3 | KEEP advisory, no rewrite | FR-304 |
| 3.4 | KEEP admin skip | FR-305 |
| 3.5 | NEW pre-authoring comparative replace; `displaced_by_dominance` is this story | FR-313, FR-314 / AC-410, AC-411 |
| 3.6 | NEW recovery: KEEP/sibling extra → REMOVE_EXTRA; true AMBIGUOUS → QUALITATIVE_REVIEW pause; WIDEN requires new author pass; HUMAN_COMPARE only unsafe | FR-315 / AC-412 |
| 7.1 | Cost eligibility registry, no free→paid fallback, pause to paste; groq/gemini unknown until a zero-charge assertion | FR-316 / AC-413 |
| 7.2 | Telemetry: unknown ≠ zero; `api_cents` null/omitted when `cost_known=false` | FR-317 / AC-414, NFR-015 |

### Out of scope for these stories

- Live seven-folder rewrite
- Auto-inserting larger metrics
- Gerund / style hard gates
- Portable Author/Review isolation (still a later CR)
- Wiring paid eval `call_llm`
- Agent auto-dispose of extra-packet findings
- Coverage ATTENTION as a selection oracle

---

## 8. Risks the reviewer must challenge

1. **Dominance bar too low** would auto-insert SAVINGS on Pearl and
   contradict F6. Same-item margin + missing-attribution-as-tie exists
   to prevent that. Cross-item REPLACE is deleted.
2. **Dominance bar too high** would make Class 1 a no-op and leave ranking
   defects as TRACE-only, which is today's 3.2/3.3 behavior. That is
   acceptable if the seven-folder set has no true REPLACE case. Class 1
   still has to be specified and tested with a synthetic REPLACE fixture
   that is *not* Pearl SAVINGS.
3. **Widening after draft** launders FR-254 if provenance is stamped onto
   the leaked sentences. WIDEN invalidates the draft and requires a new
   author pass.
4. **HUMAN_COMPARE overuse** would recreate WAITING_FOR_HUMAN. Class 2
   `AMBIGUOUS` pauses as `QUALITATIVE_REVIEW` with both candidates and
   axes, not auto-remove and not `NEEDS_DISPOSITION`. Sibling-lens extras
   stay `REMOVE_EXTRA`. HUMAN_COMPARE is only unreadable packet / missing
   catalog / WE-constraint conflict.
5. **Cost policy vs CR-108** can stall live Stage 0 if groq/gemini stay
   `unknown`. That stall is intended until Jason declares zero-dollar
   eligibility. It is not a reason to default them to free by name.
6. **`displaced_by_dominance` in the prompt** must stay a cheap code, or
   we recreate F3 packet bloat.

---

## 9. Pre-implementation review checklist

Independent reviewer (not the author of this file). Verdict: ACCEPT /
REVISE / REJECT.

Must use:

- this file
- `INVESTIGATION-2026-09-10-stage0-3-reliability-quality-tokens.md` F5/F6
- Story 3.1 scan table in the epics tracker
- FR-254 closed-world statement
- current `packet_closed_world.py` and `build_evidence_map` omitted_reasons
  contract

Must not:

- implement code
- open live `data/submissions/*` to rewrite
- treat 4/7 extras as proof they should have been selected
- mark stories complete

Required challenges:

- Would Pearl SAVINGS REPLACE (Class 1 or Class 2, including unmapped
  fallback)? If yes, REJECT.
- Would SupplyHouse SAVINGS REPLACE? If yes, REJECT.
- Are loot_labs SUPPORT and marlowe SEC locked to REMOVE_EXTRA?
- Is Class 2 KEEP/sibling `REMOVE_EXTRA`, true AMBIGUOUS a qualitative
  pause with both candidates, and HUMAN_COMPARE only for unreadable /
  missing catalog / WE-constraint conflict?
- Does WIDEN_PACKET require a new author pass and refuse to provenance-
  stamp the leaked draft?
- Is detection still separable from comparison?
- Does FAIL-closed extra-packet block finalize without a human wait on
  the four extras?
- Can groq→gemini still run while cost_class is unknown?
- Is `api_cents` omitted or null when `cost_known=false`?
- Does the author prompt still exclude TRACE scores?

Do not self-ACCEPT.
