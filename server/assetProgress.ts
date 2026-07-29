/**
 * Shared asset-creation progress: updates system_status and broadcasts SSE.
 */
import { db } from './db.js';
import { broadcastSyncEvent } from './routes/pipeline.js';

const DRAFT_STAGES = new Set(['drafting', 'research', 'resume', 'cover', 'audit', 'pdf', 'done']);
const EVAL_STAGES = new Set(['evaluating', 'fit_llm', 'gate', 'fit']);

export type AssetProgressPayload = {
  company: string;
  stage: string;
  status: 'pending' | 'running' | 'done' | 'error';
  summary?: string;
  completed?: number;
  total?: number;
  current_item?: string;
  pipeline_status?: 'evaluate_running' | 'drafting';
};

function mapBatchPhaseToStage(phase: string): string {
  if (phase === 'evaluating' || phase === 'fit_llm') return 'fit';
  if (phase === 'drafting') return 'research';
  if (['research', 'resume', 'cover', 'audit', 'pdf', 'gate', 'fit'].includes(phase)) return phase;
  if (phase === 'done') return 'cover';
  return phase;
}

function pipelineStatusForStage(stage: string, batchPhase?: string): 'evaluate_running' | 'drafting' {
  if (batchPhase && DRAFT_STAGES.has(batchPhase) && batchPhase !== 'done') return 'drafting';
  if (['research', 'resume', 'cover', 'audit', 'pdf', 'done'].includes(stage)) return 'drafting';
  if (EVAL_STAGES.has(stage)) return 'evaluate_running';
  return 'evaluate_running';
}

export function publishAssetProgress(payload: AssetProgressPayload): void {
  const currentItem =
    payload.current_item ??
    (payload.summary
      ? `${payload.company}: ${payload.summary}`
      : `${payload.company} — ${payload.stage.replace(/_/g, ' ')}`);

  const status = payload.pipeline_status ?? pipelineStatusForStage(payload.stage);

  db.prepare(`
    UPDATE system_status SET
      status = ?,
      current_item = ?,
      items_completed = COALESCE(?, items_completed),
      items_total = COALESCE(?, items_total),
      updated_at = CURRENT_TIMESTAMP
    WHERE id = 'global'
  `).run(status, currentItem, payload.completed ?? null, payload.total ?? null);

  broadcastSyncEvent('asset_progress', {
    ...payload,
    current_item: currentItem,
    pipeline_status: status,
  });
}

export function parseBatchProgressLine(line: string): AssetProgressPayload | null {
  if (!line.startsWith('[BATCH_PROGRESS]')) return null;
  const completed = line.match(/completed=(\d+)/);
  const total = line.match(/total=(\d+)/);
  const current = line.match(/current=([^\s]+)/);
  const phase = line.match(/phase=(\w+)/);
  if (!current || !phase) return null;

  const phaseVal = phase[1];
  const skipPhases = new Set([
    'starting', 'skipped', 'duplicate', 'keyword_reject', 'onsite_reject',
    'fit_error', 'rejected',
  ]);
  if (skipPhases.has(phaseVal)) return null;

  const stage = mapBatchPhaseToStage(phaseVal);
  const isDone = phaseVal === 'done';
  return {
    company: current[1],
    stage,
    status: isDone ? 'done' : 'running',
    completed: completed ? Number(completed[1]) : undefined,
    total: total ? Number(total[1]) : undefined,
    current_item: `Job ${completed?.[1] ?? '?'}/${total?.[1] ?? '?'}: ${current[1]} (${phaseVal.replace(/_/g, ' ')})`,
    pipeline_status: pipelineStatusForStage(stage, phaseVal),
  };
}

export function parseAssetProgressLine(line: string): AssetProgressPayload | null {
  if (!line.startsWith('[ASSET_PROGRESS]')) return null;
  const company = line.match(/company=([^\s]+)/);
  const stage = line.match(/stage=(\w+)/);
  const summary = line.match(/summary=(.+)$/);
  if (!company || !stage) return null;

  const stageVal = stage[1];
  return {
    company: company[1],
    stage: stageVal === 'done' ? 'cover' : stageVal,
    status: stageVal === 'done' ? 'done' : 'running',
    summary: summary?.[1]?.trim(),
    pipeline_status: pipelineStatusForStage(stageVal),
  };
}

export function parseJsonStageLine(line: string, company: string): AssetProgressPayload | null {
  try {
    const parsed = JSON.parse(line) as { id?: string; status?: string; summary?: string };
    if (!parsed.id || !parsed.status) return null;
    const status = parsed.status as AssetProgressPayload['status'];
    if (!['pending', 'running', 'done', 'error'].includes(status)) return null;
    return {
      company,
      stage: parsed.id,
      status,
      summary: parsed.summary,
      pipeline_status: pipelineStatusForStage(parsed.id),
    };
  } catch {
    return null;
  }
}
