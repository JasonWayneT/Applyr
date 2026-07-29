import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';
import { chromium } from 'playwright-extra';
import stealth from 'puppeteer-extra-plugin-stealth';
import { extractJobDescriptionFromPage, MIN_JD_CHARS } from './extract_job_page.js';

chromium.use(stealth());

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const jobId = process.argv[2];
if (!jobId) {
  console.error('Usage: _scrape_one_job.ts <job_id>');
  process.exit(2);
}

const db = new Database(path.join(__dirname, '../data/jobagent.sqlite'));
const job = db.prepare('SELECT id, company, title, url FROM jobs WHERE id = ?').get(jobId) as
  | { id: string; company: string; title: string; url: string }
  | undefined;

if (!job?.url) {
  console.error('Job or URL not found');
  process.exit(1);
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext();
try {
  console.log(`Scraping ${job.company} from ${job.url}`);
  const text = await extractJobDescriptionFromPage(context, job.url, MIN_JD_CHARS);
  if (!text || text.length < MIN_JD_CHARS) {
    console.error(`Too short: ${text?.length ?? 0} chars`);
    process.exit(1);
  }
  db.prepare("UPDATE jobs SET jd_text = ?, status = 'Drafted' WHERE id = ?").run(text, job.id);
  const companyFilename = job.company.replace(/[^a-z0-9]+/gi, '_').trim();
  const fs = await import('fs');
  const jdPath = path.join(__dirname, '../jobs', `${companyFilename}_${job.id.slice(0, 8)}.txt`);
  fs.writeFileSync(jdPath, `URL: ${job.url}\n\n${text}`, 'utf-8');
  console.log(`Saved ${text.length} chars to DB and ${jdPath}`);
} finally {
  await browser.close();
  db.close();
}
