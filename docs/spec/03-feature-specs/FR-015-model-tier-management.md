# FR-015 Model Tier Management

## Requirement ID
FR-015

## Summary
Introduce a dynamic model tier manager that selects the appropriate local LLM based on available GPU memory.
1. `model_manager.select_model()` parses `nvidia-smi` output to determine free VRAM.
2. If free VRAM >= 10 GB, return `ministral-3-14b`; otherwise return `gemma4-e4b`.
3. `model_manager.unload_all_models()` sends unload requests to Ollama for **all** loaded models and clears the cache.

## Acceptance Criteria
- The selection logic respects a configurable threshold stored in `config.json`.
- Unload routine guarantees no residual model processes after pipeline execution.
- Logs actions to `logs/model_manager.log`.

## Non‑Functional Requirements
- Selection and unload operations complete within 500 ms.
- No external network calls; uses local `nvidia-smi` and Ollama HTTP API.

## Traceability
- Maps to business rule **Model Tier Management** in the architecture.
- Linked to `FR-015` in the traceability matrix.
