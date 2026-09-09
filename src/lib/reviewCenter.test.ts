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

  it('passes through a stored answer and ignores unknown answer values', () => {
    // Implements FR-289: completed cards render their recorded answer.
    const [item] = normalizeReviewItems([{ id: 'a', title: 'Spirit', answer: 'BAD_DATA' }]);
    expect(item.answer).toBe('BAD_DATA');
    const [unknown] = normalizeReviewItems([{ id: 'b', title: 'Trello', answer: 'SOMETHING_ELSE' }]);
    expect(unknown.answer).toBeUndefined();
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
