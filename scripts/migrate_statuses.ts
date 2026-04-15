import Database from 'better-sqlite3';

const dbPath = './jobagent.sqlite';
const db = new Database(dbPath);

console.log('Migrating local DB statuses...');
db.prepare(`UPDATE jobs SET status = 'Backlog' WHERE status = 'New'`).run();
db.prepare(`UPDATE jobs SET status = 'Recruiter Screen' WHERE status = 'Screening'`).run();
db.prepare(`UPDATE jobs SET status = 'Core Interviews' WHERE status = 'Interview'`).run();
db.prepare(`UPDATE jobs SET status = 'Offer and Negotiation' WHERE status = 'Offered'`).run();
db.prepare(`UPDATE jobs SET status = 'Closed' WHERE status = 'Rejected'`).run();
console.log('Done.');
