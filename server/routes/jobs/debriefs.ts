import { Router } from 'express';
import { db, logActivity } from '../../db.js';
import { isValidJobId } from '../../middleware.js';
import {
  createInterviewDebrief,
  deleteInterviewDebrief,
  getInterviewDebrief,
  listInterviewDebriefs,
  updateInterviewDebrief,
} from '../../repository/interviewDebriefRepository.js';

const router = Router();

function getJobCompany(jobId: string): string | null {
  const row = db.prepare('SELECT company FROM jobs WHERE id = ?').get(jobId) as { company: string } | undefined;
  return row?.company ?? null;
}

function logDebriefSaved(
  jobId: string,
  company: string,
  debriefId: string,
  outcome: string,
  notesLength: number,
  action: 'created' | 'updated',
) {
  logActivity('INFO', 'DebriefLog', `Interview debrief ${action} for "${company}"`, {
    event: 'interview_debrief_saved',
    action,
    job_id: jobId,
    company,
    debrief_id: debriefId,
    outcome,
    notes_length: notesLength,
  });
}

router.get('/api/jobs/:id/debriefs', (req, res) => {
  const { id } = req.params;
  if (!isValidJobId(id)) return res.status(400).json({ error: 'Invalid job id' });
  if (!getJobCompany(id)) return res.status(404).json({ error: 'Job not found' });

  res.json({ debriefs: listInterviewDebriefs(id) });
});

router.post('/api/jobs/:id/debriefs', (req, res) => {
  const { id } = req.params;
  if (!isValidJobId(id)) return res.status(400).json({ error: 'Invalid job id' });

  const company = getJobCompany(id);
  if (!company) return res.status(404).json({ error: 'Job not found' });

  const result = createInterviewDebrief(id, req.body ?? {});
  if ('error' in result) {
    return res.status(400).json({ error: result.error });
  }

  logDebriefSaved(id, company, result.debrief.id, result.debrief.outcome, result.debrief.notes.length, 'created');
  res.status(201).json({ debrief: result.debrief });
});

router.patch('/api/jobs/:id/debriefs/:debriefId', (req, res) => {
  const { id, debriefId } = req.params;
  if (!isValidJobId(id)) return res.status(400).json({ error: 'Invalid job id' });

  const company = getJobCompany(id);
  if (!company) return res.status(404).json({ error: 'Job not found' });

  const result = updateInterviewDebrief(id, debriefId, req.body ?? {});
  if ('error' in result) {
    return res.status(result.notFound ? 404 : 400).json({ error: result.error });
  }

  logDebriefSaved(id, company, result.debrief.id, result.debrief.outcome, result.debrief.notes.length, 'updated');
  res.json({ debrief: result.debrief });
});

router.delete('/api/jobs/:id/debriefs/:debriefId', (req, res) => {
  const { id, debriefId } = req.params;
  if (!isValidJobId(id)) return res.status(400).json({ error: 'Invalid job id' });
  if (!getJobCompany(id)) return res.status(404).json({ error: 'Job not found' });

  const deleted = deleteInterviewDebrief(id, debriefId);
  if (!deleted) return res.status(404).json({ error: 'Debrief not found' });

  res.json({ success: true });
});

export default router;
