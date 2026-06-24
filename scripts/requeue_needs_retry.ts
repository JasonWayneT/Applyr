/**
 * Re-queues jobs marked "Needs Retry" into the pipeline before scrape/evaluate.
 * Implements CR-011, FR-035.
 */
import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.join(__dirname, '..');
const DB_PATH = path.join(PROJECT_ROOT, 'data/jobagent.sqlite');
const JOBS_DIR = path.join(PROJECT_ROOT, 'jobs');
const SUBMISSIONS_DIR = path.join(PROJECT_ROOT, 'data/submissions');
const MAX_AUTO_RETRIES = 3;

function resolveSubmissionFolder(company: string): string | null {
  const slug = company.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  const direct = path.join(SUBMISSIONS_DIR, slug);
  if (fs.existsSync(direct)) return direct;

  if (!fs.existsSync(SUBMISSIONS_DIR)) return null;
  const stripped = company.toLowerCase().replace(/[^a-z0-9]/g, '');
  for (const name of fs.readdirSync(SUBMISSIONS_DIR)) {
    const full = path.join(SUBMISSIONS_DIR, name);
    if (!fs.statSync(full).isDirectory()) continue;
    if (name.toLowerCase().replace(/[^a-z0-9]/g, '') === stripped) return full;
  }
  return null;
}

async function run() {
  const db = new Database(DB_PATH);

  db.prepare(`UPDATE jobs SET status = 'Needs Retry' WHERE status = 'Failed'`).run();

  const jobs = db.prepare(`
    SELECT id, company, title, url, COALESCE(retry_count, 0) AS retry_count
    FROM jobs WHERE status = 'Needs Retry'
  `).all() as { id: string; company: string; title: string; url: string | null; retry_count: number }[];

  if (jobs.length === 0) {
    console.log('No jobs marked Needs Retry.');
    db.close();
    return;
  }

  console.log(`Re-queuing ${jobs.length} job(s) marked Needs Retry...`);
  fs.mkdirSync(JOBS_DIR, { recursive: true });

  let toDrafted = 0;
  let toNew = 0;
  let skipped = 0;

  const setDrafted = db.prepare(`UPDATE jobs SET status = 'Drafted' WHERE id = ?`);
  const setNew = db.prepare(`UPDATE jobs SET status = 'New' WHERE id = ?`);

  for (const job of jobs) {
    if (job.retry_count >= MAX_AUTO_RETRIES) {
      console.log(`  -> Skip ${job.company} — max auto-retries (${MAX_AUTO_RETRIES}) reached.`);
      skipped++;
      continue;
    }

    const companyFilename = job.company.replace(/[^a-z0-9]+/gi, '_').trim();
    const stagingPath = path.join(JOBS_DIR, `${companyFilename}_${job.id.slice(0, 8)}.txt`);
    const folder = resolveSubmissionFolder(job.company);
    const originalJd = folder ? path.join(folder, 'Original_JD.txt') : null;

    if (originalJd && fs.existsSync(originalJd)) {
      let content = fs.readFileSync(originalJd, 'utf-8');
      if (job.url && !content.trimStart().startsWith('URL:')) {
        content = `URL: ${job.url}\n\n${content}`;
      }
      fs.writeFileSync(stagingPath, content, 'utf-8');
      setDrafted.run(job.id);
      console.log(`  -> ${job.company}: restored JD → Drafted (${path.basename(stagingPath)})`);
      toDrafted++;
    } else if (job.url && !job.url.startsWith('local://')) {
      setNew.run(job.id);
      console.log(`  -> ${job.company}: will re-scrape → New`);
      toNew++;
    } else {
      console.log(`  -> Skip ${job.company} — no saved JD or URL to requeue.`);
      skipped++;
    }
  }

  console.log(`[REQUEUE_DONE] ${toDrafted} → Drafted, ${toNew} → New, ${skipped} skipped.`);
  db.close();
}

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
