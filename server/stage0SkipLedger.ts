/**
 * Stage 0 skip ledger helpers (CR-091 / FR-264).
 * Keep URL normalization in lockstep with scripts/stage0_skip_ledger.py.
 */
import type Database from 'better-sqlite3';

const TRACKING_PARAMS = new Set(['gh_src', 'source', 'ref', 'trk', 'mc_cid', 'mc_eid']);

export function normalizeSkipUrl(url: string | null | undefined): string | null {
  if (!url || !url.trim()) return null;
  try {
    const parsed = new URL(url.trim());
    parsed.hostname = parsed.hostname.toLowerCase();
    parsed.protocol = (parsed.protocol || 'https:').toLowerCase();
    parsed.hash = '';
    parsed.pathname = parsed.pathname.replace(/\/+$/, '') || '';
    for (const key of [...parsed.searchParams.keys()]) {
      const lower = key.toLowerCase();
      if (lower.startsWith('utm_') || TRACKING_PARAMS.has(lower)) {
        parsed.searchParams.delete(key);
      }
    }
    let out = parsed.toString();
    if (out.endsWith('/')) out = out.slice(0, -1);
    return out;
  } catch {
    return url.trim().toLowerCase().replace(/\/+$/, '') || null;
  }
}

export function postingKey(company: string, title: string): string {
  return `${(company || '').trim().toLowerCase()}||${(title || '').trim().toLowerCase()}`;
}

type SkipRow = {
  id: number;
  url: string | null;
  skip_reason: string;
};

export function lookupStage0Skip(
  db: Database.Database,
  url: string | null | undefined,
  company: string,
  title: string,
): SkipRow | null {
  try {
    const urlKey = normalizeSkipUrl(url);
    if (urlKey) {
      const byUrl = db
        .prepare('SELECT id, url, skip_reason FROM stage0_skips WHERE url_key = ?')
        .get(urlKey) as SkipRow | undefined;
      if (byUrl) return byUrl;
    }
    const key = postingKey(company, title);
    if (key === '||') return null;
    const byPosting = db
      .prepare('SELECT id, url, skip_reason FROM stage0_skips WHERE posting_key = ?')
      .get(key) as SkipRow | undefined;
    return byPosting ?? null;
  } catch {
    return null;
  }
}

export function recordStage0Skip(
  db: Database.Database,
  args: {
    url?: string | null;
    company: string;
    title: string;
    skipReason: string;
    slug?: string;
    archivePath?: string;
  },
): void {
  const urlKey = normalizeSkipUrl(args.url ?? null);
  const key = postingKey(args.company, args.title);
  const now = new Date().toISOString();
  const existing = lookupStage0Skip(db, args.url ?? null, args.company, args.title);
  if (existing) {
    db.prepare(
      `UPDATE stage0_skips
       SET url = ?, url_key = ?, company = ?, title = ?, posting_key = ?,
           skip_reason = ?, decided_at = ?, slug = ?, archive_path = ?
       WHERE id = ?`,
    ).run(
      args.url ?? existing.url,
      urlKey,
      args.company,
      args.title,
      key,
      args.skipReason,
      now,
      args.slug ?? null,
      args.archivePath ?? null,
      existing.id,
    );
    return;
  }
  db.prepare(
    `INSERT INTO stage0_skips (
       url, url_key, company, title, posting_key, skip_reason, decided_at, slug, archive_path
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
    args.url ?? null,
    urlKey,
    args.company,
    args.title,
    key,
    args.skipReason,
    now,
    args.slug ?? null,
    args.archivePath ?? null,
  );
}
