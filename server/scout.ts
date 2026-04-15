import { db, logActivity } from './db.js';
import { TITLE_BLOCKLIST } from './config.js';

interface Company {
  id: number;
  company_name: string;
  url_string: string;
  ATS_name: string;
}

interface FoundJob {
  company_name: string;
  position_name: string;
  job_posting_url: string;
}

export const runScoutSync = async () => {
  logActivity('INFO', 'Scout', 'Manual sync triggered. Checking companies...');

  try {
    const companies = db.prepare('SELECT * FROM openpostings.companies LIMIT 50').all() as Company[];
    logActivity('INFO', 'Scout', `Beginning scan of ${companies.length} companies.`);

    for (const company of companies) {
      logActivity('INFO', 'Scout', `Scanning ${company.company_name} (${company.ATS_name})...`);

      // TODO: Replace with real ATS scraper functions (fetchWorkdayPage, fetchAshbyJobBoard, etc.)
      // This mock always emits one good role and one senior role per company for testing gate logic.
      const foundJobs: FoundJob[] = [
        {
          company_name: company.company_name,
          position_name: 'Product Manager',
          job_posting_url: `https://jobs.${company.company_name.toLowerCase().replace(/\s+/g, '')}.com/pm`,
        },
        {
          company_name: company.company_name,
          position_name: 'Senior Product Manager',
          job_posting_url: `https://jobs.${company.company_name.toLowerCase().replace(/\s+/g, '')}.com/sr-pm`,
        },
      ];

      for (const job of foundJobs) {
        const titleLower = job.position_name.toLowerCase();

        // --- Deterministic Gate ---
        const isSenior = TITLE_BLOCKLIST.some(term => titleLower.includes(term));

        if (isSenior) {
          logActivity('WARN', 'Scout', `Auto-rejected: "${job.position_name}"`, {
            company: job.company_name,
            reason: 'Seniority mismatch',
          });
          continue;
        }

        // --- Passed Gate: register as candidate job ---
        try {
          db.prepare('INSERT INTO jobs (id, company, title, url, status) VALUES (?, ?, ?, ?, ?)')
            .run(crypto.randomUUID(), job.company_name, job.position_name, job.job_posting_url, 'New');
          logActivity('INFO', 'Scout', `High-Fit found: "${job.position_name}" at ${job.company_name}`, {
            url: job.job_posting_url,
          });
        } catch {
          // Silently skip duplicates (URL UNIQUE constraint)
        }
      }
    }

    logActivity('INFO', 'Scout', 'Sync completed successfully.');
  } catch (err) {
    logActivity('ERROR', 'Scout', 'Sync failed', { error: String(err) });
  }
};
