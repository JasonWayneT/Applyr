# Archived adversarial payloads (CR-112 Story 4.2)

These `payload_*.txt` files lived under `tests/fixtures/adversarial/` but were never
wired into `scripts/run_adversarial_pressure_test.py`. They are prompt-injection
style JD bodies used as design notes, not executable cases.

They are **not** part of the adversarial runner. Do not treat presence here as
enforcement. Catalog rows that are not programmatic cases are marked
`enforced_by: not this runner` in `docs/spec/INVARIANTS_CATALOG.md`.
