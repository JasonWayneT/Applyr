import express from 'express';
import cors from 'cors';
import fs from 'fs';
import { logActivity } from './db.js';
import { ARCHIVE_DIR, SUBMISSION_DIR } from './shared.js';
import { runBuffered, pythonScriptPath } from './pipeline/processRunner.js';
import { reconcileActiveSubmissionFolders } from './submissionFolders.js';
import systemRouter   from './routes/system.js';
import jobsRouter     from './routes/jobs/index.js';
import profileRouter  from './routes/profile.js';
import pipelineRouter from './routes/pipeline.js';
import sourcesRouter  from './routes/sources.js';
import contactsRouter from './routes/contacts.js';
import gmailSyncRouter from './routes/gmailSync.js';
import llmUsageRouter from './routes/llmUsage.js';
import { startGmailSyncScheduler } from './services/gmailSyncScheduler.js';
import { resetTheirstackCreditsIfNewMonth } from './services/theirstackCreditLedger.js';

// Ensure workspace dirs exist before status transitions (FR-030)
if (!fs.existsSync(ARCHIVE_DIR)) fs.mkdirSync(ARCHIVE_DIR, { recursive: true });
if (!fs.existsSync(SUBMISSION_DIR)) fs.mkdirSync(SUBMISSION_DIR, { recursive: true });

const startupReconcile = reconcileActiveSubmissionFolders();
if (startupReconcile.archived.length || startupReconcile.removed.length) {
  console.log(
    `[FR-030] Reconciled submissions/: archived=[${startupReconcile.archived.join(', ')}], removed=[${startupReconcile.removed.join(', ')}]`,
  );
}

const app  = express();
const PORT = 3000;
const HOST = process.env.APPLYR_HOST || '127.0.0.1';

const corsOrigins = [
  /^http:\/\/localhost:\d+$/,
  /^http:\/\/127\.0\.0\.1:\d+$/,
];

app.use(cors({
  origin(origin, callback) {
    if (!origin || corsOrigins.some((re) => re.test(origin))) {
      callback(null, true);
      return;
    }
    callback(new Error('Not allowed by CORS'));
  },
}));
app.use(express.json({ limit: '2mb' }));

app.use('/', systemRouter);
app.use('/', jobsRouter);
app.use('/', profileRouter);
app.use('/', pipelineRouter);
app.use('/', sourcesRouter);
app.use('/', contactsRouter);
app.use('/', gmailSyncRouter);
app.use('/', llmUsageRouter);

app.listen(PORT, HOST, () => {
  console.log(`\n${'='.repeat(48)}`);
  console.log(`  JobAgent Server  🚀  Listening on ${HOST}:${PORT}`);
  if (HOST === '127.0.0.1') {
    console.log(`  (Set APPLYR_HOST=0.0.0.0 for Tailscale/network access)`);
  }
  console.log(`${'='.repeat(48)}\n`);
  resetTheirstackCreditsIfNewMonth();
  logActivity('INFO', 'Server', 'System initialized. Ready for local and Tailscale syncing.');

  startGmailSyncScheduler(); // CR-072 Epic 3 — immediate pass now, then every 10 minutes

  setInterval(() => {
    void runBuffered([pythonScriptPath('auto_prune_db.py')]).then(({ code }) => {
      if (code !== 0) {
        logActivity('ERROR', 'System', `Auto-pruning failed with exit code ${code}`);
      } else {
        logActivity('INFO', 'System', 'Auto-pruning completed.');
      }
    });
  }, 12 * 60 * 60 * 1000);
});
