import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

const backlog = db.prepare("SELECT company, title, score, summary FROM jobs WHERE status = 'Backlog'").all();
console.log("Backlog Jobs:");
console.log(JSON.stringify(backlog, null, 2));

const counts = db.prepare("SELECT status, count(*) as count from jobs group by status").all();
console.log("\nStatus Counts:", counts);

db.close();
