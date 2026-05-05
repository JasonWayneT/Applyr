import { db, logActivity } from './db.js';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCRIPTS_DIR = path.join(__dirname, '../scripts');

export const runScoutSync = async () => {
  logActivity('INFO', 'Scout', 'Unified local sync triggered. Starting Playwright engine...');
  db.prepare(`UPDATE system_status SET status = 'scout_running', current_item = 'Crawling and scanning direct job feeds...', updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run();

  try {
    const scoutProcess = spawn('npx', ['tsx', 'scripts/scout_local.ts'], {
      cwd: path.join(__dirname, '..'),
      shell: true
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
        const backfillProcess = spawn('npx', ['tsx', 'scripts/backfill_urls.ts'], {
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
          logActivity('INFO', 'Scout', 'Sync and crawl fully completed. Check your dashboard for new matches.');
          db.prepare(`UPDATE system_status SET status = 'completed', current_item = 'Completed sync and crawl. Check dashboard for new matches.', updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run();
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
