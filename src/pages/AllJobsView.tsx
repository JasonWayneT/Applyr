import React, { useState } from 'react';
import { Job } from '../types/job';
import StatusChip from '../components/StatusChip';

interface AllJobsViewProps {
  jobs: Job[];
  onJobClick: (job: Job) => void;
}

const AllJobsView: React.FC<AllJobsViewProps> = ({ jobs, onJobClick }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFilter, setActiveFilter] = useState('All');

  const processedJobs = jobs.filter(job => {
    // 1. Filter by status
    if (activeFilter === 'Active' && ['Closed', 'New', 'Backlog'].includes(job.status)) return false;
    if (activeFilter === 'Backlog' && !['New', 'Backlog'].includes(job.status)) return false;
    if (activeFilter === 'Interviewing' && !['Recruiter Screen', 'Core Interviews'].includes(job.status)) return false;
    if (activeFilter === 'Closed' && job.status !== 'Closed') return false;

    // 2. Filter by search term
    if (searchTerm.trim() !== '') {
      const term = searchTerm.toLowerCase();
      const matchCompany = job.company.toLowerCase().includes(term);
      const matchTitle = job.title.toLowerCase().includes(term);
      if (!matchCompany && !matchTitle) return false;
    }

    return true;
  });

  const groups = [
    { title: 'New from scout', statuses: ['New'], chipClass: 'chip-new', icon: 'fiber_new' },
    { title: 'Needs your attention', statuses: ['Backlog'], chipClass: 'chip-backlog', icon: 'priority_high' },
    { title: 'Waiting for contact', statuses: ['Applied'], chipClass: 'chip-applied', icon: 'hourglass_empty' },
    { title: 'Initial screening', statuses: ['Recruiter Screen'], chipClass: 'chip-recruiter-screen', icon: 'hourglass_top' },
    { title: 'Active gauntlet', statuses: ['Core Interviews'], chipClass: 'chip-core-interviews', icon: 'record_voice_over' },
    { title: 'In conversation', statuses: ['Offer and Negotiation'], chipClass: 'chip-offer', icon: 'handshake' },
    { title: 'Terminal', statuses: ['Closed'], chipClass: 'chip-closed', icon: 'archive' },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-headline font-extrabold text-on-surface tracking-tight">Applications</h1>
          <p className="text-on-surface-variant mt-1">Track your career journeys with clarity.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-base">search</span>
            <input
              type="text"
              placeholder="Search company or role..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input-sanctuary rounded-full pl-10 pr-4 py-2 w-56 text-sm"
            />
          </div>
          <div className="flex bg-surface-container-low p-1 rounded-xl">
            {['All', 'Backlog', 'Active', 'Interviewing', 'Closed'].map(f => (
              <button 
                key={f} 
                onClick={() => setActiveFilter(f)}
                className={`px-4 py-1.5 text-xs rounded-lg font-medium transition-colors ${f === activeFilter ? 'bg-surface-container-lowest text-on-surface editorial-shadow' : 'text-on-surface-variant hover:text-on-surface'}`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Grouped List */}
      <div className="space-y-10">
        {groups.map(group => {
          const filteredJobs = processedJobs.filter(j => group.statuses.includes(j.status));
          
          if (filteredJobs.length === 0) {
              if (group.title !== 'Closed') return null;
              // If it's Closed, only show the empty bucket if we are explicitly filtering for Closed
              if (activeFilter !== 'Closed' && activeFilter !== 'All') return null;
              if (activeFilter === 'All' && searchTerm.trim() !== '') return null;
          }

          return (
            <div key={group.title}>
              <div className="flex items-center gap-2 mb-4 px-2">
                <span className="material-symbols-outlined text-on-surface-variant text-base">{group.icon}</span>
                <h3 className="text-xs font-headline font-bold text-on-surface-variant uppercase tracking-widest">
                  {group.title}
                </h3>
                <span className="bg-surface-container-high text-on-surface-variant px-2 py-0.5 rounded-full text-[10px] font-bold">
                  {filteredJobs.length}
                </span>
              </div>
              <div className="space-y-3">
                {filteredJobs.map(job => (
                  <div
                    key={job.id}
                    onClick={() => onJobClick(job)}
                    className="group bg-surface-container-lowest p-5 rounded-2xl flex items-center justify-between editorial-shadow hover:shadow-lg transition-all border border-transparent hover:border-outline-variant/10 cursor-pointer"
                  >
                    <div className="flex items-center gap-4 flex-1 min-w-0 pr-4">
                      <div className="w-12 h-12 bg-surface-container rounded-xl flex items-center justify-center font-headline font-bold text-primary shrink-0">
                        {job.company.charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-base font-bold text-on-surface truncate">{job.company}</span>
                        <StatusChip status={job.status} />
                        </div>
                        <p className="text-sm text-on-surface-variant truncate mt-0.5">{job.title}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-6 shrink-0">
                      <div className="text-right hidden lg:block">
                        <span className={`text-sm font-bold ${job.score && job.score >= 80 ? 'text-primary' : 'text-on-surface-variant'}`}>
                          {job.score || '—'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {job.status === 'Backlog' ? (
                          <button className="btn-primary text-xs py-1.5 px-4 rounded-lg">Review</button>
                        ) : job.status === 'Core Interviews' ? (
                          <button className="btn-secondary text-xs py-1.5 px-4 rounded-lg">Cheat sheet</button>
                        ) : (
                          <button className="btn-secondary text-xs py-1.5 px-4 rounded-lg">Details</button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                {group.title === 'Closed' && filteredJobs.length === 0 && (
                  <div className="p-8 text-center text-sm text-on-surface-variant bg-surface-container-lowest rounded-2xl editorial-shadow">
                    No closed applications yet.
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default AllJobsView;
