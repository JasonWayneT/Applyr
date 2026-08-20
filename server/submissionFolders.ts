import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import { db, logActivity } from './db.js';
import {
  SUBMISSION_DIR,
  ARCHIVE_DIR,
  SKIPPED_ARCHIVE_DIR,
  resolveCompanyFolder,
} from './shared.js';
import { recordStage0Skip } from './stage0SkipLedger.js';
import { isActivePipelineStatus } from './domain/jobStatus.js';

/** Implements FR-030 — slug used for new folders; fuzzy match for existing ones. */
export function companySlug(company: string): string {
  let slug = company.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  if (!slug) {
    slug = 'company_' + crypto.createHash('md5').update(company).digest('hex').slice(0, 12);
  }
  return slug;
}

function folderNamesMatch(a: string, b: string): boolean {
  const norm = (s: string) => s.toLowerCase().replace(/[_-]/g, '');
  return a === b || norm(a) === norm(b);
}

/**
 * Merge files from src into dest (newer active copies overwrite archive).
 *
 * Safety (2026-07-31, Jason-prompted): this used to call fs.copyFileSync
 * unconditionally, silently destroying whatever was at `to` if a name
 * collided. Found real: reconcileActiveSubmissionFolders() archived a fresh
 * same-day resume/cover-letter draft into an archive folder that already
 * held real files from a genuine prior application cycle for that same
 * company (Interview_Cheat_Sheet.md, Research_Packet.pdf) -- the folder-name
 * match is by company slug only, with no concept of "this is a different
 * posting" vs "this is the same posting reposted." Before overwriting any
 * existing destination file whose content actually differs from the
 * incoming one, the old version is preserved as `{name}.bak-{timestamp}`
 * rather than silently lost. This does not fix the deeper issue (one folder
 * per company, not per posting) -- it just guarantees nothing real
 * disappears without a trace while that's still true.
 */
export function mergeSubmissionFolder(src: string, dest: string): void {
  fs.mkdirSync(dest, { recursive: true });
  for (const name of fs.readdirSync(src)) {
    const from = path.join(src, name);
    const to = path.join(dest, name);
    if (fs.statSync(from).isDirectory()) {
      mergeSubmissionFolder(from, to);
    } else {
      if (fs.existsSync(to)) {
        const existing = fs.readFileSync(to);
        const incoming = fs.readFileSync(from);
        if (!existing.equals(incoming)) {
          const stamp = fs.statSync(to).mtime.toISOString().replace(/[:.]/g, '-');
          const backupPath = path.join(dest, `${name}.bak-${stamp}`);
          if (!fs.existsSync(backupPath)) fs.copyFileSync(to, backupPath);
        }
      }
      fs.copyFileSync(from, to);
    }
  }
}

/** Prefer atomic rename; on Windows EPERM (locked file/handle), fall back to copy+delete. */
function moveOrMergeFolder(src: string, dest: string): void {
  if (fs.existsSync(dest)) {
    mergeSubmissionFolder(src, dest);
    fs.rmSync(src, { recursive: true, force: true });
    return;
  }
  try {
    fs.renameSync(src, dest);
  } catch (err) {
    const code = (err as NodeJS.ErrnoException)?.code;
    if (code !== 'EPERM' && code !== 'EACCES' && code !== 'EBUSY') throw err;
    mergeSubmissionFolder(src, dest);
    fs.rmSync(src, { recursive: true, force: true });
  }
}

/** Move or merge active submissions folder into archive (FR-030). */
export function archiveActiveSubmission(company: string): boolean {
  const activePath = resolveCompanyFolder(company, SUBMISSION_DIR);
  if (!fs.existsSync(activePath)) return false;

  fs.mkdirSync(ARCHIVE_DIR, { recursive: true });
  const archivePath = resolveCompanyFolder(company, ARCHIVE_DIR);
  moveOrMergeFolder(activePath, archivePath);
  return true;
}

/** Restore archived folder to active workspace when status returns to Backlog/Drafted. */
export function restoreArchivedSubmission(company: string): boolean {
  const archivePath = resolveCompanyFolder(company, ARCHIVE_DIR);
  if (!fs.existsSync(archivePath)) return false;

  const activePath = resolveCompanyFolder(company, SUBMISSION_DIR);
  fs.mkdirSync(SUBMISSION_DIR, { recursive: true });
  moveOrMergeFolder(archivePath, activePath);
  return true;
}

function hasResumeAndCoverPdfs(folder: string): boolean {
  try {
    const pdfs = fs.readdirSync(folder).filter(f => f.toLowerCase().endsWith('.pdf'));
    const hasResume = pdfs.some(f => f.toLowerCase().includes('resume'));
    const hasCover = pdfs.some(f => f.toLowerCase().includes('cover'));
    return hasResume && hasCover;
  } catch {
    return false;
  }
}

/**
 * True when a folder holds Stage 0 fit-gate output from generate-submission/SKILL.md but hasn't
 * reached Stage 1 drafting yet (2026-08-03, Jason-prompted after a real data loss). Stage 0's own
 * step 5 tells an agent to persist stage0_fit_gate.json + Original_JD.txt in the submission folder
 * ahead of drafting, as a deliberate hold point between triage and authoring -- but
 * reconcileActiveSubmissionFolders() ran on every server startup and treated exactly that folder
 * shape (no PDFs, no jobs row yet) as an "orphan stub" and fs.rmSync'd it. Five real Tier-2
 * fit-gate folders were deleted this way the first time a dev server restarted mid-batch. A PASS
 * folder carrying this file is legitimate in-progress work -- exempt it from the orphan sweep.
 * SKIP gates are swept to data/archive/skipped/ (CR-091); they must not stay in submissions/.
 */
function hasStage0FitGate(folder: string): boolean {
  try {
    return fs.existsSync(path.join(folder, 'stage0_fit_gate.json'));
  } catch {
    return false;
  }
}

function readStage0Decision(folder: string): { decision: string; company: string; title: string; url: string | null; reason: string } | null {
  try {
    const raw = fs.readFileSync(path.join(folder, 'stage0_fit_gate.json'), 'utf8');
    const gate = JSON.parse(raw) as {
      decision?: string;
      company?: string;
      role?: string;
      url?: string | null;
      skip_reason?: string;
      notes?: string;
    };
    return {
      decision: (gate.decision || '').toUpperCase(),
      company: gate.company || path.basename(folder),
      title: gate.role || '',
      url: gate.url ?? null,
      reason: gate.skip_reason || gate.notes || 'Stage 0 Skip',
    };
  } catch {
    return null;
  }
}

/** Move a SKIP fit-gate folder out of submissions so it cannot clutter the live workspace. */
function sweepSkippedFitGate(folderName: string, activePath: string): boolean {
  const gate = readStage0Decision(activePath);
  if (!gate || gate.decision !== 'SKIP') return false;
  fs.mkdirSync(SKIPPED_ARCHIVE_DIR, { recursive: true });
  let dest = path.join(SKIPPED_ARCHIVE_DIR, folderName);
  if (fs.existsSync(dest)) {
    dest = `${dest}_${new Date().toISOString().replace(/[:.]/g, '-')}`;
  }
  moveOrMergeFolder(activePath, dest);
  try {
    recordStage0Skip(db, {
      url: gate.url,
      company: gate.company,
      title: gate.title,
      skipReason: gate.reason,
      slug: folderName,
      archivePath: dest,
    });
  } catch (err) {
    console.warn('[FR-264] skip ledger write failed for', folderName, err);
  }
  return true;
}

function findJobsForFolder(folderName: string): { company: string; status: string }[] {
  const rows = db.prepare('SELECT company, status FROM jobs').all() as { company: string; status: string }[];
  return rows.filter(j => folderNamesMatch(companySlug(j.company), folderName));
}

/**
 * Ensures submissions/ only holds active pipeline workspaces.
 * Archives folders tied to Applied+ jobs; removes orphan stubs.
 */
export function reconcileActiveSubmissionFolders(): { archived: string[]; removed: string[] } {
  const archived: string[] = [];
  const removed: string[] = [];

  if (!fs.existsSync(SUBMISSION_DIR)) return { archived, removed };

  for (const folderName of fs.readdirSync(SUBMISSION_DIR)) {
    const activePath = path.join(SUBMISSION_DIR, folderName);
    if (!fs.statSync(activePath).isDirectory()) continue;

    const matches = findJobsForFolder(folderName);
    const inactive = matches.length > 0 && matches.every(j => !isActivePipelineStatus(j.status));
    const orphanStub = matches.length === 0 && !hasResumeAndCoverPdfs(activePath);

    if (!inactive && !orphanStub) continue;

    if (hasResumeAndCoverPdfs(activePath)) {
      const company = matches[0]?.company ?? folderName;
      if (archiveActiveSubmission(company)) archived.push(folderName);
    } else if (sweepSkippedFitGate(folderName, activePath)) {
      archived.push(folderName);
    } else if (!hasStage0FitGate(activePath)) {
      fs.rmSync(activePath, { recursive: true, force: true });
      removed.push(folderName);
    }
    // else: PASS Stage 0 fit-gate-only folder, no PDFs yet -- leave it in place.
  }

  return { archived, removed };
}

/**
 * Drafted jobs with resume + cover PDFs on disk but never promoted (e.g. manual draft scripts).
 * Promotes them to Backlog so they leave the scout queue.
 */
export function reconcileDraftedJobsWithAssets(): string[] {
  const rows = db.prepare(
    "SELECT id, company, score, summary FROM jobs WHERE status = 'Drafted'",
  ).all() as { id: string; company: string; score: number | null; summary: string | null }[];

  const promoted: string[] = [];
  for (const row of rows) {
    const folder = resolveCompanyFolder(row.company, SUBMISSION_DIR);
    if (!hasResumeAndCoverPdfs(folder)) continue;

    const scoreRow = db.prepare(
      'SELECT score_total FROM job_scores WHERE job_id = ? AND is_latest = 1',
    ).get(row.id) as { score_total: number } | undefined;

    const score = row.score ?? scoreRow?.score_total ?? null;
    const summary =
      row.summary?.trim() ||
      `Ready to apply — ${row.company} (assets on disk; promoted from Drafted queue).`;

    db.prepare(`
      UPDATE jobs
      SET status = 'Backlog',
          score = COALESCE(?, score),
          summary = ?,
          retry_count = 0
      WHERE id = ?
    `).run(score, summary, row.id);

    promoted.push(row.company);
    logActivity(
      'INFO',
      'System',
      `Promoted "${row.company}" from Drafted to Backlog (resume + cover PDFs on disk).`,
    );
  }
  return promoted;
}

function titleCaseFromSlug(folderName: string): string {
  return folderName
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

/**
 * Real rubric fit score for a submission folder, read from stage0_fit_gate.json
 * (written by scripts/build_stage0_fit_gate.py's CR-093 evidence-scale wiring).
 * Returns null when the folder has no gate file, an older gate file predating
 * that wiring, or the LLM-backed rubric call failed for this JD -- callers
 * must treat null as "unscored," never substitute a guessed number for it.
 */
function readStage0FitScore(folderPath: string): number | null {
  try {
    const raw = fs.readFileSync(path.join(folderPath, 'stage0_fit_gate.json'), 'utf8');
    const parsed = JSON.parse(raw);
    return typeof parsed.fit_score === 'number' ? parsed.fit_score : null;
  } catch {
    return null;
  }
}

/**
 * Sync jobs.score from each active submission folder's stage0_fit_gate.json (CR-093
 * evidence-scale engine) for jobs rows that already existed before Stage 0 ran --
 * the common case, since Scout creates the jobs row first and Stage 0 fit-gates a
 * folder afterward. Added 2026-08-20: readStage0FitScore() already existed and was
 * wired into reconcileOrphanSubmissionFolders() below, but that only covers the
 * narrow case of a folder with no matching jobs row yet. Every other job -- the
 * mainstream case -- kept whatever score (or null) it had from before its writer
 * (batch_pipeline.py's evaluate_job_fit/process_single/process_batch) was deleted
 * this session, so the UI's "Fit Score" badges were silently going dark for any job
 * scouted after CR-093. This closes that gap using the same read path, not a new one.
 */
export function reconcileStage0FitScores(): string[] {
  if (!fs.existsSync(SUBMISSION_DIR)) return [];

  const updated: string[] = [];
  for (const folderName of fs.readdirSync(SUBMISSION_DIR)) {
    const activePath = path.join(SUBMISSION_DIR, folderName);
    if (!fs.statSync(activePath).isDirectory()) continue;

    const freshScore = readStage0FitScore(activePath);
    if (freshScore === null) continue;

    for (const job of findJobsForFolder(folderName)) {
      const result = db
        .prepare('UPDATE jobs SET score = ? WHERE LOWER(company) = LOWER(?) AND (score IS NULL OR score != ?)')
        .run(freshScore, job.company, freshScore);
      if (result.changes > 0) updated.push(job.company);
    }
  }
  return updated;
}

function readJdMeta(folderPath: string): { title: string; url: string; jdText: string } {
  const jdPath = path.join(folderPath, 'Original_JD.txt');
  let jdText = '';
  try {
    jdText = fs.readFileSync(jdPath, 'utf8');
  } catch {
    return { title: '', url: '', jdText: '' };
  }

  const lines = jdText.replace(/^\uFEFF/, '').split(/\r?\n/);
  let url = '';
  let start = 0;
  if (lines[0]?.toLowerCase().startsWith('url:')) {
    url = lines[0].slice(4).trim();
    start = 1;
  }

  let title = '';
  const junkExact = new Set([
    'the role',
    'the position',
    'the opportunity',
    'about the role',
    'about your role',
    'job summary',
    'job description',
    'job overview',
    'overview',
    'responsibilities',
    'requirements',
    'qualifications',
    'who we are',
    'about us',
    'register here',
    'register here!',
    'apply here',
    'apply here!',
    'apply now',
    'apply now!',
    'click here',
    'click here!',
    'please apply here',
    'join our team',
    'join us',
  ]);
  const junkRe =
    /^(?:the\s+)?(?:role|position|opportunity)\s*!?\s*$|^(?:register|apply|click|sign\s*up)\s+here\b|^(?:please\s+)?apply\b|^job\s+(?:summary|description|overview)\b|^what\s+you(?:'|')?ll?\s+(?:do|be\s+doing|need|bring)\b|^who\s+(?:we\s+are|you\s+are)\b|^join\s+(?:our\s+)?(?:team|us)\b/i;
  const sloganRe =
    /\b(?:by\s+becoming|join\s+(?:our\s+)?(?:team|us)\s+as|we(?:'|')?re\s+(?:looking|seeking|hiring)|(?:looking|seeking|hiring)\s+for\s+(?:a|an|our)|create\s+the\s+future|together\s+with\s+us|opportunity\s+to\s+(?:join|become)|come\s+join|excited\s+to\s+(?:announce|share))\b/i;
  const qualLineRe =
    /^(?:proven|strong|excellent|demonstrated|ability\s+to|experience\s+(?:with|in|and)|minimum\s+of|bachelor|master|years?\s+of\s+experience|\d+\+?\s+years?)\b/i;
  const roleWordRe =
    /\b(?:manager|owner|director|pm)\b|\b(?:product|technical|platform|team|group)\s+lead\b|\blead\s+(?:product|technical|platform)\b/i;
  const pmRoleRe =
    /\b(?:senior\s+|staff\s+)?(?:technical\s+|platform\s+)?product\s+(?:manager|owner)\b/i;

  const isImplausibleTitle = (value: string): boolean => {
    const t = value.trim();
    if (!t || t.length > 120) return true;
    const low = t.toLowerCase();
    if (junkExact.has(low)) return true;
    if (junkRe.test(t)) return true;
    if (sloganRe.test(t)) return true;
    if (qualLineRe.test(t)) return true;
    if (t.split(/\s+/).length > 10) return true;
    if (t.endsWith('!') && !roleWordRe.test(t)) return true;
    return false;
  };

  const embeddedPm = (text: string): string => {
    const m = text.match(pmRoleRe);
    return m ? m[0].replace(/\s+/g, ' ').trim() : '';
  };

  const titleFromUrl = (rawUrl: string): string => {
    if (!rawUrl) return '';
    const workday = rawUrl.match(
      /\/((?:Senior-|Staff-|Sr-)?(?:Technical-)?Product-(?:Manager|Owner)(?:-[A-Za-z0-9]+)?)(?:_|\/|\?|$)/i,
    );
    if (workday?.[1]) return workday[1].replace(/-/g, ' ').trim();
    const parts = rawUrl.split('?', 1)[0].replace(/\/+$/, '').split('/').filter(Boolean);
    for (let i = parts.length - 1; i >= 0; i--) {
      const part = parts[i];
      if (/^\d+$/.test(part)) continue;
      if (!/product[-_](?:manager|owner)/i.test(part)) continue;
      return part
        .replace(/_/g, '-')
        .split('-')
        .filter(Boolean)
        .map((w) => (['ii', 'iii', 'iv'].includes(w.toLowerCase()) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
        .join(' ');
    }
    return '';
  };

  for (let i = start; i < Math.min(lines.length, start + 40); i++) {
    const line = lines[i]?.trim() || '';
    if (!line) continue;
    const low = line.toLowerCase();
    if (low.startsWith('company:') || low.startsWith('company ') || low.startsWith('position:')) {
      continue;
    }
    if (
      low.startsWith('about ') ||
      low.startsWith('who we') ||
      low.startsWith('overview') ||
      low.startsWith('job description') ||
      low.startsWith('position ')
    ) {
      // Keep scanning — do not treat chrome as a hard stop (LeafLink "About …" then "The Role").
      continue;
    }
    if (line.length >= 120) {
      const embedded = embeddedPm(line);
      if (embedded && !isImplausibleTitle(embedded)) {
        title = embedded;
        break;
      }
      continue;
    }
    if (isImplausibleTitle(line)) {
      const embedded = embeddedPm(line);
      if (embedded && !isImplausibleTitle(embedded)) {
        title = embedded;
        break;
      }
      continue;
    }
    if (line.length < 120 && !line.endsWith('.') && roleWordRe.test(line)) {
      if (line.split(/\s+/).length > 6) {
        const embedded = embeddedPm(line);
        if (embedded && !isImplausibleTitle(embedded)) {
          title = embedded;
          break;
        }
      }
      title = line;
      break;
    }
  }

  if (!title) {
    const body = lines.slice(start).join('\n');
    const embedded = embeddedPm(body);
    if (embedded && !isImplausibleTitle(embedded)) {
      title = embedded;
    }
  }
  if (!title) {
    const fromUrl = titleFromUrl(url);
    if (fromUrl && !isImplausibleTitle(fromUrl)) {
      title = fromUrl;
    }
  }

  return { title, url, jdText: lines.slice(start).join('\n').trim() };
}

/**
 * Submission folders with resume + cover PDFs but no matching jobs row.
 * Manual drafts / external packet drops land here; create Backlog rows so Today/All Jobs show them.
 */
export function reconcileOrphanSubmissionFolders(): string[] {
  if (!fs.existsSync(SUBMISSION_DIR)) return [];

  const created: string[] = [];
  for (const folderName of fs.readdirSync(SUBMISSION_DIR)) {
    const activePath = path.join(SUBMISSION_DIR, folderName);
    if (!fs.statSync(activePath).isDirectory()) continue;
    if (!hasResumeAndCoverPdfs(activePath)) continue;
    if (findJobsForFolder(folderName).length > 0) continue;

    const company = titleCaseFromSlug(folderName);
    const meta = readJdMeta(activePath);
    const title = meta.title || 'Product Manager';
    const id = crypto.randomUUID().replace(/-/g, '').slice(0, 8);
    const summary = `Ready to apply — ${company} (assets on disk; linked from submissions/).`;
    // Real rubric score from Stage 0 (CR-093's evidence-scale scorer), not a
    // guess -- was hardcoded to 80 for every folder here until 2026-08-18
    // (Jason-reported: every Backlog job in the UI showed the same score).
    // Folders authored before that wiring landed, or whose LLM-backed rubric
    // call failed, get null -- the UI should show "unscored," not a fake number.
    const score = readStage0FitScore(activePath);

    // Guard against jobs.url's UNIQUE constraint: a folder can be "orphan" by company-slug match
    // (findJobsForFolder above) while its JD URL already belongs to a differently-named job row --
    // e.g. the same posting scouted once under a mis-captured company name and drafted separately
    // under its real name. That used to throw here and 500 the entire /api/jobs route on every
    // request (found 2026-08-11: realtime_eclinical_solutions vs. an existing "Realtime Software
    // Solutions" row, both the same ADP posting). Skip + log instead of inserting a duplicate.
    if (meta.url) {
      const existing = db.prepare('SELECT id, company FROM jobs WHERE url = ?').get(meta.url) as
        { id: string; company: string } | undefined;
      if (existing) {
        logActivity(
          'WARN',
          'System',
          `Skipped linking orphan folder "${folderName}" as a new job — its JD URL already belongs to job ${existing.id} ("${existing.company}"). Reconcile the company name mismatch manually.`,
        );
        continue;
      }
    }

    db.prepare(`
      INSERT INTO jobs (id, company, title, url, score, status, summary, jd_text, retry_count)
      VALUES (?, ?, ?, ?, ?, 'Backlog', ?, ?, 0)
    `).run(id, company, title, meta.url || null, score, summary, meta.jdText || null);

    created.push(company);
    logActivity(
      'INFO',
      'System',
      `Linked orphan submission folder "${folderName}" as Backlog job ${id} (${company}).`,
    );
  }
  return created;
}

export function jobHasPdfAssets(company: string, status: string): boolean {
  const base = isActivePipelineStatus(status) ? SUBMISSION_DIR : ARCHIVE_DIR;
  const folder = resolveCompanyFolder(company, base);
  if (!fs.existsSync(folder)) return false;
  try {
    return fs.readdirSync(folder).some(f => f.toLowerCase().endsWith('.pdf'));
  } catch {
    return false;
  }
}
