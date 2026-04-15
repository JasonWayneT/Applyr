import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../lib/api';

type Tab = 'Identity' | 'Experience' | 'Preferences' | 'Security';

interface ProfileData {
  name: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  portfolio: string;
}

interface PreferenceData {
  minSalary: number;
  environment: string;
  titleBlocklist: string;
  industryBlocklist: string;
}

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

const ProfileView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('Identity');
  const [profile, setProfile] = useState<ProfileData>({
    name: '', email: '', phone: '', location: '', linkedin: '', portfolio: ''
  });
  const [preferences, setPreferences] = useState<PreferenceData>({
    minSalary: 0, environment: 'Remote', titleBlocklist: '', industryBlocklist: ''
  });
  const [experience, setExperience] = useState('');
  const [experienceDirty, setExperienceDirty] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const [loadError, setLoadError] = useState<string | null>(null);

  // Debounce timers
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [profileRes, prefRes, expRes] = await Promise.all([
          fetch(api('/api/profile/identity')),
          fetch(api('/api/profile/preferences')),
          fetch(api('/api/experience')),
        ]);
        const [profileData, prefData, expData] = await Promise.all([
          profileRes.json(),
          prefRes.json(),
          expRes.json(),
        ]);
        if (profileData.name) setProfile(profileData);
        if (prefData.minSalary) setPreferences(prefData);
        setExperience(expData.content ?? '');
      } catch {
        setLoadError('Could not connect to the local server. Make sure `npm run dev:server` is running.');
      }
    };
    loadData();
  }, []);

  const debouncedSave = useCallback((key: string, data: any) => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    setSaveStatus('saving');
    debounceTimer.current = setTimeout(async () => {
      try {
        const res = await fetch(api(`/api/profile/${key}`), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        });
        if (!res.ok) throw new Error();
        setSaveStatus('saved');
        setTimeout(() => setSaveStatus('idle'), 2000);
      } catch {
        setSaveStatus('error');
      }
    }, 1000);
  }, []);

  const saveExperience = async () => {
    setSaveStatus('saving');
    try {
      const res = await fetch(api('/api/experience'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: experience }),
      });
      if (!res.ok) throw new Error();
      setExperienceDirty(false);
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch {
      setSaveStatus('error');
    }
  };

  const StatusBadge = () => {
    if (saveStatus === 'saving') return (
      <div className="flex items-center gap-1.5 text-on-surface-variant text-xs animate-pulse">
        <div className="w-1.5 h-1.5 rounded-full bg-secondary"></div> Saving...
      </div>
    );
    if (saveStatus === 'saved') return (
      <div className="flex items-center gap-1.5 text-xs text-primary">
        <div className="w-1.5 h-1.5 rounded-full bg-primary"></div> Saved
      </div>
    );
    if (saveStatus === 'error') return (
      <div className="flex items-center gap-1.5 text-xs text-error">
        <div className="w-1.5 h-1.5 rounded-full bg-error"></div> Save failed
      </div>
    );
    return null;
  };

  return (
    <div className="space-y-8 pb-20">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-headline font-extrabold text-on-surface tracking-tight">My Profile</h1>
          <p className="text-on-surface-variant mt-1 text-sm">Your professional identity and source of truth for AI matching.</p>
        </div>
        <StatusBadge />
      </div>

      {/* Server error banner */}
      {loadError && (
        <div className="flex items-center gap-3 bg-error/10 border border-error/20 rounded-xl px-4 py-3">
          <span className="material-symbols-outlined text-error text-base">error</span>
          <span className="text-xs text-error">{loadError}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-8 border-b border-outline-variant/20">
        {(['Identity', 'Experience', 'Preferences', 'Security'] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-3 text-sm font-headline font-bold transition-all relative flex items-center gap-2 ${
              activeTab === tab ? 'text-primary' : 'text-on-surface-variant hover:text-on-surface'
            }`}
          >
            {tab}
            {tab === 'Experience' && experienceDirty && (
              <span className="w-1.5 h-1.5 rounded-full bg-secondary" title="Unsaved changes"></span>
            )}
            {activeTab === tab && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-t-full"></div>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="mt-6">
        {/* Identity Tab */}
        {activeTab === 'Identity' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-surface-container-lowest p-8 rounded-2xl editorial-shadow">
            {[
              { label: 'Full Name', key: 'name', type: 'text', placeholder: 'Jason Taylor' },
              { label: 'Email Address', key: 'email', type: 'email', placeholder: '' },
              { label: 'Phone Number', key: 'phone', type: 'text', placeholder: '' },
              { label: 'Location', key: 'location', type: 'text', placeholder: 'City, State' },
              { label: 'LinkedIn URL', key: 'linkedin', type: 'text', placeholder: '' },
              { label: 'Portfolio / GitHub', key: 'portfolio', type: 'text', placeholder: '' },
            ].map(({ label, key, type, placeholder }) => (
              <div key={key}>
                <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">{label}</label>
                <input
                  type={type}
                  value={(profile as any)[key]}
                  placeholder={placeholder}
                  onChange={(e) => {
                    const next = { ...profile, [key]: e.target.value };
                    setProfile(next);
                    debouncedSave('identity', next);
                  }}
                  className="input-sanctuary w-full rounded-xl"
                />
              </div>
            ))}
          </div>
        )}

        {/* Experience Tab */}
        {activeTab === 'Experience' && (
          <div className="bg-surface-container-lowest rounded-2xl editorial-shadow overflow-hidden">
            <div className="px-6 py-3 flex justify-between items-center bg-surface-container-low">
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-on-surface-variant font-mono uppercase tracking-widest">Master Career Context (workExperience.md)</span>
                {experienceDirty && (
                  <span className="text-[10px] text-secondary flex items-center gap-1 font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-secondary inline-block"></span> Unsaved changes
                  </span>
                )}
              </div>
              <button
                onClick={saveExperience}
                disabled={!experienceDirty || saveStatus === 'saving'}
                className={`text-[11px] font-bold px-4 py-1.5 rounded-lg flex items-center gap-1.5 transition-all ${
                  experienceDirty
                    ? 'btn-primary text-xs py-1.5'
                    : 'bg-surface-container text-on-surface-variant cursor-not-allowed'
                }`}
              >
                <span className="material-symbols-outlined text-sm">save</span>
                {saveStatus === 'saving' ? 'Saving...' : 'Save & Sync AI'}
              </button>
            </div>
            <textarea
              value={experience}
              onChange={(e) => { setExperience(e.target.value); setExperienceDirty(true); }}
              className="w-full h-[600px] bg-surface p-6 text-[13px] font-mono leading-relaxed text-on-surface focus:outline-none sanctuary-scrollbar resize-none"
              spellCheck={false}
            />
          </div>
        )}

        {/* Preferences Tab */}
        {activeTab === 'Preferences' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 bg-surface-container-lowest p-8 rounded-2xl editorial-shadow">
            <div className="space-y-6">
              <div>
                <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Minimum Salary Requirement</label>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant text-sm">$</span>
                  <input
                    type="number"
                    value={preferences.minSalary}
                    onChange={(e) => {
                      const next = { ...preferences, minSalary: parseInt(e.target.value) || 0 };
                      setPreferences(next);
                      debouncedSave('preferences', next);
                    }}
                    className="input-sanctuary w-full rounded-xl pl-8"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Preferred Work Environment</label>
                <div className="flex gap-2">
                  {['Remote', 'Hybrid', 'On-site'].map((opt) => (
                    <button
                      key={opt}
                      onClick={() => {
                        const next = { ...preferences, environment: opt };
                        setPreferences(next);
                        debouncedSave('preferences', next);
                      }}
                      className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all ${
                        preferences.environment === opt
                          ? 'bg-primary-container text-on-primary-container'
                          : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="space-y-6">
              <div>
                <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Title Blocklist (AI auto-reject)</label>
                <textarea
                  value={preferences.titleBlocklist}
                  onChange={(e) => {
                    const next = { ...preferences, titleBlocklist: e.target.value };
                    setPreferences(next);
                    debouncedSave('preferences', next);
                  }}
                  className="input-sanctuary w-full h-20 rounded-xl px-4 py-3 text-xs resize-none"
                  placeholder="Senior, VP, Director, Lead..."
                />
                <p className="text-[10px] text-on-surface-variant mt-1.5 italic">Comma separated. Auto-saves 1 second after you stop typing.</p>
              </div>
              <div>
                <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Industry Blocklist</label>
                <textarea
                  value={preferences.industryBlocklist}
                  onChange={(e) => {
                    const next = { ...preferences, industryBlocklist: e.target.value };
                    setPreferences(next);
                    debouncedSave('preferences', next);
                  }}
                  className="input-sanctuary w-full h-20 rounded-xl px-4 py-3 text-xs resize-none"
                  placeholder="Crypto, Gambling, Web3..."
                />
              </div>
            </div>
          </div>
        )}

        {/* Security Tab */}
        {activeTab === 'Security' && (
          <div className="bg-surface-container-lowest p-8 rounded-2xl editorial-shadow space-y-6">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-surface-container flex items-center justify-center shrink-0">
                <span className="material-symbols-outlined text-on-surface-variant text-2xl">shield</span>
              </div>
              <div>
                <h3 className="text-base font-headline font-bold text-on-surface">Local Privacy Mode</h3>
                <p className="text-xs text-on-surface-variant mt-1">All data is stored on your local machine in SQLite. Nothing leaves your device.</p>
              </div>
            </div>

            <div className="p-5 bg-primary-container/20 rounded-xl flex justify-between items-center">
              <div>
                <p className="text-sm font-headline font-bold text-primary">Google Identity Integration</p>
                <p className="text-xs text-on-surface-variant mt-1">Connect Gmail for automated scout result notifications (future).</p>
              </div>
              <button disabled className="bg-surface-container text-on-surface-variant text-[10px] font-bold uppercase tracking-widest px-4 py-2 rounded-lg cursor-not-allowed">
                Coming Soon
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProfileView;
