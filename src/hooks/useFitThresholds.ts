import { useEffect, useState } from 'react';
import { apiJson } from '../lib/api';

/**
 * Real fit-score bands from data/fit_rubric_calibration.json (CR-093 evidence-scale engine),
 * served by GET /api/fit-thresholds. Replaces the hardcoded 72/80/60 literals that used to be
 * scattered across SyncActivityView/TodayView/AllJobsView -- those referenced the old,
 * now-deleted scoring system and were never updated when it was replaced (found 2026-08-20).
 *
 * skip_floor: below this, the new engine would Skip the job (weak fit).
 * tier1_floor: at or above this, the new engine calls it Tier 1 (strong fit).
 * Scores in between are Tier 2 (worth a look, not a clear pass).
 */
export interface FitThresholds {
  skip_floor: number;
  tier1_floor: number;
}

// Matches data/fit_rubric_calibration.json's current provisional bands -- used only until the
// real fetch resolves, or if it fails, so the UI never silently falls back to the old numbers.
const DEFAULT_THRESHOLDS: FitThresholds = { skip_floor: 40, tier1_floor: 65 };

export function useFitThresholds(): FitThresholds {
  const [thresholds, setThresholds] = useState<FitThresholds>(DEFAULT_THRESHOLDS);

  useEffect(() => {
    let cancelled = false;
    apiJson<FitThresholds>('/api/fit-thresholds')
      .then((data) => {
        if (!cancelled && typeof data.skip_floor === 'number' && typeof data.tier1_floor === 'number') {
          setThresholds(data);
        }
      })
      .catch(() => { /* keep defaults */ });
    return () => { cancelled = true; };
  }, []);

  return thresholds;
}
