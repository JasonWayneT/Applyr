import { describe, it, expect } from 'vitest';
import {
  buildMaterializedJobSearchPrefs,
  resolveMaterializedSearchTerms,
  PRESERVE_PIPELINE_PREF_KEYS,
} from '../../server/domain/jobSearchPrefs.js';

describe('resolveMaterializedSearchTerms', () => {
  it('uses target role + UI additional titles when provided', () => {
    const terms = resolveMaterializedSearchTerms(
      {
        targetRole: 'Product Manager',
        additionalSearchTerms: 'Technical Product Manager, Platform Product Manager',
      },
      {},
    );
    expect(terms).toEqual([
      'Product Manager',
      'Technical Product Manager',
      'Platform Product Manager',
    ]);
    expect(terms).not.toContain('Product Owner');
  });

  it('allows Product Owner only when user adds it in UI field', () => {
    const terms = resolveMaterializedSearchTerms(
      { targetRole: 'Product Manager', additionalSearchTerms: 'Product Owner' },
      {},
    );
    expect(terms).toEqual(['Product Manager', 'Product Owner']);
  });

  it('strips legacy Product Owner from existing prefs when UI has no search field', () => {
    const terms = resolveMaterializedSearchTerms(
      { targetRole: 'Product Manager' },
      {
        search_terms: [
          'Product Manager',
          'Product Owner',
          'Platform Product Manager',
        ],
      },
    );
    expect(terms).toEqual(['Product Manager', 'Platform Product Manager']);
  });
});

describe('buildMaterializedJobSearchPrefs (FR-248)', () => {
  it('materializes search_terms from UI additional titles', () => {
    const result = buildMaterializedJobSearchPrefs(
      {
        targetRole: 'Product Manager',
        additionalSearchTerms: 'Platform Product Manager',
        titleBlocklist: 'Staff, VP',
      },
      {},
    );
    expect(result.search_terms).toEqual(['Product Manager', 'Platform Product Manager']);
    expect(result.search_terms).not.toContain('Product Owner');
  });

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
