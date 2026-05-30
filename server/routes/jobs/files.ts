import { Router } from 'express';
import fs from 'fs';
import path from 'path';
import AdmZip from 'adm-zip';
import { db, logActivity } from '../../db.js';
import { resolveCompanyFolder, SCRIPTS_DIR, PROJECT_ROOT } from '../../shared.js';
import { formatSkillGapOutput, isValidJobId, runPythonScript } from '../../middleware.js';
import { jobBaseDir } from './shared.js';

const router = Router();

router.get('/api/jobs/:id/files', (req, res) => {
  try {
    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(req.params.id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });
    const folder = resolveCompanyFolder(job.company, jobBaseDir(job.status));
    if (!fs.existsSync(folder)) return res.json({ files: [] });
    const files = fs.readdirSync(folder)
      .filter(f => ['.pdf', '.md', '.txt', '.json'].some(ext => f.endsWith(ext)))
      .map(f => ({ name: f, path: folder }));
    res.json({ files });
  } catch {
    res.status(500).json({ error: 'Failed to list files' });
  }
});

router.get('/api/jobs/:id/files/:filename', (req, res) => {
  try {
    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(req.params.id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });
    const folder       = resolveCompanyFolder(job.company, jobBaseDir(job.status));
    const safeFilename = path.basename(req.params.filename);
    const filePath     = path.join(folder, safeFilename);
    if (!fs.existsSync(filePath)) return res.status(404).json({ error: 'File not found' });
    res.sendFile(filePath);
  } catch {
    res.status(500).json({ error: 'Failed to serve file' });
  }
});

router.get('/api/jobs/:id/skill-gap', async (req, res) => {
  try {
    const { id } = req.params;
    if (!isValidJobId(id)) return res.status(400).json({ success: false, error: 'Invalid job id' });

    const scriptPath = path.join(SCRIPTS_DIR, 'skill_gap.py');
    const dbPath = path.join(PROJECT_ROOT, 'jobagent.sqlite');
    const { code, stdout, stderr } = await runPythonScript([scriptPath, dbPath, id]);

    if (code !== 0) {
      console.error(stderr);
      return res.status(500).json({ success: false, error: 'Failed to analyze skill gap' });
    }

    try {
      const parsed = JSON.parse(stdout.trim());
      const formatted = formatSkillGapOutput(parsed);
      if (!formatted.success) {
        return res.status(404).json(formatted);
      }
      res.json({ success: true, output: formatted.output });
    } catch {
      res.status(500).json({ success: false, error: 'Invalid JSON returned from skill-gap script' });
    }
  } catch (err) {
    console.error(err);
    res.status(500).json({ success: false, error: 'Server error' });
  }
});

router.put('/api/jobs/:id/files/:filename', async (req, res) => {
  try {
    const { id, filename } = req.params;
    const { text } = req.body;
    if (text === undefined) return res.status(400).json({ error: 'Text content is required' });

    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    const folder       = resolveCompanyFolder(job.company, jobBaseDir(job.status));
    const safeFilename = path.basename(filename);
    const filePath     = path.join(folder, safeFilename);
    if (!fs.existsSync(filePath)) return res.status(404).json({ error: 'File not found' });

    if (safeFilename.endsWith('.md') && (safeFilename === 'Resume.md' || safeFilename === 'CoverLetter.md')) {
      const manifestPath = path.join(folder, 'draft_manifest.json');
      if (fs.existsSync(manifestPath)) {
        try {
          const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
          if (manifest.verification_passed !== true) {
            return res.status(400).json({
              error: 'PDF export blocked: draft_manifest verification_passed is not true.',
            });
          }
        } catch {
          return res.status(400).json({ error: 'Invalid draft_manifest.json' });
        }
      }

      const verifyScript = path.join(SCRIPTS_DIR, 'verify_editor_save.py');
      const verified = await runPythonScript([verifyScript, folder, safeFilename], { stdin: text });
      if (verified.code !== 0) {
        const detail = (verified.stdout || verified.stderr || '').trim();
        return res.status(400).json({
          error: detail || 'Editor verification failed (numeric/tone/metrics gate).',
        });
      }
    }

    fs.writeFileSync(filePath, text, 'utf8');

    if (safeFilename.endsWith('.md')) {
      const pdfPath       = path.join(folder, safeFilename.replace('.md', '.pdf'));
      const guardScript   = path.join(SCRIPTS_DIR, 'style_compliance_guard.py');
      const compileScript = path.join(SCRIPTS_DIR, 'compile_single.py');
      const guard = await runPythonScript([guardScript, filePath]);
      if (guard.code !== 0) {
        logActivity('ERROR', 'System', `Style guard failed for "${job.company}": ${guard.stderr}`);
        return res.status(500).json({ error: 'Document saved but validation failed' });
      }
      const compiled = await runPythonScript([compileScript, filePath, pdfPath]);
      if (compiled.code !== 0) {
        logActivity('ERROR', 'System', `PDF compile failed for "${job.company}": ${compiled.stderr}`);
        return res.status(500).json({ error: 'Document saved but PDF compilation failed' });
      }
      logActivity('INFO', 'System', `Successfully validated and compiled PDF for "${job.company}"`);
      return res.json({ success: true, compiled: true });
    }

    res.json({ success: true, compiled: false });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to save file' });
  }
});

router.post('/api/jobs/:id/ai-rewrite', async (req, res) => {
  try {
    const { id } = req.params;
    const { instruction, text } = req.body;
    if (!instruction || !text) return res.status(400).json({ error: 'Instruction and text are required' });

    const scratchDir = path.join(PROJECT_ROOT, 'scratch');
    if (!fs.existsSync(scratchDir)) fs.mkdirSync(scratchDir, { recursive: true });

    const instrFile = path.join(scratchDir, `instr_${id}.tmp`);
    const textFile  = path.join(scratchDir, `text_${id}.tmp`);
    fs.writeFileSync(instrFile, instruction, 'utf8');
    fs.writeFileSync(textFile,  text,        'utf8');

    const { code, stdout, stderr } = await runPythonScript([
      path.join(SCRIPTS_DIR, 'ai_rewrite.py'),
      instrFile,
      textFile,
    ]);

    try {
      if (fs.existsSync(instrFile)) fs.unlinkSync(instrFile);
      if (fs.existsSync(textFile))  fs.unlinkSync(textFile);
    } catch (cleanErr) { console.error('Failed to clean up temp files:', cleanErr); }

    if (code !== 0) {
      console.error(`AI rewrite error: ${stderr}`);
      return res.status(500).json({ error: 'AI rewrite execution failed' });
    }
    res.json({ text: stdout.trim() });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to execute AI rewrite' });
  }
});

router.get('/api/jobs/:id/download-all', (req, res) => {
  try {
    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(req.params.id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });
    const folder = resolveCompanyFolder(job.company, jobBaseDir(job.status));
    if (!fs.existsSync(folder)) return res.status(404).json({ error: 'No files found' });

    const pdfs = fs.readdirSync(folder).filter(f => f.endsWith('.pdf'));
    if (pdfs.length === 0) return res.status(404).json({ error: 'No PDF assets generated yet' });

    const zip           = new AdmZip();
    const zipFolderName = job.company.replace(/[^a-z0-9 ]+/gi, '').trim();
    pdfs.forEach(file => zip.addLocalFile(path.join(folder, file), zipFolderName));

    res.set('Content-Type', 'application/zip');
    res.set('Content-Disposition', `attachment; filename="${path.basename(folder)}_assets.zip"`);
    res.send(zip.toBuffer());
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to create ZIP' });
  }
});

export default router;
