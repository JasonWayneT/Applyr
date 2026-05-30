import { Router } from 'express';
import { db, logActivity } from '../../db.js';
import {
  tryAcquirePipeline,
  releasePipeline,
} from '../../middleware.js';
import { readMinFitScore } from '../../shared.js';
import { spawnPython, pythonScriptPath } from '../../pipeline/processRunner.js';

const router = Router();

router.post('/api/jobs/:id/draft', (req, res) => {
  try {
    const { id } = req.params;
    const job = db.prepare('SELECT company, url, score, status FROM jobs WHERE id = ?').get(id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    const label = `Drafting assets for ${job.company}`;
    if (!tryAcquirePipeline(label)) {
      return res.status(409).json({ error: 'Pipeline is already running. Try again when sync/evaluate completes.' });
    }

    const minFit = readMinFitScore();
    const draftOnly =
      job.score != null &&
      job.score >= minFit &&
      ['Needs Retry', 'Backlog', 'Drafted'].includes(job.status);

    logActivity(
      'INFO',
      'Pipeline',
      `Manual asset generation for "${job.company}"${draftOnly ? ' [draft-only]' : ''}`,
    );

    const procArgs = [
      pythonScriptPath('batch_pipeline.py'),
      '--mode', 'single',
      '--company', job.company,
      '--url', job.url || '',
      '--job-id', id,
    ];
    if (draftOnly) procArgs.push('--draft-only');

    spawnPython(procArgs, {
      stdin: '',
      onStdout: (data) => {
        const output = data.trim();
        if (!output) return;
        try {
          const parsed = JSON.parse(output);
          if (parsed.summary) logActivity('INFO', 'Pipeline', `[Draft] ${parsed.summary}`);
        } catch { logActivity('INFO', 'Pipeline', `[Draft] ${output}`); }
      },
      onStderr: (err) => {
        if (err && !err.includes('UserWarning')) logActivity('ERROR', 'Pipeline', `[Draft Error] ${err}`);
      },
      onClose: (code) => {
        const exitCode = code ?? 1;
        logActivity(exitCode === 0 ? 'INFO' : 'ERROR', 'Pipeline', `Draft for "${job.company}" exited with code ${exitCode}`);
        releasePipeline(`Completed asset generation for ${job.company}`);
      },
    });

    res.json({ success: true, message: `Drafting started for ${job.company}` });
  } catch {
    res.status(500).json({ error: 'Failed to start drafting' });
  }
});

export default router;
