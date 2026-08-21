# Session handoff — WE truth contract + story-class claim index

**Date:** 2026-08-20  
**Identity for session logs:** `Cursor (Composer)` / prior turn was mid CR-095 indexing  
**Status:** CR-094 **done**. Follow-on story indexing **in progress, not finished**. Do not call the catalog clean.

---

## What the next session should do first

1. Read this file + [CR-094](../05-change-requests/CR-094-workexperience-truth-architecture.md) + [IMP-CR-094](./IMP-CR-094-workexperience-truth-architecture.md).
2. Run:  
   `python scripts/audit_claims_coverage.py`  
   Expect **~11 `we_unclaimed` ERROR** rows for indexable stories (live count as of handoff).
3. Finish indexing those stories as **tags-only** claim rows (no new author-facing `text` / `cover_story`). Then regenerate tags sidecar + run the audit/packet tests below.
4. Do **not** draft the new JD batch, recalibrate Stage 0 floors, commit `workExperience.md` / `jobagent.sqlite`, or bulk-write 60 claim essays.

---

## Contract (locked — Jason approved option A)

**One-sentence rule:** A resume/cover-letter sentence is fresh prose from a retrieved, attributed span of `workExperience.md` (or `aiProjects.md` for ACC-401). Never from catalog paragraphs, never invented from tags, never rounded past the story’s hedge.

- WE = source of truth **and** runtime evidence.
- Claims = index only (ids, tags, pointers, attribution, prohibited).
- When Stage 0 and Stage 1 disagree, **WE wins**.
- Plan file was **not** edited: `C:\Users\Jason\.cursor\plans\we_truth_contract_54e6a762.plan.md`.

---

## Done in this workstream (CR-094)

| Area | What landed |
|------|-------------|
| Packet | `_excerpt_for_claim` always slices WE / `aiProjects.md`. Never prefers claim `text`. |
| Lenses | First lens of a `project_id` carries the span; later lenses = pointer + lens instruction. |
| Hedges | Packet `claim_constraints` + hedge header on excerpts (`attribution`, `prohibited_claims`). |
| Classifier | `scripts/we_acc_index.py` — story / attribution / do_not_claim / tools (later extended — see below). |
| Audit | `we_unclaimed` only for **indexable** stories (not Attribution/DNC/tools). |
| Provenance | Non-story ACC tokens not treated as citable Fact IDs. Enabled sibling keeps `project_id` citable even if one lens is disabled. |
| Context pack | Strips contact / professional-references headings (PII). |
| Docs | `AGENTS.md`, `CLAIMS_STANDARD.md`, generate-submission Stage 1, digest §1/§6, packet RULES, CHANGELOG, PRODUCT_CAPABILITIES §3. |
| Spec | `docs/spec/05-change-requests/CR-094-workexperience-truth-architecture.md` + IMP tracker (stories checked). |

**Acceptance (CR-094):** AC1–AC8 intended complete. Catalog still has unlensed **stories** by design of CR-094 “Not in this CR.”

---

## In progress (story index + classifier hardening) — unfinished

Jason said “move forward” → start indexing remaining story-class ACCs. That work **did not finish**. Partial code is already on disk.

### Classifier extensions already in `scripts/we_acc_index.py`

Beyond CR-094’s four classes:

| Class | Meaning | Indexable? |
|-------|---------|------------|
| `story` | Standalone accomplishment | Yes |
| `substory` | Doc breakdown under a parent (`What Jason drove`, `Problem:`, `Outcome:`, `Primary (…`, etc.) | No (rides in parent excerpt) |
| `nonclaimable` | `Not owned:`, `Not Implemented`, `unconfirmed`, etc. | No |
| attribution / do_not_claim / tools | Unchanged | No |

Also landed in that module / callers:

- `story_span_end()` — parent excerpt includes substories + hedges; **stops before** next story / tools / **nonclaimable** sibling (so Glacier/Oracle do not land inside Docker’s card).
- Attribution vs DNC classification uses **label near the ACC marker**, not a bare “do not claim” phrase in Attribution body text (ACC-130 false DNC bug).
- `hedges_for_project` walks through substories; stops at story / tools / nonclaimable.

**No formal CR-095 doc was written yet.** Module header mentions CR-094/CR-095; either file a short CR-095 for “story-class index + ACC classes” or fold the remaining work into an IMP extension of CR-094. Prefer a small CR so audit/tests/docs stay attributable.

### Tool allowlist drift (already changed)

Verified tools in WE / `skills_catalog.json` forced deny-list cleanup:

- `docker` **removed** from `HARD_BLOCKED_TOOLS` (`scripts/blocked_tools.py`).
- Docker / AWS removed from `local_draft_stages.BLOCKED_TOOLS` and `drafting_engine.BLOCKED_TOOLS`.
- Digest exclusion-zone example no longer lists Docker as always-forbidden.
- `utils.py` local constraint prefix no longer lists Docker/AWS as forever-blocked.

**Still open:** Stage 0 test `test_familiarity_with_docker_is_soft_not_skip` and `_UNKNOWN_TOOLS` still treat docker as an unknown/hard-tool fixture — may need rewrite now that Docker is allow-listed. Confirm against `skills_catalog.json` (`Docker (hands-on, running environments)`, `AWS S3 (hands-on, console-level)`, `Parallels (VM testing)`).

### Catalog state (not done)

- `data/master_claims.json` still **69** claims.
- Only `ACC-114-COST` exists for project `ACC-114`, and it stays **`disabled: true`** (quarantine). That does **not** satisfy `we_unclaimed` for ACC-114 — need an **enabled** tags-only sibling (e.g. `ACC-114-INGEST` / `ACC-114-DEPRECATION`), keep COST disabled.
- `master_claims_tags_only.json` **not** regenerated for new rows (none added yet).

### Live audit snapshot (handoff time)

`python scripts/audit_claims_coverage.py` → indexable `we_unclaimed`:

| ACC | Notes for indexer |
|-----|-------------------|
| ACC-114 | PIC / Canadian ingest deprecation. Add **enabled** lens; keep `ACC-114-COST` disabled. OWNED on exit work; **CONTRIBUTED** hedge for full ~$800K (MET-17). Never invent PIC expansion. |
| ACC-127 | AU/NZ vendor content restrictions. Thematic overlap with `ACC-107-*` rollups — still needs own `project_id` for audit. |
| ACC-128 | Google/Yahoo sender compliance. Same: own row; overlap with ACC-107 OK. |
| ACC-134 | Visible (VOC-16) ownership / Java news ingest. Overlap with `ACC-110` / `ACC-111` — still needs own row. Do not print “Visible” in customer-facing docs. |
| ACC-135 | Legacy ETL knowledge-share. Overlap with ACC-110 — own row. |
| ACC-168 | “Why this role existed” hire-context. May be **context, not a proof story** — consider adding a substory/nonclaimable prefix in the classifier, or a single tags-only row if Jason wants it selectable. Decide deliberately; do not silently force it into resumes. |
| ACC-169 | Hands-on AWS S3 (CPRE legacy ingest). Console-level; DNC bucket/IAM/architecture. |
| ACC-172 | Hands-on Docker environments. |
| ACC-176 | Translation service API migration (vendor → internal). |
| ACC-211 | Hands-on AWS S3 at Sterkly. |
| ACC-214 | Parallels VM testing (already in skills_catalog). |

**Do not index:** Attribution ids, DO NOT CLAIM ids, ACC-119 tools, ACC-173 Glacier (not implemented), ACC-174 Oracle failover (not completed), other nonclaimable / substory brackets.

---

## Tests / code already touched (verify before claiming done)

Updated or added (may be red until catalog rows land):

- `scripts/test_we_acc_index.py` — substory / nonclaimable / story classes
- `scripts/test_build_authoring_packet.py` — parent excerpt includes substory, not next story
- `scripts/test_claim_provenance.py` — enabled sibling keeps project_id citable
- `scripts/test_audit_claims_coverage.py` — live catalog expected **clean** ERROR tier (will fail until rows exist); substory/nonclaimable not `we_unclaimed`
- `scripts/build_authoring_packet.py` — uses `story_span_end`
- `scripts/claim_provenance.py` — disabled-only project_id logic
- `scripts/audit_claims_coverage.py` — high-risk set includes ACC-169 / 172 / 211

**Suggested verify command after indexing:**

```bash
.venv\Scripts\python.exe -m unittest `
  scripts.test_we_acc_index `
  scripts.test_audit_claims_coverage `
  scripts.test_claim_provenance `
  scripts.test_build_authoring_packet `
  scripts.test_generate_authoring_rule_digest `
  scripts.test_context_pack -q

.venv\Scripts\python.exe scripts/audit_claims_coverage.py --strict
.venv\Scripts\python.exe scripts/generate_context_pack.py
.venv\Scripts\python.exe scripts/generate_authoring_rule_digest.py
```

Delete scratch file if still present: `scripts/_tmp_unclaimed_stories.txt`.

---

## How to finish indexing (concrete)

For each remaining indexable ACC above:

1. Confirm class is still `story` via `we_acc_index.classify_we_acc_ids`.
2. Add one claim key `{ACC}-LENS` with: `employer`, `project_id`, `lens`, `tags` (distinctive), `metrics` (literal only), `attribution` / `prohibited_claims` from `hedges_for_project` (clean DNC body; drop bracket noise).
3. **Do not** hand-author a new `text` / `cover_story` for authoring. Empty `text` or omit; packet uses WE. Legacy `text` on old rows can stay until a later cleanup.
4. ACC-114: add enabled lens; leave `ACC-114-COST` `disabled: true` and `_QUARANTINED_CLAIM_IDS`.
5. Regenerate `master_claims_tags_only.json` via `generate_context_pack.py` (never hand-edit the sidecar).
6. Update `data/CLAIMS_STANDARD.md` if ACC class rules need a permanent note (substory / nonclaimable).
7. Extend IMP (new CR-095 or CR-094 follow-on) with checkboxes; mark audit `--strict` clean.

Optional pressure checks from the original contract test plan:

- Unlensed true story becomes selectable without a hand-written `text` card.
- DO NOT CLAIM / Attribution never appear as `we_unclaimed`.
- CONTRIBUTED / `$800K` sole-causation still blocked (`LR-012` / `LW-028` / COST disabled).
- Two lenses ≠ byte-identical WE dumps; second is pointer.
- Stage 0-retrievable evidence has a selectable story or an explicit hard gap.

---

## Out of scope (still)

- Stage 0 floor recalibration
- New JD batch / `generate-submission` authoring
- Bulk-writing claim `text` blobs
- Rewriting WE to remove Attribution/DNC ACC numbers (parser already treats them as fields)
- Option C structured rewrite of WE
- Committing PII (`workExperience.md`, `jobagent.sqlite`)

---

## File map for the next agent

| Path | Role |
|------|------|
| `scripts/we_acc_index.py` | ACC class + hedges + story span |
| `scripts/build_authoring_packet.py` | WE-primary excerpts + constraints |
| `scripts/audit_claims_coverage.py` | Coverage ERROR/WARN |
| `scripts/claim_provenance.py` | Valid Fact IDs |
| `scripts/blocked_tools.py` | Shared hard deny-list (Docker already off) |
| `data/master_claims.json` | Index to extend |
| `data/CLAIMS_STANDARD.md` | Construction rules |
| `data/skills_catalog.json` | ACC-119 tools path (Docker / S3 / Parallels already listed) |
| `docs/spec/05-change-requests/CR-094-*.md` | Locked architecture |
| `docs/spec/08-implementation/IMP-CR-094-*.md` | CR-094 done; indexing was “Not in this CR” |

---

## One-line status

**CR-094 WE-primary authoring is implemented. Catalog still missing ~11 story-class index rows; classifier/tooling for that pass is partially on disk. Next session: add tags-only claims, regen sidecar, make `audit_claims_coverage --strict` green, then stop.**
