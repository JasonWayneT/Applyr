import { db, logActivity } from './db.js';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCRIPTS_DIR = path.join(__dirname, '../scripts');

export const runScoutSync = () => {
  logActivity('INFO', 'Scout', 'Unified local sync triggered. Starting Playwright engine...');
  db.prepare(`UPDATE system_status SET status = 'scout_running', current_item = 'Crawling and scanning direct job feeds...', updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run();

  try {
    // Implements FR-054, FR-057, FR-058, SEC-002, SEC-003
    // Reads ALL API keys from SQLite profiles and injects them at spawn time so .env is never required.
    const extraEnv: Record<string, string> = {};
    try {
      const connRow = db.prepare("SELECT value FROM profiles WHERE key = 'api_connections'").get() as any;
      if (connRow?.value) {
        const conns = JSON.parse(connRow.value);
        if (conns.adzunaAppId)  extraEnv.ADZUNA_APP_ID  = conns.adzunaAppId;
        if (conns.adzunaAppKey) extraEnv.ADZUNA_APP_KEY = conns.adzunaAppKey;
      }
    } catch { /* no api_connections record yet — skip */ }
    try {
      // Implements FR-058, FR-061, SEC-003, SEC-004
      const llmRow = db.prepare("SELECT value FROM profiles WHERE key = 'llm_settings'").get() as any;
      if (llmRow?.value) {
        const llm = JSON.parse(llmRow.value);
        if (llm.geminiApiKey)     extraEnv.GEMINI_API_KEY    = llm.geminiApiKey;
        if (llm.claudeApiKey)     extraEnv.ANTHROPIC_API_KEY = llm.claudeApiKey;
        if (llm.perplexityApiKey) extraEnv.PERPLEXITY_API_KEY = llm.perplexityApiKey;
      }
    } catch { /* no llm_settings record yet — skip */ }

    const scoutProcess = spawn('npx', ['tsx', 'scripts/scout_local.ts'], {
      cwd: path.join(__dirname, '..'),
      shell: true,
      env: { ...process.env, ...extraEnv },
    });

    scoutProcess.stdout.on('data', (data) => {
      const output = data.toString().trim();
      if (!output) return;

      const lines = output.split('\n');
      for (const line of lines) {
        if (line.startsWith('[LOG]')) {
          logActivity('INFO', 'Scout', line.replace('[LOG]', '').trim());
        } else if (line.startsWith('[FOUND]')) {
          logActivity('INFO', 'Scout', `Match Found: ${line.replace('[FOUND]', '').trim()}`);
        } else if (line.startsWith('[ACTION]')) {
          logActivity('WARN', 'Scout', `USER ACTION: ${line.replace('[ACTION]', '').trim()}`);
        } else if (line.startsWith('[REJECT]')) {
          logActivity('INFO', 'Scout', `Skipped: ${line.replace('[REJECT]', '').trim()}`);
        } else if (line.startsWith('[DONE]')) {
          logActivity('INFO', 'Scout', 'Sync completed. Check your dashboard for new matches.');
        } else if (line.trim()) {
            // General log
            logActivity('INFO', 'Scout', line.trim());
        }
      }
    });

    scoutProcess.stderr.on('data', (data) => {
      const error = data.toString().trim();
      if (error && !error.includes('DeprecationWarning')) {
        logActivity('ERROR', 'Scout', `Engine Error: ${error}`);
      }
    });

    scoutProcess.on('close', (code) => {
      logActivity('INFO', 'Scout', `Scout engine process exited with code ${code}`);
      
      if (code === 0) {
        logActivity('INFO', 'Scout', 'Starting URL backfill crawl for any missing job URLs...');
        const backfillProcess = spawn('npx', ['tsx', 'scripts/archive/backfill_urls.ts'], {
          cwd: path.join(__dirname, '..'),
          shell: true
        });

        backfillProcess.stdout.on('data', (data) => {
          const output = data.toString().trim();
          if (!output) return;
          const lines = output.split('\n');
          for (const line of lines) {
            logActivity('INFO', 'Crawler', line.trim());
          }
        });

        backfillProcess.stderr.on('data', (data) => {
          const error = data.toString().trim();
          if (error && !error.includes('DeprecationWarning')) {
            logActivity('ERROR', 'Crawler', `Engine Error: ${error}`);
          }
        });

        backfillProcess.on('close', (bfCode) => {
          logActivity('INFO', 'Crawler', `URL backfill process exited with code ${bfCode}`);
          
          logActivity('INFO', 'Scout', 'Starting job description crawling for new postings...');
          db.prepare(`UPDATE system_status SET status = 'scout_running', current_item = 'Scraping job descriptions for new postings...', updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run();

          const scrapeProcess = spawn('npx', ['tsx', 'scripts/scrape_new_jobs.ts'], {
            cwd: path.join(__dirname, '..'),
            shell: true
          });

          scrapeProcess.stdout.on('data', (data) => {
            const lines = data.toString().trim().split('\n');
            for (const line of lines) {
              if (line.trim()) logActivity('INFO', 'Scraper', line.trim());
            }
          });

          scrapeProcess.stderr.on('data', (data) => {
            const error = data.toString().trim();
            if (error && !error.includes('DeprecationWarning')) {
              logActivity('ERROR', 'Scraper', `Engine Error: ${error}`);
            }
          });

          scrapeProcess.on('close', (scrapeCode) => {
            logActivity('INFO', 'Scraper', `Job description scraper exited with code ${scrapeCode}`);
            
            logActivity('INFO', 'Scout', 'Evaluating fit and auto-generating assets...');
            db.prepare(`UPDATE system_status SET status = 'scout_running', current_item = 'Evaluating fit and generating PDF assets...', updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run();

            const evalProcess = spawn('python', ['scripts/batch_pipeline.py', '--mode', 'batch'], {
              cwd: path.join(__dirname, '..'),
              shell: true,
              env: { ...process.env, ...extraEnv },
            });

            evalProcess.stdout.on('data', (data) => {
              const lines = data.toString().trim().split('\n');
              for (const line of lines) {
                if (line.trim()) logActivity('INFO', 'Pipeline', line.trim());
              }
            });

            evalProcess.stderr.on('data', (data) => {
              const error = data.toString().trim();
              if (error) logActivity('ERROR', 'Pipeline', `Engine Error: ${error}`);
            });

            evalProcess.on('close', (evalCode) => {
              logActivity('INFO', 'Pipeline', `Evaluation pipeline exited with code ${evalCode}`);
              logActivity('INFO', 'Scout', 'End-to-end background sync fully completed. Matches and assets are ready on your dashboard.');
              db.prepare(`UPDATE system_status SET status = 'completed', current_item = 'Completed end-to-end sync. Check your dashboard for new matched roles!', updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run();
            });
          });
        });
      } else {
        logActivity('ERROR', 'Scout', 'Scout failed, skipping URL backfill crawl.');
        db.prepare(`UPDATE system_status SET status = 'idle', current_item = 'No active pipeline run', updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run();
      }
    });

  } catch (err) {
    logActivity('ERROR', 'Scout', 'Failed to launch scout engine', { error: String(err) });
  }
};
