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

/** Statuses that should auto-advance to 'Recruiter Screen' when an interview_date is set. */
const PROMOTES_TO_RECRUITER_SCREEN = new Set<string>([...PRE_APPLY_STATUSES, 'Applied']);

/**
 * Forward-only status advance when a job's interview_date is set or changed.
 * Not-yet-screening statuses (New/Backlog/Drafted/Needs Retry/Applied) move to
 * 'Recruiter Screen'; 'Recruiter Screen' moves to 'Core Interviews'. Anything already
 * at or past 'Core Interviews' (including 'Offer and Negotiation' and 'Closed') is left
 * alone, so a later interview date (e.g. a second-round call) never demotes a job that
 * already advanced further. Returns null when no promotion applies.
 */
export function deriveStatusForInterviewDateChange(currentStatus: string): string | null {
  if (currentStatus === 'Recruiter Screen') return 'Core Interviews';
  if (PROMOTES_TO_RECRUITER_SCREEN.has(currentStatus)) return 'Recruiter Screen';
  return null;
}
