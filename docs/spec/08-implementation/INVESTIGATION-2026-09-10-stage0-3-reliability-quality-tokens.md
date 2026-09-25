# Investigation — Stage 0–3 reliability, first-draft quality, and token consumption

**Date:** 2026-09-10
**Investigator:** Cursor (Grok 4.6) as investigation owner
**Status:** COMPLETE for investigation and planning. No implementation started.
**Constraint:** No implementation-code changes, no submission rewrites, no staging, no commits, no paid model experiments.

**Goal:** Make Stage 0–3 reliable, produce strong first drafts that need minimal human editing, and reduce token consumption, while keeping Applyr a composable workflow.

**Linked backlog:** [CR-112-stage0-3-reliability-quality-tokens-epics.md](./CR-112-stage0-3-reliability-quality-tokens-epics.md)

**Architectural guidance used:** [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) (2024-12-19). Treat Applyr as a *workflow* (predefined code paths with one bounded LLM compose step), not an autonomous per-JD agent swarm. Do not add a framework.

---

## Resume checkpoint

| Area | Status | Notes |
|---|---|---|
| Repo instructions | done | AGENTS.md, ACTIVE_WORKFLOW.md, generate-submission skill |
| Architecture trace | done | `run_submission.py` + `scripts/workflow/runner.py` |
| Antigravity dirty work | done | static analysis + isolated reproductions. Full runner live-exec blocked by auto-review |
| Sept 10 quality evidence | done | seven live folders under `data/submissions/` |
| Token / spawn inventory | done | estimated file sizes + prompt meta (bytes ÷ 4, not a real tokenizer count); Stage 0 API usage unavailable |
| Known concerns | done | both reproduced without paid model calls |
| Evaluation plan | done | in this report + CR-112 Epic 6 |
| Handoff | done | bottom of this file |

---

## 1. Verified architecture and model-call map

### Active path (canonical)

`python scripts/run_submission.py {folder}` is the sole writer of `workflow_state.json` and `stage_receipts/*.json`.

| Stage | What actually runs | Model / harness | Code |
|---|---|---|---|
| 0. Fit gate | Deterministic exclusion gates, then JD section extract (classifier, LLM fallback for low-confidence lines), then CR-108 evidence cascade (batched Groq then Gemini; local only if configured) | **API** (`utils.call_llm`, `max_retries=8`). Split, partial repair, same-provider retry, then provider fallback | `build_stage0_fit_gate.py`, `stage0_evidence_cascade.py` |
| 0. Skip / promote | Skip ledger + folder move; PASS from `pending_review/` → `submissions/` | none | `workflow/runner.py` |
| 1. Packet | Evidence map, excerpts, constraints, ATS term contract, optional hook-fact | none by default (`--no-hook` is CLI default). `--with-hook` is one `research-engine` API call | `build_authoring_packet.py` |
| 1. Wait | Write `authoring_prompt.md`, stop at `WAITING_FOR_LLM` | **Harness agent, not `call_llm`** | `runner.run_stage1_prompt` |
| 1. Author | External session pastes digest + packet | **Subscription allowance** if that session is Claude/Cursor/Factory | intended: `authoring_rule_digest.md` + packet only |
| 1. Validate | Lint, optimization bar, utilization, ATS terms, provenance contract | none | `author_from_packet.py --verify-only` |
| 2A–2D | Truth / ATS / HM / Mech collectors | none. HM is lint + a `hm.critical_read` WARN | `workflow/runner.py` |
| 2E Policy | Dispositions + `check_stage2_ready` | none | `workflow/policy.py` |
| 3 | `finalize_submission_job.py`, production DB write | none | `--finalize` |

Invalidation: `workflow.invalidate.reconcile_state_against_receipts` hashes outputs; mismatch → `STALE`. Resume rebuilds from the earliest stale stage.

### Legacy / optional / do-not-use-as-default

| Path | Status | Why it still burns tokens |
|---|---|---|
| `.claude/workflows/generate-submission-batch.js` | Documented opt-in ladder-2. Still live. | **3 harness agents per company** (author, review, finalize). Review prompt loads `workExperience.md` + rubric + JD + drafts. Cap 3 companies unless `allowLargeBatch`. CR-075 incident: 12 companies × 3 agents burned a five-hour allocation in minutes |
| `generate-submission` skill Stage 0 prose | Active instruction, duplicates code | Tells the *agent* to reason a full Stage 0 from WE + claims. That is a full-pack session even when `run_submission.py` already ran Stage 0 |
| `data/agent_context_pack.md` | Not default Stage 1 input after CR-074 | Still ~64k est. tokens. Easy to load if an agent follows AGENTS.md / skill habit |
| `author_from_packet.py --invoke` | Paid API compose | Exists; not the observed allowance-burn path |
| `batch_pipeline.py` evaluate/draft | Retired for compose. Sync auto-draft disabled | Do not resurrect |
| `classify_requirement()` per-line Ollama | Removed CR-108 Epic 7.7 (2026-09-09) | Cascade replaced it |

### Why the lean path is not what operators actually run

CR-074 target was: Stage 0 scripts only (0 cloud), Stage 1 one ~5–12k author call, Stage 2 scripts only.

What exists now:

1. Stage 0 is no longer 0-cloud. CR-108 cascade is batched API. That is a real cost, but it is **API quota**, not Claude 5-hour allowance.
2. Stage 1 lean prompt is real: seven live folders show `total_estimated_tokens` 11,972–12,762 (`authoring_prompt_meta.json`).
3. **A mechanism for allowance burn via harness agent spawning (not `call_llm`) is confirmed to exist and to be expensive** — AGENTS.md still says "invoke generate-submission" for today's JDs; that skill is ~17k estimated tokens and still describes a human-style Stage 0/1/2; batch review reloads WE (~34k estimated); a naive session that loads pack + skill + AGENTS + WE is ~64k + 17k + 11k + 34k estimated before the JD. **This is a real, sufficient mechanism — it is not confirmed to be what actually happened in the specific session that burned Jason's allowance** (no logs from that session were inspected; see §6 Unresolved).

CR-074's own 2026-08-06 baseline (`docs/reports/cr074-token-baseline.md`) estimated 100–150k cloud input per company for author + independent review. File sizes have grown since (WE 46k → 137k bytes; pack 157k → 256k bytes). The lean path landed. The instruction surface still invites the old load.

---

## 2. Findings ranked by user impact

### F1 — Per-JD harness agents still consume the five-hour allowance

**Impact:** Highest. This is the failure Jason named.

**Evidence:** `.claude/workflows/generate-submission-batch.js:49-51, 217-230` (3 agents/company). `reviewPrompt` (lines 172-190) loads `workExperience.md`. Skill Stage 0 (`.codex/skills/generate-submission/SKILL.md` from step 0) is still an agent reasoning pass. CHANGELOG / CR-075 already recorded a 12-company unattended burn.

**Measured vs estimated vs unavailable:**

Correction (2026-09-10, Jason's review): the rows below were originally labeled "measured." They are not — every one of them is a byte-count divided by 4, a standard rule-of-thumb estimate, not an actual tokenizer count. Relabeled as `estimated` throughout. `total_estimated_tokens` in `authoring_prompt_meta.json` is itself pipeline-computed the same way (not a real API-reported token count), so it stays an estimate too, just a per-folder one instead of a whole-file one.

| Quantity | Kind | Value |
|---|---|---|
| Lean Stage 1 prompt (7 live folders) | estimated (`total_estimated_tokens` field, bytes/4-derived) | 12.0–12.8k input |
| Rule digest | estimated (bytes ÷ 4) | 9,831 bytes ≈ 2.5k |
| `agent_context_pack.md` | estimated (bytes ÷ 4) | 255,642 bytes ≈ 64k |
| `workExperience.md` | estimated (bytes ÷ 4) | 137,327 bytes ≈ 34k |
| generate-submission skill | estimated (bytes ÷ 4) | 68,358 bytes ≈ 17k |
| Stage 0 cascade tokens this batch | unavailable | no `run_events.jsonl` on the 7 folders; no provider logs inspected |
| Subscription $ vs API $ | unavailable | moving Stage 1 to API is **not** automatically cheaper |

No row in this table is a measured token count. Treat every "k" figure here as a rough estimate, not a bill.

**Disposition:** REVISE instructions and default operator path. KEEP the orchestrator. Do not add more agents.

### F2 — Dirty Stage 0 sequential-ID remap can attach the wrong judgment to a requirement

**Impact:** High. A wrong HARD/NONE can Skip a real job or Pass a bad one.

**Reproduction (in-process, no provider call):**

```
req-001 → required:0:…  (first item in this call)
req-002 → required:1:…
req-000 → required:0:…  (same as req-001)
sub-batch starting at ordinal 5: req-001 → required:5:…  (first item *in this slice*)
bare "0" across required+preferred → None (safe)
shuffled semantic content → ACCEPTED (no check that reasoning matches the item)
```

Code: `scripts/stage0_evidence_cascade.py` `_resolve_item_id` (dirty, ~353–390). Test `test_invented_sequential_id_resolves_within_bucket` *requires* this mapping.

`_normalize_result` will hold an ungrounded HARD to NONE (`unsafe_hard`, ~505–518). That reduces Skip risk for badly grounded HARD. It does **not** stop a well-formed HARD/NONE/`evidence_level` from landing on the wrong row when the model numbered by prompt order and the content was shuffled.

The comment claims uniqueness ("accepted only when exactly one candidate matches") but the sequential branch returns `bucket_ids[position]` without a uniqueness test.

**Disposition:** REVISE. Keep the diagnosis (providers invent `req-001`). Remove position mapping. Fail that item/batch to retry or fallback. Preserve hash-suffix and unique-ordinal fallbacks that actually identify one id.

### F3 — Dirty packet builder drops `claim_constraints` and can still emit `ready`

**Impact:** High for attribution truth. CONTRIBUTED vs OWNED hedge disappears from the author prompt.

**Reproduction (isolated `assemble_packet`, no disk write to submissions):**

- Inflated excerpts + constraints → after example-drop + excerpt shrink to `_EXCERPT_MIN_CHARS` (400) + constraint wipe: `packet_status=ready`, `estimated_tokens=2912`, `claim_constraints={}`.
- Live `data/submissions/supplyhouse/authoring_packet.json`: `packet_status=ready`, `estimated_tokens=7227`, **`claim_constraints` length 0**. Other six folders have 21–28 constraints.

Fail-closed Rule 5 only checks `estimated_tokens > 8000` *after* the wipe (`build_authoring_packet.py` ~1537 then 1542). Empty constraints are not a fail-closed reason.

Comment claims verify-only gates do not read constraints. That is true. The *author* does. Closed-world rule in `author_from_packet.py` tells the model to obey `claim_constraints`. Wiping them is not "prompt convenience." It is dropping the attribution fence under token pressure.

**Disposition:** REVISE. Keep the SupplyHouse over-budget diagnosis. Do not ready a packet that had to drop constraints. Prefer dropping ATS-term padding, shrinking non-required excerpts further, or marking `incomplete` with a recorded reason.

### F4 — Adversarial runner can PASS without testing its stated invariant

**Impact:** Medium. Creates false confidence in `INVARIANTS_CATALOG.md`.

**Evidence (static read of `scripts/run_adversarial_pressure_test.py`):**

| Layer | Exercises production? | Honesty |
|---|---|---|
| Programmatic `CASES` | Calls production runner in temp dirs | **REVISE, do not treat as proven coverage.** Several checks (`check_doc_003_forbidden_punctuation`, `check_state_001_downstream_no_receipt`) catch *any* `WorkflowError` as success. A missing Stage 0 receipt can satisfy the punctuation case without the linter ever running. Calling production code shows an exception path exists, not that the named invariant fired. CR-112 Story 4.3. |
| Fixture `run_fixture_case` | Mostly no | REVISE. `case_missing_resume_section` is a string-contains check. `case_forbidden_punctuation` lints the fixture file. `case_hallucinated_claim` checks FAKE-999 ∉ catalog, not `check_claim_provenance` on a workflow folder |
| `case_stale_hash` fixture | No | **False pass.** `case_meta.json` exists; no `name ==` branch; function returns `{"status": "PASS"}` |
| Unknown fixture name | No | Same fall-through PASS |
| `tests/fixtures/adversarial/payload_*.txt` | Never discovered by this runner | INVESTIGATE / KEEP as unused older payloads |
| Positive control (healthy folder must PASS a real invariant) | Missing | ADD |
| Unrelated exception | Programmatic path records ERROR, not PASS | KEEP that behavior |
| Live `python scripts/run_adversarial_pressure_test.py` | Not executed this session | Auto-review blocked the script. Findings are from code + isolated imports |

Catalog claim "every invariant must be automatically testable via this runner" is **not true** for FIT-002/003, DOC-002/004, TRUTH-002/003, FINAL-001/002.

**Disposition:** REVISE runner. KEEP programmatic cases and the catalog as a spec. Do not treat a green fixture count as invariant proof.

### F5 — Closed-world hole: extra-packet claims pass Stage 1

**Impact:** Medium. First drafts can cite WE the packet never offered. That is both a truth leak and a token leak (authors load WE to find the "better" bullet).

**Evidence:** provenance IDs not in packet excerpts/evidence_map:

| Slug | Extra IDs |
|---|---|
| pearl_com | `ACC-101-SAVINGS` |
| supplyhouse | `ACC-101-SAVINGS` |
| loot_labs | `ACC-108-SUPPORT` |
| marlowe_companies_inc | `ACC-103-SEC` |

`_check_optimization_bar_provenance` only requires *packet required/soft_gap* IDs to be used. `rank_packet_evidence._is_cited` matches **project** prefix (`ACC-101`), so citing SAVINGS counts as using PM.

CR-102 `AC-334` requires packet claim IDs on each bullet for provenance-contract v2 packets. It does not forbid *additional* IDs.

**Disposition:** REVISE verify-only to WARN or fail extra IDs not in packet excerpts/constraints, with an explicit override. Do not treat project-prefix citation as lens citation.

### F6 — Sept 10 unused-evidence list is partly stale and partly ranking, not "missing retrieval"

Seven live folders, all `verification_passed: true`, rubric floors cleared (resume 71–85, cover 70–88). `arbiter` and `trax_technologies` are `COMPLETE`. The other five are `IN_PROGRESS` / `active=stage3`.

| Review claim | Packet | Document | Disposition |
|---|---|---|---|
| pearl_com / ACC-101-SAVINGS absent | Confirmed absent from excerpts, constraints, evidence_map | Present. Compound Cision bullet with ~$2M savings + datacenter/STERLING | **Ranking exclusion**, not retrieval miss. On "own the product roadmap…" SAVINGS ranks 3rd (4164) behind SCOPE (7322) and PM (4165). Pass 2 keeps Top-2 with `score > 0` (`build_authoring_packet.py:738-740`). Slot cap is 4; pearl used 1 ACC-101 slot. Author then cited SAVINGS anyway (F5). Coverage does **not** flag SAVINGS unused |
| supplyhouse / ACC-101-SAVINGS absent | Confirmed absent | Present. Storage-monitoring bullet already carries the ~$2M figure | **Ranking exclusion.** Never Top-2 on infra items (SQL/Kafka/AI win). 2 ACC-101 slots used (ANCHOR, TECH), under cap 4. Review's "PTO capacity-model" weak bullet is **on cdw, not supplyhouse** (stale / swapped company) |
| cdw / ACC-220-CLOUDERAEXIT | Present. Mapped to preferred "1 year contract" (weak pairing). Excerpt 79 chars | Used, welded onto the ~700-account migration bullet | **Present and used.** Mapping smell, not unused. Reviewer wanted a dedicated Cloudera bullet. Do not assume $100K beats 700-account retention for a TPM JD |
| loot_labs / ACC-108 | ACC-108-OPS in packet. ACC-108-RETENTION unused and `in_packet: false` | Weighted priority-score triage is already the last Cision bullet (ACC-108-SUPPORT, extra-packet) | **Mostly stale.** OWNED triage is in the final resume. Remaining packet miss is RETENTION, not the triage system |
| marlowe / ACC-103 | ACC-103-ROADMAP mapped to a Level II background-check required line | 300-item / ~90% security backlog is already in the resume (ACC-103-SEC, extra-packet) | **Stale for unused.** Mapping of ROADMAP → background check is a real assignment bug. ACC-103-PM (same 300/90% metrics) was never selected |

**Do not assume a larger metric is the better bullet.** ACC-101-SAVINGS is CONTRIBUTED $2M. For Pearl (backend/API/data PM) ACC-101-PM / SCOPE can be the more honest JD match. The packet should *explain* why SAVINGS lost, not auto-insert it.

Coverage `in_packet: false` flags are whole-catalog tag overlap, not "Stage 1 was offered this lens." `_load_packet_claim_ids` unions evidence_map + soft_gaps only, not canonical-role excerpts.

### F7 — Verb-led + trailing-gerund texture is real and should stay advisory

Measured on current Resume.md bullets (comma/`by`/`while` + `-ing`):

| Slug | Bullets | Unique openers | Gerundish trail |
|---|---:|---:|---:|
| arbiter | 11 | 10 | 11 |
| cdw | 10 | 9 | 10 |
| loot_labs | 9 | 9 | 7 |
| marlowe | 10 | 10 | 10 |
| pearl_com | 11 | 10 | 6 |
| supplyhouse | 10 | 9 | 8 |
| trax | 10 | 9 | 9 |

Openers already vary. The tell is the trailing mechanism clause, not a single verb. **Do not add a linter gate** until a human-reviewed sample sets a false-positive budget. Matches CR-097 proposed Story 7.5.

### F8 — Stage 2 "HM review" is not a semantic truth review

`collect_hm_findings` (`runner.py:1006-1044`) is lint plus `hm.critical_read` WARN. AGENTS.md tells the *agent* to dispose NEEDS_DISPOSITION immediately. That can mark a hiring-manager read done without one.

**Disposition:** KEEP mechanical lint. REVISE so `hm.critical_read` is not auto-disposed by the drafting agent, or move qualitative HM to send-batch only (already the skill's ladder-2 intent).

---

## 3. Component keep / revise / remove / investigate

| Component | Disposition | Why |
|---|---|---|
| `run_submission.py` + `scripts/workflow/` | KEEP | Correct composable workflow |
| Lean packet + digest Stage 1 | KEEP | Live meta ~12k. This is the intended default |
| CR-108 cascade (batched API) | KEEP, INVESTIGATE cost | Replaces per-line Ollama. Measure tokens before changing providers |
| Sequential-ID position map (dirty) | REVISE | F2 |
| `claim_constraints` wipe (dirty) | REVISE | F3 |
| `test_invented_sequential_id_resolves_within_bucket` | REVISE | Encodes the unsafe behavior |
| Programmatic adversarial `CASES` | REVISE | Calls production code, but several assertions accept any `WorkflowError` (Story 4.3) |
| Fixture `run_fixture_case` fall-through | REVISE | F4 |
| `INVARIANTS_CATALOG.md` | KEEP as spec, REVISE enforcement claim | Not fully tested |
| `payload_0*.txt` | INVESTIGATE | Unused by new runner |
| `generate-submission-batch.js` | KEEP as explicit opt-in, REVISE review prompt | Must not load WE; must not be the default |
| generate-submission skill Stage 0 agent prose | REVISE | Point at `run_submission.py`; stop re-deriving fit in-session |
| CR-097 Epics 1–6 | KEEP | First-draft self-improve. Do not block on Epic 7 |
| CR-097 proposed Epic 7 | INVESTIGATE only | Intake. Evidence routing belongs in CR-112, not silently accepted as CR-097 scope |
| CR-102 first-draft gates | KEEP | Closed-world extra-ID hole remains (F5) |
| CR-111 instruction hygiene | KEEP / continue | Directly related to F1 |
| Conversion-ready-pass as extra per-JD cloud | REVISE usage | Skill/AGENTS trigger stacking. Use on non-`generate-submission` docs only |
| Automatic gerund/style gates | DO NOT ADD | F7 |
| Local/cheaper author models | INVESTIGATE later | No eval this session. Do not assume adequacy |

Preserve Antigravity files. Do not delete the runner, fixtures, or catalog. Fix the assertions.

---

## 4. Baseline quality and tokens

### Quality (7 submissions, 2026-09-10 artifacts)

| Slug | Workflow | Resume | Cover | Constraints | Extra-packet cites |
|---|---|---:|---:|---:|---|
| arbiter | COMPLETE | 85 | 88 | 25 | none |
| trax_technologies | COMPLETE | 78 | 84 | 28 | none |
| cdw | IN_PROGRESS/stage3 | 77 | 83 | 26 | none |
| loot_labs | IN_PROGRESS/stage3 | 76 | 80 | 21 | ACC-108-SUPPORT |
| marlowe_companies_inc | IN_PROGRESS/stage3 | 74 | 76 | 26 | ACC-103-SEC |
| pearl_com | IN_PROGRESS/stage3 | 71 | 83 | 25 | ACC-101-SAVINGS |
| supplyhouse | IN_PROGRESS/stage3 | 71 | 70 | **0** | ACC-101-SAVINGS |

Floors cleared. Floors are not "done." Coverage still flags 4–13 unused catalog claims per folder, mostly `in_packet: false` tag overlap.

Human editing effort: **not instrumented**. Unknown how many minutes Jason spent. Proxy: extra-packet cites + compound bullets + five IN_PROGRESS folders still sitting at stage3.

Truth errors in this batch: **none found in mechanical receipts**. Attribution risk is concentrated on supplyhouse (no constraints) and extra-packet CONTRIBUTED/OWNED mixes.

### Tokens

| Item | Status |
|---|---|
| Lean Stage 1 input | estimated (bytes/4-derived `total_estimated_tokens`) 12.0–12.8k |
| Full-pack naive load | estimated ~120k+ (CR-074 2026-08-06). Pack+WE alone now ~98k est. |
| Harness agents per default company | designed 0 besides the one author paste. Observed risk: 3 if batch workflow used |
| Stage 0 API calls per JD | estimated 1–N (extract fallback + cascade split/retry/fallback). **Not measured on this batch** |
| Resume-after-STALE duplicate work | architecture can rebuild stages. **Not measured** |
| Paid vs subscription | subscription burn is harness context. API is `call_llm`. Different budgets |

---

## 5. Evaluation plan (controlled, no unpaid assumption)

Run on **isolated copies** + redirected SQLite. No production `jobagent.sqlite`. No paid model calls until Jason sets a budget.

| Metric | How | Gate | Baseline 2026-09-10 (Epic 6, `--no-paid-llm`) |
|---|---|---|---|
| Truth errors | `claim_provenance` + WE span check + attribution vs constraints. Count extra-packet IDs | 0 HARD attribution misses | Eval fixtures have no authored drafts yet (extra-packet count 0). Live 7-folder WARN scan: 4 folders (`loot_labs` ACC-108-SUPPORT, `marlowe_companies_inc` ACC-103-SEC, `pearl_com`/`supplyhouse` ACC-101-SAVINGS). Not a hard block. |
| Evidence selection | For each required JD item: top-2 packet IDs, rank of any "swap candidate", recorded reason if omitted (score, cap, disabled, tradeoff) | Every omission has a reason code | Local packet assemble on the 5-JD eval set: `omitted_missing_reason=0` on all five. `jd_05_wideworld_admin` fingerprint/nights/years rows have empty `claim_ids` (no ACC-103-ROADMAP). |
| First-draft acceptance | Jason binary on a frozen 5-JD set: send / one-pass / rework | Target: raise send+one-pass vs current (unknown baseline: instrument first) | `not_scored` (no Stage 1 author this run) |
| Human edit effort | Minutes + diff hunks Resume.md / CoverLetter.md | Instrument next real batch | not measured |
| Workflow recovery | Forced hash stale, skip lock, NEEDS_DISPOSITION retry | STATE-001–004 programmatic cases stay green | Adversarial runner 13/13 passed (2026-09-10) |
| Tokens | Prompt meta + `call_llm` log fields if present. Count harness agent spawns separately | Lean default: 1 author session, 0 review agents, Stage 0 API counted apart | Separate columns: `prompt_meta_estimated_tokens=742` (bytes÷4 estimate on the 5 JDs, not a tokenizer count), `call_llm_invocations=0`, `harness_spawn_count=0` |
| Cost | API invoice vs subscription sessions | Do not treat API migrate as a saving without both numbers | `api_cents=0`, `subscription_minutes=0`. Not summed. Paid budget line = 0 unless `APPLYR_CR112_PAID_BUDGET` is set. |
| Latency | `run_events.jsonl` stage durations (CR-070 Story 7.1). These 7 folders have **0 events** | Enable events on the eval set | Eval folders have `observability/run_events.jsonl` (assemble pass ~0.17s/folder). Live 7 folders unchanged. |

Positive controls: one healthy packet must stay ready with constraints intact. One invented `req-001` response must **not** map by position. One extra-packet ACC must fail or WARN.

---

## 6. Portable handoff

**Inspected:** AGENTS.md, ACTIVE_WORKFLOW.md, generate-submission skill, `run_submission.py`, `workflow/runner.py` (Stage 0–3, HM), `build_authoring_packet.py` (dirty + ranking + assemble), `stage0_evidence_cascade.py` (dirty resolve + validate + normalize), `test_stage0_evidence_cascade.py` (new test), `run_adversarial_pressure_test.py` + fixture metas, `INVARIANTS_CATALOG.md`, `author_from_packet.py` verify gates, `packet_evidence_utilization.py`, `check_ground_truth_coverage.py`, `generate-submission-batch.js`, CR-074/097/102/108/111 docs, CR-074 token baseline, Anthropic agents essay, seven `data/submissions/*` artifacts (packets, provenance, coverage, resumes, workflow, prompt meta).

**Executed:** git status/diff/log; isolated Python: sequential-ID resolve + shuffled validate; `assemble_packet` over-budget drop; claim catalog + slot counts + extra-packet set; `_score_claims_for_item` for SAVINGS on pearl/supplyhouse; resume bullet + gerund scan; file-size token estimates. **Did not** run paid `call_llm`. **Did not** get a live adversarial-runner process (auto-review). **Did not** rebuild live packets on disk.

**Completed:** This report + CR-112 backlog. Dirty Antigravity files left in place.

**Unresolved:** Stage 0 API token totals; whether Jason actually invoked batch.js on this batch; first-draft vs post-edit resume snapshots; live adversarial run; whether CR-097 Epic 1–6 should pause while CR-112 Epic 1 lands (recommend no: they are independent).

**Implementation scope locked 2026-09-10:** Epic 1 only (Stories 1.1–1.4), then a review checkpoint. Epics 2–6 stay planned.

---

## 7. Highest-priority findings (short)

1. Allowance burn is harness spawning + fat instruction loads, not the lean packet. **Two separate claims, kept distinct (2026-09-10 correction): the expensive spawning path (`generate-submission-batch.js`, 3 harness agents/company; CR-075's documented 12-company incident) is confirmed to exist and to be capable of burning the allowance fast. Whether that specific path is what fired during *this* particular allowance-burning session is unverified** — no `run_events.jsonl` or provider log was inspected for that session, and Section 6 ("Unresolved") already flags "whether Jason actually invoked batch.js on this batch" as open. Treat F1 as "a real and sufficient mechanism exists," not as "confirmed root cause of the specific incident," until that's checked.
2. Dirty sequential-ID remap is semantically unsafe.
3. Dirty constraint wipe can ready a packet with no attribution fence (live on supplyhouse).
4. Adversarial fixtures can PASS without hitting production.
5. Sept 10 "five unused swaps" are ranking / stale / already-in-doc, plus a real closed-world leak.

**Recommended first implementation story:** CR-112 Story 1.1 — reject invented sequential provider IDs instead of mapping them onto requirement positions.
