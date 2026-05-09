import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { spawn, exec } from 'child_process';
import { randomUUID } from 'crypto';
import AdmZip from 'adm-zip';
import { db, logActivity } from './db.js';
import { runScoutSync } from './scout.js';
import { TITLE_BLOCKLIST, INDUSTRY_BLOCKLIST_DEFAULT } from './config.js';

// Allowlist of columns that may be updated via the generic PATCH endpoint
const ALLOWED_JOB_FIELDS = new Set([
  'title', 'company', 'url', 'score', 'summary', 'status',
  'salary_range', 'recruiter_name', 'recruiter_url', 'source_site',
  'rejection_stage', 'rejection_type', 'outcome_notes', 'interview_date',
]);

dotenv.config();

// __dirname must be declared first — all path constants depend on it
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORK_EXPERIENCE_PATH = path.join(__dirname, '../data/workExperience.md');
const SUBMISSION_DIR = path.join(__dirname, '../submissions');
const ARCHIVE_DIR = path.join(__dirname, '../archive/submissions');
const CANDIDATE_PREFS_PATH = path.join(__dirname, '../data/candidate_preferences.json');

const DATE_POSTED_TO_DAYS: Record<string, number> = {
  'Past 24 hours': 1,
  'Past 3 days': 3,
  'Past week': 7,
  'Past month': 30,
};

const DEFAULT_JD_KEYWORDS = [
  'saas', 'b2b', 'platform', 'integration', 'enterprise', 'api',
  'product', 'software', 'agile', 'roadmap', 'stakeholder',
];

const DEFAULT_PIPELINE_PREFERENCES = {
  no_people_management: true,
  no_zero_to_one: true,
  structured_team_required: true,
  max_company_size_penalty_threshold: 50,
};

function materializeJobSearchPrefs(jobSearch: any): void {
  let existing: any = {};
  try {
    if (fs.existsSync(CANDIDATE_PREFS_PATH)) {
      existing = JSON.parse(fs.readFileSync(CANDIDATE_PREFS_PATH, 'utf-8'));
    }
  } catch { /* use defaults */ }

  const targetRole: string = jobSearch.targetRole || 'Product Manager';

  // Derive search terms: always include the target role; add "Product Owner" variant for PM roles
  const searchTerms: string[] = [targetRole];
  if (targetRole.toLowerCase().includes('product manager')) searchTerms.push('Product Owner');

  const blockedTitles: string[] = (jobSearch.titleBlocklist || '')
    .split(',').map((s: string) => s.trim()).filter(Boolean);

  const blockedIndustries: string[] = (jobSearch.industryBlocklist || '')
    .split(',').map((s: string) => s.trim()).filter(Boolean);

  const freshnessdays: number = DATE_POSTED_TO_DAYS[jobSearch.datePosted] ?? 7;

  const materialized = {
    target_role: targetRole,
    search_terms: searchTerms,
    location_preference: jobSearch.location || 'United States',
    work_setting: jobSearch.workSetting || 'Remote',
    experience_levels: jobSearch.experienceLevels || [],
    date_posted: jobSearch.datePosted || 'Past week',
    freshness_days: freshnessdays,
    blocked_titles: blockedTitles,
    blocked_industries: blockedIndustries,
    min_salary: jobSearch.minSalary ?? 0,
    min_fit_score: existing.min_fit_score ?? 72,
    jd_required_keywords: existing.jd_required_keywords ?? DEFAULT_JD_KEYWORDS,
    experience_range: existing.experience_range ?? { min: 0, max: 7, total_years_observed: 6 },
    preferences: existing.preferences ?? DEFAULT_PIPELINE_PREFERENCES,
  };

  fs.writeFileSync(CANDIDATE_PREFS_PATH, JSON.stringify(materialized, null, 2), 'utf-8');
}

function resolveCompanyFolder(company: string, baseDir: string): string {
  const companySlug = company.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  const standardPath = path.join(baseDir, companySlug);
  if (fs.existsSync(standardPath)) return standardPath;

  const withTrailing = company.toLowerCase().replace(/[^a-z0-9]+/g, '_');
  const trailingPath = path.join(baseDir, withTrailing);
  if (fs.existsSync(trailingPath)) return trailingPath;

  const simpleReplace = company.toLowerCase().replace(/ /g, '_');
  const pathSimple = path.join(baseDir, simpleReplace);
  if (fs.existsSync(pathSimple)) return pathSimple;

  try {
    const strippedTarget = company.toLowerCase().replace(/[^a-z0-9]/g, '');
    const dirs = fs.readdirSync(baseDir);
    for (const d of dirs) {
      if (d.toLowerCase().replace(/[^a-z0-9]/g, '') === strippedTarget) {
        return path.join(baseDir, d);
      }
    }
  } catch (e) {}

  return standardPath; // fallback
}

// Ensure archive dir exists on boot
if (!fs.existsSync(ARCHIVE_DIR)) {
  fs.mkdirSync(ARCHIVE_DIR, { recursive: true });
}

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// ---------------------------------------------------------------------------
// System Status
// ---------------------------------------------------------------------------
app.get('/api/system-status', (_req, res) => {
  try {
    const status = db.prepare('SELECT * FROM system_status WHERE id = ?').get('global');
    res.json(status || { status: 'idle', current_item: 'No active pipeline run' });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch system status' });
  }
});

app.post('/api/system-status', (req, res) => {
  try {
    const { status, current_item, items_completed, items_total } = req.body;
    db.prepare(`
      UPDATE system_status
      SET status = COALESCE(?, status),
          current_item = COALESCE(?, current_item),
          items_completed = COALESCE(?, items_completed),
          items_total = COALESCE(?, items_total),
          updated_at = CURRENT_TIMESTAMP
      WHERE id = 'global'
    `).run(status || null, current_item || null, items_completed ?? null, items_total ?? null);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: 'Failed to update system status' });
  }
});

// ---------------------------------------------------------------------------
// ATS Pipeline
// ---------------------------------------------------------------------------
app.get('/api/ats-pipeline', (_req, res) => {
  try {
    const pipelinePath = path.join(__dirname, '../career-ops-main/data/pipeline.md');
    if (!fs.existsSync(pipelinePath)) {
      return res.json({ jobs: [] });
    }
    const content = fs.readFileSync(pipelinePath, 'utf-8');
    const lines = content.split('\n').filter(l => l.startsWith('- [ ]'));
    const jobs = lines.map(l => {
      const parts = l.replace('- [ ]', '').trim().split('|').map(s => s.trim());
      return {
        url: parts[0] || '',
        company: parts[1] || 'Unknown',
        title: parts[2] || 'Product Role'
      };
    });
    res.json({ jobs });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch ATS pipeline' });
  }
});

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
app.get('/api/config', (_req, res) => {
  res.json({ titleBlocklist: TITLE_BLOCKLIST, industryBlocklist: INDUSTRY_BLOCKLIST_DEFAULT });
});

// ---------------------------------------------------------------------------
// Activity logs
// ---------------------------------------------------------------------------
app.get('/api/logs', (req, res) => {
  try {
    const q = req.query.q as string;
    if (q) {
      const logs = db.prepare('SELECT * FROM activity_log WHERE message LIKE ? OR source LIKE ? ORDER BY timestamp DESC LIMIT 50').all(`%${q}%`, `%${q}%`);
      return res.json(logs);
    }
    const logs = db.prepare('SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT 100').all();
    res.json(logs);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch logs' });
  }
});

// ---------------------------------------------------------------------------
// Jobs
// ---------------------------------------------------------------------------
app.get('/api/jobs', (_req, res) => {
  try {
    const jobs = db.prepare('SELECT * FROM jobs ORDER BY created_at DESC').all() as any[];
    
    // Enrich jobs with has_assets flag
    const enrichedJobs = jobs.map(job => {
      let has_assets = false;
      const activePath = resolveCompanyFolder(job.company, SUBMISSION_DIR);
      
      if (fs.existsSync(activePath)) {
        try {
          const files = fs.readdirSync(activePath);
          has_assets = files.some(file => file.toLowerCase().endsWith('.pdf'));
        } catch (e) {
          // Directory might be inaccessible
        }
      }
      return { ...job, has_assets };
    });
    
    res.json(enrichedJobs);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch jobs' });
  }
});

// API: Add a new job manually
app.post('/api/jobs', (req, res) => {
  try {
    const { id, company, title, url, score, summary, status } = req.body;
    if (!company || !title) return res.status(400).json({ error: 'company and title are required' });

    db.prepare(`
      INSERT INTO jobs (id, company, title, url, score, status, summary, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    `).run(id || randomUUID(), company, title, url || null, score || null, status || 'Drafted', summary || null);

    logActivity('INFO', 'System', `Manually added job "${company}" to drafted.`);
    res.json({ success: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to add job' });
  }
});

// API: Get job statistics for analytics
app.get('/api/jobs/stats', (_req, res) => {
  try {
    const total = db.prepare('SELECT COUNT(*) as count FROM jobs').get() as any;
    const byStatus = db.prepare('SELECT status, COUNT(*) as count FROM jobs GROUP BY status').all();
    const byRejectionStage = db.prepare("SELECT rejection_stage, COUNT(*) as count FROM jobs WHERE status = 'Closed' GROUP BY rejection_stage").all();
    const byRejectionType = db.prepare("SELECT rejection_type, COUNT(*) as count FROM jobs WHERE status = 'Closed' GROUP BY rejection_type").all();

    res.json({
      total: total.count,
      byStatus,
      byRejectionStage,
      byRejectionType
    });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch stats' });
  }
});

// API: Update Job Status + physically move submission folder
app.patch('/api/jobs/:id/status', (req, res) => {
  try {
    const { id } = req.params;
    const { status } = req.body;

    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    const companySlug = job.company.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    const activePath = path.join(SUBMISSION_DIR, companySlug);
    const archivePath = path.join(ARCHIVE_DIR, companySlug);

    if (status === 'No Longer Available') {
      const fullJob = db.prepare('SELECT company, title, url FROM jobs WHERE id = ?').get(id) as any;
      if (fullJob && fullJob.url) {
        db.prepare('INSERT OR IGNORE INTO stale_jobs (url, company, title) VALUES (?, ?, ?)')
          .run(fullJob.url, fullJob.company, fullJob.title);
      }
      
      if (fs.existsSync(activePath)) {
        fs.rmSync(activePath, { recursive: true, force: true });
      }
      if (fs.existsSync(archivePath)) {
        fs.rmSync(archivePath, { recursive: true, force: true });
      }

      db.prepare('DELETE FROM jobs WHERE id = ?').run(id);
      logActivity('INFO', 'System', `Job "${job.company}" marked No Longer Available and completely deleted.`);
      return res.json({ success: true, deleted: true });
    }

    // "Backlog" and "Drafted" are considered active workspace — everything else is archived
    const isNowArchived = !['Backlog', 'Drafted'].includes(status);
    const wasArchived = !['Backlog', 'Drafted'].includes(job.status);

    if (isNowArchived && !wasArchived && fs.existsSync(activePath)) {
      fs.renameSync(activePath, archivePath);
    } else if (!isNowArchived && wasArchived && fs.existsSync(archivePath)) {
      fs.renameSync(archivePath, activePath);
    }

    db.prepare(`
      UPDATE jobs 
      SET status = ?, 
          rejection_stage = COALESCE(?, rejection_stage),
          rejection_type = COALESCE(?, rejection_type),
          outcome_notes = COALESCE(?, outcome_notes)
      WHERE id = ?
    `).run(
      status, 
      status === 'Closed' ? (req.body.rejection_stage || job.status) : null,
      status === 'Closed' ? req.body.rejection_type : null,
      status === 'Closed' ? req.body.outcome_notes : null,
      id
    );
    logActivity('INFO', 'System', `Job "${job.company}" status changed to ${status}`);

    res.json({ success: true, status });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to update job status' });
  }
});

// API: Update Job Details (generic)
app.patch('/api/jobs/:id', (req, res) => {
  try {
    const { id } = req.params;
    const updates = req.body;
    
    // Build dynamic update query — only permit known safe columns (#1 SQL injection prevention)
    const keys = Object.keys(updates).filter(k => k !== 'id' && ALLOWED_JOB_FIELDS.has(k));
    if (keys.length === 0) return res.status(400).json({ error: 'No valid fields to update' });
    
    const setClause = keys.map(k => `${k} = ?`).join(', ');
    const values = keys.map(k => updates[k]);
    
    db.prepare(`UPDATE jobs SET ${setClause} WHERE id = ?`).run(...values, id);
    
    res.json({ success: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to update job details' });
  }
});

// API: List files for a job (from submissions or archive)
app.get('/api/jobs/:id/files', (req, res) => {
  try {
    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(req.params.id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    const baseDir = ['Backlog', 'Drafted'].includes(job.status) ? SUBMISSION_DIR : ARCHIVE_DIR;
    const folderPath = resolveCompanyFolder(job.company, baseDir);

    if (!fs.existsSync(folderPath)) return res.json({ files: [] });

    const files = fs.readdirSync(folderPath)
      .filter(f => ['.pdf', '.md', '.txt', '.json'].some(ext => f.endsWith(ext)))
      .map(f => ({ name: f, path: folderPath }));

    res.json({ files });
  } catch (err) {
    res.status(500).json({ error: 'Failed to list files' });
  }
});

// API: Download/serve a file for a job
app.get('/api/jobs/:id/files/:filename', (req, res) => {
  try {
    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(req.params.id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    const baseDir = ['Backlog', 'Drafted'].includes(job.status) ? SUBMISSION_DIR : ARCHIVE_DIR;
    const folderPath = resolveCompanyFolder(job.company, baseDir);
    // path.basename strips any directory traversal (e.g. ../../etc/passwd → passwd)
    const safeFilename = path.basename(req.params.filename);
    const filePath = path.join(folderPath, safeFilename);

    if (!fs.existsSync(filePath)) return res.status(404).json({ error: 'File not found' });

    res.sendFile(filePath);
  } catch (err) {
    res.status(500).json({ error: 'Failed to serve file' });
  }
});

// API: Save/Update document and re-compile to PDF
app.put('/api/jobs/:id/files/:filename', (req, res) => {
  try {
    const { id, filename } = req.params;
    const { text } = req.body;

    if (text === undefined) return res.status(400).json({ error: 'Text content is required' });

    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    const baseDir = ['Backlog', 'Drafted'].includes(job.status) ? SUBMISSION_DIR : ARCHIVE_DIR;
    const folderPath = resolveCompanyFolder(job.company, baseDir);
    const safeFilename = path.basename(filename);
    const filePath = path.join(folderPath, safeFilename);

    if (!fs.existsSync(filePath)) return res.status(404).json({ error: 'File not found' });

    // Write edited content to Markdown file
    fs.writeFileSync(filePath, text, 'utf8');

    // If it's a markdown file, compile the corresponding PDF automatically
    if (safeFilename.endsWith('.md')) {
      const pdfFilename = safeFilename.replace('.md', '.pdf');
      const pdfPath = path.join(folderPath, pdfFilename);
      
      const guardScript = path.join(__dirname, '../scripts/style_compliance_guard.py');
      const compileScript = path.join(__dirname, '../scripts/compile_single.py');
      
      exec(`python "${guardScript}" "${filePath}" && python "${compileScript}" "${filePath}" "${pdfPath}"`, (error, stdout, stderr) => {
        if (error) {
          console.error(`Compilation error: ${stderr || error.message}`);
          logActivity('ERROR', 'System', `Failed to validate and compile PDF for "${job.company}": ${stderr || error.message}`);
          return res.status(500).json({ error: 'Document saved but validation or compilation failed' });
        }
        logActivity('INFO', 'System', `Successfully validated and compiled PDF for "${job.company}"`);
        res.json({ success: true, compiled: true });
      });
    } else {
      res.json({ success: true, compiled: false });
    }
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to save file' });
  }
});

// API: Process AI-Assisted document edit via Python GenAI helper
app.post('/api/jobs/:id/ai-rewrite', (req, res) => {
  try {
    const { id } = req.params;
    const { instruction, text } = req.body;

    if (!instruction || !text) return res.status(400).json({ error: 'Instruction and text are required' });

    // Define temp paths in the scratch/ folder
    const scratchDir = path.join(__dirname, '../scratch');
    if (!fs.existsSync(scratchDir)) {
      fs.mkdirSync(scratchDir, { recursive: true });
    }

    const instrFile = path.join(scratchDir, `instr_${id}.tmp`);
    const textFile = path.join(scratchDir, `text_${id}.tmp`);

    // Write contents to temporary files
    fs.writeFileSync(instrFile, instruction, 'utf8');
    fs.writeFileSync(textFile, text, 'utf8');

    const rewriteScript = path.join(__dirname, '../scripts/ai_rewrite.py');

    exec(`python "${rewriteScript}" "${instrFile}" "${textFile}"`, (error, stdout, stderr) => {
      // Clean up temp files in the background
      try {
        if (fs.existsSync(instrFile)) fs.unlinkSync(instrFile);
        if (fs.existsSync(textFile)) fs.unlinkSync(textFile);
      } catch (cleanErr) {
        console.error('Failed to clean up temp files:', cleanErr);
      }

      if (error) {
        console.error(`AI rewrite error: ${stderr || error.message}`);
        return res.status(500).json({ error: 'AI rewrite execution failed' });
      }

      res.json({ text: stdout.trim() });
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to execute AI rewrite' });
  }
});

// API: Download all PDFs as a ZIP
app.get('/api/jobs/:id/download-all', (req, res) => {
  try {
    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(req.params.id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    const baseDir = ['Backlog', 'Drafted'].includes(job.status) ? SUBMISSION_DIR : ARCHIVE_DIR;
    const folderPath = resolveCompanyFolder(job.company, baseDir);

    if (!fs.existsSync(folderPath)) return res.status(404).json({ error: 'No files found' });

    const zip = new AdmZip();
    const files = fs.readdirSync(folderPath).filter(f => f.endsWith('.pdf'));

    if (files.length === 0) return res.status(404).json({ error: 'No PDF assets generated yet' });

    // Place files inside a folder named after the company for easier browsing
    const zipFolderName = job.company.replace(/[^a-z0-9 ]+/gi, '').trim();
    files.forEach(file => {
      zip.addLocalFile(path.join(folderPath, file), zipFolderName);
    });

    const companySlug = path.basename(folderPath);
    const zipName = `${companySlug}_assets.zip`;
    const buffer = zip.toBuffer();

    res.set('Content-Type', 'application/zip');
    res.set('Content-Disposition', `attachment; filename="${zipName}"`);
    res.send(buffer);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to create ZIP' });
  }
});

// ---------------------------------------------------------------------------
// Pipeline: Run drafting engine for a single JD
// ---------------------------------------------------------------------------
app.post('/api/evaluate', (req, res) => {
  const { company, jd, url } = req.body;
  if (!company || !jd) return res.status(400).json({ error: 'company and jd are required' });

  db.prepare(`UPDATE system_status SET status = 'drafting', current_item = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run(`Generating tailored assets for ${company}`);

  // Set up SSE stream
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  const send = (event: string, data: object) => {
    res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  };

  const scriptPath = path.join(__dirname, '../scripts/batch_pipeline.py');

  send('stage', { id: 'gate', status: 'running' });

  const proc = spawn('python', [scriptPath, '--company', company, '--url', url || '', '--mode', 'single'], {
    cwd: path.join(__dirname, '..'),
    env: { ...process.env }
  });

  proc.stdin.write(jd);
  proc.stdin.end();

  let buffer = '';
  proc.stdout.on('data', (chunk: Buffer) => {
    buffer += chunk.toString();
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const parsed = JSON.parse(line);
        send('stage', parsed);
      } catch {
        // raw log line — forward as info
        send('log', { message: line.trim() });
      }
    }
  });

  proc.stderr.on('data', (chunk: Buffer) => {
    send('log', { level: 'error', message: chunk.toString().trim() });
  });

  proc.on('close', (code: number) => {
    send('done', { exitCode: code, passed: code === 0 });
    res.end();
    logActivity(code === 0 ? 'INFO' : 'ERROR', 'Pipeline', `Evaluation for "${company}" exited with code ${code}`);
    db.prepare(`UPDATE system_status SET status = 'completed', current_item = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run(`Completed asset generation for ${company}`);
  });
});

app.post('/api/jobs/:id/draft', (req, res) => {
  try {
    const { id } = req.params;
    const job = db.prepare('SELECT company, url FROM jobs WHERE id = ?').get(id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    db.prepare(`UPDATE system_status SET status = 'drafting', current_item = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run(`Generating tailored assets for ${job.company}`);
    logActivity('INFO', 'Pipeline', `Manual asset generation triggered for "${job.company}"`);

    const scriptPath = path.join(__dirname, '../scripts/batch_pipeline.py');
    const proc = spawn('python', [scriptPath, '--company', job.company, '--url', job.url || '', '--mode', 'single'], {
      cwd: path.join(__dirname, '..'),
      env: { ...process.env }
    });

    proc.stdin.write('');
    proc.stdin.end();

    proc.stdout.on('data', (data) => {
      const output = data.toString().trim();
      if (output) {
        try {
          const parsed = JSON.parse(output);
          if (parsed.summary) {
            logActivity('INFO', 'Pipeline', `[Draft] ${parsed.summary}`);
          }
        } catch {
          logActivity('INFO', 'Pipeline', `[Draft] ${output}`);
        }
      }
    });

    proc.stderr.on('data', (data) => {
      const errOutput = data.toString().trim();
      if (errOutput && !errOutput.includes('UserWarning')) {
        logActivity('ERROR', 'Pipeline', `[Draft Error] ${errOutput}`);
      }
    });

    proc.on('close', (code) => {
      logActivity(code === 0 ? 'INFO' : 'ERROR', 'Pipeline', `Evaluation for "${job.company}" exited with code ${code}`);
      db.prepare(`UPDATE system_status SET status = 'completed', current_item = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run(`Completed asset generation for ${job.company}`);
    });

    res.json({ success: true, message: `Drafting started for ${job.company}` });
  } catch (err) {
    res.status(500).json({ error: 'Failed to start drafting' });
  }
});

// ---------------------------------------------------------------------------
// Profile — job_search has dedicated POST to also materialize candidate_preferences.json
// ---------------------------------------------------------------------------
app.post('/api/profile/job_search', (req, res) => {
  try {
    const value = JSON.stringify(req.body);
    db.prepare('INSERT OR REPLACE INTO profiles (key, value) VALUES (?, ?)').run('job_search', value);
    materializeJobSearchPrefs(req.body);
    logActivity('INFO', 'System', 'Job search settings saved and candidate_preferences.json updated.');
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: 'Failed to save job search settings' });
  }
});

app.get('/api/profile/:key', (req, res) => {
  try {
    const row = db.prepare('SELECT value FROM profiles WHERE key = ?').get(req.params.key) as any;
    res.json(row ? JSON.parse(row.value) : {});
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch profile' });
  }
});

app.post('/api/profile/:key', (req, res) => {
  try {
    const value = JSON.stringify(req.body);
    db.prepare('INSERT OR REPLACE INTO profiles (key, value) VALUES (?, ?)').run(req.params.key, value);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: 'Failed to update profile' });
  }
});

// ---------------------------------------------------------------------------
// Work Experience
// ---------------------------------------------------------------------------
function codifyExperienceAndAssignIDs(markdown: string): string {
  const lines = markdown.split('\n');
  let inVocabularyTable = false;
  let inMetricsTable = false;
  let currentSection = ''; // '5.1', '5.2', '5.3', etc.

  // Dynamic per-section ACC counters: section key → next ID
  // Section 5.N maps to range N*100+1 through (N+1)*100
  const sectionCounters = new Map<string, number>();
  let nextVocId = 1;
  let nextMetId = 1;

  // Scan existing IDs to seed counters above existing maxima
  lines.forEach(line => {
    const vocMatch = line.match(/\*\*VOC-(\d+)\*\*/i);
    if (vocMatch) {
      const num = parseInt(vocMatch[1], 10);
      if (num >= nextVocId) nextVocId = num + 1;
    }
    const metMatch = line.match(/\*\*MET-(\d+)\*\*/i);
    if (metMatch) {
      const num = parseInt(metMatch[1], 10);
      if (num >= nextMetId) nextMetId = num + 1;
    }
    const accMatch = line.match(/ACC-(\d+)/i);
    if (accMatch) {
      const num = parseInt(accMatch[1], 10);
      if (num >= 101) {
        // Derive which section this belongs to: 101-199 → 5.1, 201-299 → 5.2, etc.
        const sectionIdx = Math.floor((num - 1) / 100);
        const secKey = `5.${sectionIdx}`;
        const rangeBase = sectionIdx * 100 + 1;
        const prev = sectionCounters.get(secKey) ?? rangeBase;
        if (num >= prev) sectionCounters.set(secKey, num + 1);
      }
    }
  });

  const processedLines = lines.map(line => {
    const trimmed = line.trim();

    // Table section markers
    if (trimmed.startsWith('## Section 3:')) { inVocabularyTable = true; inMetricsTable = false; }
    else if (trimmed.startsWith('## Section 4:')) { inVocabularyTable = false; inMetricsTable = true; }
    else if (trimmed.startsWith('## Section 5:')) { inVocabularyTable = false; inMetricsTable = false; }
    else if (trimmed.startsWith('## Section 6:')) { inVocabularyTable = false; inMetricsTable = false; currentSection = ''; }

    // Detect any ### 5.N subsection dynamically
    const subMatch = trimmed.match(/^### (5\.\d+)/);
    if (subMatch) { inVocabularyTable = false; inMetricsTable = false; currentSection = subMatch[1]; }

    // Vocabulary table rows
    if (inVocabularyTable && trimmed.startsWith('|') && !trimmed.includes('Fact ID') && !trimmed.includes(':---')) {
      const cells = line.split('|').map(c => c.trim());
      if (cells.length >= 2 && cells[1] === '') {
        cells[1] = `**VOC-${String(nextVocId++).padStart(2, '0')}**`;
        return cells.join(' | ').trim();
      }
    }

    // Metrics table rows
    if (inMetricsTable && trimmed.startsWith('|') && !trimmed.includes('Fact ID') && !trimmed.includes(':---')) {
      const cells = line.split('|').map(c => c.trim());
      if (cells.length >= 2 && cells[1] === '') {
        cells[1] = `**MET-${String(nextMetId++).padStart(2, '0')}**`;
        return cells.join(' | ').trim();
      }
    }

    // Accomplishment bullets inside a 5.N subsection
    if (
      currentSection &&
      trimmed.startsWith('*') &&
      !trimmed.includes('DO NOT claim') &&
      !trimmed.includes('*   **Context & Constraints**') &&
      !trimmed.includes('*   **Owned Systems**') &&
      !trimmed.includes('*   **Unowned Systems**')
    ) {
      const content = trimmed.replace(/^\*\s*/, '').trim();
      if (content.startsWith('**') && !content.includes('[ACC-')) {
        const sectionIdx = parseInt(currentSection.split('.')[1], 10);
        const rangeBase = sectionIdx * 100 + 1;
        const nextId = sectionCounters.get(currentSection) ?? rangeBase;
        sectionCounters.set(currentSection, nextId + 1);
        const newContent = content.replace(/^\*\*([^*]+)\*\*/, `**[ACC-${nextId}] $1**`);
        return `*   ${newContent}`;
      }
    }

    return line;
  });

  return processedLines.join('\n');
}

app.get('/api/experience', (_req, res) => {
  try {
    if (!fs.existsSync(WORK_EXPERIENCE_PATH)) {
      return res.json({ content: '# Work Experience\n\nNo data found.' });
    }
    res.json({ content: fs.readFileSync(WORK_EXPERIENCE_PATH, 'utf-8') });
  } catch (err) {
    res.status(500).json({ error: 'Failed to read experience file' });
  }
});

app.post('/api/experience', (req, res) => {
  try {
    const { content } = req.body;
    const codifiedContent = codifyExperienceAndAssignIDs(content);
    fs.writeFileSync(WORK_EXPERIENCE_PATH, codifiedContent, 'utf-8');
    logActivity('INFO', 'System', 'workExperience.md updated and automatically codified under SDD with sequential IDs by user.');
    res.json({ success: true, content: codifiedContent });
  } catch (err) {
    res.status(500).json({ error: 'Failed to save experience file' });
  }
});

// ---------------------------------------------------------------------------
// Scout
// ---------------------------------------------------------------------------
app.post('/api/sync', (_req, res) => {
  runScoutSync();
  res.json({ message: 'Sync started' });
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
app.listen(PORT, () => {
  console.log(`\n${'='.repeat(48)}`);
  console.log(`  JobAgent Server  →  http://localhost:${PORT}`);
  console.log(`${'='.repeat(48)}\n`);
  logActivity('INFO', 'Server', 'System initialized. Ready for syncing.');
});
