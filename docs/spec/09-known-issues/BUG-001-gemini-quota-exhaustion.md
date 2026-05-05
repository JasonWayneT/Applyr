# Known Issue: BUG-001 Gemini Quota Exhaustion

## Metadata

- Bug ID: `BUG-001`
- Status: fixed
- Severity: high
- Found in: v3.1
- Fixed in: v3.2
- Related requirements: `INT-001`

## Current behavior

The pipeline fails with `429: Resource has been exhausted` when using `gemini-2.5-flash`.

## Expected behavior

The pipeline should process 10+ jobs sequentially without hitting rate limits on the free/standard tier.

## Root cause

`gemini-2.5-flash` (experimental) has significantly lower rate limits than the stable `gemini-flash-latest`.

## Verification

- **Fixed in:** `scripts/utils.py` by updating `DEFAULT_MODEL`.
- **Result:** Pipeline successfully processed 20 jobs after change.
