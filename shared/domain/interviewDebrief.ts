export const INTERVIEW_DEBRIEF_OUTCOMES = [
  'Pending',
  'Went well',
  'Concerns',
  'Rejected',
  'Ghosted',
] as const;

export type InterviewDebriefOutcome = (typeof INTERVIEW_DEBRIEF_OUTCOMES)[number];

export interface InterviewDebrief {
  id: string;
  job_id: string;
  date: string;
  notes: string;
  outcome: InterviewDebriefOutcome;
  created_at: string;
  updated_at: string;
}

export function isValidDebriefOutcome(value: unknown): value is InterviewDebriefOutcome {
  return typeof value === 'string' && (INTERVIEW_DEBRIEF_OUTCOMES as readonly string[]).includes(value);
}

export function normalizeDebriefDate(value: unknown): string | null {
  if (typeof value !== 'string' || !value.trim()) return null;
  const trimmed = value.trim();
  const parsed = trimmed.length === 10 ? new Date(`${trimmed}T12:00:00`) : new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString();
}

export function toDebriefDateInputValue(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
