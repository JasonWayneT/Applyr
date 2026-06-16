/**
 * Backfill jobs/*.txt staging files from Drafted rows (jd_text in DB).
 * Optional --purge closes Drafted rows that fail target_role title scope.
 */
import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { passesTargetRoleTitleScope } from '../shared/domain/gates.js';
import { loadMaterializedScoutPrefs } from '../shared/domain/scoutPrefs.js';
import {
  stagingFileExists,
  writeJobStagingFile,
} from '../server/services/jobStaging.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.join(__dirname, '..');
const DB_PATH = path.join(PROJECT_ROOT, 'jobagent.sqlite');

const purge = process.argv.includes('--purge');

async function run() {
  if (!fs.existsSync(DB_PATH)) {
    console.log('[EXPORT_STAGING] No database found — skipping.');
    return;
  }

  const prefs = loadMaterializedScoutPrefs();
  const targetPrefs = { targetRole: prefs.targetRole, searchTerms: prefs.searchTerms };

  const db = new Database(DB_PATH);
  const rows = db
    .prepare(
      `SELECT id, company, title, url, jd_text
       FROM jobs
       WHERE status = 'Drafted' AND jd_text IS NOT NULL AND LENGTH(TRIM(jd_text)) >= 200`,
    )
    .all() as { id: string; company: string; title: string; url: string | null; jd_text: string }[];

  let exported = 0;
  let skipped = 0;
  let purged = 0;

  const closeJob = db.prepare(`
    UPDATE jobs
    SET status = 'Closed',
        rejection_type = 'Self-Rejected',
        outcome_notes = ?
    WHERE id = ?
  `);

  for (const row of rows) {
    if (!passesTargetRoleTitleScope(row.title, targetPrefs)) {
      if (purge) {
        closeJob.run(
          `Title outside target role scope (${prefs.targetRole}): ${row.title}`,
          row.id,
        );
        purged++;
        console.log(`[PURGE] ${row.title} at ${row.company}`);
      } else {
        skipped++;
      }
      continue;
    }

    if (stagingFileExists(row.company, row.id)) {
      skipped++;
      continue;
    }

    writeJobStagingFile(row.id, row.company, row.url, row.jd_text);
    exported++;
    console.log(`[EXPORT] ${row.company} → jobs/*_${row.id.slice(0, 8)}.txt`);
  }

  db.close();
  console.log(
    `[EXPORT_STAGING_DONE] exported=${exported} skipped=${skipped} purged=${purged} target_role=${prefs.targetRole}`,
  );
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
