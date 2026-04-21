import { chromium, BrowserContext, Page } from 'playwright';
import path from 'path';
import fs from 'fs';
import Database from 'better-sqlite3';
import { randomUUID } from 'crypto';

// Constants
const DB_PATH = 'jobagent.sqlite';
const CONTEXT_DIR = path.resolve('data/browser_context');
const DB = new Database(DB_PATH);

// Types
interface ScrapedJob {
    company: string;
    title: string;
    url: string;
    description: string;
    salary_range?: string;
    recruiter_name?: string;
    recruiter_url?: string;
    source: string;
}

/**
 * Human-like interaction utilities
 */
const humanWait = async (min = 2000, max = 5000) => {
    const ms = Math.floor(Math.random() * (max - min + 1) + min);
    await new Promise(r => setTimeout(r, ms));
};

const jiggleMouse = async (page: Page) => {
    const { width, height } = page.viewportSize() || { width: 1280, height: 720 };
    for (let i = 0; i < 3; i++) {
        await page.mouse.move(Math.random() * width, Math.random() * height);
        await humanWait(100, 300);
    }
};

/**
 * Deduplication check
 */
const isJobNew = (url: string): boolean => {
    const row = DB.prepare('SELECT id FROM jobs WHERE url = ?').get(url);
    return !row;
};

/**
 * LinkedIn Scraper Module
 */
const scoutLinkedIn = async (page: Page): Promise<ScrapedJob[]> => {
    console.log('[LOG] Scouting LinkedIn...');
    
    // Search for "Product Manager", Remote US, Past Week
    const searchUrl = 'https://www.linkedin.com/jobs/search/?f_TPR=r604800&geoId=103644278&keywords=Product%20Manager&location=United%20States&f_WT=2';
    
    await page.goto(searchUrl);
    await humanWait(4000, 6000);
    
    // Check if we need to login
    if (page.url().includes('login') || (await page.$('a[href*="login"]'))) {
        console.log('[ACTION] LinkedIn Login Required. Please sign in in the browser window.');
        // We wait for the search results or feed to appear
        await page.waitForSelector('.job-card-container', { timeout: 0 });
    }

    const jobs: ScrapedJob[] = [];
    
    // Scroll a bit to load more
    await page.evaluate(() => window.scrollTo(0, 1000));
    await humanWait(2000, 3000);

    const jobCards = await page.$$('.job-card-container');
    console.log(`[LOG] Found ${jobCards.length} potential roles on LinkedIn.`);

    for (const card of jobCards) {
        try {
            await card.scrollIntoViewIfNeeded();
            await humanWait(1000, 2000);
            await card.click();
            await humanWait(3000, 5000);
            await jiggleMouse(page);

            const url = page.url().split('?')[0]; // Clean URL
            if (!isJobNew(url)) {
                // console.log(`[LOG] Duplicate skipped: ${url}`);
                continue;
            }

            const title = await page.textContent('.jobs-unified-top-card__job-title') || 'Unknown';
            const company = await page.textContent('.jobs-unified-top-card__company-name') || 'Unknown';
            const description = await page.textContent('#job-details') || '';
            
            // Salary extraction
            const salaryMatch = description.match(/\$[0-9,]+ - \$[0-9,]+/);
            const salary = salaryMatch ? salaryMatch[0] : undefined;

            // Recruiter info
            const recruiterName = await page.textContent('.jobs-poster__name') || undefined;
            const recruiterUrl = await page.getAttribute('.jobs-poster__name-link', 'href') || undefined;

            jobs.push({
                company: company.trim(),
                title: title.trim(),
                url,
                description: description.trim(),
                salary_range: salary,
                recruiter_name: recruiterName?.trim(),
                recruiter_url: recruiterUrl || undefined,
                source: 'LinkedIn'
            });

            console.log(`[FOUND] ${title} at ${company}`);
            if (jobs.length >= 10) break; 
        } catch (err) {
            // Silently fail card parse (common on LinkedIn dynamic UI)
        }
    }
    
    return jobs;
};

/**
 * Built In Scraper Module
 */
const scoutBuiltIn = async (page: Page): Promise<ScrapedJob[]> => {
    console.log('[LOG] Scouting Built In (National Index)...');
    const searchUrl = 'https://builtin.com/jobs/remote/product?days_since_posted=7';
    
    await page.goto(searchUrl);
    await humanWait(4000, 6000);
    
    const jobs: ScrapedJob[] = [];
    const jobCards = await page.$$('.job-card'); 
    
    console.log(`[LOG] Found ${jobCards.length} potential roles on Built In.`);

    for (const card of jobCards) {
        try {
            const title = await card.$eval('.title', el => el.textContent) || 'Unknown';
            const company = await card.$eval('.company-title', el => el.textContent) || 'Unknown';
            const relUrl = await card.$eval('a.job-row-link', el => el.getAttribute('href'));
            const url = relUrl ? `https://builtin.com${relUrl}` : '';

            if (url && isJobNew(url)) {
                jobs.push({
                    company: company.trim(),
                    title: title.trim(),
                    url,
                    description: '', // Built In often requires another click for description
                    source: 'Built In'
                });
                console.log(`[FOUND] ${title} at ${company} (Built In)`);
            }
            if (jobs.length >= 10) break;
        } catch (err) {
            // Skip
        }
    }
    
    return jobs;
};

/**
 * Main Execution
 */
(async () => {
    const context = await chromium.launchPersistentContext(CONTEXT_DIR, {
        headless: false,
        viewport: { width: 1440, height: 900 },
        args: ['--disable-blink-features=AutomationControlled']
    });

    const page = context.pages()[0] || await context.newPage();
    
    try {
        console.log('[START] Beginning unified scout run...');
        
        const liJobs = await scoutLinkedIn(page);
        const biJobs = await scoutBuiltIn(page);
        
        const allJobs = [...liJobs, ...biJobs];
        console.log(`[LOG] Run complete. Syncing ${allJobs.length} new roles to database.`);

        const insertStmt = DB.prepare(`
            INSERT INTO jobs (id, company, title, url, status, salary_range, recruiter_name, recruiter_url, source_site, created_at)
            VALUES (?, ?, ?, ?, 'New', ?, ?, ?, ?, CURRENT_TIMESTAMP)
        `);

        for (const job of allJobs) {
            try {
                insertStmt.run(
                    randomUUID(),
                    job.company,
                    job.title,
                    job.url,
                    job.salary_range || null,
                    job.recruiter_name || null,
                    job.recruiter_url || null,
                    job.source
                );
            } catch (err) {
                // Duplicate URL (UNIQUE constraint)
            }
        }
        
        console.log('[DONE] Database sync finished.');
        
    } catch (err) {
        console.error('[ERROR] Scout run failed:', err);
    } finally {
        await context.close();
        DB.close();
    }
})();
