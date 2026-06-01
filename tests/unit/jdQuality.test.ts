import { describe, it, expect } from 'vitest';
import {
    hasRoleSignal,
    classifyConfidence,
    buildDataQualityFlags,
} from '../../scripts/domain/jdQuality.js';
import { MIN_JD_CHARS, BUILTIN_MIN_JD_CHARS } from '../../scripts/extract_job_page.js';

// ---------------------------------------------------------------------------
// Extraction constant sanity checks
// ---------------------------------------------------------------------------

describe('extraction constants', () => {
    it('MIN_JD_CHARS stays at 200 (generic path unchanged)', () => {
        expect(MIN_JD_CHARS).toBe(200);
    });
    it('BUILTIN_MIN_JD_CHARS is 500', () => {
        expect(BUILTIN_MIN_JD_CHARS).toBe(500);
    });
    it('BUILTIN_MIN_JD_CHARS > MIN_JD_CHARS', () => {
        expect(BUILTIN_MIN_JD_CHARS).toBeGreaterThan(MIN_JD_CHARS);
    });
});

// ---------------------------------------------------------------------------
// hasRoleSignal
// ---------------------------------------------------------------------------

describe('hasRoleSignal', () => {
    it('detects "Responsibilities"', () => {
        expect(hasRoleSignal('Key Responsibilities\n- Own the product roadmap')).toBe(true);
    });
    it('detects "responsibilities" (lowercase)', () => {
        expect(hasRoleSignal('Your responsibilities include shipping features')).toBe(true);
    });
    it('detects "requirements"', () => {
        expect(hasRoleSignal('Requirements\n- 3+ years of product experience')).toBe(true);
    });
    it('detects "qualifications"', () => {
        expect(hasRoleSignal('Minimum Qualifications\n- Bachelor degree required')).toBe(true);
    });
    it('detects "you will"', () => {
        expect(hasRoleSignal('In this role you will lead cross-functional teams')).toBe(true);
    });
    it('detects "about the role"', () => {
        expect(hasRoleSignal('About the Role\nWe are looking for a PM')).toBe(true);
    });
    it('detects "in this role"', () => {
        expect(hasRoleSignal('In this role, you will define roadmap priorities')).toBe(true);
    });
    it('is case-insensitive', () => {
        expect(hasRoleSignal('RESPONSIBILITIES include building a roadmap')).toBe(true);
    });
    it('rejects pure company boilerplate', () => {
        expect(hasRoleSignal('We are a fast-growing startup focused on innovation and culture.')).toBe(false);
    });
    it('rejects benefits-only text', () => {
        expect(hasRoleSignal('We offer unlimited PTO, health insurance, and 401k matching.')).toBe(false);
    });
    it('rejects empty string', () => {
        expect(hasRoleSignal('')).toBe(false);
    });
});

// ---------------------------------------------------------------------------
// classifyConfidence
// ---------------------------------------------------------------------------

describe('classifyConfidence', () => {
    const goodJd = 'Responsibilities: Lead product strategy and define roadmap priorities. '
        + 'Requirements: 5 years PM experience in SaaS. You will work cross-functionally with engineering.'.repeat(5);

    const boilerplate = 'We are a great company with amazing culture and fantastic benefits. '
        + 'Join us and make an impact!'.repeat(10);

    it('structured + long text → high', () => {
        expect(classifyConfidence(goodJd, 'structured')).toBe('high');
    });
    it('dom + role signal → medium', () => {
        expect(classifyConfidence(goodJd, 'dom')).toBe('medium');
    });
    it('dom + no role signal → low', () => {
        expect(classifyConfidence(boilerplate, 'dom')).toBe('low');
    });
    it('body fallback → low regardless of content', () => {
        expect(classifyConfidence(goodJd, 'body')).toBe('low');
    });
    it('empty text → low', () => {
        expect(classifyConfidence('', 'structured')).toBe('low');
    });
    it('text under 100 chars → low even if structured', () => {
        expect(classifyConfidence('Short text.', 'structured')).toBe('low');
    });
});

// ---------------------------------------------------------------------------
// buildDataQualityFlags
// ---------------------------------------------------------------------------

describe('buildDataQualityFlags', () => {
    const MIN = 500;

    // 7 repeats × ~152 chars = ~1064 chars — exceeds 2×MIN (1000) so no short_jd flag
    const cleanJd = ('Responsibilities: Own the roadmap. Requirements: 3 years PM experience in B2B SaaS. '
        + 'You will work with cross-functional teams to define and ship features. ').repeat(7);

    it('clean JD with role signals has no flags', () => {
        expect(buildDataQualityFlags(cleanJd, 'dom', MIN)).toEqual([]);
    });
    it('boilerplate → no_requirements_section', () => {
        const flags = buildDataQualityFlags('Amazing company. Great culture.', 'dom', MIN);
        expect(flags).toContain('no_requirements_section');
    });
    it('short JD → short_jd flag', () => {
        // 60 chars is well below 2×MIN (1000)
        const flags = buildDataQualityFlags('Responsibilities: Build products.', 'dom', MIN);
        expect(flags).toContain('short_jd');
    });
    it('body source → body_fallback flag', () => {
        const flags = buildDataQualityFlags(cleanJd, 'body', MIN);
        expect(flags).toContain('body_fallback');
    });
    it('body source with no signal → both no_requirements_section and body_fallback', () => {
        const flags = buildDataQualityFlags('Great company.', 'body', MIN);
        expect(flags).toContain('no_requirements_section');
        expect(flags).toContain('body_fallback');
    });
    it('text at exactly 2×MIN has no short_jd flag', () => {
        const text = 'Responsibilities: Lead roadmap. Requirements: 5 years experience. '.repeat(16); // ~1040 chars
        const flags = buildDataQualityFlags(text, 'dom', MIN);
        expect(flags).not.toContain('short_jd');
    });
});
