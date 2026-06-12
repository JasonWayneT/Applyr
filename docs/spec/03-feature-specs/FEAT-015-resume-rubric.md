# FEAT-015: Deterministic Resume Rubric Scoring

**Status:** Implemented  
**Requirements:** FR-200, FR-201, FR-202  
**Source:** resume_decision_report_2026  

---

## Overview

Scores every compiled resume against a weighted rubric derived from
`resume_decision_report_2026` before PDF export. The score is logged to
`draft_manifest.json` and printed to console. Scores below 60 trigger a
human-review flag but never block pipeline execution.

---

## Rubric Weights

```
Overall = 0.40 × Summary + 0.60 × Experience
```

### Summary (40% of overall)

| Criterion | Weight | Proxy |
|---|---|---|
| Role targeting | 25% | JD req-section tokens present in summary |
| Value proposition | 25% | Summary contains at least one digit/metric |
| Evidence / outcomes | 30% | Count of summary sentences containing a metric (capped at 2) |
| Keyword alignment | 20% | Token overlap between summary and JD req section |

### Experience (60% of overall)

| Criterion | Weight | Proxy |
|---|---|---|
| Relevance | 25% | Average per-bullet req-token overlap |
| Achievement vs duties | 25% | Ratio of bullets starting with a strong past-tense action verb |
| Quantification | 20% | Ratio of bullets containing at least one digit |
| Structure | 15% | All 3 employers present + no overlong bullets (>28 words) |
| Skills integration | 15% | `## CORE COMPETENCIES` section present |

---

## Threshold

- Score >= 60: passes silently (score still logged)
- Score < 60: logged with `[BELOW THRESHOLD — review recommended]` flag
- `STRICT_RUBRIC=1` env var: raises `DraftingPipelineError` when below threshold (opt-in only)

---

## Output

Added to `draft_manifest.json`:

```json
"rubric_score": {
  "overall": 74.3,
  "threshold_flag": false,
  "summary": {
    "score": 68.5,
    "role_targeting": 72.0,
    "value_proposition": 100.0,
    "evidence_outcomes": 50.0,
    "keyword_alignment": 45.0
  },
  "experience": {
    "score": 78.2,
    "relevance": 82.0,
    "achievement_vs_duties": 90.9,
    "quantification": 72.7,
    "structure": 100.0,
    "skills_integration": 100.0
  }
}
```

---

## Implementation

- `scripts/resume_rubric.py` — scoring logic (new file)
- `scripts/draft_compiler.py` — calls `score_resume()` after `check_resume()` passes, before PDF export; writes result to manifest
- No LLM calls; fully deterministic

---

## Known Limitations

- Role targeting and keyword alignment scores are sensitive to JD noise
  (boilerplate "about the company" text inflates the req-token set when
  the JD has no detectable requirements heading).
- `extract_req_section` mitigates this but is not perfect for all JD formats.
- Scores should be treated as directional signals, not absolute thresholds,
  until calibrated against real submission outcomes via Phase 6 logging.
