import React, { useState, useEffect } from 'react';
import { Job } from '../types/job';
import { Contact } from '../types/contact';
import { api } from '../lib/api';
import { companyOpportunityKey, fetchReviewQueue, holdsStage0 } from '../lib/reviewCenter';
import type { ReviewItem } from '../types/reviewCenter';
import StatusChip from './StatusChip';
import ErrorBoundary from './ErrorBoundary';
import {
  statusRequiresInterviewDateTime,
  isValidInterviewDateTime,
  toDatetimeLocalValue,
  toDateInputValue,
  APPLICATION_FUNNEL_SET,
} from 'shared/domain/jobPipeline';
import {
  isValidDebriefOutcome,
  toDebriefDateInputValue,
  type InterviewDebrief,
} from 'shared/domain/interviewDebrief';

import StatusSection from './job-detail/StatusSection';
import InterviewScheduleSection from './job-detail/InterviewScheduleSection';
import ContactsSection, {
  type ContactFormState,
  EMPTY_CONTACT_FORM,
} from './job-detail/ContactsSection';
import DebriefSection, {
  type DebriefFormState,
  type DebriefFieldErrors,
} from './job-detail/DebriefSection';
import MatchSummarySection from './job-detail/MatchSummarySection';
import SkillGapSection from './job-detail/SkillGapSection';
import AssetsSection from './job-detail/AssetsSection';
import LogsSection from './job-detail/LogsSection';
import ClosureModal from './job-detail/ClosureModal';

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
  onNavigateToReviewCenter?: () => void;
}

const STATUS_PROGRESSIONS: Partial<Record<Job['status'], { label: string; next: string; icon: string }>> = {
  'Backlog':           { label: 'Mark as Applied',     next: 'Applied',              icon: 'mark_email_read' },
  'Drafted':           { label: 'Mark as Applied',     next: 'Applied',              icon: 'mark_email_read' },
  'Applied':           { label: 'Got a Recruiter Call', next: 'Recruiter Screen',    icon: 'phone_in_talk' },
  'Recruiter Screen':  { label: 'Moving to Interviews', next: 'Core Interviews',     icon: 'record_voice_over' },
  'Core Interviews':   { label: 'Offer Received!',      next: 'Offer and Negotiation', icon: 'celebration' },
};

const JobDetailPanel: React.FC<JobDetailPanelProps> = ({
  job,
  onClose,
  onStatusChange,
  onNavigateToReviewCenter,
}) => {
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
  const [pausedReview, setPausedReview] = useState<ReviewItem | null>(null);

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

    fetchReviewQueue()
      .then(({ items }) => {
        const opportunityKey = companyOpportunityKey(job.company);
        const match = items.find(item =>
          item.status === 'open' &&
          holdsStage0(item.type) &&
          item.affectedOpportunities.some(opportunity =>
            opportunity.jobId === job.id || opportunity.jobId === opportunityKey,
          ),
        );
        setPausedReview(match ?? null);
      })
      .catch(() => setPausedReview(null));

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

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-on-surface/20 backdrop-blur-[2px] z-40 transition-opacity animate-fade-in"
        role="button"
        tabIndex={0}
        onClick={onClose}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.currentTarget.click();
          }
        }}
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
                {job.salary_range && (
                  <span className="flex items-center gap-1 text-[10px] bg-surface-container-high px-2 py-0.5 rounded-md text-on-surface-variant font-mono">
                    <span className="material-symbols-outlined text-[11px]">payments</span>
                    {job.salary_range}
                  </span>
                )}
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
            {pausedReview && (
              <section
                className="bg-warning-container text-on-warning-container rounded-2xl p-5"
                aria-label="Review required before this opportunity can continue"
              >
                <div className="flex items-start gap-3">
                  <span className="material-symbols-outlined mt-0.5">pause_circle</span>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-bold">This opportunity is waiting for your review</h3>
                    <p className="text-xs mt-1 leading-relaxed">
                      {pausedReview.title} needs an answer before Stage 0 can continue. Open Review Center to resolve it.
                    </p>
                    {onNavigateToReviewCenter && (
                      <button
                        type="button"
                        onClick={onNavigateToReviewCenter}
                        className="min-h-10 mt-3 px-3 rounded-lg bg-surface-container-lowest text-warning text-xs font-bold hover:bg-surface-container transition-colors"
                      >
                        Open Review Center
                      </button>
                    )}
                  </div>
                </div>
              </section>
            )}

            {/* Details — discovered / applied / interview glance */}
            <section className="bg-surface-container-low p-6 rounded-2xl">
              <h3 className="text-lg font-headline font-bold text-on-surface mb-4">Details</h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <span className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">
                    Discovered
                  </span>
                  <p className="text-sm font-medium text-on-surface py-2.5">
                    {formatGlanceDate(job.created_at) || '—'}
                  </p>
                </div>
                <div>
                  <span className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">
                    Applied
                  </span>
                  {APPLICATION_FUNNEL_SET.has(job.status) || job.applied_at || job.status === 'Closed' ? (
                    <div className="flex items-center gap-2 py-2.5">
                      <p className="text-sm font-medium text-on-surface min-w-0">
                        {formatGlanceDate(appliedAtDate) || '—'}
                      </p>
                      <label
                        htmlFor="applied-at-input"
                        className="shrink-0 inline-flex items-center justify-center w-9 h-9 rounded-lg text-on-surface-variant hover:bg-surface-container-high hover:text-primary cursor-pointer transition-colors"
                        title="Edit applied date"
                      >
                        <span className="material-symbols-outlined text-[18px]">calendar_month</span>
                        <input
                          id="applied-at-input"
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
                  <span className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">
                    Interview
                  </span>
                  <p className="text-sm font-medium text-on-surface py-2.5">
                    {interviewDate
                      ? new Date(interviewDate).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
                      : '—'}
                  </p>
                </div>
              </div>
            </section>

            <ErrorBoundary><StatusSection status={job.status} /></ErrorBoundary>

            <ErrorBoundary>
              <InterviewScheduleSection
                interviewDate={interviewDate}
                onDateChange={handleDateChange}
                progression={progression}
              />
            </ErrorBoundary>

            <ErrorBoundary>
              <ContactsSection
                contacts={contacts}
                loading={loadingContacts}
                showAddForm={showAddContact}
                formState={contactForm}
                saving={savingContact}
                error={contactError}
                onToggleAddForm={setShowAddContact}
                onFormChange={setContactForm}
                onSave={saveContact}
                onCancel={() => { setShowAddContact(false); setContactForm(EMPTY_CONTACT_FORM); setContactError(null); }}
              />
            </ErrorBoundary>

            <ErrorBoundary>
              <DebriefSection
                debriefs={debriefs}
                loadingDebriefs={loadingDebriefs}
                form={debriefForm}
                formErrors={debriefFieldErrors}
                saving={savingDebrief}
                editingId={editingDebriefId}
                error={debriefError}
                onFormChange={setDebriefForm}
                onFormErrorChange={setDebriefFieldErrors}
                onSave={saveDebrief}
                onResetForm={resetDebriefForm}
                onStartEdit={startEditDebrief}
                onDelete={deleteDebrief}
              />
            </ErrorBoundary>

            <ErrorBoundary>
              <MatchSummarySection
                summary={job.summary}
                scoreTotal={job.score_total}
                score={job.score}
                scoreBreakdownJson={job.score_breakdown_json}
                reasonSummary={job.reason_summary}
              />
            </ErrorBoundary>

            <ErrorBoundary>
              <SkillGapSection
                skillGap={skillGap}
                loading={loadingSkillGap}
                onAnalyze={fetchSkillGap}
              />
            </ErrorBoundary>

            <ErrorBoundary>
              <AssetsSection
                jobId={job.id}
                jobTitle={job.title}
                jobCompany={job.company}
                jobUrl={job.url}
                files={files}
                loadingFiles={loadingFiles}
                editingFile={editingFile}
                editingContent={editingContent}
                pdfReloadKey={pdfReloadKey}
                onStartEdit={handleStartEdit}
                onClearEditingFile={() => setEditingFile(null)}
                onSaveSuccess={() => setPdfReloadKey(prev => prev + 1)}
              />
            </ErrorBoundary>

            <ErrorBoundary>
              <LogsSection
                logs={companyLogs}
                loading={loadingLogs}
                systemStatus={systemStatus}
                companyName={job.company}
              />
            </ErrorBoundary>
          </div>

          <ClosureModal
            show={showClosureForm}
            closureData={closureData}
            onClose={() => setShowClosureForm(!showClosureForm)}
            onClosureDataChange={setClosureData}
            onConfirm={updateStatus}
            progression={progression}
            onProgression={handleProgression}
            errorMsg={errorMsg}
          />
        </div>
      </div>
    </>
  );
};

export default JobDetailPanel;
