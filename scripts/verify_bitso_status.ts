import Database from 'better-sqlite3';
const db = new Database('jobagent.sqlite');
const rows = db.prepare("SELECT company, status FROM jobs WHERE LOWER(company) LIKE '%bitso%'").all();
console.log("SEARCH RESULT:", rows);
db.close();
