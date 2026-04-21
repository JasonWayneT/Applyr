import { useState, useCallback } from 'react';
import { Stage, StageStatus } from '../components/PipelineTracker';
import { api } from '../lib/api';

export const usePipeline = () => {
  const [isRunning, setIsRunning] = useState(false);
  const [isRejected, setIsRejected] = useState(false);
  const [result, setResult] = useState<{ score: number; passed: boolean } | null>(null);

  const [stages, setStages] = useState<Stage[]>([
    { id: 'gate',     label: 'Deterministic Gate',  status: 'pending' },
    { id: 'fit',      label: 'Evaluating fit',       status: 'pending' },
    { id: 'research', label: 'Researching company',  status: 'pending' },
    { id: 'resume',   label: 'Building resume',      status: 'pending' },
    { id: 'cover',    label: 'Writing cover letter', status: 'pending' },
  ]);

  const updateStage = useCallback((id: string, status: StageStatus, summary?: string) => {
    setStages(prev => prev.map(s => s.id === id ? { ...s, status, summary } : s));
  }, []);

  const runPipeline = useCallback(async (company: string, jd: string, url?: string): Promise<{ score: number; passed: boolean } | undefined> => {
    setIsRunning(true);
    setIsRejected(false);
    setResult(null);
    setStages(prev => prev.map(s => ({ ...s, status: 'pending', summary: undefined })));

    return new Promise((resolve) => {
      const evtSource = new EventSource(
        api(`/api/evaluate?company=${encodeURIComponent(company)}&url=${encodeURIComponent(url ?? '')}`),
      );

      // POST the JD body via fetch first, then stream via SSE
      // (SSE is GET-only — we use a two-step approach: POST to queue, then GET to stream)
      fetch(api('/api/evaluate'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company, jd, url }),
      }).then(async (res) => {
        const reader = res.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          setIsRunning(false);
          setIsRejected(true);
          resolve(undefined);
          return;
        }

        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const blocks = buffer.split('\n\n');
          buffer = blocks.pop() ?? '';

          for (const block of blocks) {
            if (!block.startsWith('event:')) continue;
            const lines = block.split('\n');
            const eventName = lines[0].replace('event: ', '').trim();
            const dataLine = lines.find(l => l.startsWith('data:'));
            if (!dataLine) continue;

            try {
              const payload = JSON.parse(dataLine.replace('data: ', ''));

              if (eventName === 'stage') {
                updateStage(payload.id, payload.status, payload.summary);
                if (payload.status === 'error') {
                  setIsRunning(false);
                  setIsRejected(true);
                  resolve(undefined);
                  return;
                }
              } else if (eventName === 'done') {
                const finalResult = { score: payload.score ?? 0, passed: payload.passed ?? false };
                setIsRunning(false);
                setResult(finalResult);
                resolve(finalResult);
                return;
              }
            } catch {
              // Non-JSON line — ignore
            }
          }
        }

        // Stream ended without a 'done' event
        setIsRunning(false);
        resolve(undefined);
      }).catch((err) => {
        console.error('Pipeline fetch error:', err);
        setIsRunning(false);
        setIsRejected(true);
        resolve(undefined);
      });
    });
  }, [updateStage]);

  const resetPipeline = useCallback(() => {
    setIsRunning(false);
    setIsRejected(false);
    setResult(null);
    setStages(prev => prev.map(s => ({ ...s, status: 'pending', summary: undefined })));
  }, []);

  return { stages, runPipeline, resetPipeline, isRunning, isRejected, result };
};
