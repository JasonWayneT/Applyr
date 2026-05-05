import path from 'path';
import Database from 'better-sqlite3';
import { randomUUID } from 'crypto';

// --- Configuration ---
const OPENPOSTINGS_DB_PATH = path.resolve('OpenPostings-extracted/OpenPostings-main/jobs.db');
const MAIN_DB_PATH = path.resolve('jobagent.sqlite');

const OP_DB = new Database(OPENPOSTINGS_DB_PATH);
const MAIN_DB = new Database(MAIN_DB_PATH);

// Freshness: 7 days
const FRESHNESS_CUTOFF_EPOCH = Math.floor(Date.now() / 1000) - (7 * 24 * 60 * 60);

// --- Helpers ---
const isJobNewByUrl = (url: string): boolean => {
    const row = MAIN_DB.prepare('SELECT id FROM jobs WHERE url = ?').get(url);
    return !row;
};

const isJobNewByCompanyTitle = (company: string, title: string): boolean => {
    const row = MAIN_DB.prepare('SELECT id FROM jobs WHERE company = ? AND title = ?').get(company, title);
    return !row;
};

const passesTitleBlocklist = (title: string): boolean => {
    const blocklist = ['senior', 'staff', 'vp', 'head', 'principal', 'lead', 'director', 'growth', 'assistant', 'coordinator', 'intern', 'associate', 'junior', 'analyst', 'engineer', 'developer', 'designer', 'marketer', 'founder'];
    const t = title.toLowerCase();
    return !blocklist.some(b => t.includes(b));
};

async function run() {
    console.log('[START] Scraping existing OpenPostings database...');
    
    try {
        const terms = ['%product manager%', '%product owner%'];
        const foundJobs: any[] = [];

        for (const term of terms) {
            console.log(`  [Query] Searching for "${term}" in OpenPostings DB...`);
            const postings = OP_DB.prepare(`
                SELECT company_name, position_name, job_posting_url, last_seen_epoch
                FROM Postings
                WHERE (LOWER(position_name) LIKE ?)
                AND (last_seen_epoch >= ?)
            `).all(term, FRESHNESS_CUTOFF_EPOCH);

            console.log(`    -> Found ${postings.length} candidates.`);

            for (const p of postings) {
                const jobUrl = String(p.job_posting_url || '');
                const company = String(p.company_name || '').trim();
                const title = String(p.position_name || '').trim();

                if (!company || !title) continue;
                
                // Filters
                if (!passesTitleBlocklist(title)) continue;
                if (jobUrl && !isJobNewByUrl(jobUrl)) continue;
                if (!isJobNewByCompanyTitle(company, title)) continue;

                foundJobs.push({ company, title, url: jobUrl });
            }
        }

        console.log(`  [DB] Saving ${foundJobs.length} new jobs to main database...`);
        const insert = MAIN_DB.prepare(`
            INSERT INTO jobs (id, company, title, url, status, source_site, created_at)
            VALUES (?, ?, ?, ?, 'New', 'OpenPostings', CURRENT_TIMESTAMP)
        `);

        let saved = 0;
        for (const job of foundJobs) {
            try {
                insert.run(randomUUID(), job.company, job.title, job.url);
                saved++;
                console.log(`    + Added: ${job.title} at ${job.company}`);
            } catch (e) {
                console.log(`    - Failed to save ${job.title}: ${e.message}`);
            }
        }

        console.log(`[DONE] ${saved} new roles added to jobagent.sqlite from existing OpenPostings DB.`);

    } catch (e) {
        console.error('[ERROR]', e);
    } finally {
        OP_DB.close();
        MAIN_DB.close();
    }
}

run();
