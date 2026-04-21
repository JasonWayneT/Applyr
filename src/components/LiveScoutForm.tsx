import React, { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';

interface ActivityLog {
  id: number;
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR';
  source: string;
  message: string;
}

const LiveScoutForm: React.FC = () => {
  const [isSyncing, setIsSyncing] = useState(false);
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const fetchLogs = async () => {
    try {
      const res = await fetch(api('/api/logs'));
      const data = await res.json();
      // Only show Scout logs here
      const scoutLogs = data.filter((l: any) => l.source === 'Scout');
      setLogs(scoutLogs);
      
      // Auto-scroll
      setTimeout(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
      }, 50);
    } catch (err) {
      console.error('Failed to fetch logs');
    }
  };

  const startScout = async () => {
    setIsSyncing(true);
    try {
      await fetch(api('/api/sync'), { method: 'POST' });
    } catch (err) {
      console.error('Sync trigger failed');
    }
    // We keep isSyncing true until we see a "DONE" or "code 0" in the logs, 
    // but for now a simple timeout or polling is fine.
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-surface-container-lowest rounded-3xl p-8 editorial-shadow space-y-8 animate-fade-in">
      <div className="space-y-4">
        <h2 className="text-2xl font-headline font-extrabold text-on-surface">Live Scouting Engine</h2>
        <p className="text-on-surface-variant text-sm leading-relaxed">
          The engine will search <strong>LinkedIn</strong> and <strong>Built In</strong> for "Product Manager" roles 
          in the United States (Remote) posted in the last 7 days. It uses high-stealth human patterns to 
          ensure account safety.
        </p>
      </div>

      {!isSyncing && (
        <button 
          onClick={startScout}
          className="btn-primary w-full py-4 flex items-center justify-center gap-3 text-lg"
        >
          <span className="material-symbols-outlined">rocket_launch</span>
          Start Automated Scout
        </button>
      )}

      {isSyncing && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 bg-primary rounded-full animate-ping"></div>
              <span className="text-sm font-bold text-on-surface">Engine Running...</span>
            </div>
            <button 
                onClick={() => setIsSyncing(false)}
                className="text-[10px] text-on-surface-variant uppercase tracking-widest hover:text-error"
            >
                Stop Engine
            </button>
          </div>
          
          {/* Terminal view */}
          <div className="bg-inverse-surface rounded-2xl overflow-hidden flex flex-col h-[300px]">
            <div className="bg-on-surface/10 px-4 py-2 flex justify-between items-center border-b border-white/5">
                <span className="text-[10px] text-inverse-on-surface/60 font-mono uppercase">stealth_scout_v3.log</span>
            </div>
            <div 
                ref={scrollRef}
                className="p-4 overflow-y-auto font-mono text-[11px] space-y-1.5 sanctuary-scrollbar"
            >
              {logs.slice(0, 50).reverse().map((log) => (
                <div key={log.id} className="flex gap-2 leading-tight">
                  <span className={`font-bold ${
                    log.level === 'WARN' ? 'text-secondary-container' : 
                    log.level === 'ERROR' ? 'text-error-container' : 
                    'text-primary-container'
                  }`}>
                    {log.message}
                  </span>
                </div>
              ))}
              {logs.length === 0 && (
                <div className="text-inverse-on-surface/30 italic">Initialising environment...</div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="pt-6 border-t border-outline-variant/10">
        <div className="flex items-center gap-4 p-4 bg-surface-container-low rounded-2xl">
          <span className="material-symbols-outlined text-primary">security</span>
          <div>
            <p className="text-xs font-bold text-on-surface">Safety Check</p>
            <p className="text-[10px] text-on-surface-variant">Browser will open in Headed mode. You may be asked to log in manually the first time.</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LiveScoutForm;
