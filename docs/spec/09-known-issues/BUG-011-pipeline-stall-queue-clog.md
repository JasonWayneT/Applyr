# Known Issue: BUG-011 Pipeline Stall on LLM Failure and Queue Clogging Loop

## Metadata

- Bug ID: `BUG-011`
- Status: proposed
- Severity: critical
- Found in: v6.2
- Fixed in: pending
- Related requirements: `FR-035`, `FR-065`, `FR-068`

## Current behavior

1. **Pipeline Stall on LLM Failure:** When a local LLM call fails (e.g. returns empty, times out, or triggers a JSON parse error), the batch pipeline `scripts/batch_pipeline.py` logs an error and executes a silent `continue`. Because it does not update the database state of the job (leaving it as `New`/`Drafted`) and does not remove the `.txt` staging file from the `jobs/` directory, the job is retried immediately on the next pipeline execution. This stalls the pipeline at the first failing job (e.g., Agilent).
2. **Re-Evaluation of Processed Jobs:** When a job is rejected (either at the keyword pre-filter gate or due to a fit score below the threshold), the pipeline deletes the job from the database `jobs` table and inserts it into `stale_jobs` table. However, it leaves the raw `.txt` file in the `jobs/` directory. On subsequent pipeline runs, because the pipeline only checks for the status of the job in the active `jobs` table (which is missing, returning `None`), it treats the job as completely new and re-evaluates it. This causes a massive waste of API tokens and local resources, and the queue size never decreases (always stuck at 398 jobs).
3. **Fallback Exhaustion Stalls:** When Ollama is unresponsive or slow, the local provider fails and triggers `call_llm` to fall back to Gemini. However, if the Gemini API key is exhausted (`429 RESOURCE_EXHAUSTED`), Gemini also fails and returns empty/None, causing the JSON parser to crash and triggering the stall loop above.

## Expected behavior

1. **Failure State Tracking:** If the evaluation of a job description fails consistently due to LLM errors or JSON parse failures, its status in the SQLite `jobs` table must be updated to `'Failed'` (or `'Error'`) and saved. On subsequent pipeline runs, any job with a status of `'Failed'` or `'Error'` must be skipped cleanly.
2. **Queue File Cleanup (Consumption):** Staging files in the `jobs/` directory are intended purely for ingestion. Once a job has been fully processed (whether it is keyword-rejected, low-score rejected, or successfully drafted), the pipeline must cleanly delete its `.txt` file from the `jobs/` directory. If it fails due to an LLM error, it should update its database status to `'Failed'` to prevent future retries, and optionally delete or archive the `.txt` file.
3. **Queue Stale Checking:** The pipeline should query the `stale_jobs` table before evaluating a job to verify that the job is not already in the stale list. If its URL is found in `stale_jobs`, the job should be skipped and its `.txt` file deleted immediately.

## Root cause

1. In `scripts/batch_pipeline.py` (lines 269-271), if `evaluate_job_fit` returns `None`, a `continue` is executed with no state modification.
2. The pipeline does not remove processed `.txt` files from the `jobs/` directory upon keyword rejection, fit rejection, or asset drafting.
3. The database status checking in `scripts/batch_pipeline.py` does not inspect the `stale_jobs` table or skip jobs that were already deleted from `jobs` and moved to `stale_jobs`.

## Fix Implementation

1. **Delete File on Success/Rejection:** Update `scripts/batch_pipeline.py` to delete the `.txt` file from `jobs/` as soon as it is keyword-rejected, fit-rejected, or successfully drafted (i.e., at all terminal paths of the process loop).
2. **Register Failures in Database:** Update the `if not result:` block in `scripts/batch_pipeline.py` to write `status = 'Failed'` for the job in the `jobs` database table and commit before doing `continue`, or delete the `.txt` file to prevent clogging.
3. **Check `stale_jobs` Table:** Add a check during initial database status resolution to see if the job's URL (extracted from the first line of the `.txt` file) exists in `stale_jobs`. If it does, skip the job and delete the `.txt` file.

## Verification

- Run the pipeline and verify that processed JDs (keyword rejected, low score, and successful drafts) have their `.txt` files deleted from `jobs/`.
- Verify that LLM parsing errors or timeouts update the job's DB status to `'Failed'` so they are not retried on the next run.
- Confirm that the total job queue count (398) decreases continuously as the pipeline runs.
