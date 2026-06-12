import fs from 'fs';
import path from 'path';
import { db, logActivity } from '../db.js';
import { insertJob } from '../repository/jobRepository.js';
import { checkCrawlPolicy } from '../middleware/crawlPolicy.js';
import type { JobConnector } from '../../shared/types/connectors.js';
import { createRemotiveConnector } from '../../packages/connectors/remotive/index.js';
import { createRemoteokConnector } from '../../packages/connectors/remoteok/index.js';
import { createWeworkremotelyConnector } from '../../packages/connectors/weworkremotely/index.js';
import { createHimalayasConnector } from '../../packages/connectors/himalayas/index.js';
import { createThemuseConnector } from '../../packages/connectors/themuse/index.js';
import { createJobicyConnector } from '../../packages/connectors/jobicy/index.js';
import { createWorkingnomadsConnector } from '../../packages/connectors/workingnomads/index.js';
import { createJobscolliderConnector } from '../../packages/connectors/jobscollider/index.js';
import { createAdzunaConnector } from '../../packages/connectors/adzuna/index.js';
import { createOpenPostingsConnector } from '../../packages/connectors/openpostings/index.js';
import { createBuiltInConnector } from '../../packages/connectors/builtin/index.js';
import { createLevelsFyiConnector } from '../../packages/connectors/levelsfyi/index.js';
import { createGreenhouseConnector } from '../../packages/connectors/greenhouse/index.js';
import { createLeverConnector } from '../../packages/connectors/lever/index.js';
import { createAshbyConnector } from '../../packages/connectors/ashby/index.js';
import { createWorkableConnector } from '../../packages/connectors/workable/index.js';
import { createTheirstackConnector } from '../../packages/connectors/theirstack/index.js';

const MIN_JD_CHARS = 200;

const DEFAULT_TITLE_BLOCKLIST = [
  'staff', 'vp', 'head', 'principal', 'lead', 'director',
  'group product manager', 'gpm', 'growth', 'founding', 'first',
  'manager of', 'engineering manager', 'people manager',
  'assistant', 'coordinator', 'intern', 'associate', 'entry', 'junior',
  'analyst', 'software engineer', 'developer', 'designer', 'marketer',
];

interface Prefs {
  search_terms?: string[];
  blocked_titles?: string[];
}

function loadPrefs(): { searchTerms: string[]; titleBlocklist: string[] } {
  let prefs: Prefs = {};
  try {
    const raw = fs.readFileSync(path.resolve('data/candidate_preferences.json'), 'utf-8');
    prefs = JSON.parse(raw) as Prefs;
  } catch { /* use built-in defaults when file is absent */ }

  const searchTerms = prefs.search_terms?.length ? prefs.search_terms : ['Product Manager'];
  const blockedTitles = prefs.blocked_titles?.length ? prefs.blocked_titles : DEFAULT_TITLE_BLOCKLIST;
  const titleBlocklist = blockedTitles.map((t) => t.toLowerCase().trim()).filter(Boolean);

  return { searchTerms, titleBlocklist };
}

function loadAdzunaCredentials(): { appId: string; appKey: string } {
  if (process.env.ADZUNA_APP_ID && process.env.ADZUNA_APP_KEY) {
    return { appId: process.env.ADZUNA_APP_ID, appKey: process.env.ADZUNA_APP_KEY };
  }
  const row = db
    .prepare("SELECT value FROM profiles WHERE key = 'api_connections'")
    .get() as { value: string } | undefined;
  if (row?.value) {
    try {
      const conns = JSON.parse(row.value) as Record<string, string>;
      return { appId: conns['adzunaAppId'] ?? '', appKey: conns['adzunaAppKey'] ?? '' };
    } catch { /* ignore malformed JSON */ }
  }
  return { appId: '', appKey: '' };
}

function titleMatchesBlockedTerm(title: string, term: string): boolean {
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`\\b${escaped}\\b`, 'i').test(title);
}

function passesTitleBlocklist(title: string, blocklist: string[]): boolean {
  return !blocklist.some((term) => titleMatchesBlockedTerm(title, term));
}

function isUrlKnown(url: string): boolean {
  return !!(
    db.prepare('SELECT id FROM jobs WHERE url = ?').get(url) ||
    db.prepare('SELECT url FROM stale_jobs WHERE url = ?').get(url)
  );
}

function isCompanyTitleNew(company: string, title: string): boolean {
  return !(
    db
      .prepare('SELECT id FROM jobs WHERE LOWER(company) = LOWER(?) AND LOWER(title) = LOWER(?)')
      .get(company, title) ||
    db
      .prepare('SELECT url FROM stale_jobs WHERE LOWER(company) = LOWER(?) AND LOWER(title) = LOWER(?)')
      .get(company, title)
  );
}

export function buildDefaultConnectors(): JobConnector[] {
  const builtinOnly = ['1', 'true', 'yes'].includes(
    (process.env.SCOUT_BUILTIN_ONLY ?? '').toLowerCase(),
  );
  if (builtinOnly) {
    return [createBuiltInConnector({ policyChecker: checkCrawlPolicy })];
  }

  const { searchTerms } = loadPrefs();
  const adzuna = loadAdzunaCredentials();

  return [
    createRemotiveConnector({ searchTerms }),
    createRemoteokConnector({ searchTerms }),
    createWeworkremotelyConnector(),
    createHimalayasConnector({ searchTerms }),
    createThemuseConnector(),
    createJobicyConnector({ searchTerms }),
    createWorkingnomadsConnector(),
    createJobscolliderConnector(),
    createAdzunaConnector({ appId: adzuna.appId, appKey: adzuna.appKey, searchTerms }),
    createOpenPostingsConnector({ searchTerms }),
    createBuiltInConnector({ policyChecker: checkCrawlPolicy }),
    createLevelsFyiConnector({ policyChecker: checkCrawlPolicy }),
    createGreenhouseConnector({ searchTerms }),
    createLeverConnector({ searchTerms }),
    createAshbyConnector({ searchTerms }),
    createWorkableConnector({ searchTerms }),
    createTheirstackConnector({ searchTerms }),
  ];
}

import { broadcastSyncEvent } from '../routes/pipeline.js';

export async function runConnectorOrchestration(
  connectors: JobConnector[] = buildDefaultConnectors(),
): Promise<void> {
  const { titleBlocklist } = loadPrefs();
  let totalSaved = 0;

  for (const connector of connectors) {
    const source = connector.sourceId;
    try {
      logActivity('INFO', 'Scout', `Running connector: ${source}`);
      const rawJobs = await connector.fetchJobs();
      let saved = 0;
      let filtered = 0;

      for (const raw of rawJobs) {
        try {
          const job = connector.normalize(raw);
          if (!job.title || !job.company) {
            filtered++;
            continue;
          }

          if (!passesTitleBlocklist(job.title, titleBlocklist)) {
            filtered++;
            logActivity('INFO', source, `[REJECT] ${job.title} at ${job.company} - Title Blocklist`);
            continue;
          }

          if (job.url && isUrlKnown(job.url)) {
            filtered++;
            logActivity('INFO', source, `[REJECT] ${job.title} at ${job.company} - URL already exists`);
            continue;
          }

          if (!isCompanyTitleNew(job.company, job.title)) {
            filtered++;
            logActivity('INFO', source, `[REJECT] ${job.title} at ${job.company} - Company/Title already exists`);
            continue;
          }

          const desc = (job.description ?? '').trim();
          const hasJd = desc.length >= MIN_JD_CHARS;

          try {
            insertJob({
              company: job.company,
              title: job.title,
              url: job.url ?? null,
              status: hasJd ? 'Drafted' : 'New',
              salary_range: job.salary_range ?? null,
              source_site: job.source_site,
              jd_text: hasJd ? desc : null,
            });
            saved++;
            logActivity('INFO', source, `[FOUND] ${job.title} at ${job.company}`);
          } catch {
            filtered++;
            /* UNIQUE url constraint — expected for duplicates */
          }
        } catch {
          filtered++;
          /* malformed row — skip */
        }
      }
      logActivity('INFO', 'Scout', `${source}: ${rawJobs.length} fetched, ${saved} saved`);
      totalSaved += saved;

      // Emit source progress SSE
      broadcastSyncEvent('source_progress', {
        type: 'source_progress',
        source,
        fetched: rawJobs.length,
        filtered,
        passed: saved,
      });

      try {
        const prevStatusRow = db.prepare('SELECT status FROM sources WHERE id = ?').get(source) as { status: string } | undefined;
        db.prepare(`
          UPDATE sources 
          SET last_success_at = ?, consecutive_failures = 0, status = 'active'
          WHERE id = ?
        `).run(new Date().toISOString(), source);

        if (prevStatusRow && prevStatusRow.status !== 'active') {
          broadcastSyncEvent('source_health', {
            type: 'source_health',
            source,
            status: 'active',
          });
        }
      } catch (dbErr) {
        console.warn(`[scout] Failed to update success stats for ${source}:`, dbErr);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      logActivity('ERROR', source, `Connector failed: ${msg}`);

      // Emit connector error SSE
      broadcastSyncEvent('connector_error', {
        type: 'connector_error',
        source,
        error: msg,
      });

      try {
        const row = db.prepare('SELECT consecutive_failures, status FROM sources WHERE id = ?').get(source) as
          | { consecutive_failures: number; status: string }
          | undefined;
        const nextFailures = (row?.consecutive_failures ?? 0) + 1;
        const status = nextFailures >= 3 ? 'error' : 'warning';

        db.prepare(`
          UPDATE sources 
          SET last_error_at = ?, consecutive_failures = ?, status = ? 
          WHERE id = ?
        `).run(new Date().toISOString(), nextFailures, status, source);

        if (!row || row.status !== status) {
          broadcastSyncEvent('source_health', {
            type: 'source_health',
            source,
            status,
          });
        }
      } catch (dbErr) {
        console.warn(`[scout] Failed to update error stats for ${source}:`, dbErr);
      }
    }
  }

  logActivity('INFO', 'Scout', `Scout orchestration complete. Total saved: ${totalSaved}`);
}
