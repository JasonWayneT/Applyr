import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

const workingModel = 'gemma4-e4b:latest';

console.log("Reverting config to working fallback due to upstream loading error...");
const row = db.prepare("SELECT value FROM profiles WHERE key = 'llm_settings'").get() as any;
if (row) {
  const settings = JSON.parse(row.value);
  settings.localModel = workingModel;
  
  db.prepare("UPDATE profiles SET value = ? WHERE key = 'llm_settings'").run(JSON.stringify(settings));
  console.log(`Successfully restored working model: ${workingModel}`);
}

db.close();
