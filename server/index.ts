import express from 'express';
import cors from 'cors';
import fs from 'fs';
import { logActivity } from './db.js';
import { ARCHIVE_DIR, SUBMISSION_DIR } from './shared.js';
import { reconcileActiveSubmissionFolders } from './submissionFolders.js';
import systemRouter   from './routes/system.js';
import jobsRouter     from './routes/jobs.js';
import profileRouter  from './routes/profile.js';
import pipelineRouter from './routes/pipeline.js';

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

app.use(cors());
app.use(express.json());

app.use('/', systemRouter);
app.use('/', jobsRouter);
app.use('/', profileRouter);
app.use('/', pipelineRouter);

app.listen(PORT, '0.0.0.0', () => {
  console.log(`\n${'='.repeat(48)}`);
  console.log(`  JobAgent Server  →  Listening on all interfaces (0.0.0.0:${PORT})`);
  console.log(`${'='.repeat(48)}\n`);
  logActivity('INFO', 'Server', 'System initialized. Ready for local and Tailscale syncing.');
});
