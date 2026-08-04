/**
 * Unit tests for pending-review export helpers (no DB side effects beyond module load).
 */
import { describe, expect, it } from 'vitest';
import {
  formatOriginalJd,
  pendingReviewFolderName,
} from '../server/services/exportPendingReview.js';

describe('formatOriginalJd', () => {
  it('puts URL on first line when known', () => {
    const out = formatOriginalJd('https://example.com/jobs/1', 'Build cool products.');
    expect(out).toBe('URL: https://example.com/jobs/1\n\nBuild cool products.\n');
  });

  it('omits URL line when url is null', () => {
    const out = formatOriginalJd(null, 'Raw JD only');
    expect(out).toBe('Raw JD only\n');
  });
});

describe('pendingReviewFolderName', () => {
  it('uses slug plus short id', () => {
    expect(pendingReviewFolderName('Acme Corp', 'abcdef12-3456-7890')).toBe('acme_corp_abcdef12');
  });
});
