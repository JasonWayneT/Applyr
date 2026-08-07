---
status: done
created: 2026-08-06
related: CR-074
contains: CR-074 (Token-Conscious Authoring Packet — Approach A)
---

# CR-074 — Token-Conscious Authoring Packet: Epics & Stories

**Handoff doc.** Resumable plan for [CR-074](../05-change-requests/CR-074-token-conscious-authoring-packet.md).
Gate record: [CR-074-methodology-gate-record.md](./CR-074-methodology-gate-record.md).
A new session picks up at the **first unchecked story**. Do not start Epic N+1 until Epic N’s
Definition of Done is checked.

**Operating rule:** quality floor stays. Cloud tokens go to one compose pass after deterministic prep.

```
Epic 1 (done) → Epic 2 → Epic 3 → Epic 4 → Epic 5 → Epic 6 → Epic 7
                                                          └─ Epic 8 optional
```

---

## Epic 1 — Baseline, contracts, and stop-the-bleed measurement

**Definition of Done:** Baseline note written; schema + example checked in; metrics locked.

- [x] **Story 1.1 — Inventory current cloud loads per company** (2026-08-06)
  [`docs/reports/cr074-token-baseline.md`](../../reports/cr074-token-baseline.md). Fixed corpus ~120k est. tokens if naively loaded; Stage1+Stage2 ~100–150k cloud input per company today.
- [x] **Story 1.2 — Define success metrics** (2026-08-06)
  Locked in **Metrics** table at bottom of this file.
- [x] **Story 1.3 — Freeze `authoring_packet` schema (v0)** (2026-08-06)
  `scripts/contracts/authoring_packet_schema.json` + `authoring_packet.example.json`.
- [x] **Story 1.4 — Freeze fail-closed packet rules** (2026-08-06)
  `scripts/contracts/authoring_packet_RULES.md` — incomplete if unmapped required, disabled claim, missing excerpt, Skip tier, or estimated_tokens > 8000.

---

## Epic 2 — Deterministic Stage 0 builder

**Depends on:** Epic 1. **Reuse:** skill Stage 0 rules, prefs, gates, catalogs.

**Definition of Done:** CLI builds Stage 0 JSON for ≥3 real JDs with no cloud call; Jason spot-checks Tier 1 / Skip / Tier 2.

- [x] **Story 2.1 — DB cooldown / Self-Rejected check as a script** (2026-08-06)
  `scripts/stage0_db_gate.py` + `scripts/test_stage0_db_gate.py` (28 unittest cases, in-memory SQLite). Actions: clear / reapply_flag / reject. CLI exits 0 with JSON.
- [x] **Story 2.2 — Preference + exclusion zero-token checks** (2026-08-06)
  `scripts/stage0_prefs_gate.py`: blocked companies/industries (reusing `industry_gate`), title/years (reusing `seniority_gate`), solo PM trap (reusing `solo_pm_gate`), travel ceiling (>15%), and Exclusion Zone pattern checks for people management, 0-to-1, revenue/billing ownership, AI/ML model ownership without false-positiving ACC-401 tooling language. Returns structured `{passed, rejects, flags}`.
- [x] **Story 2.3 — JD bucket extraction (rules-only v1)** (2026-08-06)
  `build_stage0_fit_gate.py`: heading-based extraction of `required[]`, `preferred[]`, `responsibilities[]`, `culture[]` from JD text; `thin_jd` (True when <2 required items extracted and <80 words); `stage_signal` (Series, seed, pre-IPO, enterprise, startup, PE-backed). URL parsed from first line `URL: <url>`.
- [x] **Story 2.4 — Hard vs soft gap classification (rules-only)** (2026-08-06)
  Anchors each required item against all tags in `master_claims_tags_only.json` + tools in `skills_catalog.json`. Hard gap: item matches curated `_HARD_BLOCKED_TOOLS` frozenset (FHIR, HL7, Snowflake, Docker, TensorFlow, etc.) → `gap_class: HARD` → Skip. Soft gap: no anchor found but no hard-blocked tool → `gap_class: SOFT` → Tier 2. Preferred items get `handling` field.
- [x] **Story 2.5 — CLI: `build_stage0_fit_gate`** (2026-08-06)
  `scripts/build_stage0_fit_gate.py`: full flow DB gate → prefs/exclusion → bucket extraction → gap classification → tier → writes `stage0_fit_gate.json` + prints `Tier 1|Tier 2|Skip — {company}: {reason}`. `scripts/test_build_stage0_fit_gate.py`: 45 unittest cases (clean PM JD → not Skip; FHIR/Snowflake JD → Skip/HARD; thin JD → thin_jd true; blocked company/industry/solo PM/travel/people management/revenue/AI-ML → reject; DB inject for clear/reject/reapply; output shape; JSON serializable). Total: 73 tests (28+45), all pass.
- [x] **Story 2.6 — Batch table report helper** (2026-08-06)
  `build_stage0_fit_gate.py --batch-table` (or multiple folders) → Markdown Tier 1 / Tier 2 / Skip table via `batch_report()`.

---

## Epic 3 — Authoring packet builder (retrieve → rank → repack)

**Depends on:** Epic 1 schema, Epic 2 Stage 0. **Reuse:** `score_claim_for_jd`, tags, workExperience slices.

- [x] **Story 3.1 — Evidence mapper** (2026-08-06)
  `build_authoring_packet.py`: `build_evidence_map()` — item-centric tag-overlap primary / JD-profile secondary scorer; soft-gap bridges attached from `flagged_gaps`; disabled claims excluded.
- [x] **Story 3.2 — Excerpt slicer** (2026-08-06)
  `_extract_excerpt_for_project()` — `[ACC-NNN]` bracket pattern in `workExperience.md`; ACC-401 routed to `aiProjects.md`; synthetic fallback from tags; cap 500 chars.
- [x] **Story 3.3 — Packet assembler + ordering** (2026-08-06)
  `assemble_packet()` — emits schema v1.0 JSON with `estimated_tokens = utf-8 bytes // 4`; `rule_digest_version = "pending-epic-4"`; all five fail-closed rules enforced.
- [x] **Story 3.4 — Hook-fact slot (optional call)** (2026-08-06)
  `get_hook_fact()` — only for Tier 1 or Tier 2+reach_out; subprocess call to `research-engine.py --hook-fact`; HTML stripped; any failure → null; `--no-hook` skips.
- [x] **Story 3.5 — CLI + size guard** (2026-08-06)
  CLI `python scripts/build_authoring_packet.py {folder} [--no-hook] [--with-stage0] [--no-write]`; exits 0; prints `ready|incomplete — company — tokens — reason`; 36 unittest cases pass.

---

## Epic 4 — Lean rule digest

- [x] **Story 4.1 — Decide digest sources** (2026-08-06)
  `docs/spec/08-implementation/CR-074-rule-digest-sources.md` — INCLUDED/EXCLUDED table; 9 INCLUDE topics, 8 EXCLUDE topics.
- [x] **Story 4.2 — `generate_authoring_rule_digest.py`** (2026-08-06)
  `scripts/generate_authoring_rule_digest.py`: writes `data/authoring_rule_digest.md` (6386 chars, ~1596 tokens, well under 8k target) and `data/authoring_rule_digest.version` (sha256[:16]). Hard-fails if content > 10k chars. Version `e02321594d5fc36e`.
- [x] **Story 4.3 — Wire version into packet builder** (2026-08-06)
  `scripts/build_authoring_packet.py`: `_load_rule_digest_version()` — reads `.version` file, falls back to hashing digest file, warns + returns `"pending-epic-4"` if neither present. `assemble_packet()` now stamps real version instead of hardcoded fallback. 19 new tests + 36 existing all pass.

---

## Epic 5 — Single cloud author path

- [x] **Story 5.1 — Authoring prompt contract** (2026-08-06)
  `docs/spec/08-implementation/CR-074-authoring-prompt.md`: SYSTEM = digest verbatim; USER = preamble + packet JSON; closed-world rule; output contract (two fenced blocks); fix-loop protocol (max 2 rounds, packet+digest only).
- [x] **Story 5.2 — `author_from_packet` runner** (2026-08-06)
  `scripts/author_from_packet.py`: loads packet + digest; refuses (exit 1) on missing packet, `packet_status != ready`, or version mismatch (unless `--force`); writes `authoring_prompt.md` + `authoring_prompt_meta.json`; prints `PROMPT_READY — {company} — ~{tokens} input — paste authoring_prompt.md into a fresh agent`. `--invoke` guard: prints error unless env key present (not implemented in v1).
- [x] **Story 5.3 — Post-author mechanical gate** (2026-08-06)
  `scripts/author_from_packet.py --verify-only {folder}`: checks Resume.md + CoverLetter.md exist;
  lints those two docs only (skips `authoring_prompt.md`, which lists forbidden phrases as
  negative examples); runs coverage + JD-term scripts with ATTENTION as WARN (judgment), HARD_BLOCK as FAIL.
- [x] **Story 5.4 — Pilot one company end-to-end** (2026-08-06)
  Pilot on `data/context_pack_validation/limble`. Packet ~2607 tokens; prompt ~4.3k input.
  Mid-pilot gap: JD ranking omitted Zero To Sixty (and thin role floors) → closed-world author
  could not invent Z2S bullets. Fixed in packet builder: canonical-role excerpt floor (≥2 claims
  per Cision/Sterkly/Zero To Sixty) + JD skill anchors (Agile/Jira/QA/Pendo). Authored Resume.md +
  CoverLetter.md from packet+digest only. `--verify-only` → PASS (lint clean; JD terms clean;
  ground-truth ATTENTION remaining is judgment-only). Backups: `*.before_cr074`.
  **Jason send-ready (Y/N):** Y (2026-08-06) — see `authoring_prompt_meta.json`.

---

## Epic 6 — Verification pyramid

- [x] **Story 6.1 — Redefine Stage 2 default in SKILL.md** (2026-08-06)
  `generate-submission/SKILL.md` v2.1.0: CR-074 default path banner; Stage 2 = scripts-first.
- [x] **Story 6.2 — Optional review ladder** (2026-08-06)
  Ladder 0/1/2 documented in Stage 2 section.
- [x] **Story 6.3 — Cross-batch sweep trigger unchanged** (2026-08-06)
  Explicitly kept at send-batch / every-3 cadence, not per-company cloud.

---

## Epic 7 — Calibration batch + full cutover

- [x] **Story 7.1 — Calibration set (≥3 companies)** (2026-08-06)
  Counted set: Limble (pilot Y) + Camunda (Y) + Paylocity (Y). Ncontracts drafted then **skipped** from cal judgment (Jason 2026-08-06).
  All counted `--verify-only` PASS. Packet tokens 1850–2607; prompt ~3.8–4.3k.
  Report: `docs/reports/cr074-calibration-report.md`.
- [x] **Story 7.2 — Fix packet/digest gaps from calibration** (2026-08-06)
  Legacy string Stage 0 items; `position`→role_title; expanded JD skill anchors (SLA/GTM/Support/Ops/Usage/AI);
  geo hard-constraint; prefer narrative over thin synthetic excerpts.
- [x] **Story 7.3 — SKILL.md + AGENTS.md/CLAUDE.md cutover** (2026-08-06)
  SKILL already v2.1.0 (Epic 6). AGENTS.md + CLAUDE.md updated byte-identical: CR-074 default path,
  file map (packet + rule digest), Required Verification step 0 (`author_from_packet --verify-only`).
- [x] **Story 7.4 — CR closeout** (2026-08-06)
  CR status Implemented; registry/README/calibration metrics filled; Epic 8 left optional/deferred.

---

## Epic 8 — Optional local assists (after v1)

- [ ] **Story 8.1 — Local soft-gap classifier** (only if rules miss)
- [ ] **Story 8.2 — CR-062 `local_rewrite` post-lint polish**
- [ ] **Story 8.3 — Local rubric draft scores**

---

## Metrics (Story 1.2 — locked 2026-08-06)

| Metric | Baseline (Epic 1) | Target | Calibration (Epic 7) |
|--------|-------------------|--------|----------------------|
| Est. cloud input tokens / company (Stage1+Stage2) | ~100–150k | ≤20k; packet ≤8k + digest ≤2k | **~3.8–4.3k** prompt input (Limble/Camunda/Paylocity) |
| Mechanical verify clean rate | Existing clean submissions | ≥ same on cal set | **3/3** counted (`--verify-only` PASS) |
| Jason send-ready (Y/N) on cal set | n/a | ≥2/3 Y or explicit accept | **3/3 Y** (Ncontracts skipped) |

**Packet size ceiling (fail-closed):** `estimated_tokens` ≤ **8000**.

---

**Next story:** none for v1 — CR-074 Epics 1–7 closed. Optional Epic 8 (local assists) deferred.

---

## Story 5.4 Pilot Instructions (Jason-runs-manually)

Stories 5.1–5.4 are done (pilot completed 2026-08-06 on `context_pack_validation/limble`).
Keep these steps for any future re-pilot or calibration company:

**Pre-pilot checklist:**
1. Pick a Tier 1 folder that already has `stage0_fit_gate.json` (e.g. `data/submissions/limble`
   or `data/context_pack_validation/limble`). If the packet is stale, rebuild it:
   ```
   python scripts/build_authoring_packet.py data/submissions/COMPANY --no-hook
   ```
2. Build the prompt:
   ```
   python scripts/author_from_packet.py data/submissions/COMPANY
   ```
   Expect: `PROMPT_READY — COMPANY — ~N input tokens — paste authoring_prompt.md into a fresh agent`

3. Open `authoring_prompt.md` in the folder. It has two sections:
   - **SYSTEM BLOCK** — paste into the system-prompt field of a fresh Cursor/Claude conversation.
   - **USER BLOCK** — paste as the first user message.

4. The agent writes Resume.md and CoverLetter.md. Copy them back into the folder.

5. Run the gate:
   ```
   python scripts/author_from_packet.py data/submissions/COMPANY --verify-only
   ```
   Fix any HARD_BLOCK violations (max 2 rounds, same packet+digest only).

6. When `VERIFY RESULT: PASS`, proceed to full verification:
   ```
   python scripts/verify_submission.py data/submissions/COMPANY
   ```

**Calibration note (Epic 7):** after the pilot, record whether Jason would send it
(`Y/N`) in `authoring_prompt_meta.json` and note any digest gaps that required
workarounds — those become Story 7.2 fixes.
