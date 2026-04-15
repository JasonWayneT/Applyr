import Database from 'better-sqlite3';

const dbPath = './jobagent.sqlite';
const db = new Database(dbPath);

console.log('Clearing local jobs database...');
const stmt = db.prepare('DELETE FROM jobs');
const info = stmt.run();

console.log(`Successfully deleted ${info.changes} jobs.`);
