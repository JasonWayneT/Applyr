import React, { useState } from 'react';
import { usePipelineQueue } from '../hooks/usePipelineQueue';
import type { PipelineLease, PipelineStuckItem } from '../types/pipelineQueue';

interface PipelineQueuePanelProps {
  onOpenJob: (jobId: string) => void;
}

function CountChip({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-surface-container-lowest rounded-xl p-3 outlined-surface min-w-0">
      <p className="text-[10px] text-on-surface-variant">{label}</p>
      <p className="text-lg font-bold text-on-surface mt-1">{value}</p>
    </div>
  );
}

function LeaseRow({
  row,
  onOpenJob,
}: {
  row: PipelineLease;
  onOpenJob: (jobId: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onOpenJob(row.slug)}
      className="w-full text-left p-3 rounded-xl outlined-surface bg-surface-container-lowest hover:bg-surface-container transition-colors"
    >
      <p className="text-sm font-bold text-on-surface">{row.slug}</p>
      <p className="text-xs text-on-surface-variant mt-1">
        {row.lockedBy || 'unknown worker'} · {row.leaseAgeMinutes} min
      </p>
    </button>
  );
}

function StuckRow({
  row,
  onOpenJob,
}: {
  row: PipelineStuckItem;
  onOpenJob: (jobId: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onOpenJob(row.slug)}
      className="w-full text-left p-3 rounded-xl outlined-surface bg-warning-container text-on-warning-container hover:opacity-90 transition-colors"
    >
      <p className="text-sm font-bold">{row.slug}</p>
      <p className="text-xs mt-1">
        {row.reason === 'expired_lease' ? 'Expired lease' : 'Stale receipt'} · {row.ageMinutes} min
      </p>
    </button>
  );
}

export default function PipelineQueuePanel({ onOpenJob }: PipelineQueuePanelProps) {
  const { items, quarantine, isLoading, error, refresh } = usePipelineQueue();
  const [showQuarantine, setShowQuarantine] = useState(false);
  const counts = items?.counts;

  return (
    <section
      className="bg-surface-container-low rounded-2xl p-4 outlined-surface"
      aria-label="Pipeline queue"
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <p className="text-sm font-bold text-on-surface">Pipeline queue</p>
          <p className="text-xs text-on-surface-variant mt-1">
            Drop-folder depth, leases, stuck work, and quarantine. Read-only.
          </p>
        </div>
        <button
          type="button"
          onClick={() => { void refresh(); }}
          className="btn-secondary min-h-10 px-3 rounded-xl text-xs flex items-center gap-2"
          disabled={isLoading}
        >
          <span className={`material-symbols-outlined text-base ${isLoading ? 'animate-spin' : ''}`}>refresh</span>
          Refresh
        </button>
      </div>

      {error && (
        <div role="alert" className="bg-error-container text-on-error-container rounded-xl px-4 py-3 mb-4 text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 mb-4">
        <CountChip label="Queued" value={counts?.queued ?? 0} />
        <CountChip label="Leased" value={counts?.leased ?? 0} />
        <CountChip label="In progress" value={counts?.in_progress ?? 0} />
        <CountChip label="Paused" value={counts?.paused ?? 0} />
        <CountChip label="Done" value={counts?.done ?? 0} />
        <CountChip label="Quarantined" value={counts?.quarantined ?? 0} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <p className="text-xs font-bold text-on-surface mb-2">Active leases</p>
          {items?.leases.length ? (
            <div className="space-y-2">
              {items.leases.map(row => (
                <LeaseRow key={row.slug} row={row} onOpenJob={onOpenJob} />
              ))}
            </div>
          ) : (
            <p className="text-xs text-on-surface-variant">No active leases.</p>
          )}
        </div>
        <div>
          <p className="text-xs font-bold text-on-surface mb-2">Stuck</p>
          {items?.stuck.length ? (
            <div className="space-y-2">
              {items.stuck.map(row => (
                <StuckRow key={row.slug} row={row} onOpenJob={onOpenJob} />
              ))}
            </div>
          ) : (
            <p className="text-xs text-on-surface-variant">Nothing stuck.</p>
          )}
        </div>
      </div>

      <div className="mt-4">
        <button
          type="button"
          onClick={() => setShowQuarantine(open => !open)}
          className="text-xs font-bold underline text-on-surface"
        >
          Quarantine ({counts?.quarantined ?? quarantine.length}) {showQuarantine ? 'hide' : 'show'}
        </button>
        {showQuarantine && (
          <div className="mt-3 space-y-2">
            {quarantine.length === 0 ? (
              <p className="text-xs text-on-surface-variant">No quarantined rows.</p>
            ) : (
              quarantine.map(row => (
                <div
                  key={row.id}
                  className="bg-surface-container-lowest rounded-xl p-3 outlined-surface text-xs"
                >
                  <p className="font-bold text-on-surface">{row.sourceFile}</p>
                  <p className="text-on-surface-variant mt-1">
                    Line {row.lineNumber ?? '—'} · {row.errorCode}
                  </p>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </section>
  );
}
