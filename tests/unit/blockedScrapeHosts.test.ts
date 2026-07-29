import { describe, it, expect } from 'vitest';
import { isBlockedScrapeUrl, isLinkedInJobUrl } from '../../shared/domain/blockedScrapeHosts.js';

describe('blockedScrapeHosts', () => {
  it('blocks linkedin job view URLs', () => {
    expect(
      isLinkedInJobUrl(
        'https://www.linkedin.com/jobs/view/4423139883/apply/?companyName=Revalize',
      ),
    ).toBe(true);
    expect(isBlockedScrapeUrl('https://linkedin.com/jobs/view/123')).toBe(true);
  });

  it('does not block non-linkedin ATS URLs', () => {
    expect(
      isBlockedScrapeUrl(
        'https://talentmanagementsolution.wd3.myworkdayjobs.com/en-US/perseus-careers/job/Remote---USA/Product-Manager_R51031-1',
      ),
    ).toBe(false);
    expect(isBlockedScrapeUrl('https://builtin.com/job/product-manager/123')).toBe(false);
  });

  it('handles empty URLs', () => {
    expect(isBlockedScrapeUrl(null)).toBe(false);
    expect(isBlockedScrapeUrl('')).toBe(false);
  });
});
