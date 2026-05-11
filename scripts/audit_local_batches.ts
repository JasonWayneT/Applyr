import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

console.log("=== LOCAL LLM BATCH ENGINE AUDIT ===");

// Look at jobs that failed and got moved to stale recently
const recentStale = db.prepare(`
  SELECT company, title, substr(created_at, 12, 8) as time_added 
  FROM stale_jobs 
  WHERE created_at >= datetime('now', '-15 minutes')
  ORDER BY created_at DESC 
  LIMIT 5
`).all();

console.log(`\nFound ${recentStale.length} jobs recently rejected by the gatekeeper:`);
recentStale.forEach(j => console.log(`  - [${j.time_added}] ${j.company}: ${j.title}`));

// Check for any backlog winners from this batch
const recentBacklog = db.prepare(`
  SELECT company, title, score, summary
  FROM jobs 
  WHERE status = 'Backlog' 
  ORDER BY score DESC
`).all();

console.log(`\nFound ${recentBacklog.length} Total Backlog Winners.`);
recentBacklog.forEach(j => console.log(`  - ${j.company} (Score ${j.score}): ${j.summary.slice(0, 80)}...`));

db.close();
