import { describe, it, expect } from 'vitest';
import {
  INTERVIEW_DEBRIEF_OUTCOMES,
  isValidDebriefOutcome,
  normalizeDebriefDate,
  toDebriefDateInputValue,
} from '../../shared/domain/interviewDebrief.js';

describe('interviewDebrief', () => {
  it('exports the expected outcome set', () => {
    expect(INTERVIEW_DEBRIEF_OUTCOMES).toContain('Pending');
    expect(INTERVIEW_DEBRIEF_OUTCOMES).toContain('Went well');
    expect(INTERVIEW_DEBRIEF_OUTCOMES).toContain('Concerns');
    expect(INTERVIEW_DEBRIEF_OUTCOMES).toContain('Rejected');
    expect(INTERVIEW_DEBRIEF_OUTCOMES).toContain('Ghosted');
    expect(INTERVIEW_DEBRIEF_OUTCOMES).toHaveLength(5);
  });

  it('validates known outcomes', () => {
    expect(isValidDebriefOutcome('Pending')).toBe(true);
    expect(isValidDebriefOutcome('Went well')).toBe(true);
    expect(isValidDebriefOutcome('Rejected')).toBe(true);
  });

  it('rejects invalid outcomes', () => {
    expect(isValidDebriefOutcome('')).toBe(false);
    expect(isValidDebriefOutcome('Excellent')).toBe(false);
    expect(isValidDebriefOutcome(null)).toBe(false);
    expect(isValidDebriefOutcome(undefined)).toBe(false);
    expect(isValidDebriefOutcome(42)).toBe(false);
  });

  it('normalizes date-only strings to ISO', () => {
    const result = normalizeDebriefDate('2026-07-15');
    expect(result).not.toBeNull();
    expect(result).toMatch(/^2026-07-15/);
  });

  it('normalizes full datetime strings to ISO', () => {
    const result = normalizeDebriefDate('2026-07-15T14:30:00');
    expect(result).not.toBeNull();
    expect(result).toMatch(/^2026-07-15/);
  });

  it('rejects empty or non-string dates', () => {
    expect(normalizeDebriefDate('')).toBeNull();
    expect(normalizeDebriefDate('   ')).toBeNull();
    expect(normalizeDebriefDate(null)).toBeNull();
    expect(normalizeDebriefDate(42)).toBeNull();
  });

  it('rejects invalid date strings', () => {
    expect(normalizeDebriefDate('not-a-date')).toBeNull();
    expect(normalizeDebriefDate('2026-13-45')).toBeNull();
  });

  it('converts ISO to date input format (YYYY-MM-DD)', () => {
    // Use a local-constructed date to avoid timezone shift issues
    const localDate = new Date(2026, 6, 15); // July 15, 2026 local time
    const result = toDebriefDateInputValue(localDate.toISOString());
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(result.startsWith('2026-07-')).toBe(true);
  });

  it('returns empty string for null or invalid input', () => {
    expect(toDebriefDateInputValue(null)).toBe('');
    expect(toDebriefDateInputValue(undefined)).toBe('');
    expect(toDebriefDateInputValue('')).toBe('');
    expect(toDebriefDateInputValue('not-a-date')).toBe('');
  });
});
