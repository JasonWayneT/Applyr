import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { db } from '../../server/db.js';
import {
  createInterviewDebrief,
  deleteInterviewDebrief,
  listInterviewDebriefs,
  updateInterviewDebrief,
} from '../../server/repository/interviewDebriefRepository.js';
import {
  isValidDebriefOutcome,
  normalizeDebriefDate,
} from '../../shared/domain/interviewDebrief.js';

const JOB_ID = 'debrief-test-job';

function seedJob() {
  db.prepare(`
    INSERT OR REPLACE INTO jobs (id, company, title, url, status)
    VALUES (?, 'Hudu', 'Product Manager', 'https://example.com/hudu-pm', 'Core Interviews')
  `).run(JOB_ID);
}

function clearDebriefs() {
  db.prepare('DELETE FROM interview_debriefs WHERE job_id = ?').run(JOB_ID);
}

beforeEach(() => {
  seedJob();
  clearDebriefs();
});

afterEach(() => {
  clearDebriefs();
  db.prepare('DELETE FROM jobs WHERE id = ?').run(JOB_ID);
});

describe('interviewDebrief domain', () => {
  it('validates outcomes and dates', () => {
    expect(isValidDebriefOutcome('Went well')).toBe(true);
    expect(isValidDebriefOutcome('Unknown')).toBe(false);
    expect(normalizeDebriefDate('2026-07-02')).toMatch(/^2026-07-02/);
    expect(normalizeDebriefDate('')).toBeNull();
  });
});

describe('interviewDebriefRepository', () => {
  it('creates and lists debriefs newest first', () => {
    const older = createInterviewDebrief(JOB_ID, {
      date: '2026-06-01',
      notes: 'First round questions about platform experience.',
      outcome: 'Went well',
    });
    expect('error' in older).toBe(false);

    const newer = createInterviewDebrief(JOB_ID, {
      date: '2026-07-02',
      notes: 'Asked how I stay current with the industry (unprepped).',
      outcome: 'Concerns',
    });
    expect('error' in newer).toBe(false);

    const list = listInterviewDebriefs(JOB_ID);
    expect(list).toHaveLength(2);
    expect(list[0].notes).toContain('stay current');
    expect(list[1].notes).toContain('platform experience');
  });

  it('rejects empty notes', () => {
    const result = createInterviewDebrief(JOB_ID, {
      date: '2026-07-02',
      notes: '   ',
      outcome: 'Went well',
    });
    expect(result).toEqual({ error: 'notes are required' });
  });

  it('rejects missing outcome', () => {
    const result = createInterviewDebrief(JOB_ID, {
      date: '2026-07-02',
      notes: 'Some notes',
    });
    expect(result).toEqual({ error: 'outcome is required' });
  });

  it('updates and deletes debriefs', () => {
    const created = createInterviewDebrief(JOB_ID, {
      date: '2026-07-02',
      notes: 'Initial notes',
      outcome: 'Pending',
    });
    if ('error' in created) throw new Error(created.error);

    const updated = updateInterviewDebrief(JOB_ID, created.debrief.id, {
      notes: 'Updated notes with more detail',
      outcome: 'Went well',
    });
    if ('error' in updated) throw new Error(updated.error);
    expect(updated.debrief.notes).toBe('Updated notes with more detail');
    expect(updated.debrief.outcome).toBe('Went well');

    expect(deleteInterviewDebrief(JOB_ID, created.debrief.id)).toBe(true);
    expect(listInterviewDebriefs(JOB_ID)).toHaveLength(0);
  });
});
