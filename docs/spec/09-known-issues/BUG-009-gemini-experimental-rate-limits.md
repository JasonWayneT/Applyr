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

## Fix Implementation (v6.1.1)

Initially switched default to **`gemini-2.0-flash`** to escape Gemini 2.5 experimental 20 RPD caps.

## Regression (May 2026)

Google AI Studio now returns **`limit: 0`** for `generate_content_free_tier_requests` on **`gemini-2.0-flash`** and **`gemini-2.0-flash-lite`** for many projects — the model is not available on the free tier at all (429 with "quota exceeded" is misleading). **`gemini-2.5-flash`** and **`gemini-2.5-flash-lite`** still work on free tier.

## Current fix

Default cloud model is **`gemini-2.5-flash-lite`** in `scripts/utils.py`, `scripts/research-engine.py`, and `scripts/test_llm.py`. Check live limits at [AI Studio rate limits](https://aistudio.google.com/rate-limit).

## Verification

- **Dry Run Connect:** Executed `scripts/test_llm.py` which proved the API key accesses and executes content synthesis successfully on the `gemini-2.0-flash` endpoint.
