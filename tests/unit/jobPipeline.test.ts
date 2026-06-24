import { describe, it, expect } from 'vitest';
import {
  statusRequiresInterviewDateTime,
  isValidInterviewDateTime,
  toDatetimeLocalValue,
  INTERVIEW_SCHEDULED_STATUSES,
} from '../../shared/domain/jobPipeline.js';

describe('jobPipeline', () => {
  it('flags screening and core interviews as requiring datetime', () => {
    expect(INTERVIEW_SCHEDULED_STATUSES.has('Recruiter Screen')).toBe(true);
    expect(INTERVIEW_SCHEDULED_STATUSES.has('Core Interviews')).toBe(true);
    expect(statusRequiresInterviewDateTime('Applied')).toBe(false);
    expect(statusRequiresInterviewDateTime('Recruiter Screen')).toBe(true);
    expect(statusRequiresInterviewDateTime('Core Interviews')).toBe(true);
  });

  it('validates interview datetime values', () => {
    expect(isValidInterviewDateTime('')).toBe(false);
    expect(isValidInterviewDateTime('   ')).toBe(false);
    expect(isValidInterviewDateTime(null)).toBe(false);
    expect(isValidInterviewDateTime('2026-06-15T14:30')).toBe(true);
    expect(isValidInterviewDateTime('2026-06-15 14:30:00')).toBe(true);
    expect(isValidInterviewDateTime('not-a-date')).toBe(false);
  });

  it('normalizes sqlite datetime for datetime-local inputs', () => {
    expect(toDatetimeLocalValue('2026-06-15 14:30:00')).toMatch(/^2026-06-15T14:30/);
    expect(toDatetimeLocalValue('2026-06-15T14:30:00')).toMatch(/^2026-06-15T14:30/);
    expect(toDatetimeLocalValue('')).toBe('');
  });
});
