# ADR-005: Materialized JSON as Single Pipeline Read Target

## Status

Accepted — implemented in `CR-003`

## Context

The Python pipeline scripts (`batch_pipeline.py`, `utils.py`, `scout_local.ts`) need to read user-configured
search criteria and evaluation thresholds at runtime. The UI stores settings in SQLite via the Express server.
Three options were evaluated for connecting the UI write path to the script read path.

## Options considered

### Option A — Python reads SQLite directly

Python scripts open `jobagent.sqlite` and query the `profiles` table for the `job_search` key.

**Rejected.** This couples the Python layer to the SQLite schema. Any schema change requires updating all
Python scripts. Python already has a sqlite3 dependency for other reasons, but making it the source of truth
for settings creates a bidirectional dependency between the Node server layer and the Python layer. It also
makes the scripts harder to run standalone for testing.

### Option B — Python calls the Express REST API

Python scripts call `GET http://localhost:3000/api/profile/job_search` at startup.

**Rejected.** This creates a circular dependency: the server launches the Python scripts as child processes.
If the Python script calls back to the server, we have a process calling itself. It also means scripts
cannot run if the server is down, and adds a network I/O dependency to every pipeline invocation.

### Option C — Server materializes a JSON file on every UI save (chosen)

When the user saves job search settings, `POST /api/profile/job_search` writes to SQLite **and** calls
`materializeJobSearchPrefs()`, which writes `data/candidate_preferences.json`. Python scripts read only
this file. The SQLite record is the canonical store; the JSON is a materialized view.

**Accepted.** This keeps Python scripts simple (file I/O only, no database or network dependencies).
The JSON file is always consistent with the last UI save. Scripts can be run standalone as long as the
JSON file exists. The transformation between UI camelCase format and Python snake_case format is handled
once, server-side, in `materializeJobSearchPrefs()`.

## Consequences

- `data/candidate_preferences.json` must never be edited manually as a permanent configuration source.
  It is a generated artifact — manual edits will be overwritten on the next UI save.
- Non-UI pipeline parameters (`min_fit_score`, `jd_required_keywords`, `preferences` flags) are preserved
  during materialization by reading the existing JSON before overwriting, so they survive UI saves unchanged.
- Adding a new configurable parameter requires: (1) adding the field to the UI, (2) updating
  `materializeJobSearchPrefs()`, and (3) reading the new field in the relevant script. No schema migrations needed.

## Affected requirements

`FR-046`, `FR-047`, `FR-048`
