---
status: plan_ready_no_paid_execution
created: 2026-09-11
from: Cursor (Grok 4.6)
related: CR-112, FR-310 / AC-407, FR-311 / AC-408
harness_branch: cr112-story61 @ 8346553
plan_branch: cr112-eval-plan (parent 8bbc497)
---

# CR-112 bounded Stage 0–3 evaluation plan

This plan uses the accepted offline eval harness. It does not run paid model
calls. It does not modify live submissions. Passing tests or rubric floors
still does not establish product readiness.

**Done means:** Jason can see what is measurable now, what is still a human
read, what requires a paid budget, what requires merging accepted local
branches, and what this work must not claim.

**Not done means:** an end-to-end Stage 0–3 run on one tree, a first-draft
quality score, or a product-ready verdict.

## How to run the offline harness

From the accepted Story 6.1/6.2 worktree only. Do not use dirty `main`.
Do not run `scripts/run_cr112_eval.py` from this `cr112-eval-plan`
worktree (it has no harness) or from the Applyr repo root (dirty main's
copy defaults assemble on and can call `build_packet`).

Absolute path:

```
cd C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Applyr\.claude\worktrees\cr112-story61
python scripts/run_cr112_eval.py --out <temp-or-gitignored-data/eval/cr112>
```

Confirm HEAD `8346553` before running (`git log -1 --oneline`).

Default behavior on `8346553`:

- `--assemble-packets` off. The flag is reserved. It does not import
  `build_authoring_packet` and does not write `authoring_packet.json`.
  Passing the flag anyway still records `assemble_packets: true` in
  `metrics.json` even though nothing was assembled. Treat that field as
  "flag requested," not "packets built."
- `--paid-llm` off. Without `APPLYR_CR112_PAID_BUDGET` the flag exits 2.
  With the env var set, the harness still does not import or call
  `call_llm`. Paid calls stay 0.
- Basename `jobagent.sqlite` is refused and the process exits. The
  accepted harness never opens SQLite. `--sqlite` only records the path
  after the basename check. A redirected eval DB is not used.
- Runtime output belongs under gitignored `data/eval/` or a temp dir.
  Fixtures stay in `tests/fixtures/cr112_eval/`.

Do not copy dirty-main mistakes:

- Dirty `run_cr112_eval.py` defaults assemble on and can call `build_packet`.
- Dirty gerund reporter measures end-of-bullet `ing`. Accepted 5.1 measures
  F7 (comma / `by` / `while` + `-ing`).

## Confirmed 2026-09-11 offline run

Tree: `cr112-story61` @ `8346553`.
Command: `python scripts/run_cr112_eval.py --out %TEMP%\cr112-eval-offline`.
Unit tests: `python -m unittest scripts.test_cr112_story61 -v` → 11/11 PASS.

| Total column | Value | Meaning |
|---|---:|---|
| `prompt_meta_estimated_tokens` | 742 | bytes÷4 of the five `Original_JD.txt` files, not a tokenizer count and not Stage 1 prompt-meta |
| `call_llm_invocations` | 0 | no `call_llm` |
| `harness_spawn_count` | 0 | no review/author spawn |
| `api_cents` | 0 | never summed with subscription minutes |
| `subscription_minutes` | 0 | never summed with API cents |
| `paid_calls` | 0 | even `--paid-llm` would still record 0 on this harness |
| `assemble_packets` | false | reserved flag unused |
| `sqlite` | null | production DB not opened |

Per-folder JD estimates (same method): northwind 163, contoso 148,
fabrikam 150, adventure 146, wideworld 135. Each folder wrote two
`eval` events (`start`, `complete`) to `observability/run_events.jsonl`.

These numbers match the Story 6.1/6.2 baseline. They measure fixture
materialization and column separation. They do not measure Stage 0
extract, packet ranking, first-draft quality, or Stage 2 review.

## Frozen 5-JD set

Fictional employers. No live employer folders. No candidate PII. Each
fixture is `Original_JD.txt` plus a stub `stage0_fit_gate.json`.

| Slug | Role framing | Why it is in the set |
|---|---|---|
| `jd_01_northwind_platform` | Platform PM, existing multi-tenant B2B | Healthy packet / positive-control candidate |
| `jd_02_contoso_data` | Technical PM, data-quality workflows | Data / DBA partner fit without warehouse overclaim |
| `jd_03_fabrikam_compliance` | Compliance-workflow PM | Legal/CX sequencing without people-management |
| `jd_04_adventure_ops` | IC ops-platform PM | Explicit not-founding / not-0-to-1 control |
| `jd_05_wideworld_admin` | Product PM plus admin hiring lines | Fingerprint + nights-and-weekends skip (Story 3.4) |

The frozen gates are labeled `decision: PASS` with no extract provenance.
They are eval inputs, not proof that live Stage 0 extract would emit the
same rows. Regenerating them through `call_llm` is a paid step, not this
plan's default.

Investigation §5's `omitted_missing_reason=0` row came from a dirty-main
assemble pass. That is a candidate observation. It is not an accepted
6.1 baseline. Accepted 6.1 never assembles packets.

---

## 1. What can be measured offline now

Run these on the named accepted branch. No merge required. No paid calls.
No live submission writes.

| Check | Tree | Command / artifact | What a green result means | What it does not mean |
|---|---|---|---|---|
| Sanitized eval harness | `cr112-story61` `8346553` | `python scripts/run_cr112_eval.py --out <temp>` | Fixtures copy, sqlite refuse, token/cost columns stay separate, spawn=0, events written | Stage 0–3 quality |
| Eval unit tests | same | `python -m unittest scripts.test_cr112_story61 -v` | Default assemble off, paid flag cannot call `call_llm`, five fictional slugs | Product readiness |
| Sequential-ID reject + constraint fail-closed + packet-integrity detector | `cr112-epic1` `9aab892` | cascade / packet / `audit_packet_integrity.py` tests | Invented `req-001` does not remap by position. Constraint wipe cannot ready a packet. Unreadable packets are incomplete inspection | Live Stage 0 extract is accurate |
| Lean spawn contract | `cr112-epic2` `ec9ee94` | `python -m unittest scripts.test_cr112_lean_spawn -v` | Skill/AGENTS text forbids WE reload and per-JD review spawn | Nobody will invoke batch.js |
| Closed-world extra-packet WARN | `cr112-epic3` `d2dc838` | `python -m unittest scripts.test_cr112_story31 -v` | Extra-packet cites WARN, exact match | Extra-packet should be a hard block |
| Omitted reasons + sibling trace | `cr112-story32` `287498b` | `python -m unittest scripts.test_cr112_story32 -v` | Packet enum is `top2_cutoff` \| `project_slot_cap`. TRACE holds scores / `score_zero` / `boilerplate_filtered`. Author prompt has no candidate scores | Live packets on main have this shape |
| Advisory swap report | `cr112-story33` `741f2db` | `python scripts/report_evidence_swaps.py` on a folder that already has `evidence_selection_trace.json` | `filter=boilerplate_filtered` → `INTENTIONAL_TRADEOFF`. CLI only. No draft rewrite | Ranking quality on a real JD |
| Admin-line skip | `cr112-story34` `b331035` (Story 3.4 commit `62a45e1`) | `python -m unittest scripts.test_cr112_story34 -v` | Eligibility-framed fingerprint / background-check and nights-and-weekends skip scoring. Years and product "background check roadmap" still score | Frozen `jd_05` gate was re-extracted live |
| Adversarial fail-closed | `cr112-epic4` `7b3ec9d` | `python scripts/run_adversarial_pressure_test.py` plus `scripts.test_cr112_adversarial` | Unknown fixture names fail. Named invariants must fire, not any `WorkflowError`. STATE-001–004 stay programmatic | A 5-JD eval folder would survive Stage 2 |
| F7 gerund reporter | `cr112-story51` `1144f80` | `python scripts/report_resume_gerund_rate.py` | Advisory CLI. Comma / `by` / `while` + `-ing`. No LW rule. No rewrite | Eval fixtures have no `Resume.md`, so this metric is empty there |
| Batch.js tracking | `cr112-story22` `4c993b1` | `python -m unittest scripts.test_cr112_story22 -v` | Force-added file is tracked. Review prompt forbids WE. Never default. Cap 3 | Portable Author/Review runtime exists |

Positive controls that stay offline:

- One healthy packet on the Epic 1 tree stays `ready` with `claim_constraints` intact.
- One invented `req-001` response does not map by position.
- One extra-packet ACC WARNs on the Epic 3 tree.

Investigation §5 rows that this harness can fill **now** (no assemble, no drafts):

| §5 metric | Offline now | Fill |
|---|---|---|
| Tokens (prompt-meta estimate) | Yes, JD bytes÷4 only | 742 |
| Cost columns | Yes | `api_cents=0`, `subscription_minutes=0`, not summed |
| Harness spawn | Yes | 0 |
| `call_llm` | Yes (absence) | 0 |
| Latency / `run_events.jsonl` | Yes, eval-stage only | 2 events/folder, assemble not run |
| Workflow recovery | Yes, on Epic 4, not on the 5-JD set | adversarial programmatic cases |
| Truth errors on eval drafts | No drafts exist | extra-packet count 0 by construction, not by review |
| Evidence-selection omission codes | Not on accepted 6.1 | needs packet assemble after merge |
| First-draft acceptance | No | `not_scored` |
| Human edit effort | No | not instrumented |

## 2. What still needs a qualitative read

These cannot be claimed from `run_cr112_eval.py`, unit tests, rubric
floors, or mechanical Stage 2.

| Question | Who | Why the harness cannot answer it |
|---|---|---|
| First-draft acceptance: send / one-pass / rework | Jason, on a frozen 5-JD set after real Stage 1 authoring | Eval folders have no `Resume.md` / `CoverLetter.md`. `first_draft_acceptance` is `not_scored` |
| Hiring-manager read (truth, relevance, writing) | The Stage 2 qualitative pass in generate-submission / AGENTS | `hm.critical_read` is a WARN placeholder. `--resume` is mechanical. F8 still applies |
| Extra-packet WARN vs hard-block | Jason only, as a product decision | Historical 2026-09-10 live mix (4 folders). Not a work list. Do not open, rewrite, or re-scan those folders for this plan. That mix is not this eval set |
| Whether a draft actually used the strongest honest evidence | Human, with packet + WE spans | Coverage ATTENTION flags are heuristics. Provenance WARN is not a substitute for reading |
| Human edit minutes | Jason, next real batch | Never instrumented. Extra-packet cites and IN_PROGRESS folders are a proxy only |
| Whether batch.js caused the five-hour allowance burn | Jason / session logs | F1 is a real mechanism. It is not confirmed as the root cause of that incident |

Do not score first-draft quality from packet `ready`, from `verify-only`,
or from conversion-rubric totals.

## 3. What needs Jason's paid budget before any `call_llm`

Set `APPLYR_CR112_PAID_BUDGET` only when Jason authorizes spend. That env
var is a gate, not an implementation.

On accepted 6.1, `--paid-llm` plus the env var **still does not call**
`call_llm`. Wiring a paid Stage 0 extract or paid author into this
harness is a later code story. It is not a flag flip.

| Paid step | Needed for | Default in this plan |
|---|---|---|
| Live Stage 0 extract / cascade / provider fallback | Measuring Stage 0 API invocations, retry cost, and whether frozen gates match live extract | Skip. Use frozen stub gates |
| Stage 1 author via `call_llm` | Automated drafts on the 5-JD set | Skip. Product path is one paste of `authoring_prompt.md`, which is harness/subscription cost, recorded separately from `api_cents` |
| Re-scoring or model bake-offs | Comparing author models | Out of CR-112 scope |

If Jason later authorizes paid execution, keep the columns separate:

- `prompt_meta_estimated_tokens` (estimate)
- `call_llm_invocations`
- `harness_spawn_count`
- `api_cents`
- `subscription_minutes`

Never add subscription minutes to API cents. Never treat an API migrate
as a saving without both numbers. Never run paid calls against production
`jobagent.sqlite` or `data/submissions/`.

## 4. What needs a merge before an end-to-end Stage 0–3 run is even defined

Accepted work lives on **sibling branches from `8bbc497`**, except Epic 1
(`9aab892` → `35842ec` → `8bbc497`). None of it is on dirty `main`.
Dirty `main` remains a candidate tree.

An end-to-end Stage 0–3 **definition** on one tree needs at least:

| Capability | Branch | Why e2e needs it |
|---|---|---|
| Sequential-ID reject, constraint fail-closed, integrity detector | `cr112-epic1` | Stage 0/1 truth fence |
| Lean default spawn + qualitative HM contract | `cr112-epic2` | Stage 0/1/2 operator path |
| Extra-packet WARN | `cr112-epic3` | Stage 1 closed-world |
| `omitted_reasons` + sibling TRACE | `cr112-story32` | Evidence explainability |
| Admin-line skip | `cr112-story34` | `jd_05` scoring contract |
| Adversarial fail-closed | `cr112-epic4` | Workflow recovery on the same code |
| Eval harness + fixtures | `cr112-story61` | Isolated copies, sqlite refuse, metrics columns |
| Swap report (optional for e2e, required for §5 evidence-selection report) | `cr112-story33` | Advisory CLI after TRACE exists |
| Gerund reporter (optional, advisory) | `cr112-story51` | Texture metric after drafts exist |
| Batch.js force-add (optional, never default) | `cr112-story22` | Prevent WE-load drift if someone runs the leftover runner |

Hard overlap on merge (same file, different stories):

- `scripts/build_authoring_packet.py`: Epic 1 + Story 3.2 + Story 3.4
- `scripts/run_all_tests.py`, `CHANGELOG.md`, requirements registry,
  traceability matrix, CR-112 epics tracker: most story branches
- `.gitignore`: Story 6.1 (`data/eval/`) + Story 2.2 (force-add note)

That merge is a Jason push/merge decision. This plan does not perform it.
Until it exists, "run Stage 0–3 on the eval set" is undefined because
packet 3.2–3.4, integrity 1.4, lean spawn 2.1/2.3, and adversarial 4.x
are not live on one tree.

Even after a clean merge, e2e still needs authored `Resume.md` /
`CoverLetter.md` (qualitative or paid) before Stage 2/3 can run on the
5-JD folders. Frozen gates plus packet assemble are Stage 0-adjacent
prep, not a finished submission.

Suggested later sequence **after** Jason authorizes merge, still with
paid calls off:

1. Integration merge of the table above onto a throwaway branch. Not dirty main.
2. Offline packet assemble on the 5 copies (`--assemble-packets` would
   then have to be implemented against the merged packet builder. Accepted
   6.1 does not do this).
3. Integrity audit + closed-world WARN + swap report on those packets.
4. Stop. Hand Jason the packets/prompts for a qualitative first-draft
   read, or wait for a paid-author story.

## 5. Explicit non-claims

Do not claim any of the following from this plan, the 742 baseline, or
the accepted local stories:

- Applyr is product ready.
- Stage 0–3 is dependable enough for daily applications.
- The 5-JD harness ran Stage 0 extract, Stage 1 author, Stage 2 review,
  or Stage 3 finalize.
- Live 7-folder rewrite is in scope. It is not.
- SupplyHouse will be rebuilt, re-authored, or given
  `HUMAN_ACCEPTED_RISK`. Recovery is closed.
- Extra-packet WARN is now a hard block.
- Gerund rate is a style gate.
- Dirty-main assemble / gerund numbers are accepted.
- `APPLYR_CR112_PAID_BUDGET` currently buys a paid eval run. It does not.
- Sibling CR-112 branches have been merged or pushed.
- Batch.js is the portable Author/Review runtime.

## Investigation §5 mapping (honest fill)

| Metric | Gate from §5 | Status in this plan |
|---|---|---|
| Truth errors | 0 HARD attribution misses | Eval set: no drafts, so 0 is vacuous. Historical live extra-packet WARN (4 folders, 2026-09-10) is context for Jason's WARN-vs-block decision, not a scan to rerun |
| Evidence selection | Every omission has a reason code | Not measured on accepted 6.1. Dirty-main assemble is not accepted. Needs merge + assemble |
| First-draft acceptance | Raise send+one-pass vs unknown baseline | `not_scored`. Instrument after real authoring |
| Human edit effort | Minutes + diff hunks | not measured |
| Workflow recovery | STATE-001–004 stay green | Independently testable on `cr112-epic4`. Not wired to the 5-JD folders |
| Tokens | Lean default, Stage 0 API counted apart | JD estimate 742. Stage 0 API **not measured**. Stage 1 prompt-meta **not present** on fixtures |
| Cost | Do not sum API and subscription | 0 and 0, columns separate |
| Latency | `run_events.jsonl` on eval set | Eval start/complete only. Live 7 folders still have 0 events unless separately enabled |

## Required user decisions (unchanged)

- Push / merge the local CR-112 branches onto main.
- Set a paid eval budget.
- Promote extra-packet WARN to hard-block.
- Start a new CR for harness-agnostic Author/Review isolation. That is
  not Story 2.2.

## Stop line

CR-112 local stories are accepted on isolated branches. This evaluation
plan is the bounded next artifact. Do not execute paid calls. Do not
merge. Do not claim product readiness.
