import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { api } from '../lib/api';

interface ProfileData {
  name: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  portfolio: string;
  github: string;
}

// Implements FR-062, FR-063, SEC-004
interface LlmSettings {
  primaryProvider: 'gemini' | 'claude' | 'local' | 'perplexity';
  geminiApiKey: string;
  claudeApiKey: string;
  localUrl: string;
  localModel: string;
  perplexityApiKey: string;
}

// Implements FR-054, SEC-002
interface ApiConnections {
  adzunaAppId: string;
  adzunaAppKey: string;
  theirstackApiKey?: string;
}

interface EnvStatus {
  gemini: boolean;
  claude: boolean;
  perplexity: boolean;
  adzuna: boolean;
  localUrl: boolean;
}

interface StatsData {
  total: number;
  byStatus: { status: string; count: number }[];
  byRejectionStage: { rejection_stage: string; count: number }[];
  byRejectionType: { rejection_type: string; count: number }[];
}

function SettingsCard({
  label,
  title,
  description,
  children,
  action,
  className = '',
}: {
  label?: string;
  title: string;
  description?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`bg-surface-container-lowest border border-outline/8 rounded-2xl p-6 md:p-7 shadow-sm ${className}`}>
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          {label && (
            <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.14em] mb-1.5">{label}</p>
          )}
          <h3 className="text-lg font-headline font-bold text-on-surface tracking-tight">{title}</h3>
          {description && <p className="text-xs text-on-surface-variant mt-1.5 leading-relaxed max-w-2xl">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function SettingsField({
  label,
  children,
  hint,
  className = '',
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
  className?: string;
}) {
  return (
    <div className={`space-y-2 ${className}`}>
      <label className="block text-[11px] font-semibold text-on-surface-variant">{label}</label>
      {children}
      {hint && <p className="text-[10px] text-on-surface-variant/80 leading-snug">{hint}</p>}
    </div>
  );
}

const inputClass =
  'w-full text-sm px-4 py-2.5 rounded-xl bg-surface border border-outline/12 text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:border-primary/35 focus:ring-2 focus:ring-primary/10 transition-colors';

const providerConfigClass = `${inputClass} font-mono text-xs w-full max-w-xl`;
const providerConfigWrapClass = 'w-full max-w-xl';

const SettingsView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('Profile');
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');

  // Unified States
  const [profile, setProfile] = useState<ProfileData>({
    name: '', email: '', phone: '', location: '', linkedin: '', portfolio: '', github: ''
  });
  const [isFormatGuideOpen, setIsFormatGuideOpen] = useState(false);
  const [llmSettings, setLlmSettings] = useState<LlmSettings>({
    primaryProvider: 'gemini',
    geminiApiKey: '',
    claudeApiKey: '',
    localUrl: 'http://localhost:11434',
    localModel: 'llama3',
    perplexityApiKey: '',
  });
  const [apiConnections, setApiConnections] = useState<ApiConnections>({ adzunaAppId: '', adzunaAppKey: '', theirstackApiKey: '' });
  const [experience, setExperience] = useState('');
  const [experienceDirty, setExperienceDirty] = useState(false);
  const [stats, setStats] = useState<StatsData | null>(null);
  const [envStatus, setEnvStatus] = useState<EnvStatus>({ gemini: false, claude: false, perplexity: false, adzuna: false, localUrl: false });

  // Debounce Ref
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch all profile/preference/experience/stats datasets on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        const [profileRes, expRes, statsRes, llmRes, connRes, envRes] = await Promise.all([
          fetch(api('/api/profile/identity')),
          fetch(api('/api/experience')),
          fetch(api('/api/jobs/stats')),
          fetch(api('/api/profile/llm_settings')),
          fetch(api('/api/profile/api_connections')),
          fetch(api('/api/env_status')),
        ]);

        const [profileData, expData, statsData, llmData, connData, envData] = await Promise.all([
          profileRes.json(),
          expRes.json(),
          statsRes.json(),
          llmRes.json(),
          connRes.json(),
          envRes.json(),
        ]);

        if (profileData && typeof profileData === 'object') {
          setProfile(prev => ({ ...prev, ...profileData }));
        }
        setExperience(expData.content ?? '');
        if (statsData && !statsData.error) {
          setStats(statsData);
        }
        if (llmData && typeof llmData === 'object') {
          // Implements FR-063: backward compat — old 'provider' field → primaryProvider
          setLlmSettings(prev => ({
            ...prev,
            ...llmData,
            primaryProvider: llmData.primaryProvider || llmData.provider || 'gemini',
            // Migrate perplexityApiKey from old api_connections location if not yet in llm_settings
            perplexityApiKey: llmData.perplexityApiKey || connData?.perplexityApiKey || '',
          }));
        }
        if (connData && !connData.error) {
          // perplexityApiKey now lives in llm_settings — exclude it from apiConnections state
          const { perplexityApiKey: _legacy, ...rest } = connData as any;
          setApiConnections(prev => ({ ...prev, ...rest }));
        }
        if (envData) {
          setEnvStatus(envData);
        }
      } catch (err) {
        console.error('Failed to load SettingsView configurations:', err);
      }
    };

    loadData();
  }, []);

  // Debounced auto-saving function
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
        if (res.ok) {
          setSaveStatus('saved');
          setTimeout(() => setSaveStatus('idle'), 2000);
        } else {
          setSaveStatus('error');
        }
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
      if (res.ok) {
        setExperienceDirty(false);
        setSaveStatus('saved');
        setTimeout(() => setSaveStatus('idle'), 2000);
      } else {
        setSaveStatus('error');
      }
    } catch {
      setSaveStatus('error');
    }
  };

  const expStats = useMemo(() => ({
    acc: (experience.match(/ACC-\d+/g) || []).length,
    voc: (experience.match(/VOC-\d+/g) || []).length,
    met: (experience.match(/MET-\d+/g) || []).length,
  }), [experience]);

  const isExperienceEmpty = experience.trim().length < 100;

  const tabs = [
    { id: 'Profile', icon: 'account_circle', short: 'Profile' },
    { id: 'Experience', icon: 'work', short: 'Experience' },
    { id: 'API or Connections', icon: 'hub', short: 'Integrations' },
    { id: 'Analytics', icon: 'analytics', short: 'Analytics' },
  ];

  const primaryProviderLabel =
    llmSettings.primaryProvider === 'gemini' ? 'Google Gemini'
    : llmSettings.primaryProvider === 'claude' ? 'Anthropic Claude'
    : llmSettings.primaryProvider === 'perplexity' ? 'Perplexity'
    : 'Local LLM';

  const saveBadge = saveStatus === 'saving' ? (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-on-surface-variant bg-surface-container px-3 py-1 rounded-full border border-outline/10">
      <span className="w-1.5 h-1.5 rounded-full bg-secondary animate-pulse" />
      Saving
    </span>
  ) : saveStatus === 'saved' ? (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-emerald-700 bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
      Saved
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-emerald-700 bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
      Local
    </span>
  );

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-10 animate-fade-in text-on-surface">
      {/* Page header — Tavily-style */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <p className="text-xs text-on-surface-variant mb-1">
            Settings <span className="text-on-surface-variant/50 mx-1">/</span> {activeTab}
          </p>
          <h1 className="text-3xl font-headline font-extrabold tracking-tight text-on-surface">{activeTab}</h1>
          <p className="text-sm text-on-surface-variant mt-1.5 max-w-xl">
            {activeTab === 'Profile' && 'Contact details and links used across resumes and applications.'}
            {activeTab === 'Experience' && 'Source of truth for accomplishments, metrics, and proof codes.'}
            {activeTab === 'API or Connections' && 'AI providers and optional job board API connections.'}
            {activeTab === 'Analytics' && 'Pipeline throughput and rejection telemetry.'}
          </p>
        </div>
        {saveBadge}
      </div>

      {/* Sub-navigation pills */}
      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold transition-all border ${
              activeTab === tab.id
                ? 'bg-on-surface text-surface border-on-surface shadow-sm'
                : 'bg-surface-container-lowest text-on-surface-variant border-outline/10 hover:border-outline/25 hover:text-on-surface'
            }`}
          >
            <span className="material-symbols-outlined text-[15px]">{tab.icon}</span>
            {tab.short}
            {tab.id === 'Experience' && experienceDirty && (
              <span className="w-1.5 h-1.5 rounded-full bg-secondary" title="Unsaved changes" />
            )}
          </button>
        ))}
      </div>

      {/* Tab content — stacked cards */}
      <div className="space-y-5">

        {/* Profile Tab */}
        {activeTab === 'Profile' && (
          <>
            <section className="rounded-2xl border border-outline/8 p-6 md:p-8 bg-gradient-to-br from-primary/8 via-surface-container-lowest to-secondary/5 shadow-sm">
              <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.14em] mb-2">Current profile</p>
              <h2 className="text-2xl md:text-3xl font-headline font-extrabold text-on-surface tracking-tight">
                {profile.name?.trim() || 'Your name'}
              </h2>
              <p className="text-sm text-on-surface-variant mt-2">
                {[profile.email, profile.location].filter(Boolean).join(' · ') || 'Add contact details below'}
              </p>
            </section>

            <SettingsCard
              label="Contact"
              title="Personal details"
              description="Used on generated resumes, cover letters, and application headers."
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {[
                  { label: 'Full name', key: 'name', type: 'text', placeholder: 'Jason Thomas' },
                  { label: 'Email', key: 'email', type: 'email', placeholder: 'you@email.com' },
                  { label: 'Phone', key: 'phone', type: 'text', placeholder: '+1 (555) 000-0000' },
                  { label: 'Location', key: 'location', type: 'text', placeholder: 'San Diego, CA' },
                ].map(({ label, key, type, placeholder }) => (
                  <SettingsField key={key} label={label}>
                    <input
                      type={type}
                      value={profile[key as keyof ProfileData] ?? ''}
                      placeholder={placeholder}
                      onChange={(e) => {
                        const next = { ...profile, [key]: e.target.value };
                        setProfile(next);
                        debouncedSave('identity', next);
                      }}
                      className={inputClass}
                    />
                  </SettingsField>
                ))}
              </div>
            </SettingsCard>

            <SettingsCard
              label="Links"
              title="Online presence"
              description="Portfolio and social links included where relevant in application materials."
            >
              <div className="grid grid-cols-1 gap-5">
                {[
                  { label: 'LinkedIn', key: 'linkedin', placeholder: 'https://linkedin.com/in/...' },
                  { label: 'Portfolio', key: 'portfolio', placeholder: 'https://yoursite.com' },
                  { label: 'GitHub', key: 'github', placeholder: 'https://github.com/...' },
                ].map(({ label, key, placeholder }) => (
                  <SettingsField key={key} label={label}>
                    <input
                      type="text"
                      value={profile[key as keyof ProfileData] ?? ''}
                      placeholder={placeholder}
                      onChange={(e) => {
                        const next = { ...profile, [key]: e.target.value };
                        setProfile(next);
                        debouncedSave('identity', next);
                      }}
                      className={inputClass}
                    />
                  </SettingsField>
                ))}
              </div>
            </SettingsCard>

            <SettingsCard label="Workspace" title="Local-first storage">
              <p className="text-sm text-on-surface-variant leading-relaxed">
                All settings auto-save to your local SQLite database. Nothing syncs to git or the cloud unless you configure it.
              </p>
            </SettingsCard>
          </>
        )}

        {/* Experience Tab */}
        {activeTab === 'Experience' && (
          <div className="space-y-4 animate-fade-in">

            {isExperienceEmpty ? (
              <div className="bg-surface-container-low rounded-2xl overflow-hidden">
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
                        experienceDirty ? 'bg-primary text-on-primary' : 'bg-surface-container text-on-surface-variant cursor-not-allowed'
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
                <div className="flex items-center gap-4 bg-surface-container-low border border-outline-variant/10 rounded-2xl px-6 py-4">
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

                {/* Collapsible edit guide */}
                <div className="bg-surface-container-low border border-outline-variant/10 rounded-2xl overflow-hidden">
                  <button
                    onClick={() => setIsFormatGuideOpen(prev => !prev)}
                    className="w-full flex items-center justify-between px-6 py-4 hover:bg-surface-container transition-colors"
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
                            stays in the line — the system preserves it.
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
                            Change <span className="font-mono text-on-surface">[ACC-NNN]</span> to <span className="font-mono text-on-surface">[RETIRED-ACC-NNN]</span> before saving.
                            The engine skips lines containing <span className="font-mono text-on-surface">RETIRED-ACC</span> and will not re-assign a new code to it.
                          </p>
                          <div className="bg-surface-container rounded-lg p-2 font-mono text-[10px] text-on-surface-variant leading-relaxed">
                            <span className="text-error">→</span> <span className="text-on-surface">**[RETIRED-ACC-101] Old claim**</span>
                            <br /><span className="text-on-surface-variant/60 pl-4">(preserved in file, invisible to AI)</span>
                          </div>
                        </div>
                      </div>

                      <div className="bg-surface-container rounded-xl px-4 py-3 flex gap-3 items-start">
                        <span className="material-symbols-outlined text-on-surface-variant text-base mt-0.5">info</span>
                        <p className="text-[11px] text-on-surface-variant leading-relaxed">
                          <strong className="text-on-surface">Never delete a coded line entirely.</strong> If a claim is no longer accurate,
                          unlink it by removing the code tag — the text stays as context but the AI will not cite it.
                          Retire, don&apos;t delete.
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
                <div className="bg-surface-container-low rounded-2xl overflow-hidden">
                  <div className="px-6 py-3 flex justify-between items-center border-b border-outline-variant/10">
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
                        experienceDirty ? 'bg-primary text-on-primary' : 'bg-surface-container text-on-surface-variant cursor-not-allowed'
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

        {/* API or Connections Tab — Implements FR-059, FR-060, FR-061, FR-062, FR-063 */}
        {activeTab === 'API or Connections' && (
          <>
            <section className="rounded-2xl border border-outline/8 p-6 md:p-8 bg-gradient-to-br from-primary/8 via-surface-container-lowest to-surface-container-low shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.14em] mb-2">Primary provider</p>
                  <h2 className="text-2xl font-headline font-extrabold text-on-surface">{primaryProviderLabel}</h2>
                  <p className="text-sm text-on-surface-variant mt-1.5">Tried first for fit scoring and drafting. Others serve as automatic fallback.</p>
                </div>
                <span className="self-start text-[11px] font-semibold text-primary bg-primary/10 px-3 py-1.5 rounded-full border border-primary/15">
                  {llmSettings.primaryProvider} · primary
                </span>
              </div>
            </section>

            <SettingsCard
              label="AI providers"
              title="API keys"
              description="Only providers with a configured key are called. Keys stay in your local database."
            >
              <div className="overflow-x-auto -mx-1">
                <table className="w-full min-w-[640px] text-left border-collapse">
                  <thead>
                    <tr className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider border-b border-outline/10">
                      <th className="pb-3 pr-4 font-bold">Provider</th>
                      <th className="pb-3 pr-4 font-bold">Role</th>
                      <th className="pb-3 pr-4 font-bold">Status</th>
                      <th className="pb-3 font-bold">Configuration</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline/8">
                    {/* Local — listed first */}
                    <tr className="align-top">
                      <td className="py-4 pr-4 w-40">
                        <p className="text-sm font-semibold text-on-surface">Local LLM</p>
                      </td>
                      <td className="py-4 pr-4">
                        {llmSettings.primaryProvider === 'local' ? (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-on-surface text-surface">Primary</span>
                        ) : (
                          <button type="button" onClick={() => { const next = { ...llmSettings, primaryProvider: 'local' as const }; setLlmSettings(next); debouncedSave('llm_settings', next); }} className="text-[10px] font-semibold text-on-surface-variant hover:text-primary">Set primary</button>
                        )}
                      </td>
                      <td className="py-4 pr-4">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${llmSettings.localUrl ? 'bg-emerald-500/10 text-emerald-700' : 'bg-surface-container text-on-surface-variant'}`}>
                          {llmSettings.localUrl ? 'Configured' : 'Not set'}
                        </span>
                      </td>
                      <td className="py-4">
                        <div className={`${providerConfigWrapClass} space-y-2`}>
                          <input type="text" value={llmSettings.localUrl ?? ''} onChange={(e) => { const next = { ...llmSettings, localUrl: e.target.value }; setLlmSettings(next); debouncedSave('llm_settings', next); }} className={providerConfigClass} placeholder="http://localhost:11434" />
                          <input type="text" value={llmSettings.localModel ?? ''} onChange={(e) => { const next = { ...llmSettings, localModel: e.target.value }; setLlmSettings(next); debouncedSave('llm_settings', next); }} className={providerConfigClass} placeholder="llama3" />
                        </div>
                      </td>
                    </tr>

                    {/* Gemini */}
                    <tr className="align-top">
                      <td className="py-4 pr-4 w-40">
                        <p className="text-sm font-semibold text-on-surface">Google Gemini</p>
                      </td>
                      <td className="py-4 pr-4">
                        {llmSettings.primaryProvider === 'gemini' ? (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-on-surface text-surface">Primary</span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => { const next = { ...llmSettings, primaryProvider: 'gemini' as const }; setLlmSettings(next); debouncedSave('llm_settings', next); }}
                            className="text-[10px] font-semibold text-on-surface-variant hover:text-primary"
                          >
                            Set primary
                          </button>
                        )}
                      </td>
                      <td className="py-4 pr-4">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${(llmSettings.geminiApiKey || envStatus.gemini) ? 'bg-emerald-500/10 text-emerald-700' : 'bg-surface-container text-on-surface-variant'}`}>
                          {(llmSettings.geminiApiKey || envStatus.gemini) ? 'Connected' : 'Not set'}
                        </span>
                      </td>
                      <td className="py-4">
                        {envStatus.gemini ? (
                          <div className={`${providerConfigWrapClass} text-xs px-3 py-2.5 rounded-xl bg-primary/10 border border-primary/15 text-primary font-medium flex items-center gap-2`}>
                            <span className="material-symbols-outlined text-sm">lock</span>
                            Doppler / env
                          </div>
                        ) : (
                          <input
                            type="password"
                            value={llmSettings.geminiApiKey ?? ''}
                            onChange={(e) => { const next = { ...llmSettings, geminiApiKey: e.target.value }; setLlmSettings(next); debouncedSave('llm_settings', next); }}
                            className={providerConfigClass}
                            placeholder="AIzaSy..."
                          />
                        )}
                      </td>
                    </tr>

                    {/* Claude */}
                    <tr className="align-top">
                      <td className="py-4 pr-4 w-40">
                        <p className="text-sm font-semibold text-on-surface">Anthropic Claude</p>
                      </td>
                      <td className="py-4 pr-4">
                        {llmSettings.primaryProvider === 'claude' ? (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-on-surface text-surface">Primary</span>
                        ) : (
                          <button type="button" onClick={() => { const next = { ...llmSettings, primaryProvider: 'claude' as const }; setLlmSettings(next); debouncedSave('llm_settings', next); }} className="text-[10px] font-semibold text-on-surface-variant hover:text-primary">Set primary</button>
                        )}
                      </td>
                      <td className="py-4 pr-4">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${(llmSettings.claudeApiKey || envStatus.claude) ? 'bg-emerald-500/10 text-emerald-700' : 'bg-surface-container text-on-surface-variant'}`}>
                          {(llmSettings.claudeApiKey || envStatus.claude) ? 'Connected' : 'Not set'}
                        </span>
                      </td>
                      <td className="py-4">
                        {envStatus.claude ? (
                          <div className={`${providerConfigWrapClass} text-xs px-3 py-2.5 rounded-xl bg-primary/10 border border-primary/15 text-primary font-medium flex items-center gap-2`}>
                            <span className="material-symbols-outlined text-sm">lock</span>
                            Doppler / env
                          </div>
                        ) : (
                          <input type="password" value={llmSettings.claudeApiKey ?? ''} onChange={(e) => { const next = { ...llmSettings, claudeApiKey: e.target.value }; setLlmSettings(next); debouncedSave('llm_settings', next); }} className={providerConfigClass} placeholder="sk-ant-api03..." />
                        )}
                      </td>
                    </tr>

                    {/* Perplexity */}
                    <tr className="align-top">
                      <td className="py-4 pr-4 w-40">
                        <p className="text-sm font-semibold text-on-surface">Perplexity</p>
                      </td>
                      <td className="py-4 pr-4">
                        {llmSettings.primaryProvider === 'perplexity' ? (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-on-surface text-surface">Primary</span>
                        ) : (
                          <button type="button" onClick={() => { const next = { ...llmSettings, primaryProvider: 'perplexity' as const }; setLlmSettings(next); debouncedSave('llm_settings', next); }} className="text-[10px] font-semibold text-on-surface-variant hover:text-primary">Set primary</button>
                        )}
                      </td>
                      <td className="py-4 pr-4">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${(llmSettings.perplexityApiKey || envStatus.perplexity) ? 'bg-emerald-500/10 text-emerald-700' : 'bg-surface-container text-on-surface-variant'}`}>
                          {(llmSettings.perplexityApiKey || envStatus.perplexity) ? 'Connected' : 'Not set'}
                        </span>
                      </td>
                      <td className="py-4">
                        {envStatus.perplexity ? (
                          <div className={`${providerConfigWrapClass} text-xs px-3 py-2.5 rounded-xl bg-primary/10 border border-primary/15 text-primary font-medium flex items-center gap-2`}>
                            <span className="material-symbols-outlined text-sm">lock</span>
                            Doppler / env
                          </div>
                        ) : (
                          <input type="password" value={llmSettings.perplexityApiKey ?? ''} onChange={(e) => { const next = { ...llmSettings, perplexityApiKey: e.target.value }; setLlmSettings(next); debouncedSave('llm_settings', next); }} className={providerConfigClass} placeholder="pplx-..." />
                        )}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </SettingsCard>

            {/* Data Sources — Implements FR-054, SEC-002 */}
            <SettingsCard
              label="Job boards"
              title="Data source APIs"
              description="Optional connectors for scout. Keys never sync to git."
            >
              <div className="space-y-6">
                <div className="rounded-xl border border-outline/10 bg-surface p-5 space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-on-surface">Adzuna</p>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${(apiConnections.adzunaAppId && apiConnections.adzunaAppKey) || envStatus.adzuna ? 'bg-emerald-500/10 text-emerald-700' : 'bg-surface-container text-on-surface-variant'}`}>
                      {(apiConnections.adzunaAppId && apiConnections.adzunaAppKey) || envStatus.adzuna ? 'Connected' : 'Not connected'}
                    </span>
                  </div>
                  {envStatus.adzuna ? (
                    <div className="text-xs px-4 py-2.5 rounded-xl bg-primary/10 border border-primary/15 text-primary font-medium flex items-center gap-2">
                      <span className="material-symbols-outlined text-sm">lock</span>
                      Doppler / env
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <SettingsField label="App ID">
                        <input type="text" value={apiConnections.adzunaAppId} onChange={(e) => { const next = { ...apiConnections, adzunaAppId: e.target.value }; setApiConnections(next); debouncedSave('api_connections', next); }} className={`${inputClass} font-mono text-xs`} placeholder="a1b2c3d4" />
                      </SettingsField>
                      <SettingsField label="App key">
                        <input type="password" value={apiConnections.adzunaAppKey} onChange={(e) => { const next = { ...apiConnections, adzunaAppKey: e.target.value }; setApiConnections(next); debouncedSave('api_connections', next); }} className={`${inputClass} font-mono text-xs`} placeholder="••••••••••••••••" />
                      </SettingsField>
                    </div>
                  )}
                </div>

                <div className="rounded-xl border border-outline/10 bg-surface p-5 space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-on-surface">TheirStack</p>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${apiConnections.theirstackApiKey ? 'bg-emerald-500/10 text-emerald-700' : 'bg-surface-container text-on-surface-variant'}`}>
                      {apiConnections.theirstackApiKey ? 'Connected' : 'Not connected'}
                    </span>
                  </div>
                  <SettingsField label="API key">
                    <input type="password" value={apiConnections.theirstackApiKey ?? ''} onChange={(e) => { const next = { ...apiConnections, theirstackApiKey: e.target.value }; setApiConnections(next); debouncedSave('api_connections', next); }} className={`${inputClass} font-mono text-xs`} placeholder="••••••••••••••••" />
                  </SettingsField>
                </div>
              </div>
            </SettingsCard>
          </>
        )}

        {/* Analytics Tab */}
        {activeTab === 'Analytics' && (
          <>
            {stats ? (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-surface-container-lowest border border-outline/8 p-5 rounded-2xl shadow-sm">
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider mb-1">Total leads</p>
                    <p className="text-3xl font-headline font-extrabold text-primary">{stats.total}</p>
                  </div>
                  <div className="bg-surface-container-lowest border border-outline/8 p-5 rounded-2xl shadow-sm">
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider mb-1">Rejected</p>
                    <p className="text-3xl font-headline font-extrabold text-error">{stats.byRejectionType.find(t => t.rejection_type === 'Rejected')?.count || 0}</p>
                  </div>
                  <div className="bg-surface-container-lowest border border-outline/8 p-5 rounded-2xl shadow-sm">
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider mb-1">Ghosted</p>
                    <p className="text-3xl font-headline font-extrabold text-on-surface-variant">{stats.byRejectionType.find(t => t.rejection_type === 'Ghosted')?.count || 0}</p>
                  </div>
                  <div className="bg-surface-container-lowest border border-outline/8 p-5 rounded-2xl shadow-sm">
                    <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider mb-1">Active</p>
                    <p className="text-3xl font-headline font-extrabold text-primary">{
                      (stats.byStatus.find(s => s.status === 'Backlog')?.count || 0) +
                      (stats.byStatus.find(s => s.status === 'Drafted')?.count || 0)
                    }</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <SettingsCard label="Pipeline" title="By status">
                    <div className="space-y-3">
                      {stats.byStatus.map((row, i) => (
                        <div key={i} className="flex justify-between items-center text-sm py-1">
                          <span className="text-on-surface-variant">{row.status}</span>
                          <span className="font-semibold text-on-surface bg-surface px-2.5 py-1 rounded-lg border border-outline/10">{row.count}</span>
                        </div>
                      ))}
                    </div>
                  </SettingsCard>
                  <SettingsCard label="Outcomes" title="By rejection stage">
                    <div className="space-y-3">
                      {stats.byRejectionStage.map((row, i) => (
                        <div key={i} className="flex justify-between items-center text-sm py-1">
                          <span className="text-on-surface-variant">{row.rejection_stage || 'N/A'}</span>
                          <span className="font-semibold text-on-surface bg-surface px-2.5 py-1 rounded-lg border border-outline/10">{row.count}</span>
                        </div>
                      ))}
                      {stats.byRejectionStage.length === 0 && (
                        <p className="text-sm italic text-on-surface-variant py-2">No rejection telemetry yet.</p>
                      )}
                    </div>
                  </SettingsCard>
                </div>
              </>
            ) : (
              <div className="p-12 bg-surface-container-lowest border border-outline/8 rounded-2xl text-center text-sm text-on-surface-variant animate-pulse">
                Loading pipeline statistics...
              </div>
            )}
          </>
        )}
      </div>
      
      {/* Floating Feedback Toast (Implements user request for immediate visual save confirmation) */}
      <div className={`fixed bottom-8 right-8 flex items-center gap-3 bg-surface-container-highest text-on-surface border border-outline-variant/20 px-5 py-3 rounded-2xl shadow-2xl transition-all duration-300 z-50 transform ${
        saveStatus === 'saved' ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0 pointer-events-none'
      }`}>
        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
          <span className="material-symbols-outlined text-primary text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
        </div>
        <div>
          <p className="text-xs font-bold">Changes Synchronized</p>
          <p className="text-[10px] text-on-surface-variant">Stored securely in your local SQLite database.</p>
        </div>
      </div>
      
      {saveStatus === 'saving' && (
        <div className="fixed bottom-8 right-8 flex items-center gap-3 bg-surface-container-highest text-on-surface border border-outline-variant/20 px-5 py-3 rounded-2xl shadow-xl z-50">
          <div className="w-5 h-5 border-2 border-secondary border-t-transparent rounded-full animate-spin" />
          <p className="text-xs font-bold text-secondary">Autosaving...</p>
        </div>
      )}
    </div>
  );
};

export default SettingsView;
