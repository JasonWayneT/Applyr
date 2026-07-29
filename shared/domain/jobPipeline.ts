/**
 * Pipeline status rules shared by API and UI (CR-051 / FR-251).
 */

/** Statuses that require interview_date before entry. */
export const INTERVIEW_SCHEDULED_STATUSES = new Set([
  'Recruiter Screen',
  'Core Interviews',
]);

/** Statuses after the candidate has submitted an application. */
export const APPLICATION_FUNNEL_STATUSES = [
  'Applied',
  'Recruiter Screen',
  'Core Interviews',
  'Offer and Negotiation',
] as const;

export const APPLICATION_FUNNEL_SET = new Set<string>(APPLICATION_FUNNEL_STATUSES);

export type ApplicationFunnelStatus = (typeof APPLICATION_FUNNEL_STATUSES)[number];

export function statusRequiresInterviewDateTime(status: string): boolean {
  return INTERVIEW_SCHEDULED_STATUSES.has(status);
}

/** True when value is a non-empty datetime suitable for interview_date. */
export function isValidInterviewDateTime(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  const s = String(value).trim();
  if (!s) return false;
  const ms = Date.parse(s);
  return Number.isFinite(ms);
}

/** Normalize DB/API datetime strings for `<input type="datetime-local" />`. */
export function toDatetimeLocalValue(value: string | null | undefined): string {
  if (!value) return '';
  const trimmed = String(value).trim();
  if (!trimmed) return '';
  const isoLike = trimmed.includes('T') ? trimmed : trimmed.replace(' ', 'T');
  const d = new Date(isoLike);
  if (!Number.isFinite(d.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Normalize DB/API datetime strings for `<input type="date" />`. */
export function toDateInputValue(value: string | null | undefined): string {
  const local = toDatetimeLocalValue(value);
  return local ? local.slice(0, 10) : '';
}

/** Pre-application pipeline statuses — applied_at should be cleared if returned here. */
export const PRE_APPLY_STATUSES = new Set([
  'New',
  'Backlog',
  'Drafted',
  'Needs Retry',
]);

export function isApplicationFunnelStatus(status: string): boolean {
  return APPLICATION_FUNNEL_SET.has(status);
}
