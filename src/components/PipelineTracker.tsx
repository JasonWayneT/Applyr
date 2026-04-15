import React from 'react';

interface PipelineTrackerProps {
  stages: Stage[];
}

export type StageStatus = 'pending' | 'running' | 'done' | 'error';

export interface Stage {
  id: string;
  label: string;
  status: StageStatus;
  summary?: string;
}

const PipelineTracker: React.FC<PipelineTrackerProps> = ({ stages }) => {
  return (
    <div className="space-y-6 relative">
      <div className="absolute left-3 top-3 bottom-3 w-px bg-outline-variant/20"></div>
      {stages.map((stage) => (
        <div key={stage.id} className="flex gap-4 relative animate-slide-up">
          {/* Step Indicator */}
          <div className={`w-6 h-6 rounded-full flex items-center justify-center z-10 shrink-0 transition-all duration-300 ${
            stage.status === 'done' ? 'bg-primary' :
            stage.status === 'running' ? 'bg-secondary ring-4 ring-secondary-container/50 animate-pulse' :
            stage.status === 'error' ? 'bg-error' :
            'bg-surface-container-highest border border-outline-variant'
          }`}>
            {stage.status === 'done' && <span className="material-symbols-outlined text-white text-[14px]">check</span>}
            {stage.status === 'error' && <span className="material-symbols-outlined text-white text-[14px]">close</span>}
            {stage.status === 'running' && <span className="material-symbols-outlined text-white text-[14px]">sync</span>}
          </div>

          {/* Content */}
          <div className={`flex-1 ${stage.status === 'pending' ? 'opacity-40' : ''}`}>
            <p className={`text-sm font-bold ${
              stage.status === 'error' ? 'text-error' :
              stage.status === 'running' ? 'text-secondary' :
              'text-on-surface'
            }`}>{stage.label}</p>
            {stage.summary && (
              <p className={`text-xs mt-1 leading-relaxed ${
                stage.status === 'error' ? 'text-error/80' : 'text-on-surface-variant'
              }`}>{stage.summary}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

export default PipelineTracker;
