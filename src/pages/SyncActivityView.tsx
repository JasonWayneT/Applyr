import React, { useEffect, useState, useRef } from 'react';
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
}

interface SystemStatus {
  status: 'idle' | 'scout_running' | 'drafting' | 'completed';
  current_item: string;
}

const SyncActivityView: React.FC = () => {
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const [matchedJobs, setMatchedJobs] = useState<JobMatch[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    status: 'idle',
    current_item: 'No active pipeline run'
  });
  const [isSyncing, setIsSyncing] = useState(false);
  const [serverError, setServerError] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

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
        // Filter to display latest backlog or drafted roles
        const matched = data.filter(j => ['Backlog', 'Drafted'].includes(j.status));
        setMatchedJobs(matched);
      }
    } catch {
      // ignore
    }
  };

  const fetchSystemStatus = async () => {
    try {
      const res = await fetch(api('/api/system-status'));
      const data = await res.json();
      if (data) {
        setSystemStatus(data);
      }
    } catch {
      // ignore
    }
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

  useEffect(() => {
    fetchLogs();
    fetchMatchedJobs();
    fetchSystemStatus();
    const interval = setInterval(() => {
      fetchLogs();
      fetchMatchedJobs();
      fetchSystemStatus();
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-8 pb-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-headline font-extrabold text-on-surface tracking-tight">Pipeline Status & Scouting</h1>
          <p className="text-on-surface-variant mt-1">Real-time visibility into process progression, scouting runs, and asset drafting.</p>
        </div>
        <button
          onClick={triggerSync}
          disabled={isSyncing || systemStatus.status === 'scout_running'}
          className="btn-primary flex items-center gap-2"
        >
          <span className={`material-symbols-outlined text-base ${isSyncing || systemStatus.status === 'scout_running' ? 'animate-spin' : ''}`}>sync</span>
          {isSyncing || systemStatus.status === 'scout_running' ? 'Scouting...' : 'Run Scout'}
        </button>
      </div>

      {/* Server error banner */}
      {serverError && (
        <div className="flex items-center gap-3 bg-error/10 border border-error/20 rounded-xl px-4 py-3">
          <span className="material-symbols-outlined text-error text-base">error</span>
          <span className="text-xs text-error">Cannot connect to server on port 3000. Run <code className="font-mono bg-error/10 px-1 rounded">npm run dev:server</code> to start it.</span>
        </div>
      )}

      {/* Process Pipeline Visual Stepper */}
      <div className="bg-surface-container-lowest border border-outline/10 p-6 rounded-2xl editorial-shadow space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold text-primary uppercase tracking-widest block mb-1">Process Status</span>
            <h2 className="text-xl font-headline font-bold text-on-surface">Automation Pipeline Progress</h2>
          </div>
          <span className={`badge ${
            systemStatus.status === 'completed' ? 'badge-primary' :
            systemStatus.status === 'idle' ? 'badge-secondary' : 'bg-secondary/10 text-secondary'
          }`}>
            {systemStatus.status.toUpperCase().replace('_', ' ')}
          </span>
        </div>

        {/* Stepper Visualization */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Step 1 */}
          <div className={`p-4 rounded-xl border flex items-start gap-3.5 select-none transition-all ${
            systemStatus.status === 'scout_running' ? 'border-primary bg-primary/5 ring-1 ring-primary' : 'border-outline/10 bg-surface-container-low opacity-60'
          }`}>
            <span className={`material-symbols-outlined text-xl ${systemStatus.status === 'scout_running' ? 'text-primary animate-pulse' : 'text-on-surface-variant'}`}>
              search_spark
            </span>
            <div>
              <h4 className="text-sm font-bold text-on-surface leading-tight">Step 1: Scouting & Matching</h4>
              <p className="text-xs text-on-surface-variant mt-0.5">Automated LinkedIn & BuiltIn direct feed analysis</p>
            </div>
          </div>

          {/* Step 2 */}
          <div className={`p-4 rounded-xl border flex items-start gap-3.5 select-none transition-all ${
            systemStatus.status === 'drafting' ? 'border-primary bg-primary/5 ring-1 ring-primary' : 'border-outline/10 bg-surface-container-low opacity-60'
          }`}>
            <span className={`material-symbols-outlined text-xl ${systemStatus.status === 'drafting' ? 'text-primary animate-pulse' : 'text-on-surface-variant'}`}>
              edit_note
            </span>
            <div>
              <h4 className="text-sm font-bold text-on-surface leading-tight">Step 2: Drafting Tailored Assets</h4>
              <p className="text-xs text-on-surface-variant mt-0.5">Generating your Resume, Cover Letter & Cheat Sheet</p>
            </div>
          </div>

          {/* Step 3 */}
          <div className={`p-4 rounded-xl border flex items-start gap-3.5 select-none transition-all ${
            systemStatus.status === 'completed' ? 'border-primary bg-primary/5 ring-1 ring-primary' : 'border-outline/10 bg-surface-container-low opacity-60'
          }`}>
            <span className={`material-symbols-outlined text-xl ${systemStatus.status === 'completed' ? 'text-primary' : 'text-on-surface-variant'}`}>
              check_circle
            </span>
            <div>
              <h4 className="text-sm font-bold text-on-surface leading-tight">Step 3: Ready for Action</h4>
              <p className="text-xs text-on-surface-variant mt-0.5">All processes finished. Check your matches to apply</p>
            </div>
          </div>
        </div>

        {/* Current running activity indicator */}
        <div className="p-4 bg-surface-container rounded-xl flex items-center justify-between border border-outline/5">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-base animate-spin text-primary opacity-80" style={{ display: ['scout_running', 'drafting'].includes(systemStatus.status) ? 'block' : 'none' }}>
              sync
            </span>
            <span className="material-symbols-outlined text-base text-primary" style={{ display: systemStatus.status === 'completed' ? 'block' : 'none' }}>
              done_all
            </span>
            <p className="text-sm text-on-surface font-headline font-bold">
              {systemStatus.current_item || 'No ongoing pipeline process'}
            </p>
          </div>
          {systemStatus.status === 'completed' && (
            <span className="text-xs font-bold text-primary bg-primary/10 px-2.5 py-1 rounded-full flex items-center gap-1 animate-fade-in">
              <span className="material-symbols-outlined text-xs">verified</span> All Processes Complete
            </span>
          )}
        </div>
      </div>

      {/* Grid: Live Process Terminal & Live Pipeline Matches */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        {/* Real-time System Terminal Log */}
        <div className="bg-inverse-surface rounded-2xl overflow-hidden flex flex-col h-[450px] editorial-shadow">
          <div className="bg-on-surface px-5 py-3 flex justify-between items-center">
              <span className="text-[10px] text-inverse-on-surface font-mono uppercase tracking-widest">Pipeline Log Console</span>
              <div className="flex gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-error/60"></div>
                  <div className="w-2.5 h-2.5 rounded-full bg-secondary/60"></div>
                  <div className="w-2.5 h-2.5 rounded-full bg-primary/60"></div>
              </div>
          </div>
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto p-5 font-mono text-[12px] space-y-1.5 applyr-scrollbar"
          >
            {logs.map((log) => (
              <div key={log.id} className="flex gap-3 leading-relaxed group">
                <span className="text-inverse-on-surface/50 whitespace-nowrap">
                  [{new Date(log.timestamp + ' Z').toLocaleTimeString()}]
                </span>
                <span className={`font-bold w-12 ${
                  log.level === 'ERROR' ? 'text-error-container' :
                  log.level === 'WARN' ? 'text-secondary-container' :
                  'text-primary-container'
                }`}>
                  {log.level}
                </span>
                <span className="text-inverse-on-surface/60 w-16">[{log.source}]</span>
                <span className="text-inverse-on-surface break-all">{log.message}</span>
              </div>
            ))}
            {logs.length === 0 && (
              <div className="text-inverse-on-surface/40 animate-pulse italic">Waiting for activity console output...</div>
            )}
          </div>
        </div>

        {/* High-Fit Matches in Current Pipeline */}
        <div className="bg-surface-container-lowest rounded-2xl overflow-hidden flex flex-col h-[450px] border border-outline/10 editorial-shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-headline font-extrabold text-on-surface tracking-tight">Active Matched Roles</h2>
              <p className="text-xs text-on-surface-variant">Matching roles extracted from source feeds passing the gate</p>
            </div>
            <span className="badge badge-secondary">{matchedJobs.length} ready to apply</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-3 pr-1 applyr-scrollbar">
            {matchedJobs.map((job) => (
              <div key={job.id} className="p-4 bg-surface-container-low hover:bg-surface-container rounded-xl flex flex-col gap-1.5 transition-all border border-outline/5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-primary uppercase tracking-widest">{job.company}</span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                    job.status === 'Drafted' ? 'bg-primary/10 text-primary' : 'bg-secondary/10 text-secondary'
                  }`}>
                    {job.status === 'Drafted' ? 'Ready to Apply' : job.status}
                  </span>
                </div>
                <h4 className="text-sm font-headline font-bold text-on-surface leading-tight">
                  {job.title}
                </h4>
                <div className="flex items-center justify-between mt-1 text-xs text-on-surface-variant">
                  <span>Score: {job.score || 'N/A'}</span>
                  <span>Discovered: {new Date(job.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            ))}
            {matchedJobs.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-center opacity-40">
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
