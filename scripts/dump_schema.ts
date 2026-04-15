import Database from 'better-sqlite3';
import fs from 'fs';
const db = new Database('./openpostings_temp/OpenPostings-main/jobs.db');
const schema = db.prepare("SELECT sql FROM sqlite_schema WHERE type='table'").all();
fs.writeFileSync('schema2.json', JSON.stringify(schema, null, 2));
