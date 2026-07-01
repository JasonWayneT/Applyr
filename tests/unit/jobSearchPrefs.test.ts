import { describe, it, expect } from 'vitest';
import {
  buildMaterializedJobSearchPrefs,
  PRESERVE_PIPELINE_PREF_KEYS,
} from '../../server/domain/jobSearchPrefs.js';

describe('buildMaterializedJobSearchPrefs (FR-248)', () => {
  it('preserves gate rollout keys when UI re-materializes', () => {
    const existing = {
      blocked_role_titles: ['Director', 'VP'],
      blocked_focus_area_words: ['Growth'],
      blocked_companies: ['Unity'],
      min_confidence_score: 55,
      min_fit_score: 75,
    };
    const result = buildMaterializedJobSearchPrefs(
      { targetRole: 'Product Manager', titleBlocklist: 'Staff, VP' },
      existing,
    );
    expect(result.blocked_role_titles).toEqual(['Director', 'VP']);
    expect(result.blocked_focus_area_words).toEqual(['Growth']);
    expect(result.blocked_companies).toEqual(['Unity']);
    expect(result.min_confidence_score).toBe(55);
    expect(result.min_fit_score).toBe(75);
    expect(result.blocked_titles).toEqual(['Staff', 'VP']);
  });

  it('documents all preserve keys', () => {
    expect(PRESERVE_PIPELINE_PREF_KEYS).toContain('blocked_companies');
  });
});
