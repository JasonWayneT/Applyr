// CR-072 Epic 3 — runs the Gmail sync once on server startup, then on a 10-minute interval for as long
// as the process stays alive. No push/webhook, no Pub/Sub — see CR-072's Decision section for why polling
// on this cadence was chosen deliberately over anything more complex.
import { logActivity } from '../db.js';
import { runGmailSync } from './gmailSyncOrchestrator.js';

const SYNC_INTERVAL_MS = 10 * 60 * 1000; // 10 minutes

let syncInProgress = false;

async function runSyncPassSafely(): Promise<void> {
  if (syncInProgress) {
    // A pass is still running from a previous tick — should be rare at personal-mailbox scale (a full
    // pass normally completes in seconds), but skip rather than overlap if it happens.
    return;
  }
  syncInProgress = true;
  try {
    const summary = await runGmailSync();
    console.log(
      `[GmailSync] scanned=${summary.scanned} classified=${summary.classified} ` +
        `matched=${summary.matched} written=${summary.written} dryRun=${summary.dryRun}`,
    );
  } catch (err) {
    // Whole-pass failure isolation (Story 3.2) — a Gmail API outage, missing/expired credentials, or any
    // error thrown before runGmailSync's own per-message try/catch even starts. Must never crash the
    // server or prevent the next scheduled tick from running.
    logActivity('ERROR', 'GmailSync', `Gmail sync pass failed: ${(err as Error).message}`);
  } finally {
    syncInProgress = false;
  }
}

export function startGmailSyncScheduler(): void {
  void runSyncPassSafely(); // immediate pass on startup
  setInterval(() => {
    void runSyncPassSafely();
  }, SYNC_INTERVAL_MS);
}
