import { db, logActivity } from './db.js';
import { buildPythonEnv, PROJECT_ROOT } from './shared.js';
import { spawn } from 'child_process';

/**
 * Standard Promise-wrapped Process Spawner to enforce isolated async execution boundaries.
 */
function spawnProcessAsync(
  command: string,
  args: string[],
  env: Record<string, string>,
  onStdout: (data: string) => void,
  onStderr: (data: string) => void
): Promise<number> {
  return new Promise((resolve, reject) => {
    try {
      const child = spawn(command, args, {
        cwd: PROJECT_ROOT,
        shell: true,
        env: { ...process.env, ...env },
      });

      child.stdout.on('data', (chunk) => onStdout(chunk.toString()));
      child.stderr.on('data', (chunk) => onStderr(chunk.toString()));

      child.on('close', (code) => resolve(code ?? 1));
      child.on('error', (err) => reject(err));
    } catch (err) {
      reject(err);
    }
  });
}

/**
 * Updates status in BOTH 'pipeline_runs' (for resumption) AND 'system_status' (for frontend display).
 */
function updateCheckpoint(runId: string, stage: string, statusMsg: string) {
  db.prepare(`UPDATE pipeline_runs SET current_stage = ?, updated_at = CURRENT_TIMESTAMP WHERE run_id = ?`).run(stage, runId);
  db.prepare(`UPDATE system_status SET status = 'scout_running', current_item = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run(statusMsg);
}

/**
 * Route subprocess stderr lines to INFO, WARN, or ERROR based on their prefixes or content.
 * Implements BUG-010
 */
function handleStderr(source: string, stderr: string) {
  const trimmed = stderr.trim();
  if (!trimmed) return;
  
  const lines = trimmed.split('\n');
  for (const line of lines) {
    const clean = line.trim();
    if (!clean || clean.includes('DeprecationWarning')) continue;
    
    const isInfo = clean.includes('[Model Manager]') || 
                   clean.includes('[LLM]') || 
                   clean.includes('[Research]') ||
                   clean.includes('[Drafting]') ||
                   clean.includes('[Audit]') ||
                   clean.includes('[Export]') ||
                   clean.includes('[Phase 1]') ||
                   clean.includes('[Phase 2]') ||
                   clean.includes('[GUARD]') ||
                   clean.includes('[HARD FACT AUDIT]') ||
                   clean.includes('[QA AUDIT PASS]') ||
                   clean.includes('[BATCH_SUMMARY]') ||
                   clean.includes('Successfully audited') ||
                   clean.includes('Running Style Compliance Guard');
                   
    if (isInfo) {
      logActivity('INFO', source, clean);
    } else if (clean.includes('[LLM Notice]') || clean.includes('Falling back to local')) {
      logActivity('WARN', source, clean);
    } else if (clean.toLowerCase().includes('warning') || clean.includes('[Audit Warning]') || clean.includes('[Local Warning]')) {
      logActivity('WARN', source, clean);
    } else {
      logActivity('ERROR', source, `Engine Stderr: ${clean}`);
    }
  }
}

export const runScoutSync = async () => {
  const extraEnv = buildPythonEnv();

  // Phase 1: Resumption Assessment
  let runId: string;
  let activeStage: 'SCOUT' | 'BACKFILL' | 'SCRAPE' | 'EVALUATE';

  const existing = db.prepare(`
    SELECT * FROM pipeline_runs 
    WHERE status IN ('FAILED', 'RUNNING') 
    AND updated_at > datetime('now', '-1 day')
    ORDER BY updated_at DESC LIMIT 1
  `).get() as { run_id: string; current_stage: string } | undefined;

  if (existing) {
    runId = existing.run_id;
    activeStage = existing.current_stage as any;
    logActivity('INFO', 'Scout', `Pipeline Resume: Recovered active run ${runId}. Resuming at [${activeStage}].`);
  } else {
    runId = `run_${Date.now()}`;
    activeStage = 'SCOUT';
    db.prepare(`
      UPDATE pipeline_runs SET status = 'FAILED', last_error = 'Superseded by newer run',
      updated_at = CURRENT_TIMESTAMP WHERE status = 'RUNNING'
    `).run();
    db.prepare(`INSERT INTO pipeline_runs (run_id, status, current_stage) VALUES (?, 'RUNNING', 'SCOUT')`).run(runId);
    logActivity('INFO', 'Scout', `Pipeline Start: Initialized run ${runId}.`);
  }

  // Set initial execution status
  db.prepare(`UPDATE pipeline_runs SET status = 'RUNNING', updated_at = CURRENT_TIMESTAMP WHERE run_id = ?`).run(runId);

  try {
    // --- STAGE 1: SCOUT ---
    if (activeStage === 'SCOUT') {
      updateCheckpoint(runId, 'SCOUT', 'Crawling and scanning direct job feeds...');
      logActivity('INFO', 'Scout', 'Executing Stage 1/5: Crawling job feeds via TS Crawler.');
      
      const code = await spawnProcessAsync('npx', ['tsx', 'scripts/scout_local.ts'], extraEnv, (output) => {
        const lines = output.trim().split('\n');
        for (const line of lines) {
          if (line.startsWith('[LOG]')) logActivity('INFO', 'Scout', line.replace('[LOG]', '').trim());
          else if (line.startsWith('[FOUND]')) logActivity('INFO', 'Scout', `Match Found: ${line.replace('[FOUND]', '').trim()}`);
          else if (line.startsWith('[ACTION]')) logActivity('WARN', 'Scout', `USER ACTION: ${line.replace('[ACTION]', '').trim()}`);
          else if (line.startsWith('[REJECT]')) logActivity('INFO', 'Scout', `Skipped: ${line.replace('[REJECT]', '').trim()}`);
          else if (line.trim()) logActivity('INFO', 'Scout', line.trim());
        }
      }, (stderr) => {
        handleStderr('Scout', stderr);
      });

      if (code !== 0) throw new Error(`Scout stage exited with non-zero code ${code}`);
      activeStage = 'BACKFILL';
    }

    // --- STAGE 2: BACKFILL ---
    if (activeStage === 'BACKFILL') {
      updateCheckpoint(runId, 'BACKFILL', 'Reconciling URLs and executing backfills...');
      logActivity('INFO', 'Scout', 'Executing Stage 2/5: Reconciling missing URLs.');

      const code = await spawnProcessAsync('npx', ['tsx', 'scripts/archive/backfill_urls.ts'], extraEnv, (output) => {
        output.trim().split('\n').forEach(line => line.trim() && logActivity('INFO', 'Crawler', line.trim()));
      }, (stderr) => {
        handleStderr('Crawler', stderr);
      });

      if (code !== 0) throw new Error(`Backfill stage exited with non-zero code ${code}`);
      activeStage = 'SCRAPE';
    }

    // --- STAGE 3: SCRAPE (requeue Needs Retry, then scrape New) ---
    if (activeStage === 'SCRAPE') {
      updateCheckpoint(runId, 'SCRAPE', 'Re-queuing jobs that need another pipeline pass...');
      logActivity('INFO', 'Scout', 'Executing Stage 3/5: Re-queuing Needs Retry jobs.');

      const requeueCode = await spawnProcessAsync('npx', ['tsx', 'scripts/requeue_needs_retry.ts'], extraEnv, (output) => {
        output.trim().split('\n').forEach(line => line.trim() && logActivity('INFO', 'Requeue', line.trim()));
      }, (stderr) => {
        handleStderr('Requeue', stderr);
      });

      if (requeueCode !== 0) throw new Error(`Requeue stage exited with non-zero code ${requeueCode}`);

      updateCheckpoint(runId, 'SCRAPE', 'Scraping job descriptions for new postings...');
      logActivity('INFO', 'Scout', 'Executing Stage 4/5: Scraping job descriptions.');

      const code = await spawnProcessAsync('npx', ['tsx', 'scripts/scrape_new_jobs.ts'], extraEnv, (output) => {
        output.trim().split('\n').forEach(line => line.trim() && logActivity('INFO', 'Scraper', line.trim()));
      }, (stderr) => {
        handleStderr('Scraper', stderr);
      });

      if (code !== 0) throw new Error(`Scrape stage exited with non-zero code ${code}`);
      activeStage = 'EVALUATE';
    }

    // --- STAGE 4: EVALUATE ---
    if (activeStage === 'EVALUATE') {
      updateCheckpoint(runId, 'EVALUATE', 'Evaluating fit and generating PDF assets...');
      logActivity('INFO', 'Scout', 'Executing Stage 5/5: Evaluating fit and drafting assets.');

      const code = await spawnProcessAsync('python', ['scripts/batch_pipeline.py', '--mode', 'batch'], extraEnv, (output) => {
        const lines = output.trim().split('\n');
        for (const line of lines) {
          const clean = line.trim();
          if (!clean) continue;
          if (clean.startsWith('[BATCH_PROGRESS]')) {
            const completed = clean.match(/completed=(\d+)/);
            const total = clean.match(/total=(\d+)/);
            const current = clean.match(/current=([^\s]+)/);
            const phase = clean.match(/phase=(\w+)/);
            const item =
              current && phase
                ? `Job ${completed?.[1] ?? '?'}/${total?.[1] ?? '?'}: ${current[1]} (${phase[1]})`
                : current?.[1];
            db.prepare(`
              UPDATE system_status SET
                status = 'evaluate_running',
                current_item = COALESCE(?, current_item),
                items_completed = COALESCE(?, items_completed),
                items_total = COALESCE(?, items_total),
                updated_at = CURRENT_TIMESTAMP
              WHERE id = 'global'
            `).run(
              item ?? null,
              completed ? Number(completed[1]) : null,
              total ? Number(total[1]) : null,
            );
          } else if (clean.startsWith('[JOB_PROGRESS]')) {
            const statusMsg = clean.replace('[JOB_PROGRESS]', '').trim();
            db.prepare(`
              UPDATE system_status SET status = 'evaluate_running', current_item = ?, updated_at = CURRENT_TIMESTAMP
              WHERE id = 'global'
            `).run(statusMsg);
          }
          logActivity('INFO', 'Pipeline', clean);
        }
      }, (stderr) => {
        handleStderr('Pipeline', stderr);
      });


      if (code !== 0) throw new Error(`Evaluation stage exited with non-zero code ${code}`);
    }

    // Final completion updates
    db.prepare(`UPDATE pipeline_runs SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP WHERE run_id = ?`).run(runId);
    db.prepare(`UPDATE system_status SET status = 'completed', current_item = 'Completed end-to-end sync successfully!', updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run();
    logActivity('INFO', 'Scout', `Pipeline ${runId} fully completed.`);

  } catch (err: any) {
    const errMsg = err.message || String(err);
    logActivity('ERROR', 'Scout', `Pipeline ${runId} aborted due to failure: ${errMsg}`);
    
    db.prepare(`UPDATE pipeline_runs SET status = 'FAILED', last_error = ?, updated_at = CURRENT_TIMESTAMP WHERE run_id = ?`).run(errMsg, runId);
    db.prepare(`UPDATE system_status SET status = 'idle', current_item = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run(`Sync stopped: ${errMsg}`);
  }
};
