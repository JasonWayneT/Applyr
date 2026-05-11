import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

const row = db.prepare("SELECT COUNT(*) as count FROM jobs WHERE status = 'New'").get();
console.log(`Jobs with status 'New': ${row.count}`);

const staleRow = db.prepare("SELECT COUNT(*) as count FROM stale_jobs").get();
console.log(`Total in stale_jobs: ${staleRow.count}`);

const recentStale = db.prepare("SELECT * FROM stale_jobs ORDER BY created_at DESC LIMIT 5").all();
console.log('Recent stale jobs:', JSON.stringify(recentStale, null, 2));

if (row.count > 0) {
  const jobs = db.prepare("SELECT id, company, url FROM jobs WHERE status = 'New' LIMIT 5").all();
  console.log('Sample:', JSON.stringify(jobs, null, 2));
}
db.close();
