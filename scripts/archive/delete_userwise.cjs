const Database = require('better-sqlite3');
const path = require('path');
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

const res = db.prepare("DELETE FROM jobs WHERE id = '575b5f6c-4f98-477c-93cf-206e64a55458'").run();
console.log(`Successfully deleted duplicate Userwise job! Changes: ${res.changes}`);
