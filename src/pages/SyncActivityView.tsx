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

const SyncActivityView: React.FC = () => {
  const [logs, setLogs] = useState<ActivityLog[]>([]);
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
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-8 pb-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-headline font-extrabold text-on-surface tracking-tight">Scout</h1>
          <p className="text-on-surface-variant mt-1">Discover new roles across 6 sources. Real-time visibility into each run.</p>
        </div>
        <button
          onClick={triggerSync}
          disabled={isSyncing}
          className="btn-primary flex items-center gap-2"
        >
          <span className={`material-symbols-outlined text-base ${isSyncing ? 'animate-spin' : ''}`}>sync</span>
          {isSyncing ? 'Scouting...' : 'Run Scout'}
        </button>
      </div>

      {/* Server error banner */}
      {serverError && (
        <div className="flex items-center gap-3 bg-error/10 border border-error/20 rounded-xl px-4 py-3">
          <span className="material-symbols-outlined text-error text-base">error</span>
          <span className="text-xs text-error">Cannot connect to server on port 3000. Run <code className="font-mono bg-error/10 px-1 rounded">npm run dev:server</code> to start it.</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Stats */}
        <div className="bg-surface-container-lowest rounded-2xl p-6 editorial-shadow">
          <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1">Gate Rejections</p>
          <p className="text-3xl font-headline font-extrabold text-error">
            {logs.filter(l => l.level === 'WARN').length}
          </p>
        </div>
        <div className="bg-surface-container-lowest rounded-2xl p-6 editorial-shadow">
          <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1">Jobs Found (High-Fit)</p>
          <p className="text-3xl font-headline font-extrabold text-primary">
            {logs.filter(l => l.message.includes('High-Fit')).length}
          </p>
        </div>
      </div>

      {/* Terminal Log */}
      <div className="bg-inverse-surface rounded-2xl overflow-hidden flex flex-col h-[500px] editorial-shadow">
        <div className="bg-on-surface px-5 py-3 flex justify-between items-center">
            <span className="text-[10px] text-inverse-on-surface font-mono uppercase tracking-widest">Scout System Log v1.0</span>
            <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-error/60"></div>
                <div className="w-2.5 h-2.5 rounded-full bg-secondary/60"></div>
                <div className="w-2.5 h-2.5 rounded-full bg-primary/60"></div>
            </div>
        </div>
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto p-5 font-mono text-[12px] space-y-1.5 sanctuary-scrollbar"
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
            <div className="text-inverse-on-surface/40 animate-pulse italic">Waiting for activity...</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SyncActivityView;
