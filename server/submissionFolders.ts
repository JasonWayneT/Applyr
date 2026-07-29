import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { db, logActivity } from './db.js';
import {
  SUBMISSION_DIR,
  ARCHIVE_DIR,
  resolveCompanyFolder,
} from './shared.js';
import { isActivePipelineStatus } from './domain/jobStatus.js';

/** Implements FR-030 — slug used for new folders; fuzzy match for existing ones. */
export function companySlug(company: string): string {
  let slug = company.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  if (!slug) {
    slug = 'company_' + crypto.createHash('md5').update(company).digest('hex').slice(0, 12);
  }
  return slug;
}

function folderNamesMatch(a: string, b: string): boolean {
  const norm = (s: string) => s.replace(/[_-]/g, '');
  return a === b || norm(a) === norm(b);
}

/** Merge files from src into dest (newer active copies overwrite archive). */
export function mergeSubmissionFolder(src: string, dest: string): void {
  fs.mkdirSync(dest, { recursive: true });
  for (const name of fs.readdirSync(src)) {
    const from = path.join(src, name);
    const to = path.join(dest, name);
    if (fs.statSync(from).isDirectory()) {
      mergeSubmissionFolder(from, to);
    } else {
      fs.copyFileSync(from, to);
    }
  }
}

/** Prefer atomic rename; on Windows EPERM (locked file/handle), fall back to copy+delete. */
function moveOrMergeFolder(src: string, dest: string): void {
  if (fs.existsSync(dest)) {
    mergeSubmissionFolder(src, dest);
    fs.rmSync(src, { recursive: true, force: true });
    return;
  }
  try {
    fs.renameSync(src, dest);
  } catch (err) {
    const code = (err as NodeJS.ErrnoException)?.code;
    if (code !== 'EPERM' && code !== 'EACCES' && code !== 'EBUSY') throw err;
    mergeSubmissionFolder(src, dest);
    fs.rmSync(src, { recursive: true, force: true });
  }
}

/** Move or merge active submissions folder into archive (FR-030). */
export function archiveActiveSubmission(company: string): boolean {
  const activePath = resolveCompanyFolder(company, SUBMISSION_DIR);
  if (!fs.existsSync(activePath)) return false;

  fs.mkdirSync(ARCHIVE_DIR, { recursive: true });
  const archivePath = resolveCompanyFolder(company, ARCHIVE_DIR);
  moveOrMergeFolder(activePath, archivePath);
  return true;
}

/** Restore archived folder to active workspace when status returns to Backlog/Drafted. */
export function restoreArchivedSubmission(company: string): boolean {
  const archivePath = resolveCompanyFolder(company, ARCHIVE_DIR);
  if (!fs.existsSync(archivePath)) return false;

  const activePath = resolveCompanyFolder(company, SUBMISSION_DIR);
  fs.mkdirSync(SUBMISSION_DIR, { recursive: true });
  moveOrMergeFolder(archivePath, activePath);
  return true;
}

function hasResumeAndCoverPdfs(folder: string): boolean {
  try {
    const pdfs = fs.readdirSync(folder).filter(f => f.toLowerCase().endsWith('.pdf'));
    const hasResume = pdfs.some(f => f.toLowerCase().includes('resume'));
    const hasCover = pdfs.some(f => f.toLowerCase().includes('cover'));
    return hasResume && hasCover;
  } catch {
    return false;
  }
}

function findJobsForFolder(folderName: string): { company: string; status: string }[] {
  const rows = db.prepare('SELECT company, status FROM jobs').all() as { company: string; status: string }[];
  return rows.filter(j => folderNamesMatch(companySlug(j.company), folderName));
}

/**
 * Ensures submissions/ only holds active pipeline workspaces.
 * Archives folders tied to Applied+ jobs; removes orphan stubs.
 */
export function reconcileActiveSubmissionFolders(): { archived: string[]; removed: string[] } {
  const archived: string[] = [];
  const removed: string[] = [];

  if (!fs.existsSync(SUBMISSION_DIR)) return { archived, removed };

  for (const folderName of fs.readdirSync(SUBMISSION_DIR)) {
    const activePath = path.join(SUBMISSION_DIR, folderName);
    if (!fs.statSync(activePath).isDirectory()) continue;

    const matches = findJobsForFolder(folderName);
    const inactive = matches.length > 0 && matches.every(j => !isActivePipelineStatus(j.status));
    const orphanStub = matches.length === 0 && !hasResumeAndCoverPdfs(activePath);

    if (!inactive && !orphanStub) continue;

    if (hasResumeAndCoverPdfs(activePath)) {
      const company = matches[0]?.company ?? folderName;
      if (archiveActiveSubmission(company)) archived.push(folderName);
    } else {
      fs.rmSync(activePath, { recursive: true, force: true });
      removed.push(folderName);
    }
  }

  return { archived, removed };
}

/**
 * Drafted jobs with resume + cover PDFs on disk but never promoted (e.g. manual draft scripts).
 * Promotes them to Backlog so they leave the scout queue.
 */
export function reconcileDraftedJobsWithAssets(): string[] {
  const rows = db.prepare(
    "SELECT id, company, score, summary FROM jobs WHERE status = 'Drafted'",
  ).all() as { id: string; company: string; score: number | null; summary: string | null }[];

  const promoted: string[] = [];
  for (const row of rows) {
    const folder = resolveCompanyFolder(row.company, SUBMISSION_DIR);
    if (!hasResumeAndCoverPdfs(folder)) continue;

    const scoreRow = db.prepare(
      'SELECT score_total FROM job_scores WHERE job_id = ? AND is_latest = 1',
    ).get(row.id) as { score_total: number } | undefined;

    const score = row.score ?? scoreRow?.score_total ?? null;
    const summary =
      row.summary?.trim() ||
      `Ready to apply — ${row.company} (assets on disk; promoted from Drafted queue).`;

    db.prepare(`
      UPDATE jobs
      SET status = 'Backlog',
          score = COALESCE(?, score),
          summary = ?,
          retry_count = 0
      WHERE id = ?
    `).run(score, summary, row.id);

    promoted.push(row.company);
    logActivity(
      'INFO',
      'System',
      `Promoted "${row.company}" from Drafted to Backlog (resume + cover PDFs on disk).`,
    );
  }
  return promoted;
}

function titleCaseFromSlug(folderName: string): string {
  return folderName
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function readJdMeta(folderPath: string): { title: string; url: string; jdText: string } {
  const jdPath = path.join(folderPath, 'Original_JD.txt');
  let jdText = '';
  try {
    jdText = fs.readFileSync(jdPath, 'utf8');
  } catch {
    return { title: '', url: '', jdText: '' };
  }

  const lines = jdText.replace(/^\uFEFF/, '').split(/\r?\n/);
  let url = '';
  let start = 0;
  if (lines[0]?.toLowerCase().startsWith('url:')) {
    url = lines[0].slice(4).trim();
    start = 1;
  }

  let title = '';
  for (let i = start; i < Math.min(lines.length, start + 8); i++) {
    const line = lines[i]?.trim() || '';
    if (!line) continue;
    const low = line.toLowerCase();
    if (low.startsWith('company:') || low.startsWith('company ') || low.startsWith('position:')) {
      continue;
    }
    if (
      low.startsWith('about ') ||
      low.startsWith('who we') ||
      low.startsWith('overview') ||
      low.startsWith('job description') ||
      low.startsWith('position ')
    ) {
      break;
    }
    if (line.length < 120 && !line.endsWith('.')) {
      title = line;
      break;
    }
  }

  return { title, url, jdText: lines.slice(start).join('\n').trim() };
}

/**
 * Submission folders with resume + cover PDFs but no matching jobs row.
 * Manual drafts / external packet drops land here; create Backlog rows so Today/All Jobs show them.
 */
export function reconcileOrphanSubmissionFolders(): string[] {
  if (!fs.existsSync(SUBMISSION_DIR)) return [];

  const created: string[] = [];
  for (const folderName of fs.readdirSync(SUBMISSION_DIR)) {
    const activePath = path.join(SUBMISSION_DIR, folderName);
    if (!fs.statSync(activePath).isDirectory()) continue;
    if (!hasResumeAndCoverPdfs(activePath)) continue;
    if (findJobsForFolder(folderName).length > 0) continue;

    const company = titleCaseFromSlug(folderName);
    const meta = readJdMeta(activePath);
    const title = meta.title || 'Product Manager';
    const id = crypto.randomUUID().replace(/-/g, '').slice(0, 8);
    const summary = `Ready to apply — ${company} (assets on disk; linked from submissions/).`;

    db.prepare(`
      INSERT INTO jobs (id, company, title, url, score, status, summary, jd_text, retry_count)
      VALUES (?, ?, ?, ?, 80, 'Backlog', ?, ?, 0)
    `).run(id, company, title, meta.url || null, summary, meta.jdText || null);

    created.push(company);
    logActivity(
      'INFO',
      'System',
      `Linked orphan submission folder "${folderName}" as Backlog job ${id} (${company}).`,
    );
  }
  return created;
}

export function jobHasPdfAssets(company: string, status: string): boolean {
  const base = isActivePipelineStatus(status) ? SUBMISSION_DIR : ARCHIVE_DIR;
  const folder = resolveCompanyFolder(company, base);
  if (!fs.existsSync(folder)) return false;
  try {
    return fs.readdirSync(folder).some(f => f.toLowerCase().endsWith('.pdf'));
  } catch {
    return false;
  }
}
