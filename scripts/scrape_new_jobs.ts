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
  const page = await context.newPage();

  for (const job of jobs) {
    if (!job.url) {
      console.log(`Skipping ${job.company} - No URL`);
      continue;
    }

    try {
      console.log(`Scraping ${job.company} from ${job.url}...`);
      await page.goto(job.url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await new Promise(r => setTimeout(r, 3000));

      // Extract the main content/text
      const text = await page.evaluate(() => {
        // Try to target common job description containers
        const selectors = [
          '.job-description', '#job-description', '.description', 
          '#description', '.JobDescription_jobDescription',
          'main', 'article', 'body'
        ];
        for (const sel of selectors) {
          const el = document.querySelector(sel);
          if (el && el.innerText.length > 500) {
            return el.innerText;
          }
        }
        return document.body.innerText;
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
    }
  }

  await browser.close();
  db.close();
  console.log('Finished scraping descriptions.');
}

run().catch(console.error);
