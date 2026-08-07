// CR-072 Story 2.1 — persisted "already processed" tracking for the Gmail intake sync, so a message
// under a label is never reprocessed on the next sync pass. Tracks processed message ids per label
// (not a single global cursor) since Epic 2 only ever reads the Incoming catch-all today, but nothing
// here assumes that stays true.
import type BetterSqlite3 from 'better-sqlite3';

export interface EmailSyncCursor {
  hasProcessed(label: string, messageId: string): boolean;
  markProcessed(label: string, messageId: string): void;
}

const PROFILE_KEY = 'gmail_sync_cursor';

export function createEmailSyncCursor(db: BetterSqlite3.Database): EmailSyncCursor {
  function load(): Record<string, string[]> {
    const row = db.prepare('SELECT value FROM profiles WHERE key = ?').get(PROFILE_KEY) as
      | { value: string }
      | undefined;
    return row ? (JSON.parse(row.value) as Record<string, string[]>) : {};
  }

  function save(state: Record<string, string[]>): void {
    db.prepare('INSERT OR REPLACE INTO profiles (key, value) VALUES (?, ?)').run(
      PROFILE_KEY,
      JSON.stringify(state),
    );
  }

  function hasProcessed(label: string, messageId: string): boolean {
    const state = load();
    return (state[label] ?? []).includes(messageId);
  }

  // Writes through immediately (not batched/cached) so a mid-batch crash never loses a record of what
  // was already handled — at most it causes a harmless reprocess-and-skip on next run, never a missed
  // duplicate-write. Personal-mailbox volume makes the per-call reload/rewrite cost irrelevant.
  function markProcessed(label: string, messageId: string): void {
    const state = load();
    const ids = state[label] ?? [];
    if (!ids.includes(messageId)) {
      state[label] = [...ids, messageId];
      save(state);
    }
  }

  return { hasProcessed, markProcessed };
}
