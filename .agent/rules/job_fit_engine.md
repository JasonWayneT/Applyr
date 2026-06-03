---
trigger: always_on
---

# Dynamic Job-Fit Decision Engine (v4.0)

This file defines a deterministic YES/NO decision system for evaluating job descriptions. It dynamically leverages the target specifications, experience ranges, blocklists, and anchors defined in the injected **Candidate Preferences JSON**.

---

## 0) Purpose & Batch Logic

**Pass threshold:** `candidate_preferences.json` → `min_fit_score` (default **72**). Python uses `get_min_fit_score()`; do not use legacy **78** from archived docs.

1. **Initialize Sandbox:** Clear previous JD context; load only `workExperience.md` (Ground Truth) and `Candidate Preferences` (Targets).
2. **Fast Gate:** Kill poor fits, seniority mismatches, blocked industries, or solo traps instantly using criteria from `Candidate Preferences`.
3. **Transition Analysis & Scoring:** Score based on alignment with the Candidate's profile, experiences, and anchors.

---

## 1) Ground Truth Profile & Preferences
Evaluate the candidate using:
- **Ground Truth (`workExperience.md`):** The candidate's actual metrics, roles, and historical timeline.
- **Candidate Preferences (Injected JSON):** The explicit parameters for the target role, experience limits, blocklists, and key focus anchors.

---

## 2) Stage A: The Fast Gate (Instant Kill)
If any of the following triggers are met, return **Score: 0**, **Decision: NO**, and **Terminate Pipeline** for this JD.

### 2.1 Title & Tier Blocklist
- **Blocked Titles:** Reject if the **job title** contains whole-word matches from `blocked_titles` (not substring hits in the JD body).
- **Senior titles allowed:** "Senior Product Manager" (and similar) is **allowed** when stated required years are within `experience_range.max`.
- **Solo PM trap:** Reject founding/first/sole/only-PM roles when `preferences.avoid_solo_pm_trap` is true. **Enforced deterministically** by `scripts/solo_pm_gate.py` (`FR-189` / CR-036).
- **Squad PM & mentorship allowed:** Squad-level ownership, structured product orgs, and informal mentorship of L1/L2 PMs are **NOT** solo traps. Cross-functional work with engineering is allowed.
- **Organization Role:** Reject if the role is explicitly "Founding," "First," "0-to-1," or "Sole" product professional unless permitted by preferences.
- **Entry-level:** Reject intern programs, 0–1 years required, or explicit greenfield 0-to-1 ownership when `no_zero_to_one` is true.

### 2.2 Experience & Constraints
- **Years Required:** Reject if required years of experience **exceeds** `experience_range.max` in Candidate Preferences. **Exactly max is allowed** (e.g. 7 years when max=7; 8+ fails). Enforced by `seniority_gate.py`; LLM must not re-penalize when `PRE-VERIFIED YEARS POLICY` is injected.
- **Blocked Industries:** Reject if the company operates in any of the `blocked_industries` listed in Candidate Preferences (user-defined moral/exclusion list only). **Enforced deterministically** by `scripts/industry_gate.py` at scout ingest and batch zero-token gate (`FR-170` / CR-027) before this LLM stage runs.
- **Industry / customer base (transferable skills):** Do **NOT** reject because the JD's vertical industry (healthcare, fintech, etc.) or customer base (B2C vs B2B) differs from the candidate's background. Score on transferable PM skills: platform/roadmap, cross-functional delivery, agile, stakeholder alignment, data complexity, compliance-aware products. Note domain gaps in RiskFlags only — never instant-kill for industry or customer-base mismatch alone (`FR-192` / CR-039).
- **Optional domain language:** When the JD marks vertical experience as optional, preferred, ideal, or "nice plus", do not penalize missing industry expertise.
- **AI tools vs AI PM:** Do **not** reject because the JD mentions AI tools, Copilot, or workflow automation. Reject only when the role requires **owning ML model development** or being the primary AI/ML product owner.

### 2.3 Location & Setting Gate
- **Home Base:** The candidate is located in the **San Diego, CA** area.
- **Remote Criteria:** If the role is explicitly "Remote", it is **ALLOWED** (provided it supports US hiring).
- **Multi-city listings:** If the JD lists US office cities **and** offers Remote (e.g. "Dallas, TX, Atlanta, GA, or Remote"), treat as **REMOTE-ELIGIBLE**. Do not instant-kill for non-SD city names when Remote is explicitly offered.
- **On-Site/Hybrid Criteria:** If the role is On-Site or Hybrid **only** (no Remote option), it MUST be located within **50 miles of San Diego, CA**.
- **Trigger:** Reject and Terminate if the role is On-Site or Hybrid in any city outside of greater San Diego (e.g., New York, Chicago, Plano, Atlanta, Seattle, Charlotte, Sunnyvale, Canada) **and** Remote is not offered.
- **Pre-verified override:** When the prompt includes `PRE-VERIFIED LOCATION POLICY: REMOTE_OK` or `SD_LOCAL_OK`, **skip this entire section** — location was already resolved deterministically; do not re-score or instant-kill on location.

---

## 3) Stage B: Full Scoring (0–100)

### A) Organizational Maturity (0-25)
*Does the candidate have a function-specific leader/mentor and team structure?*
- **22-25:** Perfect alignment with `preferences.structured_team_required` (mentions direct manager and a team).
- **15-21:** Implicitly part of a larger functional org.
- **0-14:** Solo trap (e.g., reports directly to a non-functional executive in a tiny startup).

### B) Seniority & Tenure Fit (0–25)
- **23-25:** High overlap with `experience_range` (within min and max targets). Senior title + required years at or below `experience_range.max` scores here (7 years when max=7 is full credit).
- **0-17:** Demands experience **above** `experience_range.max` (8+ when max=7), or head-of-product function ownership (not squad PM or informal mentorship).

### C) Technical & Execution Depth (0–25)
- **22-25:** High technical overlap with the `required_anchors` listed in preferences.
- **0-14:** Requires deep daily coding or non-relevant daily activities.

### D) The "Bridge" Alignment (0–25)
- **20-25:** High alignment on transferable PM skills — platform stability, roadmap, cross-functional delivery, data/system complexity — regardless of industry vertical or B2C/B2B customer base.
- **0-14:** Low PM craft overlap (not merely different industry or consumer vs enterprise).

---

## 4) Thresholds & The "Anchor" Gate
**Total Score = (A+B+C+D) - Penalties.**

### 4.1 Penalties
- **Small Startup:** Apply a -50 penalty only when the company appears to be a solo/founding trap **and** the JD lacks engineering, product design, or data team structure. **Do not apply** when the role reports to a functional technology leader (e.g. CTO) or mentions eng + design + data collaboration.

### 4.2 The "Two-Anchor Room" (Mandatory)
A **YES** decision requires at least **2 explicit overlaps** between the job description responsibilities and the `required_anchors` list in the Candidate Preferences. When `ANCHOR_GATE_ENABLED=1`, batch zero-token gate enforces this before LLM fit (`FR-172` / CR-028); default is LLM-only enforcement.

### 4.3 Final Decision
- **Score ≥ 85:** YES (Strong Fit).
- **Score 75–84:** YES (Conditional on Anchors).
- **Score < 75:** NO (Reject).

---

## 5) Output Requirements (Human + JSON)
*Constraints: No em-dashes, no transition fluff, max lengths as defined below.*

### Human-Readable Block
```text
Decision: YES/NO
Score: [0-100]
Confidence: High/Medium/Low
Summary: [Max 25 words. Direct reasoning for fit/reject.]

Top fit reasons:
- [Reason 1, Max 15 words]
- [Reason 2, Max 15 words]

Risk flags:
- [Risk 1, Max 15 words]
- [Risk 2, Max 15 words]
```