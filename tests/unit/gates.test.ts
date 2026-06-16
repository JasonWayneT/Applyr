import { describe, it, expect } from 'vitest';
import {
    passesTitleBlocklist,
    passesIndustryGate,
    passesGeographicGate,
    passesSeniorityGate,
    passesBuiltInPmTitleScope,
    passesBroadPmTitleScope,
    passesTargetRoleTitleScope,
    passesBuiltInStrictRemoteCard,
    parseMaxYearsRequired,
    titleMatchesBlocked,
    type ScrapedJob,
    type GateConfig,
} from '../../scripts/domain/gates.js';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const cfg: GateConfig = {
    blockedIndustries: ['gambling', 'cannabis', 'defense'],
    titleBlocklist: ['staff', 'vp', 'director', 'intern', 'junior', 'lead'],
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

// ---------------------------------------------------------------------------
// titleMatchesBlocked
// ---------------------------------------------------------------------------

describe('titleMatchesBlocked', () => {
    it('matches whole word', () => {
        expect(titleMatchesBlocked('Staff Product Manager', 'staff')).toBe(true);
    });
    it('does not match substring inside a word', () => {
        expect(titleMatchesBlocked('Staffing Coordinator', 'staff')).toBe(false);
    });
    it('is case-insensitive', () => {
        expect(titleMatchesBlocked('VP of Product', 'vp')).toBe(true);
    });
});

// ---------------------------------------------------------------------------
// parseMaxYearsRequired
// ---------------------------------------------------------------------------

describe('parseMaxYearsRequired', () => {
    it('parses "minimum 5 years"', () => {
        expect(parseMaxYearsRequired('Minimum 5 years of experience required.')).toBe(5);
    });
    it('parses "8+ years"', () => {
        expect(parseMaxYearsRequired('8+ years of product management experience.')).toBe(8);
    });
    it('parses a range and takes the max', () => {
        expect(parseMaxYearsRequired('5-10 years experience preferred.')).toBe(10);
    });
    it('parses "requires 3 years"', () => {
        expect(parseMaxYearsRequired('Requires 3 years of experience.')).toBe(3);
    });
    it('returns null when no years found', () => {
        expect(parseMaxYearsRequired('Passion for product, great communicator.')).toBeNull();
    });
    it('returns the highest when multiple patterns match', () => {
        expect(parseMaxYearsRequired('3 years preferred, minimum 5 years required.')).toBe(5);
    });
    it('ignores implausible large years values (e.g. 90 days / 100%)', () => {
        expect(parseMaxYearsRequired('Onboarding in 90 days. 100% remote role.')).toBeNull();
    });
    it('keeps plausible years while ignoring outliers', () => {
        expect(parseMaxYearsRequired('Requires 8+ years; team supports 100+ products.')).toBe(8);
    });
});

// ---------------------------------------------------------------------------
// passesTitleBlocklist
// ---------------------------------------------------------------------------

describe('passesTitleBlocklist', () => {
    it('passes a clean PM title', () => {
        expect(passesTitleBlocklist('Product Manager', cfg)).toBe(true);
    });
    it('rejects "Staff Product Manager"', () => {
        expect(passesTitleBlocklist('Staff Product Manager', cfg)).toBe(false);
    });
    it('rejects "VP of Product"', () => {
        expect(passesTitleBlocklist('VP of Product', cfg)).toBe(false);
    });
    it('rejects "Director of Product"', () => {
        expect(passesTitleBlocklist('Director of Product', cfg)).toBe(false);
    });
    it('rejects "Junior PM"', () => {
        expect(passesTitleBlocklist('Junior PM', cfg)).toBe(false);
    });
    it('passes empty string (no title = no block)', () => {
        expect(passesTitleBlocklist('', cfg)).toBe(true);
    });
});

// ---------------------------------------------------------------------------
// passesIndustryGate
// ---------------------------------------------------------------------------

describe('passesIndustryGate', () => {
    it('passes a clean tech company', () => {
        expect(passesIndustryGate(baseJob({ company: 'Stripe', title: 'Product Manager' }), cfg)).toBe(true);
    });
    it('rejects by company name match', () => {
        // 'DraftKings' does not contain the word 'gambling' — passes
        expect(passesIndustryGate(baseJob({ company: 'DraftKings Inc', title: 'Product Manager' }), cfg)).toBe(true);
        // 'Gambling Corp' contains 'gambling' as a whole word — rejected
        expect(passesIndustryGate(baseJob({ company: 'Gambling Corp', title: 'Product Manager' }), cfg)).toBe(false);
    });
    it('rejects by title match', () => {
        expect(passesIndustryGate(baseJob({ title: 'Product Manager - Cannabis Division' }), cfg)).toBe(false);
    });
    it('rejects by short description match (<=120 chars)', () => {
        const shortDesc = 'Build products for the defense sector.';
        expect(passesIndustryGate(baseJob({ description: shortDesc }), cfg)).toBe(false);
    });
    it('does NOT reject by long description match (>120 chars)', () => {
        const longDesc = 'We build defense technology. '.repeat(10); // >120 chars
        expect(passesIndustryGate(baseJob({ description: longDesc }), cfg)).toBe(true);
    });
    it('passes when blocked industries list is empty', () => {
        const emptyCfg: GateConfig = { ...cfg, blockedIndustries: [] };
        expect(passesIndustryGate(baseJob({ company: 'Gambling Corp' }), emptyCfg)).toBe(true);
    });
});

// ---------------------------------------------------------------------------
// passesGeographicGate
// ---------------------------------------------------------------------------

describe('passesGeographicGate', () => {
    it('passes a job with "remote" in description', () => {
        expect(passesGeographicGate(baseJob(), cfg)).toBe(true);
    });
    it('passes a job mentioning san diego (description ≥50 chars)', () => {
        // Geo gate only text-scans descriptions ≥50 chars; shorter ones hit the stub branch.
        const job = baseJob({ description: 'This is an on-site role located in San Diego, CA with hybrid options.' });
        expect(passesGeographicGate(job, cfg)).toBe(true);
    });
    it('rejects a job explicitly scoped to UK only', () => {
        const job = baseJob({
            description: 'This role is based in London, United Kingdom. No remote option.',
        });
        expect(passesGeographicGate(job, cfg)).toBe(false);
    });
    it('passes remote-only source with empty description', () => {
        const job = baseJob({ description: '', source: 'Remotive' });
        expect(passesGeographicGate(job, cfg)).toBe(true);
    });
    it('rejects non-remote-only source with empty description when workSetting=Remote', () => {
        const job = baseJob({ description: '', source: 'Built In' });
        expect(passesGeographicGate(job, cfg)).toBe(false);
    });
    it('does not reject UK mention when united states is also present', () => {
        const job = baseJob({
            description: 'Open to candidates in the United Kingdom or United States. Remote.',
        });
        expect(passesGeographicGate(job, cfg)).toBe(true);
    });
});

// ---------------------------------------------------------------------------
// passesSeniorityGate
// ---------------------------------------------------------------------------

describe('passesBuiltInPmTitleScope', () => {
    it('accepts Product Manager', () => {
        expect(passesBuiltInPmTitleScope('Product Manager')).toBe(true);
    });
    it('accepts Senior Product Manager', () => {
        expect(passesBuiltInPmTitleScope('Senior Product Manager')).toBe(true);
    });
    it('rejects Product Owner only', () => {
        expect(passesBuiltInPmTitleScope('Product Owner, CIS')).toBe(false);
    });
    it('allows Product Owner / Product Manager dual title', () => {
        expect(passesBuiltInPmTitleScope('Product Owner / Product Manager')).toBe(true);
    });
    it('rejects Product Marketing Manager', () => {
        expect(passesBuiltInPmTitleScope('Product Marketing Manager, SMB')).toBe(false);
    });
    it('rejects DevOps Engineer', () => {
        expect(passesBuiltInPmTitleScope('DevOps Engineer')).toBe(false);
    });
});

describe('passesBroadPmTitleScope', () => {
    it('accepts Product Manager', () => {
        expect(passesBroadPmTitleScope('Product Manager')).toBe(true);
    });
    it('accepts Senior Product Manager', () => {
        expect(passesBroadPmTitleScope('Senior Product Manager')).toBe(true);
    });
    it('accepts Product Owner', () => {
        expect(passesBroadPmTitleScope('Product Owner - SEPA/Payments')).toBe(true);
    });
    it('accepts Technical Product Manager', () => {
        expect(passesBroadPmTitleScope('Technical Product Manager')).toBe(true);
    });
    it('rejects Product Marketing', () => {
        expect(passesBroadPmTitleScope('Product Marketing Consultant (part-time)')).toBe(false);
    });
    // Implements FR-240 (CR-045) — 2026-06-11 incident titles
    it('rejects Sales Development Representative', () => {
        expect(passesBroadPmTitleScope('Sales Development Representative')).toBe(false);
    });
    it('rejects Solutions Engineer', () => {
        expect(passesBroadPmTitleScope('Solutions Engineer / Network Automation Consultant')).toBe(false);
    });
    it('rejects Program Manager', () => {
        expect(passesBroadPmTitleScope('Program Manager Time Migration')).toBe(false);
    });
    it('rejects Support Operations Program Manager', () => {
        expect(passesBroadPmTitleScope('Support Operations Program Manager (SaaS) REMOTE')).toBe(false);
    });
    it('rejects Account Executive', () => {
        expect(passesBroadPmTitleScope('Account Executive')).toBe(false);
    });
    it('rejects Customer Success Manager', () => {
        expect(passesBroadPmTitleScope('Senior Customer Success Manager')).toBe(false);
    });
});

describe('passesTargetRoleTitleScope', () => {
    const pmPrefs = { targetRole: 'Product Manager', searchTerms: ['Product Manager', 'Product Owner'] };

    it('accepts Product Manager for PM target', () => {
        expect(passesTargetRoleTitleScope('Senior Product Manager', pmPrefs)).toBe(true);
    });
    it('rejects Account Executive for PM target', () => {
        expect(passesTargetRoleTitleScope('Account Executive', pmPrefs)).toBe(false);
    });
    it('uses search terms only for non-PM targets', () => {
        const aePrefs = { targetRole: 'Account Executive', searchTerms: ['Account Executive', 'AE'] };
        expect(passesTargetRoleTitleScope('Account Executive', aePrefs)).toBe(true);
        expect(passesTargetRoleTitleScope('Product Manager', aePrefs)).toBe(false);
    });
});

describe('passesBuiltInStrictRemoteCard', () => {
    it('accepts plain Remote listing', () => {
        expect(passesBuiltInStrictRemoteCard('Remote United States Mid level')).toBe(true);
    });
    it('rejects Remote or Hybrid', () => {
        expect(passesBuiltInStrictRemoteCard('Remote or Hybrid United States')).toBe(false);
    });
    it('rejects In-Office or Remote', () => {
        expect(passesBuiltInStrictRemoteCard('In-Office or Remote 10 Locations')).toBe(false);
    });
    it('accepts San Diego area listing', () => {
        expect(passesBuiltInStrictRemoteCard('San Diego, CA, USA')).toBe(true);
    });
});

describe('passesSeniorityGate', () => {
    it('passes a mid-level PM with 5 years required', () => {
        const job = baseJob({ description: 'Requires 5 years of product management experience. Remote role.' });
        expect(passesSeniorityGate(job, cfg)).toBe(true);
    });
    it('rejects when required years exceed max (description ≥80 chars)', () => {
        // Year extraction only runs when desc.length >= 80 chars.
        const job = baseJob({ description: 'Minimum 10 years of product management experience required. Must have SaaS background.' });
        expect(passesSeniorityGate(job, cfg)).toBe(false);
    });
    it('rejects when title is blocked', () => {
        const job = baseJob({ title: 'Lead Product Manager' });
        expect(passesSeniorityGate(job, cfg)).toBe(false);
    });
    it('passes when description is too short to extract years (<80 chars)', () => {
        const job = baseJob({ title: 'Product Manager', description: 'Great role.' });
        expect(passesSeniorityGate(job, cfg)).toBe(true);
    });
    it('passes exactly at max years', () => {
        const job = baseJob({ description: 'Requires 7 years of product management experience in SaaS.' });
        expect(passesSeniorityGate(job, cfg)).toBe(true);
    });
    it('rejects one year over max (description ≥80 chars)', () => {
        const job = baseJob({ description: 'Requires 8 years of product management experience in SaaS. Remote-friendly team.' });
        expect(passesSeniorityGate(job, cfg)).toBe(false);
    });
});
