import { chromium } from 'playwright-extra';
import stealth from 'puppeteer-extra-plugin-stealth';
import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

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
    if (!job.url) {
      console.log(`Skipping ${job.company} - No URL`);
      continue;
    }

    // Create a FRESH page for each job to isolate network state and prevent cross-job navigation leakage
    const page = await context.newPage();

    try {
      console.log(`Scraping ${job.company} from ${job.url}...`);
      await page.goto(job.url, { waitUntil: 'domcontentloaded', timeout: 45000 });
      
      // Wait a bit longer for multi-hop redirects common on aggregator sites
      await new Promise(r => setTimeout(r, 6000));

      // Extract the main content/text
      const text = await page.evaluate(() => {
        // Try to target common job description containers
        const selectors = [
          '.job-description', '#job-description', '.description', 
          '#description', '.JobDescription_jobDescription',
          'main', 'article', 'body'
        ];
        for (const sel of selectors) {
          const el = document.querySelector(sel) as HTMLElement | null;
          if (el && el.innerText.length > 500) {
            return el.innerText;
          }
        }
        return document.body ? document.body.innerText : "";
      });

      if (text && text.length > 200) {
        // Write the JD text to jobs/[Company].txt
        const companyFilename = job.company.replace(/[^a-z0-9]+/gi, '_').trim();
        const jdPath = path.join('jobs', `${companyFilename}_${job.id.slice(0, 8)}.txt`);
        fs.writeFileSync(jdPath, `URL: ${job.url}\n\n${text}`, 'utf-8');
        console.log(`  -> Saved ${jdPath} (${text.length} chars)`);

        // Update job status in DB to Drafted
        db.prepare("UPDATE jobs SET status = 'Drafted' WHERE id = ?").run(job.id);
      } else {
        console.log(`  -> Text extraction too short or empty for ${job.company}.`);
      }
    } catch (e: any) {
      console.error(`  -> Failed to scrape ${job.company}: ${e.message}`);
      // Implements BUG-007: Handle dead links triggering instant redirects/interrupted navigation
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
    } finally {
      // Always close the page to free up memory and end pending network activity
      await page.close().catch(() => {});
    }
  }

  await browser.close();
  db.close();
  console.log('Finished scraping descriptions.');
}

run().catch(console.error);
