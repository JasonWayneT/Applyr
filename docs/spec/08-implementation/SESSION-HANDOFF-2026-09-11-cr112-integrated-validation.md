---
status: integration_ready_first_draft_remaining
created: 2026-09-11
from: Cursor (Grok 4.6)
candidate: 7bf6829
branch: cr112-integrated-validation-candidate
---

# CR-112 integrated validation candidate — 2026-09-11

## Ancestry

Treat `7bf6829` as the current complete CR-112 sequence candidate. Do not merge it onto `cr112-selection-closed-world-design` yet.

Read-only ancestry confirms:

- `b873fb5` is the merge base with local `main`.
- `7bf6829` descends linearly through the accepted Epic 3 commits and the two Epic 7 commits.
- Therefore `7bf6829` already contains local main + replacement Epic 3 + Epic 7.

Recorded on this isolated worktree:

| Field | Value |
|---|---|
| Candidate | `7bf68296bcd0ed91478f203cc4f2b6d6ed67b14f` |
| Parent | `b7f71976d0cf93935d32153e6b99deb31af084cb` |
| Parent chain `b873fb5..HEAD` | `af634a6` → `fa90320` → `8ce68a1` → `706504a` → `b7f7197` → `7bf6829` |
| Linearity | single parent at HEAD; `b873fb5`, `706504a`, `fa90320`, `8ce68a1`, `b7f7197` are ancestors |
| Worktree | `.claude/worktrees/cr112-integrated-validation-candidate` |
| Branch | `cr112-integrated-validation-candidate` (created at `7bf6829`) |
| Cleanliness at creation | clean (`git status --porcelain` empty) |
| Private sidecar in ancestry | none in `b873fb5..HEAD` names or commit subjects |
| Live submissions / production DB in diff | none (`data/submissions`, `workExperience.md`, `master_claims.json`, `jobagent.sqlite` absent from the diff) |

Changed-file inventory from `b873fb5` is 36 files (Epic 3 replacement + Epic 7 + docs). Full `--name-status` was recorded in the validation session before tests.

Untouched checkouts after worktree creation:

- `cr112-selection-closed-world-design` @ `706504a` still dirty (epics.md modified; cost-pause and reconciliation untracked)
- `cr112-story71-72` @ `7bf6829` still clean
- local `main` / `cr112-integration` still `b873fb5`

## Dirty-document comparison

Compared the dirty `cr112-selection-closed-world-design` working tree against `7bf6829` without switching, resetting, or cleaning that checkout.

| Dirty path | Result |
|---|---|
| `CR-112-cost-pause-state-design.md` (untracked) | Not byte-identical. Dirty copy is missing `follow_up_review: PASS (97887893-...)`. Candidate already has the later version. Not carried forward. |
| `CR-112-stage0-3-reliability-quality-tokens-epics.md` (modified) | Not byte-identical. Dirty copy adds a pointer to the reconciliation file but also stale 7.x / Epic 3 status that contradicts the accepted follow-up review. Stale status was not copied. Durable reconciliation pointer is carried via the reconciliation file and tracker edits below. |
| `CR-112-reconciliation-2026-09-11.md` (untracked) | Absent from `7bf6829`. Privacy scan: review IDs, SHAs, frozen slug table; no contact PII. Carried forward with an addendum so current 7.x status is not the uncommitted-FAIL snapshot. |

Local-only prerequisites in this worktree at creation:

- Missing: `data/authoring_rule_digest.md`, `data/workExperience.md`, `data/master_claims.json`, `data/jobagent.sqlite`
- Present tracked: `data/master_claims.example.json`
- Digest generator is tracked and hardcoded (no PII reads). Safe to generate locally and leave untracked.

## Follow-up handoff

`docs/spec/08-implementation/SESSION-HANDOFF-2026-09-11-cr112-story71-72-followup.md` is on the candidate. Claims to verify in this run: 41 focused 7.x tests, cascade tests, Review Center pause/resume, consumed-import rename, `WAITING_FOR_INPUT` / `cost_authorization`, missing digest as isolation not product failure.

## Tracker

CR-112 is not complete. Combined-candidate verification is this session. See the epics file for per-story states after documentation reconciliation.

## Combined verification (2026-09-11 / 2026-09-12)

Local HEAD after isolation-test commits: `165485f` (parent chain still `7bf6829` plus four local commits). No push. Production `data/jobagent.sqlite` mtime/size unchanged across practice runs.

### Automated suite from `165485f`

| Check | Result | Class if not green |
|---|---|---|
| Epic 3 focused | 66/66 | |
| Epic 7 focused | 41/41 | |
| Workflow receipt/invalidation/resume | 49/49 after isolating two tests from live WE | missing live WE; tests now mocked like sibling |
| Adversarial | 5/5 | |
| Full `run_all_tests.py --python-only` | 60/60 PASS (206s) | |
| Frontend vitest | 367 pass after deleting a too-complete worktree sqlite stub | stub schema vs migrations; not a product regression |
| Build | pass | |
| Lint | 0 errors; 24 pre-existing `any`/hooks warnings | existing unrelated |
| Instruction drift | CLEAN after copying gitignored `.claude/skills` pointer stubs | missing local pointer stubs |
| Privacy `audit_public_repo.py` | PASS (944 tracked files) | |
| Context-pack freshness | not run | missing `data/agent_context_pack.md`; do not generate a fake pack from example John Doe WE |
| Diff vs `b873fb5` | no live submissions, WE, claims, or production sqlite | |

Safe untracked local prereqs generated in this worktree only:

- `data/authoring_rule_digest.md` from tracked `generate_authoring_rule_digest.py`
- `data/workExperience.md` / `data/master_claims.json` from tracked examples (not live PII)
- `data/master_claims_tags_only.json` stripped from the example catalog (required: `load_claims` reads tags-only, not `master_claims.json`)
- Do not copy parent live WE, live claims, or production sqlite

### No-cost synthetic practice

Temp folder, `--mode practice`, redirected review sqlite, no provider adapters, no paid budget.

1. Stage 0 finds no authorized provider (`unknown_cost_class`).
2. Canonical runner commits `WAITING_FOR_INPUT`.
3. Receipt `pause_kind=cost_authorization`. `model_call_occurred=false`. `cost_applicable=false`. `api_cents` omitted.
4. `--resume` without `--mode practice` errors on mode mismatch (operational note; not a cost-pause regression). Matching `--mode practice --resume` twice stays paused, zero calls.
5. Bound `stage0_cascade_import.json` from the generated template is consumed exactly once (`stage0_cascade_import.consumed.json`).
6. Stage 0 COMPLETE. Packet + `authoring_prompt.md` written. Workflow stops at `WAITING_FOR_LLM`.
7. `--status` `check_workflow_complete: NO`.
8. Parent production sqlite unchanged.

Missing digest was generated first. The earlier Story 7 worktree FileNotFoundError is not this run.

### Frozen five-JD corpus

After the tags-only sidecar existed:

| JD | Stage 0 | Import | Packet | Prompt | First draft |
|---|---|---|---|---|---|
| northwind | cost pause, then PASS Tier 1 via import | yes, consumed | ready; 13 excerpts; 6/7 rows mapped; no replacements | ~7400 estimated tokens | not authored |
| contoso | `pause_kind=review_center` (DBA, SQL) before cost pause | n/a | n/a | n/a | stopped |
| fabrikam / adventure / wideworld | not continued | | | | |

Northwind without tags-only produced `packet_status=ready` with empty `excerpts` / empty `claim_ids`. That is missing sidecar, not an Epic 3 scoring regression. After generating example tags-only, mapping filled.

First-draft Stage 0–3 was not run. Example catalog employers are Acme/Example/Startup. Production template still requires Cision / Sterkly / Zero To Sixty. Live WE was not copied. Authoring a John Doe draft would not prove daily-use quality, and inventing Cision bullets would violate closed-world.

Contoso Review Center pause is example-WE skill confirmations, same class as the fit-gate mock. Do not auto-confirm skills just to green the eval.

### Verdict

`INTEGRATION_READY`. Combined code and no-cost workflow are verified. First-draft product proof remains.

Do not merge onto `cr112-selection-closed-world-design`. Do not push.

