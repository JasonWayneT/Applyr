import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

// Upgrade to highest-quality local model (requires ~14GB VRAM free)
// Only run this when on desktop with no other GPU-heavy tasks active.
const biggerModel = 'hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-IQ4_XS';

console.log("Fetching current config...");
const row = db.prepare("SELECT value FROM profiles WHERE key = 'llm_settings'").get() as any;
if (row) {
  const settings = JSON.parse(row.value);
  console.log(`Current model: ${settings.localModel}`);
  settings.localModel = biggerModel;
  
  console.log(`Updating config to use: ${biggerModel}...`);
  db.prepare("UPDATE profiles SET value = ? WHERE key = 'llm_settings'").run(JSON.stringify(settings));
  console.log("Successfully updated LLM settings.");
} else {
  console.error("No config found to update!");
}

db.close();
