import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

const primary = 'ministral-3-14b:latest';
const fallback = 'gemma4-e4b:latest';

console.log("Configuring Dual-Tier Local Failover...");
const row = db.prepare("SELECT value FROM profiles WHERE key = 'llm_settings'").get() as any;
if (row) {
  const settings = JSON.parse(row.value);
  settings.localModel = primary;
  settings.localFallbackModel = fallback;
  
  console.log(`PRIMARY: ${primary}`);
  console.log(`FALLBACK: ${fallback}`);
  
  db.prepare("UPDATE profiles SET value = ? WHERE key = 'llm_settings'").run(JSON.stringify(settings));
  console.log("\nSuccessfully deployed dual-model configuration registry!");
}

db.close();
