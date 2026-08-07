import { describe, it, expect } from 'vitest';
import {
    passesTitleBlocklist,
    passesIndustryGate,
    passesGeographicGate,
    passesSeniorityGate,
    passesYearsExperienceGate,
    passesBuiltInPmTitleScope,
    passesBroadPmTitleScope,
    passesTargetRoleTitleScope,
    passesBuiltInStrictRemoteCard,
    parseMaxYearsRequired,
    parseYearsForIngestGate,
    YEARS_EXPERIENCE_REJECT_BUFFER,
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
    localAreaTerms: ['san diego'],
    locationPreference: 'United States',
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
    it('ignores age requirements ("18 years old")', () => {
        expect(
            parseMaxYearsRequired(
                'Must be at least 18 years old. 6 years of direct and relevant experience in product.',
            ),
        ).toBe(6);
    });
    it('ignores company-tenure marketing ("over 20 years of experience building")', () => {
        expect(
            parseMaxYearsRequired(
                '3+ years of experience in product management. With over 20 years of experience building long-term client relationships.',
            ),
        ).toBe(3);
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
    it('passes remote-only source with empty description (display name)', () => {
        const job = baseJob({ description: '', source: 'Remotive' });
        expect(passesGeographicGate(job, cfg)).toBe(true);
    });
    it('passes remote-only source with empty description (connector sourceId)', () => {
        const job = baseJob({ description: '', source: 'remotive' });
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
    const pmPrefs = { targetRole: 'Product Manager', searchTerms: ['Product Manager'] };

    it('accepts Product Manager for PM search term', () => {
        expect(passesTargetRoleTitleScope('Senior Product Manager', pmPrefs)).toBe(true);
    });
    it('accepts Technical Product Manager for PM search term (family match, not exact title)', () => {
        expect(passesTargetRoleTitleScope('Technical Product Manager', pmPrefs)).toBe(true);
    });
    it('accepts Platform Product Manager for PM search term', () => {
        expect(passesTargetRoleTitleScope('Platform Product Manager', pmPrefs)).toBe(true);
    });
    it('rejects Product Owner when not in search_terms', () => {
        expect(passesTargetRoleTitleScope('Product Owner - SEPA/Payments', pmPrefs)).toBe(false);
    });
    it('accepts dual title when Product Manager search term matches', () => {
        expect(passesTargetRoleTitleScope('Product Owner / Product Manager', pmPrefs)).toBe(true);
    });
    it('rejects Account Executive for PM search terms', () => {
        expect(passesTargetRoleTitleScope('Account Executive', pmPrefs)).toBe(false);
    });
    it('rejects product marketing adjacent roles', () => {
        expect(passesTargetRoleTitleScope('Product Marketing Manager', pmPrefs)).toBe(false);
    });
    it('uses search terms only for non-PM targets', () => {
        const aePrefs = { targetRole: 'Account Executive', searchTerms: ['Account Executive', 'AE'] };
        expect(passesTargetRoleTitleScope('Account Executive', aePrefs)).toBe(true);
        expect(passesTargetRoleTitleScope('Product Manager', aePrefs)).toBe(false);
    });
    it('accepts Product Owner when user configured it in search_terms', () => {
        const poPrefs = { targetRole: 'Product Owner', searchTerms: ['Product Owner'] };
        expect(passesTargetRoleTitleScope('Senior Product Owner', poPrefs)).toBe(true);
    });
});

describe('passesBuiltInStrictRemoteCard', () => {
    const geo = { localAreaTerms: ['san diego'], locationPreference: 'United States' };

    it('accepts plain Remote listing', () => {
        expect(passesBuiltInStrictRemoteCard('Remote United States Mid level', geo)).toBe(true);
    });
    it('rejects Remote or Hybrid', () => {
        expect(passesBuiltInStrictRemoteCard('Remote or Hybrid United States', geo)).toBe(false);
    });
    it('rejects In-Office or Remote', () => {
        expect(passesBuiltInStrictRemoteCard('In-Office or Remote 10 Locations', geo)).toBe(false);
    });
    it('accepts listing matching configured local area', () => {
        expect(passesBuiltInStrictRemoteCard('San Diego, CA, USA', geo)).toBe(true);
    });
    it('rejects local-area-only listing when localAreaTerms empty', () => {
        expect(passesBuiltInStrictRemoteCard('San Diego, CA, USA', { localAreaTerms: [] })).toBe(false);
    });
});

describe('passesYearsExperienceGate', () => {
    // cfg.maxExperienceYears = 7; buffer = 2 → reject only when required > 9
    it(`uses buffer of ${YEARS_EXPERIENCE_REJECT_BUFFER} above max`, () => {
        expect(YEARS_EXPERIENCE_REJECT_BUFFER).toBe(2);
    });
    it('passes a mid-level PM with 5 years required', () => {
        const job = baseJob({ description: 'Requires 5 years of product management experience. Remote role.' });
        expect(passesYearsExperienceGate(job, cfg)).toBe(true);
    });
    it('passes one year over max (inside buffer) — CR-056 class', () => {
        const job = baseJob({ description: 'Requires 8 years of product management experience in SaaS. Remote-friendly team.' });
        expect(passesYearsExperienceGate(job, cfg)).toBe(true);
    });
    it('passes at max + buffer boundary (9 with max 7)', () => {
        const job = baseJob({ description: 'Requires 9 years of product management experience in B2B SaaS platforms.' });
        expect(passesYearsExperienceGate(job, cfg)).toBe(true);
    });
    it('rejects when required exceeds max + buffer (10 with max 7)', () => {
        const job = baseJob({ description: 'Minimum 10 years of product management experience required. Must have SaaS background.' });
        expect(passesYearsExperienceGate(job, cfg)).toBe(false);
    });
    it('passes unparseable / no years found', () => {
        const job = baseJob({ description: 'Passionate about product and customers. Collaborative team environment. Remote US.' });
        expect(passesYearsExperienceGate(job, cfg)).toBe(true);
    });
    it('passes when description is too short to extract years (<80 chars)', () => {
        const job = baseJob({ title: 'Product Manager', description: 'Requires 15 years experience.' });
        expect(passesYearsExperienceGate(job, cfg)).toBe(true);
    });
    it('with real prefs max=8, lets 5-10 year ranges through (ingest uses range floor)', () => {
        const realCfg = { ...cfg, maxExperienceYears: 8 };
        const job = baseJob({ description: 'Looking for someone with 5-10 years of product management experience in SaaS.' });
        expect(parseMaxYearsRequired(job.description)).toBe(10);
        expect(parseYearsForIngestGate(job.description)).toBe(5);
        expect(passesYearsExperienceGate(job, realCfg)).toBe(true);
    });
    it('lets 8-12 year ranges through when floor is within max (ingest uses range floor)', () => {
        const realCfg = { ...cfg, maxExperienceYears: 8 };
        const job = baseJob({
            description: "Bachelor's degree and a minimum of 8-12 years of related experience in product roles.",
        });
        expect(parseYearsForIngestGate(job.description)).toBe(8);
        expect(passesYearsExperienceGate(job, realCfg)).toBe(true);
    });
    it('rejects anchored minimum far above ceiling', () => {
        const realCfg = { ...cfg, maxExperienceYears: 8 };
        const job = baseJob({
            description: 'Minimum 12 years of product management experience required for this senior platform role.',
        });
        expect(passesYearsExperienceGate(job, realCfg)).toBe(false);
    });
    it('treats scraped space-range "9 11 years" as floor 9 (passes inside buffer)', () => {
        const realCfg = { ...cfg, maxExperienceYears: 8 };
        const job = baseJob({
            description:
                '9 11 years of overall experience in Product Management. 3+ years of direct experience as a Product Owner.',
        });
        expect(parseYearsForIngestGate(job.description)).toBe(9);
        expect(passesYearsExperienceGate(job, realCfg)).toBe(true);
    });
});

describe('passesSeniorityGate', () => {
    it('passes a mid-level PM with 5 years required', () => {
        const job = baseJob({ description: 'Requires 5 years of product management experience. Remote role.' });
        expect(passesSeniorityGate(job, cfg)).toBe(true);
    });
    it('rejects when required years exceed max + buffer (description ≥80 chars)', () => {
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
    it('passes one year over max (inside buffer)', () => {
        const job = baseJob({ description: 'Requires 8 years of product management experience in SaaS. Remote-friendly team.' });
        expect(passesSeniorityGate(job, cfg)).toBe(true);
    });
});
