// CR-072 Story 2.5 — ties together Stories 1.3/2.1/2.2/2.3/2.4 into one sync pass. Called on server
// startup and on a 10-minute interval (Epic 3), but is itself trigger-agnostic — nothing in here assumes
// how or when it's invoked.
import { db, logActivity } from '../db.js';
import { createGmailClient } from './gmailClient.js';
import { createEmailSyncCursor } from './emailSyncCursor.js';
import { classifyEmailText, classifyEmailWithLLM, extractSubjectAndBody } from './emailClassifier.js';
import { matchJobForEmail, type MatchableJob } from './jobMatcher.js';
import { applyJobStatusUpdate } from './jobStatusService.js';
import { isDryRunEnabled } from './gmailSyncConfig.js';
import { extractInterviewDateTime, type ExtractedInterviewDateTime } from './interviewDateExtractor.js';
import { deriveStatusForInterviewDateChange } from '../../shared/domain/jobPipeline.js';

const INCOMING_LABEL = 'Applyr/Incoming';
const REJECTED_LABEL = 'Applyr/Rejected';
const INTERVIEW_LABEL = 'Applyr/Interview';

export interface GmailSyncSummary {
  scanned: number;
  classified: number;
  matched: number;
  written: number;
  unmatched: number;
  dryRun: boolean;
  /** CR-105: how many of `classified` came from the pattern layer missing and the Groq/LLM
   *  fallback catching it — a high ratio here is a real signal the free pattern layer needs
   *  more coverage, the same way the original classifier audit found real gaps. */
  llmFallbackUsed: number;
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

  const summary: GmailSyncSummary = {
    scanned: newIds.length,
    classified: 0,
    matched: 0,
    written: 0,
    unmatched: 0,
    dryRun,
    llmFallbackUsed: 0,
  };

  for (const messageId of newIds) {
    try {
      const message = await gmail.getMessage(messageId);
      const { subject, bodyText } = extractSubjectAndBody(message);
      let category = classifyEmailText(subject, bodyText);
      let usedLlmFallback = false;
      if (!category) {
        // CR-105: the free pattern layer wasn't confident — try the low-confidence fallback
        // before giving up. Still a real cost (an API call), so only reached for the minority
        // of mail the pattern layer can't already handle for free.
        category = await classifyEmailWithLLM(subject, bodyText);
        usedLlmFallback = category !== null;
        if (usedLlmFallback) summary.llmFallbackUsed++;
      }

      if (!category) {
        cursor.markProcessed(INCOMING_LABEL, messageId);
        continue;
      }
      summary.classified++;

      const fromHeader = message.payload?.headers?.find((h) => h.name === 'From')?.value ?? null;
      const match = matchJobForEmail(jobs, { fromHeader, subject, bodyText });
      const receivedAt = formatReceivedDate(message.internalDate);

      if (!match) {
        // Previously a fully silent skip — no trace at all once cursor.markProcessed ran below, which is
        // exactly what made the "Realtime Software Solutions" miss (2026-08-11) undiagnosable without a
        // hand-simulated run against pasted email content. This is the single highest-value case to log:
        // the classifier successfully recognized this as a real application email, so the reason it went
        // untracked is a matching gap (usually the job's stored `company` name not matching what the
        // employer's own email actually calls itself) rather than "not application mail at all."
        summary.unmatched++;
        logActivity(
          'WARN',
          'GmailSync',
          `Could not match this "${category}" email to a tracked job — no auto-action taken: "${subject}"`,
          {
            event: 'gmail_sync_unmatched',
            category,
            subject,
            from_header: fromHeader,
            received_at: receivedAt,
          },
        );
        cursor.markProcessed(INCOMING_LABEL, messageId);
        continue;
      }
      summary.matched++;

      const job = jobs.find((j) => j.id === match.jobId)!;
      const labelIds = message.labelIds ?? [];
      const gmailAgreement = {
        gmail_rejected_label: rejectedLabelId ? labelIds.includes(rejectedLabelId) : null,
        gmail_interview_label: interviewLabelId ? labelIds.includes(interviewLabelId) : null,
      };

      // CR-106: computed once, ahead of the dry-run branch below, so both the dry-run preview
      // message and the real write use the same result — extraction itself has no side effects
      // (no DB write), so running it during a dry run is safe and gives an honest preview.
      let interviewExtraction: ExtractedInterviewDateTime | null = null;
      if (category === 'interview') {
        interviewExtraction = await extractInterviewDateTime(subject, bodyText);
      }

      if (dryRun) {
        const intendedAction =
          category === 'rejection'
            ? `close job as Rejected`
            : category === 'interview'
              ? interviewExtraction
                ? `advance status and set interview_date to ${interviewExtraction.isoDateTime} (via ${interviewExtraction.method})`
                : `log interview detected, no date/time found — no status change`
              : `log confirmation, no status change`;
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
            classified_via: usedLlmFallback ? 'llm_fallback' : 'pattern',
            ...gmailAgreement,
          },
        );
      } else if (category === 'rejection') {
        applyJobStatusUpdate(job.id, {
          status: 'Rejected',
          rejection_type: 'Rejected',
          outcome_notes: `Auto-detected from email: "${subject}" (received ${receivedAt})`,
        });
        // Dedicated GmailSync-sourced entry (separate from applyJobStatusUpdate's generic 'System'
        // status-change line) so the Notifications panel can find every real Gmail-detected event
        // under one source string, the same way the confirmation branch below already does.
        logActivity(
          'INFO',
          'GmailSync',
          `Rejection detected for "${job.company}" — job closed: "${subject}"`,
          {
            event: 'gmail_sync_rejection',
            job_id: job.id,
            company: job.company,
            subject,
            received_at: receivedAt,
            // CR-105: this action auto-closes a job — worth knowing whether a deterministic
            // pattern made this call or the LLM fallback's judgment did, while that fallback is new.
            classified_via: usedLlmFallback ? 'llm_fallback' : 'pattern',
          },
        );
        summary.written++;
      } else if (category === 'interview') {
        // CR-106: auto-advances status the same way the rejection branch above auto-closes —
        // only when a date/time was actually extracted AND deriveStatusForInterviewDateChange
        // says this status is eligible to move forward (it returns null for a job already past
        // 'Core Interviews', or in a terminal status — same forward-only rule the manual
        // PATCH /api/jobs/:id route already applies). Anything else stays log-only, exactly the
        // prior CR-105 behavior — a missed/ambiguous date should never block on
        // applyJobStatusUpdate's missing_interview_date gate, it should just not attempt the write.
        let statusWritten: string | null = null;
        if (interviewExtraction) {
          const current = db.prepare('SELECT status FROM jobs WHERE id = ?').get(job.id) as
            | { status: string }
            | undefined;
          const derivedStatus = current ? deriveStatusForInterviewDateChange(current.status) : null;
          if (derivedStatus) {
            const result = applyJobStatusUpdate(job.id, {
              status: derivedStatus,
              interview_date: interviewExtraction.isoDateTime,
            });
            if (result.kind === 'updated') statusWritten = derivedStatus;
          }
        }
        logActivity(
          'INFO',
          'GmailSync',
          statusWritten
            ? `Interview detected for "${job.company}" — advanced to ${statusWritten}, interview_date set to ${interviewExtraction!.isoDateTime}: "${subject}"`
            : `Interview detected for "${job.company}" — no status change: "${subject}"`,
          {
            event: 'gmail_sync_interview',
            job_id: job.id,
            company: job.company,
            subject,
            received_at: receivedAt,
            classified_via: usedLlmFallback ? 'llm_fallback' : 'pattern',
            status_written: statusWritten,
            interview_date: interviewExtraction?.isoDateTime ?? null,
            date_extraction_method: interviewExtraction?.method ?? null,
          },
        );
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
            classified_via: usedLlmFallback ? 'llm_fallback' : 'pattern',
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
