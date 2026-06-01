import { useState, useCallback } from 'react';
import { Stage, StageStatus } from '../components/PipelineTracker';
import { apiFetch } from '../lib/api';
import { parseSseChunk } from '../lib/sse';

export const usePipeline = () => {
  const [isRunning, setIsRunning] = useState(false);
  const [isRejected, setIsRejected] = useState(false);
  const [result, setResult] = useState<{ 
    score: number; 
    passed: boolean;
    company?: string;
    title?: string;
    url?: string;
    summary?: string;
  } | null>(null);

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

  const runPipeline = useCallback(async (company: string, jd: string, url?: string): Promise<{ 
    score: number; 
    passed: boolean;
    company?: string;
    title?: string;
    url?: string;
    summary?: string;
  } | undefined> => {
    setIsRunning(true);
    setIsRejected(false);
    setResult(null);
    setStages(prev => prev.map(s => ({ ...s, status: 'pending', summary: undefined })));

    return new Promise((resolve) => {
      apiFetch('/api/evaluate', {
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
          const parsed = parseSseChunk(buffer);
          buffer = parsed.remainder;

          for (const { event: eventName, data: payload } of parsed.events) {
            if (eventName === 'stage' && payload && typeof payload === 'object') {
              const stage = payload as { id: string; status: StageStatus; summary?: string };
              updateStage(stage.id, stage.status, stage.summary);
              if (stage.status === 'error') {
                setIsRunning(false);
                setIsRejected(true);
                resolve(undefined);
                return;
              }
            } else if (eventName === 'done' && payload && typeof payload === 'object') {
              const done = payload as {
                score?: number;
                passed?: boolean;
                company?: string;
                title?: string;
                url?: string;
                summary?: string;
              };
              const finalResult = {
                score: done.score ?? 0,
                passed: done.passed ?? false,
                company: done.company,
                title: done.title,
                url: done.url,
                summary: done.summary,
              };
              setIsRunning(false);
              setResult(finalResult);
              resolve(finalResult);
              return;
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
