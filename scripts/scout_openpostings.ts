import { spawn, ChildProcess } from 'child_process';
import path from 'path';
import Database from 'better-sqlite3';
import { randomUUID } from 'crypto';
// fetch is native in Node 24+

// --- Configuration ---
const OPENPOSTINGS_DIR = path.resolve('OpenPostings-extracted/OpenPostings-main');
const OPENPOSTINGS_PORT = 3010;
const DB_PATH = path.resolve('jobagent.sqlite');
const DB = new Database(DB_PATH);

// Freshness: 7 days
const FRESHNESS_CUTOFF_EPOCH = Math.floor(Date.now() / 1000) - (7 * 24 * 60 * 60);

// --- Helpers ---
const isJobNewByUrl = (url: string): boolean => {
    const row = DB.prepare('SELECT id FROM jobs WHERE url = ?').get(url);
    return !row;
};

const isJobNewByCompanyTitle = (company: string, title: string): boolean => {
    const row = DB.prepare('SELECT id FROM jobs WHERE company = ? AND title = ?').get(company, title);
    return !row;
};

const passesTitleBlocklist = (title: string): boolean => {
    const blocklist = ['senior', 'staff', 'vp', 'head', 'principal', 'lead', 'director', 'growth', 'assistant', 'coordinator', 'intern', 'associate', 'junior', 'analyst', 'engineer', 'developer', 'designer', 'marketer', 'founder'];
    const t = title.toLowerCase();
    return !blocklist.some(b => t.includes(b));
};

async function run() {
    console.log('[START] OpenPostings Sync & Scrape');
    
    let proc: ChildProcess | null = null;
    
    try {
        console.log('  [Server] Starting OpenPostings server...');
        proc = spawn('node', ['server/index.js'], {
            cwd: OPENPOSTINGS_DIR,
            stdio: 'inherit',
            env: { ...process.env, PORT: String(OPENPOSTINGS_PORT) }
        });

        // Wait for server to be ready
        await new Promise(r => setTimeout(r, 5000));

        console.log('  [ATS] Triggering full sync...');
        await fetch(`http://localhost:${OPENPOSTINGS_PORT}/sync/ats`, { method: 'POST' }).catch((e) => console.log('Sync trigger failed:', e.message));

        // Wait for sync to finalize
        console.log('  [ATS] Waiting for sync to complete (polling status)...');
        const deadline = Date.now() + 300_000; // 5 min timeout
        while (Date.now() < deadline) {
            await new Promise(r => setTimeout(r, 10_000));
            try {
                const s = await (await fetch(`http://localhost:${OPENPOSTINGS_PORT}/sync/status`)).json() as any;
                if (!s.running) {
                    console.log('  [ATS] Sync completed.');
                    break;
                }
                console.log(`  [ATS] Syncing... ${s.progress?.current || 0}/${s.progress?.total || 0} (${s.progress?.company_name || ''})`);
            } catch (e) {
                console.log('Status check failed, server might be busy or crashed.');
                break;
            }
        }

        const jobs: any[] = [];
        const terms = ['product manager', 'product owner'];
        
        for (const term of terms) {
            console.log(`  [Query] Fetching jobs for "${term}"...`);
            const url = `http://localhost:${OPENPOSTINGS_PORT}/postings?search=${encodeURIComponent(term)}&remote=remote`;
            try {
                const data = await (await fetch(url)).json() as any[];
                console.log(`  [Query] Found ${data.length} results.`);

                for (const p of data) {
                    const jobUrl = String(p.job_posting_url || '');
                    const company = String(p.company_name || '').trim();
                    const title = String(p.position_name || '').trim();

                    if (!company || !title) continue;
                    
                    // Filters
                    if (!passesTitleBlocklist(title)) continue;
                    if (jobUrl && !isJobNewByUrl(jobUrl)) continue;
                    if (!isJobNewByCompanyTitle(company, title)) continue;

                    // Freshness
                    const epoch = Number(p.last_seen_epoch || 0);
                    if (epoch && epoch < FRESHNESS_CUTOFF_EPOCH) continue;

                    jobs.push({ company, title, url: jobUrl, source: 'OpenPostings' });
                }
            } catch (e) {
                console.log(`  [Query] Error for "${term}":`, e.message);
            }
        }

        console.log(`  [DB] Saving ${jobs.length} new jobs to database...`);
        const insert = DB.prepare(`
            INSERT INTO jobs (id, company, title, url, status, source_site, created_at)
            VALUES (?, ?, ?, ?, 'New', ?, CURRENT_TIMESTAMP)
        `);

        let saved = 0;
        for (const job of jobs) {
            try {
                insert.run(randomUUID(), job.company, job.title, job.url, job.source);
                saved++;
                console.log(`    + Saved: ${job.title} at ${job.company}`);
            } catch (e) {
                // Duplicate URL or other error
            }
        }

        console.log(`[DONE] ${saved} new roles added to jobagent.sqlite.`);

    } catch (e) {
        console.error('[ERROR]', e);
    } finally {
        if (proc) {
            console.log('  [Server] Stopping OpenPostings server...');
            proc.kill();
        }
        DB.close();
    }
}

run();
