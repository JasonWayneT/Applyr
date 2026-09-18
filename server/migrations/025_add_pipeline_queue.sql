-- CR-119 / DATA-006 / FR-342 / FR-343: CSV Drop Queue — pipeline tables.
-- Additive only: creates three new tables plus their indexes.
-- Does not ALTER, DROP, or rewrite any existing table (jobs, stage0_skips,
-- contacts, or any prior schema_migrations row).
-- First server boot after this file lands will apply it once (schema_migrations)
-- against the live jobagent.sqlite. All three tables start empty; rows appear
-- only after scripts/ingest_csv_queue.py (Epic 2) deposits them.
-- Safe to re-run (IF NOT EXISTS throughout).
-- Python scripts/pipeline_queue.py:ensure_schema() uses the same DDL so the
-- ingest CLI works when the server is stopped. Story 1.3 adds the anti-drift test.

-- ── pipeline_queue ─────────────────────────────────────────────────────────
-- One row per opportunity. Keyed on slug (UNIQUE). Status is the queue lifecycle
-- value (queued → leased → in_progress → paused/done). last_workflow_status and
-- last_stage are mirror-only columns written from workflow_state.json after a run;
-- they are never used as inputs to a stage decision (CR-119 Decision 2, AC-447).

CREATE TABLE IF NOT EXISTS pipeline_queue (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,

  -- Identity
  slug                 TEXT NOT NULL UNIQUE,
  company              TEXT NOT NULL,
  title                TEXT NOT NULL,
  url                  TEXT,
  url_key              TEXT,
  posting_key          TEXT NOT NULL,

  -- Contacts verbatim from the CSV Networking Contacts cell; NULL when absent.
  -- Never parsed or written to the contacts table in this CR (AC-440, CR-071).
  networking_contacts_raw TEXT,

  -- Provenance back to csv_ingest_ledger
  source_sha256        TEXT,
  source_line          INTEGER,

  -- Folder tracking (pending_review / submissions / archive/skipped)
  folder_root          TEXT NOT NULL,

  -- Queue lifecycle — exactly five values (CR-119 Decision 3)
  status               TEXT NOT NULL CHECK(
                         status IN ('queued', 'leased', 'in_progress', 'paused', 'done')
                       ),

  -- Lease triple (FR-343, AC-441)
  locked_by            TEXT,
  lease_expires_at     TEXT,
  fencing_token        INTEGER NOT NULL DEFAULT 0,

  -- Timestamps
  queued_at            TEXT NOT NULL,
  claimed_at           TEXT,
  started_at           TEXT,
  updated_at           TEXT,

  -- Mirror-only: written from workflow_state.json, never read as a stage input
  last_workflow_status TEXT,
  last_stage           TEXT
);

-- Partial unique index on url_key: mirrors idx_stage0_skips_url_key (016 migration).
-- Two rows with the same non-empty url_key is a dedup collision; allow NULL/empty
-- because URL is absent for some postings (CR-119 Decision 12).
CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_queue_url_key
  ON pipeline_queue(url_key) WHERE url_key IS NOT NULL AND url_key != '';

-- Partial unique index on posting_key: the URL-less dedup guarantee (AC-445).
-- Deliberately NOT unconditional: two genuinely different postings for the same
-- company+title with different URLs must both be allowed. When a url_key is
-- present, URL is the preferred key and posting_key uniqueness does not apply
-- (CR-119 Decision 12).
CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_queue_posting_key
  ON pipeline_queue(posting_key) WHERE url_key IS NULL OR url_key = '';

-- ── csv_ingest_ledger ──────────────────────────────────────────────────────
-- One row per ingested file, keyed on content hash. filename is display-only
-- and is NOT part of any uniqueness constraint (CR-119 Decision 13, AC-438):
-- the same content under two filenames (e.g. applyr_jobs.csv and
-- applyr_jobs (1).csv) produces exactly one row.

CREATE TABLE IF NOT EXISTS csv_ingest_ledger (
  sha256           TEXT PRIMARY KEY,
  filename         TEXT NOT NULL,   -- display only, not unique
  ingested_at      TEXT NOT NULL,
  row_count        INTEGER NOT NULL DEFAULT 0,
  quarantine_count INTEGER NOT NULL DEFAULT 0,
  archive_path     TEXT,
  status           TEXT NOT NULL CHECK(status IN ('ingested', 'file_quarantined'))
);

-- ── csv_quarantine ─────────────────────────────────────────────────────────
-- Holds both file-level and row-level rejections in a single table.
-- scope='file': source_file, error_code, quarantine_reason; line_number IS NULL.
-- scope='row':  all columns populated; line_number is 1-based.
-- One table (not two) because AC-443's quarantine detail view renders one list
-- and the two record shapes differ only by whether line_number is present.

CREATE TABLE IF NOT EXISTS csv_quarantine (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  scope             TEXT NOT NULL CHECK(scope IN ('file', 'row')),
  source_file       TEXT NOT NULL,
  line_number       INTEGER,        -- nullable; NULL for file-scope records
  raw_payload       TEXT,
  error_code        TEXT NOT NULL,
  quarantine_reason TEXT NOT NULL
);
