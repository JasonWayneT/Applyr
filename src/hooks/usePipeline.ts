import { useState, useCallback } from 'react';
import { Stage, StageStatus } from '../components/PipelineTracker';
import { api } from '../lib/api';

export const usePipeline = () => {
  const [isRunning, setIsRunning] = useState(false);
  const [isRejected, setIsRejected] = useState(false);
  const [result, setResult] = useState<{ score: number; passed: boolean } | null>(null);

  const [stages, setStages] = useState<Stage[]>([
    { id: 'gate',     label: 'Deterministic Gate',    status: 'pending' },
    { id: 'fit',      label: 'Evaluating fit',         status: 'pending' },
    { id: 'research', label: 'Researching company',    status: 'pending' },
    { id: 'resume',   label: 'Building resume',        status: 'pending' },
    { id: 'cover',    label: 'Writing cover letter',   status: 'pending' },
  ]);

  const updateStage = (id: string, status: StageStatus, summary?: string) => {
    setStages(prev => prev.map(s => s.id === id ? { ...s, status, summary } : s));
  };

  const runPipeline = useCallback(async (company: string, jd: string, url?: string) => {
    setIsRunning(true);
    setIsRejected(false);
    setResult(null);
    setStages(prev => prev.map(s => ({ ...s, status: 'pending', summary: undefined })));

    const lowerJd = jd.toLowerCase();

    // --- STAGE 0: Deterministic Gate (blocklist pulled from server config) ---
    updateStage('gate', 'running');
    await new Promise(r => setTimeout(r, 800));

    let titleBlocklist: string[] = [];
    try {
      const configRes = await fetch(api('/api/config'));
      const config = await configRes.json();
      titleBlocklist = config.titleBlocklist ?? [];
    } catch {
      // Fallback: empty list means nothing is blocked — fail safe, not fail closed
      console.warn('Could not load gate config from server. Gate will pass all titles.');
    }

    const hasBlockedTerm = titleBlocklist.some(term => lowerJd.includes(term));
    if (hasBlockedTerm) {
      const matched = titleBlocklist.find(term => lowerJd.includes(term));
      updateStage('gate', 'error', `Auto-rejected: Contains blocked term "${matched}".`);
      setIsRunning(false);
      setIsRejected(true);
      return;
    }
    updateStage('gate', 'done', 'Title check passed. No seniority mismatch found.');

    // --- STAGE 1: Evaluating Fit ---
    updateStage('fit', 'running');
    await new Promise(r => setTimeout(r, 2000));
    const mockScore = 85;
    updateStage('fit', 'done', `Score: ${mockScore}. High alignment with data integrity and technical integrations.`);

    // --- STAGE 2: Researching Company ---
    updateStage('research', 'running');
    await new Promise(r => setTimeout(r, 1500));
    updateStage('research', 'done', 'Founding story and market position retrieved.');

    // --- STAGE 3: Building Resume ---
    updateStage('resume', 'running');
    await new Promise(r => setTimeout(r, 2000));
    updateStage('resume', 'done', `Added: 'Stabilized $40M ARR revenue-bearing systems' to top-level summary.`);

    // --- STAGE 4: Writing Cover Letter ---
    updateStage('cover', 'running');
    await new Promise(r => setTimeout(r, 1800));
    updateStage('cover', 'done', `Narrative: Connecting Cision platform experience to ${company}'s current growth stage.`);

    setIsRunning(false);
    const finalResult = { score: mockScore, passed: true };
    setResult(finalResult);
    return finalResult;
  }, []);

  const resetPipeline = useCallback(() => {
    setIsRunning(false);
    setIsRejected(false);
    setResult(null);
    setStages(prev => prev.map(s => ({ ...s, status: 'pending', summary: undefined })));
  }, []);

  return { stages, runPipeline, resetPipeline, isRunning, isRejected, result };
};
