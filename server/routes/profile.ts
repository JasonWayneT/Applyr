import { Router } from 'express';
import fs from 'fs';
import { spawn } from 'child_process';
import { db, logActivity } from '../db.js';
import {
  buildPythonEnv, materializeJobSearchPrefs,
  WORK_EXPERIENCE_PATH, PROJECT_ROOT,
} from '../shared.js';

const router = Router();

// ---------------------------------------------------------------------------
// Proof-code assignment for workExperience.md (Implements SDD anti-hallucination contract)
// Scans existing IDs before assigning new ones so re-saves never collide or renumber.
// ---------------------------------------------------------------------------
function codifyExperienceAndAssignIDs(markdown: string): string {
  const lines = markdown.split('\n');
  let inVocabularyTable = false;
  let inMetricsTable    = false;
  let currentSection    = '';

  const sectionCounters = new Map<string, number>();
  let nextVocId = 1;
  let nextMetId = 1;

  lines.forEach(line => {
    const vocMatch = line.match(/\*\*VOC-(\d+)\*\*/i);
    if (vocMatch) { const n = parseInt(vocMatch[1], 10); if (n >= nextVocId) nextVocId = n + 1; }
    const metMatch = line.match(/\*\*MET-(\d+)\*\*/i);
    if (metMatch) { const n = parseInt(metMatch[1], 10); if (n >= nextMetId) nextMetId = n + 1; }
    const accMatch = line.match(/ACC-(\d+)/i);
    if (accMatch) {
      const n = parseInt(accMatch[1], 10);
      if (n >= 101) {
        const sectionIdx = Math.floor((n - 1) / 100);
        const secKey     = `5.${sectionIdx}`;
        const rangeBase  = sectionIdx * 100 + 1;
        const prev       = sectionCounters.get(secKey) ?? rangeBase;
        if (n >= prev) sectionCounters.set(secKey, n + 1);
      }
    }
  });

  return lines.map(line => {
    const trimmed = line.trim();

    if      (trimmed.startsWith('## Section 3:')) { inVocabularyTable = true;  inMetricsTable = false; }
    else if (trimmed.startsWith('## Section 4:')) { inVocabularyTable = false; inMetricsTable = true;  }
    else if (trimmed.startsWith('## Section 5:')) { inVocabularyTable = false; inMetricsTable = false; }
    else if (trimmed.startsWith('## Section 6:')) { inVocabularyTable = false; inMetricsTable = false; currentSection = ''; }

    const subMatch = trimmed.match(/^### (5\.\d+)/);
    if (subMatch) { inVocabularyTable = false; inMetricsTable = false; currentSection = subMatch[1]; }

    if (inVocabularyTable && trimmed.startsWith('|') && !trimmed.includes('Fact ID') && !trimmed.includes(':---')) {
      const cells = line.split('|').map(c => c.trim());
      if (cells.length >= 2 && cells[1] === '') {
        cells[1] = `**VOC-${String(nextVocId++).padStart(2, '0')}**`;
        return cells.join(' | ').trim();
      }
    }

    if (inMetricsTable && trimmed.startsWith('|') && !trimmed.includes('Fact ID') && !trimmed.includes(':---')) {
      const cells = line.split('|').map(c => c.trim());
      if (cells.length >= 2 && cells[1] === '') {
        cells[1] = `**MET-${String(nextMetId++).padStart(2, '0')}**`;
        return cells.join(' | ').trim();
      }
    }

    if (
      currentSection &&
      trimmed.startsWith('*') &&
      !trimmed.includes('DO NOT claim') &&
      !trimmed.includes('*   **Context & Constraints**') &&
      !trimmed.includes('*   **Owned Systems**') &&
      !trimmed.includes('*   **Unowned Systems**')
    ) {
      const content = trimmed.replace(/^\*\s*/, '').trim();
      if (content.startsWith('**') && !content.includes('[ACC-') && !content.includes('[RETIRED-ACC-')) {
        const sectionIdx = parseInt(currentSection.split('.')[1], 10);
        const rangeBase  = sectionIdx * 100 + 1;
        const nextId     = sectionCounters.get(currentSection) ?? rangeBase;
        sectionCounters.set(currentSection, nextId + 1);
        return `*   ${content.replace(/^\*\*([^*]+)\*\*/, `**[ACC-${nextId}] $1**`)}`;
      }
    }

    return line;
  }).join('\n');
}

// ---------------------------------------------------------------------------
// Profile routes
// ---------------------------------------------------------------------------

// Specific key route must be registered before /:key to avoid param capture
router.post('/api/profile/job_search', (req, res) => {
  try {
    db.prepare('INSERT OR REPLACE INTO profiles (key, value) VALUES (?, ?)').run('job_search', JSON.stringify(req.body));
    materializeJobSearchPrefs(req.body);
    logActivity('INFO', 'System', 'Job search settings saved and candidate_preferences.json updated.');
    res.json({ success: true });
  } catch {
    res.status(500).json({ error: 'Failed to save job search settings' });
  }
});

router.get('/api/profile/:key', (req, res) => {
  try {
    const row = db.prepare('SELECT value FROM profiles WHERE key = ?').get(req.params.key) as any;
    res.json(row ? JSON.parse(row.value) : {});
  } catch {
    res.status(500).json({ error: 'Failed to fetch profile' });
  }
});

router.post('/api/profile/:key', (req, res) => {
  try {
    db.prepare('INSERT OR REPLACE INTO profiles (key, value) VALUES (?, ?)').run(req.params.key, JSON.stringify(req.body));
    res.json({ success: true });
  } catch {
    res.status(500).json({ error: 'Failed to update profile' });
  }
});

// ---------------------------------------------------------------------------
// Work experience
// ---------------------------------------------------------------------------

router.get('/api/experience', (_req, res) => {
  try {
    if (!fs.existsSync(WORK_EXPERIENCE_PATH)) return res.json({ content: '# Work Experience\n\nNo data found.' });
    res.json({ content: fs.readFileSync(WORK_EXPERIENCE_PATH, 'utf-8') });
  } catch {
    res.status(500).json({ error: 'Failed to read experience file' });
  }
});

router.post('/api/experience', (req, res) => {
  try {
    const { content } = req.body;
    const codified = codifyExperienceAndAssignIDs(content);
    fs.writeFileSync(WORK_EXPERIENCE_PATH, codified, 'utf-8');
    logActivity('INFO', 'System', 'workExperience.md updated and automatically codified under SDD with sequential IDs by user.');

    // Implements FR-064: regenerate scoring summary in background — fire and forget
    const summaryProc = spawn('python', ['scripts/generate_experience_summary.py'], {
      cwd: PROJECT_ROOT,
      shell: true,
      env: { ...process.env, ...buildPythonEnv() },
      detached: true,
      stdio: 'ignore',
    });
    summaryProc.unref();
    logActivity('INFO', 'System', 'Regenerating experience scoring summary in background...');

    res.json({ success: true, content: codified });
  } catch {
    res.status(500).json({ error: 'Failed to save experience file' });
  }
});

export default router;
