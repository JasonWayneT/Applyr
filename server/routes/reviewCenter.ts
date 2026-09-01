import { Router } from 'express';
import type Database from 'better-sqlite3';
import fs from 'fs';
import { db, logActivity } from '../db.js';
import { requireApiToken } from '../middleware.js';
import { WORK_EXPERIENCE_PATH } from '../shared.js';
import {
  answerReviewItem,
  listReviewItems,
  verifyEvidencePromotion,
  type ReviewAnswer,
} from '../repository/reviewCenterRepository.js';

const ANSWERS = new Set<ReviewAnswer>([
  'CONFIRMED_USE',
  'NOT_PRESENT',
  'UNSURE_NO_REASK',
  'KEEP_ELIGIBLE',
  'CONFIRM_HARD',
  'NEEDS_MORE_INFO',
]);

type ActivityLogger = (
  level: 'INFO' | 'WARN' | 'ERROR',
  source: string,
  message: string,
  meta?: unknown,
) => void;

// Implements FR-285 and AC-370: allow API tests to inject an isolated database.
export function createReviewCenterRouter(
  database: Database.Database = db,
  logger: ActivityLogger = logActivity,
) {
  const router = Router();
  router.use(requireApiToken);

  router.get('/api/review-center/items', (req, res) => {
    try {
      const requestedStatus = typeof req.query.status === 'string' ? req.query.status : 'all';
      if (requestedStatus !== 'all' && requestedStatus !== 'open' && requestedStatus !== 'completed') {
        return res.status(400).json({ error: 'status must be all, open, or completed' });
      }
      return res.json({ items: listReviewItems(requestedStatus, database) });
    } catch (err) {
      console.error(err);
      return res.status(500).json({ error: 'Failed to fetch Review Center items' });
    }
  });

  router.post('/api/review-center/items/:reviewKey/answer', (req, res) => {
    try {
      const reviewKey = req.params.reviewKey;
      if (!reviewKey || reviewKey.length > 200) {
        return res.status(400).json({ error: 'Invalid review item key' });
      }
      const body = req.body ?? {};
      if (!ANSWERS.has(body.answer)) {
        return res.status(400).json({ error: 'Invalid review answer' });
      }
      const result = answerReviewItem(
        reviewKey,
        body.answer,
        body.details,
        body.promoteToVerifiedEvidence === true,
        database,
      );
      if (!result.ok) {
        return res.status(result.notFound ? 404 : 400).json({ error: result.error });
      }
      logger('INFO', 'Review Center', `Review item answered: ${reviewKey}`, {
        event: 'review_center_answered',
        review_key: reviewKey,
        answer: body.answer,
      });
      return res.json({
        success: true,
        status: result.status,
        ...(result.promotionId ? { promotionId: result.promotionId } : {}),
      });
    } catch (err) {
      console.error(err);
      return res.status(500).json({ error: 'Failed to save Review Center answer' });
    }
  });

  router.post('/api/review-center/promotions/:promotionId/verify', (req, res) => {
    // Implements FR-284: source verification is an explicit authenticated action.
    try {
      const promotionId = req.params.promotionId;
      if (!promotionId || promotionId.length > 100) {
        return res.status(400).json({ error: 'Invalid evidence promotion id' });
      }
      const sourceText = fs.existsSync(WORK_EXPERIENCE_PATH)
        ? fs.readFileSync(WORK_EXPERIENCE_PATH, 'utf-8')
        : '';
      const result = verifyEvidencePromotion(promotionId, sourceText, database);
      if (!result.ok) {
        return res.status(result.notFound ? 404 : 409).json({ error: result.error });
      }
      logger('INFO', 'Review Center', `Evidence promotion verified: ${promotionId}`, {
        event: 'review_center_evidence_verified',
        promotion_id: promotionId,
      });
      return res.json({ success: true, status: result.status });
    } catch (err) {
      console.error(err);
      return res.status(500).json({ error: 'Failed to verify evidence promotion' });
    }
  });

  return router;
}

export default createReviewCenterRouter();
