# Known Issue: BUG-002 Batch Pipeline Buffered Output

## Metadata

- Bug ID: `BUG-002`
- Status: fixed
- Severity: medium
- Related requirements: `FR-024`

## Current behavior

Python logs do not appear in the Sync Activity dashboard until the script finishes or a large buffer is filled.

## Expected behavior

Logs should appear in the terminal UI line-by-line as they are generated.

## Root cause

Python's `stdout` is buffered by default when piped.

## Verification

- **Fixed by:** Running pipeline with `python -u` flag (unbuffered).
- **Result:** Real-time log streaming verified in the UI.
