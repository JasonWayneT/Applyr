import Database from 'better-sqlite3';
const db = new Database('jobagent.sqlite');
const info = db.prepare("UPDATE jobs SET status = 'New', score = NULL, summary = NULL WHERE LOWER(company) = 'bitso'").run();
console.log(`Reset ${info.changes} row(s) for Bitso back to 'New' state for cloud re-drafting.`);
db.close();
