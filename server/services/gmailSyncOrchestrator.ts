// CR-072 Story 2.5 — ties together Stories 1.3/2.1/2.2/2.3/2.4 into one sync pass. Called on server
// startup and on a 10-minute interval (Epic 3), but is itself trigger-agnostic — nothing in here assumes
// how or when it's invoked.
import { db, logActivity } from '../db.js';
import { createGmailClient } from './gmailClient.js';
import { createEmailSyncCursor } from './emailSyncCursor.js';
import { classifyEmailText, extractSubjectAndBody } from './emailClassifier.js';
import { matchJobForEmail, type MatchableJob } from './jobMatcher.js';
import { applyJobStatusUpdate } from './jobStatusService.js';
import { isDryRunEnabled } from './gmailSyncConfig.js';

const INCOMING_LABEL = 'Applyr/Incoming';
const REJECTED_LABEL = 'Applyr/Rejected';
const INTERVIEW_LABEL = 'Applyr/Interview';

export interface GmailSyncSummary {
  scanned: number;
  classified: number;
  matched: number;
  written: number;
  dryRun: boolean;
}

function formatReceivedDate(internalDate: string | null | undefined): string {
  if (!internalDate) return 'unknown date';
  const ms = Number(internalDate);
  return Number.isFinite(ms) ? new Date(ms).toISOString() : 'unknown date';
}

export async function runGmailSync(): Promise<GmailSyncSummary> {
  const gmail = createGmailClient(db);
  const cursor = createEmailSyncCursor(db);
  const dryRun = isDryRunEnabled(db);

  const [rejectedLabelId, interviewLabelId, messageIds] = await Promise.all([
    gmail.resolveLabelId(REJECTED_LABEL),
    gmail.resolveLabelId(INTERVIEW_LABEL),
    gmail.listMessageIdsUnderLabel(INCOMING_LABEL),
  ]);

  const newIds = messageIds.filter((id) => !cursor.hasProcessed(INCOMING_LABEL, id));
  const jobs = db.prepare('SELECT id, company, url FROM jobs').all() as MatchableJob[];

  const summary: GmailSyncSummary = { scanned: newIds.length, classified: 0, matched: 0, written: 0, dryRun };

  for (const messageId of newIds) {
    try {
      const message = await gmail.getMessage(messageId);
      const { subject, bodyText } = extractSubjectAndBody(message);
      const category = classifyEmailText(subject, bodyText);

      if (!category) {
        cursor.markProcessed(INCOMING_LABEL, messageId);
        continue;
      }
      summary.classified++;

      const fromHeader = message.payload?.headers?.find((h) => h.name === 'From')?.value ?? null;
      const match = matchJobForEmail(jobs, { fromHeader, subject, bodyText });

      if (!match) {
        cursor.markProcessed(INCOMING_LABEL, messageId);
        continue;
      }
      summary.matched++;

      const job = jobs.find((j) => j.id === match.jobId)!;
      const receivedAt = formatReceivedDate(message.internalDate);
      const labelIds = message.labelIds ?? [];
      const gmailAgreement = {
        gmail_rejected_label: rejectedLabelId ? labelIds.includes(rejectedLabelId) : null,
        gmail_interview_label: interviewLabelId ? labelIds.includes(interviewLabelId) : null,
      };

      if (dryRun) {
        const intendedAction =
          category === 'rejection' ? `close job as Rejected` : `log confirmation, no status change`;
        logActivity(
          'INFO',
          'GmailSyncDryRun',
          `[DRY RUN] "${job.company}": would ${intendedAction} — email "${subject}"`,
          {
            event: 'gmail_sync_dry_run',
            message_id: messageId,
            job_id: job.id,
            company: job.company,
            category,
            match_method: match.method,
            subject,
            received_at: receivedAt,
            ...gmailAgreement,
          },
        );
      } else if (category === 'rejection') {
        applyJobStatusUpdate(job.id, {
          status: 'Rejected',
          rejection_type: 'Rejected',
          outcome_notes: `Auto-detected from email: "${subject}" (received ${receivedAt})`,
        });
        summary.written++;
      } else {
        logActivity(
          'INFO',
          'GmailSync',
          `Application confirmation received for "${job.company}": "${subject}"`,
          {
            event: 'gmail_sync_confirmation',
            job_id: job.id,
            company: job.company,
            subject,
            received_at: receivedAt,
          },
        );
        summary.written++;
      }

      cursor.markProcessed(INCOMING_LABEL, messageId);
    } catch (err) {
      // Per-message error isolation (Epic 3, Story 3.2) — deliberately do NOT mark this message as
      // processed on failure, so it's retried on the next sync pass instead of silently dropped.
      logActivity(
        'ERROR',
        'GmailSync',
        `Failed to process Gmail message ${messageId}: ${(err as Error).message}`,
      );
    }
  }

  return summary;
}
