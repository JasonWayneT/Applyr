// CR-072 Story 2.4 — dry-run flag, stored in profiles (per CR-015), on by default. Deliberately fails
// open to "dry run" on any read error or missing row: a fresh install, a malformed value, or a DB read
// failure should never silently enable real writes.
import type BetterSqlite3 from 'better-sqlite3';

const DRY_RUN_KEY = 'gmail_sync_dry_run';

export function isDryRunEnabled(db: BetterSqlite3.Database): boolean {
  const row = db.prepare('SELECT value FROM profiles WHERE key = ?').get(DRY_RUN_KEY) as
    | { value: string }
    | undefined;
  if (!row) return true;
  try {
    const parsed = JSON.parse(row.value) as { enabled?: boolean };
    return parsed.enabled !== false;
  } catch {
    return true;
  }
}

/** Manual, deliberate action only — Jason flips this off himself after reviewing the dry-run log over
 *  the trial period (CR-072 Decision point 6). Nothing in this CR calls this automatically. */
export function setDryRunEnabled(db: BetterSqlite3.Database, enabled: boolean): void {
  db.prepare('INSERT OR REPLACE INTO profiles (key, value) VALUES (?, ?)').run(
    DRY_RUN_KEY,
    JSON.stringify({ enabled }),
  );
}
