import { useCallback, useEffect, useState } from 'react';
import { fetchPipelineQuarantine, fetchPipelineQueueStats } from '../lib/pipelineQueue';
import type { PipelineQueueStats, PipelineQuarantineRow } from '../types/pipelineQueue';

export function usePipelineQueue() {
  const [items, setItems] = useState<PipelineQueueStats | null>(null);
  const [quarantine, setQuarantine] = useState<PipelineQuarantineRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [stats, rows] = await Promise.all([
        fetchPipelineQueueStats(),
        fetchPipelineQuarantine(),
      ]);
      setItems(stats);
      setQuarantine(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Pipeline queue could not load.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    items,
    quarantine,
    isLoading,
    error,
    refresh,
  };
}
