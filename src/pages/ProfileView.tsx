import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../lib/api';

type Tab = 'Identity' | 'Experience' | 'Preferences' | 'Analytics' | 'Security';

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
  const [stats, setStats] = useState<{
    total: number;
    byStatus: {status: string, count: number}[];
    byRejectionStage: {rejection_stage: string, count: number}[];
    byRejectionType: {rejection_type: string, count: number}[];
  } | null>(null);

  // Debounce timers
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [profileRes, prefRes, expRes, statsRes] = await Promise.all([
          fetch(api('/api/profile/identity')),
          fetch(api('/api/profile/preferences')),
          fetch(api('/api/experience')),
          fetch(api('/api/jobs/stats')),
        ]);
        const [profileData, prefData, expData, statsData] = await Promise.all([
          profileRes.json(),
          prefRes.json(),
          expRes.json(),
          statsRes.json(),
        ]);
        if (profileData.name) setProfile(profileData);
        if (prefData.minSalary) setPreferences(prefData);
        setExperience(expData.content ?? '');
        if (!statsData.error) setStats(statsData);
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
        {(['Identity', 'Experience', 'Preferences', 'Analytics', 'Security'] as Tab[]).map((tab) => (
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

        {/* Analytics Tab */}
        {activeTab === 'Analytics' && stats && (
          <div className="space-y-8 animate-fade-in">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-surface-container-lowest p-5 rounded-2xl editorial-shadow border border-outline-variant/10">
                <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1">Total Leads</p>
                <p className="text-3xl font-headline font-extrabold text-primary">{stats.total}</p>
              </div>
              <div className="bg-surface-container-lowest p-5 rounded-2xl editorial-shadow border border-outline-variant/10 text-error">
                <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1">Rejected</p>
                <p className="text-3xl font-headline font-extrabold">{stats.byRejectionType.find(t => t.rejection_type === 'Rejected')?.count || 0}</p>
              </div>
              <div className="bg-surface-container-lowest p-5 rounded-2xl editorial-shadow border border-outline-variant/10 text-on-surface-variant">
                <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mb-1">Ghosted</p>
                <p className="text-3xl font-headline font-extrabold">{stats.byRejectionType.find(t => t.rejection_type === 'Ghosted')?.count || 0}</p>
              </div>
              <div className="bg-surface-container-lowest p-5 rounded-2xl editorial-shadow border border-outline-variant/20 bg-primary/5">
                <p className="text-[10px] font-bold text-primary uppercase tracking-widest mb-1">Interview Rate</p>
                <p className="text-3xl font-headline font-extrabold text-primary">
                  {Math.round(((stats.byStatus.find(s => s.status === 'Core Interviews')?.count || 0) / (stats.total || 1)) * 100)}%
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Funnel Visualization */}
              <div className="bg-surface-container-lowest p-8 rounded-3xl editorial-shadow">
                <h3 className="text-sm font-headline font-bold text-on-surface mb-6">Application Funnel</h3>
                <div className="space-y-4">
                  {[
                    { label: 'Backlog', status: 'Backlog', color: 'bg-outline-variant' },
                    { label: 'Applied', status: 'Applied', color: 'bg-primary-container' },
                    { label: 'Screening', status: 'Recruiter Screen', color: 'bg-secondary' },
                    { label: 'Interviews', status: 'Core Interviews', color: 'bg-primary' },
                    { label: 'Offers', status: 'Offer and Negotiation', color: 'bg-tertiary' },
                  ].map((stage, i) => {
                    const count = stage.status === 'Backlog'
                      ? (stats.byStatus.find(s => s.status === 'Backlog')?.count || 0) + (stats.byStatus.find(s => s.status === 'New')?.count || 0)
                      : stats.byStatus.find(s => s.status === stage.status)?.count || 0;
                    const percentage = Math.max(10, (count / (stats.total || 1)) * 100);
                    return (
                      <div key={stage.label} className="relative group">
                        <div className="flex justify-between items-center mb-1.5 px-1">
                          <span className="text-[11px] font-bold text-on-surface-variant uppercase tracking-wider">{stage.label}</span>
                          <span className="text-xs font-mono font-bold text-on-surface">{count}</span>
                        </div>
                        <div className="h-8 w-full bg-surface-container rounded-lg overflow-hidden flex">
                          <div 
                            className={`h-full ${stage.color} transition-all duration-1000 ease-out flex items-center px-3`}
                            style={{ width: `${percentage}%` }}
                          >
                            {percentage > 15 && <div className="w-1 h-1 rounded-full bg-white/50" />}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Dropoff Heatmap */}
              <div className="bg-surface-container-lowest p-8 rounded-3xl editorial-shadow">
                <h3 className="text-sm font-headline font-bold text-on-surface mb-6">Dropoff Patterns (Closed/Archived)</h3>
                <div className="space-y-4">
                  {['Backlog', 'Applied', 'Recruiter Screen', 'Core Interviews'].map(stage => {
                    const count = stage === 'Backlog'
                      ? (stats.byRejectionStage.find(s => s.rejection_stage === 'Backlog')?.count || 0) + (stats.byRejectionStage.find(s => s.rejection_stage === 'New')?.count || 0)
                      : stats.byRejectionStage.find(s => s.rejection_stage === stage)?.count || 0;
                    const max = Math.max(...stats.byRejectionStage.filter(s => s.rejection_stage).map(s => s.count), 1);
                    const weight = (count / max) * 100;
                    return (
                      <div key={stage} className="flex items-center gap-4">
                        <div className="w-24 text-[10px] font-bold text-on-surface-variant uppercase tracking-tighter text-right">{stage}</div>
                        <div className="flex-1 h-2 bg-surface-container rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-error/40 rounded-full" 
                            style={{ width: `${weight}%` }}
                          />
                        </div>
                        <div className="w-8 text-xs font-mono font-bold text-on-surface">{count}</div>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-8 p-4 bg-surface-container-low rounded-xl">
                  {(() => {
                    const validStages = stats.byRejectionStage.filter(s => s.rejection_stage);
                    const topStage = validStages.sort((a,b) => b.count - a.count)[0]?.rejection_stage || 'N/A';
                    return (
                      <p className="text-[11px] text-on-surface-variant leading-relaxed">
                        <span className="font-bold text-error">Insight:</span> Most applications are stalling at the <strong>{topStage}</strong> phase. Consider refining your {
                          topStage === 'Applied' ? 'Resume' : 'Interview prep'
                        }.
                      </p>
                    );
                  })()}
                </div>
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
