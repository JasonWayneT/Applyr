import React from 'react';

interface SkillGapSectionProps {
  skillGap: string | null;
  loading: boolean;
  onAnalyze: () => void;
}

/** Skill Gap Analysis — extracted from JobDetailPanel (CR-104 Story 1.6). */
const SkillGapSection: React.FC<SkillGapSectionProps> = ({ skillGap, loading, onAnalyze }) => {
  return (
    <section className="bg-surface-container-low p-6 rounded-2xl mb-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-secondary">psychology</span>
          <h3 className="text-lg font-headline font-bold text-on-surface">Skill Gap Analysis</h3>
        </div>
        <button
          onClick={onAnalyze}
          disabled={loading}
          className="btn-secondary text-xs flex items-center gap-1"
        >
          <span className="material-symbols-outlined text-sm">{loading ? 'sync' : 'analytics'}</span>
          {loading ? 'Analyzing...' : 'Analyze Now'}
        </button>
      </div>
      {skillGap && (
        <div className="p-4 bg-inverse-surface rounded-xl text-inverse-on-surface text-sm font-mono whitespace-pre-wrap">
          {skillGap}
        </div>
      )}
      {!skillGap && !loading && (
        <p className="text-xs text-on-surface-variant">
          Run a localized analysis comparing your experience against this job description to identify missing hard skills.
        </p>
      )}
    </section>
  );
};

export default SkillGapSection;
