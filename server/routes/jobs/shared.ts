import { SUBMISSION_DIR, ARCHIVE_DIR } from '../../shared.js';
import { submissionBaseDir } from '../../domain/jobStatus.js';

export function jobBaseDir(status: string): string {
  return submissionBaseDir(status, SUBMISSION_DIR, ARCHIVE_DIR);
}
