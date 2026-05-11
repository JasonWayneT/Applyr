import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';
import crypto from 'crypto';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

// Find recently added stale jobs (those created in the last hour, or just check count)
const recentStale = db.prepare("SELECT * FROM stale_jobs WHERE created_at >= '2026-05-11 20:50:00'").all() as any[];
console.log(`Found ${recentStale.length} recent stale jobs to potentially restore.`);

let restoredCount = 0;
const insertStmt = db.prepare(`
  INSERT OR IGNORE INTO jobs (id, company, title, url, status, created_at)
  VALUES (?, ?, ?, ?, 'New', ?)
`);

const deleteStmt = db.prepare("DELETE FROM stale_jobs WHERE url = ?");

db.transaction(() => {
  for (const job of recentStale) {
    const id = crypto.randomUUID();
    // Insert back as New
    insertStmt.run(id, job.company, job.title, job.url, job.created_at);
    // Remove from stale_jobs so it doesn't duplicate next run
    deleteStmt.run(job.url);
    restoredCount++;
  }
})();

console.log(`Successfully restored ${restoredCount} jobs back to the 'New' queue.`);

db.close();
