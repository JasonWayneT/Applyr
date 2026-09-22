import { describe, expect, it } from 'vitest';
import {
  decisionBasisLabel,
  hasMinimumEvidence,
  holdsStage0,
  normalizeReviewItems,
  SKILL_ANSWER_HELPERS,
  SKILL_REVIEW_SUMMARY,
  skillReviewQuestion,
} from './reviewCenter';

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

  it('passes through decision basis and uncertainty', () => {
    const [item] = normalizeReviewItems([{
      id: 'jira',
      title: 'Jira',
      requirement: 'Experience with Jira',
      evidence_excerpt: 'Named tool is in the JD.',
      decision_basis: 'Deterministic named-tool scan.',
      uncertainty: 'unknown_named_tool',
    }]);
    expect(item.decisionBasis).toBe('Deterministic named-tool scan.');
    expect(item.uncertainty).toBe('unknown_named_tool');
    expect(item.evidenceExcerpt).toBe('Named tool is in the JD.');
  });

  it('uses optional-correction fallbacks for skill cards (CR-122 / AC-468)', () => {
    const [item] = normalizeReviewItems([{ id: 'ibm', title: 'IBM Cloud' }]);
    expect(item.question).toBe(skillReviewQuestion('IBM Cloud'));
    expect(item.summary).toBe(SKILL_REVIEW_SUMMARY);
    expect(item.question).not.toMatch(/before this opportunity can continue|Do not ask again/i);
    expect(item.summary).not.toMatch(/is waiting for your review|Do not ask again|before Stage 0 can continue/i);
  });

  it('treats only hard-gate cards as a Stage 0 hold', () => {
    expect(holdsStage0('hard_gate_review')).toBe(true);
    expect(holdsStage0('skill_presence')).toBe(false);
    expect(holdsStage0('evidence_enrichment')).toBe(false);
    expect(decisionBasisLabel('hard_gate_review')).toBe('Why this paused');
    expect(decisionBasisLabel('skill_presence')).toBe('Why this was flagged');
    expect(SKILL_ANSWER_HELPERS.NOT_PRESENT).toBe(
      'Same as leaving this unanswered. Not a forever no.',
    );
    expect(SKILL_ANSWER_HELPERS.NOT_PRESENT).not.toMatch(/Do not ask again/i);
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
