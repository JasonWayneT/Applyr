import fs from 'fs';
import path from 'path';
import { PROJECT_ROOT } from '../domain/paths.js';

export const JOBS_STAGING_DIR = path.join(PROJECT_ROOT, 'jobs');

export function companyStagingSlug(company: string): string {
  return company.replace(/[^a-z0-9]+/gi, '_').trim();
}

export function stagingFilePath(company: string, jobId: string): string {
  return path.join(JOBS_STAGING_DIR, `${companyStagingSlug(company)}_${jobId.slice(0, 8)}.txt`);
}

export function stagingFileExists(company: string, jobId: string): boolean {
  return fs.existsSync(stagingFilePath(company, jobId));
}

export function writeJobStagingFile(
  jobId: string,
  company: string,
  url: string | null | undefined,
  jdText: string,
): string {
  const filePath = stagingFilePath(company, jobId);
  fs.mkdirSync(JOBS_STAGING_DIR, { recursive: true });
  const prefix = url ? `URL: ${url}\n\n` : '';
  fs.writeFileSync(filePath, `${prefix}${jdText}`, 'utf-8');
  return filePath;
}
