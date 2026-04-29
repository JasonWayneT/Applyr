import { db, logActivity } from './db.js';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCRIPTS_DIR = path.join(__dirname, '../scripts');

export const runScoutSync = async () => {
  logActivity('INFO', 'Scout', 'Unified local sync triggered. Starting Playwright engine...');

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
    });

  } catch (err) {
    logActivity('ERROR', 'Scout', 'Failed to launch scout engine', { error: String(err) });
  }
};
