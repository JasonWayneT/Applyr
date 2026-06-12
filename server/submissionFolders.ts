import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { db } from './db.js';
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
  return a === b || a.replace(/_/g, '') === b.replace(/_/g, '');
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

/** Move or merge active submissions folder into archive (FR-030). */
export function archiveActiveSubmission(company: string): boolean {
  const activePath = resolveCompanyFolder(company, SUBMISSION_DIR);
  if (!fs.existsSync(activePath)) return false;

  fs.mkdirSync(ARCHIVE_DIR, { recursive: true });
  const archivePath = resolveCompanyFolder(company, ARCHIVE_DIR);

  if (fs.existsSync(archivePath)) {
    mergeSubmissionFolder(activePath, archivePath);
    fs.rmSync(activePath, { recursive: true, force: true });
  } else {
    fs.renameSync(activePath, archivePath);
  }
  return true;
}

/** Restore archived folder to active workspace when status returns to Backlog/Drafted. */
export function restoreArchivedSubmission(company: string): boolean {
  const archivePath = resolveCompanyFolder(company, ARCHIVE_DIR);
  if (!fs.existsSync(archivePath)) return false;

  const activePath = resolveCompanyFolder(company, SUBMISSION_DIR);
  fs.mkdirSync(SUBMISSION_DIR, { recursive: true });

  if (fs.existsSync(activePath)) {
    mergeSubmissionFolder(archivePath, activePath);
    fs.rmSync(archivePath, { recursive: true, force: true });
  } else {
    fs.renameSync(archivePath, activePath);
  }
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
