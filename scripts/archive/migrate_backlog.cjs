const Database = require('better-sqlite3');
const path = require('path');
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

const res = db.prepare("UPDATE jobs SET status = 'Drafted' WHERE status = 'Backlog'").run();
console.log(`Updated ${res.changes} existing backlog jobs to Drafted!`);
