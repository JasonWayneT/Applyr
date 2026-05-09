import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { api } from '../lib/api';

type Tab = 'Identity' | 'Experience' | 'Analytics' | 'Settings';

interface ProfileData {
  name: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  portfolio: string;
}

interface LLMSettings {
  provider: 'gemini' | 'claude' | 'local';
  geminiApiKey: string;
  claudeApiKey: string;
  localUrl: string;
  localModel: string;
}

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

const ProfileView: React.FC = () => {
  const [activeTab, setActiveTabState] = useState<Tab>(() => {
    const saved = localStorage.getItem('profile_subtab');
    if (saved === 'Security' || saved === 'Preferences') return 'Settings';
    return (saved as Tab) || 'Identity';
  });

  const setActiveTab = (tab: Tab) => {
    localStorage.setItem('profile_subtab', tab);
    setActiveTabState(tab);
  };
  const [profile, setProfile] = useState<ProfileData>({
    name: '', email: '', phone: '', location: '', linkedin: '', portfolio: ''
  });
  const [llmSettings, setLlmSettings] = useState<LLMSettings>({
    provider: 'gemini',
    geminiApiKey: '',
    claudeApiKey: '',
    localUrl: 'http://localhost:11434',
    localModel: 'llama3'
  });
  const [experience, setExperience] = useState('');
  const [experienceDirty, setExperienceDirty] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const [isFormatGuideOpen, setIsFormatGuideOpen] = useState(false);
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
        const [profileRes, expRes, statsRes, llmRes] = await Promise.all([
          fetch(api('/api/profile/identity')),
          fetch(api('/api/experience')),
          fetch(api('/api/jobs/stats')),
          fetch(api('/api/profile/llm_settings')),
        ]);
        const [profileData, expData, statsData, llmData] = await Promise.all([
          profileRes.json(),
          expRes.json(),
          statsRes.json(),
          llmRes.json(),
        ]);
        if (profileData.name) setProfile(profileData);
        setExperience(expData.content ?? '');
        if (!statsData.error) setStats(statsData);
        if (llmData.provider) setLlmSettings(llmData);
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

  const expStats = useMemo(() => ({
    acc: (experience.match(/ACC-\d+/g) || []).length,
    voc: (experience.match(/VOC-\d+/g) || []).length,
    met: (experience.match(/MET-\d+/g) || []).length,
  }), [experience]);

  const isExperienceEmpty = experience.trim().length < 100;

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
        {(['Identity', 'Experience', 'Analytics', 'Settings'] as Tab[]).map((tab) => (
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
                  className="input-applyr w-full rounded-xl"
                />
              </div>
            ))}
          </div>
        )}

        {/* Experience Tab */}
        {activeTab === 'Experience' && (
          <div className="space-y-4 animate-fade-in">

            {/* Empty state — onboarding prompt */}
            {isExperienceEmpty ? (
              <div className="bg-surface-container-lowest rounded-2xl editorial-shadow overflow-hidden">
                <div className="px-8 pt-8 pb-6 space-y-6">
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center shrink-0">
                      <span className="material-symbols-outlined text-primary text-2xl">history_edu</span>
                    </div>
                    <div>
                      <h3 className="text-base font-headline font-bold text-on-surface">Master Career Experience</h3>
                      <p className="text-xs text-on-surface-variant mt-1 leading-relaxed max-w-xl">
                        This is the anti-hallucination source of truth for every resume and cover letter the system generates.
                        Every claim in a generated document must trace back to a coded proof point here —
                        an accomplishment <span className="font-mono text-primary">ACC-NNN</span>, a vocabulary
                        term <span className="font-mono text-primary">VOC-XX</span>, or a metric <span className="font-mono text-primary">MET-XX</span>.
                        If no proof code exists, the AI is not allowed to make the claim.
                      </p>
                    </div>
                  </div>

                  <div className="bg-primary/5 border border-primary/15 rounded-xl px-5 py-4 space-y-2">
                    <p className="text-xs font-bold text-primary uppercase tracking-widest">Getting started</p>
                    <p className="text-xs text-on-surface-variant leading-relaxed">
                      Paste your raw work history below in any format — job titles, bullet points, responsibilities,
                      numbers, anything you remember. Click <strong className="text-on-surface">Save & Sync AI</strong> and
                      the system will automatically structure it into five sections and assign stable proof codes to every claim.
                      You can refine the structure over time.
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
                      {[
                        { icon: 'psychology', label: 'Vocabulary (VOC)', desc: 'Terms and language that define your professional voice' },
                        { icon: 'bar_chart', label: 'Metrics (MET)', desc: 'Quantitative proof points — percentages, dollar amounts, scale' },
                        { icon: 'emoji_events', label: 'Accomplishments (ACC)', desc: 'Role-specific achievements that resume bullets are drawn from' },
                      ].map(item => (
                        <div key={item.label} className="bg-surface-container rounded-xl p-3 flex gap-3 items-start">
                          <span className="material-symbols-outlined text-primary text-base mt-0.5">{item.icon}</span>
                          <div>
                            <p className="text-[11px] font-bold text-on-surface">{item.label}</p>
                            <p className="text-[10px] text-on-surface-variant mt-0.5 leading-snug">{item.desc}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="border-t border-outline-variant/10">
                  <div className="px-4 py-2.5 flex justify-between items-center bg-surface-container-low">
                    <span className="text-[10px] text-on-surface-variant font-mono uppercase tracking-widest">workExperience.md</span>
                    <button
                      onClick={saveExperience}
                      disabled={!experienceDirty || saveStatus === 'saving'}
                      className={`text-[11px] font-bold px-4 py-1.5 rounded-lg flex items-center gap-1.5 transition-all ${
                        experienceDirty ? 'btn-primary text-xs py-1.5' : 'bg-surface-container text-on-surface-variant cursor-not-allowed'
                      }`}
                    >
                      <span className="material-symbols-outlined text-sm">auto_fix_high</span>
                      {saveStatus === 'saving' ? 'Codifying...' : 'Save & Sync AI'}
                    </button>
                  </div>
                  <textarea
                    value={experience}
                    onChange={(e) => { setExperience(e.target.value); setExperienceDirty(true); }}
                    className="w-full h-64 bg-surface p-6 text-[13px] font-mono leading-relaxed text-on-surface focus:outline-none applyr-scrollbar resize-none"
                    placeholder="Paste your work history here in any format. Include job titles, responsibilities, key projects, metrics, and anything you're proud of. Don't worry about structure — the system will organize and codify it."
                    spellCheck={false}
                  />
                </div>
              </div>
            ) : (
              <>
                {/* Codification status bar */}
                <div className="flex items-center gap-4 bg-surface-container-lowest border border-outline-variant/10 rounded-2xl px-6 py-4 editorial-shadow">
                  <span className="material-symbols-outlined text-primary text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>verified</span>
                  <div className="flex-1">
                    <p className="text-xs font-bold text-on-surface">Codification Active</p>
                    <p className="text-[11px] text-on-surface-variant mt-0.5">All generated documents must cite codes from this file.</p>
                  </div>
                  <div className="flex items-center gap-6">
                    {[
                      { label: 'Accomplishments', value: expStats.acc, color: 'text-primary', code: 'ACC' },
                      { label: 'Vocabulary', value: expStats.voc, color: 'text-secondary', code: 'VOC' },
                      { label: 'Metrics', value: expStats.met, color: 'text-tertiary', code: 'MET' },
                    ].map(stat => (
                      <div key={stat.code} className="text-center">
                        <p className={`text-2xl font-headline font-extrabold ${stat.color}`}>{stat.value}</p>
                        <p className="text-[9px] font-bold text-on-surface-variant uppercase tracking-widest mt-0.5">{stat.label}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Update process guide */}
                <div className="bg-surface-container-lowest border border-outline-variant/10 rounded-2xl editorial-shadow overflow-hidden">
                  <button
                    onClick={() => setIsFormatGuideOpen(prev => !prev)}
                    className="w-full flex items-center justify-between px-6 py-4 hover:bg-surface-container-low transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className="material-symbols-outlined text-on-surface-variant text-base">edit_note</span>
                      <span className="text-xs font-bold text-on-surface">How to edit this document without breaking codes</span>
                    </div>
                    <span className="material-symbols-outlined text-on-surface-variant text-base">
                      {isFormatGuideOpen ? 'expand_less' : 'expand_more'}
                    </span>
                  </button>

                  {isFormatGuideOpen && (
                    <div className="px-6 pb-6 space-y-4 border-t border-outline-variant/10">
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
                        <div className="bg-primary/5 border border-primary/15 rounded-xl p-4 space-y-2">
                          <div className="flex items-center gap-2">
                            <span className="material-symbols-outlined text-primary text-base" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                            <p className="text-[11px] font-bold text-primary uppercase tracking-wider">Minor Edit — Safe</p>
                          </div>
                          <p className="text-xs text-on-surface-variant leading-relaxed">
                            Fix wording, correct typos, or improve a sentence. The <span className="font-mono text-on-surface">[ACC-NNN]</span> tag
                            stays in the line — the system preserves it and updates the content it points to.
                          </p>
                          <div className="bg-surface-container rounded-lg p-2 font-mono text-[10px] text-on-surface-variant leading-relaxed">
                            <span className="text-primary">✓</span> <span className="text-on-surface">**[ACC-101] Led migration reducing latency 40%**</span>
                          </div>
                        </div>

                        <div className="bg-secondary/5 border border-secondary/15 rounded-xl p-4 space-y-2">
                          <div className="flex items-center gap-2">
                            <span className="material-symbols-outlined text-secondary text-base" style={{ fontVariationSettings: "'FILL' 1" }}>add_circle</span>
                            <p className="text-[11px] font-bold text-secondary uppercase tracking-wider">New Claim — Add</p>
                          </div>
                          <p className="text-xs text-on-surface-variant leading-relaxed">
                            Add a new bold bullet without any code tag. Save, and the system assigns the next available code automatically.
                          </p>
                          <div className="bg-surface-container rounded-lg p-2 font-mono text-[10px] text-on-surface-variant leading-relaxed">
                            <span className="text-secondary">+</span> <span className="text-on-surface">**New accomplishment here**</span>
                            <br /><span className="text-on-surface-variant/60 pl-4">→ becomes [ACC-NNN] on save</span>
                          </div>
                        </div>

                        <div className="bg-error/5 border border-error/15 rounded-xl p-4 space-y-2">
                          <div className="flex items-center gap-2">
                            <span className="material-symbols-outlined text-error text-base" style={{ fontVariationSettings: "'FILL' 1" }}>link_off</span>
                            <p className="text-[11px] font-bold text-error uppercase tracking-wider">Retire a Claim — Unlink</p>
                          </div>
                          <p className="text-xs text-on-surface-variant leading-relaxed">
                            To stop a code from being used in future drafts, <strong className="text-on-surface">remove the [ACC-NNN] tag</strong> from
                            the bold header before saving. Keep the plain text as a record. Never delete lines silently.
                          </p>
                          <div className="bg-surface-container rounded-lg p-2 font-mono text-[10px] text-on-surface-variant leading-relaxed">
                            <span className="text-error">→</span> <span className="text-on-surface">**Old claim, no longer used**</span>
                            <br /><span className="text-on-surface-variant/60 pl-4">(tag removed = unlinked from AI)</span>
                          </div>
                        </div>
                      </div>

                      <div className="bg-surface-container rounded-xl px-4 py-3 flex gap-3 items-start">
                        <span className="material-symbols-outlined text-on-surface-variant text-base mt-0.5">info</span>
                        <p className="text-[11px] text-on-surface-variant leading-relaxed">
                          <strong className="text-on-surface">Never delete a coded line entirely.</strong> If a claim is no longer accurate,
                          unlink it by removing the code tag — the text stays as context but the AI will not cite it.
                          This mirrors the SDD convention: retire, don't delete.
                        </p>
                      </div>

                      <div className="space-y-2">
                        <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Document structure (5 sections)</p>
                        <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
                          {[
                            { num: '1', label: 'Identity & Positioning', desc: 'Who you are professionally' },
                            { num: '2', label: 'Core Skills', desc: 'What you can do' },
                            { num: '3', label: 'Vocabulary (VOC)', desc: 'Terms that define your voice' },
                            { num: '4', label: 'Metrics Bank (MET)', desc: 'Quantitative proof points' },
                            { num: '5', label: 'Accomplishments (ACC)', desc: 'Per-employer bullet points' },
                          ].map(s => (
                            <div key={s.num} className="bg-surface-container rounded-xl p-3">
                              <p className="text-[9px] font-bold text-primary uppercase tracking-widest mb-1">§{s.num}</p>
                              <p className="text-[11px] font-bold text-on-surface leading-tight">{s.label}</p>
                              <p className="text-[10px] text-on-surface-variant mt-1 leading-snug">{s.desc}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Editor */}
                <div className="bg-surface-container-lowest rounded-2xl editorial-shadow overflow-hidden">
                  <div className="px-6 py-3 flex justify-between items-center bg-surface-container-low">
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] text-on-surface-variant font-mono uppercase tracking-widest">workExperience.md</span>
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
                        experienceDirty ? 'btn-primary text-xs py-1.5' : 'bg-surface-container text-on-surface-variant cursor-not-allowed'
                      }`}
                    >
                      <span className="material-symbols-outlined text-sm">save</span>
                      {saveStatus === 'saving' ? 'Saving...' : 'Save & Sync AI'}
                    </button>
                  </div>
                  <textarea
                    value={experience}
                    onChange={(e) => { setExperience(e.target.value); setExperienceDirty(true); }}
                    className="w-full h-[600px] bg-surface p-6 text-[13px] font-mono leading-relaxed text-on-surface focus:outline-none applyr-scrollbar resize-none"
                    spellCheck={false}
                  />
                </div>
              </>
            )}
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

        {/* Settings Tab */}
        {activeTab === 'Settings' && (
          <div className="space-y-8 animate-fade-in">
            {/* LLM Provider Selection Cards */}
            <div className="bg-surface-container-lowest p-8 rounded-2xl editorial-shadow space-y-6 border border-outline-variant/10">
              <div>
                <h3 className="text-sm font-headline font-bold text-on-surface">Active LLM Provider</h3>
                <p className="text-xs text-on-surface-variant mt-1">Select the intelligence engine used for job description parsing, fit evaluation, and drafting assets.</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[
                  { id: 'gemini', name: 'Google Gemini', desc: 'Default fast cloud model', icon: 'google' },
                  { id: 'claude', name: 'Anthropic Claude', desc: 'Premium reasoning cloud model', icon: 'psychology' },
                  { id: 'local', name: 'Local LLM (Ollama/LM Studio)', desc: 'Privacy-focused local execution', icon: 'terminal' }
                ].map((prov) => (
                  <button
                    key={prov.id}
                    onClick={() => {
                      const next = { ...llmSettings, provider: prov.id as any };
                      setLlmSettings(next);
                      debouncedSave('llm_settings', next);
                    }}
                    className={`p-5 rounded-2xl border text-left transition-all relative overflow-hidden flex flex-col justify-between h-36 ${
                      llmSettings.provider === prov.id
                        ? 'bg-primary/5 border-primary shadow-sm scale-98'
                        : 'border-outline-variant/20 bg-surface hover:bg-surface-container-low hover:border-outline-variant/40'
                    }`}
                  >
                    <div className="flex justify-between items-start w-full">
                      <span className="material-symbols-outlined text-primary text-xl">{prov.icon}</span>
                      {llmSettings.provider === prov.id && (
                        <span className="material-symbols-outlined text-primary text-base" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                      )}
                    </div>
                    <div>
                      <p className="text-xs font-bold text-on-surface leading-tight">{prov.name}</p>
                      <p className="text-[10px] text-on-surface-variant mt-1 leading-snug">{prov.desc}</p>
                    </div>
                  </button>
                ))}
              </div>

              {/* Dynamic Settings Fields */}
              <div className="pt-4 border-t border-outline-variant/10 space-y-6">
                {llmSettings.provider === 'gemini' && (
                  <div>
                    <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Gemini API Key</label>
                    <input
                      type="password"
                      value={llmSettings.geminiApiKey}
                      onChange={(e) => {
                        const next = { ...llmSettings, geminiApiKey: e.target.value };
                        setLlmSettings(next);
                        debouncedSave('llm_settings', next);
                      }}
                      className="input-applyr w-full rounded-xl pr-8 font-mono text-xs"
                      placeholder="AIzaSy..."
                    />
                    <p className="text-[10px] text-on-surface-variant mt-1.5 italic">Auto-saves 1 second after you stop typing.</p>
                  </div>
                )}

                {llmSettings.provider === 'claude' && (
                  <div>
                    <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Claude API Key</label>
                    <input
                      type="password"
                      value={llmSettings.claudeApiKey}
                      onChange={(e) => {
                        const next = { ...llmSettings, claudeApiKey: e.target.value };
                        setLlmSettings(next);
                        debouncedSave('llm_settings', next);
                      }}
                      className="input-applyr w-full rounded-xl pr-8 font-mono text-xs"
                      placeholder="sk-ant-api03..."
                    />
                    <p className="text-[10px] text-on-surface-variant mt-1.5 italic">Auto-saves 1 second after you stop typing.</p>
                  </div>
                )}

                {llmSettings.provider === 'local' && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Local Endpoint Base URL</label>
                      <input
                        type="text"
                        value={llmSettings.localUrl}
                        onChange={(e) => {
                          const next = { ...llmSettings, localUrl: e.target.value };
                          setLlmSettings(next);
                          debouncedSave('llm_settings', next);
                        }}
                        className="input-applyr w-full rounded-xl font-mono text-xs"
                        placeholder="http://localhost:11434"
                      />
                      <p className="text-[10px] text-on-surface-variant mt-1.5 italic">Use http://localhost:11434 for Ollama or http://localhost:1234/v1 for LM Studio.</p>
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-2">Model Identifier / Name</label>
                      <input
                        type="text"
                        value={llmSettings.localModel}
                        onChange={(e) => {
                          const next = { ...llmSettings, localModel: e.target.value };
                          setLlmSettings(next);
                          debouncedSave('llm_settings', next);
                        }}
                        className="input-applyr w-full rounded-xl font-mono text-xs"
                        placeholder="llama3"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Local Security Block */}
            <div className="bg-surface-container-lowest p-8 rounded-2xl editorial-shadow space-y-6 border border-outline-variant/10">
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-surface-container flex items-center justify-center shrink-0">
                  <span className="material-symbols-outlined text-on-surface-variant text-2xl">shield</span>
                </div>
                <div>
                  <h3 className="text-base font-headline font-bold text-on-surface">Local Privacy Mode</h3>
                  <p className="text-xs text-on-surface-variant mt-1">All database configurations, keys, and job details remain fully encrypted and local to your system SQLite files.</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProfileView;
