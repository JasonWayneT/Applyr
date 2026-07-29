import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { db } from '../../server/db.js';
import { APPLICATION_FUNNEL_STATUSES } from '../../shared/domain/jobPipeline.js';

describe('jobStats endpoint logic', () => {
  const TEST_JOB_ID = 'test-stats-job-1';

  beforeEach(() => {
    db.prepare('DELETE FROM jobs WHERE id = ?').run(TEST_JOB_ID);
  });

  afterEach(() => {
    db.prepare('DELETE FROM jobs WHERE id = ?').run(TEST_JOB_ID);
  });

  it('computes stats without throwing ReferenceError for APPLICATION_FUNNEL_STATUSES', () => {
    db.prepare(`
      INSERT INTO jobs (id, company, title, url, status)
      VALUES (?, 'StatsCorp', 'Lead Product Manager', 'https://example.com/stats', 'Applied')
    `).run(TEST_JOB_ID);

    expect(APPLICATION_FUNNEL_STATUSES).toBeDefined();
    const funnelList = APPLICATION_FUNNEL_STATUSES.map((s) => `'${s}'`).join(', ');

    const everApplied = db.prepare(
      `SELECT COUNT(*) as count FROM jobs WHERE
         status IN (${funnelList})
         OR (status = 'Closed' AND rejection_stage IN (${funnelList}))`,
    ).get() as { count: number };

    expect(everApplied.count).toBeGreaterThanOrEqual(1);
  });
});
