# Known Issue: BUG-010 False-Alarm Stderr Errors and Local Self-Audit Resume Corruption

## Metadata

- Bug ID: `BUG-010`
- Status: resolved
- Severity: high
- Found in: v6.2
- Fixed in: v6.2.1
- Related requirements: `FR-023`, `FR-035`, `FR-067`

## Current behavior

1. **False-Alarm Stderr Errors:** Subprocess stderr output is intercepted by the Express orchestrator in `server/scout.ts` and unconditionally logged as `ERROR` under the `Pipeline` prefix in the database and user interface. This logs harmless debug and status info (e.g., `[Model Manager]` or `[LLM]`) as critical pipeline errors.
2. **Local Self-Audit Resume Corruption:** When local provider is selected as `primaryProvider` but Gemini is also configured (`is_local_primary()` returns `False`), the pipeline attempts to run the high-fidelity `llm_verify_claims` audit step. Due to `provider_override=['gemini', 'local']`, it routes this complex audit step to the primary local model (`ministral-3-14b`). The local model is not capable of performing a full-scale resume audit/rewrite, and returns corrupted, unstructured text. This fails zero-tolerance structural QA checks and halts the pipeline with `Sync stopped due to stage error.`

## Expected behavior

1. Harmless status/debug messages written to `stderr` by subprocesses should be filtered and logged as `INFO` or `WARN` in the database and UI, rather than triggering false-alarm critical pipeline `ERROR` entries.
2. The complex, high-fidelity `llm_verify_claims` audit step must always route to cloud providers (e.g., Gemini) when they are configured, completely bypassing unreliable local self-auditing.

## Root cause

1. In `server/scout.ts`, `child.stderr.on('data', ...)` logs any output to stderr as `ERROR` unconditionally.
2. In `scripts/drafting_engine.py`, the `llm_verify_claims` function specifies `provider_override=['gemini', 'local']` which favors the primary local provider when active.

## Fix Implementation

1. **Robust Stderr Filtering:** Introduce a `handleStderr` routing helper in `server/scout.ts` that inspects each line of `stderr`. Lines containing known informational prefixes (`[Model Manager]`, `[LLM]`, `[GUARD]`, etc.) are routed to `logActivity('INFO', ...)`, warning-like lines to `logActivity('WARN', ...)`, and only actual errors/tracebacks are tagged as `logActivity('ERROR', ...)`.
2. **Lock Audit to Cloud:** Modify `llm_verify_claims` in `scripts/drafting_engine.py` to specify `provider_override=['gemini']` (or cloud fallbacks), ensuring that high-fidelity audits always leverage cloud intelligence when configured.

## Verification

- Rerun the pipeline and confirm that informational logs are cleanly parsed as `INFO` and `WARN` in SQLite `activity_log`, and that the resume completes drafting and compiling successfully with no QA checklist failures.
