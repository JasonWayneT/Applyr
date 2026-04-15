import React, { useState } from 'react';

interface JDInputFormProps {
  onRun: (company: string, jd: string, url?: string) => void;
  isLoading: boolean;
}

const JDInputForm: React.FC<JDInputFormProps> = ({ onRun, isLoading }) => {
  const [company, setCompany] = useState('');
  const [url, setUrl] = useState('');
  const [jd, setJd] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (company && jd) {
      onRun(company, jd, url);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="space-y-2">
        <label className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">Company Name</label>
        <input
          type="text"
          value={company}
          onChange={(e) => setCompany(e.target.value)}
          placeholder="e.g. Stripe, Airbnb, etc."
          disabled={isLoading}
          className="input-sanctuary w-full rounded-xl"
        />
      </div>

      <div className="space-y-2">
        <label className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">Job URL (Optional)</label>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://company.com/careers/pm"
          disabled={isLoading}
          className="input-sanctuary w-full rounded-xl"
        />
      </div>

      <div className="space-y-2">
        <label className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">Job Description</label>
        <textarea
          value={jd}
          onChange={(e) => setJd(e.target.value)}
          placeholder="Paste the full job description here..."
          disabled={isLoading}
          className="input-sanctuary w-full h-[320px] rounded-xl p-4 resize-none"
        />
      </div>

      <div className="pt-4 space-y-4">
        <div className="flex gap-3">
          <button
            type="submit"
            disabled={!company || !jd || isLoading}
            className="flex-1 btn-primary h-12 flex items-center justify-center gap-2 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
            ) : (
              <>
                <span className="material-symbols-outlined text-base">bolt</span>
                <span>Run automation</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={() => { setCompany(''); setJd(''); setUrl(''); }}
            disabled={isLoading || (!company && !jd && !url)}
            className="px-4 bg-surface-container-high rounded-xl hover:bg-surface-container-highest transition-colors text-on-surface-variant disabled:opacity-0"
            title="Clear form"
          >
            <span className="material-symbols-outlined text-base">delete</span>
          </button>
        </div>

        <p className="text-[10px] text-on-surface-variant text-center leading-relaxed">
          The pipeline uses Gemini Flash to evaluate fit and build assets. Your data remains local.
        </p>
      </div>
    </form>
  );
};

export default JDInputForm;
