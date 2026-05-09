import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import fs from 'fs';
import { logActivity } from './db.js';
import { ARCHIVE_DIR } from './shared.js';
import systemRouter   from './routes/system.js';
import jobsRouter     from './routes/jobs.js';
import profileRouter  from './routes/profile.js';
import pipelineRouter from './routes/pipeline.js';

dotenv.config();

// Ensure the archive directory exists before any status transitions can run
if (!fs.existsSync(ARCHIVE_DIR)) fs.mkdirSync(ARCHIVE_DIR, { recursive: true });

const app  = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

app.use('/', systemRouter);
app.use('/', jobsRouter);
app.use('/', profileRouter);
app.use('/', pipelineRouter);

app.listen(PORT, () => {
  console.log(`\n${'='.repeat(48)}`);
  console.log(`  JobAgent Server  →  http://localhost:${PORT}`);
  console.log(`${'='.repeat(48)}\n`);
  logActivity('INFO', 'Server', 'System initialized. Ready for syncing.');
});
