# CR-099 - Safe Historical Authoring-Defect Baseline

**Status:** Implemented, 2026-08-24

## Purpose

Provide a conservative way to learn from archived authoring evidence without
contaminating CR-097's live occurrence ledger or its post-launch measurement.

## Contract

- `scripts/import_historical_defects.py` writes only
  `data/authoring_defect_historical_baseline.json`.
- The importer reads structured `stage1_first_draft/verify_history.json`
  records only. It does not infer defects from final documents or free-form
  manifest prose.
- Imported records begin as `needs_review`.
- Confirmation requires an explicit note and confirmer.
- Every record permanently carries `historical_verify_history` provenance.
- Historical records are always excluded from live promotion and the
  post-launch ten-submission metric, including after confirmation.
- Stable record IDs make repeated scans idempotent.

## Usage

```text
python scripts/import_historical_defects.py --scan
python scripts/import_historical_defects.py --status
python scripts/import_historical_defects.py --confirm HIST-XXXXXXXXXX --by jason --note "..."
```

This is an informational baseline, not a retroactive CR-097 occurrence stream.
