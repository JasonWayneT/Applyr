---
trigger: always_on
---

# Dynamic Job-Fit Decision Engine (v5.0)

This file defines evaluation rules for job descriptions. **Python implements deterministic gates and scoring**; this document aligns LLM fallback behavior and human operators with that code.

**Primary scoring path (CR-053):** `scripts/structured_fit.py` when `STRUCTURED_FIT=1` (default). LLM returns per-criterion equivalence judgments only; the final 0–100 score is computed in code. Set `STRUCTURED_FIT=0` to use legacy holistic LLM Stage B below.

**Pass threshold:** `candidate_preferences.json` → `min_fit_score` (default **72**). Python uses `get_min_fit_score()`.

---

## 0) Purpose & Batch Logic

1. **Initialize Sandbox:** Clear previous JD context; load only `workExperience.md` (Ground Truth) and `Candidate Preferences` (Targets).
2. **Fast Gate:** Kill poor fits instantly — title tier, years, industries, solo trap, location, blocked companies, keywords — using criteria from `Candidate Preferences`.
3. **Structured scoring (default):** Must-have extraction → LLM yes/partial/no judgments → weighted deterministic score + confidence routing (`min_confidence_score` when set).
4. **Legacy LLM scoring (fallback):** Holistic Stage B rubric when structured path unavailable.

---

## 1) Ground Truth Profile & Preferences

Evaluate the candidate using:
- **Ground Truth (`workExperience.md`):** Actual metrics, roles, and timeline.
- **Candidate Preferences (Injected JSON):** Target role, experience limits, blocklists, anchors, gate rollout keys.

---

## 2) Stage A: The Fast Gate (Instant Kill)

If any trigger matches, return **Score: 0**, **Decision: NO**, **Terminate Pipeline**.

### 2.1 Title & Tier Blocklist

Enforced by `scripts/seniority_gate.py` (`FR-245` / CR-055):

- **`blocked_role_titles`:** Whole-word matches in the **job title** reject (e.g. `Director`, `VP`, `Head of`, `Staff`).
- **`blocked_focus_area_words`:** Reject only when the focus word appears **without** a PM/product title context (e.g. block `Growth` in "Head of Growth", allow "Product Manager, Growth").
- **`blocked_titles` (legacy):** If rollout keys absent, falls back to the single combined list from UI `titleBlocklist`.
- **Senior PM allowed** when stated required years ≤ `experience_range.max`.
- **Solo PM trap:** `scripts/solo_pm_gate.py` when `preferences.avoid_solo_pm_trap` is true (`FR-189`).
- **Entry-level / 0-to-1:** Reject when `no_zero_to_one` is true.

### 2.2 Experience & Constraints

- **Years required:** `seniority_gate.py` parses requirements-anchored phrases; ignores incidental year figures in prose (`FR-244`). Reject when required years **exceed** `experience_range.max`. Exactly max is allowed.
- **Blocked industries:** `scripts/industry_gate.py` at scout + batch (`FR-170`).
- **Blocked companies:** `blocked_companies` in prefs — zero-token reject before fit (`FR-247` / CR-054).
- **Industry / customer base:** Do **NOT** instant-kill for vertical or B2C/B2B mismatch alone (`FR-192`). Domain gaps may reduce structured score (max −10 penalty) or appear in RiskFlags.
- **AI tools vs AI PM:** Reject only when the role requires owning ML model development, not Copilot/workflow mentions.

### 2.3 Location & Setting Gate

Enforced deterministically by `scripts/zero_shot_classifier.py` (`FR-243`) before LLM:

- **Home base:** San Diego, CA area.
- **Remote US:** Allowed when JD offers Remote / work-from-anywhere for US hiring.
- **Multi-city + Remote:** US office cities listed **with** Remote → **REMOTE-ELIGIBLE**; do not kill for non-SD cities when Remote is explicit.
- **On-site / Hybrid only:** Must be within ~50 miles of San Diego. Reject non-SD US cities (NYC, Chicago, Atlanta, Seattle, etc.) when Remote is **not** offered.
- **Canada in-person:** Reject onsite/hybrid roles requiring Canada presence without SD-remote eligibility.
- **EST/CST-only remote:** Reject when remote is limited to Eastern/Central time zones only (candidate is Pacific).
- **Pre-verified override:** When prompt includes `PRE-VERIFIED LOCATION POLICY: REMOTE_OK` or `SD_LOCAL_OK`, skip location re-scoring.

---

## 3) Stage B: Structured Fit (Default — CR-053)

Implemented in `scripts/structured_fit.py`. LLM must **not** return a holistic integer score.

1. Extract must-have criteria from JD (skills, seniority signals, domain requirements).
2. For each criterion, LLM returns judgment: `yes` | `partial` | `no` with brief evidence (no numbers).
3. Python computes weighted score from judgments + tier weights.
4. **Domain penalty:** Required domain experience the candidate lacks → up to **−10** on total (not a zero-token gate).
5. **Confidence routing:** Low-confidence structured results may route to manual review when `min_confidence_score` is configured.
6. **Anchor hits:** `fit_policy.apply_anchor_floor` appends `anchor_hits_*` to **RiskFlags only** — **no score promotion** (retired `FR-188` promotion behavior).

Decision: **YES** when score ≥ `min_fit_score` and mandatory gates passed; otherwise **NO**.

---

## 4) Stage B: Legacy LLM Scoring (Fallback)

Used when `STRUCTURED_FIT=0` or structured path yields no result. Holistic 0–100 on four buckets:

### A) Organizational Maturity (0–25)
### B) Seniority & Tenure Fit (0–25)
### C) Technical & Execution Depth (0–25)
### D) Bridge Alignment (0–25)

**Penalties:** Solo/founding trap −50 only when no eng/design/data structure.

**Two-anchor rule:** YES requires ≥2 overlaps with `required_anchors` when enforced (`ANCHOR_GATE_ENABLED` or LLM).

**Thresholds (legacy rubric):** ≥85 strong YES; 75–84 conditional YES; &lt;75 NO.

---

## 5) Output Requirements (Human + JSON)

*Constraints: No em-dashes, no transition fluff.*

```text
Decision: YES/NO
Score: [0-100]
Confidence: High/Medium/Low
Summary: [Max 25 words]

Top fit reasons:
- [Reason 1]
- [Reason 2]

Risk flags:
- [Risk 1]
- [anchor_hits_* when applicable]
```

---

## 6) Pipeline Integrity (CR-054)

Post-draft audit must converge. Non-convergence raises in `drafting_engine.py` → batch reports `passed: false` and restores pre-audit submission files (`FR-246`).
