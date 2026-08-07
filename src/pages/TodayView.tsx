import React, { useState, useEffect } from 'react';
import { Job } from '../types/job';
import { Contact } from '../types/contact';
import StatusChip from '../components/StatusChip';
import { api } from '../lib/api';
import type { OpportunitiesFilter } from '../types/opportunities';
import { DASHBOARD_FILTER_MAP } from '../types/opportunities';

const CONTACT_TYPE_LABELS: Record<Contact['contact_type'], string> = {
  hiring_manager: 'Hiring manager',
  warm_connection: 'Warm connection',
  informational: 'Informational',
};

type PipelineSortOption = 'newest' | 'oldest' | 'company-asc' | 'company-desc';

const PIPELINE_SORT_OPTIONS: { value: PipelineSortOption; label: string }[] = [
  { value: 'newest', label: 'Date Added (Newest)' },
  { value: 'oldest', label: 'Date Added (Oldest)' },
  { value: 'company-asc', label: 'Company (A-Z)' },
  { value: 'company-desc', label: 'Company (Z-A)' },
];

type NeedsAttentionFormState = {
  company: string;
  contact_name: string;
  contact_title: string;
  contact_type: Contact['contact_type'] | '';
  source: string;
};

const EMPTY_NEEDS_ATTENTION_FORM: NeedsAttentionFormState = {
  company: '',
  contact_name: '',
  contact_title: '',
  contact_type: '',
  source: '',
};

const SIXTY_DAYS_MS = 60 * 24 * 60 * 60 * 1000;

interface TodayViewProps {
  jobs: Job[];
  onJobClick: (job: Job) => void;
  onNavigateToOpportunities?: (filter: OpportunitiesFilter) => void;
  onStatusChange?: (id: string, newStatus: string) => void;
}

const getGreeting = () => {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
};

const TodayView: React.FC<TodayViewProps> = ({ jobs, onJobClick, onNavigateToOpportunities, onStatusChange }) => {
  const [firstName, setFirstName] = useState('');
  const [pipelineSortBy, setPipelineSortBy] = useState<PipelineSortOption>('newest');

  const [markingAppliedId, setMarkingAppliedId] = useState<string | null>(null);
  const [applyToast, setApplyToast] = useState<{ company: string } | null>(null);
  const [checkingGmail, setCheckingGmail] = useState(false);
  const [gmailCheckToast, setGmailCheckToast] = useState<string | null>(null);

  const markApplied = async (job: Job) => {
    if (markingAppliedId) return;
    setMarkingAppliedId(job.id);
    try {
      const res = await fetch(api(`/api/jobs/${job.id}/status`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'Applied' }),
      });
      if (!res.ok) throw new Error();
      onStatusChange?.(job.id, 'Applied');
      setApplyToast({ company: job.company });
      setTimeout(() => setApplyToast(null), 3000);
    } catch {
      console.error('Failed to mark job as applied');
    } finally {
      setMarkingAppliedId(null);
    }
  };

  const checkGmailNow = async () => {
    if (checkingGmail) return;
    setCheckingGmail(true);
    try {
      const res = await fetch(api('/api/gmail-sync/run'), { method: 'POST' });
      if (!res.ok) throw new Error();
      const summary = await res.json() as { scanned: number; classified: number; matched: number; written: number; dryRun: boolean };
      const parts = [`${summary.scanned} new`, `${summary.matched} matched`];
      if (!summary.dryRun) parts.push(`${summary.written} applied`);
      setGmailCheckToast(`Gmail check: ${parts.join(', ')}${summary.dryRun ? ' (dry run)' : ''}`);
    } catch {
      setGmailCheckToast('Gmail check failed — see server logs');
    } finally {
      setCheckingGmail(false);
      setTimeout(() => setGmailCheckToast(null), 5000);
    }
  };

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loadingContacts, setLoadingContacts] = useState(false);
  const [showAddContact, setShowAddContact] = useState(false);
  const [contactForm, setContactForm] = useState<NeedsAttentionFormState>(EMPTY_NEEDS_ATTENTION_FORM);
  const [savingContact, setSavingContact] = useState(false);
  const [contactError, setContactError] = useState<string | null>(null);

  useEffect(() => {
    fetch(api('/api/profile/identity'))
      .then(r => r.json())
      .then(data => { if (data?.name) setFirstName(data.name.trim().split(' ')[0]); })
      .catch(() => {});
  }, []);

  const loadContacts = () => {
    setLoadingContacts(true);
    fetch(api('/api/contacts'))
      .then(r => r.json())
      .then(data => setContacts(data.contacts ?? []))
      .catch(() => setContacts([]))
      .finally(() => setLoadingContacts(false));
  };

  useEffect(() => {
    loadContacts();
  }, []);

  const saveNeedsAttentionContact = async () => {
    if (!contactForm.company.trim() || !contactForm.contact_name.trim() || !contactForm.contact_type) {
      setContactError('Company, name, and contact type are required.');
      return;
    }
    setSavingContact(true);
    setContactError(null);
    try {
      const res = await fetch(api('/api/contacts'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company: contactForm.company.trim(),
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
      loadContacts();
      setContactForm(EMPTY_NEEDS_ATTENTION_FORM);
      setShowAddContact(false);
    } catch (err) {
      setContactError(err instanceof Error ? err.message : 'Failed to add contact.');
    } finally {
      setSavingContact(false);
    }
  };

  const todayStr = new Date().toISOString().slice(0, 10);
  const followUpDue = contacts
    .filter(c => c.next_follow_up_due && c.next_follow_up_due.slice(0, 10) <= todayStr)
    .sort((a, b) => a.next_follow_up_due!.localeCompare(b.next_follow_up_due!));
  const worthReconnecting = contacts
    .filter(c => !c.next_follow_up_due && Date.now() - new Date(c.last_touch_at).getTime() >= SIXTY_DAYS_MS)
    .sort((a, b) => new Date(a.last_touch_at).getTime() - new Date(b.last_touch_at).getTime());

  const backlogs = jobs.filter(j => j.status === 'Backlog' && j.has_assets);
  const applied = jobs.filter(j => j.status === 'Applied');
  const activeJobs = jobs.filter(j => ['Applied', 'Recruiter Screen', 'Core Interviews', 'Offer and Negotiation'].includes(j.status));
  const pipelineJobs = jobs
    .filter(j => j.status === 'Backlog' && j.has_assets)
    .sort((a, b) => {
      switch (pipelineSortBy) {
        case 'company-asc': return a.company.localeCompare(b.company);
        case 'company-desc': return b.company.localeCompare(a.company);
        case 'oldest': return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        case 'newest':
        default: return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }
    });
  const now = Date.now();
  const upcomingInterviews = jobs
    .filter(j => {
      if (!j.interview_date || ['Closed'].includes(j.status)) return false;
      return new Date(j.interview_date).getTime() > now;
    })
    .sort((a, b) => new Date(a.interview_date!).getTime() - new Date(b.interview_date!).getTime());

  const nextInterview = upcomingInterviews[0];
  const screenings = jobs.filter(j => j.status === 'Recruiter Screen');
  const coreInterviews = jobs.filter(j => j.status === 'Core Interviews');
  const offers = jobs.filter(j => j.status === 'Offer and Negotiation');

  // Scale within this chart's series only (not total jobs). Sqrt blend keeps 1 vs 16 vs 78 visually distinct
  // without a flat 12% floor that made Screening look like Backlog (BUG-006 chart follow-up).
  const getChartBarHeight = (count: number, seriesMax: number) => {
    if (count === 0) return '4px';
    if (count >= seriesMax) return '100%';
    const max = Math.max(seriesMax, 1);
    const linearPct = (count / max) * 100;
    const sqrtPct = (Math.sqrt(count) / Math.sqrt(max)) * 100;
    const blended = 0.6 * sqrtPct + 0.4 * linearPct;
    const minVisible = 8;
    return `${Math.min(96, Math.max(minVisible, blended))}%`;
  };

  const funnelCounts = [
    backlogs.length,
    applied.length,
    screenings.length,
    coreInterviews.length,
    offers.length,
  ];
  const funnelMax = Math.max(...funnelCounts, 1);

  const statusCounts = [
    { label: 'Ready to Apply', count: backlogs.length, height: getChartBarHeight(backlogs.length, funnelMax) },
    { label: 'Applied', count: applied.length, height: getChartBarHeight(applied.length, funnelMax) },
    { label: 'Screening', count: screenings.length, height: getChartBarHeight(screenings.length, funnelMax) },
    { label: 'Interviews', count: coreInterviews.length, height: getChartBarHeight(coreInterviews.length, funnelMax) },
    { label: 'Offers', count: offers.length, height: getChartBarHeight(offers.length, funnelMax) },
  ];

  const goToOpportunities = (label: string) => {
    const filter = DASHBOARD_FILTER_MAP[label];
    if (filter && onNavigateToOpportunities) onNavigateToOpportunities(filter);
  };

  const funnelClickProps = (label: string) =>
    onNavigateToOpportunities
      ? {
          role: 'button' as const,
          tabIndex: 0,
          onClick: () => goToOpportunities(label),
          onKeyDown: (e: React.KeyboardEvent) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              goToOpportunities(label);
            }
          },
          className: 'cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/50',
          title: `View ${label} in Opportunities`,
        }
      : {};

  return (
    <div className="space-y-10">
      {/* Welcome Header */}
      <section className="mb-2 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-4xl font-headline font-extrabold text-on-surface tracking-tight mb-2">
            {getGreeting()}{firstName ? `, ${firstName}` : ''}.
          </h1>
          <p className="text-on-surface-variant text-lg">
            You have <span className="text-secondary font-bold">{activeJobs.length} submitted applications</span> in progress. Let&apos;s keep the momentum going.
          </p>
        </div>
        <button
          onClick={checkGmailNow}
          disabled={checkingGmail}
          title="Manually check Gmail for new application updates (CR-072)"
          className="btn-primary flex items-center gap-2 whitespace-nowrap shrink-0 disabled:opacity-50"
        >
          <span className={`material-symbols-outlined text-base ${checkingGmail ? 'animate-spin' : ''}`}>mail</span>
          {checkingGmail ? 'Checking...' : 'Check Gmail Now'}
        </button>
      </section>

      {/* Bento Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Application Progress Chart */}
        <div className="lg:col-span-8 bg-surface-container-lowest rounded-[2rem] p-8 editorial-shadow relative overflow-hidden">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-xl font-headline font-bold text-on-surface">Application Progress</h3>
              <p className="text-sm text-on-surface-variant">Your journey this month</p>
            </div>
          </div>

          {/* Bar Chart */}
          <div className="h-52 flex items-end gap-4 relative">
            {statusCounts.map((item, i) => (
              <div
                key={item.label}
                {...funnelClickProps(item.label)}
                className={`flex-1 rounded-t-lg transition-all duration-500 hover:opacity-80 relative group ${
                  item.count === 0
                    ? 'bg-outline-variant'
                    : i === 4 ? 'bg-success' : 'bg-primary'
                } ${onNavigateToOpportunities ? 'cursor-pointer hover:brightness-110' : ''}`}
                style={{ height: item.height }}
              >
                <div className="absolute -top-8 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-on-surface text-surface text-[10px] px-2 py-1 rounded whitespace-nowrap">
                  {item.count} {item.label}
                </div>
              </div>
            ))}
          </div>
          <div className="flex justify-between mt-4 text-[10px] font-bold text-on-surface-variant uppercase tracking-widest px-2">
            {statusCounts.map(s => (
              <button
                key={s.label}
                type="button"
                onClick={() => goToOpportunities(s.label)}
                disabled={!onNavigateToOpportunities}
                className={`text-center transition-colors ${
                  onNavigateToOpportunities
                    ? 'hover:text-primary cursor-pointer disabled:cursor-default'
                    : 'cursor-default'
                }`}
                title={onNavigateToOpportunities ? `View ${s.label} in Opportunities` : undefined}
              >
                {s.label}
                <span className="block text-[11px] text-on-surface tabular-nums normal-case tracking-normal mt-0.5">
                  {s.count}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Next Interview / Quick Stats */}
        <div className="lg:col-span-4 flex flex-col gap-6">
          {nextInterview ? (
            <div className="bg-primary text-on-primary rounded-[2rem] p-8 flex-1 flex flex-col justify-between shadow-xl shadow-primary/10 transition-all hover:-translate-y-1">
              <div>
                <span className="material-symbols-outlined text-4xl mb-4" style={{ fontVariationSettings: "'FILL' 1" }}>calendar_today</span>
                <h3 className="text-xl font-headline font-bold mb-2">Next Interview</h3>
                <p className="text-on-primary/80 text-sm mb-6">{nextInterview.title} at {nextInterview.company}</p>
                <div className="bg-on-primary/10 backdrop-blur-md rounded-2xl p-4 border border-on-primary/5">
                  <p className="text-xs font-bold uppercase tracking-widest opacity-60">Scheduled</p>
                  <p className="text-lg font-bold">
                    {new Date(nextInterview.interview_date!).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </div>
              <button 
                onClick={() => onJobClick(nextInterview)}
                className="mt-6 flex items-center justify-center gap-2 bg-on-primary text-primary font-bold py-3 rounded-xl hover:bg-on-primary-container transition-colors"
              >
                Prep for Interview
              </button>
            </div>
          ) : (
            <div className="bg-surface-container-lowest rounded-[2rem] p-8 flex-1 flex flex-col justify-center items-center editorial-shadow text-center">
              <span className="material-symbols-outlined text-4xl text-on-surface-variant/30 mb-3">event_available</span>
              <h3 className="text-lg font-headline font-bold text-on-surface mb-1">No interviews yet</h3>
              <p className="text-sm text-on-surface-variant">Keep applying and you&apos;ll land one soon.</p>
            </div>
          )}
        </div>

        {/* Ready to Apply Pipeline List */}
        <div className="lg:col-span-12 mt-2">
          <div className="flex flex-col md:flex-row md:items-center justify-between mb-2">
            <h3 className="text-2xl font-headline font-bold text-on-surface">Ready to Apply</h3>
            <div className="flex items-center gap-2 mt-4 md:mt-0">
              <select
                value={pipelineSortBy}
                onChange={(e) => setPipelineSortBy(e.target.value as PipelineSortOption)}
                className="px-3 py-2 bg-surface-container rounded-xl text-sm outline-none focus:ring-2 focus:ring-primary/50 text-on-surface cursor-pointer"
                title="Sort Ready to Apply"
              >
                {PIPELINE_SORT_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="space-y-4">
            {pipelineJobs.slice(0, 10).map(job => (
              <div
                key={job.id}
                onClick={() => onJobClick(job)}
                className="group bg-surface-container-lowest p-6 rounded-3xl flex flex-col md:flex-row md:items-center gap-4 editorial-shadow hover:shadow-lg transition-all border border-outline-variant hover:border-outline cursor-pointer"
              >
                <div className="flex items-center gap-4 flex-1">
                  <div className="w-14 h-14 bg-surface-container rounded-2xl flex items-center justify-center font-headline font-bold text-primary text-lg">
                    {job.company.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="flex items-center gap-3">
                      <h4 className="font-bold text-lg text-on-surface">{job.company}</h4>
                      {job.status === 'New' && (
                        <span className="bg-primary text-on-primary text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider">
                          New
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-on-surface-variant">{job.title}</p>
                  </div>
                </div>
                <div className="flex items-center gap-8">
                  {job.score && (
                    <div className="hidden lg:block">
                      <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1">Fit Score</p>
                      <p className={`text-sm font-bold ${job.score >= 80 ? 'text-primary' : 'text-on-surface-variant'}`}>{job.score}</p>
                    </div>
                  )}
                  <div className="min-w-[130px]">
                  <StatusChip status={job.status} hasAssets={job.has_assets} />
                  </div>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); markApplied(job); }}
                    disabled={markingAppliedId === job.id}
                    className="w-10 h-10 rounded-full flex items-center justify-center text-primary hover:bg-primary-container transition-colors disabled:opacity-50"
                    title="Mark as Applied"
                  >
                    <span className="material-symbols-outlined">
                      {markingAppliedId === job.id ? 'progress_activity' : 'check_circle'}
                    </span>
                  </button>
                  <a
                    href={api(`/api/jobs/${job.id}/download-all`)}
                    download={`${job.company.toLowerCase()}_assets.zip`}
                    onClick={(e) => e.stopPropagation()}
                    className="w-10 h-10 rounded-full flex items-center justify-center text-primary hover:bg-primary-container transition-colors"
                    title="Download all PDF assets (Resume + Cover Letter)"
                  >
                    <span className="material-symbols-outlined">download</span>
                  </a>
                  {job.url && (
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="w-10 h-10 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-secondary transition-colors"
                      title="Open original job posting"
                    >
                      <span className="material-symbols-outlined">link</span>
                    </a>
                  )}
                </div>
              </div>
            ))}
            {pipelineJobs.length === 0 && (
              <div className="bg-surface-container-lowest rounded-3xl p-12 text-center editorial-shadow">
                <span className="material-symbols-outlined text-5xl text-on-surface-variant/30 mb-3">check_circle</span>
                <p className="text-on-surface-variant">All caught up — no jobs waiting to be applied to.</p>
              </div>
            )}
          </div>
        </div>

        {/* Active Opportunities List */}
        <div className="lg:col-span-12 mt-8">
          <h3 className="text-2xl font-headline font-bold text-on-surface mb-6">Active Opportunities</h3>
          <div className="space-y-4">
            {activeJobs.slice(0, 20).map(job => (
              <div
                key={job.id}
                onClick={() => onJobClick(job)}
                className="group bg-surface-container-lowest p-6 rounded-3xl flex flex-col md:flex-row md:items-center gap-4 editorial-shadow hover:shadow-lg transition-all border border-outline-variant hover:border-outline cursor-pointer"
              >
                <div className="flex items-center gap-4 flex-1">
                  <div className="w-14 h-14 bg-surface-container rounded-2xl flex items-center justify-center font-headline font-bold text-primary text-lg">
                    {job.company.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <h4 className="font-bold text-lg text-on-surface">{job.company}</h4>
                    <p className="text-sm text-on-surface-variant">{job.title}</p>
                  </div>
                </div>
                <div className="flex items-center gap-8">
                  {job.score && (
                    <div className="hidden lg:block">
                      <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1">Fit Score</p>
                      <p className={`text-sm font-bold ${job.score >= 80 ? 'text-primary' : 'text-on-surface-variant'}`}>{job.score}</p>
                    </div>
                  )}
                  <div className="min-w-[130px]">
                  <StatusChip status={job.status} hasAssets={job.has_assets} />
                  </div>
                  <a
                    href={api(`/api/jobs/${job.id}/download-all`)}
                    download={`${job.company.toLowerCase()}_assets.zip`}
                    onClick={(e) => e.stopPropagation()}
                    className="w-10 h-10 rounded-full flex items-center justify-center text-primary hover:bg-primary-container transition-colors"
                    title="Download all PDF assets (Resume + Cover Letter)"
                  >
                    <span className="material-symbols-outlined">download</span>
                  </a>
                  {job.url && (
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="w-10 h-10 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-container hover:text-secondary transition-colors"
                      title="Open original job posting"
                    >
                      <span className="material-symbols-outlined">link</span>
                    </a>
                  )}
                </div>
              </div>
            ))}
            {activeJobs.length === 0 && (
              <div className="bg-surface-container-lowest rounded-3xl p-12 text-center editorial-shadow">
                <span className="material-symbols-outlined text-5xl text-on-surface-variant/30 mb-3">work_outline</span>
                <p className="text-on-surface-variant">No active applications yet. Start your journey.</p>
              </div>
            )}
          </div>
        </div>

        {/* Upcoming Interviews Schedule */}
        <div className="lg:col-span-12 mt-8">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-2xl font-headline font-bold text-on-surface">Upcoming Interviews</h3>
            <div className="flex gap-2">
              <span className="badge bg-secondary/10 text-secondary text-xs">{upcomingInterviews.length} Scheduled</span>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {upcomingInterviews.map(job => (
              <div 
                key={job.id}
                onClick={() => onJobClick(job)}
                className="bg-surface-container-lowest p-6 rounded-3xl editorial-shadow border border-outline-variant hover:border-primary transition-all cursor-pointer group"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="w-12 h-12 bg-surface-container rounded-2xl flex items-center justify-center font-headline font-bold text-primary">
                    {job.company.charAt(0).toUpperCase()}
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Date</p>
                    <p className="text-sm font-bold text-on-surface">
                      {new Date(job.interview_date!).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                    </p>
                  </div>
                </div>
                <h4 className="font-bold text-on-surface group-hover:text-primary transition-colors">{job.company}</h4>
                <p className="text-xs text-on-surface-variant mb-4">{job.title}</p>
                <div className="flex items-center gap-2 pt-4 border-t border-outline-variant/5">
                  <span className="material-symbols-outlined text-sm text-secondary">schedule</span>
                  <span className="text-xs font-bold text-secondary">
                    {new Date(job.interview_date!).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            ))}
            {upcomingInterviews.length === 0 && (
              <div className="col-span-full py-12 bg-surface-container-low/30 border border-dashed border-outline-variant/20 rounded-3xl text-center">
                <p className="text-on-surface-variant text-sm">No future interviews scheduled.</p>
              </div>
            )}
          </div>
        </div>

        {/* Needs Attention — networking contacts (CR-071) */}
        <div className="lg:col-span-12 mt-8">
          <div className="bg-surface-container-lowest rounded-[2rem] p-8 editorial-shadow">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-secondary">group</span>
                <h3 className="text-2xl font-headline font-bold text-on-surface">Needs Attention</h3>
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

            {showAddContact && (
              <div className="space-y-3 animate-fade-in bg-surface-container-low p-4 rounded-2xl mb-6">
                <p className="text-[11px] text-on-surface-variant">
                  For a contact with no open role tied to it yet — e.g. someone you met before a job existed.
                  For contacts tied to a specific role, add them from that job&apos;s detail panel instead.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <input
                    type="text"
                    placeholder="Company"
                    value={contactForm.company}
                    onChange={(e) => setContactForm(prev => ({ ...prev, company: e.target.value }))}
                    className="input-applyr w-full text-sm rounded-xl py-2.5 px-4 bg-surface"
                  />
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
                    className="input-applyr w-full text-sm rounded-xl py-2.5 px-4 bg-surface sm:col-span-2"
                  />
                </div>
                {contactError && <p className="text-[11px] text-error">{contactError}</p>}
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={saveNeedsAttentionContact}
                    disabled={savingContact}
                    className="btn-primary text-xs px-4 py-2 rounded-xl disabled:opacity-50"
                  >
                    {savingContact ? 'Saving...' : 'Save contact'}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setShowAddContact(false); setContactForm(EMPTY_NEEDS_ATTENTION_FORM); setContactError(null); }}
                    className="text-xs text-on-surface-variant hover:text-on-surface"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {loadingContacts ? (
              <p className="text-xs text-on-surface-variant italic">Loading...</p>
            ) : followUpDue.length === 0 && worthReconnecting.length === 0 ? (
              !showAddContact && (
                <p className="text-sm text-on-surface-variant">Nothing needs a follow-up right now.</p>
              )
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div>
                  <h4 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-3">
                    Follow-up due
                  </h4>
                  {followUpDue.length === 0 ? (
                    <p className="text-xs text-on-surface-variant italic">Nothing due.</p>
                  ) : (
                    <div className="space-y-3">
                      {followUpDue.map(c => (
                        <div key={c.id} className="bg-surface-container-low p-4 rounded-2xl border border-outline-variant/10">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-bold text-on-surface">{c.contact_name}</p>
                              <p className="text-xs text-on-surface-variant">{c.company}</p>
                            </div>
                            <span className="text-[10px] font-bold text-secondary bg-secondary-container/40 px-2 py-0.5 rounded-md shrink-0">
                              {CONTACT_TYPE_LABELS[c.contact_type]}
                            </span>
                          </div>
                          <p className="text-[11px] text-on-surface-variant mt-2 flex items-center gap-1">
                            <span className="material-symbols-outlined text-[13px]">event</span>
                            Due {new Date(c.next_follow_up_due!).toLocaleDateString([], { dateStyle: 'medium' })}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <h4 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-3">
                    Worth reconnecting
                  </h4>
                  {worthReconnecting.length === 0 ? (
                    <p className="text-xs text-on-surface-variant italic">Nobody&apos;s gone quiet.</p>
                  ) : (
                    <div className="space-y-3">
                      {worthReconnecting.map(c => (
                        <div key={c.id} className="bg-surface-container-low p-4 rounded-2xl border border-outline-variant/10">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-bold text-on-surface">{c.contact_name}</p>
                              <p className="text-xs text-on-surface-variant">{c.company}</p>
                            </div>
                            <span className="text-[10px] font-bold text-secondary bg-secondary-container/40 px-2 py-0.5 rounded-md shrink-0">
                              {CONTACT_TYPE_LABELS[c.contact_type]}
                            </span>
                          </div>
                          <p className="text-[11px] text-on-surface-variant mt-2">
                            Haven&apos;t talked since {new Date(c.last_touch_at).toLocaleDateString([], { dateStyle: 'medium' })}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mt-4 pb-8">
        {[
          { label: 'Total Active', value: activeJobs.length, icon: 'trending_up', navigable: true },
          { label: 'Screening', value: screenings.length, icon: 'hourglass_top', navigable: true },
          { label: 'Interviewing', value: coreInterviews.length, icon: 'record_voice_over', accent: true, navigable: true },
          { label: 'Response Rate', value: jobs.length > 0 ? `${Math.round((screenings.length + coreInterviews.length + offers.length) / jobs.length * 100)}%` : '0%', icon: 'insights', accent: true, navigable: false },
        ].map(stat => (
          <div
            key={stat.label}
            role={stat.navigable && onNavigateToOpportunities ? 'button' : undefined}
            tabIndex={stat.navigable && onNavigateToOpportunities ? 0 : undefined}
            onClick={stat.navigable ? () => goToOpportunities(stat.label) : undefined}
            onKeyDown={stat.navigable && onNavigateToOpportunities ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                goToOpportunities(stat.label);
              }
            } : undefined}
            className={`bg-surface-container-lowest rounded-2xl p-6 editorial-shadow ${
              stat.navigable && onNavigateToOpportunities
                ? 'cursor-pointer hover:border-primary border border-outline-variant transition-all hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/50'
                : ''
            }`}
            title={stat.navigable && onNavigateToOpportunities ? `View ${stat.label} in Opportunities` : undefined}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="material-symbols-outlined text-on-surface-variant/40">{stat.icon}</span>
            </div>
            <span className={`text-3xl font-headline font-extrabold ${stat.accent ? 'text-primary' : 'text-on-surface'}`}>{stat.value}</span>
            <p className="text-xs text-on-surface-variant mt-1 font-medium">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Mark as Applied confirmation toast */}
      <div className={`fixed bottom-8 right-8 flex items-center gap-3 bg-surface-container-highest text-on-surface border border-outline-variant/20 px-5 py-3 rounded-2xl shadow-2xl transition-all duration-300 z-50 transform ${
        applyToast ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0 pointer-events-none'
      }`}>
        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
          <span className="material-symbols-outlined text-primary text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
        </div>
        <p className="text-xs font-bold">
          {applyToast ? `Marked ${applyToast.company} as Applied` : ''}
        </p>
      </div>

      {/* Gmail check result toast (CR-072) */}
      <div className={`fixed bottom-8 left-8 flex items-center gap-3 bg-surface-container-highest text-on-surface border border-outline-variant/20 px-5 py-3 rounded-2xl shadow-2xl transition-all duration-300 z-50 transform ${
        gmailCheckToast ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0 pointer-events-none'
      }`}>
        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
          <span className="material-symbols-outlined text-primary text-xl">mail</span>
        </div>
        <p className="text-xs font-bold">{gmailCheckToast ?? ''}</p>
      </div>
    </div>
  );
};

export default TodayView;
