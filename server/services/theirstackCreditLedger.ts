import { db, logActivity } from '../db.js';
import {
  clampFetchLimit,
  currentMonthKey,
  DEFAULT_THEIRSTACK_SETTINGS,
  monthKeyFromIso,
  type TheirStackSettings,
} from '../../shared/domain/theirstackCredits.js';

const SOURCE_ID = 'theirstack';
const SETTINGS_KEY = 'theirstack_settings';

type SourceCreditRow = {
  credits_used_this_month: number;
  credits_reset_at: string | null;
  status: string;
};

export function loadTheirstackSettings(): TheirStackSettings {
  const envLimit = process.env.THEIRSTACK_FETCH_LIMIT;
  let settings = { ...DEFAULT_THEIRSTACK_SETTINGS };

  try {
    const row = db.prepare('SELECT value FROM profiles WHERE key = ?').get(SETTINGS_KEY) as
      | { value: string }
      | undefined;
    if (row?.value) {
      const parsed = JSON.parse(row.value) as Partial<TheirStackSettings>;
      settings = {
        fetchLimitPerRun: clampFetchLimit(parsed.fetchLimitPerRun ?? settings.fetchLimitPerRun),
        monthlyCap: parsed.monthlyCap ?? settings.monthlyCap,
        warnThreshold: parsed.warnThreshold ?? settings.warnThreshold,
      };
    }
  } catch {
    /* use defaults */
  }

  if (envLimit) {
    settings = { ...settings, fetchLimitPerRun: clampFetchLimit(envLimit) };
  }

  return settings;
}

/** Reset credits when the calendar month rolls over. Returns true if a reset occurred. */
export function resetTheirstackCreditsIfNewMonth(): boolean {
  try {
    const row = db.prepare(
      'SELECT credits_used_this_month, credits_reset_at, status FROM sources WHERE id = ?',
    ).get(SOURCE_ID) as SourceCreditRow | undefined;

    if (!row) return false;

    const now = new Date();
    const currentMonth = currentMonthKey(now);
    const storedMonth = monthKeyFromIso(row.credits_reset_at);

    if (storedMonth === currentMonth) return false;

    db.prepare(`
      UPDATE sources
      SET credits_used_this_month = 0,
          credits_reset_at = ?,
          status = 'active'
      WHERE id = ?
    `).run(now.toISOString(), SOURCE_ID);

    logActivity(
      'INFO',
      SOURCE_ID,
      `Monthly credit reset (${currentMonth}): 0/${DEFAULT_THEIRSTACK_SETTINGS.monthlyCap} used`,
    );
    return true;
  } catch {
    return false;
  }
}

export function getTheirstackCreditState(): {
  used: number;
  cap: number;
  warnThreshold: number;
  resetAt: string | null;
} {
  resetTheirstackCreditsIfNewMonth();
  const settings = loadTheirstackSettings();

  try {
    const row = db.prepare(
      'SELECT credits_used_this_month, credits_reset_at FROM sources WHERE id = ?',
    ).get(SOURCE_ID) as { credits_used_this_month: number; credits_reset_at: string | null } | undefined;

    return {
      used: row?.credits_used_this_month ?? 0,
      cap: settings.monthlyCap,
      warnThreshold: settings.warnThreshold,
      resetAt: row?.credits_reset_at ?? null,
    };
  } catch {
    return {
      used: 0,
      cap: settings.monthlyCap,
      warnThreshold: settings.warnThreshold,
      resetAt: null,
    };
  }
}

export function checkTheirstackCredits(settings = loadTheirstackSettings()): {
  allowed: boolean;
  used: number;
  remaining: number;
  cap: number;
  warnThreshold: number;
} {
  resetTheirstackCreditsIfNewMonth();
  const cap = settings.monthlyCap;

  try {
    const row = db.prepare('SELECT credits_used_this_month FROM sources WHERE id = ?').get(SOURCE_ID) as
      | { credits_used_this_month: number }
      | undefined;
    const used = row?.credits_used_this_month ?? 0;
    const remaining = Math.max(0, cap - used);
    return {
      allowed: used < cap,
      used,
      remaining,
      cap,
      warnThreshold: settings.warnThreshold,
    };
  } catch {
    return {
      allowed: true,
      used: 0,
      remaining: cap,
      cap,
      warnThreshold: settings.warnThreshold,
    };
  }
}

export function incrementTheirstackCredits(count: number): void {
  if (count <= 0) return;
  try {
    db.prepare(
      'UPDATE sources SET credits_used_this_month = credits_used_this_month + ? WHERE id = ?',
    ).run(count, SOURCE_ID);
  } catch {
    /* ignore in tests */
  }
}

export function pauseTheirstackSource(): void {
  try {
    db.prepare("UPDATE sources SET status = 'paused' WHERE id = ?").run(SOURCE_ID);
  } catch {
    /* ignore */
  }
}
