import React, { useState, useEffect } from 'react';
import { Job } from '../types/job';
import { Contact } from '../types/contact';
import { api } from '../lib/api';
import StatusChip from './StatusChip';
import DocumentEditor from './DocumentEditor';
import {
  statusRequiresInterviewDateTime,
  isValidInterviewDateTime,
  toDatetimeLocalValue,
  toDateInputValue,
  APPLICATION_FUNNEL_SET,
} from 'shared/domain/jobPipeline';
import {
  INTERVIEW_DEBRIEF_OUTCOMES,
  isValidDebriefOutcome,
  toDebriefDateInputValue,
  type InterviewDebrief,
} from 'shared/domain/interviewDebrief';

const CONTACT_TYPE_LABELS: Record<Contact['contact_type'], string> = {
  hiring_manager: 'Hiring manager',
  warm_connection: 'Warm connection',
  informational: 'Informational',
};

type ContactFormState = {
  contact_name: string;
  contact_title: string;
  contact_type: Contact['contact_type'] | '';
  source: string;
};

const EMPTY_CONTACT_FORM: ContactFormState = {
  contact_name: '',
  contact_title: '',
  contact_type: '',
  source: '',
};

type DebriefFormState = {
  date: string;
  notes: string;
  outcome: InterviewDebrief['outcome'] | '';
};

type DebriefFieldErrors = {
  date?: boolean;
  notes?: boolean;
  outcome?: boolean;
};

function RequiredLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-[10px] font-bold text-on-surface uppercase tracking-widest mb-1.5">
      {children}
      <span className="text-error ml-0.5" aria-hidden="true">*</span>
    </label>
  );
}

/** Glance dates in Details: "Jul 9, 2026" for both discovered and applied. */
function formatGlanceDate(value: string | null | undefined): string {
  if (!value) return '';
  const trimmed = value.trim();
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  const parsed = dateOnly
    ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
    : new Date(trimmed.includes('T') ? trimmed : trimmed.replace(' ', 'T'));
  if (Number.isNaN(parsed.getTime())) return '';
  return parsed.toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' });
}

interface JobFile {
  name: string;
}

interface JobDetailPanelProps {
  job: Job | null;
  onClose: () => void;
  onStatusChange?: (id: string, newStatus: string) => void;
}

const STATUS_PROGRESSIONS: Partial<Record<Job['status'], { label: string; next: string; icon: string }>> = {
  'Backlog':           { label: 'Mark as Applied',     next: 'Applied',              icon: 'mark_email_read' },
  'Drafted':           { label: 'Mark as Applied',     next: 'Applied',              icon: 'mark_email_read' },
  'Applied':           { label: 'Got a Recruiter Call', next: 'Recruiter Screen',    icon: 'phone_in_talk' },
  'Recruiter Screen':  { label: 'Moving to Interviews', next: 'Core Interviews',     icon: 'record_voice_over' },
  'Core Interviews':   { label: 'Offer Received!',      next: 'Offer and Negotiation', icon: 'celebration' },
};

const JobDetailPanel: React.FC<JobDetailPanelProps> = ({ job, onClose, onStatusChange }) => {
  const [files, setFiles] = useState<JobFile[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [companyLogs, setCompanyLogs] = useState<any[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [showClosureForm, setShowClosureForm] = useState(false);
  const [closureData, setClosureData] = useState<{
    stage: string;
    type: 'Ghosted' | 'Rejected' | 'Withdrawn' | 'Other' | 'Self-Rejected' | 'No Longer Available';
    notes: string;
  }>({
    stage: job?.status || 'Backlog',
    type: 'Rejected',
    notes: ''
  });
  const [interviewDate, setInterviewDate] = useState(job?.interview_date || '');
  const [appliedAtDate, setAppliedAtDate] = useState(toDateInputValue(job?.applied_at));
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [editingFile, setEditingFile] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState<string>('');
  const [pdfReloadKey, setPdfReloadKey] = useState<number>(0);
  const [systemStatus, setSystemStatus] = useState<any>(null);

  const [skillGap, setSkillGap] = useState<string | null>(null);
  const [loadingSkillGap, setLoadingSkillGap] = useState(false);

  const [debriefs, setDebriefs] = useState<InterviewDebrief[]>([]);
  const [loadingDebriefs, setLoadingDebriefs] = useState(false);
  const [savingDebrief, setSavingDebrief] = useState(false);
  const [editingDebriefId, setEditingDebriefId] = useState<string | null>(null);
  const [debriefForm, setDebriefForm] = useState<DebriefFormState>({
    date: toDebriefDateInputValue(new Date().toISOString()),
    notes: '',
    outcome: '',
  });
  const [debriefError, setDebriefError] = useState<string | null>(null);
  const [debriefFieldErrors, setDebriefFieldErrors] = useState<DebriefFieldErrors>({});

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loadingContacts, setLoadingContacts] = useState(false);
  const [showAddContact, setShowAddContact] = useState(false);
  const [contactForm, setContactForm] = useState<ContactFormState>(EMPTY_CONTACT_FORM);
  const [savingContact, setSavingContact] = useState(false);
  const [contactError, setContactError] = useState<string | null>(null);

  const debriefInputClass = (invalid: boolean) =>
    `input-applyr w-full text-sm rounded-xl py-2.5 px-4 bg-surface-container-lowest ${
      invalid ? 'ring-2 ring-error/50 border-error/40' : ''
    }`;

  const resetDebriefForm = () => {
    setEditingDebriefId(null);
    setDebriefForm({
      date: toDebriefDateInputValue(new Date().toISOString()),
      notes: '',
      outcome: '',
    });
    setDebriefError(null);
    setDebriefFieldErrors({});
  };

  useEffect(() => {
    if (!job) return;
    setInterviewDate(toDatetimeLocalValue(job.interview_date) || '');
    setAppliedAtDate(toDateInputValue(job.applied_at));
    setShowClosureForm(false);
    setClosureData({ stage: job.status, type: 'Rejected', notes: '' });
    setErrorMsg(null);
    setLoadingFiles(true);
    fetch(api(`/api/jobs/${job.id}/files`))
      .then(r => r.json())
      .then(data => setFiles(data.files ?? []))
      .catch(() => setFiles([]))
      .finally(() => setLoadingFiles(false));

    setLoadingLogs(true);
    fetch(api(`/api/logs?q=${encodeURIComponent(job.company)}`))
      .then(r => r.json())
      .then(data => setCompanyLogs(data ?? []))
      .catch(() => setCompanyLogs([]))
      .finally(() => setLoadingLogs(false));

    fetch(api('/api/system-status'))
      .then(r => r.json())
      .then(data => setSystemStatus(data))
      .catch(() => {});

    setLoadingDebriefs(true);
    resetDebriefForm();
    fetch(api(`/api/jobs/${job.id}/debriefs`))
      .then(r => r.json())
      .then(data => setDebriefs(data.debriefs ?? []))
      .catch(() => setDebriefs([]))
      .finally(() => setLoadingDebriefs(false));

    setLoadingContacts(true);
    setShowAddContact(false);
    setContactForm(EMPTY_CONTACT_FORM);
    setContactError(null);
    fetch(api(`/api/contacts?job_id=${job.id}`))
      .then(r => r.json())
      .then(data => setContacts(data.contacts ?? []))
      .catch(() => setContacts([]))
      .finally(() => setLoadingContacts(false));
  }, [job?.id, job?.company]);

  if (!job) return null;

  const timelineSteps = [
    { label: 'Backlog',            done: true,                                                                          active: job.status === 'Backlog' || job.status === 'Drafted' },
    { label: 'Applied',            done: ['Applied','Recruiter Screen','Core Interviews','Offer and Negotiation'].includes(job.status), active: job.status === 'Applied' },
    { label: 'Recruiter Screen',   done: ['Core Interviews','Offer and Negotiation'].includes(job.status),              active: job.status === 'Recruiter Screen' },
    { label: 'Core Interviews',    done: job.status === 'Offer and Negotiation',                                        active: job.status === 'Core Interviews' },
    { label: 'Offer',              done: job.status === 'Offer and Negotiation',                                        active: job.status === 'Offer and Negotiation' },
  ];

  const progression = STATUS_PROGRESSIONS[job.status];

  const fetchSkillGap = async () => {
    setLoadingSkillGap(true);
    setSkillGap(null);
    try {
      const res = await fetch(api(`/api/jobs/${job.id}/skill-gap`));
      const data = await res.json();
      if (data.success && data.output) {
        setSkillGap(data.output);
      } else if (Array.isArray(data)) {
        setSkillGap(data.map((item: { gap?: string; strategy?: string }) =>
          item.strategy ? `• ${item.gap}: ${item.strategy}` : `• ${item.gap}`,
        ).join('\n'));
      } else {
        setSkillGap(data.error || "Failed to compute skill gap.");
      }
    } catch {
      setSkillGap("Error communicating with server.");
    } finally {
      setLoadingSkillGap(false);
    }
  };

  const saveDebrief = async () => {
    const fieldErrors: DebriefFieldErrors = {
      date: !debriefForm.date.trim(),
      notes: !debriefForm.notes.trim(),
      outcome: !isValidDebriefOutcome(debriefForm.outcome),
    };
    if (fieldErrors.date || fieldErrors.notes || fieldErrors.outcome) {
      setDebriefFieldErrors(fieldErrors);
      setDebriefError('Fill in all required fields before saving.');
      return;
    }
    setSavingDebrief(true);
    setDebriefError(null);
    setDebriefFieldErrors({});
    try {
      const isEdit = !!editingDebriefId;
      const url = isEdit
        ? api(`/api/jobs/${job.id}/debriefs/${editingDebriefId}`)
        : api(`/api/jobs/${job.id}/debriefs`);
      const res = await fetch(url, {
        method: isEdit ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(debriefForm),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to save debrief');

      const listRes = await fetch(api(`/api/jobs/${job.id}/debriefs`));
      const listData = await listRes.json();
      setDebriefs(listData.debriefs ?? []);
      resetDebriefForm();
    } catch (err) {
      setDebriefError(err instanceof Error ? err.message : 'Failed to save debrief.');
    } finally {
      setSavingDebrief(false);
    }
  };

  const startEditDebrief = (debrief: InterviewDebrief) => {
    setEditingDebriefId(debrief.id);
    setDebriefForm({
      date: toDebriefDateInputValue(debrief.date),
      notes: debrief.notes,
      outcome: debrief.outcome,
    });
    setDebriefError(null);
  };

  const deleteDebrief = async (debriefId: string) => {
    if (!window.confirm('Delete this debrief?')) return;
    try {
      const res = await fetch(api(`/api/jobs/${job.id}/debriefs/${debriefId}`), { method: 'DELETE' });
      if (!res.ok) throw new Error();
      setDebriefs(prev => prev.filter(d => d.id !== debriefId));
      if (editingDebriefId === debriefId) resetDebriefForm();
    } catch {
      setDebriefError('Failed to delete debrief.');
    }
  };

  const saveContact = async () => {
    if (!contactForm.contact_name.trim() || !contactForm.contact_type) {
      setContactError('Name and contact type are required.');
      return;
    }
    setSavingContact(true);
    setContactError(null);
    try {
      const res = await fetch(api('/api/contacts'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: job.id,
          company: job.company,
          contact_name: contactForm.contact_name.trim(),
          contact_title: contactForm.contact_title.trim() || undefined,
          contact_type: contactForm.contact_type,
          source: contactForm.source.trim() || undefined,
          message_sent_at: new Date().toISOString(),
          confirmed: true,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to add contact');

      const listRes = await fetch(api(`/api/contacts?job_id=${job.id}`));
      const listData = await listRes.json();
      setContacts(listData.contacts ?? []);
      setContactForm(EMPTY_CONTACT_FORM);
      setShowAddContact(false);
    } catch (err) {
      setContactError(err instanceof Error ? err.message : 'Failed to add contact.');
    } finally {
      setSavingContact(false);
    }
  };

  const handleDateChange = async (date: string) => {
    setInterviewDate(date);
    setErrorMsg(null);
    try {
      const res = await fetch(api(`/api/jobs/${job.id}`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interview_date: date }),
      });
      if (!res.ok) throw new Error();
    } catch {
      setErrorMsg('Failed to save interview date. Check that the server is running.');
    }
  };

  const handleAppliedAtChange = async (date: string) => {
    setAppliedAtDate(date);
    setErrorMsg(null);
    try {
      const res = await fetch(api(`/api/jobs/${job.id}`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ applied_at: date || null }),
      });
      if (!res.ok) throw new Error();
    } catch {
      setErrorMsg('Failed to save applied date. Check that the server is running.');
    }
  };

  const updateStatus = async (newStatus: string, payload: Record<string, unknown> = {}) => {
    setErrorMsg(null);
    try {
      const body: Record<string, unknown> = { status: newStatus, ...payload };
      if (statusRequiresInterviewDateTime(newStatus) && interviewDate) {
        body.interview_date = interviewDate;
      }
      const res = await fetch(api(`/api/jobs/${job.id}/status`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || 'Failed to update status');
      }
      onStatusChange?.(job.id, newStatus);
      onClose();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to update status. Please try again.');
    }
  };

  const handleProgression = () => {
    if (!progression) return;
    const { next, label } = progression;
    if (statusRequiresInterviewDateTime(next) && !isValidInterviewDateTime(interviewDate)) {
      setErrorMsg(`Set date and time in Interview Schedule before "${label}".`);
      return;
    }
    updateStatus(next);
  };

  const handleStartEdit = async (filename: string) => {
    try {
      const res = await fetch(api(`/api/jobs/${job.id}/files/${encodeURIComponent(filename)}`));
      const text = await res.text();
      setEditingContent(text);
      setEditingFile(filename);
    } catch (err) {
      console.error('Failed to load markdown content:', err);
      setErrorMsg('Failed to load editable document content.');
    }
  };

  const fileIcon = (name: string) => {
    if (name.endsWith('.pdf')) return 'picture_as_pdf';
    if (name.endsWith('.md'))  return 'description';
    if (name.endsWith('.json')) return 'data_object';
    return 'insert_drive_file';
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-on-surface/20 backdrop-blur-[2px] z-40 transition-opacity animate-fade-in"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-[520px] bg-surface z-50 editorial-shadow animate-slide-in overflow-hidden">
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="p-8 pb-6 flex items-start justify-between">
            <div>
              <button onClick={onClose} className="flex items-center gap-2 text-on-surface-variant hover:text-primary transition-colors text-sm font-medium mb-4">
                <span className="material-symbols-outlined text-sm">arrow_back</span>
                Back
              </button>
              <h2 className="text-3xl font-headline font-extrabold text-on-surface tracking-tight">{job.title}</h2>
              <div className="flex items-center gap-3 mt-2 text-on-surface-variant">
                <span className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-base">domain</span>
                  {job.company}
                </span>
                {job.sources && job.sources.length > 0 && (
                  <span className="flex items-center gap-1 text-[10px] bg-surface-container-high px-2 py-0.5 rounded-md text-on-surface-variant font-mono">
                    <span className="material-symbols-outlined text-[11px]">travel_explore</span>
                    Found on: {job.sources.join(', ')}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 mt-3">
                <StatusChip status={job.status} long />
                {job.score && <span className="badge badge-primary text-xs">Score: {job.score}</span>}
              </div>
            </div>
            <div className="w-14 h-14 bg-surface-container rounded-2xl flex items-center justify-center font-headline font-bold text-primary text-xl">
              {job.company.charAt(0).toUpperCase()}
            </div>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto px-8 pb-8 space-y-8 applyr-scrollbar">
            {/* Details — discovered / applied / interview glance */}
            <section className="bg-surface-container-low p-6 rounded-2xl">
              <h3 className="text-lg font-headline font-bold text-on-surface mb-4">Details</h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">
                    Discovered
                  </label>
                  <p className="text-sm font-medium text-on-surface py-2.5">
                    {formatGlanceDate(job.created_at) || '—'}
                  </p>
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">
                    Applied
                  </label>
                  {APPLICATION_FUNNEL_SET.has(job.status) || job.applied_at || job.status === 'Closed' ? (
                    <div className="flex items-center gap-2 py-2.5">
                      <p className="text-sm font-medium text-on-surface min-w-0">
                        {formatGlanceDate(appliedAtDate) || '—'}
                      </p>
                      <label
                        className="shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-lg text-on-surface-variant hover:bg-surface-container-high hover:text-primary cursor-pointer transition-colors"
                        title="Edit applied date"
                      >
                        <span className="material-symbols-outlined text-[18px]">calendar_month</span>
                        <input
                          type="date"
                          value={appliedAtDate}
                          onChange={(e) => handleAppliedAtChange(e.target.value)}
                          className="sr-only"
                        />
                      </label>
                    </div>
                  ) : (
                    <p className="text-sm text-on-surface-variant py-2.5">Not applied yet</p>
                  )}
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">
                    Interview
                  </label>
                  <p className="text-sm font-medium text-on-surface py-2.5">
                    {interviewDate
                      ? new Date(interviewDate).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
                      : '—'}
                  </p>
                </div>
              </div>
            </section>

            {/* Timeline */}
            <section className="bg-surface-container-low p-6 rounded-2xl">
              <h3 className="text-lg font-headline font-bold text-on-surface mb-4">Application Status</h3>
              <div className="space-y-5 relative">
                <div className="absolute left-3 top-3 bottom-3 w-px bg-outline-variant/30" />
                {timelineSteps.map((step, i) => (
                  <div key={i} className="flex gap-4 relative">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center z-10 shrink-0 ${
                      step.active ? 'bg-secondary ring-4 ring-secondary-container/50' :
                      step.done  ? 'bg-primary' :
                      'bg-surface-container-highest border border-outline-variant'
                    }`}>
                      {step.done && <span className="material-symbols-outlined text-white text-[14px]">check</span>}
                    </div>
                    <div className={step.done ? '' : 'opacity-50'}>
                      <p className="text-sm font-bold text-on-surface">{step.label}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Schedule Interview */}
            <section className="bg-primary/5 p-6 rounded-2xl border border-primary/10">
              <div className="flex items-center gap-3 mb-4">
                <span className="material-symbols-outlined text-primary">calendar_month</span>
                <h3 className="text-lg font-headline font-bold text-on-surface">Interview Schedule</h3>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">Date & Time</label>
                  <input 
                    type="datetime-local"
                    value={interviewDate}
                    onChange={(e) => handleDateChange(e.target.value)}
                    className="input-applyr w-full text-sm rounded-xl py-2.5 px-4"
                    required={!!progression && statusRequiresInterviewDateTime(progression.next)}
                  />
                </div>
                {progression && statusRequiresInterviewDateTime(progression.next) && (
                  <p className="text-[11px] text-on-surface-variant">
                    Required before &ldquo;{progression.label}&rdquo;
                  </p>
                )}
                {interviewDate && (
                  <p className="text-[11px] text-primary font-medium flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">notifications_active</span>
                    Scheduled for {new Date(interviewDate).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
                  </p>
                )}
              </div>
            </section>

            {/* Contacts — networking outreach tied to this role (CR-071) */}
            <section className="bg-surface-container-low p-6 rounded-2xl">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-secondary">group</span>
                  <h3 className="text-lg font-headline font-bold text-on-surface">Contacts</h3>
                </div>
                {!showAddContact && (
                  <button
                    type="button"
                    onClick={() => setShowAddContact(true)}
                    className="btn-secondary text-xs flex items-center gap-1"
                  >
                    <span className="material-symbols-outlined text-sm">person_add</span>
                    Add contact
                  </button>
                )}
              </div>

              {loadingContacts ? (
                <p className="text-xs text-on-surface-variant italic">Loading...</p>
              ) : contacts.length === 0 && !showAddContact ? (
                <p className="text-xs text-on-surface-variant italic">No contacts logged for this role yet.</p>
              ) : (
                <div className="space-y-3 mb-4">
                  {contacts.map(c => (
                    <div key={c.id} className="bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/10">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-bold text-on-surface">{c.contact_name}</p>
                          {c.contact_title && (
                            <p className="text-xs text-on-surface-variant">{c.contact_title}</p>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <span className="text-[10px] font-bold text-secondary bg-secondary-container/40 px-2 py-0.5 rounded-md">
                            {CONTACT_TYPE_LABELS[c.contact_type]}
                          </span>
                          {!c.confirmed && (
                            <span className="text-[10px] font-bold text-on-surface-variant bg-surface-container-high px-2 py-0.5 rounded-md">
                              Draft
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-3 mt-2 text-[11px] text-on-surface-variant">
                        <span className="capitalize">{c.status}</span>
                        {c.next_follow_up_due && (
                          <span className="flex items-center gap-1">
                            <span className="material-symbols-outlined text-[13px]">event</span>
                            Follow up {new Date(c.next_follow_up_due).toLocaleDateString([], { dateStyle: 'medium' })}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {showAddContact && (
                <div className="space-y-3 animate-fade-in bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/10">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <input
                      type="text"
                      placeholder="Contact name"
                      value={contactForm.contact_name}
                      onChange={(e) => setContactForm(prev => ({ ...prev, contact_name: e.target.value }))}
                      className="input-applyr w-full text-sm rounded-xl py-2.5 px-4 bg-surface"
                    />
                    <input
                      type="text"
                      placeholder="Title (optional)"
                      value={contactForm.contact_title}
                      onChange={(e) => setContactForm(prev => ({ ...prev, contact_title: e.target.value }))}
                      className="input-applyr w-full text-sm rounded-xl py-2.5 px-4 bg-surface"
                    />
                    <select
                      value={contactForm.contact_type}
                      onChange={(e) => setContactForm(prev => ({ ...prev, contact_type: e.target.value as Contact['contact_type'] }))}
                      className="input-applyr w-full text-sm rounded-xl py-2.5 px-4 bg-surface"
                    >
                      <option value="" disabled>Contact type…</option>
                      {(Object.keys(CONTACT_TYPE_LABELS) as Contact['contact_type'][]).map(t => (
                        <option key={t} value={t}>{CONTACT_TYPE_LABELS[t]}</option>
                      ))}
                    </select>
                    <input
                      type="text"
                      placeholder="Source (optional)"
                      value={contactForm.source}
                      onChange={(e) => setContactForm(prev => ({ ...prev, source: e.target.value }))}
                      className="input-applyr w-full text-sm rounded-xl py-2.5 px-4 bg-surface"
                    />
                  </div>
                  {contactError && <p className="text-[11px] text-error">{contactError}</p>}
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={saveContact}
                      disabled={savingContact}
                      className="btn-primary text-xs px-4 py-2 rounded-xl disabled:opacity-50"
                    >
                      {savingContact ? 'Saving...' : 'Save contact'}
                    </button>
                    <button
                      type="button"
                      onClick={() => { setShowAddContact(false); setContactForm(EMPTY_CONTACT_FORM); setContactError(null); }}
                      className="text-xs text-on-surface-variant hover:text-on-surface"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </section>

            {/* Interview Debrief — post-interview notes (separate from cheat sheet prep) */}
            <section className="bg-secondary/5 p-6 rounded-2xl border border-secondary/10">
              <div className="flex items-center gap-3 mb-4">
                <span className="material-symbols-outlined text-secondary">forum</span>
                <h3 className="text-lg font-headline font-bold text-on-surface">Interview Debrief</h3>
              </div>
              <p className="text-[11px] text-on-surface-variant mb-1 leading-relaxed">
                Capture what they asked and how it went while it is fresh. This is separate from your prep cheat sheet.
              </p>
              <p className="text-[10px] text-on-surface-variant mb-4">
                Fields marked <span className="text-error font-bold">*</span> are required.
              </p>
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <RequiredLabel>Interview date</RequiredLabel>
                    <input
                      type="date"
                      value={debriefForm.date}
                      onChange={(e) => {
                        setDebriefForm(prev => ({ ...prev, date: e.target.value }));
                        setDebriefFieldErrors(prev => ({ ...prev, date: false }));
                      }}
                      className={debriefInputClass(!!debriefFieldErrors.date)}
                      aria-invalid={debriefFieldErrors.date || undefined}
                      required
                    />
                    {debriefFieldErrors.date && (
                      <p className="text-[10px] text-error mt-1">Interview date is required.</p>
                    )}
                  </div>
                  <div>
                    <RequiredLabel>Outcome</RequiredLabel>
                    <select
                      value={debriefForm.outcome}
                      onChange={(e) => {
                        const value = e.target.value;
                        setDebriefForm(prev => ({
                          ...prev,
                          outcome: isValidDebriefOutcome(value) ? value : '',
                        }));
                        setDebriefFieldErrors(prev => ({ ...prev, outcome: false }));
                      }}
                      className={debriefInputClass(!!debriefFieldErrors.outcome)}
                      aria-invalid={debriefFieldErrors.outcome || undefined}
                      required
                    >
                      <option value="" disabled>Select how it went…</option>
                      {INTERVIEW_DEBRIEF_OUTCOMES.map(o => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                    {debriefFieldErrors.outcome && (
                      <p className="text-[10px] text-error mt-1">Select an outcome before saving.</p>
                    )}
                  </div>
                </div>
                <div>
                  <RequiredLabel>Notes</RequiredLabel>
                  <textarea
                    value={debriefForm.notes}
                    onChange={(e) => {
                      setDebriefForm(prev => ({ ...prev, notes: e.target.value }));
                      setDebriefFieldErrors(prev => ({ ...prev, notes: false }));
                    }}
                    rows={6}
                    placeholder="Questions they asked, your answers, gaps, vibe, anything worth remembering..."
                    className={`${debriefInputClass(!!debriefFieldErrors.notes)} py-3 resize-y min-h-[120px]`}
                    aria-invalid={debriefFieldErrors.notes || undefined}
                    required
                  />
                  {debriefFieldErrors.notes && (
                    <p className="text-[10px] text-error mt-1">Notes are required.</p>
                  )}
                </div>
                {debriefError && (
                  <p className="text-[11px] text-error">{debriefError}</p>
                )}
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={saveDebrief}
                    disabled={savingDebrief}
                    className="btn-primary text-xs px-4 py-2 rounded-xl disabled:opacity-50"
                  >
                    {savingDebrief ? 'Saving...' : editingDebriefId ? 'Update debrief' : 'Save debrief'}
                  </button>
                  {editingDebriefId && (
                    <button
                      type="button"
                      onClick={resetDebriefForm}
                      className="text-xs text-on-surface-variant hover:text-on-surface"
                    >
                      Cancel edit
                    </button>
                  )}
                </div>
              </div>

              <div className="mt-6 pt-5 border-t border-outline-variant/10">
                <h4 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-3">Past debriefs</h4>
                {loadingDebriefs ? (
                  <p className="text-xs text-on-surface-variant italic">Loading...</p>
                ) : debriefs.length === 0 ? (
                  <p className="text-xs text-on-surface-variant italic">No debriefs yet for this role.</p>
                ) : (
                  <div className="space-y-3">
                    {debriefs.map(d => (
                      <div key={d.id} className="bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/10">
                        <div className="flex items-start justify-between gap-3 mb-2">
                          <div>
                            <p className="text-xs font-bold text-on-surface">
                              {new Date(d.date).toLocaleDateString([], { dateStyle: 'medium' })}
                            </p>
                            <span className="text-[10px] font-bold text-secondary">{d.outcome}</span>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <button
                              type="button"
                              onClick={() => startEditDebrief(d)}
                              className="text-[10px] font-bold text-primary hover:underline"
                            >
                              Edit
                            </button>
                            <button
                              type="button"
                              onClick={() => deleteDebrief(d.id)}
                              className="text-[10px] font-bold text-error hover:underline"
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                        <p className="text-sm text-on-surface-variant whitespace-pre-wrap leading-relaxed">{d.notes}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>

            {/* Match Summary */}
            {job.summary && (
              <section>
                <h3 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-3">Match Summary</h3>
                <p className="text-sm text-on-surface-variant leading-relaxed bg-surface-container-lowest p-4 rounded-xl">
                  {job.summary}
                </p>
              </section>
            )}

            {/* Score Breakdown Section */}
            <section className="bg-surface-container-low p-6 rounded-2xl">
              <h3 className="text-lg font-headline font-bold text-on-surface mb-3 flex items-center justify-between">
                <span>Scoring Transparency</span>
                <span className="text-sm bg-primary/20 text-primary px-2.5 py-0.5 rounded-full font-mono">
                  {job.score_total !== undefined && job.score_total !== null
                    ? `${job.score_total}/100`
                    : job.score
                      ? `Score: ${job.score}`
                      : 'Unscored'}
                </span>
              </h3>
              
              {job.score_breakdown_json ? (() => {
                try {
                  const b = JSON.parse(job.score_breakdown_json) as Record<string, number>;
                  const metrics = [
                    { label: 'Role Family Match', key: 'role_family_match', max: 30 },
                    { label: 'Domain Match', key: 'domain_match', max: 20 },
                    { label: 'Seniority Match', key: 'seniority_match', max: 15 },
                    { label: 'Work Arrangement', key: 'work_arrangement', max: 15 },
                    { label: 'Company Desirability', key: 'company_desirability', max: 10 },
                    { label: 'Location Compatibility', key: 'location_compatibility', max: 5 },
                    { label: 'Compensation Signal', key: 'compensation_signal', max: 5 },
                  ];

                  return (
                    <div className="space-y-3 mt-4">
                      {metrics.map(m => {
                        const val = b[m.key] ?? b[m.label] ?? 0;
                        const pct = Math.min(100, Math.max(0, (val / m.max) * 100));
                        return (
                          <div key={m.key} className="space-y-1">
                            <div className="flex justify-between text-[11px] font-bold text-on-surface-variant">
                              <span>{m.label}</span>
                              <span>{val} / {m.max}</span>
                            </div>
                            <div className="h-1.5 bg-surface-container rounded-full overflow-hidden">
                              <div
                                className="h-full bg-secondary rounded-full transition-all"
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                      {job.reason_summary && (
                        <div className="mt-4 pt-3 border-t border-outline-variant/10 text-xs text-on-surface-variant italic leading-relaxed">
                          {job.reason_summary}
                        </div>
                      )}
                    </div>
                  );
                } catch {
                  return <p className="text-xs text-on-surface-variant italic">Failed to parse score breakdown details.</p>;
                }
              })() : (
                <p className="text-xs text-on-surface-variant italic">
                  {job.score
                    ? `Score: ${job.score} available — detailed breakdown not yet generated for this role.`
                    : 'Not yet scored.'}
                </p>
              )}
            </section>

            {/* Skill Gap Analysis */}
            <section className="bg-surface-container-low p-6 rounded-2xl mb-4">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-secondary">psychology</span>
                  <h3 className="text-lg font-headline font-bold text-on-surface">Skill Gap Analysis</h3>
                </div>
                <button
                  onClick={fetchSkillGap}
                  disabled={loadingSkillGap}
                  className="btn-secondary text-xs flex items-center gap-1"
                >
                  <span className="material-symbols-outlined text-sm">{loadingSkillGap ? 'sync' : 'analytics'}</span>
                  {loadingSkillGap ? 'Analyzing...' : 'Analyze Now'}
                </button>
              </div>
              {skillGap && (
                <div className="p-4 bg-inverse-surface rounded-xl text-inverse-on-surface text-sm font-mono whitespace-pre-wrap">
                  {skillGap}
                </div>
              )}
              {!skillGap && !loadingSkillGap && (
                <p className="text-xs text-on-surface-variant">
                  Run a localized analysis comparing your experience against this job description to identify missing hard skills.
                </p>
              )}
            </section>

            {/* Application Assets */}
            <section>
              <h3 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-3">Your Assets & Links</h3>
              {loadingFiles ? (
                <p className="text-xs text-on-surface-variant animate-pulse">Loading files...</p>
              ) : (
                <div className="space-y-2">
                  {/* Original Job URL */}
                  {job.url && (
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-between p-4 bg-surface-container-lowest rounded-xl hover:bg-surface-container-low cursor-pointer transition-colors group"
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-secondary-container rounded-lg">
                          <span className="material-symbols-outlined text-secondary text-base">link</span>
                        </div>
                        <span className="text-sm text-on-surface group-hover:text-secondary transition-colors">Original Job Posting</span>
                      </div>
                      <span className="material-symbols-outlined text-on-surface-variant text-base">open_in_new</span>
                    </a>
                  )}

                  {/* PDF Assets with inline Actions */}
                  {files.filter(f => f.name.endsWith('.pdf')).map(file => {
                    const mdFilename = file.name.replace('.pdf', '.md');
                    const hasMd = files.some(f => f.name === mdFilename);
                    const isCheatSheet = /cheat.?sheet/i.test(file.name);

                    return (
                      <div
                        key={file.name}
                        className="flex items-center justify-between p-4 bg-surface-container-lowest rounded-xl hover:bg-surface-container-low transition-colors group"
                      >
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-primary-container rounded-lg">
                            <span className="material-symbols-outlined text-primary text-base">
                              {isCheatSheet ? 'fact_check' : fileIcon(file.name)}
                            </span>
                          </div>
                          <span className="text-sm text-on-surface group-hover:text-primary transition-colors">
                            {isCheatSheet ? 'Interview Cheat Sheet' : file.name}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {hasMd && (
                            <button
                              onClick={() => handleStartEdit(mdFilename)}
                              title={`Edit ${file.name.replace('.pdf', '')}`}
                              className="p-1.5 hover:bg-surface-container-high rounded-lg text-on-surface-variant hover:text-secondary transition-all flex items-center justify-center"
                            >
                              <span className="material-symbols-outlined text-lg">edit</span>
                            </button>
                          )}
                          <a
                            href={api(`/api/jobs/${job.id}/files/${encodeURIComponent(file.name)}`)}
                            download={file.name}
                            title={`Download ${file.name}`}
                            className="p-1.5 hover:bg-surface-container-high rounded-lg text-on-surface-variant hover:text-primary transition-all flex items-center justify-center"
                          >
                            <span className="material-symbols-outlined text-lg">download</span>
                          </a>
                        </div>
                      </div>
                    );
                  })}
                  
                  {files.filter(f => f.name.endsWith('.pdf')).length === 0 && (
                    <p className="text-xs text-on-surface-variant italic px-2 pt-2">No PDF assets generated yet.</p>
                  )}
                </div>
              )}
            </section>

            {/* Pipeline Process Logs */}
            <section className="border-t border-outline-variant/10 pt-6">
              <div className="flex items-center justify-between mb-1">
                <h3 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">Pipeline Process Logs</h3>
                {loadingLogs && (
                  <span className="material-symbols-outlined text-sm animate-spin text-primary">sync</span>
                )}
              </div>
              <p className="text-[10px] text-on-surface-variant italic mb-3">
                Text-matched activity feed — may include entries from unrelated roles.
              </p>

              <div className="bg-inverse-surface rounded-xl p-4 font-mono text-[11px] leading-relaxed overflow-hidden flex flex-col max-h-[180px] overflow-y-auto applyr-scrollbar">
                {systemStatus && ['scout_running', 'evaluate_running', 'drafting'].includes(systemStatus.status) && systemStatus.current_item?.toLowerCase().includes(job.company.toLowerCase()) && (
                  <div className="flex gap-2 text-emerald-400 font-bold animate-pulse border-b border-emerald-500/10 pb-1 mb-1">
                    <span className="text-emerald-400/50 shrink-0">
                      [{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}]
                    </span>
                    <span className="shrink-0">ACTIVE</span>
                    <span className="break-words">{systemStatus.current_item}</span>
                  </div>
                )}
                {companyLogs.map((log, index) => (
                  <div key={index} className="flex gap-2 text-inverse-on-surface/90 border-b border-white/5 pb-1 mb-1 last:border-b-0 last:pb-0 last:mb-0">
                    <span className="text-inverse-on-surface/40 shrink-0">
                      [{new Date(log.timestamp + ' Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}]
                    </span>
                    <span className={`font-bold shrink-0 ${
                      log.level === 'ERROR' ? 'text-error-container' :
                      log.level === 'WARN' ? 'text-secondary-container' :
                      'text-primary-container'
                    }`}>
                      {log.level}
                    </span>
                    <span className="break-words">{log.message}</span>
                  </div>
                ))}
                {companyLogs.length === 0 && !loadingLogs && (
                  <p className="text-inverse-on-surface/40 italic text-center py-2">
                    No matching activity logs found. Assets are currently queued or completed.
                  </p>
                )}
                {loadingLogs && companyLogs.length === 0 && (
                  <p className="text-inverse-on-surface/40 animate-pulse italic text-center py-2">
                    Loading activity logs...
                  </p>
                )}
              </div>
            </section>

          </div>

          {/* Footer Actions */}
          <div className="p-6 border-t border-outline-variant/10">
            {errorMsg && (
              <p className="text-xs text-error flex items-center gap-1.5 mb-3">
                <span className="material-symbols-outlined text-sm">error</span>
                {errorMsg}
              </p>
            )}
            {showClosureForm ? (
              <div className="space-y-4 animate-fade-in">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">Last Stage</label>
                    <select 
                      value={closureData.stage}
                      onChange={e => setClosureData({...closureData, stage: e.target.value})}
                      className="input-applyr w-full text-xs rounded-lg py-2"
                    >
                      {['Backlog', 'Applied', 'Recruiter Screen', 'Core Interviews', 'Offer and Negotiation'].map(s => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </div>
                  <div className="col-span-2">
                    <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">Outcome</label>
                    <div className="flex flex-wrap gap-1.5">
                      {[
                        { value: 'Rejected', label: 'Archived', color: 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-600' },
                        { value: 'Ghosted', label: 'Ghosted', color: 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-600' },
                        { value: 'Self-Rejected', label: 'Self-Reject (Not a Fit)', color: 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-700' },
                        { value: 'No Longer Available', label: 'No Longer Available', color: 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-600' }
                      ].map(t => (
                        <button
                          key={t.value}
                          type="button"
                          onClick={() => setClosureData({...closureData, type: t.value as any})}
                          className={`px-3 py-2 rounded-lg text-[10px] font-bold transition-all ${
                            closureData.type === t.value 
                              ? t.color 
                              : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'
                          }`}
                        >
                          {t.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">
                    {closureData.type === 'Self-Rejected' ? 'Critique & Feedback (Why is this not a fit?)' : 'Notes (Optional)'}
                  </label>
                  <textarea 
                    placeholder={
                      closureData.type === 'Self-Rejected' 
                        ? "e.g., Criteria needs to weigh legacy tech stack, or solo PM role..." 
                        : "e.g., Compensation mismatch, Role closed..."
                    }
                    value={closureData.notes}
                    onChange={e => setClosureData({...closureData, notes: e.target.value})}
                    rows={3}
                    className="input-applyr w-full text-xs rounded-lg py-2 px-3 resize-none focus:outline-none"
                  />
                </div>
                <div className="flex gap-3 pt-2">
                  <button 
                    onClick={() => setShowClosureForm(false)}
                    className="flex-1 py-2.5 text-xs font-bold text-on-surface-variant hover:text-on-surface transition-colors"
                  >
                    Cancel
                  </button>
                  <button 
                    onClick={() => {
                      if (closureData.type === 'No Longer Available') {
                        updateStatus('No Longer Available', {
                          rejection_stage: closureData.stage,
                          rejection_type: closureData.type,
                          outcome_notes: closureData.notes
                        });
                      } else {
                        updateStatus('Closed', {
                          rejection_stage: closureData.stage,
                          rejection_type: closureData.type,
                          outcome_notes: closureData.notes
                        });
                      }
                    }}
                    className={`flex-1 py-2.5 rounded-xl text-xs font-bold shadow-md hover:opacity-90 transition-all text-white ${
                      closureData.type === 'Self-Rejected' ? 'bg-amber-600 dark:bg-amber-500' :
                      'bg-slate-600 dark:bg-slate-500'
                    }`}
                  >
                    {closureData.type === 'No Longer Available' ? 'Confirm Deletion' :
                     closureData.type === 'Self-Rejected' ? 'Self-Reject Role' :
                     'Confirm Closure'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <button
                  onClick={() => setShowClosureForm(true)}
                  className="text-xs text-error hover:text-error-dim transition-colors font-medium flex items-center gap-1.5"
                >
                  <span className="material-symbols-outlined text-sm">archive</span>
                  Close & Archive
                </button>

                {progression && (
                  <button
                    onClick={handleProgression}
                    className="btn-primary text-sm flex items-center gap-2"
                  >
                    <span className="material-symbols-outlined text-sm">{progression.icon}</span>
                    {progression.label}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {editingFile && (
        <div className="fixed inset-0 z-50 bg-surface flex overflow-hidden animate-fade-in">
          {/* Left Pane: Compiled PDF preview (50% width) */}
          <div className="w-1/2 h-full bg-surface-container-lowest flex flex-col relative border-r border-outline-variant/10">
            <div className="px-6 py-4 bg-surface-container-low border-b border-outline-variant/10 flex justify-between items-center">
              <div>
                <h4 className="text-xs font-headline font-extrabold text-on-surface uppercase tracking-wider flex flex-center gap-1.5">
                  <span className="material-symbols-outlined text-primary text-base">picture_as_pdf</span>
                  PDF Preview
                </h4>
                <p className="text-[10px] text-on-surface-variant">Live generated asset preview</p>
              </div>
              <a
                href={api(`/api/jobs/${job.id}/files/${editingFile.replace('.md', '.pdf')}`)}
                download={editingFile.replace('.md', '.pdf')}
                className="btn-secondary text-[11px] py-1.5 px-3 rounded-lg flex items-center gap-1.5"
              >
                <span className="material-symbols-outlined text-sm">download</span>
                Download PDF
              </a>
            </div>
            <div className="flex-1 bg-surface-container-low">
              <iframe
                src={api(`/api/jobs/${job.id}/files/${editingFile.replace('.md', '.pdf')}?t=${pdfReloadKey}`)}
                className="w-full h-full border-0"
                title="PDF Preview"
              />
            </div>
          </div>

          {/* Right Pane: Toast UI rich document editor (50% width) */}
          <div className="w-1/2 h-full">
            <DocumentEditor
              jobId={job.id}
              filename={editingFile}
              initialValue={editingContent}
              jobTitle={job.title}
              jobCompany={job.company}
              onSaveSuccess={() => {
                setPdfReloadKey(prev => prev + 1);
              }}
              onClose={() => setEditingFile(null)}
            />
          </div>
        </div>
      )}
    </>
  );
};

export default JobDetailPanel;
