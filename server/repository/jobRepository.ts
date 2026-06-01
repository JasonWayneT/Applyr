/**
 * Single write boundary for the jobs table.
 * Ensures FTS sync (syncJobFts / deleteJobFts) is never skipped on mutations.
 * Stale-job bookkeeping is always included with deletes (R-008 mitigation).
 */
import { randomUUID } from 'crypto';
import { db, syncJobFts, deleteJobFts } from '../db.js';
import { ALLOWED_JOB_FIELDS } from '../shared.js';

export interface InsertJobData {
    id?: string;
    company: string;
    title: string;
    url?: string | null;
    score?: number | null;
    status?: string;
    summary?: string | null;
    salary_range?: string | null;
    recruiter_name?: string | null;
    recruiter_url?: string | null;
    source_site?: string | null;
    jd_text?: string | null;
}

/**
 * Insert a new job row and sync the FTS index.
 * Uses run().lastInsertRowid so FTS sync never needs a separate SELECT rowid.
 */
export function insertJob(data: InsertJobData): string {
    const id = data.id ?? randomUUID();
    const result = db.prepare(`
        INSERT INTO jobs
            (id, company, title, url, score, status, summary,
             salary_range, recruiter_name, recruiter_url, source_site, jd_text, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    `).run(
        id,
        data.company,
        data.title,
        data.url ?? null,
        data.score ?? null,
        data.status ?? 'Drafted',
        data.summary ?? null,
        data.salary_range ?? null,
        data.recruiter_name ?? null,
        data.recruiter_url ?? null,
        data.source_site ?? null,
        data.jd_text ?? null,
    );
    syncJobFts(Number(result.lastInsertRowid));
    return id;
}

/**
 * Apply a partial update to allowed job fields and keep FTS in sync.
 * FTS is only re-synced when a searchable column changes.
 */
export function patchJob(id: string, updates: Record<string, unknown>): void {
    const keys = Object.keys(updates).filter(k => k !== 'id' && ALLOWED_JOB_FIELDS.has(k));
    if (keys.length === 0) return;
    const setClause = keys.map(k => `${k} = ?`).join(', ');
    db.prepare(`UPDATE jobs SET ${setClause} WHERE id = ?`).run(...keys.map(k => updates[k] as any), id);
    if (keys.some(k => ['company', 'title', 'summary', 'url'].includes(k))) {
        const row = db.prepare('SELECT rowid FROM jobs WHERE id = ?').get(id) as { rowid: number } | undefined;
        if (row?.rowid) syncJobFts(row.rowid);
    }
}

/**
 * Delete a job record, remove it from FTS, and add its URL to stale_jobs
 * so the scout never re-ingests the same posting (R-008 mitigation).
 */
export function deleteJobRecord(
    id: string,
    url: string | null | undefined,
    company: string,
    title: string,
): void {
    if (url) {
        db.prepare('INSERT OR IGNORE INTO stale_jobs (url, company, title) VALUES (?, ?, ?)').run(url, company, title);
    }
    const row = db.prepare('SELECT rowid FROM jobs WHERE id = ?').get(id) as { rowid: number } | undefined;
    if (row?.rowid) deleteJobFts(row.rowid);
    db.prepare('DELETE FROM jobs WHERE id = ?').run(id);
}
