---
status: implemented
created: 2026-09-13
from: Cursor (Grok 4.6)
candidate: codex/cr112-consolidation
originating_candidate: cr112-integrated-validation-candidate
historical_head: baec191
design_review: 0562aa4a-a797-4c15-8663-02c2f2819fb7
verdict: ACCEPT WITH CHANGES
implement_this_pass: yes
do_not: add a metric-size boost, hard-code SAVINGS exclusion, weaken controls
---

# CR-112 ranking investigation — why SAVINGS beat RabbitMQ/Kafka on Camunda

Historical design recommendation and regression corpus for the Camunda
defect. The bounded Story 8.8 correction landed on
`codex/cr112-consolidation` on 2026-09-15 after the characterization and
controls were in place.

## Question

Why did `ACC-101-SAVINGS` (score 8330, picked) outrank
`ACC-215-RABBITMQ` (4860, `top2_cutoff`) and `ACC-189-KAFKA` (3766,
`top2_cutoff`) for Camunda's required item:

> Strong understanding of distributed systems concepts, including
> scalability, fault tolerance, event-driven architecture, and
> performance optimization.

## Formula (historical characterized behavior)

`scripts/build_authoring_packet.py` `_score_claims_for_item`:

```
total = capability_boost + int(round(overlap * 1000)) + jd_score
if overlap == 0 and capability_boost == 0:
    total = 0
```

- `capability_boost` fires only for compliance/privacy tokens or
  AI/ML tokens. This Camunda item has neither. Boost = 0 for all
  three claims.
- `overlap` is rarity-weighted distinctive token overlap between the
  **item text** and **claim scoring text** (not a dedicated
  distributed-systems capability).
- `jd_score` is `score_claim_for_jd` against the **full JD**, used as
  a tiebreaker in comments but added at full weight in the sum.

The Camunda trace (`data/authored_drafts/camunda_cr112_proof/evidence_selection_trace.json`)
picked `ACC-101-SAVINGS` + `ACC-111-SCOPE`. RabbitMQ and Kafka never
entered Top-2.

## What the dimensions actually did

| Claim | Tags (tags-only index) | Metrics | Score | Role |
|---|---|---|---|---|
| ACC-101-SAVINGS | Cost Reduction, Infrastructure, Storage Optimization, Legacy Systems | 2,000,000 | 8330 | picked |
| ACC-111-SCOPE | Multi-Platform Ownership, Legacy Systems, Platform Architecture, Roadmap, Java, Content Ingestion | none | 7936 | picked |
| ACC-215-RABBITMQ | RabbitMQ, Message Queues, Distributed Messaging, News Monitoring | none | 4860 | top2_cutoff |
| ACC-189-KAFKA | Kafka, Product Architecture, Data Pipeline, ETL, Architecture Planning | none | 3766 | top2_cutoff |

Item tokens that should have been decisive: distributed, scalability,
fault, event-driven, architecture, performance, optimization.

SAVINGS can still match `systems` (from Legacy Systems) and
`optimization` (from Storage Optimization) without naming Kafka,
RabbitMQ, messaging, or event-driven architecture. RabbitMQ matches
`distributed` via Distributed Messaging. Kafka matches `architecture`.
Those distinctive technical matches lost to a higher combined
overlap-plus-full-JD score on a metric-bearing infrastructure claim.

This is not a generic "metrics always win" term in the formula.
There is no explicit metric-size coefficient. The overweight comes
from:

1. Full-JD `jd_score` added at full weight, so a $2M storage-savings
   claim that is broadly relevant to a long SaaS/platform JD can
   outrun an item-specific messaging claim.
2. Overlap treating `systems` / `optimization` as enough distinctive
   contact with a distributed-systems requirement.
3. No requirement-semantics axis that says Kafka/RabbitMQ/event-driven
   are closer to this item than cost-reduction.

`ACC-111-SCOPE` winning the second slot is more defensible (Java,
platform architecture, ingestion). The defect is SAVINGS in slot one.

## Negative controls (must not become "always pick SAVINGS")

Pearl and SupplyHouse `ACC-101-SAVINGS` extras are REPLACE-control
cases from CR-112 closed-world work, not proof that SAVINGS is the
right pick whenever it scores high.

- If a JD item is not about cost, infrastructure savings, or storage
  optimization, SAVINGS must not displace a better-attributed
  item-specific claim.
- Metric size alone is already forbidden as REPLACE in `FR-313` /
  `AC-410`. Ranking into Top-2 is a different gate and currently
  weaker than that comparator.

Do not "fix" Camunda by hard-coding "never SAVINGS." That would
break honest cost-reduction items.

## Positive controls (metrics should win)

1. A required item about infrastructure cost, storage spend, or
   vendor savings should pick `ACC-101-SAVINGS` over a no-metric
   architecture claim.
2. A required item about protecting a large ARR platform / reliability
   at scale should pick the $40M / 3,500-user class evidence
   (`ACC-101-PM` or the mapped platform-stabilization claim) over a
   metric-empty process claim.

Those two are the opposite of Camunda's distributed-systems line.

## Intended general rule

Select evidence that jointly maximizes:

- direct JD-item semantics (distinctive requirement tokens, not
  full-JD vibe)
- evidence strength (including real metrics when the item is about
  an outcome those metrics measure)
- attribution safety
- distinctiveness
- domain-truth safety
- document capacity

Technical evidence does not always beat metrics. Metrics do not
always beat technical evidence. The Camunda miss is **direct
requirement semantics losing to full-JD score plus weak overlap**.

## Design recommendation

Do not ship a formula change on this evidence alone. Next change,
if accepted after review:

1. Keep `capability_boost` scoped (compliance / AI). Do not add a
   metric-size boost.
2. Either drop `jd_score` from Top-2 nomination or cap it so it
   cannot overcome zero/weak item overlap on a technical-requirement
   item.
3. Treat named technologies in the item (Kafka, RabbitMQ,
   event-driven, distributed messaging) as distinctive overlap that
   must beat generic `systems` / `optimization` contact.
4. Keep Story 3.5 REPLACE comparator as a second line of defense.
   Ranking Top-2 and REPLACE are complementary, not substitutes.

## Regression corpus (fixtures only, later story)

| Case | JD item class | Expected Top-2 | Must not win |
|---|---|---|---|
| Camunda distributed-systems | technical requirement | RabbitMQ and/or Kafka/messaging | ACC-101-SAVINGS in slot 1 |
| Pearl SAVINGS extra | closed-world REPLACE control | keep selected PM/ops evidence | automatic SAVINGS REPLACE |
| SupplyHouse SAVINGS extra | same | keep authorized selection | automatic SAVINGS REPLACE |
| Cost-reduction required | metric should win | ACC-101-SAVINGS | empty-metric architecture claim |
| ARR/reliability required | metric should win | platform-stabilization / ARR claim | process-only claim with no outcome |

No code in the investigation story. Executable characterization now lives in
`scripts/test_cr112_ranking_characterization.py` (`FR-321` / `AC-419`).
Camunda historical packet stays as the positive defect candidate. The
test reports `known_defect` when SAVINGS still wins slot 1; it does not
assert that rank as desired.

## Independent design review (2026-09-13)

**Reviewer:** [Review](0562aa4a-a797-4c15-8663-02c2f2819fb7)
**Verdict: ACCEPT WITH CHANGES. Do not implement this pass.**

Root cause stands. Capping or dropping `jd_score` is necessary but not
proven sufficient: even at `jd_score = 0`, SAVINGS can still hold two
overlap tokens (`systems`, `optimization`) against one each for
RabbitMQ/Kafka. Pearl/SupplyHouse rows test the REPLACE comparator, not
`_score_claims_for_item`. Cost-reduction and ARR rows have no executable
fixtures. Near-tie has no mechanical delta.

Before a formula story: prove Camunda flips under the live rarity
weights; encode cost-reduction and ARR as asserts against
`_score_claims_for_item`; keep REPLACE rows labeled as a different gate.

## Implementation record (2026-09-15)

Implemented as Story 8.8 (`FR-323` / `AC-421`) in
`scripts/build_authoring_packet.py`:

- adds a bounded item-specific technical-semantics boost when a requirement
  is about distributed or event-driven architecture;
- does not add a metric-size boost or ban `ACC-101-SAVINGS`;
- preserves cost-reduction and ARR/reliability metric-positive controls;
- preserves Pearl and SupplyHouse REPLACE controls as a separate gate.

Verification:

- `python -m unittest scripts.test_cr112_ranking_characterization` passes.
- The 2026-09-15 combined offline maintenance suite passed 167 tests,
  including this module.
- No model, provider, or API call is made by the ranker or these tests.

