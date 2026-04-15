import React from 'react';
import { Job } from '../types/job';

interface JobDetailPanelProps {
  job: Job | null;
  onClose: () => void;
}

const JobDetailPanel: React.FC<JobDetailPanelProps> = ({ job, onClose }) => {
  if (!job) return null;

  const timelineSteps = [
    { label: 'Backlog', date: 'Logged', done: true, active: job.status === 'Backlog' },
    { label: 'Applied', date: job.status !== 'Backlog' ? 'Submitted' : 'Pending', done: job.status !== 'Backlog', active: job.status === 'Applied' },
    { label: 'Recruiter Screen', date: ['Recruiter Screen', 'Core Interviews', 'Offer and Negotiation'].includes(job.status) ? (job.status === 'Recruiter Screen' ? 'Active' : 'Passed') : 'TBD', done: ['Core Interviews', 'Offer and Negotiation'].includes(job.status), active: job.status === 'Recruiter Screen' },
    { label: 'Core Interviews', date: ['Core Interviews', 'Offer and Negotiation'].includes(job.status) ? (job.status === 'Core Interviews' ? 'Active' : 'Passed') : 'TBD', done: job.status === 'Offer and Negotiation', active: job.status === 'Core Interviews' },
    { label: 'Offer', date: job.status === 'Offer and Negotiation' ? 'Received!' : 'TBD', done: job.status === 'Offer and Negotiation', active: job.status === 'Offer and Negotiation' },
  ];

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-on-surface/20 backdrop-blur-[2px] z-40 transition-opacity animate-fade-in"
        onClick={onClose}
      ></div>

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
              {job.score && (
                <div className="flex items-center gap-2 mt-3">
                  <span className="badge badge-primary text-xs">Score: {job.score}</span>
                </div>
              )}
            </div>
            <div className="w-14 h-14 bg-surface-container rounded-2xl flex items-center justify-center font-headline font-bold text-primary text-xl">
              {job.company.charAt(0).toUpperCase()}
            </div>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto px-8 pb-8 space-y-8 sanctuary-scrollbar">
            {/* Application Status Timeline */}
            <section className="bg-surface-container-low p-6 rounded-2xl">
              <h3 className="text-lg font-headline font-bold text-on-surface mb-4">Application Status</h3>
              <div className="space-y-5 relative">
                <div className="absolute left-3 top-3 bottom-3 w-px bg-outline-variant/30"></div>
                {timelineSteps.map((step, i) => (
                  <div key={i} className="flex gap-4 relative">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center z-10 shrink-0 ${
                      step.active ? 'bg-secondary ring-4 ring-secondary-container/50' :
                      step.done ? 'bg-primary' :
                      'bg-surface-container-highest border border-outline-variant'
                    }`}>
                      {step.done && <span className="material-symbols-outlined text-white text-[14px]">check</span>}
                    </div>
                    <div className={step.done ? '' : 'opacity-50'}>
                      <p className="text-sm font-bold text-on-surface">{step.label}</p>
                      <p className={`text-xs ${step.active ? 'text-secondary font-medium' : 'text-on-surface-variant'}`}>{step.date}</p>
                    </div>
                  </div>
                ))}
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
              <div className="space-y-2">
                {['Resume.pdf', 'CoverLetter.pdf', 'Interview_Cheat_Sheet.pdf'].map(asset => (
                  <div key={asset} className="flex items-center justify-between p-4 bg-surface-container-lowest rounded-xl hover:bg-surface-container-low cursor-pointer transition-colors group">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-primary-container rounded-lg">
                        <span className="material-symbols-outlined text-primary text-base">description</span>
                      </div>
                      <span className="text-sm text-on-surface group-hover:text-primary transition-colors">{asset}</span>
                    </div>
                    <span className="material-symbols-outlined text-on-surface-variant text-base">download</span>
                  </div>
                ))}
              </div>
            </section>

            {/* Notes */}
            <section>
              <h3 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-3">Private Notes</h3>
              <textarea
                placeholder="Add notes about this role, recruiter contact, comp details..."
                className="input-sanctuary w-full rounded-xl p-4 min-h-[120px] resize-none text-sm"
              ></textarea>
            </section>

            {/* Job Link */}
            {job.url && (
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-primary font-bold text-sm hover:underline"
              >
                View Original Posting
                <span className="material-symbols-outlined text-sm">open_in_new</span>
              </a>
            )}
          </div>

          {/* Footer Actions */}
          <div className="p-6 flex items-center justify-between border-t border-outline-variant/10">
            <button className="text-xs text-error hover:text-error-dim transition-colors font-medium">
              Remove from pipeline
            </button>
            <button className="btn-primary text-sm">
              Update Status
            </button>
          </div>
        </div>
      </div>
    </>
  );
};

export default JobDetailPanel;
