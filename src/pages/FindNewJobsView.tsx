import React, { useState, useEffect } from 'react';
import JDInputForm from '../components/JDInputForm';
import BulkUploadForm, { ParsedJob } from '../components/BulkUploadForm';
import PipelineTracker from '../components/PipelineTracker';
import { usePipeline } from '../hooks/usePipeline';

const FindNewJobsView: React.FC = () => {
  const { stages, runPipeline, resetPipeline, isRunning, isRejected, result } = usePipeline();
  const [resetKey, setResetKey] = useState(0);
  const [isAdded, setIsAdded] = useState(false);

  const [inputMode, setInputMode] = useState<'single' | 'bulk'>('single');
  const [batchProgress, setBatchProgress] = useState<{current: number, total: number, passed: number} | null>(null);

  const handleBatchRun = async (jobs: ParsedJob[]) => {
    setBatchProgress({ current: 1, total: jobs.length, passed: 0 });

    let localPassed = 0;
    for (let i = 0; i < jobs.length; i++) {
      setBatchProgress(prev => prev ? { ...prev, current: i + 1 } : null);

      const res = await runPipeline(jobs[i].company, jobs[i].jd, jobs[i].url);

      if (res && res.passed) {
        localPassed += 1;
        setBatchProgress(prev => prev ? { ...prev, passed: localPassed } : null);
      }

      // Artificial delay between jobs
      await new Promise(r => setTimeout(r, 1500));
      resetPipeline();
    }

    // Batch complete
    setBatchProgress(prev => prev ? { ...prev, current: prev.total + 1 } : null);
    setIsAdded(true);
    setTimeout(() => {
      setBatchProgress(null);
      setIsAdded(false);
      setResetKey(prev => prev + 1);
    }, 4000);
  };

  useEffect(() => {
    let timeout: NodeJS.Timeout;
    if (inputMode === 'single' && result && result.passed && !isRunning && !isAdded) {
      setIsAdded(true);
      timeout = setTimeout(() => {
        resetPipeline();
        setResetKey(prev => prev + 1);
        setIsAdded(false);
      }, 2500);
    }
    return () => clearTimeout(timeout);
  }, [result, isRunning, isAdded, resetPipeline]);

  return (
    <div className="space-y-8 pb-20">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-headline font-extrabold text-on-surface tracking-tight">Find new jobs</h1>
          <p className="text-on-surface-variant mt-1">Generate tailored assets for your next high-fit role.</p>
        </div>

        <div className="flex p-1 bg-surface-container-low rounded-xl">
          <button
            onClick={() => setInputMode('single')}
            disabled={isRunning || batchProgress !== null}
            className={`px-4 py-1.5 text-sm rounded-lg transition-colors font-medium ${inputMode === 'single' ? 'bg-surface-container-lowest text-on-surface editorial-shadow' : 'text-on-surface-variant hover:text-on-surface'} disabled:opacity-50`}
          >
            Single Paste
          </button>
          <button
            onClick={() => setInputMode('bulk')}
            disabled={isRunning || batchProgress !== null}
            className={`px-4 py-1.5 text-sm rounded-lg transition-colors font-medium ${inputMode === 'bulk' ? 'bg-surface-container-lowest text-on-surface editorial-shadow' : 'text-on-surface-variant hover:text-on-surface'} disabled:opacity-50`}
          >
            CSV Bulk Upload
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
        {/* Left: Input */}
        <div className="space-y-6">
          {inputMode === 'single' ? (
            <JDInputForm key={resetKey} onRun={runPipeline} isLoading={isRunning} />
          ) : (
            <BulkUploadForm key={`bulk-${resetKey}`} onBatchRun={handleBatchRun} isLoading={batchProgress !== null} />
          )}
        </div>

        {/* Right: Pipeline Status */}
        <div className="space-y-8">
          <div className="bg-surface-container-lowest rounded-3xl p-8 min-h-[500px] flex flex-col editorial-shadow">
            <h3 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-8">Pipeline Tracking</h3>

            {!isRunning && !result && !isRejected && !isAdded && !batchProgress && (
              <div className="flex-1 flex flex-col items-center justify-center text-center space-y-4 opacity-40">
                <div className="w-14 h-14 rounded-2xl bg-surface-container flex items-center justify-center">
                  <span className="material-symbols-outlined text-2xl text-on-surface-variant">verified_user</span>
                </div>
                <div>
                  <p className="text-sm font-headline font-bold text-on-surface">No active session</p>
                  <p className="text-xs text-on-surface-variant mt-1">
                    {inputMode === 'single' ? "Paste a JD and click 'Run' to begin." : "Upload a CSV to batch process roles."}
                  </p>
                </div>
              </div>
            )}

            {batchProgress && batchProgress.current <= batchProgress.total && (
              <div className="mb-8 p-5 bg-primary-container/30 rounded-2xl relative overflow-hidden">
                 <div className="absolute top-0 left-0 h-1 bg-primary transition-all duration-300 rounded-full" style={{ width: `${(batchProgress.current / batchProgress.total) * 100}%` }}></div>
                 <h4 className="text-sm font-headline font-bold text-primary">Processing Bulk List...</h4>
                 <p className="text-xs mt-1 text-on-surface-variant">Evaluating job {batchProgress.current} of {batchProgress.total}</p>
                 <div className="mt-4 pt-4 border-t border-outline-variant/10 flex items-center justify-between">
                   <p className="text-xs text-on-surface-variant">Matches found:</p>
                   <span className="badge badge-primary">{batchProgress.passed} added</span>
                 </div>
              </div>
            )}

            {(isRunning || result || isRejected) && (
              <div className="flex-1">
                <PipelineTracker stages={stages} />
              </div>
            )}

            {result && result.passed && !isRunning && inputMode === 'single' && (
              <div className="mt-8 pt-8 border-t border-outline-variant/10 animate-slide-up">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1">Match Result</p>
                    <div className="flex items-center gap-2">
                       <span className="text-3xl font-headline font-extrabold text-primary">{result.score}%</span>
                       <span className="badge badge-primary">High Fit</span>
                    </div>
                  </div>
                  {isAdded ? (
                    <button className="btn-primary bg-primary/80 min-w-[150px]" disabled>
                      <span className="flex items-center justify-center gap-2">
                        <span className="material-symbols-outlined text-base">check</span>
                        Added to Pipeline!
                      </span>
                    </button>
                  ) : (
                    <button className="btn-primary" onClick={() => setIsAdded(true)}>
                      Add to my pipeline
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-3">
                  {['Resume', 'Cover Letter', 'Cheat Sheet'].map(asset => (
                    <button key={asset} className="btn-secondary flex flex-col items-center gap-2 py-4 rounded-xl">
                      <span className="material-symbols-outlined text-on-surface-variant text-base">download</span>
                      <span className="text-[10px] uppercase tracking-widest font-bold">{asset}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Bulk Completion State */}
            {isAdded && inputMode === 'bulk' && batchProgress && batchProgress.current > batchProgress.total && (
              <div className="mt-8 pt-8 border-t border-outline-variant/10 animate-slide-up flex flex-col items-center justify-center text-center">
                 <div className="w-16 h-16 bg-primary-container rounded-full flex items-center justify-center text-primary mb-4">
                   <span className="material-symbols-outlined text-3xl" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                 </div>
                 <h2 className="text-2xl font-headline font-extrabold text-on-surface mb-2">Batch Complete</h2>
                 <p className="text-on-surface-variant mb-6">Pipeline evaluated {batchProgress.total} roles.</p>
                 <div className="bg-surface-container px-6 py-3 rounded-xl flex items-center gap-4">
                    <span className="text-sm font-bold text-on-surface">Auto-saved matches:</span>
                    <span className="text-primary font-extrabold text-xl font-headline">{batchProgress.passed}</span>
                 </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default FindNewJobsView;
