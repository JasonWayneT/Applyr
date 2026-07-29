import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { db } from '../../server/db.js';
import {
  checkTheirstackCredits,
  resetTheirstackCreditsIfNewMonth,
} from '../../server/services/theirstackCreditLedger.js';
import { currentMonthKey } from '../../shared/domain/theirstackCredits.js';

function seedTheirstackRow(used: number, resetAt: string | null) {
  db.prepare(`
    INSERT OR REPLACE INTO sources (id, name, type, status, credits_used_this_month, credits_reset_at)
    VALUES ('theirstack', 'TheirStack', 'vendor_api', 'active', ?, ?)
  `).run(used, resetAt);
}

beforeEach(() => {
  seedTheirstackRow(0, new Date().toISOString());
});

afterEach(() => {
  db.prepare("DELETE FROM profiles WHERE key = 'theirstack_settings'").run();
});

describe('theirstackCreditLedger', () => {
  it('resetTheirstackCreditsIfNewMonth resets when stored month differs', () => {
    const priorMonth = new Date();
    priorMonth.setMonth(priorMonth.getMonth() - 1);
    seedTheirstackRow(150, priorMonth.toISOString());
    db.prepare("UPDATE sources SET status = 'paused' WHERE id = 'theirstack'").run();

    const didReset = resetTheirstackCreditsIfNewMonth();
    expect(didReset).toBe(true);

    const row = db.prepare(
      "SELECT credits_used_this_month, status, credits_reset_at FROM sources WHERE id = 'theirstack'",
    ).get() as { credits_used_this_month: number; status: string; credits_reset_at: string };

    expect(row.credits_used_this_month).toBe(0);
    expect(row.status).toBe('active');
    expect(currentMonthKey(new Date(row.credits_reset_at))).toBe(currentMonthKey());
  });

  it('resetTheirstackCreditsIfNewMonth is a no-op within the same month', () => {
    seedTheirstackRow(42, new Date().toISOString());

    const didReset = resetTheirstackCreditsIfNewMonth();
    expect(didReset).toBe(false);

    const row = db.prepare(
      'SELECT credits_used_this_month FROM sources WHERE id = ?',
    ).get('theirstack') as { credits_used_this_month: number };
    expect(row.credits_used_this_month).toBe(42);
  });

  it('checkTheirstackCredits respects configurable fetch limit settings', () => {
    seedTheirstackRow(5, new Date().toISOString());
    db.prepare(`
      INSERT OR REPLACE INTO profiles (key, value) VALUES ('theirstack_settings', ?)
    `).run(JSON.stringify({ fetchLimitPerRun: 8 }));

    const state = checkTheirstackCredits();
    expect(state.used).toBe(5);
    expect(state.remaining).toBe(195);
    expect(state.allowed).toBe(true);
  });
});
