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
  // Pick 3-5 jobs to test
  const jobs = db.prepare("SELECT id, company, title, url FROM jobs WHERE status = 'New' LIMIT 5").all() as any[];

  if (jobs.length === 0) {
    console.log('No new jobs found for test.');
    return;
  }

  console.log(`Testing FIX on ${jobs.length} jobs...`);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();

  for (const job of jobs) {
    const page = await context.newPage();
    try {
      console.log(`[TEST] Scraping ${job.company} from ${job.url}...`);
      const response = await page.goto(job.url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      console.log(`  -> Initial goto done. HTTP Status: ${response?.status()}`);
      
      // Wait for redirects
      await new Promise(r => setTimeout(r, 6000));
      console.log(`  -> Final URL resolved to: ${page.url()}`);

      const text = await page.evaluate(() => {
        const selectors = ['main', 'article', 'body'];
        for (const sel of selectors) {
          const el = document.querySelector(sel) as HTMLElement;
          if (el && el.innerText.length > 500) return el.innerText;
        }
        return document.body ? document.body.innerText : "";
      });
      console.log(`  -> Text length: ${text.length}`);
    } catch (e: any) {
      console.error(`  -> [TEST FAILED] ERROR: ${e.message}`);
    } finally {
      await page.close().catch(() => {});
    }
  }

  await browser.close();
  db.close();
  console.log('[TEST COMPLETED]');
}

run().catch(console.error);
