import React, { useEffect, useState, useRef, useCallback } from 'react';
import { api } from '../lib/api';

interface ActivityLog {
  id: number;
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR';
  source: string;
  message: string;
  meta: string | null;
}

interface JobMatch {
  id: string;
  company: string;
  title: string;
  score: number;
  status: string;
  created_at: string;
  has_assets?: boolean;
}

type PipelineStatus = 'idle' | 'scout_running' | 'evaluate_running' | 'drafting' | 'completed';

interface SystemStatus {
  status: PipelineStatus;
  current_item: string;
  items_completed?: number;
  items_total?: number;
}

/** CR-026 / FR-035 — gate rejections logged as ERROR for legacy rows; display as INFO in UI. */
function displayLogLevel(log: ActivityLog): ActivityLog['level'] {
  if (log.level !== 'ERROR') return log.level;
  const msg = log.message;
  if (
    msg.includes('[ZERO-TOKEN REJECT]') ||
    msg.includes('keyword pre-filter') ||
    msg.includes("Marked as 'Rejected'")
  ) {
    return 'INFO';
  }
  return log.level;
}

function isPipelineActive(status: PipelineStatus): boolean {
  return status === 'scout_running' || status === 'evaluate_running' || status === 'drafting';
}

function isEvaluatePhase(status: PipelineStatus): boolean {
  return status === 'evaluate_running' || status === 'drafting';
}

function pipelineStatusLabel(status: PipelineStatus): string {
  switch (status) {
    case 'scout_running': return 'Scouting';
    case 'evaluate_running': return 'Evaluating & drafting';
    case 'drafting': return 'Drafting';
    case 'completed': return 'Complete';
    case 'idle': return 'Idle';
    default: return status;
  }
}

function runButtonLabel(status: PipelineStatus, isSyncing: boolean): string {
  if (isSyncing) return 'Starting...';
  if (status === 'scout_running') return 'Scouting...';
  if (status === 'evaluate_running') return 'Evaluating...';
  if (status === 'drafting') return 'Drafting...';
  return 'Run Job Search';
}

interface JobSearchSettings {
  targetRole: string;
  workSetting: string;
  location: string;
  experienceLevels: string[];
  datePosted: string;
  titleBlocklist: string;
  industryBlocklist: string;
  minSalary: number;
  maxYearsRequired: number;
  minYearsPreferred: number;
}

const DEFAULT_SETTINGS: JobSearchSettings = {
  targetRole: 'Product Manager',
  workSetting: 'Remote',
  location: 'United States',
  experienceLevels: [],
  datePosted: 'Past week',
  titleBlocklist: 'Staff, VP, Head, Principal, Lead, Director, Group Product Manager, GPM, Growth, Founding, First, Manager of, Engineering Manager, People Manager, Assistant, Coordinator, Intern, Associate, Entry, Junior, Analyst, Software Engineer, Developer, Designer, Marketer',
  industryBlocklist: 'Gambling, Sports Betting, Gaming, Ad Tech, Crypto, Web3',
  minSalary: 0,
  maxYearsRequired: 7,
  minYearsPreferred: 2,
};

const LOCATIONS = [
  'United States',
  'Canada',
  'United Kingdom',
  'Australia',
  'Worldwide / Remote Only',
];

const DATE_OPTIONS = ['Past 24 hours', 'Past 3 days', 'Past week', 'Past month'];

const EXP_OPTIONS = [
  'Internship',
  'Entry Level (0-1 Years)',
  'Junior (1-2 Years)',
  'Mid Level (2-5 Years)',
  'Senior Level (5-9 Years)',
  'Expert/Leader (9+ Years)',
];

interface SourceEntry {
  id: string;
  name: string;
  type: 'ats_api' | 'vendor_api' | 'crawl';
  status: 'active' | 'warning' | 'error' | 'paused';
  last_success_at: string | null;
  last_error_at: string | null;
}

const SyncActivityView: React.FC = () => {
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const [matchedJobs, setMatchedJobs] = useState<JobMatch[]>([]);
  const [sources, setSources] = useState<SourceEntry[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    status: 'idle',
    current_item: 'No active pipeline run',
  });
  const [isSyncing, setIsSyncing] = useState(false);
  const [serverError, setServerError] = useState(false);
  const [draftingJobId, setDraftingJobId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const [settings, setSettings] = useState<JobSearchSettings>(DEFAULT_SETTINGS);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [isExpOpen, setIsExpOpen] = useState(false);
  const expRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (expRef.current && !expRef.current.contains(e.target as Node)) setIsExpOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Load saved settings on mount
  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(api('/api/profile/job_search'));
        if (res.ok) {
          const data = await res.json();
          if (data && data.targetRole) {
            setSettings(prev => ({
              ...prev,
              ...data,
              maxYearsRequired: data.maxYearsRequired ?? prev.maxYearsRequired ?? 7,
              minYearsPreferred: data.minYearsPreferred ?? prev.minYearsPreferred ?? 2,
            }));
          }
        }
      } catch { /* use defaults */ }
    };
    load();
  }, []);

  const saveSettings = useCallback((next: JobSearchSettings) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    setSaveStatus('saving');
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await fetch(api('/api/profile/job_search'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(next),
        });
        setSaveStatus(res.ok ? 'saved' : 'error');
        if (res.ok) setTimeout(() => setSaveStatus('idle'), 2000);
      } catch {
        setSaveStatus('error');
      }
    }, 1000);
  }, []);

  const update = (field: keyof JobSearchSettings, value: any) => {
    const next = { ...settings, [field]: value };
    setSettings(next);
    saveSettings(next);
  };

  const toggleExpLevel = (level: string) => {
    const next = settings.experienceLevels.includes(level)
      ? settings.experienceLevels.filter(l => l !== level)
      : [...settings.experienceLevels, level];
    update('experienceLevels', next);
  };

  const fetchLogs = async () => {
    try {
      const res = await fetch(api('/api/logs'));
      const data = await res.json();
      setLogs(data);
      setServerError(false);
      setTimeout(() => {
        scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
      }, 50);
    } catch {
      setServerError(true);
    }
  };

  const fetchMatchedJobs = async () => {
    try {
      const res = await fetch(api('/api/jobs'));
      const data = await res.json();
      if (Array.isArray(data)) {
        setMatchedJobs(data.filter(j => ['Backlog', 'Drafted', 'Needs Retry'].includes(j.status)));
      }
    } catch { /* ignore */ }
  };

  const fetchSources = async () => {
    try {
      const res = await fetch(api('/api/sources'));
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) setSources(data);
      }
    } catch { /* ignore */ }
  };

  const fetchSystemStatus = async () => {
    try {
      const res = await fetch(api('/api/system-status'));
      const data = await res.json();
      if (data) setSystemStatus(data);
    } catch { /* ignore */ }
  };

  const triggerSync = async () => {
    setIsSyncing(true);
    try {
      await fetch(api('/api/sync'), { method: 'POST' });
    } catch {
      setServerError(true);
    }
    setTimeout(() => setIsSyncing(false), 2000);
  };

  const handleDraftAssets = async (jobId: string) => {
    setDraftingJobId(jobId);
    try {
      await fetch(api(`/api/jobs/${jobId}/draft`), { method: 'POST' });
      for (let i = 0; i < 120; i++) {
        await new Promise(r => setTimeout(r, 2000));
        const res = await fetch(api('/api/system-status'));
        const data = await res.json();
        if (data?.status !== 'drafting') break;
      }
      fetchSystemStatus();
      fetchMatchedJobs();
    } catch { /* ignore */ }
    finally { setDraftingJobId(null); }
  };

  const handleDismissJob = async (jobId: string, mode: 'remove' | 'not_a_fit') => {
    try {
      const body =
        mode === 'remove'
          ? { status: 'No Longer Available' }
          : {
              status: 'Closed',
              rejection_type: 'Self-Rejected',
              outcome_notes: 'Dismissed from Scout — not pursuing',
            };
      const res = await fetch(api(`/api/jobs/${jobId}/status`), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) fetchMatchedJobs();
    } catch { /* ignore */ }
  };

  useEffect(() => {
    fetchLogs();
    fetchMatchedJobs();
    fetchSources();
    fetchSystemStatus();
    const interval = setInterval(() => {
      fetchLogs();
      fetchMatchedJobs();
      fetchSources();
      fetchSystemStatus();
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const eventSourceRef = useRef<EventSource | null>(null);

  const connectSSE = useCallback(() => {
    if (eventSourceRef.current) return;

    const es = new EventSource(api('/api/sync/stream'));
    eventSourceRef.current = es;

    es.addEventListener('stage_handoff', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        let nextStatus: PipelineStatus = 'scout_running';
        let currentItem = '';
        if (data.to === 'EVALUATE') {
          nextStatus = 'evaluate_running';
          currentItem = 'Evaluating fit and drafting assets';
        } else if (data.to === 'SCOUT') {
          nextStatus = 'scout_running';
          currentItem = 'Running job connector orchestration';
        } else if (data.to === 'BACKFILL') {
          nextStatus = 'scout_running';
          currentItem = 'Reconciling URLs and executing backfills';
        } else if (data.to === 'SCRAPE') {
          nextStatus = 'scout_running';
          currentItem = 'Crawling and scraping full descriptions';
        }

        setSystemStatus((prev) => ({
          ...prev,
          status: nextStatus,
          current_item: currentItem || prev.current_item,
        }));
        fetchLogs();
        fetchMatchedJobs();
      } catch (err) {
        console.error('Failed to parse stage_handoff SSE event:', err);
      }
    });

    es.addEventListener('source_progress', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        // Add log entry locally to show immediate progress
        const localLog: ActivityLog = {
          id: Date.now(),
          timestamp: new Date().toISOString().replace('Z', ''),
          level: 'INFO',
          source: data.source,
          message: `${data.source}: ${data.fetched} fetched, ${data.passed} saved`,
          meta: null,
        };
        setLogs((prev) => [...prev, localLog]);
        
        // Update source entry status and progress dynamically in source registry
        setSources((prev) =>
          prev.map((s) => {
            if (s.id === data.source || s.name === data.source) {
              return {
                ...s,
                status: 'active',
                last_success_at: new Date().toISOString(),
              };
            }
            return s;
          })
        );
        fetchLogs();
      } catch (err) {
        console.error('Failed to parse source_progress SSE event:', err);
      }
    });

    es.addEventListener('source_health', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        setSources((prev) =>
          prev.map((s) => {
            if (s.id === data.source || s.name === data.source) {
              return {
                ...s,
                status: data.status,
                last_success_at: data.status === 'active' ? new Date().toISOString() : s.last_success_at,
                last_error_at: ['warning', 'error'].includes(data.status) ? new Date().toISOString() : s.last_error_at,
              };
            }
            return s;
          })
        );
      } catch (err) {
        console.error('Failed to parse source_health SSE event:', err);
      }
    });

    es.addEventListener('connector_error', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        const localLog: ActivityLog = {
          id: Date.now(),
          timestamp: new Date().toISOString().replace('Z', ''),
          level: 'ERROR',
          source: data.source,
          message: `Connector failed: ${data.error}`,
          meta: null,
        };
        setLogs((prev) => [...prev, localLog]);
        fetchLogs();
      } catch (err) {
        console.error('Failed to parse connector_error SSE event:', err);
      }
    });

    es.addEventListener('run_complete', (e: MessageEvent) => {
      try {
        setSystemStatus({
          status: 'completed',
          current_item: 'Completed end-to-end sync successfully!',
        });
        setIsSyncing(false);
        fetchLogs();
        fetchMatchedJobs();
        fetchSources();
      } catch (err) {
        console.error('Failed to parse run_complete SSE event:', err);
      }
    });

    es.onerror = () => {
      console.warn('SSE connection encountered an error.');
    };
  }, []);

  const disconnectSSE = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  useEffect(() => {
    connectSSE();
    return () => {
      disconnectSSE();
    };
  }, [connectSSE, disconnectSSE]);

  const isRunning = isSyncing || isPipelineActive(systemStatus.status);
  const evaluateProgress =
    (systemStatus.items_total ?? 0) > 0
      ? Math.min(100, Math.round(((systemStatus.items_completed ?? 0) / systemStatus.items_total!) * 100))
      : null;

  const scoutQueue = matchedJobs.filter(j => j.status === 'Drafted');
  const evaluatedJobs = matchedJobs.filter(j => j.status === 'Backlog' || j.status === 'Needs Retry');
  const readyCount = evaluatedJobs.filter(j => j.status === 'Backlog' && j.has_assets).length;

  const renderJobCard = (job: JobMatch) => (
    <div key={job.id} className="p-4 bg-surface-container-low hover:bg-surface-container rounded-xl flex flex-col gap-1.5 transition-all border border-outline/5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold text-primary uppercase tracking-widest">{job.company}</span>
        <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded ${
          job.status === 'Backlog' && job.has_assets
            ? 'bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400'
            : job.status === 'Drafted'
              ? 'bg-sky-500/10 text-sky-600 dark:bg-sky-500/20 dark:text-sky-400'
              : 'bg-amber-500/10 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400'
        }`}>
          {job.status === 'Needs Retry'
            ? 'Needs retry'
            : job.status === 'Drafted'
              ? 'Awaiting evaluation'
              : job.status === 'Backlog' && job.has_assets
                ? 'Ready to Apply'
                : 'Pending Assets'}
        </span>
      </div>
      <h4 className="text-sm font-headline font-bold text-on-surface leading-tight">{job.title}</h4>
      <div className="flex items-center justify-between mt-1 text-xs text-on-surface-variant">
        <span>Score: {job.score || 'N/A'}</span>
        <span>Discovered: {new Date(job.created_at).toLocaleDateString()}</span>
      </div>
      <div className="mt-2.5 flex flex-wrap justify-end gap-2">
        {((job.status === 'Backlog' && !job.has_assets) || job.status === 'Needs Retry') && (
          <button
            onClick={() => handleDraftAssets(job.id)}
            disabled={draftingJobId === job.id || isEvaluatePhase(systemStatus.status)}
            className="btn-secondary py-1 px-3 text-[11px] font-bold flex items-center gap-1.5 rounded-lg border border-amber-500/20 text-amber-700 bg-amber-500/5 hover:bg-amber-500/10 transition-colors"
          >
            <span className={`material-symbols-outlined text-[13px] ${draftingJobId === job.id ? 'animate-spin' : ''}`}>auto_fix</span>
            {draftingJobId === job.id ? 'Drafting...' : 'Draft Assets'}
          </button>
        )}
        <button type="button" onClick={() => handleDismissJob(job.id, 'not_a_fit')} className="py-1 px-3 text-[11px] font-bold rounded-lg border border-outline-variant/30 text-on-surface-variant hover:bg-surface-container transition-colors">Not a fit</button>
        <button type="button" onClick={() => handleDismissJob(job.id, 'remove')} className="py-1 px-3 text-[11px] font-bold rounded-lg border border-outline-variant/30 text-on-surface-variant hover:bg-surface-container transition-colors">Remove</button>
      </div>
    </div>
  );

  return (
    <div className="space-y-6 pb-10">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-headline font-extrabold text-on-surface tracking-tight">Job Search</h1>
          <p className="text-on-surface-variant mt-1 text-sm">Configure your search criteria, then run the scout to find and evaluate matching roles.</p>
        </div>
        <div className="flex items-center gap-3">
          {saveStatus === 'saving' && (
            <span className="text-[10px] bg-secondary/20 text-secondary border border-secondary/30 font-bold px-2.5 py-1 rounded-full animate-pulse">Saving...</span>
          )}
          {saveStatus === 'saved' && (
            <span className="text-[10px] bg-primary/20 text-primary border border-primary/30 font-bold px-2.5 py-1 rounded-full animate-fade-in">Saved</span>
          )}
          <button
            onClick={triggerSync}
            disabled={isRunning}
            className="btn-primary flex items-center gap-2"
          >
            <span className={`material-symbols-outlined text-base ${isRunning ? 'animate-spin' : ''}`}>radar</span>
            {runButtonLabel(systemStatus.status, isSyncing)}
          </button>
        </div>
      </div>

      {serverError && (
        <div className="flex items-center gap-3 bg-error/10 border border-error/20 rounded-xl px-4 py-3">
          <span className="material-symbols-outlined text-error text-base">error</span>
          <span className="text-xs text-error">Cannot connect to server on port 3000. Run <code className="font-mono bg-error/10 px-1 rounded">npm run dev:server</code> to start it.</span>
        </div>
      )}

      {/* PRIMARY: Search Targeting Card */}
      <div className="bg-surface-container-lowest border border-outline/10 p-6 rounded-2xl editorial-shadow space-y-6">
        <div>
          <span className="text-[10px] font-bold text-primary uppercase tracking-widest block mb-1">Search Targeting</span>
          <h2 className="text-lg font-headline font-bold text-on-surface">Active Search Criteria</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 items-start">
          {/* Target Role */}
          <div>
            <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Target Role</label>
            <input
              type="text"
              value={settings.targetRole}
              onChange={e => update('targetRole', e.target.value)}
              placeholder="e.g. Product Manager"
              className="input-applyr w-full rounded-xl text-xs py-2.5"
            />
            <p className="text-[10px] text-on-surface-variant mt-1.5 italic">Use a standard title for best results.</p>
          </div>

          {/* Work Setting */}
          <div>
            <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Work Setting</label>
            <div className="flex gap-1.5 p-1 bg-surface-container-low rounded-xl border border-outline-variant/10">
              {['Remote', 'Hybrid', 'On-site'].map(opt => (
                <button
                  key={opt}
                  onClick={() => update('workSetting', opt)}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    settings.workSetting === opt
                      ? 'bg-primary/20 text-primary border border-primary/25'
                      : 'text-on-surface-variant hover:text-on-surface'
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>

          {/* Location */}
          <div>
            <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Location</label>
            <select
              value={settings.location}
              onChange={e => update('location', e.target.value)}
              className="input-applyr w-full rounded-xl text-xs py-2.5 bg-surface-container-low cursor-pointer"
            >
              {LOCATIONS.map(loc => (
                <option key={loc} value={loc}>{loc}</option>
              ))}
            </select>
          </div>

          {/* Date Posted */}
          <div>
            <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Date Posted</label>
            <div className="grid grid-cols-2 gap-1.5">
              {DATE_OPTIONS.map(opt => (
                <button
                  key={opt}
                  onClick={() => update('datePosted', opt)}
                  className={`py-1.5 rounded-lg text-[11px] font-bold transition-all text-center ${
                    settings.datePosted === opt
                      ? 'bg-primary/20 text-primary border border-primary/25'
                      : 'bg-surface-container-low text-on-surface-variant hover:text-on-surface border border-transparent'
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Experience Level — full row */}
        <div className="pt-2 border-t border-outline-variant/10">
          <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Experience Level</label>
          <div className="relative" ref={expRef}>
            <button
              type="button"
              onClick={() => setIsExpOpen(prev => !prev)}
              className="w-full md:w-72 flex items-center justify-between bg-surface-container-low text-xs text-on-surface py-2.5 px-4 rounded-xl font-semibold border border-transparent hover:bg-surface-container transition-all"
            >
              <span className="truncate">
                {settings.experienceLevels.length > 0
                  ? settings.experienceLevels.join(', ')
                  : 'Any level'}
              </span>
              <span className="material-symbols-outlined text-sm text-on-surface-variant ml-2 shrink-0">
                {isExpOpen ? 'arrow_drop_up' : 'arrow_drop_down'}
              </span>
            </button>

            {isExpOpen && (
              <div className="absolute left-0 top-full mt-2 bg-surface-container-lowest border border-outline/10 rounded-2xl shadow-2xl p-4 z-50 animate-fade-in space-y-3 min-w-[260px]">
                <div className="space-y-2.5">
                  {EXP_OPTIONS.map(level => (
                    <label key={level} className="flex items-center gap-3 text-xs font-semibold text-on-surface hover:text-primary cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={settings.experienceLevels.includes(level)}
                        onChange={() => toggleExpLevel(level)}
                        className="rounded border-outline-variant/30 text-primary focus:ring-primary/20 w-4 h-4 bg-surface-container-low"
                      />
                      <span>{level}</span>
                    </label>
                  ))}
                </div>
                <div className="h-px bg-outline-variant/10" />
                <button
                  type="button"
                  onClick={() => { update('experienceLevels', []); setIsExpOpen(false); }}
                  className="w-full text-left text-[11px] font-extrabold text-primary uppercase tracking-wider"
                >
                  Clear
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* SECONDARY: Gate Filters Card */}
      <div className="bg-surface-container-lowest border border-outline/10 p-6 rounded-2xl editorial-shadow space-y-4">
        <div>
          <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest block mb-1">Gate Filters</span>
          <h2 className="text-base font-headline font-bold text-on-surface">Blocklists & Minimum Salary</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Title Blocklist (auto-reject)</label>
            <textarea
              value={settings.titleBlocklist}
              onChange={e => update('titleBlocklist', e.target.value)}
              rows={3}
              placeholder="Senior, VP, Director, Lead..."
              className="input-applyr w-full rounded-xl px-4 py-3 text-xs resize-none"
            />
            <p className="text-[10px] text-on-surface-variant mt-1 italic">Comma separated. Whole-word match on job title only. Senior is allowed; use years cap below.</p>
          </div>
          <div>
            <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Max years required (reject above)</label>
            <input
              type="number"
              min={3}
              max={15}
              value={settings.maxYearsRequired}
              onChange={e => update('maxYearsRequired', parseInt(e.target.value, 10) || 7)}
              className="input-applyr w-full rounded-xl px-4 py-3 text-sm"
            />
            <p className="text-[10px] text-on-surface-variant mt-1 italic">JD requiring more than this is auto-rejected (your profile: ~6 years).</p>
          </div>
          <div>
            <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Industry Blocklist</label>
            <textarea
              value={settings.industryBlocklist}
              onChange={e => update('industryBlocklist', e.target.value)}
              rows={3}
              placeholder="Crypto, Gambling, Web3..."
              className="input-applyr w-full rounded-xl px-4 py-3 text-xs resize-none"
            />
            <p className="text-[10px] text-on-surface-variant mt-1 italic">Comma separated. Matched against company descriptions.</p>
          </div>
          <div>
            <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Minimum Salary</label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant text-sm">$</span>
              <input
                type="number"
                value={settings.minSalary}
                onChange={e => update('minSalary', parseInt(e.target.value) || 0)}
                className="input-applyr w-full rounded-xl pl-8 text-xs py-2.5"
                placeholder="0"
              />
            </div>
            <p className="text-[10px] text-on-surface-variant mt-1 italic">Annual salary in USD. Set to 0 to disable.</p>
          </div>
        </div>
      </div>

      {/* Source Health Registry Section */}
      <div className="bg-surface-container-lowest border border-outline/10 p-6 rounded-2xl editorial-shadow space-y-4">
        <div>
          <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest block mb-1">Source Registries</span>
          <h2 className="text-base font-headline font-bold text-on-surface">Integrated Job Sources & Health Status</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {sources.map(src => {
            let badgeClass = 'bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/20 dark:text-emerald-400 border border-emerald-500/20';
            let statusText = 'Active';
            if (src.status === 'warning') {
              badgeClass = 'bg-amber-500/10 text-amber-600 dark:bg-amber-500/20 dark:text-amber-400 border border-amber-500/20 animate-pulse';
              statusText = 'Warning';
            } else if (src.status === 'error') {
              badgeClass = 'bg-red-500/10 text-red-600 dark:bg-red-500/20 dark:text-red-400 border border-red-500/20';
              statusText = 'Error';
            } else if (src.status === 'paused') {
              badgeClass = 'bg-slate-500/10 text-slate-600 dark:bg-slate-500/20 dark:text-slate-400 border border-slate-500/20';
              statusText = 'Paused';
            }
            return (
              <div key={src.id} className="p-3 bg-surface-container-low border border-outline-variant/10 rounded-xl flex flex-col justify-between hover:border-primary/20 transition-all select-none">
                <span className="text-xs font-bold text-on-surface truncate">{src.name}</span>
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-[9px] text-on-surface-variant font-mono uppercase">{src.type.replace('_', ' ')}</span>
                  <span className={`text-[9px] font-extrabold px-1.5 py-0.5 rounded capitalize ${badgeClass}`}>
                    {statusText}
                  </span>
                </div>
              </div>
            );
          })}
          {sources.length === 0 && (
            <div className="col-span-full py-4 text-center text-xs text-on-surface-variant italic">No configured sources found.</div>
          )}
        </div>
      </div>

      {/* Pipeline Process Stepper */}
      <div className="bg-surface-container-lowest border border-outline/10 p-6 rounded-2xl editorial-shadow space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold text-primary uppercase tracking-widest block mb-1">Process Status</span>
            <h2 className="text-lg font-headline font-bold text-on-surface">Automation Pipeline</h2>
          </div>
          <span className={`badge ${
            systemStatus.status === 'completed' ? 'badge-primary' :
            systemStatus.status === 'idle' ? 'badge-secondary' : 'bg-secondary/10 text-secondary'
          }`}>
            {pipelineStatusLabel(systemStatus.status)}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { key: 'scout_running', icon: 'search_spark', label: 'Step 1: Scouting & Matching', desc: 'Crawling job feeds and applying your search criteria' },
            { key: 'drafting',      icon: 'edit_note',    label: 'Step 2: Evaluating & Drafting', desc: 'Fit scoring, gate filters, resume, cover letter & cheat sheet' },
            { key: 'completed',    icon: 'check_circle',  label: 'Step 3: Ready for Action', desc: 'All processes finished. Check your matches to apply' },
          ].map(step => {
            const active =
              step.key === 'scout_running'
                ? systemStatus.status === 'scout_running'
                : step.key === 'drafting'
                  ? isEvaluatePhase(systemStatus.status)
                  : systemStatus.status === 'completed';
            return (
              <div key={step.key} className={`p-4 rounded-xl border flex items-start gap-3.5 select-none transition-all ${
                active ? 'border-primary bg-primary/5 ring-1 ring-primary' : 'border-outline/10 bg-surface-container-low opacity-60'
              }`}>
                <span className={`material-symbols-outlined text-xl ${active ? 'text-primary animate-pulse' : 'text-on-surface-variant'}`}>
                  {step.icon}
                </span>
                <div>
                  <h4 className="text-sm font-bold text-on-surface leading-tight">{step.label}</h4>
                  <p className="text-xs text-on-surface-variant mt-0.5">{step.desc}</p>
                </div>
              </div>
            );
          })}
        </div>

        <div className="p-4 bg-surface-container rounded-xl border border-outline/5 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              {isPipelineActive(systemStatus.status) && (
                <span className="material-symbols-outlined text-base animate-spin text-primary opacity-80 shrink-0">sync</span>
              )}
              {systemStatus.status === 'completed' && (
                <span className="material-symbols-outlined text-base text-primary shrink-0">done_all</span>
              )}
              <p className="text-sm text-on-surface font-headline font-bold truncate">
                {systemStatus.current_item || 'No ongoing pipeline process'}
              </p>
            </div>
            {systemStatus.status === 'completed' && (
              <span className="text-xs font-bold text-primary bg-primary/10 px-2.5 py-1 rounded-full flex items-center gap-1 animate-fade-in shrink-0">
                <span className="material-symbols-outlined text-xs">verified</span> All Processes Complete
              </span>
            )}
          </div>
          {isEvaluatePhase(systemStatus.status) && evaluateProgress !== null && (
            <div className="space-y-1.5">
              <div className="flex justify-between text-[11px] font-bold text-on-surface-variant uppercase tracking-wide">
                <span>Batch evaluate & draft</span>
                <span>
                  {systemStatus.items_completed ?? 0} / {systemStatus.items_total} jobs
                </span>
              </div>
              <div className="h-2 bg-surface-container-highest rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-300 rounded-full"
                  style={{ width: `${evaluateProgress}%` }}
                />
              </div>
            </div>
          )}
          {systemStatus.status === 'completed' && (systemStatus.items_total ?? 0) > 0 && (
            <p className="text-[11px] text-on-surface-variant">
              Processed {systemStatus.items_completed ?? 0} of {systemStatus.items_total} queued jobs this run.
            </p>
          )}
        </div>
      </div>

      {/* Terminal Log + Matched Jobs */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        <div className="bg-inverse-surface rounded-2xl overflow-hidden flex flex-col h-[450px] editorial-shadow">
          <div className="bg-on-surface px-5 py-3 flex justify-between items-center">
            <span className="text-[10px] text-inverse-on-surface font-mono uppercase tracking-widest">Pipeline Log Console</span>
            <div className="flex gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-error/60" />
              <div className="w-2.5 h-2.5 rounded-full bg-secondary/60" />
              <div className="w-2.5 h-2.5 rounded-full bg-primary/60" />
            </div>
          </div>
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 font-mono text-[12px] space-y-1.5 applyr-scrollbar">
            {logs.map(log => {
              const level = displayLogLevel(log);
              return (
              <div key={log.id} className="flex gap-3 leading-relaxed">
                <span className="text-inverse-on-surface/50 whitespace-nowrap">
                  [{new Date(log.timestamp + ' Z').toLocaleTimeString()}]
                </span>
                <span className={`font-bold w-12 ${
                  level === 'ERROR' ? 'text-error-container' :
                  level === 'WARN'  ? 'text-secondary-container' :
                  'text-primary-container'
                }`}>{level}</span>
                <span className="text-inverse-on-surface/60 w-16">[{log.source}]</span>
                <span className="text-inverse-on-surface break-all">{log.message}</span>
              </div>
            );})}
            {isPipelineActive(systemStatus.status) && (
              <div className="flex gap-3 leading-relaxed text-emerald-400 font-bold animate-pulse">
                <span className="text-emerald-400/50 whitespace-nowrap">[{new Date().toLocaleTimeString()}]</span>
                <span className="w-12">ACTIVE</span>
                <span className="text-emerald-400/60 w-16">[System]</span>
                <span className="break-all">
                  {systemStatus.current_item || 'Processing...'}
                  {isEvaluatePhase(systemStatus.status) && evaluateProgress !== null && (
                    <span className="text-emerald-400/80 font-normal"> ({systemStatus.items_completed}/{systemStatus.items_total})</span>
                  )}
                </span>
              </div>
            )}
            {logs.length === 0 && !isPipelineActive(systemStatus.status) && (
              <div className="text-inverse-on-surface/40 animate-pulse italic">Waiting for activity console output...</div>
            )}
          </div>
        </div>

        <div className="bg-surface-container-lowest rounded-2xl overflow-hidden flex flex-col h-[450px] border border-outline/10 editorial-shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-headline font-extrabold text-on-surface tracking-tight">Pipeline Roles</h2>
              <p className="text-xs text-on-surface-variant">
                Evaluated matches for {settings.targetRole || 'your target role'}
              </p>
            </div>
            <span className="badge badge-secondary">{readyCount} ready to apply</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-4 pr-1 applyr-scrollbar">
            <div>
              <h3 className="text-[11px] font-bold uppercase tracking-widest text-on-surface-variant mb-2">
                Evaluated ({evaluatedJobs.length})
              </h3>
              <div className="space-y-3">
                {evaluatedJobs.map(renderJobCard)}
                {evaluatedJobs.length === 0 && (
                  <p className="text-xs text-on-surface-variant/70 italic py-2">No evaluated roles yet.</p>
                )}
              </div>
            </div>

            {scoutQueue.length > 0 && (
              <div className="pt-2 border-t border-outline/10">
                <h3 className="text-[11px] font-bold uppercase tracking-widest text-on-surface-variant mb-1">
                  Scout queue ({scoutQueue.length})
                </h3>
                <p className="text-[10px] text-on-surface-variant/70 mb-2">
                  Discovered by connectors — runs through evaluation on the next sync.
                </p>
                <div className="space-y-3">
                  {scoutQueue.map(renderJobCard)}
                </div>
              </div>
            )}

            {matchedJobs.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-center opacity-40 py-8">
                <span className="material-symbols-outlined text-3xl mb-1 text-on-surface-variant">verified_user</span>
                <p className="text-xs text-on-surface">No matching jobs discovered yet.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SyncActivityView;
