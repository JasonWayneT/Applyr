import React, { useState, useEffect } from 'react';
import { Job } from '../types/job';
import { api } from '../lib/api';
import StatusChip from './StatusChip';
import DocumentEditor from './DocumentEditor';

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
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [editingFile, setEditingFile] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState<string>('');
  const [pdfReloadKey, setPdfReloadKey] = useState<number>(0);

  useEffect(() => {
    if (!job) return;
    setInterviewDate(job.interview_date || '');
    setShowClosureForm(false);
    setClosureData({ stage: job.status, type: 'Rejected', notes: '' });
    setErrorMsg(null);
    setLoadingFiles(true);
    fetch(api(`/api/jobs/${job.id}/files`))
      .then(r => r.json())
      .then(data => setFiles(data.files ?? []))
      .catch(() => setFiles([]))
      .finally(() => setLoadingFiles(false));
  }, [job?.id]);

  if (!job) return null;

  const timelineSteps = [
    { label: 'Backlog',            done: true,                                                                          active: job.status === 'Backlog' || job.status === 'Drafted' },
    { label: 'Applied',            done: ['Applied','Recruiter Screen','Core Interviews','Offer and Negotiation'].includes(job.status), active: job.status === 'Applied' },
    { label: 'Recruiter Screen',   done: ['Core Interviews','Offer and Negotiation'].includes(job.status),              active: job.status === 'Recruiter Screen' },
    { label: 'Core Interviews',    done: job.status === 'Offer and Negotiation',                                        active: job.status === 'Core Interviews' },
    { label: 'Offer',              done: job.status === 'Offer and Negotiation',                                        active: job.status === 'Offer and Negotiation' },
  ];

  const progression = STATUS_PROGRESSIONS[job.status];

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

  const updateStatus = async (newStatus: string, payload: any = {}) => {
    setErrorMsg(null);
    try {
      const res = await fetch(api(`/api/jobs/${job.id}/status`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus, ...payload }),
      });
      if (!res.ok) throw new Error();
      onStatusChange?.(job.id, newStatus);
      onClose();
    } catch {
      setErrorMsg('Failed to update status. Please try again.');
    }
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

                    return (
                      <div
                        key={file.name}
                        className="flex items-center justify-between p-4 bg-surface-container-lowest rounded-xl hover:bg-surface-container-low transition-colors group"
                      >
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-primary-container rounded-lg">
                            <span className="material-symbols-outlined text-primary text-base">{fileIcon(file.name)}</span>
                          </div>
                          <span className="text-sm text-on-surface group-hover:text-primary transition-colors">{file.name}</span>
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
                        { value: 'Rejected', label: 'Rejected', color: 'bg-error-container text-on-error-container border border-error-variant/20' },
                        { value: 'Ghosted', label: 'Ghosted', color: 'bg-error-container text-on-error-container border border-error-variant/20' },
                        { value: 'Self-Rejected', label: 'Self-Reject (Not a Fit)', color: 'bg-amber-100 text-amber-800 border border-amber-300' },
                        { value: 'No Longer Available', label: 'No Longer Available', color: 'bg-slate-100 text-slate-800 border border-slate-300' }
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
                      closureData.type === 'No Longer Available' ? 'bg-slate-600' :
                      closureData.type === 'Self-Rejected' ? 'bg-amber-600' :
                      'bg-error'
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
