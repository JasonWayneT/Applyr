import { db, logActivity } from '../db.js';
import { insertJob } from '../repository/jobRepository.js';
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
import { createTheirstackConnector } from '../../packages/connectors/theirstack/index.js';
import {
  passesTargetRoleTitleScope,
  passesIndustryGate,
  passesGeographicGate,
  passesCompanyBlocklist,
  titleMatchesBlocked,
  type GateConfig,
  type ScrapedJob,
} from '../../shared/domain/gates.js';
import { loadMaterializedScoutPrefs } from '../../shared/domain/scoutPrefs.js';
import { writeJobStagingFile } from './jobStaging.js';
import { broadcastSyncEvent } from '../routes/pipeline.js';
import { isBlockedScrapeUrl } from '../../shared/domain/blockedScrapeHosts.js';

const MIN_JD_CHARS = 200;

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

function passesTitleBlocklist(title: string, blocklist: string[]): boolean {
  return !blocklist.some((term) => titleMatchesBlocked(title, term));
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
  const prefs = loadMaterializedScoutPrefs();
  const adzuna = loadAdzunaCredentials();
  const titleScopePrefs = {
    targetRole: prefs.targetRole,
    searchTerms: prefs.searchTerms,
    builtinStrictTitle: prefs.builtinStrictTitle,
  };

  return [
    createRemotiveConnector({ searchTerms: prefs.searchTerms }),
    createRemoteokConnector({ searchTerms: prefs.searchTerms }),
    createWeworkremotelyConnector({ titleScopePrefs }),
    createHimalayasConnector({ searchTerms: prefs.searchTerms, titleScopePrefs }),
    createThemuseConnector(),
    createJobicyConnector({ searchTerms: prefs.searchTerms }),
    createWorkingnomadsConnector({ searchTerms: prefs.searchTerms }),
    createJobscolliderConnector({ titleScopePrefs }),
    createAdzunaConnector({ appId: adzuna.appId, appKey: adzuna.appKey, searchTerms: prefs.searchTerms }),
    createOpenPostingsConnector({ searchTerms: prefs.searchTerms }),
    createTheirstackConnector({ searchTerms: prefs.searchTerms }),
  ];
}

export async function runConnectorOrchestration(
  connectors: JobConnector[] = buildDefaultConnectors(),
): Promise<void> {
  const prefs = loadMaterializedScoutPrefs();
  const gateConfig: GateConfig = {
    blockedIndustries: prefs.blockedIndustries,
    titleBlocklist: prefs.titleBlocklist,
    workSetting: prefs.workSetting,
    maxExperienceYears: prefs.maxExperienceYears,
    localAreaTerms: prefs.localAreaTerms,
    locationPreference: prefs.locationPreference,
  };
  const targetPrefs = {
    targetRole: prefs.targetRole,
    searchTerms: prefs.searchTerms,
    builtinStrictTitle: prefs.builtinStrictTitle,
  };
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

          if (!passesTitleBlocklist(job.title, prefs.titleBlocklist)) {
            filtered++;
            logActivity('INFO', source, `[REJECT] ${job.title} at ${job.company} - Title Blocklist`);
            continue;
          }

          if (!passesCompanyBlocklist(job.company, prefs.blockedCompanies)) {
            filtered++;
            logActivity('INFO', source, `[REJECT] ${job.title} at ${job.company} - Company blocklist`);
            continue;
          }

          if (!passesTargetRoleTitleScope(job.title, targetPrefs, source)) {
            filtered++;
            logActivity(
              'INFO',
              source,
              `[REJECT] ${job.title} at ${job.company} - target_role_scope:${prefs.targetRole}`,
            );
            continue;
          }

          const scraped: ScrapedJob = {
            company: job.company,
            title: job.title,
            url: job.url ?? '',
            description: job.description ?? '',
            source,
          };
          if (!passesIndustryGate(scraped, gateConfig)) {
            filtered++;
            continue;
          }
          if (!passesGeographicGate(scraped, gateConfig)) {
            filtered++;
            continue;
          }

          if (job.url && isBlockedScrapeUrl(job.url)) {
            filtered++;
            logActivity(
              'INFO',
              source,
              `[REJECT] ${job.title} at ${job.company} - LinkedIn URL blocked (FR-080)`,
            );
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
            const jobId = insertJob({
              company: job.company,
              title: job.title,
              url: job.url ?? null,
              status: hasJd ? 'Drafted' : 'New',
              salary_range: job.salary_range ?? null,
              source_site: job.source_site,
              jd_text: hasJd ? desc : null,
            });
            if (hasJd) {
              writeJobStagingFile(jobId, job.company, job.url, desc);
            }
            saved++;
            logActivity('INFO', source, `[FOUND] ${job.title} at ${job.company}`);
          } catch (err) {
            logActivity('ERROR', source, `[ERROR] Failed to insert ${job.title} at ${job.company}: ${err instanceof Error ? err.message : String(err)}`);
            filtered++;
          }
        } catch {
          filtered++;
        }
      }
      logActivity('INFO', 'Scout', `${source}: ${rawJobs.length} fetched, ${saved} saved`);
      totalSaved += saved;

      broadcastSyncEvent('source_progress', {
        type: 'source_progress',
        source,
        fetched: rawJobs.length,
        filtered,
        passed: saved,
      });

      try {
        const prevStatusRow = db.prepare('SELECT status FROM sources WHERE id = ?').get(source) as
          | { status: string }
          | undefined;
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
