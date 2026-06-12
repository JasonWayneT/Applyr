import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  passesTitleBlocklist,
  passesSeniorityGate,
  passesGeographicGate,
  type ScrapedJob,
  type GateConfig,
} from '../../scripts/domain/gates.js';

const cfg: GateConfig = {
  blockedIndustries: ['gambling', 'cannabis', 'defense'],
  titleBlocklist: ['staff', 'vp', 'director', 'intern', 'junior', 'lead', 'software engineer', 'sales manager'],
  workSetting: 'Remote',
  maxExperienceYears: 7,
};

const baseJob = (overrides: Partial<ScrapedJob> = {}): ScrapedJob => ({
  company: 'Acme Corp',
  title: 'Product Manager',
  url: 'https://example.com/job/123',
  description: 'We are hiring a remote product manager in the United States.',
  source: 'Built In',
  ...overrides,
});

describe('Scoring Gates & Thresholds (Story 4.4)', () => {
  describe('Title Blocklist Gate', () => {
    it('blocks invalid non-PM titles', () => {
      expect(passesTitleBlocklist('Software Engineer', cfg)).toBe(false);
      expect(passesTitleBlocklist('Sales Manager', cfg)).toBe(false);
    });

    it('allows valid PM titles', () => {
      expect(passesTitleBlocklist('Senior Product Manager', cfg)).toBe(true);
      expect(passesTitleBlocklist('Group PM', cfg)).toBe(true);
    });
  });

  describe('Salary / Location / Years Gate', () => {
    it('blocks non-US/non-remote jobs', () => {
      const job = baseJob({
        description: 'Onsite office located in London, United Kingdom. No remote possibilities.',
      });
      expect(passesGeographicGate(job, cfg)).toBe(false);
    });

    it('passes remote-eligible US jobs', () => {
      const job = baseJob({
        description: 'US-based remote role. Open to remote work in San Diego CA.',
      });
      expect(passesGeographicGate(job, cfg)).toBe(true);
    });

    it('rejects years required above max constraint (7)', () => {
      const job = baseJob({
        description: 'Requires at least 10+ years of product management experience. Core leadership role.',
      });
      expect(passesSeniorityGate(job, cfg)).toBe(false);
    });

    it('allows years required within max constraint (7)', () => {
      const job = baseJob({
        description: 'Seeking 5 years of product management experience. Remote.',
      });
      expect(passesSeniorityGate(job, cfg)).toBe(true);
    });
  });
});
