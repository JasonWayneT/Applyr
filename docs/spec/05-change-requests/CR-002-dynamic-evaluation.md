# CR-002: Dynamic Candidate Evaluation Engine

## Metadata
- **Status**: Approved
- **Date**: May 7, 2026
- **Author**: JobAgent (via SDD enforcement)
- **Related Requirements**: `FR-039`

## Problem
The evaluation and gating rules were hardcoded in `.agent/rules/job_fit_engine.md` specific to Jason Taylor's experience. If a user edited `data/candidate_preferences.json`, it was completely ignored by Python, and changing personas was impossible. Additionally, the pre-filter zero-token keyword gate was static, resulting in unnecessary LLM invocations for roles with blocklisted titles.

## Decision
Refactor the evaluation process to actively consume `data/candidate_preferences.json` as the source of truth:

1. **Rubric Generalization**: Refactor `.agent/rules/job_fit_engine.md` into a generic assessment rubric that refers to "Injected Candidate Preferences" instead of hardcoding Jason Taylor.
2. **Dynamic Zero-Token Gating**: Update Python to load `data/candidate_preferences.json` and perform a fast, zero-token check to reject jobs whose titles contain any of the `blocked_titles` before hitting the LLM.
3. **Dynamic Prompt Construction**: Update `evaluate_job_fit` in `batch_pipeline.py` to load and inject the candidate preferences from JSON into the prompt, making the decision engine 100% dynamic.

## Implementation Impact
- `utils.py`: Define `load_candidate_preferences` and expose path.
- `batch_pipeline.py`: Modify `passes_jd_keyword_gate` and `evaluate_job_fit` to load and pass dynamic preferences.
- `.agent/rules/job_fit_engine.md`: Redraft as a generic instruction template.
