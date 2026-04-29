import { chromium } from 'playwright-extra';
import stealth from 'puppeteer-extra-plugin-stealth';
import Database from 'better-sqlite3';

chromium.use(stealth());

async function run() {
  const db = new Database('jobagent.sqlite');
  const jobs = db.prepare('SELECT id, company FROM jobs WHERE url IS NULL OR url = \'\'').all() as any[];

  if (jobs.length === 0) {
    console.log('No jobs need backfilling.');
    return;
  }

  console.log(`Found ${jobs.length} jobs missing URLs. Launching browser...`);
  
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  let count = 0;
  for (const job of jobs) {
    count++;
    try {
      console.log(`[${count}/${jobs.length}] Searching for ${job.company} careers...`);
      const query = encodeURIComponent(`${job.company} careers`);
      await page.goto(`https://duckduckgo.com/?q=${query}`, { waitUntil: 'domcontentloaded' });
      
      // Wait for results to load
      await page.waitForSelector('a[data-testid="result-title-a"]', { timeout: 5000 }).catch(() => {});

      const firstLink = await page.evaluate(() => {
        const links = Array.from(document.querySelectorAll('a[data-testid="result-title-a"]'));
        if (links.length > 0) return links[0].getAttribute('href');
        return null;
      });

      if (firstLink && !firstLink.includes('duckduckgo.com')) {
        console.log(`  -> Found: ${firstLink}`);
        db.prepare('UPDATE jobs SET url = ? WHERE id = ?').run(firstLink, job.id);
      } else {
        // Fallback to a google search link if we couldn't scrape it
        const fallbackUrl = `https://www.google.com/search?q=${query}`;
        console.log(`  -> Not found. Using Google search fallback.`);
        db.prepare('UPDATE jobs SET url = ? WHERE id = ?').run(fallbackUrl, job.id);
      }
      
      // Delay to prevent rate limiting
      await new Promise(r => setTimeout(r, 1500));
    } catch (e: any) {
      console.error(`  -> Error searching for ${job.company}: ${e.message}`);
      const fallbackUrl = `https://www.google.com/search?q=${encodeURIComponent(`${job.company} careers`)}`;
      db.prepare('UPDATE jobs SET url = ? WHERE id = ?').run(fallbackUrl, job.id);
    }
  }

  await browser.close();
  console.log('Finished backfilling URLs.');
}

run().catch(console.error);
