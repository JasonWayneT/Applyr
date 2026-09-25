import React from 'react';

interface MatchSummarySectionProps {
  summary?: string | null;
  scoreTotal?: number | null;
  score?: number | null;
  scoreBreakdownJson?: string | null;
  reasonSummary?: string | null;
}

/** Match Summary + Scoring Transparency — extracted from JobDetailPanel (CR-104 Story 1.5). */
const MatchSummarySection: React.FC<MatchSummarySectionProps> = ({
  summary,
  scoreTotal,
  score,
  scoreBreakdownJson,
  reasonSummary,
}) => {
  return (
    <>
      {summary && (
        <section>
          <h3 className="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-3">Match Summary</h3>
          <p className="text-sm text-on-surface-variant leading-relaxed bg-surface-container-lowest p-4 rounded-xl">
            {summary}
          </p>
        </section>
      )}

      <section className="bg-surface-container-low p-6 rounded-2xl">
        <h3 className="text-lg font-headline font-bold text-on-surface mb-3 flex items-center justify-between">
          <span>Scoring Transparency</span>
          <span className="text-sm bg-primary/20 text-primary px-2.5 py-0.5 rounded-full font-mono">
            {scoreTotal !== undefined && scoreTotal !== null
              ? `${scoreTotal}/100`
              : score
                ? `Score: ${score}`
                : 'Unscored'}
          </span>
        </h3>

        {scoreBreakdownJson ? (() => {
          try {
            const b = JSON.parse(scoreBreakdownJson) as Record<string, number>;
            const metrics = [
              { label: 'Role Family Match', key: 'role_family_match', max: 30 },
              { label: 'Domain Match', key: 'domain_match', max: 20 },
              { label: 'Seniority Match', key: 'seniority_match', max: 15 },
              { label: 'Work Arrangement', key: 'work_arrangement', max: 15 },
              { label: 'Company Desirability', key: 'company_desirability', max: 10 },
              { label: 'Location Compatibility', key: 'location_compatibility', max: 5 },
              { label: 'Compensation Signal', key: 'compensation_signal', max: 5 },
            ];

            return (
              <div className="space-y-3 mt-4">
                {metrics.map(m => {
                  const val = b[m.key] ?? b[m.label] ?? 0;
                  const pct = Math.min(100, Math.max(0, (val / m.max) * 100));
                  return (
                    <div key={m.key} className="space-y-1">
                      <div className="flex justify-between text-[11px] font-bold text-on-surface-variant">
                        <span>{m.label}</span>
                        <span>{val} / {m.max}</span>
                      </div>
                      <div className="h-1.5 bg-surface-container rounded-full overflow-hidden">
                        <div
                          className="h-full bg-secondary rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
                {reasonSummary && (
                  <div className="mt-4 pt-3 border-t border-outline-variant/10 text-xs text-on-surface-variant italic leading-relaxed">
                    {reasonSummary}
                  </div>
                )}
              </div>
            );
          } catch {
            return <p className="text-xs text-on-surface-variant italic">Failed to parse score breakdown details.</p>;
          }
        })() : (
          <p className="text-xs text-on-surface-variant italic">
            {score
              ? `Score: ${score} available — detailed breakdown not yet generated for this role.`
              : 'Not yet scored.'}
          </p>
        )}
      </section>
    </>
  );
};

export default MatchSummarySection;
