import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

console.log("--- Job Status Breakdown ---");
const counts = db.prepare("SELECT status, COUNT(*) as count FROM jobs GROUP BY status").all();
counts.forEach(row => {
  console.log(`${row.status}: ${row.count}`);
});

console.log("\n--- Submissions Stats ---");
// Check submissions directory contents
import fs from 'fs';
const submissionsDir = path.join(__dirname, '../submissions');
if (fs.existsSync(submissionsDir)) {
  const dirs = fs.readdirSync(submissionsDir).filter(f => fs.statSync(path.join(submissionsDir, f)).isDirectory());
  console.log(`Total Companies in Submissions folder: ${dirs.length}`);
  
  // Check how many have final artifacts like Resume.md
  let completeCount = 0;
  dirs.forEach(dir => {
    const resumePath = path.join(submissionsDir, dir, 'Resume.md');
    if (fs.existsSync(resumePath)) {
       completeCount++;
    }
  });
  console.log(`Completed Packs (have Resume.md): ${completeCount}`);
}

db.close();
