import { describe, expect, it } from 'vitest';
import { hasMinimumEvidence, normalizeReviewItems } from './reviewCenter';

describe('Review Center data contract', () => {
  // Implements FR-285: protect the shared UI/client contract from malformed records.
  it('normalizes API question naming into the UI model', () => {
    const items = normalizeReviewItems({
      items: [{
        id: 'sc_trello',
        question_type: 'skill_presence',
        skill_key: 'trello',
        title: 'Trello',
        question: 'Have you used Trello in your work?',
        affected_opportunities: [{
          job_id: 'job-1',
          company: 'Example Co',
          title: 'Product Manager',
        }],
      }],
    });

    expect(items).toEqual([expect.objectContaining({
      id: 'sc_trello',
      type: 'skill_presence',
      skillKey: 'trello',
      affectedOpportunities: [{
        jobId: 'job-1',
        company: 'Example Co',
        title: 'Product Manager',
      }],
    })]);
  });

  it('drops malformed review items instead of rendering unsafe partial records', () => {
    expect(normalizeReviewItems([
      { id: 'missing-title' },
      null,
      { id: 'valid', title: 'Trello' },
    ])).toHaveLength(1);
  });

  it('requires context, activity, and timeframe before evidence promotion', () => {
    expect(hasMinimumEvidence({
      context: 'Example Co',
      activity: 'managed sprint planning',
      timeframe: '2018 to 2021',
    })).toBe(true);
    expect(hasMinimumEvidence({
      context: 'Example Co',
      activity: 'managed sprint planning',
      timeframe: '',
    })).toBe(false);
  });
});
