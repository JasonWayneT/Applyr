import React, { useState } from 'react';
import { Job } from '../types/job';
import StatusChip from '../components/StatusChip';
import { api } from '../lib/api';
import { useFitThresholds } from '../hooks/useFitThresholds';
import type { OpportunitiesFilter } from '../types/opportunities';
import { OPPORTUNITIES_FILTERS, FILTER_STATUS_MAP } from '../types/opportunities';

interface AllJobsViewProps {
  jobs: Job[];
  onJobClick: (job: Job) => void;
  activeFilter: OpportunitiesFilter;
  onFilterChange: (filter: OpportunitiesFilter) => void;
}

type SortOption = 'newest' | 'oldest' | 'company-asc' | 'company-desc' | 'score-desc';

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: 'newest', label: 'Date Added (Newest)' },
  { value: 'oldest', label: 'Date Added (Oldest)' },
  { value: 'company-asc', label: 'Company (A-Z)' },
  { value: 'company-desc', label: 'Company (Z-A)' },
  { value: 'score-desc', label: 'Fit Score (High-Low)' },
];

const AllJobsView: React.FC<AllJobsViewProps> = ({ jobs, onJobClick, activeFilter, onFilterChange }) => {
  const { skip_floor: skipFloor, tier1_floor: tier1Floor } = useFitThresholds();
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<SortOption>('newest');
  const [bannerDismissed, setBannerDismissed] = useState(false);

  const newFromScout = jobs.filter(j => j.status === 'New');

  const processedJobs = jobs.filter(job => {
    if (job.status === 'Drafted') return false;
    if (job.status === 'Rejected') return false;

    const allowedStatuses = FILTER_STATUS_MAP[activeFilter];
    if (allowedStatuses && !allowedStatuses.includes(job.status)) return false;

    if (searchTerm.trim() !== '') {
      const term = searchTerm.toLowerCase();
      const matchCompany = job.company.toLowerCase().includes(term);
      const matchTitle = job.title.toLowerCase().includes(term);
      if (!matchCompany && !matchTitle) return false;
    }

    return true;
  }).sort((a, b) => {
    switch (sortBy) {
      case 'company-asc': return a.company.localeCompare(b.company);
      case 'company-desc': return b.company.localeCompare(a.company);
      case 'oldest': return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      case 'score-desc': return (b.score ?? -1) - (a.score ?? -1);
      case 'newest':
      default: return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    }
  });

  const groups = [
    { title: 'New from scout', statuses: ['New'], chipClass: 'chip-new', icon: 'fiber_new' },
    { title: 'Ready to Apply', statuses: ['Backlog'], chipClass: 'chip-backlog', icon: 'priority_high' },
    { title: 'Needs retry', statuses: ['Needs Retry'], chipClass: 'chip-drafted', icon: 'replay' },
    { title: 'Applied', statuses: ['Applied'], chipClass: 'chip-applied', icon: 'hourglass_empty' },
    { title: 'Screening', statuses: ['Recruiter Screen'], chipClass: 'chip-recruiter-screen', icon: 'hourglass_top' },
    { title: 'Interviews', statuses: ['Core Interviews'], chipClass: 'chip-core-interviews', icon: 'record_voice_over' },
    { title: 'Offers', statuses: ['Offer and Negotiation'], chipClass: 'chip-offer', icon: 'handshake' },
    { title: 'Terminal', statuses: ['Closed'], chipClass: 'chip-closed', icon: 'archive' },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-3xl font-headline font-extrabold text-on-surface tracking-tight">Opportunities</h1>
          <p className="text-on-surface-variant mt-1">Track your career journeys with clarity.</p>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="relative">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-base">search</span>
            <input
              type="text"
              placeholder="Search company or role..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input-applyr rounded-full pl-10 pr-9 py-2 w-full sm:w-56 text-sm"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant hover:text-on-surface"
                title="Clear search"
              >
                <span className="material-symbols-outlined text-base">close</span>
              </button>
            )}
          </div>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            className="input-applyr rounded-full px-4 py-2 text-sm cursor-pointer"
            title="Sort jobs"
          >
            {SORT_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <div className="flex flex-wrap bg-surface-container-low p-1 rounded-xl gap-0.5 max-w-full">
            {OPPORTUNITIES_FILTERS.map(f => (
              <button 
                key={f} 
                onClick={() => onFilterChange(f)}
                className={`px-3 py-1.5 text-xs rounded-lg font-medium transition-colors whitespace-nowrap ${f === activeFilter ? 'bg-surface-container-lowest text-on-surface editorial-shadow' : 'text-on-surface-variant hover:text-on-surface'}`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* New-from-scout banner */}
      {newFromScout.length > 0 && !bannerDismissed && (
        <div className="flex items-center gap-3 bg-status-drafted-bg text-status-drafted-text px-5 py-3 rounded-2xl">
          <span className="material-symbols-outlined text-xl shrink-0">refresh</span>
          <p className="flex-1 text-sm font-bold">
            There {newFromScout.length === 1 ? 'is' : 'are'} {newFromScout.length} new role{newFromScout.length > 1 ? 's' : ''} from your last scout.
          </p>
          <button
            type="button"
            onClick={() => setBannerDismissed(true)}
            className="text-status-drafted-text/60 hover:text-status-drafted-text shrink-0"
            title="Dismiss"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>
      )}

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
                    className={`group bg-surface-container-lowest p-5 rounded-2xl flex items-center justify-between editorial-shadow hover:shadow-lg transition-all border border-outline-variant hover:border-outline border-l-4 cursor-pointer ${
                      job.score && job.score >= tier1Floor
                        ? 'border-l-primary'
                        : job.score && job.score >= skipFloor
                        ? 'border-l-secondary'
                        : 'border-l-outline-variant'
                    }`}
                  >
                    <div className="flex items-center gap-4 flex-1 min-w-0 pr-4">
                      <div className="w-12 h-12 bg-surface-container rounded-xl flex items-center justify-center font-headline font-bold text-primary shrink-0">
                        {job.company.charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-base font-bold text-on-surface truncate">{job.company}</span>
                        <StatusChip status={job.status} hasAssets={job.has_assets} />
                        </div>
                        <p className="text-sm text-on-surface-variant truncate mt-0.5">{job.title}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-6 shrink-0">
                      <div className="text-right hidden lg:block">
                        <span className={`text-sm font-bold ${job.score && job.score >= tier1Floor ? 'text-primary' : 'text-on-surface-variant'}`}>
                          {job.score || '—'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {['Drafted', 'Applied', 'Recruiter Screen', 'Core Interviews', 'Offer and Negotiation'].includes(job.status) && (
                          <a
                            href={api(`/api/jobs/${job.id}/download-all`)}
                            download={`${job.company.toLowerCase()}_assets.zip`}
                            onClick={(e) => e.stopPropagation()}
                            className="flex items-center justify-center p-1.5 rounded-lg hover:bg-primary/10 text-primary transition-colors"
                            title="Download all PDF assets (ZIP)"
                          >
                            <span className="material-symbols-outlined text-[18px]">download</span>
                          </a>
                        )}
                        {job.url && (
                          <a
                            href={job.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="flex items-center justify-center p-1.5 rounded-lg hover:bg-secondary/10 text-on-surface-variant hover:text-secondary transition-colors"
                            title="Open original job posting"
                          >
                            <span className="material-symbols-outlined text-[18px]">link</span>
                          </a>
                        )}
                        {job.status === 'Backlog' && job.has_assets ? (
                          <button className="btn-primary text-xs py-1.5 px-4 rounded-lg">Review to Apply</button>
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
