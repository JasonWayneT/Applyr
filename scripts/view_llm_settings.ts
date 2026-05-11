import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

const row = db.prepare("SELECT value FROM profiles WHERE key = 'llm_settings'").get() as any;
if (row) {
  console.log("Current LLM Settings JSON:");
  console.log(row.value);
} else {
  console.log("Key 'llm_settings' not found in profiles table.");
}

db.close();
