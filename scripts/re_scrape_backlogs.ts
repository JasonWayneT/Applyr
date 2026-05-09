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
  
  // Find all jobs in 'Backlog' status
  const jobs = db.prepare("SELECT id, company, title, url FROM jobs WHERE status = 'Backlog'").all() as any[];

  if (jobs.length === 0) {
    console.log('No Backlog jobs found.');
    db.close();
    return;
  }

  console.log(`Checking JDs for ${jobs.length} Backlog jobs...`);
  
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  let scrapedCount = 0;

  for (const job of jobs) {
    const companyFilename = job.company.replace(/[^a-z0-9]+/gi, '_').trim();
    const idPrefix = job.id.slice(0, 8);
    const jdPath = path.join(__dirname, '../jobs', `${companyFilename}_${idPrefix}.txt`);

    // Check if the file already exists on disk
    if (fs.existsSync(jdPath)) {
      console.log(`[Skip] ${job.company} - JD already exists at ${jdPath}`);
      // Mark as Drafted so it gets picked up by the batch pipeline
      db.prepare("UPDATE jobs SET status = 'Drafted' WHERE id = ?").run(job.id);
      continue;
    }

    if (!job.url) {
      console.log(`[Skip] ${job.company} - No URL available.`);
      continue;
    }

    try {
      console.log(`\n---> Scraping ${job.company} from ${job.url}...`);
      await page.goto(job.url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await new Promise(r => setTimeout(r, 3000));

      // Extract text content
      const text = await page.evaluate(() => {
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
        return document.body.innerText;
      });

      if (text && text.length > 200) {
        fs.writeFileSync(jdPath, `URL: ${job.url}\n\n${text}`, 'utf-8');
        console.log(`  [SUCCESS] Saved JD to ${jdPath} (${text.length} chars)`);
        
        // Update job status in DB to 'Drafted' so batch_pipeline.py processes it
        db.prepare("UPDATE jobs SET status = 'Drafted' WHERE id = ?").run(job.id);
        scrapedCount++;
      } else {
        console.log(`  [FAILED] Scraped text too short or empty for ${job.company}.`);
      }
    } catch (e: any) {
      console.error(`  [ERROR] Failed to scrape ${job.company}: ${e.message}`);
    }
  }

  await browser.close();
  db.close();
  console.log(`\n==================================================`);
  console.log(`Completed. Scraped/Recovered ${scrapedCount} job descriptions.`);
  console.log(`All jobs have been reset to 'Drafted' status to await batch pipeline processing.`);
  console.log(`==================================================`);
}

run().catch(console.error);
