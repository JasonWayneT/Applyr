# Known Issue: BUG-009 Gemini 2.5 Experimental Family Quota Restriction

## Metadata

- Bug ID: `BUG-009`
- Status: fixed
- Severity: critical
- Found in: v6.1
- Fixed in: v6.1.1
- Related requirements: `FR-035`, `FR-040`, `FR-060`

## Current behavior

When the pipeline attempts to execute more than 20 jobs in a 24-hour window using the `gemini-2.5-flash-lite` (or standard) models, Google AI Studio immediately shuts down the endpoint, returning `429 Resource has been exhausted`. This produces hundreds of cascading errors in the background worker pipeline, fully freezing cloud evaluation and drafting operations.

## Expected behavior

The cloud-backed LLM tier should accommodate typical user processing volumes (up to 1,500 requests per day) on the standard Free Tier to support deep-scrapes and batch synthesis.

## Root cause

Google enforces an extremely restrictive, experimental quota of exactly **20 Requests Per Day (RPD)** for all models residing within the brand-new **Gemini 2.5** experimental family (both Standard and Lite). Switching to standard Gemini 2.0 public preview restores the general availability free quota limits.

## Fix Implementation

Downgraded the global default cloud fallback model to **`gemini-2.0-flash`**:
1. Modified `DEFAULT_MODEL` in `scripts/utils.py` to target `"gemini-2.0-flash"`.
2. Updated `scripts/research-engine.py` fallback targeting from `gemini-2.5-flash-lite` to `"gemini-2.0-flash"`.

This restores Jason's limits to **1,500 Requests Per Day** (a 75x expansion) and **15 Requests Per Minute** (a 3x speed expansion).

## Verification

- **Dry Run Connect:** Executed `scripts/test_llm.py` which proved the API key accesses and executes content synthesis successfully on the `gemini-2.0-flash` endpoint.
