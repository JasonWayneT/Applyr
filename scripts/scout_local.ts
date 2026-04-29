import { chromium } from 'playwright-extra';
import stealthPlugin from 'puppeteer-extra-plugin-stealth';
import { Page } from 'playwright';
import path from 'path';
import Database from 'better-sqlite3';
import { randomUUID } from 'crypto';
import { spawn, ChildProcess } from 'child_process';

chromium.use(stealthPlugin());

const DB_PATH = 'jobagent.sqlite';
const CONTEXT_DIR = path.resolve('data/browser_context');
const OPENPOSTINGS_DIR = path.resolve('OpenPostings-extracted/OpenPostings-main');
const OPENPOSTINGS_PORT = 8787;
const SCOUT_FRESHNESS_DAYS = 7;
const FRESHNESS_CUTOFF_EPOCH = Math.floor(Date.now() / 1000) - (SCOUT_FRESHNESS_DAYS * 24 * 60 * 60);

const DB = new Database(DB_PATH);

// Mirrors server/config.ts — single source of truth lives there
const TITLE_BLOCKLIST = [
    'senior', 'staff', 'vp', 'head', 'principal', 'lead product manager',
    'director', 'growth', 'founding', 'manager of',
];

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

// Per-source observability record
interface SourceHealth {
    name: string;
    status: 'ok' | 'error' | 'skipped';
    found: number;
    durationMs: number;
    error?: string;
}

// Wraps any source fn — catches unexpected throws, records timing + status
const runWithHealth = async (
    name: string,
    fn: () => Promise<ScrapedJob[]>
): Promise<{ jobs: ScrapedJob[]; health: SourceHealth }> => {
    const t0 = Date.now();
    try {
        const jobs = await fn();
        return {
            jobs,
            health: { name, status: 'ok', found: jobs.length, durationMs: Date.now() - t0 },
        };
    } catch (err) {
        const error = String(err);
        console.log(`[WARN] ${name}: Unexpected failure — ${error}`);
        return {
            jobs: [],
            health: { name, status: 'error', found: 0, durationMs: Date.now() - t0, error },
        };
    }
};

// ---------------------------------------------------------------------------
// Gates — all deterministic, zero tokens
// ---------------------------------------------------------------------------

const isJobNewByUrl = (url: string): boolean =>
    !DB.prepare('SELECT id FROM jobs WHERE url = ?').get(url);

const isJobNewByCompanyTitle = (company: string, title: string): boolean =>
    !DB.prepare('SELECT id FROM jobs WHERE LOWER(company) = LOWER(?) AND LOWER(title) = LOWER(?)').get(company, title);

const passesTitleBlocklist = (title: string): boolean => {
    const lower = title.toLowerCase();
    return !TITLE_BLOCKLIST.some(blocked => lower.includes(blocked));
};

// ---------------------------------------------------------------------------
// Shared browser utilities
// ---------------------------------------------------------------------------

const humanWait = (min = 2000, max = 5000) => {
    const ms = Math.floor(Math.random() * (max - min + 1) + min);
    return new Promise(r => setTimeout(r, ms));
};

const jiggleMouse = async (page: Page) => {
    const { width, height } = page.viewportSize() || { width: 1280, height: 720 };
    for (let i = 0; i < 3; i++) {
        await page.mouse.move(Math.random() * width, Math.random() * height);
        await humanWait(100, 300);
    }
};

// ---------------------------------------------------------------------------
// Source A: OpenPostings ATS Firehose (zero scraping risk)
// ---------------------------------------------------------------------------

const startOpenPostingsServer = (): Promise<ChildProcess> => {
    return new Promise((resolve, reject) => {
        const proc = spawn('node', ['server/index.js'], {
            cwd: OPENPOSTINGS_DIR,
            stdio: ['ignore', 'pipe', 'pipe'],
        });

        const timeout = setTimeout(() =>
            reject(new Error('OpenPostings server did not start within 20s')), 20000);

        proc.stdout?.on('data', (chunk: Buffer) => {
            const line = chunk.toString();
            if (line.includes(String(OPENPOSTINGS_PORT)) || line.includes('listening')) {
                clearTimeout(timeout);
                resolve(proc);
            }
        });

        proc.on('error', err => { clearTimeout(timeout); reject(err); });
    });
};

const waitForHealth = async () => {
    for (let i = 0; i < 12; i++) {
        try {
            const res = await fetch(`http://localhost:${OPENPOSTINGS_PORT}/health`);
            if (res.ok) return;
        } catch { /* not ready */ }
        await new Promise(r => setTimeout(r, 1500));
    }
    throw new Error('OpenPostings health check timed out');
};

const scoutOpenPostings = async (): Promise<ScrapedJob[]> => {
    console.log('[LOG] OpenPostings: Starting ATS firehose...');
    let proc: ChildProcess | null = null;
    const jobs: ScrapedJob[] = [];

    try {
        proc = await startOpenPostingsServer();
        await waitForHealth();
        console.log('[LOG] OpenPostings: Server healthy. Triggering sync...');

        // Non-blocking sync — we poll status and take whatever syncs in ~2 min
        fetch(`http://localhost:${OPENPOSTINGS_PORT}/sync/ats`, { method: 'POST' }).catch(() => {});

        // Poll until sync finishes or timeout (2 min)
        const deadline = Date.now() + 120_000;
        while (Date.now() < deadline) {
            await new Promise(r => setTimeout(r, 10_000));
            try {
                const s = await (await fetch(`http://localhost:${OPENPOSTINGS_PORT}/sync/status`)).json() as any;
                if (!s.running) { console.log('[LOG] OpenPostings: Sync completed early.'); break; }
            } catch { break; }
        }

        // Query for both search terms
        for (const term of ['product manager', 'product owner']) {
            try {
                const url = `http://localhost:${OPENPOSTINGS_PORT}/postings?search=${encodeURIComponent(term)}&remote=remote`;
                const data = await (await fetch(url)).json() as any[];
                console.log(`[LOG] OpenPostings: ${data.length} results for "${term}"`);

                for (const p of data) {
                    if (jobs.length >= 60) break;
                    const jobUrl = String(p.job_posting_url || '');
                    const company = String(p.company_name || '').trim();
                    const title   = String(p.position_name || '').trim();

                    if (!jobUrl || !company || !title) continue;
                    if (!passesTitleBlocklist(title)) {
                        console.log(`[REJECT] ${title} at ${company} (OpenPostings) - Title Blocklist`);
                        continue;
                    }
                    if (!isJobNewByUrl(jobUrl)) {
                        console.log(`[REJECT] ${title} at ${company} (OpenPostings) - URL already exists`);
                        continue;
                    }
                    if (!isJobNewByCompanyTitle(company, title)) {
                        console.log(`[REJECT] ${title} at ${company} (OpenPostings) - Company/Title already exists`);
                        continue;
                    }

                    // 7-day freshness gate on last_seen_epoch
                    const epoch = Number(p.last_seen_epoch || 0);
                    if (epoch && epoch < FRESHNESS_CUTOFF_EPOCH) {
                        console.log(`[REJECT] ${title} at ${company} (OpenPostings) - Stale (Past 7 days)`);
                        continue;
                    }

                    jobs.push({ company, title, url: jobUrl, description: '', source: 'OpenPostings' });
                    console.log(`[FOUND] ${title} at ${company} (OpenPostings)`);
                }
            } catch (err) {
                console.log(`[LOG] OpenPostings query error for "${term}": ${err}`);
            }
        }
    } catch (err) {
        console.log(`[LOG] OpenPostings module skipped: ${err}`);
    } finally {
        if (proc) { proc.kill(); console.log('[LOG] OpenPostings server stopped.'); }
    }

    return jobs;
};

// ---------------------------------------------------------------------------
// Source B: LinkedIn (Playwright, stealth, 7-day param in URL)
// ---------------------------------------------------------------------------

const scoutLinkedIn = async (page: Page): Promise<ScrapedJob[]> => {
    console.log('[LOG] LinkedIn: Checking session health...');

    // Session health check — fail fast if login wall detected
    try {
        await page.goto('https://www.linkedin.com/feed/', { timeout: 15000 });
        await humanWait(2000, 3000);
        if (page.url().includes('login') || page.url().includes('checkpoint')) {
            console.log('[ACTION] LinkedIn session expired. Sign in manually to restore. Skipping LinkedIn this run.');
            return [];
        }
    } catch {
        console.log('[LOG] LinkedIn session check failed. Skipping LinkedIn.');
        return [];
    }

    const jobs: ScrapedJob[] = [];

    for (const term of ['Product%20Manager', 'Product%20Owner']) {
        const searchUrl = `https://www.linkedin.com/jobs/search/?f_TPR=r604800&geoId=103644278&keywords=${term}&location=United%20States&f_WT=2`;

        try {
            await page.goto(searchUrl);
            await humanWait(4000, 6000);
            await page.evaluate(() => window.scrollTo(0, 1000));
            await humanWait(2000, 3000);

            const cards = await page.$$('.job-card-container');
            console.log(`[LOG] LinkedIn: ${cards.length} cards for "${decodeURIComponent(term)}"`);

            for (const card of cards) {
                if (jobs.length >= 25) break;
                try {
                    await card.scrollIntoViewIfNeeded();
                    await humanWait(1000, 2000);
                    await card.click();
                    await humanWait(3000, 5000);
                    await jiggleMouse(page);

                    const url     = page.url().split('?')[0];
                    const title   = (await page.textContent('.jobs-unified-top-card__job-title')   || '').trim();
                    const company = (await page.textContent('.jobs-unified-top-card__company-name') || '').trim();

                    if (!url || !title || !company) continue;
                    if (!passesTitleBlocklist(title)) {
                        console.log(`[REJECT] ${title} at ${company} (LinkedIn) - Title Blocklist`);
                        continue;
                    }
                    if (!isJobNewByUrl(url)) {
                        console.log(`[REJECT] ${title} at ${company} (LinkedIn) - URL already exists`);
                        continue;
                    }
                    if (!isJobNewByCompanyTitle(company, title)) {
                        console.log(`[REJECT] ${title} at ${company} (LinkedIn) - Company/Title already exists`);
                        continue;
                    }

                    const desc     = (await page.textContent('#job-details') || '').slice(0, 1500);
                    const salary   = desc.match(/\$[\d,]+ ?[-–] ?\$[\d,]+/)?.[0];
                    const recName  = (await page.textContent('.jobs-poster__name').catch(() => ''))?.trim() || undefined;
                    const recUrl   = (await page.getAttribute('.jobs-poster__name-link', 'href').catch(() => '')) || undefined;

                    jobs.push({ company, title, url, description: desc,
                        salary_range: salary, recruiter_name: recName, recruiter_url: recUrl || undefined, source: 'LinkedIn' });
                    console.log(`[FOUND] ${title} at ${company} (LinkedIn)`);
                } catch { /* silently skip bad cards */ }
            }
        } catch (err) {
            console.log(`[LOG] LinkedIn search failed for "${term}": ${err}`);
        }
    }

    return jobs;
};

// ---------------------------------------------------------------------------
// Source C: BuiltIn (Playwright, 7-day param in URL)
// ---------------------------------------------------------------------------

const scoutBuiltIn = async (page: Page): Promise<ScrapedJob[]> => {
    console.log('[LOG] Built In: Scouting...');
    const jobs: ScrapedJob[] = [];

    try {
        await page.goto('https://builtin.com/jobs/remote/product?days_since_posted=7', { waitUntil: 'domcontentloaded' });
        await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
        await humanWait(2000, 4000);
        await page.waitForSelector('.job-card', { timeout: 10000 }).catch(() => {});

        const cards = await page.$$('.job-card');
        console.log(`[LOG] Built In: ${cards.length} cards found.`);

        for (const card of cards) {
            if (jobs.length >= 20) break;
            try {
                const title   = (await card.$eval('.title',         el => el.textContent).catch(() => '')).trim();
                const company = (await card.$eval('.company-title', el => el.textContent).catch(() => '')).trim();
                const relUrl  = await card.$eval('a.job-row-link', el => el.getAttribute('href')).catch(() => '');
                const url     = relUrl ? `https://builtin.com${relUrl}` : '';

                if (!url || !title || !company) continue;
                if (!passesTitleBlocklist(title)) {
                    console.log(`[REJECT] ${title} at ${company} (Built In) - Title Blocklist`);
                    continue;
                }
                if (!isJobNewByUrl(url)) {
                    console.log(`[REJECT] ${title} at ${company} (Built In) - URL already exists`);
                    continue;
                }
                if (!isJobNewByCompanyTitle(company, title)) {
                    console.log(`[REJECT] ${title} at ${company} (Built In) - Company/Title already exists`);
                    continue;
                }

                jobs.push({ company, title, url, description: '', source: 'Built In' });
                console.log(`[FOUND] ${title} at ${company} (Built In)`);
            } catch { /* skip */ }
        }
    } catch (err) {
        console.log(`[LOG] Built In scrape failed: ${err}`);
    }

    return jobs;
};

// ---------------------------------------------------------------------------
// Source D: Remotive (Public JSON API, zero risk)
// ---------------------------------------------------------------------------

const scoutRemotive = async (): Promise<ScrapedJob[]> => {
    console.log('[LOG] Remotive: Fetching product jobs...');
    const jobs: ScrapedJob[] = [];

    try {
        const res = await fetch('https://remotive.com/api/remote-jobs?category=product&limit=100');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json() as any;
        const postings = data.jobs || [];
        console.log(`[LOG] Remotive: ${postings.length} raw results.`);

        for (const p of postings) {
            const title   = String(p.title || '').trim();
            const company = String(p.company_name || '').trim();
            const url     = String(p.url || '').trim();
            const pubDate = p.publication_date ? new Date(p.publication_date) : null;

            if (!title || !company || !url) continue;
            if (pubDate && pubDate.getTime() < FRESHNESS_CUTOFF_EPOCH * 1000) {
                console.log(`[REJECT] ${title} at ${company} (Remotive) - Stale`);
                continue;
            }
            if (!passesTitleBlocklist(title)) {
                console.log(`[REJECT] ${title} at ${company} (Remotive) - Title Blocklist`);
                continue;
            }
            if (!isJobNewByUrl(url)) {
                console.log(`[REJECT] ${title} at ${company} (Remotive) - URL already exists`);
                continue;
            }
            if (!isJobNewByCompanyTitle(company, title)) {
                console.log(`[REJECT] ${title} at ${company} (Remotive) - Company/Title already exists`);
                continue;
            }

            jobs.push({
                company, title, url,
                description: String(p.description || '').slice(0, 1500),
                salary_range: p.salary || undefined,
                source: 'Remotive',
            });
            console.log(`[FOUND] ${title} at ${company} (Remotive)`);
        }
    } catch (err) {
        console.log(`[WARN] Remotive failed: ${err}`);
    }

    return jobs;
};

// ---------------------------------------------------------------------------
// Source E: RemoteOK (Public JSON API, zero risk)
// ---------------------------------------------------------------------------

const scoutRemoteOK = async (): Promise<ScrapedJob[]> => {
    console.log('[LOG] RemoteOK: Fetching product manager jobs...');
    const jobs: ScrapedJob[] = [];

    try {
        const res = await fetch('https://remoteok.com/api?tags=product+manager', {
            headers: { 'User-Agent': 'JobAgent/1.0' },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json() as any[];

        // First element is a legal notice object, skip it
        const postings = data.filter((p: any) => p.id && p.position);
        console.log(`[LOG] RemoteOK: ${postings.length} raw results.`);

        for (const p of postings) {
            const title   = String(p.position || '').trim();
            const company = String(p.company || '').trim();
            const url     = String(p.url || p.apply_url || '').trim();
            const epoch   = Number(p.epoch || 0);

            if (!title || !company || !url) continue;
            if (epoch && epoch < FRESHNESS_CUTOFF_EPOCH) {
                console.log(`[REJECT] ${title} at ${company} (RemoteOK) - Stale`);
                continue;
            }
            if (!passesTitleBlocklist(title)) {
                console.log(`[REJECT] ${title} at ${company} (RemoteOK) - Title Blocklist`);
                continue;
            }
            if (!isJobNewByUrl(url)) {
                console.log(`[REJECT] ${title} at ${company} (RemoteOK) - URL already exists`);
                continue;
            }
            if (!isJobNewByCompanyTitle(company, title)) {
                console.log(`[REJECT] ${title} at ${company} (RemoteOK) - Company/Title already exists`);
                continue;
            }

            jobs.push({
                company, title, url,
                description: String(p.description || '').replace(/<[^>]+>/g, '').slice(0, 1500),
                salary_range: p.salary_min && p.salary_max ? `$${p.salary_min} - $${p.salary_max}` : undefined,
                source: 'RemoteOK',
            });
            console.log(`[FOUND] ${title} at ${company} (RemoteOK)`);
        }
    } catch (err) {
        console.log(`[WARN] RemoteOK failed: ${err}`);
    }

    return jobs;
};

// ---------------------------------------------------------------------------
// Source F: We Work Remotely (RSS feed, zero risk)
// ---------------------------------------------------------------------------

const scoutWWR = async (): Promise<ScrapedJob[]> => {
    console.log('[LOG] WWR: Fetching product jobs via RSS...');
    const jobs: ScrapedJob[] = [];

    try {
        const res = await fetch('https://weworkremotely.com/categories/remote-product-jobs.rss');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const xml = await res.text();

        // Simple regex XML parsing — no dependency needed for RSS
        const items = xml.match(/<item>[\s\S]*?<\/item>/g) || [];
        console.log(`[LOG] WWR: ${items.length} RSS items.`);

        for (const item of items) {
            const extract = (tag: string) => {
                const m = item.match(new RegExp(`<${tag}><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>`))
                    || item.match(new RegExp(`<${tag}>([\\s\\S]*?)<\\/${tag}>`));
                return m ? m[1].trim() : '';
            };

            const rawTitle = extract('title');
            const url      = extract('link');
            const pubDate  = extract('pubDate');

            // Title format is usually "Company: Role Title"
            const colonIdx = rawTitle.indexOf(':');
            const company  = colonIdx > 0 ? rawTitle.slice(0, colonIdx).trim() : 'Unknown';
            const title    = colonIdx > 0 ? rawTitle.slice(colonIdx + 1).trim() : rawTitle;

            if (!title || !url) continue;
            if (pubDate) {
                const d = new Date(pubDate);
                if (d.getTime() < FRESHNESS_CUTOFF_EPOCH * 1000) {
                    console.log(`[REJECT] ${title} at ${company} (WWR) - Stale`);
                    continue;
                }
            }
            if (!passesTitleBlocklist(title)) {
                console.log(`[REJECT] ${title} at ${company} (WWR) - Title Blocklist`);
                continue;
            }
            if (!isJobNewByUrl(url)) {
                console.log(`[REJECT] ${title} at ${company} (WWR) - URL already exists`);
                continue;
            }
            if (!isJobNewByCompanyTitle(company, title)) {
                console.log(`[REJECT] ${title} at ${company} (WWR) - Company/Title already exists`);
                continue;
            }

            jobs.push({ company, title, url, description: '', source: 'WWR' });
            console.log(`[FOUND] ${title} at ${company} (WWR)`);
        }
    } catch (err) {
        console.log(`[WARN] WWR (We Work Remotely) failed: ${err}`);
    }

    return jobs;
};

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

(async () => {
    const healthLog: SourceHealth[] = [];

    console.log('[START] Multi-source scout run starting (6 sources)...');

    // --- Phase 1: All API sources + OpenPostings run in parallel (no browser needed) ---
    const [opResult, remotiveResult, remoteOkResult, wwrResult] = await Promise.all([
        runWithHealth('OpenPostings', scoutOpenPostings),
        runWithHealth('Remotive', scoutRemotive),
        runWithHealth('RemoteOK', scoutRemoteOK),
        runWithHealth('WWR', scoutWWR),
    ]);

    healthLog.push(opResult.health, remotiveResult.health, remoteOkResult.health, wwrResult.health);
    const apiJobs = [...opResult.jobs, ...remotiveResult.jobs, ...remoteOkResult.jobs, ...wwrResult.jobs];

    // --- Phase 2: Browser sources (LinkedIn + BuiltIn) run sequentially ---
    let browserJobs: ScrapedJob[] = [];
    try {
        const context = await chromium.launchPersistentContext(CONTEXT_DIR, {
            headless: false,
            viewport: { width: 1440, height: 900 },
            args: ['--disable-blink-features=AutomationControlled'],
        });
        const page = context.pages()[0] || await context.newPage();

        const liResult = await runWithHealth('LinkedIn', () => scoutLinkedIn(page));
        healthLog.push(liResult.health);

        const biResult = await runWithHealth('BuiltIn', () => scoutBuiltIn(page));
        healthLog.push(biResult.health);

        browserJobs = [...liResult.jobs, ...biResult.jobs];
        await context.close();
    } catch (err) {
        console.log(`[WARN] Browser init failed. Skipping LinkedIn + BuiltIn: ${err}`);
        healthLog.push(
            { name: 'LinkedIn', status: 'skipped', found: 0, durationMs: 0, error: String(err) },
            { name: 'BuiltIn', status: 'skipped', found: 0, durationMs: 0, error: String(err) },
        );
    }

    // --- Phase 3: Merge, dedup, save ---
    const allJobs = [...apiJobs, ...browserJobs];

    const seenUrls = new Set<string>();
    const uniqueJobs = allJobs.filter(j => {
        if (seenUrls.has(j.url)) return false;
        seenUrls.add(j.url);
        return true;
    });

    const insert = DB.prepare(`
        INSERT INTO jobs (id, company, title, url, status, salary_range, recruiter_name, recruiter_url, source_site, created_at)
        VALUES (?, ?, ?, ?, 'New', ?, ?, ?, ?, CURRENT_TIMESTAMP)
    `);

    let saved = 0;
    for (const job of uniqueJobs) {
        try {
            insert.run(randomUUID(), job.company, job.title, job.url,
                job.salary_range || null, job.recruiter_name || null,
                job.recruiter_url || null, job.source);
            saved++;
        } catch { /* UNIQUE URL constraint */ }
    }

    // --- Phase 4: Observability summary ---
    console.log('\n====================================');
    console.log('  SCOUT RUN SUMMARY');
    console.log('====================================');
    console.log(`${'Source'.padEnd(15)} ${'Status'.padEnd(10)} ${'Found'.padEnd(8)} Duration`);
    console.log('-'.repeat(50));
    for (const h of healthLog) {
        const dur = h.durationMs < 1000 ? `${h.durationMs}ms` : `${(h.durationMs / 1000).toFixed(1)}s`;
        const icon = h.status === 'ok' ? 'OK' : h.status === 'error' ? 'FAIL' : 'SKIP';
        console.log(`${h.name.padEnd(15)} ${icon.padEnd(10)} ${String(h.found).padEnd(8)} ${dur}`);
        if (h.error) console.log(`  -> ${h.error.slice(0, 120)}`);
    }
    console.log('-'.repeat(50));
    console.log(`Total raw: ${allJobs.length} | After dedup: ${uniqueJobs.length} | Saved: ${saved}`);
    console.log('====================================\n');

    console.log(`[DONE] ${saved} new roles added to pipeline.`);
    DB.close();
})();
