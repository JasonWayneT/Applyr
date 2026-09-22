import React, { useEffect, useMemo, useState } from 'react';
import WorkflowOperator from '../components/WorkflowOperator';
import PipelineQueuePanel from '../components/PipelineQueuePanel';
import { decisionBasisLabel, hasMinimumEvidence, SKILL_ANSWER_HELPERS } from '../lib/reviewCenter';
import type {
  EvidenceDetails,
  ReviewAnswer,
  ReviewAnswerPayload,
  ReviewItem,
} from '../types/reviewCenter';

type QueueView = 'needs_answer' | 'strengthen' | 'completed';

interface ReviewCenterViewProps {
  items: ReviewItem[];
  isLoading: boolean;
  available: boolean;
  error: string | null;
  onRefresh: () => void;
  onAnswer: (itemId: string, payload: ReviewAnswerPayload) => Promise<void>;
  onVerifyPromotion: (promotionId: string) => Promise<void>;
  onOpenJob: (jobId: string) => void;
}

const EMPTY_DETAILS: EvidenceDetails = {
  context: '',
  activity: '',
  timeframe: '',
  scope: '',
  outcome: '',
};

const QUEUE_LABELS: Array<{ id: QueueView; label: string }> = [
  { id: 'needs_answer', label: 'Needs your answer' },
  { id: 'strengthen', label: 'Strengthen evidence' },
  { id: 'completed', label: 'Completed' },
];

function itemBelongsToQueue(item: ReviewItem, queue: QueueView): boolean {
  if (queue === 'completed') return item.status === 'completed';
  if (item.status === 'completed') return false;
  if (queue === 'strengthen') {
    return item.type === 'evidence_enrichment' || item.evidenceStatus === 'incomplete' || item.evidenceStatus === 'ready';
  }
  return item.type === 'skill_presence' || item.type === 'hard_gate_review';
}

function itemTypeLabel(item: ReviewItem): string {
  if (item.type === 'hard_gate_review') return 'Hard-gate review';
  if (item.type === 'evidence_enrichment') return 'Evidence prompt';
  return 'Skill confirmation';
}

function itemTypeIcon(item: ReviewItem): string {
  if (item.type === 'hard_gate_review') return 'warning';
  if (item.type === 'evidence_enrichment') return 'playlist_add_check';
  return 'help';
}

function buildEvidencePreview(details: EvidenceDetails, title: string): string {
  const activity = details.activity.trim();
  const context = details.context.trim();
  const timeframe = details.timeframe.trim();
  return `Used ${title} ${context ? `at ${context}` : ''}${timeframe ? ` during ${timeframe}` : ''} to ${activity}.`
    .replace(/\s+/g, ' ')
    .replace(' to .', '.')
    .trim();
}

function EmptyState({ title, body, icon = 'task_alt' }: { title: string; body: string; icon?: string }) {
  return (
    <div className="bg-surface-container-lowest rounded-2xl outlined-surface p-10 text-center">
      <div className="w-14 h-14 rounded-full bg-primary-container text-on-primary-container flex items-center justify-center mx-auto mb-4">
        <span className="material-symbols-outlined text-3xl">{icon}</span>
      </div>
      <h2 className="text-xl font-headline font-bold text-on-surface">{title}</h2>
      <p className="text-sm text-on-surface-variant max-w-md mx-auto mt-2 leading-relaxed">{body}</p>
    </div>
  );
}

function ReviewQueueRow({
  item,
  selected,
  onSelect,
}: {
  item: ReviewItem;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? 'true' : undefined}
      className={`w-full text-left p-4 rounded-xl transition-colors outlined-surface ${
        selected
          ? 'bg-surface-container-lowest border-primary/50'
          : 'bg-surface-container-lowest border-outline-variant hover:border-outline hover:bg-surface-container'
      }`}
    >
      <div className="flex items-start gap-3">
        <span className={`material-symbols-outlined text-lg mt-0.5 ${
          item.type === 'hard_gate_review' ? 'text-warning' : 'text-primary'
        }`}>
          {itemTypeIcon(item)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center justify-between gap-2">
            <span className="text-sm font-bold text-on-surface truncate">{item.title}</span>
            {item.status === 'completed' && (
              <span className="material-symbols-outlined text-success text-base" aria-label="Completed">check_circle</span>
            )}
          </span>
          <span className="block text-[11px] text-on-surface-variant mt-1">{itemTypeLabel(item)}</span>
          <span className="block text-xs text-on-surface-variant mt-2 line-clamp-2">{item.question}</span>
          {item.affectedOpportunities.length > 0 && (
            <span className="block text-[11px] text-on-surface-variant mt-3">
              {item.affectedOpportunities.length} affected {item.affectedOpportunities.length === 1 ? 'opportunity' : 'opportunities'}
            </span>
          )}
        </span>
      </div>
    </button>
  );
}

function EvidenceFields({
  details,
  onChange,
}: {
  details: EvidenceDetails;
  onChange: (field: keyof EvidenceDetails, value: string) => void;
}) {
  const fields: Array<{ key: keyof EvidenceDetails; label: string; placeholder: string; wide?: boolean }> = [
    { key: 'context', label: 'Where did you use it?', placeholder: 'Company, project, or work context' },
    { key: 'activity', label: 'What did you personally do?', placeholder: 'Describe the hands-on work' },
    { key: 'timeframe', label: 'When did you use it?', placeholder: 'Approximate dates or duration' },
    { key: 'scope', label: 'What was the scope?', placeholder: 'Team, workflow, scale, or ownership', wide: true },
    { key: 'outcome', label: 'What changed as a result?', placeholder: 'Optional outcome or metric', wide: true },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {fields.map(field => (
        <label key={field.key} className={field.wide ? 'sm:col-span-2' : ''}>
          <span className="block text-xs font-bold text-on-surface mb-1.5">{field.label}</span>
          <input
            value={details[field.key]}
            onChange={event => onChange(field.key, event.target.value)}
            placeholder={field.placeholder}
            className="input-applyr w-full text-sm"
          />
        </label>
      ))}
    </div>
  );
}

const SKILL_ANSWER_OPTIONS: ReadonlyArray<{ value: ReviewAnswer; label: string; helper: string }> = [
  { value: 'CONFIRMED_USE', label: "Yes, I've used it", helper: SKILL_ANSWER_HELPERS.CONFIRMED_USE },
  { value: 'NOT_PRESENT', label: 'Not in my history', helper: SKILL_ANSWER_HELPERS.NOT_PRESENT },
  { value: 'UNSURE_NO_REASK', label: 'Not sure', helper: SKILL_ANSWER_HELPERS.UNSURE_NO_REASK },
  { value: 'BAD_DATA', label: 'Not a real skill', helper: SKILL_ANSWER_HELPERS.BAD_DATA },
];

const ANSWER_LABELS: Record<ReviewAnswer, string> = {
  CONFIRMED_USE: "Yes, I've used it",
  NOT_PRESENT: 'Not in my history',
  UNSURE_NO_REASK: 'Not sure',
  BAD_DATA: 'Not a real skill',
  KEEP_ELIGIBLE: 'Keep eligible',
  CONFIRM_HARD: 'Confirm hard',
  NEEDS_MORE_INFO: 'Need more information',
};

function SkillAnswerPad({
  saving,
  onSelect,
}: {
  saving: boolean;
  onSelect: (value: ReviewAnswer) => void;
}) {
  // Implements FR-288: one tap saves the answer; there is no separate save step.
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {SKILL_ANSWER_OPTIONS.map(option => (
        <button
          key={option.value}
          type="button"
          onClick={() => onSelect(option.value)}
          disabled={saving}
          className={`min-h-12 rounded-xl px-4 py-3 text-left outlined-surface transition-colors disabled:opacity-50 ${
            option.value === 'BAD_DATA'
              ? 'bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container'
              : 'bg-surface-container-low hover:bg-surface-container-high'
          }`}
        >
          <span className="block text-sm font-bold">{option.label}</span>
          <span className="block text-[11px] mt-1 opacity-80">{option.helper}</span>
        </button>
      ))}
    </div>
  );
}

function ReviewDetail({
  item,
  onAnswer,
  onVerifyPromotion,
  onOpenJob,
}: {
  item: ReviewItem;
  onAnswer: (payload: ReviewAnswerPayload) => Promise<void>;
  onVerifyPromotion: (promotionId: string) => Promise<void>;
  onOpenJob: (jobId: string) => void;
}) {
  const [details, setDetails] = useState<EvidenceDetails>(EMPTY_DETAILS);
  const [showEvidencePreview, setShowEvidencePreview] = useState(false);
  const [changingAnswer, setChangingAnswer] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDetails(EMPTY_DETAILS);
    setShowEvidencePreview(false);
    setChangingAnswer(false);
    setSaving(false);
    setError(null);
  }, [item.id]);

  const canReviewEvidence = hasMinimumEvidence(details);
  const showAnswerPad = item.status === 'open' || changingAnswer;

  const saveAnswer = async (selectedAnswer: ReviewAnswer, promote = false) => {
    if (promote && !canReviewEvidence) {
      setError('Add where, what, and when before promoting this to verified evidence.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onAnswer({
        answer: selectedAnswer,
        details: item.type === 'evidence_enrichment' ? details : undefined,
        promoteToVerifiedEvidence: promote,
      });
      setChangingAnswer(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The answer could not be saved.');
    } finally {
      setSaving(false);
    }
  };

  return (
    // Implements FR-288: the keyed remount plus card-swap animation is the
    // visible transition into the next card in the queue.
    <div className="card-applyr space-y-8 animate-card-swap">
      <div className="flex items-start justify-between gap-4">
        <div>
          <span className={`badge ${item.type === 'hard_gate_review' ? 'bg-warning-container text-on-warning-container' : 'badge-primary'}`}>
            {itemTypeLabel(item)}
          </span>
          <h2 className="text-2xl font-headline font-extrabold text-on-surface mt-3">{item.title}</h2>
        </div>
        {item.status === 'completed' && (
          <span className="chip bg-success-container text-on-success-container shrink-0">
            <span className="material-symbols-outlined text-sm">check</span>
            Resolved
          </span>
        )}
      </div>

      <div>
        <p className="text-lg font-semibold text-on-surface leading-relaxed">{item.question}</p>
        <p className="text-sm text-on-surface-variant leading-relaxed mt-3">{item.summary}</p>
      </div>

      {(item.requirement || item.evidenceExcerpt || item.decisionBasis || item.uncertainty) && (
        <div className="bg-surface-container-low rounded-xl p-5 space-y-4">
          {item.requirement && (
            <div>
              <p className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant">Job requirement</p>
              <p className="text-sm text-on-surface mt-1 leading-relaxed">{item.requirement}</p>
            </div>
          )}
          {item.evidenceExcerpt && (
            <div>
              <p className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant">What Applyr found</p>
              <p className="text-sm text-on-surface mt-1 leading-relaxed">{item.evidenceExcerpt}</p>
            </div>
          )}
          {item.decisionBasis && (
            <div>
              <p className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant">{decisionBasisLabel(item.type)}</p>
              <p className="text-sm text-on-surface mt-1 leading-relaxed">{item.decisionBasis}</p>
            </div>
          )}
          {item.uncertainty && (
            <div>
              <p className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant">Uncertainty</p>
              <p className="text-sm text-on-surface mt-1 leading-relaxed">{item.uncertainty.replace(/_/g, ' ')}</p>
            </div>
          )}
        </div>
      )}

      {item.affectedOpportunities.length > 0 && (
        <section aria-labelledby="affected-opportunities-heading">
          <div className="flex items-center justify-between gap-3 mb-3">
            <h3 id="affected-opportunities-heading" className="text-xs uppercase tracking-widest font-bold text-on-surface-variant">
              Affected opportunities
            </h3>
            <span className="text-xs text-on-surface-variant">{item.affectedOpportunities.length} total</span>
          </div>
          <div className="space-y-2">
            {item.affectedOpportunities.map(opportunity => (
              <div key={opportunity.jobId} className="flex items-center gap-3 bg-surface-container-low rounded-xl px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-bold text-on-surface truncate">{opportunity.company}</p>
                  <p className="text-xs text-on-surface-variant truncate">{opportunity.title}</p>
                </div>
                {opportunity.status && <span className="text-[10px] text-on-surface-variant hidden sm:block">{opportunity.status}</span>}
                <button
                  type="button"
                  onClick={() => onOpenJob(opportunity.jobId)}
                  className="min-h-10 px-3 rounded-lg text-xs font-bold text-primary hover:bg-primary-container transition-colors shrink-0"
                >
                  Open job
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {showAnswerPad && item.type === 'hard_gate_review' && (
        <div className="space-y-4">
          <div className="bg-warning-container text-on-warning-container rounded-xl p-4">
            <p className="text-sm font-bold">This decision affects whether the opportunity can continue.</p>
            <p className="text-xs mt-1 leading-relaxed">
              Keep it eligible to continue weighted scoring, confirm the hard requirement to disqualify it, or request more information.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {([
              ['KEEP_ELIGIBLE', 'Keep eligible', 'Continue scoring', 'btn-primary'],
              ['CONFIRM_HARD', 'Confirm hard', 'Disqualify this job', 'btn-secondary text-error'],
              ['NEEDS_MORE_INFO', 'Need more information', 'Leave it paused', 'btn-secondary'],
            ] as const).map(([value, label, helper, className]) => (
              <button
                key={value}
                type="button"
                onClick={() => {
                  void saveAnswer(value);
                }}
                className={`${className} min-h-12 rounded-xl px-4 text-left disabled:opacity-50`}
                disabled={saving}
              >
                <span className="block text-sm font-bold">{label}</span>
                <span className="block text-[11px] mt-1 opacity-80">{helper}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {showAnswerPad && item.type === 'skill_presence' && (
        <div className="space-y-4">
          <div>
            <h3 className="text-xs uppercase tracking-widest font-bold text-on-surface-variant mb-3">Your answer</h3>
            <SkillAnswerPad saving={saving} onSelect={value => { void saveAnswer(value); }} />
          </div>
          <p className="text-xs text-on-surface-variant leading-relaxed">
            One tap saves and opens the next card. A Yes can get where/what/when detail later under
            Strengthen evidence, and any answer can be corrected from Completed.
          </p>
        </div>
      )}

      {showAnswerPad && item.type === 'evidence_enrichment' && (
        <div className="space-y-5">
          <div className="bg-surface-container-low rounded-2xl p-5 space-y-5">
            <div>
              <h3 className="text-sm font-bold text-on-surface">Add optional context</h3>
              <p className="text-xs text-on-surface-variant mt-1 leading-relaxed">
                A Yes is enough to remember that you used this skill. Add where, what, and when if you want it to support stronger job requirements later.
              </p>
            </div>
            <EvidenceFields
              details={details}
              onChange={(field, value) => setDetails(previous => ({ ...previous, [field]: value }))}
            />
            {canReviewEvidence && (
              <div className="bg-success-container text-on-success-container rounded-xl p-4 space-y-3">
                <div className="flex items-start gap-2">
                  <span className="material-symbols-outlined text-base mt-0.5">check_circle</span>
                  <div>
                    <p className="text-sm font-bold">Enough context for an evidence review</p>
                    <p className="text-xs mt-1 leading-relaxed">
                      Review the proposed wording before deciding whether to add it to verified evidence.
                    </p>
                  </div>
                </div>
                {!showEvidencePreview ? (
                  <button
                    type="button"
                    onClick={() => setShowEvidencePreview(true)}
                    className="min-h-10 px-3 rounded-lg bg-surface-container-lowest text-success text-xs font-bold hover:bg-surface-container transition-colors"
                  >
                    Review evidence preview
                  </button>
                ) : (
                  <div className="bg-surface-container-lowest rounded-xl p-4">
                    <p className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant">Proposed evidence</p>
                    <p className="text-sm text-on-surface mt-2 leading-relaxed">
                      {buildEvidencePreview(details, item.title)}
                      {details.scope.trim() ? ` Scope: ${details.scope.trim()}.` : ''}
                      {details.outcome.trim() ? ` Outcome: ${details.outcome.trim()}.` : ''}
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        void saveAnswer('CONFIRMED_USE', true);
                      }}
                      className="btn-primary min-h-10 mt-4 px-4 rounded-lg text-xs"
                      disabled={saving}
                    >
                      Submit for source verification
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          <div>
            <h3 className="text-xs uppercase tracking-widest font-bold text-on-surface-variant mb-3">Your answer</h3>
            <SkillAnswerPad saving={saving} onSelect={value => { void saveAnswer(value); }} />
          </div>
          <p className="text-xs text-on-surface-variant leading-relaxed">
            Your answer is stored for future opportunities using the same skill.
          </p>
        </div>
      )}

      {item.status === 'completed' && !changingAnswer && (
        <div className="space-y-4">
          {item.promotionStatus === 'PENDING_SOURCE_UPDATE' && item.promotionId ? (
            <PromotionVerification
              promotionId={item.promotionId}
              onVerify={onVerifyPromotion}
              onError={setError}
            />
          ) : (
            <div className="bg-success-container text-on-success-container rounded-xl p-4 flex items-start gap-2">
              <span className="material-symbols-outlined text-base mt-0.5">check_circle</span>
              <p className="text-sm leading-relaxed">
                This review item is complete. Its decision is available to future Stage 0 runs.
                {item.promotionStatus === 'VERIFIED' ? ' The evidence is verified in the source of truth.' : ''}
              </p>
            </div>
          )}
          {/* Implements FR-289: a completed card stays correctable in place. */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            {item.answer ? (
              <p className="text-sm text-on-surface-variant">
                Your answer: <span className="font-bold text-on-surface">{ANSWER_LABELS[item.answer]}</span>
              </p>
            ) : <span />}
            <button
              type="button"
              onClick={() => setChangingAnswer(true)}
              className="btn-secondary min-h-10 px-4 rounded-xl text-sm shrink-0"
            >
              Change answer
            </button>
          </div>
        </div>
      )}

      {error && (
        <p role="alert" className="text-sm text-error bg-error-container rounded-xl px-4 py-3">
          {error}
        </p>
      )}
    </div>
  );
}

function PromotionVerification({
  promotionId,
  onVerify,
  onError,
}: {
  promotionId: string;
  onVerify: (promotionId: string) => Promise<void>;
  onError: (message: string | null) => void;
}) {
  // Implements FR-284: present the source-update boundary instead of implying automatic promotion.
  const [saving, setSaving] = useState(false);
  return (
    <div className="bg-warning-container text-on-warning-container rounded-xl p-4 space-y-3">
      <div className="flex items-start gap-2">
        <span className="material-symbols-outlined text-base mt-0.5">pending_actions</span>
        <div>
          <p className="text-sm font-bold">Source update still needs verification</p>
          <p className="text-xs mt-1 leading-relaxed">
            The details are saved as a proposal only. Add the same context, activity, and timeframe to workExperience.md, then verify the source update here.
          </p>
        </div>
      </div>
      <button
        type="button"
        className="btn-primary min-h-10 px-4 rounded-lg text-xs"
        disabled={saving}
        onClick={async () => {
          setSaving(true);
          onError(null);
          try {
            await onVerify(promotionId);
          } catch (err) {
            onError(err instanceof Error ? err.message : 'The source update could not be verified.');
          } finally {
            setSaving(false);
          }
        }}
      >
        {saving ? 'Verifying...' : 'Verify source update'}
      </button>
    </div>
  );
}

const ReviewCenterView: React.FC<ReviewCenterViewProps> = ({
  items,
  isLoading,
  available,
  error,
  onRefresh,
  onAnswer,
  onVerifyPromotion,
  onOpenJob,
}) => {
  // Implements FR-285: render the focused Review Center queue and evidence workflow.
  const [queue, setQueue] = useState<QueueView>('needs_answer');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const counts = useMemo(() => ({
    needs_answer: items.filter(item => itemBelongsToQueue(item, 'needs_answer')).length,
    strengthen: items.filter(item => itemBelongsToQueue(item, 'strengthen')).length,
    completed: items.filter(item => itemBelongsToQueue(item, 'completed')).length,
  }), [items]);

  const visibleItems = useMemo(
    () => items.filter(item => itemBelongsToQueue(item, queue)),
    [items, queue],
  );

  useEffect(() => {
    if (visibleItems.length === 0) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !visibleItems.some(item => item.id === selectedId)) {
      setSelectedId(visibleItems[0].id);
    }
  }, [selectedId, visibleItems]);

  const selectedItem = visibleItems.find(item => item.id === selectedId) ?? null;

  // Implements FR-288: a saved answer advances straight to the next card in the
  // queue. Corrections made from the Completed queue stay on the same card.
  const handleAnswer = async (item: ReviewItem, payload: ReviewAnswerPayload) => {
    const index = visibleItems.findIndex(candidate => candidate.id === item.id);
    const next = index >= 0 ? visibleItems[index + 1] ?? null : null;
    await onAnswer(item.id, payload);
    if (queue !== 'completed' && next) {
      setSelectedId(next.id);
    }
  };

  const renderQueue = () => (
    <section className="bg-surface-container-low rounded-2xl p-3 outlined-surface" aria-label="Review Center queue">
      <div className="px-3 pt-2 pb-3">
        <p className="text-[10px] uppercase tracking-widest font-bold text-on-surface-variant">Review Center</p>
        <p className="text-xs text-on-surface-variant mt-1 leading-relaxed">Work through one decision at a time.</p>
      </div>
      <div className="space-y-1 mb-3" role="tablist" aria-label="Review categories">
        {QUEUE_LABELS.map(option => (
          <button
            key={option.id}
            type="button"
            role="tab"
            aria-selected={queue === option.id}
            onClick={() => setQueue(option.id)}
            className={`w-full flex items-center justify-between min-h-10 rounded-xl px-3 text-sm transition-colors ${
              queue === option.id
                ? 'bg-surface-container-lowest text-on-surface font-bold outlined-surface'
                : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
            }`}
          >
            <span>{option.label}</span>
            <span className={`badge ${queue === option.id ? 'badge-primary' : 'bg-surface-container-highest text-on-surface-variant'}`}>
              {counts[option.id]}
            </span>
          </button>
        ))}
      </div>
      <div className="space-y-2 max-h-[620px] overflow-y-auto applyr-scrollbar pr-1" role="list">
        {visibleItems.map(item => (
          <ReviewQueueRow
            key={item.id}
            item={item}
            selected={item.id === selectedId}
            onSelect={() => setSelectedId(item.id)}
          />
        ))}
      </div>
    </section>
  );

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <p className="text-[10px] uppercase tracking-widest font-bold text-primary mb-2">Decision queue</p>
          <h1 className="text-3xl font-headline font-extrabold text-on-surface tracking-tight">Review Center</h1>
          <p className="text-on-surface-variant mt-2 max-w-2xl leading-relaxed">
            Resolve the questions that keep opportunities from moving forward. You decide what Applyr can remember and use.
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          className="btn-secondary min-h-10 px-4 rounded-xl text-sm flex items-center gap-2 self-start lg:self-auto"
          disabled={isLoading}
        >
          <span className={`material-symbols-outlined text-base ${isLoading ? 'animate-spin' : ''}`}>refresh</span>
          Refresh
        </button>
      </div>

      <WorkflowOperator />

      <PipelineQueuePanel onOpenJob={onOpenJob} />

      {error && (
        <div role="alert" className="bg-error-container text-on-error-container rounded-xl px-4 py-3 flex items-center gap-3">
          <span className="material-symbols-outlined text-lg">error</span>
          <p className="text-sm flex-1">{error}</p>
          <button type="button" onClick={onRefresh} className="text-xs font-bold underline">Try again</button>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center h-64 text-on-surface-variant text-sm gap-2">
          <span className="material-symbols-outlined animate-spin">progress_activity</span>
          Loading review items...
        </div>
      ) : error ? (
        <EmptyState
          icon="cloud_off"
          title="Review Center could not connect"
          body="Your review decisions are not available right now. Try refreshing before continuing."
        />
      ) : !available ? (
        <EmptyState
          icon="fact_check"
          title="Review Center is ready"
          body="Questions will appear here when Stage 0 needs your input. The confirmation service is not enabled in this build yet."
        />
      ) : items.length === 0 ? (
        <EmptyState
          title="You are all caught up"
          body="There are no open decisions or evidence prompts right now. Applyr will bring questions here instead of interrupting your job workflow."
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(240px,0.36fr)_minmax(0,1fr)] gap-6 items-start">
          {renderQueue()}
          {selectedItem ? (
            <ReviewDetail
              key={selectedItem.id}
              item={selectedItem}
              onAnswer={payload => handleAnswer(selectedItem, payload)}
              onVerifyPromotion={onVerifyPromotion}
              onOpenJob={onOpenJob}
            />
          ) : (
            <EmptyState
              icon="task_alt"
              title={queue === 'completed' ? 'Nothing completed yet' : 'This queue is clear'}
              body={queue === 'completed'
                ? 'Answered items land here, where you can revisit or correct any of them.'
                : 'Every question in this queue has an answer. Completed holds anything you want to revisit.'}
            />
          )}
        </div>
      )}
    </div>
  );
};

export default ReviewCenterView;
