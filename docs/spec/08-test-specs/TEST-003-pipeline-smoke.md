# Test Spec: TEST-003 Pipeline Smoke Regression

## Metadata

- Test ID: `TEST-003`
- Type: integration | smoke
- Status: implemented | manual
- Related requirements: `FR-*` (full pipeline: scout → evaluate → draft → verify), `NFR-*` (pipeline reliability)
- Related acceptance criteria: `AC-*` in `FEAT-001-scouting.md`, `FEAT-002`, `FEAT-009`, `FEAT-010`

## Purpose

Prove that the Python pipeline (`scripts/batch_pipeline.py` and related modules) runs end-to-end without crashing, produces expected outputs for known inputs, and does not reintroduce previously fixed bugs. This is the integration safety net — it runs against the live local environment (SQLite, file system) rather than mocks.

## Preconditions

- Python 3.10+ installed
- `requirements.txt` dependencies installed (`pip install -r requirements.txt`)
- `data/workExperience.md` exists (or `workExperience.example.md` bootstrapped via `python scripts/bootstrap_local_data.py`)
- `data/candidate_preferences.json` exists with valid search criteria
- At least one LLM provider key configured in the local SQLite database, OR the test is run in offline/fixture mode
- Node.js 18+ and SQLite database initialized (`npm run dev` started at least once to seed the DB schema)

## Test groups

### Gate regression fixtures (`REG-08+`)

Each `tests/fixtures/` file represents a real-world job that previously caused a gate to misfire. The smoke test must:

1. Load the fixture job data
2. Run it through all deterministic gates
3. Assert the expected pass/fail result

Any new gate change (per `SDD_PROCESS.md`) must add a corresponding fixture before the code ships.

| Fixture | Expected gate result | Bug it prevents |
|---|---|---|
| Add new fixtures here as bugs are fixed | — | Link to `BUG-*` ID |

### Pipeline invocation (batch mode)

| Check | Expected |
|---|---|
| `python scripts/batch_pipeline.py --mode batch` runs without unhandled exception | Exit code 0 or expected empty-queue exit |
| Pipeline respects `min_fit_score` from `candidate_preferences.json` | No job below threshold proceeds to drafting |
| LLM fallback chain activates correctly when primary provider unavailable | Secondary provider is used; no crash |

### Pipeline invocation (single mode)

| Check | Expected |
|---|---|
| `python scripts/batch_pipeline.py --mode single --job-id <id>` processes a single job | Resume, cover letter, cheat sheet generated in `submissions/` |
| Output files exist and are non-empty | `Resume.md`, `CoverLetter.md`, `Interview_Cheat_Sheet.md` all present |
| PDF compilation completes | Corresponding `.pdf` files generated in `submissions/<company>/` |

### Anti-regression checks

| Known bug | Regression test | `BUG-*` ID |
|---|---|---|
| Gemini quota exhaustion causes silent drop | Pipeline logs `[FALLBACK]` and switches provider; no job lost | Add `BUG-*` ref when filed |
| Batch buffer not flushed on SIGINT | Verify partial batches write to DB before exit | Add `BUG-*` ref when filed |
| Preference fields lost on re-materialize | `materializeJobSearchPrefs()` preserves all existing fields (ADR-005) | Add `BUG-*` ref when filed |

## Steps

1. Run `python scripts/test_smoke_regression.py` from the project root
2. Review output for any FAIL lines
3. On failure: check the failing fixture against the current gate logic in `scripts/domain/gates.ts`
4. If a gate changed intentionally: update the fixture and the corresponding `CR-*` record
5. If a gate regressed: file a `BUG-*` and revert or fix before merge

## Expected result

- All fixture cases produce the expected gate result
- No unhandled exceptions during smoke run
- Exit code 0

## Regression coverage

- Related bug IDs: `BUG-001` through `BUG-016` (see `docs/spec/09-known-issues/`)
- Known failure modes prevented:
  - Gate logic changes silently altering which jobs reach the LLM
  - Provider fallback chain breaking mid-pipeline
  - `candidate_preferences.json` field loss on update

## Automation notes

- Test file: `scripts/test_smoke_regression.py`
- Command: `python scripts/test_smoke_regression.py`
- Fixtures: `tests/fixtures/` — add offline gate fixtures here per `SDD_PROCESS.md`
- Mocking: offline mode uses fixture data; full smoke test requires live LLM keys and SQLite DB
- CI note: full smoke test is not currently wired to CI — add a `--dry-run` flag to enable CI-safe gate-only mode
