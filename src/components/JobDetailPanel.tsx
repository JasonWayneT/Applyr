import React, { useState, useEffect } from 'react';
import { Job } from '../types/job';
import { api } from '../lib/api';
import StatusChip from './StatusChip';

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
  'Applied':           { label: 'Got a Recruiter Call', next: 'Recruiter Screen',    icon: 'phone_in_talk' },
  'Recruiter Screen':  { label: 'Moving to Interviews', next: 'Core Interviews',     icon: 'record_voice_over' },
  'Core Interviews':   { label: 'Offer Received!',      next: 'Offer and Negotiation', icon: 'celebration' },
};

const JobDetailPanel: React.FC<JobDetailPanelProps> = ({ job, onClose, onStatusChange }) => {
  const [files, setFiles] = useState<JobFile[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [showClosureForm, setShowClosureForm] = useState(false);
  const [closureData, setClosureData] = useState<{
    stage: string;
    type: 'Ghosted' | 'Rejected' | 'Withdrawn' | 'Other';
    notes: string;
  }>({
    stage: job?.status || 'Backlog',
    type: 'Rejected',
    notes: ''
  });
  const [interviewDate, setInterviewDate] = useState(job?.interview_date || '');

  useEffect(() => {
    if (!job) return;
    setInterviewDate(job.interview_date || '');
    setLoadingFiles(true);
    fetch(api(`/api/jobs/${job.id}/files`))
      .then(r => r.json())
      .then(data => setFiles(data.files ?? []))
      .catch(() => setFiles([]))
      .finally(() => setLoadingFiles(false));
  }, [job?.id]);

  if (!job) return null;

  const timelineSteps = [
    { label: 'Backlog',            done: true,                                                                          active: job.status === 'Backlog' },
    { label: 'Applied',            done: ['Applied','Recruiter Screen','Core Interviews','Offer and Negotiation'].includes(job.status), active: job.status === 'Applied' },
    { label: 'Recruiter Screen',   done: ['Core Interviews','Offer and Negotiation'].includes(job.status),              active: job.status === 'Recruiter Screen' },
    { label: 'Core Interviews',    done: job.status === 'Offer and Negotiation',                                        active: job.status === 'Core Interviews' },
    { label: 'Offer',              done: job.status === 'Offer and Negotiation',                                        active: job.status === 'Offer and Negotiation' },
  ];

  const progression = STATUS_PROGRESSIONS[job.status];

  const handleDateChange = async (date: string) => {
    setInterviewDate(date);
    await fetch(api(`/api/jobs/${job.id}`), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interview_date: date }),
    });
  };

  const updateStatus = async (newStatus: string, payload: any = {}) => {
    await fetch(api(`/api/jobs/${job.id}/status`), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus, ...payload }),
    });
    onStatusChange?.(job.id, newStatus);
    onClose();
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
          <div className="flex-1 overflow-y-auto px-8 pb-8 space-y-8 sanctuary-scrollbar">
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
                    className="input-sanctuary w-full text-sm rounded-xl py-2.5 px-4"
                  />
                </div>
                {interviewDate && (
                  <p className="text-[11px] text-primary font-medium flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">notifications_active</span>
                    Scheduled for {new Date(interviewDate).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
                  </p>
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

            {/* Application Assets */}
            <section>
              <h3 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-3">Your Assets</h3>
              {loadingFiles ? (
                <p className="text-xs text-on-surface-variant animate-pulse">Loading files...</p>
              ) : files.length === 0 ? (
                <p className="text-xs text-on-surface-variant italic">No files generated yet.</p>
              ) : (
                <div className="space-y-2">
                  {files.map(file => (
                    <a
                      key={file.name}
                      href={api(`/api/jobs/${job.id}/files/${encodeURIComponent(file.name)}`)}
                      download={file.name}
                      className="flex items-center justify-between p-4 bg-surface-container-lowest rounded-xl hover:bg-surface-container-low cursor-pointer transition-colors group"
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-primary-container rounded-lg">
                          <span className="material-symbols-outlined text-primary text-base">{fileIcon(file.name)}</span>
                        </div>
                        <span className="text-sm text-on-surface group-hover:text-primary transition-colors">{file.name}</span>
                      </div>
                      <span className="material-symbols-outlined text-on-surface-variant text-base">download</span>
                    </a>
                  ))}
                </div>
              )}
            </section>

            {/* Apply CTA */}
            {job.url && (
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 bg-primary text-on-primary hover:opacity-90 font-bold text-lg py-4 px-6 rounded-2xl transition-all shadow-md w-full"
              >
                <span className="material-symbols-outlined">rocket_launch</span>
                Open Application URL
              </a>
            )}
          </div>

          {/* Footer Actions */}
          <div className="p-6 border-t border-outline-variant/10">
            {showClosureForm ? (
              <div className="space-y-4 animate-fade-in">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">Last Stage</label>
                    <select 
                      value={closureData.stage}
                      onChange={e => setClosureData({...closureData, stage: e.target.value})}
                      className="input-sanctuary w-full text-xs rounded-lg py-2"
                    >
                      {['Backlog', 'Applied', 'Recruiter Screen', 'Core Interviews', 'Offer and Negotiation'].map(s => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">Outcome</label>
                    <div className="flex gap-1">
                      {(['Rejected', 'Ghosted'] as const).map(t => (
                        <button
                          key={t}
                          onClick={() => setClosureData({...closureData, type: t})}
                          className={`flex-1 py-2 rounded-lg text-[10px] font-bold transition-all ${
                            closureData.type === t 
                              ? 'bg-error-container text-on-error-container' 
                              : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'
                          }`}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">Notes (Optional)</label>
                  <input 
                    type="text"
                    placeholder="e.g. Compensation mismatch, Role closed..."
                    value={closureData.notes}
                    onChange={e => setClosureData({...closureData, notes: e.target.value})}
                    className="input-sanctuary w-full text-xs rounded-lg py-2"
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
                    onClick={() => updateStatus('Closed', {
                      rejection_stage: closureData.stage,
                      rejection_type: closureData.type,
                      outcome_notes: closureData.notes
                    })}
                    className="flex-1 py-2.5 bg-error text-on-error rounded-xl text-xs font-bold shadow-md hover:opacity-90 transition-all"
                  >
                    Confirm Closure
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
                    onClick={() => updateStatus(progression.next)}
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
    </>
  );
};

export default JobDetailPanel;
