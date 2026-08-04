import { db, logActivity } from './db.js';
import { buildPythonEnv, buildTsxSpawn } from './shared.js';
import { isPipelineBusy } from './pipelineLock.js';
import { runStreamLines } from './pipeline/processRunner.js';
import { runConnectorOrchestration } from './services/scoutOrchestrator.js';
import { exportPendingReviewJobs } from './services/exportPendingReview.js';

function spawnProcessAsync(
  command: string,
  args: string[],
  env: Record<string, string>,
  onStdout: (data: string) => void,
  onStderr: (data: string) => void,
): Promise<number> {
  return runStreamLines(command, args, { env, onStdout, onStderr });
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
                   clean.includes('[ZERO-TOKEN REJECT]') ||
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

import { broadcastSyncEvent } from './routes/pipeline.js';

export const runScoutSync = async () => {
  if (isPipelineBusy()) {
    logActivity('WARN', 'Scout', 'Sync skipped — pipeline already running.');
    return;
  }

  db.prepare(`
    UPDATE system_status SET status = 'scout_running', current_item = 'Scout pipeline starting...',
    updated_at = CURRENT_TIMESTAMP WHERE id = 'global'
  `).run();

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
      broadcastSyncEvent('stage_handoff', { type: 'stage_handoff', from: 'NONE', to: 'SCOUT', total_passed: 0 });
      updateCheckpoint(runId, 'SCOUT', 'Running connector orchestration...');
      logActivity('INFO', 'Scout', 'Executing Stage 1/5: Running job connector orchestration.');
      await runConnectorOrchestration();
      activeStage = 'BACKFILL';
    }

    // --- STAGE 2: BACKFILL ---
    if (activeStage === 'BACKFILL') {
      broadcastSyncEvent('stage_handoff', { type: 'stage_handoff', from: 'SCOUT', to: 'BACKFILL', total_passed: 0 });
      updateCheckpoint(runId, 'BACKFILL', 'Reconciling URLs and executing backfills...');
      logActivity('INFO', 'Scout', 'Executing Stage 2/5: Reconciling missing URLs.');

      const backfillSpawn = buildTsxSpawn('scripts/backfill_urls.ts');
      const code = await spawnProcessAsync(backfillSpawn.command, backfillSpawn.args, extraEnv, (output) => {
        output.trim().split('\n').forEach(line => line.trim() && logActivity('INFO', 'Crawler', line.trim()));
      }, (stderr) => {
        handleStderr('Crawler', stderr);
      });

      if (code !== 0) throw new Error(`Backfill stage exited with non-zero code ${code}`);
      activeStage = 'SCRAPE';
    }

    // --- STAGE 3: SCRAPE (requeue Needs Retry, then scrape New) ---
    if (activeStage === 'SCRAPE') {
      broadcastSyncEvent('stage_handoff', { type: 'stage_handoff', from: 'BACKFILL', to: 'SCRAPE', total_passed: 0 });
      updateCheckpoint(runId, 'SCRAPE', 'Re-queuing jobs that need another pipeline pass...');
      logActivity('INFO', 'Scout', 'Executing Stage 3/5: Re-queuing Needs Retry jobs.');

      const requeueSpawn = buildTsxSpawn('scripts/requeue_needs_retry.ts');
      const requeueCode = await spawnProcessAsync(requeueSpawn.command, requeueSpawn.args, extraEnv, (output) => {
        output.trim().split('\n').forEach(line => line.trim() && logActivity('INFO', 'Requeue', line.trim()));
      }, (stderr) => {
        handleStderr('Requeue', stderr);
      });

      if (requeueCode !== 0) throw new Error(`Requeue stage exited with non-zero code ${requeueCode}`);

      updateCheckpoint(runId, 'SCRAPE', 'Scraping job descriptions for new postings...');
      logActivity('INFO', 'Scout', 'Executing Stage 4/5: Scraping job descriptions.');

      const scrapeSpawn = buildTsxSpawn('scripts/scrape_new_jobs.ts');
      const code = await spawnProcessAsync(scrapeSpawn.command, scrapeSpawn.args, extraEnv, (output) => {
        output.trim().split('\n').forEach(line => line.trim() && logActivity('INFO', 'Scraper', line.trim()));
      }, (stderr) => {
        handleStderr('Scraper', stderr);
      });

      if (code !== 0) throw new Error(`Scrape stage exited with non-zero code ${code}`);
      activeStage = 'EVALUATE';
    }

    // --- STAGE 4: REVIEW EXPORT (was EVALUATE — silent auto-draft removed 2026-08-04) ---
    // No Ollama, no batch_pipeline. Gate-passed Drafted jobs with JD text → data/pending_review/.
    if (activeStage === 'EVALUATE') {
      broadcastSyncEvent('stage_handoff', { type: 'stage_handoff', from: 'SCRAPE', to: 'EVALUATE', total_passed: 0 });

      updateCheckpoint(runId, 'EVALUATE', 'Exporting new JDs to pending review...');
      logActivity(
        'INFO',
        'Scout',
        'Executing Stage 5/5: Exporting gate-passed JDs to data/pending_review/ (no LLM, no auto-draft).',
      );

      db.prepare(`
        UPDATE system_status SET status = 'evaluate_running', current_item = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = 'global'
      `).run('Exporting jobs to pending review...');

      const result = exportPendingReviewJobs();
      const total = result.exported + result.skippedExisting;
      db.prepare(`
        UPDATE system_status SET
          status = 'evaluate_running',
          current_item = ?,
          items_completed = ?,
          items_total = ?,
          updated_at = CURRENT_TIMESTAMP
        WHERE id = 'global'
      `).run(
        `Review export: ${result.exported} new, ${result.skippedExisting} already on disk`,
        total,
        total,
      );
      logActivity(
        'INFO',
        'Scout',
        `Review export complete: ${result.exported} written, ${result.skippedExisting} already present (${total} total this run).`,
      );
    }

    // Final completion updates
    db.prepare(`UPDATE pipeline_runs SET status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP WHERE run_id = ?`).run(runId);
    db.prepare(`UPDATE system_status SET status = 'completed', current_item = 'Completed end-to-end sync successfully!', updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run();
    logActivity('INFO', 'Scout', `Pipeline ${runId} fully completed.`);

    // Find warned/errored sources
    const sourcesWarned = db.prepare("SELECT name FROM sources WHERE status IN ('warning', 'error')").all().map((s: any) => s.name);
    broadcastSyncEvent('run_complete', {
      type: 'run_complete',
      total_fetched: 0,
      total_passed: 0,
      sources_warned: sourcesWarned,
    });

  } catch (err: any) {
    const errMsg = err.message || String(err);
    logActivity('ERROR', 'Scout', `Pipeline ${runId} aborted due to failure: ${errMsg}`);
    
    db.prepare(`UPDATE pipeline_runs SET status = 'FAILED', last_error = ?, updated_at = CURRENT_TIMESTAMP WHERE run_id = ?`).run(errMsg, runId);
    db.prepare(`UPDATE system_status SET status = 'idle', current_item = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run(`Sync stopped: ${errMsg}`);

    broadcastSyncEvent('connector_error', {
      type: 'connector_error',
      source: 'Scout',
      error: errMsg,
    });
  }
};
