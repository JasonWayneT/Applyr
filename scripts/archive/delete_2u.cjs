const Database = require('better-sqlite3');
const path = require('path');
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

const select = db.prepare("SELECT id, company, title FROM jobs WHERE company LIKE '%2U%' OR company = '2u'").all();
console.log('Found 2U jobs:', JSON.stringify(select, null, 2));

const res = db.prepare("DELETE FROM jobs WHERE company LIKE '%2U%' OR company = '2u'").run();
console.log(`Successfully deleted 2U job(s)! Changes: ${res.changes}`);
