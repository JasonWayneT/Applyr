import React from 'react';
import { Job } from '../types/job';

interface TuningLogViewProps {
  jobs: Job[];
  onJobClick: (job: Job) => void;
}

const TuningLogView: React.FC<TuningLogViewProps> = ({ jobs, onJobClick }) => {
  // Filter for jobs that were self-rejected by the user (not the company)
  const selfRejectedJobs = jobs.filter(
    job => job.status === 'Closed' && job.rejection_type === 'Self-Rejected'
  );

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-headline font-extrabold text-on-surface tracking-tight">
            Tuning Log
          </h1>
          <p className="text-on-surface-variant mt-1 text-sm">
            Review discrepancies between automated fit scoring and your manual self-rejections.
          </p>
        </div>
        <div className="flex bg-amber-500/10 border border-amber-500/20 px-4 py-2 rounded-xl items-center gap-2 max-w-sm">
          <span className="material-symbols-outlined text-amber-600 text-lg">tune</span>
          <p className="text-[11px] font-medium text-amber-800 leading-normal">
            Use these critiques to polish constraints inside <code className="bg-amber-500/20 px-1 py-0.5 rounded font-mono">job_fit_engine.md</code>.
          </p>
        </div>
      </div>

      {/* Stats Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <div className="bg-surface-container-lowest p-5 rounded-2xl border border-outline-variant/10 editorial-shadow">
          <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest block mb-1">
            Total Critiques
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-headline font-extrabold text-on-surface">
              {selfRejectedJobs.length}
            </span>
            <span className="text-xs text-on-surface-variant">recorded mismatches</span>
          </div>
        </div>

        <div className="bg-surface-container-lowest p-5 rounded-2xl border border-outline-variant/10 editorial-shadow">
          <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest block mb-1">
            Avg Mismatched Score
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-headline font-extrabold text-primary">
              {selfRejectedJobs.length > 0
                ? Math.round(
                    selfRejectedJobs.reduce((sum, j) => sum + (j.score || 0), 0) /
                      selfRejectedJobs.length
                  )
                : '—'}
            </span>
            <span className="text-xs text-on-surface-variant">computed fit rating</span>
          </div>
        </div>

        <div className="bg-surface-container-lowest p-5 rounded-2xl border border-outline-variant/10 editorial-shadow">
          <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest block mb-1">
            Target Mismatch Stage
          </span>
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-headline font-extrabold text-secondary truncate max-w-full">
              {selfRejectedJobs.length > 0
                ? selfRejectedJobs.reduce((acc, curr) => {
                    const s = curr.rejection_stage || 'Drafted';
                    acc[s] = (acc[s] || 0) + 1;
                    return acc;
                  }, {} as Record<string, number>)[
                    Object.keys(
                      selfRejectedJobs.reduce((acc, curr) => {
                        const s = curr.rejection_stage || 'Drafted';
                        acc[s] = (acc[s] || 0) + 1;
                        return acc;
                      }, {} as Record<string, number>)
                    ).reduce((a, b) =>
                      selfRejectedJobs.reduce((acc, curr) => {
                        const s = curr.rejection_stage || 'Drafted';
                        acc[s] = (acc[s] || 0) + 1;
                        return acc;
                      }, {} as Record<string, number>)[a] >
                      selfRejectedJobs.reduce((acc, curr) => {
                        const s = curr.rejection_stage || 'Drafted';
                        acc[s] = (acc[s] || 0) + 1;
                        return acc;
                      }, {} as Record<string, number>)[b]
                        ? a
                        : b
                    )
                  ] &&
                  Object.keys(
                    selfRejectedJobs.reduce((acc, curr) => {
                      const s = curr.rejection_stage || 'Drafted';
                      acc[s] = (acc[s] || 0) + 1;
                      return acc;
                    }, {} as Record<string, number>)
                  ).reduce((a, b) =>
                    selfRejectedJobs.reduce((acc, curr) => {
                      const s = curr.rejection_stage || 'Drafted';
                      acc[s] = (acc[s] || 0) + 1;
                      return acc;
                    }, {} as Record<string, number>)[a] >
                    selfRejectedJobs.reduce((acc, curr) => {
                      const s = curr.rejection_stage || 'Drafted';
                      acc[s] = (acc[s] || 0) + 1;
                      return acc;
                    }, {} as Record<string, number>)[b]
                      ? a
                      : b
                  )
                : '—'}
            </span>
          </div>
        </div>
      </div>

      {/* Main Feedback List */}
      <div className="space-y-4">
        <h3 className="text-xs font-headline font-bold text-on-surface-variant uppercase tracking-widest px-2">
          Feedback Records
        </h3>

        {selfRejectedJobs.length === 0 ? (
          <div className="p-12 text-center text-sm text-on-surface-variant bg-surface-container-lowest rounded-2xl border border-dashed border-outline-variant/20 editorial-shadow">
            <span className="material-symbols-outlined text-4xl text-on-surface-variant/30 mb-2 block">
              checklist
            </span>
            No self-rejected critiques logged yet. When you self-reject roles, they will appear here to optimize criteria.
          </div>
        ) : (
          <div className="space-y-4">
            {selfRejectedJobs.map(job => (
              <div
                key={job.id}
                onClick={() => onJobClick(job)}
                className="group bg-surface-container-lowest p-6 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4 border border-transparent hover:border-outline-variant/10 hover:shadow-lg transition-all cursor-pointer editorial-shadow"
              >
                {/* Job Metadata Column */}
                <div className="flex items-start gap-4 flex-1 min-w-0">
                  <div className="w-12 h-12 bg-amber-500/10 border border-amber-500/20 rounded-xl flex items-center justify-center font-headline font-bold text-amber-700 shrink-0">
                    {job.company.charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-base font-bold text-on-surface truncate">
                        {job.company}
                      </span>
                      <span className="bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full text-[9px] font-bold border border-amber-200">
                        Self-Rejected
                      </span>
                    </div>
                    <p className="text-xs font-medium text-on-surface-variant truncate">
                      {job.title}
                    </p>
                    {job.rejection_stage && (
                      <p className="text-[10px] text-on-surface-variant/70">
                        Discovered Mismatch at:{' '}
                        <span className="font-semibold text-on-surface-variant">
                          {job.rejection_stage}
                        </span>
                      </p>
                    )}
                  </div>
                </div>

                {/* Outcome Critique Column */}
                <div className="flex-1 max-w-xl bg-surface-container-low px-4 py-3 rounded-xl border border-outline-variant/10">
                  <span className="text-[9px] font-bold text-on-surface-variant uppercase tracking-widest block mb-1">
                    Critique Reason
                  </span>
                  <p className="text-xs text-on-surface font-medium leading-relaxed italic">
                    "{job.outcome_notes || 'No critique explanation provided.'}"
                  </p>
                </div>

                {/* Score & Controls Column */}
                <div className="flex items-center gap-6 shrink-0 md:pl-4 justify-between md:justify-end">
                  <div className="text-center md:text-right">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest block mb-0.5">
                      Engine Score
                    </span>
                    <span className="text-lg font-extrabold text-primary">
                      {job.score !== null ? job.score : '—'}
                    </span>
                  </div>
                  <button className="btn-secondary text-xs py-1.5 px-4 rounded-lg">
                    Inspect
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default TuningLogView;
