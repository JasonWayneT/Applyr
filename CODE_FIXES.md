# Code Fixes Backlog

Issues observed from auditing the `/data/submissions` folder against the research report criteria (2026-06-25). Not yet implemented.

**Superseded by:** [docs/pipeline-quality-epics.md](docs/pipeline-quality-epics.md) — this file's fixes
were restructured into formal epics there (some now partially implemented, uncommitted; see that doc's
header). Keep this file for historical context on what the original audit found; treat the epics doc
as the active plan. Fix 6 below (incomplete `napster_corp_` submission folder) is the same
silently-swallowed-failure pattern independently confirmed in
[docs/spec/08-implementation/CR-053-fit-rubric-overhaul-epics.md](docs/spec/08-implementation/CR-053-fit-rubric-overhaul-epics.md)'s
CR-054 — two separate audits, five days apart, hit the same bug class.

---

## Fix 1 — R8 (B2B SaaS Legibility) scores 3/20 on every resume

**Severity:** High — affects all 22 submissions  
**Pattern:** Every resume eval shows R8 as 3/20 with the same flag: missing buyer/user distinction, sales motion signals, and internal cross-functional partner references.  
**Root cause:** The resume generation prompt doesn't instruct the model to extract and embed B2B SaaS operating context from the JD profile.  
**Fix:** Add a required `b2b_saas_legibility` block to the resume generation prompt. For each role, the generator should identify and weave in: customer segment (enterprise/mid-market/SMB), sales motion (sales-led/PLG/hybrid), buyer vs. user distinction, contract size signals, and relevant internal partners (sales, CS, solutions engineering, compliance, support).

---

## Fix 2 — Cover letter opening hook (C1) is consistently generic

**Severity:** High — primary blocker on 10+ BLOCKED submissions  
**Pattern:** C1 scores 0–12/25. Flagged wording: "too generic," "could be more specific to [company]'s context."  
**Root cause:** The cover letter generation prompt doesn't enforce a company-specific opening. It likely tells the model to open with enthusiasm or fit without requiring a concrete, company-anchored hook.  
**Fix:** Add a constraint to the CL generation prompt: the opening sentence must reference a specific, verifiable fact about the company's product, market position, recent move, or stated mission — sourced from `Research_Packet.json`. Generic openings ("I'm excited to apply...") should be flagged or blocked.

---

## Fix 3 — Cover letter proof density (C2) is consistently weak

**Severity:** High — co-blocker alongside Fix 2 on most BLOCKED submissions  
**Pattern:** C2 scores 10–20/25. Flagged as "stronger proof point from the resume needed."  
**Root cause:** The CL generator likely picks surface-level or mid-tier bullets from the resume rather than the highest-impact ones. It may not have a mechanism to rank proof points before selecting.  
**Fix:** Before generating the cover letter, run a proof-point ranking step: score the top 5 resume bullets by business-outcome tier (revenue/retention/conversion > efficiency > scale/scope > output), then instruct the CL generator to use the top 1–2 as its evidence anchors. Include baseline, delta, timeframe in the proof point pulled into the letter.

---

## Fix 4 — R6 (Seniority Altitude) flags junior framing across all resumes

**Severity:** Medium — flagged on all 22 submissions, not a hard blocker but lowers overall score  
**Pattern:** Flagged verbs: "co-created," "coordinated," "protected," "managed," "migrated," "Owned." These signal execution support rather than strategic ownership.  
**Root cause:** The resume generator doesn't apply a seniority-level filter to bullet framing.  
**Fix:** Add a post-generation step that checks each bullet's primary verb against a junior-framing blocklist and suggests replacements. For PM roles targeting senior/lead level: replace "coordinated" → "aligned," "co-created" → "led," "managed" → "owned end-to-end," "protected" → "sustained."

---

## Fix 5 — R5 (PM Craft: Discovery + GTM) is absent on most resumes

**Severity:** Medium — flagged on all 22, not a hard blocker but a conversion risk  
**Pattern:** Discovery and GTM Partnership are the two most commonly absent PM craft signals. Experimentation is absent on roughly half.  
**Root cause:** The resume generator doesn't audit for PM craft coverage before finalizing.  
**Fix:** Add a PM craft coverage check after bullet generation. If discovery (user research, problem framing, hypothesis testing) and GTM partnership (launch coordination, sales enablement, adoption tracking) have zero bullets, the generator should add or surface existing experience that maps to these craft areas rather than outputting a discovery-blind resume.

---

## Fix 6 — `napster_corp_` folder is incomplete (no resume, CL, or eval)

**Severity:** Low — single submission  
**Pattern:** The folder contains only `Interview_Cheat_Sheet.md` and `Research_Packet.json`. The pipeline stopped before generating the resume, cover letter, or eval.  
**Root cause:** Unknown — possibly a pipeline error or early exit during the generation phase.  
**Fix:** Add pipeline completion verification: after each submission folder is created, check that all 5 expected artifacts exist (`Resume.md`, `CoverLetter.md`, `Resume.pdf`, `CoverLetter.pdf`, `eval_report.json`). Log incomplete submissions to a completion report rather than leaving them silently partial.

---

## Fix 7 — Cover letter length violations go undetected pre-eval

**Severity:** Low — affects element451 (too long, ~500+ words) and meta (too short)  
**Pattern:** Length is only caught during eval, not during generation.  
**Fix:** Add a word count gate to the CL generation step. Target 275–400 words. If the draft is outside that range, run a trim or expand pass before saving.

---

## Recurring Non-Blocking Flags (Not Code Fixes — Resume Content Quality)

These appear on all resumes as soft flags and are content-level (not pipeline) issues:
- R2: JD keywords that require manual domain knowledge to match (sales-led, PLG, specific product nouns)
- R3: Top-third narrative doesn't tune to company stage — would require stage-detection logic
- R4: Tier-3 metrics without baseline/delta — content problem, not a generation failure

These are worth addressing in a future prompting improvement pass but are not blocking the current pipeline from functioning.
