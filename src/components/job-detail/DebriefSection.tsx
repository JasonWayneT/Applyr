import React from 'react';
import {
  INTERVIEW_DEBRIEF_OUTCOMES,
  isValidDebriefOutcome,
  type InterviewDebrief,
} from 'shared/domain/interviewDebrief';

export interface DebriefFormState {
  date: string;
  notes: string;
  outcome: InterviewDebrief['outcome'] | '';
}

export interface DebriefFieldErrors {
  date?: boolean;
  notes?: boolean;
  outcome?: boolean;
}

function RequiredLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-[10px] font-bold text-on-surface uppercase tracking-widest mb-1.5">
      {children}
      <span className="text-error ml-0.5" aria-hidden="true">*</span>
    </label>
  );
}

interface DebriefSectionProps {
  debriefs: InterviewDebrief[];
  loadingDebriefs: boolean;
  form: DebriefFormState;
  formErrors: DebriefFieldErrors;
  saving: boolean;
  editingId: string | null;
  error: string | null;
  onFormChange: (form: DebriefFormState) => void;
  onFormErrorChange: (errors: DebriefFieldErrors) => void;
  onSave: () => void;
  onResetForm: () => void;
  onStartEdit: (debrief: InterviewDebrief) => void;
  onDelete: (debriefId: string) => void;
}

/** Interview Debrief — extracted from JobDetailPanel (CR-104 Story 1.4). */
const DebriefSection: React.FC<DebriefSectionProps> = ({
  debriefs,
  loadingDebriefs,
  form,
  formErrors,
  saving,
  editingId,
  error,
  onFormChange,
  onFormErrorChange,
  onSave,
  onResetForm,
  onStartEdit,
  onDelete,
}) => {
  const debriefInputClass = (invalid: boolean) =>
    `input-applyr w-full text-sm rounded-xl py-2.5 px-4 bg-surface-container-lowest ${
      invalid ? 'ring-2 ring-error/50 border-error/40' : ''
    }`;

  return (
    <section className="bg-secondary/5 p-6 rounded-2xl border border-secondary/10">
      <div className="flex items-center gap-3 mb-4">
        <span className="material-symbols-outlined text-secondary">forum</span>
        <h3 className="text-lg font-headline font-bold text-on-surface">Interview Debrief</h3>
      </div>
      <p className="text-[11px] text-on-surface-variant mb-1 leading-relaxed">
        Capture what they asked and how it went while it is fresh. This is separate from your prep cheat sheet.
      </p>
      <p className="text-[10px] text-on-surface-variant mb-4">
        Fields marked <span className="text-error font-bold">*</span> are required.
      </p>
      <div className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <RequiredLabel>Interview date</RequiredLabel>
            <input
              type="date"
              value={form.date}
              onChange={(e) => {
                onFormChange({ ...form, date: e.target.value });
                onFormErrorChange({ ...formErrors, date: false });
              }}
              className={debriefInputClass(!!formErrors.date)}
              aria-invalid={formErrors.date || undefined}
              required
            />
            {formErrors.date && (
              <p className="text-[10px] text-error mt-1">Interview date is required.</p>
            )}
          </div>
          <div>
            <RequiredLabel>Outcome</RequiredLabel>
            <select
              value={form.outcome}
              onChange={(e) => {
                const value = e.target.value;
                onFormChange({
                  ...form,
                  outcome: isValidDebriefOutcome(value) ? value : '',
                });
                onFormErrorChange({ ...formErrors, outcome: false });
              }}
              className={debriefInputClass(!!formErrors.outcome)}
              aria-invalid={formErrors.outcome || undefined}
              required
            >
              <option value="" disabled>Select how it went…</option>
              {INTERVIEW_DEBRIEF_OUTCOMES.map(o => (
                <option key={o} value={o}>{o}</option>
              ))}
            </select>
            {formErrors.outcome && (
              <p className="text-[10px] text-error mt-1">Select an outcome before saving.</p>
            )}
          </div>
        </div>
        <div>
          <RequiredLabel>Notes</RequiredLabel>
          <textarea
            value={form.notes}
            onChange={(e) => {
              onFormChange({ ...form, notes: e.target.value });
              onFormErrorChange({ ...formErrors, notes: false });
            }}
            rows={6}
            placeholder="Questions they asked, your answers, gaps, vibe, anything worth remembering..."
            className={`${debriefInputClass(!!formErrors.notes)} py-3 resize-y min-h-[120px]`}
            aria-invalid={formErrors.notes || undefined}
            required
          />
          {formErrors.notes && (
            <p className="text-[10px] text-error mt-1">Notes are required.</p>
          )}
        </div>
        {error && (
          <p className="text-[11px] text-error">{error}</p>
        )}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onSave}
            disabled={saving}
            className="btn-primary text-xs px-4 py-2 rounded-xl disabled:opacity-50"
          >
            {saving ? 'Saving...' : editingId ? 'Update debrief' : 'Save debrief'}
          </button>
          {editingId && (
            <button
              type="button"
              onClick={onResetForm}
              className="text-xs text-on-surface-variant hover:text-on-surface"
            >
              Cancel edit
            </button>
          )}
        </div>
      </div>

      <div className="mt-6 pt-5 border-t border-outline-variant/10">
        <h4 className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-3">Past debriefs</h4>
        {loadingDebriefs ? (
          <p className="text-xs text-on-surface-variant italic">Loading...</p>
        ) : debriefs.length === 0 ? (
          <p className="text-xs text-on-surface-variant italic">No debriefs yet for this role.</p>
        ) : (
          <div className="space-y-3">
            {debriefs.map(d => (
              <div key={d.id} className="bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/10">
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div>
                    <p className="text-xs font-bold text-on-surface">
                      {new Date(d.date).toLocaleDateString([], { dateStyle: 'medium' })}
                    </p>
                    <span className="text-[10px] font-bold text-secondary">{d.outcome}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => onStartEdit(d)}
                      className="text-[10px] font-bold text-primary hover:underline"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(d.id)}
                      className="text-[10px] font-bold text-error hover:underline"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <p className="text-sm text-on-surface-variant whitespace-pre-wrap leading-relaxed">{d.notes}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
};

export default DebriefSection;
