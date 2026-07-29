import { describe, it, expect } from 'vitest';
import {
  deriveSearchTermsFromTargetRole,
  expandProductManagerSearchTerms,
} from '../../shared/domain/scoutPrefs.js';

describe('deriveSearchTermsFromTargetRole', () => {
  it('expands Product Manager to include Technical Product Manager', () => {
    expect(deriveSearchTermsFromTargetRole('Product Manager')).toEqual([
      'Product Manager',
      'Technical Product Manager',
    ]);
  });

  it('does not inject Product Owner for PM targets', () => {
    const terms = deriveSearchTermsFromTargetRole('Product Manager');
    expect(terms).not.toContain('Product Owner');
  });

  it('returns empty array for blank target', () => {
    expect(deriveSearchTermsFromTargetRole('')).toEqual([]);
  });

  it('preserves arbitrary user target roles', () => {
    expect(deriveSearchTermsFromTargetRole('Data Engineer')).toEqual(['Data Engineer']);
  });
});

describe('expandProductManagerSearchTerms', () => {
  it('adds Technical Product Manager when Product Manager is configured', () => {
    expect(expandProductManagerSearchTerms(['Product Manager'])).toEqual([
      'Product Manager',
      'Technical Product Manager',
    ]);
  });

  it('does not duplicate Technical Product Manager when already present', () => {
    expect(
      expandProductManagerSearchTerms(['Product Manager', 'Technical Product Manager']),
    ).toEqual(['Product Manager', 'Technical Product Manager']);
  });

  it('is a no-op for non-PM search terms', () => {
    expect(expandProductManagerSearchTerms(['Account Executive'])).toEqual(['Account Executive']);
  });
});
