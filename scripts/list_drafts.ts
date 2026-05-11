import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

console.log("--- Top 40 Drafted Jobs ordered by most recently inserted/updated? ---");
// Let's peek schema first to know the column name for timestamp.
const info = db.prepare("PRAGMA table_info(jobs)").all();
console.log("Columns:", info.map(c => c.name).join(", "));

const drafts = db.prepare("SELECT company, title, created_at FROM jobs WHERE status = 'Drafted' ORDER BY created_at DESC").all();
console.log(JSON.stringify(drafts, null, 2));

db.close();
