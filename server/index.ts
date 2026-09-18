import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
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
import reviewCenterRouter from './routes/reviewCenter.js';
import pipelineQueueRouter from './routes/pipelineQueue.js';
import { runSubmissionRouter } from './routes/runSubmission.js';
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

// CR-104 Epic 2: fail-closed when binding to all interfaces without an auth token.
// Prevents silently running unprotected on a wide bind (0.0.0.0 / Tailscale / LAN).
if (HOST !== '127.0.0.1' && HOST !== 'localhost' && !process.env.APPLYR_API_TOKEN) {
  console.error(
    `\n  FATAL: APPLYR_HOST="${HOST}" binds to a non-localhost address, but APPLYR_API_TOKEN is not set.\n` +
    `  Set APPLYR_API_TOKEN to protect mutating routes, or unset APPLYR_HOST to bind localhost only.\n`
  );
  process.exit(1);
}

const corsOrigins = [
  /^http:\/\/localhost:\d+$/,
  /^http:\/\/127\.0\.0\.1:\d+$/,
];

// CR-104 Epic 3: baseline Express hardening — Helmet for security headers,
// rate limiting to cap abuse. Sized generously (300 req/min per IP) so the
// app's own polling (5-10s intervals from multiple components) never trips.
app.use(helmet());
app.use(
  '/api/',
  rateLimit({
    windowMs: 60 * 1000,
    max: 300,
    standardHeaders: true,
    legacyHeaders: false,
    message: { error: 'Too many requests, please slow down.' },
  }),
);

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
app.use('/', reviewCenterRouter);
app.use('/', pipelineQueueRouter);
// Implements FR-316 / AC-413: authenticated backend access to the canonical CLI.
app.use('/', runSubmissionRouter);

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
