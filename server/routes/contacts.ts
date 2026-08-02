import { randomUUID } from 'crypto';
import { Router } from 'express';
import { db } from '../db.js';
import { requireApiToken } from '../middleware.js';

const router = Router();
router.use(requireApiToken);

const CONTACT_TYPES = new Set(['hiring_manager', 'warm_connection', 'informational']);
const CONTACT_STATUSES = new Set(['active', 'responded', 'closed']);

type ContactRow = {
  id: string;
  job_id: string | null;
  company: string;
  contact_name: string;
  contact_title: string | null;
  contact_type: string;
  source: string | null;
  message_sent_at: string;
  status: string;
  next_follow_up_due: string | null;
  last_touch_at: string;
  follow_up_count: number;
  notes: string | null;
  confirmed: number;
  created_at: string;
  updated_at: string;
};

function mapRow(row: ContactRow) {
  return { ...row, confirmed: !!row.confirmed };
}

router.get('/api/contacts', (req, res) => {
  try {
    const { status, contact_type, job_id, confirmed } = req.query;
    const clauses: string[] = [];
    const params: unknown[] = [];

    if (typeof status === 'string') { clauses.push('status = ?'); params.push(status); }
    if (typeof contact_type === 'string') { clauses.push('contact_type = ?'); params.push(contact_type); }
    if (typeof job_id === 'string') { clauses.push('job_id = ?'); params.push(job_id); }
    if (typeof confirmed === 'string') { clauses.push('confirmed = ?'); params.push(confirmed === 'true' || confirmed === '1' ? 1 : 0); }

    const where = clauses.length ? `WHERE ${clauses.join(' AND ')}` : '';
    const rows = db.prepare(`SELECT * FROM contacts ${where} ORDER BY created_at DESC`).all(...params) as ContactRow[];
    res.json({ contacts: rows.map(mapRow) });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to fetch contacts' });
  }
});

router.post('/api/contacts', (req, res) => {
  try {
    const body = req.body ?? {};
    const { company, contact_name, contact_type } = body;
    if (!company || !contact_name) return res.status(400).json({ error: 'company and contact_name are required' });
    if (!CONTACT_TYPES.has(contact_type)) {
      return res.status(400).json({ error: 'contact_type must be one of hiring_manager, warm_connection, informational' });
    }
    const status = CONTACT_STATUSES.has(body.status) ? body.status : 'active';

    const id = randomUUID();
    const now = new Date().toISOString();
    const messageSentAt = body.message_sent_at || now;

    db.prepare(`
      INSERT INTO contacts
        (id, job_id, company, contact_name, contact_title, contact_type, source,
         message_sent_at, status, next_follow_up_due, last_touch_at, follow_up_count,
         notes, confirmed, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      id,
      body.job_id || null,
      company,
      contact_name,
      body.contact_title || null,
      contact_type,
      body.source || null,
      messageSentAt,
      status,
      body.next_follow_up_due || null,
      now,
      0,
      body.notes || null,
      body.confirmed ? 1 : 0,
      now,
      now,
    );

    const contact = db.prepare('SELECT * FROM contacts WHERE id = ?').get(id) as ContactRow;
    res.status(201).json({ contact: mapRow(contact) });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to create contact' });
  }
});

router.patch('/api/contacts/:id', (req, res) => {
  try {
    const { id } = req.params;
    const existing = db.prepare('SELECT * FROM contacts WHERE id = ?').get(id) as ContactRow | undefined;
    if (!existing) return res.status(404).json({ error: 'Contact not found' });

    const body = req.body ?? {};
    const fields: string[] = [];
    const values: unknown[] = [];

    if (body.status !== undefined) {
      if (!CONTACT_STATUSES.has(body.status)) return res.status(400).json({ error: 'Invalid status' });
      fields.push('status = ?'); values.push(body.status);
    }
    if (body.confirmed !== undefined) {
      fields.push('confirmed = ?'); values.push(body.confirmed ? 1 : 0);
    }
    if (body.follow_up_count !== undefined) {
      fields.push('follow_up_count = ?'); values.push(Number(body.follow_up_count) || 0);
    }
    if (body.next_follow_up_due !== undefined) {
      fields.push('next_follow_up_due = ?'); values.push(body.next_follow_up_due || null);
    }
    let touchedNotes = false;
    if (body.notes !== undefined) {
      fields.push('notes = ?'); values.push(body.notes || null);
      touchedNotes = true;
    }

    const logTouch = touchedNotes || body.log_touch === true;

    if (fields.length === 0 && !logTouch) {
      return res.status(400).json({ error: 'No valid fields to update' });
    }

    const now = new Date().toISOString();
    fields.push('updated_at = ?'); values.push(now);
    if (logTouch) { fields.push('last_touch_at = ?'); values.push(now); }

    db.prepare(`UPDATE contacts SET ${fields.join(', ')} WHERE id = ?`).run(...values, id);

    const contact = db.prepare('SELECT * FROM contacts WHERE id = ?').get(id) as ContactRow;
    res.json({ contact: mapRow(contact) });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to update contact' });
  }
});

export default router;
