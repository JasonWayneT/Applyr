# CR-052 — Private Data Consolidation

**Status:** Implemented  
**Date:** 2026-06-24  
**Type:** Infrastructure / Developer Experience

---

## Problem

Private runtime data was spread across three root-level locations:

- `submissions/` — tailored application assets per company
- `archive/` — archived applications
- `jobagent.sqlite` — the primary database (API keys, jobs, pipeline state)

This meant syncing the application between devices required tracking four separate things (the above three plus `data/` personal files). There was no single folder that captured the full private state.

Additionally:
- The public GitHub repo was cluttered with duplicate root-level docs, stale files, and accidentally-tracked personal notes.
- `scripts/utils.py` `ARCHIVE_DIR` diverged from the path actually used by all archive scripts.
- CI smoke tests failed on every push because the public repo audit script ran before `setup-python` on ubuntu-latest.
- `POST /api/stream/local-model` crashed because it read from `.agent/llm_settings.json` which does not exist; LLM settings live in SQLite.

---

## Solution

**Consolidate all private data under `data/`:**

```
data/
  jobagent.sqlite       ← moved from root
  submissions/          ← moved from root
  archive/              ← moved from root
  workExperience.md     ← already here
  master_claims.json    ← already here
  ... (all personal files)
```

Google Drive sync of `data/` is now sufficient to move the full application state between devices.

**Secondary fixes included in this CR:**

- Fix CI smoke test ordering (`setup-python` before audit script)
- Fix `server/routes/system.ts` to read LLM settings from SQLite profiles table
- Align `scripts/utils.py` `ARCHIVE_DIR` to `data/archive/submissions`
- Remove accidentally-tracked files: `data/thinking/`, `_bmad-output/`, root duplicate docs
- Move example files to `data/` to colocate with their real counterparts

---

## Files Changed

**Path constants updated (64 files total):**
- `server/db.ts` — DB_PATH
- `server/shared.ts` — SUBMISSION_DIR, ARCHIVE_DIR
- `server/routes/jobs/files.ts` — inline dbPath
- `scripts/utils.py` — SUBMISSIONS_DIR, ARCHIVE_DIR, DB_PATH (new module-level constant)
- 20+ Python scripts — local db_path / SUBMISSIONS_DIR / ARCHIVE_DIR definitions
- 22 TypeScript/MJS scripts — path.join and Database() constructor paths

**Configuration:**
- `.gitignore` — swap `submissions/`, `archive/` patterns to `data/submissions/`, `data/archive/`
- `package.json` — simplify tsx watch excludes to single `--exclude "data/**"`
- `.github/workflows/smoke.yml` — fix setup-python ordering

**Bug fixes:**
- `server/routes/system.ts` — replace fs.readFileSync with SQLite query

---

## Cross-Device Setup (Post-CR)

New device setup:
1. `git clone https://github.com/JasonWayneT/Applyr.git`
2. `npm install && pip install -r requirements.txt`
3. Copy `data/` from Google Drive (or wait for sync)
4. `npm run dev`

No private repo, no hosted database, no environment configuration beyond what's in `data/jobagent.sqlite`.
