import dotenv from 'dotenv';
dotenv.config();
import { chromium } from 'playwright-extra';
import stealthPlugin from 'puppeteer-extra-plugin-stealth';
import { Page } from 'playwright';
import path from 'path';
import fs from 'fs';
import Database from 'better-sqlite3';
import { randomUUID } from 'crypto';
import { spawn, ChildProcess } from 'child_process';

chromium.use(stealthPlugin());

const DB_PATH = 'jobagent.sqlite';
const CONTEXT_DIR = path.resolve('data/browser_context');
const OPENPOSTINGS_DIR = path.resolve('OpenPostings-extracted/OpenPostings-main');
const OPENPOSTINGS_PORT = 8787;

// ---------------------------------------------------------------------------
// Load candidate preferences — single source of truth
// ---------------------------------------------------------------------------
let prefs: any = {};
try {
    const raw = fs.readFileSync(path.resolve('data/candidate_preferences.json'), 'utf-8');
    prefs = JSON.parse(raw);
} catch {
    console.log('[WARN] Could not load candidate_preferences.json — using built-in defaults.');
}

const TARGET_ROLE: string           = prefs.target_role || 'Product Manager';
// Implements FR-056 — fallback uses only TARGET_ROLE; variant expansion happens in materializeJobSearchPrefs
const SEARCH_TERMS: string[]        = prefs.search_terms?.length ? prefs.search_terms : [TARGET_ROLE];
const WORK_SETTING: string          = prefs.work_setting || 'Remote';
const LOCATION: string              = prefs.location_preference || 'United States';
const EXPERIENCE_LEVELS: string[]   = prefs.experience_levels || [];
const FRESHNESS_DAYS: number        = prefs.freshness_days ?? 7;
const TITLE_BLOCKLIST: string[]     = (prefs.blocked_titles || [
    'senior', 'staff', 'vp', 'head', 'principal', 'lead product manager',
    'director', 'growth', 'founding', 'manager of',
    'assistant', 'coordinator', 'intern', 'associate', 'junior',
    'analyst', 'engineer', 'developer', 'designer', 'marketer',
]).map((t: string) => t.toLowerCase());

const FRESHNESS_CUTOFF_EPOCH = Math.floor(Date.now() / 1000) - (FRESHNESS_DAYS * 24 * 60 * 60);

const ADZUNA_APP_ID  = process.env.ADZUNA_APP_ID  || '';
const ADZUNA_APP_KEY = process.env.ADZUNA_APP_KEY || '';

// Implements FR-055 — free-tier rate guard: 25 req/min, 250 req/day
const MAX_ADZUNA_CALLS_PER_RUN = 10;

// Implements FR-056 — map target role to The Muse API category slug
function getTheMuseCategory(targetRole: string): string {
    const lower = targetRole.toLowerCase();
    if (lower.includes('data') || lower.includes('scientist') || lower.includes('analytics')) return 'Data Science';
    if (lower.includes('design') || lower.includes('ux') || lower.includes('ui'))             return 'Design';
    if (lower.includes('engineer') || lower.includes('developer') || lower.includes('software') ||
        lower.includes('backend')  || lower.includes('frontend')  || lower.includes('fullstack')) return 'Engineering & Tech';
    if (lower.includes('market')) return 'Marketing';
    return 'Product'; // default covers PM/PO/product roles
}


// Experience level → BuiltIn slug
const BUILTIN_EXP_SLUGS: Record<string, string> = {
    'Internship':             'internship',
    'Entry Level (0-1 Years)': 'entry-level',
    'Junior (1-2 Years)':     'entry-level',
    'Mid Level (2-5 Years)':  'mid-level',
    'Senior Level (5-9 Years)': 'senior-level',
    'Expert/Leader (9+ Years)': 'senior-level',
};

// ---------------------------------------------------------------------------
// URL builders
// ---------------------------------------------------------------------------

function buildBuiltInUrlsForTerm(term: string): string[] {
    const workPrefix = WORK_SETTING === 'Hybrid' ? 'hybrid' : WORK_SETTING === 'On-site' ? '' : 'remote';
    const expSlugs = EXPERIENCE_LEVELS.length > 0
        ? [...new Set(EXPERIENCE_LEVELS.map(l => BUILTIN_EXP_SLUGS[l]).filter(Boolean))]
        : [];

    const targets: string[] = [];
    const pathSegments = ['jobs'];
    
    if (workPrefix) pathSegments.push(workPrefix);
    // Leverage first experience slug inside URL path, mirroring Built In's routing architecture
    if (expSlugs.length > 0) pathSegments.push(expSlugs[0]);

    const basePath = pathSegments.join('/');
    
    // Combine daysSinceUpdated and days_since_posted queries to ensure API routing coverage
    let query = `?search=${encodeURIComponent(term)}&daysSinceUpdated=${FRESHNESS_DAYS}&days_since_posted=${FRESHNESS_DAYS}&country=USA&allLocations=true`;
    
    // Append remaining experience slugs as array params
    if (expSlugs.length > 1) {
        for (let i = 1; i < expSlugs.length; i++) {
            query += `&experience%5B%5D=${expSlugs[i]}`;
        }
    }

    targets.push(`https://builtin.com/${basePath}${query}`);
    return targets;
}

function buildBuiltInTaxonomyUrl(): string {
    const workPrefix = WORK_SETTING === 'Hybrid' ? 'hybrid' : WORK_SETTING === 'On-site' ? '' : 'remote';
    const base = workPrefix
        ? `https://builtin.com/jobs/${workPrefix}/product-management`
        : 'https://builtin.com/jobs/product-management';

    let url = `${base}?days_since_posted=${FRESHNESS_DAYS}`;

    if (EXPERIENCE_LEVELS.length > 0) {
        const slugs = [...new Set(EXPERIENCE_LEVELS.map(l => BUILTIN_EXP_SLUGS[l]).filter(Boolean))];
        for (const slug of slugs) url += `&experience%5B%5D=${slug}`;
    }

    return url;
}

const DB = new Database(DB_PATH);

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

/**
 * Implements FR-070: Early Ingestion Location Gate
 * Prevents persisting job listings that are neither Remote nor local to San Diego/Carlsbad metro.
 */
function passesGeographicGate(job: ScrapedJob): boolean {
    const text = `${job.title} ${job.description || ''}`.toLowerCase();
    
    // If description is placeholder or very short, bypass gate here to allow 
    // the down-funnel scrape_new_jobs + batch_pipeline stages to evaluate fully.
    if ((job.description || '').trim().length < 50) {
        return true; 
    }

    const hasLocalSD = text.includes('san diego') || 
                       text.includes('carlsbad') || 
                       text.includes('la jolla') || 
                       text.includes('encinitas') || 
                       text.includes('del mar') || 
                       text.includes('solana beach') ||
                       text.includes('ca'); // Keep CA as soft local signal

    const hasRemote = text.includes('remote') || 
                      text.includes('anywhere in') || 
                      text.includes('work from home') || 
                      text.includes('telecommute');

    // Explicit exclusion of major non-US geographies if no US indicators are present
    const isExplicitForeign = (
        text.includes('canada') || 
        text.includes('united kingdom') || 
        text.includes('london,') || 
        text.includes('europe') || 
        text.includes('germany') || 
        text.includes('india') || 
        text.includes('apac')
    ) && !(
        text.includes('united states') || 
        text.includes('within the us') || 
        text.includes('us citizen')
    );

    if (isExplicitForeign) {
        return false;
    }

    // Accept if it has SD local bounds or is Remote
    if (hasLocalSD || hasRemote) {
        return true;
    }

    // Hardwired acceptance for remote-only sources
    const explicitRemoteSources = ['Remotive', 'RemoteOK', 'WWR', 'Himalayas'];
    if (explicitRemoteSources.includes(job.source)) {
        return true;
    }

    // If it has neither remote nor local indicators, and it's from LinkedIn/BuiltIn,
    // reject it as an out-of-bound on-site role.
    return false;
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
    !DB.prepare('SELECT id FROM jobs WHERE url = ?').get(url) &&
    !DB.prepare('SELECT url FROM stale_jobs WHERE url = ?').get(url);

const isJobNewByCompanyTitle = (company: string, title: string): boolean =>
    !DB.prepare('SELECT id FROM jobs WHERE LOWER(company) = LOWER(?) AND LOWER(title) = LOWER(?)').get(company, title) &&
    !DB.prepare('SELECT url FROM stale_jobs WHERE LOWER(company) = LOWER(?) AND LOWER(title) = LOWER(?)').get(company, title);

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

        // Query for all configured search terms
        for (const term of SEARCH_TERMS) {
            try {
                const remoteParam = WORK_SETTING === 'Remote' ? '&remote=remote' : '';
                const url = `http://localhost:${OPENPOSTINGS_PORT}/postings?search=${encodeURIComponent(term)}${remoteParam}`;
                const res = await fetch(url);
                const data = await res.json() as any;
                
                if (!data || !Array.isArray(data)) {
                    console.log(`[LOG] OpenPostings: Unexpected response for "${term}" (Not an array): ${JSON.stringify(data).slice(0, 200)}`);
                    continue;
                }
                
                console.log(`[LOG] OpenPostings: ${data.length} results for "${term}"`);

                for (const p of data) {
                    if (jobs.length >= 60) break;
                    const jobUrl = String(p.job_posting_url || '');
                    const company = String(p.company_name || '').trim();
                    const title   = String(p.position_name || '').trim();

                    if (!company || !title) continue;
                    if (!passesTitleBlocklist(title)) {
                        console.log(`[REJECT] ${title} at ${company} (OpenPostings) - Title Blocklist`);
                        continue;
                    }
                    if (jobUrl && !isJobNewByUrl(jobUrl)) {
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
// Source C: BuiltIn (Playwright, 7-day param in URL)
// ---------------------------------------------------------------------------

const scoutBuiltIn = async (page: Page): Promise<ScrapedJob[]> => {
    console.log('[LOG] Built In: Scouting multiple target channels...');
    const jobs: ScrapedJob[] = [];
    const seenUrls = new Set<string>();

    // Gather combined endpoints: Term-specific text search and legacy taxonomy fallback
    const targets: { url: string; label: string }[] = [];
    for (const term of SEARCH_TERMS) {
        const urls = buildBuiltInUrlsForTerm(term);
        for (const u of urls) {
            targets.push({ url: u, label: `Search: ${term}` });
        }
    }
    targets.push({ url: buildBuiltInTaxonomyUrl(), label: 'Taxonomy Fallback' });

    for (const target of targets) {
        try {
            console.log(`[LOG] Built In: Crawling ${target.label}...`);
            await page.goto(target.url, { waitUntil: 'domcontentloaded' });
            await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
            await humanWait(2000, 4000);
            
            // Wait for either traditional .job-item OR modern div[data-id="job-card"]
            await page.waitForSelector('.job-item, div[data-id="job-card"]', { timeout: 10000 }).catch(() => {});

            const cards = await page.$$('.job-item, div[data-id="job-card"]');
            console.log(`[LOG] Built In: ${cards.length} cards found for ${target.label}.`);

            for (const card of cards) {
                if (jobs.length >= 60) break; // Aggregate safety cap
                try {
                    // Resilient Dual-Archetype Metadata Selectors
                    const title = (await card.$eval('[data-id="job-card-title"], .card-alias-after-overlay', el => el.textContent).catch(() => '')).trim();
                    
                    // Extract company name using data-id, falling back to general anchor link
                    const company = (await card.$eval('[data-id="company-title"]', el => el.textContent).catch(() => 
                                     card.$eval('a[href^="/company/"]', el => el.textContent).catch(() => ''))).trim();
                    
                    const relUrl = await card.$eval('[data-id="job-card-title"], a.card-alias-after-overlay', el => el.getAttribute('href')).catch(() => '');
                    
                    if (!relUrl || !title || !company) {
                        continue;
                    }

                    const url = relUrl.startsWith('http') ? relUrl : `https://builtin.com${relUrl}`;

                    if (seenUrls.has(url)) continue;
                    seenUrls.add(url);

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
                } catch (cardErr) {
                    console.log(`[LOG] Built In card process failed: ${cardErr}`);
                }
            }
        } catch (err) {
            console.log(`[LOG] Built In scrape failed for ${target.label}: ${err}`);
        }
        
        // Pause briefly between endpoints to protect browser session health
        await humanWait(1500, 3000);
    }

    return jobs;
};

// ---------------------------------------------------------------------------
// Source C2: Levels.fyi (Playwright crawler)
// ---------------------------------------------------------------------------

const scoutLevelsFyi = async (page: Page): Promise<ScrapedJob[]> => {
    console.log('[LOG] Levels.fyi: Scouting...');
    const jobs: ScrapedJob[] = [];

    try {
        await page.goto('https://www.levels.fyi/jobs?jobId=1', { waitUntil: 'domcontentloaded' });
        await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
        await humanWait(2000, 4000);

        // Simple scraper trying to grab job items/rows
        const cards = await page.$$('a[href*="/jobs/"]');
        console.log(`[LOG] Levels.fyi: ${cards.length} anchor links found.`);

        for (const card of cards) {
            if (jobs.length >= 10) break;
            try {
                const url = (await card.getAttribute('href')) || '';
                const fullUrl = url.startsWith('http') ? url : `https://www.levels.fyi${url}`;

                // Just fetch context/title if we can
                const text = (await card.textContent() || '').trim();
                if (!text || !fullUrl) continue;

                // Extract company and title if possible, or fallback
                const parts = text.split('\n').map(p => p.trim()).filter(Boolean);
                const title = parts[0] || 'Product Manager';
                const company = parts[1] || 'Levels.fyi Candidate';

                if (!passesTitleBlocklist(title)) {
                    console.log(`[REJECT] ${title} at ${company} (Levels.fyi) - Title Blocklist`);
                    continue;
                }
                if (!isJobNewByUrl(fullUrl)) {
                    console.log(`[REJECT] ${title} at ${company} (Levels.fyi) - URL already exists`);
                    continue;
                }
                if (!isJobNewByCompanyTitle(company, title)) {
                    console.log(`[REJECT] ${title} at ${company} (Levels.fyi) - Company/Title already exists`);
                    continue;
                }

                jobs.push({ company, title, url: fullUrl, description: '', source: 'Levels.fyi' });
                console.log(`[FOUND] ${title} at ${company} (Levels.fyi)`);
            } catch (cardErr) {
                console.log(`[LOG] Levels.fyi card process failed: ${cardErr}`);
            }
        }
    } catch (err) {
        console.log(`[LOG] Levels.fyi scrape failed: ${err}`);
    }

    return jobs;
};

// ---------------------------------------------------------------------------
// Source D: Remotive (Public JSON API, zero risk)
// ---------------------------------------------------------------------------

const scoutRemotive = async (): Promise<ScrapedJob[]> => {
    console.log('[LOG] Remotive: Fetching jobs by search terms...');
    const jobs: ScrapedJob[] = [];
    const seenUrls = new Set<string>();

    for (const term of SEARCH_TERMS) {
        try {
            const res = await fetch(`https://remotive.com/api/remote-jobs?search=${encodeURIComponent(term)}&limit=50`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json() as any;
            const postings = data.jobs || [];
            console.log(`[LOG] Remotive: ${postings.length} results for "${term}".`);

            for (const p of postings) {
                const title   = String(p.title || '').trim();
                const company = String(p.company_name || '').trim();
                const url     = String(p.url || '').trim();
                const pubDate = p.publication_date ? new Date(p.publication_date) : null;

                if (!title || !company || !url) continue;
                if (seenUrls.has(url)) continue;
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

                seenUrls.add(url);
                jobs.push({
                    company, title, url,
                    description: String(p.description || '').slice(0, 1500),
                    salary_range: p.salary || undefined,
                    source: 'Remotive',
                });
                console.log(`[FOUND] ${title} at ${company} (Remotive)`);
            }
        } catch (err) {
            console.log(`[WARN] Remotive search failed for "${term}": ${err}`);
        }
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
        // RemoteOK tags are hyphen-separated slugs (not URL-encoded spaces)
        const tags = SEARCH_TERMS.slice(0, 2).map(t => t.toLowerCase().replace(/\s+/g, '-')).join(',');
        const res = await fetch(`https://remoteok.com/api?tags=${encodeURIComponent(tags)}`, {
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
    console.log('[LOG] WWR: Fetching product & management jobs via RSS...');
    const jobs: ScrapedJob[] = [];
    const seenUrls = new Set<string>();

    const feeds = [
        'https://weworkremotely.com/categories/remote-product-jobs.rss',
        'https://weworkremotely.com/categories/remote-management-finance-jobs.rss',
    ];

    const extract = (item: string, tag: string) => {
        const m = item.match(new RegExp(`<${tag}><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>`))
            || item.match(new RegExp(`<${tag}>([\\s\\S]*?)<\\/${tag}>`));
        return m ? m[1].trim() : '';
    };

    for (const feedUrl of feeds) {
        try {
            const res = await fetch(feedUrl);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const xml = await res.text();

            const items = xml.match(/<item>[\s\S]*?<\/item>/g) || [];
            console.log(`[LOG] WWR: ${items.length} RSS items from ${feedUrl.split('/').pop()}.`);

            for (const item of items) {
                const rawTitle = extract(item, 'title');
                const url      = extract(item, 'link');
                const pubDate  = extract(item, 'pubDate');

                const colonIdx = rawTitle.indexOf(':');
                const company  = colonIdx > 0 ? rawTitle.slice(0, colonIdx).trim() : 'Unknown';
                const title    = colonIdx > 0 ? rawTitle.slice(colonIdx + 1).trim() : rawTitle;

                if (!title || !url) continue;
                if (seenUrls.has(url)) continue;
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

                seenUrls.add(url);
                jobs.push({ company, title, url, description: '', source: 'WWR' });
                console.log(`[FOUND] ${title} at ${company} (WWR)`);
            }
        } catch (err) {
            console.log(`[WARN] WWR feed ${feedUrl.split('/').pop()}: ${err}`);
        }
    }

    return jobs;
};

// ---------------------------------------------------------------------------
// Source G: Himalayas (Public JSON API, zero risk)
// ---------------------------------------------------------------------------

const scoutHimalayas = async (): Promise<ScrapedJob[]> => {
    console.log('[LOG] Himalayas: Fetching remote jobs...');
    const jobs: ScrapedJob[] = [];
    const seenUrls = new Set<string>();

    for (const term of SEARCH_TERMS) {
        try {
            const slug = term.toLowerCase().replace(/\s+/g, '-');
            const res = await fetch(`https://himalayas.app/jobs/api?roles=${encodeURIComponent(slug)}&limit=50`, {
                headers: { 'Accept': 'application/json' },
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json() as any;
            const postings = data.jobs || [];
            console.log(`[LOG] Himalayas: ${postings.length} results for "${term}".`);

            for (const p of postings) {
                const title   = String(p.title || '').trim();
                const company = String(p.companyName || '').trim();
                const url     = String(p.applicationLink || '').trim();
                const pubDate = p.publishedAt ? new Date(p.publishedAt) : null;

                if (!title || !company || !url) continue;
                if (seenUrls.has(url)) continue;
                if (pubDate && pubDate.getTime() < FRESHNESS_CUTOFF_EPOCH * 1000) {
                    console.log(`[REJECT] ${title} at ${company} (Himalayas) - Stale`);
                    continue;
                }
                if (!passesTitleBlocklist(title)) {
                    console.log(`[REJECT] ${title} at ${company} (Himalayas) - Title Blocklist`);
                    continue;
                }
                if (!isJobNewByUrl(url)) {
                    console.log(`[REJECT] ${title} at ${company} (Himalayas) - URL already exists`);
                    continue;
                }
                if (!isJobNewByCompanyTitle(company, title)) {
                    console.log(`[REJECT] ${title} at ${company} (Himalayas) - Company/Title already exists`);
                    continue;
                }

                seenUrls.add(url);
                jobs.push({
                    company, title, url,
                    description: String(p.description || '').replace(/<[^>]+>/g, '').slice(0, 1500),
                    salary_range: p.salaryRange || undefined,
                    source: 'Himalayas',
                });
                console.log(`[FOUND] ${title} at ${company} (Himalayas)`);
            }
        } catch (err) {
            console.log(`[WARN] Himalayas search failed for "${term}": ${err}`);
        }
    }

    return jobs;
};

// ---------------------------------------------------------------------------
// Source H: The Muse (Public JSON API, no auth, zero risk)
// ---------------------------------------------------------------------------

// Implements FR-056 — category derived from TARGET_ROLE, not hardcoded to "Product"
const scoutTheMuse = async (): Promise<ScrapedJob[]> => {
    const museCategory = getTheMuseCategory(TARGET_ROLE);
    console.log(`[LOG] The Muse: Fetching ${museCategory} jobs...`);
    const jobs: ScrapedJob[] = [];

    try {
        for (let page = 0; page <= 1; page++) {
            const locationParam = WORK_SETTING === 'Remote' ? '&location=Flexible%20%2F%20Remote' : '';
            const res = await fetch(
                `https://www.themuse.com/api/public/jobs?category=${encodeURIComponent(museCategory)}&level=Mid+Level${locationParam}&page=${page}`,
                { headers: { 'Accept': 'application/json' } }
            );
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json() as any;
            const postings = data.results || [];
            if (postings.length === 0) break;
            console.log(`[LOG] The Muse: ${postings.length} results (page ${page}).`);

            for (const p of postings) {
                const title   = String(p.name || '').trim();
                const company = String(p.company?.name || '').trim();
                const url     = String(p.refs?.landing_page || '').trim();
                const pubDate = p.publication_date ? new Date(p.publication_date) : null;

                if (!title || !company || !url) continue;
                if (pubDate && pubDate.getTime() < FRESHNESS_CUTOFF_EPOCH * 1000) {
                    console.log(`[REJECT] ${title} at ${company} (The Muse) - Stale`);
                    continue;
                }
                if (!passesTitleBlocklist(title)) {
                    console.log(`[REJECT] ${title} at ${company} (The Muse) - Title Blocklist`);
                    continue;
                }
                if (!isJobNewByUrl(url)) {
                    console.log(`[REJECT] ${title} at ${company} (The Muse) - URL already exists`);
                    continue;
                }
                if (!isJobNewByCompanyTitle(company, title)) {
                    console.log(`[REJECT] ${title} at ${company} (The Muse) - Company/Title already exists`);
                    continue;
                }

                const desc = String(p.contents || '').replace(/<[^>]+>/g, '').slice(0, 1500);
                jobs.push({ company, title, url, description: desc, source: 'The Muse' });
                console.log(`[FOUND] ${title} at ${company} (The Muse)`);
            }
        }
    } catch (err) {
        console.log(`[WARN] The Muse failed: ${err}`);
    }

    return jobs;
};

// ---------------------------------------------------------------------------
// Source I: Adzuna (Paid API, aggregates many boards)
// ---------------------------------------------------------------------------

// Implements FR-052, FR-054, FR-055, SEC-002
const scoutAdzuna = async (): Promise<ScrapedJob[]> => {
    if (!ADZUNA_APP_ID || !ADZUNA_APP_KEY) {
        console.log('[LOG] Adzuna: No API credentials configured. Skipping.');
        return [];
    }

    console.log('[LOG] Adzuna: Fetching jobs...');
    const jobs: ScrapedJob[] = [];
    const seenUrls = new Set<string>();
    let callCount = 0;

    for (const term of SEARCH_TERMS) {
        if (callCount >= MAX_ADZUNA_CALLS_PER_RUN) {
            console.log(`[WARN] Adzuna: Rate cap reached (${MAX_ADZUNA_CALLS_PER_RUN} calls/run). Stopping early.`);
            break;
        }
        // 3s gap between calls to respect 25 req/min free-tier limit (Implements FR-055)
        if (callCount > 0) await new Promise(r => setTimeout(r, 3000));
        callCount++;
        try {
            const queryTerm = WORK_SETTING === 'Remote' ? `${term} remote` : term;
            const params = new URLSearchParams({
                app_id: ADZUNA_APP_ID,
                app_key: ADZUNA_APP_KEY,
                results_per_page: '50',
                what: queryTerm,
                max_days_old: String(FRESHNESS_DAYS),
                'content-type': 'application/json',
            });
            const res = await fetch(`https://api.adzuna.com/v1/api/jobs/us/search/1?${params}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json() as any;
            const postings = data.results || [];
            console.log(`[LOG] Adzuna: ${postings.length} results for "${term}".`);

            for (const p of postings) {
                const title   = String(p.title || '').trim();
                const company = String(p.company?.display_name || '').trim();
                const url     = String(p.redirect_url || '').trim();

                if (!title || !company || !url) continue;
                if (seenUrls.has(url)) continue;
                if (!passesTitleBlocklist(title)) {
                    console.log(`[REJECT] ${title} at ${company} (Adzuna) - Title Blocklist`);
                    continue;
                }
                if (!isJobNewByUrl(url)) {
                    console.log(`[REJECT] ${title} at ${company} (Adzuna) - URL already exists`);
                    continue;
                }
                if (!isJobNewByCompanyTitle(company, title)) {
                    console.log(`[REJECT] ${title} at ${company} (Adzuna) - Company/Title already exists`);
                    continue;
                }

                seenUrls.add(url);
                const salary = p.salary_min && p.salary_max
                    ? `$${Math.round(p.salary_min / 1000)}k - $${Math.round(p.salary_max / 1000)}k`
                    : undefined;
                const desc = String(p.description || '').replace(/<[^>]+>/g, '').slice(0, 1500);
                jobs.push({ company, title, url, description: desc, salary_range: salary, source: 'Adzuna' });
                console.log(`[FOUND] ${title} at ${company} (Adzuna)`);
            }
        } catch (err) {
            console.log(`[WARN] Adzuna search failed for "${term}": ${err}`);
        }
    }

    return jobs;
};

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

(async () => {
    const healthLog: SourceHealth[] = [];

    console.log('[START] Multi-source scout run starting (9 sources)...');

    // --- Phase 1: All API sources run in parallel (no browser needed) ---
    const [opResult, remotiveResult, remoteOkResult, wwrResult, himalayasResult, theMuseResult, adzunaResult] = await Promise.all([
        runWithHealth('OpenPostings', scoutOpenPostings),
        runWithHealth('Remotive', scoutRemotive),
        runWithHealth('RemoteOK', scoutRemoteOK),
        runWithHealth('WWR', scoutWWR),
        runWithHealth('Himalayas', scoutHimalayas),
        runWithHealth('The Muse', scoutTheMuse),
        runWithHealth('Adzuna', scoutAdzuna),
    ]);

    healthLog.push(
        opResult.health, remotiveResult.health, remoteOkResult.health, wwrResult.health,
        himalayasResult.health, theMuseResult.health, adzunaResult.health,
    );
    const apiJobs = [
        ...opResult.jobs, ...remotiveResult.jobs, ...remoteOkResult.jobs, ...wwrResult.jobs,
        ...himalayasResult.jobs, ...theMuseResult.jobs, ...adzunaResult.jobs,
    ];

    // --- Phase 2: Browser sources (LinkedIn + BuiltIn + Levels.fyi) run sequentially ---
    let browserJobs: ScrapedJob[] = [];
    try {
        const context = await chromium.launchPersistentContext(CONTEXT_DIR, {
            headless: false,
            viewport: { width: 1440, height: 900 },
            args: ['--disable-blink-features=AutomationControlled'],
        });
        const page = context.pages()[0] || await context.newPage();

        console.log('[LOG] LinkedIn: Bypassed (Permanently decommissioned due to security-risk directives)');
        healthLog.push({ name: 'LinkedIn', status: 'skipped', found: 0, durationMs: 0, error: 'Decommissioned' });

        const biResult = await runWithHealth('BuiltIn', () => scoutBuiltIn(page));
        healthLog.push(biResult.health);

        const lvResult = await runWithHealth('Levels.fyi', () => scoutLevelsFyi(page));
        healthLog.push(lvResult.health);

        browserJobs = [...biResult.jobs, ...lvResult.jobs];
        await context.close();
    } catch (err) {
        console.log(`[WARN] Browser init failed. Skipping LinkedIn + BuiltIn + Levels.fyi: ${err}`);
        healthLog.push(
            { name: 'LinkedIn', status: 'skipped', found: 0, durationMs: 0, error: String(err) },
            { name: 'BuiltIn', status: 'skipped', found: 0, durationMs: 0, error: String(err) },
            { name: 'Levels.fyi', status: 'skipped', found: 0, durationMs: 0, error: String(err) },
        );
    }

    // --- Phase 3: Merge, dedup, save ---
    const allJobs = [...apiJobs, ...browserJobs];

    const seenUrls = new Set<string>();
    const uniqueJobs = allJobs.filter(j => {
        if (!j.url) return true; // Don't dedupe missing URLs here
        if (seenUrls.has(j.url)) return false;
        seenUrls.add(j.url);
        return true;
    });

    // Apply geographic boundary pre-gate
    const gatedJobs = uniqueJobs.filter(j => {
        if (!passesGeographicGate(j)) {
            console.log(`[REJECT] ${j.title} at ${j.company} (${j.source}) - [GEOGRAPHIC REJECT]`);
            return false;
        }
        return true;
    });

    const insert = DB.prepare(`
        INSERT INTO jobs (id, company, title, url, status, salary_range, recruiter_name, recruiter_url, source_site, created_at)
        VALUES (?, ?, ?, ?, 'New', ?, ?, ?, ?, CURRENT_TIMESTAMP)
    `);

    let saved = 0;
    for (const job of gatedJobs) {
        try {
            insert.run(randomUUID(), job.company, job.title, job.url || null,
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
