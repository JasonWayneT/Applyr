import React from 'react';

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

interface SystemStatus {
  status: string;
  current_item?: string;
}

interface LogsSectionProps {
  logs: LogEntry[];
  loading: boolean;
  systemStatus: SystemStatus | null;
  companyName: string;
}

/** Pipeline Process Logs — extracted from JobDetailPanel (CR-104 Story 1.8). */
const LogsSection: React.FC<LogsSectionProps> = ({ logs, loading, systemStatus, companyName }) => {
  return (
    <section className="border-t border-outline-variant/10 pt-6">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">Pipeline Process Logs</h3>
        {loading && (
          <span className="material-symbols-outlined text-sm animate-spin text-primary">sync</span>
        )}
      </div>
      <p className="text-[10px] text-on-surface-variant italic mb-3">
        Text-matched activity feed — may include entries from unrelated roles.
      </p>

      <div className="bg-inverse-surface rounded-xl p-4 font-mono text-[11px] leading-relaxed overflow-hidden flex flex-col max-h-[180px] overflow-y-auto applyr-scrollbar">
        {systemStatus && ['scout_running', 'evaluate_running', 'drafting'].includes(systemStatus.status) && systemStatus.current_item?.toLowerCase().includes(companyName.toLowerCase()) && (
          <div className="flex gap-2 text-success font-bold animate-pulse border-b border-success/10 pb-1 mb-1">
            <span className="text-success/50 shrink-0">
              [{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}]
            </span>
            <span className="shrink-0">ACTIVE</span>
            <span className="break-words">{systemStatus.current_item}</span>
          </div>
        )}
        {logs.map((log, index) => (
          <div key={index} className="flex gap-2 text-inverse-on-surface/90 border-b border-white/5 pb-1 mb-1 last:border-b-0 last:pb-0 last:mb-0">
            <span className="text-inverse-on-surface/40 shrink-0">
              [{new Date(log.timestamp + ' Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}]
            </span>
            <span className={`font-bold shrink-0 ${
              log.level === 'ERROR' ? 'text-error-container' :
              log.level === 'WARN' ? 'text-warning-container' :
              'text-primary-container'
            }`}>
              {log.level}
            </span>
            <span className="break-words">{log.message}</span>
          </div>
        ))}
        {logs.length === 0 && !loading && (
          <p className="text-inverse-on-surface/40 italic text-center py-2">
            No matching activity logs found. Assets are currently queued or completed.
          </p>
        )}
        {loading && logs.length === 0 && (
          <p className="text-inverse-on-surface/40 animate-pulse italic text-center py-2">
            Loading activity logs...
          </p>
        )}
      </div>
    </section>
  );
};

export default LogsSection;
