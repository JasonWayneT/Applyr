-- Migration 001: Add domain_policies table for crawl governance
-- Applied by server/migrations runner at startup (idempotent)

CREATE TABLE IF NOT EXISTS domain_policies (
  domain TEXT PRIMARY KEY,
  robots_reviewed INTEGER NOT NULL DEFAULT 0,
  robots_reviewed_at TEXT,
  tos_reviewed INTEGER NOT NULL DEFAULT 0,
  tos_reviewed_at TEXT,
  max_rps REAL NOT NULL DEFAULT 0.5,
  cooldown_seconds INTEGER NOT NULL DEFAULT 10,
  status TEXT NOT NULL DEFAULT 'manual_review'
    CHECK(status IN ('allowed', 'paused', 'blocked', 'manual_review'))
);

-- Seed: builtin.com — robots.txt and ToS reviewed 2026-06-12
INSERT OR IGNORE INTO domain_policies
  (domain, robots_reviewed, robots_reviewed_at, tos_reviewed, tos_reviewed_at, max_rps, cooldown_seconds, status)
VALUES
  ('builtin.com', 1, '2026-06-12', 1, '2026-06-12', 0.5, 10, 'allowed');

-- Seed: levels.fyi — robots.txt and ToS reviewed 2026-06-12
INSERT OR IGNORE INTO domain_policies
  (domain, robots_reviewed, robots_reviewed_at, tos_reviewed, tos_reviewed_at, max_rps, cooldown_seconds, status)
VALUES
  ('levels.fyi', 1, '2026-06-12', 1, '2026-06-12', 0.5, 10, 'allowed');
