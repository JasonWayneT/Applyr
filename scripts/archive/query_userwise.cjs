const Database = require('better-sqlite3');
const path = require('path');
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

const res = db.prepare("SELECT id, company, title, url FROM jobs WHERE company LIKE '%Userwise%'").all();
console.log(JSON.stringify(res, null, 2));
