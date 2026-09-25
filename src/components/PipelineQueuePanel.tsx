import React, { useRef, useState } from 'react';
import { usePipelineQueue } from '../hooks/usePipelineQueue';
import { redoPipelineJob, uploadPipelineCsv } from '../lib/pipelineQueue';
import WorkflowOperator from './WorkflowOperator';
import type { PipelineDecisionItem } from '../types/pipelineQueue';

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

function DecisionRow({
  row,
  onOpenJob,
  onRetry,
}: {
  row: PipelineDecisionItem;
  onOpenJob: (jobId: string) => void;
  onRetry: (slug: string) => void;
}) {
  return (
    <div className="w-full p-3 rounded-xl outlined-surface bg-surface-container-lowest">
      <button
        type="button"
        onClick={() => onOpenJob(row.slug)}
        className="w-full text-left"
      >
        <p className="text-sm font-bold text-on-surface">{row.company || row.slug}</p>
        <p className="text-xs text-on-surface-variant mt-1">{row.state}. {row.reason}</p>
      </button>
      {row.canRetry && (
        <button
          type="button"
          onClick={() => onRetry(row.slug)}
          className="btn-secondary min-h-10 mt-2 px-3 rounded-lg text-xs"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export default function PipelineQueuePanel({ onOpenJob }: PipelineQueuePanelProps) {
  const { items, quarantine, isLoading, error, refresh } = usePipelineQueue();
  const [showQuarantine, setShowQuarantine] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const counts = items?.counts;

  async function handleCsvFile(file: File) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setUploadMessage('CSV only.');
      return;
    }
    setUploading(true);
    setUploadMessage(null);
    try {
      const result = await uploadPipelineCsv(file);
      setUploadMessage(
        `Queued ${result.queued}, duplicate ${result.duplicate}, quarantined ${result.quarantined}.`,
      );
      await refresh();
    } catch (err) {
      setUploadMessage(err instanceof Error ? err.message : 'CSV upload failed.');
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  const decisions = items?.decisions ?? [];
  const countState = (state: PipelineDecisionItem['state']) =>
    decisions.filter(row => row.state === state).length;

  async function retryJob(slug: string) {
    setUploadMessage(null);
    try {
      await redoPipelineJob(slug);
      setUploadMessage(`${slug} is queued again. The worker was not started.`);
      await refresh();
    } catch (err) {
      setUploadMessage(err instanceof Error ? err.message : 'This job could not be tried again.');
    }
  }

  return (
    <section
      className="bg-surface-container-low rounded-2xl p-4 outlined-surface"
      aria-label="Pipeline queue"
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <p className="text-sm font-bold text-on-surface">Pipeline queue</p>
          <p className="text-xs text-on-surface-variant mt-1">
            CSV upload lands in data/inbox/csv/, same as a harness drop.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            aria-label="Upload jobs CSV"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void handleCsvFile(file);
            }}
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="btn-secondary min-h-10 px-3 rounded-xl text-xs flex items-center gap-2"
            disabled={isLoading || uploading}
          >
            <span className="material-symbols-outlined text-base">upload</span>
            {uploading ? 'Uploading' : 'Upload CSV'}
          </button>
          <button
            type="button"
            onClick={() => { void refresh(); }}
            className="btn-secondary min-h-10 px-3 rounded-xl text-xs flex items-center gap-2"
            disabled={isLoading || uploading}
          >
            <span className={`material-symbols-outlined text-base ${isLoading ? 'animate-spin' : ''}`}>refresh</span>
            Refresh
          </button>
        </div>
      </div>

      {uploadMessage && (
        <div className="bg-surface-container-lowest rounded-xl px-4 py-3 mb-4 text-sm text-on-surface" role="status">
          {uploadMessage}
        </div>
      )}

      {error && (
        <div role="alert" className="bg-error-container text-on-error-container rounded-xl px-4 py-3 mb-4 text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
        <CountChip label="Continuing" value={countState('Continuing')} />
        <CountChip label="Skipped" value={countState('Skipped')} />
        <CountChip label="Running" value={countState('Running')} />
        <CountChip label="Failed" value={countState('Failed')} />
      </div>

      <div className="space-y-4">
        {(['Continuing', 'Skipped', 'Running', 'Failed'] as const).map(state => {
          const rows = decisions.filter(row => row.state === state);
          return (
            <div key={state}>
              <p className="text-xs font-bold text-on-surface mb-2">{state}</p>
              {rows.length ? (
                <div className="space-y-2">
                  {rows.map(row => (
                    <DecisionRow
                      key={row.slug}
                      row={row}
                      onOpenJob={onOpenJob}
                      onRetry={slug => { void retryJob(slug); }}
                    />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-on-surface-variant">None.</p>
              )}
            </div>
          );
        })}
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

      <details className="mt-4">
        <summary className="text-xs font-bold text-on-surface cursor-pointer">Folder form</summary>
        <div className="mt-3">
          <WorkflowOperator />
        </div>
      </details>
    </section>
  );
}
