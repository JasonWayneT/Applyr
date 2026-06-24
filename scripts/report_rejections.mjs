/**
 * Generate rejection breakdown from jobagent.sqlite (no Python required).
 */
import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';

const ROOT = path.resolve(import.meta.dirname, '..');
const DB = path.join(ROOT, 'data/jobagent.sqlite');
const OUT = path.join(ROOT, 'docs', 'reports', 'rejection-analysis-2026-06-02.md');
const SCOUT_LOG = path.join(ROOT, 'logs', 'builtin-scout-run.txt');

const db = new Database(DB, { readonly: true });

function categorize(job) {
  const s = (job.summary || '').toLowerCase();
  const notes = (job.outcome_notes || '').toLowerCase();
  const stage = (job.rejection_stage || '').toLowerCase();
  const text = `${s} ${notes} ${stage}`;

  if (text.includes('duplicate') || text.includes('vector similarity')) return 'duplicate_jd';
  if (text.includes('keyword') || text.includes('title gate') || text.includes('zero-token')) return 'zero_token_gate';
  if (text.includes('on-site') || text.includes('onsite') || text.includes('location')) return 'location_gate';
  if (text.includes('industry')) return 'industry_gate';
  if (text.includes('years') || text.includes('experience') && text.includes('exceeds')) return 'years_gate';
  if (text.includes('below threshold') || text.includes('low fit') || (job.score != null && job.score < 72)) return 'llm_fit_below_threshold';
  if (job.score === 28) return 'llm_fit_score_28';
  if (job.score != null && job.score >= 72) return 'passed_score_but_rejected';
  if (!job.summary && job.score == null) return 'rejected_no_summary';
  if (job.score == null) return 'rejected_null_score';
  return 'other';
}

function titleLooksOffTitle(title) {
  const t = (title || '').toLowerCase();
  const pmSignals = ['product manager', 'product owner', 'platform manager', 'technical product'];
  if (pmSignals.some(p => t.includes(p))) return false;
  const offRole = [
    'engineer', 'developer', 'designer', 'editor', 'sales', 'recruiter',
    'analyst', 'coordinator', 'specialist', 'advisor', 'manager, montreal',
    'talent acquisition', 'collections', 'account manager', 'success manager',
  ];
  return offRole.some(k => t.includes(k));
}

const allRejected = db.prepare(`
  SELECT id, company, title, url, status, score, pre_score, summary, rejection_stage,
         rejection_type, outcome_notes, source_site, jd_text, created_at
  FROM jobs WHERE status = 'Rejected'
  ORDER BY created_at DESC
`).all();

const recentCutoff = new Date('2026-05-25').toISOString().slice(0, 10);
const recent = allRejected.filter(j => (j.created_at || '').slice(0, 10) >= recentCutoff);

const byCategory = {};
for (const j of allRejected) {
  const cat = categorize(j);
  byCategory[cat] = (byCategory[cat] || 0) + 1;
}

const recentByCategory = {};
for (const j of recent) {
  const cat = categorize(j);
  recentByCategory[cat] = (recentByCategory[cat] || 0) + 1;
}

const scoreBuckets = { null: 0, '28': 0, '29-50': 0, '51-71': 0, '72+': 0 };
for (const j of allRejected) {
  if (j.score == null) scoreBuckets.null++;
  else if (j.score === 28) scoreBuckets['28']++;
  else if (j.score <= 50) scoreBuckets['29-50']++;
  else if (j.score <= 71) scoreBuckets['51-71']++;
  else scoreBuckets['72+']++;
}

const bySource = {};
for (const j of recent) {
  const src = j.source_site || '(unknown)';
  bySource[src] = (bySource[src] || 0) + 1;
}

const offTitleRecent = recent.filter(j => titleLooksOffTitle(j.title));
const nullScoreRecent = recent.filter(j => j.score == null);
const score28Recent = recent.filter(j => j.score === 28);

// Scout log [REJECT] lines
let scoutRejects = [];
if (fs.existsSync(SCOUT_LOG)) {
  const log = fs.readFileSync(SCOUT_LOG, 'utf-8');
  scoutRejects = log.split('\n').filter(l => l.includes('[REJECT]'));
  const scoutReasons = {};
  for (const line of scoutRejects) {
    const m = line.match(/\[REJECT\].*?-\s*(.+)$/);
    const reason = m ? m[1].trim() : 'unknown';
    scoutReasons[reason] = (scoutReasons[reason] || 0) + 1;
  }
  var scoutReasonCounts = scoutReasons;
} else {
  var scoutReasonCounts = {};
}

// Sample rows per category (recent)
const samples = {};
for (const j of recent) {
  const cat = categorize(j);
  if (!samples[cat]) samples[cat] = [];
  if (samples[cat].length < 8) samples[cat].push(j);
}

const topSummaries = db.prepare(`
  SELECT summary, COUNT(*) as c FROM jobs
  WHERE status = 'Rejected' AND created_at >= '2026-05-25'
  GROUP BY summary ORDER BY c DESC LIMIT 12
`).all();

const zeroTokenSamples = db.prepare(`
  SELECT company, title, summary, pre_score, source_site FROM jobs
  WHERE status = 'Rejected' AND created_at >= '2026-05-25'
  AND (summary LIKE '%keyword%' OR summary LIKE '%title gate%' OR summary LIKE '%years%')
  LIMIT 10
`).all();

const prefsPath = path.join(ROOT, 'data', 'candidate_preferences.json');
let prefsNote = '(candidate_preferences.json not readable — using defaults from code)';
if (fs.existsSync(prefsPath)) {
  try {
    const p = JSON.parse(fs.readFileSync(prefsPath, 'utf-8'));
    prefsNote = [
      `target_role: ${p.target_role || 'Product Manager'}`,
      `min_fit_score: ${p.min_fit_score ?? 72}`,
      `max_experience_years: ${p.experience_range?.max ?? 7}`,
      `work_setting: ${p.work_setting || 'Remote'}`,
      `search_terms: ${(p.search_terms || []).slice(0, 5).join(', ') || '(default)'}`,
      `blocked_titles (count): ${(p.blocked_titles || []).length}`,
      `blocked_industries (count): ${(p.blocked_industries || []).length}`,
    ].join('\n');
  } catch { /* ignore */ }
}

const lines = [];
lines.push('# Job Rejection Analysis Report');
lines.push('');
lines.push(`**Generated:** 2026-06-02`);
lines.push(`**Database:** \`jobagent.sqlite\``);
lines.push('');
lines.push('## Executive summary');
lines.push('');
lines.push(`Your pipeline has **${allRejected.length} total Rejected** jobs. Since **2026-05-25**, **${recent.length}** new rejections were recorded.`);
lines.push('');
lines.push('**Ready to Apply is empty** because no jobs reached `Backlog` with PDF assets — recent activity is almost entirely rejections at evaluate time, not successful drafts.');
lines.push('');
lines.push('The dominant patterns in recent rejections:');
lines.push('');
const sortedRecent = Object.entries(recentByCategory).sort((a, b) => b[1] - a[1]);
for (const [cat, n] of sortedRecent) {
  lines.push(`- **${cat.replace(/_/g, ' ')}:** ${n}`);
}
lines.push('');
lines.push(`Additionally, **${offTitleRecent.length}** recent rejections have titles that do not look like Product Manager roles (wrong role scraped or weak search targeting).`);
lines.push(`**${score28Recent.length}** recent rows have the recurring LLM score of **28** (typical hard-reject band).`);
lines.push(`**${nullScoreRecent.length}** recent rows have **null score** (often zero-token gate or ingest-only reject before fit scoring).`);
lines.push('');

lines.push('## Top rejection summary strings (recent)');
lines.push('');
lines.push('| Count | Summary (truncated) |');
lines.push('|------:|---------------------|');
for (const r of topSummaries) {
  lines.push(`| ${r.c} | ${(r.summary || '(empty)').replace(/\|/g, '/').slice(0, 90)} |`);
}
lines.push('');

lines.push('## Zero-token gate examples (pre-score can still be high)');
lines.push('');
for (const j of zeroTokenSamples.slice(0, 8)) {
  lines.push(`- **${j.company}** — ${j.title} (pre_score: ${j.pre_score ?? 'null'})`);
  lines.push(`  - ${(j.summary || '').slice(0, 150)}`);
}
lines.push('');

lines.push('## Active candidate preferences');
lines.push('');
lines.push('```');
lines.push(prefsNote);
lines.push('```');
lines.push('');

lines.push('## Rejection funnel (how a job gets rejected)');
lines.push('');
lines.push('```mermaid');
lines.push('flowchart TD');
lines.push('  A[Scout finds job] --> B{Scout gates}');
lines.push('  B -->|title blocklist / geo / industry| R1[Never ingested]');
lines.push('  B -->|pass| C[Saved as New or Drafted]');
lines.push('  C --> D{Zero-token gates}');
lines.push('  D -->|years / keywords / title in JD| R2[Rejected - no LLM score]');
lines.push('  D -->|pass| E[LLM fit scoring]');
lines.push('  E -->|score below 72 or Decision NO| R3[Rejected - score 28 etc]');
lines.push('  E -->|pass| F[Draft assets]');
lines.push('  F --> G[Backlog - Ready to Apply]');
lines.push('```');
lines.push('');

lines.push('## All-time rejection categories (from DB summary/score heuristics)');
lines.push('');
lines.push('| Category | Count |');
lines.push('|----------|------:|');
for (const [cat, n] of Object.entries(byCategory).sort((a, b) => b[1] - a[1])) {
  lines.push(`| ${cat.replace(/_/g, ' ')} | ${n} |`);
}
lines.push('');

lines.push('## Recent rejections since 2026-05-25');
lines.push('');
lines.push('| Category | Count |');
lines.push('|----------|------:|');
for (const [cat, n] of sortedRecent) {
  lines.push(`| ${cat.replace(/_/g, ' ')} | ${n} |`);
}
lines.push('');

lines.push('## Score distribution (all Rejected)');
lines.push('');
lines.push('| Score bucket | Count |');
lines.push('|--------------|------:|');
for (const [k, n] of Object.entries(scoreBuckets)) {
  lines.push(`| ${k} | ${n} |`);
}
lines.push('');
lines.push('> **Note:** Score **28** appears repeatedly when the fit engine hard-rejects (Decision NO). It is a sentinel value, not a nuanced 28/100 fit.');
lines.push('');

lines.push('## Recent rejections by source');
lines.push('');
lines.push('| Source | Count |');
lines.push('|--------|------:|');
for (const [src, n] of Object.entries(bySource).sort((a, b) => b[1] - a[1])) {
  lines.push(`| ${src} | ${n} |`);
}
lines.push('');

if (Object.keys(scoutReasonCounts).length) {
  lines.push('## Scout-stage rejections (from latest Built In scout log)');
  lines.push('');
  lines.push('These jobs were rejected **before ingest** during `scout_local.ts` gates:');
  lines.push('');
  lines.push('| Reason | Count |');
  lines.push('|--------|------:|');
  for (const [r, n] of Object.entries(scoutReasonCounts).sort((a, b) => b[1] - a[1]).slice(0, 15)) {
    lines.push(`| ${r} | ${n} |`);
  }
  lines.push('');
}

lines.push('## Wrong-role titles (recent sample)');
lines.push('');
lines.push('These made it into the DB but are not PM-targeted — search/feed quality issue:');
lines.push('');
lines.push('| Company | Title | Score | Source |');
lines.push('|---------|-------|------:|--------|');
for (const j of offTitleRecent.slice(0, 20)) {
  lines.push(`| ${j.company.slice(0, 40)} | ${j.title.slice(0, 45)} | ${j.score ?? 'null'} | ${j.source_site || '?'} |`);
}
lines.push('');

lines.push('## Representative examples by category');
lines.push('');
for (const [cat, rows] of Object.entries(samples).sort((a, b) => b[1].length - a[1].length)) {
  lines.push(`### ${cat.replace(/_/g, ' ')}`);
  lines.push('');
  for (const j of rows.slice(0, 5)) {
    lines.push(`- **${j.company}** — ${j.title}`);
    lines.push(`  - score: ${j.score ?? 'null'}, pre_score: ${j.pre_score ?? 'null'}, source: ${j.source_site || '?'}`);
    lines.push(`  - summary: ${(j.summary || '(none)').slice(0, 200)}`);
    if (j.url) lines.push(`  - url: ${j.url.slice(0, 100)}`);
  }
  lines.push('');
}

lines.push('## Why this may feel wrong');
lines.push('');
lines.push('1. **High pre-score, still rejected:** Zero-token gates (years required, blocked title words in JD, missing SaaS/platform keywords) run *before* or *instead of* trusting LLM fit. A job can show pre_score 90+ in logs but still reject on `required_years_8_exceeds_max_7`.');
lines.push('2. **Score 28 everywhere:** The fit model uses 28 as a common hard-reject output when Decision=NO — it does not mean "28% match" in a linear sense.');
lines.push('3. **Null scores:** Usually keyword/title/year gates or geographic scout rejects — never reached LLM fit.');
lines.push('4. **Feed pollution:** Non-PM titles (Video Editor, Sales Manager, Collections Specialist) indicate aggregator feeds (Adzuna, Built In broad crawl) are returning off-target roles that gates then kill.');
lines.push('5. **4 Drafted @ score 87 but no Ready to Apply:** Those jobs passed fit historically but asset PDF generation never completed (`submissions/` is empty); they were never promoted to Backlog.');
lines.push('');

lines.push('## Recommended actions');
lines.push('');
lines.push('| Priority | Action | Expected effect |');
lines.push('|----------|--------|-----------------|');
lines.push('| 1 | Tighten scout sources (Built In strict URL already in place; review Adzuna/OpenPostings query terms) | Fewer wrong-role ingestions |');
lines.push('| 2 | Review `max_experience_years` (default 7) if legitimate PM roles require 8–10 years | Fewer `required_years_*_exceeds_max_7` rejects |');
lines.push('| 3 | Review `jd_required_keywords` / signal keywords in preferences | Fewer `no_signal_keywords` rejects |');
lines.push('| 4 | Re-run draft pipeline on the 4 stuck `Drafted` jobs (Jobgether, Global Payments) | Populate Ready to Apply |');
lines.push('| 5 | Inspect fit rubric / `job_fit_rules` if many PM titles still score 28 | Reduce false-negative LLM rejects |');
lines.push('');

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, lines.join('\n'), 'utf-8');
console.log(`Wrote ${OUT}`);
console.log(`Total rejected: ${allRejected.length}, recent: ${recent.length}`);
console.log('Recent categories:', recentByCategory);

db.close();
