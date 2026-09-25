import React from 'react';
import type { Contact } from '../../types/contact';

const CONTACT_TYPE_LABELS: Record<Contact['contact_type'], string> = {
  hiring_manager: 'Hiring manager',
  warm_connection: 'Warm connection',
  informational: 'Informational',
};

export interface ContactFormState {
  contact_name: string;
  contact_title: string;
  contact_type: Contact['contact_type'] | '';
  source: string;
}

export const EMPTY_CONTACT_FORM: ContactFormState = {
  contact_name: '',
  contact_title: '',
  contact_type: '',
  source: '',
};

interface ContactsSectionProps {
  contacts: Contact[];
  loading: boolean;
  showAddForm: boolean;
  formState: ContactFormState;
  saving: boolean;
  error: string | null;
  onToggleAddForm: (show: boolean) => void;
  onFormChange: (form: ContactFormState) => void;
  onSave: () => void;
  onCancel: () => void;
}

/** Contacts — extracted from JobDetailPanel (CR-104 Story 1.3). */
const ContactsSection: React.FC<ContactsSectionProps> = ({
  contacts,
  loading,
  showAddForm,
  formState,
  saving,
  error,
  onToggleAddForm,
  onFormChange,
  onSave,
  onCancel,
}) => {
  return (
    <section className="bg-surface-container-low p-6 rounded-2xl">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-secondary">group</span>
          <h3 className="text-lg font-headline font-bold text-on-surface">Contacts</h3>
        </div>
        {!showAddForm && (
          <button
            type="button"
            onClick={() => onToggleAddForm(true)}
            className="btn-secondary text-xs flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-sm">person_add</span>
            Add contact
          </button>
        )}
      </div>

      {loading ? (
        <p className="text-xs text-on-surface-variant italic">Loading...</p>
      ) : contacts.length === 0 && !showAddForm ? (
        <p className="text-xs text-on-surface-variant italic">No contacts logged for this role yet.</p>
      ) : (
        <div className="space-y-3 mb-4">
          {contacts.map(c => (
            <div key={c.id} className="bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/10">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold text-on-surface">{c.contact_name}</p>
                  {c.contact_title && (
                    <p className="text-xs text-on-surface-variant">{c.contact_title}</p>
                  )}
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="text-[10px] font-bold text-secondary bg-secondary-container/40 px-2 py-0.5 rounded-md">
                    {CONTACT_TYPE_LABELS[c.contact_type]}
                  </span>
                  {!c.confirmed && (
                    <span className="text-[10px] font-bold text-on-surface-variant bg-surface-container-high px-2 py-0.5 rounded-md">
                      Draft
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3 mt-2 text-[11px] text-on-surface-variant">
                <span className="capitalize">{c.status}</span>
                {c.next_follow_up_due && (
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-[13px]">event</span>
                    Follow up {new Date(c.next_follow_up_due).toLocaleDateString([], { dateStyle: 'medium' })}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showAddForm && (
        <div className="space-y-3 animate-fade-in bg-surface-container-lowest p-4 rounded-xl border border-outline-variant/10">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <input
              type="text"
              placeholder="Contact name"
              value={formState.contact_name}
              onChange={(e) => onFormChange({ ...formState, contact_name: e.target.value })}
              className="input-applyr w-full text-sm rounded-xl py-2.5 px-4 bg-surface"
            />
            <input
              type="text"
              placeholder="Title (optional)"
              value={formState.contact_title}
              onChange={(e) => onFormChange({ ...formState, contact_title: e.target.value })}
              className="input-applyr w-full text-sm rounded-xl py-2.5 px-4 bg-surface"
            />
            <select
              value={formState.contact_type}
              onChange={(e) => onFormChange({ ...formState, contact_type: e.target.value as Contact['contact_type'] })}
              className="input-applyr w-full text-sm rounded-xl py-2.5 px-4 bg-surface"
            >
              <option value="" disabled>Contact type…</option>
              {(Object.keys(CONTACT_TYPE_LABELS) as Contact['contact_type'][]).map(t => (
                <option key={t} value={t}>{CONTACT_TYPE_LABELS[t]}</option>
              ))}
            </select>
            <input
              type="text"
              placeholder="Source (optional)"
              value={formState.source}
              onChange={(e) => onFormChange({ ...formState, source: e.target.value })}
              className="input-applyr w-full text-sm rounded-xl py-2.5 px-4 bg-surface"
            />
          </div>
          {error && <p className="text-[11px] text-error">{error}</p>}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onSave}
              disabled={saving}
              className="btn-primary text-xs px-4 py-2 rounded-xl disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save contact'}
            </button>
            <button
              type="button"
              onClick={onCancel}
              className="text-xs text-on-surface-variant hover:text-on-surface"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
};

export default ContactsSection;
