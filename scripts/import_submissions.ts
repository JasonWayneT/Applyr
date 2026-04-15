import fs from 'fs';
import path from 'path';
import Database from 'better-sqlite3';

const dbPath = './jobagent.sqlite';
const db = new Database(dbPath);

const submissionsDir = path.join(process.cwd(), 'submissions');

if (!fs.existsSync(submissionsDir)) {
  console.log('No submissions directory found.');
  process.exit(0);
}

const folders = fs.readdirSync(submissionsDir).filter(f => fs.statSync(path.join(submissionsDir, f)).isDirectory());

console.log(`Found ${folders.length} submission folders.`);

const insertStmt = db.prepare(`
  INSERT INTO jobs (id, company, title, url, score, status, summary, created_at)
  VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
  ON CONFLICT(id) DO UPDATE SET
    company=excluded.company,
    title=excluded.title,
    url=excluded.url,
    status='Applied',
    score=85
`);

let count = 0;

for (const folder of folders) {
  const folderPath = path.join(submissionsDir, folder);
  
  // Create beautiful company name from folder string (e.g. cart_com -> Cart Com, stitch_fix -> Stitch Fix)
  const company = folder.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  let title = 'Product Manager';
  let url = '#';
  let summary = 'Submission generated successfully.';

  // Read metadata.json for URL
  const metaPath = path.join(folderPath, 'metadata.json');
  if (fs.existsSync(metaPath)) {
    try {
      const metaStr = fs.readFileSync(metaPath, 'utf8');
      const meta = JSON.parse(metaStr);
      if (meta.source_url) {
        url = meta.source_url;
      }
    } catch (e) {
      console.warn(`Could not parse metadata for ${folder}`);
    }
  }

  // Read Original_JD.txt to find a better title if possible, looking for "Title: "
  const jdPath = path.join(folderPath, 'Original_JD.txt');
  if (fs.existsSync(jdPath)) {
    try {
      const jdContent = fs.readFileSync(jdPath, 'utf8');
      const lines = jdContent.split('\n').filter(Boolean);
      for (const line of lines.slice(0, 10)) {
        if (line.match(/^Title:|^Job Title:/i)) {
          title = line.replace(/^Title:|^Job Title:/i, '').trim();
          break;
        }
      }
    } catch (e) {
      console.warn(`Could not read JD for ${folder}`);
    }
  }
  
  // Fallback: Check Research packet for title
  const researchPath = path.join(folderPath, 'Research_Packet.md');
  if (fs.existsSync(researchPath) && title === 'Product Manager') {
     try {
       const content = fs.readFileSync(researchPath, 'utf8');
       const match = content.match(/## Role:\s*(.*)/);
       if (match && match[1]) {
           title = match[1].trim();
       }
     } catch (e) {
       // Ignore
     }
  }

  // Insert into DB
  try {
    const id = `${company.toLowerCase().replace(/[^a-z0-9]/g, '')}_${Date.now()}_${Math.floor(Math.random()*1000)}`;
    insertStmt.run(id, company, title, url, 85, 'Applied', summary);
    console.log(`Inserted: ${company} - ${title}`);
    count++;
  } catch (err) {
    console.error(`Failed to insert ${company}:`, err);
  }
}

console.log(`\nSuccessfully imported ${count} jobs into the database.`);
