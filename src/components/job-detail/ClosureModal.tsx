import React from 'react';

interface Progression {
  label: string;
  next: string;
  icon: string;
}

interface ClosureData {
  stage: string;
  type: 'Ghosted' | 'Rejected' | 'Withdrawn' | 'Other' | 'Self-Rejected' | 'No Longer Available';
  notes: string;
}

interface ClosureModalProps {
  show: boolean;
  closureData: ClosureData;
  onClose: () => void;
  onClosureDataChange: (data: ClosureData) => void;
  onConfirm: (newStatus: string, payload: Record<string, unknown>) => void;
  progression?: Progression;
  onProgression: () => void;
  errorMsg: string | null;
}

/** Footer closure modal + progression button — extracted from JobDetailPanel (CR-104 Story 1.9). */
const ClosureModal: React.FC<ClosureModalProps> = ({
  show,
  closureData,
  onClose,
  onClosureDataChange,
  onConfirm,
  progression,
  onProgression,
  errorMsg,
}) => {
  return (
    <div className="p-6 border-t border-outline-variant/10">
      {errorMsg && (
        <p className="text-xs text-error flex items-center gap-1.5 mb-3">
          <span className="material-symbols-outlined text-sm">error</span>
          {errorMsg}
        </p>
      )}
      {show ? (
        <div className="space-y-4 animate-fade-in">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="closure-stage-input" className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">Last Stage</label>
              <select
                id="closure-stage-input"
                value={closureData.stage}
                onChange={e => onClosureDataChange({ ...closureData, stage: e.target.value })}
                className="input-applyr w-full text-xs rounded-lg py-2"
              >
                {['Backlog', 'Applied', 'Recruiter Screen', 'Core Interviews', 'Offer and Negotiation'].map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div className="col-span-2">
              <span className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">Outcome</span>
              <div className="flex flex-wrap gap-1.5">
                {[
                  { value: 'Rejected', label: 'Closed', color: 'bg-status-closed-bg text-status-closed-text border border-outline-variant' },
                  { value: 'Ghosted', label: 'Ghosted', color: 'bg-status-closed-bg text-status-closed-text border border-outline-variant' },
                  { value: 'Self-Rejected', label: 'Self-Reject (Not a Fit)', color: 'bg-warning-container text-on-warning-container border border-warning/30' },
                  { value: 'No Longer Available', label: 'No Longer Available', color: 'bg-status-closed-bg text-status-closed-text border border-outline-variant' }
                ].map(t => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => onClosureDataChange({ ...closureData, type: t.value as ClosureData['type'] })}
                    className={`px-3 py-2 rounded-lg text-[10px] font-bold transition-all ${
                      closureData.type === t.value
                        ? t.color
                        : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div>
            <label htmlFor="closure-notes-input" className="block text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1.5">
              {closureData.type === 'Self-Rejected' ? 'Critique & Feedback (Why is this not a fit?)' : 'Notes (Optional)'}
            </label>
            <textarea
              id="closure-notes-input"
              placeholder={
                closureData.type === 'Self-Rejected'
                  ? "e.g., Criteria needs to weigh legacy tech stack, or solo PM role..."
                  : "e.g., Compensation mismatch, Role closed..."
              }
              value={closureData.notes}
              onChange={e => onClosureDataChange({ ...closureData, notes: e.target.value })}
              rows={3}
              className="input-applyr w-full text-xs rounded-lg py-2 px-3 resize-none focus:outline-none"
            />
          </div>
          <div className="flex gap-3 pt-2">
            <button
              onClick={onClose}
              className="flex-1 py-2.5 text-xs font-bold text-on-surface-variant hover:text-on-surface transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                if (closureData.type === 'No Longer Available') {
                  onConfirm('No Longer Available', {
                    rejection_stage: closureData.stage,
                    rejection_type: closureData.type,
                    outcome_notes: closureData.notes
                  });
                } else {
                  onConfirm('Closed', {
                    rejection_stage: closureData.stage,
                    rejection_type: closureData.type,
                    outcome_notes: closureData.notes
                  });
                }
              }}
              className={`flex-1 py-2.5 rounded-xl text-xs font-bold shadow-md hover:opacity-90 transition-all text-white ${
                closureData.type === 'Self-Rejected' ? 'bg-warning' :
                'bg-tertiary'
              }`}
            >
              {closureData.type === 'No Longer Available' ? 'Confirm Deletion' :
               closureData.type === 'Self-Rejected' ? 'Self-Reject Role' :
               'Confirm Closure'}
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-center justify-between">
          <button
            onClick={onClose}
            className="text-xs text-error hover:text-error-dim transition-colors font-medium flex items-center gap-1.5"
          >
            <span className="material-symbols-outlined text-sm">archive</span>
            Close & Archive
          </button>

          {progression && (
            <button
              onClick={onProgression}
              className="btn-primary text-sm flex items-center gap-2"
            >
              <span className="material-symbols-outlined text-sm">{progression.icon}</span>
              {progression.label}
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default ClosureModal;
