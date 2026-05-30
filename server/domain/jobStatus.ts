/**
 * Canonical job status rules for submission folder placement (CR-ARCH-002 / FR-030).
 */
export const ACTIVE_STATUSES = new Set(['Backlog', 'Drafted']);

export function isActivePipelineStatus(status: string): boolean {
  return ACTIVE_STATUSES.has(status);
}

export function submissionBaseDir(status: string, submissionDir: string, archiveDir: string): string {
  return isActivePipelineStatus(status) ? submissionDir : archiveDir;
}
