import { useCallback, useEffect, useMemo, useState } from 'react';
import { answerReviewItem, fetchReviewQueue, verifyEvidencePromotion } from '../lib/reviewCenter';
import type { ReviewAnswerPayload, ReviewItem } from '../types/reviewCenter';

export function useReviewCenter() {
  // Implements FR-285: keep queue state and answer refresh behavior in one client hook.
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [available, setAvailable] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetchReviewQueue();
      setAvailable(result.available);
      setItems(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Review Center could not load.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const answer = useCallback(async (itemId: string, payload: ReviewAnswerPayload) => {
    await answerReviewItem(itemId, payload);
    await refresh();
  }, [refresh]);

  const verifyPromotion = useCallback(async (promotionId: string) => {
    await verifyEvidencePromotion(promotionId);
    await refresh();
  }, [refresh]);

  const pendingCount = useMemo(
    () => items.filter(item => item.status === 'open').length,
    [items],
  );

  return {
    items,
    available,
    isLoading,
    error,
    pendingCount,
    refresh,
    answer,
    verifyPromotion,
  };
}
