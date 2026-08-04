/**
 * Export scraped, gate-passed jobs to data/pending_review/ for human Stage 0 review.
 *
 * Replaces the Sync EVALUATE stage's silent Ollama + batch_pipeline auto-draft path
 * (SESSION-HANDOFF-2026-08-04-URGENT-disable-silent-autodraft + sync-review-queue).
 *
 * No LLM calls. Title/geo/industry gates already ran at connector ingest
 * (scoutOrchestrator). This step only picks Drafted rows with real JD text that
 * have not been exported yet (exported_for_review_at IS NULL).
 */
import fs from 'fs';
import path from 'path';
import { db, logActivity } from '../db.js';
import { PROJECT_ROOT, sanitizeCompanySlug } from '../shared.js';

export const PENDING_REVIEW_DIR = path.join(PROJECT_ROOT, 'data', 'pending_review');

export type PendingReviewJobRow = {
  id: string;
  company: string;
  title: string;
  url: string | null;
  jd_text: string;
};

export type ExportPendingReviewResult = {
  exported: number;
  skippedExisting: number;
  folders: string[];
};

/** Folder name: {slug}_{id8} so two roles at the same company never collide. */
export function pendingReviewFolderName(company: string, jobId: string): string {
  const slug = sanitizeCompanySlug(company);
  const id8 = jobId.replace(/-/g, '').slice(0, 8);
  return `${slug}_${id8}`;
}

/** CLAUDE.md Original_JD.txt convention: optional URL line, blank line, then raw JD. */
export function formatOriginalJd(url: string | null | undefined, jdText: string): string {
  const body = jdText.replace(/^\uFEFF/, '').trimEnd();
  if (url && url.trim()) {
    return `URL: ${url.trim()}\n\n${body}\n`;
  }
  return `${body}\n`;
}

function selectPendingRows(): PendingReviewJobRow[] {
  return db
    .prepare(
      `SELECT id, company, title, url, jd_text
       FROM jobs
       WHERE exported_for_review_at IS NULL
         AND status = 'Drafted'
         AND jd_text IS NOT NULL
         AND LENGTH(TRIM(jd_text)) >= 200`,
    )
    .all() as PendingReviewJobRow[];
}

/**
 * Write Original_JD.txt for each unexported Drafted job and stamp exported_for_review_at.
 * Idempotent: rows already stamped are not selected; existing folders are not rewritten
 * (row is still stamped so Sync won't keep retrying a stuck folder).
 */
export function exportPendingReviewJobs(): ExportPendingReviewResult {
  fs.mkdirSync(PENDING_REVIEW_DIR, { recursive: true });

  const rows = selectPendingRows();
  const folders: string[] = [];
  let exported = 0;
  let skippedExisting = 0;

  const stamp = db.prepare(
    `UPDATE jobs SET exported_for_review_at = CURRENT_TIMESTAMP WHERE id = ? AND exported_for_review_at IS NULL`,
  );

  for (const row of rows) {
    const folderName = pendingReviewFolderName(row.company, row.id);
    const folderPath = path.join(PENDING_REVIEW_DIR, folderName);
    const jdPath = path.join(folderPath, 'Original_JD.txt');

    if (fs.existsSync(jdPath)) {
      stamp.run(row.id);
      skippedExisting += 1;
      folders.push(folderName);
      continue;
    }

    fs.mkdirSync(folderPath, { recursive: true });
    fs.writeFileSync(jdPath, formatOriginalJd(row.url, row.jd_text), 'utf8');
    stamp.run(row.id);
    exported += 1;
    folders.push(folderName);
    logActivity(
      'INFO',
      'ReviewExport',
      `Exported "${row.company}" / ${row.title} → pending_review/${folderName}`,
    );
  }

  return { exported, skippedExisting, folders };
}
