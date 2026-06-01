/**
 * Pipeline mutual-exclusion primitives.
 * Extracted from middleware.ts (CR-ARCH-002 follow-up).
 * Uses a single SQLite row for CAS — works correctly under WAL mode.
 */
import { db } from './db.js';

const BUSY_STATUSES = new Set(['drafting', 'scout_running', 'evaluate_running']);

export function isPipelineBusy(): boolean {
    const row = db.prepare(`SELECT status FROM system_status WHERE id = 'global'`).get() as
        | { status: string }
        | undefined;
    return BUSY_STATUSES.has(row?.status ?? '');
}

export function tryAcquirePipeline(currentItem: string): boolean {
    if (isPipelineBusy()) return false;
    const result = db.prepare(`
        UPDATE system_status
        SET status = 'drafting', current_item = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = 'global' AND status NOT IN ('drafting', 'scout_running', 'evaluate_running')
    `).run(currentItem);
    return result.changes > 0;
}

export function releasePipeline(message: string): void {
    db.prepare(`
        UPDATE system_status
        SET status = 'completed', current_item = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = 'global'
    `).run(message);
}
