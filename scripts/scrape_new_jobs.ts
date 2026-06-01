import { chromium } from 'playwright-extra';
import stealth from 'puppeteer-extra-plugin-stealth';
import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { extractJobDescriptionFromPage, MIN_JD_CHARS } from './extract_job_page.js';

chromium.use(stealth());

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function run() {
  const db = new Database(path.join(__dirname, '../jobagent.sqlite'));
  const jobs = db.prepare("SELECT id, company, title, url FROM jobs WHERE status = 'New'").all() as any[];

  if (jobs.length === 0) {
    console.log('No new jobs to scrape.');
    return;
  }

  console.log(`Scraping descriptions for ${jobs.length} new jobs...`);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();

  for (const job of jobs) {
    if (!job.url || job.url.startsWith('local://')) {
      console.log(`Skipping ${job.company} - ${!job.url ? 'No URL' : 'Local Mock URL'}`);
      continue;
    }

    try {
      console.log(`Scraping ${job.company} from ${job.url}...`);
      const text = await extractJobDescriptionFromPage(context, job.url, MIN_JD_CHARS);

      if (text && text.length > MIN_JD_CHARS) {
        const companyFilename = job.company.replace(/[^a-z0-9]+/gi, '_').trim();
        const jdPath = path.join('jobs', `${companyFilename}_${job.id.slice(0, 8)}.txt`);
        fs.writeFileSync(jdPath, `URL: ${job.url}\n\n${text}`, 'utf-8');
        console.log(`  -> Saved ${jdPath} (${text.length} chars)`);

        db.prepare("UPDATE jobs SET status = 'Drafted', jd_text = ? WHERE id = ?").run(text, job.id);
      } else {
        console.log(`  -> Text extraction too short or empty for ${job.company}.`);
      }
    } catch (e: any) {
      console.error(`  -> Failed to scrape ${job.company}: ${e.message}`);
      if (e.message && e.message.includes('interrupted by another navigation')) {
        console.warn(`  [BUG-007] Detected dead/redirected link for ${job.company}. Archiving to stale_jobs.`);
        try {
          db.prepare('INSERT OR IGNORE INTO stale_jobs (url, company, title) VALUES (?, ?, ?)').run(job.url, job.company, job.title);
          db.prepare('DELETE FROM jobs WHERE id = ?').run(job.id);
          console.log(`  -> Successfully moved dead link to stale_jobs and removed from active queue.`);
        } catch (dbErr) {
          console.error(`  -> Database operation failed while handling dead link:`, dbErr);
        }
      }
    }
  }

  await browser.close();
  db.close();
  console.log('Finished scraping descriptions.');
}

run().catch(console.error);
