import { randomUUID } from 'crypto';
import { db } from '../db.js';
import {
  isValidDebriefOutcome,
  normalizeDebriefDate,
  type InterviewDebrief,
  type InterviewDebriefOutcome,
} from '../../shared/domain/interviewDebrief.js';

type DebriefRow = {
  id: string;
  job_id: string;
  debrief_date: string;
  notes: string;
  outcome: string;
  created_at: string;
  updated_at: string;
};

function mapRow(row: DebriefRow): InterviewDebrief {
  return {
    id: row.id,
    job_id: row.job_id,
    date: row.debrief_date,
    notes: row.notes,
    outcome: row.outcome as InterviewDebriefOutcome,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

export function listInterviewDebriefs(jobId: string): InterviewDebrief[] {
  const rows = db.prepare(`
    SELECT id, job_id, debrief_date, notes, outcome, created_at, updated_at
    FROM interview_debriefs
    WHERE job_id = ?
    ORDER BY debrief_date DESC, created_at DESC
  `).all(jobId) as DebriefRow[];
  return rows.map(mapRow);
}

export function getInterviewDebrief(jobId: string, debriefId: string): InterviewDebrief | null {
  const row = db.prepare(`
    SELECT id, job_id, debrief_date, notes, outcome, created_at, updated_at
    FROM interview_debriefs
    WHERE id = ? AND job_id = ?
  `).get(debriefId, jobId) as DebriefRow | undefined;
  return row ? mapRow(row) : null;
}

export function createInterviewDebrief(
  jobId: string,
  input: { date: unknown; notes: unknown; outcome?: unknown },
): { debrief: InterviewDebrief } | { error: string } {
  const debriefDate = normalizeDebriefDate(input.date);
  if (!debriefDate) return { error: 'date is required and must be a valid date' };

  const notes = typeof input.notes === 'string' ? input.notes.trim() : '';
  if (!notes) return { error: 'notes are required' };

  if (!isValidDebriefOutcome(input.outcome)) {
    return { error: 'outcome is required' };
  }
  const outcome: InterviewDebriefOutcome = input.outcome;

  const id = randomUUID();
  const now = new Date().toISOString();

  db.prepare(`
    INSERT INTO interview_debriefs (id, job_id, debrief_date, notes, outcome, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(id, jobId, debriefDate, notes, outcome, now, now);

  const debrief = getInterviewDebrief(jobId, id);
  if (!debrief) return { error: 'Failed to create debrief' };
  return { debrief };
}

export function updateInterviewDebrief(
  jobId: string,
  debriefId: string,
  input: { date?: unknown; notes?: unknown; outcome?: unknown },
): { debrief: InterviewDebrief } | { error: string; notFound?: boolean } {
  const existing = getInterviewDebrief(jobId, debriefId);
  if (!existing) return { error: 'Debrief not found', notFound: true };

  let debriefDate = existing.date;
  if (input.date !== undefined) {
    const normalized = normalizeDebriefDate(input.date);
    if (!normalized) return { error: 'date must be a valid date' };
    debriefDate = normalized;
  }

  let notes = existing.notes;
  if (input.notes !== undefined) {
    notes = typeof input.notes === 'string' ? input.notes.trim() : '';
    if (!notes) return { error: 'notes are required' };
  }

  let outcome = existing.outcome;
  if (input.outcome !== undefined) {
    if (!isValidDebriefOutcome(input.outcome)) return { error: 'outcome is required' };
    outcome = input.outcome;
  }

  const now = new Date().toISOString();
  db.prepare(`
    UPDATE interview_debriefs
    SET debrief_date = ?, notes = ?, outcome = ?, updated_at = ?
    WHERE id = ? AND job_id = ?
  `).run(debriefDate, notes, outcome, now, debriefId, jobId);

  const debrief = getInterviewDebrief(jobId, debriefId);
  if (!debrief) return { error: 'Failed to update debrief' };
  return { debrief };
}

export function deleteInterviewDebrief(jobId: string, debriefId: string): boolean {
  const result = db.prepare('DELETE FROM interview_debriefs WHERE id = ? AND job_id = ?').run(debriefId, jobId);
  return result.changes > 0;
}
