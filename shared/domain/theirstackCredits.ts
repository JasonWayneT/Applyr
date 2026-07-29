/** TheirStack free-tier credit constants (1 credit per job returned). */
export const THEIRSTACK_MONTHLY_CAP = 200;
export const THEIRSTACK_WARN_THRESHOLD = 160;
export const THEIRSTACK_MAX_PAGE_SIZE = 25;
export const THEIRSTACK_DEFAULT_FETCH_LIMIT = 10;

export interface TheirStackSettings {
  fetchLimitPerRun: number;
  monthlyCap: number;
  warnThreshold: number;
}

export const DEFAULT_THEIRSTACK_SETTINGS: TheirStackSettings = {
  fetchLimitPerRun: THEIRSTACK_DEFAULT_FETCH_LIMIT,
  monthlyCap: THEIRSTACK_MONTHLY_CAP,
  warnThreshold: THEIRSTACK_WARN_THRESHOLD,
};

export function currentMonthKey(date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  return `${y}-${m}`;
}

export function monthKeyFromIso(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return currentMonthKey(d);
}

export function clampFetchLimit(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return THEIRSTACK_DEFAULT_FETCH_LIMIT;
  return Math.min(THEIRSTACK_MAX_PAGE_SIZE, Math.max(1, Math.round(n)));
}
